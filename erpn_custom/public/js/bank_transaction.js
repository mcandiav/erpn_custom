frappe.ui.form.on("Bank Transaction", {
	refresh(frm) {
		const orphan =
			flt(frm.doc.deposit) > 0 &&
			!frm.doc.party &&
			cint(frm.doc.docstatus) < 2;
		if (!orphan) return;
		frm.add_custom_button(__("Asignar a Customer"), () => {
			frappe.prompt(
				[
					{
						fieldname: "customer",
						fieldtype: "Link",
						options: "Customer",
						label: __("Customer beneficiario"),
						reqd: 1,
					},
				],
				(values) => {
					frappe.call({
						method: "erpn_custom.chile.page.vinculador_pagos.vinculador_pagos.assign_orphan",
						args: {
							bank_transaction: frm.doc.name,
							customer: values.customer,
						},
						freeze: true,
						freeze_message: __("Asignando depósito"),
						callback(r) {
							const msg = r.message || {};
							if (msg.ok) {
								frappe.show_alert({
									message: __(
										"Asignado → {0} · PE {1}",
										[msg.customer, msg.payment_entry || "-"]
									),
									indicator: "green",
								});
								frm.reload_doc();
							} else {
								frappe.msgprint(msg.message || msg.reason || __("Error"));
							}
						},
					});
				},
				__("Asignar pago huérfano"),
				__("Asignar")
			);
		});
	},
});
