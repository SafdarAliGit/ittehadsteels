"""
Server side for the Ittehad Steels KPI Dashboard page.

Everything in this file is queried live from real doctypes (Rolling Entry,
Melting Entry, Workday Closing Entry, Sales Invoice, Safety Incident, Steel
Dashboard Settings). Sections with no backing doctype yet for their ACTUALS
(Quality, Maintenance, Gross Margin) still live in
steel_dashboard_demo_data.py and are merged in at the end of
get_dashboard_data() - replace those one at a time as real modules land, the
same way Safety was (see get_safety()) once Safety Incident landed. Capacity
Utilization/OEE (see get_gauges()) and every actual's TARGET line (see
get_kv_panels()/get_safety()) are computed live from Steel Dashboard
Settings, a Single doctype the Settings section (steel_dashboard.js) reads
and can edit directly.
"""

import base64
import mimetypes

import frappe
from frappe.utils import flt, cint, getdate, add_days, add_months, escape_html

from ittehadsteels.ittehadsteels.page.steel_dashboard import steel_dashboard_demo_data as demo


# --------------------------------------------------------------- utilities

def _company_logo():
	"""File URL of the default company's logo, or "" if none is set - the
	sidebar brand area shows nothing (not a placeholder icon) when this is
	empty, see steel_dashboard.js::render_data()."""
	company = frappe.defaults.get_global_default("company")
	return (frappe.db.get_value("Company", company, "company_logo") if company else None) or ""


def _company_header():
	"""(company name, logo as a data URI) for the Reports section's exported
	PDFs (see export_report_pdf()) - a data URI, not the bare file URL
	_company_logo() returns, because wkhtmltopdf renders standalone (no
	browser session/cookies) and needs either a filesystem path or an
	embedded data URI to actually show the image; a data URI always works
	regardless of where Frappe is serving files from."""
	company = frappe.defaults.get_global_default("company") or ""
	logo_url = _company_logo()
	logo_data_uri = ""
	if logo_url:
		try:
			file_doc = frappe.get_doc("File", {"file_url": logo_url})
			content = file_doc.get_content()
			mime = mimetypes.guess_type(logo_url)[0] or "image/png"
			logo_data_uri = f"data:{mime};base64,{base64.b64encode(content).decode()}"
		except Exception:
			logo_data_uri = ""
	return company, logo_data_uri


def _dashboard_settings():
	"""The one Steel Dashboard Settings document (a Single, like Frappe's own
	System Settings) - rated capacity/cycle time for Capacity Utilization
	and OEE (see get_gauges()), and the target line shown alongside every
	Quality/Maintenance/Safety actual. frappe.get_cached_doc() so the same
	request doesn't re-fetch it for every section that needs it."""
	return frappe.get_cached_doc("Steel Dashboard Settings")


def _prev_period(from_date, to_date):
	"""Return the immediately preceding period of the same length, used for
	every 'vs Last Period' comparison on the dashboard (see
	kpi_card_html() in steel_dashboard.js) - the dashboard's date range
	isn't fixed to a week, so the label doesn't claim it is."""
	from_date = getdate(from_date)
	to_date = getdate(to_date)
	days = (to_date - from_date).days + 1
	prev_to = add_days(from_date, -1)
	prev_from = add_days(prev_to, -(days - 1))
	return prev_from, prev_to


def _delta_pct(current, previous):
	current, previous = flt(current), flt(previous)
	if not previous:
		return 0
	return flt((current - previous) / previous * 100, 1)


# ------------------------------------------------------------ live: kpis

def _raw_material_consumption_mt(from_date, to_date):
	"""Raw Material Consumption (Scrap Item) - Melting Entry's
	total_input_weight, the scrap fed into melting, in Ton."""
	total = frappe.db.sql(
		"""
		select sum(total_input_weight)
		from `tabMelting Entry`
		where docstatus = 1 and posting_date between %s and %s
		""",
		(from_date, to_date),
	)[0][0]
	return flt(total)


def _billet_production_mt(from_date, to_date):
	total = frappe.db.sql(
		"""
		select sum(total_output_weight)
		from `tabMelting Entry`
		where docstatus = 1 and posting_date between %s and %s
		""",
		(from_date, to_date),
	)[0][0]
	return flt(total)


def _bar_production_mt(from_date, to_date):
	total = frappe.db.sql(
		"""
		select sum(total_finish_qty)
		from `tabRolling Entry`
		where docstatus = 1 and date between %s and %s
		""",
		(from_date, to_date),
	)[0][0]
	return flt(total)


def _heats(from_date, to_date):
	return cint(
		frappe.db.count(
			"Melting Entry",
			filters={"docstatus": 1, "posting_date": ["between", [from_date, to_date]]},
		)
	)


def _sales(from_date, to_date):
	row = frappe.db.sql(
		"""
		select sum(sii.qty), sum(si.base_grand_total)
		from `tabSales Invoice` si
		inner join `tabSales Invoice Item` sii on sii.parent = si.name
		where si.docstatus = 1 and si.posting_date between %s and %s
		""",
		(from_date, to_date),
	)
	qty, revenue = row[0] if row else (0, 0)
	return flt(qty), flt(revenue)


def _sales_order_value(from_date, to_date):
	"""Sum of Sales Order base_net_total placed in the period - the Sales
	section's equivalent of /app/dashboard-view/Selling's "Annual Sales"
	number card, but scoped to the dashboard's own date range rather than a
	fixed fiscal year, same as every other KPI here."""
	total = frappe.db.sql(
		"""
		select sum(base_net_total)
		from `tabSales Order`
		where docstatus = 1 and status not in ('Draft', 'Cancelled', 'Closed')
			and transaction_date between %s and %s
		""",
		(from_date, to_date),
	)[0][0]
	return flt(total)


def _sales_orders_pending(from_date, to_date, statuses):
	"""Count of Sales Orders placed in the period still pending delivery/billing
	- same "To Deliver"/"To Bill" statuses as the Selling dashboard's number
	cards, filtered to the dashboard's date range instead of being a
	point-in-time count of every open order regardless of age."""
	return cint(
		frappe.db.count(
			"Sales Order",
			filters={
				"docstatus": 1,
				"status": ["in", statuses],
				"transaction_date": ["between", [from_date, to_date]],
			},
		)
	)


def _active_customers():
	"""Count of non-disabled Customers - same as the Selling dashboard's own
	"Active Customers" number card (a live total, not scoped to the
	dashboard's date range, same precedent as Inventory (Warehouse Wise))."""
	return cint(frappe.db.count("Customer", filters={"disabled": 0}))


def _invoice_total(doctype, from_date, to_date):
	"""Sum of base_grand_total for a submitted Sales/Purchase Invoice in the
	period - Finance's "Total Incoming Bills"/"Total Outgoing Bills" KPIs."""
	total = frappe.db.sql(
		"""
		select sum(base_grand_total)
		from `tab{doctype}`
		where docstatus = 1 and posting_date between %s and %s
		""".format(doctype=doctype),
		(from_date, to_date),
	)[0][0]
	return flt(total)


def _payment_total(payment_type, from_date, to_date):
	"""Sum of Payment Entry base_paid_amount for the period, by direction
	('Receive' = incoming, 'Pay' = outgoing) - Finance's "Total Incoming
	Payment"/"Total Outgoing Payment" KPIs."""
	total = frappe.db.sql(
		"""
		select sum(base_paid_amount)
		from `tabPayment Entry`
		where docstatus = 1 and payment_type = %s and posting_date between %s and %s
		""",
		(payment_type, from_date, to_date),
	)[0][0]
	return flt(total)


def _total_active_items():
	"""Count of non-disabled Items - Inventory's "Total Active Items" KPI."""
	return cint(frappe.db.count("Item", filters={"disabled": 0}))


def _total_warehouses():
	"""Count of non-disabled Warehouses - Inventory's "Total Warehouses" KPI."""
	return cint(frappe.db.count("Warehouse", filters={"disabled": 0}))


def _total_stock_value():
	"""Sum of Bin.stock_value across every warehouse - Inventory's "Total
	Stock Value" KPI (money, not the Ton quantity
	get_inventory_by_warehouse() shows)."""
	total = frappe.db.sql("select sum(stock_value) from `tabBin`")[0][0]
	return flt(total)


