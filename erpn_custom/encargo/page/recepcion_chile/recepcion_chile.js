const RC_METHOD = "erpn_custom.encargo.reception.";
// Same library and settings as the shopper page; decodes in JS where the browser has no BarcodeDetector (iPhone).
const RC_SCANNER_SRC = "/assets/frappe/node_modules/html5-qrcode/html5-qrcode.min.js";

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
		wrapper.reception.stop_camera();
	}
};

const RC_HISTORY_MAX = 15;

const rc_escape = (value) => frappe.utils.escape_html(value == null ? "" : String(value));

// One id per physical read, created before sending: retries reuse it so the server never counts a unit twice.
function rc_scan_id() {
	if (window.crypto && crypto.randomUUID) {
		return crypto.randomUUID();
	}
	const bytes = new Uint8Array(16);
	(window.crypto || window.msCrypto).getRandomValues(bytes);
	return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

class ReceptionStation {
	constructor(page) {
		this.page = page;
		this.queue = [];
		this.history = [];
		this.working = false;
		this.view = "pending";
		this.scanner = null;
		this.scanner_lib = null;
		this.page.main.html(`
			<style>
				.rc-wrap { max-width: 720px; margin: 0 auto; }
				.rc-row { display: flex; gap: 8px; }
				.rc-code { font-size: 20px; height: 56px; }
				.rc-camera-btn { height: 56px; font-size: 18px; font-weight: 700; white-space: nowrap; }
				.rc-reader { margin-top: 12px; border-radius: 8px; overflow: hidden; }
				.rc-result { margin-top: 16px; padding: 24px 16px; border-radius: 12px; text-align: center; }
				.rc-result-encargo { background: #fff3cd; border: 4px solid #f0ad4e; color: #5c3c00; }
				.rc-result-stock { background: #e3f0ff; border: 4px solid #2f80ed; color: #0b3b7a; }
				.rc-result-warning { background: #fde2e1; border: 4px solid #d9534f; color: #6b1210; }
				.rc-result-title { font-size: 34px; font-weight: 800; letter-spacing: 1px; }
				.rc-result-message { margin-top: 8px; font-weight: 600; }
				.rc-duplicate { margin-top: 8px; font-weight: 800; }
				.rc-history { margin-top: 12px; }
				.rc-history-title { font-weight: 700; margin-bottom: 4px; }
				.rc-history-row { display: flex; justify-content: space-between; align-items: center; gap: 8px;
					padding: 6px 10px; border-left: 4px solid var(--border-color); margin-bottom: 4px; background: var(--subtle-fg); }
				.rc-history-encargo { border-left-color: #f0ad4e; }
				.rc-history-stock { border-left-color: #2f80ed; }
				.rc-history-warning, .rc-history-failed { border-left-color: #d9534f; }
				.rc-history-code { font-family: monospace; word-break: break-all; }
				.rc-result-enc { font-size: 44px; font-weight: 800; margin: 8px 0; word-break: break-all; }
				.rc-result-detail { font-size: 16px; }
				.rc-tabs { display: flex; gap: 8px; margin: 24px 0 8px; }
				.rc-tabs button { flex: 1; height: 44px; font-weight: 600; }
				.rc-card { padding: 10px 12px; border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 8px; }
				.rc-card-title { font-weight: 700; }
				@media (max-width: 480px) {
					.rc-result-title { font-size: 28px; }
					.rc-result-enc { font-size: 34px; }
				}
			</style>
			<div class="rc-wrap">
				<div class="rc-row">
					<input type="text" class="form-control rc-code" autocomplete="off" spellcheck="false"
						inputmode="text" placeholder="${__("Código y Enter")}">
					<button class="btn btn-primary rc-camera-btn">${__("ESCANEAR")}</button>
				</div>
				<div class="rc-reader"></div>
				<div class="rc-result-box"></div>
				<div class="rc-history"></div>
				<div class="rc-tabs">
					<button class="btn btn-default" data-view="pending">${__("Comprados no recibidos")}</button>
					<button class="btn btn-default" data-view="today">${__("Recibidos hoy")}</button>
				</div>
				<input type="text" class="form-control rc-search" placeholder="${__("Buscar: ENC, OV, cliente, marca, código")}">
				<div class="rc-list" style="margin-top: 8px;"></div>
			</div>
		`);
		this.$code = this.page.main.find(".rc-code");
		this.$reader = this.page.main.find(".rc-reader");
		this.$result = this.page.main.find(".rc-result-box");
		this.$history = this.page.main.find(".rc-history");
		this.$history.on("click", ".rc-retry", (e) => this.retry($(e.currentTarget).attr("data-id")));
		this.$list = this.page.main.find(".rc-list");
		this.$search = this.page.main.find(".rc-search");
		this.$code.on("keydown", (e) => {
			if (e.key === "Enter") {
				e.preventDefault();
				this.enqueue(this.$code.val());
				this.$code.val("");
			}
		});
		this.page.main.find(".rc-camera-btn").on("click", () => this.toggle_camera());
		this.page.main.find(".rc-tabs button").on("click", (e) => {
			this.view = $(e.currentTarget).data("view");
			this.load_list();
		});
		this.$search.on("input", frappe.utils.debounce(() => this.load_list(), 300));
		this.load_list();
	}

	on_show() {
		this.focus();
	}

	focus() {
		// A touch screen would pop the keyboard on every focus; a Bluetooth scanner there needs one tap on the field.
		if (!("ontouchstart" in window)) {
			this.$code.trigger("focus");
		}
	}

	enqueue(value) {
		// Identical units are scanned in a row: every read is kept and sent one at a time, in order.
		const code = String(value || "").trim();
		if (!code) {
			return;
		}
		const read = { code, id: rc_scan_id(), state: "queued", result: null };
		this.history.unshift(read);
		this.history = this.history.slice(0, RC_HISTORY_MAX);
		this.queue.push(read);
		this.render_history();
		this.process();
	}

	retry(id) {
		// Same id: if the first call did reach the server, it answers DUPLICADO instead of a second unit.
		const read = this.history.find((row) => row.id === id);
		if (!read || read.state !== "failed") {
			return;
		}
		read.state = "queued";
		this.queue.push(read);
		this.render_history();
		this.process();
	}

	process() {
		if (this.working || !this.queue.length) {
			return;
		}
		this.working = true;
		const read = this.queue.shift();
		read.state = "sending";
		this.render_history();
		frappe.call({
			method: RC_METHOD + "receive_scan",
			type: "POST",
			args: { code: read.code, scan_event_id: read.id },
			callback: (r) => {
				if (r.message) {
					read.state = "done";
					read.result = r.message;
					this.show_result(r.message);
				}
			},
			always: () => {
				if (read.state !== "done") {
					read.state = "failed";
				}
				this.working = false;
				this.render_history();
				if (this.queue.length) {
					this.process();
				} else {
					this.load_list();
					this.focus();
				}
			},
		});
	}

	show_result(data) {
		if (navigator.vibrate) {
			navigator.vibrate(data.kind === "encargo" ? [200, 100, 200] : data.kind === "warning" ? [400] : 150);
		}
		const enc = data.encargo;
		const duplicate = data.duplicate
			? `<div class="rc-result-detail rc-duplicate">${__("DUPLICADO: esta lectura ya estaba registrada, no se creó otra unidad")}</div>`
			: "";
		const encargo_block = enc
			? `
				<div class="rc-result-enc">${rc_escape(enc.name)}</div>
				<div class="rc-result-detail">${rc_escape(enc.customer)} · ${rc_escape(enc.sales_order)}</div>
				<div class="rc-result-detail">${rc_escape(enc.brand)} ${rc_escape(enc.description)}</div>
				<div class="rc-result-detail" style="margin-top: 8px;">${__("Recibidas {0} de {1} · faltan {2}", [
					rc_escape(enc.received_qty || 0),
					rc_escape(enc.requested_qty || 0),
					rc_escape(data.pending_receive_qty || 0),
				])}</div>`
			: `<div class="rc-result-detail">${rc_escape(data.item_name || data.item || __("Sin Encargo pendiente"))}</div>`;
		const message = data.message ? `<div class="rc-result-detail rc-result-message">${rc_escape(data.message)}</div>` : "";
		this.$result.html(`
			<div class="rc-result rc-result-${rc_escape(data.kind)}">
				<div class="rc-result-title">${rc_escape(__(data.screen))}</div>
				${encargo_block}
				<div class="rc-result-detail" style="word-break: break-all;">${rc_escape(data.code)}</div>
				${message}
				${duplicate}
			</div>
		`);
	}

	render_history() {
		if (!this.history.length) {
			this.$history.empty();
			return;
		}
		const label = {
			queued: __("En cola"),
			sending: __("Enviando"),
			failed: __("Falló"),
		};
		this.$history.html(`
			<div class="rc-history-title">${__("Lecturas de esta sesión")}</div>
			${this.history
				.map((read) => {
					const state = read.state === "done" ? __(read.result.screen) + (read.result.duplicate ? " · " + __("DUPLICADO") : "") : label[read.state];
					const enc = read.result && read.result.encargo ? " · " + rc_escape(read.result.encargo.name) : "";
					const retry =
						read.state === "failed"
							? `<button class="btn btn-xs btn-warning rc-retry" data-id="${rc_escape(read.id)}">${__("Reintentar")}</button>`
							: "";
					return `
						<div class="rc-history-row rc-history-${rc_escape(read.result ? read.result.kind : read.state)}">
							<div style="min-width: 0;">
								<div class="rc-history-code">${rc_escape(read.code)}</div>
								<div class="small">${rc_escape(state)}${enc}</div>
							</div>
							${retry}
						</div>
					`;
				})
				.join("")}
		`);
	}

	load_list() {
		this.page.main.find(".rc-tabs button").each((_, el) => {
			$(el).toggleClass("btn-primary", $(el).data("view") === this.view);
			$(el).toggleClass("btn-default", $(el).data("view") !== this.view);
		});
		frappe.call({
			method: RC_METHOD + "list_reception",
			args: { view: this.view, search: this.$search.val() },
			callback: (r) => this.render_list(r.message || []),
		});
	}

	render_list(rows) {
		if (!rows.length) {
			this.$list.html(`<div class="text-muted" style="padding: 12px 0;">${__("Sin registros")}</div>`);
			return;
		}
		this.$list.html(rows.map((row) => (this.view === "today" ? this.unit_card(row) : this.encargo_card(row))).join(""));
	}

	unit_card(row) {
		const who = row.encargo ? `${rc_escape(row.encargo)} · ${rc_escape(row.customer)}` : rc_escape(row.item_name || row.scanned_code);
		return `
			<div class="rc-card">
				<div class="rc-card-title">${rc_escape(__(row.screen))}</div>
				<div>${who}</div>
				<div class="text-muted small" style="word-break: break-all;">${rc_escape(row.scanned_code)}</div>
				<div class="text-muted small">${__("Recibido")} ${rc_escape(frappe.datetime.str_to_user(row.received_on))} · ${rc_escape(
					row.received_by
				)}</div>
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
		this.$reader.empty();
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
