frappe.ui.form.on("Customer", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.custom_tax_id_type) {
			frm.set_value("custom_tax_id_type", "RUT");
		}
	},
	refresh(frm) {
		if (!frm.is_new()) show_known_payers(frm);
	},
	custom_tax_id_type(frm) {
		const type = frm.doc.custom_tax_id_type;
		if (type === "RUT") {
			frm.set_value("custom_tax_id_country", "Chile");
		} else if (type === "CPF") {
			frm.set_value("custom_tax_id_country", "Brazil");
		}
	},
});

function show_known_payers(frm) {
	frappe.call({
		method: "erpn_custom.chile.known_payer.customer_known_payers",
		args: { customer: frm.doc.name },
		callback(r) {
			const data = r.message || {};
			if (!data.can_read) return;
			const escape = frappe.utils.escape_html;
			const rows = data.rows || [];
			const body = rows.length
				? `<table class="table table-bordered table-sm">
					<thead><tr>
						<th>${__("RUT pagador")}</th>
						<th>${__("Nombre informado por banco")}</th>
						<th>${__("Estado")}</th>
						<th>${__("Fecha de asociación")}</th>
						<th>${__("Último uso")}</th>
					</tr></thead>
					<tbody>${rows
						.map(
							(row) => `<tr>
							<td><a href="/app/known-payer/${encodeURIComponent(row.name)}">${escape(row.payer_tax_id || "")}</a></td>
							<td>${escape(row.payer_name || "")}</td>
							<td>${cint(row.active) ? __("Activo") : __("Inactivo")}</td>
							<td>${row.confirmed_on ? frappe.datetime.str_to_user(row.confirmed_on) : ""}</td>
							<td>${row.last_used_on ? frappe.datetime.str_to_user(row.last_used_on) : ""}</td>
						</tr>`
						)
						.join("")}</tbody>
				</table>`
				: `<p class="text-muted">${__("No hay pagadores conocidos asociados.")}</p>`;
			const add = data.can_create
				? `<button class="btn btn-xs btn-default btn-add-known-payer" type="button">${__("Agregar pagador conocido")}</button>`
				: "";
			if (frm.known_payer_section) frm.known_payer_section.remove();
			frm.known_payer_section = frm.dashboard.add_section(
				`${body}${add}`,
				__("Pagadores conocidos")
			);
			frm.dashboard.show();
			frm.known_payer_section.find(".btn-add-known-payer").on("click", () =>
				frappe.new_doc("Known Payer", { customer: frm.doc.name, source: "Manual" })
			);
		},
	});
}