def get_kpis(from_date, to_date, prev_from, prev_to):
	"""Ordered, self-describing list of KPI cards - the dashboard's top row
	renders however many of these come back, with whatever label/icon/color
	each one carries. To add a KPI card: add one entry here (`icon`/`color`
	must match a name ittehad_dashboard.icon()/the CSS palette knows about) -
	the front end needs no changes, see steel_dashboard.js::render_kpis()."""
	raw_material_consumption_mt, prev_raw_material_consumption_mt = (
		_raw_material_consumption_mt(from_date, to_date),
		_raw_material_consumption_mt(prev_from, prev_to),
	)
	billet_production_mt, prev_billet_production_mt = (
		_billet_production_mt(from_date, to_date),
		_billet_production_mt(prev_from, prev_to),
	)
	bar_production_mt, prev_bar_production_mt = (
		_bar_production_mt(from_date, to_date),
		_bar_production_mt(prev_from, prev_to),
	)
	heats, prev_heats = _heats(from_date, to_date), _heats(prev_from, prev_to)
	sales_qty, revenue = _sales(from_date, to_date)
	prev_sales_qty, prev_revenue = _sales(prev_from, prev_to)
	gross_margin = demo.get_gross_margin()

	sales_order_value, prev_sales_order_value = (
		_sales_order_value(from_date, to_date),
		_sales_order_value(prev_from, prev_to),
	)
	sales_orders_to_deliver, prev_sales_orders_to_deliver = (
		_sales_orders_pending(from_date, to_date, ["To Deliver and Bill", "To Deliver"]),
		_sales_orders_pending(prev_from, prev_to, ["To Deliver and Bill", "To Deliver"]),
	)
	sales_orders_to_bill, prev_sales_orders_to_bill = (
		_sales_orders_pending(from_date, to_date, ["To Deliver and Bill", "To Bill"]),
		_sales_orders_pending(prev_from, prev_to, ["To Deliver and Bill", "To Bill"]),
	)
	active_customers = _active_customers()

	total_outgoing_bills, prev_total_outgoing_bills = (
		_invoice_total("Purchase Invoice", from_date, to_date),
		_invoice_total("Purchase Invoice", prev_from, prev_to),
	)
	total_incoming_bills, prev_total_incoming_bills = (
		_invoice_total("Sales Invoice", from_date, to_date),
		_invoice_total("Sales Invoice", prev_from, prev_to),
	)
	total_incoming_payment, prev_total_incoming_payment = (
		_payment_total("Receive", from_date, to_date),
		_payment_total("Receive", prev_from, prev_to),
	)
	total_outgoing_payment, prev_total_outgoing_payment = (
		_payment_total("Pay", from_date, to_date),
		_payment_total("Pay", prev_from, prev_to),
	)

	total_active_items = _total_active_items()
	total_warehouses = _total_warehouses()
	total_stock_value = _total_stock_value()

	power_units, power_output_mt = _power_units_and_output_mt(from_date, to_date)
	prev_power_units, prev_power_output_mt = _power_units_and_output_mt(prev_from, prev_to)
	power_consumption_kwh_per_ton = flt(power_units / power_output_mt, 1) if power_output_mt else 0
	prev_power_consumption_kwh_per_ton = flt(prev_power_units / prev_power_output_mt, 1) if prev_power_output_mt else 0

	gas_cost, gas_output_mt = _gas_consumption_and_output_mt(from_date, to_date)
	prev_gas_cost, prev_gas_output_mt = _gas_consumption_and_output_mt(prev_from, prev_to)
	gas_cost_per_ton = flt(gas_cost / gas_output_mt, 2) if gas_output_mt else 0
	prev_gas_cost_per_ton = flt(prev_gas_cost / prev_gas_output_mt, 2) if prev_gas_output_mt else 0

	return [
		{
			"key": "raw_material_consumption_mt",
			"label": "Raw Material Consumption",
			"icon": "scrap",
			"color": "orange",
			"unit": "Ton",
			"precision": 1,
			"value": round(raw_material_consumption_mt, 1),
			"delta": _delta_pct(raw_material_consumption_mt, prev_raw_material_consumption_mt),
		},
		{
			"key": "billet_production_mt",
			"label": "Billet Production",
			"icon": "billet",
			"color": "gold",
			"unit": "Ton",
			"precision": 1,
			"value": round(billet_production_mt, 1),
			"delta": _delta_pct(billet_production_mt, prev_billet_production_mt),
		},
		{
			"key": "bar_production_mt",
			"label": "Bar Production",
			"icon": "coil",
			"color": "blue",
			"unit": "Ton",
			"precision": 1,
			"value": round(bar_production_mt, 1),
			"delta": _delta_pct(bar_production_mt, prev_bar_production_mt),
		},
		{
			"key": "heats",
			"label": "Liquid Steel (Heat)",
			"icon": "heat",
			"color": "orange",
			"unit": "Heats",
			"precision": 0,
			"value": heats,
			"delta": _delta_pct(heats, prev_heats),
		},
		{
			"key": "sales_mt",
			"label": "Sales",
			"icon": "truck",
			"color": "green",
			"unit": "Ton",
			"precision": 1,
			"value": round(sales_qty, 1),
			"delta": _delta_pct(sales_qty, prev_sales_qty),
		},
		{
			"key": "revenue_m",
			"label": "Revenue",
			"icon": "coins",
			"color": "gold",
			"unit": "PKR M",
			"precision": 2,
			"value": round(revenue / 1_000_000, 2),
			"delta": _delta_pct(revenue, prev_revenue),
		},
		{
			"key": "gross_margin_pct",
			"label": "Gross Margin",
			"icon": "pie",
			"color": "purple",
			"unit": "%",
			"precision": 1,
			"value": gross_margin["value"],
			"delta": gross_margin["delta"],
			"is_demo": gross_margin.get("is_demo"),
		},
		# Sales section only (see KPI_ROWS.sales in steel_dashboard.js) - the
		# Ittehad equivalent of /app/dashboard-view/Selling's four number
		# cards (Annual Sales, Sales Orders to Deliver, Sales Orders to Bill,
		# Active Customers), scoped to this dashboard's date range.
		{
			"key": "sales_order_value",
			"label": "Sales Order Value",
			"icon": "dollar",
			"color": "green",
			"unit": "PKR M",
			"precision": 2,
			"value": round(sales_order_value / 1_000_000, 2),
			"delta": _delta_pct(sales_order_value, prev_sales_order_value),
		},
		{
			"key": "sales_orders_to_deliver",
			"label": "Sales Orders to Deliver",
			"icon": "box",
			"color": "blue",
			"unit": "Orders",
			"precision": 0,
			"value": sales_orders_to_deliver,
			"delta": _delta_pct(sales_orders_to_deliver, prev_sales_orders_to_deliver),
		},
		{
			"key": "sales_orders_to_bill",
			"label": "Sales Orders to Bill",
			"icon": "doc",
			"color": "orange",
			"unit": "Orders",
			"precision": 0,
			"value": sales_orders_to_bill,
			"delta": _delta_pct(sales_orders_to_bill, prev_sales_orders_to_bill),
		},
		{
			"key": "active_customers",
			"label": "Active Customers",
			"icon": "cart",
			"color": "purple",
			"unit": "Customers",
			"precision": 0,
			"value": active_customers,
			"delta": 0,
		},
		# Finance section only (see KPI_ROWS.finance in steel_dashboard.js) -
		# the Ittehad equivalent of /app/dashboard-view/Accounts' four number
		# cards (Total Outgoing/Incoming Bills, Total Incoming/Outgoing
		# Payment), scoped to this dashboard's date range.
		{
			"key": "total_outgoing_bills",
			"label": "Total Outgoing Bills",
			"icon": "doc",
			"color": "orange",
			"unit": "PKR M",
			"precision": 2,
			"value": round(total_outgoing_bills / 1_000_000, 2),
			"delta": _delta_pct(total_outgoing_bills, prev_total_outgoing_bills),
		},
		{
			"key": "total_incoming_bills",
			"label": "Total Incoming Bills",
			"icon": "coins",
			"color": "green",
			"unit": "PKR M",
			"precision": 2,
			"value": round(total_incoming_bills / 1_000_000, 2),
			"delta": _delta_pct(total_incoming_bills, prev_total_incoming_bills),
		},
		{
			"key": "total_incoming_payment",
			"label": "Total Incoming Payment",
			"icon": "dollar",
			"color": "blue",
			"unit": "PKR M",
			"precision": 2,
			"value": round(total_incoming_payment / 1_000_000, 2),
			"delta": _delta_pct(total_incoming_payment, prev_total_incoming_payment),
		},
		{
			"key": "total_outgoing_payment",
			"label": "Total Outgoing Payment",
			"icon": "truck",
			"color": "purple",
			"unit": "PKR M",
			"precision": 2,
			"value": round(total_outgoing_payment / 1_000_000, 2),
			"delta": _delta_pct(total_outgoing_payment, prev_total_outgoing_payment),
		},
		# Inventory section only (see KPI_ROWS.inventory in
		# steel_dashboard.js) - the Ittehad equivalent of
		# /app/dashboard-view/Stock's three number cards (Total Active Items,
		# Total Warehouses, Total Stock Value). Live snapshots, not scoped to
		# the dashboard's date range, same precedent as Active Customers.
		{
			"key": "total_active_items",
			"label": "Total Active Items",
			"icon": "box",
			"color": "blue",
			"unit": "Items",
			"precision": 0,
			"value": total_active_items,
			"delta": 0,
		},
		{
			"key": "total_warehouses",
			"label": "Total Warehouses",
			"icon": "factory",
			"color": "purple",
			"unit": "Warehouses",
			"precision": 0,
			"value": total_warehouses,
			"delta": 0,
		},
		{
			"key": "total_stock_value",
			"label": "Total Stock Value",
			"icon": "coins",
			"color": "gold",
			"unit": "PKR M",
			"precision": 2,
			"value": round(total_stock_value / 1_000_000, 2),
			"delta": 0,
		},
		# Energy section only (see KPI_ROWS.energy in steel_dashboard.js) -
		# Power and Gas each as a total spend plus a per-Ton efficiency ratio,
		# the same two Melting Entry figures get_power_consumption()/
		# get_gas_consumption() already expose to the kv panels, as proper
		# KPI cards with a vs-last-period delta.
		{
			"key": "total_power_units",
			"label": "Power Units Consumed",
			"icon": "bolt",
			"color": "gold",
			"unit": "kWh",
			"precision": 0,
			"value": round(power_units, 0),
			"delta": _delta_pct(power_units, prev_power_units),
		},
		{
			"key": "power_consumption_kwh_per_ton",
			"label": "Power Consumption",
			"icon": "bolt",
			"color": "orange",
			"unit": "kWh/Ton",
			"precision": 1,
			"value": power_consumption_kwh_per_ton,
			"delta": _delta_pct(power_consumption_kwh_per_ton, prev_power_consumption_kwh_per_ton),
		},
		{
			"key": "total_gas_cost_m",
			"label": "Gas Consumption Cost",
			"icon": "coins",
			"color": "blue",
			"unit": "PKR M",
			"precision": 2,
			"value": round(gas_cost / 1_000_000, 2),
			"delta": _delta_pct(gas_cost, prev_gas_cost),
		},
		{
			"key": "gas_cost_per_ton",
			"label": "Gas Consumption",
			"icon": "coins",
			"color": "purple",
			"unit": "PKR/Ton",
			"precision": 2,
			"value": gas_cost_per_ton,
			"delta": _delta_pct(gas_cost_per_ton, prev_gas_cost_per_ton),
		},
	]


