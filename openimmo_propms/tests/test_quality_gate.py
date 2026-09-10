"""Tests for the Quality Gate script sandbox and the export batch evaluator."""

from types import SimpleNamespace

import frappe
from frappe.tests import IntegrationTestCase

from openimmo_propms.services.quality_gate import (
	evaluate_quality_gate_for_export,
	validate_quality_gate,
)


def source(script=None, **overrides):
	values = {"quality_gate_script": script, "name": "_Test QG Source", "target_doctype": "Property Type"}
	values.update(overrides)
	return SimpleNamespace(**values)


class TestValidateQualityGate(IntegrationTestCase):
	def test_passes_when_no_script_is_configured(self):
		self.assertEqual(validate_quality_gate(source(None), {"name": "P1"}), (True, []))

	def test_passes_for_a_blank_script(self):
		self.assertEqual(validate_quality_gate(source("   "), {"name": "P1"}), (True, []))

	def test_a_script_can_accept_a_record(self):
		is_valid, reasons = validate_quality_gate(source("is_valid = True"), {"name": "P1"})

		self.assertTrue(is_valid)
		self.assertEqual(reasons, [])

	def test_a_script_can_block_a_record_with_a_reason(self):
		script = "is_valid = False\nreasons.append('missing price')"

		is_valid, reasons = validate_quality_gate(source(script), {"name": "P1"})

		self.assertFalse(is_valid)
		self.assertEqual(reasons, ["missing price"])

	def test_blocking_without_a_reason_gets_a_default_reason(self):
		is_valid, reasons = validate_quality_gate(source("is_valid = False"), {"name": "P1"})

		self.assertFalse(is_valid)
		self.assertEqual(reasons, ["Quality Gate Failed"])

	def test_the_script_can_read_the_record(self):
		script = "is_valid = doc.get('kaufpreis') is not None"

		self.assertTrue(validate_quality_gate(source(script), {"kaufpreis": 100})[0])
		self.assertFalse(validate_quality_gate(source(script), {})[0])

	def test_a_broken_script_blocks_the_record_and_reports_why(self):
		is_valid, reasons = validate_quality_gate(source("this is not python"), {"name": "P1"})

		self.assertFalse(is_valid)
		self.assertIn("Quality Gate script error", reasons[0])

	def test_accepts_a_dict_source(self):
		self.assertEqual(validate_quality_gate({"quality_gate_script": ""}, {"name": "P1"}), (True, []))


class TestEvaluateQualityGateForExport(IntegrationTestCase):
	def tearDown(self):
		frappe.local.openimmo_quality_gate_details = None

	def test_returns_every_record_when_no_script_is_set(self):
		records = [{"name": "P1"}, {"name": "P2"}]

		self.assertEqual(evaluate_quality_gate_for_export(source(None), records), records)

	def test_filters_out_blocked_records(self):
		script = "is_valid = doc.get('publish') == 1"
		records = [{"name": "P1", "publish": 1}, {"name": "P2", "publish": 0}]

		kept = evaluate_quality_gate_for_export(source(script), records)

		self.assertEqual([record["name"] for record in kept], ["P1"])

	def test_records_a_processing_detail_row_per_record(self):
		script = "is_valid = doc.get('publish') == 1"
		records = [{"name": "P1", "publish": 1}, {"name": "P2", "publish": 0}]

		evaluate_quality_gate_for_export(source(script), records)

		details = frappe.local.openimmo_quality_gate_details["_Test QG Source"]
		self.assertEqual([row["status"] for row in details], ["Success", "Skipped"])
		self.assertEqual([row["record_id"] for row in details], ["P1", "P2"])
		self.assertEqual(details[0]["record_type"], "Property Type")

	def test_details_are_keyed_per_source(self):
		evaluate_quality_gate_for_export(source("is_valid = True", name="_Test QG A"), [{"name": "P1"}])
		evaluate_quality_gate_for_export(source("is_valid = True", name="_Test QG B"), [{"name": "P2"}])

		self.assertEqual(sorted(frappe.local.openimmo_quality_gate_details), ["_Test QG A", "_Test QG B"])

	def test_an_empty_batch_yields_an_empty_result(self):
		self.assertEqual(evaluate_quality_gate_for_export(source("is_valid = True"), []), [])
