frappe.listview_settings['CRM Lead'] = {
	refresh: function(listview) {
		listview.page.add_inner_button(__('Import Lead XML'), function() {
			new frappe.ui.Dialog({
				title: __('Import Lead XML'),
				fields: [
					{
						label: __('XML File'),
						fieldname: 'xml_file',
						fieldtype: 'Attach',
						reqd: 1
					}
				],
				primary_action_label: __('Import'),
				primary_action(values) {
					frappe.call({
						method: 'openimmo_propms.api.server_script.import_lead_xml',
						args: {
							file_url: values.xml_file
						},
						callback: function(r) {
							if (!r.exc) {
								frappe.show_alert({message: __('Imported successfully'), indicator: 'green'});
								listview.refresh();
							}
						}
					});
					this.hide();
				}
			}).show();
		});
	}
};