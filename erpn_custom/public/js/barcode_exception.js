// Spec 017: commercial decision on a purchased barcode that differs from the expected Item.
// Spec 020: the decision applies to one purchase event of the Encargo.
// Shared by the Encargo form and the Recepción Comercial page.
window.erpn_barcode_decision = function (action, encargo, override, done, supply_event) {
	const config = {
		approve: {
			method: "approve",
			title: __("Aprobar código para {0}", [encargo]),
			label: __("Aprobar"),
			note: __("El código quedará asociado al Item esperado y las unidades de esta compra continuarán su flujo."),
		},
		reject: {
			method: "reject",
			title: __("Rechazar compra de {0}", [encargo]),
			label: __("Rechazar"),
			note: __(
				"La compra queda en el historial pero deja de abastecer la OV: su cantidad vuelve a la cola del Shopper. Las unidades ya recibidas pasan a stock normal."
			),
		},
	}[action];
	if (!config) {
		return;
	}
	const required = action !== "approve" || override;
	const dialog = new frappe.ui.Dialog({
		title: config.title,
		fields: [
			{ fieldtype: "HTML", options: `<p class="text-muted">${frappe.utils.escape_html(config.note)}</p>` },
			{ fieldname: "comment", fieldtype: "Small Text", label: __("Comentario"), reqd: required ? 1 : 0 },
		],
		primary_action_label: config.label,
		primary_action: (values) => {
			dialog.hide();
			frappe.call({
				method: "erpn_custom.encargo.barcode_exception." + config.method,
				type: "POST",
				args: { encargo, comment: values.comment || null, supply_event: supply_event || null },
				freeze: true,
				callback: () => {
					frappe.show_alert({ message: __("Decisión registrada"), indicator: "green" });
					done && done();
				},
			});
		},
	});
	dialog.show();
};
