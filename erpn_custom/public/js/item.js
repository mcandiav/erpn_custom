frappe.ui.form.on("Item", {
	refresh(frm) {
		frm.set_query("custom_brand_supplier", () => ({
			query: "erpn_custom.encargo.api.suppliers_for_brand_query",
			filters: { brand: frm.doc.brand },
		}));
		load_classification_options(frm);
	},

	brand(frm) {
		if (frm.doc.custom_brand_supplier) {
			frm.set_value("custom_brand_supplier", null);
		}
	},

	item_group(frm) {
		load_classification_options(frm);
	},

	custom_departamento(frm) {
		load_classification_options(frm);
	},
});

function load_classification_options(frm) {
	frappe.call({
		method: "erpn_custom.catalog.item.get_classification_options",
		args: { item_group: frm.doc.item_group, departamento: frm.doc.custom_departamento },
		callback(r) {
			const data = r.message || {};
			if ((frm.doc.custom_familia || null) !== (data.familia || null)) {
				frm.doc.custom_familia = data.familia || null;
				frm.refresh_field("custom_familia");
				frm.refresh_fields();
			}
			Object.entries(data.options || {}).forEach(([fieldname, values]) => {
				frm.set_df_property(fieldname, "options", values);
			});
		},
	});
}
