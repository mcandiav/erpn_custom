frappe.ui.form.on("Encargo", {
	refresh(frm) {
		bind_reference_image_paste(frm);
		render_reference_image_preview(frm);
		render_reference_url_link(frm);
		render_purchase_images_preview(frm);
		show_customer_contact_alert(frm);
		add_reception_button(frm);
		add_barcode_exception_actions(frm);
		add_supply_actions(frm);
		frm.set_query("supplier", () => ({
			query: "erpn_custom.encargo.api.suppliers_for_brand_query",
			filters: { brand: frm.doc.brand },
		}));
	},

	brand(frm) {
		if (frm.doc.supplier) {
			frm.set_value("supplier", null);
		}
	},

	reference_image(frm) {
		render_reference_image_preview(frm);
	},

	reference_url(frm) {
		render_reference_url_link(frm);
	},
});

// Reference URL is free text: without a scheme the browser would resolve it against this site.
function reference_href(value) {
	const text = String(value || "").trim();
	if (/^https?:\/\//i.test(text)) {
		return text;
	}
	if (/^[^\s\/]+\.[a-z]{2,}(\/\S*)?$/i.test(text)) {
		return "https://" + text;
	}
	return null;
}

function render_reference_url_link(frm) {
	const href = reference_href(frm.doc.reference_url);
	const description = href
		? `<a href="${frappe.utils.escape_html(href)}" target="_blank" rel="noopener">${__("Abrir enlace")} ↗</a>`
		: "";
	frm.set_df_property("reference_url", "description", description);
}

function render_reference_image_preview(frm) {
	const field = frm.fields_dict.reference_image_preview;
	if (!field) {
		return;
	}
	const url = frm.doc.reference_image;
	if (!url) {
		field.$wrapper.empty();
		return;
	}
	const src = frappe.utils.escape_html(url);
	field.$wrapper.html(
		`<a href="${src}" target="_blank" rel="noopener" title="${__("Abrir imagen")}">` +
			`<img src="${src}" alt="${__("Imagen de referencia")}" ` +
			`style="width: 100%; height: auto; border-radius: var(--border-radius-md); margin-top: var(--margin-sm);">` +
			`</a>`
	);
}

function render_purchase_images_preview(frm) {
	const field = frm.fields_dict.purchase_images_preview;
	if (!field) {
		return;
	}
	const images = [
		[frm.doc.purchase_product_image, __("Foto del producto")],
		[frm.doc.purchase_label_image, __("Foto de etiqueta")],
	].filter(([url]) => url);
	if (!images.length) {
		field.$wrapper.empty();
		return;
	}
	field.$wrapper.html(
		`<div style="display: flex; gap: var(--margin-sm); margin-top: var(--margin-sm);">` +
			images
				.map(([url, label]) => {
					const src = frappe.utils.escape_html(url);
					return (
						`<a href="${src}" target="_blank" rel="noopener" title="${label}" style="flex: 1;">` +
						`<img src="${src}" alt="${label}" style="width: 100%; height: auto; border-radius: var(--border-radius-md);">` +
						`<div class="text-muted small">${label}</div></a>`
					);
				})
				.join("") +
			`</div>`
	);
}

// Units are returned to stock one by one from the commercial reception view (Spec 018 §14).
function add_reception_button(frm) {
	const has_supply = (frm.doc.supply_events || []).length || frm.doc.purchase_status === "PURCHASED";
	if (!has_supply || !frappe.user.has_role(["ComercialFRA", "System Manager"])) {
		return;
	}
	frm.add_custom_button(__("Ver recepción"), () => {
		frappe.route_options = { search: frm.doc.name };
		frappe.set_route("recepcion-comercial");
	});
}

// Spec 017 §12.3 / Spec 020 §13: one decision per purchase event; the server checks who may resolve.
function add_barcode_exception_actions(frm) {
	if (frm.doc.status !== "Open") {
		return;
	}
	const pending = (frm.doc.supply_events || []).filter(
		(e) => e.barcode_exception_status === "PENDING_APPROVAL" && ["COMMITTED", "RECEIVED"].includes(e.status)
	);
	if (!pending.length) {
		return;
	}
	frm.dashboard.set_headline_alert(
		pending
			.map((e) =>
				__("Excepción barcode: compra de {0} u. con código {1}; el Item {2} espera {3}. Aprobar o rechazar.", [
					e.qty,
					e.purchase_barcode,
					frm.doc.expected_item,
					e.expected_barcode || __("sin código"),
				])
			)
			.join("<br>"),
		"orange"
	);
	if (!frappe.user.has_role(["ComercialFRA", "System Manager"])) {
		return;
	}
	const override = frappe.user.has_role("System Manager") && !frappe.user.has_role("ComercialFRA");
	const group = __("Excepción barcode");
	pending.forEach((e) => {
		const tag = pending.length > 1 ? ` · ${e.purchase_barcode} (${e.qty})` : "";
		const decide = (action) => erpn_barcode_decision(action, frm.doc.name, override, () => frm.reload_doc(), e.name);
		frm.add_custom_button(__("Aprobar") + tag, () => decide("approve"), group);
		frm.add_custom_button(__("Rechazar") + tag, () => decide("reject"), group);
	});
}

