"""
Placeholder data for dashboard sections that have no backing doctype yet
(Quality, Maintenance, Energy, Safety, and a few efficiency gauges).

This is the ONLY place in the dashboard that returns made-up numbers.
When a real module/doctype is added for one of these, replace the matching
function below with a real query (see steel_dashboard.py for the query style) -
steel_dashboard.py and steel_dashboard.js need no other changes.
"""


def get_quality():
	return {
		"first_pass_yield": 95.3,
		"rejection_rate": 2.15,
		"customer_complaints": 3,
		"inspection_pass_rate": 97.6,
	}


def get_inventory():
	# TODO: once warehouse/item-group conventions are finalised, replace with
	# a `Bin` aggregate grouped by item group (Raw Material / WIP / Finished Goods).
	return {
		"raw_materials": 18650,
		"work_in_process": 3245,
		"finished_goods": 7980,
		"total": 29875,
	}


def get_maintenance():
	return {
		"planned_maintenance": 92,
		"breakdown_hrs": 16.5,
		"mtbf": 128,
		"mttr": 2.6,
	}


def get_energy():
	return {
		"specific_energy_kwh_mt": 595,
		"total_energy_cost_m": 18.6,
		"energy_efficiency": 1.68,
	}


def get_safety():
	return {
		"man_hours": 24560,
		"ltifr": 0.41,
		"trir": 0.82,
		"observations": 46,
		"status": "SAFE",
	}


def get_efficiency_gauges():
	# capacity_utilization / conversion_yield / OEE need machine-hours and
	# planned-vs-actual output data that isn't captured yet; rolling_mill_yield
	# is already live (see dashboard.py::_rolling_mill_yield).
	return {
		"capacity_utilization": {"value": 78, "is_demo": 1},
		"conversion_yield": {"value": 92, "is_demo": 1},
		"oee": {"value": 72, "is_demo": 1},
	}


def get_gross_margin():
	# no cost/COGS doctype yet to compute a real margin
	return {"value": 14.8, "delta": 1.9, "is_demo": 1}
