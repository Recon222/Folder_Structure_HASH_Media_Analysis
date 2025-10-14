"""
Transcode worker.

Background thread worker for executing video transcoding operations
with progress reporting via Qt signals.
"""

from pathlib import Path
from typing import List, Optional
from PyQt6.QtCore import QThread, pyqtSignal

from ..models.transcode_settings import TranscodeSettings
from ..models.processing_result import ProcessingResult, BatchProcessingStatistics
from ..services.transcode_service import TranscodeService


class TranscodeWorker(QThread):
    """
    Background worker for transcode operations.
    
    Runs TranscodeService in a separate thread to prevent UI blocking.
    Emits signals for progress updates and completion.
    
    Signals:
        progress_update: (percentage: float, message: str)
        result_ready: (result: ProcessingResult or BatchProcessingStatistics)
        error: (error_message: str)
    """
    
    # Signals
    progress_update = pyqtSignal(float, str)  # percentage, message
    result_ready = pyqtSignal(object)  # ProcessingResult or BatchProcessingStatistics
    error = pyqtSignal(str)  # error message
    
    def __init__(
        self,
        input_files: List[Path],
        settings: TranscodeSettings,
        parent=None
    ):
        """
        Initialize transcode worker.
        
        Args:
            input_files: List of input file paths to transcode
            settings: TranscodeSettings configuration
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self.input_files = input_files
        self.settings = settings
        self.service = TranscodeService()
        self._cancelled = False
    
    def run(self):
        """
        Execute transcode operation(s) in background thread.
        
        This method is called when the thread starts. It processes single
        or multiple files and emits signals for progress and completion.
        """
        try:
            if len(self.input_files) == 1:
                # Single file transcode
                self._transcode_single()
            else:
                # Batch transcode
                self._transcode_batch()
        
        except Exception as e:
            self.error.emit(f"Transcode worker error: {str(e)}")
    
    def cancel(self):
        """
        Cancel the transcode operation.
        
        Sets cancellation flag which will be checked by the service
        during batch processing.
        """
        self._cancelled = True
        self.service.cancel()
    
    def _transcode_single(self):
        """Transcode a single file."""
        input_file = self.input_files[0]
        
        # Generate output path
        output_file = self._generate_output_path(input_file)
        
        # Define progress callback
        def progress_callback(percentage: float, message: str):
            if not self._cancelled:
                self.progress_update.emit(percentage, message)
        
        # Execute transcode
        result = self.service.transcode_file(
            input_file=input_file,
            output_file=output_file,
            settings=self.settings,
            progress_callback=progress_callback
        )
        
        # Emit result
        if not self._cancelled:
            self.result_ready.emit(result)
    
    def _transcode_batch(self):
        """Transcode multiple files."""
        # Define progress callback
        def progress_callback(percentage: float, message: str):
            if not self._cancelled:
                self.progress_update.emit(percentage, message)
        
        # Execute batch transcode
        results = self.service.transcode_batch(
            input_files=self.input_files,
            settings=self.settings,
            progress_callback=progress_callback
        )
        
        # Build statistics
        stats = BatchProcessingStatistics()
        for result in results:
            stats.add_result(result)
        
        # Emit result
        if not self._cancelled:
            self.result_ready.emit(stats)
    
    def _generate_output_path(self, input_file: Path) -> Path:
        """
        Generate output file path based on settings.
        
        Args:
            input_file: Input file path
        
        Returns:
            Output file path
        """
        # Get output directory
        if self.settings.output_directory:
            output_dir = self.settings.output_directory
        else:
            output_dir = input_file.parent
        
        # Parse filename pattern
        pattern = self.settings.output_filename_pattern
        
        # Replace placeholders
        original_name = input_file.stem
        ext = self.settings.output_format
        
        output_filename = pattern.format(
            original_name=original_name,
            ext=ext
        )
        
        output_path = output_dir / output_filename
        
        # Handle existing files
        if not self.settings.overwrite_existing and output_path.exists():
            counter = 1
            while output_path.exists():
                output_filename = pattern.format(
                    original_name=f"{original_name}_{counter}",
                    ext=ext
                )
                output_path = output_dir / output_filename
                counter += 1
        
        return output_path
