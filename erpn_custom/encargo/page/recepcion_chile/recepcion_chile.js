const RC_METHOD = "erpn_custom.encargo.reception.";
const RC_RETURN_KEY = "erpn_custom_reception_return";
const RC_ATTRIBUTES = [
	["custom_departamento", "Departamento"],
	["custom_color", "Color"],
	["custom_talla", "Talla"],
	["custom_taco", "Taco"],
	["custom_manga", "Manga"],
	["custom_tamano", "Tamaño"],
	["custom_tono", "Tono"],
	["custom_contenido", "Contenido"],
	["model", "Modelo"],
];

frappe.pages["recepcion-chile"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Recepción Chile"),
		single_column: true,
	});
	wrapper.reception = new ReceptionStation(page);
};

frappe.pages["recepcion-chile"].on_page_show = function (wrapper) {
	if (wrapper.reception) {
		wrapper.reception.on_show();
	}
};

class ReceptionStation {
	constructor(page) {
		this.page = page;
		this.busy = false;
		this.tab = "PENDING";
		this.page.main.html(`
			<div class="rc-scan" style="margin: 8px 0 16px;">
				<label style="font-size: 18px; font-weight: 700;">${__("ESCANEAR PRODUCTO")}</label>
				<input type="text" class="form-control rc-code" autocomplete="off" spellcheck="false"
					placeholder="${__("Escanea la etiqueta o escribe el código y presiona Enter")}"
					style="font-size: 22px; height: 56px;">
			</div>
			<div class="rc-alert"></div>
			<div class="rc-case"></div>
			<div class="rc-list-box" style="margin-top: 24px;">
				<div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 8px;">
					<div class="btn-group rc-tabs">
						<button class="btn btn-default btn-sm" data-tab="PENDING">${__("Comprados no recibidos")}</button>
						<button class="btn btn-default btn-sm" data-tab="RECEIVED">${__("Apartados sin resolver")}</button>
						<button class="btn btn-default btn-sm" data-tab="RESOLVED_TO_ENC">${__("Resueltos")}</button>
					</div>
					<input type="text" class="form-control input-sm rc-search" style="max-width: 320px;"
						placeholder="${__("Buscar: ENC, OV, cliente, marca, código, lugar")}">
				</div>
				<div class="rc-list"></div>
			</div>
		`);
		this.$code = this.page.main.find(".rc-code");
		this.$alert = this.page.main.find(".rc-alert");
		this.$case = this.page.main.find(".rc-case");
		this.$list = this.page.main.find(".rc-list");
		this.$search = this.page.main.find(".rc-search");
		this.$code.on("keydown", (e) => {
			if (e.key === "Enter") {
				e.preventDefault();
				this.scan(this.$code.val());
			}
		});
		this.page.main.find(".rc-tabs button").on("click", (e) => {
			this.tab = $(e.currentTarget).data("tab");
			this.load_list();
		});
		this.$search.on("input", frappe.utils.debounce(() => this.load_list(), 300));
		this.$list.on("click", "[data-encargo]", (e) => {
			e.preventDefault();
			this.open_from_list($(e.currentTarget).data("encargo"), $(e.currentTarget).data("status"));
		});
		this.load_list();
	}

	on_show() {
		const saved = JSON.parse(localStorage.getItem(RC_RETURN_KEY) || "null");
		localStorage.removeItem(RC_RETURN_KEY);
		if (saved && saved.encargo) {
			this.open_case(saved.encargo, saved.since);
			return;
		}
		this.focus();
	}

	focus() {
		if (!this.$alert.children().length && !this.$case.children().length) {
			this.$code.prop("disabled", false).val("").trigger("focus");
		}
	}

	lock_scanner() {
		this.$code.prop("disabled", true);
	}

	reset() {
		this.$alert.empty();
		this.$case.empty();
		this.item_control = null;
		this.focus();
		this.load_list();
	}

	call(method, args, freeze_message) {
		// A pending promise on double click or server error: the follow-up never runs twice.
		if (this.busy) {
			return new Promise(() => {});
		}
		this.busy = true;
		this.page.main.find(".rc-action").prop("disabled", true);
		return new Promise((resolve) => {
			frappe.call({
				method: RC_METHOD + method,
				args,
				freeze: true,
				freeze_message,
				callback: (r) => resolve(r.message),
				always: () => {
					this.busy = false;
					this.page.main.find(".rc-action").prop("disabled", false);
				},
			});
		});
	}

