import frappe
from frappe.utils import flt, nowdate, nowtime
from erpnext.stock.utils import get_incoming_rate


@frappe.whitelist()
def raw_item_valuation_rate(
	item_code=None, warehouse=None, company=None,
	posting_date=None, posting_time=None, qty=None
):
	if not item_code or not warehouse:
		return

	if not frappe.has_permission("Item", "read"):
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

	rate = get_incoming_rate(
		{
			"item_code": item_code,
			"warehouse": warehouse,
			"posting_date": posting_date or nowdate(),
			"posting_time": posting_time or nowtime(),
			"qty": -1 * abs(flt(qty)) or -1,
			"company": company or frappe.defaults.get_user_default("Company"),
			"voucher_type": "Stock Entry",
			"serial_and_batch_bundle": None,
		},
		raise_error_if_no_rate=False,
	)

	return flt(rate)