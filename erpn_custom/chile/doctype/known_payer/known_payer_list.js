frappe.listview_settings["Known Payer"] = {
	add_fields: ["active"],
	get_indicator(doc) {
		return cint(doc.active)
			? [__("Activo"), "green", "active,=,1"]
			: [__("Inactivo"), "gray", "active,=,0"];
	},
};