# --------------------------------------------------------- live: charts

def _daily_production_trend(from_date, to_date, prev_from, prev_to, doctype, date_field, sum_field):
	"""Shared day-by-day trend series (this period vs the same length of the
	previous period), in Ton - used for both the Furnace (Melting Entry) and
	Deformed Bar (Rolling Entry) production trend charts."""

	def _daily(f, t):
		rows = frappe.db.sql(
			"""
			select {date_field}, sum({sum_field})
			from `tab{doctype}`
			where docstatus = 1 and {date_field} between %s and %s
			group by {date_field}
			""".format(date_field=date_field, sum_field=sum_field, doctype=doctype),
			(f, t),
		)
		return {str(r[0]): flt(r[1]) for r in rows}

	this_map, prev_map = _daily(from_date, to_date), _daily(prev_from, prev_to)

	days = (getdate(to_date) - getdate(from_date)).days + 1
	labels, this_week, last_week = [], [], []
	for i in range(days):
		d, pd = add_days(from_date, i), add_days(prev_from, i)
		labels.append(getdate(d).strftime("%a"))
		this_week.append(round(this_map.get(str(getdate(d)), 0), 2))
		last_week.append(round(prev_map.get(str(getdate(pd)), 0), 2))
	return {"labels": labels, "this_week": this_week, "last_week": last_week}


def get_furnace_production_trend(from_date, to_date, prev_from, prev_to):
	return _daily_production_trend(
		from_date, to_date, prev_from, prev_to, "Melting Entry", "posting_date", "total_output_weight"
	)


def get_deformed_bar_production_trend(from_date, to_date, prev_from, prev_to):
	return _daily_production_trend(
		from_date, to_date, prev_from, prev_to, "Rolling Entry", "date", "total_finish_qty"
	)


def _by_product_wastage_mt(from_date, to_date):
	total = frappe.db.sql(
		"""
		select sum(total_by_product_weight)
		from `tabWorkday Closing Entry`
		where docstatus = 1 and from_date between %s and %s
		""",
		(from_date, to_date),
	)[0][0]
	return flt(total)


def get_production_by_product(from_date, to_date):
	"""Production By Product Group - one row per output stream, each pulled
	from the doctype that actually produces it (Item Group noted for context,
	not as a query filter): Billet (Melting Entry output), Deformed Bar
	(Rolling Entry output), By Product Wastage (Workday Closing Entry)."""
	rows = [
		{"label": "Billet", "qty_mt": _billet_production_mt(from_date, to_date)},
		{"label": "Deformed Bar", "qty_mt": _bar_production_mt(from_date, to_date)},
		{"label": "By Product Wastage", "qty_mt": _by_product_wastage_mt(from_date, to_date)},
	]
	total = sum(r["qty_mt"] for r in rows) or 1
	return [
		{"label": r["label"], "qty_mt": round(r["qty_mt"], 2), "pct": round(r["qty_mt"] / total * 100, 1)}
		for r in rows
	]


def _month_buckets(from_date, to_date):
	"""Ordered list of calendar month-start dates covering [from_date,
	to_date] - one entry per bar in every month-bucketed trend chart below."""
	from_date, to_date = getdate(from_date), getdate(to_date)
	months = (to_date.year - from_date.year) * 12 + (to_date.month - from_date.month) + 1
	cursor = from_date.replace(day=1)
	out = []
	for _ in range(months):
		out.append(cursor)
		cursor = add_months(cursor, 1)
	return out


def _align_monthly(this_map, prev_map, from_date, to_date, prev_from):
	"""Turn two {'YYYY-MM': value} maps into aligned labels/this/last lists,
	one entry per calendar month in [from_date, to_date] (the "last period"
	series walks forward from prev_from the same number of months) - shared
	by every month-bucketed trend chart (get_sales_order_trend()'s wide-range
	branch, Incoming/Outgoing Bills, Profit trend). Deliberately labeled
	"Jul"/"Aug" (not Frappe's own "Jul (Amt)") - the "(Amt)" suffix is a
	value-field name leaking into the chart, not something a reader needs."""
	months = _month_buckets(from_date, to_date)
	prev_cursor = getdate(prev_from).replace(day=1)
	labels, this_values, prev_values = [], [], []
	for m in months:
		labels.append(m.strftime("%b"))
		this_values.append(round(this_map.get(m.strftime("%Y-%m"), 0), 2))
		prev_values.append(round(prev_map.get(prev_cursor.strftime("%Y-%m"), 0), 2))
		prev_cursor = add_months(prev_cursor, 1)
	return labels, this_values, prev_values


def _monthly_trend(doctype, date_field, sum_field, from_date, to_date, prev_from, prev_to):
	"""Month-bucketed sum(sum_field), for date ranges too wide for daily bars
	to stay readable (a full year is 365 bars) - one bar per calendar month,
	this period vs the same number of months starting at prev_from. Used for
	Incoming/Outgoing Bills below and Sales Order Trends' wide-range branch
	(see get_sales_order_trend())."""

	def _monthly(f, t):
		rows = frappe.db.sql(
			"""
			select date_format({date_field}, '%%Y-%%m') ym, sum({sum_field})
			from `tab{doctype}`
			where docstatus = 1 and {date_field} between %s and %s
			group by ym
			""".format(date_field=date_field, sum_field=sum_field, doctype=doctype),
			(f, t),
		)
		return {r[0]: flt(r[1]) for r in rows}

	this_map, prev_map = _monthly(from_date, to_date), _monthly(prev_from, prev_to)
	labels, this_values, prev_values = _align_monthly(this_map, prev_map, from_date, to_date, prev_from)
	return {"labels": labels, "this_week": this_values, "last_week": prev_values}


def _adaptive_trend(doctype, date_field, sum_field, from_date, to_date, prev_from, prev_to):
	"""Daily buckets (_daily_production_trend(), matching the Production
	Trend charts) for a date range a month wide or less; beyond that a
	day-per-bar chart stops being readable (a full year is 365 bars), so
	this switches to one bar per calendar month instead (_monthly_trend()) -
	shared by every trend chart whose date range isn't fixed to a short
	window (Sales Order Trends, Energy's Power/Gas Consumption Trends)."""
	days = (getdate(to_date) - getdate(from_date)).days + 1
	if days <= 31:
		return _daily_production_trend(from_date, to_date, prev_from, prev_to, doctype, date_field, sum_field)
	return _monthly_trend(doctype, date_field, sum_field, from_date, to_date, prev_from, prev_to)


