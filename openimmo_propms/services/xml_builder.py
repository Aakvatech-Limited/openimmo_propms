import xml.etree.ElementTree as ET
import re


def ensure_xml_path(parent, path):
    """Create nested XML nodes for a dotted path and return the last node."""
    current = parent
    for part in path.split("."):
        child = current.find(part)
        if child is None:
            child = ET.SubElement(current, part)
        current = child
    return current


def set_xml_value(parent, path, value):
    """Set a text value at a dotted XML path."""
    if value is None or value == "":
        return

    node = ensure_xml_path(parent, path)
    node.text = str(value)


def build_openimmo_document(
    anbieter_id,
    properties,
    portal_name=None,
    transfer_scope=None,
    transfer_mode=None,
):
    """Build the fixed OpenImmo envelope around mapped property nodes."""
    root = ET.Element("openimmo")
    uebertragung = ET.SubElement(root, "uebertragung")
    uebertragung.set("umfang", transfer_scope or "VOLL")
    uebertragung.set("modus", transfer_mode or "NEW")
    if portal_name:
        uebertragung.set("portal", portal_name)

    anbieter = ET.SubElement(root, "anbieter")
    ET.SubElement(anbieter, "anbieternr").text = str(anbieter_id)

    for property_node in properties:
        anbieter.append(property_node)

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        root,
        encoding="unicode",
    )


def render_template(template, context, raw_keys=None):
    """Replace {{key}} placeholders from a flat context dictionary."""
    if not template:
        return ""

    raw_keys = set(raw_keys or [])

    def replace(match):
        key = match.group(1).strip()
        value = context.get(key, "")
        if key in raw_keys:
            return "" if value is None else str(value)
        return _escape_xml(value)

    return re.sub(r"\{\{\s*([^}]+)\s*\}\}", replace, template)


def render_property_template(property_template, mapped_data):
    """Render one property block from the configured property template."""
    return render_template(property_template, mapped_data)


def render_xml_template(xml_template, context):
    """Render the full XML document from the configured XML template."""
    return render_template(xml_template, context, raw_keys={"record_blocks"})


def _escape_xml(value):
    value = "" if value is None else str(value)
    value = value.replace("&", "&amp;")
    value = value.replace("<", "&lt;")
    value = value.replace(">", "&gt;")
    value = value.replace('"', "&quot;")
    return value
