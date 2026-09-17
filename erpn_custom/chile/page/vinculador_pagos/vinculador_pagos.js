frappe.pages["vinculador-pagos"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Pagos de Clientes"),
		single_column: true,
	});
	page.set_primary_action(__("Vincular pagos"), () => enqueue_mapping(page));
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
		method: "erpn_custom.chile.page.vinculador_pagos.vinculador_pagos.enqueue_mapping",
		freeze: true,
		freeze_message: __("Encolando vinculación"),
		callback(r) {
			if (r.message && r.message.ok) {
				frappe.show_alert({ message: __("Ejecucion iniciada: {0}", [r.message.run]), indicator: "green" });
			} else {
				frappe.show_alert({
					message: __("Ya hay una vinculación en ejecución"),
					indicator: "orange",
				});
			}
			refresh_dashboard(page);
		},
	});
}

function refresh_dashboard(page) {
	frappe.call({
		method: "erpn_custom.chile.page.vinculador_pagos.vinculador_pagos.dashboard",
		callback(r) {
			const data = r.message || {};
			const running = data.running ? __("Vinculación en ejecución") : __("Motor en reposo");
			const interval = data.interval_minutes || 15;
			const sched = data.scheduler_enabled
				? __("Scheduler activo · cada {0} min", [interval])
				: __("Scheduler apagado");
			page.main.find(".pagos-clientes-status").text(`${running} · ${sched}`);
			const last = data.last_run || {};
			page.main.find(".pagos-clientes-kpis").html(`
				${kpi(__("Pendientes"), data.pending)}
				${kpi(__("Huérfanos"), data.orphan_count)}
				${kpi(__("Vinculados última ejecución"), last.mapped_count)}
				${kpi(__("Sin coincidencia"), last.no_match_count)}
				${kpi(__("Conflictos"), last.conflict_count)}
				${kpi(__("Errores"), last.error_count)}
				${kpi(__("Última Manual"), format_run(data.last_manual))}
				${kpi(__("Última Scheduler"), format_run(data.last_scheduler))}
				${kpi(__("Última API"), format_run(data.last_api))}
			`);
			const rows = (data.exceptions || [])
				.map(
					(row) => `<tr>
					<td><a href="/app/bank-transaction/${encodeURIComponent(row.name)}">${frappe.utils.escape_html(row.name)}</a></td>
					<td>${frappe.datetime.str_to_user(row.date) || ""}</td>
					<td>${frappe.utils.escape_html(row.transaction_id || "")}</td>
					<td>${frappe.utils.escape_html(row.bank_party_name || "")}</td>
					<td>${frappe.utils.escape_html(row.custom_rut_del_pagador || "")}</td>
					<td>${format_amount(row.deposit)}</td>
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

function format_amount(value) {
	return frappe.format(value || 0, { fieldtype: "Currency" });
}
