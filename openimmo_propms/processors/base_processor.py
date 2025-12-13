# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from abc import ABC, abstractmethod


class BaseProcessor(ABC):
    """Abstract base class for all integration processors"""
    
    def __init__(self, source):
        self.source = source
        self.source_doc = frappe.get_doc("Integration Source", source)
    
    @abstractmethod
    def receive_files(self):
        """Receive files from source - must be implemented by child classes"""
        raise NotImplementedError("Subclass must implement receive_files()")
    
    def validate_file(self, file_path):
        """Validate XML file structure"""
        from openimmo_propms.services.validator import validate_xml_file
        return validate_xml_file(file_path)
    
    def create_job(self, file_path, file_name):
        """Create Integration Job record"""
        job = frappe.get_doc({
            'doctype': 'Integration Job',
            'source_name': self.source,
            'xml_file': file_path,
            'file_name': file_name,
            'status': 'Pending'
        })
        job.insert(ignore_permissions=True)
        frappe.db.commit()
        return job.name
    
    def log_error(self, title, message):
        """Log error to Error Log"""
        frappe.log_error(message, title)
    
    def update_source_status(self, status, last_sync_at=None):
        """Update source last sync status"""
        self.source_doc.last_sync_status = status
        if last_sync_at:
            self.source_doc.last_sync_at = last_sync_at
        self.source_doc.save(ignore_permissions=True)
        frappe.db.commit()
