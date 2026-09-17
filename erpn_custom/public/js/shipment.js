frappe.ui.form.on("Shipment", {
	refresh(frm) {
		frm.set_query("custom_courier_configuration", () => ({
			filters: { enabled: 1 },
		}));
		_render_courier_actions(frm);
	},

	custom_courier_configuration(frm) {
		_render_courier_actions(frm);
	},
});

function _render_courier_actions(frm) {
	frm.remove_custom_button(__("Validar courier"));
	frm.remove_custom_button(__("Cotizar envío"));
	frm.remove_custom_button(__("Crear envío en Chilexpress"));
	frm.remove_custom_button(__("Obtener etiqueta"));
	frm.remove_custom_button(__("Actualizar tracking"));
	frm.remove_custom_button(__("Reconciliar OT"));

	if (!frm.doc.custom_courier_configuration || frm.is_new()) {
		return;
	}

	const state = frm.doc.custom_courier_creation_state || "Not Requested";
	const hasOt = !!(frm.doc.shipment_id || frm.doc.awb_number);
	const env = frm.doc.custom_courier_environment || "";

	if (env === "Test") {
		frm.dashboard.set_headline_alert(
			__("Courier Environment: Test"),
			"orange"
		);
	}

	frm.add_custom_button(__("Validar courier"), () => {
		frappe.call({
			method: "erpn_custom.chile.shipment_service.preflight_shipment",
			args: { shipment_name: frm.doc.name },
			freeze: true,
			callback(r) {
				const res = r.message || {};
				if (res.ok) {
					frappe.msgprint({ message: __("Preflight OK"), indicator: "green" });
					return;
				}
				_show_errors(res.errors || []);
			},
		});
	}, __("Courier"));

	if (!hasOt && state !== "Created") {
		frm.add_custom_button(__("Cotizar envío"), () => {
			frappe.call({
				method: "erpn_custom.chile.shipment_service.quote_shipment",
				args: { shipment_name: frm.doc.name },
				freeze: true,
				callback(r) {
					const res = r.message || {};
					if (!res.ok) {
						_show_errors(res.errors || []);
						return;
					}
					_pick_quote(frm, res.quotes || []);
				},
			});
		}, __("Courier"));
	}

	if (
		!hasOt &&
		frm.doc.custom_courier_service_code &&
		!["Creating", "Created", "Uncertain"].includes(state)
	) {
		frm.add_custom_button(__("Crear envío en Chilexpress"), () => {
			frappe.confirm(__("¿Crear OT Chilexpress Test para este Shipment?"), () => {
				frappe.call({
					method: "erpn_custom.chile.shipment_service.create_courier_shipment",
					args: { shipment_name: frm.doc.name },
					freeze: true,
					callback(r) {
						const res = r.message || {};
						if (!res.ok) {
							_show_errors(res.errors || []);
							return;
						}
						frappe.show_alert({
							message: __("OT creada: {0}", [res.shipment_id]),
							indicator: "green",
						});
						frm.reload_doc();
					},
				});
			});
		}, __("Courier"));
	}

	if (hasOt) {
		frm.add_custom_button(__("Obtener etiqueta"), () => {
			frappe.call({
				method: "erpn_custom.chile.shipment_service.fetch_label",
				args: { shipment_name: frm.doc.name },
				freeze: true,
				callback(r) {
					frappe.show_alert({
						message: __("Etiqueta adjuntada"),
						indicator: "green",
					});
					frm.reload_doc();
				},
			});
		}, __("Courier"));

		frm.add_custom_button(__("Actualizar tracking"), () => {
			frappe.call({
				method: "erpn_custom.chile.shipment_service.update_tracking",
				args: { shipment_name: frm.doc.name },
				freeze: true,
				callback(r) {
					const res = r.message || {};
					frappe.msgprint({
						message: __("Tracking: {0} — {1}", [
							res.tracking_status || "",
							res.tracking_status_info || "",
						]),
						indicator: "blue",
					});
					frm.reload_doc();
				},
			});
		}, __("Courier"));
	}

	if (["Uncertain", "Creating", "Failed"].includes(state) && !hasOt) {
		frm.add_custom_button(__("Reconciliar OT"), () => {
			frappe.prompt(
				{
					fieldname: "transport_order_number",
					fieldtype: "Data",
					label: __("OT Chilexpress"),
					reqd: 1,
				},
				(values) => {
					frappe.call({
						method: "erpn_custom.chile.shipment_service.reconcile_uncertain",
						args: {
							shipment_name: frm.doc.name,
							transport_order_number: values.transport_order_number,
						},
						freeze: true,
						callback() {
							frm.reload_doc();
						},
					});
				},
				__("Reconciliar resultado incierto"),
				__("Guardar OT")
			);
		}, __("Courier"));
	}
}

function _pick_quote(frm, quotes) {
	if (!quotes.length) {
		frappe.msgprint(__("Chilexpress no devolvió servicios cotizables"));
		return;
	}
	const options = quotes.map(
		(q) => `${q.service_code} | ${q.service_name} | ${q.price}`
	);
	frappe.prompt(
		{
			fieldname: "quote",
			fieldtype: "Select",
			label: __("Servicio Chilexpress"),
			options: options.join("\n"),
			reqd: 1,
		},
		(values) => {
			const selected = quotes.find(
				(q) => `${q.service_code} | ${q.service_name} | ${q.price}` === values.quote
			);
			if (!selected) {
				return;
			}
			frappe.call({
				method: "erpn_custom.chile.shipment_service.select_quote",
				args: {
					shipment_name: frm.doc.name,
					service_code: selected.service_code,
					service_name: selected.service_name,
					price: selected.price,
				},
				freeze: true,
				callback() {
					frm.reload_doc();
				},
			});
		},
		__("Cotización Chilexpress"),
		__("Seleccionar")
	);
}

function _show_errors(errors) {
	const lines = (errors || []).map((e) => e.message || JSON.stringify(e));
	frappe.msgprint({
		title: __("Preflight courier"),
		message: lines.join("<br>"),
		indicator: "red",
	});
}
