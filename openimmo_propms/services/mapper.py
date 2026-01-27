# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def map_to_crm_lead(applicant_data, xml_meta_data):
    """
    Service: Maps OpenImmo applicant data to the Frappe CRM Lead schema.
    
    :param applicant_data: Dictionary from parser (interessent node)
    :param xml_meta_data: Dictionary containing unique_id, portal_obj_id and oobj_id
    """
    if not applicant_data:
        return None

    # Extraction of IDs for traceability
    unique_id = xml_meta_data.get('unique_id')
    portal_property_id = xml_meta_data.get('portal_obj_id')
    broker_property_id = xml_meta_data.get('oobj_id')
    
    first_name = applicant_data.get('first_name', '')
    last_name = applicant_data.get('last_name', '')

    # Construct the Lead Dictionary matching your FCRM JSON fields
    return {
        "doctype": "CRM Lead",
        "naming_series": "CRM-LEAD-.YYYY.-",
        "salutation": _get_valid_salutation(applicant_data.get('salutation')),
        "first_name": first_name,
        "last_name": last_name,
        "lead_name": f"{first_name} {last_name}".strip(),
        "email": applicant_data.get('email'), # Matching FCRM 'email' field
        "mobile_no": applicant_data.get('mobile') or applicant_data.get('phone'),
        "phone": applicant_data.get('phone'),
        "organization": applicant_data.get('company'),
        "status": "New",
        "source": _ensure_crm_lead_source("OpenImmo Portal"),
        
        # Mapping to your Custom Fields (OpenImmo specific)
        "openimmo_id_key": unique_id,
        "external_property_id": broker_property_id or portal_property_id,
        "portal_source": xml_meta_data.get('portal_name') or "OpenImmo",
        "contact_preference": applicant_data.get('preferred_contact'),
        "inquiry_type": applicant_data.get('request_type'),
        "inquiry_text": applicant_data.get('inquiry')
    }

def find_existing_lead(external_id):
    """
    Utility: Checks for duplicate leads using the Unique OpenImmo Key.
    Essential for Idempotency.
    """
    if not external_id:
        return None
        
    return frappe.db.get_value(
        "CRM Lead", 
        {"openimmo_id_key": external_id}, 
        "name"
    )

def _ensure_crm_lead_source(source_name):
    """
    Utility: Checks and creates a CRM Lead Source if it doesn't exist.
    """
    if not frappe.db.exists("CRM Lead Source", source_name):
        try:
            doc = frappe.get_doc({
                "doctype": "CRM Lead Source",
                "source_name": source_name
            })
            doc.insert(ignore_permissions=True)
        except Exception:
            # Silence error to prevent blocking the whole import
            pass
    return source_name

def _get_valid_salutation(salutation):
    """
    Utility: Matches XML salutation (Frau/Herr) to Frappe Salutation records.
    """
    if salutation and frappe.db.exists("Salutation", salutation):
        return salutation
    return None