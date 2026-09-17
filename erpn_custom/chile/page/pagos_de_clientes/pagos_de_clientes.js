frappe.pages["pagos-de-clientes"].on_page_load = function (wrapper) {
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
		<hr>
		<div id="pagos-huerfanos">
			<h5>${__("Pagos huérfanos")}</h5>
			<p class="text-muted">${__("Depósitos sin Customer. Asigne el beneficiario comercial sin alterar el pagador bancario.")}</p>
			<div class="pagos-clientes-orphans"></div>
		</div>
	`);
	page.orphan_controls = {};
	refresh_dashboard(page);
	if (window.location.hash === "#pagos-huerfanos") {
		setTimeout(() => {
			const el = document.getElementById("pagos-huerfanos");
			if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
		}, 400);
	}
};

function enqueue_mapping(page) {
	frappe.call({
		method: "erpn_custom.chile.page.pagos_de_clientes.pagos_de_clientes.enqueue_mapping",
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
		method: "erpn_custom.chile.page.pagos_de_clientes.pagos_de_clientes.dashboard",
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
			render_orphans(page, data.orphans || []);
		},
	});
}

function render_orphans(page, orphans) {
	page.orphan_controls = {};
	const $wrap = page.main.find(".pagos-clientes-orphans");
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
			<td>${frappe.utils.escape_html(row.bank_party_account_number || "")}</td>
			<td>${format_amount(row.deposit)}</td>
			<td>${frappe.utils.escape_html(row.transaction_id || "")}</td>
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
				<th>${__("Pagador bancario")}</th>
				<th>${__("RUT pagador")}</th>
				<th>${__("Banco origen")}</th>
				<th>${__("Cuenta origen")}</th>
				<th>${__("Monto")}</th>
				<th>${__("ID transacción")}</th>
				<th>${__("Estado mapping")}</th>
				<th>${__("Customer")}</th>
				<th>${__("Acción")}</th>
			</tr></thead>
			<tbody>${body}</tbody>
		</table>
	`);
	orphans.forEach((row) => {
		const $row = $wrap.find("tr").filter(function () {
			return $(this).attr("data-bt") === row.name;
		});
		const $cell = $row.find(".orphan-customer-cell");
		const control = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				options: "Customer",
				fieldname: `orphan_customer_${row.name}`,
				placeholder: __("Customer beneficiario"),
				only_select: 1,
			},
			parent: $cell.get(0),
			render_input: true,
		});
		control.refresh();
		page.orphan_controls[row.name] = control;
	});
	$wrap.find(".btn-assign-orphan").on("click", function () {
		const bt = $(this).closest("tr").attr("data-bt");
		const control = page.orphan_controls[bt];
		const customer = control ? control.get_value() : "";
		if (!customer) {
			frappe.show_alert({ message: __("Seleccione un Customer"), indicator: "orange" });
			return;
		}
		frappe.call({
			method: "erpn_custom.chile.page.pagos_de_clientes.pagos_de_clientes.assign_orphan",
			args: { bank_transaction: bt, customer },
			freeze: true,
			freeze_message: __("Asignando depósito"),
			callback(r) {
				const msg = r.message || {};
				if (msg.ok) {
					frappe.show_alert({
						message: __(
							"Asignado {0} → {1} · PE {2} · {3}",
							[msg.bank_transaction, msg.customer, msg.payment_entry || "-", format_amount(msg.amount)]
						),
						indicator: "green",
					});
					refresh_dashboard(page);
				} else {
					frappe.msgprint({
						title: __("No se pudo asignar"),
						message: msg.message || msg.reason || __("Error"),
						indicator: "red",
					});
					if (msg.reason === "conflict") {
						refresh_dashboard(page);
					}
				}
			},
		});
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
