# Copyright (c) 2026, Safdar Ali and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

DIRECT_EXPENSE_GROUPS = [
	"Furnace Expenses",
	"Rolling Expenses",
	"Manufacturing Expenses",
	"Labour Expense",
]

INDIRECT_EXPENSE_GROUPS = [
	"Indirect Expenses",
]


def execute(filters=None):
	filters = frappe._dict(filters or {})

	if not filters.company:
		filters.company = frappe.defaults.get_user_default("Company")
	if not filters.company:
		frappe.throw(_("Company is required"))
	if not filters.from_date or not filters.to_date:
		frappe.throw(_("From Date and To Date are required"))

	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"fieldname": "particulars", "label": _("Particulars"), "fieldtype": "Data", "width": 260},
		{"fieldname": "qty", "label": _("Qty (Ton)"), "fieldtype": "Float", "width": 120},
		{"fieldname": "amount", "label": _("Amount"), "fieldtype": "Currency", "width": 150},
		{"fieldname": "rate", "label": _("Per Ton"), "fieldtype": "Currency", "width": 130},
	]


def get_data(filters):
	direct_expense_groups = get_expense_groups(DIRECT_EXPENSE_GROUPS, filters.company)
	direct_accounts = get_leaf_accounts([row.name for row in direct_expense_groups])

	indirect_expense_groups = get_expense_groups(INDIRECT_EXPENSE_GROUPS, filters.company)
	indirect_accounts = get_leaf_accounts([row.name for row in indirect_expense_groups])

	rolling = get_rolling_entry_totals(filters)
	melting = get_melting_entry_totals(filters)
	sales = get_sales_invoice_totals(filters)

	finish_qty = flt(rolling.total_finish_qty)
	issue_qty = flt(rolling.total_issue_qty)
	raw_material_amount = flt(rolling.total_raw_material_amount)

	scrap_qty = flt(melting.total_input_weight)
	scrap_amount = flt(melting.total_input_amount)

	finish_cost_per_ton = raw_material_amount / finish_qty if finish_qty else 0
	finish_amount = finish_cost_per_ton * finish_qty

	billet_rate = raw_material_amount / issue_qty if issue_qty else 0
	scrap_rate = scrap_amount / scrap_qty if scrap_qty else 0

	direct_expense_amount = get_expense_amount(direct_accounts, filters)
	indirect_expense_amount = get_expense_amount(indirect_accounts, filters)

	direct_rate = direct_expense_amount / finish_qty if finish_qty else 0
	indirect_rate = indirect_expense_amount / finish_qty if finish_qty else 0

	total_expense = direct_expense_amount + indirect_expense_amount
	per_ton_cost = finish_cost_per_ton + direct_rate + indirect_rate

	sales_qty = flt(sales.qty)
	sales_amount = flt(sales.amount)
	sales_rate = sales_amount / sales_qty if sales_qty else 0

	margin = sales_rate - per_ton_cost
	margin_percent = (margin / per_ton_cost) * 100 if per_ton_cost else 0
	gross_margin_percent = (margin / sales_rate) * 100 if sales_rate else 0

	rows = [
		{
			"particulars": bold(_("Finish Item Production")),
			"indent": 0,
			"qty": finish_qty,
			"amount": finish_amount,
			"rate": finish_cost_per_ton,
		},
		{
			"particulars": bold(_("Raw Material")),
			"indent": 0,
		},
		{
			"particulars": _("Billets Consumption"),
			"indent": 1,
			"qty": issue_qty,
			"amount": raw_material_amount,
			"rate": billet_rate,
		},
		{
			"particulars": _("Scrap Item"),
			"indent": 1,
			"qty": scrap_qty,
			"amount": scrap_amount,
			"rate": scrap_rate,
		},
		{
			"particulars": bold(_("Expenses")),
			"indent": 0,
		},
		{
			"particulars": _("Direct Expense"),
			"indent": 1,
			"amount": direct_expense_amount,
			"rate": direct_rate,
		},
		*get_expense_group_rows(direct_expense_groups, filters, finish_qty, indent=2),
		{
			"particulars": _("Indirect Expense"),
			"indent": 1,
			"amount": indirect_expense_amount,
			"rate": indirect_rate,
		},
		*get_expense_group_rows(indirect_expense_groups, filters, finish_qty, indent=2),
		{
			"particulars": bold(_("Total Expense")),
			"indent": 0,
			"amount": total_expense,
		},
		{
			"particulars": bold(_("Per Ton Cost")),
			"indent": 0,
			"rate": per_ton_cost,
		},
		{
			"particulars": _("Sale Invoice (submitted)"),
			"indent": 0,
			"qty": sales_qty,
			"amount": sales_amount,
			"rate": sales_rate,
		},
		{
			"particulars": bold(_("Margin (Sale Rate - Per Ton Cost)")),
			"indent": 0,
			"rate": margin,
		},
		{
			"particulars": bold(_("Margin % (Margin / Per Ton Cost * 100)")),
			"indent": 0,
			"rate": margin_percent,
		},
		{
			"particulars": bold(_("Gross Margin % (Margin / Sale Rate * 100)")),
			"indent": 0,
			"rate": gross_margin_percent,
		},
	]
	return rows