const SUPPLY_SOURCE_LABELS = {
	SHOPPER_PURCHASE: __("Shopper"),
	RECEPTION_DIRECT: __("Recepción directa"),
	STOCK_REALLOCATION: __("Stock"),
	MIGRATION: __("Migración"),
};

// Spec 020 §14-§16: supply figures and the commercial actions on them.
function add_supply_actions(frm) {
	if (frm.is_new() || frm.doc.status !== "Open" || !frappe.user.has_role(["ComercialFRA", "System Manager"])) {
		return;
	}
	const group = __("Abastecimiento");
	if (frm.doc.source_type === "KNOWN_ITEM" && frm.doc.pending_supply_qty > 0) {
		frm.add_custom_button(__("Asignar stock a demanda"), () => allocate_stock_dialog(frm), group);
	}
	const releasable = (frm.doc.supply_events || []).filter(
		(e) => ["COMMITTED", "RECEIVED"].includes(e.status) && e.source_type !== "RECEPTION_DIRECT"
	);
	if (releasable.length) {
		frm.add_custom_button(__("Liberar compromiso"), () => release_event_dialog(frm, releasable), group);
	}
	if (frm.doc.source_type === "KNOWN_ITEM" && frm.doc.pending_supply_qty > 0 && frappe.user.has_role("System Manager")) {
		frm.add_custom_button(__("Regularizar recepciones directas"), () => regularization_dialog(frm), group);
	}
}

function allocate_stock_dialog(frm) {
	frappe.call({
		method: "erpn_custom.encargo.supply_actions.propose_stock_allocation",
		args: { encargo: frm.doc.name },
		callback(r) {
			const data = r.message || {};
			if (!(data.warehouses || []).length) {
				frappe.msgprint(__("No hay stock libre de {0} para reservar.", [data.item]));
				return;
			}
			const fifo_note =
				data.fifo_encargo && data.fifo_encargo !== frm.doc.name
					? __("FIFO: la demanda más antigua es {0}. Solo System Manager puede saltarla, con motivo.", [data.fifo_encargo])
					: __("Esta es la demanda compatible más antigua (FIFO).");
			const dialog = new frappe.ui.Dialog({
				title: __("Asignar stock a {0}", [frm.doc.name]),
				fields: [
					{ fieldtype: "HTML", options: `<p class="text-muted">${frappe.utils.escape_html(fifo_note)}</p>` },
					{
						fieldname: "warehouse",
						fieldtype: "Select",
						label: __("Bodega"),
						reqd: 1,
						options: data.warehouses.map((w) => ({ value: w.warehouse, label: `${w.warehouse} (${w.available})` })),
						default: data.warehouses[0].warehouse,
					},
					{
						fieldname: "qty",
						fieldtype: "Int",
						label: __("Cantidad (máx. {0})", [data.pending_supply_qty]),
						reqd: 1,
						default: 1,
					},
					{ fieldname: "reason", fieldtype: "Small Text", label: __("Motivo") },
				],
				primary_action_label: __("Asignar"),
				primary_action: (values) => {
					dialog.hide();
					frappe.call({
						method: "erpn_custom.encargo.supply_actions.allocate_stock",
						type: "POST",
						args: { encargo: frm.doc.name, warehouse: values.warehouse, qty: values.qty, reason: values.reason || null },
						freeze: true,
						callback: () => frm.reload_doc(),
					});
				},
			});
			dialog.show();
		},
	});
}

