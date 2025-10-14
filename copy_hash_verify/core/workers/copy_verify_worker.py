#!/usr/bin/env python3
"""
Copy & Verify Worker - Background copy with hash verification thread

Performs file copy operations with integrated hash verification using
BufferedFileOperations for optimal performance.
"""

from pathlib import Path
from typing import List, Dict
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import QThread, Signal

from core.buffered_file_ops import BufferedFileOperations
from core.result_types import Result, FileOperationResult
from core.logger import logger
from copy_hash_verify.core.storage_detector import StorageDetector
from copy_hash_verify.utils.thread_calculator import ThreadCalculator


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

            # Calculate common root path for structure preservation
            # This handles the case where UI expands folders to individual files
            common_root = None
            if self.preserve_structure and self.source_paths:
                # Find the immediate common parent of all files
                if len(self.source_paths) == 1:
                    immediate_parent = self.source_paths[0].parent
                else:
                    # Multiple items - find common ancestor
                    all_parts = [list(f.parents)[::-1] for f in self.source_paths]
                    immediate_parent = None
                    for parts in zip(*all_parts):
                        if len(set(parts)) == 1:
                            immediate_parent = parts[0]
                        else:
                            break

                    # Fallback if no common parent found
                    if immediate_parent is None:
                        immediate_parent = self.source_paths[0].parent

                # Go up one more level to preserve the folder name
                # This ensures "Photos" folder is preserved when copying from D:\Evidence\Photos\
                common_root = immediate_parent.parent

                logger.info(f"Common root for structure preservation: {common_root}")
                logger.debug(f"Immediate parent: {immediate_parent}, Common root: {common_root}")

            for source_path in self.source_paths:
                if source_path.is_file():
                    # Single file
                    if self.preserve_structure and common_root:
                        # Preserve full relative path from common root
                        try:
                            relative_path = source_path.relative_to(common_root)
                        except ValueError:
                            # Fallback to just filename if relative_to fails
                            logger.warning(f"Cannot calculate relative path for {source_path}, using filename only")
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

            # Detect storage characteristics and select optimal strategy
            detector = StorageDetector()

            # Use first source path for storage detection (representative sample)
            source_for_detection = self.source_paths[0]
            source_info = detector.analyze_path(source_for_detection)
            dest_info = detector.analyze_path(self.destination)

            logger.info(
                f"Storage detection:\n"
                f"  Source: {source_info.drive_type.value} on {source_info.drive_letter} "
                f"(perf_class={source_info.performance_class})\n"
                f"  Destination: {dest_info.drive_type.value} on {dest_info.drive_letter} "
                f"(perf_class={dest_info.performance_class})"
            )

            # Use ThreadCalculator for CPU-aware thread calculation
            calculator = ThreadCalculator()
            threads = calculator.calculate_optimal_threads(
                source_info=source_info,
                dest_info=dest_info,
                file_count=len(all_items),
                operation_type="copy"
            )

            # Execute copy with selected strategy
            if threads > 1 and len(all_items) > 1:
                # Parallel copying for SSD/NVMe with multiple files
                logger.info(f"Using parallel copy strategy with {threads} threads")
                result = self._copy_files_parallel(all_items, threads)
            else:
                # Sequential copying (HDD, single file, or fallback)
                logger.info("Using sequential copy strategy")
                result = self.file_ops._copy_files_internal(
                    all_items,
                    self.destination,
                    calculate_hash=True
                )

            # Convert FileOperationResult to Result for unified interface
            if result.success:
                # Success - emit with results dict (stored in 'value' field)
                self.result_ready.emit(Result.success(result.value))
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

    def _copy_files_parallel(self, all_items: List, threads: int) -> FileOperationResult:
        """
        Copy files in parallel using ThreadPoolExecutor.

        Args:
            all_items: List of (type, source_path, relative_path) tuples
            threads: Number of parallel worker threads

        Returns:
            FileOperationResult with aggregated results
        """
        import time

        start_time = time.time()
        total_files = len(all_items)
        total_bytes = sum(item[1].stat().st_size for item in all_items if item[1].exists())

        # Thread-safe progress tracking
        completed_files = 0
        completed_bytes = 0
        progress_lock = Lock()
        results_dict = {}

        def update_progress(bytes_delta: int, file_completed: bool):
            """Thread-safe progress update"""
            nonlocal completed_files, completed_bytes

            with progress_lock:
                completed_bytes += bytes_delta
                if file_completed:
                    completed_files += 1

                # Calculate progress percentage
                if total_bytes > 0:
                    percentage = int((completed_bytes / total_bytes) * 100)
                else:
                    percentage = int((completed_files / total_files) * 100)

                # Emit progress update
                self._on_progress(
                    percentage,
                    f"Copied {completed_files}/{total_files} files"
                )

        # Execute parallel copying
        with ThreadPoolExecutor(max_workers=threads) as executor:
            # Submit all copy tasks
            futures = {}
            for item_type, source_path, relative_path in all_items:
                if self._is_cancelled:
                    break

                future = executor.submit(
                    self._copy_single_file,
                    source_path,
                    relative_path,
                    update_progress
                )
                futures[future] = (source_path, relative_path)

            # Process completed tasks
            for future in as_completed(futures):
                if self._is_cancelled:
                    logger.info("Parallel copy cancelled by user")
                    break

                source_path, relative_path = futures[future]

                try:
                    result = future.result()
                    key = str(relative_path) if relative_path else source_path.name
                    results_dict[key] = result

                except Exception as e:
                    logger.error(f"Failed to copy {source_path.name}: {e}")
                    key = str(relative_path) if relative_path else source_path.name
                    results_dict[key] = {'error': str(e), 'success': False}

        # Calculate final metrics
        duration = time.time() - start_time
        speed_mbps = (completed_bytes / (1024 * 1024)) / duration if duration > 0 else 0

        logger.info(
            f"Parallel copy completed: {completed_files}/{total_files} files, "
            f"{completed_bytes / (1024*1024):.1f} MB in {duration:.1f}s ({speed_mbps:.1f} MB/s)"
        )

        # Create FileOperationResult using factory method
        from core.exceptions import FileOperationError

        success = completed_files == total_files and not self._is_cancelled

        if success:
            # Add performance stats to results_dict (matches BufferedFileOperations pattern)
            results_dict['_performance_stats'] = {
                'total_time': duration,
                'average_speed_mbps': speed_mbps,
                'start_time': start_time,
                'end_time': time.time()
            }

            # Success path - use factory method
            return FileOperationResult.create(
                results_dict,
                files_processed=completed_files,
                bytes_processed=completed_bytes
            )
        else:
            # Error path - create appropriate error
            if self._is_cancelled:
                error = FileOperationError(
                    "Copy operation cancelled by user",
                    user_message="Operation was cancelled."
                )
            else:
                error = FileOperationError(
                    f"Some files failed to copy: {completed_files}/{total_files} succeeded",
                    user_message=f"Only {completed_files} of {total_files} files were copied successfully."
                )
            return FileOperationResult.error(error)

    def _copy_single_file(self, source_path: Path, relative_path, progress_callback) -> Dict:
        """
        Copy a single file (runs in worker thread).

        Args:
            source_path: Source file path
            relative_path: Relative path for destination (or None for flat copy)
            progress_callback: Callback to update progress (bytes_delta, file_completed)

        Returns:
            Dictionary with copy results
        """
        try:
            # Calculate destination path
            if relative_path:
                dest_path = self.destination / relative_path
            else:
                dest_path = self.destination / source_path.name

            # Create parent directory if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Get file size for progress tracking
            file_size = source_path.stat().st_size

            # Create BufferedFileOperations for this thread
            file_ops = BufferedFileOperations(
                progress_callback=None,  # No per-file progress in parallel mode
                cancelled_check=self._check_cancelled,
                pause_check=None  # Pause not supported in parallel mode
            )

            # Copy file with hash verification
            copy_result = file_ops.copy_file_buffered(
                source_path,
                dest_path,
                calculate_hash=True
            )

            # Update progress
            progress_callback(file_size, True)

            if copy_result.success:
                return copy_result.value
            else:
                logger.error(f"Copy failed for {source_path.name}: {copy_result.error}")
                return {
                    'error': str(copy_result.error),
                    'success': False,
                    'source_path': str(source_path),
                    'dest_path': str(dest_path)
                }

        except Exception as e:
            logger.error(f"Exception copying {source_path}: {e}", exc_info=True)
            progress_callback(0, True)  # Mark file as attempted
            return {
                'error': str(e),
                'success': False,
                'source_path': str(source_path)
            }

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
