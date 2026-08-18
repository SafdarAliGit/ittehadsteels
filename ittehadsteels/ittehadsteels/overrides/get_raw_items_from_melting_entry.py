import frappe

# (source fieldname in Melting Finish Item, destination fieldname in Raw Items)
FIELD_MAP = [
	("finish_item", "item_code"),
	("batch", "heat_no"),
	("length","length"),
	("grade", "grade"),
	("warehouse","warehouse")
]


@frappe.whitelist()
def get_raw_items_from_melting_entry(melting_entry=None):
	if not melting_entry:
		return []

	if not frappe.has_permission("Melting Entry", "read", doc=melting_entry):
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

	source_fields = [source for source, _dest in FIELD_MAP]
	rows = frappe.get_all(
		"Melting Finish Item",
		filters={"parenttype": "Melting Entry", "parent": melting_entry},
		fields=source_fields,
		order_by="idx asc",
	)

	batch_names = {row.get("batch") for row in rows if row.get("batch")}
	batch_qty_map = {}
	if batch_names:
		batch_qty_map = {
			b.name: b.batch_qty
			for b in frappe.get_all(
				"Batch", filters={"name": ["in", list(batch_names)]}, fields=["name", "batch_qty"]
			)
		}

	raw_items = []
	for row in rows:
		item = {dest: row.get(source) for source, dest in FIELD_MAP}
		item["available_qty"] = batch_qty_map.get(row.get("batch"))
		raw_items.append(item)

	return raw_items
