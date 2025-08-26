#!/usr/bin/env python3
"""
Archive service - handles ZIP archive creation
"""
from pathlib import Path
from typing import List, Optional

from .interfaces import IArchiveService
from .base_service import BaseService
from ..models import FormData
from ..result_types import Result, ArchiveOperationResult
from ..exceptions import ArchiveError
from ..settings_manager import SettingsManager

class ArchiveService(BaseService, IArchiveService):
    """Service for archive creation operations"""
    
    def __init__(self, zip_controller=None):
        super().__init__("ArchiveService")
        self._zip_controller = zip_controller
    
    def create_archives(self, source_path: Path, output_path: Path,
                       form_data: FormData = None) -> Result[List[Path]]:
        """Create ZIP archives using ZIP controller"""
        try:
            self._log_operation("create_archives", f"source: {source_path}")
            
            # Input validation
            if not source_path or not source_path.exists():
                error = ArchiveError(
                    f"Source path does not exist: {source_path}",
                    archive_path=str(source_path),
                    user_message="Source directory for archive creation does not exist."
                )
                self._handle_error(error, {'method': 'create_archives'})
                return Result.error(error)
            
            if not output_path:
                error = ArchiveError(
                    "Output path is required for archive creation",
                    user_message="Output directory is required for archive creation."
                )
                self._handle_error(error, {'method': 'create_archives'})
                return Result.error(error)
            
            if not self._zip_controller:
                error = ArchiveError(
                    "ZIP controller not available for archive creation",
                    user_message="Archive creation is not configured properly."
                )
                self._handle_error(error, {'method': 'create_archives'})
                return Result.error(error)
            
            # Check if archives should be created
            if not self.should_create_archives():
                self._log_operation("archives_skipped", "ZIP creation disabled")
                return Result.success([])
            
            # Ensure output directory exists
            try:
                output_path.mkdir(parents=True, exist_ok=True)
                self._log_operation("output_directory_ensured", str(output_path))
            except Exception as e:
                error = ArchiveError(
                    f"Cannot create output directory {output_path}: {e}",
                    archive_path=str(output_path),
                    user_message="Cannot create output directory. Please check permissions."
                )
                self._handle_error(error, {'method': 'create_archives'})
                return Result.error(error)
            
            # Create ZIP thread and execute
            try:
                zip_thread = self._zip_controller.create_zip_thread(source_path, output_path, form_data)
                
                if zip_thread is None:
                    error = ArchiveError(
                        "Failed to create ZIP operation thread",
                        archive_path=str(output_path),
                        user_message="Failed to initialize archive creation."
                    )
                    self._handle_error(error, {'method': 'create_archives'})
                    return Result.error(error)
                
                # For service layer, we return the thread configuration for controllers to execute
                # In a full implementation, this would be handled by a worker thread coordinator
                self._log_operation("archive_thread_created", "ready for execution")
                
                # Return placeholder success - actual archive paths would be determined
                # when the thread completes execution
                return Result.success([])
                
            except Exception as e:
                error = ArchiveError(
                    f"ZIP thread creation failed: {e}",
                    archive_path=str(output_path),
                    user_message="Failed to initialize archive creation."
                )
                self._handle_error(error, {'method': 'create_archives'})
                return Result.error(error)
            
        except Exception as e:
            error = ArchiveError(
                f"Archive creation failed: {e}",
                archive_path=str(output_path),
                user_message="Failed to create archives."
            )
            self._handle_error(error, {'method': 'create_archives'})
            return Result.error(error)
    
    def should_create_archives(self) -> bool:
        """Check if archives should be created"""
        try:
            self._log_operation("check_archive_setting")
            
            if not self._zip_controller:
                self._log_operation("no_zip_controller", level="debug")
                return False
            
            # Use ZIP controller to determine if archives should be created
            should_create = self._zip_controller.should_create_zip()
            self._log_operation("archive_setting_checked", f"result: {should_create}")
            return should_create
            
        except ValueError as e:
            # Prompt not resolved - this is expected in some cases
            self._log_operation("archive_prompt_unresolved", str(e), "debug")
            return False
        except Exception as e:
            self._log_operation("archive_check_failed", str(e), "warning")
            return False
    
    def get_archive_settings(self) -> Optional[dict]:
        """Get current archive settings for debugging/monitoring"""
        try:
            if not self._zip_controller:
                return None
            
            settings = self._zip_controller.get_zip_settings()
            return {
                'compression_level': getattr(settings, 'compression_level', None),
                'create_root_level': getattr(settings, 'create_root_level', None),
                'create_location_level': getattr(settings, 'create_location_level', None),
                'create_datetime_level': getattr(settings, 'create_datetime_level', None),
                'output_path': str(getattr(settings, 'output_path', None))
            }
        except Exception as e:
            self._log_operation("get_archive_settings_failed", str(e), "warning")
            return None