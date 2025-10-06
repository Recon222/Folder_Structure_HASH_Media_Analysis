#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Folder structure thread with unified error handling and Result objects

Nuclear migration complete - replaces old boolean/signal patterns with
modern Result-based error handling and comprehensive folder structure processing.
"""

import time
import shutil
import logging
import os
import ctypes
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
                 performance_monitor: Optional['PerformanceMonitorDialog'] = None,
                 is_same_drive: Optional[bool] = None):
        """
        Initialize folder structure thread

        Args:
            items: List of (type, path, relative_path) tuples to copy
            destination: Destination directory
            calculate_hash: Whether to calculate and verify file hashes
            performance_monitor: Optional performance monitoring dialog
            is_same_drive: Pre-calculated same-drive detection result (None=not checked, True=same, False=different)
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
        self.is_same_drive = is_same_drive  # Store same-drive detection result

        # Initialize logger
        self.logger = logging.getLogger(__name__)

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
            self.check_pause()
            
            # Analyze folder structure and collect files
            self.emit_progress(5, "Analyzing folder structure...")
            structure_analysis = self._analyze_folder_structure()

            # Check if there's anything to process (files, empty dirs, OR folder items for same-drive move)
            if not structure_analysis['total_files'] and not structure_analysis['empty_dirs'] and not structure_analysis['folder_items']:
                self.logger.info("Nothing to process - no files, directories, or folders found")
                return FileOperationResult.create(
                    {},
                    files_processed=0,
                    bytes_processed=0
                ).add_metadata('analysis', structure_analysis).add_metadata('base_forensic_path', str(self.destination))
            
            # Check for cancellation and pause after analysis
            self.check_cancellation()
            self.check_pause()
            
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
        folder_items = []  # Keep folders intact for same-drive moves
        empty_dirs = set()
        analysis_errors = []
        total_size = 0

        self.emit_progress(10, "Scanning folder structure...")

        # DEBUG: Log analysis start state
        self.logger.info(f"=== ANALYSIS START ===")
        self.logger.info(f"Total items to process: {len(self.items)}")
        self.logger.info(f"is_same_drive flag: {self.is_same_drive}")
        self.logger.info(f"Destination: {self.destination}")

        for item_type, path, relative in self.items:
            # DEBUG: Log each item being processed
            self.logger.info(f"Processing item: type={item_type}, path={path}, relative={relative}")
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
                    # DEBUG: Log folder processing
                    self.logger.info(f">>> FOLDER ITEM DETECTED <<<")
                    self.logger.info(f"  Path exists: {path.exists()}")
                    self.logger.info(f"  Path value: {path}")

                    if not path.exists():
                        self.logger.error(f"  FOLDER NOT FOUND: {path}")
                        analysis_errors.append(f"Folder not found: {path}")
                        continue

                    # Use pre-calculated same-drive flag from ForensicTab
                    # This was determined when destination was set using the base destination path
                    # No runtime detection needed - just use the flag!
                    self.logger.info(f"  Checking is_same_drive: {self.is_same_drive}")

                    if self.is_same_drive:
                        # Keep as folder item for instant move
                        self.logger.info(f"  ✓ SAME DRIVE - Adding to folder_items for instant move")
                        self.logger.info(f"  folder_items before append: {len(folder_items)}")

                        folder_items.append(('folder', path, relative))

                        self.logger.info(f"  folder_items after append: {len(folder_items)}")
                        self.logger.info(f"  Added: ('folder', {path}, {relative})")

                        # Still calculate size for progress
                        try:
                            file_count = 0
                            for item_path in path.rglob('*'):
                                if item_path.is_file():
                                    file_count += 1
                                    try:
                                        total_size += item_path.stat().st_size
                                    except:
                                        pass
                            self.logger.info(f"  Scanned {file_count} files in folder for size calculation")
                        except Exception as e:
                            self.logger.error(f"  Error calculating folder size: {e}")
                    else:
                        # Different drives - explode into files for copy
                        self.logger.info(f"  ✗ DIFFERENT DRIVES - Exploding folder into files")
                        try:
                            file_count = 0
                            for item_path in path.rglob('*'):
                                relative_path = item_path.relative_to(path.parent)

                                if item_path.is_file():
                                    total_files.append((item_path, relative_path))
                                    file_count += 1
                                    try:
                                        total_size += item_path.stat().st_size
                                    except:
                                        pass
                                elif item_path.is_dir():
                                    empty_dirs.add(relative_path)
                            self.logger.info(f"  Exploded into {file_count} individual files")
                        except PermissionError as e:
                            self.logger.error(f"  Permission denied scanning {path}: {e}")
                            analysis_errors.append(f"Permission denied scanning {path}: {e}")
                        except Exception as e:
                            self.logger.error(f"  Error scanning {path}: {e}")
                            analysis_errors.append(f"Error scanning {path}: {e}")

            except Exception as e:
                self.logger.error(f"Exception processing item: {e}")
                analysis_errors.append(f"Error processing {item_type} {path}: {e}")

        # DEBUG: Log analysis results
        self.logger.info(f"=== ANALYSIS COMPLETE ===")
        self.logger.info(f"Total files: {len(total_files)}")
        self.logger.info(f"Folder items (for instant move): {len(folder_items)}")
        self.logger.info(f"Empty dirs: {len(empty_dirs)}")
        self.logger.info(f"Analysis errors: {len(analysis_errors)}")
        if analysis_errors:
            for error in analysis_errors:
                self.logger.error(f"  - {error}")

        return {
            'total_files': total_files,
            'folder_items': folder_items,  # New: intact folders for same-drive moves
            'empty_dirs': list(empty_dirs),
            'total_size': total_size,
            'analysis_errors': analysis_errors,
            'file_count': len(total_files),
            'dir_count': len(empty_dirs),
            'folder_count': len(folder_items)
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
        folder_items = analysis['folder_items']  # Get intact folders for same-drive moves
        empty_dirs = analysis['empty_dirs']

        # DEBUG: Log execution phase start
        self.logger.info(f"=== EXECUTION PHASE START ===")
        self.logger.info(f"Received from analysis:")
        self.logger.info(f"  total_files: {len(total_files)}")
        self.logger.info(f"  folder_items: {len(folder_items)}")
        self.logger.info(f"  empty_dirs: {len(empty_dirs)}")

        try:
            # Initialize buffered file operations
            self.buffered_ops = BufferedFileOperations(
                progress_callback=self._handle_progress_update,
                metrics_callback=self._handle_metrics_update,
                cancelled_check=lambda: self.is_cancelled(),
                pause_check=lambda: self.check_pause()
            )
            
            # Create empty directories first
            directories_created = 0
            self.emit_progress(15, "Creating directory structure...")
            
            for dir_path in empty_dirs:
                if self.is_cancelled():
                    break
                self.check_pause()
                    
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
                    # Create directory (Python's mkdir handles long paths automatically on Windows 10+)
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

            # Process whole folders first (instant same-drive moves!)
            if folder_items:
                self.logger.info(f"Same-drive optimization active: Moving {len(folder_items)} folders instantly")
                self.emit_progress(20, f"Moving {len(folder_items)} folders (instant)...")

                for folder_type, source_folder, relative in folder_items:
                    try:
                        # Calculate destination folder path
                        if relative:
                            # Use full relative path to preserve structure
                            dest_folder = self.destination / relative
                        else:
                            # For same-drive instant move: rename source TO destination
                            # The destination IS the final folder, don't append source name
                            dest_folder = self.destination

                        # With LongPathsEnabled=1, no \\?\ prefix needed - Windows handles it automatically
                        # shutil.move() uses os.rename() internally for same-drive, handles folders correctly

                        # DEBUG: Detailed path logging
                        self.logger.info(f"=== FOLDER MOVE DEBUG ===")
                        self.logger.info(f"  Source folder: {source_folder}")
                        self.logger.info(f"  Source exists: {source_folder.exists()}")
                        self.logger.info(f"  Dest folder: {dest_folder}")
                        self.logger.info(f"  Dest exists: {dest_folder.exists()}")
                        self.logger.info(f"  Dest parent: {dest_folder.parent}")
                        self.logger.info(f"  Dest parent exists: {dest_folder.parent.exists()}")

                        # Check if destination already exists
                        if dest_folder.exists():
                            self.logger.error(f"  DESTINATION ALREADY EXISTS: {dest_folder}")
                            self.logger.error(f"  This will cause os.rename() to fail!")

                        # Perform instant folder move using Win32 MoveFileEx API
                        # This bypasses Python's shutil.move() quirks and uses Windows directly
                        # MoveFileEx performs instant metadata-only moves on same filesystem
                        # With LongPathsEnabled=1, it handles long paths perfectly

                        # CRITICAL: Use Win32 MoveFileW API directly
                        # os.rename() fails moving to different parent dirs on Windows
                        # shutil.move() silently falls back to copying when os.rename() fails
                        # Solution: Call MoveFileW directly via ctypes for instant same-drive moves

                        # Ensure parent directory exists
                        if not dest_folder.parent.exists():
                            dest_folder.parent.mkdir(parents=True, exist_ok=True)
                            self.logger.info(f"  Created parent directory: {dest_folder.parent}")

                        # Use Win32 MoveFileExW with MOVEFILE_COPY_ALLOWED flag
                        # This allows the move to succeed even if it requires copying
                        self.logger.info(f"  Calling Win32 MoveFileExW API...")

                        # Windows API call
                        if os.name == 'nt':
                            # MoveFileExW flags
                            MOVEFILE_REPLACE_EXISTING = 0x1
                            MOVEFILE_COPY_ALLOWED = 0x2
                            MOVEFILE_WRITE_THROUGH = 0x8

                            kernel32 = ctypes.windll.kernel32

                            # Try 1: Standard move (instant if possible)
                            self.logger.info(f"    Attempt 1: Standard move (should be instant on same drive)...")
                            result = kernel32.MoveFileExW(
                                str(source_folder),
                                str(dest_folder),
                                MOVEFILE_WRITE_THROUGH
                            )

                            if result:
                                self.logger.info(f"✓ Instant move succeeded!")
                            else:
                                error_code = kernel32.GetLastError()
                                self.logger.error(f"    Move failed with error: {error_code}")

                                if error_code == 5:  # ERROR_ACCESS_DENIED
                                    self.logger.info(f"    Error 5 = ACCESS_DENIED")
                                    self.logger.info(f"    Possible causes:")
                                    self.logger.info(f"      - Open file handles in source directory")
                                    self.logger.info(f"      - NTFS permission conflicts")
                                    self.logger.info(f"      - Windows Search/antivirus locking files")
                                    self.logger.info(f"    Attempt 2: Try with MOVEFILE_COPY_ALLOWED flag...")

                                    # Try 2: Allow copy as fallback
                                    result = kernel32.MoveFileExW(
                                        str(source_folder),
                                        str(dest_folder),
                                        MOVEFILE_COPY_ALLOWED | MOVEFILE_WRITE_THROUGH
                                    )

                                    if result:
                                        self.logger.info(f"✓ Move succeeded with COPY_ALLOWED (may have copied)")
                                    else:
                                        error_code2 = kernel32.GetLastError()
                                        self.logger.error(f"    Still failed with error: {error_code2}")
                                        self.logger.info(f"  Final fallback to shutil.move()...")
                                        shutil.move(str(source_folder), str(dest_folder))
                                        self.logger.info(f"✓ Move completed via shutil (copied)")
                                else:
                                    self.logger.info(f"  Falling back to shutil.move()...")
                                    shutil.move(str(source_folder), str(dest_folder))
                                    self.logger.info(f"✓ Move completed (copied)")
                        else:
                            # Non-Windows: use shutil.move()
                            shutil.move(str(source_folder), str(dest_folder))
                            self.logger.info(f"✓ Move completed")

                    except Exception as e:
                        self.logger.error(f"Folder move failed for {source_folder}: {e}")
                        self.handle_error(
                            FileOperationError(f"Folder move failed: {e}"),
                            {'stage': 'folder_move', 'folder': str(source_folder)}
                        )
            else:
                # No folders for instant move - either different drives or no folders selected
                if self.is_same_drive is False:
                    self.logger.info("Different drives detected - files will be copied individually")
                else:
                    self.logger.info("No folders for same-drive move optimization")

            # Process individual files with structure preservation using intelligent move/copy
            if total_files:
                self.emit_progress(25, f"Processing {len(total_files)} files...")

                # Build items list for move_files_preserving_structure
                # Format: List[(type, path, relative_path)]
                items_for_processing = []
                for source_file, relative_path in total_files:
                    # Security validation before adding to items
                    try:
                        dest_file = self.destination / relative_path
                        dest_resolved = dest_file.resolve()
                        base_resolved = self.destination.resolve()
                        if not str(dest_resolved).startswith(str(base_resolved)):
                            self.handle_error(
                                FileOperationError(f"Security: Path traversal detected for {relative_path}"),
                                {'stage': 'security_validation', 'path': str(relative_path)}
                            )
                            continue  # Skip this file
                    except Exception as e:
                        self.handle_error(
                            FileOperationError(f"Path validation error: {e}"),
                            {'stage': 'security_validation', 'path': str(relative_path)}
                        )
                        continue  # Skip this file

                    items_for_processing.append(('file', source_file, relative_path))

                # Use intelligent move/copy operation (respects user settings)
                operation_result = self.buffered_ops.move_files_preserving_structure(
                    items_for_processing,
                    self.destination,
                    calculate_hash=self.calculate_hash
                )

                # Handle Result object from move_files_preserving_structure
                if operation_result.success:
                    # Merge results from the operation
                    operation_data = operation_result.value
                    files_processed = 0

                    for key, value in operation_data.items():
                        if key != '_performance_stats':  # Skip metadata
                            results[key] = {
                                'source_path': value.get('source_path', ''),
                                'dest_path': value.get('dest_path', ''),
                                'source_hash': value.get('source_hash', ''),
                                'dest_hash': value.get('dest_hash', ''),
                                'verified': value.get('verified', True),
                                'size': value.get('size', 0),
                                'success': True,
                                'operation': value.get('operation', 'copy')  # Track move vs copy
                            }
                            files_processed += 1

                    # Update final progress
                    self.emit_progress(85, f"Processed {files_processed}/{len(total_files)} files")
                else:
                    # Operation failed - log error and return
                    self.handle_error(operation_result.error, {'stage': 'file_processing'})
                    return operation_result
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
            # Add base forensic path for correct documents placement
            result.add_metadata('base_forensic_path', str(self.destination))
            
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