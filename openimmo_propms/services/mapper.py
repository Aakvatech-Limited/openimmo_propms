# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def map_to_property(property_data, source_name):
    """Map OpenImmo property data to PropMS Property DocType"""
    if not property_data:
        return None
    
    # Get default company from Global Defaults
    company = frappe.db.get_single_value('Global Defaults', 'default_company')
    if not company:
        company = frappe.db.get_value('Company', {'disabled': 0}, 'name')
    
    # Get cost center
    cost_center = frappe.db.get_value('Company', company, 'cost_center')
    
    return {
        'doctype': 'Property',
        'name1': property_data.get('title'),
        'company': company,
        'cost_center': cost_center,
        'external_reference': property_data.get('external_id'),
        'portal_listing_id': property_data.get('portal_id'),
        'portal_url': property_data.get('expose_url'),
        'marketing_type': property_data.get('marketing_type'),
        'property_street': property_data.get('street'),
        'property_city': property_data.get('city'),
        'description': property_data.get('title', '')
    }


def map_to_lead(applicant_data, source_name, property_name=None):
    """Map OpenImmo applicant to Lead DocType"""
    if not applicant_data:
        return None
    
    source_doc = frappe.get_doc("Integration Source", source_name)
    
    email = applicant_data.get('email')
    first_name = applicant_data.get('first_name', '')
    last_name = applicant_data.get('last_name', '')
    salutation = applicant_data.get('salutation')
    
    lead_name = f"{first_name} {last_name}".strip() or email
    
    # Ensure salutation exists
    valid_salutation = _ensure_salutation_exists(salutation)
    
    # Ensure source exists
    _ensure_lead_source_exists('OpenImmo Portal')
    
    return {
        'doctype': 'Lead',
        'first_name': first_name,
        'last_name': last_name,
        'lead_name': lead_name,
        'email_id': email,
        'mobile_no': applicant_data.get('mobile') or applicant_data.get('phone'),
        'phone': applicant_data.get('phone'),
        'company_name': applicant_data.get('company'),
        'salutation': valid_salutation,
        'source': 'OpenImmo Portal',
        'type': 'Client',
        'property_interest': property_name,
        'portal_source': source_doc.provider_name,
        'contact_preference': applicant_data.get('preferred_contact'),
        'inquiry_type': applicant_data.get('request_type'),
        'inquiry_text': applicant_data.get('inquiry')
    }



def _ensure_salutation_exists(salutation):
    """Check if salutation exists, create if not, return valid value"""
    if not salutation:
        return None
    
    exists = frappe.db.exists('Salutation', salutation)
    
    if not exists:
        try:
            doc = frappe.get_doc({
                'doctype': 'Salutation',
                'salutation': salutation
            })
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
            return salutation
        except Exception as e:
            frappe.log_error(f"Failed to create salutation: {salutation}", "OpenImmo Import")
            return None
    
    return salutation


def _ensure_lead_source_exists(source_name):
    """Check if lead source exists, create if not"""
    if not source_name:
        return
    
    exists = frappe.db.exists('Lead Source', source_name)
    
    if not exists:
        try:
            doc = frappe.get_doc({
                'doctype': 'Lead Source',
                'source_name': source_name
            })
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"Failed to create lead source: {source_name}", "OpenImmo Import")


def find_existing_property(external_id):
    """Check if property exists by external reference"""
    if not external_id:
        return None
    
    return frappe.db.get_value(
        'Property',
        {'external_reference': external_id},
        'name'
    )


def find_existing_lead(email):
    """Check if lead exists by email"""
    if not email:
        return None
    
    return frappe.db.get_value(
        'Lead',
        {'email_id': email, 'status': ('!=', 'Converted')},
        'name'
    )
