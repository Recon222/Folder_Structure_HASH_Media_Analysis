#!/usr/bin/env python3
"""
ExifTool Worker Thread - Background processing for forensic metadata extraction
Follows unified worker pattern with Result objects and progress signals
"""

from pathlib import Path
from typing import List, Optional, Any
from threading import Event

from PySide6.QtCore import Signal

from .base_worker import BaseWorkerThread
from ..exiftool.exiftool_models import ExifToolSettings, ExifToolAnalysisResult
from ..result_types import Result
from ..exceptions import MediaAnalysisError
from ..logger import logger


class ExifToolWorker(BaseWorkerThread):
    """
    Worker thread for ExifTool metadata extraction
    Follows unified signal pattern established across application
    """
    
    # Unified signals
    result_ready = Signal(Result)       # Result[ExifToolAnalysisResult]
    progress_update = Signal(int, str)  # percentage, message
    
    def __init__(
        self,
        files: List[Path],
        settings: ExifToolSettings,
        service: Any,  # MediaAnalysisService
        form_data: Optional[Any] = None,
        parent=None
    ):
        """
        Initialize ExifTool worker
        
        Args:
            files: List of files to analyze
            settings: ExifTool extraction settings
            service: MediaAnalysisService instance
            form_data: Optional FormData for report generation
            parent: Parent QObject
        """
        super().__init__(parent)
        
        self.files = files
        self.settings = settings
        self.service = service
        self.form_data = form_data
        self.results: Optional[ExifToolAnalysisResult] = None
        
        logger.info(f"ExifToolWorker initialized for {len(files)} files")
    
    def execute(self) -> Result:
        """
        Execute ExifTool analysis in thread
        
        Returns:
            Result containing ExifToolAnalysisResult or error
        """
        try:
            # Progress: Starting
            self.progress_update.emit(0, "Starting ExifTool analysis...")
            
            # Check for cancellation
            if self.check_cancellation():
                raise MediaAnalysisError("Analysis cancelled by user")
            
            # Progress: Validation
            self.progress_update.emit(5, "Validating files...")
            
            # Validate that we have files
            if not self.files:
                return Result.error(
                    MediaAnalysisError(
                        "No files to analyze",
                        user_message="Please select files to analyze with ExifTool."
                    )
                )
            
            # Progress callback for service
            def progress_callback(percentage: float, message: str):
                """Internal progress callback"""
                # Map service progress (0-100) to worker progress (5-95)
                adjusted_progress = 5 + int(percentage * 0.9)
                self.progress_update.emit(adjusted_progress, message)
                
                # Check for cancellation
                if self.check_cancellation():
                    raise MediaAnalysisError("Analysis cancelled")
            
            # Progress: Analysis
            self.progress_update.emit(10, f"Analyzing {len(self.files)} files with ExifTool...")
            
            # Perform analysis through service
            result = self.service.analyze_with_exiftool(
                self.files,
                self.settings,
                progress_callback=progress_callback
            )
            
            # Check result
            if not result.success:
                logger.error(f"ExifTool analysis failed: {result.error}")
                return result
            
            # Store results
            self.results = result.value
            
            # Progress: Complete
            self.progress_update.emit(95, "Processing complete")
            
            # Build completion message
            completion_message = self._build_completion_message(self.results)
            self.progress_update.emit(100, completion_message)
            
            logger.info(
                f"ExifTool analysis complete: {self.results.successful} successful, "
                f"{self.results.failed} failed, {len(self.results.gps_locations)} with GPS"
            )
            
            return result
            
        except MediaAnalysisError as e:
            # Check if it's a cancellation
            if "cancelled" in str(e).lower():
                logger.info("ExifTool analysis cancelled by user")
                return Result.error(
                    MediaAnalysisError(
                        str(e),
                        user_message="Analysis cancelled."
                    )
                )
            else:
                # Re-raise if not a cancellation
                raise
            
        except Exception as e:
            logger.error(f"ExifTool worker error: {e}", exc_info=True)
            return Result.error(
                MediaAnalysisError(
                    f"Analysis failed: {str(e)}",
                    user_message="An error occurred during ExifTool analysis."
                )
            )
    
    def _build_completion_message(self, results: ExifToolAnalysisResult) -> str:
        """
        Build user-friendly completion message
        
        Args:
            results: Analysis results
            
        Returns:
            Completion message string
        """
        parts = []
        
        # Basic counts
        parts.append(f"Analyzed {results.total_files} files")
        
        if results.successful > 0:
            parts.append(f"{results.successful} successful")
        
        if results.failed > 0:
            parts.append(f"{results.failed} failed")
        
        # GPS information
        if results.gps_locations:
            parts.append(f"{len(results.gps_locations)} with GPS data")
        
        # Device information
        if results.device_map:
            device_count = len(results.device_map)
            parts.append(f"{device_count} unique device{'s' if device_count != 1 else ''}")
        
        # Processing time
        if results.processing_time > 0:
            parts.append(f"completed in {results.processing_time:.1f}s")
        
        return ", ".join(parts)
    
    def get_results(self) -> Optional[ExifToolAnalysisResult]:
        """
        Get analysis results
        
        Returns:
            ExifToolAnalysisResult or None
        """
        return self.results
    
    def cancel(self):
        """Cancel the analysis"""
        logger.info("ExifTool analysis cancellation requested")
        super().cancel()
        
        # The service will check for cancellation during processing
        # via the progress callback