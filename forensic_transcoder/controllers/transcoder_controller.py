"""
Transcoder controller.

Orchestrates transcode workflows between UI, workers, and services.
Manages worker lifecycle and provides a clean interface for the UI layer.
"""

from pathlib import Path
from typing import List, Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal

from ..models.transcode_settings import TranscodeSettings
from ..models.processing_result import ProcessingResult, BatchProcessingStatistics
from ..workers.transcode_worker import TranscodeWorker


class TranscoderController(QObject):
    """
    Controller for transcode operations.
    
    Provides a clean interface for the UI to initiate transcode operations.
    Manages worker thread lifecycle and signal forwarding.
    
    Signals:
        progress_update: (percentage: float, message: str)
        transcode_complete: (result: ProcessingResult or BatchProcessingStatistics)
        transcode_error: (error_message: str)
    """
    
    # Signals
    progress_update = pyqtSignal(float, str)  # percentage, message
    transcode_complete = pyqtSignal(object)  # ProcessingResult or BatchProcessingStatistics
    transcode_error = pyqtSignal(str)  # error message
    
    def __init__(self, parent=None):
        """
        Initialize transcoder controller.
        
        Args:
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self.worker: Optional[TranscodeWorker] = None
    
    def start_transcode(
        self,
        input_files: List[Path],
        settings: TranscodeSettings
    ):
        """
        Start transcode operation in background thread.
        
        Args:
            input_files: List of input file paths
            settings: TranscodeSettings configuration
        
        Raises:
            RuntimeError: If a transcode operation is already running
        """
        if self.worker and self.worker.isRunning():
            raise RuntimeError("Transcode operation already in progress")
        
        # Create worker
        self.worker = TranscodeWorker(
            input_files=input_files,
            settings=settings,
            parent=self
        )
        
        # Connect signals
        self.worker.progress_update.connect(self._on_progress_update)
        self.worker.result_ready.connect(self._on_result_ready)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self._on_worker_finished)
        
        # Start worker
        self.worker.start()
    
    def cancel_transcode(self):
        """
        Cancel ongoing transcode operation.
        
        Requests cancellation from the worker thread. The operation may take
        time to stop as it waits for the current file to complete.
        """
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
    
    def is_running(self) -> bool:
        """
        Check if a transcode operation is currently running.
        
        Returns:
            True if operation is in progress
        """
        return self.worker is not None and self.worker.isRunning()
    
    def _on_progress_update(self, percentage: float, message: str):
        """Handle progress update from worker."""
        self.progress_update.emit(percentage, message)
    
    def _on_result_ready(self, result):
        """Handle result from worker."""
        self.transcode_complete.emit(result)
    
    def _on_error(self, error_message: str):
        """Handle error from worker."""
        self.transcode_error.emit(error_message)
    
    def _on_worker_finished(self):
        """Handle worker thread completion."""
        # Clean up worker reference
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
