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


# ------------------------------------------------------------ live: inventory

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

def get_kv_panels(from_date, to_date):
	"""Ordered, self-describing list of label/value panels - same "frontend
	renders however many come back, with whatever title each one carries"
	approach as get_kpis()/get_gauges(). Quality/Maintenance have no backing
	doctype yet (see steel_dashboard_demo_data.py); both Energy panels are
	live now (see get_power_consumption()/get_gas_consumption()), same as
	Inventory's demo MT breakdown was already replaced by the real Inventory
	(Warehouse Wise) table (get_inventory_by_warehouse()) everywhere it used
	to appear. Safety is its own widget (shield + status), not part of this
	generic list, so it stays in the `demo` bucket of get_dashboard_data()."""
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
				["First Pass Yield", f"{quality['first_pass_yield']}%"],
				["Rejection Rate", f"{quality['rejection_rate']}%"],
				["Customer Complaints", quality["customer_complaints"]],
				["Inspection Pass Rate", f"{quality['inspection_pass_rate']}%"],
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
		"inventory_by_warehouse": get_inventory_by_warehouse(),
		"gauges": get_gauges(from_date, to_date),
		"kv_panels": get_kv_panels(from_date, to_date),
		"demo": {
			"safety": demo.get_safety(),
		},
	}