	scan(value) {
		const code = String(value || "").trim();
		if (!code || this.busy) {
			return;
		}
		this.call("find_candidates", { code }, __("Buscando")).then((data) => {
			this.$case.empty();
			this.lock_scanner();
			if (data.match === "encargo") {
				this.show_detected(data.encargo, data.code, data.pending_count);
			} else if (data.match === "received") {
				this.show_already_received(data);
			} else {
				this.show_no_encargo(data);
			}
		});
	}

	show_detected(enc, code, pending_count) {
		const others =
			pending_count > 1
				? `<div style="font-size: 16px; margin-top: 8px;">${__(
						"Hay {0} Encargos comprados con este código; esta unidad va al de compra más antigua.",
						[pending_count]
				  )}</div>`
				: "";
		this.$alert.html(`
			<div class="rc-detected" role="alert" style="border: 6px solid #b45309; background: #fef3c7; color: #1f2937;
				border-radius: 12px; padding: 24px; text-align: center;">
				<div style="font-size: 28px; font-weight: 800; letter-spacing: 2px;">${__("ENCARGO DETECTADO")}</div>
				<div style="font-size: 72px; font-weight: 900; line-height: 1.1; margin: 12px 0; word-break: break-all;">
					${esc(enc.name)}</div>
				<div style="font-size: 26px; font-weight: 800;">${__("APARTAR / CLASIFICAR ENCARGO")}</div>
				<div style="font-size: 18px; margin-top: 12px;">${esc(enc.description)} · ${esc(enc.brand)}</div>
				<div style="font-size: 15px; margin-top: 4px;">${esc(enc.sales_order)} · ${esc(enc.customer)}</div>
				${others}
				<div style="font-size: 13px; margin-top: 8px; word-break: break-all;">${__("Código")}: ${esc(code)}</div>
				<div style="margin-top: 20px; display: flex; gap: 12px; justify-content: center; flex-wrap: wrap;">
					<button class="btn btn-primary btn-lg rc-action rc-received" style="font-size: 20px; padding: 12px 32px;">
						${__("APARTADO / CONTINUAR")}</button>
					<button class="btn btn-default btn-lg rc-action rc-detail">${__("VER DETALLE")}</button>
					<button class="btn btn-default btn-lg rc-action rc-not-matching">${__("NO CORRESPONDE")}</button>
				</div>
			</div>
		`);
		this.$alert.find(".rc-received").on("click", () => {
			this.call("mark_received", { encargo: enc.name, code }, __("Apartando")).then(() => {
				frappe.show_alert({ message: __("{0} apartado", [enc.name]), indicator: "green" });
				this.$alert.empty();
				this.open_case(enc.name);
			});
		});
		this.$alert.find(".rc-detail").on("click", () => open_encargo(enc.name));
		this.$alert.find(".rc-not-matching").on("click", () => this.not_matching(enc.name, code));
		this.$alert.find(".rc-received").trigger("focus");
	}

	not_matching(encargo, code) {
		frappe.prompt(
			[{ fieldname: "notes", fieldtype: "Small Text", label: __("Observación (opcional)") }],
			(values) => {
				this.call("not_matching", { encargo, code, notes: values.notes }, __("Registrando")).then(() => {
					frappe.show_alert({ message: __("Registrado: no corresponde a {0}", [encargo]), indicator: "orange" });
					this.reset();
				});
			},
			__("La unidad no corresponde a {0}", [encargo]),
			__("Registrar")
		);
	}

	show_already_received(data) {
		const rows = data.received
			.map(
				(enc) => `<tr>
					<td style="font-size: 20px; font-weight: 800;">${esc(enc.name)}</td>
					<td>${esc(enc.description)} · ${esc(enc.brand)}</td>
					<td>${__("Apartado por {0}", [esc(enc.received_by)])} · ${fmt_dt(enc.received_on)}</td>
					<td><button class="btn btn-default btn-sm rc-action" data-open="${esc(enc.name)}">${__("Conciliar")}</button></td>
				</tr>`
			)
			.join("");
		this.$alert.html(`
			<div role="alert" style="border: 4px solid #6b7280; background: #f3f4f6; border-radius: 12px; padding: 20px;">
				<div style="font-size: 24px; font-weight: 800;">${__("UNIDAD YA APARTADA")}</div>
				<div style="margin: 6px 0 12px; word-break: break-all;">${__(
					"Todos los Encargos con este código ya fueron apartados. Código: {0}",
					[esc(data.code)]
				)}</div>
				<table class="table table-bordered" style="background: #fff;"><tbody>${rows}</tbody></table>
				<button class="btn btn-default rc-action rc-close">${__("Cerrar y seguir escaneando")}</button>
			</div>
		`);
		this.$alert.find("[data-open]").on("click", (e) => {
			const name = $(e.currentTarget).data("open");
			this.$alert.empty();
			this.open_case(name);
		});
		this.$alert.find(".rc-close").on("click", () => this.reset());
	}

