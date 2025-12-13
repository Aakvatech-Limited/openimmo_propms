# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
import os


class IntegrationJob(Document):
    def validate(self):
        self._validate_file_extension()
        self._set_file_name()
    
    def on_update(self):
        if self._should_trigger_processing():
            self.flags.ignore_processing = 1
            self._process_job()
    
    def _validate_file_extension(self):
        if not self.xml_file:
            return
        
        file_ext = self.xml_file.lower().split('.')[-1]
        if file_ext != 'xml':
            frappe.throw(_("Only XML files are allowed"))
    
    def _set_file_name(self):
        if self.xml_file and not self.file_name:
            self.file_name = os.path.basename(self.xml_file)
    
    def _should_trigger_processing(self):
        return (
            self.xml_file 
            and self.status == "Pending" 
            and not self.flags.get('ignore_processing')
        )
    
    def _process_job(self):
        try:
            from openimmo_propms.services.processor import process_integration_job
            frappe.msgprint(_("Processing started..."), alert=True, indicator='blue')
            process_integration_job(self.name)
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Integration Job Auto-Process Failed")
            frappe.msgprint(_("Processing failed. Check Error Log."), alert=True, indicator='red')
    
    def update_status(self, status, error_msg=None):
        self.status = status
        if error_msg:
            self.error_log = error_msg
        if status in ["Success", "Failed", "Partially Completed"]:
            self.processed_at = frappe.utils.now()
        self.save(ignore_permissions=True)
        frappe.db.commit()
    
    def add_processing_detail(self, record_type, record_id, status, error_msg=None):
        self.append('processing_details', {
            'record_type': record_type,
            'record_id': record_id,
            'status': status,
            'error_message': error_msg
        })


# Standalone function for button action
@frappe.whitelist()
def process_now(doc):
    """Process integration job - called from button"""
    import json
    
    # Parse doc if it's a string
    if isinstance(doc, str):
        doc = json.loads(doc)
    
    job_name = doc.get('name')
    
    if not job_name:
        frappe.throw(_("Job name not provided"))
    
    job = frappe.get_doc("Integration Job", job_name)
    
    if not job.xml_file:
        frappe.throw(_("Please attach an XML file first"))
    
    if job.status not in ["Pending", "Failed"]:
        frappe.throw(_("Only Pending or Failed jobs can be processed"))
    
    from openimmo_propms.services.processor import process_integration_job
    
    try:
        process_integration_job(job.name)
        job.reload()
        
        frappe.msgprint(
            _("Processing completed! Total: {0}, Success: {1}, Failed: {2}").format(
                job.total_records, job.successful_records, job.failed_records
            ), 
            alert=True, 
            indicator='green' if job.failed_records == 0 else 'orange'
        )
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Integration Job Processing Failed - {job.name}")
        frappe.msgprint(_("Processing failed: {0}").format(str(e)), alert=True, indicator='red')
        raise
    
    return True