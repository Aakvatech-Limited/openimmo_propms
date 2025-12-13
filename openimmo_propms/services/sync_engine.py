# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from openimmo_propms.processors.email_processor import EmailProcessor
from openimmo_propms.processors.api_processor import APIProcessor
from openimmo_propms.processors.ftp_processor import FTPProcessor
from openimmo_propms.processors.manual_processor import ManualProcessor


def execute_sync(source_name):
    """Execute sync for a specific integration source"""
    try:
        source = frappe.get_doc("Integration Source", source_name)
        
        if not source.enabled:
            frappe.throw(_("Integration Source is disabled"))
        
        # Get appropriate processor based on source type
        processor = _get_processor(source)
        
        # Receive files from source
        job_names = processor.receive_files()
        
        frappe.msgprint(
            _("Sync completed. Created {0} job(s)").format(len(job_names)),
            alert=True,
            indicator='green'
        )
        
        return job_names
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Sync Engine Error - {source_name}")
        frappe.throw(_("Sync failed: {0}").format(str(e)))


def execute_scheduled_sync():
    """Execute sync for all enabled sources with scheduled frequency"""
    sources = frappe.get_all(
        "Integration Source",
        filters={
            "enabled": 1,
            "sync_frequency": ["!=", "Manual"]
        },
        fields=["name", "sync_frequency"]
    )
    
    for source in sources:
        if _should_sync_now(source):
            frappe.enqueue(
                'openimmo_propms.services.sync_engine.execute_sync',
                source_name=source.name,
                queue='long',
                timeout=3000
            )


def _get_processor(source):
    """Get appropriate processor instance based on source type"""
    processor_map = {
        'Email': EmailProcessor,
        'API': APIProcessor,
        'FTP': FTPProcessor,
        'Manual Upload': ManualProcessor
    }
    
    processor_class = processor_map.get(source.source_type)
    
    if not processor_class:
        frappe.throw(_("Invalid source type: {0}").format(source.source_type))
    
    return processor_class(source.name)


def _should_sync_now(source):
    """Check if source should sync based on frequency and last sync time"""
    if not source.get('sync_frequency') or source.sync_frequency == "Manual":
        return False
    
    source_doc = frappe.get_doc("Integration Source", source.name)
    last_sync = source_doc.last_sync_at
    
    if not last_sync:
        return True
    
    from frappe.utils import now_datetime, add_to_date
    current_time = now_datetime()
    
    if source.sync_frequency == "Hourly":
        next_sync = add_to_date(last_sync, hours=1)
    elif source.sync_frequency == "Daily":
        next_sync = add_to_date(last_sync, days=1)
    elif source.sync_frequency == "Weekly":
        next_sync = add_to_date(last_sync, weeks=1)
    else:
        return False
    
    return current_time >= next_sync
