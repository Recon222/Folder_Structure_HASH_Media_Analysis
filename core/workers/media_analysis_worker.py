#!/usr/bin/env python3
"""
Media Analysis Worker - Thread handling for media analysis operations
Follows unified worker patterns with Result objects
"""

from pathlib import Path
from typing import List, Optional, Any
import time

from core.workers.base_worker import BaseWorkerThread
from core.media_analysis_models import MediaAnalysisSettings, MediaAnalysisResult
from core.models import FormData
from core.result_types import Result
from core.exceptions import MediaAnalysisError
from core.logger import logger


class MediaAnalysisWorker(BaseWorkerThread):
    """
    Worker thread for media analysis operations
    Processes media files and extracts metadata using the media service
    """
    
    def __init__(
        self,
        files: List[Path],
        settings: MediaAnalysisSettings,
        service: Any,  # IMediaAnalysisService
        form_data: Optional[FormData] = None
    ):
        """
        Initialize media analysis worker
        
        Args:
            files: List of files to analyze
            settings: Analysis settings and preferences
            service: Media analysis service instance
            form_data: Optional form data for report generation
        """
        super().__init__()
        
        self.files = files
        self.settings = settings
        self.service = service
        self.form_data = form_data
        
        # Track operation state
        self.analysis_result: Optional[MediaAnalysisResult] = None
        
        # Set operation name for logging
        self.set_operation_name(f"Media Analysis ({len(files)} files)")
    
    def execute(self) -> Result[MediaAnalysisResult]:
        """
        Execute media analysis operation
        
        Returns:
            Result containing MediaAnalysisResult or error
        """
        try:
            # Check for cancellation at start
            self.check_cancellation()
            
            # Initial progress
            self.emit_progress(0, f"Starting analysis of {len(self.files)} files...")
            
            # Create progress callback for service
            def progress_callback(completed: int, total: int):
                """Progress callback from service to worker"""
                if self.is_cancelled():
                    raise InterruptedError("Operation cancelled")
                
                # Calculate percentage (reserve 0-5% for setup, 5-95% for processing, 95-100% for completion)
                percentage = 5 + int((completed / total) * 90) if total > 0 else 5
                
                # Emit progress with descriptive message
                self.emit_progress(
                    percentage,
                    f"Analyzed {completed}/{total} files"
                )
                
                # Check for pause
                self.check_pause()
            
            # Perform analysis through service
            self.emit_progress(5, "Analyzing media files...")
            
            result = self.service.analyze_media_files(
                self.files,
                self.settings,
                progress_callback=progress_callback
            )
            
            # Check if analysis was successful
            if not result.success:
                return result
            
            # Store result for later use
            self.analysis_result = result.value
            
            # Final progress
            self.emit_progress(100, self._build_completion_message(self.analysis_result))
            
            logger.info(f"Media analysis completed: {self.analysis_result.successful} successful, "
                       f"{self.analysis_result.failed} failed, {self.analysis_result.skipped} skipped")
            
            return result
            
        except InterruptedError:
            # User cancelled
            error = MediaAnalysisError(
                "Operation cancelled by user",
                user_message="Media analysis was cancelled."
            )
            logger.info("Media analysis cancelled by user")
            return Result.error(error)
            
        except Exception as e:
            # Unexpected error
            error = MediaAnalysisError(
                f"Media analysis failed: {e}",
                user_message="An error occurred during media analysis."
            )
            self.handle_error(error)
            return Result.error(error)
    
    def _build_completion_message(self, result: MediaAnalysisResult) -> str:
        """
        Build descriptive completion message
        
        Args:
            result: Analysis result
            
        Returns:
            Completion message string
        """
        parts = []
        
        if result.successful > 0:
            parts.append(f"{result.successful} media files analyzed")
        
        if result.skipped > 0:
            parts.append(f"{result.skipped} non-media files skipped")
        
        if result.failed > 0:
            parts.append(f"{result.failed} failed")
        
        if not parts:
            return "Analysis complete"
        
        message = "Analysis complete: " + ", ".join(parts)
        
        # Add performance info
        if result.processing_time > 0:
            message += f" ({result.processing_time:.1f}s)"
        
        return message
    
    def get_results(self) -> Optional[MediaAnalysisResult]:
        """
        Get analysis results if available
        
        Returns:
            MediaAnalysisResult or None if not complete
        """
        return self.analysis_result
    
    def cleanup(self):
        """Clean up worker resources"""
        # Cancel any ongoing operations
        if self.isRunning():
            self.cancel()
            self.wait(2000)  # Wait up to 2 seconds
        
        # Clear references
        self.files = []
        self.analysis_result = None
        self.service = None
        
        super().cleanup()