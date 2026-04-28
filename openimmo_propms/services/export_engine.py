import frappe
from frappe import _
from frappe.utils import cint, get_url
from frappe.utils.file_manager import save_file
import hashlib
import ftplib
from io import BytesIO

from openimmo_propms.services.export_mapper import build_property_data
from openimmo_propms.services.xml_builder import (
    build_openimmo_document,
    render_xml_template,
)


def run_export(source_name, **kwargs):
    """Run a metadata-driven export without touching the import flow."""
    source = frappe.get_doc("Integration Source", source_name)
    _validate_export_source(source)

    records = _get_records_for_export(source, kwargs)
    mapped_records = [build_property_data(source, record) for record in records]
    export_records = list(zip(records, mapped_records))
    documents = _build_export_documents(source, export_records, kwargs)
    should_save = _should_save_file(source, kwargs.get("save_file"))
    responses = []

    for document in documents:
        xml_hash = _build_xml_hash(document["xml_content"])
        response = {
            "status": "success",
            "record_count": document["record_count"],
            "filename": document["filename"],
            "xml_hash": xml_hash,
        }

        if should_save:
            file_doc = save_file(
                document["filename"],
                document["xml_content"],
                "Integration Source",
                source.name,
                is_private=1,
            )
            response["file_url"] = file_doc.file_url
        else:
            response["xml"] = document["xml_content"]

        delivery_result = _deliver_export(source, document["filename"], document["xml_content"], xml_hash)
        if delivery_result:
            response.update(delivery_result)

        if should_save:
            job = _create_export_job(source, response)
            response["job_name"] = job.name

        responses.append(response)

    return _summarize_export_response(source, responses)


def _validate_export_source(source):
    if source.operation_type != "Export":
        frappe.throw(_("Integration Source must be configured for Export"))

    if source.export_format != "OpenImmo":
        frappe.throw(_("Only OpenImmo export is supported in this version"))

    if not source.field_mappings:
        frappe.throw(_("Please configure at least one field mapping"))

    if not source.target_doctype:
        frappe.throw(_("Target DocType is required for export"))

    if source.xml_template and "{{record_blocks}}" not in source.xml_template:
        frappe.throw(_("XML Template must include the {{record_blocks}} placeholder"))


def _deliver_export(source, filename, xml_content, xml_hash):
    if source.source_type == "FTP" and cint(source.ftp_transfer_enabled):
        return _upload_via_ftp(source, filename, xml_content, xml_hash)

    return {
        "delivery_channel": source.source_type or "Manual Upload",
        "delivery_status": "skipped",
    }


def _build_export_documents(source, export_records, params):
    if source.record_packaging == "Separate XML per Record":
        return [
            {
                "filename": _build_record_filename(source, index + 1),
                "xml_content": _build_xml_content(source, [export_record], params),
                "record_count": 1,
            }
            for index, export_record in enumerate(export_records)
        ]

    return [
        {
            "filename": _build_batch_filename(source),
            "xml_content": _build_xml_content(source, export_records, params),
            "record_count": len(export_records),
        }
    ]


def _build_xml_content(source, export_records, params):
    anbieter_id = params.get("anbieter_id") or source.anbieter_id

    if source.xml_template:
        return _normalize_xml_document(
            render_xml_template(
                source.xml_template,
                {
                    "anbieter_id": anbieter_id,
                    "portal_name": source.portal_name or "",
                    "transfer_scope": source.transfer_scope or "VOLL",
                    "transfer_mode": source.transfer_mode or "NEW",
                    "record_blocks": _build_record_blocks(source, export_records),
                },
            )
        )

    xml_nodes = [
        _build_xml_node(source, record, mapped_record)
        for record, mapped_record in export_records
    ]
    return _normalize_xml_document(
        build_openimmo_document(
            anbieter_id,
            xml_nodes,
            portal_name=source.portal_name,
            transfer_scope=source.transfer_scope,
            transfer_mode=source.transfer_mode,
        )
    )


def _normalize_xml_document(xml_content):
    # XML declaration must be the very first content in the document.
    return (xml_content or "").lstrip("\ufeff\r\n\t ")


def _build_xml_hash(xml_content):
    return hashlib.sha256((xml_content or "").encode("utf-8")).hexdigest()


def _build_batch_filename(source):
    return f"{source.name.lower().replace(' ', '_')}_openimmo_export.xml"


def _build_record_filename(source, index):
    return f"{source.name.lower().replace(' ', '_')}_openimmo_export_{index}.xml"


