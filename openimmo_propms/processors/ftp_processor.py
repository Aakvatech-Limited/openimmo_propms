# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from openimmo_propms.processors.base_processor import BaseProcessor
import ftplib
import os


class FTPProcessor(BaseProcessor):
    """Processor for FTP-based file reception"""
    
    def receive_files(self):
        """Fetch XML files from configured FTP server"""
        if not (self.source_doc.ftp_host and self.source_doc.ftp_username):
            frappe.throw(_("FTP configuration incomplete"))
        
        try:
            ftp = self._connect_ftp()
            received_files = []
            
            directory = self.source_doc.ftp_directory or '/'
            ftp.cwd(directory)
            
            xml_files = [f for f in ftp.nlst() if f.lower().endswith('.xml')]
            
            for filename in xml_files:
                file_path = self._download_file(ftp, filename)
                job_name = self.create_job(file_path, filename)
                received_files.append(job_name)
            
            ftp.quit()
            self.update_source_status("Success", frappe.utils.now())
            return received_files
            
        except Exception as e:
            self.log_error(f"FTP Processor Error - {self.source}", str(e))
            self.update_source_status("Failed", frappe.utils.now())
            raise
    
    def _connect_ftp(self):
        """Establish FTP connection"""
        ftp = ftplib.FTP()
        ftp.connect(
            self.source_doc.ftp_host,
            self.source_doc.ftp_port or 21
        )
        ftp.login(
            self.source_doc.ftp_username,
            self.source_doc.get_password('ftp_password')
        )
        return ftp
    
    def _download_file(self, ftp, filename):
        """Download file from FTP and save locally"""
        local_path = frappe.get_site_path('private', 'files', filename)
        
        with open(local_path, 'wb') as local_file:
            ftp.retrbinary(f'RETR {filename}', local_file.write)
        
        # Create File doc
        file_doc = frappe.get_doc({
            'doctype': 'File',
            'file_name': filename,
            'file_url': f'/private/files/{filename}',
            'is_private': 1
        })
        file_doc.save(ignore_permissions=True)
        
        return file_doc.file_url
