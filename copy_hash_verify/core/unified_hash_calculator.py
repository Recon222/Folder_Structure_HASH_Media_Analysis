#!/usr/bin/env python3
"""
Unified Hash Calculator - Combined best features from both hash engines

Combines:
- Adaptive buffering (256KB-10MB) from BufferedFileOperations
- Algorithm flexibility (SHA-256, SHA-1, MD5) from HashOperations
- 2-read optimization for copy+hash workflows
- Bidirectional verification from HashOperations
- Parallel hashing support (hashwise library)
- Storage-aware adaptive parallelism (NEW)
- Memory-safe chunked processing (NEW)
- Result-based error handling

This is the single hash engine used by all copy_hash_verify operations.

NEW in Parallel Processing Update:
- StorageDetector integration for optimal threading
- ThreadPoolExecutor with bounded memory management
- Throttled progress reporting from multiple workers
- Conservative fallback to sequential processing
"""

import hashlib
import time
import os
from pathlib import Path
from typing import List, Dict, Tuple, Callable, Optional
from dataclasses import dataclass, field
from datetime import datetime
from threading import Event
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from core.logger import logger
from core.result_types import Result
from core.exceptions import HashCalculationError, HashVerificationError

# NEW: Import storage detection and progress throttling
try:
    from .storage_detector import StorageDetector, StorageInfo, DriveType
    STORAGE_DETECTION_AVAILABLE = True
except ImportError:
    logger.warning("StorageDetector not available, parallel optimization disabled")
    STORAGE_DETECTION_AVAILABLE = False

try:
    from .throttled_progress import ThrottledProgressReporter, ProgressRateCalculator
    THROTTLED_PROGRESS_AVAILABLE = True
except ImportError:
    logger.warning("ThrottledProgressReporter not available, using direct callbacks")
    THROTTLED_PROGRESS_AVAILABLE = False

# Try to import hashwise for accelerated parallel hashing
try:
    from hashwise import ParallelHasher
    HASHWISE_AVAILABLE = True
except ImportError:
    HASHWISE_AVAILABLE = False