def bold(value):
	return f"<b>{value}</b>"


def get_expense_groups(group_names, company):
	return frappe.get_all(
		"Account",
		filters={"account_name": ["in", group_names], "company": company, "is_group": 1},
		fields=["name", "account_name"],
		order_by="lft",
	)


def get_rolling_entry_totals(filters):
	result = frappe.db.get_all(
		"Rolling Entry",
		filters={
			"docstatus": 1,
			"date": ["between", [filters.from_date, filters.to_date]],
		},
		fields=[
			"sum(total_finish_qty) as total_finish_qty",
			"sum(total_issue_qty) as total_issue_qty",
			"sum(total_raw_material_amount) as total_raw_material_amount",
		],
	)
	return result[0] if result else frappe._dict()


def get_melting_entry_totals(filters):
	result = frappe.db.get_all(
		"Melting Entry",
		filters={
			"docstatus": 1,
			"posting_date": ["between", [filters.from_date, filters.to_date]],
		},
		fields=[
			"sum(total_input_weight) as total_input_weight",
			"sum(total_input_amount) as total_input_amount",
		],
	)
	return result[0] if result else frappe._dict()


def get_sales_invoice_totals(filters):
	result = frappe.db.get_all(
		"Sales Invoice",
		filters={
			"docstatus": 1,
			"company": filters.company,
			"posting_date": ["between", [filters.from_date, filters.to_date]],
		},
		fields=[
			"sum(total_qty) as qty",
			"sum(base_net_total) as amount",
		],
	)
	return result[0] if result else frappe._dict()


def get_leaf_accounts(group_accounts):
	"""All non-group (ledger) accounts nested anywhere under the given group accounts."""
	leaves = []
	for name in group_accounts:
		group = frappe.db.get_value("Account", name, ["lft", "rgt"], as_dict=True)
		if not group:
			continue
		leaves += frappe.get_all(
			"Account",
			filters={"lft": [">", group.lft], "rgt": ["<", group.rgt], "is_group": 0},
			pluck="name",
		)
	return leaves


def get_expense_group_rows(groups, filters, finish_qty, indent):
	"""List each expense group and its full child/subchild account hierarchy.
	Only leaf (non-group) accounts carry an amount/rate, and only when that
	amount is greater than 0 - zero-value leaves and groups left with no
	remaining children are skipped so the tree only shows real activity and
	group totals can't be misread as separate figures to sum."""

	def walk(account, account_name, is_group, depth):
		if is_group:
			children = frappe.get_all(
				"Account",
				filters={"parent_account": account},
				fields=["name", "account_name", "is_group"],
				order_by="lft",
			)
			child_rows = []
			for child in children:
				child_rows += walk(child.name, child.account_name, child.is_group, depth + 1)
			if not child_rows:
				return []
			return [{"particulars": account_name, "indent": indent + depth}] + child_rows

		amount = get_expense_amount([account], filters)
		if amount <= 0:
			return []
		return [
			{
				"particulars": account_name,
				"indent": indent + depth,
				"amount": amount,
				"rate": amount / finish_qty if finish_qty else 0,
			}
		]

	rows = []
	for group in groups:
		rows += walk(group.name, group.account_name, True, 0)
	return rows


def get_expense_amount(accounts, filters):
	if not accounts:
		return 0

	result = frappe.db.get_all(
		"GL Entry",
		filters={
			"account": ["in", accounts],
			"company": filters.company,
			"posting_date": ["between", [filters.from_date, filters.to_date]],
			"is_cancelled": 0,
		},
		fields=["sum(debit) - sum(credit) as amount"],
	)
	return flt(result[0].amount) if result and result[0].amount else 0