	show_no_encargo(data) {
		const item = data.item
			? `<div style="margin-top: 8px;">${__("Item con este código")}: <a href="/app/item/${encodeURIComponent(
					data.item
			  )}" target="_blank" rel="noopener">${esc(data.item)}</a></div>`
			: "";
		this.$alert.html(`
			<div role="alert" style="border: 4px solid #1d4ed8; background: #eff6ff; color: #1f2937; border-radius: 12px; padding: 20px;">
				<div style="font-size: 26px; font-weight: 800;">${__("PRODUCTO SIN ENCARGO IDENTIFICADO")}</div>
				<div style="font-size: 16px; margin-top: 6px; word-break: break-all;">${__("Código")}: ${esc(data.code)}</div>
				<div style="font-size: 15px; margin-top: 6px;">${__("Recepción normal de stock: no apartar.")}</div>
				${item}
				<div style="margin-top: 16px; display: flex; gap: 12px; flex-wrap: wrap;">
					<button class="btn btn-primary btn-lg rc-action rc-stock">${__("INGRESAR A STOCK NORMAL")}</button>
					<button class="btn btn-default btn-lg rc-action rc-find-item">${__("BUSCAR ITEM")}</button>
					<button class="btn btn-default btn-lg rc-action rc-find-enc">${__("BUSCAR ENCARGO MANUALMENTE")}</button>
				</div>
			</div>
		`);
		this.$alert.find(".rc-stock").on("click", () => this.reset()).trigger("focus");
		this.$alert.find(".rc-find-item").on("click", () => {
			window.open(data.item ? `/app/item/${encodeURIComponent(data.item)}` : "/app/item", "_blank");
		});
		this.$alert.find(".rc-find-enc").on("click", () => {
			this.$alert.empty();
			this.tab = "PENDING";
			this.focus();
			this.$search.val("").trigger("focus");
			this.load_list();
		});
	}

	open_from_list(encargo, status) {
		if (status === "RESOLVED_TO_ENC") {
			open_encargo(encargo);
			return;
		}
		this.call("get_case", { encargo }, __("Abriendo")).then((data) => {
			this.$alert.empty();
			this.$case.empty();
			this.lock_scanner();
			if (data.encargo.reception_status === "PENDING") {
				this.show_detected(data.encargo, data.encargo.purchase_barcode, 1);
			} else {
				this.render_case(data);
			}
			window.scrollTo({ top: 0, behavior: "smooth" });
		});
	}

	open_case(encargo, created_since) {
		this.call("get_case", { encargo }, __("Abriendo")).then((data) => {
			this.lock_scanner();
			this.render_case(data);
			if (created_since) {
				this.prefill_created_item(created_since);
			}
		});
	}

	render_case(data) {
		const enc = data.encargo;
		if (enc.reception_status !== "RECEIVED") {
			frappe.show_alert({ message: __("{0} ya no está apartado sin resolver", [enc.name]), indicator: "orange" });
			this.reset();
			return;
		}
		this.case = data;
		this.$case.html(`
			<div style="border: 2px solid #d1d5db; border-radius: 12px; padding: 16px;">
				<div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px;">
					<div style="font-size: 40px; font-weight: 900;">${esc(enc.name)}</div>
					<div>${__("Apartado por {0}", [esc(enc.received_by)])} · ${fmt_dt(enc.received_on)}</div>
				</div>
				<div class="row" style="margin-top: 12px;">
					<div class="col-md-6">${side_original(enc)}</div>
					<div class="col-md-6">${side_purchase(enc)}</div>
				</div>
				<hr>
				<h4>${__("Item real de la unidad")}</h4>
				<div class="rc-item-hint text-muted" style="margin-bottom: 6px;"></div>
				<div class="rc-item-field" style="max-width: 480px;"></div>
				<div class="rc-link-box checkbox" style="margin: 8px 0;">
					<label><input type="checkbox" class="rc-link-code">
						${__("Asociar el código comprado a este Item (identificador estable del proveedor)")}</label>
				</div>
				<button class="btn btn-default btn-sm rc-action rc-new-item">${__("Crear Item")}</button>
				<div style="margin-top: 20px; display: flex; gap: 12px; flex-wrap: wrap;">
					<button class="btn btn-success btn-lg rc-action rc-satisfies">${__("SATISFACE ENCARGO")}</button>
					<button class="btn btn-danger btn-lg rc-action rc-annul">${__("ANULAR COMPRA / ITEM A STOCK")}</button>
					<button class="btn btn-default btn-lg rc-action rc-later">${__("Dejar pendiente y seguir escaneando")}</button>
				</div>
			</div>
		`);
		this.item_control = frappe.ui.form.make_control({
			parent: this.$case.find(".rc-item-field"),
			df: {
				fieldname: "item_code",
				fieldtype: "Link",
				options: "Item",
				label: __("Item"),
				get_query: () => ({ filters: { disabled: 0, has_variants: 0 } }),
				change: () => this.update_link_box(),
			},
			render_input: true,
		});
		this.item_control.set_value(data.item || enc.expected_item || "");
		this.$case.find(".rc-item-hint").text(
			data.item
				? __("El código comprado ya identifica al Item {0}.", [data.item])
				: __("El código comprado no pertenece a ningún Item.")
		);
		this.update_link_box();
		this.$case.find(".rc-new-item").on("click", () => this.create_item(enc));
		this.$case.find(".rc-satisfies").on("click", () => this.satisfies(enc));
		this.$case.find(".rc-annul").on("click", () => this.annul(enc));
		this.$case.find(".rc-later").on("click", () => this.reset());
	}

