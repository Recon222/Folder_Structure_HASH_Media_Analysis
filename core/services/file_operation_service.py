#!/usr/bin/env python3
"""
File operation service - handles file and folder operations
"""
from pathlib import Path
from typing import List

from .interfaces import IFileOperationService
from .base_service import BaseService
from ..result_types import FileOperationResult
from ..exceptions import FileOperationError
from ..buffered_file_ops import BufferedFileOperations

class FileOperationService(BaseService, IFileOperationService):
    """Service for file and folder operations"""
    
    def __init__(self):
        super().__init__("FileOperationService")
    
    def copy_files(self, files: List[Path], destination: Path, 
                  calculate_hash: bool = True) -> FileOperationResult:
        """Copy files to destination using buffered operations"""
        try:
            self._log_operation("copy_files", f"{len(files)} files to {destination}")
            
            # Input validation
            if not files:
                error = FileOperationError(
                    "No files provided for copy operation",
                    user_message="No files selected for copying."
                )
                self._handle_error(error, {'method': 'copy_files'})
                return FileOperationResult(success=False, error=error, value={})
            
            if not destination:
                error = FileOperationError(
                    "Destination path is required for copy operation",
                    user_message="Destination directory is required."
                )
                self._handle_error(error, {'method': 'copy_files'})
                return FileOperationResult(success=False, error=error, value={})
            
            # Ensure destination exists
            try:
                destination.mkdir(parents=True, exist_ok=True)
                self._log_operation("destination_ensured", str(destination))
            except Exception as e:
                error = FileOperationError(
                    f"Cannot create destination directory {destination}: {e}",
                    user_message="Cannot create destination directory. Please check permissions."
                )
                self._handle_error(error, {'method': 'copy_files'})
                return FileOperationResult(success=False, error=error, value={})
            
            # Filter valid files
            valid_files = []
            for file_path in files:
                if file_path.exists() and file_path.is_file():
                    valid_files.append(file_path)
                else:
                    self.logger.warning(f"Skipping invalid file: {file_path}")
            
            if not valid_files:
                error = FileOperationError(
                    "No valid files found for copy operation",
                    user_message="No valid files found. Please check file paths."
                )
                self._handle_error(error, {'method': 'copy_files'})
                return FileOperationResult(success=False, error=error, value={})
            
            # Create buffered file operations
            file_ops = BufferedFileOperations()
            
            # Execute copy operation
            result = file_ops.copy_files(valid_files, destination, calculate_hash)
            
            self._log_operation("copy_files_completed", 
                              f"processed {result.files_processed} files")
            return result
            
        except Exception as e:
            error = FileOperationError(
                f"File copy operation failed: {e}",
                user_message="File copy operation failed. Please check file permissions and disk space."
            )
            self._handle_error(error, {'method': 'copy_files'})
            return FileOperationResult(success=False, error=error, value={})
    
    def copy_folders(self, folders: List[Path], destination: Path,
                    calculate_hash: bool = True) -> FileOperationResult:
        """Copy folders to destination"""
        try:
            self._log_operation("copy_folders", f"{len(folders)} folders to {destination}")
            
            # Input validation
            if not folders:
                error = FileOperationError(
                    "No folders provided for copy operation",
                    user_message="No folders selected for copying."
                )
                self._handle_error(error, {'method': 'copy_folders'})
                return FileOperationResult(success=False, error=error, value={})
            
            if not destination:
                error = FileOperationError(
                    "Destination path is required for copy operation",
                    user_message="Destination directory is required."
                )
                self._handle_error(error, {'method': 'copy_folders'})
                return FileOperationResult(success=False, error=error, value={})
            
            # Expand folders to files for processing
            all_files = []
            for folder in folders:
                if folder.exists() and folder.is_dir():
                    try:
                        # Get all files in folder recursively
                        folder_files = list(folder.rglob('*'))
                        files_only = [f for f in folder_files if f.is_file()]
                        all_files.extend(files_only)
                        self._log_operation("folder_expanded", 
                                          f"{folder}: {len(files_only)} files")
                    except Exception as e:
                        self.logger.warning(f"Error expanding folder {folder}: {e}")
                else:
                    self.logger.warning(f"Skipping invalid folder: {folder}")
            
            if not all_files:
                error = FileOperationError(
                    "No files found in provided folders",
                    user_message="No files found in the selected folders."
                )
                self._handle_error(error, {'method': 'copy_folders'})
                return FileOperationResult(success=False, error=error, value={})
            
            # Use file copy operation for consistency
            self._log_operation("folder_copy_delegated", f"processing {len(all_files)} files")
            return self.copy_files(all_files, destination, calculate_hash)
            
        except Exception as e:
            error = FileOperationError(
                f"Folder copy operation failed: {e}",
                user_message="Folder copy operation failed. Please check folder permissions."
            )
            self._handle_error(error, {'method': 'copy_folders'})
            return FileOperationResult(success=False, error=error, value={})