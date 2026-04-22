import frappe

from openimmo_propms.services.export_engine import run_export


@frappe.whitelist()
def run_openimmo_export(
    source_name,
    filter_publish=None,
    filter_status=None,
    filter_company=None,
    property_name=None,
    anbieter_id=None,
    save_file=None,
):
    """Whitelisted wrapper for the minimal metadata-driven export flow."""
    return run_export(
        source_name=source_name,
        filter_publish=filter_publish,
        filter_status=filter_status,
        filter_company=filter_company,
        property_name=property_name,
        anbieter_id=anbieter_id,
        save_file=save_file,
    )
