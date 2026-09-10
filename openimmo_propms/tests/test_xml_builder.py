"""Tests for dotted-path XML construction and the OpenImmo envelope."""

from frappe.tests import UnitTestCase
from lxml import etree

from openimmo_propms.services.xml_builder import (
	_escape_xml,
	build_openimmo_document,
	ensure_xml_path,
	render_xml_template,
	set_xml_value,
)


class TestEnsureXmlPath(UnitTestCase):
	def test_creates_nested_elements(self):
		root = etree.Element("immobilie")

		node, attr = ensure_xml_path(root, "geo.plz")

		self.assertEqual(node.tag, "plz")
		self.assertIsNone(attr)
		self.assertIsNotNone(root.find("geo/plz"))

	def test_reuses_an_existing_element(self):
		root = etree.Element("immobilie")
		ensure_xml_path(root, "geo.plz")
		ensure_xml_path(root, "geo.ort")

		self.assertEqual(len(root.findall("geo")), 1)

	def test_returns_a_trailing_attribute_name(self):
		root = etree.Element("immobilie")

		node, attr = ensure_xml_path(root, "geo.land@iso_land")

		self.assertEqual(node.tag, "land")
		self.assertEqual(attr, "iso_land")

	def test_creates_indexed_siblings(self):
		root = etree.Element("immobilie")
		ensure_xml_path(root, "bewertung.feld.1.name")

		self.assertEqual(len(root.findall("bewertung/feld")), 2)

	def test_an_indexed_path_can_carry_an_attribute(self):
		root = etree.Element("immobilie")

		node, attr = ensure_xml_path(root, "anhaenge.anhang.0@location")

		self.assertEqual(node.tag, "anhang")
		self.assertEqual(attr, "location")


class TestSetXmlValue(UnitTestCase):
	def test_sets_element_text(self):
		root = etree.Element("immobilie")

		set_xml_value(root, "geo.ort", "Berlin")

		self.assertEqual(root.findtext("geo/ort"), "Berlin")

	def test_sets_an_attribute(self):
		root = etree.Element("immobilie")

		set_xml_value(root, "geo.land@iso_land", "DEU")

		self.assertEqual(root.find("geo/land").get("iso_land"), "DEU")

	def test_renders_booleans_in_openimmo_style(self):
		root = etree.Element("immobilie")

		set_xml_value(root, "ausstattung.balkon", True)
		set_xml_value(root, "ausstattung.keller", False)

		self.assertEqual(root.findtext("ausstattung/balkon"), "true")
		self.assertEqual(root.findtext("ausstattung/keller"), "false")

	def test_none_writes_nothing(self):
		root = etree.Element("immobilie")

		set_xml_value(root, "geo.ort", None)

		self.assertIsNone(root.find("geo"))

	def test_numbers_are_stringified(self):
		root = etree.Element("immobilie")

		set_xml_value(root, "preise.kaufpreis", 1200.5)

		self.assertEqual(root.findtext("preise/kaufpreis"), "1200.5")


class TestBuildOpenimmoDocument(UnitTestCase):
	def _document(self, properties, **kwargs):
		xml = build_openimmo_document("A-1", properties, **kwargs)
		return xml, etree.fromstring(xml.encode("utf-8"))

	def test_wraps_property_nodes_in_the_envelope(self):
		node = etree.Element("immobilie")
		etree.SubElement(node, "objekttitel").text = "Loft"

		_xml, root = self._document([node])

		self.assertEqual(root.tag, "openimmo")
		self.assertEqual(root.findtext("anbieter/anbieternr"), "A-1")
		self.assertEqual(root.findtext("anbieter/immobilie/objekttitel"), "Loft")

	def test_sets_the_transfer_attributes(self):
		_xml, root = self._document([], transfer_scope="TEIL", transfer_mode="DELETE", portal_name="Immowelt")
		uebertragung = root.find("uebertragung")

		self.assertEqual(uebertragung.get("umfang"), "TEIL")
		self.assertEqual(uebertragung.get("modus"), "DELETE")
		self.assertEqual(uebertragung.get("portal"), "Immowelt")
		self.assertEqual(uebertragung.get("art"), "ONLINE")

	def test_defaults_the_transfer_scope_to_voll(self):
		_xml, root = self._document([])

		self.assertEqual(root.find("uebertragung").get("umfang"), "VOLL")

	def test_emits_an_xml_declaration(self):
		xml, _root = self._document([])

		self.assertTrue(xml.startswith("<?xml"))

	def test_accepts_a_property_node_given_as_a_string(self):
		_xml, root = self._document(["<immobilie><objekttitel>Villa</objekttitel></immobilie>"])

		self.assertEqual(root.findtext("anbieter/immobilie/objekttitel"), "Villa")

	def test_a_malformed_property_string_does_not_break_the_document(self):
		_xml, root = self._document(["<immobilie><unclosed>"])

		self.assertEqual(root.tag, "openimmo")


class TestTemplateRendering(UnitTestCase):
	def test_substitutes_placeholders(self):
		self.assertEqual(render_xml_template("<a>{{ ort }}</a>", {"ort": "Berlin"}), "<a>Berlin</a>")

	def test_unknown_placeholders_become_empty(self):
		self.assertEqual(render_xml_template("<a>{{ nope }}</a>", {}), "<a></a>")

	def test_values_are_xml_escaped(self):
		rendered = render_xml_template("<a>{{ ort }}</a>", {"ort": "Berlin & <Mitte>"})

		self.assertEqual(rendered, "<a>Berlin &amp; &lt;Mitte&gt;</a>")

	def test_escape_handles_none(self):
		self.assertEqual(_escape_xml(None), "")

	def test_escape_covers_quotes(self):
		self.assertEqual(_escape_xml('a"b'), "a&quot;b")
