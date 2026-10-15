const RCC_METHOD = "erpn_custom.encargo.reception.";
const RCC_BOX_METHOD = "erpn_custom.encargo.box_reception.";
const RCC_BARCODE_METHOD = "erpn_custom.encargo.barcode_exception.";
const RCC_BARCODE_VIEWS = [
	{ view: "pending", label: __("Pendiente aprobación") },
	{ view: "rejected", label: __("Rechazadas (historial)") },
];
const RCC_VIEWS = [
	{ view: "apartados", label: __("Apartados") },
	{ view: "clasificacion", label: __("Pendientes de clasificación") },
	{ view: "barcode", label: __("Excepciones barcode") },
	{ view: "valorizacion", label: __("Pendientes de valorización") },
	{ view: "vincular", label: __("Pendientes de vincular a OV") },
	{ view: "cajas", label: __("Cajas con incidencias") },
];

const rcc_escape = (value) => frappe.utils.escape_html(value == null ? "" : String(value));

frappe.pages["recepcion-comercial"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Recepción Comercial"),
		single_column: true,
	});
	wrapper.reception = new CommercialReception(page);
};

frappe.pages["recepcion-comercial"].on_page_show = function (wrapper) {
	if (wrapper.reception) {
		wrapper.reception.on_show();
	}
};

class CommercialReception {
	constructor(page) {
		this.page = page;
		this.view = "apartados";
		this.barcode_view = "pending";
		this.rows = [];
		this.page.main.html(`
			<style>
				.rcc-wrap { max-width: 960px; margin: 0 auto; }
				.rcc-tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
				.rcc-tabs button { font-weight: 600; }
				.rcc-banner { padding: 10px 12px; border-radius: 8px; margin-bottom: 8px; background: #fde2e1; color: #6b1210; font-weight: 600; }
				.rcc-card { padding: 10px 12px; border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 8px; }
				.rcc-card-head { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
				.rcc-card-title { font-weight: 700; }
				.rcc-actions { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
				.rcc-message { margin-top: 4px; color: #a94442; font-weight: 600; }
				.rcc-code { font-family: monospace; word-break: break-all; }
				.rcc-subtabs { display: none; gap: 8px; margin-bottom: 8px; }
				.rcc-evidence { display: flex; gap: 8px; margin-top: 6px; }
				.rcc-evidence img { max-height: 120px; border-radius: 6px; border: 1px solid var(--border-color); }
			</style>
			<div class="rcc-wrap">
				<div class="rcc-tabs">
					${RCC_VIEWS.map(
						(v) => `<button class="btn btn-default btn-sm" data-view="${v.view}">${rcc_escape(v.label)}</button>`
					).join("")}
				</div>
				<div class="rcc-subtabs">
					${RCC_BARCODE_VIEWS.map(
						(v) => `<button class="btn btn-default btn-xs" data-barcode-view="${v.view}">${rcc_escape(v.label)}</button>`
					).join("")}
				</div>
				<div class="rcc-banner-box"></div>
				<input type="text" class="form-control rcc-search" placeholder="${__("Buscar: ENC, OV, cliente, Item, código")}">
				<div class="rcc-list" style="margin-top: 8px;"></div>
			</div>
		`);
		this.$banner = this.page.main.find(".rcc-banner-box");
		this.$list = this.page.main.find(".rcc-list");
		this.$search = this.page.main.find(".rcc-search");
		this.page.main.find(".rcc-tabs button").on("click", (e) => {
			this.view = $(e.currentTarget).data("view");
			this.load();
		});
		this.page.main.find(".rcc-subtabs button").on("click", (e) => {
			this.barcode_view = $(e.currentTarget).data("barcode-view");
			this.load();
		});
		this.$search.on("input", frappe.utils.debounce(() => this.load(), 300));
		this.$list.on("click", "[data-action]", (e) => {
			const $btn = $(e.currentTarget);
			if ($btn.attr("data-box")) {
				this.box_act($btn.attr("data-action"), $btn.attr("data-box"));
			} else if ($btn.attr("data-encargo")) {
				this.barcode_act(
					$btn.attr("data-action"),
					$btn.attr("data-encargo"),
					$btn.attr("data-override") === "1",
					$btn.attr("data-event")
				);
			} else {
				this.act($btn.attr("data-action"), $btn.attr("data-unit"));
			}
		});
		this.page.set_secondary_action(__("Actualizar"), () => this.load());
	}

	on_show() {
		// The Encargo form opens this page already filtered by that Encargo.
		if (frappe.route_options && frappe.route_options.search) {
			this.$search.val(frappe.route_options.search);
			frappe.route_options = null;
		}
		this.load();
	}

