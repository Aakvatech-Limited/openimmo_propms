# path/to/openimmo_propms/services/mapper.py

import frappe
from frappe.utils import flt, cint

def map_external_data_to_doctype(source_name, entry_data):
	"""
	Core mapping engine that creates a DocType based on metadata rules.
	"""
	source = frappe.get_doc("Integration Source", source_name)
	target_meta = frappe.get_meta(source.target_doctype)
	target_doc = frappe.new_doc(source.target_doctype)

	for mapping in source.field_mappings:
		# 1. Validate Target Field Exists in Meta
		if not target_meta.has_field(mapping.target_field):
			continue

		value = get_value_by_json_path(entry_data, mapping.source_field)
		
		# Metadata Fallback
		if (value is None or value == "") and mapping.default_value:
			value = mapping.default_value
			
		if value is not None:
			value = apply_data_transformation(value, mapping.transformation)
			
			# 2. Type Casting and Special Handling for Link Fields
			df = target_meta.get_field(mapping.target_field)
			value = cast_value_to_fieldtype(value, df)
			
			if value:
				target_doc.set(mapping.target_field, value)

	# Handle Idempotency (Unique Field Constraint)
	if is_duplicate_record(target_doc, source):
		return None

	target_doc.insert(ignore_permissions=True)
	return target_doc.name

def get_value_by_json_path(data, path):
	"""Traverses dictionary keys using dot-notation."""
	if not path: return None
	for key in path.split('.'):
		if isinstance(data, dict):
			data = data.get(key)
		else:
			return None
	return data

def apply_data_transformation(value, transform_type):
	"""Standard string transformations."""
	if not value: return value
	if transform_type == "Upper Case": return str(value).upper()
	if transform_type == "Lower Case": return str(value).lower()
	if transform_type == "Title Case": return str(value).title()
	if transform_type == "Integer": return cint(value)
	if transform_type == "Float": return flt(value)
	return value

def cast_value_to_fieldtype(value, df):
	"""
	Ensures the value matches the target DocType field type.
	Handles Link fields by checking/creating the linked record.
	"""
	fieldtype = df.fieldtype
	if not value: return value

	if fieldtype in ["Int", "Check"]:
		return cint(value)
	elif fieldtype in ["Float", "Currency", "Percent"]:
		return flt(value)
	elif fieldtype in ["Small Text", "Text", "Long Text"]:
		return str(value)
	elif fieldtype == "Link":
		return handle_link_field(value, df.options)
	
	return value

def handle_link_field(value, link_doctype):
	"""
	Checks if a value exists in the linked DocType.
	If it's a Salutation or similar simple DocType, it creates it if missing.
	"""
	if not value or not link_doctype:
		return None

	# Check if record exists
	if frappe.db.exists(link_doctype, value):
		return value

	# Special Case: Auto-create common simple Link DocTypes
	if link_doctype in ["Salutation", "Lead Source", "Campaign"]:
		try:
			new_doc = frappe.get_doc({
				"doctype": link_doctype,
				"name" if frappe.get_meta(link_doctype).autoname == "field:name" else (
					"salutation" if link_doctype == "Salutation" else "source_name"
				): value
			})
			# Handle DocTypes that use 'salutation' or other fields as their ID
			if link_doctype == "Salutation":
				new_doc.salutation = value
			
			new_doc.insert(ignore_permissions=True)
			return new_doc.name
		except Exception:
			# If creation fails (e.g. mandatory fields), return None to avoid crashing the whole import
			return None

	return None # Don't return value if it doesn't exist to avoid Link validation errors

def is_duplicate_record(doc, source):
	"""Checks if a record with unique mapping already exists."""
	unique_field = next((m.target_field for m in source.field_mappings if m.is_unique), None)
	if unique_field and doc.get(unique_field):
		if frappe.db.exists(source.target_doctype, {unique_field: doc.get(unique_field)}):
			return True
	return False