def get_sales_order_trend(from_date, to_date, prev_from, prev_to):
	"""Sales section's equivalent of /app/dashboard-view/Selling's "Sales Order
	Trends" chart - Sales Order value (PKR M), this period vs last, drawn with
	the same trend_card_html()/bars()+sparkline() widgets as the Production
	Trend charts (see _adaptive_trend())."""
	trend = _adaptive_trend("Sales Order", "transaction_date", "base_net_total", from_date, to_date, prev_from, prev_to)
	scale = lambda values: [round(v / 1_000_000, 3) for v in values]
	return {"labels": trend["labels"], "this_week": scale(trend["this_week"]), "last_week": scale(trend["last_week"])}


def get_top_customers(from_date, to_date, limit=8):
	"""Sales section's equivalent of /app/dashboard-view/Selling's "Top
	Customers" chart - customers ranked by invoiced revenue (PKR M) in the
	period, rendered as a horizontal bar list (widgets.hbars(), same as Sales
	by Product's own bar list)."""
	rows = frappe.db.sql(
		"""
		select customer_name, sum(base_grand_total) revenue
		from `tabSales Invoice`
		where docstatus = 1 and posting_date between %s and %s
		group by customer
		order by revenue desc
		limit %s
		""",
		(from_date, to_date, limit),
	)
	return [{"customer": r[0], "revenue": round(flt(r[1]) / 1_000_000, 3), "unit": "PKR M"} for r in rows]


def get_sales_order_billing_split(from_date, to_date):
	"""Sales section's equivalent of /app/dashboard-view/Selling's "Sales
	Order Analysis" donut - Billed vs still-to-bill amount, for open Sales
	Orders placed in the period ("To Bill"/"To Deliver" only, same status
	filter Selling's own chart uses - "To Deliver and Bill" orders are fully
	unbilled so they'd only ever add to one side and skew the split)."""
	rows = frappe.db.sql(
		"""
		select grand_total, per_billed
		from `tabSales Order`
		where docstatus = 1 and status in ('To Bill', 'To Deliver')
			and transaction_date between %s and %s
		""",
		(from_date, to_date),
	)
	billed = sum(flt(r[0]) * flt(r[1]) / 100 for r in rows)
	total = sum(flt(r[0]) for r in rows)
	return [
		{"label": "Amount to Bill", "value": round(total - billed, 2)},
		{"label": "Billed Amount", "value": round(billed, 2)},
	]


def get_sales_by_product(from_date, to_date):
	"""Sales by Product - per actual product (Item), not just Item Group, so
	"by Product" shows what it says: the specific items driving sales, sorted
	best-selling first. Grouped by (item, uom) rather than item alone - the
	same item sold in two different UOMs would otherwise get summed into one
	meaningless qty (same mixed-unit trap as Inventory (Warehouse Wise)).
	revenue (base_amount) powers the second "by Revenue" pie alongside qty."""
	rows = frappe.db.sql(
		"""
		select coalesce(sii.item_name, sii.item_code) item, sii.uom, sum(sii.qty) qty, sum(sii.base_amount) revenue
		from `tabSales Invoice Item` sii
		inner join `tabSales Invoice` si on si.name = sii.parent
		where si.docstatus = 1 and si.posting_date between %s and %s
		group by sii.item_code, sii.uom
		order by qty desc
		""",
		(from_date, to_date),
	)
	return [
		{"label": r[0], "unit": r[1], "qty": round(flt(r[2]), 1), "revenue": round(flt(r[3]), 2)} for r in rows
	]


# -------------------------------------------------------- live: finance

def _income_expense(from_date, to_date):
	"""(income, expense) totals from GL Entry for the period - Income
	accounts carry a credit balance (credit - debit), Expense accounts a
	debit balance (debit - credit)."""
	rows = frappe.db.sql(
		"""
		select acc.root_type, sum(gle.debit) debit, sum(gle.credit) credit
		from `tabGL Entry` gle
		inner join `tabAccount` acc on acc.name = gle.account
		where gle.is_cancelled = 0 and gle.posting_date between %s and %s
			and acc.root_type in ('Income', 'Expense')
		group by acc.root_type
		""",
		(from_date, to_date),
		as_dict=True,
	)
	by_type = {r.root_type: r for r in rows}
	income = (flt(by_type["Income"].credit) - flt(by_type["Income"].debit)) if "Income" in by_type else 0
	expense = (flt(by_type["Expense"].debit) - flt(by_type["Expense"].credit)) if "Expense" in by_type else 0
	return income, expense


def get_profit_and_loss(from_date, to_date):
	"""Finance section's equivalent of /app/dashboard-view/Accounts' "Profit
	and Loss" card - Total Income/Total Expense/Profit for the period (this
	dashboard's own date range stands in for Frappe's fixed "This Year",
	same precedent as every other KPI here)."""
	income, expense = _income_expense(from_date, to_date)
	return {
		"income": round(income / 1_000_000, 2),
		"expense": round(expense / 1_000_000, 2),
		"profit": round((income - expense) / 1_000_000, 2),
	}


def get_profit_and_loss_statement(from_date, to_date):
	"""Finance Report's hierarchical Profit and Loss Statement - the real
	Chart of Accounts (Income/Expense, indented by account group, group
	totals bold) with each account's actual GL Entry balance for the period,
	the same shape /app/query-report/Profit and Loss Statement shows.
	Reuses ERPNext's own financial_statements module (the account-tree
	rollup it runs) instead of re-deriving nested-set/debit-credit-sign
	logic here - one row per account: {label, indent, is_group, value}.
	Empty if there's no default Company or no Fiscal Year covers the
	selected range (get_period_list() needs one) - same "front end shows
	empty state" precedent as Budget Variance/Item Shortage Summary."""
	company = frappe.defaults.get_global_default("company")
	if not company:
		return []

	try:
		from erpnext.accounts.report.financial_statements import get_data, get_period_list
		from erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement import (
			get_net_profit_loss,
		)

		period_list = get_period_list(None, None, from_date, to_date, "Date Range", "Yearly", company=company)
		report_filters = frappe._dict({"company": company, "accumulated_values": 0})

		income = get_data(
			company, "Income", "Credit", period_list, filters=report_filters, accumulated_values=0, ignore_closing_entries=True
		)
		expense = get_data(
			company, "Expense", "Debit", period_list, filters=report_filters, accumulated_values=0, ignore_closing_entries=True
		)
		net_profit_loss = get_net_profit_loss(income, expense, period_list, company)
	except Exception:
		frappe.log_error(title="Steel Dashboard: Profit and Loss Statement")
		return []

	rows = []
	for section in (income or []) + (expense or []):
		if not section or not section.get("account_name"):
			continue
		# add_total_row() wraps "Total Income (Credit)"/"Total Expense
		# (Debit)" in literal single-quotes (an internal
		# not-a-real-account-link convention) - strip them for display, and
		# bold them like a group row even though is_group is unset for them.
		label = section.get("account_name", "").strip("'")
		is_group = bool(section.get("is_group"))
		rows.append(
			{
				"label": label,
				"indent": cint(section.get("indent", 0)),
				"is_group": is_group,
				"bold": is_group or label.startswith("Total "),
				"value": flt(section.get("total", 0), 2),
			}
		)
	if net_profit_loss:
		rows.append(
			{
				"label": "Profit for the Period",
				"indent": 0,
				"is_group": True,
				"bold": True,
				"value": flt(net_profit_loss.get("total", 0), 2),
			}
		)
	return rows


def get_profit_and_loss_trend(from_date, to_date, prev_from, prev_to):
	"""Month-bucketed Profit (Income - Expense, PKR M) trend, this period vs
	last - drawn with the same trend_card_html()/bars()+sparkline() widgets
	as Sales Order Trends (see _align_monthly())."""

	def _monthly_profit(f, t):
		rows = frappe.db.sql(
			"""
			select date_format(gle.posting_date, '%%Y-%%m') ym, acc.root_type,
				sum(gle.debit) debit, sum(gle.credit) credit
			from `tabGL Entry` gle
			inner join `tabAccount` acc on acc.name = gle.account
			where gle.is_cancelled = 0 and gle.posting_date between %s and %s
				and acc.root_type in ('Income', 'Expense')
			group by ym, acc.root_type
			""",
			(f, t),
			as_dict=True,
		)
		by_ym = {}
		for r in rows:
			by_ym.setdefault(r.ym, {})[r.root_type] = r
		out = {}
		for ym, types in by_ym.items():
			income = (flt(types["Income"].credit) - flt(types["Income"].debit)) if "Income" in types else 0
			expense = (flt(types["Expense"].debit) - flt(types["Expense"].credit)) if "Expense" in types else 0
			out[ym] = income - expense
		return out

	this_map, prev_map = _monthly_profit(from_date, to_date), _monthly_profit(prev_from, prev_to)
	labels, this_values, prev_values = _align_monthly(this_map, prev_map, from_date, to_date, prev_from)
	scale = lambda values: [round(v / 1_000_000, 3) for v in values]
	return {"labels": labels, "this_week": scale(this_values), "last_week": scale(prev_values)}


