// Keep in sync with DEFAULT_DELIVERY_DAYS in selling/delivery_date.py.
const DEFAULT_DELIVERY_DAYS = 7;

frappe.ui.form.on("Sales Order", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.delivery_date) {
			const base = frm.doc.transaction_date || frappe.datetime.get_today();
			frm.set_value("delivery_date", frappe.datetime.add_days(base, DEFAULT_DELIVERY_DAYS));
		}
	},

	refresh(frm) {
		frm.trigger("show_customer_credit");
		frm.trigger("setup_encargo_ui");
		frm.trigger("setup_item_search");
		frm.trigger("show_encargo_materialization");
		frm.trigger("show_line_supply");
	},

	// Spec 017 §12.2: Continuar confirms the figure; the server rechecks it before reserving.
	before_submit(frm) {
		frm.doc.custom_shopper_qty_confirmed = "";
		return new Promise((resolve) => {
			frappe.call({
				method: "erpn_custom.encargo.supply.shopper_preview",
				type: "POST",
				args: {
					items: (frm.doc.items || []).map((row) => ({
						name: row.name,
						idx: row.idx,
						item_code: row.item_code,
						warehouse: row.warehouse,
						qty: row.qty,
					})),
					set_warehouse: frm.doc.set_warehouse || null,
				},
				callback(r) {
					const data = r.message || { total: 0, lines: [] };
					if (!data.total) {
						frm.doc.custom_shopper_qty_confirmed = "0";
						resolve();
						return;
					}
					confirm_shopper_dialog(frm, data, resolve);
				},
				error() {
					frappe.validated = false;
					resolve();
				},
			});
		});
	},

	show_line_supply(frm) {
		const wrapper = frm.fields_dict.items?.$wrapper;
		if (!wrapper) {
			return;
		}
		wrapper.find(".erpn-line-supply").remove();
		if (frm.doc.docstatus === 0) {
			return;
		}
		frappe.call({
			method: "erpn_custom.encargo.supply.order_supply",
			args: { sales_order: frm.doc.name },
			callback(r) {
				const lines = (r.message || {}).lines || [];
				if (!lines.length) {
					return;
				}
				const box = $('<div class="erpn-line-supply small" style="margin-top: 8px;"></div>');
				box.append($("<div class='text-muted'>").text(__("Abastecimiento por línea")));
				lines.forEach((line) => {
					box.append(
						$("<div>").text(
							__("fila {0}: {1} x{2} · {3}", [
								line.idx,
								line.item_code,
								format_number(line.qty, null, 0),
								line.summary,
							])
						)
					);
				});
				wrapper.append(box);
			},
		});
	},

	show_encargo_materialization(frm) {
		const wrapper = frm.fields_dict.items?.$wrapper;
		if (!wrapper) {
			return;
		}
		wrapper.find(".erpn-encargo-materialization").remove();
		if (frm.doc.docstatus !== 1) {
			return;
		}
		frappe.call({
			method: "erpn_custom.encargo.materialization.order_summary",
			args: { sales_order: frm.doc.name },
			callback(r) {
				const rows = r.message || [];
				if (!rows.length) {
					return;
				}
				const box = $('<div class="erpn-encargo-materialization small" style="margin-top: 8px;"></div>');
				box.append($("<div class='text-muted'>").text(__("Encargos por llegar (Spec 019)")));
				rows.forEach((enc) => {
					const lines = (enc.lines || [])
						.map((l) => __("fila {0}: {1} x{2}", [l.idx, l.item_code, format_number(l.qty, null, 0)]))
						.join(" · ");
					const line = $("<div>")
						.append(
							$("<a>")
								.attr("href", `/app/encargo/${encodeURIComponent(enc.name)}`)
								.text(enc.name)
						)
						.append(
							document.createTextNode(
								" · " +
									__("Pedido {0} · Materializado {1} · Pendiente {2}", [
										format_number(enc.requested_qty, null, 0),
										format_number(enc.materialized_qty, null, 0),
										format_number(enc.pending_materialize_qty, null, 0),
									]) +
									(lines ? " · " + lines : "")
							)
						);
					box.append(line);
				});
				wrapper.append(box);
			},
		});
	},

	setup_item_search(frm) {
		frm.remove_custom_button(__("Buscar producto"));
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Buscar producto"), () => open_item_search_dialog(frm));
		}
	},

	customer(frm) {
		frm.trigger("show_customer_credit");
	},

	setup_encargo_ui(frm) {
		// Hide native reserve-stock UI; Spec 013 drives partial SRE via hooks.
		frm.set_df_property("reserve_stock", "hidden", 1);
		if (frm.fields_dict.items?.grid) {
			frm.fields_dict.items.grid.update_docfield_property("reserve_stock", "hidden", 1);
		}

		frm.remove_custom_button(__("Agregar Encargo"));
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			frm.add_custom_button(__("Agregar Encargo"), () => open_encargo_dialog(frm));
		}
	},

	show_customer_credit(frm) {
		if (!frm.doc.customer || frm.doc.docstatus === 2) {
			return;
		}
		frappe.call({
			method: "erpn_custom.chile.sales_order_credit.credit_summary",
			args: {
				sales_order: frm.doc.name,
				customer: frm.doc.customer,
			},
			callback(r) {
				const data = r.message;
				if (!data) {
					return;
				}
				frm.dashboard.set_headline(
					__(
						"Saldo a favor {0} · Total {1} · Anticipo {2} · Pendiente {3}",
						[
							format_money(data.available, frm.doc.currency),
							format_money(data.grand_total, frm.doc.currency),
							format_money(data.advance_paid, frm.doc.currency),
							format_money(data.pending, frm.doc.currency),
						]
					)
				);
				frm.remove_custom_button(__("Aplicar saldo a favor"));
				if (frm.doc.docstatus < 2 && data.available > 0 && data.pending > 0 && !frm.is_new()) {
					frm.add_custom_button(__("Aplicar saldo a favor"), () => apply_credit_dialog(frm, data));
				}
			},
			error() {
				// Roles fuera de ALLOWED u OV sin crédito: no bloquear el formulario.
			},
		});
	},
});