	update_link_box() {
		const enc = this.case && this.case.encargo;
		const show = enc && enc.purchase_barcode && !this.case.item;
		this.$case.find(".rc-link-box").toggle(Boolean(show));
	}

	selected_item() {
		const item_code = this.item_control && this.item_control.get_value();
		if (!item_code) {
			frappe.msgprint(__("Elige o crea el Item real de la unidad."));
		}
		return item_code;
	}

	link_code() {
		return this.$case.find(".rc-link-code").is(":visible") && this.$case.find(".rc-link-code").is(":checked") ? 1 : 0;
	}

	satisfies(enc) {
		const item_code = this.selected_item();
		if (!item_code) {
			return;
		}
		const send = (confirm_mismatch) =>
			this.call(
				"resolve_to_encargo",
				{ encargo: enc.name, item_code, link_code: this.link_code(), confirm_mismatch },
				__("Resolviendo")
			).then(() => {
				frappe.show_alert({ message: __("{0} satisfecho con {1}", [enc.name, item_code]), indicator: "green" });
				this.reset();
			});
		if (enc.source_type === "KNOWN_ITEM" && enc.expected_item && enc.expected_item !== item_code) {
			frappe.confirm(
				__("La venta pidió {0} y elegiste {1}. ¿El producto recibido satisface el Encargo?", [
					esc(enc.expected_item),
					esc(item_code),
				]),
				() => send(1)
			);
			return;
		}
		send(0);
	}

	annul(enc) {
		const item_code = this.selected_item();
		if (!item_code) {
			return;
		}
		frappe.prompt(
			[
				{
					fieldtype: "HTML",
					options: `<p>${__(
						"La compra se anula: la unidad ({0}) pasa a stock normal y {1} vuelve a la lista del Shopper. La evidencia de la compra queda en la bitácora.",
						[esc(item_code), esc(enc.name)]
					)}</p>`,
				},
				{ fieldname: "notes", fieldtype: "Small Text", label: __("Motivo"), reqd: 1 },
			],
			(values) => {
				this.call(
					"annul_purchase",
					{ encargo: enc.name, item_code, link_code: this.link_code(), notes: values.notes },
					__("Anulando compra")
				).then(() => {
					frappe.show_alert({ message: __("Compra anulada: {0} vuelve al Shopper", [enc.name]), indicator: "orange" });
					this.reset();
				});
			},
			__("Anular compra de {0}", [enc.name]),
			__("Anular compra")
		);
	}

	create_item(enc) {
		localStorage.setItem(RC_RETURN_KEY, JSON.stringify({ encargo: enc.name, since: frappe.datetime.now_datetime() }));
		const values = { item_name: enc.description, description: enc.description, brand: enc.brand, item_group: enc.item_group };
		RC_ATTRIBUTES.forEach(([field]) => {
			if (enc[field] && field !== "model") {
				values[field] = enc[field];
			}
		});
		frappe.new_doc("Item", values);
	}

	prefill_created_item(since) {
		frappe.db
			.get_list("Item", {
				filters: { owner: frappe.session.user, creation: [">=", since] },
				fields: ["name"],
				order_by: "creation desc",
				limit: 1,
			})
			.then((rows) => {
				if (rows.length && this.item_control) {
					this.item_control.set_value(rows[0].name);
				}
			});
	}

