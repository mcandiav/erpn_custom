const RC_METHOD = "erpn_custom.encargo.reception.";
const RC_BOX_METHOD = "erpn_custom.encargo.box_reception.";
// Same library and settings as the shopper page; decodes in JS where the browser has no BarcodeDetector (iPhone).
const RC_SCANNER_SRC = "/assets/frappe/node_modules/html5-qrcode/html5-qrcode.min.js";
const RC_POLL_MS = 3000;
const RC_LAST_BOX = "erpn_custom_rc_box";
const RC_STATUS = {
	DRAFT: { label: __("BORRADOR"), color: "orange" },
	FINALIZING: { label: __("PROCESANDO"), color: "blue" },
	FINALIZED: { label: __("FINALIZADA"), color: "green" },
	FINALIZED_WITH_EXCEPTIONS: { label: __("FINALIZADA CON EXCEPCIONES"), color: "red" },
	CANCELLED: { label: __("ANULADA"), color: "gray" },
};

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

frappe.pages["recepcion-chile"].on_page_hide = function (wrapper) {
	if (wrapper.reception) {
		wrapper.reception.on_hide();
	}
};

const rc_escape = (value) => frappe.utils.escape_html(value == null ? "" : String(value));

// One id per physical read, created before sending: retries reuse it so the server never stores a read twice.
function rc_scan_id() {
	if (window.crypto && crypto.randomUUID) {
		return crypto.randomUUID();
	}
	const bytes = new Uint8Array(16);
	(window.crypto || window.msCrypto).getRandomValues(bytes);
	return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

function rc_status_badge(status) {
	const s = RC_STATUS[status] || { label: status, color: "gray" };
	return `<span class="indicator-pill ${s.color}">${rc_escape(s.label)}</span>`;
}

function rc_link(doctype, name) {
	return name ? `<a href="/app/${frappe.router.slug(doctype)}/${encodeURIComponent(name)}">${rc_escape(name)}</a>` : "";
}

class ReceptionStation {
	constructor(page) {
		this.page = page;
		this.mode = "home";
		this.view = "open";
		this.box = null;
		this.queue = [];
		this.local = [];
		this.working = false;
		this.poll = null;
		this.scanner = null;
		this.scanner_lib = null;
		this.page.main.html(`
			<style>
				.rc-wrap { max-width: 720px; margin: 0 auto; }
				.rc-row { display: flex; gap: 8px; }
				.rc-code { font-size: 20px; height: 56px; }
				.rc-camera-btn { height: 56px; font-size: 18px; font-weight: 700; white-space: nowrap; }
				.rc-reader { margin-top: 12px; border-radius: 8px; overflow: hidden; }
				.rc-big-btn { height: 52px; font-size: 18px; font-weight: 700; width: 100%; margin-bottom: 8px; }
				.rc-box-head { padding: 12px; border-radius: 10px; background: var(--subtle-fg); margin-bottom: 12px; }
				.rc-box-title { font-size: 26px; font-weight: 800; letter-spacing: 1px; }
				.rc-counter { font-size: 18px; font-weight: 700; margin-top: 4px; }
				.rc-warn { margin-top: 8px; padding: 10px 12px; border-radius: 8px; background: #fff3cd; color: #5c3c00; font-weight: 700; }
				.rc-line { display: flex; justify-content: space-between; align-items: center; gap: 8px;
					padding: 8px 10px; border-left: 4px solid var(--border-color); margin-bottom: 6px; background: var(--subtle-fg); border-radius: 4px; }
				.rc-line-encargo { border-left-color: #f0ad4e; }
				.rc-line-stock { border-left-color: #2f80ed; }
				.rc-line-warning, .rc-line-failed, .rc-line-error { border-left-color: #d9534f; }
				.rc-line-discarded { opacity: 0.55; text-decoration: line-through; }
				.rc-line-code { font-family: monospace; word-break: break-all; }
				.rc-line-screen { font-weight: 800; }
				.rc-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 16px; }
				.rc-actions .btn { flex: 1; min-height: 44px; font-weight: 700; }
				.rc-tabs { display: flex; gap: 8px; margin: 16px 0 8px; flex-wrap: wrap; }
				.rc-tabs button { flex: 1; height: 44px; font-weight: 600; }
				.rc-filters { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
				.rc-filters > * { flex: 1; min-width: 140px; }
				.rc-card { padding: 10px 12px; border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 8px; }
				.rc-card-head { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; align-items: center; }
				.rc-card-title { font-weight: 700; }
				.rc-summary { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
				.rc-summary div { flex: 1; min-width: 120px; padding: 8px; border-radius: 8px; background: var(--subtle-fg); text-align: center; font-weight: 700; }
			</style>
			<div class="rc-wrap">
				<div class="rc-home"></div>
				<div class="rc-box-view" style="display: none;"></div>
			</div>
		`);
		this.$home = this.page.main.find(".rc-home");
		this.$boxview = this.page.main.find(".rc-box-view");
		this.render_home();
	}

	on_show() {
		if (this.mode === "box" && this.box) {
			this.refresh_box();
			return;
		}
		const last = localStorage.getItem(RC_LAST_BOX);
		if (last) {
			this.open_existing(last, true);
		} else {
			this.load_list();
		}
	}

	on_hide() {
		this.stop_poll();
		this.stop_camera();
	}

	// ------------------------------------------------------------ home

	render_home() {
		this.$home.html(`
			<button class="btn btn-primary rc-big-btn rc-open">${__("Abrir caja")}</button>
			<div class="rc-tabs">
				<button class="btn btn-default" data-view="open">${__("Cajas abiertas")}</button>
				<button class="btn btn-default" data-view="history">${__("Historial de cajas")}</button>
				<button class="btn btn-default" data-view="pending">${__("Comprados no recibidos")}</button>
			</div>
			<div class="rc-filters">
				<input type="text" class="form-control rc-search" placeholder="${__("Buscar: BOX, código, ENC, OV, Item")}">
				<select class="form-control rc-status-filter">
					<option value="">${__("Todos los estados")}</option>
					${Object.keys(RC_STATUS)
						.map((s) => `<option value="${s}">${rc_escape(RC_STATUS[s].label)}</option>`)
						.join("")}
				</select>
				<input type="date" class="form-control rc-date-filter">
				<label class="rc-mine" style="display: flex; align-items: center; gap: 6px; margin: 0;">
					<input type="checkbox" class="rc-mine-filter"> ${__("Con mis lecturas")}
				</label>
			</div>
			<div class="rc-list"></div>
		`);
		this.$list = this.$home.find(".rc-list");
		this.$search = this.$home.find(".rc-search");
		this.$home.find(".rc-open").on("click", () => this.open_new());
		this.$home.find(".rc-tabs button").on("click", (e) => {
			this.view = $(e.currentTarget).data("view");
			this.load_list();
		});
		this.$search.on("input", frappe.utils.debounce(() => this.load_list(), 300));
		this.$home.find(".rc-status-filter, .rc-date-filter, .rc-mine-filter").on("change", () => this.load_list());
		this.$list.on("click", "[data-box]", (e) => this.open_existing($(e.currentTarget).attr("data-box")));
	}

	show_home() {
		this.mode = "home";
		this.box = null;
		this.queue = [];
		this.local = [];
		localStorage.removeItem(RC_LAST_BOX);
		this.stop_poll();
		this.stop_camera();
		this.$boxview.hide();
		this.$home.show();
		this.load_list();
	}

	load_list() {
		this.$home.find(".rc-tabs button").each((_, el) => {
			$(el).toggleClass("btn-primary", $(el).data("view") === this.view);
			$(el).toggleClass("btn-default", $(el).data("view") !== this.view);
		});
		const history = this.view === "history";
		this.$home.find(".rc-status-filter, .rc-date-filter, .rc-mine").toggle(history);
		const request = (this.request = (this.request || 0) + 1);
		const done = (rows) => {
			if (request === this.request) {
				this.render_list(rows || []);
			}
		};
		if (this.view === "pending") {
			frappe.call({
				method: RC_METHOD + "list_reception",
				args: { view: "pending", search: this.$search.val() },
				callback: (r) => done(r.message),
			});
			return;
		}
		frappe.call({
			method: RC_BOX_METHOD + "list_boxes",
			args: {
				view: this.view,
				search: this.$search.val(),
				status: history ? this.$home.find(".rc-status-filter").val() : null,
				date: history ? this.$home.find(".rc-date-filter").val() : null,
				user: history && this.$home.find(".rc-mine-filter").is(":checked") ? frappe.session.user : null,
			},
			callback: (r) => done(r.message),
		});
	}

	render_list(rows) {
		if (!rows.length) {
			const empty = this.view === "open" ? __("No hay cajas abiertas") : __("Sin registros");
			this.$list.html(`<div class="text-muted" style="padding: 12px 0;">${rc_escape(empty)}</div>`);
			return;
		}
		this.$list.html(rows.map((row) => (this.view === "pending" ? this.encargo_card(row) : this.box_card(row))).join(""));
	}

	box_card(row) {
		const action = row.status === "DRAFT" ? __("Continuar caja") : __("Ver detalle");
		const counts =
			row.status === "FINALIZING"
				? __("Procesadas {0} de {1}", [row.processed_lines || 0, row.active_lines || 0])
				: __("{0} lecturas · {1} quitadas", [row.active_lines || 0, row.discarded_lines || 0]);
		const exceptions = row.exception_lines ? ` · ${__("{0} con excepción", [row.exception_lines])}` : "";
		return `
			<div class="rc-card">
				<div class="rc-card-head">
					<div class="rc-card-title">${rc_escape(row.name)}${row.external_ref ? " · " + rc_escape(row.external_ref) : ""}</div>
					${rc_status_badge(row.status)}
				</div>
				<div class="small">${rc_escape(counts)}${rc_escape(exceptions)}</div>
				<div class="text-muted small">${__("Abierta")} ${rc_escape(frappe.datetime.str_to_user(row.opened_on))} · ${rc_escape(
					row.opened_by
				)}</div>
				<button class="btn btn-sm ${row.status === "DRAFT" ? "btn-primary" : "btn-default"}" style="margin-top: 6px;" data-box="${rc_escape(
					row.name
				)}">${rc_escape(action)}</button>
			</div>
		`;
	}

	encargo_card(row) {
		return `
			<div class="rc-card">
				<div class="rc-card-title">${rc_escape(row.name)} · ${rc_escape(row.customer)}</div>
				<div>${rc_escape(row.brand)} ${rc_escape(row.description)}</div>
				<div class="small">${__("Recibidas {0} de {1}", [rc_escape(row.received_qty || 0), rc_escape(row.requested_qty || 0)])}</div>
				<div class="text-muted small">${__("Compradas por llegar: {0}", [rc_escape(row.pending_receive_qty || 0)])}</div>
			</div>
		`;
	}

	open_new() {
		frappe.prompt(
			[
				{
					fieldname: "external_ref",
					fieldtype: "Data",
					label: __("Etiqueta del transportista (opcional)"),
				},
			],
			(values) => {
				frappe.call({
					method: RC_BOX_METHOD + "open_box",
					type: "POST",
					args: { external_ref: values.external_ref || null },
					freeze: true,
					callback: (r) => r.message && this.show_box(r.message),
				});
			},
			__("Abrir caja"),
			__("Abrir")
		);
	}

	open_existing(name, silent) {
		frappe.call({
			method: RC_BOX_METHOD + "get_box",
			args: { box: name },
			callback: (r) => {
				if (r.message) {
					this.show_box(r.message);
				} else if (silent) {
					this.show_home();
				}
			},
			error: () => silent && this.show_home(),
		});
	}

	// ------------------------------------------------------------ box

	show_box(data) {
		this.mode = "box";
		this.box = data;
		localStorage.setItem(RC_LAST_BOX, data.name);
		this.$home.hide();
		this.$boxview.show();
		this.render_box();
		this.sync_poll();
		this.focus();
	}

	refresh_box() {
		if (!this.box) {
			return;
		}
		frappe.call({
			method: RC_BOX_METHOD + "get_box",
			args: { box: this.box.name },
			callback: (r) => {
				if (r.message && this.box && r.message.name === this.box.name) {
					this.box = r.message;
					this.render_box();
					this.sync_poll();
				}
			},
		});
	}

	sync_poll() {
		if (this.box && this.box.status === "FINALIZING") {
			if (!this.poll) {
				this.poll = setInterval(() => this.refresh_box(), RC_POLL_MS);
			}
		} else {
			this.stop_poll();
		}
	}

	stop_poll() {
		if (this.poll) {
			clearInterval(this.poll);
			this.poll = null;
		}
	}

	render_box() {
		const b = this.box;
		const draft = b.status === "DRAFT";
		const lines = b.lines || [];
		const active = lines.filter((l) => l.status !== "DISCARDED").length;
		const discarded = lines.length - active;
		let progress = "";
		if (b.status === "FINALIZING") {
			progress = `<div class="rc-counter">${__("Procesando {0} de {1}", [b.processed_lines || 0, active])}</div>`;
			if (b.error_lines) {
				progress += `<div class="rc-warn">${__(
					"{0} lecturas con error técnico: se reintentan automáticamente; Comercial puede reintentar.",
					[b.error_lines]
				)}</div>`;
			}
		}
		this.$boxview.html(`
			<div class="rc-box-head">
				<div class="rc-card-head">
					<div class="rc-box-title">${rc_escape(b.name)}</div>
					${rc_status_badge(b.status)}
				</div>
				${b.external_ref ? `<div class="small">${__("Etiqueta")}: ${rc_escape(b.external_ref)}</div>` : ""}
				<div class="rc-counter">${__("{0} lecturas", [active])}${discarded ? " · " + __("{0} quitadas", [discarded]) : ""}</div>
				${progress}
			</div>
			${
				draft
					? `<div class="rc-row">
						<input type="text" class="form-control rc-code" autocomplete="off" spellcheck="false"
							inputmode="text" placeholder="${__("Código y Enter")}">
						<button class="btn btn-primary rc-camera-btn">${__("ESCANEAR")}</button>
					</div>
					<div class="rc-reader"></div>
					<div class="rc-warn-box"></div>
					<div class="text-muted small" style="margin-top: 6px;">${__(
						"Vista previa no comprometida: la asignación, reserva y bodega se deciden al finalizar."
					)}</div>`
					: ""
			}
			${this.summary_html()}
			<div class="rc-lines" style="margin-top: 12px;"></div>
			<div class="rc-actions">${this.actions_html()}</div>
		`);
		this.$code = this.$boxview.find(".rc-code");
		this.$reader = this.$boxview.find(".rc-reader");
		this.$warn = this.$boxview.find(".rc-warn-box");
		this.$lines = this.$boxview.find(".rc-lines");
		this.$code.on("keydown", (e) => {
			if (e.key === "Enter") {
				e.preventDefault();
				this.enqueue(this.$code.val());
				this.$code.val("");
			}
		});
		this.$boxview.find(".rc-camera-btn").on("click", () => this.toggle_camera());
		this.$boxview.find(".rc-finalize").on("click", () => this.finalize());
		this.$boxview.find(".rc-back").on("click", () => this.show_home());
		this.$boxview.find(".rc-cancel").on("click", () => this.cancel());
		this.$lines.on("click", ".rc-discard", (e) => this.discard($(e.currentTarget).attr("data-line")));
		this.$lines.on("click", ".rc-retry", (e) => this.retry($(e.currentTarget).attr("data-id")));
		this.render_lines();
	}

	summary_html() {
		const b = this.box;
		if (!["FINALIZED", "FINALIZED_WITH_EXCEPTIONS"].includes(b.status)) {
			return "";
		}
		const units = (b.lines || []).filter((l) => l.unit).map((l) => l.unit);
		const count = (kind) => units.filter((u) => u.kind === kind).length;
		return `
			<div class="rc-summary">
				<div style="background: #fff3cd;">${__("APARTAR")}: ${count("encargo")}</div>
				<div style="background: #e3f0ff;">${__("STOCK NORMAL")}: ${count("stock")}</div>
				<div style="background: #fde2e1;">${__("EXCEPCIONES")}: ${units.filter((u) => u.exception).length}</div>
			</div>
		`;
	}

	actions_html() {
		const b = this.box;
		const back = `<button class="btn btn-default rc-back">${__("Volver a mis cajas")}</button>`;
		if (b.status !== "DRAFT") {
			return back;
		}
		return `
			<button class="btn btn-primary rc-finalize">${__("Finalizar recepción")}</button>
			${back}
			<button class="btn btn-danger rc-cancel">${__("Anular caja")}</button>
		`;
	}

	render_lines() {
		const b = this.box;
		const draft = b.status === "DRAFT";
		const pending = this.local
			.filter((read) => read.state !== "done")
			.map((read) => {
				const label = { queued: __("En cola"), sending: __("Enviando"), failed: __("Falló") }[read.state];
				const retry =
					read.state === "failed"
						? `<button class="btn btn-xs btn-warning rc-retry" data-id="${rc_escape(read.id)}">${__("Reintentar")}</button>`
						: "";
				return `
					<div class="rc-line rc-line-${rc_escape(read.state)}">
						<div style="min-width: 0;">
							<div class="rc-line-code">${rc_escape(read.code)}</div>
							<div class="small">${rc_escape(label)}</div>
						</div>
						${retry}
					</div>`;
			});
		const rows = (b.lines || [])
			.slice()
			.reverse()
			.map((line) => this.line_html(line, draft));
		const all = pending.concat(rows);
		this.$lines.html(
			all.length
				? `<div class="rc-card-title" style="margin-bottom: 4px;">${__("Lecturas de la caja")}</div>${all.join("")}`
				: `<div class="text-muted">${__("Sin lecturas todavía: escanea la primera unidad.")}</div>`
		);
	}

	line_html(line, draft) {
		const discarded = line.status === "DISCARDED";
		let kind = discarded ? "discarded" : line.status === "ERROR" ? "error" : "";
		let detail = rc_escape(line.preview || "");
		let title = `#${rc_escape(line.ordinal)}`;
		if (line.unit) {
			const u = line.unit;
			kind = u.kind;
			title += ` · <span class="rc-line-screen">${rc_escape(__(u.screen))}</span>`;
			const who = u.encargo
				? `${rc_link("Encargo", u.encargo)} · ${rc_escape(u.customer)} · ${rc_link("Sales Order", u.sales_order)}`
				: "";
			detail = [who, u.item ? `${rc_link("Item", u.item)} ${rc_escape(u.item_name)}` : "", rc_link("Recepcion Unidad", u.name)]
				.filter(Boolean)
				.join(" · ");
			if (u.message) {
				detail += `<div class="text-danger small">${rc_escape(u.message)}</div>`;
			}
		} else if (line.status === "ERROR") {
			title += ` · <span class="rc-line-screen">${__("ERROR TÉCNICO - PENDIENTE DE REINTENTO")}</span>`;
		} else if (line.status === "ACTIVE" && this.box.status === "FINALIZING") {
			title += ` · ${__("En proceso")}`;
		}
		const who = discarded
			? __("Quitada por {0}", [line.discarded_by])
			: __("Leída por {0}", [line.scanned_by]);
		const discard =
			draft && line.status === "ACTIVE"
				? `<button class="btn btn-xs btn-default rc-discard" data-line="${rc_escape(line.name)}">${__("Quitar")}</button>`
				: "";
		return `
			<div class="rc-line rc-line-${rc_escape(kind)}">
				<div style="min-width: 0;" class="${discarded ? "rc-line-discarded" : ""}">
					<div class="small">${title}</div>
					<div class="rc-line-code">${rc_escape(line.scanned_code)}</div>
					${detail ? `<div class="small">${detail}</div>` : ""}
					<div class="text-muted small">${rc_escape(who)} · ${rc_escape(frappe.datetime.str_to_user(line.scanned_on))}</div>
				</div>
				${discard}
			</div>`;
	}

	focus() {
		// A touch screen would pop the keyboard on every focus; a Bluetooth scanner there needs one tap on the field.
		if (this.$code && this.$code.length && !("ontouchstart" in window)) {
			this.$code.trigger("focus");
		}
	}

	enqueue(value) {
		// Identical units are scanned in a row: every read is kept and sent one at a time, in order.
		const code = String(value || "").trim();
		if (!code || !this.box || this.box.status !== "DRAFT") {
			return;
		}
		const read = { code, id: rc_scan_id(), state: "queued", box: this.box.name };
		this.local.unshift(read);
		this.queue.push(read);
		this.render_lines();
		this.process();
	}

	retry(id) {
		// Same id: if the first call did reach the server, it answers DUPLICADO instead of a second line.
		const read = this.local.find((row) => row.id === id);
		if (!read || read.state !== "failed") {
			return;
		}
		read.state = "queued";
		this.queue.push(read);
		this.render_lines();
		this.process();
	}

	process() {
		if (this.working || !this.queue.length) {
			return;
		}
		this.working = true;
		const read = this.queue.shift();
		read.state = "sending";
		this.render_lines();
		frappe.call({
			method: RC_BOX_METHOD + "add_line",
			type: "POST",
			args: { box: read.box, code: read.code, scan_event_id: read.id },
			callback: (r) => {
				const line = r.message;
				if (!line) {
					return;
				}
				read.state = "done";
				if (this.box && this.box.name === line.box) {
					const lines = this.box.lines || (this.box.lines = []);
					if (!lines.some((l) => l.name === line.name)) {
						lines.push(line);
					}
				}
				this.warn(line);
			},
			always: () => {
				if (read.state !== "done") {
					read.state = "failed";
				}
				this.local = this.local.filter((row) => row.state !== "done");
				this.working = false;
				if (this.mode === "box" && this.box && this.box.name === read.box) {
					this.render_box_counts();
				}
				if (this.queue.length) {
					this.process();
				} else {
					this.focus();
				}
			},
		});
	}

	render_box_counts() {
		const scrolled = window.scrollY;
		const code = this.$code ? this.$code.val() : "";
		const warn = this.$warn ? this.$warn.html() : "";
		this.render_box();
		this.$code.val(code);
		this.$warn.html(warn);
		window.scrollTo(0, scrolled);
	}

	warn(line) {
		if (navigator.vibrate) {
			navigator.vibrate(line.repeated || line.duplicate ? [300, 100, 300] : 120);
		}
		let text = "";
		if (line.duplicate) {
			text = __("DUPLICADO: esta lectura ya estaba registrada, no se agregó otra.");
		} else if (line.repeated) {
			text = __("Posible doble lectura consecutiva del mismo código. Si fue un error, quita una lectura.");
		}
		this.pending_warn = text ? `<div class="rc-warn">${rc_escape(text)}</div>` : "";
		if (this.$warn) {
			this.$warn.html(this.pending_warn);
		}
	}

	discard(line) {
		frappe.confirm(__("¿Quitar esta lectura de la caja?"), () => {
			frappe.call({
				method: RC_BOX_METHOD + "discard_line",
				type: "POST",
				args: { box: this.box.name, line },
				callback: () => this.refresh_box(),
			});
		});
	}

	finalize() {
		if (this.local.some((read) => read.state !== "done")) {
			frappe.msgprint(__("Hay lecturas sin enviar: espera o reintenta antes de finalizar."));
			return;
		}
		const lines = this.box.lines || [];
		const active = lines.filter((l) => l.status === "ACTIVE").length;
		const discarded = lines.filter((l) => l.status === "DISCARDED").length;
		if (!active) {
			frappe.msgprint(__("Una caja sin lecturas activas no puede finalizarse. Puedes anularla."));
			return;
		}
		frappe.confirm(
			__("Finalizar {0}: {1} lecturas activas, {2} quitadas. Después no se podrá modificar la caja.", [
				this.box.name,
				active,
				discarded,
			]),
			() => {
				this.stop_camera();
				frappe.call({
					method: RC_BOX_METHOD + "finalize_box",
					type: "POST",
					args: { box: this.box.name },
					freeze: true,
					callback: (r) => r.message && this.show_box(r.message),
				});
			}
		);
	}

	cancel() {
		frappe.confirm(
			__("¿Anular la caja {0}? No afecta stock ni Encargos y no se podrá reabrir.", [this.box.name]),
			() => {
				frappe.call({
					method: RC_BOX_METHOD + "cancel_box",
					type: "POST",
					args: { box: this.box.name },
					freeze: true,
					callback: () => this.show_home(),
				});
			}
		);
	}

	// ------------------------------------------------------------ camera

	load_scanner() {
		if (window.__Html5QrcodeLibrary__) {
			return Promise.resolve(window.__Html5QrcodeLibrary__);
		}
		if (!this.scanner_lib) {
			this.scanner_lib = new Promise((resolve, reject) => {
				const script = document.createElement("script");
				script.src = RC_SCANNER_SRC;
				script.onload = () => resolve(window.__Html5QrcodeLibrary__);
				script.onerror = () => {
					this.scanner_lib = null;
					reject(new Error(__("No se pudo cargar el lector")));
				};
				document.head.appendChild(script);
			});
		}
		return this.scanner_lib;
	}

	camera_error(e) {
		const text = String((e && (e.name || e.message)) || e || "");
		if (/NotAllowed|Permission/i.test(text)) return __("Permiso de cámara denegado: habilítalo para este sitio en el navegador");
		if (/NotFound|Overconstrained/i.test(text)) return __("No se encontró la cámara trasera");
		if (/NotReadable|in use/i.test(text)) return __("La cámara está en uso por otra app");
		if (!window.isSecureContext) return __("La cámara requiere https");
		return __("No se pudo abrir la cámara: {0}", [text]);
	}

	async stop_camera() {
		const scanner = this.scanner;
		this.scanner = null;
		if (this.$reader) {
			this.$reader.empty();
		}
		if (!scanner) {
			return;
		}
		try {
			await scanner.stop();
			scanner.clear();
		} catch (e) {}
	}

	async toggle_camera() {
		if (this.scanner) {
			await this.stop_camera();
			return;
		}
		if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
			frappe.show_alert({ message: __("Este navegador no permite usar la cámara: escribe el código"), indicator: "orange" });
			return;
		}
		let lib;
		try {
			lib = await this.load_scanner();
		} catch (e) {
			frappe.show_alert({ message: e.message, indicator: "red" });
			return;
		}
		this.$reader.html(`<div id="rc-reader-view"></div>`);
		const F = lib.Html5QrcodeSupportedFormats;
		const scanner = new lib.Html5Qrcode("rc-reader-view", {
			verbose: false,
			formatsToSupport: [F.EAN_13, F.EAN_8, F.UPC_A, F.UPC_E, F.CODE_128, F.CODE_39, F.ITF, F.QR_CODE],
			experimentalFeatures: { useBarCodeDetectorIfSupported: true },
		});
		this.scanner = scanner;
		try {
			await scanner.start(
				{ facingMode: "environment" },
				{ fps: 10, qrbox: (w, h) => ({ width: Math.floor(w * 0.85), height: Math.floor(Math.min(h, w) * 0.45) }) },
				async (text) => {
					// The camera keeps reading the same label: it closes after one read, one unit per press.
					if (this.scanner !== scanner) {
						return;
					}
					await this.stop_camera();
					this.enqueue(text);
				},
				() => {}
			);
		} catch (e) {
			this.scanner = null;
			this.$reader.empty();
			frappe.show_alert({ message: this.camera_error(e), indicator: "red" });
		}
	}
}
