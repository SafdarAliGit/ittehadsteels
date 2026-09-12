"""
Server side for the Ittehad Steels KPI Dashboard page.

Everything in this file is queried live from real doctypes (Rolling Entry,
Melting Entry, Workday Closing Entry, Sales Invoice). Sections with no
backing doctype yet (Quality, Maintenance, Energy, Safety, some gauges,
Gross Margin) live in steel_dashboard_demo_data.py and are merged in at the
end of get_dashboard_data() - replace those one at a time as real modules land.
"""

import frappe
from frappe.utils import flt, cint, getdate, add_days

from ittehadsteels.ittehadsteels.page.steel_dashboard import steel_dashboard_demo_data as demo


# --------------------------------------------------------------- utilities

def _company_logo():
	"""File URL of the default company's logo, or "" if none is set - the
	sidebar brand area shows nothing (not a placeholder icon) when this is
	empty, see steel_dashboard.js::render_data()."""
	company = frappe.defaults.get_global_default("company")
	return (frappe.db.get_value("Company", company, "company_logo") if company else None) or ""


def _prev_period(from_date, to_date):
	"""Return the immediately preceding period of the same length, used for
	every 'vs Last Week' comparison on the dashboard."""
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

def _production_mt(from_date, to_date):
	total = frappe.db.sql(
		"""
		select sum(total_finish_qty)
		from `tabRolling Entry`
		where docstatus = 1 and date between %s and %s
		""",
		(from_date, to_date),
	)[0][0]
	return flt(total) / 1000.0


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


