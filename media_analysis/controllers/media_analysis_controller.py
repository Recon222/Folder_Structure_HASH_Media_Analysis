#!/usr/bin/env python3
"""
Media Analysis Controller - Orchestrates media analysis operations
Follows SOA architecture with full service integration
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from controllers.base_controller import BaseController
from core.services.interfaces import IMediaAnalysisService, IReportService
from ..workers.media_analysis_worker import MediaAnalysisWorker
from core.workers.exiftool_worker import ExifToolWorker
from ..core.media_analysis_models import MediaAnalysisSettings, MediaAnalysisResult
from ..exiftool.exiftool_models import ExifToolSettings, ExifToolAnalysisResult, GPSData
from core.models import FormData
from core.result_types import Result
from core.exceptions import MediaAnalysisError
from core.logger import logger
from core.resource_coordinators import WorkerResourceCoordinator


class MediaAnalysisController(BaseController):
    """Controller for media analysis operations"""
    
    def __init__(self):
        """Initialize media analysis controller"""
        super().__init__("MediaAnalysisController")
        self.current_worker: Optional[MediaAnalysisWorker] = None
        self._current_worker_id: Optional[str] = None
        
        # Service dependencies (lazy loaded)
        self._media_service = None
        self._report_service = None
    
    def _create_resource_coordinator(self, component_id: str) -> WorkerResourceCoordinator:
        """Use WorkerResourceCoordinator for media analysis worker management"""
        return WorkerResourceCoordinator(component_id)
    
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
            
            # Track worker with resource coordinator
            if self.resources:
                self._current_worker_id = self.resources.track_worker(
                    worker,
                    name=f"media_analysis_{datetime.now():%H%M%S}"
                )
            
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
        
        # Clear references - coordinator handles cleanup
        self.current_worker = None
        self._current_worker_id = None
        
        if self.current_worker:
            logger.info("Analysis operation cancelled")
    
    def get_ffprobe_status(self) -> Dict[str, Any]:
        """
        Get FFprobe availability status
        
        Returns:
            Dictionary with ffprobe status information
        """
        return self.media_service.get_ffprobe_status()
    
    def start_exiftool_workflow(
        self,
        paths: List[Path],
        settings: ExifToolSettings,
        form_data: Optional[FormData] = None
    ) -> Result[ExifToolWorker]:
        """
        Start ExifTool analysis workflow
        
        Args:
            paths: List of files/folders to analyze
            settings: ExifTool analysis settings
            form_data: Optional form data for report generation
            
        Returns:
            Result containing ExifToolWorker or error
        """
        try:
            self._log_operation("start_exiftool_workflow", 
                              f"Starting ExifTool analysis of {len(paths)} items")
            
            # Step 1: Validate files (ExifTool can handle more formats than FFprobe)
            valid_files = []
            for path in paths:
                if path.is_file():
                    valid_files.append(path)
                elif path.is_dir():
                    # Get all files from directory
                    valid_files.extend(path.rglob("*"))
            
            # Filter to only files
            valid_files = [f for f in valid_files if f.is_file()]
            
            if not valid_files:
                error = MediaAnalysisError(
                    "No valid files found to analyze",
                    user_message="No files found in the selected items."
                )
                self._handle_error(error)
                return Result.error(error)
            
            logger.info(f"Found {len(valid_files)} files for ExifTool analysis")
            
            # Step 2: Create worker thread
            worker = ExifToolWorker(
                files=valid_files,
                settings=settings,
                service=self.media_service,
                form_data=form_data
            )
            
            # Store reference to current worker
            self.current_worker = worker
            
            # Track worker with resource coordinator
            if self.resources:
                self._current_worker_id = self.resources.track_worker(
                    worker,
                    name=f"exiftool_{datetime.now():%H%M%S}"
                )
            
            logger.info(f"Created ExifToolWorker for {len(valid_files)} files")
            return Result.success(worker)
            
        except Exception as e:
            error = MediaAnalysisError(
                f"Failed to start ExifTool workflow: {e}",
                user_message="Failed to start ExifTool analysis. Please try again."
            )
            self._handle_error(error)
            return Result.error(error)
    
    def export_exiftool_to_csv(
        self,
        results: ExifToolAnalysisResult,
        output_path: Path
    ) -> Result[Path]:
        """
        Export ExifTool results to CSV
        
        Args:
            results: ExifTool analysis results
            output_path: Path for CSV file
            
        Returns:
            Result containing CSV path or error
        """
        try:
            self._log_operation("export_exiftool_to_csv", 
                              f"Exporting {results.total_files} ExifTool results to CSV")
            
            # Delegate to media service
            result = self.media_service.export_exiftool_to_csv(results, output_path)
            
            if result.success:
                logger.info(f"ExifTool CSV exported successfully to {output_path}")
            
            return result
            
        except Exception as e:
            error = MediaAnalysisError(
                f"Failed to export ExifTool CSV: {e}",
                user_message="Failed to export ExifTool results to CSV."
            )
            self._handle_error(error)
            return Result.error(error)
    
    def export_to_kml(
        self,
        gps_locations: List[GPSData],
        output_path: Path,
        group_by_device: bool = True
    ) -> Result[Path]:
        """
        Export GPS locations to KML
        
        Args:
            gps_locations: List of GPS location data
            output_path: Path for KML file
            group_by_device: Whether to group locations by device
            
        Returns:
            Result containing KML path or error
        """
        try:
            self._log_operation("export_to_kml", 
                              f"Exporting {len(gps_locations)} GPS locations to KML")
            
            # Delegate to media service
            result = self.media_service.export_to_kml(
                gps_locations, output_path, group_by_device
            )
            
            if result.success:
                logger.info(f"KML exported successfully to {output_path}")
            
            return result
            
        except Exception as e:
            error = MediaAnalysisError(
                f"Failed to export KML: {e}",
                user_message="Failed to export GPS locations to KML."
            )
            self._handle_error(error)
            return Result.error(error)
    
    def cleanup(self):
        """Clean up all resources"""
        # Cancel any running operation
        if self.current_worker and self.current_worker.isRunning():
            self.cancel_current_operation()
        
        # Let resource coordinator handle cleanup
        if self.resources:
            self.resources.cleanup_all()
        
        # Clear references
        self.current_worker = None
        self._current_worker_id = None