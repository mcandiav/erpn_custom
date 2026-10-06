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

const rc_escape = (value) => frappe.utils.escape_html(value == null ? "" : String(value));

class ReceptionStation {
	constructor(page) {
		this.page = page;
		this.queue = [];
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
				.rc-result-title { font-size: 34px; font-weight: 800; letter-spacing: 1px; }
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
		this.queue.push(code);
		this.process();
	}

	process() {
		if (this.working || !this.queue.length) {
			return;
		}
		this.working = true;
		const code = this.queue.shift();
		frappe.call({
			method: RC_METHOD + "receive_scan",
			args: { code },
			callback: (r) => {
				if (r.message) {
					this.show_result(r.message);
				}
			},
			always: () => {
				this.working = false;
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
			navigator.vibrate(data.match === "encargo" ? [200, 100, 200] : 150);
		}
		if (data.match === "encargo") {
			const enc = data.encargo || {};
			const left = data.pending_left
				? `<div class="rc-result-detail" style="margin-top: 8px;">${__("Quedan {0} Encargos por recibir con este código", [data.pending_left])}</div>`
				: "";
			this.$result.html(`
				<div class="rc-result rc-result-encargo">
					<div class="rc-result-title">${__("APARTAR")}</div>
					<div class="rc-result-enc">${rc_escape(enc.name)}</div>
					<div class="rc-result-detail">${rc_escape(enc.customer)} · ${rc_escape(enc.sales_order)}</div>
					<div class="rc-result-detail">${rc_escape(enc.brand)} ${rc_escape(enc.description)}</div>
					${left}
				</div>
			`);
			return;
		}
		this.$result.html(`
			<div class="rc-result rc-result-stock">
				<div class="rc-result-title">${__("STOCK NORMAL")}</div>
				<div class="rc-result-detail">${__("Sin Encargo pendiente")}</div>
				<div class="rc-result-detail" style="word-break: break-all;">${rc_escape(data.code)}</div>
			</div>
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
		this.$list.html(
			rows
				.map((row) => {
					const when =
						this.view === "today"
							? `${__("Recibido")} ${rc_escape(frappe.datetime.str_to_user(row.received_on))} · ${rc_escape(row.received_by)}`
							: `${__("Comprado")} ${rc_escape(frappe.datetime.str_to_user(row.purchased_on))} · ${rc_escape(
									row.purchase_supplier || row.proposed_supplier_name
							  )}`;
					return `
						<div class="rc-card">
							<div class="rc-card-title">${rc_escape(row.name)} · ${rc_escape(row.customer)}</div>
							<div>${rc_escape(row.brand)} ${rc_escape(row.description)}</div>
							<div class="text-muted small">${when}</div>
						</div>
					`;
				})
				.join("")
		);
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
