import frappe

from openimmo_propms.services.mapper import apply_data_transformation


def build_property_data(source, record):
    """Map one Frappe record into a flat XML-path-to-value dictionary."""
    record_data = dict(record)
    mapped_data = {}

    for mapping in source.field_mappings:
        xml_path = (mapping.source_field or "").strip()
        fieldname = (mapping.target_field or "").strip()
        source_value_type = (mapping.get("source_value_type") or "Field").strip()

        if not xml_path or (source_value_type == "Field" and not fieldname):
            continue

        if source_value_type == "Static":
            value = mapping.get("static_value")
        else:
            value = _get_record_value(record_data, fieldname, source.target_doctype)

        if (value is None or value == "") and mapping.default_value:
            value = mapping.default_value

        if value is None or value == "":
            continue

        value = apply_data_transformation(value, mapping, record_data)
        value = _strip_prefix_for_export(value, mapping.get("export_strip_prefix"))
        mapped_data[xml_path] = value

    if (
        (getattr(source, "transfer_scope", "") or "").strip().upper() == "TEIL"
        and not mapped_data.get("verwaltung_techn.aktion")
        and (getattr(source, "transfer_mode", "") or "").strip()
    ):
        mapped_data["verwaltung_techn.aktion"] = source.transfer_mode.strip().upper()

    return mapped_data


def _strip_prefix_for_export(value, prefix_to_strip):
    prefix = (prefix_to_strip or "").strip()
    if not prefix:
        return value

    if isinstance(value, str):
        if "\n" in value:
            return "\n".join(_strip_prefix_for_export(line, prefix) for line in value.splitlines())
        if value.lower().startswith(prefix.lower()):
            return value[len(prefix) :]
    return value


def _get_record_value(record_data, fieldname, root_doctype=None):
    """Backward compatible wrapper."""
    return _resolve_value(record_data, fieldname, root_doctype)


def _resolve_value(record_data, fieldname, root_doctype):
    current = record_data
    current_doctype = root_doctype
    parts = fieldname.split(".")

    for index, part in enumerate(parts):
        remaining = parts[index + 1 :]

        if isinstance(current, dict):
            value = current.get(part)
            if not remaining:
                return _normalize_value(value)

            if isinstance(value, list):
                return _resolve_list_values(value, remaining, current_doctype, part)

            if isinstance(value, dict):
                current = value
                current_doctype = None
                continue

            link_meta = _get_link_meta(current_doctype, part)
            if link_meta and value:
                current = frappe.get_doc(link_meta.options, value).as_dict()
                current_doctype = link_meta.options
                continue

            current = value
            continue

        return None

    return _normalize_value(current)


def _resolve_list_values(items, remaining_parts, current_doctype, fieldname):
    values = []
    child_doctype = _get_child_table_options(current_doctype, fieldname)
    subpath = ".".join(remaining_parts)

    for item in items:
        if isinstance(item, dict):
            resolved = _resolve_value(item, subpath, child_doctype)
            if resolved not in (None, ""):
                values.append(resolved)

    if not values:
        return None

    return "\n".join(str(value) for value in values)


def _get_link_meta(doctype_name, fieldname):
    if not doctype_name:
        return None

    meta = frappe.get_meta(doctype_name)
    field = meta.get_field(fieldname)
    if field and field.fieldtype == "Link":
        return field
    return None


def _get_child_table_options(doctype_name, fieldname):
    if not doctype_name:
        return None

    meta = frappe.get_meta(doctype_name)
    field = meta.get_field(fieldname)
    if field and field.fieldtype == "Table":
        return field.options
    return None


def _normalize_value(value):
    if isinstance(value, list):
        cleaned = [str(item) for item in value if item not in (None, "")]
        return "\n".join(cleaned) if cleaned else None
    return value