def get_incoming_bills_trend(from_date, to_date, prev_from, prev_to):
	"""Finance section's equivalent of /app/dashboard-view/Accounts'
	"Incoming Bills (Purchase Invoice)" chart - Purchase Invoice value
	(PKR M) per month, this period vs last."""
	trend = _monthly_trend("Purchase Invoice", "posting_date", "base_grand_total", from_date, to_date, prev_from, prev_to)
	scale = lambda values: [round(v / 1_000_000, 3) for v in values]
	return {"labels": trend["labels"], "this_week": scale(trend["this_week"]), "last_week": scale(trend["last_week"])}


def get_outgoing_bills_trend(from_date, to_date, prev_from, prev_to):
	"""Finance section's equivalent of /app/dashboard-view/Accounts'
	"Outgoing Bills (Sales Invoice)" chart - Sales Invoice value (PKR M) per
	month, this period vs last."""
	trend = _monthly_trend("Sales Invoice", "posting_date", "base_grand_total", from_date, to_date, prev_from, prev_to)
	scale = lambda values: [round(v / 1_000_000, 3) for v in values]
	return {"labels": trend["labels"], "this_week": scale(trend["this_week"]), "last_week": scale(trend["last_week"])}


_AGEING_BUCKETS = [("0-30", 0, 30), ("31-60", 31, 60), ("61-90", 61, 90), ("91-120", 91, 120), ("121-Above", 121, None)]


def _ageing_buckets(doctype):
	"""0-30/31-60/61-90/91-120/121-Above split of outstanding (unpaid)
	<doctype> amount, aged off today() - due_date (falls back to
	posting_date when due_date is blank) - same buckets ERPNext's own
	Accounts Receivable/Payable Ageing report uses. A point-in-time snapshot
	of what's currently outstanding (not scoped to the dashboard's date
	range, same precedent as Active Customers/Inventory (Warehouse Wise)) -
	a 61-90 day overdue invoice from before the selected range is still
	money owed today."""
	rows = frappe.db.sql(
		"""
		select outstanding_amount, coalesce(due_date, posting_date) due_date
		from `tab{doctype}`
		where docstatus = 1 and outstanding_amount > 0
		""".format(doctype=doctype),
		as_dict=True,
	)
	totals = {label: 0 for label, _, _ in _AGEING_BUCKETS}
	today_ = getdate()
	for r in rows:
		age = max((today_ - getdate(r.due_date)).days, 0)
		for label, lo, hi in _AGEING_BUCKETS:
			if age >= lo and (hi is None or age <= hi):
				totals[label] += flt(r.outstanding_amount)
				break
	return [{"label": label, "value": round(totals[label], 2)} for label, _, _ in _AGEING_BUCKETS]


def get_ar_ageing():
	"""Finance section's equivalent of /app/dashboard-view/Accounts'
	"Accounts Receivable Ageing" donut - outstanding Sales Invoice amount by
	age bucket."""
	return _ageing_buckets("Sales Invoice")


def get_ap_ageing():
	"""Finance section's equivalent of /app/dashboard-view/Accounts'
	"Accounts Payable Ageing" donut - outstanding Purchase Invoice amount by
	age bucket."""
	return _ageing_buckets("Purchase Invoice")


def get_budget_variance(from_date, to_date):
	"""Finance section's equivalent of /app/dashboard-view/Accounts' "Budget
	Variance" chart - Budgeted vs Actual (GL Entry) spend per Budget
	Account, for submitted Budgets whose fiscal year overlaps the selected
	range. Empty (front end shows "No Data") until a Budget doc exists, same
	as the reference chart with none configured yet."""
	fiscal_years = frappe.db.sql(
		"""
		select name from `tabFiscal Year`
		where year_start_date <= %s and year_end_date >= %s
		""",
		(to_date, from_date),
	)
	fiscal_years = [r[0] for r in fiscal_years]
	if not fiscal_years:
		return []

	budgets = frappe.get_all("Budget", filters={"docstatus": 1, "fiscal_year": ["in", fiscal_years]}, pluck="name")
	if not budgets:
		return []

	accounts = frappe.get_all(
		"Budget Account", filters={"parent": ["in", budgets]}, fields=["account", "budget_amount"]
	)
	rows = []
	for a in accounts:
		actual = frappe.db.sql(
			"""
			select sum(gle.debit) - sum(gle.credit)
			from `tabGL Entry` gle
			where gle.account = %s and gle.is_cancelled = 0
				and gle.posting_date between %s and %s
			""",
			(a.account, from_date, to_date),
		)[0][0]
		rows.append({"label": a.account, "budget": round(flt(a.budget_amount), 2), "actual": round(flt(actual), 2)})
	return rows


def get_bank_balance_trend(from_date, to_date):
	"""Finance section's equivalent of /app/dashboard-view/Accounts' "Bank
	Balance" chart - running balance (PKR) of every Bank-type Account,
	summed, one point per day in the range. Empty (front end shows "No
	Data") until the Chart of Accounts has a Bank account configured."""
	bank_accounts = frappe.get_all("Account", filters={"account_type": "Bank", "is_group": 0}, pluck="name")
	if not bank_accounts:
		return {"labels": [], "values": []}

	opening = frappe.db.sql(
		"""
		select sum(debit) - sum(credit)
		from `tabGL Entry`
		where account in %s and is_cancelled = 0 and posting_date < %s
		""",
		(bank_accounts, from_date),
	)[0][0]
	balance = flt(opening)

	daily_rows = frappe.db.sql(
		"""
		select posting_date, sum(debit) - sum(credit)
		from `tabGL Entry`
		where account in %s and is_cancelled = 0 and posting_date between %s and %s
		group by posting_date
		""",
		(bank_accounts, from_date, to_date),
	)
	daily_map = {str(r[0]): flt(r[1]) for r in daily_rows}

	days = (getdate(to_date) - getdate(from_date)).days + 1
	labels, values = [], []
	for i in range(days):
		d = getdate(add_days(from_date, i))
		balance += daily_map.get(str(d), 0)
		labels.append(d.strftime("%d-%m-%Y"))
		values.append(round(balance, 2))
	return {"labels": labels, "values": values}


# ------------------------------------------------------------- live: energy

def _power_units_and_output_mt(from_date, to_date):
	row = frappe.db.sql(
		"""
		select sum(power_units), sum(total_output_weight)
		from `tabMelting Entry`
		where docstatus = 1 and posting_date between %s and %s
		""",
		(from_date, to_date),
	)[0]
	return flt(row[0]), flt(row[1])


def get_power_consumption(from_date, to_date):
	"""Energy Consumption (Power) - both figures come from the same two
	Melting Entry totals (power_units, total_output_weight), just expressed
	as reciprocal ratios: Power Consumption is kWh spent per Ton produced,
	Energy Efficiency is Ton produced per MWh spent."""
	power_units, output_mt = _power_units_and_output_mt(from_date, to_date)
	power_consumption = flt(power_units / output_mt, 1) if output_mt else 0
	energy_efficiency = flt(output_mt * 1000 / power_units, 3) if power_units else 0
	return {"power_consumption": power_consumption, "energy_efficiency": energy_efficiency}


def _gas_consumption_and_output_mt(from_date, to_date):
	row = frappe.db.sql(
		"""
		select sum(gas_consumption), sum(total_output_weight)
		from `tabMelting Entry`
		where docstatus = 1 and posting_date between %s and %s
		""",
		(from_date, to_date),
	)[0]
	return flt(row[0]), flt(row[1])


def get_gas_consumption(from_date, to_date):
	"""Energy Consumption (Gas) - Gas Consumption Cost is Melting Entry's
	gas_consumption summed as-is over the period; Energy Efficiency is that
	same cost per Ton produced (gas_consumption / total_output_weight)."""
	gas_cost, output_mt = _gas_consumption_and_output_mt(from_date, to_date)
	energy_efficiency = flt(gas_cost / output_mt, 2) if output_mt else 0
	return {"gas_consumption_cost": round(gas_cost, 2), "energy_efficiency": energy_efficiency}


def get_power_consumption_trend(from_date, to_date, prev_from, prev_to):
	"""Energy section's Power Consumption Trend - power_units (kWh) from
	Melting Entry, this period vs last, drawn with the same
	trend_card_html()/bars()+sparkline() widgets as the Production Trend
	charts (see _adaptive_trend())."""
	return _adaptive_trend("Melting Entry", "posting_date", "power_units", from_date, to_date, prev_from, prev_to)


def get_gas_consumption_trend(from_date, to_date, prev_from, prev_to):
	"""Energy section's Gas Consumption Trend - gas_consumption (PKR cost)
	from Melting Entry, this period vs last (see _adaptive_trend())."""
	return _adaptive_trend("Melting Entry", "posting_date", "gas_consumption", from_date, to_date, prev_from, prev_to)


