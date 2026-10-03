frappe.ui.form.on("Bank Transaction", {
	refresh(frm) {
		show_attribution(frm);
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
								frappe.require("/assets/erpn_custom/js/known_payer_learning.js", () =>
									erpn_custom.known_payer.offer_learning(msg)
								);
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

function show_attribution(frm) {
	frm.set_intro("");
	const rule = frm.doc.custom_attribution_rule;
	if (!frm.doc.party || !rule) return;
	const escape = frappe.utils.escape_html;
	const labels = {
		"Exact Tax ID": __("RUT del cliente"),
		"manual-attribution-v1": __("Manual"),
		"Known Payer": __("Pagador conocido"),
	};
	const lines = [
		`${__("Cliente identificado")}: <a href="/app/customer/${encodeURIComponent(frm.doc.party)}">${escape(frm.doc.party)}</a>`,
		`${__("Método de identificación")}: ${escape(labels[rule] || rule)}`,
	];
	if (frm.doc.custom_known_payer) {
		lines.push(
			`${__("Pagador conocido")}: <a href="/app/known-payer/${encodeURIComponent(frm.doc.custom_known_payer)}">${escape(frm.doc.custom_rut_del_pagador || "")} · ${escape(frm.doc.custom_known_payer)}</a>`
		);
	}
	frm.set_intro(lines.join("<br>"), "blue");
}
