import frappe
from frappe import _
from openimmo_propms.processors.base_processor import BaseProcessor
import xml.etree.ElementTree as ET
import json


class APIProcessor(BaseProcessor):
    """Processor for API-based XML/JSON reception"""

    def receive_files(self):
        """Fetch data from API, split into files, create jobs"""
        try:
            # BaseProcessor से common request
            response = self._make_api_request()

            files = self._parse_api_response(response)
            received_files = []

            for file_data in files:
                file_url = self._save_api_file(file_data["content"], file_data["filename"])
                job_name = self.create_job(file_url, file_data["filename"])
                received_files.append(job_name)

            self.update_source_status("Success", len(files), frappe.utils.now())
            return received_files

        except Exception as e:
            self.log_error(f"API Processor Error - {self.source}", str(e))
            self.update_source_status("Failed", frappe.utils.now())
            raise

    def _parse_api_response(self, response):
        """Decide XML vs JSON and return list of {content, filename}"""
        content_type = (response.headers.get("content-type") or "").lower()
        text = response.text or ""

        if "xml" in content_type or text.strip().startswith("<"):
            return self._parse_xml(response.content)

        if "json" in content_type:
            return self._parse_json(response.json())

        return [{
            "content": text,
            "filename": "api_response.txt",
        }]

    def _parse_xml(self, content):
        """Example OpenImmo: split per <angebot>"""
        files = []
        try:
            root = ET.fromstring(content)
            angebote = root.findall(".//{http://www.openimmo.de/}angebot")

            if not angebote:
                return [{
                    "content": content.decode("utf-8"),
                    "filename": "openimmo_full.xml",
                }]

            for idx, angebot in enumerate(angebote):
                xml_str = ET.tostring(angebot, encoding="unicode")
                obj_id = angebot.get("objectid", f"obj_{idx}")
                files.append({
                    "content": xml_str,
                    "filename": f"openimmo_{obj_id}.xml",
                })
        except ET.ParseError:
            files.append({
                "content": content.decode("utf-8"),
                "filename": "openimmo_invalid.xml",
            })
        return files

    def _parse_json(self, data):
        """Generic JSON: one file per property/item"""
        files = []
        items = data.get("properties") or data.get("results") or []
        for idx, item in enumerate(items):
            files.append({
                "content": json.dumps(item),
                "filename": f"api_item_{item.get('id', idx)}.json",
            })

        if not files:
            files.append({
                "content": json.dumps(data),
                "filename": "api_response.json",
            })
        return files
