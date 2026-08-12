// Copyright (c) 2026, Safdar Ali and contributors
// For license information, please see license.txt

frappe.ui.form.on("Rolling Entry", {
	refresh: function (frm) {
		frm.set_query("item_code", "raw_items", function () {
			return {
				filters: {
					item_group: "Billets",
				},
			};
		});
	},
});

frappe.ui.form.on("Raw Items", {
	item_code: function (frm, cdt, cdn) {
		fetch_raw_item_rate(frm, cdt, cdn);
	},

	warehouse: function (frm, cdt, cdn) {
		fetch_raw_item_rate(frm, cdt, cdn);
	},

	issue_qty: function (frm, cdt, cdn) {
		calculate_raw_item_amount(frm, cdt, cdn);
	},

	rate: function (frm, cdt, cdn) {
		calculate_raw_item_amount(frm, cdt, cdn);
	},

	raw_items_remove: function (frm) {
		calculate_total_issue_qty(frm);
		calculate_total_raw_material_amount(frm);
	},
});

frappe.ui.form.on("Finish Items", {
	qty_kgs: function (frm) {
		calculate_total_finish_qty(frm);
	},

	finish_items_remove: function (frm) {
		calculate_total_finish_qty(frm);
	},
});

frappe.ui.form.on("Consumables", {
	qty: function (frm, cdt, cdn) {
		calculate_consumable_amount(frm, cdt, cdn);
	},

	rate: function (frm, cdt, cdn) {
		calculate_consumable_amount(frm, cdt, cdn);
	},
});

function fetch_raw_item_rate(frm, cdt, cdn) {
	const row = locals[cdt][cdn];

	if (!row.item_code || !row.warehouse) {
		return;
	}

	frappe.call({
		method: "ittehadsteels.ittehadsteels.overrides.raw_item_valuation_rate.raw_item_valuation_rate",
		args: {
			item_code: row.item_code,
			warehouse: row.warehouse,
		},
		callback: function (r) {
			if (!r.message) {
				return;
			}
			frappe.model.set_value(cdt, cdn, "rate", flt(r.message));
		},
	});
}

function calculate_raw_item_amount(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "amount", flt(row.issue_qty) * flt(row.rate));
	calculate_total_issue_qty(frm);
	calculate_total_raw_material_amount(frm);
}

function calculate_total_issue_qty(frm) {
	let total_issue_qty = 0;
	(frm.doc.raw_items || []).forEach((row) => {
		total_issue_qty += flt(row.issue_qty);
	});
	frm.set_value("total_issue_qty", total_issue_qty);
}

function calculate_total_raw_material_amount(frm) {
	let total_amount = 0;
	(frm.doc.raw_items || []).forEach((row) => {
		total_amount += flt(row.amount);
	});
	frm.set_value("total_raw_material_amount", total_amount);
	calculate_cost_per_kg(frm);
}

function calculate_total_finish_qty(frm) {
	let total_qty = 0;
	(frm.doc.finish_items || []).forEach((row) => {
		total_qty += flt(row.qty_kgs);
	});
	frm.set_value("total_finish_qty", total_qty);
	calculate_cost_per_kg(frm);
}

function calculate_cost_per_kg(frm) {
	let cost_per_kg = frm.doc.total_finish_qty
		? flt(frm.doc.total_raw_material_amount) / flt(frm.doc.total_finish_qty)
		: 0;
	frm.set_value("cost_per_kg", cost_per_kg);
	frm.set_value("cost_per_ton", flt(cost_per_kg) / 1000);
}

function calculate_consumable_amount(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
}
