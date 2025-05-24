#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Folder structure thread for copying files while preserving directory hierarchies
"""

import shutil
import hashlib
from pathlib import Path
from typing import List, Tuple

from PySide6.QtCore import QThread, Signal


class FolderStructureThread(QThread):
    """Thread for copying files and preserving folder structures"""
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(bool, str, dict)  # success, message, results
    
    def __init__(self, items: List[Tuple], destination: Path, calculate_hash: bool = True):
        super().__init__()
        self.items = items  # List of (type, path, relative_path) tuples
        self.destination = destination
        self.calculate_hash = calculate_hash
        self.cancelled = False
        
    def run(self):
        """Copy files and folders preserving structure"""
        try:
            results = {}
            total_files = []
            
            # First, collect all files to process
            for item_type, path, relative in self.items:
                if item_type == 'file':
                    total_files.append((path, relative))
                elif item_type == 'folder':
                    # Get all files in folder recursively
                    for file_path in path.rglob('*'):
                        if file_path.is_file():
                            # Preserve the folder structure
                            relative_path = file_path.relative_to(path.parent)
                            total_files.append((file_path, relative_path))
            
            if not total_files:
                self.finished.emit(True, "No files to copy", {})
                return
                
            # Calculate total size for progress
            total_size = sum(f[0].stat().st_size for f in total_files if f[0].exists())
            copied_size = 0
            
            # Copy each file preserving structure
            for source_file, relative_path in total_files:
                if self.cancelled:
                    self.finished.emit(False, "Operation cancelled", results)
                    return
                    
                try:
                    # Create destination path preserving folder structure
                    dest_file = self.destination / relative_path
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