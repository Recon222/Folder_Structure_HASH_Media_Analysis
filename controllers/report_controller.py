#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Report controller - handles all report generation
"""

from pathlib import Path
from typing import Dict, List, Optional
import zipfile

from PySide6.QtCore import QSettings

from core.models import FormData
from core.pdf_gen import PDFGenerator
from utils.zip_utils import ZipUtility, ZipSettings


class ReportController:
    """Handles all report generation and archiving"""
    
    def __init__(self, settings: QSettings):
        self.settings = settings
        
    def generate_reports(
        self,
        form_data: FormData,
        file_results: Dict[str, Dict[str, str]],
        output_dir: Path
    ) -> Dict[str, Path]:
        """Generate all reports and return paths"""
        generated_reports = {}
        
        try:
            pdf_gen = PDFGenerator()
        except ImportError:
            raise ImportError("ReportLab not installed. Install with: pip install reportlab")
            
        # Generate time offset report if offset exists
        if form_data.time_offset != 0:
            time_report_path = output_dir / "Time_Offset_Report.pdf"
            if pdf_gen.generate_time_offset_report(form_data, time_report_path):
                generated_reports['time_offset'] = time_report_path
                
        # Generate technician log
        tech_log_path = output_dir / "Technician_Log.pdf"
        if pdf_gen.generate_technician_log(form_data, tech_log_path):
            generated_reports['technician_log'] = tech_log_path
            
        # Generate hash verification CSV only if hashing was enabled
        # Check if any file has hash values
        has_hashes = any(
            result.get('source_hash') or result.get('dest_hash') 
            for result in file_results.values()
        )
        
        if has_hashes:
            hash_csv_path = output_dir / "Hash_Verification.csv"
            if pdf_gen.generate_hash_verification_csv(file_results, hash_csv_path):
                generated_reports['hash_csv'] = hash_csv_path
            
        return generated_reports
        
    def get_zip_settings(self) -> ZipSettings:
        """Get ZIP settings for thread creation"""
        settings = ZipSettings()
        settings.compression_level = self.settings.value(
            'zip_compression_level', 
            zipfile.ZIP_STORED
        )
        settings.create_at_root = self.settings.value(
            'zip_at_root', 
            True, 
            type=bool
        )
        settings.create_at_location = self.settings.value(
            'zip_at_location', 
            False, 
            type=bool
        )
        settings.create_at_datetime = self.settings.value(
            'zip_at_datetime', 
            False, 
            type=bool
        )
        return settings
        
    def create_zip_archives(
        self,
        base_path: Path,
        output_directory: Path,
        progress_callback=None
    ) -> List[Path]:
        """Legacy method for backward compatibility - consider using get_zip_settings() with ZipOperationThread instead"""
        settings = self.get_zip_settings()
        settings.output_path = output_directory
        
        # Create ZIP utility
        zip_util = ZipUtility(progress_callback=progress_callback)
        
        # The base_path is the datetime folder, so we go up to get the occurrence folder
        root_folder = base_path.parents[1]
        
        # Create archives
        created = zip_util.create_multi_level_archives(root_folder, settings)
        
        return created
        
    def should_create_zip(self) -> bool:
        """Check if ZIP creation is enabled in settings"""
        return (
            self.settings.value('zip_at_root', True, type=bool) or
            self.settings.value('zip_at_location', False, type=bool) or
            self.settings.value('zip_at_datetime', False, type=bool)
        )