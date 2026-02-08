# path/to/openimmo_propms/services/processor.py

import frappe
from openimmo_propms.services.parser import get_dict_from_xml
from openimmo_propms.services.mapper import map_external_data_to_doctype

def run_integration_engine(job_name):
	"""
	Main orchestrator to process an Integration Job.
	"""
	job = frappe.get_doc("Integration Job", job_name)
	source = frappe.get_doc("Integration Source", job.source_name)
	
	try:
		job.db_set("status", "Processing")
		
		# 1. Parse
		data_dict = get_dict_from_xml(job.xml_file)
		
		# 2. Navigate to Root Node
		entries = navigate_to_root_node(data_dict, source.root_node)
		
		if not entries:
			raise Exception(frappe._("No records found at: {0}").format(source.root_node))
		
		if not isinstance(entries, list):
			entries = [entries]

		# 3. Process Mappings
		success_count = 0
		for entry in entries:
			doc_id = map_external_data_to_doctype(source.name, entry)
			if doc_id:
				success_count += 1
		
		job.db_set({
			"status": "Success",
			"log_message": frappe._("Imported {0} records.").format(success_count)
		})
		
	except Exception as e:
		frappe.log_error("Integration Engine Error", frappe.get_traceback())
		job.db_set({
			"status": "Failed", 
			"error_log": str(e)
		})

def navigate_to_root_node(data, path):
	"""Helper to move to the starting data block."""
	if not path: return data
	for key in path.split('.'):
		if isinstance(data, dict):
			data = data.get(key)
		else:
			return None
	return data