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
                    {'stage': 'cancellation'}
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
                'exception_type': e.__class__.__name__
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
            # Analyze results - FIXED: Separate actual hash mismatches from missing files
            total_comparisons = len(verification_results)
            matches = len([v for v in verification_results if v.match])
            # CRITICAL FIX: Only count actual hash mismatches, not missing files
            hash_mismatches = len([v for v in verification_results 
                                 if v.target_result is not None and v.source_result is not None 
                                 and not v.match])
            
            # Count files with errors - BIDIRECTIONAL SUPPORT
            source_errors = len([v for v in verification_results if v.source_result and not v.source_result.success])
            target_errors = len([v for v in verification_results if v.target_result and not v.target_result.success])
            missing_targets = len([v for v in verification_results if v.comparison_type == "missing_target"])
            missing_sources = len([v for v in verification_results if v.comparison_type == "missing_source"])
            
            # Convert results to dictionary format - BIDIRECTIONAL: Include missing files for CSV export
            verification_dict = {}
            for i, result in enumerate(verification_results):
                # Handle both missing targets and missing sources for key generation
                if result.source_result:
                    key = f"verification_{i}_{result.source_result.file_path.name}"
                else:
                    # Missing source - use target file name
                    key = f"verification_{i}_{result.target_result.file_path.name}"
                
                # BIDIRECTIONAL FIX: Handle all three cases
                if result.comparison_type == "missing_target":
                    # Missing target file - source exists, no target
                    verification_dict[key] = {
                        'source_path': str(result.source_result.file_path),
                        'target_path': 'MISSING',  # Clear indicator for CSV
                        'source_relative_path': str(result.source_result.relative_path),
                        'target_relative_path': 'MISSING',
                        'source_hash': result.source_result.hash_value if result.source_result.success else None,
                        'target_hash': 'MISSING',  # Clear indicator
                        'match': False,  # Missing files never match
                        'algorithm': self.algorithm,
                        'source_success': result.source_result.success,
                        'target_success': False,  # Missing = not successful
                        'source_error': result.source_result.error_message if not result.source_result.success else None,
                        'target_error': 'File not found in target location',
                        'comparison_type': result.comparison_type,
                        'verification_status': 'MISSING_TARGET'
                    }
                elif result.comparison_type == "missing_source":
                    # Missing source file - target exists, no source
                    verification_dict[key] = {
                        'source_path': 'MISSING',  # Clear indicator for CSV
                        'target_path': str(result.target_result.file_path),
                        'source_relative_path': 'MISSING',
                        'target_relative_path': str(result.target_result.relative_path),
                        'source_hash': 'MISSING',  # Clear indicator
                        'target_hash': result.target_result.hash_value if result.target_result.success else None,
                        'match': False,  # Missing files never match
                        'algorithm': self.algorithm,
                        'source_success': False,  # Missing = not successful
                        'target_success': result.target_result.success,
                        'source_error': 'File not found in source location',
                        'target_error': result.target_result.error_message if not result.target_result.success else None,
                        'comparison_type': result.comparison_type,
                        'verification_status': 'MISSING_SOURCE'
                    }
                else:
                    # Normal comparison (file exists in both locations) 
                    verification_dict[key] = {
                        'source_path': str(result.source_result.file_path),
                        'target_path': str(result.target_result.file_path),
                        'source_relative_path': str(result.source_result.relative_path),
                        'target_relative_path': str(result.target_result.relative_path),
                        'source_hash': result.source_result.hash_value if result.source_result.success else None,
                        'target_hash': result.target_result.hash_value if result.target_result.success else None,
                        'match': result.match,
                        'algorithm': self.algorithm,
                        'source_success': result.source_result.success,
                        'target_success': result.target_result.success,
                        'source_error': result.source_result.error_message if not result.source_result.success else None,
                        'target_error': result.target_result.error_message if not result.target_result.success else None,
                        'comparison_type': result.comparison_type,
                        'verification_status': 'MATCH' if result.match else 'MISMATCH'
                    }
            
            # Determine overall success and create appropriate error if needed - BIDIRECTIONAL
            total_errors = source_errors + target_errors + missing_targets + missing_sources + hash_mismatches
            overall_success = total_errors == 0
            
            # CRITICAL FIX: Missing files should always be treated as verification failures
            # This ensures they trigger the error system and are reported properly
            verification_failed = not overall_success
            
            if verification_failed:
                error_details = []
                # Prioritize missing files first - these are the most critical
                if missing_targets > 0:
                    error_details.append(f"{missing_targets} missing target files")
                if missing_sources > 0:
                    error_details.append(f"{missing_sources} missing source files")
                if hash_mismatches > 0:
                    error_details.append(f"{hash_mismatches} hash mismatches")
                if source_errors > 0:
                    error_details.append(f"{source_errors} source file errors")
                if target_errors > 0:
                    error_details.append(f"{target_errors} target file errors")
                
                # Emit detailed progress message showing the issues
                issues_summary = ', '.join(error_details)
                if matches > 0:
                    self.emit_progress(100, f"Verification failed: {matches} files match, but found {issues_summary}")
                else:
                    self.emit_progress(100, f"Verification failed: No files match. Issues: {issues_summary}")
                
                # Determine severity: missing files are serious verification failures
                if missing_targets > 0 or missing_sources > 0 or hash_mismatches > 0:
                    severity = ErrorSeverity.ERROR if matches > 0 else ErrorSeverity.CRITICAL
                else:
                    severity = ErrorSeverity.WARNING  # Only file access errors
                
                # Create detailed verification failure message
                detailed_message = self._create_detailed_verification_message(
                    verification_results, matches, total_comparisons, error_details
                )
                
                error = HashVerificationError(
                    f"Hash verification failed: {', '.join(error_details)}",
                    user_message=detailed_message
                )
                
                self.handle_error(error, {
                    'stage': 'verification_analysis',
                    'total_verification_entries': total_comparisons,
                    'successful_matches': matches,
                    'missing_targets': missing_targets,
                    'missing_sources': missing_sources,  # NEW: Track missing sources
                    'hash_mismatches': hash_mismatches,
                    'source_errors': source_errors,
                    'target_errors': target_errors,
                    'total_verification_failures': total_errors
                })
                
                result = HashOperationResult(
                    success=False,  # CRITICAL: Any missing files or mismatches = verification failure
                    error=error,
                    value=verification_dict,
                    files_hashed=total_comparisons,
                    verification_failures=total_errors,
                    hash_algorithm=self.algorithm,
                    processing_time=metrics.duration
                )
                
                # Add specific warnings for partial success scenarios
                if matches > 0:
                    result.add_warning(f"Partial verification: {matches} files matched, but {total_errors} issues found")
                
                return result
            
            # All successful - only reached if no missing files or mismatches
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
    
    def _create_detailed_verification_message(self, verification_results, matches: int, total_comparisons: int, error_details: list) -> str:
        """Create detailed user-friendly verification message with file-specific information"""
        
        # Count different types of issues - BIDIRECTIONAL SUPPORT
        missing_target_files = [v for v in verification_results if v.comparison_type == "missing_target"]
        missing_source_files = [v for v in verification_results if v.comparison_type == "missing_source"]
        mismatched_files = [v for v in verification_results if not v.match and v.target_result is not None and v.source_result is not None]
        error_files = [v for v in verification_results if (v.source_result and not v.source_result.success) or (v.target_result and not v.target_result.success)]
        
        # Start with clear bidirectional summary
        total_missing = len(missing_target_files) + len(missing_source_files)
        message_parts = [
            f"Hash Verification Failed - {matches}/{total_comparisons} verification entries processed successfully, but {total_missing} files are missing."
        ]
        
        # Add critical issues summary prioritizing missing files
        if error_details:
            message_parts.append(f"\n\n❌ VERIFICATION FAILURES:")
            for detail in error_details:
                message_parts.append(f"\n• {detail}")
        
        # PRIORITY 1: Missing target files (source files without targets)
        if missing_target_files:
            message_parts.append(f"\n\n📂 MISSING TARGET FILES ({len(missing_target_files)}):")
            message_parts.append("The following source files have no corresponding target files:")
            
            for i, result in enumerate(missing_target_files[:5], 1):  # Show first 5
                relative_path = str(result.source_result.relative_path)
                message_parts.append(f"\n{i}. {relative_path}")
                
            if len(missing_target_files) > 5:
                remaining = len(missing_target_files) - 5
                message_parts.append(f"\n   ... and {remaining} more missing target files")
        
        # PRIORITY 1B: Missing source files (target files without sources) - NEW!
        if missing_source_files:
            message_parts.append(f"\n\n📁 MISSING SOURCE FILES ({len(missing_source_files)}):")
            message_parts.append("The following target files have no corresponding source files:")
            
            for i, result in enumerate(missing_source_files[:5], 1):  # Show first 5
                relative_path = str(result.target_result.relative_path)
                message_parts.append(f"\n{i}. {relative_path}")
                
            if len(missing_source_files) > 5:
                remaining = len(missing_source_files) - 5
                message_parts.append(f"\n   ... and {remaining} more missing source files")
        
        # PRIORITY 2: Hash mismatches
        if mismatched_files:
            message_parts.append(f"\n\n🔍 HASH MISMATCHES ({len(mismatched_files)}):")
            message_parts.append("Files exist in both locations but have different content:")
            
            for i, result in enumerate(mismatched_files[:3], 1):  # Limit to first 3 for readability
                source_hash = result.source_result.hash_value if result.source_result.success else "ERROR"
                target_hash = result.target_result.hash_value if result.target_result.success else "ERROR"
                
                message_parts.append(f"\n{i}. File: {result.source_result.relative_path.name}")
                message_parts.append(f"   Source: {source_hash[:16]}...")
                message_parts.append(f"   Target: {target_hash[:16]}...")
                
            if len(mismatched_files) > 3:
                remaining = len(mismatched_files) - 3
                message_parts.append(f"\n   ... and {remaining} more mismatched files")
        
        # PRIORITY 3: File access errors
        if error_files:
            message_parts.append(f"\n\n⚠️ FILE ACCESS ERRORS ({len(error_files)}):")
            for i, result in enumerate(error_files[:3], 1):  # Limit to first 3
                file_name = result.source_result.relative_path.name
                if not result.source_result.success:
                    message_parts.append(f"\n{i}. {file_name} (source error: {result.source_result.error_message})")
                elif result.target_result and not result.target_result.success:
                    message_parts.append(f"\n{i}. {file_name} (target error: {result.target_result.error_message})")
                    
            if len(error_files) > 3:
                remaining = len(error_files) - 3
                message_parts.append(f"\n   ... and {remaining} more files with access errors")
        
        # Add actionable bidirectional recommendations
        message_parts.append("\n\n💡 RECOMMENDED ACTIONS:")
        
        if missing_target_files:
            message_parts.append(f"\n• Check if {len(missing_target_files)} source files were properly copied to target")
            message_parts.append("• Verify target folder structure matches source structure")
        
        if missing_source_files:
            message_parts.append(f"\n• Investigate {len(missing_source_files)} extra files in target that don't exist in source")
            message_parts.append("• Determine if extra target files should be removed or if source is incomplete")
        
        if mismatched_files:
            message_parts.append(f"\n• Investigate why {len(mismatched_files)} files have different content")
            message_parts.append("• Consider re-copying files that don't match")
        
        message_parts.append("\n• Export CSV report for complete file-by-file analysis")
        message_parts.append("• Review file paths and permissions")
        
        return "".join(message_parts)
    
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
                    {'stage': 'cancellation'}
                )