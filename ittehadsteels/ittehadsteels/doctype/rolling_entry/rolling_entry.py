# Copyright (c) 2026, Safdar Ali and contributors
# For license information, please see license.txt

import string

import re
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

# (source fieldname in Finish Items, destination fieldname in Batch)
FINISH_ITEM_BATCH_FIELD_MAP = [
	("item_code", "item"),
	("grade", "grade"),
	("length", "length"),
	("guage", "guage"),
	("qty_kgs", "batch_qty"),
	("qty_pcs", "qty_in_pcs"),
]


class RollingEntry(Document):
	def validate(self):
		self.calculate_totals()

	def on_submit(self):
		self.create_batches_for_finish_items()
		self.create_repack_stock_entry()

	def calculate_totals(self):
		self.total_issue_qty = sum(flt(row.issue_qty) for row in self.get("raw_items"))
		self.total_raw_material_amount = sum(flt(row.amount) for row in self.get("raw_items"))
		self.total_finish_qty = sum(flt(row.qty_kgs) for row in self.get("finish_items"))

		self.cost_per_kg = flt(self.total_raw_material_amount) / self.total_finish_qty if self.total_finish_qty else 0
		self.cost_per_ton = flt(self.cost_per_kg) / 1000

	def create_batches_for_finish_items(self):
		rows = [row for row in self.get("finish_items") if row.item_code]
		if not rows:
			return

		if not self.melting_entry:
			frappe.throw(_("Melting Entry is required to generate Batch IDs for Finish Items"))

		next_idx = get_next_batch_index(self.melting_entry)

		for row in rows:
			if row.batch:
				# already generated, don't create a duplicate on re-submit/re-run
				continue

			batch_id = f"{self.melting_entry}-{next_idx:02d}"

			# safety net in case a batch was created outside this flow
			while frappe.db.exists("Batch", batch_id):
				next_idx += 1
				batch_id = f"{self.melting_entry}-{next_idx:02d}"

			batch = frappe.get_doc(
				{
					"doctype": "Batch",
					"batch_id": batch_id,
					**{dest: row.get(source) for source, dest in FINISH_ITEM_BATCH_FIELD_MAP},
				}
			).insert(ignore_permissions=True)

			row.db_set("batch", batch.name, update_modified=False)
			next_idx += 1

	def create_repack_stock_entry(self):
		raw_rows = [row for row in self.get("raw_items") if row.item_code]
		finish_rows = [row for row in self.get("finish_items") if row.item_code]
		by_product_rows = [row for row in self.get("finish_by_products") if row.item]

		if not raw_rows or not finish_rows:
			frappe.throw(
				_("Raw Items and Finish Items are required to create the Repack Stock Entry")
			)

		for row in raw_rows:
			if not row.warehouse:
				frappe.throw(
					_("Row #{0}: Warehouse is required in Raw Items to create the Repack Stock Entry").format(row.idx)
				)

		for row in finish_rows:
			if not row.warehouse:
				frappe.throw(
					_("Row #{0}: Warehouse is required in Finish Items to create the Repack Stock Entry").format(row.idx)
				)

		for row in by_product_rows:
			if not row.warehouse:
				frappe.throw(
					_("Row #{0}: Warehouse is required in Finish By Products to create the Repack Stock Entry").format(row.idx)
				)

		company = frappe.defaults.get_user_default("Company")
		if not company:
			frappe.throw(_("Default Company is not set for the current user"))

		stock_entry = frappe.new_doc("Stock Entry")
		stock_entry.stock_entry_type = "Repack"
		stock_entry.purpose = "Repack"
		stock_entry.company = company
		stock_entry.posting_date = self.date
		stock_entry.remarks = _("Repack generated from Rolling Entry {0}").format(self.name)
		stock_entry.custom_rolling_entry = self.name

		for row in raw_rows:
			stock_entry.append(
				"items",
				{
					"item_code": row.item_code,
					"s_warehouse": row.warehouse,
					"qty": flt(row.issue_qty),
					# "basic_rate": flt(row.rate),
					"allow_zero_valuation_rate": 1,
					"batch_no": row.heat_no,
					**get_stock_uom_fields(row.item_code)
				},
			)

		for row in finish_rows:
			stock_entry.append(
				"items",
				{
					"item_code": row.item_code,
					"t_warehouse": row.warehouse,
					"qty": flt(row.qty_kgs),
					"basic_rate": flt(self.cost_per_kg),
					"use_serial_batch_fields":1,
					"batch_no": row.batch,
					"is_finish_item":1,
					**get_stock_uom_fields(row.item_code)
				},
			)

		for row in by_product_rows:
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


def get_stock_uom_fields(item_code):
	stock_uom = frappe.get_cached_value("Item", item_code, "stock_uom")
	return {"uom": stock_uom, "stock_uom": stock_uom, "conversion_factor": 1}


def get_next_batch_index(prefix):
    """
    Look at existing batches named `<prefix>-01`, `<prefix>-02`, ...
    and return the next number to use (1 if none exist).
    """
    existing = frappe.get_all(
        "Batch",
        filters={"name": ("like", f"{prefix}-%")},
        pluck="name",
    )

    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    last = 0

    for name in existing:
        match = pattern.match(name)
        if match:
            last = max(last, int(match.group(1)))

    return last + 1
