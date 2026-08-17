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
