# Copyright (c) 2026, Safdar Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class RollingEntry(Document):
	def validate(self):
		self.calculate_totals()

	def calculate_totals(self):
		self.total_issue_qty = sum(flt(row.issue_qty) for row in self.get("raw_items"))
		self.total_raw_material_amount = sum(flt(row.amount) for row in self.get("raw_items"))
		self.total_finish_qty = sum(flt(row.qty_kgs) for row in self.get("finish_items"))

		self.cost_per_kg = flt(self.total_raw_material_amount) / self.total_finish_qty if self.total_finish_qty else 0
		self.cost_per_ton = flt(self.cost_per_kg) / 1000
