#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Folder structure thread for copying files while preserving directory hierarchies
"""

import shutil
import hashlib
import time
from pathlib import Path
from typing import List, Tuple, Optional

from PySide6.QtCore import QThread, Signal

from core.settings_manager import SettingsManager
from core.buffered_file_ops import BufferedFileOperations, PerformanceMetrics


class FolderStructureThread(QThread):
    """Thread for copying files and preserving folder structures"""
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(bool, str, dict)  # success, message, results
    metrics_updated = Signal(PerformanceMetrics)  # For performance monitoring
    
    def __init__(self, items: List[Tuple], destination: Path, calculate_hash: bool = True,
                 performance_monitor: Optional['PerformanceMonitorDialog'] = None):
        super().__init__()
        self.items = items  # List of (type, path, relative_path) tuples
        self.destination = destination
        self.calculate_hash = calculate_hash
        self.cancelled = False
        self.performance_monitor = performance_monitor
        self.settings = SettingsManager()
        
    def run(self):
        """Copy files and folders preserving structure"""
        try:
            results = {}
            total_files = []
            
            # First, collect all files and directories to process
            empty_dirs = []  # Track empty directories separately
            for item_type, path, relative in self.items:
                if item_type == 'file':
                    total_files.append((path, relative))
                elif item_type == 'folder':
                    # Get all items in folder recursively
                    for item_path in path.rglob('*'):
                        relative_path = item_path.relative_to(path.parent)
                        if item_path.is_file():
                            # Add files to be copied
                            total_files.append((item_path, relative_path))
                        elif item_path.is_dir():
                            # Track directories to ensure they're created (including empty ones)
                            empty_dirs.append(relative_path)
            
            if not total_files:
                self.finished.emit(True, "No files to copy", {})
                return
                
            # Calculate total size for progress
            total_size = sum(f[0].stat().st_size for f in total_files if f[0].exists())
            copied_size = 0
            
            # Check if we should use buffered operations
            if self.settings.use_buffered_operations:
                # Use high-performance buffered operations
                self.status.emit("[HIGH-PERFORMANCE MODE] Using buffered file operations")
                self._copy_with_buffering(total_files, total_size, results, empty_dirs)
                return  # _copy_with_buffering handles the finished signal
            else:
                # Legacy method - copy each file preserving structure
                # First create empty directories
                if empty_dirs:
                    for dir_path in empty_dirs:
                        dest_dir = self.destination / dir_path
                        try:
                            dest_dir.mkdir(parents=True, exist_ok=True)
                        except Exception as e:
                            self.status.emit(f"Failed to create directory {dir_path}: {e}")
                
                for source_file, relative_path in total_files:
                    if self.cancelled:
                        self.finished.emit(False, "Operation cancelled", results)
                        return
                    
                    try:
                        # Create destination path preserving folder structure
                        dest_file = self.destination / relative_path
                        
                        # SECURITY: Validate destination stays within bounds
                        try:
                            dest_resolved = dest_file.resolve()
                            base_resolved = self.destination.resolve()
                            if not str(dest_resolved).startswith(str(base_resolved)):
                                raise ValueError(f"Security: Path traversal detected for {relative_path}")
                        except Exception as e:
                            self.status.emit(f"Security error: {str(e)}")
                            continue
                        
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Emit status
                        self.status.emit(f"Copying: {relative_path}")
                        
                        # Calculate hash if requested
                        source_hash = ""
                        if self.calculate_hash:
                            source_hash = self._calculate_file_hash(source_file)
                        
                        # Copy file
                        shutil.copy2(source_file, dest_file)
                        
                        # Calculate destination hash
                        dest_hash = ""
                        if self.calculate_hash:
                            dest_hash = self._calculate_file_hash(dest_file)
                        
                        # Store results
                        results[str(relative_path)] = {
                            'source_path': str(source_file),
                            'dest_path': str(dest_file),
                            'source_hash': source_hash,
                            'dest_hash': dest_hash,
                            'verified': source_hash == dest_hash if self.calculate_hash else True
                        }
                        
                        # Update progress
                        copied_size += source_file.stat().st_size
                        progress_pct = int((copied_size / total_size * 100) if total_size > 0 else 100)
                        self.progress.emit(progress_pct)
                        
                    except Exception as e:
                        self.status.emit(f"Error copying {source_file.name}: {str(e)}")
                    
            self.finished.emit(True, f"Successfully copied {len(results)} files", results)
            
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}", {})
            
    def _copy_with_buffering(self, total_files: List[Tuple], total_size: int, results: dict, empty_dirs: List[Path] = None):
        """Copy files using high-performance buffered operations"""
        # Create empty directories first and track them
        directories_created = 0
        total_directories = len(empty_dirs) if empty_dirs else 0
        
        if empty_dirs:
            for dir_path in empty_dirs:
                dest_dir = self.destination / dir_path
                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    directories_created += 1
                    self.status.emit(f"Created directory: {dir_path}")
                except Exception as e:
                    self.status.emit(f"Failed to create directory {dir_path}: {e}")
        
        # Create buffered file operations with callbacks
        buffered_ops = BufferedFileOperations(
            progress_callback=lambda pct, msg: (
                self.progress.emit(pct),
                self.status.emit(msg)
            ),
            metrics_callback=self._handle_metrics_update
        )
        
        # Initialize metrics with total file count, size, and directory info
        buffered_ops.metrics.total_files = len(total_files)
        buffered_ops.metrics.total_bytes = total_size
        buffered_ops.metrics.total_directories = total_directories
        buffered_ops.metrics.directories_created = directories_created
        buffered_ops.metrics.start_time = time.time()
        
        # Hook up to performance monitor if available
        if self.performance_monitor:
            self.performance_monitor.set_metrics_source(buffered_ops.get_metrics())
        
        # Copy each file with buffering
        for idx, (source_file, relative_path) in enumerate(total_files):
            if self.cancelled:
                buffered_ops.cancel()
                self.finished.emit(False, "Operation cancelled", results)
                return
            
            try:
                # Create destination path preserving folder structure
                dest_file = self.destination / relative_path
                
                # SECURITY: Validate destination stays within bounds
                try:
                    dest_resolved = dest_file.resolve()
                    base_resolved = self.destination.resolve()
                    if not str(dest_resolved).startswith(str(base_resolved)):
                        raise ValueError(f"Security: Path traversal detected for {relative_path}")
                except Exception as e:
                    self.status.emit(f"Security error: {str(e)}")
                    continue
                
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Use buffered copy
                copy_result = buffered_ops.copy_file_buffered(
                    source_file,
                    dest_file,
                    calculate_hash=self.calculate_hash
                )
                
                # Store results
                results[str(relative_path)] = {
                    'source_path': str(source_file),
                    'dest_path': str(dest_file),
                    'source_hash': copy_result.get('source_hash', ''),
                    'dest_hash': copy_result.get('dest_hash', ''),
                    'verified': copy_result.get('verified', True)
                }
                
                # Update file count in metrics if successful
                # Note: copy_file_buffered doesn't increment files_processed when called individually
                # So we need to do it here
                if copy_result.get('success'):
                    buffered_ops.metrics.files_processed += 1
                    
                # Emit overall progress based on files processed
                progress_pct = int((buffered_ops.metrics.files_processed / len(total_files) * 100)) if len(total_files) > 0 else 0
                self.progress.emit(progress_pct)
                # Include directory info in status if we have directories
                if buffered_ops.metrics.total_directories > 0:
                    self.status.emit(f"Files: {buffered_ops.metrics.files_processed}/{len(total_files)}, Folders: {buffered_ops.metrics.directories_created}/{buffered_ops.metrics.total_directories}")
                else:
                    self.status.emit(f"Files copied: {buffered_ops.metrics.files_processed}/{len(total_files)}")
                
            except Exception as e:
                self.status.emit(f"Error copying {source_file.name}: {str(e)}")
                buffered_ops.metrics.errors.append(str(e))
        
        # Set final metrics
        buffered_ops.metrics.end_time = time.time()
        buffered_ops.metrics.calculate_summary()
        
        # Get final metrics for reporting
        final_metrics = buffered_ops.get_metrics()
        
        # Emit final metrics update
        if self.performance_monitor:
            self.performance_monitor.set_metrics_source(final_metrics)
        
        # Emit final status with complete counts
        final_msg = f"Successfully copied {buffered_ops.metrics.files_processed}/{buffered_ops.metrics.total_files} files"
        if buffered_ops.metrics.total_directories > 0:
            final_msg += f" and created {buffered_ops.metrics.directories_created}/{buffered_ops.metrics.total_directories} folders"
        self.finished.emit(True, final_msg, results)
    
    def _handle_metrics_update(self, metrics: PerformanceMetrics):
        """Handle metrics updates from buffered operations"""
        self.metrics_updated.emit(metrics)
        if self.performance_monitor:
            self.performance_monitor.set_metrics_source(metrics)
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
        
    def cancel(self):
        """Cancel the operation"""
        self.cancelled = True