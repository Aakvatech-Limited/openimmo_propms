"""Tests for the metadata-driven mapping engine."""

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from openimmo_propms.services.mapper import (
	DuplicateRecordError,
	apply_data_transformation,
	apply_value_mapping,
	cast_value_to_fieldtype,
	evaluate_expression,
	find_recursively,
	get_value_by_json_path,
	handle_link_field,
	map_external_data_to_doctype,
)

from .fixtures import add_field_mapping, make_integration_source

NESTED = {
	"immobilie": {
		"geo": {"ort": "Berlin", "plz": "10115"},
		"kontakt": [{"email": "a@example.com"}, {"email": "b@example.com"}],
	}
}


class TestJsonPathLookup(UnitTestCase):
	def test_reads_a_dotted_path(self):
		self.assertEqual(get_value_by_json_path(NESTED, "immobilie.geo.ort"), "Berlin")

	def test_returns_none_for_an_empty_path(self):
		self.assertIsNone(get_value_by_json_path(NESTED, ""))

	def test_returns_none_when_a_dotted_path_misses(self):
		self.assertIsNone(get_value_by_json_path(NESTED, "immobilie.geo.strasse"))

	def test_falls_back_to_a_recursive_search_for_a_bare_key(self):
		self.assertEqual(get_value_by_json_path(NESTED, "plz"), "10115")

	def test_recursive_search_descends_into_lists(self):
		self.assertEqual(find_recursively(NESTED, "email"), "a@example.com")

	def test_recursive_search_returns_none_for_a_non_dict(self):
		self.assertIsNone(find_recursively("not-a-dict", "email"))


class TestValueMapping(UnitTestCase):
	def test_maps_a_matching_key(self):
		self.assertEqual(apply_value_mapping("EMAIL", "EMAIL=Email\nTEL=Phone"), "Email")

	def test_leaves_an_unmatched_value_untouched(self):
		self.assertEqual(apply_value_mapping("FAX", "EMAIL=Email"), "FAX")

	def test_ignores_rows_without_a_separator(self):
		self.assertEqual(apply_value_mapping("EMAIL", "garbage\nEMAIL=Email"), "Email")

	def test_returns_the_value_when_no_mapping_is_configured(self):
		self.assertEqual(apply_value_mapping("EMAIL", ""), "EMAIL")

	def test_splits_only_on_the_first_separator(self):
		self.assertEqual(apply_value_mapping("K", "K=a=b"), "a=b")


class TestTransformations(UnitTestCase):
	def _mapping(self, **kwargs):
		row = frappe._dict(transformation=None, value_mapping=None, expression_pattern=None)
		row.update(kwargs)
		return row

	def test_upper_case(self):
		self.assertEqual(
			apply_data_transformation("berlin", self._mapping(transformation="Upper Case")), "BERLIN"
		)

	def test_lower_case(self):
		self.assertEqual(
			apply_data_transformation("BERLIN", self._mapping(transformation="Lower Case")), "berlin"
		)

	def test_title_case(self):
		self.assertEqual(
			apply_data_transformation("berlin mitte", self._mapping(transformation="Title Case")),
			"Berlin Mitte",
		)

	def test_integer(self):
		self.assertEqual(apply_data_transformation("42.9", self._mapping(transformation="Integer")), 42)

	def test_float(self):
		self.assertEqual(apply_data_transformation("42.5", self._mapping(transformation="Float")), 42.5)

	def test_value_mapping_runs_after_a_string_transformation(self):
		row = self._mapping(transformation="Upper Case", value_mapping="BERLIN=Hauptstadt")
		self.assertEqual(apply_data_transformation("berlin", row), "BERLIN")

	def test_empty_values_short_circuit(self):
		self.assertEqual(apply_data_transformation("", self._mapping(transformation="Upper Case")), "")


class TestExpressionEvaluation(UnitTestCase):
	def test_substitutes_the_current_value(self):
		self.assertEqual(evaluate_expression("REF-{value}", "99", None), "REF-99")

	def test_substitutes_the_xml_field_alias(self):
		self.assertEqual(evaluate_expression("REF-{xml_field}", "99", None), "REF-99")

	def test_substitutes_date_placeholders(self):
		from frappe.utils import now_datetime

		expected = now_datetime().strftime("%Y")
		self.assertEqual(evaluate_expression("{YYYY}", "x", None), expected)

	def test_substitutes_a_sibling_field_reference(self):
		self.assertEqual(evaluate_expression("{immobilie.geo.ort}", "x", NESTED), "Berlin")

	def test_unknown_references_collapse_to_an_empty_string(self):
		self.assertEqual(evaluate_expression("[{immobilie.geo.strasse}]", "x", NESTED), "[]")


