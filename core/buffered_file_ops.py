#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
High-performance buffered file operations with streaming support
Phase 5 Performance Optimization
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
        
        logger.info(f"[BUFFERED OPS] Copying {source.name} with buffer size {buffer_size/1024:.0f}KB")
        
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
            
            # Calculate source hash if needed (before copy)
            source_hash = ""
            if calculate_hash:
                source_hash = self._calculate_hash_streaming(source, buffer_size)
                result['source_hash'] = source_hash
            
            # Choose copy strategy based on file size
            if file_size < self.SMALL_FILE_THRESHOLD:
                # Small files: copy at once (fastest for small files)
                shutil.copy2(source, dest)
                bytes_copied = file_size
                
                # Force flush to disk to ensure complete write (fixes VLC playback issue)
                with open(dest, 'rb+') as f:
                    os.fsync(f.fileno())
                
            else:
                # Medium/Large files: stream with buffer
                bytes_copied = self._stream_copy(source, dest, buffer_size, file_size)
            
            # Preserve metadata
            shutil.copystat(source, dest)
            
            # Calculate destination hash if needed
            if calculate_hash:
                dest_hash = self._calculate_hash_streaming(dest, buffer_size)
                result['dest_hash'] = dest_hash
                hash_match = source_hash == dest_hash
                result['verified'] = hash_match
                
                # Handle hash verification failure
                if not hash_match:
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
        
        # Create FileOperationResult
        return FileOperationResult.create(
            results,
            files_processed=self.metrics.files_processed,
            bytes_processed=self.metrics.bytes_copied
        )
    
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