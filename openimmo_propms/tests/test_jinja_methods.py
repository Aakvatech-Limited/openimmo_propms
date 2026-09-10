"""Tests for the Jinja helpers the export templates rely on."""

import datetime

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from openimmo_propms.utils.jinja_methods import (
	format_decimal,
	format_immowelt_date,
	get_document,
	get_value,
)


class TestFormatImmoweltDate(UnitTestCase):
	def test_formats_an_iso_string(self):
		self.assertEqual(format_immowelt_date("2029-05-01"), "05-2029")

	def test_formats_a_date_object(self):
		self.assertEqual(format_immowelt_date(datetime.date(2024, 12, 31)), "12-2024")

	def test_formats_a_datetime_object(self):
		self.assertEqual(format_immowelt_date(datetime.datetime(2024, 1, 2, 3, 4)), "01-2024")

	def test_empty_input_yields_an_empty_string(self):
		self.assertEqual(format_immowelt_date(None), "")
		self.assertEqual(format_immowelt_date(""), "")

	def test_an_unparseable_value_is_returned_as_text(self):
		self.assertEqual(format_immowelt_date("not-a-date"), "not-a-date")


class TestFormatDecimal(UnitTestCase):
	def test_german_decimal_comma(self):
		self.assertEqual(format_decimal("189,0"), "189.0")

	def test_german_thousands_and_decimal(self):
		self.assertEqual(format_decimal("1.200,5"), "1200.5")

	def test_comma_thousands_separator(self):
		self.assertEqual(format_decimal("1,200"), "1200.0")

	def test_plain_number_passes_through(self):
		self.assertEqual(format_decimal("42.5"), "42.5")

	def test_numeric_input(self):
		self.assertEqual(format_decimal(42.5), "42.5")

	def test_empty_input_yields_an_empty_string(self):
		self.assertEqual(format_decimal(None), "")
		self.assertEqual(format_decimal(""), "")

	def test_whitespace_is_trimmed(self):
		self.assertEqual(format_decimal("  189,0  "), "189.0")


class TestDocumentHelpers(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Property Type", "_Test Jinja PT"):
			frappe.get_doc(
				{"doctype": "Property Type", "property_type_name": "_Test Jinja PT", "description": "desc"}
			).insert(ignore_permissions=True)

	def test_get_document_by_name(self):
		doc = get_document("Property Type", "_Test Jinja PT")

		self.assertIsNotNone(doc)
		self.assertEqual(doc.description, "desc")

	def test_get_document_by_filters(self):
		doc = get_document("Property Type", filters={"property_type_name": "_Test Jinja PT"})

		self.assertIsNotNone(doc)
		self.assertEqual(doc.name, "_Test Jinja PT")

	def test_get_document_returns_none_for_a_missing_record(self):
		self.assertIsNone(get_document("Property Type", "_Test Jinja Absent"))

	def test_get_document_returns_none_without_a_doctype(self):
		self.assertIsNone(get_document(None, "x"))

	def test_get_value_accepts_a_name_string(self):
		self.assertEqual(get_value("Property Type", "_Test Jinja PT", "description"), "desc")

	def test_get_value_accepts_a_filter_dict(self):
		self.assertEqual(
			get_value("Property Type", {"property_type_name": "_Test Jinja PT"}, "description"), "desc"
		)

	def test_get_value_returns_none_without_a_doctype(self):
		self.assertIsNone(get_value(None))

	def test_get_value_can_return_a_dict(self):
		row = get_value("Property Type", "_Test Jinja PT", ["name", "description"], as_dict=True)

		self.assertEqual(row.description, "desc")


class TestJinjaHooksAreWired(IntegrationTestCase):
	def test_every_declared_jinja_method_imports(self):
		from frappe.utils.jinja import get_jenv

		jenv = get_jenv()
		for name in ("format_immowelt_date", "format_decimal", "get_document", "get_value"):
			with self.subTest(method=name):
				self.assertIn(name, jenv.globals)

	def test_the_declared_filters_are_registered(self):
		from frappe.utils.jinja import get_jenv

		jenv = get_jenv()
		for name in ("format_immowelt_date", "format_decimal"):
			with self.subTest(filter=name):
				self.assertIn(name, jenv.filters)
