frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		frm.trigger("show_customer_credit");
	},

	customer(frm) {
		frm.trigger("show_customer_credit");
	},

	show_customer_credit(frm) {
		if (!frm.doc.customer || frm.doc.docstatus === 2) {
			return;
		}
		frappe.call({
			method: "erpn_custom.chile.sales_order_credit.credit_summary",
			args: {
				sales_order: frm.doc.name,
				customer: frm.doc.customer,
			},
			callback(r) {
				const data = r.message;
				if (!data) {
					return;
				}
				frm.dashboard.set_headline(
					__(
						"Saldo a favor {0} · Total {1} · Anticipo {2} · Pendiente {3}",
						[
							format_currency(data.available, frm.doc.currency),
							format_currency(data.grand_total, frm.doc.currency),
							format_currency(data.advance_paid, frm.doc.currency),
							format_currency(data.pending, frm.doc.currency),
						]
					)
				);
				frm.remove_custom_button(__("Aplicar saldo a favor"));
				if (frm.doc.docstatus < 2 && data.available > 0 && data.pending > 0 && !frm.is_new()) {
					frm.add_custom_button(__("Aplicar saldo a favor"), () => apply_credit_dialog(frm, data));
				}
			},
			error() {
				// Roles fuera de ALLOWED u OV sin crédito: no bloquear el formulario.
			},
		});
	},
});

function apply_credit_dialog(frm, data) {
	const proposed = data.proposed || 0;
	const dialog = new frappe.ui.Dialog({
		title: __("Aplicar saldo a favor"),
		fields: [
			{
				fieldname: "available",
				label: __("Saldo a favor disponible del cliente"),
				fieldtype: "Currency",
				default: data.available,
				read_only: 1,
				options: frm.doc.currency,
			},
			{
				fieldname: "pending",
				label: __("Saldo pendiente de esta Nota de Venta"),
				fieldtype: "Currency",
				default: data.pending,
				read_only: 1,
				options: frm.doc.currency,
			},
			{
				fieldname: "amount",
				label: __("Monto a aplicar"),
				fieldtype: "Currency",
				default: proposed,
				reqd: 1,
				options: frm.doc.currency,
			},
		],
		primary_action_label: __("Confirmar"),
		primary_action(values) {
			dialog.hide();
			frappe.call({
				method: "erpn_custom.chile.sales_order_credit.apply_credit",
				args: {
					sales_order: frm.doc.name,
					amount: values.amount,
				},
				freeze: true,
				freeze_message: __("Aplicando saldo a favor"),
				callback() {
					frm.reload_doc();
				},
			});
		},
	});
	dialog.show();
}
