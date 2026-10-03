frappe.ui.form.on("Known Payer", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Ver cliente"), () =>
			frappe.set_route("Form", "Customer", frm.doc.customer)
		);
		if (frm.doc.source_bank_transaction) {
			frm.add_custom_button(__("Ver movimiento de origen"), () =>
				frappe.set_route("Form", "Bank Transaction", frm.doc.source_bank_transaction)
			);
		}
		const manager =
			frappe.user.has_role("Accounts Manager") || frappe.user.has_role("System Manager");
		if (!manager) return;
		if (cint(frm.doc.active)) {
			frm.add_custom_button(__("Desactivar asociación"), () => confirm_deactivate(frm));
		} else {
			frm.add_custom_button(__("Reactivar asociación"), () =>
				change_status(frm, "reactivate")
			);
		}
	},
});

function confirm_deactivate(frm) {
	const rut = frappe.utils.escape_html(frm.doc.payer_tax_id || "");
	const customer = frappe.utils.escape_html(frm.doc.customer || "");
	const dialog = new frappe.ui.Dialog({
		title: __("¿Desactivar este pagador conocido?"),
		fields: [{ fieldtype: "HTML", fieldname: "body" }],
		primary_action_label: __("Desactivar"),
		primary_action() {
			dialog.hide();
			change_status(frm, "deactivate");
		},
		secondary_action_label: __("Cancelar"),
		secondary_action() {
			dialog.hide();
		},
	});
	dialog.fields_dict.body.$wrapper.html(`
		<p>${__(
			"Los futuros depósitos provenientes del RUT {0} dejarán de asociarse automáticamente a {1}.",
			[rut, customer]
		)}</p>
		<p>${__("Los movimientos ya procesados no serán modificados.")}</p>
	`);
	dialog.show();
}

function change_status(frm, action) {
	frappe.call({
		method: `erpn_custom.chile.known_payer.${action}`,
		args: { name: frm.doc.name },
		freeze: true,
		callback() {
			frm.reload_doc();
		},
	});
}
