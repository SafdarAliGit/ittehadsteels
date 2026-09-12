// Shared icon registry for the Ittehad Steels dashboard.
// Add a new icon here and every widget/page that calls ittehad_dashboard.icon(name)
// picks it up automatically - nothing else needs to change.
frappe.provide("ittehad_dashboard");

ittehad_dashboard.icons = {
	factory: `<svg viewBox="0 0 24 24" fill="none"><path d="M3 21V10l5 3V10l5 3V7l6 4v10H3z" fill="currentColor"/><path d="M6 17h2M10 17h2M14 17h2" stroke="#0b1220" stroke-width="1.2"/></svg>`,
	// Two overlapping steel coils (rolls), each with a dark bore hole -
	// bigger viewBox so it stays crisp at the large size these KPI icons
	// render at (see .isd-kpi-icon in steel_dashboard.css).
	coil: `<svg viewBox="0 0 48 48" fill="none"><circle cx="18" cy="30" r="15" fill="currentColor"/><circle cx="18" cy="30" r="6" fill="#0b1220"/><circle cx="32" cy="15" r="10" fill="currentColor" opacity=".75"/><circle cx="32" cy="15" r="4" fill="#0b1220"/></svg>`,
	// A tipped ladle pouring liquid steel: scoop + angled handle + drips.
	heat: `<svg viewBox="0 0 48 48" fill="none"><path d="M6 12h24l-9 19h-6z" fill="currentColor"/><rect x="24" y="3" width="17" height="5" rx="2.5" fill="currentColor" transform="rotate(35 32.5 5.5)"/><circle cx="11" cy="37" r="2.6" fill="currentColor" opacity=".85"/><circle cx="17" cy="42" r="1.8" fill="currentColor" opacity=".6"/></svg>`,
	truck: `<svg viewBox="0 0 48 48" fill="none"><rect x="4" y="14" width="24" height="16" rx="2" fill="currentColor"/><path d="M28 19h9l7 7v4h-16z" fill="currentColor" opacity=".85"/><rect x="32" y="22" width="7" height="6" rx="1" fill="#0b1220"/><circle cx="13" cy="34" r="3.4" fill="#0b1220"/><circle cx="35" cy="34" r="3.4" fill="#0b1220"/></svg>`,
	// Two coin-cylinder stacks with a growth arrow above them.
	coins: `<svg viewBox="0 0 48 48" fill="none"><path d="M17 5l6 8h-4v6h-4v-6h-4z" fill="currentColor"/><ellipse cx="12" cy="27" rx="9" ry="4" fill="currentColor"/><rect x="3" y="27" width="18" height="10" fill="currentColor"/><ellipse cx="12" cy="37" rx="9" ry="4" fill="currentColor"/><g opacity=".75"><ellipse cx="29" cy="31" rx="9" ry="4" fill="currentColor"/><rect x="20" y="31" width="18" height="8" fill="currentColor"/><ellipse cx="29" cy="39" rx="9" ry="4" fill="currentColor"/></g></svg>`,
	// Pac-man style pie with a lighter highlight wedge for depth.
	pie: `<svg viewBox="0 0 48 48" fill="none"><path d="M24 4a20 20 0 1 0 20 20H24V4z" fill="currentColor"/><path d="M24 4a20 20 0 0 1 14.1 5.9L24 24V4z" fill="currentColor" opacity=".55"/></svg>`,
	grid: `<svg viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="7" height="7" rx="1" fill="currentColor"/><rect x="14" y="3" width="7" height="7" rx="1" fill="currentColor"/><rect x="3" y="14" width="7" height="7" rx="1" fill="currentColor"/><rect x="14" y="14" width="7" height="7" rx="1" fill="currentColor"/></svg>`,
	cart: `<svg viewBox="0 0 24 24" fill="none"><path d="M3 4h2l2 11h11l2-8H6" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><circle cx="9" cy="19" r="1.4" fill="currentColor"/><circle cx="16" cy="19" r="1.4" fill="currentColor"/></svg>`,
	box: `<svg viewBox="0 0 24 24" fill="none"><path d="M3 7l9-4 9 4-9 4-9-4z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M3 7v10l9 4 9-4V7" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M12 11v10" stroke="currentColor" stroke-width="1.6"/></svg>`,
	check: `<svg viewBox="0 0 24 24" fill="none"><path d="M12 2l7 3v6c0 5-3 8-7 11-4-3-7-6-7-11V5l7-3z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M9 12l2 2 4-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
	wrench: `<svg viewBox="0 0 24 24" fill="none"><path d="M14.7 6.3a4 4 0 0 1-5.4 5.4L4 17l3 3 5.3-5.3a4 4 0 0 1 5.4-5.4l-3 3-2-2 2.9-2.9z" fill="currentColor"/></svg>`,
	bolt: `<svg viewBox="0 0 24 24" fill="none"><path d="M13 2L4 14h6l-1 8 9-12h-6l1-8z" fill="currentColor"/></svg>`,
	dollar: `<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.6"/><path d="M12 6v12M9 9.5c0-1.4 1.3-2 3-2s3 .8 3 2-1.2 1.7-3 2.2-3 1-3 2.3 1.3 2 3 2 3-.7 3-2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>`,
	shield: `<svg viewBox="0 0 24 24" fill="none"><path d="M12 2l8 3v6c0 5-3.4 8.7-8 11-4.6-2.3-8-6-8-11V5l8-3z" fill="currentColor"/></svg>`,
	doc: `<svg viewBox="0 0 24 24" fill="none"><path d="M6 2h9l4 4v16H6z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M9 12h7M9 16h7M9 8h3" stroke="currentColor" stroke-width="1.4"/></svg>`,
	gear: `<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.6"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`,
	download: `<svg viewBox="0 0 24 24" fill="none"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 19h16" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
};

ittehad_dashboard.icon = function (name) {
	return ittehad_dashboard.icons[name] || "";
};
