// Copyright (c) 2026, Safdar Ali and contributors
// For license information, please see license.txt

frappe.ui.form.on("Workday Closing Entry", {
	from_date: function (frm) {
		fetch_rolling_entries(frm);
	},

	to_date: function (frm) {
		fetch_rolling_entries(frm);
	},
});

frappe.ui.form.on("Rolling Entry Item", {
	rolling_entry_item_remove: function (frm) {
		calculate_total_balance_qty(frm);
	},
});

frappe.ui.form.on("Finish By Products", {
	qty: function (frm) {
		calculate_total_by_product_weight(frm);
	},

	finish_by_products_remove: function (frm) {
		calculate_total_by_product_weight(frm);
	},
});

function fetch_rolling_entries(frm) {
	if (!frm.doc.from_date || !frm.doc.to_date) {
		return;
	}

	if (frm.doc.to_date < frm.doc.from_date) {
		frappe.msgprint(__("To Date cannot be before From Date"));
		return;
	}

	frappe.call({
		method:
			"ittehadsteels.ittehadsteels.overrides.get_rolling_entries_for_workday_closing.get_rolling_entries_for_workday_closing",
		args: {
			from_date: frm.doc.from_date,
			to_date: frm.doc.to_date,
		},
		callback: function (r) {
			if (!r.message) {
				return;
			}

			frm.clear_table("rolling_entry_item");
			r.message.forEach((entry) => {
				const row = frm.add_child("rolling_entry_item");
				frappe.model.set_value(row.doctype, row.name, entry);
			});
			frm.refresh_field("rolling_entry_item");
			calculate_totals(frm);
		},
	});
}

function calculate_total_issue_qty(frm) {
	let total_issue_qty = 0;
	(frm.doc.rolling_entry_item || []).forEach((row) => {
		total_issue_qty += flt(row.total_issue_qty);
	});
	frm.set_value("total_issue_qty", total_issue_qty);
}

function calculate_total_finish_qty(frm) {
	let total_finish_qty = 0;
	(frm.doc.rolling_entry_item || []).forEach((row) => {
		total_finish_qty += flt(row.total_finish_qty);
	});
	frm.set_value("total_finish_qty", total_finish_qty);
}

function calculate_total_balance_qty(frm) {
	let total_balance_qty = 0;
	(frm.doc.rolling_entry_item || []).forEach((row) => {
		total_balance_qty += flt(row.balance_qty);
	});
	frm.set_value("total_balance_qty", total_balance_qty);
	calculate_difference(frm);
}

function calculate_total_by_product_weight(frm) {
	let total_by_product_weight = 0;
	(frm.doc.finish_by_products || []).forEach((row) => {
		total_by_product_weight += flt(row.qty);
	});
	frm.set_value("total_by_product_weight", total_by_product_weight);
	calculate_difference(frm);
}

function calculate_difference(frm) {
	const difference = flt(frm.doc.total_balance_qty) - flt(frm.doc.total_by_product_weight);
	frm.set_value("difference", difference);
	calculate_yield_percent(frm);
}

function calculate_yield_percent(frm) {
	const yield_percent = frm.doc.total_issue_qty
		? (flt(frm.doc.difference) * 100) / flt(frm.doc.total_issue_qty)
		: 0;
	frm.set_value("yield_percent", yield_percent);
}

function calculate_totals(frm) {
	calculate_total_issue_qty(frm);
	calculate_total_finish_qty(frm);
	calculate_total_balance_qty(frm);
	calculate_total_by_product_weight(frm);
}
