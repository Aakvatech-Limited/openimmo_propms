# Copyright (c) 2026, Talib sheikh and Contributors
# See license.txt

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from openimmo_propms.openimmo_propms.doctype.integration_source.integration_source import (
	template_renders_deletes,
)
from openimmo_propms.services.export_engine import (
	_get_configured_export_filters,
	_keep_rendered_deletes,
	_persist_portal_listings_state,
	_rendered_delete_obids,
)

_SRC = "TEST-SRC-PORTAL"


def _cleanup(listing_name):
	if frappe.db.exists("Portal Listing", listing_name):
		frappe.delete_doc("Portal Listing", listing_name, ignore_permissions=True, force=True)


def _make_source(**kwargs):
	defaults = {"name": _SRC, "export_filters_json": "", "last_sync_at": None}
	defaults.update(kwargs)
	return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# strip_modified filter tests
# ---------------------------------------------------------------------------


class TestStripModifiedFilters(FrappeTestCase):
	def test_strips_modified_from_dict(self):
		src = _make_source(
			export_filters_json=json.dumps({"custom_is_published": 1, "modified": [">", "2026-01-01"]})
		)
		result = _get_configured_export_filters(src, strip_modified=True)
		self.assertIn("custom_is_published", result)
		self.assertNotIn("modified", result)

	def test_strips_modified_from_list_format(self):
		src = _make_source(
			export_filters_json=json.dumps([["custom_is_published", "=", 1], ["modified", ">", "2026-01-01"]])
		)
		result = _get_configured_export_filters(src, strip_modified=True)
		field_names = [row[0] for row in result if isinstance(row, list)]
		self.assertIn("custom_is_published", field_names)
		self.assertNotIn("modified", field_names)

	def test_keeps_modified_when_flag_false(self):
		src = _make_source(
			export_filters_json=json.dumps({"custom_is_published": 1, "modified": [">", "2026-01-01"]})
		)
		result = _get_configured_export_filters(src, strip_modified=False)
		self.assertIn("modified", result)

	def test_empty_filters_returns_empty_dict(self):
		src = _make_source(export_filters_json="")
		self.assertEqual(_get_configured_export_filters(src, strip_modified=True), {})

	def test_last_sync_at_jinja_renders(self):
		src = _make_source(
			export_filters_json='{"custom_is_published": 1, "modified": [">", "{{ last_sync_at }}"]}',
			last_sync_at="2026-09-01 00:00:00",
		)
		result = _get_configured_export_filters(src, strip_modified=False)
		self.assertIn("2026-09-01", result["modified"][1])


# ---------------------------------------------------------------------------
# _persist_portal_listings_state tests
# ---------------------------------------------------------------------------


class TestPersistPortalListings(FrappeTestCase):
	def tearDown(self):
		for suffix in ["PROP-A", "PROP-B", "PROP-C", "PROP-GONE"]:
			_cleanup(f"{_SRC}-{suffix}")

	def test_insert_new_online_listing(self):
		_persist_portal_listings_state(
			_SRC, "Property", [("PROP-A", "OBID-A")], [], "JOB-0001", "2026-10-28 10:00:00"
		)
		doc = frappe.get_doc("Portal Listing", f"{_SRC}-PROP-A")
		self.assertEqual(doc.state, "Online")
		self.assertEqual(doc.last_action, "CHANGE")
		self.assertEqual(doc.obid, "OBID-A")

	def test_update_existing_listing_to_withdrawn(self):
		_persist_portal_listings_state(
			_SRC, "Property", [("PROP-B", "OBID-B")], [], "JOB-0001", "2026-10-28 10:00:00"
		)
		_persist_portal_listings_state(
			_SRC, "Property", [], [("PROP-B", "OBID-B")], "JOB-0002", "2026-10-28 11:00:00"
		)
		doc = frappe.get_doc("Portal Listing", f"{_SRC}-PROP-B")
		self.assertEqual(doc.state, "Withdrawn")
		self.assertEqual(doc.last_action, "DELETE")
		self.assertEqual(doc.last_job, "JOB-0002")

	def test_upsert_updates_obid_on_existing(self):
		_persist_portal_listings_state(
			_SRC, "Property", [("PROP-C", "OLD-OBID")], [], "JOB-0001", "2026-10-28 10:00:00"
		)
		_persist_portal_listings_state(
			_SRC, "Property", [("PROP-C", "NEW-OBID")], [], "JOB-0002", "2026-10-28 12:00:00"
		)
		doc = frappe.get_doc("Portal Listing", f"{_SRC}-PROP-C")
		self.assertEqual(doc.obid, "NEW-OBID")

	def test_delete_missing_listing_is_noop(self):
		_cleanup(f"{_SRC}-PROP-GONE")
		try:
			_persist_portal_listings_state(
				_SRC, "Property", [], [("PROP-GONE", "OBID-X")], "JOB-0001", "2026-10-28 10:00:00"
			)
		except Exception as e:
			self.fail(f"Should not raise for missing listing: {e}")


# ---------------------------------------------------------------------------
# Delivery failure guard — Portal Listing must NOT be persisted on FTP failure
# ---------------------------------------------------------------------------


