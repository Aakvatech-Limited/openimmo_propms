# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from abc import ABC, abstractmethod
import requests
import base64



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
    
    def update_source_status(self, status, count=None, last_sync_at=None):
        """Update source last sync status"""
        self.source_doc.last_sync_status = status
        if count is not None and hasattr(self.source_doc, "last_sync_count"):
            self.source_doc.last_sync_count = count
        if last_sync_at:
            self.source_doc.last_sync_at = last_sync_at
        self.source_doc.save(ignore_permissions=True)
        frappe.db.commit()


    # ===== API helper methods (common for all API processors) =====

    def _make_api_request(self):
        """Common GET call using Integration Source config"""
        if not getattr(self.source_doc, "api_endpoint", None):
            frappe.throw(_("API Endpoint not configured"))

        headers = self._build_api_headers()

        try:
            response = requests.get(
                self.source_doc.api_endpoint,
                headers=headers,
                timeout=30,
                verify=True,
            )
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            self.log_error(f"API Request Failed - {self.source}", str(e))
            raise

    def _build_api_headers(self):
        """Build API request headers with auth"""
        headers = {
            "Accept": "application/xml, application/json",
            "User-Agent": "PropMS-Integration/1.0",
        }

        api_key = getattr(self.source_doc, "api_key", None)
        if api_key:
            api_key = self.source_doc.get_password("api_key")
            headers["Authorization"] = f"Bearer {api_key}"
            return headers

        api_user = getattr(self.source_doc, "api_username", None)
        api_pass = getattr(self.source_doc, "api_password", None)
        if api_user and api_pass:
            api_pass = self.source_doc.get_password("api_password")
            token = base64.b64encode(f"{api_user}:{api_pass}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"

        return headers

    def _save_api_file(self, content, filename):
        """Save response content as File and return file_url"""
        file_content = content.encode("utf-8") if isinstance(content, str) else content

        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "content": file_content,
            "decode": True,
            "is_private": 1,
        })
        file_doc.insert(ignore_permissions=True)
        return file_doc.file_url