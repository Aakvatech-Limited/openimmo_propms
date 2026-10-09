"""Shared fixture builders for the openimmo_propms test suite."""

import frappe

TEST_SOURCE_PREFIX = "_Test OpenImmo"


def make_integration_source(name, **overrides):
	"""Create (or reuse) an Integration Source with import defaults."""
	values = {
		"doctype": "Integration Source",
		"source_name": name,
		"source_type": "Manual Upload",
		"operation_type": "Import",
		"enabled": 1,
		"target_doctype": "Property Type",
		"sync_frequency": "Manual",
	}
	values.update(overrides)

	if frappe.db.exists("Integration Source", name):
		frappe.delete_doc("Integration Source", name, force=True, ignore_permissions=True)

	source = frappe.get_doc(values)
	source.insert(ignore_permissions=True)
	return source


def make_export_source(name, **overrides):
	"""Create an Integration Source configured for OpenImmo export."""
	values = {
		"source_type": "Manual Upload",
		"operation_type": "Export",
		"export_format": "OpenImmo",
		"anbieter_id": "TEST-ANBIETER",
		"transfer_mode": "CHANGE",
		"transfer_scope": "VOLL",
		"target_doctype": "Property Type",
	}
	values.update(overrides)
	return make_integration_source(name, **values)


def add_field_mapping(source, source_field, target_field, **overrides):
	"""Append an Integration Field Mapping row and return it."""
	row = {"source_field": source_field, "target_field": target_field}
	row.update(overrides)
	return source.append("field_mappings", row)


def write_site_file(relative_path, content, private=False):
	"""Write a file into the site's public/private files directory and return its file_url."""
	import os

	folder = frappe.get_site_path("private" if private else "public", "files")
	os.makedirs(folder, exist_ok=True)
	path = os.path.join(folder, relative_path)

	mode = "wb" if isinstance(content, bytes) else "w"
	with open(path, mode) as handle:
		handle.write(content)

	return ("/private/files/" if private else "/files/") + relative_path, path


def make_email_account(name="_Test OpenImmo Inbox"):
	"""Create (or reuse) a minimal incoming Email Account and return its name."""
	if frappe.db.exists("Email Account", name):
		return name

	account = frappe.get_doc(
		{
			"doctype": "Email Account",
			"email_account_name": name,
			"email_id": "_test_openimmo_inbox@example.com",
			"password": "secret",
			"email_server": "imap.example.com",
			"enable_incoming": 0,
			"enable_outgoing": 0,
		}
	)
	account.insert(ignore_permissions=True)
	return account.name
