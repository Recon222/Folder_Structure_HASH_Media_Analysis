"""
Concatenate controller.

Orchestrates concatenation workflows between UI, workers, and services.
Manages worker lifecycle and provides a clean interface for the UI layer.
"""

from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal

from ..models.concatenate_settings import ConcatenateSettings
from ..models.processing_result import ProcessingResult
from ..workers.concatenate_worker import ConcatenateWorker


class ConcatenateController(QObject):
    """
    Controller for concatenation operations.
    
    Provides a clean interface for the UI to initiate concatenation operations.
    Manages worker thread lifecycle and signal forwarding.
    
    Signals:
        progress_update: (percentage: float, message: str)
        concatenate_complete: (result: ProcessingResult)
        concatenate_error: (error_message: str)
    """
    
    # Signals
    progress_update = pyqtSignal(float, str)  # percentage, message
    concatenate_complete = pyqtSignal(ProcessingResult)  # result
    concatenate_error = pyqtSignal(str)  # error message
    
    def __init__(self, parent=None):
        """
        Initialize concatenate controller.
        
        Args:
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self.worker: Optional[ConcatenateWorker] = None
    
    def start_concatenate(
        self,
        settings: ConcatenateSettings
    ):
        """
        Start concatenation operation in background thread.
        
        Args:
            settings: ConcatenateSettings configuration (includes input files and output)
        
        Raises:
            RuntimeError: If a concatenation operation is already running
        """
        if self.worker and self.worker.isRunning():
            raise RuntimeError("Concatenation operation already in progress")
        
        # Create worker
        self.worker = ConcatenateWorker(
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
    
    def cancel_concatenate(self):
        """
        Cancel ongoing concatenation operation.
        
        Requests cancellation from the worker thread. The operation may take
        time to stop as it waits for FFmpeg to finish.
        """
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
    
    def is_running(self) -> bool:
        """
        Check if a concatenation operation is currently running.
        
        Returns:
            True if operation is in progress
        """
        return self.worker is not None and self.worker.isRunning()
    
    def _on_progress_update(self, percentage: float, message: str):
        """Handle progress update from worker."""
        self.progress_update.emit(percentage, message)
    
    def _on_result_ready(self, result: ProcessingResult):
        """Handle result from worker."""
        self.concatenate_complete.emit(result)
    
    def _on_error(self, error_message: str):
        """Handle error from worker."""
        self.concatenate_error.emit(error_message)
    
    def _on_worker_finished(self):
        """Handle worker thread completion."""
        # Clean up worker reference
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
