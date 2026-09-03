# Copyright (c) 2026, Safdar Ali and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from ittehadsteels.ittehadsteels.doctype.rolling_entry.rolling_entry import get_stock_uom_fields


class WorkdayClosingEntry(Document):
	def validate(self):
		self.calculate_totals()

	def on_submit(self):
		self.mark_rolling_entries_as_used()
		self.create_material_receipt_for_by_products()

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

	def create_material_receipt_for_by_products(self):
		if self.material_receipt_entry:
			# already generated, don't create a duplicate on re-submit/re-run
			return

		rows = [row for row in self.get("finish_by_products") if row.item]
		if not rows:
			return

		for row in rows:
			if not row.warehouse:
				frappe.throw(
					_("Row #{0}: Warehouse is required in Finish By Products to create the Material Receipt").format(row.idx)
				)

		company = frappe.defaults.get_user_default("Company")
		if not company:
			frappe.throw(_("Default Company is not set for the current user"))

		stock_entry = frappe.new_doc("Stock Entry")
		stock_entry.stock_entry_type = "Material Receipt"
		stock_entry.purpose = "Material Receipt"
		stock_entry.company = company
		stock_entry.posting_date = self.to_date
		stock_entry.remarks = _("By Products generated from Workday Closing Entry {0}").format(self.name)

		for row in rows:
			stock_entry.append(
				"items",
				{
					"item_code": row.item,
					"t_warehouse": row.warehouse,
					"qty": flt(row.qty),
					"allow_zero_valuation_rate": 1,
					**get_stock_uom_fields(row.item)
				},
			)

		stock_entry.insert(ignore_permissions=True)
		stock_entry.submit()

		self.db_set("material_receipt_entry", stock_entry.name, update_modified=False)

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
