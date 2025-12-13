# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from openimmo_propms.processors.base_processor import BaseProcessor
import requests


class APIProcessor(BaseProcessor):
    """Processor for API-based file reception"""
    
    def receive_files(self):
        """Fetch XML files from configured API endpoint"""
        if not self.source_doc.api_endpoint:
            frappe.throw(_("API Endpoint not configured"))
        
        try:
            headers = self._build_headers()
            response = requests.get(
                self.source_doc.api_endpoint,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            received_files = []
            files = self._parse_api_response(response)
            
            for file_data in files:
                file_path = self._save_file(file_data)
                job_name = self.create_job(file_path, file_data['filename'])
                received_files.append(job_name)
            
            self.update_source_status("Success", frappe.utils.now())
            return received_files
            
        except Exception as e:
            self.log_error(f"API Processor Error - {self.source}", str(e))
            self.update_source_status("Failed", frappe.utils.now())
            raise
    
    def _build_headers(self):
        """Build API request headers with authentication"""
        headers = {'Content-Type': 'application/json'}
        
        if self.source_doc.api_key:
            headers['Authorization'] = f"Bearer {self.source_doc.get_password('api_key')}"
        
        return headers
    
    def _parse_api_response(self, response):
        """Parse API response to extract file data"""
        # Implement based on your API response format
        return []
    
    def _save_file(self, file_data):
        """Save file from API response"""
        file_doc = frappe.get_doc({
            'doctype': 'File',
            'file_name': file_data['filename'],
            'content': file_data['content'],
            'is_private': 1
        })
        file_doc.save(ignore_permissions=True)
        return file_doc.file_url