# ------------------------------------------------------------ live: inventory

def get_warehouse_stock_value():
	"""Inventory section's equivalent of /app/dashboard-view/Stock's
	"Warehouse wise Stock Value" chart - live Bin.stock_value (money) summed
	per warehouse, unlike get_inventory_by_warehouse()'s Ton quantity table.
	A live snapshot, not scoped to the dashboard's date range, same
	precedent as the rest of the Inventory section."""
	rows = frappe.db.sql(
		"""
		select b.warehouse, sum(b.stock_value)
		from `tabBin` b
		inner join `tabWarehouse` w on w.name = b.warehouse
		where w.disabled = 0
		group by b.warehouse
		having sum(b.stock_value) != 0
		order by 2 desc
		"""
	)
	return [{"label": r[0], "value": round(flt(r[1]) / 1_000_000, 3)} for r in rows]


def get_purchase_receipt_trend(from_date, to_date, prev_from, prev_to):
	"""Inventory section's equivalent of /app/dashboard-view/Stock's
	"Purchase Receipt Trends" chart - Purchase Receipt value (PKR M) per
	month, this period vs last (see _monthly_trend())."""
	trend = _monthly_trend("Purchase Receipt", "posting_date", "base_grand_total", from_date, to_date, prev_from, prev_to)
	scale = lambda values: [round(v / 1_000_000, 3) for v in values]
	return {"labels": trend["labels"], "this_week": scale(trend["this_week"]), "last_week": scale(trend["last_week"])}


def get_delivery_trend(from_date, to_date, prev_from, prev_to):
	"""Inventory section's equivalent of /app/dashboard-view/Stock's
	"Delivery Trends" chart - Delivery Note value (PKR M) per month, this
	period vs last (see _monthly_trend())."""
	trend = _monthly_trend("Delivery Note", "posting_date", "base_grand_total", from_date, to_date, prev_from, prev_to)
	scale = lambda values: [round(v / 1_000_000, 3) for v in values]
	return {"labels": trend["labels"], "this_week": scale(trend["this_week"]), "last_week": scale(trend["last_week"])}


def get_oldest_items(limit=10):
	"""Inventory section's equivalent of /app/dashboard-view/Stock's "Oldest
	Items" chart - days since each in-stock item's last Stock Ledger Entry,
	oldest (longest untouched) first. A point-in-time snapshot, not scoped
	to the dashboard's date range (same precedent as Active Customers) - a
	fast-moving item that simply didn't move within the selected range
	shouldn't read as "old" just because the range excludes its last sale."""
	rows = frappe.db.sql(
		"""
		select sle.item_code, coalesce(it.item_name, sle.item_code) item_name, max(sle.posting_date) last_movement
		from `tabStock Ledger Entry` sle
		inner join `tabItem` it on it.name = sle.item_code
		where sle.is_cancelled = 0
			and sle.item_code in (select distinct item_code from `tabBin` where actual_qty > 0)
		group by sle.item_code
		order by last_movement asc
		limit %s
		""",
		(limit,),
	)
	today_ = getdate()
	return [{"label": r[1], "days": (today_ - getdate(r[2])).days} for r in rows]


def get_item_shortage_summary(limit=10):
	"""Inventory section's equivalent of /app/dashboard-view/Stock's "Item
	Shortage Summary" chart - Projected Qty short of the configured reorder
	level (warehouse_reorder_level - Bin.projected_qty), positive only
	(items actually needing reorder), worst first. Empty (front end shows
	"No data") until an Item's Reorder Level table is set up, same
	precedent as Budget Variance/Bank Balance in the Finance section."""
	rows = frappe.db.sql(
		"""
		select ir.parent, coalesce(it.item_name, ir.parent) item_name,
			ir.warehouse_reorder_level - coalesce(b.projected_qty, 0) shortage
		from `tabItem Reorder` ir
		inner join `tabItem` it on it.name = ir.parent
		left join `tabBin` b on b.item_code = ir.parent and b.warehouse = ir.warehouse
		where ir.warehouse_reorder_level > 0
		having shortage > 0
		order by shortage desc
		limit %s
		""",
		(limit,),
	)
	return [{"label": r[1], "value": round(flt(r[2]), 2)} for r in rows]


def get_inventory_by_warehouse():
	"""Inventory (Warehouse Wise) - live stock balance (`Bin.actual_qty`)
	summed per warehouse, as Ton. A warehouse's Bin rows can carry different
	stock UOMs per item (Kg or Ton in this app); Kg rows are folded into the
	same Ton total as-is (values are already recorded in Ton going forward -
	no unit conversion applied), while any other UOM is kept as its own row
	(with its own unit). Bin is a live snapshot (not date-ranged), so this
	ignores the dashboard's from/to filters - same as the rest of the
	Inventory section."""
	rows = frappe.db.sql(
		"""
		select b.warehouse, b.stock_uom, sum(b.actual_qty) qty
		from `tabBin` b
		inner join `tabWarehouse` w on w.name = b.warehouse
		where w.disabled = 0 and b.actual_qty != 0
		group by b.warehouse, b.stock_uom
		"""
	)

	ton_totals = {}
	other_rows = []
	for warehouse, stock_uom, qty in rows:
		qty = flt(qty)
		if stock_uom == "Ton":
			ton_totals[warehouse] = ton_totals.get(warehouse, 0) + qty
		elif stock_uom == "Kg":
			ton_totals[warehouse] = ton_totals.get(warehouse, 0) + qty
		else:
			other_rows.append({"warehouse": warehouse, "qty": round(qty, 2), "unit": stock_uom})

	ton_rows = [{"warehouse": w, "qty": round(qty, 2), "unit": "Ton"} for w, qty in ton_totals.items()]
	ton_rows.sort(key=lambda r: r["qty"], reverse=True)
	return ton_rows + other_rows


# ------------------------------------------------------- live: gauges

def _actual_melting_hours(from_date, to_date):
	seconds = frappe.db.sql(
		"""
		select sum(total_melting_time)
		from `tabMelting Entry`
		where docstatus = 1 and posting_date between %s and %s
		""",
		(from_date, to_date),
	)[0][0]
	return flt(seconds) / 3600


def get_gauges(from_date, to_date):
	"""Ordered, self-describing list of efficiency gauges - same "frontend
	renders however many come back" approach as get_kpis(). Capacity
	Utilization and OEE used to sit here as flat demo numbers (78%/72%,
	never changing); both are live now, computed from Melting Entry against
	Steel Dashboard Settings' rated capacity/planned hours/standard cycle
	time (see _dashboard_settings()) - edit those instead of the code to
	retune either gauge. To add a gauge: add one entry here - the front end
	needs no changes."""
	settings = _dashboard_settings()

	rolling_mill_yield = frappe.db.sql(
		"""
		select avg(yield_percent)
		from `tabWorkday Closing Entry`
		where docstatus = 1 and from_date between %s and %s
		""",
		(from_date, to_date),
	)[0][0]

	# Conversion Yield - Billet Production (Melting Entry output) as a % of
	# Raw Material Consumption (Melting Entry input) for the same period;
	# reuses the exact figures behind the Raw Material Consumption/Billet
	# Production KPI cards, so this gauge always agrees with them. Also
	# doubles as OEE's Quality factor below - the fraction of melted input
	# that actually became usable output.
	input_mt = _raw_material_consumption_mt(from_date, to_date)
	output_mt = _billet_production_mt(from_date, to_date)
	conversion_yield = flt(output_mt / input_mt * 100, 1) if input_mt else 0

	# Working days actually covered by the selected range, prorated by
	# Working Days per Week - e.g. a 7-day range at 5 working days/week
	# counts as 5 working days, not 7, so a weekend-inclusive range doesn't
	# understate Capacity Utilization/Availability.
	days = (getdate(to_date) - getdate(from_date)).days + 1
	working_days_per_week = settings.working_days_per_week or 7
	working_days = days * working_days_per_week / 7

	rated_capacity_mt = flt(settings.rated_melting_capacity_mt) * working_days
	capacity_utilization = flt(output_mt / rated_capacity_mt * 100, 1) if rated_capacity_mt else 0

	# OEE = Availability x Performance x Quality (standard formula):
	# Availability is time actually spent melting (Melting Entry's own
	# total_melting_time) against Planned Production Hours; Performance is
	# the ideal time Standard Cycle Time says the actual output should have
	# taken, against the time actually spent; Quality is Conversion Yield
	# above (good output / input).
	actual_hours = _actual_melting_hours(from_date, to_date)
	planned_hours = flt(settings.planned_production_hours) * working_days
	availability = actual_hours / planned_hours if planned_hours else 0

	ideal_hours = output_mt * flt(settings.standard_cycle_time_min) / 60
	performance = ideal_hours / actual_hours if actual_hours else 0

	oee = flt(availability * performance * (conversion_yield / 100) * 100, 1)

	return [
		{"key": "capacity_utilization", "label": "Capacity Utilization", "value": capacity_utilization},
		{"key": "conversion_yield", "label": "Conversion Yield", "value": conversion_yield},
		{"key": "rolling_mill_yield", "label": "Rolling Mill Yield", "value": flt(rolling_mill_yield, 1)},
		{"key": "oee", "label": "OEE", "value": oee},
	]


