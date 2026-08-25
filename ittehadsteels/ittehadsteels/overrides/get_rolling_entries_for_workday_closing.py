import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_rolling_entries_for_workday_closing(from_date=None, to_date=None):
	if not from_date or not to_date:
		return []

	if not frappe.has_permission("Rolling Entry", "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	filters = {
		"docstatus": 1,
		"date": ["between", [from_date, to_date]],
		"workday_closing_entry": ["in", ["", None]],
	}

	rolling_entries = frappe.get_all(
		"Rolling Entry",
		filters=filters,
		fields=["name", "date", "melting_entry", "total_issue_qty", "total_finish_qty"],
		order_by="date asc",
	)

	rows = []
	for entry in rolling_entries:
		rows.append(
			{
				"date": entry.date,
				"rolling_entry": entry.name,
				"melting_entry": entry.melting_entry,
				"total_issue_qty": entry.total_issue_qty,
				"total_finish_qty": entry.total_finish_qty,
				"balance_qty": flt(entry.total_issue_qty) - flt(entry.total_finish_qty),
			}
		)

	return rows
