frappe.ui.form.on("Encargo", {
	refresh(frm) {
		bind_reference_image_paste(frm);
		if (frm.fields_dict.encargo_brand_store) {
			frm.set_query("encargo_brand_store", () => ({
				query: "erpn_custom.encargo.api.encargo_brand_store_query",
			}));
		}
	},
});

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