frappe.ui.form.on("Sales Order Item", {
	form_render(frm, cdt, cdn) {
		show_view_encargo_button(frm, cdn);
	},
});

function show_view_encargo_button(frm, cdn) {
	const grid_row = frm.fields_dict.items.grid.grid_rows_by_docname[cdn];
	// Not inside .row-actions: Frappe hides it once the order is submitted.
	const toolbar = grid_row?.grid_form?.wrapper?.find(".grid-form-heading .grid-header-toolbar");
	if (!toolbar?.length) {
		return;
	}
	toolbar.find(".erpn-view-encargo").remove();
	const encargo = grid_row.doc.custom_encargo || grid_row.doc.custom_encargo_origin;
	if (!encargo) {
		return;
	}
	$('<button class="btn btn-primary btn-sm pull-right erpn-view-encargo"></button>')
		.text(__("Ver Encargo {0}", [encargo]))
		.appendTo(toolbar)
		.on("click", () => {
			frappe.set_route("Form", "Encargo", encargo);
			// The heading click would collapse the row.
			return false;
		});
}

function confirm_shopper_dialog(frm, data, resolve) {
	let decided = false;
	const finish = (proceed) => {
		if (decided) {
			return;
		}
		decided = true;
		if (proceed) {
			frm.doc.custom_shopper_qty_confirmed = String(data.total);
		} else {
			frappe.validated = false;
		}
		dialog.hide();
		resolve();
	};
	const rows = data.lines
		.map(
			(line) =>
				`<li>${frappe.utils.escape_html(
					__("fila {0}: {1} · {2} de {3} al Shopper", [
						line.idx,
						line.item_code,
						format_number(line.shopper_qty, null, 0),
						format_number(line.qty, null, 0),
					])
				)}</li>`
		)
		.join("");
	const dialog = new frappe.ui.Dialog({
		title: __("Confirmar envío al Shopper"),
		fields: [
			{
				fieldtype: "HTML",
				options: `<p><b>${frappe.utils.escape_html(
					__("Esta Orden de Venta enviará {0} unidad(es) al Shopper por falta de stock.", [
						format_number(data.total, null, 0),
					])
				)}</b></p><ul>${rows}</ul>`,
			},
		],
		primary_action_label: __("Continuar"),
		primary_action: () => finish(true),
		secondary_action_label: __("Cancelar"),
		secondary_action: () => finish(false),
	});
	dialog.onhide = () => finish(false);
	dialog.show();
}

