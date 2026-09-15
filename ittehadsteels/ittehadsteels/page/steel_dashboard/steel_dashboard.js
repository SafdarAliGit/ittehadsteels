// Ittehad Steels KPI Dashboard - page controller.
// Icons live in public/js/ittehad_dashboard/icons.js, chart/gauge/table
// rendering lives in public/js/ittehad_dashboard/widgets.js (both are
// reusable and loaded via the `page_js` hook in hooks.py). This file only
// wires those pieces to the data returned by steel_dashboard.py.
//
// The page is a single-page app: every sidebar item shows/hides an in-page
// <section> - nothing ever navigates away from /app/steel-dashboard.
// Duplicate widgets (e.g. the Quality panel shown on both the Dashboard
// overview and the Quality section) share the same CSS class/data-attribute,
// so a single render_data() pass fills every copy at once (jQuery setters
// like .html()/.text() apply to every matched element).
//
// Most of this dashboard is data-driven rather than hardcoded: KPI cards,
// efficiency gauges, and the Quality/Inventory/Maintenance/Energy panels are
// all ordered, self-describing lists returned by steel_dashboard.py
// (get_kpis()/get_gauges()/get_kv_panels()) - this file just renders however
// many of each come back, with whatever label/icon/color/title they carry.
// Add, remove, or reorder one of those on the backend and the front end
// needs no change. *_ROWS (below) only controls which subset of a list a
// given section's compact row shows; "dashboard" always shows the full list
// regardless of its length. (Production Trend/by Product, Sales by Product,
// and Top Raw Material Consumption were already this way - real doctypes
// produce a variable-length list and the widgets just render it.)
//
// What's still fixed in code: the sidebar menu itself, which row/grid a
// panel appears in, and one-off widgets like the Safety card (shield +
// status, not a plain label/value list). To add a new sidebar section: add
// one entry to NAV_ITEMS and one entry to section_layout() (built from the
// *_card_html() blocks below it).

// Maps CSS color names steel_dashboard.py sends to the actual CSS variables.
const KPI_COLORS = { blue: "var(--blue)", green: "var(--green)", orange: "var(--orange)", purple: "var(--purple)", gold: "var(--gold)" };

// Which KPI keys (by steel_dashboard.py's `key`) each section's compact KPI
// row shows, in that order. `null` = show the full list the backend
// returned, as-is - dashboard used to rely on this, but get_kpis() now also
// carries the Sales section's own four cards (sales_order_value onward), so
// "dashboard" lists its original set explicitly instead of picking those up.
const KPI_ROWS = {
	dashboard: [
		"raw_material_consumption_mt",
		"billet_production_mt",
		"bar_production_mt",
		"heats",
		"sales_mt",
		"revenue_m",
		"gross_margin_pct",
	],
	// The full production funnel (input -> billet -> bar -> heats) in one
	// row - all four are already computed for the Dashboard section's own
	// KPI row, just not previously surfaced here.
	production: ["raw_material_consumption_mt", "billet_production_mt", "bar_production_mt", "heats"],
	// Mirrors /app/dashboard-view/Selling's four number cards (Annual Sales,
	// Sales Orders to Deliver, Sales Orders to Bill, Active Customers)
	// alongside this dashboard's own Sales/Revenue KPIs.
	sales: ["sales_mt", "revenue_m", "sales_order_value", "sales_orders_to_deliver", "sales_orders_to_bill", "active_customers"],
	// Mirrors /app/dashboard-view/Accounts' four number cards exactly: Total
	// Outgoing/Incoming Bills, Total Incoming/Outgoing Payment.
	finance: ["total_outgoing_bills", "total_incoming_bills", "total_incoming_payment", "total_outgoing_payment"],
	// Mirrors /app/dashboard-view/Stock's three number cards exactly: Total
	// Active Items, Total Warehouses, Total Stock Value.
	inventory: ["total_active_items", "total_warehouses", "total_stock_value"],
	// Power and Gas each as a total (the actual spend) plus a per-Ton
	// efficiency ratio - all four already computed by
	// _power_units_and_output_mt()/_gas_consumption_and_output_mt() in
	// steel_dashboard.py, same figures the Dashboard section's compact
	// Energy (Power)/Energy (Gas) kv panels already show, just as proper KPI
	// cards with a vs-last-period delta.
	energy: ["total_power_units", "power_consumption_kwh_per_ton", "total_gas_cost_m", "gas_cost_per_ton"],
};

// Same idea as KPI_ROWS, but for the label/value panels get_kv_panels()
// returns (Quality/Maintenance/Energy (Power)/Energy (Gas)). Quality and
// Maintenance still have no backing doctype. The dedicated Energy section no
// longer uses these - see KPI_ROWS.energy above and
// power_consumption_trend_card_html()/gas_consumption_trend_card_html() for
// its own KPI cards and trend charts; "dashboard" keeps the compact
// Energy (Power)/Energy (Gas) panels alongside Quality/Maintenance's.
const KV_PANEL_ROWS = {
	dashboard: ["energy_power", "energy_gas"],
	quality: ["quality"],
	maintenance: ["maintenance"],
};

// Reports section - one button-card per report type. `kpi_row`, when set,
// pulls that section's own KPI_ROWS grouping into the report's metric rows
// (see build_report()) - the report mirrors whatever's already on that
// section's own dashboard page, not a hand-picked subset kept separately.
// `columns` names the report's own two columns - meaningful/related to what
// that report actually lists (Finance's real Chart of Accounts gets
// "Particulars"/"Amount (PKR)", the standard financial-statement term),
// not a generic "Metric"/"Value" reused everywhere.
const REPORTS = [
	{ key: "production", label: "Production", icon: "factory", kpi_row: "production", columns: ["Production Metric", "Value"] },
	{ key: "sales", label: "Sales", icon: "cart", kpi_row: "sales", columns: ["Sales Metric", "Value"] },
	{ key: "inventory", label: "Inventory", icon: "box", kpi_row: "inventory", columns: ["Inventory Metric", "Value"] },
	{ key: "finance", label: "Finance", icon: "dollar", kpi_row: "finance", columns: ["Particulars", "Amount (PKR)"] },
	{ key: "energy", label: "Energy", icon: "bolt", kpi_row: "energy", columns: ["Energy Metric", "Value"] },
	{ key: "quality", label: "Quality", icon: "check", columns: ["Quality Metric", "Value"] },
	{ key: "maintenance", label: "Maintenance", icon: "wrench", columns: ["Maintenance Metric", "Value"] },
	{ key: "safety", label: "Safety", icon: "shield", columns: ["Safety Metric", "Value"] },
];

const NAV_ITEMS = [
	{ key: "dashboard", label: "Dashboard", icon: "grid", title: "STEEL MANUFACTURING KPI DASHBOARD" },
	{ key: "production", label: "Production", icon: "factory", title: "PRODUCTION OVERVIEW" },
	{ key: "sales", label: "Sales", icon: "cart", title: "SALES OVERVIEW" },
	{ key: "inventory", label: "Inventory", icon: "box", title: "INVENTORY OVERVIEW" },
	{ key: "quality", label: "Quality", icon: "check", title: "QUALITY OVERVIEW" },
	{ key: "maintenance", label: "Maintenance", icon: "wrench", title: "MAINTENANCE OVERVIEW" },
	{ key: "energy", label: "Energy", icon: "bolt", title: "ENERGY OVERVIEW" },
	{ key: "finance", label: "Finance", icon: "dollar", title: "FINANCE OVERVIEW" },
	{ key: "safety", label: "Safety", icon: "shield", title: "SAFETY OVERVIEW" },
	{ key: "reports", label: "Reports", icon: "doc", title: "REPORTS" },
	{ key: "settings", label: "Settings", icon: "gear", title: "SETTINGS" },
];

const DEFAULT_SECTION = "dashboard";

frappe.pages["steel-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: "Steel Dashboard", single_column: true });

	// this page owns its own header/sidebar - hide the stock desk page head
	$(page.wrapper).find(".page-head").hide();
	$(page.wrapper).addClass("isd-page-wrapper");

	new IttehadDashboard(page);
};

class IttehadDashboard {
	constructor(page) {
		this.page = page;
		this.$container = $(page.main);
		this.state = {
			section: DEFAULT_SECTION,
			from_date: frappe.datetime.week_start(),
			to_date: frappe.datetime.week_end(),
			report: null,
			report_filter: "",
		};
		this.render_shell();
		this.bind_events();
		this.fetch_and_render();
	}

