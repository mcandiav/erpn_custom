frappe.ui.form.on("Encargo", {
	refresh(frm) {
		bind_reference_image_paste(frm);
		render_reference_image_preview(frm);
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
});

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
