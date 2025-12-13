# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import xml.etree.ElementTree as ET
import os


def parse_openimmo_xml(file_path):
    """Parse OpenImmo XML file and extract structured data"""
    absolute_path = _get_absolute_path(file_path)
    
    tree = ET.parse(absolute_path)
    root = tree.getroot()
    
    # Check if it's feedback format or transfer format
    is_feedback = root.find('.//sender') is not None or root.find('.//objekt') is not None
    
    if is_feedback:
        return _parse_feedback_format(root)
    else:
        return _parse_transfer_format(root)


def _parse_feedback_format(root):
    """Parse OpenImmo Feedback format (from portals like Immowelt)"""
    provider = {
        'name': _get_text(root, './/sender/name'),
        'portal_id': _get_text(root, './/sender/makler_id'),
        'date': _get_text(root, './/sender/datum'),
        'openimmo_anid': _get_text(root, './/sender/openimmo_anid')
    }
    
    properties = []
    applicants = []
    
    # In feedback format, objekt contains both property and interessent
    objekt_nodes = root.findall('.//objekt')
    
    for objekt in objekt_nodes:
        # Extract property
        property_data = {
            'external_id': _get_text(objekt, 'oobj_id'),
            'portal_id': _get_text(objekt, 'portal_obj_id'),
            'portal_unique_id': _get_text(objekt, 'portal_unique_id'),
            'title': _get_text(objekt, 'bezeichnung'),
            'street': _get_text(objekt, 'strasse'),
            'city': _get_text(objekt, 'ort'),
            'country': _get_text(objekt, 'land'),
            'district': _get_text(objekt, 'stadtbezirk'),
            'marketing_type': _get_text(objekt, 'vermarktungsart'),
            'expose_url': _get_text(objekt, 'expose_url'),
            'floor': _get_text(objekt, 'etage'),
            'apartment_number': _get_text(objekt, 'whg_nr'),
            'price': _get_text(objekt, 'preis'),
            'rooms': _get_text(objekt, 'anzahl_zimmer'),
            'area': _get_text(objekt, 'flaeche'),
            'currency': _get_text(objekt, 'wae'),
            'additional_ref': _get_text(objekt, 'zusatz_refnr'),
            'provider_id': _get_text(objekt, 'anbieter_id')
        }
        
        # Only add if property has external_id
        if property_data.get('external_id'):
            properties.append(property_data)
        
        # Extract interessent (applicant) - nested inside objekt
        interessent = objekt.find('.//interessent')
        if interessent is not None:
            applicant_data = {
                'int_id': _get_text(interessent, 'int_id'),
                'salutation': _get_text(interessent, 'anrede'),
                'first_name': _get_text(interessent, 'vorname'),
                'last_name': _get_text(interessent, 'nachname'),
                'email': _get_text(interessent, 'email'),
                'phone': _get_text(interessent, 'tel'),
                'mobile': _get_text(interessent, 'mobil'),
                'fax': _get_text(interessent, 'fax'),
                'company': _get_text(interessent, 'firma'),
                'street': _get_text(interessent, 'strasse'),
                'postal_code': _get_text(interessent, 'plz'),
                'city': _get_text(interessent, 'ort'),
                'postbox': _get_text(interessent, 'postfach'),
                'inquiry': _get_text(interessent, 'anfrage'),
                'preferred_contact': _get_text(interessent, 'bevorzugt'),
                'request_type': _get_text(interessent, 'wunsch'),
                'property_reference': property_data.get('external_id'),
                'property_portal_id': property_data.get('portal_obj_id')
            }
            
            # Only add if applicant has email or phone
            if applicant_data.get('email') or applicant_data.get('phone'):
                applicants.append(applicant_data)
    
    return {
        'provider': provider,
        'properties': properties,
        'applicants': applicants
    }


