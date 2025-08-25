#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hash worker threads with unified error handling and Result objects

Nuclear migration complete - replaces old boolean/signal patterns with
modern Result-based error handling and unified signal system.
"""

from pathlib import Path
from typing import List, Optional

from core.hash_operations import HashOperations, HashResult, VerificationResult, HashOperationMetrics
from core.settings_manager import settings
from core.workers.base_worker import BaseWorkerThread
from core.result_types import HashOperationResult, Result
from core.exceptions import HashVerificationError, ValidationError, ConfigurationError, ErrorSeverity
from core.error_handler import handle_error


class SingleHashWorker(BaseWorkerThread):
    """
    Worker thread for single hash operations (hash files/folders)
    
    NUCLEAR MIGRATION COMPLETE:
    - OLD: finished = Signal(bool, str, object)  ❌ REMOVED
    - OLD: progress = Signal(int)                ❌ REMOVED  
    - OLD: status = Signal(str)                  ❌ REMOVED
    - NEW: result_ready = Signal(Result)         ✅ UNIFIED
    - NEW: progress_update = Signal(int, str)    ✅ UNIFIED
    """
    
    def __init__(self, paths: List[Path], algorithm: str = None):
        """Initialize single hash worker
        
        Args:
            paths: List of file/folder paths to hash
            algorithm: Hash algorithm to use (defaults to settings)
        """
        super().__init__()
        self.paths = paths
        self.algorithm = algorithm or settings.hash_algorithm
        self.hash_ops = None
        
        # Set descriptive operation name
        path_count = len(paths) if paths else 0
        self.set_operation_name(f"Hash Calculation ({path_count} items)")
    
    def execute(self) -> Result:
        """Execute hash calculation operation with comprehensive error handling
        
        Returns:
            HashOperationResult containing hash results and performance data
        """
        try:
            # Validate inputs
            validation_result = self._validate_inputs()
            if not validation_result.success:
                return validation_result
            
            # Check for cancellation before starting
            self.check_cancellation()
            
            # Initialize hash operations
            self.hash_ops = HashOperations(self.algorithm)
            self.hash_ops.set_callbacks(
                progress_callback=self._handle_progress_update,
                status_callback=self._handle_status_update
            )
            
            # Execute hash operation
            self.emit_progress(10, f"Starting {self.algorithm.upper()} hash calculation...")
            
            results, metrics = self.hash_ops.hash_multiple_files(self.paths)
            
            # Check for cancellation after operation
            self.check_cancellation()
            
            # Process and validate results
            return self._process_hash_results(results, metrics)
            
        except HashVerificationError as e:
            self.handle_error(e, {'stage': 'hash_calculation'})
            return Result.error(e)
            
        except ConfigurationError as e:
            self.handle_error(e, {'stage': 'hash_configuration', 'algorithm': self.algorithm})
            return Result.error(e)
            
        except PermissionError as e:
            error = HashVerificationError(
                f"Permission denied during hash calculation: {e}",
                user_message="Cannot access files for hashing. Please check permissions.",
                severity=ErrorSeverity.ERROR,
                recoverable=True
            )
            self.handle_error(error, {
                'stage': 'hash_calculation',
                'error_type': 'permission',
                'paths_attempted': len(self.paths)
            })
            return Result.error(error)
            
        except FileNotFoundError as e:
            error = HashVerificationError(
                f"File not found during hash calculation: {e}",
                user_message="One or more files could not be found for hashing.",
                severity=ErrorSeverity.ERROR,
                recoverable=True
            )
            self.handle_error(error, {
                'stage': 'hash_calculation',
                'error_type': 'file_not_found'
            })
            return Result.error(error)
            
        except Exception as e:
            error = HashVerificationError(
                f"Unexpected error during hash calculation: {str(e)}",
                user_message="An unexpected error occurred during hash calculation.",
                severity=ErrorSeverity.CRITICAL
            )
            self.handle_error(error, {
                'stage': 'hash_calculation',
                'error_type': 'unexpected',
                'exception_type': e.__class__.__name__,
                'severity': 'critical'
            })
            return Result.error(error)
    
    def _validate_inputs(self) -> Result:
        """Validate input parameters
        
        Returns:
            Result indicating validation success or failure
        """
        if not self.paths:
            error = ValidationError(
                {'paths': 'No files or folders provided for hashing'},
                user_message="No files selected. Please select files or folders to hash."
            )
            return Result.error(error)
        
        if not self.algorithm:
            error = ConfigurationError(
                "No hash algorithm specified",
                setting_key="hash_algorithm",
                user_message="Hash algorithm not configured. Please check settings."
            )
            return Result.error(error)
        
        # Validate paths exist
        missing_paths = []
        for path in self.paths:
            if not path.exists():
                missing_paths.append(str(path))
        
        if missing_paths:
            error = ValidationError(
                {'paths': f"Missing paths: {', '.join(missing_paths[:3])}{'...' if len(missing_paths) > 3 else ''}"},
                user_message=f"{len(missing_paths)} files or folders could not be found."
            )
            return Result.error(error)
        
        return Result.success(None)
    
    def _process_hash_results(self, results: List[HashResult], metrics: HashOperationMetrics) -> HashOperationResult:
        """Process hash operation results
        
        Args:
            results: Hash results from operations
            metrics: Performance metrics
            
        Returns:
            HashOperationResult with processed data
        """
        try:
            # Count results
            successful_files = len([r for r in results if r.success])
            total_files = len(results)
            failed_files = total_files - successful_files
            
            # Convert results to dictionary format for compatibility
            hash_dict = {}
            for result in results:
                hash_dict[str(result.file_path)] = {
                    'file_path': str(result.file_path),
                    'hash_value': result.hash_value if result.success else None,
                    'algorithm': self.algorithm,
                    'success': result.success,
                    'error': result.error_message if not result.success else None,
                    'file_size': result.file_size,
                    'duration': result.duration
                }
            
            # Handle failures
            if failed_files > 0:
                failed_paths = [str(r.file_path) for r in results if not r.success]
                error = HashVerificationError(
                    f"Hash calculation failed for {failed_files} files: {', '.join(failed_paths[:3])}{'...' if len(failed_paths) > 3 else ''}",
                    user_message=f"Hash calculation failed for {failed_files} out of {total_files} files.",
                    severity=ErrorSeverity.WARNING if successful_files > 0 else ErrorSeverity.ERROR
                )
                
                self.handle_error(error, {
                    'stage': 'hash_processing',
                    'failed_files': failed_paths[:10],  # Limit context size
                    'total_files': total_files,
                    'successful_files': successful_files
                })
                
                result = HashOperationResult(
                    success=successful_files > 0,  # Partial success if some files worked
                    error=error if successful_files == 0 else None,
                    value=hash_dict,
                    files_hashed=successful_files,
                    verification_failures=failed_files,
                    hash_algorithm=self.algorithm,
                    processing_time=metrics.duration
                )
                
                if successful_files > 0:
                    result.add_warning(f"Hash calculation failed for {failed_files} files")
                
                return result
            
            # All successful
            self.emit_progress(100, f"Successfully calculated hashes for {successful_files} files")
            
            result = HashOperationResult.create(
                hash_dict,
                hash_algorithm=self.algorithm
            )
            
            # Add operation metadata
            result.add_metadata('total_size_mb', metrics.processed_bytes / (1024 * 1024))
            result.add_metadata('average_speed_mbps', metrics.average_speed_mbps)
            result.add_metadata('algorithm', self.algorithm)
            result.add_metadata('source_paths', [str(p) for p in self.paths])
            
            return result
            
        except Exception as e:
            error = HashVerificationError(
                f"Failed to process hash results: {str(e)}",
                user_message="Error processing hash calculation results.",
                severity=ErrorSeverity.ERROR
            )
            self.handle_error(error, {'stage': 'result_processing'})
            return HashOperationResult(success=False, error=error, value={})
    
    def _handle_progress_update(self, percent: int, status_msg: str):
        """Handle progress updates from hash operations"""
        self.emit_progress(percent, status_msg)
    
    def _handle_status_update(self, status_msg: str):
        """Handle status updates from hash operations"""
        # Status is now included in progress updates - emit as progress with current percentage
        # We'll use a reasonable default percentage based on status
        percent = 50  # Default middle progress for status-only updates
        self.emit_progress(percent, status_msg)
    
    def cancel(self):
        """Cancel the hash operation"""
        super().cancel()
        
        if self.hash_ops:
            try:
                self.hash_ops.cancel()
            except Exception as e:
                handle_error(
                    HashVerificationError(f"Error during hash operation cancellation: {e}"),
                    {'stage': 'cancellation', 'severity': 'warning'}
                )


class VerificationWorker(BaseWorkerThread):
    """
    Worker thread for hash verification operations (compare two sets of files)
    
    NUCLEAR MIGRATION COMPLETE:
    - OLD: finished = Signal(bool, str, object)  ❌ REMOVED
    - OLD: progress = Signal(int)                ❌ REMOVED  
    - OLD: status = Signal(str)                  ❌ REMOVED
    - NEW: result_ready = Signal(Result)         ✅ UNIFIED
    - NEW: progress_update = Signal(int, str)    ✅ UNIFIED
    """
    
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
        self.hash_ops = None
        
        # Set descriptive operation name
        source_count = len(source_paths) if source_paths else 0
        target_count = len(target_paths) if target_paths else 0
        self.set_operation_name(f"Hash Verification ({source_count} vs {target_count} items)")
        
    def execute(self) -> Result:
        """Execute hash verification operation with comprehensive error handling
        
        Returns:
            HashOperationResult containing verification results and performance data
        """
        try:
            # Validate inputs
            validation_result = self._validate_verification_inputs()
            if not validation_result.success:
                return validation_result
            
            # Check for cancellation before starting
            self.check_cancellation()
            
            # Initialize hash operations
            self.hash_ops = HashOperations(self.algorithm)
            self.hash_ops.set_callbacks(
                progress_callback=self._handle_progress_update,
                status_callback=self._handle_status_update
            )
            
            # Execute verification operation
            self.emit_progress(10, f"Starting {self.algorithm.upper()} hash verification...")
            
            verification_results, metrics = self.hash_ops.verify_hashes(self.source_paths, self.target_paths)
            
            # Check for cancellation after operation
            self.check_cancellation()
            
            # Process and validate results
            return self._process_verification_results(verification_results, metrics)
            
        except HashVerificationError as e:
            self.handle_error(e, {'stage': 'hash_verification'})
            return Result.error(e)
            
        except ConfigurationError as e:
            self.handle_error(e, {'stage': 'verification_configuration', 'algorithm': self.algorithm})
            return Result.error(e)
            
        except PermissionError as e:
            error = HashVerificationError(
                f"Permission denied during hash verification: {e}",
                user_message="Cannot access files for verification. Please check permissions.",
                severity=ErrorSeverity.ERROR,
                recoverable=True
            )
            self.handle_error(error, {
                'stage': 'hash_verification',
                'error_type': 'permission',
                'source_paths': len(self.source_paths),
                'target_paths': len(self.target_paths)
            })
            return Result.error(error)
            
        except Exception as e:
            error = HashVerificationError(
                f"Unexpected error during hash verification: {str(e)}",
                user_message="An unexpected error occurred during hash verification.",
                severity=ErrorSeverity.CRITICAL
            )
            self.handle_error(error, {
                'stage': 'hash_verification',
                'error_type': 'unexpected',
                'exception_type': e.__class__.__name__,
                'severity': 'critical'
            })
            return Result.error(error)
    
    def _validate_verification_inputs(self) -> Result:
        """Validate verification input parameters
        
        Returns:
            Result indicating validation success or failure
        """
        if not self.source_paths:
            error = ValidationError(
                {'source_paths': 'No source files or folders provided'},
                user_message="No source files selected. Please select source files for verification."
            )
            return Result.error(error)
        
        if not self.target_paths:
            error = ValidationError(
                {'target_paths': 'No target files or folders provided'},
                user_message="No target files selected. Please select target files for verification."
            )
            return Result.error(error)
        
        if not self.algorithm:
            error = ConfigurationError(
                "No hash algorithm specified for verification",
                setting_key="hash_algorithm",
                user_message="Hash algorithm not configured. Please check settings."
            )
            return Result.error(error)
        
        return Result.success(None)
    
    def _process_verification_results(self, verification_results: List[VerificationResult], 
                                    metrics: HashOperationMetrics) -> HashOperationResult:
        """Process hash verification results
        
        Args:
            verification_results: Verification results from operations
            metrics: Performance metrics
            
        Returns:
            HashOperationResult with processed verification data
        """
        try:
            # Analyze results
            total_comparisons = len(verification_results)
            matches = len([v for v in verification_results if v.match])
            mismatches = total_comparisons - matches
            
            # Count files with errors
            source_errors = len([v for v in verification_results if not v.source_result.success])
            target_errors = len([v for v in verification_results if v.target_result and not v.target_result.success])
            missing_targets = len([v for v in verification_results if v.target_result is None])
            
            # Convert results to dictionary format
            verification_dict = {}
            for i, result in enumerate(verification_results):
                key = f"verification_{i}_{result.source_result.file_path.name}"
                verification_dict[key] = {
                    'source_path': str(result.source_result.file_path),
                    'target_path': str(result.target_result.file_path) if result.target_result else None,
                    'source_hash': result.source_result.hash_value if result.source_result.success else None,
                    'target_hash': result.target_result.hash_value if result.target_result and result.target_result.success else None,
                    'match': result.match,
                    'algorithm': self.algorithm,
                    'source_success': result.source_result.success,
                    'target_success': result.target_result.success if result.target_result else False,
                    'source_error': result.source_result.error_message if not result.source_result.success else None,
                    'target_error': result.target_result.error_message if result.target_result and not result.target_result.success else None
                }
            
            # Determine overall success and create appropriate error if needed
            total_errors = source_errors + target_errors + missing_targets + mismatches
            overall_success = total_errors == 0
            
            if not overall_success:
                error_details = []
                if mismatches > 0:
                    error_details.append(f"{mismatches} hash mismatches")
                if source_errors > 0:
                    error_details.append(f"{source_errors} source errors")
                if target_errors > 0:
                    error_details.append(f"{target_errors} target errors")
                if missing_targets > 0:
                    error_details.append(f"{missing_targets} missing targets")
                
                severity = ErrorSeverity.CRITICAL if matches == 0 else (
                    ErrorSeverity.ERROR if mismatches > matches else ErrorSeverity.WARNING
                )
                
                error = HashVerificationError(
                    f"Hash verification completed with issues: {', '.join(error_details)}",
                    user_message=f"Verification found issues: {', '.join(error_details)}. {matches}/{total_comparisons} files match.",
                    severity=severity
                )
                
                self.handle_error(error, {
                    'stage': 'verification_analysis',
                    'matches': matches,
                    'mismatches': mismatches,
                    'source_errors': source_errors,
                    'target_errors': target_errors,
                    'missing_targets': missing_targets
                })
                
                result = HashOperationResult(
                    success=matches > 0,  # Partial success if some files matched
                    error=error if matches == 0 else None,
                    value=verification_dict,
                    files_hashed=total_comparisons,
                    verification_failures=total_errors,
                    hash_algorithm=self.algorithm,
                    processing_time=metrics.duration
                )
                
                if matches > 0:
                    result.add_warning(f"Verification issues found: {', '.join(error_details)}")
                
                return result
            
            # All successful
            self.emit_progress(100, f"Verification completed successfully. All {matches} files match perfectly.")
            
            result = HashOperationResult.create(
                verification_dict,
                hash_algorithm=self.algorithm
            )
            
            # Add verification metadata
            result.add_metadata('verification_type', 'hash_comparison')
            result.add_metadata('total_comparisons', total_comparisons)
            result.add_metadata('matches', matches)
            result.add_metadata('total_size_mb', metrics.processed_bytes / (1024 * 1024))
            result.add_metadata('average_speed_mbps', metrics.average_speed_mbps)
            result.add_metadata('source_count', len(self.source_paths))
            result.add_metadata('target_count', len(self.target_paths))
            
            return result
            
        except Exception as e:
            error = HashVerificationError(
                f"Failed to process verification results: {str(e)}",
                user_message="Error processing hash verification results.",
                severity=ErrorSeverity.ERROR
            )
            self.handle_error(error, {'stage': 'verification_result_processing'})
            return HashOperationResult(success=False, error=error, value={})
    
    def _handle_progress_update(self, percent: int, status_msg: str):
        """Handle progress updates from hash operations"""
        self.emit_progress(percent, status_msg)
    
    def _handle_status_update(self, status_msg: str):
        """Handle status updates from hash operations"""
        # Status is now included in progress updates
        percent = 50  # Default middle progress for status-only updates
        self.emit_progress(percent, status_msg)
    
    def cancel(self):
        """Cancel the verification operation"""
        super().cancel()
        
        if self.hash_ops:
            try:
                self.hash_ops.cancel()
            except Exception as e:
                handle_error(
                    HashVerificationError(f"Error during verification cancellation: {e}"),
                    {'stage': 'cancellation', 'severity': 'warning'}
                )