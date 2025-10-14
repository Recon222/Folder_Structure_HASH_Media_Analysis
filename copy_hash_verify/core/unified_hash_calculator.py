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

# NEW: Import storage detection, thread calculation, and progress throttling
try:
    from .storage_detector import StorageDetector, StorageInfo, DriveType
    STORAGE_DETECTION_AVAILABLE = True
except ImportError:
    logger.warning("StorageDetector not available, parallel optimization disabled")
    STORAGE_DETECTION_AVAILABLE = False

try:
    from copy_hash_verify.utils.thread_calculator import ThreadCalculator
    THREAD_CALCULATOR_AVAILABLE = True
except ImportError:
    logger.warning("ThreadCalculator not available, using fallback thread calculation")
    THREAD_CALCULATOR_AVAILABLE = False

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
    source_result: Optional[HashResult]
    target_result: Optional[HashResult]
    match: bool
    comparison_type: str  # 'exact_match', 'hash_mismatch', 'missing_target', 'missing_source'
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


class _VerificationProgressAggregator:
    """
    Thread-safe progress aggregation for dual-source verification

    Properly weights progress based on file counts (not simple averaging).
    Prevents race conditions during parallel hash operations.
    """
    def __init__(self, source_file_count: int, target_file_count: int,
                 progress_callback: Optional[Callable[[int, str], None]]):
        """
        Initialize progress aggregator

        Args:
            source_file_count: Number of files in source
            target_file_count: Number of files in target
            progress_callback: Function that receives (percentage, message)
        """
        from threading import Lock

        self.source_file_count = source_file_count
        self.target_file_count = target_file_count
        self.total_files = source_file_count + target_file_count
        self.progress_callback = progress_callback

        self._lock = Lock()
        self._source_pct = 0
        self._target_pct = 0
        self._source_msg = "Waiting..."
        self._target_msg = "Waiting..."

    def update_source_progress(self, percentage: int, message: str):
        """
        Update source progress (thread-safe)

        Args:
            percentage: Progress percentage (0-100)
            message: Status message
        """
        with self._lock:
            self._source_pct = percentage
            self._source_msg = message
            self._emit_combined_progress()

    def update_target_progress(self, percentage: int, message: str):
        """
        Update target progress (thread-safe)

        Args:
            percentage: Progress percentage (0-100)
            message: Status message
        """
        with self._lock:
            self._target_pct = percentage
            self._target_msg = message
            self._emit_combined_progress()

    def _emit_combined_progress(self):
        """Calculate and emit weighted progress"""
        if not self.progress_callback or self.total_files == 0:
            return

        # Weight by file count (not simple average)
        source_weight = self.source_file_count / self.total_files
        target_weight = self.target_file_count / self.total_files

        overall_pct = int(
            (self._source_pct * source_weight) +
            (self._target_pct * target_weight)
        )

        combined_msg = f"Source: {self._source_pct}% ({self._source_msg}) | Target: {self._target_pct}% ({self._target_msg})"

        self.progress_callback(overall_pct, combined_msg)