class TestFieldTypeCasting(UnitTestCase):
	def _df(self, fieldtype, options=None):
		return frappe._dict(fieldtype=fieldtype, options=options)

	def test_casts_int(self):
		self.assertEqual(cast_value_to_fieldtype("42", self._df("Int")), 42)

	def test_casts_float(self):
		self.assertEqual(cast_value_to_fieldtype("42.5", self._df("Float")), 42.5)

	def test_casts_currency(self):
		self.assertEqual(cast_value_to_fieldtype("1200.50", self._df("Currency")), 1200.50)

	def test_casts_text_to_string(self):
		self.assertEqual(cast_value_to_fieldtype(42, self._df("Text")), "42")

	def test_leaves_unknown_field_types_alone(self):
		self.assertEqual(cast_value_to_fieldtype("2026-01-01", self._df("Date")), "2026-01-01")


class TestLinkFieldHandling(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_returns_the_value_when_the_linked_record_exists(self):
		if not frappe.db.exists("Property Type", "_Test Link Existing"):
			frappe.get_doc({"doctype": "Property Type", "property_type_name": "_Test Link Existing"}).insert(
				ignore_permissions=True
			)

		self.assertEqual(
			handle_link_field("_Test Link Existing", "Property Type", auto_create=False),
			"_Test Link Existing",
		)

	def test_returns_none_when_the_record_is_missing_and_auto_create_is_off(self):
		self.assertIsNone(handle_link_field("_Test Link Absent", "Property Type", auto_create=False))

	def test_creates_the_record_when_auto_create_is_on(self):
		created = handle_link_field("_Test Link Created", "Property Type", auto_create=True)

		self.assertEqual(created, "_Test Link Created")
		self.assertTrue(frappe.db.exists("Property Type", "_Test Link Created"))

	def test_returns_none_without_a_link_doctype(self):
		self.assertIsNone(handle_link_field("anything", None, auto_create=True))


class TestMappingEngine(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _source(self, name="_Test Mapper Source", **overrides):
		source = make_integration_source(name, **overrides)
		add_field_mapping(source, "objekttitel", "property_type_name", is_unique=1)
		source.save(ignore_permissions=True)
		return source

	def test_maps_an_entry_into_the_target_doctype(self):
		source = self._source()

		name = map_external_data_to_doctype(source.name, {"objekttitel": "_Test Mapped Loft"})

		self.assertEqual(name, "_Test Mapped Loft")
		self.assertTrue(frappe.db.exists("Property Type", "_Test Mapped Loft"))

	def test_raises_duplicate_record_error_for_an_existing_unique_value(self):
		source = self._source()
		map_external_data_to_doctype(source.name, {"objekttitel": "_Test Mapped Dup"})

		with self.assertRaises(DuplicateRecordError) as caught:
			map_external_data_to_doctype(source.name, {"objekttitel": "_Test Mapped Dup"})

		self.assertEqual(caught.exception.record_id, "_Test Mapped Dup")

	def test_applies_the_default_value_when_the_source_field_is_absent(self):
		source = make_integration_source("_Test Mapper Default")
		add_field_mapping(
			source, "objekttitel", "property_type_name", is_unique=1, default_value="_Test Mapped Default"
		)
		source.save(ignore_permissions=True)

		name = map_external_data_to_doctype(source.name, {"other": "x"})

		self.assertEqual(name, "_Test Mapped Default")

	def test_skips_target_fields_that_do_not_exist_on_the_doctype(self):
		source = make_integration_source("_Test Mapper Unknown Field")
		add_field_mapping(source, "objekttitel", "property_type_name", is_unique=1)
		add_field_mapping(source, "whatever", "field_that_does_not_exist")
		source.save(ignore_permissions=True)

		name = map_external_data_to_doctype(
			source.name, {"objekttitel": "_Test Mapped Skip", "whatever": "x"}
		)

		self.assertEqual(name, "_Test Mapped Skip")

	def test_raises_when_a_mandatory_target_field_has_no_source_value(self):
		source = make_integration_source("_Test Mapper Missing Reqd")
		add_field_mapping(source, "objekttitel", "property_type_name", is_unique=1)
		source.save(ignore_permissions=True)

		with self.assertRaises(Exception) as caught:
			map_external_data_to_doctype(source.name, {})

		self.assertIn("missing in the XML data", str(caught.exception))

	def test_a_zero_valued_check_field_is_still_written(self):
		"""cint("0") is falsy, but 0 is a legitimate value for a Check field."""
		source = make_integration_source("_Test Mapper Zero Check")
		add_field_mapping(source, "objekttitel", "property_type_name", is_unique=1)
		add_field_mapping(source, "aktiv", "is_active")
		source.save(ignore_permissions=True)

		name = map_external_data_to_doctype(source.name, {"objekttitel": "_Test Mapped Zero", "aktiv": "0"})

		self.assertEqual(frappe.db.get_value("Property Type", name, "is_active"), 0)
