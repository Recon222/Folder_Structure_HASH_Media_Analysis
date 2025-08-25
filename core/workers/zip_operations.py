"""
ZIP operation thread for non-blocking archive creation

Nuclear migration complete - unified error handling and Result objects.
"""
from PySide6.QtCore import Signal
from pathlib import Path
from typing import List, Optional
import zipfile

# Nuclear migration imports
from .base_worker import BaseWorkerThread
from ..result_types import ArchiveOperationResult, Result
from ..exceptions import ArchiveError, ValidationError, ErrorSeverity
from ..error_handler import handle_error

# Existing imports
from utils.zip_utils import ZipUtility, ZipSettings


class ZipOperationThread(BaseWorkerThread):
    """
    Thread for ZIP archive creation operations with unified error handling
    
    NUCLEAR MIGRATION COMPLETE:
    - OLD: progress = Signal(int)              ❌ REMOVED
    - OLD: status = Signal(str)                ❌ REMOVED  
    - OLD: finished = Signal(bool, str, list)  ❌ REMOVED
    - NEW: result_ready = Signal(Result)       ✅ UNIFIED (inherited)
    - NEW: progress_update = Signal(int, str)  ✅ UNIFIED (inherited)
    """
    
    # Unified signals inherited from BaseWorkerThread:
    # result_ready = Signal(Result)      # Archive operation result
    # progress_update = Signal(int, str) # Archive creation progress
    
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
        # cancelled is inherited from BaseWorkerThread
        
        # Set descriptive operation name
        archive_count = sum([settings.create_at_root, settings.create_at_location, settings.create_at_datetime])
        self.set_operation_name(f"ZIP Archive Creation ({archive_count} levels)")
        
    def execute(self) -> Result:
        """Execute ZIP operations with comprehensive error handling"""
        try:
            # Input validation
            if not self.base_path or not self.base_path.exists():
                error = ValidationError(
                    field_errors={"base_path": f"Base path does not exist: {self.base_path}"},
                    user_message="Source directory not found. Please check the path and try again."
                )
                self.handle_error(error, {'stage': 'validation', 'base_path': str(self.base_path)})
                return Result.error(error)
            
            if not self.output_directory:
                error = ValidationError(
                    field_errors={"output_directory": "Output directory not specified"},
                    user_message="Output directory must be specified for archive creation."
                )
                self.handle_error(error, {'stage': 'validation'})
                return Result.error(error)
            
            if not self.settings:
                error = ValidationError(
                    field_errors={"settings": "ZIP settings not provided"},
                    user_message="Archive settings are required for ZIP creation."
                )
                self.handle_error(error, {'stage': 'validation'})
                return Result.error(error)
            
            # Check for cancellation before starting
            self.check_cancellation()
            
            # Update output path in settings
            self.settings.output_path = self.output_directory
            
            # Create ZIP utility with progress callback
            self.zip_util = ZipUtility(
                progress_callback=lambda pct, msg: self.emit_progress(pct, msg)
            )
            
            # Create archives
            self.emit_progress(0, "Starting archive creation...")
            created_archives = self.zip_util.create_multi_level_archives(
                self.base_path,
                self.settings,
                self.form_data
            )
            
            # Check for cancellation after operation
            self.check_cancellation()
            
            # Validate results
            if not created_archives:
                error = ArchiveError(
                    "No archives were created during operation",
                    user_message="Archive creation completed but no files were created. Please check source directory.",
                    context={'base_path': str(self.base_path), 'settings': str(self.settings)}
                )
                self.handle_error(error, {'stage': 'result_validation'})
                return Result.error(error)
            
            # Create successful result
            result = ArchiveOperationResult.create_successful(
                created_archives,
                compression_level=self.settings.compression_level,
                metadata={
                    'base_path': str(self.base_path),
                    'output_directory': str(self.output_directory),
                    'archives_created': len(created_archives),
                    'settings': {
                        'create_at_root': self.settings.create_at_root,
                        'create_at_location': self.settings.create_at_location,
                        'create_at_datetime': self.settings.create_at_datetime
                    }
                }
            )
            
            self.emit_progress(100, f"Created {len(created_archives)} archives successfully")
            return result
            
        except ValidationError as e:
            # ValidationErrors are already properly formatted
            self.handle_error(e, {'stage': 'archive_creation'})
            return Result.error(e)
            
        except PermissionError as e:
            error = ArchiveError(
                f"Permission denied during archive creation: {e}",
                archive_path=str(self.output_directory),
                user_message="Cannot create archives. Please check folder permissions and try again."
            )
            self.handle_error(error, {'stage': 'permission_error', 'output_directory': str(self.output_directory)})
            return Result.error(error)
            
        except OSError as e:
            error = ArchiveError(
                f"File system error during archive creation: {e}",
                archive_path=str(self.output_directory),
                user_message="Archive creation failed due to a file system error. Please check available disk space."
            )
            self.handle_error(error, {'stage': 'filesystem_error', 'error_code': e.errno if hasattr(e, 'errno') else 'unknown'})
            return Result.error(error)
            
        except Exception as e:
            error = ArchiveError(
                f"Unexpected error during archive creation: {e}",
                archive_path=str(self.output_directory) if self.output_directory else None,
                user_message="Archive creation failed due to an unexpected error."
            )
            context = {
                'stage': 'unexpected_error',
                'exception_type': e.__class__.__name__,
                'exception_str': str(e),
                'severity': 'critical'
            }
            self.handle_error(error, context)
            return Result.error(error)
    
    def cancel(self):
        """Cancel the ZIP operation"""
        # Call base class cancel for unified cancellation
        super().cancel()
        
        # Cancel the ZIP utility operation if running
        if self.zip_util:
            self.zip_util.cancel()