	load() {
		this.page.main.find(".rcc-tabs button").each((_, el) => {
			$(el).toggleClass("btn-primary", $(el).data("view") === this.view);
			$(el).toggleClass("btn-default", $(el).data("view") !== this.view);
		});
		const $subtabs = this.page.main.find(".rcc-subtabs");
		$subtabs.css("display", this.view === "barcode" ? "flex" : "none");
		$subtabs.find("button").each((_, el) => {
			$(el).toggleClass("btn-primary", $(el).data("barcode-view") === this.barcode_view);
			$(el).toggleClass("btn-default", $(el).data("barcode-view") !== this.barcode_view);
		});
		const request = (this.request = (this.request || 0) + 1);
		if (this.view === "barcode") {
			this.load_exceptions(request);
			return;
		}
		if (this.view === "cajas") {
			this.load_boxes(request);
			return;
		}
		frappe.call({
			method: RCC_METHOD + "list_units",
			args: { view: this.view, search: this.$search.val() },
			callback: (r) => {
				if (request !== this.request) {
					return;
				}
				const data = r.message || {};
				this.rows = data.rows || [];
				this.$banner.html(
					data.configured
						? ""
						: `<div class="rcc-banner">${__(
								"Falta la cuenta transitoria en Configuracion Recepcion FRA: las unidades quedan pendientes de valorización."
						  )}</div>`
				);
				this.render();
			},
		});
	}

	load_exceptions(request) {
		this.$banner.html("");
		frappe.call({
			method: RCC_BARCODE_METHOD + "list_exceptions",
			args: { view: this.barcode_view, search: this.$search.val() },
			callback: (r) => {
				if (request !== this.request) {
					return;
				}
				this.rows = (r.message || {}).rows || [];
				this.render();
			},
		});
	}

	load_boxes(request) {
		this.$banner.html("");
		frappe.call({
			method: RCC_BOX_METHOD + "list_incidents",
			callback: (r) => {
				if (request !== this.request) {
					return;
				}
				const text = (this.$search.val() || "").toLowerCase();
				this.rows = (r.message || []).filter((row) => !text || String(row.name).toLowerCase().includes(text));
				this.render();
			},
		});
	}

	render() {
		if (!this.rows.length) {
			const empty = this.view === "barcode" ? __("Sin excepciones") : this.view === "cajas" ? __("Sin cajas con incidencias") : __("Sin registros");
			this.$list.html(`<div class="text-muted" style="padding: 12px 0;">${rcc_escape(empty)}</div>`);
			return;
		}
		const card =
			this.view === "barcode"
				? (row) => this.exception_card(row)
				: this.view === "cajas"
				? (row) => this.box_card(row)
				: (row) => this.card(row);
		this.$list.html(this.rows.map(card).join(""));
	}

	box_card(row) {
		const btn = (action, label, style) =>
			`<button class="btn btn-xs ${style}" data-action="${action}" data-box="${rcc_escape(row.name)}">${rcc_escape(label)}</button>`;
		return `
			<div class="rcc-card">
				<div class="rcc-card-head">
					<div class="rcc-card-title">${rcc_escape(row.name)}${row.external_ref ? " · " + rcc_escape(row.external_ref) : ""}</div>
					<div class="text-muted small">${__("Finalizar pulsado")} ${rcc_escape(
						frappe.datetime.str_to_user(row.finalize_requested_on)
					)} · ${rcc_escape(row.finalize_requested_by)}</div>
				</div>
				<div class="small">${__("Procesadas {0} de {1} · con error técnico {2}", [
					rcc_escape(row.processed_lines || 0),
					rcc_escape(row.active_lines || 0),
					rcc_escape(row.error_lines || 0),
				])}</div>
				<div class="small text-muted">${__("Último avance")}: ${rcc_escape(frappe.datetime.str_to_user(row.job_heartbeat))}</div>
				${row.last_error ? `<div class="rcc-message small rcc-code">${rcc_escape(String(row.last_error).slice(-300))}</div>` : ""}
				<div class="rcc-actions">${btn("retry", __("Reintentar procesamiento"), "btn-primary")}${btn(
					"detail",
					__("Ver caja"),
					"btn-default"
				)}</div>
			</div>
		`;
	}

	box_act(action, box) {
		if (action === "detail") {
			this.show_box(box);
			return;
		}
		frappe.call({
			method: RCC_BOX_METHOD + "retry_box",
			type: "POST",
			args: { box },
			freeze: true,
			callback: () => {
				frappe.show_alert({ message: __("Reintento en cola para {0}", [box]), indicator: "green" });
				this.load();
			},
		});
	}

