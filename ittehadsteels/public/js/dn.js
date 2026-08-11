frappe.ui.form.on("Delivery Note Item", {
	first_weight(frm, cdt, cdn) {
		calculate_net_weight(frm, cdt, cdn);
	},

	second_weight(frm, cdt, cdn) {
		calculate_net_weight(frm, cdt, cdn);
	},

	gross_weight_by_receiver(frm, cdt, cdn) {
		calculate_net_weight_by_receiver(frm, cdt, cdn);
	},

	tare_weight_by_receiver(frm, cdt, cdn) {
		calculate_net_weight_by_receiver(frm, cdt, cdn);
	},

	billing_quantity_by(frm, cdt, cdn) {
		apply_billing_quantity(frm, cdt, cdn);
	},
});

async function calculate_net_weight(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const net_weight = flt(row.second_weight) - flt(row.first_weight);
	await frappe.model.set_value(cdt, cdn, "net_weight", net_weight);
	await calculate_weight_summary(frm, cdt, cdn);
}

async function calculate_net_weight_by_receiver(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	// Per spec: Tare Weight By Receiver - Gross Weight By Receiver (not Gross - Tare).
	const net_weight_by_receiver = flt(row.tare_weight_by_receiver) - flt(row.gross_weight_by_receiver);
	await frappe.model.set_value(cdt, cdn, "net_weight_by_receiver", net_weight_by_receiver);
	await calculate_weight_summary(frm, cdt, cdn);
}

async function calculate_weight_summary(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const average_weight = (flt(row.net_weight) - flt(row.net_weight_by_receiver)) / 2;
	const weight_difference = flt(row.net_weight) - flt(row.net_weight_by_receiver);

	await frappe.model.set_value(cdt, cdn, "average_weight", average_weight);
	await frappe.model.set_value(cdt, cdn, "weight_difference", weight_difference);
	await apply_billing_quantity(frm, cdt, cdn);
}

async function apply_billing_quantity(frm, cdt, cdn) {
	const row = locals[cdt][cdn];

	const qty_by_billing_method = {
		"Delivered Weight": row.net_weight,
		"Receiver Weight": row.net_weight_by_receiver,
		"Average Weight": row.average_weight,
	};

	const qty = qty_by_billing_method[row.billing_quantity_by];
	if (qty === undefined) return;

	await frappe.model.set_value(cdt, cdn, "qty", flt(qty));
}
