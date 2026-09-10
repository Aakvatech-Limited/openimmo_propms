"""Tests for XML structural and XSD validation."""

import os

import frappe
from frappe.tests import IntegrationTestCase

from openimmo_propms.services.validator import (
	_get_absolute_path,
	validate_xml_against_xsd,
	validate_xml_file,
)

from .fixtures import write_site_file

VALID = """<?xml version="1.0" encoding="UTF-8"?>
<openimmo><anbieter><anbieternr>A-1</anbieternr></anbieter></openimmo>
"""

NO_REQUIRED_ELEMENTS = """<?xml version="1.0" encoding="UTF-8"?>
<openimmo><nichts/></openimmo>
"""

NOT_OPENIMMO = """<?xml version="1.0" encoding="UTF-8"?>
<katalog><eintrag/></katalog>
"""


class TestValidateXmlFile(IntegrationTestCase):
	def _write(self, name, content):
		file_url, path = write_site_file(name, content)
		self.addCleanup(os.remove, path)
		return file_url

	def test_accepts_a_valid_openimmo_document(self):
		valid, message = validate_xml_file(self._write("_test_val_ok.xml", VALID))

		self.assertTrue(valid, message)
		self.assertEqual(message, "")

	def test_rejects_a_missing_file(self):
		valid, message = validate_xml_file("/files/_test_val_absent.xml")

		self.assertFalse(valid)
		self.assertIn("File not found", message)

	def test_rejects_malformed_xml(self):
		valid, message = validate_xml_file(self._write("_test_val_bad.xml", "<openimmo><unclosed>"))

		self.assertFalse(valid)
		self.assertIn("Invalid XML format", message)

	def test_rejects_a_document_that_is_not_openimmo(self):
		valid, message = validate_xml_file(self._write("_test_val_other.xml", NOT_OPENIMMO))

		self.assertFalse(valid)
		self.assertIn("Not a valid OpenImmo", message)

	def test_rejects_a_document_without_required_elements(self):
		valid, message = validate_xml_file(self._write("_test_val_empty.xml", NO_REQUIRED_ELEMENTS))

		self.assertFalse(valid)
		self.assertIn("Missing required OpenImmo elements", message)

	def test_does_not_expand_external_entities(self):
		"""An XXE payload must not leak file contents through the validator."""
		_secret_url, secret_path = write_site_file("_test_val_secret.txt", "TOP-SECRET-VALUE")
		self.addCleanup(os.remove, secret_path)

		payload = (
			'<?xml version="1.0"?>'
			f'<!DOCTYPE openimmo [<!ENTITY xxe SYSTEM "file://{secret_path}">]>'
			"<openimmo><anbieter><anbieternr>&xxe;</anbieternr></anbieter></openimmo>"
		)
		file_url = self._write("_test_val_xxe.xml", payload)

		_valid, message = validate_xml_file(file_url)

		self.assertNotIn("TOP-SECRET-VALUE", message)


class TestValidatorPathResolution(IntegrationTestCase):
	def setUp(self):
		self.site_path = os.path.realpath(frappe.get_site_path())

	def assert_inside_site(self, file_url):
		resolved = os.path.realpath(_get_absolute_path(file_url))
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

	def test_rejects_traversal_embedded_in_a_public_url(self):
		self.assert_inside_site("/files/../../../../etc/passwd.xml")


class TestXsdValidation(IntegrationTestCase):
	def test_reports_a_missing_schema_file(self):
		valid, message = validate_xml_against_xsd("<openimmo/>", "_does_not_exist.xsd")

		self.assertFalse(valid)
		self.assertIn("XSD file not found", message)

	def test_rejects_a_document_that_violates_the_schema(self):
		valid, message = validate_xml_against_xsd("<openimmo><bogus/></openimmo>")

		self.assertFalse(valid)
		self.assertTrue(message)

	def test_the_shipped_schema_loads(self):
		import xmlschema

		xsd_path = frappe.get_app_path("openimmo_propms", "templates", "xsd", "openimmo_127c.xsd")

		self.assertTrue(os.path.exists(xsd_path))
		self.assertTrue(xmlschema.XMLSchema(xsd_path).is_valid("<openimmo/>") in (True, False))
