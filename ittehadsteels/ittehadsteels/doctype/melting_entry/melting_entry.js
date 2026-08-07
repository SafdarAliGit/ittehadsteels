// Copyright (c) 2026, Safdar Ali and contributors
// For license information, please see license.txt

frappe.ui.form.on("Melting Entry", {
	onload: function (frm) {
		frm.set_query("finish_item", "finish_items", function () {
			return {
				filters: {
					item_group: "Products",
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
