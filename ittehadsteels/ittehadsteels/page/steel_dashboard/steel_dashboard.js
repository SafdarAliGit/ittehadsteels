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
// row shows. `null` = show the full list the backend returned, in order.
const KPI_ROWS = {
	dashboard: null,
	production: ["production_mt", "heats"],
	sales: ["sales_mt", "revenue_m"],
	finance: ["revenue_m", "gross_margin_pct"],
};

// Same idea as KPI_ROWS, but for the label/value panels get_kv_panels()
// returns (Quality/Inventory/Maintenance/Energy). Each single-topic section
// shows just its own panel; "dashboard" shows all of them.
const KV_PANEL_ROWS = {
	dashboard: null,
	inventory: ["inventory"],
	quality: ["quality"],
	maintenance: ["maintenance"],
	energy: ["energy"],
};

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
				<div class="isd-kpi-footer">${ittehad_dashboard.widgets.delta_html(k.delta)} vs Last Week</div>
			</div>
		`;
	}

	trend_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Production Trend (MT)</div>
				<div class="isd-legend">
					<span><span class="dot" style="background:var(--blue)"></span>This Week</span>
					<span><span class="dash"></span>Last Week</span>
				</div>
				<div class="isd-bars isd-trend"></div>
			</div>
		`;
	}

	donut_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Production by Product (MT)</div>
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

	raw_materials_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Top Raw Material Consumption (This Week)</div>
				<table class="isd-table">
					<thead><tr><th>Material</th><th>Consumed (kg)</th><th>vs Last Week</th></tr></thead>
					<tbody class="isd-raw-materials"></tbody>
				</table>
			</div>
		`;
	}

	sales_by_product_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Sales by Product</div>
				<div class="isd-sales-by-product"></div>
			</div>
		`;
	}

	safety_card_html() {
		return `
			<div class="isd-card">
				<div class="isd-card-title">Safety (This Week) <span class="isd-demo-tag">v1 demo</span></div>
				<div class="isd-kv-list isd-safety" style="margin-bottom:10px"></div>
				<svg class="isd-safety-shield" viewBox="0 0 24 24" fill="none"><path d="M12 2l8 3v6c0 5-3.4 8.7-8 11-4.6-2.3-8-6-8-11V5l8-3z" fill="var(--green)"/><path d="M8 12l2.5 2.5L16 9" stroke="#0b1220" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
				<div class="isd-safety-status"><div class="ok">SAFE</div><small>Keep up the good work!</small></div>
			</div>
		`;
	}

	placeholder_card_html(text) {
		return `<div class="isd-card"><div class="isd-empty" style="min-height:80px">${text}</div></div>`;
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
				{ cls: "r2", cards: [this.trend_card_html(), this.donut_card_html(), this.gauges_card_html()] },
				{ cls: "r3", kv_row: "dashboard" },
				{
					cls: "r4",
					cards: [this.raw_materials_card_html(), this.sales_by_product_card_html(), this.safety_card_html()],
				},
			],
			production: [
				{ cls: "kpis-2", kpi_row: "production" },
				{ cls: "r2", cards: [this.trend_card_html(), this.donut_card_html(), this.gauges_card_html()] },
				{ cls: "r1", cards: [this.raw_materials_card_html()] },
			],
			sales: [
				{ cls: "kpis-2", kpi_row: "sales" },
				{ cls: "r1", cards: [this.sales_by_product_card_html()] },
			],
			inventory: [{ cls: "r1", kv_row: "inventory" }],
			quality: [{ cls: "r1", kv_row: "quality" }],
			maintenance: [{ cls: "r1", kv_row: "maintenance" }],
			energy: [{ cls: "r1", kv_row: "energy" }],
			finance: [
				{ cls: "kpis-2", kpi_row: "finance" },
				{
					cls: "r1",
					cards: [
						this.placeholder_card_html(
							"Full financial statements will appear here once Chart of Accounts mapping is finalised."
						),
					],
				},
			],
			safety: [{ cls: "r1-narrow", cards: [this.safety_card_html()] }],
			reports: [
				{
					cls: "r1",
					cards: [this.placeholder_card_html("Custom reports for Ittehad Steels will appear here as they're built.")],
				},
			],
			settings: [
				{
					cls: "r1",
					cards: [
						this.placeholder_card_html(
							"Dashboard settings (Plant/Department masters, refresh interval, etc.) will appear here."
						),
					],
				},
			],
		};
	}

	sections_html() {
		const layout = this.section_layout();
		const row_html = (r) => {
			if (r.kpi_row) return `<div class="isd-row ${r.cls} isd-kpi-row" data-kpi-row="${r.kpi_row}"></div>`;
			if (r.kv_row) return `<div class="isd-row ${r.cls} isd-kv-row" data-kv-row="${r.kv_row}"></div>`;
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

		w.bars(this.$container.find(".isd-trend"), {
			labels: data.production_trend.labels,
			values: data.production_trend.this_week,
		});

		w.donut(this.$container.find(".isd-donut-target"), {
			items: data.production_by_product,
			value_key: "qty_mt",
			label_key: "label",
			total_label: "MT Total",
		});

		// data.gauges is already [{key, label, value, is_demo}], see
		// steel_dashboard.py::get_gauges() - the widget just wants `demo`
		// instead of `is_demo` as the flag name.
		w.gauges(
			this.$container.find(".isd-gauges-target"),
			data.gauges.map((g) => ({ label: g.label, value: Math.round(g.value), demo: !!g.is_demo }))
		);

		this.render_kv_panels(data.kv_panels);

		w.kv_list(this.$container.find(".isd-safety"), [
			["Total Man Hours", frappe.format(data.demo.safety.man_hours, { fieldtype: "Float", precision: 0 }, { only_value: 1 })],
			["LTIFR", data.demo.safety.ltifr],
			["TRIR", data.demo.safety.trir],
			["Safety Observations", data.demo.safety.observations],
		]);

		this.render_raw_materials(data.top_raw_materials);

		w.hbars(this.$container.find(".isd-sales-by-product"), {
			items: data.sales_by_product,
			label_key: "label",
			value_key: "qty",
		});
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

	render_raw_materials(rows) {
		const $body = this.$container.find(".isd-raw-materials");
		const w = ittehad_dashboard.widgets;
		if (!rows || !rows.length) {
			$body.html(`<tr><td colspan="3">${w.empty_state("No consumption data for this period")}</td></tr>`);
			return;
		}
		$body.html(
			rows
				.map(
					(r) => `<tr>
						<td>${r.material}</td>
						<td>${frappe.format(r.consumed_kg, { fieldtype: "Float", precision: 1 }, { only_value: 1 })}</td>
						<td>${w.delta_html(r.delta_pct)}</td>
					</tr>`
				)
				.join("")
		);
	}

	// -------------------------------------------------------------- export
	export_csv() {
		if (!this.data) return;
		const rows = [["Metric", "Value"]];
		this.data.kpi.forEach((k) => rows.push([k.label, k.value]));
		rows.push([]);
		rows.push(["Material", "Consumed (kg)", "Delta %"]);
		this.data.top_raw_materials.forEach((r) => rows.push([r.material, r.consumed_kg, r.delta_pct]));

		const blob = new Blob([rows.map((r) => r.join(",")).join("\n")], { type: "text/csv" });
		const link = document.createElement("a");
		link.href = URL.createObjectURL(blob);
		link.download = `dashboard_${this.state.from_date}_to_${this.state.to_date}.csv`;
		link.click();
	}
}
