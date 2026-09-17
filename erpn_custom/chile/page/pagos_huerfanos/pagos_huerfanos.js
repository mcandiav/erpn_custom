frappe.pages["pagos-huerfanos"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Pagos huérfanos"),
		single_column: true,
	});
	page.set_primary_action(__("Actualizar"), () => refresh_orphans(page));
	page.main.html(`
		<p class="text-muted">${__("Depósitos sin Customer (estado huérfano).")}</p>
		<div class="pagos-huerfanos-list"></div>
	`);
	page.orphan_controls = {};
	refresh_orphans(page);
};

function refresh_orphans(page) {
	frappe.call({
		method: "erpn_custom.chile.page.vinculador_pagos.vinculador_pagos.dashboard",
		callback(r) {
			const orphans = (r.message && r.message.orphans) || [];
			render_orphans(page, orphans);
		},
	});
}

function render_orphans(page, orphans) {
	page.orphan_controls = {};
	const $wrap = page.main.find(".pagos-huerfanos-list");
	if (!orphans.length) {
		$wrap.html(`<p class="text-muted">${__("Sin pagos huérfanos")}</p>`);
		return;
	}
	const body = orphans
		.map(
			(row) => `<tr data-bt="${frappe.utils.escape_html(row.name)}">
			<td>${frappe.datetime.str_to_user(row.date) || ""}</td>
			<td><a href="/app/bank-transaction/${encodeURIComponent(row.name)}">${frappe.utils.escape_html(row.name)}</a></td>
			<td>${frappe.utils.escape_html(row.bank_party_name || "")}</td>
			<td>${frappe.utils.escape_html(row.custom_rut_del_pagador || "")}</td>
			<td>${frappe.utils.escape_html(row.custom_banco_origen || "")}</td>
			<td>${frappe.format(row.deposit || 0, { fieldtype: "Currency" })}</td>
			<td>${frappe.utils.escape_html(row.custom_mapping_status || "")}</td>
			<td class="orphan-customer-cell" style="min-width:220px"></td>
			<td><button class="btn btn-xs btn-primary btn-assign-orphan" type="button">${__("Asignar")}</button></td>
		</tr>`
		)
		.join("");
	$wrap.html(`
		<table class="table table-bordered">
			<thead><tr>
				<th>${__("Fecha")}</th>
				<th>${__("Bank Transaction")}</th>
				<th>${__("Pagador")}</th>
				<th>${__("RUT")}</th>
				<th>${__("Banco")}</th>
				<th>${__("Monto")}</th>
				<th>${__("Estado")}</th>
				<th>${__("Customer")}</th>
				<th></th>
			</tr></thead>
			<tbody>${body}</tbody>
		</table>
	`);
	orphans.forEach((row) => {
		const $row = $wrap.find("tr").filter(function () {
			return $(this).attr("data-bt") === row.name;
		});
		const control = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				options: "Customer",
				fieldname: `orphan_customer_${row.name}`,
				placeholder: __("Customer"),
				only_select: 1,
			},
			parent: $row.find(".orphan-customer-cell").get(0),
			render_input: true,
		});
		control.refresh();
		page.orphan_controls[row.name] = control;
	});
	$wrap.find(".btn-assign-orphan").on("click", function () {
		const bt = $(this).closest("tr").attr("data-bt");
		const customer = (page.orphan_controls[bt] || {}).get_value
			? page.orphan_controls[bt].get_value()
			: "";
		if (!customer) {
			frappe.show_alert({ message: __("Seleccione un Customer"), indicator: "orange" });
			return;
		}
		frappe.call({
			method: "erpn_custom.chile.page.vinculador_pagos.vinculador_pagos.assign_orphan",
			args: { bank_transaction: bt, customer },
			freeze: true,
			callback(r) {
				const msg = r.message || {};
				if (msg.ok) {
					frappe.show_alert({
						message: __("Asignado {0} → {1}", [msg.bank_transaction, msg.customer]),
						indicator: "green",
					});
					refresh_orphans(page);
				} else {
					frappe.msgprint(msg.message || msg.reason || __("Error"));
				}
			},
		});
	});
}
