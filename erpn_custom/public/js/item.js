frappe.ui.form.on("Item", {
	refresh(frm) {
		frm.set_query("custom_brand_supplier", () => ({
			query: "erpn_custom.encargo.api.suppliers_for_brand_query",
			filters: { brand: frm.doc.brand },
		}));
	},

	brand(frm) {
		if (frm.doc.custom_brand_supplier) {
			frm.set_value("custom_brand_supplier", null);
		}
	},
});
