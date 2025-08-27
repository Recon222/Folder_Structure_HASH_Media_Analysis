#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
High-performance buffered ZIP operations with streaming support
Designed to match BufferedFileOperations performance and architecture
"""

import zipfile
import time
import os
import logging
from pathlib import Path
from typing import List, Dict, Callable, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from threading import Event

from core.settings_manager import SettingsManager
from core.logger import logger
from core.result_types import Result, ArchiveOperationResult
from core.exceptions import ArchiveError, FileOperationError


@dataclass
class ZipPerformanceMetrics:
    """Track performance metrics for ZIP operations - mirrors PerformanceMetrics"""
    start_time: float = 0.0
    end_time: float = 0.0
    total_bytes: int = 0
    bytes_processed: int = 0
    files_processed: int = 0
    total_files: int = 0
    buffer_size_used: int = 0
    peak_speed_mbps: float = 0.0
    average_speed_mbps: float = 0.0
    current_speed_mbps: float = 0.0
    operation_type: str = "buffered_zip"
    errors: List[str] = field(default_factory=list)
    
    # ZIP-specific metrics
    archive_size: int = 0
    compression_ratio: float = 1.0  # 1.0 = no compression (ZIP_STORED)
    
    # File size distribution
    small_files_count: int = 0  # < 1MB
    medium_files_count: int = 0  # 1MB - 100MB
    large_files_count: int = 0  # > 100MB
    
    # Performance samples for monitoring
    speed_samples: List[Tuple[float, float]] = field(default_factory=list)  # (timestamp, speed_mbps)
    
    def calculate_summary(self):
        """Calculate summary statistics"""
        if self.end_time > self.start_time:
            duration = self.end_time - self.start_time
            self.average_speed_mbps = (self.bytes_processed / (1024 * 1024)) / duration if duration > 0 else 0
        
        # Calculate compression ratio (should be 1.0 for ZIP_STORED)
        if self.total_bytes > 0:
            self.compression_ratio = self.archive_size / self.total_bytes
    
    def add_speed_sample(self, speed_mbps: float):
        """Add a speed sample for monitoring"""
        self.speed_samples.append((time.time(), speed_mbps))
        if speed_mbps > self.peak_speed_mbps:
            self.peak_speed_mbps = speed_mbps


class BufferedZipOperations:
    """High-performance ZIP operations with configurable buffering and streaming"""
    
    # File size thresholds - same as BufferedFileOperations
    SMALL_FILE_THRESHOLD = 1_000_000      # 1MB - use threading
    LARGE_FILE_THRESHOLD = 100_000_000    # 100MB - use large buffers
    
    def __init__(self, progress_callback: Optional[Callable[[int, str], None]] = None,
                 metrics_callback: Optional[Callable[[ZipPerformanceMetrics], None]] = None,
                 cancelled_check: Optional[Callable[[], bool]] = None):
        """
        Initialize with optional callbacks
        
        Args:
            progress_callback: Function that receives (progress_pct, status_message)
            metrics_callback: Function that receives ZipPerformanceMetrics updates
            cancelled_check: Function that returns True if operation should be cancelled
        """
        self.progress_callback = progress_callback
        self.metrics_callback = metrics_callback
        self.cancelled_check = cancelled_check
        self.cancelled = False
        self.cancel_event = Event()
        self.settings = SettingsManager()
        self.metrics = ZipPerformanceMetrics()
        
    def get_optimal_buffer_size(self, file_size: int) -> int:
        """
        Get optimal buffer size based on file size - matches BufferedFileOperations logic
        
        Args:
            file_size: Size of file in bytes
            
        Returns:
            Optimal buffer size for this file
        """
        if file_size < self.SMALL_FILE_THRESHOLD:          # < 1MB
            return 256 * 1024                              # 256KB
        elif file_size < self.LARGE_FILE_THRESHOLD:        # < 100MB  
            return 2 * 1024 * 1024                         # 2MB
        else:                                              # >= 100MB
            return 10 * 1024 * 1024                        # 10MB
    
    def _categorize_file_by_size(self, file_size: int):
        """Categorize file by size for metrics"""
        if file_size < 1_000_000:          # < 1MB
            self.metrics.small_files_count += 1
        elif file_size < 100_000_000:      # < 100MB
            self.metrics.medium_files_count += 1
        else:                              # >= 100MB
            self.metrics.large_files_count += 1
    
    def add_file_optimized(self, zf: zipfile.ZipFile, file_path: Path, 
                          arcname: str) -> Result[int]:
        """
        Add file to ZIP using optimal method based on file size
        - Small files (< 1MB): Use fast legacy method
        - Large files (>= 1MB): Use buffered streaming for better performance
        
        Args:
            zf: Open ZipFile object
            file_path: Source file to add
            arcname: Archive name for the file
            
        Returns:
            Result containing bytes processed or error
        """
        try:
            file_size = file_path.stat().st_size
            
            # Update metrics
            self._categorize_file_by_size(file_size)
            
            # Choose optimal method based on file size
            if file_size < self.SMALL_FILE_THRESHOLD:
                # Small files: Use legacy method (faster for small files)
                return self._add_file_legacy(zf, file_path, arcname, file_size)
            else:
                # Large files: Use buffered streaming (faster for large files)  
                return self._add_file_buffered_streaming(zf, file_path, arcname, file_size)
                
        except Exception as e:
            error = ArchiveError(
                f"Unexpected error adding file to archive: {e}",
                archive_path=str(file_path),
                user_message=f"Failed to add {file_path.name} to archive."
            )
            self.metrics.errors.append(str(error))
            return Result.error(error)
    
    def _add_file_legacy(self, zf: zipfile.ZipFile, file_path: Path, 
                        arcname: str, file_size: int) -> Result[int]:
        """Add small file using legacy method (fast for small files)"""
        try:
            # Use the standard zipfile.write() for small files
            zf.write(file_path, arcname)
            
            self.metrics.bytes_processed += file_size
            self.metrics.buffer_size_used = 0  # No buffering used
            
            # Simple progress reporting
            self._report_progress(
                100,  # Small files complete immediately
                f"Added: {file_path.name}"
            )
            
            return Result.success(file_size)
            
        except Exception as e:
            error = ArchiveError(
                f"Error adding small file: {e}",
                archive_path=str(file_path),
                user_message=f"Failed to add {file_path.name} to archive."
            )
            self.metrics.errors.append(str(error))
            return Result.error(error)
    
    def _add_file_buffered_streaming(self, zf: zipfile.ZipFile, file_path: Path, 
                                   arcname: str, file_size: int) -> Result[int]:
        """Add large file using buffered streaming (faster for large files)"""
        try:
            buffer_size = self.get_optimal_buffer_size(file_size)
            bytes_processed = 0
            last_progress_time = time.time()
            last_progress_bytes = 0
            
            self.metrics.buffer_size_used = buffer_size
            
            # Stream file to ZIP with buffering
            with zf.open(arcname, 'w') as zf_file:
                with open(file_path, 'rb') as source_file:
                    while True:
                        # Check cancellation
                        if self.cancelled or (self.cancelled_check and self.cancelled_check()):
                            return Result.error(ArchiveError("Operation cancelled by user"))
                        
                        # Read chunk
                        chunk = source_file.read(buffer_size)
                        if not chunk:
                            break
                            
                        # Write to ZIP
                        zf_file.write(chunk)
                        bytes_processed += len(chunk)
                        self.metrics.bytes_processed += len(chunk)
                        
                        # Progress reporting (throttled to avoid UI flooding)
                        current_time = time.time()
                        if current_time - last_progress_time >= 0.1:  # Update every 100ms max
                            # Calculate current speed
                            time_delta = current_time - last_progress_time
                            bytes_delta = bytes_processed - last_progress_bytes
                            speed_mbps = (bytes_delta / (1024 * 1024)) / time_delta if time_delta > 0 else 0
                            
                            self.metrics.current_speed_mbps = speed_mbps
                            self.metrics.add_speed_sample(speed_mbps)
                            
                            # Report progress
                            progress_pct = int((bytes_processed / file_size * 100) if file_size > 0 else 100)
                            self._report_progress(
                                progress_pct,
                                f"Streaming: {file_path.name} ({speed_mbps:.1f} MB/s)"
                            )
                            
                            last_progress_time = current_time
                            last_progress_bytes = bytes_processed
                            
                            # Update metrics callback
                            if self.metrics_callback:
                                self.metrics_callback(self.metrics)
            
            # Ensure file data is written to disk (forensic integrity)
            if hasattr(zf, '_file') and hasattr(zf._file, 'fileno'):
                try:
                    os.fsync(zf._file.fileno())
                except (AttributeError, OSError):
                    pass  # Not all file objects support fsync
                    
            return Result.success(bytes_processed)
            
        except PermissionError as e:
            error = ArchiveError(
                f"Permission denied accessing file: {file_path}",
                archive_path=str(file_path),
                user_message=f"Cannot access file {file_path.name}. Check file permissions."
            )
            self.metrics.errors.append(str(error))
            return Result.error(error)
            
        except OSError as e:
            error = ArchiveError(
                f"File system error processing {file_path}: {e}",
                archive_path=str(file_path),
                user_message=f"Error reading file {file_path.name}. File may be corrupted or unavailable."
            )
            self.metrics.errors.append(str(error))
            return Result.error(error)
            
        except Exception as e:
            error = ArchiveError(
                f"Unexpected error adding file to archive: {e}",
                archive_path=str(file_path),
                user_message=f"Failed to add {file_path.name} to archive."
            )
            self.metrics.errors.append(str(error))
            return Result.error(error)
    
    def create_archive_buffered(self, source_path: Path, output_path: Path, 
                               compression_level: int = zipfile.ZIP_STORED) -> Result[ArchiveOperationResult]:
        """
        Create ZIP archive using high-performance buffered streaming
        
        Args:
            source_path: Directory or file to compress
            output_path: Where to save the ZIP file
            compression_level: ZIP compression level (default: ZIP_STORED for speed)
            
        Returns:
            Result containing ArchiveOperationResult with performance metrics
        """
        self.metrics = ZipPerformanceMetrics()  # Reset metrics
        self.metrics.start_time = time.time()
        
        try:
            # Get all files to compress
            if source_path.is_dir():
                files = [f for f in source_path.rglob('*') if f.is_file()]
            else:
                files = [source_path] if source_path.is_file() else []
            
            if not files:
                self._report_progress(100, "No files to compress")
                error = ArchiveError(
                    "No files found to compress",
                    archive_path=str(source_path),
                    user_message="No files were found in the specified location."
                )
                return Result.error(error)
            
            # Calculate metrics
            self.metrics.total_files = len(files)
            self.metrics.total_bytes = sum(f.stat().st_size for f in files)
            
            self._report_progress(0, f"Starting buffered ZIP creation: {len(files)} files")
            
            # Create ZIP file with buffered streaming
            with zipfile.ZipFile(output_path, 'w', compression=compression_level, 
                               compresslevel=None, allowZip64=True) as zf:
                
                for i, file_path in enumerate(files):
                    # Check cancellation
                    if self.cancelled or (self.cancelled_check and self.cancelled_check()):
                        self._report_progress(0, "ZIP operation cancelled")
                        return Result.error(ArchiveError("ZIP operation cancelled by user"))
                    
                    # Calculate archive name
                    if source_path.is_dir():
                        try:
                            arcname = file_path.relative_to(source_path)
                        except ValueError:
                            # Fallback if file is not under source_path
                            arcname = file_path.name
                    else:
                        arcname = file_path.name
                    
                    # Add file using optimized method (legacy for small, buffered for large)
                    result = self.add_file_optimized(zf, file_path, str(arcname))
                    
                    if not result.success:
                        # Continue with other files even if one fails (forensic robustness)
                        logger.warning(f"Failed to add file {file_path}: {result.error}")
                        self.metrics.errors.append(f"Failed to add {file_path.name}: {result.error}")
                        continue
                    
                    self.metrics.files_processed += 1
                    
                    # Overall progress reporting
                    overall_progress = int((i + 1) / len(files) * 100)
                    self._report_progress(
                        overall_progress,
                        f"Processed {i + 1}/{len(files)} files"
                    )
            
            # Final metrics calculation
            self.metrics.end_time = time.time()
            self.metrics.calculate_summary()
            
            # Get final archive size
            if output_path.exists():
                self.metrics.archive_size = output_path.stat().st_size
            
            # Create successful result
            archive_result = ArchiveOperationResult.create_successful(
                created_archives=[output_path],
                compression_level=compression_level,
                metadata={
                    'total_files': self.metrics.total_files,
                    'files_processed': self.metrics.files_processed,
                    'total_bytes': self.metrics.total_bytes,
                    'bytes_processed': self.metrics.bytes_processed,
                    'archive_size': self.metrics.archive_size,
                    'compression_ratio': self.metrics.compression_ratio,
                    'average_speed_mbps': self.metrics.average_speed_mbps,
                    'peak_speed_mbps': self.metrics.peak_speed_mbps,
                    'operation_duration': self.metrics.end_time - self.metrics.start_time,
                    'errors': self.metrics.errors,
                    'small_files': self.metrics.small_files_count,
                    'medium_files': self.metrics.medium_files_count,
                    'large_files': self.metrics.large_files_count
                }
            )
            
            self._report_progress(100, f"Archive created: {output_path.name} ({self.metrics.average_speed_mbps:.1f} MB/s avg)")
            
            # Final metrics callback
            if self.metrics_callback:
                self.metrics_callback(self.metrics)
            
            return archive_result
            
        except PermissionError as e:
            error = ArchiveError(
                f"Permission denied creating archive: {e}",
                archive_path=str(output_path),
                user_message="Cannot create archive. Check folder permissions and available disk space."
            )
            return Result.error(error)
            
        except OSError as e:
            error = ArchiveError(
                f"File system error creating archive: {e}",
                archive_path=str(output_path),
                user_message="Cannot create archive due to file system error. Check available disk space."
            )
            return Result.error(error)
            
        except Exception as e:
            error = ArchiveError(
                f"Unexpected error creating archive: {e}",
                archive_path=str(output_path),
                user_message="Archive creation failed due to an unexpected error."
            )
            return Result.error(error)
    
    def _report_progress(self, percentage: int, message: str):
        """Report progress if callback is available"""
        if self.progress_callback:
            self.progress_callback(percentage, message)
    
    def cancel(self):
        """Cancel the current operation"""
        self.cancelled = True
        self.cancel_event.set()
    
    def is_cancelled(self) -> bool:
        """Check if operation is cancelled"""
        return self.cancelled or (self.cancelled_check and self.cancelled_check())