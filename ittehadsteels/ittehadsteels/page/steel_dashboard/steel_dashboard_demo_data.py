"""
Placeholder data for dashboard sections that have no backing doctype yet
(Quality, Maintenance, and Gross Margin - Safety moved off this file once
Safety Incident landed, see steel_dashboard.py::get_safety()).

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


def get_maintenance():
	return {
		"planned_maintenance": 92,
		"breakdown_hrs": 16.5,
		"mtbf": 128,
		"mttr": 2.6,
	}


def get_gross_margin():
	# no cost/COGS doctype yet to compute a real margin
	return {"value": 14.8, "delta": 1.9, "is_demo": 1}
