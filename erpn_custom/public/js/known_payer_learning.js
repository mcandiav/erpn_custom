frappe.provide("erpn_custom.known_payer");

erpn_custom.known_payer.offer_learning = function (msg) {
	const learn = (msg && msg.learn) || {};
	if (!learn.offer) return;
	const escape = frappe.utils.escape_html;
	const dialog = new frappe.ui.Dialog({
		title: __("Pagador conocido"),
		fields: [{ fieldtype: "HTML", fieldname: "question" }],
		primary_action_label: __("Sí, recordar"),
		primary_action() {
			dialog.hide();
			frappe.call({
				method: "erpn_custom.chile.known_payer.remember_payer",
				args: { bank_transaction: msg.bank_transaction, customer: msg.customer },
				freeze: true,
				callback(r) {
					show_result(r.message || {});
				},
			});
		},
		secondary_action_label: __("No"),
		secondary_action() {
			dialog.hide();
		},
	});
	dialog.fields_dict.question.$wrapper.html(`
		<p>${__("¿Recordar este RUT de origen para futuros depósitos de {0}?", [
			escape(learn.customer_name || msg.customer),
		])}</p>
		<p class="text-muted">${__("RUT de origen")}: ${escape(learn.payer_tax_id || "")}</p>
	`);
	dialog.show();

	function link(name, label) {
		return `<a href="/app/known-payer/${encodeURIComponent(name)}">${label}</a>`;
	}

	function show_result(m) {
		if (m.ok) {
			const text =
				m.result === "already_exists"
					? __("El pagador conocido ya estaba registrado.")
					: __("Pagador conocido registrado.");
			frappe.show_alert(
				{
					message: `${text} ${link(m.known_payer, __("Ver pagador conocido"))}`,
					indicator: "green",
				},
				10
			);
			return;
		}
		const review = m.known_payer
			? `<br><br>${link(m.known_payer, __("Revisar asociación"))}`
			: "";
		frappe.msgprint({
			title: __("Pagador conocido"),
			message: `${m.message || escape(m.reason || __("Error"))}${review}`,
			indicator: m.reason === "conflict" ? "orange" : "red",
		});
	}
};
