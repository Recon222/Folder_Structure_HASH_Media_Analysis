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
    
    def generate_reports_with_path_determination(
        self,
        form_data: FormData,
        file_operation_result,
        output_directory: Path,
        settings
    ) -> Result[Dict]:
        """
        Generate reports with proper path determination
        
        This method handles the complete report generation workflow including:
        1. Extracting the base forensic path from the file operation result
        2. Determining the correct documents location based on template settings
        3. Generating all requested reports
        
        Args:
            form_data: Form data with report information
            file_operation_result: Result object from file operations containing base_forensic_path
            output_directory: Base output directory
            settings: Settings object with report generation flags
            
        Returns:
            Result containing generated reports and documents directory
        """
        try:
            self._log_operation("generate_reports_with_path_determination", "Starting report generation with path determination")
            
            # Extract base forensic path from result metadata
            base_forensic_path = None
            if hasattr(file_operation_result, 'metadata') and file_operation_result.metadata:
                base_forensic_path = file_operation_result.metadata.get('base_forensic_path')
            
            if not base_forensic_path:
                # Fallback: try to reconstruct the path using PathService
                from core.services.interfaces import IPathService
                path_service = self._get_service(IPathService)
                path_result = path_service.build_forensic_path(form_data, output_directory)
                if path_result.success:
                    base_forensic_path = str(path_result.value)
                    self._log_operation("base_path_reconstructed", f"Reconstructed base path: {base_forensic_path}")
                else:
                    error = ReportGenerationError(
                        "Cannot determine base forensic path for documents placement",
                        user_message="Cannot determine where to place documents. Please check the folder structure."
                    )
                    self._handle_error(error, {'method': 'generate_reports_with_path_determination'})
                    return Result.error(error)
            
            self._log_operation("base_forensic_path", f"Using base path: {base_forensic_path}")
            
            # Use PathService to determine documents location
            from core.services.interfaces import IPathService
            path_service = self._get_service(IPathService)
            documents_location_result = path_service.determine_documents_location(
                Path(base_forensic_path),  # Pass the base forensic path, not a file path
                output_directory
            )
            
            if not documents_location_result.success:
                error = ReportGenerationError(
                    f"Failed to determine documents location: {documents_location_result.error.message}",
                    user_message=documents_location_result.error.user_message
                )
                self._handle_error(error, {'method': 'generate_reports_with_path_determination'})
                return Result.error(error)
            
            documents_dir = documents_location_result.value
            self._log_operation("documents_location", f"Documents will be placed at: {documents_dir}")
            
            # Extract file results from the Result object
            file_results = {}
            if hasattr(file_operation_result, 'value') and file_operation_result.value:
                file_results = file_operation_result.value
            
            # Generate reports based on settings
            generate_time_offset = getattr(settings, 'generate_time_offset_pdf', False)
            generate_upload_log = getattr(settings, 'generate_upload_log_pdf', False)
            generate_hash_csv = getattr(settings, 'calculate_hashes', False)
            
            generated_reports = self.generate_all_reports(
                form_data=form_data,
                file_results=file_results,
                output_dir=documents_dir,
                generate_time_offset=generate_time_offset,
                generate_upload_log=generate_upload_log,
                generate_hash_csv=generate_hash_csv
            )
            
            # Return success with both reports and documents directory
            return Result.success({
                'reports': generated_reports,
                'documents_dir': documents_dir,
                'base_forensic_path': base_forensic_path
            })
            
        except Exception as e:
            error = ReportGenerationError(
                f"Report generation with path determination failed: {e}",
                user_message="Failed to generate reports. Please check the logs."
            )
            self._handle_error(error, {'method': 'generate_reports_with_path_determination'})
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