import frappe

# (source fieldname in Melting Finish Item, destination fieldname in Raw Items)
FIELD_MAP = [
	("finish_item", "item_code"),
	("batch", "heat_no"),
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

	raw_items = []
	for row in rows:
		raw_items.append({dest: row.get(source) for source, dest in FIELD_MAP})

	return raw_items
