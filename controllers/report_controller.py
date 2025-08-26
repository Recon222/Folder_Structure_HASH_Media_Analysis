#!/usr/bin/env python3
"""
Report controller - orchestrates report generation workflows
"""
from pathlib import Path
from typing import Dict, List, Optional

from .base_controller import BaseController
from core.models import FormData
from core.services.interfaces import IReportService, IArchiveService
from core.result_types import ReportGenerationResult, Result
from core.exceptions import ReportGenerationError

class ReportController(BaseController):
    """Orchestrates report generation and archiving workflows"""
    
    def __init__(self, zip_controller=None):
        super().__init__("ReportController")
        self.zip_controller = zip_controller
        
        # Service dependencies (injected)
        self._report_service = None
        self._archive_service = None
    
    @property
    def report_service(self) -> IReportService:
        """Lazy load report service"""
        if self._report_service is None:
            self._report_service = self._get_service(IReportService)
        return self._report_service
    
    @property
    def archive_service(self) -> IArchiveService:
        """Lazy load archive service"""
        if self._archive_service is None:
            self._archive_service = self._get_service(IArchiveService)
        return self._archive_service
        
    def generate_all_reports(
        self,
        form_data: FormData,
        file_results: Dict[str, Dict[str, str]],
        output_dir: Path,
        generate_time_offset: bool = True,
        generate_upload_log: bool = True,
        generate_hash_csv: bool = True
    ) -> Dict[str, ReportGenerationResult]:
        """
        Generate all requested reports
        
        Orchestrates the generation of multiple report types based on settings
        and form data. Each report is generated independently.
        
        Returns:
            Dictionary mapping report types to their generation results
        """
        try:
            self._log_operation("generate_all_reports", f"output: {output_dir}")
            
            generated_reports = {}
            
            # Time offset report
            if generate_time_offset and self._should_generate_time_offset_report(form_data):
                time_report_path = output_dir / "Time_Offset_Report.pdf"
                result = self.report_service.generate_time_offset_report(form_data, time_report_path)
                generated_reports['time_offset'] = result
                
                if result.success:
                    self._log_operation("time_offset_report_generated", str(time_report_path))
                else:
                    self._log_operation("time_offset_report_failed", str(result.error), "warning")
            
            # Upload/technician log
            if generate_upload_log:
                upload_log_path = output_dir / "Upload_Log.pdf"
                result = self.report_service.generate_technician_log(form_data, upload_log_path)
                generated_reports['upload_log'] = result
                
                if result.success:
                    self._log_operation("upload_log_generated", str(upload_log_path))
                else:
                    self._log_operation("upload_log_failed", str(result.error), "warning")
            
            # Hash verification CSV
            if generate_hash_csv and self._should_generate_hash_csv(file_results):
                hash_csv_path = output_dir / "Hash_Verification.csv"
                result = self.report_service.generate_hash_csv(file_results, hash_csv_path)
                generated_reports['hash_csv'] = result
                
                if result.success:
                    self._log_operation("hash_csv_generated", str(hash_csv_path))
                else:
                    self._log_operation("hash_csv_failed", str(result.error), "warning")
            
            self._log_operation("report_generation_completed", f"{len(generated_reports)} reports")
            return generated_reports
            
        except Exception as e:
            error = ReportGenerationError(
                f"Report generation workflow failed: {e}",
                user_message="Failed to generate reports. Please check output directory permissions."
            )
            self._handle_error(error, {'method': 'generate_all_reports'})
            
            # Return failed result for all requested reports
            failed_result = ReportGenerationResult(success=False, error=error, value=None)
            return {
                report_type: failed_result 
                for report_type in ['time_offset', 'upload_log', 'hash_csv']
                if locals().get(f'generate_{report_type}', False)
            }
    
    # Backward compatibility method
    def generate_reports(self, *args, **kwargs):
        """Backward compatibility wrapper for generate_all_reports"""
        return self.generate_all_reports(*args, **kwargs)
    
    def _should_generate_time_offset_report(self, form_data: FormData) -> bool:
        """Check if time offset report should be generated"""
        return form_data.time_offset != 0
    
    def _should_generate_hash_csv(self, file_results: Dict[str, Dict[str, str]]) -> bool:
        """Check if hash CSV should be generated based on results"""
        return any(
            result.get('source_hash') or result.get('dest_hash') 
            for result in file_results.values()
            if isinstance(result, dict)  # Skip performance stats entry
        )
    
    def should_create_archives(self) -> bool:
        """Check if archives should be created"""
        try:
            return self.archive_service.should_create_archives()
        except Exception as e:
            self._log_operation("archive_check_failed", str(e), "warning")
            return False
    
    def create_workflow_archives(
        self,
        base_path: Path,
        output_directory: Path,
        form_data: FormData = None
    ) -> Result[List[Path]]:
        """Create archives as part of complete workflow"""
        try:
            self._log_operation("create_workflow_archives", f"base: {base_path}")
            return self.archive_service.create_archives(base_path, output_directory, form_data)
            
        except Exception as e:
            error = ReportGenerationError(
                f"Archive creation workflow failed: {e}",
                user_message="Failed to create archives."
            )
            self._handle_error(error, {'method': 'create_workflow_archives'})
            return Result.error(error)
    
    # Legacy compatibility methods
    def should_create_zip(self) -> bool:
        """Legacy method - check if ZIP creation is enabled in settings"""
        return self.should_create_archives()
    
    def create_zip_archives(self, base_path: Path, output_directory: Path, progress_callback=None) -> List[Path]:
        """Legacy method for backward compatibility"""
        try:
            result = self.create_workflow_archives(base_path, output_directory)
            if result.success:
                return result.value or []
            else:
                self._log_operation("legacy_zip_creation_failed", str(result.error), "error")
                return []
        except Exception as e:
            self._log_operation("legacy_zip_creation_error", str(e), "error")
            return []