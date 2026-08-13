# Copyright (c) 2026, Safdar Ali and contributors
# For license information, please see license.txt

import string

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

		for idx, row in enumerate(rows):
			batch = frappe.get_doc(
				{
					"doctype": "Batch",
					"batch_id": f"{self.melting_entry}{batch_suffix(idx)}",
					**{dest: row.get(source) for source, dest in FINISH_ITEM_BATCH_FIELD_MAP},
				}
			).insert(ignore_permissions=True)

			row.db_set("batch", batch.name, update_modified=False)


def batch_suffix(idx):
	"""0 -> A, 1 -> B, ..., 25 -> Z, 26 -> AA, 27 -> AB, ..."""
	letters = string.ascii_uppercase
	suffix = ""
	idx += 1
	while idx > 0:
		idx, remainder = divmod(idx - 1, 26)
		suffix = letters[remainder] + suffix
	return suffix
