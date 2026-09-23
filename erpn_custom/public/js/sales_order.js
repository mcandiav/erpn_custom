frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		frm.trigger("show_customer_credit");
		frm.trigger("setup_encargo_ui");
	},

	customer(frm) {
		frm.trigger("show_customer_credit");
	},

	setup_encargo_ui(frm) {
		// Hide native reserve-stock UI; Spec 013 drives partial SRE via hooks.
		frm.set_df_property("reserve_stock", "hidden", 1);
		if (frm.fields_dict.items?.grid) {
			frm.fields_dict.items.grid.update_docfield_property("reserve_stock", "hidden", 1);
		}

		frm.remove_custom_button(__("Agregar Encargo"));
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			frm.add_custom_button(__("Agregar Encargo"), () => open_encargo_dialog(frm));
		}
	},

	show_customer_credit(frm) {
		if (!frm.doc.customer || frm.doc.docstatus === 2) {
			return;
		}
		frappe.call({
			method: "erpn_custom.chile.sales_order_credit.credit_summary",
			args: {
				sales_order: frm.doc.name,
				customer: frm.doc.customer,
			},
			callback(r) {
				const data = r.message;
				if (!data) {
					return;
				}
				frm.dashboard.set_headline(
					__(
						"Saldo a favor {0} · Total {1} · Anticipo {2} · Pendiente {3}",
						[
							format_currency(data.available, frm.doc.currency),
							format_currency(data.grand_total, frm.doc.currency),
							format_currency(data.advance_paid, frm.doc.currency),
							format_currency(data.pending, frm.doc.currency),
						]
					)
				);
				frm.remove_custom_button(__("Aplicar saldo a favor"));
				if (frm.doc.docstatus < 2 && data.available > 0 && data.pending > 0 && !frm.is_new()) {
					frm.add_custom_button(__("Aplicar saldo a favor"), () => apply_credit_dialog(frm, data));
				}
			},
			error() {
				// Roles fuera de ALLOWED u OV sin crédito: no bloquear el formulario.
			},
		});
	},
});

function apply_credit_dialog(frm, data) {
	const proposed = data.proposed || 0;
	const dialog = new frappe.ui.Dialog({
		title: __("Aplicar saldo a favor"),
		fields: [
			{
				fieldname: "available",
				label: __("Saldo a favor disponible del cliente"),
				fieldtype: "Currency",
				default: data.available,
				read_only: 1,
				options: frm.doc.currency,
			},
			{
				fieldname: "pending",
				label: __("Saldo pendiente de esta Nota de Venta"),
				fieldtype: "Currency",
				default: data.pending,
				read_only: 1,
				options: frm.doc.currency,
			},
			{
				fieldname: "amount",
				label: __("Monto a aplicar"),
				fieldtype: "Currency",
				default: proposed,
				reqd: 1,
				options: frm.doc.currency,
			},
		],
		primary_action_label: __("Confirmar"),
		primary_action(values) {
			dialog.hide();
			frappe.call({
				method: "erpn_custom.chile.sales_order_credit.apply_credit",
				args: {
					sales_order: frm.doc.name,
					amount: values.amount,
				},
				freeze: true,
				freeze_message: __("Aplicando saldo a favor"),
				callback() {
					frm.reload_doc();
				},
			});
		},
	});
	dialog.show();
}

function open_encargo_dialog(frm) {
	let pasted_b64 = null;
	let pasted_name = null;

	const dialog = new frappe.ui.Dialog({
		title: __("Agregar Encargo"),
		fields: [
			{ fieldname: "description", label: __("Descripción"), fieldtype: "Small Text", reqd: 1 },
			{
				fieldname: "brand",
				label: __("Marca"),
				fieldtype: "Link",
				options: "Brand",
				reqd: 1,
			},
			{
				fieldname: "supplier",
				label: __("Proveedor"),
				fieldtype: "Link",
				options: "Supplier",
				reqd: 1,
			},
			{ fieldname: "qty", label: __("Cantidad"), fieldtype: "Float", default: 1, reqd: 1 },
			{
				fieldname: "rate",
				label: __("Precio de venta"),
				fieldtype: "Currency",
				options: frm.doc.currency,
			},
			{ fieldname: "model", label: __("Modelo"), fieldtype: "Data" },
			{ fieldname: "size", label: __("Talla"), fieldtype: "Data" },
			{ fieldname: "color", label: __("Color"), fieldtype: "Data" },
			{ fieldname: "reference_url", label: __("URL"), fieldtype: "Data" },
			{ fieldname: "notes", label: __("Observaciones"), fieldtype: "Small Text" },
			{
				fieldname: "image_hint",
				fieldtype: "HTML",
				options:
					"<p class='text-muted'>" +
					__("Pegue una imagen (Ctrl+V) o adjunte un archivo.") +
					"</p>",
			},
			{ fieldname: "image", label: __("Imagen"), fieldtype: "Attach Image" },
		],
		primary_action_label: __("Crear Encargo"),
		primary_action(values) {
			const args = {
				sales_order: frm.doc.name,
				description: values.description,
				brand: values.brand,
				supplier: values.supplier,
				qty: values.qty,
				rate: values.rate,
				model: values.model,
				size: values.size,
				color: values.color,
				reference_url: values.reference_url,
				notes: values.notes,
			};
			if (pasted_b64 && pasted_name) {
				args.image_filename = pasted_name;
				args.image_b64 = pasted_b64;
			} else if (values.image) {
				args.reference_image = values.image;
			}
			dialog.hide();
			frappe.call({
				method: "erpn_custom.encargo.api.create_unknown_encargo",
				args,
				freeze: true,
				freeze_message: __("Creando Encargo"),
				callback() {
					frm.reload_doc();
				},
			});
		},
	});

	dialog.$wrapper.on("paste", (e) => {
		const items = e.originalEvent && e.originalEvent.clipboardData && e.originalEvent.clipboardData.items;
		if (!items) {
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
			const reader = new FileReader();
			reader.onload = () => {
				pasted_b64 = String(reader.result).split(",")[1] || "";
				pasted_name = file.name || "referencia.png";
				frappe.show_alert({
					message: __("Imagen lista para adjuntar: {0}", [pasted_name]),
					indicator: "green",
				});
			};
			reader.readAsDataURL(file);
			return;
		}
	});

	dialog.show();
}