def _get_records_for_export(source, params):
    filters = _get_configured_export_filters(source)
    fieldnames = _sanitize_query_fields(_get_requested_fieldnames(source))
    runtime_filters = {}

    if params.get("filter_company"):
        runtime_filters[_get_required_filter_fieldname(source.company_field, _("Company Field"))] = params.get("filter_company")

    if params.get("property_name"):
        runtime_filters[_get_required_filter_fieldname(source.name_field, _("Name Field"))] = params.get("property_name")

    if params.get("filter_status"):
        runtime_filters[_get_required_filter_fieldname(source.status_field, _("Status Field"))] = params.get("filter_status")

    if params.get("filter_publish") is not None:
        runtime_filters[_get_required_filter_fieldname(source.publish_field, _("Publish Field"))] = cint(params.get("filter_publish"))

    filters = _merge_filters(filters, runtime_filters)

    records, used_name_only_fallback = _get_all_records(source.target_doctype, filters, fieldnames)

    if _requires_full_doc(source) or used_name_only_fallback:
        return [frappe.get_doc(source.target_doctype, record["name"]).as_dict() for record in records]

    return [frappe._dict(record) for record in records]


def _get_configured_export_filters(source):
    filters_json = (source.export_filters_json or "").strip()
    if not filters_json:
        return {}

    parsed_filters = frappe.parse_json(filters_json)
    if isinstance(parsed_filters, list):
        return _normalize_list_filters(parsed_filters)
    if isinstance(parsed_filters, dict):
        return dict(parsed_filters)

    frappe.throw(_("Export Filters (JSON) must be a JSON object or list"))


def _merge_filters(configured_filters, runtime_filters):
    if not runtime_filters:
        return configured_filters

    if isinstance(configured_filters, list):
        merged_filters = list(configured_filters)
        for fieldname, value in runtime_filters.items():
            merged_filters.append([fieldname, "=", value])
        return merged_filters

    merged_filters = dict(configured_filters or {})
    merged_filters.update(runtime_filters)
    return merged_filters


def _normalize_list_filters(filters):
    normalized = list(filters or [])
    if normalized and isinstance(normalized[0], str):
        return [normalized]
    return normalized


def _build_xml_node(source, record, mapped_record):
    import xml.etree.ElementTree as ET

    from openimmo_propms.services.xml_builder import set_xml_value

    immobilie = ET.Element("immobilie")
    for xml_path, value in mapped_record.items():
        set_xml_value(immobilie, xml_path, value)
    _append_image_attachment(source, record, immobilie)
    return immobilie


def _build_record_blocks(source, export_records):
    import xml.etree.ElementTree as ET

    blocks = []
    for record, mapped_record in export_records:
        blocks.append(ET.tostring(_build_xml_node(source, record, mapped_record), encoding="unicode"))
    return "\n".join(blocks)


def _append_image_attachment(source, record, immobilie):
    image_field = (source.image_field or "").strip()
    if not image_field:
        return

    image_value = record.get(image_field) if isinstance(record, dict) else None
    image_url = _build_absolute_media_url(source, image_value)
    if not image_url:
        return

    import xml.etree.ElementTree as ET

    anhaenge = ET.SubElement(immobilie, "anhaenge")
    anhang = ET.SubElement(anhaenge, "anhang")
    ET.SubElement(anhang, "gruppe").text = source.image_group or "TITELBILD"
    ET.SubElement(anhang, "location").text = source.image_location or "EXTERN"
    ET.SubElement(anhang, "daten").text = image_url


def _build_absolute_media_url(source, image_value):
    if not image_value:
        return None

    image_url = str(image_value).strip()
    if not image_url:
        return None

    if image_url.startswith(("http://", "https://")):
        return image_url

    base_url = (source.base_media_url or "").strip() or get_url()
    if not base_url:
        return image_url

    return "{0}/{1}".format(base_url.rstrip("/"), image_url.lstrip("/"))


def _get_requested_fieldnames(source):
    fieldnames = {"name"}

    for mapping in source.field_mappings:
        fieldname = _get_configured_fieldname(mapping.target_field)
        if fieldname and "." not in fieldname:
            fieldnames.add(fieldname)

    for configured_field in [
        source.name_field,
        source.company_field,
        source.status_field,
        source.publish_field,
        source.image_field,
    ]:
        fieldname = _get_configured_fieldname(configured_field)
        if fieldname and "." not in fieldname:
            fieldnames.add(fieldname)

    return sorted(fieldnames)


def _sanitize_query_fields(fieldnames):
    cleaned = []
    for fieldname in fieldnames or []:
        text = str(fieldname).strip()
        if text:
            cleaned.append(text)
    return cleaned


def _get_all_records(doctype, filters, fieldnames):
    try:
        return (
            frappe.get_all(
                doctype,
                filters=filters,
                fields=fieldnames,
                limit_page_length=0,
            ),
            False,
        )
    except TypeError as exc:
        if "not iterable" not in str(exc):
            raise

        frappe.log_error(
            message=(
                f"TypeError in export get_all for {doctype}. "
                f"fields={fieldnames!r}, filters={filters!r}, error={exc}"
            ),
            title="OpenImmo Export Query Fallback",
        )

        return (
            frappe.get_all(
                doctype,
                filters=filters,
                fields=["name"],
                limit_page_length=0,
            ),
            True,
        )


