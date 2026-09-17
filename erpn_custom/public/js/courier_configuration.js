frappe.ui.form.on("Courier Configuration", {
	onload(frm) {
		if (!frm.is_new()) {
			return;
		}
		if ((frm.doc.credentials || []).length) {
			return;
		}
		["coverage_api_key", "rating_api_key", "shipping_api_key"].forEach((key) => {
			frm.add_child("credentials", { credential_key: key });
		});
		frm.refresh_field("credentials");
	},
});