function format_money(value, currency) {
	const code = currency || "CLP";
	// CLP has no decimals in practice.
	const amount = code === "CLP" ? format_number(Math.round(value || 0), "#.###", 0) : format_number(value || 0, null, 2);
	return `${code}$${amount}`;
}

function apply_credit_dialog(frm, data) {
	const proposed = data.proposed || 0;
	const dialog = new frappe.ui.Dialog({
		title: __("Aplicar saldo a favor"),
		fields: [
			{
				fieldname: "available",
				label: __("Saldo a favor disponible del cliente"),
				fieldtype: "Currency",
				default: data.available,
				read_only: 1,
				options: frm.doc.currency,
			},
			{
				fieldname: "pending",
				label: __("Saldo pendiente de esta Nota de Venta"),
				fieldtype: "Currency",
				default: data.pending,
				read_only: 1,
				options: frm.doc.currency,
			},
			{
				fieldname: "amount",
				label: __("Monto a aplicar"),
				fieldtype: "Currency",
				default: proposed,
				reqd: 1,
				options: frm.doc.currency,
			},
		],
		primary_action_label: __("Confirmar"),
		primary_action(values) {
			dialog.hide();
			frappe.call({
				method: "erpn_custom.chile.sales_order_credit.apply_credit",
				args: {
					sales_order: frm.doc.name,
					amount: values.amount,
				},
				freeze: true,
				freeze_message: __("Aplicando saldo a favor"),
				callback() {
					frm.reload_doc();
				},
			});
		},
	});
	dialog.show();
}

