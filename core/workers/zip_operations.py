"""ZIP operation thread for non-blocking archive creation"""
from PySide6.QtCore import QThread, Signal
from pathlib import Path
from typing import List, Optional
import zipfile

from utils.zip_utils import ZipUtility, ZipSettings


class ZipOperationThread(QThread):
    """Thread for ZIP archive creation operations"""
    
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(bool, str, list)  # success, message, created_archives
    
    def __init__(self, base_path: Path, output_directory: Path, settings: ZipSettings, 
                 form_data=None):
        """Initialize ZIP operation thread
        
        Args:
            base_path: Root path for archive creation
            output_directory: Where to save archives
            settings: ZIP settings including compression and locations
            form_data: Optional FormData for creating descriptive ZIP names
        """
        super().__init__()
        self.base_path = base_path
        self.output_directory = output_directory
        self.settings = settings
        self.form_data = form_data
        self.zip_util: Optional[ZipUtility] = None
        self._is_cancelled = False
        
    def run(self):
        """Run ZIP operations in thread"""
        try:
            # Update output path in settings
            self.settings.output_path = self.output_directory
            
            # Create ZIP utility with progress callback
            self.zip_util = ZipUtility(
                progress_callback=lambda pct, msg: self._handle_progress(pct, msg)
            )
            
            # Create archives
            self.status.emit("Creating ZIP archives...")
            created = self.zip_util.create_multi_level_archives(
                self.base_path,
                self.settings,
                self.form_data
            )
            
            if self._is_cancelled:
                self.finished.emit(False, "ZIP operation cancelled", [])
            else:
                self.finished.emit(True, f"Created {len(created)} archives", created)
            
        except Exception as e:
            self.finished.emit(False, f"ZIP Error: {str(e)}", [])
    
    def _handle_progress(self, percentage: int, message: str):
        """Handle progress updates from ZIP utility
        
        Args:
            percentage: Progress percentage (0-100)
            message: Status message
        """
        if self._is_cancelled:
            return
            
        self.progress.emit(percentage)
        if message:
            self.status.emit(message)
    
    def cancel(self):
        """Cancel the ZIP operation"""
        self._is_cancelled = True
        if self.zip_util:
            self.zip_util.cancel()