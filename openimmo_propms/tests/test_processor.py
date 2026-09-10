"""End-to-end tests for the integration engine that turns an XML job into records."""

from typing import ClassVar

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from openimmo_propms.services.processor import navigate_to_root_node, run_integration_engine

from .fixtures import add_field_mapping, make_integration_source, write_site_file

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<openimmo>
	<anbieter>
		<immobilie><objekttitel>_Test Feed Loft</objekttitel></immobilie>
		<immobilie><objekttitel>_Test Feed Villa</objekttitel></immobilie>
	</anbieter>
</openimmo>
"""

SINGLE = """<?xml version="1.0" encoding="UTF-8"?>
<openimmo>
	<anbieter><immobilie><objekttitel>_Test Feed Solo</objekttitel></immobilie></anbieter>
</openimmo>
"""


class TestNavigateToRootNode(UnitTestCase):
	DATA: ClassVar[dict] = {"openimmo": {"anbieter": {"immobilie": [{"a": 1}, {"a": 2}]}}}

	def test_walks_a_dotted_path(self):
		found = navigate_to_root_node(self.DATA, "openimmo.anbieter.immobilie")

		self.assertEqual(found, [{"a": 1}, {"a": 2}])

	def test_an_empty_path_wraps_the_whole_document(self):
		self.assertEqual(navigate_to_root_node(self.DATA, ""), [self.DATA])

	def test_returns_none_for_a_missing_path(self):
		self.assertIsNone(navigate_to_root_node(self.DATA, "openimmo.nope.immobilie"))

	def test_returns_none_when_the_path_runs_into_a_scalar(self):
		self.assertIsNone(navigate_to_root_node({"a": "scalar"}, "a.b"))


class TestRunIntegrationEngine(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _source(self, name):
		source = make_integration_source(name, root_node="openimmo.anbieter.immobilie")
		add_field_mapping(source, "objekttitel", "property_type_name", is_unique=1)
		source.save(ignore_permissions=True)
		return source

	def _job(self, source, filename, content):
		file_url, _path = write_site_file(filename, content)
		job = frappe.get_doc(
			{
				"doctype": "Integration Job",
				"source_name": source.name,
				"xml_file": file_url,
				"status": "Pending",
			}
		)
		job.insert(ignore_permissions=True)
		return job

	def test_imports_every_entry_in_the_feed(self):
		source = self._source("_Test Engine Multi")
		job = self._job(source, "_test_engine_multi.xml", FEED)

		run_integration_engine(job.name)
		job.reload()

		self.assertEqual(job.total_records, 2)
		self.assertEqual(job.successful_records, 2)
		self.assertEqual(job.failed_records, 0)
		self.assertTrue(frappe.db.exists("Property Type", "_Test Feed Loft"))
		self.assertTrue(frappe.db.exists("Property Type", "_Test Feed Villa"))

	def test_a_single_entry_is_wrapped_into_a_list(self):
		source = self._source("_Test Engine Single")
		job = self._job(source, "_test_engine_single.xml", SINGLE)

		run_integration_engine(job.name)
		job.reload()

		self.assertEqual(job.total_records, 1)
		self.assertEqual(job.successful_records, 1)

	def test_the_job_reaches_a_terminal_status(self):
		source = self._source("_Test Engine Status")
		job = self._job(source, "_test_engine_status.xml", SINGLE)

		run_integration_engine(job.name)
		job.reload()

		self.assertNotEqual(job.status, "Processing")
		self.assertEqual(job.status, "Success")

	def test_a_repeat_run_skips_records_that_already_exist(self):
		source = self._source("_Test Engine Repeat")
		first = self._job(source, "_test_engine_repeat.xml", SINGLE)
		run_integration_engine(first.name)

		second = self._job(source, "_test_engine_repeat_2.xml", SINGLE)
		run_integration_engine(second.name)
		second.reload()

		self.assertEqual(second.skipped_records, 1)
		self.assertEqual(second.successful_records, 0)
		self.assertEqual(second.status, "Partially Completed")

	def test_processing_details_record_one_row_per_entry(self):
		source = self._source("_Test Engine Details")
		job = self._job(source, "_test_engine_details.xml", FEED)

		run_integration_engine(job.name)
		job.reload()

		self.assertEqual(len(job.processing_details), 2)
		self.assertEqual({row.status for row in job.processing_details}, {"Success"})
		self.assertEqual({row.record_type for row in job.processing_details}, {"Property Type"})

	def test_a_root_node_that_matches_nothing_fails_the_job(self):
		source = make_integration_source("_Test Engine Bad Root", root_node="openimmo.nope")
		add_field_mapping(source, "objekttitel", "property_type_name", is_unique=1)
		source.save(ignore_permissions=True)
		job = self._job(source, "_test_engine_bad_root.xml", FEED)

		run_integration_engine(job.name)
		job.reload()

		self.assertEqual(job.status, "Failed")
		self.assertTrue(job.error_log)

	def test_a_missing_mandatory_field_is_counted_as_a_failure(self):
		source = make_integration_source("_Test Engine Missing", root_node="openimmo.anbieter.immobilie")
		add_field_mapping(source, "nicht_vorhanden", "property_type_name", is_unique=1)
		source.save(ignore_permissions=True)
		job = self._job(source, "_test_engine_missing.xml", SINGLE)

		run_integration_engine(job.name)
		job.reload()

		self.assertEqual(job.failed_records, 1)
		self.assertEqual(job.status, "Failed")