// preset: {description, brand, item_group, custom_departamento, attributes} from the item search.
function open_encargo_dialog(frm, preset) {
	let pasted_b64 = null;
	let pasted_name = null;

	const dialog = new frappe.ui.Dialog({
		title: __("Agregar Encargo"),
		fields: [
			{
				fieldname: "copy_from",
				label: __("Copiar de un producto similar"),
				fieldtype: "Link",
				options: "Item",
				description: __("Copia marca, grupo, departamento, atributos y descripción. El código de barras queda en blanco."),
				onchange: () => copy_from_item(dialog.get_value("copy_from")),
			},
			{ fieldname: "description", label: __("Descripción"), fieldtype: "Small Text", reqd: 1 },
			{
				fieldname: "brand",
				label: __("Marca"),
				fieldtype: "Link",
				options: "Brand",
				reqd: 1,
				onchange() {
					dialog.set_value("supplier", null);
				},
			},
			{
				fieldname: "supplier",
				label: __("Proveedor sugerido"),
				fieldtype: "Link",
				options: "Supplier",
				reqd: 0,
				get_query() {
					return {
						query: "erpn_custom.encargo.api.suppliers_for_brand_query",
						filters: { brand: dialog.get_value("brand") },
					};
				},
			},
			{
				fieldname: "item_group",
				label: __("Grupo de producto"),
				fieldtype: "Link",
				options: "Item Group",
				reqd: 1,
				get_query: () => ({ filters: { is_group: 0 } }),
				onchange: () => load_classification(),
			},
			{ fieldname: "custom_familia", label: __("Familia"), fieldtype: "Data", read_only: 1 },
			{
				fieldname: "custom_departamento",
				label: __("Departamento"),
				fieldtype: "Select",
				onchange: () => load_classification(),
			},
			...SEARCH_ATTRIBUTE_FIELDS.map(([fieldname, label]) => ({
				fieldname,
				label: __(label),
				fieldtype: "Autocomplete",
				hidden: 1,
				onchange: () => reject_outside_list(fieldname),
			})),
			{ fieldname: "qty", label: __("Cantidad"), fieldtype: "Float", default: 1, reqd: 1 },
			{
				fieldname: "rate",
				label: __("Precio de venta"),
				fieldtype: "Currency",
				options: frm.doc.currency,
			},
			{ fieldname: "model", label: __("Modelo"), fieldtype: "Data" },
			{ fieldname: "reference_url", label: __("URL"), fieldtype: "Data" },
			{ fieldname: "notes", label: __("Observaciones"), fieldtype: "Small Text" },
			{
				fieldname: "image_hint",
				fieldtype: "HTML",
				options:
					"<p class='text-muted'>" +
					__("Pegue una imagen (Ctrl+V) o adjunte un archivo.") +
					"</p>",
			},
			{ fieldname: "image", label: __("Imagen"), fieldtype: "Attach Image" },
		],
		primary_action_label: __("Crear Encargo"),
		primary_action(values) {
			const args = {
				sales_order: frm.doc.name,
				description: values.description,
				brand: values.brand,
				supplier: values.supplier,
				qty: values.qty,
				rate: values.rate,
				model: values.model,
				reference_url: values.reference_url,
				notes: values.notes,
				item_group: values.item_group,
				custom_departamento: values.custom_departamento,
				attributes: {},
			};
			SEARCH_ATTRIBUTE_FIELDS.forEach(([fieldname]) => {
				if (values[fieldname]) {
					args.attributes[fieldname] = values[fieldname];
				}
			});
			if (pasted_b64 && pasted_name) {
				args.image_filename = pasted_name;
				args.image_b64 = pasted_b64;
			} else if (values.image) {
				args.reference_image = values.image;
			}
			dialog.hide();
			frappe.call({
				method: "erpn_custom.encargo.api.create_unknown_encargo",
				args,
				freeze: true,
				freeze_message: __("Creando Encargo"),
				callback() {
					frm.reload_doc();
				},
			});
		},
	});

	let attribute_options = {};

	function load_classification() {
		return frappe
			.call({
				method: "erpn_custom.catalog.search.get_search_filters",
				args: {
					item_group: dialog.get_value("item_group"),
					departamento: dialog.get_value("custom_departamento"),
				},
			})
			.then((r) => {
				const data = r.message || {};
				if (!dialog.fields_dict.custom_departamento.df.options) {
					dialog.set_df_property("custom_departamento", "options", [""].concat(data.departamentos || []));
				}
				dialog.set_value("custom_familia", data.familia || "");
				attribute_options = data.options || {};
				SEARCH_ATTRIBUTE_FIELDS.forEach(([fieldname]) => {
					const values = attribute_options[fieldname];
					dialog.set_df_property(fieldname, "hidden", values ? 0 : 1);
					dialog.fields_dict[fieldname].set_data(values || []);
					reject_outside_list(fieldname);
				});
			});
	}

	function reject_outside_list(fieldname) {
		const value = dialog.get_value(fieldname);
		if (!value || (attribute_options[fieldname] || []).includes(value)) {
			return;
		}
		erpn_custom.classification.alert_outside_list(dialog.fields_dict[fieldname].df.label, value);
		dialog.set_value(fieldname, "");
	}

	SEARCH_ATTRIBUTE_FIELDS.forEach(([fieldname]) => {
		erpn_custom.classification.warn_when_discarded(
			dialog.fields_dict[fieldname],
			() => attribute_options[fieldname] || []
		);
	});

	async function copy_from_item(item_code) {
		if (!item_code) {
			return;
		}
		const fields = ["item_name", "brand", "item_group", "custom_departamento"].concat(
			SEARCH_ATTRIBUTE_FIELDS.map(([fieldname]) => fieldname)
		);
		const item = (await frappe.db.get_value("Item", item_code, fields)).message || {};
		await dialog.set_values({
			description: item.item_name || "",
			brand: item.brand || "",
			item_group: item.item_group || "",
			custom_departamento: item.custom_departamento || "",
		});
		await load_classification();
		const attributes = {};
		SEARCH_ATTRIBUTE_FIELDS.forEach(([fieldname]) => {
			attributes[fieldname] = item[fieldname] || "";
		});
		await dialog.set_values(attributes);
	}

	async function apply_preset() {
		await load_classification();
		if (!preset) {
			return;
		}
		const is_group = preset.item_group
			? (await frappe.db.get_value("Item Group", preset.item_group, "is_group")).message?.is_group
			: 0;
		await dialog.set_values({
			description: preset.description || "",
			brand: preset.brand || "",
			item_group: is_group ? "" : preset.item_group || "",
			custom_departamento: preset.custom_departamento || "",
		});
		await load_classification();
		await dialog.set_values(preset.attributes || {});
	}

	apply_preset();

	dialog.$wrapper.on("paste", (e) => {
		const items = e.originalEvent && e.originalEvent.clipboardData && e.originalEvent.clipboardData.items;
		if (!items) {
			return;
		}
		for (const item of items) {
			if (!item.type || !item.type.startsWith("image/")) {
				continue;
			}
			e.preventDefault();
			const file = item.getAsFile();
			if (!file) {
				return;
			}
			const reader = new FileReader();
			reader.onload = () => {
				const data_url = String(reader.result);
				pasted_b64 = data_url.split(",")[1] || "";
				pasted_name = file.name || "referencia.png";
				dialog.fields_dict.image_hint.$wrapper.html(
					$("<div>")
						.append($("<p class='text-muted'>").text(__("Imagen pegada (se guardará al crear el Encargo):")))
						.append(
							$("<img>").attr("src", data_url).css({
								"max-width": "100%",
								"max-height": "240px",
								"border-radius": "6px",
								border: "1px solid var(--border-color)",
							})
						)
				);
			};
			reader.readAsDataURL(file);
			return;
		}
	});

	dialog.show();
}