	// ------------------------------------------------------- reusable cards
	// Every helper returns a self-contained "isd-card" block. The same block
	// can be dropped into more than one section - it's plain markup, so
	// render_data() (which selects by class, not by position) fills every
	// copy on the page in one pass.
	// Renders one KPI card already filled with its value - unlike the other
	// *_card_html() helpers, this needs live data so it's only ever called
	// from render_kpi_rows() (after fetch_and_render() resolves), never from
	// section_layout() at shell-build time.
	kpi_card_html(k) {
		const color = KPI_COLORS[k.color] || k.color;
		const value = frappe.format(k.value, { fieldtype: "Float", precision: k.precision }, { only_value: 1 });
		return `
			<div class="isd-card isd-kpi">
				<div class="isd-kpi-top">
					<div class="isd-kpi-icon" style="color:${color}">${ittehad_dashboard.icon(k.icon)}</div>
					<div class="isd-kpi-text">
						<div class="isd-card-title">${k.label}</div>
						<div class="isd-kpi-value">${value}<small>${k.unit}</small></div>
					</div>
				</div>
				<div class="isd-kpi-footer">${ittehad_dashboard.widgets.delta_html(k.delta)} vs Last Period</div>
			</div>
		`;
	}

	// The bar chart lives in the left 70%; the right 30% is a compact line
	// chart (This <period> solid, Last <period> dashed) of the same data -
	// see widgets.sparkline() / render_trend_sparkline(). `period` defaults
	// to "Week" for the Production Trend charts below, which really are
	// always a 7-day bucket; callers whose bucket width varies with the
	// dashboard's date range (daily for a short range, monthly for a wide
	// one - see get_sales_order_trend()) or is always monthly (Finance's
	// trend cards) pass "Period" instead, since "This Week"/"Last Week"
	// would misdescribe a chart that's actually showing months.
	trend_card_html(title, target_cls, spark_cls, period = "Week") {
		return `
			<div class="isd-card">
				<div class="isd-card-title">${title}</div>
				<div class="isd-trend-split">
					<div class="isd-trend-main">
						<div class="isd-legend">
							<span><span class="dot" style="background:var(--blue)"></span>This ${period}</span>
							<span><span class="dash"></span>Last ${period}</span>
						</div>
						<div class="isd-bars ${target_cls}"></div>
					</div>
					<div class="isd-trend-side ${spark_cls}"></div>
				</div>
			</div>
		`;
	}

	furnace_trend_card_html() {
		return this.trend_card_html(
			"Production Trend (Furnace) - Bar Production (Ton)",
			"isd-trend-furnace",
			"isd-trend-spark-furnace"
		);
	}

	deformed_bar_trend_card_html() {
		return this.trend_card_html(
			"Production Trend (Deformed Bar) - Bar Production (Ton)",
			"isd-trend-deformed-bar",
			"isd-trend-spark-deformed-bar"
		);
	}

