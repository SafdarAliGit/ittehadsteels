# Copyright (c) 2026, Safdar Ali and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_timedelta


class MeltingEntry(Document):
	def validate(self):
		# self.validate_times()
		# self.validate_finish_items()
		# self.validate_raw_materials()
		# self.calculate_raw_material_amounts()
		# self.calculate_summary_totals()
		self.calculate_total_qty_kg()
		self.calculate_total_qty_kg_raw_material()
		self.calculate_total_amount_raw_material()
		self.calculate_finish_rate()

	def on_submit(self):
			self.create_batches_for_finish_items()
			self.create_repack_stock_entry()

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

	def calculate_total_qty_kg(self):
		total_qty_kg = 0
		for row in self.get("finish_items"):
			total_qty_kg += flt(row.qty_kg) or 0
		self.total_output_weight = total_qty_kg

	def calculate_total_qty_kg_raw_material(self):
		total_qty_kg = 0
		for row in self.get("raw_material_consumption"):
			total_qty_kg += flt(row.qty_kg) or 0
		self.total_input_weight = total_qty_kg

	def calculate_total_amount_raw_material(self):
		total_amount = 0
		for row in self.get("raw_material_consumption"):
			total_amount += flt(row.amount) or 0
		self.total_input_amount = total_amount

	def calculate_finish_rate(self):
		total_output = flt(self.total_output_weight)
		self.finish_rate = flt(self.total_input_amount) / total_output if total_output else 0



	def create_batches_for_finish_items(self):

		for row in self.get("finish_items"):
			if not row.finish_item:
				continue


			batch = frappe.get_doc(
				{
					"doctype": "Batch",
					"batch_id": self.name,
					"item": row.finish_item,
					"batch_qty": flt(row.qty_kg),
				}
			).insert(ignore_permissions=True)

			row.db_set("batch", batch.name, update_modified=False)

	def create_repack_stock_entry(self):
		raw_rows = [row for row in self.get("raw_material_consumption") if row.item_code]
		finish_rows = [row for row in self.get("finish_items") if row.finish_item]

		if not raw_rows or not finish_rows:
			frappe.throw(
				_("Raw Material Consumption and Finish Items are required to create the Repack Stock Entry")
			)

		for row in raw_rows:
			if not row.warehouse:
				frappe.throw(
					_("Row #{0}: Warehouse is required in Raw Material Consumption to create the Repack Stock Entry").format(row.idx)
				)

		for row in finish_rows:
			if not row.warehouse:
				frappe.throw(
					_("Row #{0}: Warehouse is required in Finish Items to create the Repack Stock Entry").format(row.idx)
				)

		company = frappe.defaults.get_user_default("Company")
		if not company:
			frappe.throw(_("Default Company is not set for the current user"))

		stock_entry = frappe.new_doc("Stock Entry")
		stock_entry.stock_entry_type = "Repack"
		stock_entry.purpose = "Repack"
		stock_entry.company = company
		stock_entry.posting_date = self.posting_date
		stock_entry.remarks = _("Repack generated from Melting Entry {0}").format(self.name)
		stock_entry.custom_melting_entry = self.name

		for row in raw_rows:
			stock_entry.append(
				"items",
				{
					"item_code": row.item_code,
					"s_warehouse": row.warehouse,
					"qty": flt(row.qty_kg),
					# "basic_rate": flt(row.rate),
					"allow_zero_valuation_rate": 1,
					**get_stock_uom_fields(row.item_code),
				},
			)

		for row in finish_rows:
			stock_entry.append(
				"items",
				{
					"item_code": row.finish_item,
					"t_warehouse": row.warehouse,
					"qty": flt(row.qty_kg),
					"basic_rate": flt(self.finish_rate),
					"batch_no": row.batch,
					"is_finish_item":1,
					**get_stock_uom_fields(row.finish_item),
				},
			)

		stock_entry.insert(ignore_permissions=True)
		stock_entry.submit()


def get_stock_uom_fields(item_code):
	stock_uom = frappe.get_cached_value("Item", item_code, "stock_uom")
	return {"uom": stock_uom, "stock_uom": stock_uom, "conversion_factor": 1}