class TestDeliveryFailureGuard(FrappeTestCase):
	@patch("openimmo_propms.services.export_engine._persist_portal_listings_state")
	@patch("openimmo_propms.services.export_engine._deliver_export")
	@patch("openimmo_propms.services.export_engine._create_export_job")
	@patch("openimmo_propms.services.export_engine._build_export_documents")
	@patch("openimmo_propms.services.export_engine.validate_xml_against_xsd", return_value=(True, ""))
	@patch(
		"openimmo_propms.services.export_engine.generate_xsd_based_xml",
		return_value="<?xml version='1.0'?><openimmo/>",
	)
	@patch(
		"openimmo_propms.services.export_engine.build_property_data",
		return_value={"verwaltung_techn.openimmo_obid": "OBID-1"},
	)
	@patch("openimmo_propms.services.export_engine._validate_export_source")
	@patch("openimmo_propms.services.export_engine.evaluate_quality_gate_for_export")
	@patch("openimmo_propms.services.export_engine._get_records_for_export")
	def test_persist_not_called_when_delivery_fails(
		self,
		mock_get_records,
		mock_quality_gate,
		mock_validate_source,
		mock_build_property,
		mock_xsd_build,
		mock_xsd_validate,
		mock_build_docs,
		mock_create_job,
		mock_deliver,
		mock_persist,
	):
		import frappe as _frappe

		from openimmo_propms.services.export_engine import run_export

		source = frappe._dict(
			name="TEST-SRC-FTP",
			operation_type="Export",
			export_format="OpenImmo",
			transfer_scope="VOLL",
			transfer_mode="CHANGE",
			source_type="FTP",
			ftp_transfer_enabled=1,
			record_packaging="Single XML",
			use_jinja_template=0,
			xml_template=None,
			field_mappings=[],
			target_doctype="Property",
			last_sync_at=None,
			send_as_zip=0,
			save_file_by_default=0,
			anbieter_id="ANBIETER-1",
			portal_name="",
			provider_name="Test",
			openimmo_anid="",
			export_file_name=None,
			db_set=MagicMock(),
		)

		original_get_doc = _frappe.get_doc

		def _get_doc_side_effect(doctype, *args, **kwargs):
			if doctype == "Integration Source":
				return source
			return original_get_doc(doctype, *args, **kwargs)

		mock_get_records.return_value = [{"name": "P-001", "modified": "2026-10-28 09:00:00"}]
		mock_quality_gate.return_value = ([{"name": "P-001", "modified": "2026-10-28 09:00:00"}], [])
		mock_deliver.return_value = {"delivery_channel": "FTP", "delivery_status": "failed"}
		mock_create_job.return_value = MagicMock(name="JOB-F-001")

		with patch.object(_frappe, "get_doc", side_effect=_get_doc_side_effect):
			run_export("TEST-SRC-FTP")

		mock_persist.assert_not_called()


# ---------------------------------------------------------------------------
# Deletions must only be marked Withdrawn when the XML carries them
# ---------------------------------------------------------------------------

_XML_WITH_DELETE = """<?xml version="1.0" encoding="UTF-8"?>
<openimmo><anbieter>
<immobilie><verwaltung_techn><openimmo_obid>OBID-CHG</openimmo_obid>
<aktion aktionart="CHANGE"/></verwaltung_techn></immobilie>
<immobilie><verwaltung_techn><objektnr_intern>OBID-DEL</objektnr_intern>
<aktion aktionart="DELETE"/></verwaltung_techn></immobilie>
</anbieter></openimmo>"""

_XML_WITHOUT_DELETE = """<?xml version="1.0" encoding="UTF-8"?>
<openimmo><anbieter>
<immobilie><verwaltung_techn><openimmo_obid>OBID-CHG</openimmo_obid>
<aktion aktionart="CHANGE"/></verwaltung_techn></immobilie>
</anbieter></openimmo>"""


class TestRenderedDeletes(FrappeTestCase):
	def test_finds_delete_obid(self):
		obids = _rendered_delete_obids([{"xml_content": _XML_WITH_DELETE}])
		self.assertEqual(obids, {"OBID-DEL"})

	def test_change_only_has_no_delete(self):
		self.assertEqual(_rendered_delete_obids([{"xml_content": _XML_WITHOUT_DELETE}]), set())

	@patch("openimmo_propms.services.export_engine.frappe.log_error")
	def test_unrendered_delete_is_kept_online_and_logged(self, mock_log):
		source = frappe._dict(name=_SRC)
		kept = _keep_rendered_deletes(
			source, [{"xml_content": _XML_WITHOUT_DELETE}], [("PROP-GONE", "OBID-DEL")]
		)
		self.assertEqual(kept, [])
		mock_log.assert_called_once()
		self.assertEqual(mock_log.call_args.kwargs["title"], f"Portal deletions not rendered: {_SRC}")

	@patch("openimmo_propms.services.export_engine.frappe.log_error")
	def test_rendered_delete_is_kept_for_withdrawal(self, mock_log):
		source = frappe._dict(name=_SRC)
		kept = _keep_rendered_deletes(
			source, [{"xml_content": _XML_WITH_DELETE}], [("PROP-GONE", "OBID-DEL")]
		)
		self.assertEqual(kept, [("PROP-GONE", "OBID-DEL")])
		mock_log.assert_not_called()


class TestTemplateRendersDeletes(FrappeTestCase):
	def test_batch_template_with_delete_loop(self):
		tpl = "{% for d in delete_records %}{{ d.openimmo_obid }}{% endfor %}"
		self.assertTrue(template_renders_deletes(tpl, "Single XML for All Records"))

	def test_batch_template_without_delete_loop(self):
		tpl = "{% for r in all_records %}{{ r.doc.name }}{% endfor %}"
		self.assertFalse(template_renders_deletes(tpl, "Single XML for All Records"))

	def test_separate_packaging_never_renders_deletes(self):
		tpl = "{% for d in delete_records %}{{ d.openimmo_obid }}{% endfor %}"
		self.assertFalse(template_renders_deletes(tpl, "Separate XML per Record"))
