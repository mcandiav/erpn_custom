// Loaded after classification.js (hooks doctype_js); the doctype's own encargo.js loads before both.
const KNOWN_ITEM_LOCKED_FIELDS = [
	"brand",
	"size",
	"color",
	"description",
	"model",
	"item_group",
	"custom_departamento",
	...erpn_custom.classification.FIELDS,
];

frappe.ui.form.on("Encargo", {
	refresh(frm) {
		const known = frm.doc.source_type === "KNOWN_ITEM" ? 1 : 0;
		KNOWN_ITEM_LOCKED_FIELDS.forEach((fieldname) => frm.set_df_property(fieldname, "read_only", known));
		frm.set_query("item_group", () => ({ filters: { is_group: 0 } }));
		erpn_custom.classification.load(frm);
	},

	...erpn_custom.classification.form_events(),
});