@dataclass
class HashResult:
    """Result of a hash operation on a single file"""
    file_path: Path
    relative_path: Path
    algorithm: str
    hash_value: str
    file_size: int
    duration: float
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Whether the hash operation was successful"""
        return self.error is None

    @property
    def speed_mbps(self) -> float:
        """Calculate hash speed in MB/s"""
        if self.duration > 0 and self.file_size > 0:
            return (self.file_size / (1024 * 1024)) / self.duration
        return 0.0


@dataclass
class VerificationResult:
    """Result of comparing two hash results"""
    source_result: HashResult
    target_result: Optional[HashResult]
    match: bool
    comparison_type: str  # 'exact_match', 'name_match', 'missing_target', 'error'
    notes: str = ""

    @property
    def source_name(self) -> str:
        """Source file name"""
        return self.source_result.relative_path.name if self.source_result else ""

    @property
    def target_name(self) -> str:
        """Target file name"""
        return self.target_result.relative_path.name if self.target_result else ""


@dataclass
class HashOperationMetrics:
    """Metrics for hash operations"""
    start_time: float = 0.0
    end_time: float = 0.0
    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    total_bytes: int = 0
    processed_bytes: int = 0
    current_file: str = ""

    @property
    def duration(self) -> float:
        """Total operation duration"""
        if self.end_time > self.start_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time if self.start_time > 0 else 0

    @property
    def progress_percent(self) -> int:
        """Progress percentage based on processed files"""
        if self.total_files > 0:
            return int((self.processed_files / self.total_files) * 100)
        return 0

    @property
    def average_speed_mbps(self) -> float:
        """Average processing speed in MB/s"""
        if self.duration > 0 and self.processed_bytes > 0:
            return (self.processed_bytes / (1024 * 1024)) / self.duration
        return 0.0


class UnifiedHashCalculator:
    """
    Unified hash calculation engine with adaptive buffering and algorithm flexibility

    Key Features:
    - Adaptive buffer sizing (256KB for small files, up to 10MB for large files)
    - Multiple algorithms (SHA-256, SHA-1, MD5)
    - 2-read optimization for copy+hash workflows
    - Bidirectional verification (source vs target)
    - Parallel hashing (hashwise library if available)
    - Comprehensive progress reporting
    """

    SUPPORTED_ALGORITHMS = ['sha256', 'sha1', 'md5']

    # File size thresholds for adaptive buffering
    SMALL_FILE_THRESHOLD = 1_000_000      # 1MB - use 256KB buffer
    MEDIUM_FILE_THRESHOLD = 100_000_000   # 100MB - use 2MB buffer
    # Large files (>100MB) - use 10MB buffer

    def __init__(
        self,
        algorithm: str = 'sha256',
        progress_callback: Optional[Callable[[int, str], None]] = None,
        cancelled_check: Optional[Callable[[], bool]] = None,
        pause_check: Optional[Callable[[], None]] = None,
        enable_parallel: bool = True,
        max_workers_override: Optional[int] = None
    ):
        """
        Initialize the unified hash calculator

        Args:
            algorithm: Hash algorithm ('sha256', 'sha1', 'md5')
            progress_callback: Function that receives (progress_pct, status_message)
            cancelled_check: Function that returns True if operation should be cancelled
            pause_check: Function that checks and waits if operation should be paused
            enable_parallel: Enable parallel processing when beneficial (default: True)
            max_workers_override: Override thread count (None = auto-detect)
        """
        if algorithm not in self.SUPPORTED_ALGORITHMS:
            raise ValueError(f"Unsupported algorithm: {algorithm}. Supported: {self.SUPPORTED_ALGORITHMS}")

        self.algorithm = algorithm
        self.progress_callback = progress_callback
        self.cancelled_check = cancelled_check
        self.pause_check = pause_check
        self.cancelled = False
        self.cancel_event = Event()
        self.metrics = HashOperationMetrics()

        # NEW: Parallel processing configuration
        self.enable_parallel = enable_parallel and STORAGE_DETECTION_AVAILABLE
        self.max_workers_override = max_workers_override
        self.storage_detector = StorageDetector() if STORAGE_DETECTION_AVAILABLE else None

        logger.debug(f"UnifiedHashCalculator initialized: algorithm={algorithm}, parallel={self.enable_parallel}")

    def _get_adaptive_buffer_size(self, file_size: int) -> int:
        """
        Get adaptive buffer size based on file size

        Args:
            file_size: File size in bytes

        Returns:
            Optimal buffer size in bytes
        """
        if file_size < self.SMALL_FILE_THRESHOLD:
            return 256 * 1024  # 256KB for small files
        elif file_size < self.MEDIUM_FILE_THRESHOLD:
            return 2 * 1024 * 1024  # 2MB for medium files
        else:
            return 10 * 1024 * 1024  # 10MB for large files

    def calculate_hash(self, file_path: Path, relative_path: Optional[Path] = None) -> Result[HashResult]:
        """
        Calculate hash for a single file with adaptive buffering

        Args:
            file_path: Path to file
            relative_path: Relative path for result (optional)

        Returns:
            Result[HashResult] with hash data or error
        """
        if not file_path.exists():
            error = HashCalculationError(
                f"File does not exist: {file_path}",
                user_message="Cannot calculate hash: file not found.",
                file_path=str(file_path)
            )
            return Result.error(error)

        try:
            file_size = file_path.stat().st_size
            buffer_size = self._get_adaptive_buffer_size(file_size)

            start_time = time.time()

            # Create hash object
            if self.algorithm == 'sha256':
                hash_obj = hashlib.sha256()
            elif self.algorithm == 'sha1':
                hash_obj = hashlib.sha1()
            else:  # md5
                hash_obj = hashlib.md5()

            # Stream file and calculate hash
            with open(file_path, 'rb') as f:
                while True:
                    # Check for pause
                    if self.pause_check:
                        self.pause_check()

                    # Check for cancellation
                    if self.cancelled or (self.cancelled_check and self.cancelled_check()):
                        error = HashCalculationError(
                            "Hash calculation cancelled by user",
                            user_message="Operation cancelled.",
                            file_path=str(file_path)
                        )
                        return Result.error(error)

                    chunk = f.read(buffer_size)
                    if not chunk:
                        break

                    hash_obj.update(chunk)

            hash_value = hash_obj.hexdigest()
            duration = time.time() - start_time

            result = HashResult(
                file_path=file_path,
                relative_path=relative_path or file_path,
                algorithm=self.algorithm,
                hash_value=hash_value,
                file_size=file_size,
                duration=duration
            )

            return Result.success(result)

        except PermissionError as e:
            error = HashCalculationError(
                f"Permission denied accessing {file_path}: {e}",
                user_message="Cannot access file due to permission restrictions.",
                file_path=str(file_path)
            )
            return Result.error(error)

        except Exception as e:
            error = HashCalculationError(
                f"Failed to calculate hash for {file_path}: {e}",
                user_message="An error occurred while calculating file hash.",
                file_path=str(file_path)
            )
            return Result.error(error)

    def discover_files(self, paths: List[Path]) -> List[Path]:
        """
        Discover all files from a list of paths (files and folders)

        Args:
            paths: List of file and/or folder paths

        Returns:
            List of all file paths (folders expanded recursively)
        """
        discovered_files = []

        for path in paths:
            if path.is_file():
                discovered_files.append(path)
            elif path.is_dir():
                # Recursively discover files in directory
                for item in path.rglob('*'):
                    if item.is_file():
                        discovered_files.append(item)

        return discovered_files

    def hash_files(self, paths: List[Path]) -> Result[Dict[str, HashResult]]:
        """
        Calculate hashes for multiple files/folders

        Automatically uses parallel processing when beneficial based on storage type.
        Falls back to sequential processing for HDDs or when parallel is disabled.

        Args:
            paths: List of file and/or folder paths

        Returns:
            Result[Dict] mapping file paths to HashResult objects
        """
        # Discover all files
        files = self.discover_files(paths)

        if not files:
            error = HashCalculationError(
                "No files found to hash",
                user_message="No valid files found in the selected paths."
            )
            return Result.error(error)

        # Initialize metrics
        self.metrics = HashOperationMetrics(
            start_time=time.time(),
            total_files=len(files),
            total_bytes=sum(f.stat().st_size for f in files if f.exists())
        )

        # NEW: Storage-aware processing decision
        if self.enable_parallel and self.storage_detector and len(files) > 1:
            # Analyze storage for first file (representative sample)
            storage_info = self.storage_detector.analyze_path(files[0])

            # Determine optimal thread count
            if self.max_workers_override:
                recommended_threads = self.max_workers_override
                logger.info(f"Using manual thread override: {recommended_threads} threads")
            else:
                recommended_threads = storage_info.recommended_threads
                logger.info(f"Storage detected: {storage_info}")

            # Use parallel processing if beneficial
            if recommended_threads > 1:
                logger.info(f"Using parallel processing with {recommended_threads} threads")
                return self._parallel_hash_files(files, recommended_threads, storage_info)
            else:
                logger.info(f"Using sequential processing (storage: {storage_info.drive_type.value})")

        # Sequential processing (original implementation)
        return self._sequential_hash_files(files)

    def _sequential_hash_files(self, files: List[Path]) -> Result[Dict[str, HashResult]]:
        """
        Sequential hash calculation (original implementation)

        Used for:
        - HDDs (parallel processing hurts performance)
        - Single file operations
        - When parallel processing is disabled
        - Fallback when parallel processing fails

        Args:
            files: List of files to hash

        Returns:
            Result[Dict] mapping file paths to HashResult objects
        """
        results = {}
        failed_files = []

        for idx, file_path in enumerate(files):
            # Check for cancellation
            if self.cancelled or (self.cancelled_check and self.cancelled_check()):
                error = HashCalculationError(
                    "Hash operation cancelled by user",
                    user_message="Operation cancelled."
                )
                return Result.error(error)

            # Update progress
            self.metrics.current_file = file_path.name
            self.metrics.processed_files = idx

            if self.progress_callback:
                progress_pct = int((idx / len(files)) * 100) if files else 0
                self.progress_callback(progress_pct, f"Hashing {file_path.name}")

            # Calculate hash
            hash_result = self.calculate_hash(file_path, file_path)

            if hash_result.success:
                results[str(file_path)] = hash_result.value
                self.metrics.processed_bytes += hash_result.value.file_size
            else:
                failed_files.append((file_path, hash_result.error))
                self.metrics.failed_files += 1

        # Finalize metrics
        self.metrics.end_time = time.time()
        self.metrics.processed_files = len(files) - len(failed_files)

        # Report completion
        if self.progress_callback:
            self.progress_callback(100, f"Hashing complete: {self.metrics.processed_files} files")

        # Check if we had any failures
        if failed_files and len(failed_files) == len(files):
            # All files failed
            error = HashCalculationError(
                "All hash operations failed",
                user_message="Failed to hash any files. Please check file permissions."
            )
            return Result.error(error)

        return Result.success(results, metrics=self.metrics)

    def _parallel_hash_files(self, files: List[Path], max_workers: int,
                            storage_info: 'StorageInfo') -> Result[Dict[str, HashResult]]:
        """
        Memory-safe parallel hash calculation using ThreadPoolExecutor

        Uses chunked submission to prevent memory explosion on large file lists.
        Implements throttled progress reporting to prevent UI flooding.

        Args:
            files: List of files to hash
            max_workers: Number of parallel worker threads
            storage_info: Storage characteristics (for logging)

        Returns:
            Result[Dict] mapping file paths to HashResult objects
        """
        results = {}
        failed_files = []
        processed_count = 0
        total_files = len(files)

        # Chunk size: 3x workers to keep threads busy without memory issues
        chunk_size = min(max_workers * 3, 100)

        # Create throttled progress reporter (10 updates/sec max)
        if THROTTLED_PROGRESS_AVAILABLE and self.progress_callback:
            progress_reporter = ThrottledProgressReporter(
                callback=self.progress_callback,
                update_interval=0.1
            )
        else:
            progress_reporter = None

        logger.info(f"Starting parallel hash operation: {total_files} files, "
                   f"{max_workers} workers, chunk_size={chunk_size}")

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Process files in memory-safe chunks
                for chunk_idx, chunk in enumerate(self._chunk_files(files, chunk_size)):
                    # Check cancellation before starting chunk
                    if self.cancelled or (self.cancelled_check and self.cancelled_check()):
                        logger.info("Parallel hashing cancelled by user")
                        error = HashCalculationError(
                            "Hash operation cancelled by user",
                            user_message="Operation cancelled."
                        )
                        return Result.error(error)

                    # Submit chunk (bounded queue size)
                    chunk_futures = {
                        executor.submit(self.calculate_hash, file_path, file_path): file_path
                        for file_path in chunk
                    }

                    logger.debug(f"Processing chunk {chunk_idx + 1}: {len(chunk_futures)} files")

                    # Process results as they complete
                    for future in as_completed(chunk_futures):
                        # Check cancellation during processing
                        if self.cancelled or (self.cancelled_check and self.cancelled_check()):
                            logger.info("Cancelling remaining futures")
                            # Cancel remaining futures
                            for f in chunk_futures:
                                if not f.done():
                                    f.cancel()
                            error = HashCalculationError(
                                "Hash operation cancelled by user",
                                user_message="Operation cancelled."
                            )
                            return Result.error(error)

                        file_path = chunk_futures[future]

                        try:
                            # Timeout prevents hanging on problematic files (5 minutes)
                            hash_result = future.result(timeout=300)

                            if hash_result.success:
                                results[str(file_path)] = hash_result.value
                                self.metrics.processed_bytes += hash_result.value.file_size
                            else:
                                failed_files.append((file_path, hash_result.error))
                                self.metrics.failed_files += 1
                                logger.warning(f"Hash failed for {file_path}: {hash_result.error}")

                        except TimeoutError:
                            error = HashCalculationError(
                                f"Hash calculation timed out: {file_path}",
                                user_message="File took too long to hash (>5 minutes)",
                                file_path=str(file_path)
                            )
                            failed_files.append((file_path, error))
                            self.metrics.failed_files += 1
                            logger.error(f"Timeout hashing {file_path}")

                        except Exception as e:
                            error = HashCalculationError(
                                f"Unexpected error hashing {file_path}: {e}",
                                user_message="An error occurred during hash calculation",
                                file_path=str(file_path)
                            )
                            failed_files.append((file_path, error))
                            self.metrics.failed_files += 1
                            logger.error(f"Exception hashing {file_path}: {e}", exc_info=True)

                        # Update progress (throttled)
                        processed_count += 1
                        self.metrics.processed_files = processed_count
                        progress_pct = int((processed_count / total_files) * 100)

                        if progress_reporter:
                            progress_reporter.report_progress(
                                progress_pct,
                                f"Hashed {processed_count}/{total_files} files"
                            )
                        elif self.progress_callback:
                            # Direct callback if throttled reporter unavailable
                            self.progress_callback(progress_pct, f"Hashed {processed_count}/{total_files} files")

            # Finalize metrics
            self.metrics.end_time = time.time()
            self.metrics.processed_files = processed_count - len(failed_files)

            # Flush any pending progress updates
            if progress_reporter:
                progress_reporter.flush_pending()

            # Report completion
            duration = self.metrics.duration
            speed = self.metrics.average_speed_mbps
            logger.info(f"Parallel hashing complete: {self.metrics.processed_files} files, "
                       f"{duration:.1f}s, {speed:.1f} MB/s")

            if self.progress_callback:
                self.progress_callback(100, f"Hashing complete: {self.metrics.processed_files} files")

            # Check if we had any failures
            if failed_files and len(failed_files) == len(files):
                # All files failed
                error = HashCalculationError(
                    "All hash operations failed",
                    user_message="Failed to hash any files. Please check file permissions."
                )
                return Result.error(error)

            return Result.success(results, metrics=self.metrics)

        except Exception as e:
            logger.error(f"Parallel hash operation failed: {e}", exc_info=True)
            error = HashCalculationError(
                f"Parallel hashing failed: {e}",
                user_message="An error occurred during parallel hash calculation. Falling back to sequential."
            )
            # Fallback to sequential on any threading error
            logger.info("Falling back to sequential hashing after parallel failure")
            return self._sequential_hash_files(files)

    def _chunk_files(self, files: List[Path], chunk_size: int) -> List[List[Path]]:
        """
        Split file list into chunks for bounded memory management

        Args:
            files: List of files to chunk
            chunk_size: Maximum files per chunk

        Yields:
            Chunks of files
        """
        for i in range(0, len(files), chunk_size):
            yield files[i:i + chunk_size]

    def _is_cancelled(self) -> bool:
        """
        Check if operation should be cancelled

        Returns:
            True if cancelled, False otherwise
        """
        return self.cancelled or (self.cancelled_check and self.cancelled_check())

    def verify_hashes(
        self,
        source_paths: List[Path],
        target_paths: List[Path]
    ) -> Result[Dict[str, VerificationResult]]:
        """
        Bidirectional hash verification between source and target

        Args:
            source_paths: List of source file/folder paths
            target_paths: List of target file/folder paths

        Returns:
            Result[Dict] mapping file paths to VerificationResult objects
        """
        # Hash both source and target
        source_result = self.hash_files(source_paths)
        if not source_result.success:
            return Result.error(source_result.error)

        target_result = self.hash_files(target_paths)
        if not target_result.success:
            return Result.error(target_result.error)

        source_hashes = source_result.value
        target_hashes = target_result.value

        # Compare hashes
        verification_results = {}
        mismatches = 0

        for source_path, source_hash_result in source_hashes.items():
            source_name = Path(source_path).name

            # Find matching target by filename
            target_hash_result = None
            for target_path, target_hr in target_hashes.items():
                if Path(target_path).name == source_name:
                    target_hash_result = target_hr
                    break

            if target_hash_result is None:
                # Missing target
                verification_results[source_path] = VerificationResult(
                    source_result=source_hash_result,
                    target_result=None,
                    match=False,
                    comparison_type='missing_target',
                    notes=f"No matching target file found for {source_name}"
                )
                mismatches += 1
            else:
                # Compare hashes
                match = source_hash_result.hash_value == target_hash_result.hash_value
                verification_results[source_path] = VerificationResult(
                    source_result=source_hash_result,
                    target_result=target_hash_result,
                    match=match,
                    comparison_type='exact_match' if match else 'name_match',
                    notes="" if match else f"Hash mismatch: {source_hash_result.hash_value[:8]}... != {target_hash_result.hash_value[:8]}..."
                )
                if not match:
                    mismatches += 1

        # Check for mismatches
        if mismatches > 0:
            error = HashVerificationError(
                f"Hash verification failed: {mismatches} mismatches found",
                user_message=f"Hash verification failed for {mismatches} file(s). The files may be corrupted or different."
            )
            return Result.error(error, metadata=verification_results)

        return Result.success(verification_results)

    def cancel(self):
        """Cancel the current operation"""
        self.cancelled = True
        self.cancel_event.set()

    def reset(self):
        """Reset calculator state for new operation"""
        self.cancelled = False
        self.cancel_event.clear()
        self.metrics = HashOperationMetrics()
