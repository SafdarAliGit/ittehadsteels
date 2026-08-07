# Copyright (c) 2026, Safdar Ali and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_timedelta


class MeltingEntry(Document):
	def validate(self):
		self.validate_heat_no()
		self.validate_times()
		self.validate_finish_items()
		self.validate_raw_materials()
		self.calculate_raw_material_amounts()
		self.calculate_summary_totals()

	def validate_heat_no(self):
		if not self.heat_no:
			return

		filters = {"heat_no": self.heat_no}
		if not self.is_new():
			filters["name"] = ["!=", self.name]

		if frappe.db.exists("Melting Entry", filters):
			frappe.throw(_("Heat No {0} already exists").format(self.heat_no))

	def validate_times(self):
		if not (self.start_time and self.end_time):
			return

		start = get_timedelta(self.start_time)
		end = get_timedelta(self.end_time)

		if end <= start:
			frappe.throw(_("End Time must be greater than Start Time"))

		self.total_melting_time = (end - start).total_seconds()

	def validate_finish_items(self):
		seen = set()
		for row in self.get("finish_items"):
			if not row.finish_item:
				continue

			if row.finish_item in seen:
				frappe.throw(
					_("Row #{0}: Duplicate Finish Item {1}").format(row.idx, row.finish_item)
				)
			seen.add(row.finish_item)

			if not flt(row.qty_kg) and not flt(row.qty_pcs):
				frappe.throw(_("Row #{0}: Quantity cannot be zero").format(row.idx))

	def validate_raw_materials(self):
		seen = set()
		for row in self.get("raw_material_consumption"):
			if not row.item_code:
				continue

			if row.item_code in seen:
				frappe.throw(
					_("Row #{0}: Duplicate Raw Material Item {1}").format(row.idx, row.item_code)
				)
			seen.add(row.item_code)

			if not flt(row.qty_kg):
				frappe.throw(_("Row #{0}: Quantity cannot be zero").format(row.idx))

	def calculate_raw_material_amounts(self):
		for row in self.get("raw_material_consumption"):
			row.amount = flt(row.qty_kg) * flt(row.rate)

	def calculate_summary_totals(self):
		total_consumption = 0.0
		total_alloy = 0.0
		item_group_cache = {}

		for row in self.get("raw_material_consumption"):
			qty = flt(row.qty_kg)
			total_consumption += qty

			if not row.item_code:
				continue

			if row.item_code not in item_group_cache:
				item_group_cache[row.item_code] = frappe.db.get_value(
					"Item", row.item_code, "item_group"
				)

			if item_group_cache[row.item_code] == "Alloy":
				total_alloy += qty

		self.total_consumption_weight = total_consumption
		self.total_alloy_weight = total_alloy
		self.total_input_weight = total_consumption
