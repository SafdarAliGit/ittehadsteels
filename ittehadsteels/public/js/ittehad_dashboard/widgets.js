// Reusable, stateless chart/UI widgets for the Ittehad Steels dashboard.
// Every function takes plain data + a jQuery target and (re)draws into it -
// no shared state, so any of these can be reused on a future page/report
// without touching dashboard.js.
frappe.provide("ittehad_dashboard");

ittehad_dashboard.widgets = {
	// vertical bar chart, e.g. "This Week" production trend
	bars($target, { labels, values }) {
		if (!labels || !labels.length) {
			$target.html(ittehad_dashboard.widgets.empty_state("No data for this period"));
			return;
		}
		const max = Math.max(...values, 1);
		$target.html(
			labels
				.map((label, i) => {
					const val = values[i];
					const height = Math.max(2, (val / max) * 100);
					return `
					<div class="isd-bar-col">
						<div class="isd-bar-val">${val}</div>
						<div class="isd-bar" style="height:${height}%"></div>
						<div class="isd-bar-label">${label}</div>
					</div>`;
				})
				.join("")
		);
	},

	// compact line chart (This Week solid, Last Week dashed), e.g. the side
	// panel next to a Production Trend bar chart
	sparkline($target, { labels, this_week, last_week }) {
		if (!this_week || !this_week.length) {
			$target.html(ittehad_dashboard.widgets.empty_state("No data"));
			return;
		}
		// Scaled tight to this data's own min/max, NOT forced down to a 0
		// baseline: this week vs last week values are usually close together
		// (e.g. 0.10-0.12), so a 0-anchored scale squashes both lines into a
		// thin sliver near the top and they visually merge into one line.
		// A tight domain spreads that same variation across the full height.
		const all = [...this_week, ...(last_week || [])];
		const max = Math.max(...all);
		const min = Math.min(...all);
		const range = max - min || 1;
		const vb_w = 100,
			vb_h = 100,
			pad = 8;
		const n = this_week.length;
		const x = (i) => (n > 1 ? pad + (i / (n - 1)) * (vb_w - pad * 2) : vb_w / 2);
		const y = (v) => vb_h - pad - ((v - min) / range) * (vb_h - pad * 2);
		const to_points = (arr) => arr.map((v, i) => `${x(i)},${y(v)}`).join(" ");
		const this_points = to_points(this_week);
		const last_points = last_week && last_week.length ? to_points(last_week) : "";
		// Rising (last day >= first day) reads green, falling reads red - same
		// up/down semantics as isd-delta elsewhere on the dashboard.
		const trend_color = this_week[this_week.length - 1] >= this_week[0] ? "var(--green)" : "var(--red)";
		// vector-effect="non-scaling-stroke" - without it, preserveAspectRatio
		//="none" stretches the 100x100 viewBox non-uniformly to fill the
		// card's actual (taller-than-wide) box, and that same non-uniform
		// scale gets applied to the stroke itself: it comes out thick and
		// blobby at the rounded joins instead of a clean thin line. This
		// keeps the stroke a true 1.5px in screen space regardless of scale.
		$target.html(`
			<svg viewBox="0 0 ${vb_w} ${vb_h}" preserveAspectRatio="none" class="isd-sparkline">
				${last_points ? `<polyline points="${last_points}" fill="none" stroke="var(--muted)" stroke-width="1.5" stroke-dasharray="4 3" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>` : ""}
				<polyline points="${this_points}" fill="none" stroke="${trend_color}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>
			</svg>
		`);
	},

	// donut chart built from a CSS conic-gradient, with a centered total label
	donut($target, { items, value_key, label_key, total_label, colors }) {
		colors = colors || ["var(--blue)", "var(--green)", "var(--orange)", "var(--purple)", "var(--gold)"];
		if (!items || !items.length) {
			$target.html(ittehad_dashboard.widgets.empty_state("No data for this period"));
			return;
		}
		const total = items.reduce((s, it) => s + it[value_key], 0) || 1;
		let acc = 0;
		const stops = items
			.map((it, i) => {
				const start = acc;
				acc += (it[value_key] / total) * 100;
				return `${colors[i % colors.length]} ${start}% ${acc}%`;
			})
			.join(", ");
		// One % label per slice, placed at its mid-angle just outside the
		// ring's r=65 outer edge (130px .isd-donut) rather than on top of the
		// slice itself - conic-gradient's 0% is straight up, going clockwise,
		// hence sin/-cos rather than the usual cos/sin.
		acc = 0;
		const cx = 65,
			cy = 65,
			r = 80;
		const seg_labels = items
			.map((it) => {
				const start = acc;
				const slice_pct = (it[value_key] / total) * 100;
				acc += slice_pct;
				if (slice_pct < 5) return ""; // too thin for a legible label
				const mid_angle = ((start + slice_pct / 2) / 100) * 2 * Math.PI;
				const x = cx + r * Math.sin(mid_angle);
				const y = cy - r * Math.cos(mid_angle);
				const pct = Math.round(slice_pct * 10) / 10;
				return `<span class="isd-donut-seg-label" style="left:${x}px;top:${y}px">${pct}%</span>`;
			})
			.join("");
		const legend = items
			.map((it, i) => {
				const pct = Math.round((it[value_key] / total) * 1000) / 10;
				return `
				<div class="item">
					<span class="l"><span class="swatch" style="background:${colors[i % colors.length]}"></span>${it[label_key]}</span>
					<span>${frappe.format(it[value_key], { fieldtype: "Float", precision: 2 }, { only_value: 1 })} (${pct}%)</span>
				</div>`;
			})
			.join("");
		$target.html(`
			<div class="isd-donut" style="background:conic-gradient(${stops})">
				${seg_labels}
				<div class="isd-donut-center"><b>${frappe.format(total, { fieldtype: "Float", precision: 0 }, { only_value: 1 })}</b><span>${total_label || ""}</span></div>
			</div>
			<div class="isd-donut-legend">${legend}</div>
		`);
	},

	// semi-circle gauge, 0-100
	gauge_svg(pct, color) {
		pct = Math.max(0, Math.min(100, pct));
		const arc = `M 10 50 A 40 40 0 0 1 90 50`;
		const circumference = 125.6; // approx length of the half-circle path above
		const angle = Math.PI - (pct / 100) * Math.PI;
		const x = 50 + 40 * Math.cos(angle);
		const y = 50 - 40 * Math.sin(angle);
		return `
			<svg viewBox="0 0 100 60">
				<path d="${arc}" stroke="#26314c" stroke-width="8" fill="none" stroke-linecap="round"/>
				<path d="${arc}" stroke="${color}" stroke-width="8" fill="none" stroke-linecap="round"
					stroke-dasharray="${(pct / 100) * circumference} ${circumference}"/>
				<line x1="50" y1="50" x2="${x}" y2="${y}" stroke="#fff" stroke-width="2"/>
				<circle cx="50" cy="50" r="3" fill="#fff"/>
				<text x="50" y="48" text-anchor="middle" fill="var(--text)" font-size="14" font-weight="700">${pct}%</text>
			</svg>
		`;
	},

	// pick a gauge color by value; override thresholds per-caller if needed
	gauge_color(pct, thresholds = { good: 85, warn: 60 }) {
		if (pct >= thresholds.good) return "var(--green)";
		if (pct >= thresholds.warn) return "var(--orange)";
		return "var(--red)";
	},

	gauges($target, items) {
		// items: [{ label, value, demo (optional) }]
		$target.html(
			items
				.map(
					(g) => `
				<div class="isd-gauge">
					${ittehad_dashboard.widgets.gauge_svg(g.value, ittehad_dashboard.widgets.gauge_color(g.value))}
					<div class="isd-gauge-label">${g.label}${g.demo ? '<span class="isd-demo-tag">v1 demo</span>' : ""}</div>
				</div>`
				)
				.join("")
		);
	},

	// label/value list, e.g. Quality / Maintenance / Energy / Safety panels
	kv_list($target, rows) {
		$target.html(
			rows.map(([k, v]) => `<div class="kv"><span class="k">${k}</span><span class="v">${v}</span></div>`).join("")
		);
	},

	// horizontal bar list, e.g. Sales by Product. unit_key is optional - when
	// given, each bar's value is suffixed with that row's own unit (items can
	// carry different units, e.g. Ton vs Kg, so this reads per-row not global).
	hbars($target, { items, label_key, value_key, unit_key, colors }) {
		colors = colors || ["var(--blue)", "var(--green)", "var(--orange)", "var(--purple)", "var(--gold)"];
		if (!items || !items.length) {
			$target.html(ittehad_dashboard.widgets.empty_state("No data for this period"));
			return;
		}
		const max = Math.max(...items.map((i) => i[value_key]), 1);
		$target.html(
			items
				.map(
					(it, i) => `
				<div class="isd-hbar-row">
					<div class="isd-hbar-label">${it[label_key]}</div>
					<div class="isd-hbar-track"><div class="isd-hbar-fill" style="width:${(it[value_key] / max) * 100}%;background:${colors[i % colors.length]}"></div></div>
					<div class="isd-hbar-val">${frappe.format(it[value_key], { fieldtype: "Float", precision: 1 }, { only_value: 1 })}${unit_key && it[unit_key] ? " " + it[unit_key] : ""}</div>
				</div>`
				)
				.join("")
		);
	},

	// delta pill, e.g. "▲ 7.6%" / "▼ 2.1%"
	delta_html(pct) {
		const up = pct >= 0;
		return `<span class="isd-delta ${up ? "up" : "down"}">${up ? "▲" : "▼"} ${Math.abs(pct)}%</span>`;
	},

	empty_state(text) {
		return `<div class="isd-empty">${text}</div>`;
	},
};
