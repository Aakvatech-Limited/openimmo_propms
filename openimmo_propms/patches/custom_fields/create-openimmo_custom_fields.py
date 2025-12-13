# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Add custom fields for OpenImmo XML Import"""
    fields = {
        "Property": [
            {
                "fieldname": "openimmo_section",
                "fieldtype": "Section Break",
                "label": "OpenImmo Portal Details",
                "insert_after": "description",
                "collapsible": 1
            },
            {
                "fieldname": "external_reference",
                "fieldtype": "Data",
                "label": "External Reference",
                "insert_after": "openimmo_section",
                "unique": 1,
                "description": "OpenImmo property ID (oobj_id)"
            },
            {
                "fieldname": "portal_listing_id",
                "fieldtype": "Data",
                "label": "Portal Listing ID",
                "insert_after": "external_reference",
                "description": "Portal object ID"
            },
            {
                "fieldname": "column_break_openimmo",
                "fieldtype": "Column Break",
                "insert_after": "portal_listing_id"
            },
            {
                "fieldname": "portal_url",
                "fieldtype": "Data",
                "label": "Portal URL",
                "insert_after": "column_break_openimmo",
                "options": "URL",
                "description": "Property listing URL on portal"
            },
            {
                "fieldname": "marketing_type",
                "fieldtype": "Select",
                "label": "Marketing Type",
                "insert_after": "portal_url",
                "options": "\nMiete\nKauf\nErbpacht\nLeasing",
                "description": "Marketing type from OpenImmo (Miete=Rent, Kauf=Sale)"
            },
            {
                "fieldname": "property_street",
                "fieldtype": "Data",
                "label": "Street",
                "insert_after": "marketing_type"
            },
            {
                "fieldname": "property_city",
                "fieldtype": "Data",
                "label": "City",
                "insert_after": "property_street"
            }
        ],
        "Lead": [
            {
                "fieldname": "openimmo_inquiry_section",
                "fieldtype": "Section Break",
                "label": "OpenImmo Inquiry Details",
                "insert_after": "notes",  # Changed from "request_type" to "notes"
                "collapsible": 1
            },
            {
                "fieldname": "property_interest",
                "fieldtype": "Link",
                "options": "Property",
                "label": "Property Interest",
                "insert_after": "openimmo_inquiry_section",
                "description": "Property the lead is interested in"
            },
            {
                "fieldname": "portal_source",
                "fieldtype": "Data",
                "label": "Portal Source",
                "insert_after": "property_interest",
                "description": "Portal name (e.g., Immowelt, ImmoScout24)"
            },
            {
                "fieldname": "column_break_inquiry",
                "fieldtype": "Column Break",
                "insert_after": "portal_source"
            },
            {
                "fieldname": "contact_preference",
                "fieldtype": "Select",
                "label": "Contact Preference",
                "insert_after": "column_break_inquiry",
                "options": "\nEMAIL\nTEL\nPOST",
                "description": "Preferred contact method from OpenImmo"
            },
            {
                "fieldname": "inquiry_type",
                "fieldtype": "Select",
                "label": "Inquiry Type",
                "insert_after": "contact_preference",
                "options": "\nDETAIL\nEXPOSE\nBESICHTIGUNG\nVISIT",
                "description": "Type of information requested (OpenImmo wunsch field)"
            },
            {
                "fieldname": "inquiry_details_section",
                "fieldtype": "Section Break",
                "label": "Inquiry Message",
                "insert_after": "inquiry_type"
            },
            {
                "fieldname": "inquiry_text",
                "fieldtype": "Long Text",
                "label": "Inquiry Text",
                "insert_after": "inquiry_details_section",
                "description": "Detailed inquiry message from applicant"
            }
        ]
    }
    
    create_custom_fields(fields, update=True)
    frappe.db.commit()
    
    print("Custom fields created for Property and Lead")
