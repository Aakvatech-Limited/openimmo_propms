"""Tests for export configuration validation, filter handling and document assembly."""

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from openimmo_propms.services.export_engine import (
	_build_batch_filename,
	_build_export_documents,
	_build_record_filename,
	_build_xml_hash,
	_get_configured_export_filters,
	_get_required_filter_fieldname,
	_merge_filters,
	_normalize_list_filters,
	_normalize_xml_document,
	_sanitize_query_fields,
	_should_save_file,
	_validate_export_source,
	_validate_single_hero_image,
	run_export,
)

from .fixtures import add_field_mapping, make_export_source, make_integration_source


class TestExportSourceValidation(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _source(self, **overrides):
		source = make_export_source("_Test Export Validate", **overrides)
		add_field_mapping(source, "objekttitel", "property_type_name")
		source.save(ignore_permissions=True)
		return source

	def test_accepts_a_well_formed_export_source(self):
		_validate_export_source(self._source())

	def test_rejects_an_import_source(self):
		source = make_integration_source("_Test Export Is Import")

		with self.assertRaises(frappe.ValidationError):
			_validate_export_source(source)

	def test_rejects_a_source_without_field_mappings(self):
		source = make_export_source("_Test Export No Mappings")

		with self.assertRaises(frappe.ValidationError):
			_validate_export_source(source)

	def test_a_jinja_source_needs_no_field_mappings(self):
		source = make_export_source(
			"_Test Export Jinja Only", use_jinja_template=1, xml_template="<openimmo/>"
		)

		_validate_export_source(source)

	def test_rejects_a_template_without_the_record_blocks_placeholder(self):
		source = self._source()
		source.xml_template = "<openimmo></openimmo>"

		with self.assertRaises(frappe.ValidationError):
			_validate_export_source(source)


class TestExportFilters(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_no_configured_filters_yields_an_empty_dict(self):
		source = make_export_source("_Test Filters None")

		self.assertEqual(_get_configured_export_filters(source), {})

	def test_parses_an_object_filter(self):
		source = make_export_source("_Test Filters Object", export_filters_json='{"is_active": 1}')

		self.assertEqual(_get_configured_export_filters(source), {"is_active": 1})

	def test_parses_a_list_filter(self):
		source = make_export_source("_Test Filters List", export_filters_json='[["is_active", "=", 1]]')

		self.assertEqual(_get_configured_export_filters(source), [["is_active", "=", 1]])

	def test_renders_the_today_placeholder(self):
		from frappe.utils import nowdate

		source = make_export_source(
			"_Test Filters Jinja", export_filters_json='{"modified": [">", "{{ today }}"]}'
		)

		self.assertEqual(_get_configured_export_filters(source)["modified"], [">", nowdate()])

	def test_last_sync_at_defaults_to_the_epoch(self):
		source = make_export_source(
			"_Test Filters Sync", export_filters_json='{"modified": [">", "{{ last_sync_at }}"]}'
		)

		self.assertEqual(_get_configured_export_filters(source)["modified"], [">", "1970-01-01 00:00:00"])

	def test_a_bare_list_filter_is_wrapped(self):
		self.assertEqual(_normalize_list_filters(["is_active", "=", 1]), [["is_active", "=", 1]])

	def test_an_already_nested_list_filter_is_left_alone(self):
		self.assertEqual(_normalize_list_filters([["is_active", "=", 1]]), [["is_active", "=", 1]])

	def test_runtime_filters_merge_into_a_dict(self):
		self.assertEqual(_merge_filters({"a": 1}, {"b": 2}), {"a": 1, "b": 2})

	def test_runtime_filters_append_to_a_list(self):
		self.assertEqual(_merge_filters([["a", "=", 1]], {"b": 2}), [["a", "=", 1], ["b", "=", 2]])

	def test_merging_without_runtime_filters_is_a_no_op(self):
		self.assertEqual(_merge_filters({"a": 1}, {}), {"a": 1})

	def test_a_required_filter_fieldname_must_be_configured(self):
		with self.assertRaises(frappe.ValidationError):
			_get_required_filter_fieldname("", "Company Field")

	def test_a_configured_filter_fieldname_is_trimmed(self):
		self.assertEqual(_get_required_filter_fieldname("  company  ", "Company Field"), "company")


class TestExportHelpers(UnitTestCase):
	def test_the_xml_declaration_is_moved_to_the_front(self):
		self.assertTrue(_normalize_xml_document('﻿\n  <?xml version="1.0"?>').startswith("<?xml"))

	def test_normalising_none_yields_an_empty_string(self):
		self.assertEqual(_normalize_xml_document(None), "")

	def test_the_hash_is_stable_and_content_sensitive(self):
		self.assertEqual(_build_xml_hash("<a/>"), _build_xml_hash("<a/>"))
		self.assertNotEqual(_build_xml_hash("<a/>"), _build_xml_hash("<b/>"))

	def test_the_batch_filename_is_slugified(self):
		source = frappe._dict(name="My Source", export_format="OpenImmo")

		self.assertEqual(_build_batch_filename(source), "my_source_openimmo_export.xml")

	def test_the_per_record_filename_carries_the_index(self):
		source = frappe._dict(name="My Source", export_format="Immowelt")

		self.assertEqual(_build_record_filename(source, 3), "my_source_immowelt_export_3.xml")

	def test_blank_query_fields_are_dropped(self):
		self.assertEqual(_sanitize_query_fields(["name", "  ", None, " title "]), ["name", "title"])

	def test_saving_falls_back_to_the_source_default(self):
		self.assertEqual(_should_save_file(frappe._dict(save_file_by_default=1), None), 1)
		self.assertEqual(_should_save_file(frappe._dict(save_file_by_default=0), None), 0)

	def test_an_explicit_save_flag_wins(self):
		self.assertEqual(_should_save_file(frappe._dict(save_file_by_default=0), 1), 1)
		self.assertEqual(_should_save_file(frappe._dict(save_file_by_default=1), 0), 0)


class TestHeroImageValidation(UnitTestCase):
	def test_accepts_a_single_hero_image(self):
		_validate_single_hero_image(
			{"name": "P1", "custom_image_gallery": [{"is_hero_image": 1}, {"is_hero_image": 0}]}
		)

	def test_accepts_a_gallery_without_a_hero_image(self):
		_validate_single_hero_image({"name": "P1", "custom_image_gallery": [{"is_hero_image": 0}]})

	def test_rejects_two_hero_images(self):
		with self.assertRaises(frappe.ValidationError):
			_validate_single_hero_image(
				{"name": "P1", "custom_image_gallery": [{"is_hero_image": 1}, {"is_hero_image": 1}]}
			)

	def test_a_missing_gallery_is_accepted(self):
		_validate_single_hero_image({"name": "P1"})

	def test_a_non_list_gallery_is_ignored(self):
		_validate_single_hero_image({"name": "P1", "custom_image_gallery": "not a list"})


class TestExportDocumentPackaging(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _source(self, packaging):
		source = make_export_source("_Test Packaging", record_packaging=packaging)
		add_field_mapping(source, "objekttitel", "property_type_name")
		source.save(ignore_permissions=True)
		return source

	def _records(self):
		return [
			({"name": "P1", "property_type_name": "P1"}, {"objekttitel": "P1"}),
			({"name": "P2", "property_type_name": "P2"}, {"objekttitel": "P2"}),
		]

	def test_a_batch_export_produces_one_document(self):
		source = self._source("Single XML for All Records")

		documents = _build_export_documents(source, self._records(), {})

		self.assertEqual(len(documents), 1)
		self.assertEqual(documents[0]["record_count"], 2)
		self.assertEqual(documents[0]["filename"], "_test_packaging_openimmo_export.xml")

	def test_a_per_record_export_produces_one_document_per_record(self):
		source = self._source("Separate XML per Record")

		documents = _build_export_documents(source, self._records(), {})

		self.assertEqual(len(documents), 2)
		self.assertEqual([document["record_count"] for document in documents], [1, 1])
		self.assertEqual(documents[0]["filename"], "_test_packaging_openimmo_export_1.xml")


class TestRunExport(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_a_source_with_no_matching_records_throws_for_an_interactive_caller(self):
		source = make_export_source(
			"_Test Run Export Empty",
			export_filters_json='{"property_type_name": "_Test No Such Property Type"}',
		)
		add_field_mapping(source, "objekttitel", "property_type_name")
		source.save(ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError):
			run_export(source.name)

	def test_the_xsd_gate_rejects_a_document_without_an_object_type(self):
		"""OpenImmo requires an objektart tag, so the export must refuse the document.

		A fully compliant export needs a `custom_property_type` custom field on the
		target doctype, which no app on this bench provides, so this covers the gate
		rather than the happy path.
		"""
		if not frappe.db.exists("Property Type", "_Test Export PT"):
			frappe.get_doc({"doctype": "Property Type", "property_type_name": "_Test Export PT"}).insert(
				ignore_permissions=True
			)

		source = make_export_source(
			"_Test Run Export OK",
			name_field="property_type_name",
			openimmo_anid="TEST-ANID",
			export_filters_json='{"property_type_name": "_Test Export PT"}',
		)
		add_field_mapping(source, "objekttitel", "property_type_name")
		source.save(ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError) as caught:
			run_export(source.name)

		self.assertIn("not compliant with XSD", str(caught.exception))
