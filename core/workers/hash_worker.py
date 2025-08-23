#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hash worker threads for async hash operations
"""

from pathlib import Path
from typing import List

from PySide6.QtCore import QThread, Signal

from core.hash_operations import HashOperations, HashResult, VerificationResult, HashOperationMetrics
from core.settings_manager import settings
from core.logger import logger


class SingleHashWorker(QThread):
    """Worker thread for single hash operations (hash files/folders)"""
    
    # Signals
    progress = Signal(int)  # Progress percentage
    status = Signal(str)   # Status message
    finished = Signal(bool, str, object)  # success, message, results
    
    def __init__(self, paths: List[Path], algorithm: str = None):
        """Initialize single hash worker
        
        Args:
            paths: List of file/folder paths to hash
            algorithm: Hash algorithm to use (defaults to settings)
        """
        super().__init__()
        self.paths = paths
        self.algorithm = algorithm or settings.hash_algorithm
        self.cancelled = False
        
    def run(self):
        """Execute the hash operation"""
        try:
            # Validate inputs
            if not self.paths:
                self.finished.emit(False, "No files or folders specified", None)
                return
                
            # Initialize hash operations
            hash_ops = HashOperations(self.algorithm)
            hash_ops.set_callbacks(
                progress_callback=self._on_progress,
                status_callback=self._on_status
            )
            
            # Set cancellation callback
            def check_cancellation():
                if self.cancelled:
                    hash_ops.cancel()
                    
            # Start operation
            self.status.emit(f"Starting {self.algorithm.upper()} hash calculation...")
            
            # Hash all files
            results, metrics = hash_ops.hash_multiple_files(self.paths)
            
            if self.cancelled:
                self.finished.emit(False, "Operation cancelled", None)
                return
            
            # Count successful results
            successful_files = len([r for r in results if r.success])
            total_files = len(results)
            failed_files = total_files - successful_files
            
            # Prepare result summary
            result_data = {
                'results': results,
                'metrics': metrics,
                'algorithm': self.algorithm,
                'summary': {
                    'total_files': total_files,
                    'successful_files': successful_files,
                    'failed_files': failed_files,
                    'total_size_mb': metrics.processed_bytes / (1024 * 1024),
                    'duration_seconds': metrics.duration,
                    'average_speed_mbps': metrics.average_speed_mbps
                }
            }
            
            # Create completion message
            if failed_files > 0:
                message = f"Hash calculation completed with {failed_files} errors. {successful_files}/{total_files} files processed successfully."
            else:
                message = f"Hash calculation completed successfully. {successful_files} files processed."
                
            # Add performance info
            if metrics.duration > 0:
                message += f" ({metrics.average_speed_mbps:.1f} MB/s avg)"
            
            self.finished.emit(True, message, result_data)
            
        except Exception as e:
            logger.error(f"Hash worker error: {e}", exc_info=True)
            self.finished.emit(False, f"Hash operation failed: {str(e)}", None)
    
    def _on_progress(self, percent: int, status_msg: str):
        """Handle progress updates from hash operations"""
        self.progress.emit(percent)
        
    def _on_status(self, status_msg: str):
        """Handle status updates from hash operations"""
        self.status.emit(status_msg)
        
    def cancel(self):
        """Cancel the operation"""
        self.cancelled = True


class VerificationWorker(QThread):
    """Worker thread for hash verification operations (compare two sets of files)"""
    
    # Signals
    progress = Signal(int)  # Progress percentage
    status = Signal(str)   # Status message
    finished = Signal(bool, str, object)  # success, message, results
    
    def __init__(self, source_paths: List[Path], target_paths: List[Path], algorithm: str = None):
        """Initialize verification worker
        
        Args:
            source_paths: Source file/folder paths to hash
            target_paths: Target file/folder paths to compare against
            algorithm: Hash algorithm to use (defaults to settings)
        """
        super().__init__()
        self.source_paths = source_paths
        self.target_paths = target_paths
        self.algorithm = algorithm or settings.hash_algorithm
        self.cancelled = False
        
    def run(self):
        """Execute the verification operation"""
        try:
            # Validate inputs
            if not self.source_paths:
                self.finished.emit(False, "No source files or folders specified", None)
                return
                
            if not self.target_paths:
                self.finished.emit(False, "No target files or folders specified", None)
                return
                
            # Initialize hash operations
            hash_ops = HashOperations(self.algorithm)
            hash_ops.set_callbacks(
                progress_callback=self._on_progress,
                status_callback=self._on_status
            )
            
            # Start verification
            self.status.emit(f"Starting {self.algorithm.upper()} hash verification...")
            
            # Perform verification
            verification_results, metrics = hash_ops.verify_hashes(self.source_paths, self.target_paths)
            
            if self.cancelled:
                self.finished.emit(False, "Operation cancelled", None)
                return
            
            # Analyze results
            total_comparisons = len(verification_results)
            matches = len([v for v in verification_results if v.match])
            mismatches = total_comparisons - matches
            
            # Count files with errors
            source_errors = len([v for v in verification_results if not v.source_result.success])
            target_errors = len([v for v in verification_results if v.target_result and not v.target_result.success])
            missing_targets = len([v for v in verification_results if v.target_result is None])
            
            # Prepare result summary
            result_data = {
                'verification_results': verification_results,
                'metrics': metrics,
                'algorithm': self.algorithm,
                'summary': {
                    'total_comparisons': total_comparisons,
                    'matches': matches,
                    'mismatches': mismatches,
                    'source_errors': source_errors,
                    'target_errors': target_errors,
                    'missing_targets': missing_targets,
                    'total_size_mb': metrics.processed_bytes / (1024 * 1024),
                    'duration_seconds': metrics.duration,
                    'average_speed_mbps': metrics.average_speed_mbps
                }
            }
            
            # Create completion message
            if mismatches > 0 or source_errors > 0 or target_errors > 0 or missing_targets > 0:
                error_details = []
                if mismatches > 0:
                    error_details.append(f"{mismatches} hash mismatches")
                if source_errors > 0:
                    error_details.append(f"{source_errors} source errors")
                if target_errors > 0:
                    error_details.append(f"{target_errors} target errors")
                if missing_targets > 0:
                    error_details.append(f"{missing_targets} missing targets")
                    
                message = f"Verification completed with issues: {', '.join(error_details)}. {matches}/{total_comparisons} files match."
            else:
                message = f"Verification completed successfully. All {matches} files match perfectly."
                
            # Add performance info
            if metrics.duration > 0:
                message += f" ({metrics.average_speed_mbps:.1f} MB/s avg)"
            
            self.finished.emit(True, message, result_data)
            
        except Exception as e:
            logger.error(f"Verification worker error: {e}", exc_info=True)
            self.finished.emit(False, f"Verification operation failed: {str(e)}", None)
    
    def _on_progress(self, percent: int, status_msg: str):
        """Handle progress updates from hash operations"""
        self.progress.emit(percent)
        
    def _on_status(self, status_msg: str):
        """Handle status updates from hash operations"""
        self.status.emit(status_msg)
        
    def cancel(self):
        """Cancel the operation"""
        self.cancelled = True