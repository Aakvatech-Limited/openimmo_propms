# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import xml.etree.ElementTree as ET
import os


def validate_xml_file(file_path):
    """Validate XML file structure and format"""
    try:
        # Check file exists
        absolute_path = _get_absolute_path(file_path)
        
        if not os.path.exists(absolute_path):
            return False, _("File not found: {0}").format(file_path)
        
        # Parse XML
        tree = ET.parse(absolute_path)
        root = tree.getroot()
        
        # Check if it's OpenImmo XML
        if 'openimmo' not in root.tag.lower():
            return False, _("Not a valid OpenImmo XML file")
        
        # Additional validations
        if not _has_required_elements(root):
            return False, _("Missing required OpenImmo elements")
        
        return True, ""
        
    except ET.ParseError as e:
        return False, _("Invalid XML format: {0}").format(str(e))
    except Exception as e:
        return False, _("Validation error: {0}").format(str(e))


def _get_absolute_path(file_url):
    """Convert Frappe file URL to absolute path"""
    if file_url.startswith('/private/files/'):
        return frappe.get_site_path('private', 'files', os.path.basename(file_url))
    elif file_url.startswith('/files/'):
        return frappe.get_site_path('public', 'files', os.path.basename(file_url))
    else:
        return frappe.get_site_path('public', file_url.lstrip('/'))


def _has_required_elements(root):
    """Check for required OpenImmo elements"""
    # Check for basic structure
    has_sender = root.find('.//anbieter') is not None
    has_object = root.find('.//immobilie') is not None or root.find('.//objekt') is not None
    
    return has_sender or has_object
