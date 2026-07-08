# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

from lxml import etree
import re


def ensure_xml_path(parent, path):
    """
    Create nested XML nodes for a dotted path and return the last node.
    Supports attributes via @ notation and numeric array indices (e.g. 'bewertung.feld.0.name').
    """
    current = parent
    parts = path.split(".")
    
    i = 0
    while i < len(parts):
        part = parts[i]
        attr_name = None
        if "@" in part:
            part, attr_name = part.split("@")
        
        # Check if the next part is a numeric index
        index = None
        if i + 1 < len(parts) and parts[i+1].isdigit():
            index = int(parts[i+1])
            
        if index is not None:
            # Find all children with the tag name
            children = current.findall(part)
            # Ensure we have enough children to satisfy the index
            while len(children) <= index:
                new_child = etree.SubElement(current, part)
                children.append(new_child)
            child = children[index]
            current = child
            i += 2  # Skip the index part
        else:
            child = current.find(part)
            if child is None:
                child = etree.SubElement(current, part)
            current = child
            i += 1
            
        if attr_name and i == len(parts):
            return current, attr_name
            
    return current, None


def set_xml_value(parent, path, value):
    """Set a text value or attribute at a dotted XML path."""
    if value is None:
        return

    # Standard OpenImmo booleans are lowercase "true" or "false"
    if isinstance(value, bool):
        value = "true" if value else "false"

    node, attr_name = ensure_xml_path(parent, path)
    
    if attr_name:
        node.set(attr_name, str(value))
    else:
        node.text = str(value)


def build_openimmo_document(
    anbieter_id,
    properties,
    portal_name=None,
    transfer_scope=None,
    transfer_mode=None,
    version="1.2.7",
):
    """Build the fixed OpenImmo envelope around mapped property nodes."""
    from frappe.utils import now_datetime

    root = etree.Element("openimmo")
    
    # 1. uebertragung
    uebertragung = etree.SubElement(root, "uebertragung")
    uebertragung.set("art", "ONLINE")
    uebertragung.set("umfang", transfer_scope or "VOLL")
    if transfer_mode:
        uebertragung.set("modus", transfer_mode)
    uebertragung.set("version", version)
    uebertragung.set("sendersoftware", "OIGEN")
    uebertragung.set("senderversion", "1.0")
    uebertragung.set("timestamp", now_datetime().strftime("%Y-%m-%dT%H:%M:%S"))
    if portal_name:
        uebertragung.set("portal", portal_name)

    # 2. anbieter
    anbieter = etree.SubElement(root, "anbieter")
    etree.SubElement(anbieter, "anbieternr").text = str(anbieter_id)

    # 3. immobilie blocks
    for property_node in properties:
        if isinstance(property_node, etree._Element):
            anbieter.append(property_node)
        else:
            # If it's a string (rendered from template), we need to parse it
            # This is less efficient but supports the old template way
            try:
                node = etree.fromstring(property_node)
                anbieter.append(node)
            except Exception:
                pass

    return etree.tostring(
        root,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8"
    ).decode("utf-8")


def render_xml_template(xml_template, context):
    """
    Render the full XML document from the configured XML template.
    Note: For strict XSD, it's better to use build_openimmo_document with nodes.
    """
    # Simple replacement if we still want to use template strings
    def replace(match):
        key = match.group(1).strip()
        value = context.get(key, "")
        return _escape_xml(value)

    rendered = re.sub(r"\{\{\s*([^}]+)\s*\}\}", replace, xml_template)
    return rendered


def _escape_xml(value):
    value = "" if value is None else str(value)
    value = value.replace("&", "&amp;")
    value = value.replace("<", "&lt;")
    value = value.replace(">", "&gt;")
    value = value.replace('"', "&quot;")
    return value
