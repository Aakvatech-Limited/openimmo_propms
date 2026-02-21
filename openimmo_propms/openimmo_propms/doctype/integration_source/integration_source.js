frappe.ui.form.on("Integration Source", {
	refresh(frm) {
		// Only show FTP buttons if source type is FTP
		if (frm.doc.source_type === "FTP") {
			
			// 1. Connection Test Button
			frm.add_custom_button(__("FTP Test Connection"), () => {
				frm.call({
					method: "openimmo_propms.services.sync_engine.test_integration_connection",
					args: {
						source_name: frm.doc.name
					},
					freeze: true,
					freeze_message: __("Testing Connection to {0}...", [frm.doc.ftp_host]),
					callback: (r) => {
						if (r.message && r.message.status === "success") {
							frappe.msgprint({
								title: __('Connection Test Passed'),
								message: r.message.message,
								indicator: 'green'
							});
						} else if (r.message) {
							frappe.msgprint({
								title: __('Connection Test Failed'),
								message: r.message.message,
								indicator: 'red'
							});
						}
					}
				});
			});

			// 2. Manual Sync Button
			if (frm.doc.enabled && frm.doc.sync_frequency === "Manual") {
				frm.add_custom_button(__("FTP Sync Now"), () => {
					frappe.confirm(__("Are you sure you want to fetch and process files from FTP now?"), () => {
						// State: Start Syncing in UI
						frm.set_df_property('last_sync_status', 'value', 'Syncing...');
						
						frm.call({
							method: "openimmo_propms.services.sync_engine.execute_sync",
							args: {
								source_name: frm.doc.name
							},
							freeze: true,
							freeze_message: __("Connecting to {0}...", [frm.doc.ftp_host || "FTP Server"]),
							callback: (r) => {
								if (!r.exc && r.message) {
									if (r.message.status === "success") {
										frappe.show_alert({
											message: r.message.message,
											indicator: 'green'
										});
									} else {
										frappe.msgprint({
											title: __('Sync Error'),
											message: r.message.message,
											indicator: 'red'
										});
									}
								}
								frm.reload_doc();
							},
							error: (r) => {
								frm.reload_doc();
							}
						});
					});
				});
			} // End if manual
		} // End if FTP
	},
});
