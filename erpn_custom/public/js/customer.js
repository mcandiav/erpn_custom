frappe.ui.form.on("Customer", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.custom_tax_id_type) {
			frm.set_value("custom_tax_id_type", "RUT");
		}
	},
	custom_tax_id_type(frm) {
		const type = frm.doc.custom_tax_id_type;
		if (type === "RUT") {
			frm.set_value("custom_tax_id_country", "Chile");
		} else if (type === "CPF") {
			frm.set_value("custom_tax_id_country", "Brazil");
		}
	},
});
