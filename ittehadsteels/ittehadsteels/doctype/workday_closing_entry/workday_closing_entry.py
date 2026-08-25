# Copyright (c) 2026, Safdar Ali and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class WorkdayClosingEntry(Document):
	def validate(self):
		self.calculate_totals()

	def on_submit(self):
		self.mark_rolling_entries_as_used()

	def on_cancel(self):
		self.release_rolling_entries()

	def mark_rolling_entries_as_used(self):
		rows = [row for row in self.get("rolling_entry_item") if row.rolling_entry]

		for row in rows:
			existing = frappe.db.get_value(
				"Rolling Entry", row.rolling_entry, "workday_closing_entry", for_update=True
			)
			if existing and existing != self.name:
				frappe.throw(
					_("Row #{0}: Rolling Entry {1} is already used in Workday Closing Entry {2}").format(
						row.idx, row.rolling_entry, existing
					)
				)

		for row in rows:
			frappe.db.set_value("Rolling Entry", row.rolling_entry, "workday_closing_entry", self.name)

	def release_rolling_entries(self):
		for row in self.get("rolling_entry_item"):
			if not row.rolling_entry:
				continue
			frappe.db.set_value("Rolling Entry", row.rolling_entry, "workday_closing_entry", None)

	def calculate_totals(self):
		self.total_issue_qty = sum(flt(row.total_issue_qty) for row in self.get("rolling_entry_item"))
		self.total_finish_qty = sum(flt(row.total_finish_qty) for row in self.get("rolling_entry_item"))

		for row in self.get("rolling_entry_item"):
			row.balance_qty = flt(row.total_issue_qty) - flt(row.total_finish_qty)

		self.total_balance_qty = sum(flt(row.balance_qty) for row in self.get("rolling_entry_item"))
		self.total_by_product_weight = sum(flt(row.qty) for row in self.get("finish_by_products"))

		self.difference = flt(self.total_balance_qty) - flt(self.total_by_product_weight)
		self.yield_percent = (
			flt(self.difference) * 100 / flt(self.total_issue_qty) if self.total_issue_qty else 0
		)