	load_list() {
		this.page.main.find(".rc-tabs button").each((_, btn) => {
			$(btn).toggleClass("btn-primary", $(btn).data("tab") === this.tab).toggleClass("btn-default", $(btn).data("tab") !== this.tab);
		});
		frappe.call({
			method: RC_METHOD + "list_reception",
			args: { search: this.$search.val(), reception_status: this.tab },
			callback: (r) => {
				const rows = r.message || [];
				if (!rows.length) {
					this.$list.html(`<div class="text-muted">${__("Sin Encargos en esta lista.")}</div>`);
					return;
				}
				const body = rows
					.map(
						(row) => `<tr>
						<td><a href="#" data-encargo="${esc(row.name)}" data-status="${esc(row.reception_status)}"
							style="font-weight: 700;">${esc(row.name)}</a></td>
						<td>${esc(row.brand)}</td>
						<td>${esc(row.description)}</td>
						<td>${esc(row.sales_order)}<br><span class="text-muted">${esc(row.customer)}</span></td>
						<td>${esc(row.purchase_supplier || row.proposed_supplier_name)}<br>
							<span class="text-muted">${esc(row.shopper_user)}</span></td>
						<td>${fmt_dt(row.purchased_on)}<br><span class="text-muted">${days_since(row.purchased_on)}</span></td>
						<td style="word-break: break-all; max-width: 200px;">${esc(row.purchase_barcode)}</td>
						<td>${row.received_on ? `${fmt_dt(row.received_on)}<br><span class="text-muted">${esc(row.received_by)}</span>` : ""}</td>
					</tr>`
					)
					.join("");
				this.$list.html(`
					<table class="table table-bordered table-hover">
						<thead><tr>
							<th>${__("ENC")}</th><th>${__("Marca")}</th><th>${__("Descripción")}</th>
							<th>${__("OV / Cliente")}</th><th>${__("Lugar / Shopper")}</th><th>${__("Compra")}</th>
							<th>${__("Código")}</th><th>${__("Recepción")}</th>
						</tr></thead>
						<tbody>${body}</tbody>
					</table>
				`);
			},
		});
	}
}

function esc(value) {
	return frappe.utils.escape_html(value == null ? "" : String(value));
}

function fmt_dt(value) {
	return value ? frappe.datetime.str_to_user(value) : "";
}

function days_since(value) {
	if (!value) {
		return "";
	}
	const days = frappe.datetime.get_day_diff(frappe.datetime.now_date(), value.slice(0, 10));
	return days === 0 ? __("hoy") : __("hace {0} días", [days]);
}

function open_encargo(name) {
	window.open(`/app/encargo/${encodeURIComponent(name)}`, "_blank");
}

function image(url, label) {
	if (!url) {
		return "";
	}
	const src = esc(url);
	return `<a href="${src}" target="_blank" rel="noopener" title="${esc(label)}">
		<img src="${src}" alt="${esc(label)}" style="max-width: 48%; max-height: 220px; border-radius: 8px; margin: 4px;"></a>`;
}

function fact(label, value) {
	return value ? `<div><span class="text-muted">${esc(label)}:</span> ${esc(value)}</div>` : "";
}

function side_original(enc) {
	const attributes = RC_ATTRIBUTES.map(([field, label]) => fact(__(label), enc[field])).join("");
	return `
		<h5 style="font-weight: 800;">${__("Solicitud original")}</h5>
		${image(enc.reference_image, __("Imagen de referencia"))}
		<div style="font-size: 16px; font-weight: 700; margin-top: 6px;">${esc(enc.description)}</div>
		${fact(__("Marca"), enc.brand)}
		${fact(__("Grupo"), enc.item_group)}
		${attributes}
		${fact(__("Item vendido"), enc.expected_item)}
		${fact(__("Notas"), enc.notes)}
		${fact(__("Referencia"), enc.reference_url)}
		${fact(__("OV"), enc.sales_order)}
		${fact(__("Cliente"), enc.customer)}
	`;
}

function side_purchase(enc) {
	return `
		<h5 style="font-weight: 800;">${__("Compra Shopper")}</h5>
		${image(enc.purchase_product_image, __("Foto del producto"))}
		${image(enc.purchase_label_image, __("Foto de etiqueta"))}
		${fact(__("Lugar"), enc.purchase_supplier || enc.proposed_supplier_name)}
		${fact(__("Shopper"), enc.shopper_user)}
		${fact(__("Fecha"), fmt_dt(enc.purchased_on))}
		${fact(__("Código"), enc.purchase_barcode)}
		${fact(__("Precio"), enc.purchase_price != null ? format_number(enc.purchase_price, null, 2) : "")}
	`;
}
