// Copyright (c) 2025, Talib sheikh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Integration Job", {
	refresh: function (frm) {
		// 1. Render Dynamic Header Info
		frm.trigger("render_status_intro");

		// 2. Setup Action Buttons
		frm.trigger("setup_actions");
	},

	render_status_intro: function (frm) {
		// Map status to indicators and dynamic messages
		const status_map = {
			Pending: ["blue", __("Job is ready for processing.")],
			Processing: ["orange", __("Integration engine is currently running. Please wait...")],
			Success: ["green", __("All records processed successfully. Total: {0}", [frm.doc.successful_records])],
			Failed: ["red", __("Processing failed. Refer to the error log for details. Total Failed: {0}", [frm.doc.failed_records])],
			"Partially Completed": [
				"yellow",
				__("Completed with errors. Total: {0}, Success: {1}, Failed: {2}", [
					frm.doc.total_records,
					frm.doc.successful_records,
					frm.doc.failed_records,
				]),
			],
		};

		const config = status_map[frm.doc.status] || ["grey", __("Status Unknown")];
		frm.set_intro(config[1], config[0]);
	},

	setup_actions: function (frm) {
		// Remove existing buttons to prevent duplication on refresh
		frm.clear_custom_buttons();

		// Standard Practice: Processing ke waqt button hide rakhte hain
		if (frm.doc.status !== "Processing") {
			const btn_label =
				frm.doc.status === "Pending" ? __("Process Now") : __("Re-process Job");

			frm.add_custom_button(btn_label, () => {
				frm.trigger("execute_integration");
			}).addClass("btn-primary");
		}
	},

	execute_integration: function (frm) {
		// Minimalist validation check
		if (!frm.doc.xml_file && !frm.doc.raw_data) {
			frappe.throw(
				__("No data found to process. Please attach a file or provide raw data."),
			);
		}

		frappe.confirm(__("Start processing this integration?"), () => {
			frappe.call({
				// Generic naming convention follow karte hue
				method: "openimmo_propms.services.processor.run_integration_engine",
				args: {
					job_name: frm.doc.name,
				},
				freeze: true,
				freeze_message: __("Syncing Data..."),
				callback: function (r) {
					if (!r.exc) {
						frm.reload_doc();
						frappe.show_alert({
							message: __("Sync Process Completed"),
							indicator: "green",
						});
					}
				},
			});
		});
	},
});
