"""Tests for the source processors that fetch XML and open Integration Jobs."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from openimmo_propms.processors.api_processor import APIProcessor
from openimmo_propms.processors.manual_processor import ManualProcessor

from .fixtures import make_integration_source, write_site_file

API_XML = (
	'<?xml version="1.0" encoding="UTF-8"?>'
	"<feed><objekt id='A'><titel>One</titel></objekt>"
	"<objekt id='B'><titel>Two</titel></objekt></feed>"
)


class FakeResponse:
	def __init__(self, text, content_type="application/xml"):
		self.text = text
		self.content = text.encode("utf-8")
		self.headers = {"content-type": content_type}

	def raise_for_status(self):
		return None

	def json(self):
		import json

		return json.loads(self.text)


class TestApiProcessorConfiguration(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _source(self, name="_Test API Source", **overrides):
		return make_integration_source(
			name,
			source_type="API",
			api_endpoint="https://example.com/feed.xml",
			**overrides,
		)

	def test_the_split_configuration_fields_exist_on_the_doctype(self):
		"""APIProcessor reads these directly, so a missing field is an AttributeError at runtime."""
		meta = frappe.get_meta("Integration Source")

		for fieldname in ("data_split_node", "xml_namespace"):
			with self.subTest(fieldname=fieldname):
				self.assertIsNotNone(meta.get_field(fieldname))

	def test_the_processor_can_read_its_split_configuration(self):
		source = self._source(data_split_node="objekt")
		processor = APIProcessor(source.name)

		self.assertEqual(processor.source_doc.data_split_node, "objekt")
		self.assertIsNone(processor.source_doc.xml_namespace)

	def test_splits_the_response_into_one_job_per_node(self):
		source = self._source("_Test API Split", data_split_node="objekt")
		processor = APIProcessor(source.name)

		with patch(
			"openimmo_propms.processors.api_processor.requests.get", return_value=FakeResponse(API_XML)
		):
			job_names = processor.receive_files()

		self.assertEqual(len(job_names), 2)
		self.assertEqual(
			frappe.db.get_value("Integration Source", source.name, "last_sync_status"), "Success"
		)

	def test_a_response_without_a_split_node_becomes_a_single_job(self):
		source = self._source("_Test API Whole")
		processor = APIProcessor(source.name)

		with patch(
			"openimmo_propms.processors.api_processor.requests.get", return_value=FakeResponse(API_XML)
		):
			job_names = processor.receive_files()

		self.assertEqual(len(job_names), 1)

	def test_a_missing_endpoint_is_reported(self):
		source = make_integration_source("_Test API No Endpoint", source_type="Manual Upload")
		source.db_set("source_type", "API")
		processor = APIProcessor(source.name)

		with self.assertRaises(frappe.ValidationError):
			processor._make_api_request()


class TestManualProcessor(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_returns_the_pending_jobs_for_its_source(self):
		source = make_integration_source("_Test Manual Source")
		file_url, _path = write_site_file("_test_manual.xml", "<openimmo/>")
		job = frappe.get_doc(
			{
				"doctype": "Integration Job",
				"source_name": source.name,
				"xml_file": file_url,
				"status": "Pending",
			}
		)
		job.insert(ignore_permissions=True)

		self.assertIn(job.name, ManualProcessor(source.name).receive_files())

	def test_returns_nothing_when_no_job_is_pending(self):
		source = make_integration_source("_Test Manual Empty")

		self.assertEqual(ManualProcessor(source.name).receive_files(), [])


class TestCrmLeadCustomFieldsPatch(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_the_patch_targets_the_lead_doctype_available_on_this_site(self):
		from openimmo_propms.patches.custom_fields import openimmo_custom_fields_Crm_Lead as patch_module

		patch_module.execute()

		doctype = "CRM Lead" if frappe.db.exists("DocType", "CRM Lead") else "Lead"
		self.assertTrue(frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": "openimmo_id_key"}))

	def test_the_patch_is_idempotent(self):
		from openimmo_propms.patches.custom_fields import openimmo_custom_fields_Crm_Lead as patch_module

		patch_module.execute()
		patch_module.execute()

		doctype = "CRM Lead" if frappe.db.exists("DocType", "CRM Lead") else "Lead"
		self.assertEqual(frappe.db.count("Custom Field", {"dt": doctype, "fieldname": "openimmo_id_key"}), 1)

	def test_the_list_view_script_is_registered_for_every_available_lead_doctype(self):
		from openimmo_propms import hooks

		self.assertEqual(set(hooks.doctype_list_js), {"CRM Lead", "Lead"})
