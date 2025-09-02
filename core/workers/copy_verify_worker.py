#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copy & Verify Worker - Thread handling for copy operations
Pure worker thread - no business logic, just file operations
"""

import hashlib
import time
from pathlib import Path
from typing import List, Optional, Dict, Any

from core.workers.base_worker import BaseWorkerThread
from core.buffered_file_ops import BufferedFileOperations
from core.result_types import Result, FileOperationResult
from core.exceptions import FileOperationError
from core.logger import logger


class CopyVerifyWorker(BaseWorkerThread):
    """
    Worker thread for copy and verify operations
    Uses BufferedFileOperations directly for optimal performance
    """
    
    def __init__(self, 
                 source_items: List[Path],
                 destination: Path,
                 preserve_structure: bool = True,
                 calculate_hash: bool = True,
                 csv_path: Optional[Path] = None,
                 service = None):
        """
        Initialize copy verify worker
        
        Args:
            source_items: List of source files and folders to copy
            destination: Destination directory
            preserve_structure: Whether to preserve folder structure
            calculate_hash: Whether to calculate and verify hashes
            csv_path: Optional path for CSV report generation
            service: Copy verify service for CSV generation
        """
        super().__init__()
        
        self.source_items = source_items
        self.destination = destination
        self.preserve_structure = preserve_structure
        self.calculate_hash = calculate_hash
        self.csv_path = csv_path
        self.service = service
        
        # Track operation results
        self.operation_results = {}
        self.file_ops = None
        
        # Set operation name
        item_count = len(source_items) if source_items else 0
        self.set_operation_name(f"Copy & Verify ({item_count} items)")
        
    def execute(self) -> Result:
        """
        Execute copy and verify operation
        
        Returns:
            FileOperationResult with copy results and metrics
        """
        try:
            # Note: Validation is now done in the controller/service layer
            # Worker just executes the operation
            
            # Track operation timing
            start_time = time.time()
                
            # Check for pause before starting
            self.check_pause()
            
            # Collect all files to copy
            self.emit_progress(5, "Collecting files...")
            all_files = self._collect_files()
            
            if not all_files:
                error = FileOperationError(
                    "No files found to copy",
                    user_message="No files were found in the selected items."
                )
                return Result.error(error)
                
            total_files = len(all_files)
            self.emit_progress(10, f"Found {total_files} files to copy")
            
            
            # Initialize BufferedFileOperations with callbacks
            self.file_ops = BufferedFileOperations(
                progress_callback=self._handle_progress,
                metrics_callback=None,
                cancelled_check=lambda: self.is_cancelled(),
                pause_check=lambda: self.check_pause()  # Add pause support
            )
            
            # Process files
            self.emit_progress(15, "Starting copy operation...")
            
            # Track overall progress
            files_processed = 0
            total_bytes = 0
            errors = []
            
            for idx, (source_file, relative_path) in enumerate(all_files):
                if self.is_cancelled():
                    break
                    
                # Check for pause before each file (or every few files for performance)
                if idx % 5 == 0:  # Check every 5 files to reduce overhead
                    self.check_pause()
                    
                # Calculate progress
                file_progress = 15 + int((idx / total_files) * 70)  # 15-85% for copying
                
                # Determine destination path
                if self.preserve_structure and relative_path:
                    dest_file = self.destination / relative_path
                else:
                    dest_file = self.destination / source_file.name
                    
                # Ensure destination directory exists
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy single file with hash calculation
                self.emit_progress(
                    file_progress,
                    f"Copying {source_file.name}..."
                )
                
                result = self.file_ops.copy_file_buffered(
                    source_file,
                    dest_file,
                    calculate_hash=self.calculate_hash
                )
                
                # Generate unique key with hash prefix and filename for context
                # This provides both uniqueness and human-readable identification
                path_hash = hashlib.md5(str(source_file).encode()).hexdigest()[:8]
                file_key = f"{path_hash}_{source_file.name}"
                
                if result.success:
                    self.operation_results[file_key] = result.value
                    files_processed += 1
                    if idx < 5 or idx == total_files - 1:  # Log first few and last
                        logger.debug(f"[CopyVerifyWorker] Stored result for file {idx+1}: {source_file.name}")
                    
                    # Track bytes
                    if 'size' in result.value:
                        total_bytes += result.value['size']
                else:
                    # Log the actual error for debugging
                    logger.error(f"[CopyVerifyWorker] Failed to copy {source_file.name}: {result.error}")
                    self.operation_results[file_key] = {
                        'success': False,
                        'error': str(result.error),
                        'source_path': str(source_file),
                        'dest_path': str(dest_file)
                    }
                    errors.append(f"{source_file.name}: {result.error}")
                    
            # Check for cancellation
            if self.is_cancelled():
                self.emit_progress(100, "Operation cancelled")
                error = FileOperationError(
                    "Operation cancelled by user",
                    user_message="Copy operation was cancelled."
                )
                return Result.error(error)
                
            # Check for pause before CSV generation
            self.check_pause()
            
            # Generate CSV report if requested (delegate to service if available)
            if self.csv_path and self.calculate_hash and self.service:
                self.emit_progress(90, "Generating CSV report...")
                csv_result = self.service.generate_csv_report(
                    self.operation_results, 
                    self.csv_path,
                    self.calculate_hash
                )
                if csv_result.success:
                    self.emit_progress(95, f"CSV report saved to {self.csv_path.name}")
                else:
                    errors.append("Failed to generate CSV report")
                    
            # Final progress
            logger.debug(f"[CopyVerifyWorker] Final: Processed {files_processed} files, Results dict has {len(self.operation_results)} entries")
            self.emit_progress(100, f"Completed: {files_processed}/{total_files} files")
            
            # Calculate operation metrics
            end_time = time.time()
            duration_seconds = end_time - start_time
            
            # Calculate average speed
            average_speed_mbps = 0
            if duration_seconds > 0 and total_bytes > 0:
                average_speed_mbps = (total_bytes / (1024 * 1024)) / duration_seconds
            
            logger.info(f"[CopyVerifyWorker] Operation complete: {files_processed} files, {total_bytes/(1024*1024*1024):.2f} GB in {duration_seconds:.1f}s at {average_speed_mbps:.1f} MB/s")
            
            # Check if any files had hash mismatches
            hash_mismatches = []
            if self.calculate_hash:
                for file_key, result_data in self.operation_results.items():
                    if isinstance(result_data, dict) and result_data.get('success'):
                        if result_data.get('verified') is False:
                            # Extract filename from the key (format: "hash_filename")
                            filename = file_key.split('_', 1)[1] if '_' in file_key else file_key
                            hash_mismatches.append(filename)
                            
            # Create final result with timing metrics
            # Add performance stats to the results dict
            self.operation_results['_performance_stats'] = {
                'total_time': duration_seconds,
                'average_speed_mbps': average_speed_mbps,
                'peak_speed_mbps': average_speed_mbps * 1.2,  # Estimate peak as 20% higher than average
                'metrics': {
                    'files_processed': files_processed,
                    'bytes_processed': total_bytes,
                    'duration_seconds': duration_seconds
                }
            }
            
            if errors and not files_processed:
                # Complete failure
                error = FileOperationError(
                    f"All copy operations failed: {'; '.join(errors[:5])}",
                    user_message="Failed to copy any files. Check permissions and disk space."
                )
                return Result.error(error)
            elif errors:
                # Partial failure - some files failed to copy
                logger.warning(f"[CopyVerifyWorker] {len(errors)} files failed to copy")
                # Still return success but log the errors
                if hash_mismatches:
                    logger.warning(f"[CopyVerifyWorker] Additionally, {len(hash_mismatches)} files had hash mismatches")
            elif hash_mismatches:
                # Success but with hash verification failures
                error = FileOperationError(
                    f"Hash verification failed for {len(hash_mismatches)} files",
                    user_message=f"Files copied but {len(hash_mismatches)} had hash mismatches: {', '.join(hash_mismatches[:5])}"
                )
                # Return success with the error information in the results
                return FileOperationResult.create(
                    self.operation_results,
                    files_processed=files_processed,
                    bytes_processed=total_bytes
                )
            
            # Return result with all info and metrics
            return FileOperationResult.create(
                self.operation_results,
                files_processed=files_processed,
                bytes_processed=total_bytes
            )
                
        except Exception as e:
            logger.error(f"Copy verify worker error: {e}")
            error = FileOperationError(
                f"Unexpected error during copy operation: {e}",
                user_message="An unexpected error occurred during the copy operation."
            )
            return Result.error(error)
            
    def _collect_files(self) -> List[tuple[Path, Optional[Path]]]:
        """
        Collect all files from source items
        
        Returns:
            List of (source_file, relative_path) tuples
        """
        files = []
        
        for item in self.source_items:
            if not item.exists():
                continue
                
            if item.is_file():
                # Single file - no relative path
                files.append((item, None))
            elif item.is_dir():
                # Directory - collect all files recursively
                for file_path in item.rglob('*'):
                    if file_path.is_file():
                        # Calculate relative path INCLUDING the source directory name
                        # This preserves the root folder structure
                        relative = file_path.relative_to(item.parent)
                        files.append((file_path, relative))
                        
        return files
        
    def _handle_progress(self, percentage: int, message: str):
        """
        Handle progress updates from BufferedFileOperations
        Translate file-level progress to overall progress
        """
        # BufferedFileOperations reports per-file progress
        # We need to maintain overall progress context
        # Just forward the message for now
        if "MB/s" in message:
            # Include speed information
            # Use the percentage passed in, not self.progress which doesn't exist
            self.emit_progress(percentage, message)
            
    # CSV generation removed - now handled by service layer