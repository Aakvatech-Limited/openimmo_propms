import frappe


def execute():
	fields = ["custom_level_in_the_building", "custom_garage_spaces"]

	for fieldname in fields:
		if frappe.db.has_column("Property", fieldname):
			records = frappe.get_all(
				"Property", filters={fieldname: ["is", "set"]}, fields=["name", fieldname]
			)
			for record in records:
				val = record.get(fieldname)
				if val is not None:
					try:
						int(val)
					except (ValueError, TypeError):
						frappe.db.set_value("Property", record["name"], fieldname, None)

		frappe.db.set_value(
			"Custom Field",
			{"dt": "Property", "fieldname": fieldname},
			"fieldtype",
			"Int",
			update_modified=False,
		)
