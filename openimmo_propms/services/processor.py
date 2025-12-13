# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from openimmo_propms.services.validator import validate_xml_file
from openimmo_propms.services.parser import parse_openimmo_xml
from openimmo_propms.services.mapper import (
    map_to_property, map_to_lead,
    find_existing_property, find_existing_lead
)


def process_integration_job(job_name):
    """Main processing function - orchestrates the entire workflow"""
    job = frappe.get_doc("Integration Job", job_name)
    
    try:
        job.status = "Processing"
        job.save(ignore_permissions=True)
        frappe.db.commit()
        
        # Validate XML
        is_valid, error_msg = validate_xml_file(job.xml_file)
        if not is_valid:
            job.update_status("Failed", error_msg)
            return
        
        # Parse XML
        parsed_data = parse_openimmo_xml(job.xml_file)
        
        # Process records
        stats = _process_records(job, parsed_data)
        
        # Update job results
        job.total_records = stats['total']
        job.successful_records = stats['success']
        job.failed_records = stats['failed']
        job.processed_at = frappe.utils.now()
        
        # Set final status
        if stats['failed'] == 0:
            job.status = "Success"
        elif stats['success'] > 0:
            job.status = "Partially Completed"
        else:
            job.status = "Failed"
            job.error_log = "All records failed to process"
        
        job.save(ignore_permissions=True)
        frappe.db.commit()
        
        frappe.msgprint(_("Job processed: {0} successful, {1} failed").format(
            stats['success'], stats['failed']
        ), alert=True)
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Integration Job Failed - {job_name}")
        job.status = "Failed"
        job.error_log = str(e)
        job.save(ignore_permissions=True)
        frappe.db.commit()


def _process_records(job, parsed_data):
    """Process all records from parsed data"""
    stats = {'total': 0, 'success': 0, 'failed': 0}
    property_names = {}
    
    # Process Properties
    for property_data in parsed_data.get('properties', []):
        stats['total'] += 1
        try:
            property_name = _create_or_update_property(property_data, job.source_name)
            
            row = job.append('processing_details', {})
            row.record_type = 'Property'
            row.record_id = property_name
            row.status = 'Success'
            
            stats['success'] += 1
            
            # Store for lead linking
            external_id = property_data.get('external_id')
            if external_id:
                property_names[external_id] = property_name
                
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Property Processing Error - {job.name}")
            
            row = job.append('processing_details', {})
            row.record_type = 'Property'
            row.status = 'Failed'
            row.error_message = str(e)
            
            stats['failed'] += 1
    
    # Process Leads
    for applicant_data in parsed_data.get('applicants', []):
        stats['total'] += 1
        try:
            # Get linked property name
            property_ref = applicant_data.get('property_reference')
            linked_property = property_names.get(property_ref)
            
            lead_name = _create_or_update_lead(applicant_data, job.source_name, linked_property)
            
            row = job.append('processing_details', {})
            row.record_type = 'Lead'
            row.record_id = lead_name
            row.status = 'Success'
            
            stats['success'] += 1
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Lead Processing Error - {job.name}")
            
            row = job.append('processing_details', {})
            row.record_type = 'Lead'
            row.status = 'Failed'
            row.error_message = str(e)
            
            stats['failed'] += 1
    
    return stats


def _create_or_update_property(property_data, source_name):
    """Create or update property record"""
    external_id = property_data.get('external_id')
    existing = find_existing_property(external_id)
    
    mapped_data = map_to_property(property_data, source_name)
    
    if not mapped_data:
        raise Exception("Property mapping failed")
    
    if existing:
        doc = frappe.get_doc('Property', existing)
        for key, value in mapped_data.items():
            if key != 'doctype' and value is not None:
                doc.set(key, value)
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc(mapped_data)
        doc.insert(ignore_permissions=True)
    
    frappe.db.commit()
    return doc.name


def _create_or_update_lead(applicant_data, source_name, property_name=None):
    """Create or update Lead record"""
    email = applicant_data.get('email')
    existing = find_existing_lead(email)
    
    mapped_data = map_to_lead(applicant_data, source_name, property_name)
    
    if not mapped_data:
        raise Exception("Lead mapping failed")
    
    if existing:
        # Update existing lead
        doc = frappe.get_doc('Lead', existing)
        
        # Safely update fields - REMOVED 'notes' from list
        safe_update_fields = [
            'first_name', 'last_name', 'lead_name', 'email_id',
            'mobile_no', 'phone', 'company_name', 'salutation',
            'source', 'type'
        ]
        
        # Add custom fields
        custom_fields = ['property_interest', 'portal_source', 'contact_preference', 
                        'inquiry_type', 'inquiry_text']
        
        for field in safe_update_fields + custom_fields:
            if field in mapped_data and mapped_data[field] is not None:
                if hasattr(doc, field):
                    setattr(doc, field, mapped_data[field])
        
        doc.save(ignore_permissions=True)
        
    else:
        # Create new lead using frappe.new_doc
        doc = frappe.new_doc('Lead')
        
        # Set standard fields
        doc.lead_name = mapped_data.get('lead_name', 'Unknown Lead')
        doc.type = mapped_data.get('type', 'Client')
        doc.source = mapped_data.get('source', 'OpenImmo Portal')
        
        if mapped_data.get('first_name'):
            doc.first_name = mapped_data['first_name']
        
        if mapped_data.get('last_name'):
            doc.last_name = mapped_data['last_name']
        
        if mapped_data.get('email_id'):
            doc.email_id = mapped_data['email_id']
        
        if mapped_data.get('mobile_no'):
            doc.mobile_no = mapped_data['mobile_no']
        
        if mapped_data.get('phone'):
            doc.phone = mapped_data['phone']
        
        if mapped_data.get('company_name'):
            doc.company_name = mapped_data['company_name']
        
        if mapped_data.get('salutation'):
            doc.salutation = mapped_data['salutation']
        
        # Set custom fields if they exist
        if hasattr(doc, 'property_interest') and mapped_data.get('property_interest'):
            doc.property_interest = mapped_data['property_interest']
        
        if hasattr(doc, 'portal_source') and mapped_data.get('portal_source'):
            doc.portal_source = mapped_data['portal_source']
        
        if hasattr(doc, 'contact_preference') and mapped_data.get('contact_preference'):
            doc.contact_preference = mapped_data['contact_preference']
        
        if hasattr(doc, 'inquiry_type') and mapped_data.get('inquiry_type'):
            doc.inquiry_type = mapped_data['inquiry_type']
        
        if hasattr(doc, 'inquiry_text') and mapped_data.get('inquiry_text'):
            doc.inquiry_text = mapped_data['inquiry_text']
        
        doc.insert(ignore_permissions=True)
    
    frappe.db.commit()
    return doc.name
