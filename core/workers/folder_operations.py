#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Folder structure thread with unified error handling and Result objects

Nuclear migration complete - replaces old boolean/signal patterns with
modern Result-based error handling and comprehensive folder structure processing.
"""

import time
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from core.buffered_file_ops import BufferedFileOperations, PerformanceMetrics
from core.workers.base_worker import FileWorkerThread
from core.result_types import FileOperationResult, Result
from core.exceptions import FileOperationError, ValidationError, ErrorSeverity
from core.error_handler import handle_error


class FolderStructureThread(FileWorkerThread):
    """
    Thread for copying files while preserving complete directory hierarchies
    
    NUCLEAR MIGRATION COMPLETE:
    - OLD: finished = Signal(bool, str, dict)  ❌ REMOVED
    - OLD: progress = Signal(int)              ❌ REMOVED  
    - OLD: status = Signal(str)                ❌ REMOVED
    - NEW: result_ready = Signal(Result)       ✅ UNIFIED
    - NEW: progress_update = Signal(int, str)  ✅ UNIFIED
    """
    
    def __init__(self, items: List[Tuple], destination: Path, calculate_hash: bool = True,
                 performance_monitor: Optional['PerformanceMonitorDialog'] = None):
        """
        Initialize folder structure thread
        
        Args:
            items: List of (type, path, relative_path) tuples to copy
            destination: Destination directory
            calculate_hash: Whether to calculate and verify file hashes
            performance_monitor: Optional performance monitoring dialog
        """
        # Extract file paths for parent class initialization
        file_paths = []
        for item_type, path, relative in items:
            if item_type == 'file':
                file_paths.append(path)
            elif item_type == 'folder':
                # Add all files in folder
                try:
                    file_paths.extend([p for p in path.rglob('*') if p.is_file()])
                except Exception:
                    pass  # Handle access errors gracefully
        
        super().__init__(files=file_paths, destination=destination)
        
        self.items = items
        self.calculate_hash = calculate_hash
        self.performance_monitor = performance_monitor
        self.buffered_ops = None
        
        # Set descriptive operation name
        file_count = len(file_paths)
        folder_count = sum(1 for item_type, _, _ in items if item_type == 'folder')
        self.set_operation_name(f"Folder Structure ({file_count} files, {folder_count} folders)")
    
    def execute(self) -> Result:
        """
        Execute folder structure copying with comprehensive error handling
        
        Returns:
            FileOperationResult containing operation results and performance data
        """
        try:
            # Validate inputs
            validation_result = self._validate_inputs()
            if not validation_result.success:
                return validation_result
            
            # Check for cancellation before starting
            self.check_cancellation()
            
            # Analyze folder structure and collect files
            self.emit_progress(5, "Analyzing folder structure...")
            structure_analysis = self._analyze_folder_structure()
            
            if not structure_analysis['total_files'] and not structure_analysis['empty_dirs']:
                return FileOperationResult.create(
                    {},
                    files_processed=0,
                    bytes_processed=0
                ).add_metadata('analysis', structure_analysis)
            
            # Check for cancellation after analysis
            self.check_cancellation()
            
            # Execute folder structure copying
            return self._execute_structure_copy(structure_analysis)
            
        except ValidationError as e:
            self.handle_error(e, {'stage': 'validation'})
            return Result.error(e)
            
        except FileOperationError as e:
            self.handle_error(e, {'stage': 'folder_operation'})
            return Result.error(e)
            
        except PermissionError as e:
            error = FileOperationError(
                f"Permission denied during folder operation: {e}",
                user_message="Cannot access files or create directories. Please check permissions.",
                severity=ErrorSeverity.ERROR,
                recoverable=True
            )
            self.handle_error(error, {
                'stage': 'folder_operation',
                'error_type': 'permission',
                'items_count': len(self.items)
            })
            return Result.error(error)
            
        except OSError as e:
            error = FileOperationError(
                f"System error during folder operation: {e}",
                user_message="A system error occurred. Please check available disk space.",
                severity=ErrorSeverity.ERROR,
                recoverable=True
            )
            self.handle_error(error, {
                'stage': 'folder_operation',
                'error_type': 'system_error',
                'system_error_code': getattr(e, 'errno', None)
            })
            return Result.error(error)
            
        except Exception as e:
            error = FileOperationError(
                f"Unexpected error during folder operation: {str(e)}",
                user_message="An unexpected error occurred during folder copying.",
                severity=ErrorSeverity.CRITICAL
            )
            self.handle_error(error, {
                'stage': 'folder_operation',
                'error_type': 'unexpected',
                'exception_type': e.__class__.__name__,
                'severity': 'critical'
            })
            return Result.error(error)
    
    def _validate_inputs(self) -> Result:
        """
        Validate input parameters
        
        Returns:
            Result indicating validation success or failure
        """
        if not self.items:
            error = ValidationError(
                {'items': 'No items provided for folder structure operation'},
                user_message="No files or folders selected. Please select items to copy."
            )
            return Result.error(error)
        
        if not self.destination:
            error = ValidationError(
                {'destination': 'No destination provided'},
                user_message="No destination folder selected. Please choose where to copy the structure."
            )
            return Result.error(error)
        
        # Validate item structure
        invalid_items = []
        for i, item in enumerate(self.items):
            if not isinstance(item, tuple) or len(item) != 3:
                invalid_items.append(f"Item {i}: Invalid format")
            elif item[0] not in ['file', 'folder']:
                invalid_items.append(f"Item {i}: Invalid type '{item[0]}'")
            elif not isinstance(item[1], Path):
                invalid_items.append(f"Item {i}: Invalid path type")
        
        if invalid_items:
            error = ValidationError(
                {'items': f"Invalid item format: {'; '.join(invalid_items[:3])}"},
                user_message="Invalid folder structure data. Please refresh and try again."
            )
            return Result.error(error)
        
        return Result.success(None)
    
    def _analyze_folder_structure(self) -> Dict[str, Any]:
        """
        Analyze folder structure and collect files to copy
        
        Returns:
            Dictionary containing analysis results
        """
        total_files = []
        empty_dirs = set()
        analysis_errors = []
        total_size = 0
        
        self.emit_progress(10, "Scanning folder structure...")
        
        for item_type, path, relative in self.items:
            try:
                if item_type == 'file':
                    if path.exists() and path.is_file():
                        total_files.append((path, relative))
                        try:
                            total_size += path.stat().st_size
                        except:
                            pass  # Size is optional
                    else:
                        analysis_errors.append(f"File not found: {path}")
                        
                elif item_type == 'folder':
                    if not path.exists():
                        analysis_errors.append(f"Folder not found: {path}")
                        continue
                        
                    # Collect all items in folder recursively
                    try:
                        for item_path in path.rglob('*'):
                            relative_path = item_path.relative_to(path.parent)
                            
                            if item_path.is_file():
                                total_files.append((item_path, relative_path))
                                try:
                                    total_size += item_path.stat().st_size
                                except:
                                    pass
                            elif item_path.is_dir():
                                empty_dirs.add(relative_path)
                    except PermissionError as e:
                        analysis_errors.append(f"Permission denied scanning {path}: {e}")
                    except Exception as e:
                        analysis_errors.append(f"Error scanning {path}: {e}")
                        
            except Exception as e:
                analysis_errors.append(f"Error processing {item_type} {path}: {e}")
        
        return {
            'total_files': total_files,
            'empty_dirs': list(empty_dirs),
            'total_size': total_size,
            'analysis_errors': analysis_errors,
            'file_count': len(total_files),
            'dir_count': len(empty_dirs)
        }
    
    def _execute_structure_copy(self, analysis: Dict[str, Any]) -> FileOperationResult:
        """
        Execute the actual folder structure copying
        
        Args:
            analysis: Folder structure analysis results
            
        Returns:
            FileOperationResult with operation results
        """
        results = {}
        total_files = analysis['total_files']
        empty_dirs = analysis['empty_dirs']
        
        try:
            # Initialize buffered file operations
            self.buffered_ops = BufferedFileOperations(
                progress_callback=self._handle_progress_update,
                metrics_callback=self._handle_metrics_update,
                cancelled_check=lambda: self.is_cancelled()
            )
            
            # Create empty directories first
            directories_created = 0
            self.emit_progress(15, "Creating directory structure...")
            
            for dir_path in empty_dirs:
                if self.is_cancelled():
                    break
                    
                dest_dir = self.destination / dir_path
                
                # Security validation - prevent path traversal
                try:
                    dest_resolved = dest_dir.resolve()
                    base_resolved = self.destination.resolve()
                    if not str(dest_resolved).startswith(str(base_resolved)):
                        raise FileOperationError(
                            f"Security: Path traversal detected for {dir_path}",
                            user_message="Invalid folder path detected. Operation blocked for security."
                        )
                except FileOperationError:
                    raise  # Re-raise security errors
                except Exception as e:
                    self.handle_error(
                        FileOperationError(f"Path validation error: {e}"),
                        {'stage': 'security_validation', 'path': str(dir_path)}
                    )
                    continue
                
                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    directories_created += 1
                    
                    if directories_created % 10 == 0:  # Update progress every 10 directories
                        self.emit_progress(15 + int((directories_created / len(empty_dirs)) * 10), 
                                         f"Created {directories_created}/{len(empty_dirs)} directories")
                        
                except Exception as e:
                    error_msg = f"Failed to create directory {dir_path}: {e}"
                    self.handle_error(
                        FileOperationError(error_msg),
                        {'stage': 'directory_creation', 'directory': str(dir_path)}
                    )
                    # Continue with other directories
            
            self.check_cancellation()
            
            # Copy files with structure preservation
            if total_files:
                self.emit_progress(25, f"Copying {len(total_files)} files...")
                files_processed = 0
                
                for source_file, relative_path in total_files:
                    if self.is_cancelled():
                        break
                    
                    try:
                        # Create destination path preserving structure
                        dest_file = self.destination / relative_path
                        
                        # Security validation
                        try:
                            dest_resolved = dest_file.resolve()
                            base_resolved = self.destination.resolve()
                            if not str(dest_resolved).startswith(str(base_resolved)):
                                raise FileOperationError(
                                    f"Security: Path traversal detected for {relative_path}"
                                )
                        except FileOperationError:
                            raise
                        except Exception:
                            continue  # Skip files with path issues
                        
                        # Ensure parent directory exists
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Copy file with buffering
                        copy_result = self.buffered_ops.copy_file_buffered(
                            source_file,
                            dest_file,
                            calculate_hash=self.calculate_hash
                        )
                        
                        # Handle Result object from copy_file_buffered
                        if copy_result.success:
                            # Store successful results
                            copy_data = copy_result.value
                            results[str(relative_path)] = {
                                'source_path': str(source_file),
                                'dest_path': str(dest_file),
                                'source_hash': copy_data.get('source_hash', ''),
                                'dest_hash': copy_data.get('dest_hash', ''),
                                'verified': copy_data.get('verified', True),
                                'success': True
                            }
                            files_processed += 1
                        else:
                            # Store error results
                            results[str(relative_path)] = {
                                'source_path': str(source_file),
                                'dest_path': str(dest_file),
                                'source_hash': '',
                                'dest_hash': '',
                                'verified': False,
                                'success': False,
                                'error': str(copy_result.error)
                            }
                            # Log error but continue processing other files
                            error_details.append(f"{relative_path}: {copy_result.error}")
                            logger.warning(f"File copy failed for {relative_path}: {copy_result.error}")
                        
                        # Update progress
                        file_progress = int((files_processed / len(total_files)) * 60)  # 60% for files
                        total_progress = 25 + file_progress
                        self.emit_progress(total_progress, 
                                         f"Copied {files_processed}/{len(total_files)} files")
                        
                        # Update file progress tracking
                        self.update_file_progress(files_processed, source_file.name)
                        
                    except Exception as e:
                        self.handle_file_error(e, str(source_file), {
                            'relative_path': str(relative_path),
                            'stage': 'file_copy'
                        })
                        # Continue with other files
            else:
                files_processed = 0
            
            # Final progress update
            self.emit_progress(95, "Finalizing folder structure...")
            
            # Check for hash verification failures
            hash_failures = []
            if self.calculate_hash:
                for filename, file_result in results.items():
                    if isinstance(file_result, dict) and not file_result.get('verified', True):
                        hash_failures.append(filename)
            
            # Create result with comprehensive metadata
            self.emit_progress(100, f"Structure copy complete: {files_processed} files, {directories_created} directories")
            
            result = FileOperationResult.create(
                results,
                files_processed=files_processed,
                bytes_processed=analysis['total_size']
            )
            
            # Add comprehensive metadata
            result.add_metadata('directories_created', directories_created)
            result.add_metadata('total_directories', len(empty_dirs))
            result.add_metadata('analysis_errors', analysis['analysis_errors'])
            result.add_metadata('hash_failures', hash_failures)
            result.add_metadata('calculate_hash', self.calculate_hash)
            result.add_metadata('structure_type', 'folder_hierarchy')
            
            # Handle hash verification failures
            if hash_failures:
                from core.exceptions import HashVerificationError
                error = HashVerificationError(
                    f"Hash verification failed for {len(hash_failures)} files in folder structure",
                    user_message=f"Hash verification failed for {len(hash_failures)} files. Some files may be corrupted."
                )
                result.success = False
                result.error = error
                result.add_warning(f"Hash verification failed for {len(hash_failures)} files")
                
                self.handle_error(error, {
                    'stage': 'hash_verification',
                    'failed_files': hash_failures[:10],  # Limit context size
                    'total_failures': len(hash_failures)
                })
            
            return result
            
        except Exception as e:
            error = FileOperationError(
                f"Error during folder structure copy: {str(e)}",
                user_message="Error occurred while copying folder structure.",
                severity=ErrorSeverity.ERROR
            )
            self.handle_error(error, {'stage': 'structure_copy'})
            return FileOperationResult(success=False, error=error, value=results)
    
    def _handle_progress_update(self, percentage: int, message: str):
        """
        Handle progress updates from buffered file operations
        
        Args:
            percentage: Progress percentage from buffered operations
            message: Status message from buffered operations
        """
        # Adjust percentage to account for our overall progress stages
        # Buffered operations cover roughly 60% of our total progress (25% to 85%)
        adjusted_percentage = 25 + int((percentage / 100) * 60)
        adjusted_percentage = min(85, max(25, adjusted_percentage))  # Clamp to range
        
        self.emit_progress(adjusted_percentage, message)
    
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
        Cancel the folder structure operation
        
        Overrides base cancel to also cancel buffered operations.
        """
        super().cancel()
        
        if self.buffered_ops:
            try:
                self.buffered_ops.cancel()
            except Exception as e:
                # Don't let cancellation errors propagate
                handle_error(
                    FileOperationError(f"Error during operation cancellation: {e}"),
                    {'stage': 'cancellation', 'severity': 'warning'}
                )