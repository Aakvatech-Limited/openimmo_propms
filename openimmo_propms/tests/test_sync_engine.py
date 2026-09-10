"""Tests for source dispatch, scheduling decisions and the whitelisted sync entry points."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from openimmo_propms.processors.api_processor import APIProcessor
from openimmo_propms.processors.email_processor import EmailProcessor
from openimmo_propms.processors.ftp_processor import FTPProcessor
from openimmo_propms.processors.manual_processor import ManualProcessor
from openimmo_propms.services.sync_engine import (
	_get_processor,
	_should_sync_now,
	execute_sync,
	test_integration_connection,
)

from .fixtures import make_email_account, make_export_source, make_integration_source


class TestProcessorDispatch(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_maps_each_source_type_to_its_processor(self):
		expected = {
			"Manual Upload": ManualProcessor,
			"API": APIProcessor,
			"FTP": FTPProcessor,
		}

		for source_type, processor_class in expected.items():
			with self.subTest(source_type=source_type):
				source = make_integration_source(
					f"_Test Dispatch {source_type}",
					source_type=source_type,
					api_endpoint="https://example.com/feed.xml",
					ftp_host="ftp.example.com",
					ftp_username="user",
				)
				self.assertIsInstance(_get_processor(source), processor_class)

	def test_an_email_source_maps_to_the_email_processor(self):
		account = make_email_account()
		source = make_integration_source("_Test Dispatch Email", source_type="Email", email_account=account)

		self.assertIsInstance(_get_processor(source), EmailProcessor)

	def test_throws_for_an_unknown_source_type(self):
		source = frappe._dict(source_type="Carrier Pigeon", name="_Test Dispatch Unknown")

		with self.assertRaises(frappe.ValidationError):
			_get_processor(source)


class TestShouldSyncNow(IntegrationTestCase):
	def test_manual_sources_never_sync_automatically(self):
		self.assertFalse(_should_sync_now(frappe._dict(sync_frequency="Manual")))

	def test_a_source_without_a_frequency_never_syncs(self):
		self.assertFalse(_should_sync_now(frappe._dict(sync_frequency=None)))

	def test_only_the_configured_frequencies_are_reachable(self):
		"""The Select field must not offer a frequency the scheduler cannot honour."""
		options = frappe.get_meta("Integration Source").get_field("sync_frequency").options
		configured = {option for option in options.split("\n") if option}

		self.assertEqual(configured, {"Manual", "Daily", "Weekly"})

	def test_daily_syncs_once_the_calendar_date_has_changed(self):
		source = make_integration_source("_Test Sched Daily", sync_frequency="Daily")
		source.db_set("last_sync_at", add_to_date(now_datetime(), days=-1))

		self.assertTrue(_should_sync_now(frappe._dict(name=source.name, sync_frequency="Daily")))

	def test_daily_does_not_sync_twice_on_the_same_day(self):
		source = make_integration_source("_Test Sched Daily Same", sync_frequency="Daily")
		source.db_set("last_sync_at", now_datetime())

		self.assertFalse(_should_sync_now(frappe._dict(name=source.name, sync_frequency="Daily")))

	def test_weekly_syncs_after_seven_days(self):
		source = make_integration_source("_Test Sched Weekly", sync_frequency="Weekly")
		source.db_set("last_sync_at", add_to_date(now_datetime(), days=-8))

		self.assertTrue(_should_sync_now(frappe._dict(name=source.name, sync_frequency="Weekly")))

	def test_weekly_waits_inside_the_window(self):
		source = make_integration_source("_Test Sched Weekly Wait", sync_frequency="Weekly")
		source.db_set("last_sync_at", add_to_date(now_datetime(), days=-2))

		self.assertFalse(_should_sync_now(frappe._dict(name=source.name, sync_frequency="Weekly")))

	def test_a_source_that_never_synced_is_due(self):
		source = make_integration_source("_Test Sched Never", sync_frequency="Daily")
		source.db_set("last_sync_at", None)

		self.assertTrue(_should_sync_now(frappe._dict(name=source.name, sync_frequency="Daily")))


class TestWhitelistedSyncEntryPoints(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_connection_test_is_limited_to_ftp_export_sources(self):
		source = make_export_source("_Test Conn Export", source_type="Manual Upload")

		result = test_integration_connection(source.name)

		self.assertEqual(result["status"], "error")
		self.assertIn("only available for FTP export", result["message"])

	def test_sync_refuses_export_sources(self):
		source = make_export_source("_Test Sync Export")

		result = execute_sync(source.name)

		self.assertEqual(result["status"], "error")
		self.assertIn("Use the export API", result["message"])

	def test_sync_refuses_a_disabled_source(self):
		source = make_integration_source("_Test Sync Disabled", enabled=0)

		result = execute_sync(source.name)

		self.assertEqual(result["status"], "error")
		self.assertIn("disabled", result["message"])

	def test_sync_records_a_failed_status_on_the_source(self):
		source = make_integration_source(
			"_Test Sync Failure", source_type="FTP", ftp_host="h", ftp_username="u"
		)

		execute_sync(source.name)

		self.assertEqual(frappe.db.get_value("Integration Source", source.name, "last_sync_status"), "Failed")
