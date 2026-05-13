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

        if not xml_path:
            continue

        if source_value_type == "Static":
            value = mapping.get("static_value")
        else:
            if not fieldname:
                continue
            value = _get_record_value(record_data, fieldname, source.target_doctype)

        if (value is None or value == "") and mapping.default_value:
            value = mapping.default_value

        if value is None or value == "":
            # For specific mandatory OpenImmo attributes, we might want to keep the key even if empty
            # but generally we skip to keep XML clean.
            continue

        value = apply_data_transformation(value, mapping, record_data)
        value = _strip_prefix_for_export(value, mapping.get("export_strip_prefix"))
        mapped_data[xml_path] = value

    # Smart fallback for mandatory OpenImmo fields
    _ensure_mandatory_openimmo_fields(mapped_data, record_data, source)

    if (
        (getattr(source, "transfer_scope", "") or "").strip().upper() == "TEIL"
        and not mapped_data.get("verwaltung_techn.aktion")
        and (getattr(source, "transfer_mode", "") or "").strip()
    ):
        mapped_data["verwaltung_techn.aktion"] = source.transfer_mode.strip().upper()

    return mapped_data


def _ensure_mandatory_openimmo_fields(mapped_data, record_data, source):
    """Ensure Immowelt doesn't reject due to missing type or category tags."""
    
    # 1. Resolve Usage (nutzungsart) - Explicitly set all to avoid 'null' errors
    usage_fields = ["WOHNEN", "GEWERBE", "ANLAGE", "WAZ"]
    usage_detected = False
    for field in usage_fields:
        path = f"objektkategorie.nutzungsart@{field}"
        if mapped_data.get(path) in (True, "true", 1, "1"):
            mapped_data[path] = True
            usage_detected = True
        elif path not in mapped_data:
            mapped_data[path] = False

    if not usage_detected:
        # Default logic if nothing mapped
        is_commercial = "buero" in str(mapped_data).lower() or "laden" in str(mapped_data).lower()
        if is_commercial:
            mapped_data["objektkategorie.nutzungsart@GEWERBE"] = True
        else:
            mapped_data["objektkategorie.nutzungsart@WOHNEN"] = True

    # 2. Resolve Marketing (vermarktungsart) - Explicitly set all
    market_fields = ["KAUF", "MIETE_PACHT", "ERBPACHT", "LEASING"]
    market_detected = False
    for field in market_fields:
        path = f"objektkategorie.vermarktungsart@{field}"
        if mapped_data.get(path) in (True, "true", 1, "1"):
            mapped_data[path] = True
            market_detected = True
        elif path not in mapped_data:
            mapped_data[path] = False

    if not market_detected:
        if mapped_data.get("preise.kaltmiete") or mapped_data.get("preise.warmmiete"):
            mapped_data["objektkategorie.vermarktungsart@MIETE_PACHT"] = True
        else:
            mapped_data["objektkategorie.vermarktungsart@KAUF"] = True

    # 3. Resolve Object Type (e.g., <wohnung />)
    has_type_tag = any(
        key.startswith("objektkategorie.objektart.") and "@" not in key 
        for key in mapped_data
    )
    
    if not has_type_tag:
        # Check both raw record and already mapped text in 'objektart'
        type_hint = _normalize_value(
            mapped_data.get("objektkategorie.objektart") or
            record_data.get(source.name_field) or 
            record_data.get("property_type") or 
            record_data.get("type") or ""
        ).lower()

        if any(w in type_hint for w in ["flat", "apartment", "wohnung", "etage"]):
            mapped_data["objektkategorie.objektart.wohnung@wohnungtyp"] = "ETAGE"
        elif any(w in type_hint for w in ["house", "haus", "villa"]):
            mapped_data["objektkategorie.objektart.haus@haustyp"] = "EINFAMILIENHAUS"
        elif any(w in type_hint for w in ["office", "buero", "praxis", "laden", "shop"]):
            mapped_data["objektkategorie.objektart.buero_praxen@buerotyp"] = "BUEROFLAECHE"
        elif any(w in type_hint for w in ["garage", "stellplatz", "parking"]):
            mapped_data["objektkategorie.objektart.parken@parken_typ"] = "STELLPLATZ"
        elif any(w in type_hint for w in ["zimmer"]):
            mapped_data["objektkategorie.objektart.zimmer@zimmertyp"] = "ZIMMER"
        else:
            mapped_data["objektkategorie.objektart.zusatz_erweit@objektart_standard"] = "SONSTIGE"

    # If 'objektart' text was mapped (like 'Apartment'), we usually want to clear it 
    # to avoid having both text AND sub-tags inside <objektart>, which is non-standard.
    if has_type_tag or not mapped_data.get("objektkategorie.objektart.zusatz_erweit@objektart_standard") == "SONSTIGE":
        if "objektkategorie.objektart" in mapped_data:
            # Move the text to a more appropriate place or clear it
            if not mapped_data.get("freitexte.objekttitel"):
                mapped_data["freitexte.objekttitel"] = mapped_data["objektkategorie.objektart"]
            del mapped_data["objektkategorie.objektart"]

    # 4. Ensure some optional but helpful 'proper' tags exist
    if "objektkategorie.user_defined_simplefield@feldname" not in mapped_data:
        mapped_data["objektkategorie.user_defined_simplefield@feldname"] = ""


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
