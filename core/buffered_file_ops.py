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
from pathlib import Path
from typing import List, Dict, Callable, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from threading import Event

from core.settings_manager import SettingsManager
from core.logger import logger


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
                 metrics_callback: Optional[Callable[[PerformanceMetrics], None]] = None):
        """
        Initialize with optional callbacks
        
        Args:
            progress_callback: Function that receives (progress_pct, status_message)
            metrics_callback: Function that receives PerformanceMetrics updates
        """
        self.progress_callback = progress_callback
        self.metrics_callback = metrics_callback
        self.cancelled = False
        self.cancel_event = Event()
        self.settings = SettingsManager()
        self.metrics = PerformanceMetrics()
        
    def copy_file_buffered(self, source: Path, dest: Path, 
                          buffer_size: Optional[int] = None,
                          calculate_hash: bool = True) -> Dict:
        """
        Copy a single file with intelligent buffering based on file size
        
        Args:
            source: Source file path
            dest: Destination file path
            buffer_size: Buffer size in bytes (uses settings if None)
            calculate_hash: Whether to calculate SHA-256 hash
            
        Returns:
            Dict with copy results and metrics
        """
        # Get buffer size from settings (convert from KB to bytes)
        if buffer_size is None:
            buffer_size_kb = self.settings.copy_buffer_size  # Already clamped 8KB-10MB
            buffer_size = buffer_size_kb * 1024
        else:
            # Ensure buffer size is reasonable
            buffer_size = min(max(buffer_size, 8192), 10485760)  # 8KB to 10MB
        
        logger.info(f"[BUFFERED OPS] Copying {source.name} with buffer size {buffer_size/1024:.0f}KB")
        
        file_size = source.stat().st_size
        result = {
            'source': str(source),
            'destination': str(dest),
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
                
            else:
                # Medium/Large files: stream with buffer
                bytes_copied = self._stream_copy(source, dest, buffer_size, file_size)
            
            # Preserve metadata
            shutil.copystat(source, dest)
            
            # Calculate destination hash if needed
            if calculate_hash:
                dest_hash = self._calculate_hash_streaming(dest, buffer_size)
                result['dest_hash'] = dest_hash
                result['verified'] = source_hash == dest_hash
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
            
            return result
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
            logger.error(f"Buffered copy failed for {source}: {e}")
            self.metrics.errors.append(f"{source.name}: {str(e)}")
            return result
    
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
        
        return bytes_copied
    
    def _calculate_hash_streaming(self, file_path: Path, buffer_size: int) -> str:
        """Calculate file hash with streaming read"""
        hash_obj = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(buffer_size)
                if not chunk:
                    break
                hash_obj.update(chunk)
                
                # Check cancellation
                if self.cancelled:
                    raise InterruptedError("Hash calculation cancelled")
        
        return hash_obj.hexdigest()
    
    def copy_files(self, files: List[Path], destination: Path,
                   calculate_hash: bool = True) -> Dict[str, Dict]:
        """
        Copy multiple files with buffering and detailed metrics
        
        Args:
            files: List of files to copy
            destination: Destination directory
            calculate_hash: Whether to calculate hashes
            
        Returns:
            Dict with results and performance metrics
        """
        # Initialize metrics
        self.metrics = PerformanceMetrics(
            start_time=time.time(),
            total_files=len(files),
            total_bytes=sum(f.stat().st_size for f in files if f.exists()),
            buffer_size_used=self.settings.copy_buffer_size * 1024,
            operation_type="buffered"
        )
        
        results = {}
        destination.mkdir(parents=True, exist_ok=True)
        
        for idx, file in enumerate(files):
            if self.cancelled:
                break
            
            if not file.exists():
                continue
            
            # Copy with buffering
            dest_file = destination / file.name
            result = self.copy_file_buffered(
                file, 
                dest_file,
                calculate_hash=calculate_hash
            )
            
            # Store result
            results[file.name] = result
            
            # Update metrics - only increment on success
            if result.get('success'):
                self.metrics.files_processed += 1
                # Also accumulate the bytes from this file
                if 'bytes_copied' in result:
                    self.metrics.bytes_copied += result['bytes_copied']
            
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
        
        # Add performance metrics to results
        results['_performance_metrics'] = {
            'total_files': self.metrics.total_files,
            'files_processed': self.metrics.files_processed,
            'total_bytes': self.metrics.total_bytes,
            'bytes_copied': self.metrics.bytes_copied,
            'duration': self.metrics.end_time - self.metrics.start_time,
            'average_speed_mbps': self.metrics.average_speed_mbps,
            'peak_speed_mbps': self.metrics.peak_speed_mbps,
            'buffer_size': self.metrics.buffer_size_used,
            'small_files': self.metrics.small_files_count,
            'medium_files': self.metrics.medium_files_count,
            'large_files': self.metrics.large_files_count,
            'errors': self.metrics.errors,
            'operation_type': 'buffered_streaming'
        }
        
        # Final progress report
        self._report_progress(
            100,
            f"Completed: {self.metrics.files_processed} files, "
            f"{self.metrics.bytes_copied/(1024*1024):.1f} MB @ "
            f"{self.metrics.average_speed_mbps:.1f} MB/s avg"
        )
        
        return results
    
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