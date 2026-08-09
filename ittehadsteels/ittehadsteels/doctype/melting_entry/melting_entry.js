// Copyright (c) 2026, Safdar Ali and contributors
// For license information, please see license.txt

frappe.ui.form.on("Melting Entry", {
	refresh: function (frm) {
		frm.set_query("product_group", "finish_items", function () {
			return {
				filters: {
					name: ["descendants of", "Products"],
				},
			};
		});
		frm.set_query("item_code", "raw_material_consumption", function (doc, cdt, cdn) {
			return {
				filters: {
					item_group: ["descendants of", "Raw Material"],
				},
			};
		});

		frm.set_query("finish_item", "finish_items", function (frm, cdt, cdn) {
			grid_row = locals[cdt][cdn];
			return {
				filters: {
					item_group: grid_row.product_group,
				},
			};
		});
	},


	start_time: function (frm) {
		frm.trigger("calculate_total_melting_time");
	},

	end_time: function (frm) {
		frm.trigger("calculate_total_melting_time");
	},

	calculate_total_melting_time: function (frm) {
		if (!frm.doc.start_time || !frm.doc.end_time) {
			return;
		}

		let start = frappe.datetime.str_to_obj("2000-01-01 " + frm.doc.start_time);
		let end = frappe.datetime.str_to_obj("2000-01-01 " + frm.doc.end_time);
		let diff_seconds = (end - start) / 1000;

		frm.set_value("total_melting_time", diff_seconds > 0 ? diff_seconds : 0);
	},

	calculate_totals: function (frm) {
		let total_consumption = 0;

		(frm.doc.raw_material_consumption || []).forEach((row) => {
			total_consumption += flt(row.qty_kg);
		});

		frm.set_value("total_consumption_weight", total_consumption);
		frm.set_value("total_input_weight", total_consumption);
	},
		


	validate: function (frm) {
		if (
			frm.doc.start_time &&
			frm.doc.end_time &&
			frappe.datetime.str_to_obj("2000-01-01 " + frm.doc.end_time) <=
				frappe.datetime.str_to_obj("2000-01-01 " + frm.doc.start_time)
		) {
			frappe.throw(__("End Time must be greater than Start Time"));
		}

		let finish_items_seen = new Set();
		(frm.doc.finish_items || []).forEach((row) => {
			if (!row.finish_item) {
				return;
			}

			if (finish_items_seen.has(row.finish_item)) {
				frappe.throw(__("Row #{0}: Duplicate Finish Item {1}", [row.idx, row.finish_item]));
			}
			finish_items_seen.add(row.finish_item);

			if (!flt(row.qty_kg) && !flt(row.qty_pcs)) {
				frappe.throw(__("Row #{0}: Quantity cannot be zero", [row.idx]));
			}
		});

		let raw_materials_seen = new Set();
		(frm.doc.raw_material_consumption || []).forEach((row) => {
			if (!row.item_code) {
				return;
			}

			if (raw_materials_seen.has(row.item_code)) {
				frappe.throw(
					__("Row #{0}: Duplicate Raw Material Item {1}", [row.idx, row.item_code])
				);
			}
			raw_materials_seen.add(row.item_code);

			if (!flt(row.qty_kg)) {
				frappe.throw(__("Row #{0}: Quantity cannot be zero", [row.idx]));
			}
		});
	},
});

frappe.ui.form.on("Melting Finish Item", {

	qty_kg: function (frm, cdt, cdn) {
		calculate_total_qty_kg(frm, cdt, cdn)
	},
	
});

function calculate_total_qty_kg(frm, cdt, cdn) {
	let total_qty_kg = 0;
	let finish_rate = 0;
	(frm.doc.finish_items || []).forEach((row) => {
		total_qty_kg += flt(row.qty_kg) || 0;
	});
	frm.set_value("total_output_weight", total_qty_kg);

	finish_rate = frm.doc.total_input_amount / total_qty_kg || 0;
	frm.set_value("finish_rate", finish_rate);
}

frappe.ui.form.on("Melting Raw Material", {
	qty_kg: function (frm, cdt, cdn) {
		calculate_amount(frm, cdt, cdn)
		calculate_total_qty_kg_raw_material(frm, cdt, cdn);
		calculate_total_amount_raw_material(frm, cdt, cdn);
	},

	rate: function (frm, cdt, cdn) {
		calculate_amount(frm, cdt, cdn);
		calculate_total_amount_raw_material(frm, cdt, cdn);
	},
	item_code: function (frm, cdt, cdn) {
		raw_item_valuation_rate(frm, cdt, cdn);
	},

	warehouse: function (frm, cdt, cdn) {
		raw_item_valuation_rate(frm, cdt, cdn);
	},

});

function calculate_amount(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "amount", flt(row.qty_kg) * flt(row.rate));
	
}

function calculate_total_qty_kg_raw_material(frm, cdt, cdn) {
	let total_qty_kg = 0;
	(frm.doc.raw_material_consumption || []).forEach((row) => {
		total_qty_kg += flt(row.qty_kg) || 0;
	});
	frm.set_value("total_input_weight", total_qty_kg);
}

function calculate_total_amount_raw_material(frm, cdt, cdn) {
	let total_amount = 0;
	let finish_rate = 0;
	(frm.doc.raw_material_consumption || []).forEach((row) => {
		total_amount += flt(row.amount) || 0;
	});
	frm.set_value("total_input_amount", total_amount);

	finish_rate = total_amount / frm.doc.total_output_weight || 0;
	frm.set_value("finish_rate", finish_rate);
}
	

function raw_item_valuation_rate(frm, cdt, cdn) {
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