#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File operations - copying, hashing, and verification
"""

import shutil
import hashlib
from pathlib import Path
from typing import List, Dict, Callable, Optional


class FileOperations:
    """Handles file operations with progress reporting"""
    
    def __init__(self, progress_callback: Optional[Callable[[int, str], None]] = None):
        """
        Initialize with optional progress callback
        
        Args:
            progress_callback: Function that receives (progress_pct, status_message)
        """
        self.progress_callback = progress_callback
        self.cancelled = False
        
    def copy_files(self, files: List[Path], destination: Path, 
                   calculate_hash: bool = True) -> Dict[str, Dict[str, str]]:
        """
        Copy files to destination with optional hash calculation
        
        Args:
            files: List of files to copy
            destination: Destination directory
            calculate_hash: Whether to calculate SHA-256 hashes
            
        Returns:
            Dict mapping filenames to their source and destination hashes
        """
        results = {}
        
        # Calculate total size for progress
        total_size = sum(f.stat().st_size for f in files if f.exists())
        copied_size = 0
        
        # Ensure destination exists
        destination.mkdir(parents=True, exist_ok=True)
        
        for file in files:
            if self.cancelled:
                break
                
            if not file.exists():
                continue
                
            # Report status
            self._report_progress(
                int((copied_size / total_size * 100) if total_size > 0 else 0),
                f"Copying: {file.name}"
            )
            
            # Calculate source hash if requested
            source_hash = ""
            if calculate_hash:
                source_hash = self._calculate_file_hash(file)
                
            # Copy file
            dest_file = destination / file.name
            shutil.copy2(file, dest_file)
            
            # Calculate destination hash if requested
            dest_hash = ""
            if calculate_hash:
                dest_hash = self._calculate_file_hash(dest_file)
                
            # Store results
            results[file.name] = {
                'source_path': str(file),
                'dest_path': str(dest_file),
                'source_hash': source_hash,
                'dest_hash': dest_hash,
                'verified': source_hash == dest_hash if calculate_hash else True
            }
            
            # Update progress
            copied_size += file.stat().st_size
            
        # Final progress report
        self._report_progress(100, f"Completed: {len(results)} files copied")
        
        return results
    
    def _calculate_file_hash(self, file_path: Path, algorithm: str = 'sha256') -> str:
        """Calculate hash of a file"""
        hash_func = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            # Read in chunks for large files
            for chunk in iter(lambda: f.read(8192), b''):
                hash_func.update(chunk)
                
        return hash_func.hexdigest()
    
    def _report_progress(self, percentage: int, message: str):
        """Report progress if callback is available"""
        if self.progress_callback:
            self.progress_callback(percentage, message)
            
    def cancel(self):
        """Cancel the current operation"""
        self.cancelled = True
        
    def verify_hashes(self, file_results: Dict[str, Dict[str, str]]) -> Dict[str, bool]:
        """
        Verify that source and destination hashes match
        
        Args:
            file_results: Results from copy_files operation
            
        Returns:
            Dict mapping filenames to verification status
        """
        verification_results = {}
        
        for filename, data in file_results.items():
            if data['source_hash'] and data['dest_hash']:
                verification_results[filename] = data['source_hash'] == data['dest_hash']
            else:
                verification_results[filename] = True  # No hash to verify
                
        return verification_results
    
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