def get_kpis(from_date, to_date, prev_from, prev_to):
	"""Ordered, self-describing list of KPI cards - the dashboard's top row
	renders however many of these come back, with whatever label/icon/color
	each one carries. To add a KPI card: add one entry here (`icon`/`color`
	must match a name ittehad_dashboard.icon()/the CSS palette knows about) -
	the front end needs no changes, see steel_dashboard.js::render_kpis()."""
	production_mt, prev_production_mt = _production_mt(from_date, to_date), _production_mt(prev_from, prev_to)
	heats, prev_heats = _heats(from_date, to_date), _heats(prev_from, prev_to)
	sales_qty, revenue = _sales(from_date, to_date)
	prev_sales_qty, prev_revenue = _sales(prev_from, prev_to)
	gross_margin = demo.get_gross_margin()

	return [
		{
			"key": "production_mt",
			"label": "Total Production",
			"icon": "coil",
			"color": "blue",
			"unit": "MT",
			"precision": 1,
			"value": round(production_mt, 1),
			"delta": _delta_pct(production_mt, prev_production_mt),
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
			"unit": "MT",
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
	]


# --------------------------------------------------------- live: charts

def get_production_trend(from_date, to_date, prev_from, prev_to):
	def _daily(f, t):
		rows = frappe.db.sql(
			"""
			select date, sum(total_finish_qty)
			from `tabRolling Entry`
			where docstatus = 1 and date between %s and %s
			group by date
			""",
			(f, t),
		)
		return {str(r[0]): flt(r[1]) / 1000.0 for r in rows}

	this_map, prev_map = _daily(from_date, to_date), _daily(prev_from, prev_to)

	days = (getdate(to_date) - getdate(from_date)).days + 1
	labels, this_week, last_week = [], [], []
	for i in range(days):
		d, pd = add_days(from_date, i), add_days(prev_from, i)
		labels.append(getdate(d).strftime("%a"))
		this_week.append(round(this_map.get(str(getdate(d)), 0), 2))
		last_week.append(round(prev_map.get(str(getdate(pd)), 0), 2))
	return {"labels": labels, "this_week": this_week, "last_week": last_week}


def get_production_by_product(from_date, to_date):
	rows = frappe.db.sql(
		"""
		select coalesce(i.item_group, 'Others') item_group, sum(fi.qty_kgs) qty
		from `tabFinish Items` fi
		inner join `tabRolling Entry` re on re.name = fi.parent
		left join `tabItem` i on i.name = fi.item_code
		where re.docstatus = 1 and re.date between %s and %s
		group by item_group
		order by qty desc
		""",
		(from_date, to_date),
	)
	total = sum(flt(r[1]) for r in rows) or 1
	return [
		{"label": r[0], "qty_mt": round(flt(r[1]) / 1000.0, 2), "pct": round(flt(r[1]) / total * 100, 1)}
		for r in rows
	]


def get_sales_by_product(from_date, to_date):
	rows = frappe.db.sql(
		"""
		select coalesce(sii.item_group, 'Others') item_group, sum(sii.qty) qty
		from `tabSales Invoice Item` sii
		inner join `tabSales Invoice` si on si.name = sii.parent
		where si.docstatus = 1 and si.posting_date between %s and %s
		group by item_group
		order by qty desc
		""",
		(from_date, to_date),
	)
	return [{"label": r[0], "qty": round(flt(r[1]), 1)} for r in rows]


# --------------------------------------------------------- live: tables

def get_top_raw_materials(from_date, to_date, prev_from, prev_to, limit=5):
	def _consumption(f, t):
		rows = frappe.db.sql(
			"""
			select mrm.item_name, sum(mrm.qty_kg)
			from `tabMelting Raw Material` mrm
			inner join `tabMelting Entry` me on me.name = mrm.parent
			where me.docstatus = 1 and me.posting_date between %s and %s
			group by mrm.item_name
			""",
			(f, t),
		)
		return {r[0]: flt(r[1]) for r in rows}

	this_map, prev_map = _consumption(from_date, to_date), _consumption(prev_from, prev_to)
	items = sorted(this_map.items(), key=lambda x: x[1], reverse=True)[:limit]
	return [
		{"material": name, "consumed_kg": round(qty, 1), "delta_pct": _delta_pct(qty, prev_map.get(name, 0))}
		for name, qty in items
	]


# ------------------------------------------------------- live: gauges

def get_gauges(from_date, to_date):
	"""Ordered, self-describing list of efficiency gauges - same "frontend
	renders however many come back" approach as get_kpis(). To add a gauge:
	add one entry here (and to steel_dashboard_demo_data.get_efficiency_gauges()
	if it isn't backed by a real query yet)."""
	rolling_mill_yield = frappe.db.sql(
		"""
		select avg(yield_percent)
		from `tabWorkday Closing Entry`
		where docstatus = 1 and from_date between %s and %s
		""",
		(from_date, to_date),
	)[0][0]

	demo_gauges = demo.get_efficiency_gauges()
	return [
		{"key": "capacity_utilization", "label": "Capacity Utilization", **demo_gauges["capacity_utilization"]},
		{"key": "conversion_yield", "label": "Conversion Yield", **demo_gauges["conversion_yield"]},
		{"key": "rolling_mill_yield", "label": "Rolling Mill Yield", "value": flt(rolling_mill_yield, 1)},
		{"key": "oee", "label": "OEE", **demo_gauges["oee"]},
	]


# ------------------------------------------------------ live: kv panels

def get_kv_panels():
	"""Ordered, self-describing list of label/value panels - same "frontend
	renders however many come back, with whatever title each one carries"
	approach as get_kpis()/get_gauges(). Quality/Maintenance/Energy/Inventory
	have no backing doctype yet (see steel_dashboard_demo_data.py); Safety is
	its own widget (shield + status), not part of this generic list, so it
	stays in the `demo` bucket of get_dashboard_data()."""
	quality = demo.get_quality()
	inventory = demo.get_inventory()
	maintenance = demo.get_maintenance()
	energy = demo.get_energy()

	return [
		{
			"key": "quality",
			"title": "Quality (This Week)",
			"is_demo": 1,
			"rows": [
				["First Pass Yield", f"{quality['first_pass_yield']}%"],
				["Rejection Rate", f"{quality['rejection_rate']}%"],
				["Customer Complaints", quality["customer_complaints"]],
				["Inspection Pass Rate", f"{quality['inspection_pass_rate']}%"],
			],
		},
		{
			"key": "inventory",
			"title": "Inventory (MT)",
			"is_demo": 1,
			"rows": [
				["Raw Materials", f"{inventory['raw_materials']:,}"],
				["Work In Process", f"{inventory['work_in_process']:,}"],
				["Finished Goods", f"{inventory['finished_goods']:,}"],
				["Total Inventory", f"{inventory['total']:,}"],
			],
		},
		{
			"key": "maintenance",
			"title": "Maintenance",
			"is_demo": 1,
			"rows": [
				["Planned Maintenance", f"{maintenance['planned_maintenance']}%"],
				["Breakdown (hrs)", maintenance["breakdown_hrs"]],
				["MTBF (hrs)", maintenance["mtbf"]],
				["MTTR (hrs)", maintenance["mttr"]],
			],
		},
		{
			"key": "energy",
			"title": "Energy (This Week)",
			"is_demo": 1,
			"rows": [
				["Specific Energy Consumption", f"{energy['specific_energy_kwh_mt']} kWh/MT"],
				["Total Energy Cost", f"PKR {energy['total_energy_cost_m']}M"],
				["Energy Efficiency", f"{energy['energy_efficiency']} MT/MWh"],
			],
		},
	]


# --------------------------------------------------------------- endpoint

@frappe.whitelist()
def get_dashboard_data(from_date, to_date):
	prev_from, prev_to = _prev_period(from_date, to_date)

	return {
		"company_logo": _company_logo(),
		"kpi": get_kpis(from_date, to_date, prev_from, prev_to),
		"production_trend": get_production_trend(from_date, to_date, prev_from, prev_to),
		"production_by_product": get_production_by_product(from_date, to_date),
		"sales_by_product": get_sales_by_product(from_date, to_date),
		"top_raw_materials": get_top_raw_materials(from_date, to_date, prev_from, prev_to),
		"gauges": get_gauges(from_date, to_date),
		"kv_panels": get_kv_panels(),
		"demo": {
			"safety": demo.get_safety(),
		},
	}
