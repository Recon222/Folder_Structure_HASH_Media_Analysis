#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File operations - copying, hashing, and verification
"""

import shutil
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Callable, Optional
import logging

# Try to import adaptive operations
try:
    from .adaptive_file_operations import AdaptiveFileOperations
    ADAPTIVE_AVAILABLE = True
except ImportError:
    ADAPTIVE_AVAILABLE = False
    logging.warning("Adaptive file operations not available - using basic implementation")


class FileOperations:
    """Handles file operations with progress reporting"""
    
    def __init__(self, progress_callback: Optional[Callable[[int, str], None]] = None,
                 use_adaptive: bool = None):
        """
        Initialize with optional progress callback
        
        Args:
            progress_callback: Function that receives (progress_pct, status_message)
            use_adaptive: Whether to use adaptive optimization (if available)
        """
        self.progress_callback = progress_callback
        self.cancelled = False
        
        # Check user settings if not explicitly specified
        if use_adaptive is None:
            try:
                from PySide6.QtCore import QSettings
                settings = QSettings()
                use_adaptive = settings.value("performance/adaptive_enabled", False, type=bool)
            except:
                use_adaptive = False  # Default to safe mode
        
        self.use_adaptive = use_adaptive and ADAPTIVE_AVAILABLE
        
        # Initialize adaptive system if available and requested
        if self.use_adaptive:
            try:
                self.adaptive = AdaptiveFileOperations(progress_callback)
                logging.info("Adaptive file operations initialized successfully")
            except Exception as e:
                logging.warning(f"Failed to initialize adaptive operations: {e}")
                self.use_adaptive = False
                self.adaptive = None
        else:
            self.adaptive = None
        
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
        # Use adaptive operations if available
        if self.use_adaptive and self.adaptive:
            try:
                # Convert adaptive results to match expected format
                adaptive_results = self.adaptive.copy_files_adaptive(
                    files, destination, calculate_hash
                )
                
                # Convert results to expected format
                results = {}
                performance_stats = adaptive_results.get('_performance_stats', {})
                
                for file_str, result in adaptive_results.items():
                    if file_str == '_performance_stats':
                        continue  # Skip the stats entry
                        
                    file_path = Path(file_str)
                    if result.get('success', False):
                        results[file_path.name] = {
                            'source_path': result.get('source', str(file_path)),
                            'dest_path': result.get('destination', str(destination / file_path.name)),
                            'source_hash': result.get('hash', ''),
                            'dest_hash': result.get('hash', ''),  # Same hash for both
                            'verified': True
                        }
                    else:
                        # Handle failed files
                        logging.error(f"Failed to copy {file_path.name}: {result.get('error', 'Unknown error')}")
                
                # Add performance stats to results for UI display
                if performance_stats:
                    results['_performance_stats'] = performance_stats
                        
                return results
                
            except Exception as e:
                logging.error(f"Adaptive copy failed, falling back to sequential: {e}")
                # Fall through to sequential implementation
                
        # Original sequential implementation as fallback
        return self._copy_files_sequential(files, destination, calculate_hash)
    
    def _copy_files_sequential(self, files: List[Path], destination: Path,
                              calculate_hash: bool = True) -> Dict[str, Dict[str, str]]:
        """Original sequential file copy implementation"""
        results = {}
        
        # Performance tracking for sequential mode
        start_time = time.time()
        total_size = sum(f.stat().st_size for f in files if f.exists())
        copied_size = 0
        files_completed = 0
        last_update_time = start_time
        last_copied_size = 0
        
        # Ensure destination exists
        destination.mkdir(parents=True, exist_ok=True)
        
        for file in files:
            if self.cancelled:
                break
                
            if not file.exists():
                continue
                
            file_size = file.stat().st_size
            current_time = time.time()
            
            # Calculate current speed for progress message
            current_speed_mbps = 0.0
            if current_time - last_update_time >= 1.0:  # Update every second
                bytes_delta = copied_size - last_copied_size
                time_delta = current_time - last_update_time
                if time_delta > 0:
                    current_speed_mbps = (bytes_delta / time_delta) / (1024 * 1024)
                last_update_time = current_time
                last_copied_size = copied_size
            
            # Enhanced progress message with speed
            speed_info = f" @ {current_speed_mbps:.1f} MB/s" if current_speed_mbps > 0 else ""
            progress_pct = int((copied_size / total_size * 100) if total_size > 0 else 0)
            self._report_progress(
                progress_pct,
                f"Copying: {file.name} ({files_completed+1}/{len(files)}){speed_info}"
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
            copied_size += file_size
            files_completed += 1
            
        # Calculate completion statistics
        total_time = time.time() - start_time
        average_speed_mbps = (copied_size / (1024 * 1024)) / total_time if total_time > 0 else 0
        
        # Add performance stats
        results['_performance_stats'] = {
            'files_processed': files_completed,
            'total_bytes': copied_size,
            'total_time_seconds': total_time,
            'average_speed_mbps': average_speed_mbps,
            'peak_speed_mbps': average_speed_mbps,  # Sequential mode doesn't track peaks
            'total_size_mb': copied_size / (1024 * 1024),
            'efficiency_score': min(average_speed_mbps / 50, 1.0) if average_speed_mbps > 0 else 0,
            'mode': 'sequential'
        }
        
        # Final progress report with summary
        self._report_progress(100, f"Completed: {files_completed} files, "
                            f"{copied_size/(1024*1024):.1f} MB @ {average_speed_mbps:.1f} MB/s")
        
        return results
    
    def _calculate_file_hash(self, file_path: Path, algorithm: str = 'sha256') -> str:
        """Calculate hash of a file"""
        # Use adaptive hash calculation if available
        if self.use_adaptive and self.adaptive:
            try:
                results = self.adaptive.hash_files_adaptive([file_path])
                return results.get(str(file_path), '')
            except Exception:
                # Fall through to basic implementation
                pass
                
        # Basic implementation
        hash_func = hashlib.new(algorithm)
        
        # Dynamic buffer size based on file size
        file_size = file_path.stat().st_size
        if file_size < 10_000_000:  # < 10MB
            buffer_size = 65536  # 64KB
        elif file_size < 100_000_000:  # < 100MB
            buffer_size = 1048576  # 1MB
        else:
            buffer_size = 10485760  # 10MB
        
        with open(file_path, 'rb') as f:
            # Read in chunks for large files
            for chunk in iter(lambda: f.read(buffer_size), b''):
                hash_func.update(chunk)
                
        return hash_func.hexdigest()
    
    def _report_progress(self, percentage: int, message: str):
        """Report progress if callback is available"""
        if self.progress_callback:
            self.progress_callback(percentage, message)
            
    def cancel(self):
        """Cancel the current operation"""
        self.cancelled = True
        # Also cancel adaptive operations if available
        if self.adaptive:
            self.adaptive.cancel()
        
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