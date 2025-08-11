#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File operation thread for asynchronous file copying with progress
"""

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QThread, Signal

from core.file_ops import FileOperations
from core.buffered_file_ops import BufferedFileOperations, PerformanceMetrics
from core.settings_manager import SettingsManager


class FileOperationThread(QThread):
    """Thread for file operations with progress - bridges business logic to UI"""
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(bool, str, dict)  # success, message, results
    metrics_updated = Signal(PerformanceMetrics)  # For performance monitoring
    
    def __init__(self, files: List[Path], destination: Path, calculate_hash: bool = True,
                 performance_monitor: Optional['PerformanceMonitorDialog'] = None):
        super().__init__()
        self.files = files
        self.destination = destination
        self.calculate_hash = calculate_hash
        self.file_ops = None
        self.performance_monitor = performance_monitor
        self.settings = SettingsManager()
        
    def run(self):
        """Run file operations in thread"""
        try:
            # Check if we should use buffered operations
            if self.settings.use_buffered_operations:
                # Use high-performance buffered operations
                self.file_ops = BufferedFileOperations(
                    progress_callback=lambda pct, msg: (
                        self.progress.emit(pct),
                        self.status.emit(msg)
                    ),
                    metrics_callback=self._handle_metrics_update
                )
                
                # Hook up to performance monitor if available
                if self.performance_monitor:
                    self.file_ops.metrics_callback = lambda m: (
                        self.performance_monitor.set_metrics_source(m),
                        self.metrics_updated.emit(m)
                    )
                
                # Copy files with buffering
                results = self.file_ops.copy_files(
                    self.files, 
                    self.destination, 
                    self.calculate_hash
                )
            else:
                # Use legacy file operations
                self.file_ops = FileOperations(
                    progress_callback=lambda pct, msg: (
                        self.progress.emit(pct),
                        self.status.emit(msg)
                    )
                )
                
                # Copy files
                results = self.file_ops.copy_files(
                    self.files, 
                    self.destination, 
                    self.calculate_hash
                )
            
            # Check if all files were verified
            if self.calculate_hash:
                all_verified = all(r['verified'] for r in results.values())
                if not all_verified:
                    self.finished.emit(False, "Some files failed hash verification!", results)
                    return
                    
            self.finished.emit(True, f"Successfully copied {len(results)} files", results)
            
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}", {})
    
    def _handle_metrics_update(self, metrics: PerformanceMetrics):
        """Handle metrics updates from buffered operations"""
        self.metrics_updated.emit(metrics)
        if self.performance_monitor:
            self.performance_monitor.set_metrics_source(metrics)
            
    def cancel(self):
        """Cancel the operation"""
        if self.file_ops:
            self.file_ops.cancel()