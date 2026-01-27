# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from openimmo_propms.services.validator import validate_xml_file
from openimmo_propms.services.parser import parse_openimmo_xml
from openimmo_propms.services.mapper import map_to_crm_lead, find_existing_lead

def process_integration_job(job_name):
    """
    Orchestrates the OpenImmo XML import process.
    Focus: CRM Lead creation only.
    """
    job = frappe.get_doc("Integration Job", job_name)
    
    try:
        job.status = "Processing"
        job.save(ignore_permissions=True)
        frappe.db.commit()
        
        # 1. Validation
        is_valid, error_msg = validate_xml_file(job.xml_file)
        if not is_valid:
            job.update_status("Failed", error_msg)
            return
        
        # 2. Parsing
        parsed_data = parse_openimmo_xml(job.xml_file)
        
        # 3. Processing Leads
        stats = _process_leads(job, parsed_data)
        
        # 4. Finalizing Job Status
        job.total_records = stats['total']
        job.successful_records = stats['success']
        job.failed_records = stats['failed']
        job.processed_at = frappe.utils.now()
        
        if stats['failed'] == 0:
            job.status = "Success"
        elif stats['success'] > 0:
            job.status = "Partially Completed"
        else:
            job.status = "Failed"
            job.error_log = _("All lead records failed to process.")
        
        job.save(ignore_permissions=True)
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Integration Job Failed: {job_name}")
        job.status = "Failed"
        job.error_log = str(e)
        job.save(ignore_permissions=True)
        frappe.db.commit()

def _process_leads(job, parsed_data):
    """
    Iterates through applicants and creates CRM Lead records.
    """
    stats = {'total': 0, 'success': 0, 'failed': 0}
    provider_name = parsed_data.get('provider', {}).get('name', 'OpenImmo')
    
    for applicant in parsed_data.get('applicants', []):
        stats['total'] += 1
        try:
            portal_obj_id = applicant.get('property_portal_id')
            email = applicant.get('email')
            
            # Construct a Composite Unique Key: PropertyID_Email
            unique_id = f"{portal_obj_id}_{email}" if portal_obj_id and email else portal_obj_id or email

            # Metadata for mapper
            xml_meta = {
                'unique_id': unique_id,
                'portal_obj_id': portal_obj_id,
                'oobj_id': applicant.get('property_reference'),
                'portal_name': provider_name
            }
            
            # Check for existing lead using the composite unique key
            existing_lead = find_existing_lead(unique_id)
            
            if existing_lead:
                _log_detail(job, 'CRM Lead', existing_lead, 'Skipped', _("Duplicate OpenImmo ID"))
                stats['success'] += 1 # Count as handled
                continue

            # Map to CRM Lead schema
            lead_data = map_to_crm_lead(applicant, xml_meta)
            if not lead_data:
                raise Exception(_("Mapping failed for applicant {0}").format(applicant.get('email')))

            # Create and Insert
            lead_doc = frappe.get_doc(lead_data)
            lead_doc.insert(ignore_permissions=True)
            
            _log_detail(job, 'CRM Lead', lead_doc.name, 'Success')
            stats['success'] += 1
            
        except Exception as e:
            error_trace = frappe.get_traceback()
            frappe.log_error(error_trace, f"Lead Import Error: {job.name}")
            _log_detail(job, 'CRM Lead', None, 'Failed', str(e))
            stats['failed'] += 1
            
    return stats

def _log_detail(job, record_type, record_id, status, error_message=None):
    """Helper to append processing log rows."""
    job.append('processing_details', {
        'record_type': record_type,
        'record_id': record_id,
        'status': status,
        'error_message': error_message
    })