# ------------------------------------------------------ live: kv panels

def get_kv_panels(from_date, to_date):
	"""Ordered, self-describing list of label/value panels - same "frontend
	renders however many come back, with whatever title each one carries"
	approach as get_kpis()/get_gauges(). Quality/Maintenance actuals still
	have no backing doctype (see steel_dashboard_demo_data.py) - but the
	Target alongside each one is real, read from Steel Dashboard Settings
	(see _dashboard_settings()), not hardcoded. Both Energy panels are live
	(see get_power_consumption()/get_gas_consumption()), same as
	Inventory's demo MT breakdown was already replaced by the real Inventory
	(Warehouse Wise) table (get_inventory_by_warehouse()) everywhere it used
	to appear. Safety is live too now (Safety Incident, see get_safety()),
	but stays its own top-level key/widget (shield + status), not part of
	this generic list."""
	settings = _dashboard_settings()
	quality = demo.get_quality()
	maintenance = demo.get_maintenance()
	power = get_power_consumption(from_date, to_date)
	gas = get_gas_consumption(from_date, to_date)

	return [
		{
			"key": "quality",
			"title": "Quality (This Week)",
			"is_demo": 1,
			"rows": [
				["First Pass Yield", f"{quality['first_pass_yield']}% (Target {settings.target_first_pass_yield}%)"],
				["Rejection Rate", f"{quality['rejection_rate']}% (Target {settings.target_rejection_rate}%)"],
				["Customer Complaints", quality["customer_complaints"]],
				["Inspection Pass Rate", f"{quality['inspection_pass_rate']}% (Target {settings.target_inspection_pass_rate}%)"],
			],
		},
		{
			"key": "maintenance",
			"title": "Maintenance",
			"is_demo": 1,
			"rows": [
				["Planned Maintenance", f"{maintenance['planned_maintenance']}% (Target {settings.target_planned_maintenance}%)"],
				["Breakdown (hrs)", maintenance["breakdown_hrs"]],
				["MTBF (hrs)", f"{maintenance['mtbf']} (Target {settings.target_mtbf_hours})"],
				["MTTR (hrs)", f"{maintenance['mttr']} (Target {settings.target_mttr_hours})"],
			],
		},
		{
			"key": "energy_power",
			"title": "Energy Consumption (Power)",
			"rows": [
				["Power Consumption", f"{power['power_consumption']} kWh/Ton"],
				["Energy Efficiency", f"{power['energy_efficiency']} Ton/MWh"],
			],
		},
		{
			"key": "energy_gas",
			"title": "Energy Consumption (Gas)",
			"rows": [
				["Gas Consumption Cost", f"PKR {gas['gas_consumption_cost']}"],
				["Energy Efficiency", f"PKR {gas['energy_efficiency']}/Ton"],
			],
		},
	]


def get_safety(from_date, to_date):
	"""Safety (This Week) - live now, counted from submitted Safety Incident
	records in the period against Man-Hours per Day (Steel Dashboard
	Settings, prorated the same way Rated Melting Capacity is - this app has
	no Attendance/timesheet data to derive man-hours from instead):
	  LTIFR = Lost Time Injuries x 200,000 / Man-Hours
	  TRIR  = (Lost Time Injuries + Recordable Incidents) x 200,000 / Man-Hours
	(the standard OSHA-style frequency-rate formulas, incidents per 200,000
	man-hours - roughly 100 employees working a full year). `status` is SAFE
	only while LTIFR and TRIR are within their Settings targets AND Safety
	Observations meets its target (more observations is better - a low
	count means fewer people are reporting near-misses, not that nothing
	happened). Target values are included so the front end can show them
	alongside each actual, same as get_kv_panels()'s Quality/Maintenance
	rows."""
	settings = _dashboard_settings()

	days = (getdate(to_date) - getdate(from_date)).days + 1
	working_days_per_week = settings.working_days_per_week or 7
	working_days = days * working_days_per_week / 7
	man_hours = flt(settings.man_hours_per_day) * working_days

	rows = frappe.db.sql(
		"""
		select incident_type, count(*)
		from `tabSafety Incident`
		where docstatus = 1 and incident_date between %s and %s
		group by incident_type
		""",
		(from_date, to_date),
	)
	counts = {r[0]: r[1] for r in rows}
	lost_time = cint(counts.get("Lost Time Injury"))
	recordable = cint(counts.get("Recordable Incident"))
	observations = cint(counts.get("Near Miss / Observation"))

	ltifr = flt(lost_time * 200_000 / man_hours, 2) if man_hours else 0
	trir = flt((lost_time + recordable) * 200_000 / man_hours, 2) if man_hours else 0

	is_safe = ltifr <= settings.target_ltifr and trir <= settings.target_trir and observations >= settings.target_safety_observations

	return {
		"man_hours": round(man_hours, 0),
		"ltifr": ltifr,
		"trir": trir,
		"observations": observations,
		"status": "SAFE" if is_safe else "AT RISK",
		"target_ltifr": settings.target_ltifr,
		"target_trir": settings.target_trir,
		"target_observations": settings.target_safety_observations,
	}


def get_settings_summary():
	"""Ordered, self-describing list of Steel Dashboard Settings groups - same
	"frontend renders however many come back" approach as get_kpis(). The
	Settings section (steel_dashboard.js) renders this as an editable form
	(each field's raw value + step, not a pre-formatted display string) and
	posts changes back through update_settings()."""
	settings = _dashboard_settings()
	return [
		{
			"title": "Capacity & OEE",
			"fields": [
				{"fieldname": "rated_melting_capacity_mt", "label": "Rated Melting Capacity (Ton/Day)", "value": settings.rated_melting_capacity_mt, "step": 0.01},
				{"fieldname": "standard_cycle_time_min", "label": "Standard Cycle Time (Min/Ton)", "value": settings.standard_cycle_time_min, "step": 0.01},
				{"fieldname": "planned_production_hours", "label": "Planned Production Hours (Per Day)", "value": settings.planned_production_hours, "step": 0.1},
				{"fieldname": "working_days_per_week", "label": "Working Days per Week", "value": settings.working_days_per_week, "step": 1},
			],
		},
		{
			"title": "Quality Targets",
			"fields": [
				{"fieldname": "target_first_pass_yield", "label": "Target First Pass Yield (%)", "value": settings.target_first_pass_yield, "step": 0.1},
				{"fieldname": "target_rejection_rate", "label": "Target Rejection Rate (%)", "value": settings.target_rejection_rate, "step": 0.1},
				{"fieldname": "target_inspection_pass_rate", "label": "Target Inspection Pass Rate (%)", "value": settings.target_inspection_pass_rate, "step": 0.1},
			],
		},
		{
			"title": "Maintenance Targets",
			"fields": [
				{"fieldname": "target_planned_maintenance", "label": "Target Planned Maintenance (%)", "value": settings.target_planned_maintenance, "step": 0.1},
				{"fieldname": "target_mtbf_hours", "label": "Target MTBF (Hours)", "value": settings.target_mtbf_hours, "step": 0.1},
				{"fieldname": "target_mttr_hours", "label": "Target MTTR (Hours)", "value": settings.target_mttr_hours, "step": 0.1},
			],
		},
		{
			"title": "Safety Targets",
			"fields": [
				{"fieldname": "target_ltifr", "label": "Target LTIFR", "value": settings.target_ltifr, "step": 0.01},
				{"fieldname": "target_trir", "label": "Target TRIR", "value": settings.target_trir, "step": 0.01},
				{"fieldname": "target_safety_observations", "label": "Target Safety Observations (Per Period)", "value": settings.target_safety_observations, "step": 1},
			],
		},
	]


# Every field update_settings() is allowed to touch - posted keys outside
# this set are silently ignored rather than passed to doc.set(), so the
# Settings section's edit form can never write to a field it doesn't
# actually render (or anything else on the doctype).
_EDITABLE_SETTINGS_FIELDS = {
	"rated_melting_capacity_mt",
	"standard_cycle_time_min",
	"planned_production_hours",
	"working_days_per_week",
	"target_first_pass_yield",
	"target_rejection_rate",
	"target_inspection_pass_rate",
	"target_planned_maintenance",
	"target_mtbf_hours",
	"target_mttr_hours",
	"target_ltifr",
	"target_trir",
	"target_safety_observations",
}


