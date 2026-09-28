// Classification lists shared by the Item and Encargo forms (same fieldnames on both).
frappe.provide("erpn_custom.classification");

erpn_custom.classification.FIELDS = [
	"custom_color",
	"custom_talla",
	"custom_taco",
	"custom_manga",
	"custom_tamano",
	"custom_tono",
	"custom_contenido",
];

erpn_custom.classification.allowed_values = function (frm, fieldname) {
	return (frm.__classification_options || {})[fieldname] || [];
};

let last_outside_alert = { text: null, at: 0 };

erpn_custom.classification.alert_outside_list = function (label, value) {
	const text = __("{0} «{1}» no existe en la lista. Pide al administrador que lo agregue.", [__(label), value]);
	if (last_outside_alert.text === text && Date.now() - last_outside_alert.at < 2000) {
		return;
	}
	last_outside_alert = { text, at: Date.now() };
	frappe.show_alert({ message: text, indicator: "orange" }, 7);
};

// The Autocomplete control silently drops typed text that is not in its list; tell the user.
erpn_custom.classification.warn_when_discarded = function (control, allowed_values) {
	if (!control || !control.$input || control.$input.data("erpn-discard-warning")) {
		return;
	}
	control.$input.data("erpn-discard-warning", 1);
	let typed = "";
	control.$input.on("input", () => {
		typed = (control.$input.val() || "").trim();
	});
	control.$input.on("blur", () => {
		setTimeout(() => {
			if (typed && !control.get_value() && !allowed_values().includes(typed)) {
				erpn_custom.classification.alert_outside_list(control.df.label, typed);
			}
			typed = "";
		}, 300);
	});
};

erpn_custom.classification.reject_value_outside_list = function (frm, fieldname) {
	const value = frm.doc[fieldname];
	if (!value || erpn_custom.classification.allowed_values(frm, fieldname).includes(value)) {
		return;
	}
	erpn_custom.classification.alert_outside_list(frm.fields_dict[fieldname].df.label, value);
	frm.set_value(fieldname, null);
};

erpn_custom.classification.load = function (frm) {
	frappe.call({
		method: "erpn_custom.catalog.item.get_classification_options",
		args: { item_group: frm.doc.item_group, departamento: frm.doc.custom_departamento },
		callback(r) {
			const data = r.message || {};
			if ((frm.doc.custom_familia || null) !== (data.familia || null)) {
				frm.doc.custom_familia = data.familia || null;
				frm.refresh_field("custom_familia");
				frm.refresh_fields();
			}
			frm.__classification_options = data.options || {};
			Object.entries(frm.__classification_options).forEach(([fieldname, values]) => {
				const control = frm.fields_dict[fieldname];
				if (!control) {
					return;
				}
				control.df.options = values;
				if (control.set_data) {
					control.set_data(values);
				}
				erpn_custom.classification.warn_when_discarded(control, () =>
					erpn_custom.classification.allowed_values(frm, fieldname)
				);
				if (frm.doc[fieldname] && !values.includes(frm.doc[fieldname])) {
					erpn_custom.classification.reject_value_outside_list(frm, fieldname);
				}
			});
		},
	});
};

// Form events for item_group, custom_departamento and the attribute fields.
erpn_custom.classification.form_events = function () {
	const events = {
		item_group: (frm) => erpn_custom.classification.load(frm),
		custom_departamento: (frm) => erpn_custom.classification.load(frm),
	};
	erpn_custom.classification.FIELDS.forEach((fieldname) => {
		events[fieldname] = (frm) => erpn_custom.classification.reject_value_outside_list(frm, fieldname);
	});
	return events;
};
