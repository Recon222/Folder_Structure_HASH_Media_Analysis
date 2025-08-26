#!/usr/bin/env python3
"""
Report service - handles all report generation
"""
from pathlib import Path
from typing import Dict, Any

from .interfaces import IReportService
from .base_service import BaseService
from ..models import FormData
from ..result_types import ReportGenerationResult
from ..exceptions import ReportGenerationError
from ..pdf_gen import PDFGenerator

class ReportService(BaseService, IReportService):
    """Service for report generation operations"""
    
    def __init__(self):
        super().__init__("ReportService")
        self._pdf_generator = None
    
    @property
    def pdf_generator(self) -> PDFGenerator:
        """Lazy load PDF generator"""
        if self._pdf_generator is None:
            try:
                self._pdf_generator = PDFGenerator()
                self._log_operation("pdf_generator_initialized")
            except ImportError as e:
                error = ReportGenerationError(
                    f"PDF generator initialization failed: {e}",
                    report_type="initialization",
                    user_message="PDF generation requires reportlab. Install with: pip install reportlab"
                )
                self._handle_error(error, {'method': 'pdf_generator'})
                raise
        return self._pdf_generator
    
    def generate_time_offset_report(self, form_data: FormData, 
                                   output_path: Path) -> ReportGenerationResult:
        """Generate time offset report"""
        try:
            self._log_operation("generate_time_offset_report", str(output_path))
            
            # Input validation
            if not form_data:
                error = ReportGenerationError(
                    "Form data is required for time offset report generation",
                    report_type="time_offset",
                    output_path=str(output_path),
                    user_message="Form data is missing for report generation."
                )
                self._handle_error(error, {'method': 'generate_time_offset_report'})
                return ReportGenerationResult(success=False, error=error, value=output_path)
            
            if not output_path:
                error = ReportGenerationError(
                    "Output path is required for time offset report generation",
                    report_type="time_offset",
                    user_message="Output path is required for report generation."
                )
                self._handle_error(error, {'method': 'generate_time_offset_report'})
                return ReportGenerationResult(success=False, error=error, value=None)
            
            # Ensure output directory exists
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                self._log_operation("output_directory_ensured", str(output_path.parent))
            except Exception as e:
                error = ReportGenerationError(
                    f"Cannot create output directory {output_path.parent}: {e}",
                    report_type="time_offset",
                    output_path=str(output_path),
                    user_message="Cannot create output directory. Please check permissions."
                )
                self._handle_error(error, {'method': 'generate_time_offset_report'})
                return ReportGenerationResult(success=False, error=error, value=output_path)
            
            # Generate report using existing PDF generator
            result = self.pdf_generator.generate_time_offset_report(form_data, output_path)
            
            if result.success:
                self._log_operation("time_offset_report_generated", str(output_path))
            else:
                self._log_operation("time_offset_report_failed", str(result.error), "warning")
            
            return result
            
        except Exception as e:
            error = ReportGenerationError(
                f"Time offset report generation failed: {e}",
                report_type="time_offset",
                output_path=str(output_path),
                user_message="Failed to generate time offset report."
            )
            self._handle_error(error, {'method': 'generate_time_offset_report'})
            return ReportGenerationResult(success=False, error=error, value=output_path)
    
    def generate_technician_log(self, form_data: FormData,
                               output_path: Path) -> ReportGenerationResult:
        """Generate technician log report"""
        try:
            self._log_operation("generate_technician_log", str(output_path))
            
            # Input validation
            if not form_data:
                error = ReportGenerationError(
                    "Form data is required for technician log generation",
                    report_type="technician_log",
                    output_path=str(output_path),
                    user_message="Form data is missing for report generation."
                )
                self._handle_error(error, {'method': 'generate_technician_log'})
                return ReportGenerationResult(success=False, error=error, value=output_path)
            
            if not output_path:
                error = ReportGenerationError(
                    "Output path is required for technician log generation",
                    report_type="technician_log",
                    user_message="Output path is required for report generation."
                )
                self._handle_error(error, {'method': 'generate_technician_log'})
                return ReportGenerationResult(success=False, error=error, value=None)
            
            # Ensure output directory exists
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                self._log_operation("output_directory_ensured", str(output_path.parent))
            except Exception as e:
                error = ReportGenerationError(
                    f"Cannot create output directory {output_path.parent}: {e}",
                    report_type="technician_log",
                    output_path=str(output_path),
                    user_message="Cannot create output directory. Please check permissions."
                )
                self._handle_error(error, {'method': 'generate_technician_log'})
                return ReportGenerationResult(success=False, error=error, value=output_path)
            
            # Generate report using existing PDF generator
            result = self.pdf_generator.generate_technician_log(form_data, output_path)
            
            if result.success:
                self._log_operation("technician_log_generated", str(output_path))
            else:
                self._log_operation("technician_log_failed", str(result.error), "warning")
            
            return result
            
        except Exception as e:
            error = ReportGenerationError(
                f"Technician log generation failed: {e}",
                report_type="technician_log",
                output_path=str(output_path),
                user_message="Failed to generate technician log."
            )
            self._handle_error(error, {'method': 'generate_technician_log'})
            return ReportGenerationResult(success=False, error=error, value=output_path)
    
    def generate_hash_csv(self, file_results: Dict[str, Any],
                         output_path: Path) -> ReportGenerationResult:
        """Generate hash verification CSV"""
        try:
            self._log_operation("generate_hash_csv", str(output_path))
            
            # Input validation
            if not file_results:
                error = ReportGenerationError(
                    "File results are required for hash CSV generation",
                    report_type="hash_csv", 
                    output_path=str(output_path),
                    user_message="No file results available for hash verification CSV."
                )
                self._handle_error(error, {'method': 'generate_hash_csv'})
                return ReportGenerationResult(success=False, error=error, value=output_path)
            
            if not output_path:
                error = ReportGenerationError(
                    "Output path is required for hash CSV generation",
                    report_type="hash_csv",
                    user_message="Output path is required for CSV generation."
                )
                self._handle_error(error, {'method': 'generate_hash_csv'})
                return ReportGenerationResult(success=False, error=error, value=None)
            
            # Check if any files have hash values
            has_hashes = any(
                result.get('source_hash') or result.get('dest_hash') 
                for result in file_results.values()
                if isinstance(result, dict)  # Skip performance stats entry
            )
            
            if not has_hashes:
                self._log_operation("hash_csv_skipped", "no hash values found")
                # Return success but indicate no CSV was generated
                return ReportGenerationResult(
                    success=True,
                    message="No hash verification data available",
                    value=None
                )
            
            # Ensure output directory exists
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                self._log_operation("output_directory_ensured", str(output_path.parent))
            except Exception as e:
                error = ReportGenerationError(
                    f"Cannot create output directory {output_path.parent}: {e}",
                    report_type="hash_csv",
                    output_path=str(output_path),
                    user_message="Cannot create output directory. Please check permissions."
                )
                self._handle_error(error, {'method': 'generate_hash_csv'})
                return ReportGenerationResult(success=False, error=error, value=output_path)
            
            # Generate CSV using existing PDF generator
            result = self.pdf_generator.generate_hash_verification_csv(file_results, output_path)
            
            if result.success:
                self._log_operation("hash_csv_generated", str(output_path))
            else:
                self._log_operation("hash_csv_failed", str(result.error), "warning")
            
            return result
            
        except Exception as e:
            error = ReportGenerationError(
                f"Hash CSV generation failed: {e}",
                report_type="hash_csv", 
                output_path=str(output_path),
                user_message="Failed to generate hash verification CSV."
            )
            self._handle_error(error, {'method': 'generate_hash_csv'})
            return ReportGenerationResult(success=False, error=error, value=output_path)