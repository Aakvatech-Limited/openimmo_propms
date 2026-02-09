# path/to/openimmo_propms/services/processor.py

import frappe
from frappe.utils import now_datetime
from openimmo_propms.services.parser import get_dict_from_xml
from openimmo_propms.services.mapper import map_external_data_to_doctype

@frappe.whitelist()
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
		job.total_records = len(entries)
		job.successful_records = 0
		job.failed_records = 0
		job.processing_details = []

		for entry in entries:
			try:
				doc_id = map_external_data_to_doctype(source.name, entry)
				if doc_id:
					job.successful_records += 1
					job.append("processing_details", {
						"record_type": source.target_doctype,
						"record_id": doc_id,
						"status": "Success"
					})
				else:
					job.failed_records += 1
					job.append("processing_details", {
						"record_type": source.target_doctype,
						"status": "Skipped",
						"error_message": "Duplicate or Mapping Issue"
					})
			except Exception as e:
				job.failed_records += 1
				job.append("processing_details", {
					"record_type": source.target_doctype,
					"status": "Failed",
					"error_message": str(e)
				})

		job.status = "Success" if job.failed_records == 0 else ("Failed" if job.successful_records == 0 else "Partially Completed")
		job.processed_at = now_datetime()
		job.log_message = frappe._("Processed {0} records. Success: {1}, Failed: {2}").format(
			job.total_records, job.successful_records, job.failed_records
		)
		job.save()
		
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