	donut_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Production By Product Group (Ton)</div>
				<div class="isd-donut-wrap isd-donut-target"></div>
			</div>
		`;
	}

	gauges_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Production Efficiency</div>
				<div class="isd-gauges isd-gauges-target"></div>
			</div>
		`;
	}

	// Renders one label/value panel already filled with its rows - like
	// kpi_card_html(), this needs live data so it's only ever called from
	// render_kv_panels() (after fetch_and_render() resolves).
	kv_panel_card_html(p) {
		const rows = p.rows.map(([k, v]) => `<div class="kv"><span class="k">${k}</span><span class="v">${v}</span></div>`).join("");
		return `
			<div class="isd-card">
				<div class="isd-card-title">${p.title}${p.is_demo ? '<span class="isd-demo-tag">v1 demo</span>' : ""}</div>
				<div class="isd-kv-list">${rows}</div>
			</div>
		`;
	}

	warehouse_inventory_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Inventory (Warehouse Wise)</div>
				<table class="isd-table">
					<thead><tr><th>Warehouse</th><th>Stock Balance</th><th>Unit</th></tr></thead>
					<tbody class="isd-warehouse-inventory"></tbody>
				</table>
			</div>
		`;
	}

	// Inventory section - the Ittehad-styled equivalent of every widget on
	// /app/dashboard-view/Stock, named to match 1:1: "Warehouse wise Stock
	// Value" (this one, money - unlike warehouse_inventory_card_html()'s Ton
	// quantity table above), "Purchase Receipt Trends"/"Delivery Trends" and
	// "Oldest Items"/"Item Shortage Summary" below.
	warehouse_stock_value_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Warehouse wise Stock Value (PKR M)</div>
				<div class="isd-bars isd-warehouse-stock-value-chart"></div>
			</div>
		`;
	}

	purchase_receipt_trend_card_html() {
		return this.trend_card_html("Purchase Receipt Trends (PKR M)", "isd-trend-purchase-receipt", "isd-trend-spark-purchase-receipt", "Period");
	}

	delivery_trend_card_html() {
		return this.trend_card_html("Delivery Trends (PKR M)", "isd-trend-delivery", "isd-trend-spark-delivery", "Period");
	}

	// Days since each in-stock item's last Stock Ledger Entry, oldest first
	// (see get_oldest_items()) - hbars(), not a vertical bars() chart: item
	// names ("DEFROMED STEEL BARS G-60 25MM (1")") are far too long for a
	// ~32-60px bar column's nowrap label, which overflows into the next
	// column and reads as merged/garbled text. hbars()' fixed-width,
	// ellipsis-truncated label column (already used for Top Customers/Sales
	// by Product) is built for exactly this.
	oldest_items_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Oldest Items (Days Since Last Movement)</div>
				<div class="isd-oldest-items-chart"></div>
			</div>
		`;
	}

	// Items short of their configured reorder level (see
	// get_item_shortage_summary()) - empty until Item Reorder is set up for
	// at least one item, same precedent as Budget Variance in Finance. hbars()
	// for the same long-item-name reason as Oldest Items above.
	item_shortage_summary_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Item Shortage Summary</div>
				<div class="isd-item-shortage-chart"></div>
			</div>
		`;
	}

	// Energy section - Power/Gas each get a KPI card pair (see KPI_ROWS.energy)
	// plus their own trend, same bars()+sparkline() split as the Production
	// Trend charts, drawn straight from Melting Entry's power_units/
	// gas_consumption (see get_power_consumption_trend()/
	// get_gas_consumption_trend()) rather than the compact kv-panel summary
	// the Dashboard section still uses. Daily for a short date range, monthly
	// for a wide one (see _adaptive_trend() in steel_dashboard.py) - "Period"
	// reads correctly either way.
	power_consumption_trend_card_html() {
		return this.trend_card_html("Power Consumption Trend (kWh)", "isd-trend-power", "isd-trend-spark-power", "Period");
	}

	gas_consumption_trend_card_html() {
		return this.trend_card_html("Gas Consumption Trend (PKR)", "isd-trend-gas", "isd-trend-spark-gas", "Period");
	}

	// Item name + qty/unit as a horizontal bar list on top, two pies below it
	// breaking the same items down by qty and by revenue (with % in each
	// pie's legend, see widgets.donut()).
	// Two pie circles (Qty, Revenue) but ONE shared legend below them - each
	// item listed once with both percentages together, instead of the same
	// item list repeated twice (see render_sales_pie_legend()).
	sales_by_product_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Sales by Product</div>
				<div class="isd-sales-by-product-chart"></div>
				<div class="isd-sales-pie-row">
					<div>
						<div class="isd-sales-pie-title">By Qty</div>
						<div class="isd-donut-wrap isd-sales-by-product-pie-qty"></div>
					</div>
					<div>
						<div class="isd-sales-pie-title">By Revenue</div>
						<div class="isd-donut-wrap isd-sales-by-product-pie-revenue"></div>
					</div>
				</div>
				<div class="isd-donut-legend isd-sales-pie-legend"></div>
			</div>
		`;
	}

	// Sales section - the Ittehad-styled equivalent of every widget on
	// /app/dashboard-view/Selling, named to match 1:1 (see section_layout()
	// for the same Full/Half/Half ordering that page uses): "Sales Order
	// Trends" (this one, bar+sparkline split like Production Trend), "Top
	// Customers" and "Sales Order Analysis" below.
	sales_order_trend_card_html() {
		// Daily for a short date range, monthly for a wide one (see
		// get_sales_order_trend()) - "Period" reads correctly either way,
		// unlike a hardcoded "Week" would once the range switches to months.
		return this.trend_card_html("Sales Order Trends (PKR M)", "isd-trend-sales-order", "isd-trend-spark-sales-order", "Period");
	}

	// Sales Order Analysis - Billed vs Amount to Bill split for open Sales
	// Orders, as a donut (same chart type and two categories Selling's own
	// "Sales Order Analysis" chart uses - see get_sales_order_billing_split()).
	sales_order_status_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Sales Order Analysis</div>
				<div class="isd-donut-wrap isd-sales-order-status-target"></div>
			</div>
		`;
	}

	// Top Customers - reuses the same horizontal bar list widget as Sales by
	// Product's own item breakdown.
	top_customers_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Top Customers</div>
				<div class="isd-top-customers-chart"></div>
			</div>
		`;
	}

	// Finance section - the Ittehad-styled equivalent of every widget on
	// /app/dashboard-view/Accounts, named to match 1:1: "Profit and Loss"
	// (this one), "Incoming Bills (Purchase Invoice)"/"Outgoing Bills (Sales
	// Invoice)", "Accounts Receivable/Payable Ageing", "Budget Variance" and
	// "Bank Balance" below. Income/Expense/Profit stats up top (see
	// render_profit_and_loss()), a Profit trend (this vs last period) below
	// them using the same trend_card_html() bars()+sparkline() split as
	// every other trend chart on this dashboard.
	profit_and_loss_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Profit and Loss</div>
				<div class="isd-pnl-summary">
					<div class="isd-pnl-stat"><span class="isd-pnl-label">Total Income</span><span class="isd-pnl-value isd-pnl-income">-</span></div>
					<div class="isd-pnl-op">&minus;</div>
					<div class="isd-pnl-stat"><span class="isd-pnl-label">Total Expense</span><span class="isd-pnl-value isd-pnl-expense">-</span></div>
					<div class="isd-pnl-op">=</div>
					<div class="isd-pnl-stat"><span class="isd-pnl-label">Profit</span><span class="isd-pnl-value isd-pnl-profit">-</span></div>
				</div>
				<div class="isd-trend-split isd-pnl-trend">
					<div class="isd-trend-main">
						<div class="isd-legend">
							<span><span class="dot" style="background:var(--blue)"></span>This Period</span>
							<span><span class="dash"></span>Last Period</span>
						</div>
						<div class="isd-bars isd-trend-pnl"></div>
					</div>
					<div class="isd-trend-side isd-trend-spark-pnl"></div>
				</div>
			</div>
		`;
	}

	// Finance's trend cards are always month-bucketed (see
	// get_incoming_bills_trend()/get_outgoing_bills_trend()/
	// get_profit_and_loss_trend()), never a 7-day window - "Period" instead
	// of the default "Week" so the legend doesn't claim something the chart
	// isn't showing.
	incoming_bills_card_html() {
		return this.trend_card_html("Incoming Bills (Purchase Invoice, PKR M)", "isd-trend-incoming-bills", "isd-trend-spark-incoming-bills", "Period");
	}

	outgoing_bills_card_html() {
		return this.trend_card_html("Outgoing Bills (Sales Invoice, PKR M)", "isd-trend-outgoing-bills", "isd-trend-spark-outgoing-bills", "Period");
	}

	// Ageing bar list (see widgets.ageing()), not a donut - the 5 buckets are
	// inherently ordered (0-30 closer to due, 121-Above most overdue), which
	// a donut's arbitrary slice order obscures; bars keep that order and read
	// as a severity ramp (green -> red), the way real ageing reports do. A
	// "Total Outstanding" figure up top gives the single number a reader
	// actually wants before the breakdown.
	ar_ageing_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Accounts Receivable Ageing</div>
				<div class="isd-ageing-total">Total Outstanding <b class="isd-ar-ageing-total">-</b></div>
				<div class="isd-ageing-chart isd-ar-ageing-target"></div>
			</div>
		`;
	}

	ap_ageing_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Accounts Payable Ageing</div>
				<div class="isd-ageing-total">Total Outstanding <b class="isd-ap-ageing-total">-</b></div>
				<div class="isd-ageing-chart isd-ap-ageing-target"></div>
			</div>
		`;
	}

	// Budgeted vs Actual (GL Entry) spend per Budget Account - a plain table
	// like Inventory (Warehouse Wise) rather than a bar/donut, since
	// budget/actual/variance are three numbers per account best read side by
	// side, not areas to compare visually. Empty (see render_budget_variance())
	// until a Budget doc exists, same as the reference chart with none set up.
	budget_variance_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Budget Variance</div>
				<table class="isd-table">
					<thead><tr><th>Account</th><th>Budgeted</th><th>Actual</th><th>Variance</th></tr></thead>
					<tbody class="isd-budget-variance"></tbody>
				</table>
			</div>
		`;
	}

	bank_balance_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Bank Balance</div>
				<div class="isd-bank-balance-chart"></div>
			</div>
		`;
	}

	// Live now (data.safety, see render_safety()) - actuals are counted from
	// submitted Safety Incident records against Steel Dashboard Settings'
	// Man-Hours per Day (steel_dashboard.py::get_safety()), and the shield
	// color/status text reflect the real LTIFR/TRIR/Observations-vs-target
	// calculation, not a hardcoded green "SAFE". "+ Log Incident" opens a
	// new Safety Incident - the record this whole card is calculated from.
	safety_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Safety (This Week)</div>
				<div class="isd-kv-list isd-safety" style="margin-bottom:10px"></div>
				<svg class="isd-safety-shield" viewBox="0 0 24 24" fill="none"><path class="isd-safety-shield-fill" d="M12 2l8 3v6c0 5-3.4 8.7-8 11-4.6-2.3-8-6-8-11V5l8-3z" fill="var(--green)"/><path d="M8 12l2.5 2.5L16 9" stroke="#0b1220" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
				<div class="isd-safety-status"><div class="isd-safety-status-text ok">SAFE</div><small class="isd-safety-status-caption">Keep up the good work!</small></div>
				<a class="isd-safety-log-link" href="/app/safety-incident/new" target="_blank" rel="noopener">+ Log Incident</a>
			</div>
		`;
	}

	placeholder_card_html(text) {
		return `<div class="isd-card"><div class="isd-empty" style="min-height:80px">${text}</div></div>`;
	}

	// Reports section - one button-card per REPORTS entry (click ->
	// select_report()); the filter/actions bar and table below stay hidden
	// (see reports_content_card_html()) until a report is picked.
	report_type_card_html(rep) {
		return `
			<div class="isd-report-card" data-key="${rep.key}">
				<div class="isd-report-card-icon">${ittehad_dashboard.icon(rep.icon)}</div>
				<div class="isd-report-card-label">${rep.label}</div>
			</div>
		`;
	}

	reports_cards_row_html() {
		return `<div class="isd-report-cards">${REPORTS.map((r) => this.report_type_card_html(r)).join("")}</div>`;
	}

	// Header (Company logo/name + report title + date range/generated-on,
	// same identity block export_report_pdf()/print_report() put on the
	// PDF/print output - the on-screen version matches what you'd get from
	// either), a filter bar (a real, working row-search since every row is
	// already loaded client-side), and iconic Print/Export Excel/Export PDF
	// actions, all scoped to whichever report is currently selected (see
	// select_report()/render_report()).
	reports_content_card_html() {
		return `
			<div class="isd-card isd-report-panel" hidden>
				<div class="isd-report-toolbar">
					<div class="isd-report-header">
						<img class="isd-report-logo isd-hidden" src="" alt="" />
						<div>
							<div class="isd-report-company"></div>
							<div class="isd-card-title isd-report-title">Report</div>
							<div class="isd-report-range"></div>
						</div>
					</div>
					<div class="isd-report-actions">
						<input type="text" class="isd-report-search" placeholder="Filter rows..." />
						<button class="isd-report-print-btn" type="button" title="Print">${ittehad_dashboard.icon("print")}<span>Print</span></button>
						<button class="isd-report-excel-btn" type="button" title="Export Excel">${ittehad_dashboard.icon("excel")}<span>Excel</span></button>
						<button class="isd-report-pdf-btn" type="button" title="Export PDF">${ittehad_dashboard.icon("pdf")}<span>PDF</span></button>
					</div>
				</div>
				<table class="isd-table">
					<thead><tr class="isd-report-thead"></tr></thead>
					<tbody class="isd-report-table-body"></tbody>
				</table>
			</div>
		`;
	}

	// Settings section - an editable form for Steel Dashboard Settings (see
	// get_settings_summary()/on_save_settings()), the Single doctype backing
	// Capacity Utilization/OEE (Production's gauges) and every Quality/
	// Maintenance/Safety target line. Edits save through update_settings()
	// and go through the same Document.save() a direct edit on the real
	// doctype form would - that form (linked below) is still there for
	// version history/bulk edit, this is just the everyday path.
	settings_intro_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Dashboard Settings</div>
				<div class="isd-settings-intro">
					These values drive Production's Capacity Utilization/OEE gauges and the target line shown next to every Quality, Maintenance, and Safety actual elsewhere on this dashboard. Edit them below and Save, or use the full form for version history.
				</div>
				<div class="isd-settings-save-row">
					<button class="isd-settings-save-btn" type="button">Save Settings</button>
					<a class="isd-settings-edit-link" href="/app/steel-dashboard-settings" target="_blank" rel="noopener">
						Open Full Settings Form &rarr;
					</a>
				</div>
			</div>
		`;
	}

	// -------------------------------------------------------------- shell
	render_shell() {
		this.$container.html(`
			<div class="isd-dash">
				<aside class="isd-sidebar">
					<div class="isd-brand">
						<div class="isd-logo isd-company-logo"></div>
						<div class="isd-brand-text">ITTEHAD STEELS<small>MANUFACTURING</small></div>
					</div>
					<ul class="isd-nav">${this.nav_html()}</ul>
					<div class="isd-plant-card">
						<div class="isd-pc-title">Plant Overview</div>
						<div class="isd-plant-row"><span>Plant</span><span>Main Plant</span></div>
						<div class="isd-plant-row"><span>Shift</span><span class="isd-shift">-</span></div>
						<div class="isd-plant-row"><span>Date</span><span class="isd-date">-</span></div>
						<div class="isd-plant-row"><span>Time</span><span class="isd-time">-</span></div>
					</div>
					<div class="isd-user">
						<div class="avatar">${(frappe.session.user_fullname || "U")[0]}</div>
						<div>
							<div style="font-weight:600">${frappe.session.user_fullname || frappe.session.user}</div>
							<div style="color:var(--muted); font-size:11px">${frappe.user.has_role("System Manager") ? "Administrator" : "User"}</div>
						</div>
					</div>
				</aside>
				<div class="isd-main">
					<div class="isd-topbar">
						<div class="isd-title"><span class="isd-title-logo isd-company-logo"></span> <span class="isd-title-text"></span></div>
						<div class="isd-filters">
							<select class="isd-plant-filter" disabled title="No Plant master configured yet"><option>Plant: All</option></select>
							<select class="isd-dept-filter" disabled title="No Department master configured yet"><option>Department: All</option></select>
							<input type="text" class="isd-from-date" readonly value="${this.format_date_display(this.state.from_date)}">
							<span style="color:var(--muted)">-</span>
							<input type="text" class="isd-to-date" readonly value="${this.format_date_display(this.state.to_date)}">
							<button class="isd-export-btn">${ittehad_dashboard.icon("download")} Export</button>
						</div>
					</div>
					<div class="isd-content">${this.sections_html()}</div>
					<div class="isd-footnote">MT: Metric Ton  |  MTBF: Mean Time Between Failures  |  MTTR: Mean Time To Repair  |  OEE: Overall Equipment Effectiveness  |  LTIFR: Lost Time Injury Frequency Rate  |  TRIR: Total Recordable Injury Rate</div>
				</div>
			</div>
		`);

		this.set_section(this.state.section);
		this.update_plant_overview();
		this.init_date_pickers();
	}

	// dd/mm/yyyy display everywhere the date range is shown - moment.js is
	// always available in Desk, no extra dependency needed.
	format_date_display(iso_date) {
		return moment(iso_date).format("DD/MM/YYYY");
	}

	// Text inputs + the same air-datepicker widget Frappe's own Date control
	// uses (frappe/form/controls/date.js), but with an explicit dd/mm/yyyy
	// dateFormat instead of the site-wide default - a plain <input
	// type="date"> can't be forced into a custom display format, its
	// rendering is fixed by the browser/OS locale.
	init_date_pickers() {
		// language: "en" - forced, not left to inherit whatever the site/user
		// locale happens to be (air-datepicker shares that as global state,
		// so another Date field elsewhere on the site can otherwise leak a
		// non-English calendar into this one).
		const base_opts = { dateFormat: "dd/mm/yyyy", language: "en", autoClose: true, keyboardNav: false, todayButton: true };
		this.$container.find(".isd-from-date").datepicker({
			...base_opts,
			position: "bottom left",
			onSelect: (formatted, dates) => this.on_date_picked("from", dates),
		});
		// "bottom right" - the To field sits near the right edge of the
		// topbar; the default "bottom left" grows the calendar rightward off
		// the input and off the edge of the screen. Anchoring its right edge
		// to the input's right edge instead grows it back into the topbar.
		this.$container.find(".isd-to-date").datepicker({
			...base_opts,
			position: "bottom right",
			onSelect: (formatted, dates) => this.on_date_picked("to", dates),
		});
	}

	// Only the DEFAULT range is a fixed 7 days (this.state's initial value,
	// set in the constructor). Once loaded, from/to move independently - the
	// user is free to widen or narrow the window to whatever they need.
	on_date_picked(which, dates) {
		const picked = Array.isArray(dates) ? dates[0] : dates;
		if (!picked) return;
		const iso = moment(picked).format("YYYY-MM-DD");
		if (which === "from") {
			this.state.from_date = iso;
		} else {
			this.state.to_date = iso;
		}
		this.apply_date_range();
	}

	nav_html() {
		return NAV_ITEMS.map(
			(n) => `<li class="${n.key === this.state.section ? "active" : ""}" data-key="${n.key}">
				<a>${ittehad_dashboard.icon(n.icon)}<span>${n.label}</span></a>
			</li>`
		).join("");
	}

	// Declarative menu -> layout map: one entry per sidebar item, each a list
	// of rows, each row a css class + either a fixed set of cards, a
	// `kpi_row` name (KPI_ROWS), or a `kv_row` name (KV_PANEL_ROWS) - the
	// latter two are filled dynamically once data arrives, see
	// render_kpi_rows()/render_kv_panels(). To add a new menu section: add
	// one key here (and one entry in NAV_ITEMS) - nothing else in this file
	// changes. Fixed cards can be reused across sections (e.g. the Safety
	// card appears on both "dashboard" and "safety") since render_data()
	// fills every element matching a class, not just the first.
	section_layout() {
		return {
			dashboard: [
				{ cls: "kpis", kpi_row: "dashboard" },
				{ cls: "r2c", cards: [this.donut_card_html(), this.warehouse_inventory_card_html()], kv_row: "dashboard" },
				{ cls: "r2-trend", cards: [this.furnace_trend_card_html(), this.deformed_bar_trend_card_html()] },
				{ cls: "r1", cards: [this.sales_by_product_card_html()] },
			],
			production: [
				{ cls: "kpis-4", kpi_row: "production" },
				{ cls: "r2b", cards: [this.donut_card_html(), this.gauges_card_html()] },
				{ cls: "r2-trend", cards: [this.furnace_trend_card_html(), this.deformed_bar_trend_card_html()] },
			],
			// Every widget on /app/dashboard-view/Selling, in that page's own
			// order and Full/Half widths, rendered with this dashboard's own
			// card style: 6 number cards -> Sales Order Trends (Full) -> Top
			// Customers + Sales Order Analysis (Half each). Sales by Product
			// (the qty/revenue breakdown already on this dashboard) is kept
			// as an extra row after that - it isn't part of Selling's own
			// dashboard, but overlaps the same ground with more detail.
			sales: [
				{ cls: "kpis-3", kpi_row: "sales" },
				{ cls: "r1", cards: [this.sales_order_trend_card_html()] },
				{ cls: "r2b", cards: [this.top_customers_card_html(), this.sales_order_status_card_html()] },
				{ cls: "r1", cards: [this.sales_by_product_card_html()] },
			],
			// Every widget on /app/dashboard-view/Stock, in that page's own
			// order, rendered with this dashboard's own card style: 3 number
			// cards -> Warehouse wise Stock Value (Full) -> Purchase
			// Receipt/Delivery Trends (Half each) -> Oldest Items/Item
			// Shortage Summary (Half each). Inventory (Warehouse Wise) (the
			// Ton quantity table already on this dashboard) is kept as an
			// extra row after that - it isn't part of Stock's own dashboard,
			// but overlaps the same ground with a different unit.
			inventory: [
				{ cls: "kpis-3", kpi_row: "inventory" },
				{ cls: "r1", cards: [this.warehouse_stock_value_card_html()] },
				{ cls: "r2b", cards: [this.purchase_receipt_trend_card_html(), this.delivery_trend_card_html()] },
				{ cls: "r2b", cards: [this.oldest_items_card_html(), this.item_shortage_summary_card_html()] },
				{ cls: "r1", cards: [this.warehouse_inventory_card_html()] },
			],
			quality: [{ cls: "r1", kv_row: "quality" }],
			maintenance: [{ cls: "r1", kv_row: "maintenance" }],
			energy: [
				{ cls: "kpis-4", kpi_row: "energy" },
				{ cls: "r2b", cards: [this.power_consumption_trend_card_html(), this.gas_consumption_trend_card_html()] },
			],
			// Every widget on /app/dashboard-view/Accounts, in that page's own
			// order, rendered with this dashboard's own card style: 4 number
			// cards -> Profit and Loss (Full) -> Incoming/Outgoing Bills
			// (Half each) -> Receivable/Payable Ageing (Half each) -> Budget
			// Variance (Full) -> Bank Balance (Full).
			finance: [
				{ cls: "kpis-4", kpi_row: "finance" },
				{ cls: "r1", cards: [this.profit_and_loss_card_html()] },
				{ cls: "r2b", cards: [this.incoming_bills_card_html(), this.outgoing_bills_card_html()] },
				{ cls: "r2b", cards: [this.ar_ageing_card_html(), this.ap_ageing_card_html()] },
				{ cls: "r1", cards: [this.budget_variance_card_html()] },
				{ cls: "r1", cards: [this.bank_balance_card_html()] },
			],
			safety: [{ cls: "r1-narrow", cards: [this.safety_card_html()] }],
			reports: [
				{ cls: "r1", cards: [this.reports_cards_row_html()] },
				{ cls: "r1", cards: [this.reports_content_card_html()] },
			],
			settings: [
				{ cls: "r1-narrow", cards: [this.settings_intro_card_html()] },
				{ cls: "r2c", settings_row: true },
			],
		};
	}

	sections_html() {
		const layout = this.section_layout();
		const row_html = (r) => {
			if (r.kpi_row) return `<div class="isd-row ${r.cls} isd-kpi-row" data-kpi-row="${r.kpi_row}"></div>`;
			// A row with both `cards` and `kv_row` mixes static card(s) with
			// dynamic kv panels as siblings in the SAME css grid: the kv
			// panels render into a nested `isd-kv-inline` wrapper (kept
			// `display:contents` in CSS) instead of the row div itself, so
			// render_kv_panels()'s find(".isd-kv-row") + .html() still works
			// unchanged while the panels line up as their own grid columns
			// next to the static card(s) - see steel_dashboard.css.
			if (r.kv_row && r.cards) {
				return `<div class="isd-row ${r.cls}">${r.cards.join("")}<div class="isd-kv-row isd-kv-inline" data-kv-row="${r.kv_row}"></div></div>`;
			}
			if (r.kv_row) return `<div class="isd-row ${r.cls} isd-kv-row" data-kv-row="${r.kv_row}"></div>`;
			// Settings section only - one card per group get_settings_summary()
			// returns, filled by render_settings() the same way render_kv_panels()
			// fills isd-kv-row, just without a KV_PANEL_ROWS lookup (Settings
			// always shows every group, there's no per-section subset).
			if (r.settings_row) return `<div class="isd-row ${r.cls} isd-settings-row"></div>`;
			return `<div class="isd-row ${r.cls}">${r.cards.join("")}</div>`;
		};
		return Object.keys(layout)
			.map((key) => {
				const rows = layout[key].map(row_html).join("");
				return `<div class="isd-section" data-section="${key}" ${key === DEFAULT_SECTION ? "" : "hidden"}>${rows}</div>`;
			})
			.join("");
	}

	set_section(key) {
		this.state.section = key;
		this.$container.find(".isd-section").each((i, el) => {
			$(el).attr("hidden", $(el).data("section") !== key);
		});
		this.$container.find(".isd-nav li").each((i, el) => {
			$(el).toggleClass("active", $(el).data("key") === key);
		});
		const item = NAV_ITEMS.find((n) => n.key === key);
		this.$container.find(".isd-title-text").text(item ? item.title : "");
	}

	update_plant_overview() {
		this.$container.find(".isd-date").text(frappe.datetime.str_to_user(frappe.datetime.now_date()));
		this.$container.find(".isd-time").text(moment(frappe.datetime.now_datetime()).format("hh:mm A"));
	}

	// ------------------------------------------------------------- events
	bind_events() {
		this.$container.on("click", ".isd-nav li", (e) => this.set_section($(e.currentTarget).data("key")));
		// Date range changes are handled by the air-datepicker widgets set
		// up in init_date_pickers() -> on_date_picked().
		this.$container.on("click", ".isd-export-btn", () => this.export_csv());
		// Delegated (not bound once at shell-build time) - render_settings()
		// replaces this button's markup every time settings data reloads.
		this.$container.on("click", ".isd-settings-save-btn", () => this.save_settings());
		this.$container.on("click", ".isd-report-card", (e) => this.select_report($(e.currentTarget).data("key")));
		this.$container.on("input", ".isd-report-search", (e) => {
			this.state.report_filter = $(e.currentTarget).val();
			this.render_report();
		});
		this.$container.on("click", ".isd-report-print-btn", () => this.print_report());
		this.$container.on("click", ".isd-report-excel-btn", () => this.export_report("excel"));
		this.$container.on("click", ".isd-report-pdf-btn", () => this.export_report("pdf"));
	}

	// Pushes this.state's from/to back into both date inputs, dd/mm/yyyy-
	// formatted, then refetches.
	apply_date_range() {
		this.$container.find(".isd-from-date").val(this.format_date_display(this.state.from_date));
		this.$container.find(".isd-to-date").val(this.format_date_display(this.state.to_date));
		this.fetch_and_render();
	}

	fetch_and_render() {
		frappe.call({
			method: "ittehadsteels.ittehadsteels.page.steel_dashboard.steel_dashboard.get_dashboard_data",
			args: { from_date: this.state.from_date, to_date: this.state.to_date },
			freeze: true,
			callback: (r) => {
				if (!r.message) return;
				this.data = r.message;
				this.render_data(r.message);
			},
		});
	}

	// -------------------------------------------------------------- render
	render_data(data) {
		const w = ittehad_dashboard.widgets;

		// Fills both the sidebar brand logo AND the topbar title logo in one
		// go (same .isd-company-logo class on both, sized differently per
		// spot - see steel_dashboard.css). No placeholder icon on purpose -
		// if the Company has no logo set yet, both slots stay empty.
		this.$container
			.find(".isd-company-logo")
			.html(data.company_logo ? `<img src="${data.company_logo}" alt="Logo">` : "");

		this.render_kpi_rows(data.kpi);

		w.bars(this.$container.find(".isd-trend-furnace"), {
			labels: data.production_trend_furnace.labels,
			values: data.production_trend_furnace.this_week,
		});
		w.sparkline(this.$container.find(".isd-trend-spark-furnace"), data.production_trend_furnace);

		w.bars(this.$container.find(".isd-trend-deformed-bar"), {
			labels: data.production_trend_deformed_bar.labels,
			values: data.production_trend_deformed_bar.this_week,
		});
		w.sparkline(this.$container.find(".isd-trend-spark-deformed-bar"), data.production_trend_deformed_bar);

		w.donut(this.$container.find(".isd-donut-target"), {
			items: data.production_by_product,
			value_key: "qty_mt",
			label_key: "label",
			total_label: "Ton Total",
		});

		// data.gauges is already [{key, label, value, is_demo}], see
		// steel_dashboard.py::get_gauges() - the widget just wants `demo`
		// instead of `is_demo` as the flag name.
		w.gauges(
			this.$container.find(".isd-gauges-target"),
			data.gauges.map((g) => ({ label: g.label, value: Math.round(g.value), demo: !!g.is_demo }))
		);

		this.render_kv_panels(data.kv_panels);
		this.render_settings(data.settings);

		this.render_safety(data.safety);

		this.render_inventory_by_warehouse(data.inventory_by_warehouse);
		this.render_sales_by_product(data.sales_by_product);

		w.bars(this.$container.find(".isd-trend-sales-order"), {
			labels: data.sales_order_trend.labels,
			values: data.sales_order_trend.this_week,
		});
		w.sparkline(this.$container.find(".isd-trend-spark-sales-order"), data.sales_order_trend);

		w.donut(this.$container.find(".isd-sales-order-status-target"), {
			items: data.sales_order_billing_split,
			value_key: "value",
			label_key: "label",
			total_label: "PKR Total",
		});

		w.hbars(this.$container.find(".isd-top-customers-chart"), {
			items: data.top_customers,
			label_key: "customer",
			value_key: "revenue",
			unit_key: "unit",
		});

		this.render_profit_and_loss(data.profit_and_loss, data.profit_and_loss_trend);

		w.bars(this.$container.find(".isd-trend-incoming-bills"), {
			labels: data.incoming_bills_trend.labels,
			values: data.incoming_bills_trend.this_week,
		});
		w.sparkline(this.$container.find(".isd-trend-spark-incoming-bills"), data.incoming_bills_trend);

		w.bars(this.$container.find(".isd-trend-outgoing-bills"), {
			labels: data.outgoing_bills_trend.labels,
			values: data.outgoing_bills_trend.this_week,
		});
		w.sparkline(this.$container.find(".isd-trend-spark-outgoing-bills"), data.outgoing_bills_trend);

		this.render_ageing(".isd-ar-ageing-target", ".isd-ar-ageing-total", data.ar_ageing);
		this.render_ageing(".isd-ap-ageing-target", ".isd-ap-ageing-total", data.ap_ageing);

		this.render_budget_variance(data.budget_variance);

		w.line(this.$container.find(".isd-bank-balance-chart"), data.bank_balance_trend);

		w.bars(this.$container.find(".isd-warehouse-stock-value-chart"), {
			labels: data.warehouse_stock_value.map((r) => r.label),
			values: data.warehouse_stock_value.map((r) => r.value),
		});

		w.bars(this.$container.find(".isd-trend-purchase-receipt"), {
			labels: data.purchase_receipt_trend.labels,
			values: data.purchase_receipt_trend.this_week,
		});
		w.sparkline(this.$container.find(".isd-trend-spark-purchase-receipt"), data.purchase_receipt_trend);

		w.bars(this.$container.find(".isd-trend-delivery"), {
			labels: data.delivery_trend.labels,
			values: data.delivery_trend.this_week,
		});
		w.sparkline(this.$container.find(".isd-trend-spark-delivery"), data.delivery_trend);

		w.hbars(this.$container.find(".isd-oldest-items-chart"), {
			items: data.oldest_items.map((r) => ({ label: r.label, days: r.days, unit: "days" })),
			label_key: "label",
			value_key: "days",
			unit_key: "unit",
		});

		w.hbars(this.$container.find(".isd-item-shortage-chart"), {
			items: data.item_shortage_summary,
			label_key: "label",
			value_key: "value",
		});

		w.bars(this.$container.find(".isd-trend-power"), {
			labels: data.power_consumption_trend.labels,
			values: data.power_consumption_trend.this_week,
		});
		w.sparkline(this.$container.find(".isd-trend-spark-power"), data.power_consumption_trend);

		w.bars(this.$container.find(".isd-trend-gas"), {
			labels: data.gas_consumption_trend.labels,
			values: data.gas_consumption_trend.this_week,
		});
		w.sparkline(this.$container.find(".isd-trend-spark-gas"), data.gas_consumption_trend);

		// Refreshes whichever report is currently open (if any) so a date
		// range change or Settings save updates it too, not just the section
		// it mirrors.
		this.render_report();
	}

	// Total Income/Total Expense/Profit stats above the Profit trend chart -
	// unlike the plain KPI cards (kpi_card_html()), Profit needs to flip red
	// when the period ran at a loss, same up/down semantics as isd-delta
	// elsewhere on the dashboard.
	render_profit_and_loss(pnl, trend) {
		const w = ittehad_dashboard.widgets;
		const fmt = (v) => frappe.format(v, { fieldtype: "Float", precision: 2 }, { only_value: 1 });
		this.$container.find(".isd-pnl-income").text(`PKR ${fmt(pnl.income)} M`);
		this.$container.find(".isd-pnl-expense").text(`PKR ${fmt(pnl.expense)} M`);
		this.$container
			.find(".isd-pnl-profit")
			.text(`PKR ${fmt(pnl.profit)} M`)
			.toggleClass("isd-negative", pnl.profit < 0);

		w.bars(this.$container.find(".isd-trend-pnl"), { labels: trend.labels, values: trend.this_week });
		w.sparkline(this.$container.find(".isd-trend-spark-pnl"), trend);
	}

	// AR/AP Ageing - the bar list (see widgets.ageing()) plus the single
	// "Total Outstanding" figure above it, computed here from the same rows
	// rather than sent separately from the backend (it's just their sum).
	render_ageing(target_sel, total_sel, items) {
		const w = ittehad_dashboard.widgets;
		const total = (items || []).reduce((s, it) => s + it.value, 0);
		this.$container.find(total_sel).text(frappe.format(total, { fieldtype: "Currency" }, { only_value: 1 }));
		w.ageing(this.$container.find(target_sel), { items });
	}

	// Budgeted vs Actual per Budget Account - a plain table (see
	// budget_variance_card_html()), empty until a Budget doc exists.
	render_budget_variance(rows) {
		const w = ittehad_dashboard.widgets;
		const $body = this.$container.find(".isd-budget-variance");
		if (!rows || !rows.length) {
			$body.html(`<tr><td colspan="4">${w.empty_state("No Data")}</td></tr>`);
			return;
		}
		const fmt = (v) => frappe.format(v, { fieldtype: "Float", precision: 2 }, { only_value: 1 });
		$body.html(
			rows
				.map((r) => {
					const variance = r.actual - r.budget;
					return `<tr>
						<td>${r.label}</td>
						<td>${fmt(r.budget)}</td>
						<td>${fmt(r.actual)}</td>
						<td class="${variance > 0 ? "isd-negative" : ""}">${fmt(variance)}</td>
					</tr>`;
				})
				.join("")
		);
	}

	// kpi_list is whatever steel_dashboard.py::get_kpis() returned - however
	// many cards, in whatever order. Each .isd-kpi-row on the page (see
	// section_layout()) shows either all of them ("dashboard") or the subset
	// named in KPI_ROWS, still in the backend's order.
	render_kpi_rows(kpi_list) {
		const by_key = {};
		kpi_list.forEach((k) => (by_key[k.key] = k));

		this.$container.find(".isd-kpi-row").each((i, el) => {
			const $row = $(el);
			const wanted = KPI_ROWS[$row.data("kpiRow")];
			const items = wanted ? wanted.map((key) => by_key[key]).filter(Boolean) : kpi_list;
			$row.html(items.map((k) => this.kpi_card_html(k)).join(""));
		});
	}

	// panel_list is whatever steel_dashboard.py::get_kv_panels() returned.
	// Same pattern as render_kpi_rows() above, keyed off KV_PANEL_ROWS.
	render_kv_panels(panel_list) {
		const by_key = {};
		panel_list.forEach((p) => (by_key[p.key] = p));

		this.$container.find(".isd-kv-row").each((i, el) => {
			const $row = $(el);
			const wanted = KV_PANEL_ROWS[$row.data("kvRow")];
			const items = wanted ? wanted.map((key) => by_key[key]).filter(Boolean) : panel_list;
			$row.html(items.map((p) => this.kv_panel_card_html(p)).join(""));
		});
	}

	// Safety card - kv rows plus each actual's Target (see
	// steel_dashboard.py::get_safety()), and the shield/status flip to red/
	// "AT RISK" when the real LTIFR/TRIR/Observations-vs-target calculation
	// says so, instead of the hardcoded green "SAFE" this card used to
	// always show.
	render_safety(safety) {
		const w = ittehad_dashboard.widgets;
		w.kv_list(this.$container.find(".isd-safety"), [
			["Total Man Hours", frappe.format(safety.man_hours, { fieldtype: "Float", precision: 0 }, { only_value: 1 })],
			["LTIFR", `${safety.ltifr} (Target ${safety.target_ltifr})`],
			["TRIR", `${safety.trir} (Target ${safety.target_trir})`],
			["Safety Observations", `${safety.observations} (Target ${safety.target_observations})`],
		]);

		const is_safe = safety.status === "SAFE";
		this.$container.find(".isd-safety-shield-fill").attr("fill", is_safe ? "var(--green)" : "var(--red)");
		this.$container
			.find(".isd-safety-status-text")
			.text(safety.status)
			.toggleClass("ok", is_safe)
			.toggleClass("warn", !is_safe);
		this.$container
			.find(".isd-safety-status-caption")
			.text(is_safe ? "Keep up the good work!" : "LTIFR/TRIR/Observations missed target - review.");
	}

	// -------------------------------------------------------------- reports
	// Every report is built entirely from this.data, the same payload every
	// other section already renders from - no separate report endpoint, so a
	// report can never disagree with the section it mirrors. select_report()
	// switches the active card and (re)builds+renders; render_report()
	// re-applies the search filter without re-fetching; export/print read
	// back whatever render_report() last put on screen (this._report), so
	// they export exactly what's visible, filter included.

	select_report(key) {
		this.state.report = key;
		this.state.report_filter = "";
		this.$container.find(".isd-report-card").each((i, el) => {
			$(el).toggleClass("active", $(el).data("key") === key);
		});
		this.$container.find(".isd-report-panel").prop("hidden", false);
		this.$container.find(".isd-report-search").val("");
		this.render_report();
	}

	// Every row is {label, value, indent, bold} - bold indent-0 rows are
	// section headers (or, for Finance, real account-group totals), giving
	// every report the same hierarchical look Finance's Profit and Loss
	// Statement has, not a flat metric list. Metric rows reuse the section's
	// own KPI_ROWS grouping (see REPORTS' `kpi_row`) so "everything
	// mentioned in that section" lands here without hand-picking fields a
	// second time; detail rows pull from the same arrays that section's own
	// charts/tables already render. Column headers come from REPORTS'
	// `columns` - named for what's actually in that report (e.g. Finance's
	// "Particulars"/"Amount (PKR)"), not a generic "Metric"/"Value" reused
	// everywhere.
	build_report(key) {
		const rep = REPORTS.find((r) => r.key === key);
		const data = this.data;
		const rows = [];

		const section = (label) => rows.push({ label, value: "", indent: 0, bold: true });
		const detail = (label, value, indent = 1) => rows.push({ label, value, indent, bold: false });
		const kpi_rows = () => {
			if (!rep.kpi_row || !KPI_ROWS[rep.kpi_row]) return;
			const by_key = {};
			data.kpi.forEach((k) => (by_key[k.key] = k));
			KPI_ROWS[rep.kpi_row].forEach((k) => {
				const item = by_key[k];
				if (item) detail(item.label, `${item.value} ${item.unit}`);
			});
		};
		const gauge = (gkey) => {
			const g = (data.gauges || []).find((x) => x.key === gkey);
			return g ? `${g.value}%` : "-";
		};
		const kv_rows = (pkey) => ((data.kv_panels || []).find((p) => p.key === pkey) || {}).rows || [];

		if (key === "finance") {
			// The real hierarchical Profit and Loss Statement - see
			// get_profit_and_loss_statement() (reuses ERPNext's own financial
			// statements engine, same account tree /app/query-report/Profit
			// and Loss Statement shows). Falls back to just the sections below
			// if no default Company/Fiscal Year covers the selected range.
			const pl_rows = data.profit_and_loss_statement || [];
			if (pl_rows.length) {
				section("Profit and Loss Statement");
				pl_rows.forEach((r) =>
					rows.push({
						label: r.label,
						value: frappe.format(r.value, { fieldtype: "Currency" }, { only_value: 1 }),
						indent: r.indent + 1,
						bold: r.bold,
					})
				);
			}
			section("Finance KPIs");
			kpi_rows();
			if ((data.ar_ageing || []).some((r) => r.value)) {
				section("Receivable Ageing");
				data.ar_ageing.forEach((r) => detail(r.label, frappe.format(r.value, { fieldtype: "Currency" }, { only_value: 1 })));
			}
			if ((data.ap_ageing || []).some((r) => r.value)) {
				section("Payable Ageing");
				data.ap_ageing.forEach((r) => detail(r.label, frappe.format(r.value, { fieldtype: "Currency" }, { only_value: 1 })));
			}
		} else if (key === "production") {
			section("Production Metrics");
			kpi_rows();
			section("Production by Product");
			(data.production_by_product || []).forEach((r) => detail(r.label, `${r.qty_mt} Ton (${r.pct}%)`));
			section("Efficiency Gauges");
			detail("Capacity Utilization", gauge("capacity_utilization"));
			detail("Conversion Yield", gauge("conversion_yield"));
			detail("Rolling Mill Yield", gauge("rolling_mill_yield"));
			detail("OEE", gauge("oee"));
		} else if (key === "sales") {
			section("Sales Metrics");
			kpi_rows();
			section("Top Customers");
			(data.top_customers || []).forEach((r) => detail(r.customer, `${r.revenue} ${r.unit}`));
			section("Sales by Product");
			(data.sales_by_product || []).forEach((r) => detail(r.label, `${r.qty} ${r.unit}`));
		} else if (key === "inventory") {
			section("Inventory Metrics");
			kpi_rows();
			section("Warehouse Stock");
			(data.inventory_by_warehouse || []).forEach((r) => detail(r.warehouse, `${r.qty} ${r.unit}`));
			section("Oldest Items");
			(data.oldest_items || []).forEach((r) => detail(r.label, `${r.days} days`));
			if ((data.item_shortage_summary || []).length) {
				section("Item Shortage");
				data.item_shortage_summary.forEach((r) => detail(r.label, r.value));
			}
		} else if (key === "energy") {
			section("Energy Metrics");
			kpi_rows();
		} else if (key === "quality") {
			section("Quality");
			kv_rows("quality").forEach((r) => detail(r[0], r[1]));
		} else if (key === "maintenance") {
			section("Maintenance");
			kv_rows("maintenance").forEach((r) => detail(r[0], r[1]));
		} else if (key === "safety") {
			section("Safety");
			const s = data.safety || {};
			detail("Total Man Hours", s.man_hours);
			detail("LTIFR", `${s.ltifr} (Target ${s.target_ltifr})`);
			detail("TRIR", `${s.trir} (Target ${s.target_trir})`);
			detail("Safety Observations", `${s.observations} (Target ${s.target_observations})`);
			rows.push({ label: "Status", value: s.status, indent: 1, bold: true });
		}

		return { title: `${rep.label} Report`, columns: rep.columns, rows };
	}

	// Redraws the table for the currently selected report, applying
	// state.report_filter (a plain substring match across label+value) -
	// called on report switch and on every keystroke in the search box, and
	// after every dashboard refresh (see render_data()). Caches the
	// FILTERED result plus a header/subtitle as this._report so export/
	// print match exactly what's on screen.
	render_report() {
		if (!this.state.report || !this.data) return;
		const report = this.build_report(this.state.report);
		const q = (this.state.report_filter || "").toLowerCase();
		const rows = q ? report.rows.filter((r) => `${r.label}`.toLowerCase().includes(q) || `${r.value}`.toLowerCase().includes(q)) : report.rows;

		const range = `${this.format_date_display(this.state.from_date)} - ${this.format_date_display(this.state.to_date)}`;
		const generated = moment().format("DD/MM/YYYY hh:mm A");
		this._report = {
			title: report.title,
			columns: report.columns,
			rows,
			subtitle: `${range} | Generated ${generated}`,
		};

		const company = (frappe.sys_defaults && frappe.sys_defaults.company) || "";
		this.$container.find(".isd-report-company").text(company);
		this.$container.find(".isd-report-logo").attr("src", this.data.company_logo || "").toggleClass("isd-hidden", !this.data.company_logo);
		this.$container.find(".isd-report-title").text(report.title);
		this.$container.find(".isd-report-range").text(`${range}  ·  Generated ${generated}`);
		this.$container.find(".isd-report-thead").html(report.columns.map((c) => `<th>${c}</th>`).join(""));
		this.$container.find(".isd-report-table-body").html(
			rows.length
				? rows.map((r) => this._report_row_html(r)).join("")
				: `<tr><td colspan="2">${ittehad_dashboard.widgets.empty_state("No rows match")}</td></tr>`
		);
	}

	_report_row_html(r) {
		const style = r.bold ? "font-weight:700;" : "";
		const value = r.value === "" || r.value === null || r.value === undefined ? "" : r.value;
		return `<tr><td style="padding-left:${10 + r.indent * 18}px;${style}">${r.label}</td><td style="text-align:right;${style}">${value}</td></tr>`;
	}

	print_report() {
		if (!this._report) return;
		const { title, columns, rows, subtitle } = this._report;
		const win = window.open("", "_blank");
		if (!win) return;
		const company = (frappe.sys_defaults && frappe.sys_defaults.company) || "";
		const logo = this.data.company_logo ? `<img src="${this.data.company_logo}" />` : "";
		const thead = columns.map((c) => `<th>${c}</th>`).join("");
		const tbody = rows.map((r) => this._report_row_html(r)).join("");
		win.document.write(`
			<html>
				<head>
					<title>${title}</title>
					<style>
						body { font-family: sans-serif; padding: 28px; color: #111; }
						table { width: 100%; border-collapse: collapse; font-size: 12px; }
						th, td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; }
						th { background: #f0f0f0; }
						.isd-print-header { display: flex; align-items: flex-start; justify-content: space-between; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 18px; }
						.isd-print-header img { height: 48px; }
						.isd-print-company { color: #666; font-size: 12px; }
						h2 { margin: 2px 0; }
						.isd-print-range { color: #666; font-size: 11px; }
					</style>
				</head>
				<body>
					<div class="isd-print-header">
						<div>
							<div class="isd-print-company">${company}</div>
							<h2>${title}</h2>
							<div class="isd-print-range">${subtitle}</div>
						</div>
						${logo}
					</div>
					<table><thead><tr>${thead}</tr></thead><tbody>${tbody}</tbody></table>
				</body>
			</html>
		`);
		win.document.close();
		win.focus();
		win.print();
	}

	// kind: "excel" | "pdf" - posts the currently displayed report (see
	// render_report()'s this._report) to the matching whitelisted method via
	// Frappe's own open_url_post() (handles the CSRF token and triggers the
	// browser's normal file-download flow for a POST response). The PDF
	// backend adds the Company's own logo/name to its header
	// (see export_report_pdf()/_company_header()); Excel gets the same
	// title/subtitle as leading rows instead, since embedding an image in a
	// write-only xlsx workbook isn't worth the complexity for a data export.
	export_report(kind) {
		if (!this._report) return;
		const { title, columns, rows, subtitle } = this._report;
		const method =
			kind === "excel"
				? "ittehadsteels.ittehadsteels.page.steel_dashboard.steel_dashboard.export_report_excel"
				: "ittehadsteels.ittehadsteels.page.steel_dashboard.steel_dashboard.export_report_pdf";
		open_url_post(`/api/method/${method}`, { title, columns: JSON.stringify(columns), rows: JSON.stringify(rows), subtitle }, true);
	}

	// settings_list is whatever steel_dashboard.py::get_settings_summary()
	// returned - one kv_panel_card_html() card per group, same generic
	// "frontend renders however many come back" approach as
	// render_kv_panels(), just without a KV_PANEL_ROWS subset lookup (the
	// Settings section always shows every group).
	render_settings(settings_list) {
		const field_html = (f) => `
			<label class="isd-settings-field">
				<span class="isd-settings-field-label">${f.label}</span>
				<input type="number" class="isd-settings-input" step="${f.step}" min="0" value="${f.value}" data-field="${f.fieldname}" />
			</label>
		`;
		const group_html = (g) => `
			<div class="isd-card">
				<div class="isd-card-title">${g.title}</div>
				${g.fields.map(field_html).join("")}
			</div>
		`;
		this.$container.find(".isd-settings-row").html(settings_list.map(group_html).join(""));
	}

	// Reads every .isd-settings-input across all 4 groups (they're plain
	// siblings in the DOM, not nested per-group forms, so one pass covers
	// every field regardless of which card it's in), saves them in one call,
	// then redraws the form with the saved values AND refreshes the whole
	// dashboard - Capacity Utilization/OEE and every Quality/Maintenance/
	// Safety target line elsewhere read these same settings.
	save_settings() {
		const values = {};
		this.$container.find(".isd-settings-input").each((i, el) => {
			const $el = $(el);
			values[$el.data("field")] = parseFloat($el.val());
		});

		const $btn = this.$container.find(".isd-settings-save-btn");
		$btn.prop("disabled", true).text("Saving...");
		frappe.call({
			method: "ittehadsteels.ittehadsteels.page.steel_dashboard.steel_dashboard.update_settings",
			args: { values },
			callback: (r) => {
				$btn.prop("disabled", false).text("Save Settings");
				if (!r.message) return;
				this.render_settings(r.message);
				frappe.show_alert({ message: "Dashboard settings saved", indicator: "green" });
				this.fetch_and_render();
			},
			error: () => $btn.prop("disabled", false).text("Save Settings"),
		});
	}

	// Radial gauge in the trend card's 30% side section: this week's total
	// (sum of the bar chart's own values) as a % of last week's total.
	// Clamped 0-100 by gauge_svg() like every other gauge on this dashboard,
	// so a week that beats last week still reads as a full gauge.
	render_inventory_by_warehouse(rows) {
		const $body = this.$container.find(".isd-warehouse-inventory");
		const w = ittehad_dashboard.widgets;
		if (!rows || !rows.length) {
			$body.html(`<tr><td colspan="3">${w.empty_state("No stock balance found")}</td></tr>`);
			return;
		}
		$body.html(
			rows
				.map(
					(r) => `<tr>
						<td>${r.warehouse}</td>
						<td>${frappe.format(r.qty, { fieldtype: "Float", precision: 2 }, { only_value: 1 })}</td>
						<td>${r.unit}</td>
					</tr>`
				)
				.join("")
		);
	}

	render_sales_by_product(rows) {
		const w = ittehad_dashboard.widgets;
		w.hbars(this.$container.find(".isd-sales-by-product-chart"), {
			items: rows,
			label_key: "label",
			value_key: "qty",
			unit_key: "unit",
		});
		w.donut(this.$container.find(".isd-sales-by-product-pie-qty"), {
			items: rows,
			value_key: "qty",
			label_key: "label",
			total_label: "Qty Total",
		});
		w.donut(this.$container.find(".isd-sales-by-product-pie-revenue"), {
			items: rows,
			value_key: "revenue",
			label_key: "label",
			total_label: "Revenue Total",
		});
		// Each donut draws its own legend by default - hide both (their %
		// would just duplicate the same item list twice) in favor of the one
		// shared legend below with both percentages per item.
		this.$container.find(".isd-sales-by-product-pie-qty, .isd-sales-by-product-pie-revenue").find(".isd-donut-legend").hide();
		this.render_sales_pie_legend(rows);
	}

	// Shared legend for the two Sales by Product pies above: one row per
	// item with its Qty% and Revenue% side by side, colors matching the
	// pies' own default color cycle (same order, same palette).
	render_sales_pie_legend(rows) {
		const $el = this.$container.find(".isd-sales-pie-legend");
		if (!rows || !rows.length) {
			$el.html("");
			return;
		}
		const colors = ["var(--blue)", "var(--green)", "var(--orange)", "var(--purple)", "var(--gold)"];
		const qty_total = rows.reduce((s, r) => s + r.qty, 0) || 1;
		const revenue_total = rows.reduce((s, r) => s + r.revenue, 0) || 1;
		$el.html(
			rows
				.map((r, i) => {
					const color = colors[i % colors.length];
					const qty = frappe.format(r.qty, { fieldtype: "Float", precision: 1 }, { only_value: 1 });
					const revenue = frappe.format(r.revenue, { fieldtype: "Currency" }, { only_value: 1 });
					const qty_pct = Math.round((r.qty / qty_total) * 1000) / 10;
					const revenue_pct = Math.round((r.revenue / revenue_total) * 1000) / 10;
					return `
					<div class="item">
						<span class="l"><span class="swatch" style="background:${color}"></span><b style="color:${color}">${r.label}</b></span>
						<span><b style="color:var(--green)">Qty:</b> ${qty} ${r.unit} <b class="isd-pct-strong" style="color:var(--green)">${qty_pct}%</b>, <b style="color:var(--gold)">Revenue:</b> ${revenue} <b class="isd-pct-strong" style="color:var(--gold)">${revenue_pct}%</b></span>
					</div>`;
				})
				.join("")
		);
	}

	// -------------------------------------------------------------- export
	export_csv() {
		if (!this.data) return;
		const rows = [["Metric", "Value"]];
		this.data.kpi.forEach((k) => rows.push([k.label, k.value]));

		const blob = new Blob([rows.map((r) => r.join(",")).join("\n")], { type: "text/csv" });
		const link = document.createElement("a");
		link.href = URL.createObjectURL(blob);
		link.download = `dashboard_${this.state.from_date}_to_${this.state.to_date}.csv`;
		link.click();
	}
}
