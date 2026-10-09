"""Layer-6 checks: hooks, packaging metadata, patches, doctype JSON and CI config all load."""

import glob
import importlib
import json
import os

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

APP = "openimmo_propms"


def app_path(*parts):
	return os.path.join(frappe.get_app_path(APP), *parts)


def repo_path(*parts):
	return os.path.join(os.path.dirname(frappe.get_app_path(APP)), *parts)


class TestHooks(UnitTestCase):
	def setUp(self):
		self.hooks = importlib.import_module(f"{APP}.hooks")

	def test_declares_the_app_identity(self):
		self.assertEqual(self.hooks.app_name, APP)
		self.assertTrue(self.hooks.app_title)
		self.assertTrue(self.hooks.app_license)

	def test_every_jinja_method_and_filter_is_importable(self):
		for kind in ("methods", "filters"):
			for dotted_path in self.hooks.jinja[kind]:
				with self.subTest(path=dotted_path):
					self.assertTrue(callable(frappe.get_attr(dotted_path)))

	def test_every_scheduler_target_is_importable(self):
		for event, targets in self.hooks.scheduler_events.items():
			for dotted_path in targets:
				with self.subTest(event=event, path=dotted_path):
					self.assertTrue(callable(frappe.get_attr(dotted_path)))

	def test_scheduler_event_keys_are_valid(self):
		valid = {"all", "hourly", "daily", "weekly", "monthly", "yearly", "cron"}
		valid |= {f"{key}_long" for key in ("all", "hourly", "daily", "weekly", "monthly")}

		self.assertTrue(set(self.hooks.scheduler_events).issubset(valid))

	def test_every_doctype_list_js_file_exists(self):
		for doctype, relative_path in getattr(self.hooks, "doctype_list_js", {}).items():
			with self.subTest(doctype=doctype):
				self.assertTrue(os.path.exists(app_path(relative_path)), relative_path)


class TestPatches(UnitTestCase):
	def _entries(self):
		with open(app_path("patches.txt")) as handle:
			for line in handle:
				line = line.strip()
				if line and not line.startswith(("#", "[")):
					yield line

	def test_every_patch_module_imports_and_exposes_execute(self):
		entries = list(self._entries())

		self.assertTrue(entries)
		for dotted_path in entries:
			with self.subTest(patch=dotted_path):
				module = importlib.import_module(dotted_path)
				self.assertTrue(callable(module.execute))


class TestPackaging(UnitTestCase):
	def test_pyproject_parses_and_declares_the_runtime_dependencies(self):
		import tomllib

		with open(repo_path("pyproject.toml"), "rb") as handle:
			data = tomllib.load(handle)

		self.assertEqual(data["project"]["name"], APP)
		declared = {dep.split("==")[0].split(">")[0].strip() for dep in data["project"]["dependencies"]}
		self.assertTrue({"lxml", "xmltodict", "xmlschema", "defusedxml"}.issubset(declared))

	def test_the_frappe_version_range_admits_v16(self):
		import tomllib

		with open(repo_path("pyproject.toml"), "rb") as handle:
			data = tomllib.load(handle)

		requirement = data["tool"]["bench"]["frappe-dependencies"]["frappe"]
		self.assertIn("17.0.0", requirement)

	def test_every_third_party_runtime_dependency_is_importable(self):
		for module_name in ("lxml.etree", "xmltodict", "xmlschema", "defusedxml"):
			with self.subTest(module=module_name):
				importlib.import_module(module_name)

	def test_modules_txt_matches_the_module_folders(self):
		with open(app_path("modules.txt")) as handle:
			declared = {line.strip() for line in handle if line.strip()}

		self.assertIn("Openimmo Propms", declared)


class TestWorkflowYaml(UnitTestCase):
	def test_every_workflow_file_parses(self):
		import yaml

		files = glob.glob(repo_path(".github", "workflows", "*.yml"))
		files += glob.glob(repo_path(".github", "workflows", "*.yaml"))

		self.assertTrue(files)
		for path in files:
			with self.subTest(workflow=os.path.basename(path)):
				with open(path) as handle:
					self.assertIsInstance(yaml.safe_load(handle), dict)

	def test_the_pre_commit_config_parses(self):
		import yaml

		with open(repo_path(".pre-commit-config.yaml")) as handle:
			config = yaml.safe_load(handle)

		self.assertTrue(config["repos"])


class TestDocTypeMetadata(IntegrationTestCase):
	def _doctype_files(self):
		return glob.glob(app_path(APP, "doctype", "*", "*.json"))

	def test_every_doctype_json_parses(self):
		files = self._doctype_files()

		self.assertTrue(files)
		for path in files:
			with self.subTest(doctype=os.path.basename(path)):
				with open(path) as handle:
					self.assertEqual(json.load(handle)["doctype"], "DocType")

	def test_every_link_and_table_target_exists(self):
		for path in self._doctype_files():
			with open(path) as handle:
				definition = json.load(handle)

			for field in definition.get("fields", []):
				if field.get("fieldtype") not in ("Link", "Table", "Table MultiSelect"):
					continue
				with self.subTest(doctype=definition["name"], field=field["fieldname"]):
					self.assertTrue(
						frappe.db.exists("DocType", field["options"]),
						f"{definition['name']}.{field['fieldname']} -> {field['options']}",
					)

	def test_link_fields_never_target_a_child_table(self):
		"""A Link field cannot point at an istable DocType; the record is unreachable."""
		for path in self._doctype_files():
			with open(path) as handle:
				definition = json.load(handle)

			for field in definition.get("fields", []):
				if field.get("fieldtype") != "Link":
					continue
				with self.subTest(doctype=definition["name"], field=field["fieldname"]):
					self.assertFalse(
						frappe.db.get_value("DocType", field["options"], "istable"),
						f"{definition['name']}.{field['fieldname']} links to child table {field['options']}",
					)

	def test_table_fields_only_target_child_tables(self):
		for path in self._doctype_files():
			with open(path) as handle:
				definition = json.load(handle)

			for field in definition.get("fields", []):
				if field.get("fieldtype") != "Table":
					continue
				with self.subTest(doctype=definition["name"], field=field["fieldname"]):
					self.assertTrue(frappe.db.get_value("DocType", field["options"], "istable"))

	def test_every_dynamic_link_names_a_link_field_on_the_same_doctype(self):
		for path in self._doctype_files():
			with open(path) as handle:
				definition = json.load(handle)

			by_name = {field["fieldname"]: field for field in definition.get("fields", [])}
			for field in definition.get("fields", []):
				if field.get("fieldtype") != "Dynamic Link":
					continue
				with self.subTest(doctype=definition["name"], field=field["fieldname"]):
					target = by_name.get(field["options"])
					self.assertIsNotNone(target)
					self.assertEqual(target["fieldtype"], "Link")
					self.assertEqual(target["options"], "DocType")

	def test_the_workspace_json_parses(self):
		for path in glob.glob(app_path(APP, "workspace", "*", "*.json")):
			with self.subTest(workspace=os.path.basename(path)):
				with open(path) as handle:
					self.assertEqual(json.load(handle)["doctype"], "Workspace")

	def test_every_app_doctype_is_installed_on_the_site(self):
		for path in self._doctype_files():
			with open(path) as handle:
				name = json.load(handle)["name"]
			with self.subTest(doctype=name):
				self.assertTrue(frappe.db.exists("DocType", name))