def _parse_transfer_format(root):
    """Parse OpenImmo Transfer format (standard property transfer)"""
    provider = _extract_provider(root)
    properties = _extract_properties(root)
    applicants = _extract_applicants(root)
    
    return {
        'provider': provider,
        'properties': properties,
        'applicants': applicants
    }


def _extract_provider(root):
    """Extract provider/sender information (transfer format)"""
    sender = root.find('.//anbieter')
    if sender is None:
        sender = root.find('.//sender')
    
    if sender is None:
        return {}
    
    return {
        'name': _get_text(sender, 'firma') or _get_text(sender, 'name'),
        'openimmo_id': _get_text(sender, 'openimmo_anid'),
        'email': _get_text(sender, 'email'),
        'phone': _get_text(sender, 'tel')
    }


def _extract_properties(root):
    """Extract property records (transfer format)"""
    properties = []
    
    # Check both possible property tags
    property_nodes = root.findall('.//immobilie')
    if not property_nodes:
        property_nodes = root.findall('.//objekt')
    
    for prop in property_nodes:
        property_data = {
            'external_id': _get_text(prop, './/objektnr_extern') or _get_text(prop, 'oobj_id'),
            'portal_id': _get_text(prop, './/objektnr_intern') or _get_text(prop, 'portal_obj_id'),
            'title': _get_text(prop, './/titel') or _get_text(prop, 'bezeichnung'),
            'street': _get_text(prop, './/strasse'),
            'house_number': _get_text(prop, './/hausnummer'),
            'postal_code': _get_text(prop, './/plz'),
            'city': _get_text(prop, './/ort'),
            'country': _get_text(prop, './/land'),
            'marketing_type': _get_text(prop, './/vermarktungsart'),
            'property_type': _get_text(prop, './/objektart'),
            'price': _get_text(prop, './/kaufpreis') or _get_text(prop, './/kaltmiete'),
            'living_area': _get_text(prop, './/wohnflaeche'),
            'plot_area': _get_text(prop, './/grundstuecksflaeche'),
            'rooms': _get_text(prop, './/anzahl_zimmer'),
            'description': _get_text(prop, './/objektbeschreibung'),
            'expose_url': _get_text(prop, './/expose_url')
        }
        properties.append(property_data)
    
    return properties


def _extract_applicants(root):
    """Extract applicant/lead records (transfer format)"""
    applicants = []
    
    interessent_nodes = root.findall('.//interessent')
    
    for person in interessent_nodes:
        applicant_data = {
            'salutation': _get_text(person, 'anrede'),
            'first_name': _get_text(person, 'vorname'),
            'last_name': _get_text(person, 'nachname'),
            'email': _get_text(person, 'email'),
            'phone': _get_text(person, 'tel') or _get_text(person, 'tel_privat'),
            'mobile': _get_text(person, 'tel_mobil'),
            'company': _get_text(person, 'firma'),
            'street': _get_text(person, 'strasse'),
            'postal_code': _get_text(person, 'plz'),
            'city': _get_text(person, 'ort'),
            'inquiry': _get_text(person, 'anfrage') or _get_text(person, 'nachricht'),
            'preferred_contact': _get_text(person, 'bevorzugt'),
            'request_type': _get_text(person, 'wunsch'),
            'property_reference': _get_text(person, '../objektnr_extern')
        }
        applicants.append(applicant_data)
    
    return applicants


def _get_absolute_path(file_url):
    """Convert Frappe file URL to absolute path"""
    if file_url.startswith('/private/files/'):
        return frappe.get_site_path('private', 'files', os.path.basename(file_url))
    elif file_url.startswith('/files/'):
        return frappe.get_site_path('public', 'files', os.path.basename(file_url))
    else:
        return frappe.get_site_path('public', file_url.lstrip('/'))


def _get_text(element, path, default=''):
    """Safely extract text from XML element"""
    if element is None:
        return default
    
    found = element.find(path)
    if found is not None and found.text:
        return found.text.strip()
    
    return default
