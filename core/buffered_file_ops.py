#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
High-performance buffered file operations with streaming support and forensic integrity

BUFFER REUSE OPTIMIZATION:
This module implements a 2-read optimization for hash-verified file copies:
- Previous approach: 3 separate reads (source hash, copy, destination hash)
- Optimized approach: 2 reads (combined source read/hash/copy, then destination verification)
- Performance improvement: 33% reduction in disk I/O operations

FORENSIC INTEGRITY GUARANTEE:
For law enforcement and legal compliance, destination hashes are ALWAYS calculated
by reading the actual file from disk, not from memory buffers. This ensures:
1. The hash represents what's physically stored on disk
2. Legal defensibility in court proceedings
3. Detection of any storage-level corruption
4. Compliance with evidence handling requirements

The performance trade-off (2 reads vs theoretical 1 read) is accepted to maintain
cryptographic proof of accurate disk storage.
"""

import shutil
import hashlib
import time
import os
import logging
from pathlib import Path
from typing import List, Dict, Callable, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from threading import Event
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.settings_manager import SettingsManager
from core.logger import logger
from core.result_types import Result, FileOperationResult
from core.exceptions import FileOperationError, HashVerificationError

# Try to import hashwise for accelerated parallel hashing
try:
    from hashwise import ParallelHasher
    HASHWISE_AVAILABLE = True
except ImportError:
    HASHWISE_AVAILABLE = False


@dataclass
class PerformanceMetrics:
    """Track performance metrics for file operations"""
    start_time: float = 0.0
    end_time: float = 0.0
    total_bytes: int = 0
    bytes_copied: int = 0
    files_processed: int = 0
    total_files: int = 0
    buffer_size_used: int = 0
    peak_speed_mbps: float = 0.0
    average_speed_mbps: float = 0.0
    current_speed_mbps: float = 0.0
    operation_type: str = "buffered"
    errors: List[str] = field(default_factory=list)
    
    # Directory tracking
    directories_created: int = 0
    total_directories: int = 0
    
    # Detailed metrics
    small_files_count: int = 0  # < 1MB
    medium_files_count: int = 0  # 1MB - 100MB
    large_files_count: int = 0  # > 100MB
    
    # Performance samples for graph
    speed_samples: List[Tuple[float, float]] = field(default_factory=list)  # (timestamp, speed_mbps)
    
    # Buffer reuse optimization tracking
    optimization_used: bool = True  # Now enabled by default
    disk_reads_saved: int = 0  # Number of disk reads eliminated by optimization
    
    def calculate_summary(self):
        """Calculate summary statistics"""
        if self.end_time > self.start_time:
            duration = self.end_time - self.start_time
            self.average_speed_mbps = (self.bytes_copied / (1024 * 1024)) / duration if duration > 0 else 0
        
    def add_speed_sample(self, speed_mbps: float):
        """Add a speed sample for monitoring"""
        self.speed_samples.append((time.time(), speed_mbps))
        if speed_mbps > self.peak_speed_mbps:
            self.peak_speed_mbps = speed_mbps


class BufferedFileOperations:
    """High-performance file operations with configurable buffering and streaming"""
    
    # File size thresholds
    SMALL_FILE_THRESHOLD = 1_000_000      # 1MB - copy at once
    LARGE_FILE_THRESHOLD = 100_000_000    # 100MB - use large buffers
    
    def __init__(self, progress_callback: Optional[Callable[[int, str], None]] = None,
                 metrics_callback: Optional[Callable[[PerformanceMetrics], None]] = None,
                 cancelled_check: Optional[Callable[[], bool]] = None,
                 pause_check: Optional[Callable[[], None]] = None):
        """
        Initialize with optional callbacks

        Args:
            progress_callback: Function that receives (progress_pct, status_message)
            metrics_callback: Function that receives PerformanceMetrics updates
            cancelled_check: Function that returns True if operation should be cancelled
            pause_check: Function that checks and waits if operation should be paused
        """
        self.progress_callback = progress_callback
        self.metrics_callback = metrics_callback
        self.cancelled_check = cancelled_check
        self.pause_check = pause_check
        self.cancelled = False
        self.cancel_event = Event()
        self.settings = SettingsManager()
        self.metrics = PerformanceMetrics()

    def _is_same_filesystem(self, source: Path, dest: Path) -> bool:
        """
        Check if source and destination are on the same filesystem.

        Uses st_dev (device ID) which works across platforms and correctly
        identifies network drives, RAID arrays, virtual drives, etc.

        Args:
            source: Source file or folder path
            dest: Destination directory path

        Returns:
            True if same filesystem, False otherwise or on any error
        """
        try:
            # Resolve any symlinks to get actual paths
            source_resolved = source.resolve()
            dest_resolved = dest.resolve() if dest.exists() else dest.parent.resolve()

            # Get device IDs
            source_stat = source_resolved.stat()
            dest_stat = dest_resolved.stat()

            # Compare device IDs
            same_device = source_stat.st_dev == dest_stat.st_dev

            if same_device:
                logger.debug(f"Same filesystem detected: {source} and {dest} (device: {source_stat.st_dev})")
            else:
                logger.debug(f"Different filesystems: {source} (device: {source_stat.st_dev}) vs {dest} (device: {dest_stat.st_dev})")

            return same_device

        except Exception as e:
            # On any error, return False to safely fall back to COPY mode
            logger.warning(f"Filesystem detection failed, defaulting to COPY mode: {e}")
            return False

    def _check_needs_long_path(self, path: Path, threshold: int = 248) -> bool:
        """
        Check if a path exceeds Windows MAX_PATH and needs the \\?\ prefix.

        Windows has a 260-character MAX_PATH limit. We use 248 as a conservative
        threshold to account for directory operations.

        Args:
            path: Path to check
            threshold: Character limit (default: 248 for safety margin)

        Returns:
            True if path needs \\?\ prefix, False otherwise
        """
        try:
            # Always check actual path length, not a pre-calculated flag
            path_str = str(path.resolve())
            needs_prefix = len(path_str) > threshold

            if needs_prefix:
                logger.debug(f"Path exceeds {threshold} chars ({len(path_str)}): {path_str[:100]}...")

            return needs_prefix

        except Exception as e:
            logger.debug(f"Could not check path length for {path}: {e}")
            return False

    def copy_file_buffered(self, source: Path, dest: Path, 
                          buffer_size: Optional[int] = None,
                          calculate_hash: bool = True) -> Result[Dict]:
        """
        Copy a single file with intelligent buffering based on file size
        
        Args:
            source: Source file path
            dest: Destination file path
            buffer_size: Buffer size in bytes (uses settings if None)
            calculate_hash: Whether to calculate SHA-256 hash
            
        Returns:
            Result[Dict] with copy results and metrics, or error information
        """
        # Input validation
        if not source or not source.exists():
            error = FileOperationError(
                f"Source file does not exist: {source}",
                user_message="Source file not found. Please check the file path."
            )
            return Result.error(error)
            
        if not dest:
            error = FileOperationError(
                "Destination path not provided",
                user_message="Destination path is required for file copy operation."
            )
            return Result.error(error)
        
        # Get buffer size from settings (convert from KB to bytes)
        if buffer_size is None:
            buffer_size_kb = self.settings.copy_buffer_size  # Already clamped 8KB-10MB
            buffer_size = buffer_size_kb * 1024
        else:
            # Ensure buffer size is reasonable
            buffer_size = min(max(buffer_size, 8192), 10485760)  # 8KB to 10MB
        
        logger.debug(f"[BUFFERED OPS] Copying {source.name} with buffer size {buffer_size/1024:.0f}KB")
        
        try:
            file_size = source.stat().st_size
        except OSError as e:
            error = FileOperationError(
                f"Cannot access source file {source}: {e}",
                user_message="Cannot access source file. Please check file permissions."
            )
            return Result.error(error)
        result = {
            'source_path': str(source),
            'dest_path': str(dest),
            'size': file_size,
            'start_time': time.time(),
            'buffer_size': buffer_size,
            'method': 'buffered'
        }
        
        try:
            # Ensure destination directory exists
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            # Categorize file size
            if file_size < self.SMALL_FILE_THRESHOLD:
                self.metrics.small_files_count += 1
                result['method'] = 'direct'
            elif file_size < self.LARGE_FILE_THRESHOLD:
                self.metrics.medium_files_count += 1
            else:
                self.metrics.large_files_count += 1
            
            # Choose copy strategy based on file size
            if file_size < self.SMALL_FILE_THRESHOLD:
                # Small files: Direct copy with separate hashing for simplicity
                # For small files, the optimization provides minimal benefit
                
                # Read file once for both copy and source hash
                with open(source, 'rb') as f:
                    data = f.read()
                
                # Calculate source hash if needed
                source_hash = ""
                if calculate_hash:
                    source_hash = hashlib.sha256(data).hexdigest()
                    result['source_hash'] = source_hash
                
                # Write data to destination
                with open(dest, 'wb') as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                
                bytes_copied = file_size
                
                # Verify destination hash for forensic integrity
                if calculate_hash:
                    dest_hash = self._calculate_hash_streaming(dest, buffer_size)
                    result['dest_hash'] = dest_hash
                    result['verified'] = source_hash == dest_hash
                    
                    if not result['verified']:
                        error = HashVerificationError(
                            f"Hash verification failed for {source}: source={source_hash}, dest={dest_hash}",
                            user_message="File integrity check failed. The copied file may be corrupted.",
                            file_path=str(dest),
                            expected_hash=source_hash,
                            actual_hash=dest_hash
                        )
                        return Result.error(error)
                else:
                    result['verified'] = True
                
            else:
                # Medium/Large files: Use OPTIMIZED streaming with integrated source hashing
                # This is where we get the major performance benefit (33% reduction in reads)
                logger.debug(f"[BUFFERED OPS OPTIMIZED] Using 2-read optimization for {source.name}")
                
                bytes_copied, source_hash, dest_hash = self._stream_copy_with_hash(
                    source, dest, buffer_size, file_size, calculate_hash
                )
                
                # Track optimization benefit
                if calculate_hash:
                    self.metrics.disk_reads_saved += 1  # Saved 1 read (combined source hash+copy)
                
                if calculate_hash:
                    result['source_hash'] = source_hash
                    result['dest_hash'] = dest_hash
                    result['verified'] = source_hash == dest_hash
                    
                    # Handle hash verification failure
                    if not result['verified']:
                        error = HashVerificationError(
                            f"Hash verification failed for {source}: source={source_hash}, dest={dest_hash}",
                            user_message="File integrity check failed. The copied file may be corrupted.",
                            file_path=str(dest),
                            expected_hash=source_hash,
                            actual_hash=dest_hash
                        )
                        return Result.error(error)
                else:
                    result['verified'] = True
            
            # Preserve metadata
            shutil.copystat(source, dest)
            
            # Calculate metrics
            result['end_time'] = time.time()
            result['duration'] = result['end_time'] - result['start_time']
            result['bytes_copied'] = bytes_copied
            result['success'] = True
            
            # Speed calculation
            if result['duration'] > 0:
                result['speed_mbps'] = (bytes_copied / (1024 * 1024)) / result['duration']
            else:
                result['speed_mbps'] = 0
            
            # Update cumulative metrics for this file
            self.metrics.bytes_copied += bytes_copied
            
            # Note: We don't update files_processed here since this is for a single file
            # The calling code should handle file counting
            
            return Result.success(result)
            
        except PermissionError as e:
            error = FileOperationError(
                f"Permission denied copying {source} to {dest}: {e}",
                user_message="Cannot copy file due to permission restrictions. Please check folder permissions."
            )
            self.metrics.errors.append(f"{source.name}: Permission denied")
            return Result.error(error)
            
        except OSError as e:
            error = FileOperationError(
                f"File system error copying {source} to {dest}: {e}",
                user_message="File copy failed due to a file system error. Please check available disk space."
            )
            self.metrics.errors.append(f"{source.name}: {str(e)}")
            return Result.error(error)
            
        except Exception as e:
            error = FileOperationError(
                f"Unexpected error copying {source} to {dest}: {e}",
                user_message="An unexpected error occurred during file copying."
            )
            self.metrics.errors.append(f"{source.name}: {str(e)}")
            return Result.error(error)
    
    def _stream_copy(self, source: Path, dest: Path, buffer_size: int, total_size: int) -> int:
        """
        Stream copy with progress reporting
        
        Returns:
            Bytes copied
        """
        bytes_copied = 0
        last_update_time = time.time()
        last_copied_bytes = 0
        
        with open(source, 'rb') as src:
            with open(dest, 'wb') as dst:
                while not self.cancelled:
                    # Check for pause - this should block if paused
                    if self.pause_check:
                        self.pause_check()  # This should block until resumed
                    
                    # Read chunk
                    chunk = src.read(buffer_size)
                    if not chunk:
                        break
                    
                    # Write chunk
                    dst.write(chunk)
                    bytes_copied += len(chunk)
                    
                    # Calculate progress and speed
                    current_time = time.time()
                    time_delta = current_time - last_update_time
                    
                    # Update every 0.1 seconds for smooth progress
                    if time_delta >= 0.1:
                        bytes_delta = bytes_copied - last_copied_bytes
                        current_speed_mbps = (bytes_delta / time_delta) / (1024 * 1024) if time_delta > 0 else 0
                        
                        # Update metrics
                        self.metrics.current_speed_mbps = current_speed_mbps
                        self.metrics.add_speed_sample(current_speed_mbps)
                        # Don't accumulate bytes here - we'll update the total after the file is done
                        
                        # Report progress for this individual file
                        file_progress_pct = int((bytes_copied / total_size * 100)) if total_size > 0 else 0
                        
                        # Calculate overall progress if we have total_bytes set
                        if self.metrics.total_bytes > 0:
                            # Overall progress = already copied + current file progress
                            overall_bytes = self.metrics.bytes_copied + bytes_copied
                            overall_progress_pct = int((overall_bytes / self.metrics.total_bytes * 100))
                            self._report_progress(
                                overall_progress_pct,
                                f"Streaming {source.name} @ {current_speed_mbps:.1f} MB/s"
                            )
                        else:
                            # Fall back to file-level progress
                            self._report_progress(
                                file_progress_pct,
                                f"Streaming {source.name} @ {current_speed_mbps:.1f} MB/s"
                            )
                        
                        # Update metrics callback
                        if self.metrics_callback:
                            self.metrics_callback(self.metrics)
                        
                        last_update_time = current_time
                        last_copied_bytes = bytes_copied
                    
                    # Check for cancellation
                    if self.cancel_event.is_set():
                        raise InterruptedError("Operation cancelled")
                
                # Force flush to disk after streaming copy
                dst.flush()
                os.fsync(dst.fileno())
        
        return bytes_copied
    
    def _calculate_hash_streaming(self, file_path: Path, buffer_size: int) -> str:
        """Calculate file hash with streaming read"""
        hash_obj = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            while True:
                # Check for pause
                if self.pause_check:
                    self.pause_check()
                
                chunk = f.read(buffer_size)
                if not chunk:
                    break
                hash_obj.update(chunk)
                
                # Check cancellation (support both internal flag and external check)
                if self.cancelled or (self.cancelled_check and self.cancelled_check()):
                    raise InterruptedError("Hash calculation cancelled")
        
        return hash_obj.hexdigest()
    
    def _stream_copy_with_hash(self, source: Path, dest: Path, buffer_size: int,
                               total_size: int, calculate_hash: bool = True) -> Tuple[int, str, str]:
        """
        Optimized stream copy with integrated source hashing.
        
        FORENSIC INTEGRITY NOTE:
        This method performs a 2-read optimization for forensic applications:
        1. Reads source file ONCE, hashing while reading and copying
        2. Reads destination file separately to verify actual disk content
        
        This ensures the destination hash represents what's actually on disk,
        not just what was in memory, which is critical for legal defensibility.
        
        Performance: 33% reduction in disk reads vs. the previous 3-read approach.
        
        Args:
            source: Source file path
            dest: Destination file path  
            buffer_size: Buffer size for streaming
            total_size: Total file size for progress reporting
            calculate_hash: Whether to calculate SHA-256 hashes
            
        Returns:
            Tuple of (bytes_copied, source_hash, dest_hash)
        """
        bytes_copied = 0
        last_update_time = time.time()
        last_copied_bytes = 0
        
        # Initialize source hash object if needed
        source_hash_obj = hashlib.sha256() if calculate_hash else None
        
        with open(source, 'rb') as src:
            with open(dest, 'wb') as dst:
                while not self.cancelled:
                    # Check for pause
                    if self.pause_check:
                        self.pause_check()
                    
                    # Read chunk once
                    chunk = src.read(buffer_size)
                    if not chunk:
                        break
                    
                    # Hash source data during read (OPTIMIZATION)
                    if source_hash_obj:
                        source_hash_obj.update(chunk)
                    
                    # Write chunk to destination
                    bytes_written = dst.write(chunk)
                    
                    # Verify complete write
                    if bytes_written != len(chunk):
                        raise IOError(f"Incomplete write: {bytes_written} of {len(chunk)} bytes")
                    
                    bytes_copied += bytes_written
                    
                    # Progress reporting
                    current_time = time.time()
                    time_delta = current_time - last_update_time
                    
                    if time_delta >= 0.1:  # Update every 100ms
                        bytes_delta = bytes_copied - last_copied_bytes
                        current_speed_mbps = (bytes_delta / time_delta) / (1024 * 1024) if time_delta > 0 else 0
                        
                        # Update metrics
                        self.metrics.current_speed_mbps = current_speed_mbps
                        self.metrics.add_speed_sample(current_speed_mbps)
                        
                        # Calculate progress percentage
                        file_progress_pct = int((bytes_copied / total_size * 100)) if total_size > 0 else 0
                        
                        # Report progress with appropriate message
                        status_msg = f"Copying and hashing source {source.name} @ {current_speed_mbps:.1f} MB/s"
                        
                        # Use overall progress if available, otherwise file progress
                        if self.metrics.total_bytes > 0:
                            overall_bytes = self.metrics.bytes_copied + bytes_copied
                            overall_progress_pct = int((overall_bytes / self.metrics.total_bytes * 100))
                            self._report_progress(overall_progress_pct, status_msg)
                        else:
                            self._report_progress(file_progress_pct, status_msg)
                        
                        # Call metrics callback if provided
                        if self.metrics_callback:
                            self.metrics_callback(self.metrics)
                        
                        last_update_time = current_time
                        last_copied_bytes = bytes_copied
                    
                    # Check for cancellation
                    if self.cancel_event.is_set():
                        raise InterruptedError("Operation cancelled")
                
                # Force flush to disk
                dst.flush()
                os.fsync(dst.fileno())
        
        # Calculate source hash from the read operation
        source_hash = source_hash_obj.hexdigest() if source_hash_obj else ""
        
        # CRITICAL FOR FORENSICS: Hash the destination file from disk
        # This ensures we're verifying what's actually stored, not what's in memory
        dest_hash = ""
        if calculate_hash:
            # Report verification progress
            self._report_progress(100, f"Hashing destination and verifying {dest.name}...")
            dest_hash = self._calculate_hash_streaming(dest, buffer_size)
        
        return bytes_copied, source_hash, dest_hash
    
    def copy_files(self, files: List[Path], destination: Path,
                   calculate_hash: bool = True) -> FileOperationResult:
        """
        Copy multiple files with buffering and detailed metrics
        
        Args:
            files: List of files to copy
            destination: Destination directory
            calculate_hash: Whether to calculate hashes
            
        Returns:
            FileOperationResult with results and performance metrics
        """
        # Input validation
        if not files:
            error = FileOperationError(
                "No files provided for copy operation",
                user_message="Please select files to copy."
            )
            return FileOperationResult.error(error)
            
        if not destination:
            error = FileOperationError(
                "Destination path not provided",
                user_message="Destination directory is required for file copy operation."
            )
            return FileOperationResult.error(error)
        
        # Initialize metrics
        try:
            total_size = sum(f.stat().st_size for f in files if f.exists())
        except OSError as e:
            error = FileOperationError(
                f"Cannot access file size information: {e}",
                user_message="Cannot access some files. Please check file permissions."
            )
            return FileOperationResult.error(error)
            
        self.metrics = PerformanceMetrics(
            start_time=time.time(),
            total_files=len(files),
            total_bytes=total_size,
            buffer_size_used=self.settings.copy_buffer_size * 1024,
            operation_type="buffered"
        )
        
        results = {}
        
        # Create destination directory
        try:
            destination.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            error = FileOperationError(
                f"Cannot create destination directory {destination}: {e}",
                user_message="Cannot create destination directory. Please check folder permissions."
            )
            return FileOperationResult.error(error)
        
        for idx, file in enumerate(files):
            if self.cancelled or (self.cancelled_check and self.cancelled_check()):
                break
            
            if not file.exists():
                # Track skipped files
                results[file.name] = {
                    'success': False,
                    'error': f"File does not exist: {file}",
                    'source_path': str(file),
                    'skipped': True
                }
                continue
            
            # Copy with buffering
            dest_file = destination / file.name
            copy_result = self.copy_file_buffered(
                file, 
                dest_file,
                calculate_hash=calculate_hash
            )
            
            # Handle Result object from copy_file_buffered
            if copy_result.success:
                # Store the successful result data
                result_data = copy_result.value
                result_data['success'] = True
                results[file.name] = result_data
                
                # Update metrics
                self.metrics.files_processed += 1
                if 'bytes_copied' in result_data:
                    self.metrics.bytes_copied += result_data['bytes_copied']
            else:
                # Store error result
                results[file.name] = {
                    'success': False,
                    'error': str(copy_result.error),
                    'source_path': str(file),
                    'dest_path': str(dest_file)
                }
                self.metrics.errors.append(f"{file.name}: {copy_result.error}")
            
            # Overall progress
            overall_progress = int((self.metrics.bytes_copied / self.metrics.total_bytes * 100)) \
                             if self.metrics.total_bytes > 0 else 0
            self._report_progress(
                overall_progress,
                f"Completed {self.metrics.files_processed}/{self.metrics.total_files} files"
            )
        
        # Calculate final metrics
        self.metrics.end_time = time.time()
        self.metrics.calculate_summary()
        
        # Add performance stats to results (matching legacy format)
        duration = self.metrics.end_time - self.metrics.start_time
        results['_performance_stats'] = {
            'files_processed': self.metrics.files_processed,
            'total_bytes': self.metrics.bytes_copied,
            'total_time_seconds': duration,
            'average_speed_mbps': self.metrics.average_speed_mbps,
            'peak_speed_mbps': self.metrics.peak_speed_mbps,
            'total_size_mb': self.metrics.bytes_copied / (1024 * 1024),
            'efficiency_score': min(self.metrics.average_speed_mbps / 50, 1.0) if self.metrics.average_speed_mbps > 0 else 0,
            'mode': 'buffered'
        }
        
        # Final progress report
        self._report_progress(
            100,
            f"Completed: {self.metrics.files_processed} files, "
            f"{self.metrics.bytes_copied/(1024*1024):.1f} MB @ "
            f"{self.metrics.average_speed_mbps:.1f} MB/s avg"
        )
        
        # Log comprehensive summary statistics (replaces per-file logging)
        if self.metrics.files_processed > 0:
            logger.info(f"[BUFFERED OPS SUMMARY] Operation Complete:")
            logger.info(f"  • Files processed: {self.metrics.files_processed}/{self.metrics.total_files}")
            logger.info(f"  • Data copied: {self.metrics.bytes_copied/(1024*1024):.1f} MB")
            logger.info(f"  • Time taken: {duration:.1f} seconds")
            logger.info(f"  • Average speed: {self.metrics.average_speed_mbps:.1f} MB/s")
            logger.info(f"  • Peak speed: {self.metrics.peak_speed_mbps:.1f} MB/s")
            if self.metrics.disk_reads_saved > 0:
                logger.info(f"  • Optimization: Saved {self.metrics.disk_reads_saved} disk reads (33% I/O reduction)")
            if self.metrics.small_files_count > 0:
                logger.info(f"  • File distribution: {self.metrics.small_files_count} small, "
                          f"{self.metrics.medium_files_count} medium, {self.metrics.large_files_count} large")
        
        # Create FileOperationResult
        return FileOperationResult.create(
            results,
            files_processed=self.metrics.files_processed,
            bytes_processed=self.metrics.bytes_copied
        )

    def move_files_preserving_structure(
        self,
        items: List[tuple],  # (type, path, relative_path)
        destination: Path,
        calculate_hash: bool = True
    ) -> FileOperationResult:
        """
        Move files/folders while preserving directory structure.

        Automatically detects if source and destination are on the same filesystem.
        If yes, uses fast MOVE operations. If no, falls back to COPY.

        This is the main entry point for intelligent file operations.

        Args:
            items: List of (type, path, relative_path) tuples
            destination: Destination directory
            calculate_hash: Whether to calculate post-operation hashes

        Returns:
            FileOperationResult with operation details
        """
        try:
            # Check settings preference
            behavior = self.settings.same_drive_behavior

            # Determine if same filesystem (check first item as representative)
            if not items:
                error = FileOperationError(
                    "No items provided for move operation",
                    user_message="No files selected to process."
                )
                return FileOperationResult.error(error)

            first_item = items[0]
            same_filesystem = self._is_same_filesystem(first_item[1], destination)

            # Determine operation mode based on settings and detection
            if behavior == 'auto_copy':
                # User wants COPY only
                operation_mode = 'copy'
                self._report_progress(0, "Standard mode: Copying files (user preference)")
                logger.info(
                    f"COPY MODE SELECTED:\n"
                    f"  Reason: User preference (always copy)\n"
                    f"  Files: {len(items)}\n"
                    f"  User setting: {behavior}"
                )
            elif behavior == 'auto_move' and same_filesystem:
                # Auto-move enabled and same filesystem
                operation_mode = 'move'
                self._report_progress(0, "Fast mode: Moving files (same drive detected)")
                source_dev = first_item[1].stat().st_dev
                dest_dev = destination.stat().st_dev if destination.exists() else destination.parent.stat().st_dev
                logger.info(
                    f"MOVE MODE SELECTED:\n"
                    f"  Reason: Same filesystem detected\n"
                    f"  Source device: {source_dev}\n"
                    f"  Dest device: {dest_dev}\n"
                    f"  Files: {len(items)}\n"
                    f"  User setting: {behavior}"
                )
            elif behavior == 'ask':
                # Not implemented yet - default to copy for now
                # TODO: Phase 2 - implement confirmation dialog
                operation_mode = 'copy'
                self._report_progress(0, "Standard mode: Copying files")
                logger.info(
                    f"COPY MODE SELECTED:\n"
                    f"  Reason: Ask mode not implemented yet\n"
                    f"  Files: {len(items)}\n"
                    f"  User setting: {behavior}"
                )
            else:
                # Different filesystem or other cases
                operation_mode = 'copy'
                reason = "different filesystems" if not same_filesystem else "default"
                if not same_filesystem:
                    self._report_progress(0, "Standard mode: Copying files (different drives)")
                else:
                    self._report_progress(0, "Standard mode: Copying files")
                logger.info(
                    f"COPY MODE SELECTED:\n"
                    f"  Reason: {reason}\n"
                    f"  Files: {len(items)}\n"
                    f"  User setting: {behavior}"
                )

            # Execute appropriate operation
            if operation_mode == 'move':
                return self._move_files_internal(items, destination, calculate_hash)
            else:
                return self._copy_files_internal(items, destination, calculate_hash)

        except Exception as e:
            error = FileOperationError(
                f"File operation failed: {e}",
                user_message="File processing failed. Please check permissions and disk space."
            )
            logger.error(f"move_files_preserving_structure failed: {e}", exc_info=True)
            return FileOperationResult.error(error)

    def _move_files_internal(
        self,
        items: List[tuple],
        destination: Path,
        calculate_hash: bool
    ) -> FileOperationResult:
        """
        Internal method to move files with progress tracking and hash verification.

        This uses file-count based progress (not byte-based) since moves are instant.
        """
        try:
            self.metrics.start_time = time.time()
            total_items = len(items)
            results = {}

            logger.info(f"Starting MOVE operation: {total_items} items to {destination}")

            # Ensure destination exists
            destination.mkdir(parents=True, exist_ok=True)

            # Track moved items for potential rollback
            moved_items = []  # [(source, dest), ...]

            for idx, (item_type, source_path, relative_path) in enumerate(items):
                # Check cancellation
                if self.cancelled or (self.cancelled_check and self.cancelled_check()):
                    logger.warning("MOVE operation cancelled by user")
                    # Rollback moved items
                    self._rollback_moves(moved_items)
                    error = FileOperationError(
                        "Operation cancelled by user",
                        user_message="File move operation was cancelled."
                    )
                    return FileOperationResult.error(error)

                # Check pause
                if self.pause_check:
                    self.pause_check()

                # Calculate progress based on file count
                progress_pct = int((idx / total_items * 100)) if total_items > 0 else 0

                # Status message (moves are instant, so no ETA calculation needed)
                status_message = f"Moving: {source_path.name} ({idx+1}/{total_items})"

                # Determine destination path
                if relative_path:
                    dest_path = destination / relative_path
                else:
                    dest_path = destination / source_path.name

                # CRITICAL: For shutil.move() to work, BOTH source and dest must use
                # the same path format (both with \\?\ or both without).
                # Check if EITHER path needs long path support.
                source_needs_long = self._check_needs_long_path(source_path)
                dest_needs_long = self._check_needs_long_path(dest_path)
                needs_long_path = source_needs_long or dest_needs_long

                # Apply \\?\ prefix to BOTH or NEITHER (never mix formats!)
                if needs_long_path:
                    # Both paths get the prefix to avoid namespace mismatch
                    source_str = f"\\\\?\\{source_path.resolve()}"
                    dest_str = f"\\\\?\\{dest_path.resolve()}"
                    logger.debug(f"Using long path support for move: {source_path.name}")
                else:
                    # Neither gets the prefix
                    source_str = str(source_path)
                    dest_str = str(dest_path)

                # Ensure parent directory exists
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Report progress
                self._report_progress(progress_pct, status_message)

                try:
                    # Get file size before move (for metrics)
                    if item_type == 'file' and source_path.exists():
                        file_size = source_path.stat().st_size
                    else:
                        file_size = 0

                    # Perform the move with matched path formats
                    shutil.move(source_str, dest_str)

                    # Track for potential rollback
                    moved_items.append((source_path, dest_path))

                    # Calculate hash after move (verifies file is readable at destination)
                    dest_hash = None
                    if calculate_hash and item_type == 'file':
                        dest_hash = self._calculate_hash_streaming(dest_path, 65536)

                    # Store result
                    result_data = {
                        'source_path': str(source_path),
                        'dest_path': str(dest_path),
                        'size': file_size,
                        'operation': 'move',
                        'dest_hash': dest_hash,
                        'verified': True
                    }

                    results[str(relative_path if relative_path else source_path.name)] = result_data

                    # Update metrics
                    self.metrics.files_processed += 1
                    self.metrics.bytes_copied += file_size

                except PermissionError as e:
                    logger.error(f"Permission denied moving {source_path}: {e}")
                    self._rollback_moves(moved_items)
                    error = FileOperationError(
                        f"Permission denied: {source_path.name}",
                        user_message=(
                            f"Cannot move '{source_path.name}': Permission denied.\n\n"
                            "Possible causes:\n"
                            "• File is locked by another program\n"
                            "• You don't have write access to destination\n"
                            "• File or folder is read-only\n\n"
                            "Try closing any programs using these files and try again."
                        )
                    )
                    return FileOperationResult.error(error)

                except OSError as e:
                    logger.error(f"OS error moving {source_path}: {e}")
                    self._rollback_moves(moved_items)

                    # Check for disk full
                    if "No space left on device" in str(e) or (hasattr(e, 'errno') and e.errno == 28):
                        error_msg = (
                            f"Cannot move files: Destination drive is full.\n\n"
                            f"Please free up space and try again."
                        )
                    # Check for path too long (Windows)
                    elif "path too long" in str(e).lower() or (hasattr(e, 'errno') and e.errno == 36):
                        error_msg = (
                            f"Cannot move '{source_path.name}': Path too long.\n\n"
                            "Windows has a 260-character path limit.\n"
                            "Try using a shorter destination path."
                        )
                    else:
                        error_msg = f"Cannot move '{source_path.name}': {e}"

                    error = FileOperationError(
                        f"OS error: {e}",
                        user_message=error_msg
                    )
                    return FileOperationResult.error(error)

                except Exception as e:
                    # Move failed for this item - rollback all previous moves
                    logger.error(f"Unexpected error moving {source_path}: {e}", exc_info=True)
                    self._rollback_moves(moved_items)
                    error = FileOperationError(
                        f"Unexpected error: {e}",
                        user_message=(
                            f"An unexpected error occurred moving '{source_path.name}'.\n"
                            f"Error: {str(e)}\n\n"
                            "Previous moves have been rolled back."
                        )
                    )
                    return FileOperationResult.error(error)

            # All moves succeeded
            self.metrics.end_time = time.time()
            self.metrics.calculate_summary()

            # Final progress
            self._report_progress(100, f"Move complete: {self.metrics.files_processed} items")

            # Add performance stats
            duration = self.metrics.end_time - self.metrics.start_time
            results['_performance_stats'] = {
                'files_processed': self.metrics.files_processed,
                'total_bytes': self.metrics.bytes_copied,
                'total_time_seconds': duration,
                'operation_mode': 'move',
                'average_speed_mbps': self.metrics.average_speed_mbps,
                'mode': 'move'
            }

            logger.info(
                f"MOVE operation completed: {self.metrics.files_processed} items, "
                f"{duration:.2f}s"
            )

            return FileOperationResult.create(
                results,
                files_processed=self.metrics.files_processed,
                bytes_processed=self.metrics.bytes_copied
            )

        except Exception as e:
            logger.error(f"MOVE operation failed: {e}", exc_info=True)
            error = FileOperationError(
                f"Move operation failed: {e}",
                user_message="File move operation failed. Changes may have been partially applied."
            )
            return FileOperationResult.error(error)

    def _rollback_moves(self, moved_items: List[tuple]):
        """
        Rollback moved files back to their original locations.

        Args:
            moved_items: List of (original_source, current_dest) tuples
        """
        if not moved_items:
            return

        logger.warning(f"Rolling back {len(moved_items)} moved items")

        failed_rollbacks = []

        # Rollback in reverse order
        for source_path, dest_path in reversed(moved_items):
            try:
                if dest_path.exists():
                    shutil.move(str(dest_path), str(source_path))
                    logger.debug(f"Rolled back: {dest_path} -> {source_path}")
            except Exception as e:
                logger.error(f"Rollback failed for {dest_path} -> {source_path}: {e}")
                failed_rollbacks.append((source_path, dest_path, str(e)))

        if failed_rollbacks:
            logger.error(f"Rollback incomplete: {len(failed_rollbacks)} items could not be restored")
            for source, dest, error in failed_rollbacks:
                logger.error(f"  Failed: {dest} -> {source}: {error}")
        else:
            logger.info("Rollback completed successfully")

    def _copy_files_internal(
        self,
        items: List[tuple],
        destination: Path,
        calculate_hash: bool
    ) -> FileOperationResult:
        """
        Internal method to copy files with progress tracking and hash verification.

        Uses traditional COPY operations (does not modify source location).
        """
        try:
            self.metrics.start_time = time.time()
            total_items = len(items)
            results = {}

            logger.info(f"Starting COPY operation: {total_items} items to {destination}")

            # Ensure destination exists
            destination.mkdir(parents=True, exist_ok=True)

            for idx, (item_type, source_path, relative_path) in enumerate(items):
                # Check cancellation
                if self.cancelled or (self.cancelled_check and self.cancelled_check()):
                    logger.warning("COPY operation cancelled by user")
                    error = FileOperationError(
                        "Operation cancelled by user",
                        user_message="File copy operation was cancelled."
                    )
                    return FileOperationResult.error(error)

                # Check pause
                if self.pause_check:
                    self.pause_check()

                # Calculate progress based on file count
                progress_pct = int((idx / total_items * 100)) if total_items > 0 else 0

                # Status message
                status_message = f"Copying: {source_path.name} ({idx+1}/{total_items})"

                # Determine destination path
                if relative_path:
                    dest_path = destination / relative_path
                else:
                    dest_path = destination / source_path.name

                # Note: For copy_file_buffered(), we don't need the \\?\ prefix
                # because it opens files directly with Python's open(), which handles
                # long paths automatically on Windows 10+ with LongPathsEnabled registry.
                # Only shutil.move() with os.rename() has the namespace mismatch issue.

                # Ensure parent directory exists
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Report progress
                self._report_progress(progress_pct, status_message)

                try:
                    # Perform the copy using existing buffered method
                    copy_result = self.copy_file_buffered(
                        source_path,
                        dest_path,
                        calculate_hash=calculate_hash
                    )

                    if copy_result.success:
                        copy_data = copy_result.value
                        result_data = {
                            'source_path': str(source_path),
                            'dest_path': str(dest_path),
                            'size': copy_data.get('size', 0),
                            'operation': 'copy',
                            'source_hash': copy_data.get('source_hash'),
                            'dest_hash': copy_data.get('dest_hash'),
                            'verified': copy_data.get('verified', True)
                        }
                        results[str(relative_path if relative_path else source_path.name)] = result_data

                        # Update metrics
                        self.metrics.files_processed += 1
                        self.metrics.bytes_copied += copy_data.get('size', 0)
                    else:
                        # Copy failed
                        error = copy_result.error
                        logger.error(f"Copy failed for {source_path}: {error}")
                        return FileOperationResult.error(error)

                except Exception as e:
                    logger.error(f"Unexpected error copying {source_path}: {e}", exc_info=True)
                    error = FileOperationError(
                        f"Unexpected error: {e}",
                        user_message=f"An unexpected error occurred copying '{source_path.name}'."
                    )
                    return FileOperationResult.error(error)

            # All copies succeeded
            self.metrics.end_time = time.time()
            self.metrics.calculate_summary()

            # Final progress
            self._report_progress(100, f"Copy complete: {self.metrics.files_processed} items")

            # Add performance stats
            duration = self.metrics.end_time - self.metrics.start_time
            results['_performance_stats'] = {
                'files_processed': self.metrics.files_processed,
                'total_bytes': self.metrics.bytes_copied,
                'total_time_seconds': duration,
                'operation_mode': 'copy',
                'average_speed_mbps': self.metrics.average_speed_mbps,
                'mode': 'copy'
            }

            logger.info(
                f"COPY operation completed: {self.metrics.files_processed} items, "
                f"{duration:.2f}s"
            )

            return FileOperationResult.create(
                results,
                files_processed=self.metrics.files_processed,
                bytes_processed=self.metrics.bytes_copied
            )

        except Exception as e:
            logger.error(f"COPY operation failed: {e}", exc_info=True)
            error = FileOperationError(
                f"Copy operation failed: {e}",
                user_message="File copy operation failed."
            )
            return FileOperationResult.error(error)

    def _report_progress(self, percentage: int, message: str):
        """Report progress if callback is available"""
        if self.progress_callback:
            self.progress_callback(percentage, message)
    
    def cancel(self):
        """Cancel the current operation"""
        self.cancelled = True
        self.cancel_event.set()
    
    def get_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics"""
        return self.metrics
    
    def reset_metrics(self):
        """Reset metrics for new operation"""
        self.metrics = PerformanceMetrics()
        self.cancelled = False
        self.cancel_event.clear()
    
    def verify_hashes(self, file_results: Dict[str, Dict]) -> Dict[str, bool]:
        """
        Verify that source and destination hashes match
        
        Args:
            file_results: Results from copy_files operation
            
        Returns:
            Dict mapping filenames to verification status
        """
        verification_results = {}
        
        for filename, data in file_results.items():
            if isinstance(data, dict) and 'source_hash' in data and 'dest_hash' in data:
                if data['source_hash'] and data['dest_hash']:
                    verification_results[filename] = data['source_hash'] == data['dest_hash']
                else:
                    verification_results[filename] = True  # No hash to verify
        
        return verification_results
    
    def hash_files_parallel(self, files: List[Path]) -> Dict[str, str]:
        """
        Calculate SHA-256 hashes for multiple files in parallel
        
        Args:
            files: List of files to hash
            
        Returns:
            Dict mapping file paths to their hashes
        """
        results = {}
        
        # Use hashwise if available for large batches
        if HASHWISE_AVAILABLE and len(files) >= 4:
            try:
                hasher = ParallelHasher(
                    algorithm='sha256',
                    workers=min(os.cpu_count() or 4, 8),  # Reasonable worker limit
                    chunk_size='auto'
                )
                hash_results = hasher.hash_files(files)
                return {str(path): hash_val for path, hash_val in hash_results.items()}
            except Exception as e:
                logging.warning(f"Hashwise failed, falling back to ThreadPoolExecutor: {e}")
        
        # Fallback to ThreadPoolExecutor for parallel hashing
        workers = min(os.cpu_count() or 4, 8)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_file = {
                executor.submit(self._calculate_hash_streaming, file, 65536): file
                for file in files
            }
            
            for future in as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    hash_value = future.result()
                    results[str(file)] = hash_value
                except Exception as e:
                    logging.error(f"Failed to hash {file}: {e}")
                    results[str(file)] = None
                    
        return results
    
    @staticmethod
    def get_folder_files(folder: Path, recursive: bool = False) -> List[Path]:
        """
        Get all files in a folder
        
        Args:
            folder: Folder path
            recursive: Whether to include subdirectories
            
        Returns:
            List of file paths
        """
        if recursive:
            return [f for f in folder.rglob('*') if f.is_file()]
        else:
            return [f for f in folder.iterdir() if f.is_file()]