function release_event_dialog(frm, events) {
	const label = (e) =>
		`${SUPPLY_SOURCE_LABELS[e.source_type] || e.source_type} · ${e.qty} u. · ${e.purchase_barcode || e.item || ""} · ${e.status}`;
	const dialog = new frappe.ui.Dialog({
		title: __("Liberar compromiso de {0}", [frm.doc.name]),
		fields: [
			{
				fieldtype: "HTML",
				options: `<p class="text-muted">${frappe.utils.escape_html(
					__("La cantidad en tránsito deja de abastecer esta OV. Si llega después, entra como stock normal. Las unidades ya recibidas se devuelven a stock una a una.")
				)}</p>`,
			},
			{
				fieldname: "supply_event",
				fieldtype: "Select",
				label: __("Abastecimiento"),
				reqd: 1,
				options: events.map((e) => ({ value: e.name, label: label(e) })),
				default: events[0].name,
			},
			{ fieldname: "reason", fieldtype: "Small Text", label: __("Motivo"), reqd: 1 },
		],
		primary_action_label: __("Liberar"),
		primary_action: (values) => {
			dialog.hide();
			frappe.call({
				method: "erpn_custom.encargo.supply_actions.release_supply_event",
				type: "POST",
				args: { encargo: frm.doc.name, supply_event: values.supply_event, reason: values.reason },
				freeze: true,
				callback: () => frm.reload_doc(),
			});
		},
	});
	dialog.show();
}

function regularization_dialog(frm) {
	frappe.call({
		method: "erpn_custom.encargo.supply_actions.preview_direct_regularization",
		args: { encargo: frm.doc.name },
		callback(r) {
			const data = r.message || {};
			const units = data.units || [];
			if (!units.length) {
				frappe.msgprint(__("No hay unidades recibidas como stock normal que correspondan a esta demanda."));
				return;
			}
			const esc = frappe.utils.escape_html;
			const rows = units
				.map(
					(u) =>
						`<tr><td>${esc(u.name)}</td><td>${esc(u.scanned_code || "")}</td><td>${esc(
							frappe.datetime.str_to_user(u.received_on)
						)}</td><td>${esc(u.received_by || "")}</td></tr>`
				)
				.join("");
			const dialog = new frappe.ui.Dialog({
				title: __("Regularizar {0} (vista previa)", [frm.doc.name]),
				size: "large",
				fields: [
					{
						fieldtype: "HTML",
						options: `<p>${esc(
							__("Cada unidad se traslada de Matriz a Recepción Encargos, se vincula a {0}, se reserva para {1} y queda como recepción directa. Pendiente de abastecer: {2}. Stock libre en Matriz: {3}.", [
								frm.doc.name,
								data.sales_order,
								data.pending_supply_qty,
								data.available_in_stock,
							])
						)}</p>
						<table class="table table-bordered small"><thead><tr><th>${__("Unidad")}</th><th>${__("Código")}</th><th>${__(
							"Recibida"
						)}</th><th>${__("Por")}</th></tr></thead><tbody>${rows}</tbody></table>`,
					},
				],
				primary_action_label: __("Aplicar regularización"),
				primary_action: () => {
					dialog.hide();
					frappe.call({
						method: "erpn_custom.encargo.supply_actions.apply_direct_regularization",
						type: "POST",
						args: { encargo: frm.doc.name, units: units.map((u) => u.name) },
						freeze: true,
						callback(res) {
							const out = res.message || {};
							frappe.msgprint(
								__("Regularizadas {0} unidades. Pendiente de abastecer: {1}. Cubierto: {2}.", [
									(out.units || []).length,
									out.pending_supply_qty,
									out.covered_qty,
								])
							);
							frm.reload_doc();
						},
					});
				},
			});
			dialog.show();
		},
	});
}

function show_customer_contact_alert(frm) {
	if (!frm.doc.needs_commercial_review || !(frm.doc.pending_supply_qty > 0)) {
		return;
	}
	frm.dashboard.set_headline_alert(
		__("El shopper no encontró este producto {0} veces. Contactar al cliente y decidir: seguir buscando, esperar reposición, ofrecer alternativa o cancelar.", [
			frm.doc.not_found_count,
		]),
		"red"
	);
}

function bind_reference_image_paste(frm) {
	if (frm._encargo_paste_bound) {
		return;
	}
	frm._encargo_paste_bound = true;
	$(frm.wrapper).on("paste.encargo_image", (e) => {
		const clip = e.originalEvent && e.originalEvent.clipboardData;
		const items = clip && clip.items;
		if (!items || frm.doc.docstatus === 2) {
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
			upload_reference_image(frm, file);
			return;
		}
	});
}

function upload_reference_image(frm, file) {
	if (frm.is_new()) {
		frappe.msgprint(__("Guarde el Encargo antes de pegar la imagen."));
		return;
	}
	const reader = new FileReader();
	reader.onload = () => {
		frappe.call({
			method: "erpn_custom.encargo.api.attach_reference_image",
			args: {
				encargo: frm.doc.name,
				filename: file.name || "referencia.png",
				content_b64: String(reader.result).split(",")[1] || "",
			},
			freeze: true,
			callback(r) {
				if (r.message) {
					frm.reload_doc();
				}
			},
		});
	};
	reader.readAsDataURL(file);
}
