#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File operation thread with unified error handling and Result objects

Nuclear migration complete - replaces old boolean/signal patterns with
modern Result-based error handling and unified signal system.
"""

from pathlib import Path
from typing import List, Optional

from core.buffered_file_ops import BufferedFileOperations, PerformanceMetrics
from core.workers.base_worker import FileWorkerThread
from core.result_types import FileOperationResult, Result
from core.exceptions import FileOperationError, HashVerificationError, ErrorSeverity
from core.error_handler import handle_error


class FileOperationThread(FileWorkerThread):
    """
    Thread for file operations with unified error handling
    
    NUCLEAR MIGRATION COMPLETE:
    - OLD: finished = Signal(bool, str, dict)  ❌ REMOVED
    - OLD: progress = Signal(int)              ❌ REMOVED  
    - OLD: status = Signal(str)                ❌ REMOVED
    - NEW: result_ready = Signal(Result)       ✅ UNIFIED
    - NEW: progress_update = Signal(int, str)  ✅ UNIFIED
    """
    
    def __init__(self, files: List[Path], destination: Path, calculate_hash: bool = True,
                 performance_monitor: Optional['PerformanceMonitorDialog'] = None):
        """
        Initialize file operation thread
        
        Args:
            files: List of files to copy
            destination: Destination directory
            calculate_hash: Whether to calculate and verify hashes
            performance_monitor: Optional performance monitoring dialog
        """
        super().__init__(files=files, destination=destination)
        
        self.calculate_hash = calculate_hash
        self.performance_monitor = performance_monitor
        self.file_ops = None
        
        # Set descriptive operation name
        file_count = len(files) if files else 0
        self.set_operation_name(f"File Copy ({file_count} files)")
    
    def execute(self) -> Result:
        """
        Execute file copying operation with comprehensive error handling
        
        Returns:
            FileOperationResult containing operation results and performance data
        """
        try:
            # Initialize buffered file operations with progress callbacks
            self.file_ops = BufferedFileOperations(
                progress_callback=self._handle_progress_update,
                metrics_callback=self._handle_metrics_update,
                cancelled_check=lambda: self.is_cancelled()
            )
            
            # Check for cancellation before starting
            self.check_cancellation()
            
            # Validate inputs
            if not self.files:
                error = FileOperationError(
                    "No files provided for copying operation",
                    user_message="No files selected. Please select files to copy."
                )
                self.handle_error(error, {'validation': 'empty_files_list'})
                return Result.error(error)
            
            if not self.destination:
                error = FileOperationError(
                    "No destination provided for copying operation",
                    user_message="No destination folder selected. Please choose where to copy files."
                )
                self.handle_error(error, {'validation': 'no_destination'})
                return Result.error(error)
            
            # Execute file copying operation
            self.emit_progress(10, "Starting file copy operation...")
            
            file_op_result = self.file_ops.copy_files(
                self.files,
                self.destination, 
                self.calculate_hash
            )
            
            # Check for cancellation after operation
            self.check_cancellation()
            
            # Handle FileOperationResult from copy_files
            if not file_op_result.success:
                # Return the error result directly
                return file_op_result
            
            # Process and validate results (raw_results is now file_op_result.value)
            return self._process_file_results(file_op_result.value, file_op_result)
            
        except FileOperationError as e:
            # Already an FSAError - just handle it
            self.handle_error(e, {'stage': 'file_operation'})
            return Result.error(e)
            
        except PermissionError as e:
            error = FileOperationError(
                f"Permission denied during file operation: {e}",
                user_message="Cannot access files or destination. Please check permissions and try again.",
                severity=ErrorSeverity.ERROR,
                recoverable=True
            )
            self.handle_error(error, {
                'stage': 'file_operation',
                'error_type': 'permission',
                'files_attempted': len(self.files)
            })
            return Result.error(error)
            
        except FileNotFoundError as e:
            error = FileOperationError(
                f"File not found during operation: {e}",
                user_message="One or more files could not be found. They may have been moved or deleted.",
                severity=ErrorSeverity.ERROR,
                recoverable=True
            )
            self.handle_error(error, {
                'stage': 'file_operation', 
                'error_type': 'file_not_found'
            })
            return Result.error(error)
            
        except OSError as e:
            error = FileOperationError(
                f"System error during file operation: {e}",
                user_message="A system error occurred. Please check available disk space and try again.",
                severity=ErrorSeverity.ERROR,
                recoverable=True
            )
            self.handle_error(error, {
                'stage': 'file_operation',
                'error_type': 'system_error',
                'system_error_code': getattr(e, 'errno', None)
            })
            return Result.error(error)
            
        except Exception as e:
            # Convert unexpected exceptions to FileOperationError
            error = FileOperationError(
                f"Unexpected error during file operation: {str(e)}",
                user_message="An unexpected error occurred during file copying. Please try again.",
                severity=ErrorSeverity.CRITICAL
            )
            self.handle_error(error, {
                'stage': 'file_operation',
                'error_type': 'unexpected',
                'exception_type': e.__class__.__name__,
                'severity': 'critical'
            })
            return Result.error(error)
    
    def _process_file_results(self, raw_results: dict, base_result: FileOperationResult) -> FileOperationResult:
        """
        Process raw file operation results and handle hash verification
        
        Args:
            raw_results: Raw results dictionary from FileOperationResult.value
            base_result: Base FileOperationResult with metrics and performance data
            
        Returns:
            FileOperationResult with processed data and validation
        """
        try:
            # Count successful files
            successful_files = 0
            total_bytes = 0
            hash_failures = []
            
            for filename, file_result in raw_results.items():
                if filename == '_performance_stats':
                    continue
                    
                if isinstance(file_result, dict):
                    if 'dest_path' in file_result:
                        successful_files += 1
                        
                    # Check hash verification if enabled
                    if self.calculate_hash and 'verified' in file_result:
                        if not file_result['verified']:
                            hash_failures.append(filename)
                            
                        # Try to get file size for byte count
                        try:
                            if 'source_path' in file_result:
                                source_path = Path(file_result['source_path'])
                                if source_path.exists():
                                    total_bytes += source_path.stat().st_size
                        except:
                            pass  # File size is optional
            
            # Handle hash verification failures
            if hash_failures:
                error = HashVerificationError(
                    f"Hash verification failed for {len(hash_failures)} files: {', '.join(hash_failures[:3])}{'...' if len(hash_failures) > 3 else ''}",
                    user_message=f"Hash verification failed for {len(hash_failures)} files. File integrity may be compromised.",
                    severity=ErrorSeverity.CRITICAL
                )
                
                self.handle_error(error, {
                    'stage': 'hash_verification',
                    'failed_files': hash_failures,
                    'total_files': len(self.files),
                    'successful_files': successful_files
                })
                
                # Return error result with preserved base metrics
                return FileOperationResult(
                    success=False,
                    error=error,
                    value=raw_results,
                    files_processed=base_result.files_processed,
                    bytes_processed=base_result.bytes_processed,
                    performance_metrics=base_result.performance_metrics
                )
            
            # Create successful result
            self.emit_progress(100, f"Successfully copied {base_result.files_processed} files")
            
            # Return the base_result since it already has all the correct information
            result = base_result
            
            # Add operation metadata
            result.add_metadata('calculate_hash', self.calculate_hash)
            result.add_metadata('destination', str(self.destination))
            result.add_metadata('source_files', len(self.files))
            
            return result
            
        except Exception as e:
            error = FileOperationError(
                f"Failed to process file operation results: {str(e)}",
                user_message="Error processing file operation results.",
                severity=ErrorSeverity.ERROR
            )
            self.handle_error(error, {'stage': 'result_processing'})
            return FileOperationResult(success=False, error=error, value=raw_results or {})
    
    def _handle_progress_update(self, percentage: int, message: str):
        """
        Handle progress updates from buffered file operations
        
        Args:
            percentage: Progress percentage (0-100)
            message: Status message
        """
        # Use unified progress signal
        self.emit_progress(percentage, message)
        
        # Update file progress tracking
        if hasattr(self, 'files') and self.files:
            # Try to extract current file info from message for better tracking
            current_file = ""
            if "Copying" in message and len(self.files) > 0:
                # Try to parse current file from message
                parts = message.split("Copying")
                if len(parts) > 1:
                    current_file = parts[1].strip().split()[0] if parts[1].strip() else ""
            
            # Estimate files completed based on percentage
            estimated_files_done = int((percentage / 100) * len(self.files))
            self.update_file_progress(estimated_files_done, current_file)
    
    def _handle_metrics_update(self, metrics: PerformanceMetrics):
        """
        Handle performance metrics updates
        
        Args:
            metrics: Performance metrics from buffered operations
        """
        # Forward to performance monitor if available
        if self.performance_monitor:
            try:
                self.performance_monitor.set_metrics_source(metrics)
            except Exception as e:
                # Don't let performance monitoring errors break the operation
                handle_error(
                    FileOperationError(f"Performance monitor error: {e}"),
                    {'stage': 'performance_monitoring', 'severity': 'warning'}
                )
    
    def cancel(self):
        """
        Cancel the file operation
        
        Overrides base cancel to also cancel buffered file operations.
        """
        super().cancel()
        
        if self.file_ops:
            try:
                self.file_ops.cancel()
            except Exception as e:
                # Don't let cancellation errors propagate
                handle_error(
                    FileOperationError(f"Error during operation cancellation: {e}"),
                    {'stage': 'cancellation', 'severity': 'warning'}
                )