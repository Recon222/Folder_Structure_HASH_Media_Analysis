#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File operation thread for asynchronous file copying with progress
"""

from pathlib import Path
from typing import List

from PySide6.QtCore import QThread, Signal

from core.file_ops import FileOperations


class FileOperationThread(QThread):
    """Thread for file operations with progress - bridges business logic to UI"""
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(bool, str, dict)  # success, message, results
    
    def __init__(self, files: List[Path], destination: Path, calculate_hash: bool = True):
        super().__init__()
        self.files = files
        self.destination = destination
        self.calculate_hash = calculate_hash
        self.file_ops = None
        
    def run(self):
        """Run file operations in thread"""
        try:
            # Create file operations with progress callback
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
            
    def cancel(self):
        """Cancel the operation"""
        if self.file_ops:
            self.file_ops.cancel()