const SEARCH_ATTRIBUTE_FIELDS = [
	["custom_color", "Color"],
	["custom_talla", "Talla"],
	["custom_tamano", "Tamaño"],
	["custom_taco", "Taco"],
	["custom_manga", "Manga"],
	["custom_tono", "Tono"],
	["custom_contenido", "Contenido"],
];

function open_item_search_dialog(frm) {
	const order_warehouse =
		frm.doc.set_warehouse || (frm.doc.items || []).map((row) => row.warehouse).find(Boolean) || null;
	let request = 0;

	const dialog = new frappe.ui.Dialog({
		title: __("Buscar producto"),
		size: "extra-large",
		fields: [
			{ fieldname: "text", label: __("Código, nombre o SKU"), fieldtype: "Data", onchange: () => run_search() },
			{
				fieldname: "item_group",
				label: __("Grupo / Familia / Tipo"),
				fieldtype: "Link",
				options: "Item Group",
				onchange: () => refresh_filters(),
			},
			{ fieldname: "brand", label: __("Marca"), fieldtype: "Link", options: "Brand", onchange: () => run_search() },
			{ fieldtype: "Column Break" },
			{ fieldname: "departamento", label: __("Departamento"), fieldtype: "Select", onchange: () => refresh_filters() },
			{
				fieldname: "warehouse",
				label: __("Bodega"),
				fieldtype: "Link",
				options: "Warehouse",
				default: order_warehouse,
				get_query: () => ({ filters: { is_group: 0, company: frm.doc.company } }),
				onchange: () => run_search(),
			},
			{ fieldtype: "Column Break" },
			...SEARCH_ATTRIBUTE_FIELDS.map(([fieldname, label]) => ({
				fieldname,
				label: __(label),
				fieldtype: "Select",
				hidden: 1,
				onchange: () => run_search(),
			})),
			{ fieldtype: "Section Break" },
			{ fieldname: "results", fieldtype: "HTML" },
		],
	});

	const run_search = frappe.utils.debounce(search, 300);

	function refresh_filters() {
		frappe.call({
			method: "erpn_custom.catalog.search.get_search_filters",
			args: {
				item_group: dialog.get_value("item_group"),
				departamento: dialog.get_value("departamento"),
			},
			callback(r) {
				const data = r.message || {};
				if (!dialog.fields_dict.departamento.df.options) {
					dialog.set_df_property("departamento", "options", [""].concat(data.departamentos || []));
				}
				const options = data.options || {};
				SEARCH_ATTRIBUTE_FIELDS.forEach(([fieldname]) => {
					const values = options[fieldname];
					const current = dialog.get_value(fieldname);
					dialog.set_df_property(fieldname, "hidden", values ? 0 : 1);
					dialog.set_df_property(fieldname, "options", [""].concat(values || []));
					if (current && !(values || []).includes(current)) {
						dialog.set_value(fieldname, "");
					}
				});
				run_search();
			},
		});
	}

	function search() {
		const values = dialog.get_values(true) || {};
		const attributes = {};
		SEARCH_ATTRIBUTE_FIELDS.forEach(([fieldname]) => {
			if (values[fieldname]) {
				attributes[fieldname] = values[fieldname];
			}
		});
		const current = ++request;
		frappe.call({
			method: "erpn_custom.catalog.search.search_items",
			args: {
				item_group: values.item_group,
				brand: values.brand,
				departamento: values.departamento,
				text: values.text,
				warehouse: values.warehouse,
				attributes,
			},
			callback(r) {
				if (current === request && r.message) {
					render(r.message);
				}
			},
		});
	}

	function open_encargo_from_filters() {
		if (frm.is_new()) {
			frappe.msgprint(__("Guarda la orden de venta antes de agregar un Encargo."));
			return;
		}
		const values = dialog.get_values(true) || {};
		const attributes = {};
		SEARCH_ATTRIBUTE_FIELDS.forEach(([fieldname]) => {
			if (values[fieldname]) {
				attributes[fieldname] = values[fieldname];
			}
		});
		dialog.hide();
		open_encargo_dialog(frm, {
			description: values.text,
			brand: values.brand,
			item_group: values.item_group,
			custom_departamento: values.departamento,
			attributes,
		});
	}

	function encargo_button() {
		return $("<button class='btn btn-sm btn-default'>")
			.text(__("Crear Encargo con estos filtros"))
			.on("click", open_encargo_from_filters);
	}

	function render(data) {
		const wrapper = dialog.fields_dict.results.$wrapper.empty();
		if (!data.items.length) {
			wrapper.append($("<p class='text-muted'>").text(__("Sin resultados.")), encargo_button());
			return;
		}
		const headers = [
			__("Código"),
			__("Producto"),
			__("Marca"),
			__("Tipo"),
			__("Atributos"),
			data.warehouse ? __("Disponible en {0}", [data.warehouse]) : __("Disponible"),
			__("Total"),
			"",
		];
		const table = $("<table class='table table-bordered table-sm'>");
		table.append($("<thead>").append($("<tr>").append(headers.map((h) => $("<th>").text(h)))));
		const body = $("<tbody>").appendTo(table);
		data.items.forEach((item) => {
			const attributes = [item.custom_departamento, ...SEARCH_ATTRIBUTE_FIELDS.map(([f]) => item[f])]
				.filter(Boolean)
				.join(" / ");
			const add = $("<button class='btn btn-xs btn-primary'>")
				.text(__("Agregar"))
				.on("click", () => add_item(item));
			body.append(
				$("<tr>").append(
					$("<td>").text(item.name),
					$("<td>").text(item.item_name || ""),
					$("<td>").text(item.brand || ""),
					$("<td>").text(item.item_group || ""),
					$("<td>").text(attributes),
					$("<td class='text-right'>").text(
						item.stock_bodega == null ? "—" : format_number(item.stock_bodega, null, 0)
					),
					$("<td class='text-right'>").text(format_number(item.stock_total, null, 0)),
					$("<td>").append(add)
				)
			);
		});
		wrapper.append($("<div style='max-height: 420px; overflow-y: auto'>").append(table));
		if (data.truncated) {
			wrapper.append(
				$("<p class='text-muted'>").text(
					__("Se muestran los primeros {0}; agrega filtros para acotar.", [data.limit])
				)
			);
		}
		wrapper.append(
			$("<p class='text-muted'>").text(__("¿No está la talla o el color que pide la clienta?")),
			encargo_button()
		);
	}

	async function add_item(item) {
		const warehouse = dialog.get_value("warehouse");
		const row = (frm.doc.items || []).find((r) => !r.item_code) || frm.add_child("items");
		await frappe.model.set_value(row.doctype, row.name, "item_code", item.name);
		// get_item_details may replace the warehouse; apply the chosen one once it returns.
		frappe.after_ajax(() => {
			if (warehouse) {
				frappe.model.set_value(row.doctype, row.name, "warehouse", warehouse);
			}
			frm.refresh_field("items");
		});
		frappe.show_alert({ message: __("{0} agregado", [item.name]), indicator: "green" });
	}

	dialog.show();
	refresh_filters();
}
