frappe.ui.form.on("Configuracion Recepcion FRA", {
	setup(frm) {
		frm.set_query("clearing_account", () => ({
			filters: { is_group: 0, account_type: ["!=", "Stock"] },
		}));
	},

	refresh(frm) {
		if (!frappe.user.has_role("System Manager")) {
			return;
		}
		// Units received before Spec 018 have a reception mark but no inventory movement.
		frm.add_custom_button(__("Regularizar recepciones previas"), () => {
			if (frm.is_dirty()) {
				frappe.msgprint(__("Guarda la configuración antes de regularizar."));
				return;
			}
			frappe.confirm(
				__("Se ingresará al inventario cada recepción anterior a la Spec 018 que no tenga movimiento. ¿Continuar?"),
				() => {
					frappe.call({
						method: "erpn_custom.encargo.reception.regularize_previous_receptions",
						freeze: true,
						callback(r) {
							const rows = r.message || [];
							if (!rows.length) {
								frappe.msgprint(__("No hay recepciones previas por regularizar."));
								return;
							}
							const html = rows
								.map(
									(row) =>
										`<tr><td>${frappe.utils.escape_html(row.encargo)}</td><td>${frappe.utils.escape_html(
											row.unit
										)}</td><td>${frappe.utils.escape_html(row.screen)}</td><td>${frappe.utils.escape_html(
											row.message || ""
										)}</td></tr>`
								)
								.join("");
							frappe.msgprint({
								title: __("Regularización"),
								message: `<table class="table table-bordered"><tr><th>Encargo</th><th>Unidad</th><th>Resultado</th><th>Detalle</th></tr>${html}</table>`,
								wide: true,
							});
						},
					});
				}
			);
		});
	},
});
