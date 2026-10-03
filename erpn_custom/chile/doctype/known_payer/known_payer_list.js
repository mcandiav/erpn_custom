frappe.listview_settings["Known Payer"] = {
	add_fields: ["active"],
	onload() {
		// The list is administrative; ComercialFRA keeps read access for Customer / Bank Transaction links.
		if (frappe.user.has_role(["Accounts User", "Accounts Manager", "System Manager"])) return;
		frappe.show_alert({
			message: __("La lista de pagadores conocidos es administrativa. Consúltelos desde la ficha del cliente."),
			indicator: "orange",
		});
		frappe.set_route("pagos-huerfanos");
	},
	get_indicator(doc) {
		return cint(doc.active)
			? [__("Activo"), "green", "active,=,1"]
			: [__("Inactivo"), "gray", "active,=,0"];
	},
};
