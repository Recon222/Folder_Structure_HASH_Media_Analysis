#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copy & Verify Worker - Direct file copying with hash verification
Leverages BufferedFileOperations with buffer reuse optimization
"""

import csv
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from core.workers.base_worker import BaseWorkerThread
from core.buffered_file_ops import BufferedFileOperations
from core.result_types import Result, FileOperationResult
from core.exceptions import FileOperationError, ValidationError
from core.logger import logger
from core.settings_manager import settings


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
                 csv_path: Optional[Path] = None):
        """
        Initialize copy verify worker
        
        Args:
            source_items: List of source files and folders to copy
            destination: Destination directory
            preserve_structure: Whether to preserve folder structure
            calculate_hash: Whether to calculate and verify hashes
            csv_path: Optional path for CSV report generation
        """
        super().__init__()
        
        self.source_items = source_items
        self.destination = destination
        self.preserve_structure = preserve_structure
        self.calculate_hash = calculate_hash
        self.csv_path = csv_path
        
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
            # Validate inputs
            if not self.source_items:
                error = ValidationError(
                    {"source_items": "No source files or folders specified"},
                    user_message="Please select files or folders to copy."
                )
                return Result.error(error)
                
            if not self.destination:
                error = ValidationError(
                    {"destination": "No destination path specified"},
                    user_message="Please select a destination folder."
                )
                return Result.error(error)
                
            # Ensure destination exists
            try:
                self.destination.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                error = FileOperationError(
                    f"Failed to create destination directory: {e}",
                    user_message=f"Cannot create destination folder: {e}"
                )
                return Result.error(error)
                
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
            
            # Generate CSV report if requested
            if self.csv_path and self.calculate_hash:
                self.emit_progress(90, "Generating CSV report...")
                csv_success = self._generate_csv_report()
                if csv_success:
                    self.emit_progress(95, f"CSV report saved to {self.csv_path.name}")
                else:
                    errors.append("Failed to generate CSV report")
                    
            # Final progress
            logger.debug(f"[CopyVerifyWorker] Final: Processed {files_processed} files, Results dict has {len(self.operation_results)} entries")
            self.emit_progress(100, f"Completed: {files_processed}/{total_files} files")
            
            # Check if any files had hash mismatches
            hash_mismatches = []
            if self.calculate_hash:
                for file_key, result_data in self.operation_results.items():
                    if isinstance(result_data, dict) and result_data.get('success'):
                        if result_data.get('verified') is False:
                            # Extract filename from the key (format: "hash_filename")
                            filename = file_key.split('_', 1)[1] if '_' in file_key else file_key
                            hash_mismatches.append(filename)
                            
            # Create final result
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
            
            # Return result with all info
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
            
    def _generate_csv_report(self) -> bool:
        """
        Generate CSV report from operation results
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                # Write metadata header
                csvfile.write(f"# Copy & Verify Report\n")
                csvfile.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                csvfile.write(f"# Algorithm: {settings.hash_algorithm.upper()}\n")
                csvfile.write(f"# Total Files: {len(self.operation_results)}\n")
                csvfile.write("\n")
                
                # Write data
                fieldnames = [
                    'Source Path', 'Destination Path', 'Size (bytes)',
                    'Source Hash', 'Destination Hash', 'Match', 'Status', 'Error'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for file_key, result_data in self.operation_results.items():
                    if isinstance(result_data, dict):
                        if result_data.get('success'):
                            # Successful copy
                            row = {
                                'Source Path': result_data.get('source_path', file_key),
                                'Destination Path': result_data.get('dest_path', ''),
                                'Size (bytes)': result_data.get('size', 0),
                                'Source Hash': result_data.get('source_hash', 'N/A'),
                                'Destination Hash': result_data.get('dest_hash', 'N/A'),
                                'Match': 'Yes' if result_data.get('verified') else 'No',
                                'Status': 'Success' if result_data.get('verified') else 'Hash Mismatch',
                                'Error': ''
                            }
                        else:
                            # Failed copy
                            row = {
                                'Source Path': result_data.get('source_path', file_key),
                                'Destination Path': result_data.get('dest_path', ''),
                                'Size (bytes)': 0,
                                'Source Hash': '',
                                'Destination Hash': '',
                                'Match': '',
                                'Status': 'Failed',
                                'Error': result_data.get('error', 'Unknown error')
                            }
                        writer.writerow(row)
                        
                # Write summary
                csvfile.write("\n# Summary\n")
                successful = sum(1 for r in self.operation_results.values() 
                               if isinstance(r, dict) and r.get('success'))
                failed = len(self.operation_results) - successful
                
                if self.calculate_hash:
                    verified = sum(1 for r in self.operation_results.values()
                                 if isinstance(r, dict) and r.get('verified'))
                    mismatched = successful - verified
                    csvfile.write(f"# Successful: {successful}, Failed: {failed}, ")
                    csvfile.write(f"Verified: {verified}, Mismatched: {mismatched}\n")
                else:
                    csvfile.write(f"# Successful: {successful}, Failed: {failed}\n")
                    
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate CSV report: {e}")
            return False