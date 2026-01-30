# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from abc import ABC, abstractmethod
import requests
import base64
import os

class BaseProcessor(ABC):
    """
    Abstract Base Class for all OpenImmo Integration Processors.
    Provides shared utilities for API calls, file saving, and job creation.
    """
    
    def __init__(self, source_name):
        self.source = source_name
        self.source_doc = frappe.get_doc("Integration Source", source_name)
    
    @abstractmethod
    def receive_files(self):
        """
        Abstract method to fetch files from a remote or local source.
        Must return a list of created Integration Job names.
        """
        raise NotImplementedError("Subclass must implement receive_files()")
    
    def create_job(self, file_url, file_name):
        """
        Creates an Integration Job record for a received XML file.
        """
        job = frappe.new_doc('Integration Job')
        job.update({
            'source_name': self.source,
            'xml_file': file_url,
            'file_name': file_name,
            'status': 'Pending'
        })
        job.insert(ignore_permissions=True)
        
        # Explicit commit to ensure the job is visible to background workers 
        # even if the main sync process continues for other files.
        frappe.db.commit()
        return job.name
    
    def update_source_status(self, status, count=None):
        """
        Updates the synchronization status on the Integration Source record.
        Uses db_set to avoid triggering unnecessary document hooks.
        """
        self.source_doc.db_set("last_sync_status", status)
        self.source_doc.db_set("last_sync_at", frappe.utils.now())
        if count is not None:
            self.source_doc.db_set("last_sync_count", count)

    def log_error(self, message):
        """Logs integration errors specifically tied to this source."""
        frappe.log_error(
            title=f"Integration Error: {self.source}",
            message=message
        )

    # ===== API & HTTP UTILITIES =====

    def _make_api_request(self, method="GET", payload=None):
        """Standardized HTTP request handler using Source configuration."""
        if not self.source_doc.api_endpoint:
            frappe.throw(_("API Endpoint is missing for source: {0}").format(self.source))

        headers = self._build_api_headers()
        try:
            response = requests.request(
                method=method,
                url=self.source_doc.api_endpoint,
                headers=headers,
                json=payload if method == "POST" else None,
                timeout=30
            )
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            self.log_error(str(e))
            raise

    def _build_api_headers(self):
        """Builds headers with secure password retrieval for Auth."""
        headers = {
            "Accept": "application/xml",
            "User-Agent": "PropMS-XML-Importer/1.0",
        }

        # Bearer Token Auth
        if self.source_doc.api_key:
            token = self.source_doc.get_password("api_key")
            headers["Authorization"] = f"Bearer {token}"
            return headers

        # Basic Auth
        user = self.source_doc.api_username
        password = self.source_doc.get_password("api_password")
        if user and password:
            auth_str = f"{user}:{password}"
            encoded_auth = base64.b64encode(auth_str.encode()).decode()
            headers["Authorization"] = f"Basic {encoded_auth}"

        return headers

    def _save_file_to_frappe(self, content, filename):
        """
        Saves raw content as a private Frappe File and returns the URL.
        """
        _file = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "content": content,
            "is_private": 1,
            "folder": "Home/Attachments"
        })
        _file.insert(ignore_permissions=True)
        return _file.file_url