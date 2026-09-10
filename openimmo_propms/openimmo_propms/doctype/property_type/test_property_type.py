# Copyright (c) 2026, Talib sheikh and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase


class TestPropertyType(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _make(self, name, **overrides):
		values = {"doctype": "Property Type", "property_type_name": name}
		values.update(overrides)
		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		return doc

	def test_is_named_after_the_property_type_name(self):
		doc = self._make("_Test PT Loft")

		self.assertEqual(doc.name, "_Test PT Loft")

	def test_the_name_is_mandatory(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({"doctype": "Property Type"}).insert(ignore_permissions=True)

	def test_names_are_unique(self):
		self._make("_Test PT Unique")

		with self.assertRaises(frappe.DuplicateEntryError):
			self._make("_Test PT Unique")

	def test_supports_a_parent_property_type(self):
		parent = self._make("_Test PT Parent", is_group=1)
		child = self._make("_Test PT Child", parent_property_type=parent.name)

		self.assertEqual(child.parent_property_type, parent.name)

	def test_stores_the_openimmo_classification_triple(self):
		doc = self._make(
			"_Test PT Classified",
			openimmo_objektart="wohnung",
			openimmo_attribute="wohnungtyp",
			openimmo_value="LOFT-STUDIO-ATELIER",
		)

		self.assertEqual(doc.openimmo_objektart, "wohnung")
		self.assertEqual(doc.openimmo_value, "LOFT-STUDIO-ATELIER")

	def test_usage_flags_default_to_off(self):
		doc = self._make("_Test PT Usage")

		self.assertEqual(
			(doc.use_residential, doc.use_commercial, doc.use_investment, doc.use_mixed), (0, 0, 0, 0)
		)
