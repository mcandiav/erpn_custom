frappe.pages["pagos-de-clientes"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Pagos de Clientes"),
		single_column: true,
	});
	page.set_primary_action(__("Ejecutar mapeo"), () => enqueue_mapping(page));
	page.main.html(`
		<div class="pagos-clientes-status text-muted"></div>
		<div class="pagos-clientes-kpis" style="display:flex;gap:16px;flex-wrap:wrap;margin:12px 0;"></div>
		<h5>${__("Pendientes / Excepciones")}</h5>
		<div class="pagos-clientes-exceptions"></div>
	`);
	refresh_dashboard(page);
};

function enqueue_mapping(page) {
	frappe.call({
		method: "erpn_custom.chile.page.pagos_de_clientes.pagos_de_clientes.enqueue_mapping",
		freeze: true,
		freeze_message: __("Encolando mapeo"),
		callback(r) {
			if (r.message && r.message.ok) {
				frappe.show_alert({ message: __("Ejecucion iniciada: {0}", [r.message.run]), indicator: "green" });
			} else {
				frappe.show_alert({
					message: __("Ya hay un mapeo en ejecucion"),
					indicator: "orange",
				});
			}
			refresh_dashboard(page);
		},
	});
}

function refresh_dashboard(page) {
	frappe.call({
		method: "erpn_custom.chile.page.pagos_de_clientes.pagos_de_clientes.dashboard",
		callback(r) {
			const data = r.message || {};
			const running = data.running ? __("Mapeo en ejecucion") : __("Motor en reposo");
			const interval = data.interval_minutes || 15;
			const sched = data.scheduler_enabled ? __("cada {0} min", [interval]) : __("job periodico apagado");
			page.main.find(".pagos-clientes-status").text(`${running} · ${sched}`);
			const last = data.last_run || {};
			page.main.find(".pagos-clientes-kpis").html(`
				${kpi(__("Pendientes"), data.pending)}
				${kpi(__("Mapeados ultima ejecucion"), last.mapped_count)}
				${kpi(__("Sin coincidencia"), last.no_match_count)}
				${kpi(__("Conflictos"), last.conflict_count)}
				${kpi(__("Errores"), last.error_count)}
				${kpi(__("Ultima manual"), format_run(data.last_manual))}
				${kpi(__("Ultima automatica"), format_run(data.last_scheduler))}
				${kpi(__("Ultima API banco"), format_run(data.last_api))}
			`);
			const rows = (data.exceptions || [])
				.map(
					(row) => `<tr>
					<td><a href="/app/bank-transaction/${row.name}">${frappe.utils.escape_html(row.name)}</a></td>
					<td>${frappe.datetime.str_to_user(row.date) || ""}</td>
					<td>${frappe.utils.escape_html(row.transaction_id || "")}</td>
					<td>${frappe.utils.escape_html(row.bank_party_name || "")}</td>
					<td>${frappe.utils.escape_html(row.custom_rut_del_pagador || "")}</td>
					<td>${format_number(row.deposit)}</td>
					<td>${frappe.utils.escape_html(row.custom_banco_origen || "")}</td>
					<td>${frappe.utils.escape_html(row.custom_mapping_status || __("Pendiente"))}</td>
				</tr>`
				)
				.join("");
			page.main.find(".pagos-clientes-exceptions").html(`
				<table class="table table-bordered">
					<thead><tr>
						<th>${__("Bank Transaction")}</th>
						<th>${__("Fecha")}</th>
						<th>${__("Transaction ID")}</th>
						<th>${__("Pagador")}</th>
						<th>${__("RUT")}</th>
						<th>${__("Monto")}</th>
						<th>${__("Banco origen")}</th>
						<th>${__("Estado")}</th>
					</tr></thead>
					<tbody>${rows || `<tr><td colspan="8">${__("Sin pendientes")}</td></tr>`}</tbody>
				</table>
			`);
		},
	});
}

function kpi(label, value) {
	return `<div class="border rounded p-3" style="min-width:140px"><div class="text-muted">${label}</div><div class="h5">${value ?? "-"}</div></div>`;
}

function format_run(run) {
	if (!run) return "-";
	const when = run.finished_at || run.started_at || "";
	return `${run.status || ""} ${when}`.trim();
}
