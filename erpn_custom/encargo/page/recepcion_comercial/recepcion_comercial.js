const RCC_METHOD = "erpn_custom.encargo.reception.";
const RCC_VIEWS = [
	{ view: "apartados", label: __("Apartados") },
	{ view: "clasificacion", label: __("Pendientes de clasificación") },
	{ view: "barcode", label: __("Excepciones barcode") },
	{ view: "valorizacion", label: __("Pendientes de valorización") },
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
			</style>
			<div class="rcc-wrap">
				<div class="rcc-tabs">
					${RCC_VIEWS.map(
						(v) => `<button class="btn btn-default btn-sm" data-view="${v.view}">${rcc_escape(v.label)}</button>`
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
		this.$search.on("input", frappe.utils.debounce(() => this.load(), 300));
		this.$list.on("click", "[data-action]", (e) => {
			const $btn = $(e.currentTarget);
			this.act($btn.attr("data-action"), $btn.attr("data-unit"));
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
		frappe.call({
			method: RCC_METHOD + "list_units",
			args: { view: this.view, search: this.$search.val() },
			callback: (r) => {
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

	render() {
		if (!this.rows.length) {
			const empty =
				this.view === "barcode"
					? __("Sin excepciones. La aprobación de códigos se habilita con la Spec 017.")
					: __("Sin registros");
			this.$list.html(`<div class="text-muted" style="padding: 12px 0;">${rcc_escape(empty)}</div>`);
			return;
		}
		this.$list.html(this.rows.map((row) => this.card(row)).join(""));
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
				${extra ? `<div class="small">${extra}</div>` : ""}
				${row.reservation_note ? `<div class="text-muted small">${rcc_escape(row.reservation_note)}</div>` : ""}
				${row.message ? `<div class="rcc-message small">${rcc_escape(row.message)}</div>` : ""}
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
		return "";
	}

	act(action, unit) {
		if (action === "return") {
			this.return_unit(unit);
		} else if (action === "resolve") {
			this.resolve(unit);
		} else if (action === "retry") {
			this.call("resolve_unit", { unit });
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
