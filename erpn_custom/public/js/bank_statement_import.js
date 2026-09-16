frappe.ui.form.on("Bank Statement Import", {
	refresh(frm) {
		frm.set_df_property("custom_banco_chile_import_result", "hidden", 1);
		frm.trigger("show_banco_chile_import_summary");
	},

	show_banco_chile_import_summary(frm) {
		const raw = frm.doc.custom_banco_chile_import_result;
		if (!raw) {
			return;
		}
		let data;
		try {
			data = JSON.parse(raw);
		} catch (e) {
			return;
		}
		if (data.created == null) {
			return;
		}
		frm.dashboard.set_headline(
			__("Created {0}, skipped duplicates {1}, errors {2}.", [
				data.created,
				data.skipped_duplicate || 0,
				data.rejected || 0,
			])
		);
	},
});
