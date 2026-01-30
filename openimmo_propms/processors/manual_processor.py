# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from openimmo_propms.processors.base_processor import BaseProcessor

class ManualProcessor(BaseProcessor):
    """
    Processor for manual file uploads.
    Instead of fetching from a remote server, it fetches 'Pending' 
    Integration Jobs already created by users in the system.
    """
    
    def receive_files(self):
        """
        Identifies Integration Jobs that were manually uploaded but not yet processed.
        Returns a list of Job names to be handled by the sync engine.
        """
        # 1. Fetch pending jobs specifically for this source
        pending_jobs = frappe.get_all("Integration Job", filters={
            "source_name": self.source,
            "status": "Pending",
            "xml_file": ["is", "set"] # Ensure there is actually a file to process
        }, fields=["name"])

        job_names = [job.name for job in pending_jobs]

        if not job_names:
            # We use logger instead of msgprint for background/scheduled compatibility
            frappe.logger("utils").info(f"ManualProcessor: No pending jobs found for {self.source}")
            return []

        # 2. Update the Source status using BaseProcessor's utility
        self.update_source_status("Success", count=len(job_names))
        
        return job_names