@frappe.whitelist()
def update_settings(values):
	"""Save the Settings section's edit form (steel_dashboard.js) back to the
	Steel Dashboard Settings singleton, then return the refreshed summary so
	the form can redraw with the saved values. Goes through Document.save(),
	so it fails exactly like editing the doctype form directly would for a
	user without write permission on Steel Dashboard Settings - no separate
	permission check needed here."""
	if isinstance(values, str):
		values = frappe.parse_json(values)

	doc = _dashboard_settings()
	for fieldname, value in values.items():
		if fieldname in _EDITABLE_SETTINGS_FIELDS:
			doc.set(fieldname, value)
	doc.save()
	return get_settings_summary()


# --------------------------------------------------------------- endpoint

@frappe.whitelist()
def get_dashboard_data(from_date, to_date):
	prev_from, prev_to = _prev_period(from_date, to_date)

	return {
		"company_logo": _company_logo(),
		"kpi": get_kpis(from_date, to_date, prev_from, prev_to),
		"production_trend_furnace": get_furnace_production_trend(from_date, to_date, prev_from, prev_to),
		"production_trend_deformed_bar": get_deformed_bar_production_trend(from_date, to_date, prev_from, prev_to),
		"production_by_product": get_production_by_product(from_date, to_date),
		"sales_by_product": get_sales_by_product(from_date, to_date),
		"sales_order_trend": get_sales_order_trend(from_date, to_date, prev_from, prev_to),
		"top_customers": get_top_customers(from_date, to_date),
		"sales_order_billing_split": get_sales_order_billing_split(from_date, to_date),
		"profit_and_loss": get_profit_and_loss(from_date, to_date),
		"profit_and_loss_statement": get_profit_and_loss_statement(from_date, to_date),
		"profit_and_loss_trend": get_profit_and_loss_trend(from_date, to_date, prev_from, prev_to),
		"incoming_bills_trend": get_incoming_bills_trend(from_date, to_date, prev_from, prev_to),
		"outgoing_bills_trend": get_outgoing_bills_trend(from_date, to_date, prev_from, prev_to),
		"ar_ageing": get_ar_ageing(),
		"ap_ageing": get_ap_ageing(),
		"budget_variance": get_budget_variance(from_date, to_date),
		"bank_balance_trend": get_bank_balance_trend(from_date, to_date),
		"inventory_by_warehouse": get_inventory_by_warehouse(),
		"warehouse_stock_value": get_warehouse_stock_value(),
		"purchase_receipt_trend": get_purchase_receipt_trend(from_date, to_date, prev_from, prev_to),
		"delivery_trend": get_delivery_trend(from_date, to_date, prev_from, prev_to),
		"oldest_items": get_oldest_items(),
		"item_shortage_summary": get_item_shortage_summary(),
		"power_consumption_trend": get_power_consumption_trend(from_date, to_date, prev_from, prev_to),
		"gas_consumption_trend": get_gas_consumption_trend(from_date, to_date, prev_from, prev_to),
		"gauges": get_gauges(from_date, to_date),
		"kv_panels": get_kv_panels(from_date, to_date),
		"safety": get_safety(from_date, to_date),
		"settings": get_settings_summary(),
	}


# ---------------------------------------------------------------- reports

def _parse_report_payload(columns, rows):
	if isinstance(columns, str):
		columns = frappe.parse_json(columns)
	if isinstance(rows, str):
		rows = frappe.parse_json(rows)
	return columns, rows


@frappe.whitelist()
def export_report_excel(title, columns, rows, subtitle=None):
	"""Generic "these exact rows, as a downloaded .xlsx" endpoint for the
	Reports section (steel_dashboard.js) - the report content itself is
	already computed client-side from the same get_dashboard_data() payload
	every other section renders from (see build_report()), so this only
	formats it, it doesn't recompute anything. `rows` is a list of
	{label, value, indent, bold, section} (the same shape the Finance
	Report's hierarchical Profit and Loss Statement uses, see
	get_profit_and_loss_statement()) - indent renders as leading spaces.
	A regular (not write-only) Workbook is built directly here rather than
	via frappe.utils.xlsxutils.make_xlsx(), since a `section` row (the
	dashboard Export dialog's per-section title, see build_export_rows() in
	steel_dashboard.js) needs a real filled/bold cell to stand out from its
	own section's internal bold sub-headers, and write-only sheets have no
	per-cell style hook for that."""
	columns, rows = _parse_report_payload(columns, rows)

	import openpyxl
	from openpyxl.styles import Font, PatternFill

	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = "Report"

	ws.append([title])
	ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=14)
	if subtitle:
		ws.append([subtitle])
	ws.append([])
	ws.append(columns)
	for cell in ws[ws.max_row]:
		cell.font = Font(bold=True)

	section_fill = PatternFill(start_color="DCE6F5", end_color="DCE6F5", fill_type="solid")
	for r in rows:
		indent = cint(r.get("indent", 0))
		label = ("    " * indent) + str(r.get("label", ""))
		value = r.get("value", "")
		ws.append([label, "" if value is None else value])
		if r.get("section"):
			for cell in ws[ws.max_row]:
				cell.font = Font(bold=True, size=12, color="1D4ED8")
				cell.fill = section_fill
		elif r.get("bold"):
			for cell in ws[ws.max_row]:
				cell.font = Font(bold=True)

	ws.column_dimensions["A"].width = 46
	ws.column_dimensions["B"].width = 24

	from io import BytesIO

	xlsx_file = BytesIO()
	wb.save(xlsx_file)
	frappe.response["filename"] = f"{title}.xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "download"


@frappe.whitelist()
def export_report_pdf(title, columns, rows, subtitle=None):
	"""Same idea as export_report_excel() but as a PDF - a real indented/
	bold HTML table (padding-left per indent level, bold group/total rows)
	run through Frappe's own PDF generator (wkhtmltopdf, via
	frappe.utils.pdf) - the same hierarchy the Finance Report's Profit and
	Loss Statement shows on screen, not a flattened metric list. Headed with
	the default Company's logo/name (see _company_header()) - a table-based
	layout, not flexbox, since wkhtmltopdf's CSS support is dated enough that
	flexbox isn't reliable."""
	columns, rows = _parse_report_payload(columns, rows)

	from frappe.utils.pdf import get_pdf

	company, logo_data_uri = _company_header()
	logo_cell = f'<td style="text-align:right;vertical-align:top;"><img src="{logo_data_uri}" style="height:64px;" /></td>' if logo_data_uri else ""

	thead = "".join(f"<th>{escape_html(str(c))}</th>" for c in columns)
	body_rows = []
	for r in rows:
		label = escape_html(str(r.get("label", "")))
		# A `section` row (the dashboard Export dialog's per-section title,
		# see build_export_rows() in steel_dashboard.js) is highlighted as
		# its own full-width band rather than just another bold cell, so
		# several exported sections stay visually distinct from each other
		# and from their own internal bold sub-headers (e.g. "Finance KPIs").
		if r.get("section"):
			body_rows.append(
				f'<tr><td colspan="{len(columns)}" style="background:#eef3fb;border-bottom:2px solid #3b82f6;'
				f'padding:8px 10px;font-size:14px;font-weight:700;color:#1d4ed8;">{label}</td></tr>'
			)
			continue
		indent = cint(r.get("indent", 0))
		style = "font-weight:700;" if r.get("bold") else ""
		value = r.get("value", "")
		value = escape_html("" if value is None else str(value))
		body_rows.append(
			f'<tr><td style="padding-left:{10 + indent * 16}px;{style}">{label}</td>'
			f'<td style="text-align:right;{style}">{value}</td></tr>'
		)
	tbody = "".join(body_rows)
	subtitle_html = f'<div style="color:#666;font-size:11px;margin-top:2px;">{escape_html(subtitle)}</div>' if subtitle else ""

	html = f"""
		<table style="width:100%;border-collapse:collapse;font-family:sans-serif;border-bottom:2px solid #333;padding-bottom:10px;margin-bottom:16px;">
			<tr>
				<td style="vertical-align:top;">
					<div style="font-size:22px;font-weight:700;color:#111;">{escape_html(company)}</div>
					<h2 style="margin:2px 0 0;font-size:16px;font-weight:600;">{escape_html(title)}</h2>
					{subtitle_html}
				</td>
				{logo_cell}
			</tr>
		</table>
		<table style="width:100%;border-collapse:collapse;font-family:sans-serif;font-size:11px;">
			<thead><tr style="background:#f0f0f0;">{thead}</tr></thead>
			<tbody>{tbody}</tbody>
		</table>
		<style>td, th {{ border: 1px solid #ccc; padding: 5px 8px; text-align: left; }}</style>
	"""
	frappe.response["filename"] = f"{title}.pdf"
	frappe.response["filecontent"] = get_pdf(html)
	frappe.response["type"] = "pdf"