def _get_configured_fieldname(value):
    if not isinstance(value, str):
        return ""
    return value.strip()


def _get_required_filter_fieldname(configured_value, label):
    fieldname = _get_configured_fieldname(configured_value)
    if not fieldname:
        frappe.throw(_("{0} is required when corresponding runtime filter is used").format(label))
    return fieldname


def _requires_full_doc(source):
    for mapping in source.field_mappings:
        target_field = (mapping.target_field or "").strip()
        if target_field and "." in target_field:
            return True
    return False


def _should_save_file(source, save_file):
    if save_file is None:
        return cint(source.save_file_by_default)

    return cint(save_file)


def _create_export_job(source, response):
    job = frappe.get_doc(
        {
            "doctype": "Integration Job",
            "source_name": source.name,
            "status": "Success",
            "xml_file": response["file_url"],
            "file_name": response["filename"],
            "xml_hash": response.get("xml_hash"),
            "delivery_channel": response.get("delivery_channel"),
            "delivery_status": response.get("delivery_status"),
            "delivery_target": response.get("delivery_target"),
            "received_at": frappe.utils.now(),
            "processed_at": frappe.utils.now(),
            "total_records": response.get("record_count", 0),
            "successful_records": response.get("record_count", 0),
            "failed_records": 0,
            "skipped_records": 0,
            "log_message": _build_export_log_message(response),
        }
    )
    job.insert(ignore_permissions=True)
    return job


def _build_export_log_message(response):
    delivery_status = response.get("delivery_status", "generated")
    delivery_channel = response.get("delivery_channel", "Manual")
    return _(
        "Export completed. Records: {0}, Delivery: {1}, Channel: {2}"
    ).format(
        response.get("record_count", 0),
        delivery_status,
        delivery_channel,
    )


def _summarize_export_response(source, responses):
    if source.record_packaging != "Separate XML per Record":
        return responses[0] if responses else {"status": "success", "record_count": 0}

    return {
        "status": "success",
        "record_count": sum(response.get("record_count", 0) for response in responses),
        "file_count": len(responses),
        "delivery_channel": responses[0].get("delivery_channel") if responses else source.source_type,
        "delivery_status": responses[0].get("delivery_status") if responses else "skipped",
        "files": [
            {
                "filename": response.get("filename"),
                "file_url": response.get("file_url"),
                "job_name": response.get("job_name"),
            }
            for response in responses
        ],
    }


def _upload_via_ftp(source, filename, xml_content, xml_hash):
    if not source.ftp_host:
        frappe.throw(_("FTP Host is required for FTP export delivery"))

    delivery_target = _build_ftp_delivery_target(source)
    if _has_successful_ftp_delivery(source.name, xml_hash, delivery_target):
        source.db_set("last_sync_status", _("Duplicate export skipped"))
        return {
            "delivery_channel": "FTP",
            "delivery_status": "skipped_duplicate",
            "delivery_target": delivery_target,
        }

    ftp = _connect_ftp(source)
    try:
        if source.ftp_directory:
            ftp.cwd(source.ftp_directory)

        ftp.storbinary(
            f"STOR {filename}",
            BytesIO(xml_content.encode("utf-8")),
        )
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()

    source.db_set("last_sync_status", _("Export uploaded successfully"))
    source.db_set("last_sync_at", frappe.utils.now())

    return {
        "delivery_channel": "FTP",
        "delivery_status": "uploaded",
        "delivery_target": delivery_target,
    }


def _build_ftp_delivery_target(source):
    if source.ftp_directory:
        return "{0}/{1}".format(
            source.ftp_host.rstrip("/"),
            source.ftp_directory.strip("/"),
        )
    return source.ftp_host


def _has_successful_ftp_delivery(source_name, xml_hash, delivery_target):
    return bool(
        frappe.db.exists(
            "Integration Job",
            {
                "source_name": source_name,
                "status": "Success",
                "delivery_channel": "FTP",
                "delivery_status": "uploaded",
                "delivery_target": delivery_target,
                "xml_hash": xml_hash,
            },
        )
    )


def _connect_ftp(source):
    host = source.ftp_host
    port = source.ftp_port or 21
    user = source.ftp_username
    password = source.get_password("ftp_password")

    try:
        ftp = ftplib.FTP_TLS(timeout=60)
        ftp.encoding = "utf-8"
        ftp.connect(host, port)
        if user:
            ftp.login(user, password)
            ftp.prot_p()
        else:
            ftp.login()
        ftp.set_pasv(True)
        return ftp
    except Exception as exc:
        frappe.log_error(f"FTP TLS failed, trying plain FTP: {str(exc)}", "FTP Export")
        ftp = ftplib.FTP(timeout=60)
        ftp.connect(host, port)
        ftp.login(user, password)
        ftp.set_pasv(True)
        return ftp
