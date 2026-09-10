"""Tests for the whitelisted endpoints, including who is allowed to call them."""

import frappe
from frappe.tests import IntegrationTestCase

from openimmo_propms.api.export import get_default_template, preview_jinja_xml
from openimmo_propms.api.server_script import import_lead_xml

from .fixtures import add_field_mapping, make_export_source, make_integration_source, write_site_file

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<openimmo>
	<anbieter><immobilie><objekttitel>_Test Api Loft</objekttitel></immobilie></anbieter>
</openimmo>
"""

WHITELISTED_ENDPOINTS = (
	"openimmo_propms.api.export.run_openimmo_export",
	"openimmo_propms.api.export.get_default_template",
	"openimmo_propms.api.export.preview_jinja_xml",
	"openimmo_propms.api.server_script.import_lead_xml",
	"openimmo_propms.services.processor.run_integration_engine",
	"openimmo_propms.services.sync_engine.execute_sync",
	"openimmo_propms.services.sync_engine.test_integration_connection",
)


def make_limited_user(email="_test_openimmo_limited@example.com"):
	"""A logged-in user with no Integration Source or Job permissions."""
	if not frappe.db.exists("User", email):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Limited",
				"send_welcome_email": 0,
				"roles": [],
			}
		)
		user.insert(ignore_permissions=True)
	return email


class TestDefaultTemplate(IntegrationTestCase):
	def test_returns_the_shipped_openimmo_template(self):
		template = get_default_template("OpenImmo 1.2.7")

		self.assertIn("openimmo", template)

	def test_throws_for_an_unknown_template(self):
		with self.assertRaises(frappe.ValidationError):
			get_default_template("No Such Template")


class TestPreviewJinjaXml(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_throws_when_jinja_is_not_enabled_for_the_source(self):
		source = make_export_source("_Test Preview Off", use_jinja_template=0)

		with self.assertRaises(frappe.ValidationError):
			preview_jinja_xml(source.name)

	def test_throws_when_no_records_match_the_filters(self):
		source = make_export_source(
			"_Test Preview Empty",
			use_jinja_template=1,
			xml_template="<openimmo/>",
			export_filters_json='{"property_type_name": "_Test No Such Property Type"}',
		)

		with self.assertRaises(frappe.ValidationError):
			preview_jinja_xml(source.name)


class TestImportLeadXml(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _manual_source(self, name="_Test Import Source"):
		source = make_integration_source(name, root_node="openimmo.anbieter.immobilie")
		add_field_mapping(source, "objekttitel", "property_type_name", is_unique=1)
		source.save(ignore_permissions=True)
		return source

	def test_creates_and_processes_a_job(self):
		source = self._manual_source()
		file_url, _path = write_site_file("_test_api_import.xml", FEED)

		job_name = import_lead_xml(file_url, source.name)
		job = frappe.get_doc("Integration Job", job_name)

		self.assertEqual(job.successful_records, 1)
		self.assertTrue(frappe.db.exists("Property Type", "_Test Api Loft"))

	def test_falls_back_to_an_enabled_manual_source(self):
		source = self._manual_source("_Test Import Fallback")
		file_url, _path = write_site_file("_test_api_import_fb.xml", FEED)

		job_name = import_lead_xml(file_url)

		self.assertEqual(frappe.db.get_value("Integration Job", job_name, "source_name"), source.name)

	def test_throws_when_no_manual_source_exists(self):
		frappe.db.set_value("Integration Source", {"source_type": "Manual Upload"}, "enabled", 0)
		file_url, _path = write_site_file("_test_api_import_none.xml", FEED)

		with self.assertRaises(frappe.ValidationError):
			import_lead_xml(file_url)

	def test_rejects_a_non_xml_attachment(self):
		self._manual_source("_Test Import Bad Ext")

		with self.assertRaises(frappe.ValidationError):
			import_lead_xml("/files/report.pdf")

	def test_a_file_url_cannot_escape_the_site_directory(self):
		"""A traversal payload must resolve inside the site, so the job simply finds no file."""
		import os

		from openimmo_propms.services.parser import get_absolute_path

		self._manual_source("_Test Import Traversal")
		traversal = "/files/../../private/files/_test_import_secret.xml"

		resolved = os.path.realpath(get_absolute_path(traversal))
		self.assertTrue(resolved.startswith(os.path.realpath(frappe.get_site_path("public")) + os.sep))

		job_name = import_lead_xml(traversal)

		self.assertEqual(frappe.db.get_value("Integration Job", job_name, "status"), "Failed")


class TestEndpointPermissions(IntegrationTestCase):
	"""Every whitelisted endpoint must refuse a user without the matching DocType permission."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.limited_user = make_limited_user()

	def setUp(self):
		if not frappe.db.exists("Property Type", "_Test Perm PT"):
			frappe.get_doc({"doctype": "Property Type", "property_type_name": "_Test Perm PT"}).insert(
				ignore_permissions=True
			)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_every_endpoint_is_registered_as_whitelisted(self):
		for dotted_path in WHITELISTED_ENDPOINTS:
			with self.subTest(endpoint=dotted_path):
				method = frappe.get_attr(dotted_path)
				self.assertIn(method, frappe.whitelisted)

	def test_import_lead_xml_refuses_a_user_without_job_permissions(self):
		source = make_integration_source("_Test Perm Import")
		file_url, _path = write_site_file("_test_perm_import.xml", FEED)
		frappe.set_user(self.limited_user)

		with self.assertRaises(frappe.PermissionError):
			import_lead_xml(file_url, source.name)

	def test_run_integration_engine_refuses_a_user_without_job_permissions(self):
		from openimmo_propms.services.processor import run_integration_engine

		source = make_integration_source("_Test Perm Engine")
		file_url, _path = write_site_file("_test_perm_engine.xml", FEED)
		job = frappe.get_doc(
			{
				"doctype": "Integration Job",
				"source_name": source.name,
				"xml_file": file_url,
				"status": "Pending",
			}
		)
		job.insert(ignore_permissions=True)
		frappe.set_user(self.limited_user)

		with self.assertRaises(frappe.PermissionError):
			run_integration_engine(job.name)

	def test_execute_sync_refuses_a_user_without_source_permissions(self):
		from openimmo_propms.services.sync_engine import execute_sync

		source = make_integration_source("_Test Perm Sync")
		frappe.set_user(self.limited_user)

		with self.assertRaises(frappe.PermissionError):
			execute_sync(source.name)

	def test_connection_test_refuses_a_user_without_source_permissions(self):
		from openimmo_propms.services.sync_engine import test_integration_connection

		source = make_integration_source("_Test Perm Conn")
		frappe.set_user(self.limited_user)

		with self.assertRaises(frappe.PermissionError):
			test_integration_connection(source.name)

	def test_the_export_endpoint_refuses_a_user_without_source_permissions(self):
		from openimmo_propms.api.export import run_openimmo_export

		source = make_export_source(
			"_Test Perm Export",
			name_field="property_type_name",
			export_filters_json='{"property_type_name": "_Test Perm PT"}',
		)
		add_field_mapping(source, "objekttitel", "property_type_name")
		source.save(ignore_permissions=True)
		frappe.set_user(self.limited_user)

		with self.assertRaises(frappe.PermissionError):
			run_openimmo_export(source.name)

	def test_the_jinja_preview_refuses_a_user_without_source_permissions(self):
		source = make_export_source(
			"_Test Perm Preview",
			use_jinja_template=1,
			xml_template="<openimmo/>",
			name_field="property_type_name",
			export_filters_json='{"property_type_name": "_Test Perm PT"}',
		)
		frappe.set_user(self.limited_user)

		with self.assertRaises(frappe.PermissionError):
			preview_jinja_xml(source.name)
