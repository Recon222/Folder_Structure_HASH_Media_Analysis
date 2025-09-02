#!/usr/bin/env python3
"""
Media Analysis Controller - Orchestrates media analysis operations
Follows SOA architecture with full service integration
"""

from pathlib import Path
from typing import List, Optional, Dict, Any

from .base_controller import BaseController
from core.services.interfaces import IMediaAnalysisService, IReportService
from core.workers.media_analysis_worker import MediaAnalysisWorker
from core.media_analysis_models import MediaAnalysisSettings, MediaAnalysisResult
from core.models import FormData
from core.result_types import Result
from core.exceptions import MediaAnalysisError
from core.logger import logger


class MediaAnalysisController(BaseController):
    """Controller for media analysis operations"""
    
    def __init__(self):
        """Initialize media analysis controller"""
        super().__init__("MediaAnalysisController")
        self.current_worker: Optional[MediaAnalysisWorker] = None
        
        # Service dependencies (lazy loaded)
        self._media_service = None
        self._report_service = None
    
    @property
    def media_service(self) -> IMediaAnalysisService:
        """Lazy load media analysis service"""
        if self._media_service is None:
            self._media_service = self._get_service(IMediaAnalysisService)
        return self._media_service
    
    @property
    def report_service(self) -> IReportService:
        """Lazy load report service"""
        if self._report_service is None:
            self._report_service = self._get_service(IReportService)
        return self._report_service
    
    def start_analysis_workflow(
        self,
        paths: List[Path],
        settings: MediaAnalysisSettings,
        form_data: Optional[FormData] = None
    ) -> Result[MediaAnalysisWorker]:
        """
        Start media analysis workflow
        
        This method orchestrates the entire analysis workflow:
        1. Validates input files
        2. Creates worker thread
        3. Returns worker for UI to monitor
        
        Args:
            paths: List of files/folders to analyze
            settings: Analysis settings and preferences
            form_data: Optional form data for report generation
            
        Returns:
            Result containing MediaAnalysisWorker or error
        """
        try:
            self._log_operation("start_analysis_workflow", 
                              f"Starting analysis of {len(paths)} items")
            
            # Step 1: Validate and prepare files
            validation_result = self.media_service.validate_media_files(paths)
            if not validation_result.success:
                return Result.error(validation_result.error)
            
            valid_files = validation_result.value
            
            if not valid_files:
                error = MediaAnalysisError(
                    "No valid files found to analyze",
                    user_message="No files found in the selected items."
                )
                self._handle_error(error)
                return Result.error(error)
            
            logger.info(f"Validated {len(valid_files)} files for analysis")
            
            # Step 2: Create worker thread
            worker = MediaAnalysisWorker(
                files=valid_files,
                settings=settings,
                service=self.media_service,
                form_data=form_data
            )
            
            # Store reference to current worker
            self.current_worker = worker
            
            logger.info(f"Created MediaAnalysisWorker for {len(valid_files)} files")
            return Result.success(worker)
            
        except Exception as e:
            error = MediaAnalysisError(
                f"Failed to start analysis workflow: {e}",
                user_message="Failed to start media analysis. Please try again."
            )
            self._handle_error(error)
            return Result.error(error)
    
    def generate_report(
        self,
        results: MediaAnalysisResult,
        output_path: Path,
        form_data: Optional[FormData] = None
    ) -> Result[Path]:
        """
        Generate PDF report from analysis results
        
        Args:
            results: Media analysis results
            output_path: Path for report file
            form_data: Optional form data for case information
            
        Returns:
            Result containing report path or error
        """
        try:
            self._log_operation("generate_report", 
                              f"Generating report with {len(results.metadata_list)} files")
            
            # Delegate to media service for report generation
            result = self.media_service.generate_analysis_report(
                results, output_path, form_data
            )
            
            if result.success:
                logger.info(f"Report generated successfully at {output_path}")
            
            return result
            
        except Exception as e:
            error = MediaAnalysisError(
                f"Failed to generate report: {e}",
                user_message="Failed to generate analysis report."
            )
            self._handle_error(error)
            return Result.error(error)
    
    def export_to_csv(
        self,
        results: MediaAnalysisResult,
        output_path: Path
    ) -> Result[Path]:
        """
        Export analysis results to CSV
        
        Args:
            results: Media analysis results
            output_path: Path for CSV file
            
        Returns:
            Result containing CSV path or error
        """
        try:
            self._log_operation("export_to_csv", 
                              f"Exporting {len(results.metadata_list)} results to CSV")
            
            # Delegate to media service
            result = self.media_service.export_to_csv(results, output_path)
            
            if result.success:
                logger.info(f"CSV exported successfully to {output_path}")
            
            return result
            
        except Exception as e:
            error = MediaAnalysisError(
                f"Failed to export CSV: {e}",
                user_message="Failed to export results to CSV."
            )
            self._handle_error(error)
            return Result.error(error)
    
    def cancel_current_operation(self):
        """Cancel the current analysis operation if running"""
        if self.current_worker and self.current_worker.isRunning():
            self._log_operation("cancel_current_operation", "Cancelling analysis")
            self.current_worker.cancel()
            self.current_worker.wait(5000)  # Wait up to 5 seconds
            
            if self.current_worker.isRunning():
                logger.warning("Worker did not stop gracefully, terminating")
                self.current_worker.terminate()
            
            self.current_worker = None
            logger.info("Analysis operation cancelled")
    
    def get_ffprobe_status(self) -> Dict[str, Any]:
        """
        Get FFprobe availability status
        
        Returns:
            Dictionary with ffprobe status information
        """
        return self.media_service.get_ffprobe_status()
    
    def cleanup(self):
        """Clean up resources"""
        self.cancel_current_operation()
        super().cleanup()