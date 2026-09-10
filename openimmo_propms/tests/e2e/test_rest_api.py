"""REST-level checks against a served site.

Skipped unless OPENIMMO_E2E_BASE_URL is set, so the framework runner stays green
on a bench with no HTTP worker.
"""

import os
import re
import unittest

import requests

BASE_URL = os.environ.get("OPENIMMO_E2E_BASE_URL")
ADMIN_PASSWORD = os.environ.get("OPENIMMO_E2E_PASSWORD", "admin")

ENDPOINTS = (
	"openimmo_propms.api.export.get_default_template",
	"openimmo_propms.api.export.run_openimmo_export",
	"openimmo_propms.api.export.preview_jinja_xml",
	"openimmo_propms.api.server_script.import_lead_xml",
	"openimmo_propms.services.processor.run_integration_engine",
	"openimmo_propms.services.sync_engine.execute_sync",
	"openimmo_propms.services.sync_engine.test_integration_connection",
)


@unittest.skipUnless(BASE_URL, "set OPENIMMO_E2E_BASE_URL to run the REST suite")
class TestRestApi(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.session = requests.Session()
		response = cls.session.post(
			f"{BASE_URL}/api/method/login",
			data={"usr": "Administrator", "pwd": ADMIN_PASSWORD},
			timeout=30,
		)
		response.raise_for_status()
		cls.csrf_token = cls._read_csrf_token()

	@classmethod
	def _read_csrf_token(cls):
		page = cls.session.get(f"{BASE_URL}/desk", timeout=30).text
		match = re.search(r'frappe\.csrf_token\s*=\s*"([^"]+)"', page)
		return match.group(1) if match else None

	def post(self, method, **payload):
		return self.session.post(
			f"{BASE_URL}/api/method/{method}",
			json=payload,
			headers={"X-Frappe-CSRF-Token": self.csrf_token or ""},
			timeout=60,
		)

	def test_the_desk_route_is_reachable(self):
		response = self.session.get(f"{BASE_URL}/desk", timeout=30)

		self.assertEqual(response.status_code, 200)

	def test_the_legacy_app_route_redirects_to_desk(self):
		response = self.session.get(f"{BASE_URL}/app", timeout=30, allow_redirects=False)

		self.assertIn(response.status_code, (301, 302, 308))
		self.assertIn("/desk", response.headers.get("Location", ""))

	def test_a_csrf_token_is_available_on_the_desk_page(self):
		self.assertTrue(self.csrf_token)

	def test_the_default_template_endpoint_returns_xml(self):
		response = self.post(
			"openimmo_propms.api.export.get_default_template", template_name="OpenImmo 1.2.7"
		)

		self.assertEqual(response.status_code, 200)
		self.assertIn("openimmo", response.json()["message"])

	def test_an_unknown_template_is_rejected(self):
		response = self.post(
			"openimmo_propms.api.export.get_default_template", template_name="No Such Template"
		)

		self.assertIn(response.status_code, (417, 500))

	def test_every_endpoint_refuses_an_anonymous_caller(self):
		anonymous = requests.Session()
		for method in ENDPOINTS:
			with self.subTest(endpoint=method):
				response = anonymous.post(f"{BASE_URL}/api/method/{method}", json={}, timeout=30)
				self.assertIn(response.status_code, (401, 403))

	def test_the_integration_source_list_is_reachable(self):
		response = self.session.get(
			f"{BASE_URL}/api/resource/Integration Source", params={"limit_page_length": 1}, timeout=30
		)

		self.assertEqual(response.status_code, 200)
		self.assertIn("data", response.json())

	def test_the_integration_job_list_is_reachable(self):
		response = self.session.get(
			f"{BASE_URL}/api/resource/Integration Job", params={"limit_page_length": 1}, timeout=30
		)

		self.assertEqual(response.status_code, 200)
