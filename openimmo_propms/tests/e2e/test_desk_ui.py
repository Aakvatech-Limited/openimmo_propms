"""Browser sweep of the app's desk routes.

Skipped unless OPENIMMO_E2E_BASE_URL is set and Playwright is importable.
"""

import os
import unittest

BASE_URL = os.environ.get("OPENIMMO_E2E_BASE_URL")
ADMIN_PASSWORD = os.environ.get("OPENIMMO_E2E_PASSWORD", "admin")

try:
	from playwright.sync_api import sync_playwright
except ImportError:
	sync_playwright = None

DESK_ROUTES = (
	"/desk/integration-source",
	"/desk/integration-source/new",
	"/desk/integration-job",
	"/desk/property-type",
	"/desk/property-type/new",
	"/desk/openimmo-integration",
)

IGNORED_CONSOLE_PATTERNS = (
	"favicon",
	"Failed to load resource",
	"socket.io",
	"[Report Only]",
)


@unittest.skipUnless(BASE_URL and sync_playwright, "set OPENIMMO_E2E_BASE_URL and install playwright")
class TestDeskRoutes(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls._playwright = sync_playwright().start()
		cls.browser = cls._playwright.chromium.launch(channel="chrome", headless=True)
		cls.context = cls.browser.new_context()
		page = cls.context.new_page()
		page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
		page.fill("#login_email", "Administrator")
		page.fill("#login_password", ADMIN_PASSWORD)
		page.click("button.btn-login")
		page.wait_for_url("**/desk**", timeout=60000, wait_until="commit")
		page.close()

	@classmethod
	def tearDownClass(cls):
		cls.context.close()
		cls.browser.close()
		cls._playwright.stop()

	def _visit(self, route):
		page = self.context.new_page()
		errors = []
		page.on("pageerror", lambda error: errors.append(str(error)))
		page.on(
			"console",
			lambda message: (
				errors.append(message.text)
				if message.type == "error"
				and not any(pattern in message.text for pattern in IGNORED_CONSOLE_PATTERNS)
				else None
			),
		)
		response = page.goto(f"{BASE_URL}{route}", wait_until="domcontentloaded", timeout=60000)
		page.wait_for_timeout(3000)
		status = response.status if response else 0
		page.close()
		return status, errors

	def test_every_desk_route_loads_without_a_console_error(self):
		for route in DESK_ROUTES:
			with self.subTest(route=route):
				status, errors = self._visit(route)
				self.assertLess(status, 400, f"{route} returned {status}")
				self.assertEqual(errors, [], f"{route} logged {errors}")
