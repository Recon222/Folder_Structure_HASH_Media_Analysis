"""
Concatenate worker.

Background thread worker for executing video concatenation operations
with progress reporting via Qt signals.
"""

from PySide6.QtCore import QThread, Signal

from ..models.concatenate_settings import ConcatenateSettings
from ..models.processing_result import ProcessingResult
from ..services.concatenate_service import ConcatenateService


class ConcatenateWorker(QThread):
    """
    Background worker for concatenation operations.
    
    Runs ConcatenateService in a separate thread to prevent UI blocking.
    Emits signals for progress updates and completion.
    
    Signals:
        progress_update: (percentage: float, message: str)
        result_ready: (result: ProcessingResult)
        error: (error_message: str)
    """
    
    # Signals
    progress_update = Signal(float, str)  # percentage, message
    result_ready = Signal(ProcessingResult)  # result
    error = Signal(str)  # error message
    
    def __init__(
        self,
        settings: ConcatenateSettings,
        parent=None
    ):
        """
        Initialize concatenate worker.
        
        Args:
            settings: ConcatenateSettings configuration (includes input files and output path)
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self.settings = settings
        self.service = ConcatenateService()
        self._cancelled = False
    
    def run(self):
        """
        Execute concatenation operation in background thread.
        
        This method is called when the thread starts. It joins multiple video
        files and emits signals for progress and completion.
        """
        try:
            # Define progress callback
            def progress_callback(percentage: float, message: str):
                if not self._cancelled:
                    self.progress_update.emit(percentage, message)
            
            # Execute concatenation
            result = self.service.concatenate_files(
                settings=self.settings,
                progress_callback=progress_callback
            )
            
            # Emit result
            if not self._cancelled:
                self.result_ready.emit(result)
        
        except Exception as e:
            self.error.emit(f"Concatenate worker error: {str(e)}")
    
    def cancel(self):
        """
        Cancel the concatenation operation.
        
        Sets cancellation flag which will be checked by the service.
        """
        self._cancelled = True
        self.service.cancel()
