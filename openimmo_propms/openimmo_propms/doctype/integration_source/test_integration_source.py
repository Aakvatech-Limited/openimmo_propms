# Copyright (c) 2025, Talib sheikh and Contributors
# See license.txt

from types import SimpleNamespace

import frappe
from frappe.tests import IntegrationTestCase
from lxml import etree

from openimmo_propms.services.export_engine import _append_image_attachment, _requires_full_doc
from openimmo_propms.tests.fixtures import add_field_mapping, make_export_source, make_integration_source


class TestIntegrationSourceValidation(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_status_tracks_the_enabled_flag(self):
		enabled = make_integration_source("_Test Source Enabled", enabled=1)
		disabled = make_integration_source("_Test Source Disabled", enabled=0)

		self.assertEqual(enabled.status, "Active")
		self.assertEqual(disabled.status, "Inactive")

	def test_an_api_source_requires_an_endpoint(self):
		with self.assertRaises(frappe.ValidationError):
			make_integration_source("_Test Source API", source_type="API")

	def test_an_ftp_source_requires_a_host_and_username(self):
		with self.assertRaises(frappe.ValidationError):
			make_integration_source("_Test Source FTP", source_type="FTP", ftp_host="ftp.example.com")

	def test_an_email_source_requires_an_email_account(self):
		with self.assertRaises(frappe.ValidationError):
			make_integration_source("_Test Source Email", source_type="Email")

	def test_the_target_doctype_must_exist(self):
		with self.assertRaises(frappe.ValidationError):
			make_integration_source("_Test Source Bad Target", target_doctype="No Such DocType")

	def test_an_openimmo_export_requires_an_anbieter_id(self):
		with self.assertRaises(frappe.ValidationError):
			make_export_source("_Test Export No Anbieter", anbieter_id=None)

	def test_the_export_format_falls_back_to_the_doctype_default(self):
		source = make_export_source("_Test Export No Format", export_format=None)

		self.assertEqual(source.export_format, "OpenImmo")

	def test_transfer_defaults_come_from_the_doctype(self):
		source = make_export_source("_Test Export Defaults", transfer_scope=None, transfer_mode=None)

		self.assertEqual(source.transfer_scope, "TEIL")
		self.assertEqual(source.transfer_mode, "CHANGE")

	def test_export_filters_json_must_parse(self):
		with self.assertRaises(frappe.ValidationError):
			make_export_source("_Test Export Bad JSON", export_filters_json="{not json")

	def test_export_filters_json_must_be_an_object_or_list(self):
		with self.assertRaises(frappe.ValidationError):
			make_export_source("_Test Export Scalar JSON", export_filters_json='"a string"')

	def test_export_filters_json_accepts_an_object(self):
		source = make_export_source("_Test Export Good JSON", export_filters_json='{"is_active": 1}')

		self.assertTrue(source.name)

	def test_a_delete_export_requires_the_identifier_mappings(self):
		with self.assertRaises(frappe.ValidationError):
			make_export_source("_Test Export Delete", transfer_mode="DELETE")

	def test_a_delete_export_passes_with_the_identifier_mappings(self):
		source = make_export_source("_Test Export Delete OK", transfer_mode="CHANGE")
		for path in (
			"verwaltung_techn.objektnr_intern",
			"verwaltung_techn.objektnr_extern",
			"verwaltung_techn.openimmo_obid",
		):
			add_field_mapping(source, path, "name")
		source.transfer_mode = "DELETE"
		source.save(ignore_permissions=True)

		self.assertEqual(source.transfer_mode, "DELETE")

	def test_an_invalid_jinja_template_is_rejected(self):
		with self.assertRaises(Exception):
			make_export_source("_Test Export Bad Jinja", use_jinja_template=1, xml_template="{% for x in %}")


class TestExportImageAttachments(IntegrationTestCase):
	def _source(self, **overrides):
		values = {
			"image_field": "main_picture",
			"child_image_field": "child_pictures.image",
			"parent_image_field": "parent_pictures.image",
			"fallback_image_field": "property_type_symbol",
			"image_group": "TITELBILD",
			"image_location": "EXTERN",
			"base_media_url": "https://example.com",
			"target_doctype": "Property",
			"field_mappings": [],
		}
		values.update(overrides)
		return SimpleNamespace(**values)

	def test_attachments_follow_the_main_child_parent_order(self):
		record = {
			"main_picture": "/files/main.jpg",
			"child_pictures": [{"image": "/files/child-1.jpg"}, {"image": "/files/child-2.jpg"}],
			"parent_pictures": [{"image": "/files/parent-1.jpg"}],
			"property_type_symbol": "/files/symbol.jpg",
		}
		immobilie = etree.Element("immobilie")

		_append_image_attachment(self._source(), record, immobilie)

		self.assertEqual(
			[node.findtext("daten/pfad") for node in immobilie.findall("./anhaenge/anhang")],
			[
				"https://example.com/files/main.jpg",
				"https://example.com/files/child-1.jpg",
				"https://example.com/files/child-2.jpg",
				"https://example.com/files/parent-1.jpg",
			],
		)

	def test_the_fallback_image_is_used_when_nothing_else_exists(self):
		record = {
			"main_picture": None,
			"child_pictures": [],
			"parent_pictures": [],
			"property_type_symbol": "/files/symbol.jpg",
		}
		immobilie = etree.Element("immobilie")

		_append_image_attachment(self._source(), record, immobilie)

		attachments = immobilie.findall("./anhaenge/anhang")
		self.assertEqual(len(attachments), 1)
		self.assertEqual(attachments[0].findtext("daten/pfad"), "https://example.com/files/symbol.jpg")

	def test_no_attachment_node_is_added_without_images(self):
		record = {
			"main_picture": None,
			"child_pictures": [],
			"parent_pictures": [],
			"property_type_symbol": None,
		}
		immobilie = etree.Element("immobilie")

		_append_image_attachment(self._source(), record, immobilie)

		self.assertEqual(immobilie.findall("./anhaenge/anhang"), [])

	def test_dotted_image_fields_require_the_full_document(self):
		source = self._source(parent_image_field=None, fallback_image_field=None)

		self.assertTrue(_requires_full_doc(source))

	def test_plain_image_fields_do_not_require_the_full_document(self):
		source = self._source(child_image_field=None, parent_image_field=None, fallback_image_field=None)

		self.assertFalse(_requires_full_doc(source))
