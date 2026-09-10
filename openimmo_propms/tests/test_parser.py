"""Tests for the XML parsing service and its file-path resolution."""

import os

import frappe
from frappe.tests import IntegrationTestCase

from openimmo_propms.services.parser import get_absolute_path, get_dict_from_xml

from .fixtures import write_site_file

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<openimmo>
	<anbieter>
		<anbieternr>A-1</anbieternr>
		<immobilie>
			<objektkategorie><objektart><wohnung wohnungtyp="LOFT"/></objektart></objektkategorie>
			<geo><plz>10115</plz><ort>Berlin</ort></geo>
		</immobilie>
	</anbieter>
</openimmo>
"""


class TestParser(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_parses_well_formed_xml_into_a_dict(self):
		file_url, path = write_site_file("_test_parser_ok.xml", SAMPLE_XML)
		self.addCleanup(os.remove, path)

		data = get_dict_from_xml(file_url)

		self.assertEqual(data["openimmo"]["anbieter"]["anbieternr"], "A-1")
		self.assertEqual(data["openimmo"]["anbieter"]["immobilie"]["geo"]["ort"], "Berlin")

	def test_falls_back_to_latin_1_for_non_utf8_payloads(self):
		latin1 = SAMPLE_XML.replace("Berlin", "München").encode("latin-1")
		file_url, path = write_site_file("_test_parser_latin1.xml", latin1)
		self.addCleanup(os.remove, path)

		data = get_dict_from_xml(file_url)

		self.assertEqual(data["openimmo"]["anbieter"]["immobilie"]["geo"]["ort"], "München")

	def test_strips_the_browser_stylesheet_warning(self):
		noisy = "This XML file does not appear to have any style information\n" + SAMPLE_XML
		file_url, path = write_site_file("_test_parser_noisy.xml", noisy)
		self.addCleanup(os.remove, path)

		data = get_dict_from_xml(file_url)

		self.assertEqual(data["openimmo"]["anbieter"]["anbieternr"], "A-1")

	def test_throws_when_the_file_is_missing(self):
		with self.assertRaises(frappe.ValidationError):
			get_dict_from_xml("/files/_test_parser_absent.xml")

	def test_throws_on_malformed_xml(self):
		file_url, path = write_site_file("_test_parser_bad.xml", "<openimmo><unclosed>")
		self.addCleanup(os.remove, path)

		with self.assertRaises(frappe.ValidationError):
			get_dict_from_xml(file_url)

	def test_rejects_xml_entity_declarations(self):
		"""xmltodict must refuse entity definitions so XXE and billion-laughs cannot land."""
		payload = (
			'<?xml version="1.0"?>'
			'<!DOCTYPE openimmo [<!ENTITY xxe SYSTEM "file:///etc/hostname">]>'
			"<openimmo><anbieter>&xxe;</anbieter></openimmo>"
		)
		file_url, path = write_site_file("_test_parser_xxe.xml", payload)
		self.addCleanup(os.remove, path)

		with self.assertRaises(frappe.ValidationError):
			get_dict_from_xml(file_url)


class TestParserPathResolution(IntegrationTestCase):
	"""get_absolute_path must never resolve outside the site's own files directories."""

	def setUp(self):
		self.site_path = os.path.realpath(frappe.get_site_path())

	def assert_inside_site(self, file_url):
		resolved = os.path.realpath(get_absolute_path(file_url))
		self.assertTrue(
			resolved.startswith(self.site_path + os.sep),
			f"{file_url!r} resolved to {resolved!r}, outside {self.site_path!r}",
		)

	def test_resolves_public_files_under_the_site(self):
		self.assert_inside_site("/files/report.xml")

	def test_resolves_private_files_under_the_site(self):
		self.assert_inside_site("/private/files/report.xml")

	def test_rejects_parent_directory_traversal(self):
		self.assert_inside_site("../../../../../../etc/hosts.xml")

	def test_public_url_cannot_reach_the_private_files_directory(self):
		resolved = os.path.realpath(get_absolute_path("/files/../../private/files/secret.xml"))
		private_root = os.path.realpath(frappe.get_site_path("private"))
		self.assertFalse(
			resolved.startswith(private_root + os.sep),
			f"public file URL escaped into the private directory: {resolved!r}",
		)

	def test_embedded_traversal_segments_are_stripped(self):
		self.assert_inside_site("/files/../../../../etc/passwd.xml")
