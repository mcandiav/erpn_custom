frappe.ui.form.on("Encargo", {
	refresh(frm) {
		bind_reference_image_paste(frm);
		render_reference_image_preview(frm);
		render_reference_url_link(frm);
		render_purchase_images_preview(frm);
		show_customer_contact_alert(frm);
		add_reception_button(frm);
		add_barcode_exception_actions(frm);
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
	if (frm.doc.purchase_status !== "PURCHASED" || !frappe.user.has_role(["ComercialFRA", "System Manager"])) {
		return;
	}
	frm.add_custom_button(__("Ver recepción"), () => {
		frappe.route_options = { search: frm.doc.name };
		frappe.set_route("recepcion-comercial");
	});
}

// Spec 017 §12.3: the server checks who may resolve; the buttons only offer the next valid step.
function add_barcode_exception_actions(frm) {
	const status = frm.doc.barcode_exception_status;
	if (frm.doc.status !== "Open" || frm.doc.purchase_status !== "PURCHASED") {
		return;
	}
	if (status === "PENDING_APPROVAL") {
		frm.dashboard.set_headline_alert(
			__("Excepción barcode: se compró {0} y el Item {1} espera {2}. Aprobar o rechazar.", [
				frm.doc.purchase_barcode,
				frm.doc.expected_item,
				frm.doc.expected_barcode || __("sin código"),
			]),
			"orange"
		);
	} else if (status === "REJECTED") {
		frm.dashboard.set_headline_alert(
			__("Compra rechazada - decide el vendedor: anular o modificar la OV, o solicitar nueva compra."),
			"red"
		);
	} else {
		return;
	}
	if (!frappe.user.has_role(["ComercialFRA", "System Manager"])) {
		return;
	}
	const override = frappe.user.has_role("System Manager") && !frappe.user.has_role("ComercialFRA");
	const decide = (action) => erpn_barcode_decision(action, frm.doc.name, override, () => frm.reload_doc());
	const group = __("Excepción barcode");
	if (status === "PENDING_APPROVAL") {
		frm.add_custom_button(__("Aprobar"), () => decide("approve"), group);
		frm.add_custom_button(__("Rechazar"), () => decide("reject"), group);
	} else {
		frm.add_custom_button(__("Solicitar nueva compra"), () => decide("new_purchase"), group);
	}
}

function show_customer_contact_alert(frm) {
	if (!frm.doc.needs_commercial_review || frm.doc.purchase_status !== "PENDING") {
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
