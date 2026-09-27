const CLASSIFICATION_FIELDS = [
	"custom_color",
	"custom_talla",
	"custom_taco",
	"custom_manga",
	"custom_tamano",
	"custom_tono",
	"custom_contenido",
];

const item_events = {
	refresh(frm) {
		frm.set_query("custom_brand_supplier", () => ({
			query: "erpn_custom.encargo.api.suppliers_for_brand_query",
			filters: { brand: frm.doc.brand },
		}));
		load_classification_options(frm);
	},

	brand(frm) {
		if (frm.doc.custom_brand_supplier) {
			frm.set_value("custom_brand_supplier", null);
		}
	},

	item_group(frm) {
		load_classification_options(frm);
	},

	custom_departamento(frm) {
		load_classification_options(frm);
	},
};

CLASSIFICATION_FIELDS.forEach((fieldname) => {
	item_events[fieldname] = (frm) => reject_value_outside_list(frm, fieldname);
});

frappe.ui.form.on("Item", item_events);

function allowed_values(frm, fieldname) {
	return (frm.__classification_options || {})[fieldname] || [];
}

function reject_value_outside_list(frm, fieldname) {
	const value = frm.doc[fieldname];
	if (!value || allowed_values(frm, fieldname).includes(value)) {
		return;
	}
	frappe.show_alert(
		{
			message: __("{0} «{1}» no existe en la lista. Pide al administrador que lo agregue.", [
				__(frm.fields_dict[fieldname].df.label),
				value,
			]),
			indicator: "orange",
		},
		7
	);
	frm.set_value(fieldname, null);
}

function load_classification_options(frm) {
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
				if (frm.doc[fieldname] && !values.includes(frm.doc[fieldname])) {
					reject_value_outside_list(frm, fieldname);
				}
			});
		},
	});
}