class _VerificationCoordinator:
    """
    Simple thread coordinator for parallel hash verification

    Simpler than ThreadPoolExecutor - just manages two threads for source/target.
    Handles error propagation and thread lifecycle explicitly.
    Storage detection is performed once before creating coordinator to avoid redundancy.
    """
    def __init__(self, algorithm: str, source_paths: List[Path], target_paths: List[Path],
                 source_threads: int, target_threads: int,
                 progress_aggregator: _VerificationProgressAggregator,
                 cancelled_check: Optional[Callable[[], bool]],
                 enable_parallel: bool = True):
        """
        Initialize verification coordinator

        Args:
            algorithm: Hash algorithm to use
            source_paths: Source file paths
            target_paths: Target file paths
            source_threads: Optimal threads for source storage
            target_threads: Optimal threads for target storage
            progress_aggregator: Progress aggregation handler
            cancelled_check: Cancellation check function
            enable_parallel: Enable parallel processing (overrides threads to force optimization)
        """
        from threading import Thread

        self.algorithm = algorithm
        self.source_paths = source_paths
        self.target_paths = target_paths
        self.source_threads = source_threads
        self.target_threads = target_threads
        self.progress_aggregator = progress_aggregator
        self.cancelled_check = cancelled_check
        self.enable_parallel = enable_parallel

        # Results
        self.source_result = None
        self.target_result = None
        self.source_exception = None
        self.target_exception = None

    def _hash_source(self):
        """Hash source files (runs in separate thread)"""
        try:
            logger.info(f"Source hashing started: {len(self.source_paths)} files, {self.source_threads} threads")

            # Create calculator for source with progress routing
            # IMPORTANT: max_workers_override forces use of pre-detected optimal threads
            # and skips redundant storage detection
            source_calculator = UnifiedHashCalculator(
                algorithm=self.algorithm,
                progress_callback=lambda pct, msg: self.progress_aggregator.update_source_progress(pct, msg),
                cancelled_check=self.cancelled_check,
                enable_parallel=self.enable_parallel,
                max_workers_override=self.source_threads  # Pre-detected optimal threads
            )

            self.source_result = source_calculator.hash_files(self.source_paths)
            logger.info(f"Source hashing completed: {self.source_result.success}")

        except Exception as e:
            logger.error(f"Source hashing exception: {e}", exc_info=True)
            self.source_exception = e

    def _hash_target(self):
        """Hash target files (runs in separate thread)"""
        try:
            logger.info(f"Target hashing started: {len(self.target_paths)} files, {self.target_threads} threads")

            # Create calculator for target with progress routing
            # IMPORTANT: max_workers_override forces use of pre-detected optimal threads
            # and skips redundant storage detection
            target_calculator = UnifiedHashCalculator(
                algorithm=self.algorithm,
                progress_callback=lambda pct, msg: self.progress_aggregator.update_target_progress(pct, msg),
                cancelled_check=self.cancelled_check,
                enable_parallel=self.enable_parallel,
                max_workers_override=self.target_threads  # Pre-detected optimal threads
            )

            self.target_result = target_calculator.hash_files(self.target_paths)
            logger.info(f"Target hashing completed: {self.target_result.success}")

        except Exception as e:
            logger.error(f"Target hashing exception: {e}", exc_info=True)
            self.target_exception = e

    def run_parallel(self) -> Tuple[Result, Result]:
        """
        Run parallel hashing for both source and target

        Returns:
            Tuple of (source_result, target_result)

        Raises:
            Exception: If either thread encounters an unhandled exception
        """
        from threading import Thread

        # Create threads
        source_thread = Thread(target=self._hash_source, name="SourceHashThread")
        target_thread = Thread(target=self._hash_target, name="TargetHashThread")

        # Start both threads
        source_thread.start()
        target_thread.start()

        # Wait for both to complete
        source_thread.join()
        target_thread.join()

        # Check for exceptions
        if self.source_exception:
            raise self.source_exception
        if self.target_exception:
            raise self.target_exception

        # Return results
        return self.source_result, self.target_result


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

        # NEW: Storage-aware processing decision with ThreadCalculator
        if self.enable_parallel and len(files) > 1:
            # Determine optimal thread count
            if self.max_workers_override:
                # Thread count pre-determined - skip redundant storage detection
                optimal_threads = self.max_workers_override
                storage_info = None  # Avoid redundant detection
                logger.info(f"Using manual thread override: {optimal_threads} threads (skipping storage detection)")
            elif self.storage_detector and THREAD_CALCULATOR_AVAILABLE:
                # Perform storage detection and use ThreadCalculator
                storage_info = self.storage_detector.analyze_path(files[0])
                calculator = ThreadCalculator()
                optimal_threads = calculator.calculate_optimal_threads(
                    source_info=storage_info,
                    dest_info=None,  # Hash-only operation
                    file_count=len(files),
                    operation_type="hash"
                )
                logger.info(f"Storage detected: {storage_info}")
                logger.info(f"ThreadCalculator: {optimal_threads} threads optimal for hash operation")
            else:
                # No storage detector or thread calculator available, use sequential
                logger.debug("Storage detector or ThreadCalculator unavailable, using sequential processing")
                return self._sequential_hash_files(files)

            # Use parallel processing if beneficial
            if optimal_threads > 1:
                logger.info(f"Using parallel processing with {optimal_threads} threads")
                return self._parallel_hash_files(files, optimal_threads, storage_info)
            else:
                logger.info(f"Using sequential processing (storage: {storage_info.drive_type.value if storage_info else 'unknown'})")

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
                            storage_info: Optional['StorageInfo']) -> Result[Dict[str, HashResult]]:
        """
        Memory-safe parallel hash calculation using ThreadPoolExecutor

        Uses chunked submission to prevent memory explosion on large file lists.
        Implements throttled progress reporting to prevent UI flooding.

        Args:
            files: List of files to hash
            max_workers: Number of parallel worker threads
            storage_info: Storage characteristics (for logging), None if skipped

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

        Automatically uses parallel processing when beneficial based on storage type.
        Falls back to sequential for safety if parallel processing fails.

        Args:
            source_paths: List of source file/folder paths
            target_paths: List of target file/folder paths

        Returns:
            Result[Dict] mapping file paths to VerificationResult objects
        """
        # Try parallel verification first if enabled
        if self.enable_parallel and self.storage_detector:
            try:
                return self.verify_hashes_parallel(source_paths, target_paths)
            except Exception as e:
                logger.warning(f"Parallel verification failed: {e}, falling back to sequential")

        # Sequential implementation (safety net) - call extracted method
        return self._verify_hashes_sequential(source_paths, target_paths)

    def _verify_hashes_sequential(
        self,
        source_paths: List[Path],
        target_paths: List[Path]
    ) -> Result[Dict[str, VerificationResult]]:
        """
        Sequential bidirectional hash verification

        Used as fallback when parallel processing fails or is disabled.
        Hashes source and target one after the other.

        Args:
            source_paths: List of source file/folder paths
            target_paths: List of target file/folder paths

        Returns:
            Result[Dict] mapping file paths to VerificationResult objects
        """
        # Hash both source and target sequentially
        source_result = self.hash_files(source_paths)
        if not source_result.success:
            return Result.error(source_result.error)

        target_result = self.hash_files(target_paths)
        if not target_result.success:
            return Result.error(target_result.error)

        # Compare hashes using extracted helper
        verification_results = self._compare_hashes(
            source_result.value,
            target_result.value
        )

        # Verification complete - mismatches and missing files are RESULTS, not errors
        # Return success with all verification results for UI to display
        return Result.success(verification_results)

    def verify_hashes_parallel(
        self,
        source_paths: List[Path],
        target_paths: List[Path]
    ) -> Result[Dict[str, VerificationResult]]:
        """
        Parallel bidirectional hash verification with independent storage optimization

        Hashes source and target simultaneously, each with optimal thread allocation
        based on detected storage type. Provides massive speedup for symmetric scenarios
        (both NVMe/SSD) and efficient resource utilization for asymmetric scenarios.

        Args:
            source_paths: List of source file/folder paths
            target_paths: List of target file/folder paths

        Returns:
            Result[Dict] mapping file paths to VerificationResult objects with
            comprehensive metadata including storage detection and performance metrics
        """
        try:
            # Step 1: Discover files from both sources
            source_files = self.discover_files(source_paths)
            target_files = self.discover_files(target_paths)

            if not source_files:
                error = HashCalculationError(
                    "No source files found to verify",
                    user_message="No valid files found in the source paths."
                )
                return Result.error(error)

            if not target_files:
                error = HashCalculationError(
                    "No target files found to verify",
                    user_message="No valid files found in the target paths."
                )
                return Result.error(error)

            # Step 2: Independent storage detection
            if not self.storage_detector:
                logger.warning("StorageDetector unavailable, falling back to sequential")
                return self.verify_hashes(source_paths, target_paths)

            source_storage = self.storage_detector.analyze_path(source_files[0])
            target_storage = self.storage_detector.analyze_path(target_files[0])

            # Step 3: Calculate optimal thread allocation using ThreadCalculator
            if self.max_workers_override:
                source_threads = self.max_workers_override
                target_threads = self.max_workers_override
            elif THREAD_CALCULATOR_AVAILABLE:
                calculator = ThreadCalculator()
                source_threads = calculator.calculate_optimal_threads(
                    source_info=source_storage,
                    dest_info=None,
                    file_count=len(source_files),
                    operation_type="hash"
                )
                target_threads = calculator.calculate_optimal_threads(
                    source_info=target_storage,
                    dest_info=None,
                    file_count=len(target_files),
                    operation_type="hash"
                )
            else:
                # Fallback to 4 threads if ThreadCalculator unavailable
                source_threads = 4
                target_threads = 4

            logger.info(f"Parallel verification starting:")
            logger.info(f"  Source: {source_storage.drive_type.value} on {source_storage.drive_letter} "
                       f"({source_threads} threads, {source_storage.confidence:.0%} confidence)")
            logger.info(f"  Target: {target_storage.drive_type.value} on {target_storage.drive_letter} "
                       f"({target_threads} threads, {target_storage.confidence:.0%} confidence)")

            # Step 4: Create progress aggregator
            progress_aggregator = _VerificationProgressAggregator(
                source_file_count=len(source_files),
                target_file_count=len(target_files),
                progress_callback=self.progress_callback
            )

            # Step 5: Create coordinator and run parallel hashing
            coordinator = _VerificationCoordinator(
                algorithm=self.algorithm,
                source_paths=source_paths,
                target_paths=target_paths,
                source_threads=source_threads,
                target_threads=target_threads,
                progress_aggregator=progress_aggregator,
                cancelled_check=self.cancelled_check,
                enable_parallel=self.enable_parallel  # Pass parallel flag to prevent nested detection
            )

            source_result, target_result = coordinator.run_parallel()

            # Step 6: Error handling
            if not source_result.success:
                return Result.error(source_result.error)
            if not target_result.success:
                return Result.error(target_result.error)

            # Step 7: Compare hashes
            verification_results = self._compare_hashes(
                source_result.value,
                target_result.value
            )

            # Step 8: Build comprehensive metadata
            combined_metrics = self._build_combined_metrics(
                source_result=source_result,
                target_result=target_result,
                source_storage=source_storage,
                target_storage=target_storage,
                source_threads=source_threads,
                target_threads=target_threads,
                verification_results=verification_results
            )

            # Step 9: Log completion with performance metrics
            duration = combined_metrics['total_duration']
            speed = combined_metrics['effective_speed_mbps']
            source_speed = combined_metrics['source_speed_mbps']
            target_speed = combined_metrics['target_speed_mbps']

            logger.info(f"Parallel verification complete: {duration:.1f}s")
            logger.info(f"  Source: {source_speed:.1f} MB/s | Target: {target_speed:.1f} MB/s | Combined: {speed:.1f} MB/s")

            # Step 10: Return success with verification results (mismatches are results, not errors)
            # The UI will handle displaying matched/mismatched/missing files
            return Result.success(verification_results, **combined_metrics)

        except Exception as e:
            logger.error(f"Parallel verification crashed: {e}", exc_info=True)
            logger.info("Falling back to sequential verification")
            return self._verify_hashes_sequential(source_paths, target_paths)

    def _find_common_root(self, paths: List[str]) -> Path:
        """
        Find the deepest common directory among a list of file paths

        For example:
        - Input: ["C:/Test 1/Folder/File1.txt", "C:/Test 1/Folder/File2.txt"]
        - Output: Path("C:/Test 1/Folder")

        Args:
            paths: List of file path strings

        Returns:
            Common root directory as Path object
        """
        if not paths:
            return Path(".")

        path_objs = [Path(p).parent for p in paths]

        # Start with first path's parent directory
        common = path_objs[0]

        # Find common ancestor by checking if all paths are relative to it
        while common != common.parent:  # Not at filesystem root
            try:
                if all(p.is_relative_to(common) for p in path_objs):
                    return common
            except (ValueError, AttributeError):
                # is_relative_to not available or paths don't match
                pass
            common = common.parent

        return common

    def _compare_hashes(
        self,
        source_hashes: Dict[str, HashResult],
        target_hashes: Dict[str, HashResult]
    ) -> Dict[str, VerificationResult]:
        """
        Compare source and target hash results by relative path structure

        Extracted from verify_hashes() for reuse in parallel implementation.
        Matches files by their relative path from common root (not just filename).
        This ensures files with duplicate names are matched correctly by structure.
        Also detects files that exist in target but not in source.

        Args:
            source_hashes: Dict mapping source file paths to HashResult objects
            target_hashes: Dict mapping target file paths to HashResult objects

        Returns:
            Dict mapping file paths to VerificationResult objects
        """
        verification_results = {}

        # Find common roots for relative path calculation
        source_root = self._find_common_root(list(source_hashes.keys()))
        target_root = self._find_common_root(list(target_hashes.keys()))

        logger.debug(f"Source common root: {source_root}")
        logger.debug(f"Target common root: {target_root}")

        # Build target lookup by relative path (not just filename)
        target_by_relpath = {}
        for target_path, target_hr in target_hashes.items():
            try:
                rel_path = Path(target_path).relative_to(target_root)
                target_by_relpath[str(rel_path)] = (target_path, target_hr)
            except ValueError:
                # Path not relative to common root - use as-is
                target_by_relpath[Path(target_path).name] = (target_path, target_hr)

        matched_relpaths = set()

        # First pass: Match source files by relative path
        for source_path, source_hash_result in source_hashes.items():
            try:
                source_rel = str(Path(source_path).relative_to(source_root))
            except ValueError:
                # Path not relative to common root - use filename
                source_rel = Path(source_path).name

            if source_rel in target_by_relpath:
                # Found matching file with same relative path
                target_path, target_hash_result = target_by_relpath[source_rel]
                matched_relpaths.add(source_rel)

                # Compare hashes
                match = source_hash_result.hash_value == target_hash_result.hash_value
                verification_results[source_path] = VerificationResult(
                    source_result=source_hash_result,
                    target_result=target_hash_result,
                    match=match,
                    comparison_type='exact_match' if match else 'hash_mismatch',
                    notes="" if match else f"Hash mismatch: {source_hash_result.hash_value[:8]}... != {target_hash_result.hash_value[:8]}..."
                )
            else:
                # Missing from target
                verification_results[source_path] = VerificationResult(
                    source_result=source_hash_result,
                    target_result=None,
                    match=False,
                    comparison_type='missing_target',
                    notes=f"File with relative path '{source_rel}' not found in target"
                )

        # Second pass: Find files in target missing from source
        for rel_path, (target_path, target_hash_result) in target_by_relpath.items():
            if rel_path not in matched_relpaths:
                verification_results[target_path] = VerificationResult(
                    source_result=None,
                    target_result=target_hash_result,
                    match=False,
                    comparison_type='missing_source',
                    notes=f"File with relative path '{rel_path}' not found in source"
                )

        return verification_results

    def _build_combined_metrics(
        self,
        source_result: Result,
        target_result: Result,
        source_storage: 'StorageInfo',
        target_storage: 'StorageInfo',
        source_threads: int,
        target_threads: int,
        verification_results: Dict[str, VerificationResult]
    ) -> dict:
        """
        Build comprehensive combined metrics for UI and reporting

        Args:
            source_result: Result object from source hashing
            target_result: Result object from target hashing
            source_storage: Storage information for source
            target_storage: Storage information for target
            source_threads: Thread count used for source
            target_threads: Thread count used for target
            verification_results: Comparison results

        Returns:
            Dict with comprehensive metadata for UI display and reporting
        """
        source_metrics = source_result.metadata.get('metrics') if source_result.metadata else None
        target_metrics = target_result.metadata.get('metrics') if target_result.metadata else None

        # Calculate wall-clock duration (max of both since parallel)
        total_duration = max(
            source_metrics.duration if source_metrics else 0,
            target_metrics.duration if target_metrics else 0
        )

        # Calculate effective throughput (total bytes / wall-clock time)
        total_bytes = (
            (source_metrics.processed_bytes if source_metrics else 0) +
            (target_metrics.processed_bytes if target_metrics else 0)
        )
        effective_speed_mbps = (
            (total_bytes / (1024 * 1024)) / total_duration
            if total_duration > 0 else 0
        )

        # Calculate individual drive speeds
        source_speed_mbps = source_metrics.average_speed_mbps if source_metrics else 0
        target_speed_mbps = target_metrics.average_speed_mbps if target_metrics else 0

        return {
            # Source details
            'source_metrics': source_metrics,
            'source_storage': {
                'drive_type': source_storage.drive_type.value,
                'bus_type': source_storage.bus_type.value,
                'drive_letter': source_storage.drive_letter,
                'performance_class': source_storage.performance_class,
                'confidence': source_storage.confidence
            },
            'source_threads_used': source_threads,
            'source_speed_mbps': source_speed_mbps,

            # Target details
            'target_metrics': target_metrics,
            'target_storage': {
                'drive_type': target_storage.drive_type.value,
                'bus_type': target_storage.bus_type.value,
                'drive_letter': target_storage.drive_letter,
                'performance_class': target_storage.performance_class,
                'confidence': target_storage.confidence
            },
            'target_threads_used': target_threads,
            'target_speed_mbps': target_speed_mbps,

            # Combined metrics
            'total_duration': total_duration,
            'total_bytes_processed': total_bytes,
            'effective_speed_mbps': effective_speed_mbps,
            'execution_mode': 'parallel',

            # Verification results
            'verification_results': verification_results,
        }

    def cancel(self):
        """Cancel the current operation"""
        self.cancelled = True
        self.cancel_event.set()

    def reset(self):
        """Reset calculator state for new operation"""
        self.cancelled = False
        self.cancel_event.clear()
        self.metrics = HashOperationMetrics()
