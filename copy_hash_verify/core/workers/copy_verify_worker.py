#!/usr/bin/env python3
"""
Copy & Verify Worker - Background copy with hash verification thread

Performs file copy operations with integrated hash verification using
BufferedFileOperations for optimal performance.
"""

from pathlib import Path
from typing import List, Dict

from PySide6.QtCore import QThread, Signal

from core.buffered_file_ops import BufferedFileOperations
from core.result_types import Result, FileOperationResult
from core.logger import logger


class CopyVerifyWorker(QThread):
    """
    Background worker for copy with hash verification

    Signals:
        result_ready: Emitted when operation completes with Result object
        progress_update: Emitted during operation with (percentage, message)
    """

    # Unified signals matching core/workers/ pattern
    result_ready = Signal(Result)
    progress_update = Signal(int, str)

    def __init__(self, source_paths: List[Path], destination: Path,
                 algorithm: str = 'sha256', preserve_structure: bool = False,
                 parent=None):
        """
        Initialize copy & verify worker

        Args:
            source_paths: List of source file/folder paths
            destination: Destination directory path
            algorithm: Hash algorithm ('sha256', 'sha1', 'md5')
            preserve_structure: Whether to preserve folder structure
            parent: Parent QObject
        """
        super().__init__(parent)

        self.source_paths = source_paths
        self.destination = destination
        self.algorithm = algorithm
        self.preserve_structure = preserve_structure
        self.file_ops = None
        self._is_cancelled = False
        self._is_paused = False

    def run(self):
        """Execute copy with verification in background thread"""
        try:
            logger.info(
                f"CopyVerifyWorker starting: {len(self.source_paths)} items to {self.destination}"
            )

            # Create file operations handler with callbacks
            self.file_ops = BufferedFileOperations(
                progress_callback=self._on_progress,
                cancelled_check=self._check_cancelled,
                pause_check=self._check_paused
            )

            # Discover all files to copy with structure information
            # Build list of (type, path, relative_path) tuples for structure preservation
            all_items = []

            for source_path in self.source_paths:
                if source_path.is_file():
                    # Single file
                    if self.preserve_structure:
                        # Preserve the filename within its parent context
                        relative_path = source_path.name
                    else:
                        # Flat copy - no relative path
                        relative_path = None

                    all_items.append(('file', source_path, relative_path))

                elif source_path.is_dir():
                    # Folder - discover all files within
                    if self.preserve_structure:
                        # Calculate relative paths from the source folder's parent
                        # This preserves the source folder name and its structure
                        base_path = source_path.parent
                    else:
                        # Flat copy - no relative paths
                        base_path = None

                    for file_path in source_path.rglob('*'):
                        if file_path.is_file():
                            if self.preserve_structure and base_path:
                                # Calculate relative path from base
                                try:
                                    relative_path = file_path.relative_to(base_path)
                                except ValueError:
                                    # Fallback to just filename if relative_to fails
                                    relative_path = file_path.name
                            else:
                                # Flat copy
                                relative_path = None

                            all_items.append(('file', file_path, relative_path))

            if not all_items:
                from core.exceptions import FileOperationError
                error = FileOperationError(
                    "No files found to copy",
                    user_message="No valid files found in the selected paths."
                )
                self.result_ready.emit(Result.error(error))
                return

            logger.info(
                f"CopyVerifyWorker discovered {len(all_items)} files, "
                f"preserve_structure={self.preserve_structure}"
            )

            # Copy files with structure preservation using internal method
            # This method supports (type, path, relative_path) tuples
            result = self.file_ops._copy_files_internal(
                all_items,
                self.destination,
                calculate_hash=True  # Always calculate hashes for verification
            )

            # Convert FileOperationResult to Result for unified interface
            if result.success:
                # Success - emit with results dict
                self.result_ready.emit(Result.success(result.results))
                logger.info(
                    f"CopyVerifyWorker completed: {result.files_processed} files, "
                    f"{result.bytes_processed / (1024*1024):.1f} MB"
                )
            else:
                # Error - emit error result
                self.result_ready.emit(Result.error(result.error))
                logger.warning(f"CopyVerifyWorker completed with error: {result.error}")

        except Exception as e:
            # Unhandled exception - emit error result
            logger.error(f"CopyVerifyWorker crashed: {e}", exc_info=True)
            from core.exceptions import FileOperationError
            error = FileOperationError(
                f"Copy worker crashed: {e}",
                user_message="An unexpected error occurred during file copy operation."
            )
            self.result_ready.emit(Result.error(error))

    def _on_progress(self, percentage: int, message: str):
        """
        Progress callback from file operations

        Args:
            percentage: Progress percentage (0-100)
            message: Status message
        """
        self.progress_update.emit(percentage, message)

    def _check_cancelled(self) -> bool:
        """
        Check if operation should be cancelled

        Returns:
            True if cancelled, False otherwise
        """
        return self._is_cancelled

    def _check_paused(self):
        """
        Check if operation is paused and wait if so

        This blocks the worker thread until resume() is called
        """
        while self._is_paused and not self._is_cancelled:
            self.msleep(100)  # Sleep for 100ms and check again

    def cancel(self):
        """Cancel the current operation"""
        self._is_cancelled = True
        if self.file_ops:
            self.file_ops.cancel()
        logger.info("CopyVerifyWorker cancellation requested")

    def pause(self):
        """Pause the current operation"""
        self._is_paused = True
        logger.info("CopyVerifyWorker paused")

    def resume(self):
        """Resume a paused operation"""
        self._is_paused = False
        logger.info("CopyVerifyWorker resumed")