	show_box(box) {
		frappe.call({
			method: RCC_BOX_METHOD + "get_box",
			args: { box },
			callback: (r) => {
				const data = r.message;
				if (!data) {
					return;
				}
				const rows = (data.lines || [])
					.map((line) => {
						const u = line.unit;
						const result = u
							? `${rcc_escape(__(u.screen))} · <a href="/app/recepcion-unidad/${encodeURIComponent(u.name)}">${rcc_escape(u.name)}</a>`
							: rcc_escape(line.status) + (line.error_message ? ` · ${rcc_escape(String(line.error_message).slice(-160))}` : "");
						return `<tr><td>${rcc_escape(line.ordinal)}</td><td class="rcc-code">${rcc_escape(line.scanned_code)}</td><td>${rcc_escape(
							line.scanned_by
						)}</td><td>${result}</td></tr>`;
					})
					.join("");
				frappe.msgprint({
					title: `${data.name} · ${data.status}`,
					wide: true,
					message: `<table class="table table-sm"><thead><tr><th>#</th><th>${__("Código")}</th><th>${__("Leída por")}</th><th>${__(
						"Resultado"
					)}</th></tr></thead><tbody>${rows}</tbody></table>`,
				});
			},
		});
	}

	exception_card(row) {
		const link = (doctype, name) =>
			name ? `<a href="/app/${frappe.router.slug(doctype)}/${encodeURIComponent(name)}">${rcc_escape(name)}</a>` : "";
		const image = (url) => (url ? `<a href="${rcc_escape(url)}" target="_blank"><img src="${rcc_escape(url)}"></a>` : "");
		const responsible = row.escalated
			? `${__("Sin vendedor resoluble - escalado a System Manager")}: ${rcc_escape((row.responsible || []).join(", "))}`
			: `${__("Responsable")}: ${rcc_escape((row.responsible || []).join(", "))}`;
		const btn = (action, label, style) =>
			`<button class="btn btn-xs ${style}" data-action="${action}" data-encargo="${rcc_escape(row.name)}" data-event="${rcc_escape(
				row.supply_event
			)}" data-override="${row.override ? 1 : 0}">${rcc_escape(label)}</button>`;
		let actions = "";
		if (row.can_resolve && this.barcode_view === "pending") {
			actions = btn("approve", __("Aprobar"), "btn-primary") + btn("reject", __("Rechazar"), "btn-danger");
		}
		return `
			<div class="rcc-card">
				<div class="rcc-card-head">
					<div class="rcc-card-title">${link("Encargo", row.name)} · ${rcc_escape(row.customer)} · ${link(
						"Sales Order",
						row.sales_order
					)}</div>
					<div class="text-muted small">${rcc_escape(row.label)}</div>
				</div>
				<div>${__("Item esperado")}: ${link("Item", row.expected_item)} ${rcc_escape(row.expected_item_name)}</div>
				<div class="small">${__("Código esperado")}: <span class="rcc-code">${rcc_escape(
					row.expected_barcode || __("sin código")
				)}</span></div>
				<div class="small">${__("Código comprado")}: <span class="rcc-code">${rcc_escape(row.purchase_barcode)}</span> · ${__(
					"{0} u. de {1}",
					[rcc_escape(row.qty), rcc_escape(row.requested_qty)]
				)}</div>
				<div class="small text-muted">${__("Compra")}: ${rcc_escape(frappe.datetime.str_to_user(row.purchased_on))} · ${rcc_escape(
					row.shopper_user
				)} · ${rcc_escape(row.purchase_supplier || row.proposed_supplier_name)}</div>
				<div class="small">${responsible}</div>
				${
					row.conflict_item
						? `<div class="rcc-message small">${__(
								"El código pertenece al Item {0}: la aprobación queda bloqueada hasta que System Manager corrija el maestro.",
								[rcc_escape(row.conflict_item)]
						  )}</div>`
						: ""
				}
				${
					row.barcode_resolution_comment
						? `<div class="text-muted small">${rcc_escape(row.barcode_resolved_by)}: ${rcc_escape(
								row.barcode_resolution_comment
						  )}</div>`
						: ""
				}
				<div class="rcc-evidence">${image(row.purchase_product_image)}${image(row.purchase_label_image)}</div>
				<div class="rcc-actions">${actions}</div>
			</div>
		`;
	}

	barcode_act(action, encargo, override, supply_event) {
		erpn_barcode_decision(action, encargo, override, () => this.load(), supply_event);
	}

