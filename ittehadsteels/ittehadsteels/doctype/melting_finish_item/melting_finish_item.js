// Copyright (c) 2026, Safdar Ali and contributors
// For license information, please see license.txt

// Item Grade is auto-fetched from Finish Item via fetch_from in melting_finish_item.json.
// The "only finished product items" filter on Finish Item is set on the parent form
// (see melting_entry.js onload -> frm.set_query).

// frappe.ui.form.on("Melting Finish Item", {
// 	refresh(frm) {

// 	},
// });


frappe.ui.form.on("Melting Raw Material", {
	qty_kg: function (frm, cdt, cdn) {
		calculate_amount(frm, cdt, cdn)
	},

	rate: function (frm, cdt, cdn) {
		calculate_amount(frm, cdt, cdn);
	},

	raw_material_consumption_add: function (frm) {
		calculate_amount(frm, cdt, cdn)
	},

	raw_material_consumption_remove: function (frm) {
		calculate_amount(frm, cdt, cdn)
	},
});

function calculate_amount(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "amount", flt(row.qty_kg) * flt(row.rate));
	frm.trigger("calculate_totals");
}