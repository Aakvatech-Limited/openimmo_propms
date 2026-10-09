# Copyright (c) 2025, Talib sheikh and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from openimmo_propms.tests.fixtures import make_integration_source, write_site_file


class TestIntegrationJob(IntegrationTestCase):
	def setUp(self):
		self.source = make_integration_source("_Test Job Source")
		self.file_url, _path = write_site_file("_test_job.xml", "<openimmo/>")

	def tearDown(self):
		frappe.db.rollback()

	def _job(self, **overrides):
		values = {
			"doctype": "Integration Job",
			"source_name": self.source.name,
			"xml_file": self.file_url,
			"status": "Pending",
		}
		values.update(overrides)
		return frappe.get_doc(values)

	def test_rejects_a_non_xml_attachment(self):
		with self.assertRaises(frappe.ValidationError):
			self._job(xml_file="/files/report.pdf").insert(ignore_permissions=True)

	def test_accepts_an_uppercase_xml_extension(self):
		file_url, _path = write_site_file("_test_job_upper.XML", "<openimmo/>")

		job = self._job(xml_file=file_url)
		job.insert(ignore_permissions=True)

		self.assertTrue(job.name)

	def test_derives_the_file_name_from_the_attachment(self):
		job = self._job()
		job.insert(ignore_permissions=True)

		self.assertEqual(job.file_name, "_test_job.xml")

	def test_keeps_an_explicit_file_name(self):
		job = self._job(file_name="custom.xml")
		job.insert(ignore_permissions=True)

		self.assertEqual(job.file_name, "custom.xml")

	def test_status_stays_pending_before_any_processing(self):
		job = self._job()
		job.insert(ignore_permissions=True)

		self.assertEqual(job.status, "Pending")

	def test_status_becomes_success_when_every_record_landed(self):
		job = self._job(successful_records=5, failed_records=0, skipped_records=0)
		job.insert(ignore_permissions=True)

		self.assertEqual(job.status, "Success")

	def test_status_becomes_failed_when_nothing_landed(self):
		job = self._job(successful_records=0, failed_records=3, skipped_records=0)
		job.insert(ignore_permissions=True)

		self.assertEqual(job.status, "Failed")

	def test_status_becomes_partially_completed_for_a_mixed_result(self):
		job = self._job(successful_records=2, failed_records=1, skipped_records=0)
		job.insert(ignore_permissions=True)

		self.assertEqual(job.status, "Partially Completed")

	def test_skipped_only_counts_as_partially_completed(self):
		job = self._job(successful_records=0, failed_records=0, skipped_records=4)
		job.insert(ignore_permissions=True)

		self.assertEqual(job.status, "Partially Completed")

	def test_a_processing_job_resolves_its_status_once_counts_arrive(self):
		"""A job left in Processing must not stay there after its records are counted."""
		job = self._job()
		job.insert(ignore_permissions=True)
		job.db_set("status", "Processing")

		job.successful_records = 3
		job.failed_records = 0
		job.skipped_records = 0
		job.save(ignore_permissions=True)

		self.assertEqual(job.status, "Success")

	def test_update_status_stamps_processed_at_on_a_terminal_status(self):
		job = self._job()
		job.insert(ignore_permissions=True)

		job.update_status("Success")

		self.assertTrue(frappe.db.get_value("Integration Job", job.name, "processed_at"))

	def test_update_status_does_not_stamp_processed_at_while_running(self):
		job = self._job()
		job.insert(ignore_permissions=True)

		job.update_status("Processing")

		self.assertFalse(frappe.db.get_value("Integration Job", job.name, "processed_at"))

	def test_update_status_stores_the_error_log(self):
		job = self._job()
		job.insert(ignore_permissions=True)

		job.update_status("Failed", "boom")

		self.assertEqual(frappe.db.get_value("Integration Job", job.name, "error_log"), "boom")