	card(row) {
		const link = (doctype, name) =>
			name ? `<a href="/app/${frappe.router.slug(doctype)}/${encodeURIComponent(name)}">${rcc_escape(name)}</a>` : "";
		const who = row.encargo
			? `${link("Encargo", row.encargo)} · ${rcc_escape(row.customer)} · ${link("Sales Order", row.sales_order)}`
			: __("Sin Encargo");
		const item = row.item ? `${link("Item", row.item)} ${rcc_escape(row.item_name)}` : __("Sin Item");
		const extra = [
			row.warehouse ? `${__("Bodega")}: ${rcc_escape(row.warehouse)}` : "",
			row.incoming_rate ? `${__("Costo")}: ${rcc_escape(format_currency(row.incoming_rate))}` : "",
			row.stock_entry ? link("Stock Entry", row.stock_entry) : "",
		]
			.filter(Boolean)
			.join(" · ");
		return `
			<div class="rcc-card">
				<div class="rcc-card-head">
					<div class="rcc-card-title">${link("Recepcion Unidad", row.name)} · ${who}</div>
					<div class="text-muted small">${rcc_escape(frappe.datetime.str_to_user(row.received_on))} · ${rcc_escape(
						row.received_by
					)}</div>
				</div>
				<div>${item}</div>
				<div class="rcc-code small">${rcc_escape(row.scanned_code)}</div>
				<div class="small">${__("Caja")}: ${row.box ? link("Recepcion Caja", row.box) : rcc_escape(__("Sin caja (LEGACY)"))}</div>
				${extra ? `<div class="small">${extra}</div>` : ""}
				${row.reservation_note ? `<div class="text-muted small">${rcc_escape(row.reservation_note)}</div>` : ""}
				${row.message ? `<div class="rcc-message small">${rcc_escape(row.message)}</div>` : ""}
				${
					row.materialization_message
						? `<div class="rcc-message small">${rcc_escape(row.materialization_message)}</div>`
						: ""
				}
				<div class="rcc-actions">${this.actions(row)}</div>
			</div>
		`;
	}

	actions(row) {
		const btn = (action, label, style) =>
			`<button class="btn btn-xs ${style}" data-action="${action}" data-unit="${rcc_escape(row.name)}">${rcc_escape(label)}</button>`;
		if (this.view === "apartados") {
			return btn("return", __("Devolver a stock"), "btn-danger");
		}
		if (this.view === "clasificacion") {
			return btn("resolve", __("Resolver"), "btn-primary");
		}
		if (this.view === "valorizacion") {
			return btn("retry", __("Reintentar valorización"), "btn-primary");
		}
		if (this.view === "vincular") {
			return btn("link", __("Reintentar vinculación"), "btn-primary");
		}
		return "";
	}

	act(action, unit) {
		if (action === "return") {
			this.return_unit(unit);
		} else if (action === "resolve") {
			this.resolve(unit);
		} else if (action === "retry") {
			this.call("resolve_unit", { unit });
		} else if (action === "link") {
			this.call("retry_materialization", { unit });
		}
	}

	resolve(unit) {
		const dialog = new frappe.ui.Dialog({
			title: __("Resolver {0}", [unit]),
			fields: [
				{
					fieldtype: "HTML",
					options: `<p class="text-muted">${__(
						"Completa la clasificación del Encargo y reintenta, o elige un Item existente con stock para esta unidad."
					)}</p>`,
				},
				{
					fieldname: "item",
					fieldtype: "Link",
					options: "Item",
					label: __("Item existente (opcional)"),
					get_query: () => ({ filters: { disabled: 0, is_stock_item: 1 } }),
				},
			],
			primary_action_label: __("Resolver"),
			primary_action: (values) => {
				dialog.hide();
				this.call("resolve_unit", { unit, item: values.item || null });
			},
		});
		dialog.show();
	}

	return_unit(unit) {
		frappe.prompt(
			[{ fieldname: "notes", fieldtype: "Small Text", label: __("Motivo"), reqd: 1 }],
			(values) => this.call("return_unit", { unit, notes: values.notes }),
			__("Devolver a stock {0}", [unit]),
			__("Devolver a stock")
		);
	}

	call(method, args) {
		frappe.call({
			method: RCC_METHOD + method,
			type: "POST",
			args,
			freeze: true,
			callback: (r) => {
				const data = r.message || {};
				frappe.show_alert({
					message: `${rcc_escape(__(data.screen || ""))}${data.message ? ": " + rcc_escape(data.message) : ""}`,
					indicator: data.kind === "warning" ? "orange" : "green",
				});
				this.load();
			},
		});
	}
}
