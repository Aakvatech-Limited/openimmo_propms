# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class IntegrationSource(Document):
    def validate(self):
        self._validate_source_config()
        self._validate_target_doctype()
    
    def on_update(self):
        if self.enabled and self._has_scheduler_changed():
            self._setup_scheduler()
    
    def _validate_source_config(self):
        """Validate source-specific configurations"""
        if self.source_type == "Email" and not self.email_account:
            frappe.throw(_("Email Account is required for Email source type"))
        
        if self.source_type == "API" and not self.api_endpoint:
            frappe.throw(_("API Endpoint is required for API source type"))
        
        if self.source_type == "FTP" and not (self.ftp_host and self.ftp_username):
            frappe.throw(_("FTP Host and Username are required for FTP source type"))
    
    def _validate_target_doctype(self):
        """Validate target doctype exists"""
        if self.target_doctype and not frappe.db.exists("DocType", self.target_doctype):
            frappe.throw(_("Target DocType {0} does not exist").format(self.target_doctype))
    
    def _has_scheduler_changed(self):
        """Check if scheduler settings changed"""
        if self.is_new():
            return True
        
        old_doc = self.get_doc_before_save()
        if not old_doc:
            return True
        
        return (
            old_doc.enabled != self.enabled or
            old_doc.sync_frequency != self.sync_frequency
        )
    
    def _setup_scheduler(self):
        """Setup background scheduler for auto-sync"""
        # This will be implemented with scheduler hooks
        pass
    
    @frappe.whitelist()
    def sync_now(self):
        """Trigger manual sync"""
        if not self.enabled:
            frappe.throw(_("Source is disabled. Enable it first."))
        
        frappe.enqueue(
            'openimmo_propms.services.sync_engine.execute_sync',
            source_name=self.name,
            queue='long',
            timeout=3000
        )
        
        frappe.msgprint(_("Sync job queued successfully"), alert=True, indicator='green')
