# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from openimmo_propms.processors.base_processor import BaseProcessor


class ManualProcessor(BaseProcessor):
    """Processor for manual file uploads"""
    
    def receive_files(self):
        """For manual uploads, files are already attached to Integration Job"""
        frappe.msgprint(_("Manual upload does not require file reception"), alert=True)
        return []
