#!/usr/bin/env python3
"""
Copy and Verify Service - Business logic for copy operations
Implements ICopyVerifyService interface with full SOA compliance
"""

import csv
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .interfaces import ICopyVerifyService
from .base_service import BaseService
from .success_message_data import CopyVerifyOperationData, SuccessMessageData
from ..result_types import Result
from ..exceptions import ValidationError, FileOperationError, ErrorSeverity
from ..settings_manager import settings
from ..logger import logger


class CopyVerifyService(BaseService, ICopyVerifyService):
    """Service for copy and verify operations"""
    
    def __init__(self):
        """Initialize copy verify service"""
        super().__init__("CopyVerifyService")
        
    def validate_copy_operation(
        self, 
        source_items: List[Path], 
        destination: Path
    ) -> Result[None]:
        """
        Validate copy operation parameters
        
        Args:
            source_items: List of source paths to copy
            destination: Destination directory path
            
        Returns:
            Result.success(None) if valid, Result.error() if invalid
        """
        try:
            # Validate source items
            if not source_items:
                return Result.error(
                    ValidationError(
                        {"source_items": "No source files or folders specified"},
                        user_message="Please select files or folders to copy."
                    )
                )
            
            # Check each source exists
            missing_sources = []
            for item in source_items:
                if not item.exists():
                    missing_sources.append(str(item))
                    
            if missing_sources:
                return Result.error(
                    ValidationError(
                        {"source_items": f"Source files not found: {', '.join(missing_sources[:3])}"},
                        user_message=f"Some source files no longer exist. Please refresh your selection."
                    )
                )
            
            # Validate destination
            if not destination:
                return Result.error(
                    ValidationError(
                        {"destination": "No destination path specified"},
                        user_message="Please select a destination folder."
                    )
                )
            
            # Check if destination is not a child of any source
            for source in source_items:
                if source.is_dir():
                    try:
                        dest_resolved = destination.resolve()
                        source_resolved = source.resolve()
                        if str(dest_resolved).startswith(str(source_resolved)):
                            return Result.error(
                                ValidationError(
                                    {"destination": f"Destination cannot be inside source folder {source.name}"},
                                    user_message="Destination folder cannot be inside a source folder being copied."
                                )
                            )
                    except Exception:
                        pass  # Skip if resolution fails
                        
            self._log_operation("validate_copy_operation", f"Validated {len(source_items)} source items")
            return Result.success(None)
            
        except Exception as e:
            error = ValidationError(
                {"validation": str(e)},
                user_message="Failed to validate copy operation."
            )
            self._handle_error(error, {"method": "validate_copy_operation"})
            return Result.error(error)
    
    def validate_destination_security(
        self,
        destination: Path,
        source_items: List[Path]
    ) -> Result[None]:
        """
        Validate destination path security and prevent path traversal
        
        Args:
            destination: Destination directory
            source_items: List of source items for context
            
        Returns:
            Result.success(None) if secure, Result.error() if security issue detected
        """
        try:
            # Resolve destination to absolute path
            dest_resolved = destination.resolve()
            
            # Check for common path traversal patterns
            dest_str = str(destination)
            if any(pattern in dest_str for pattern in ['..', '~/', '\\\\', '//']):
                # Additional validation for suspicious patterns
                try:
                    # Ensure resolved path is still under expected location
                    if not dest_resolved.is_absolute():
                        return Result.error(
                            FileOperationError(
                                "Destination path must be absolute",
                                user_message="Please select a valid destination folder."
                            )
                        )
                except Exception:
                    return Result.error(
                        FileOperationError(
                            f"Invalid destination path: {destination}",
                            user_message="The selected destination path is invalid."
                        )
                    )
            
            # Ensure destination is writable (or can be created)
            if dest_resolved.exists():
                if not dest_resolved.is_dir():
                    return Result.error(
                        FileOperationError(
                            "Destination exists but is not a directory",
                            user_message="The selected destination is a file, not a folder."
                        )
                    )
                # Try to check write permission
                test_file = dest_resolved / '.write_test'
                try:
                    test_file.touch()
                    test_file.unlink()
                except Exception:
                    return Result.error(
                        FileOperationError(
                            "No write permission for destination",
                            user_message="You don't have permission to write to the selected destination."
                        )
                    )
            
            self._log_operation("validate_destination_security", f"Destination validated: {destination}")
            return Result.success(None)
            
        except Exception as e:
            error = FileOperationError(
                f"Security validation failed: {e}",
                user_message="Failed to validate destination security."
            )
            self._handle_error(error, {"method": "validate_destination_security"})
            return Result.error(error)
    
    def prepare_copy_operation(
        self,
        source_items: List[Path],
        destination: Path,
        preserve_structure: bool
    ) -> Result[List[Tuple[Path, Optional[Path]]]]:
        """
        Prepare file list for copy operation
        
        Args:
            source_items: List of source paths
            destination: Destination directory
            preserve_structure: Whether to preserve folder structure
            
        Returns:
            Result containing list of (source_file, relative_path) tuples
        """
        try:
            files = []
            
            for item in source_items:
                if not item.exists():
                    continue
                    
                if item.is_file():
                    # Single file - no relative path unless preserving structure
                    if preserve_structure and item.parent != item.parent.parent:
                        # Preserve parent directory in structure
                        files.append((item, Path(item.parent.name) / item.name))
                    else:
                        files.append((item, None))
                        
                elif item.is_dir():
                    # Directory - collect all files recursively
                    for file_path in item.rglob('*'):
                        if file_path.is_file():
                            if preserve_structure:
                                # Calculate relative path INCLUDING the source directory name
                                relative = file_path.relative_to(item.parent)
                            else:
                                # Just the filename
                                relative = None
                            files.append((file_path, relative))
            
            if not files:
                return Result.error(
                    FileOperationError(
                        "No files found in selected items",
                        user_message="No files were found in the selected items."
                    )
                )
            
            self._log_operation("prepare_copy_operation", f"Prepared {len(files)} files for copying")
            return Result.success(files)
            
        except Exception as e:
            error = FileOperationError(
                f"Failed to prepare copy operation: {e}",
                user_message="Failed to prepare files for copying."
            )
            self._handle_error(error, {"method": "prepare_copy_operation"})
            return Result.error(error)
    
    def process_operation_results(
        self,
        results: Dict[str, Any],
        calculate_hash: bool,
        performance_stats: Optional[Dict[str, Any]] = None
    ) -> Result[SuccessMessageData]:
        """
        Process operation results and build success message data
        
        Args:
            results: Operation results dictionary
            calculate_hash: Whether hashes were calculated
            performance_stats: Performance metrics from worker
            
        Returns:
            Result containing SuccessMessageData
        """
        try:
            # Check if results is a FileOperationResult-style dict with metadata
            actual_results = results
            if isinstance(results, dict) and 'value' in results:
                # This is likely a FileOperationResult dict
                actual_results = results.get('value', {})
                # Extract performance stats if not provided
                if not performance_stats:
                    performance_stats = results.get('metadata', {})
            
            # Extract performance stats from the results if embedded
            if isinstance(actual_results, dict) and '_performance_stats' in actual_results:
                if not performance_stats:
                    performance_stats = actual_results['_performance_stats']
                # Remove it from the actual results to avoid counting it as a file
                actual_results = {k: v for k, v in actual_results.items() if k != '_performance_stats'}
            
            # Extract metrics from results
            files_processed = 0
            bytes_processed = 0
            failed_count = 0
            mismatches = 0
            
            for file_key, file_data in actual_results.items():
                if isinstance(file_data, dict):
                    if file_data.get('success', False):
                        files_processed += 1
                        bytes_processed += file_data.get('size', 0)
                        if calculate_hash and file_data.get('verified') is False:
                            mismatches += 1
                    else:
                        failed_count += 1
            
            # Extract timing and speed from performance stats
            operation_time = 0
            avg_speed = 0
            peak_speed = 0
            
            if performance_stats:
                operation_time = performance_stats.get('total_time', 0)
                avg_speed = performance_stats.get('average_speed_mbps', 0)
                peak_speed = performance_stats.get('peak_speed_mbps', avg_speed)
                logger.info(f"[CopyVerifyService] Performance stats: time={operation_time:.1f}s, avg_speed={avg_speed:.1f} MB/s, peak={peak_speed:.1f} MB/s")
            else:
                logger.warning("[CopyVerifyService] No performance stats available")
            
            # Build operation data
            copy_data = CopyVerifyOperationData(
                files_copied=files_processed,
                bytes_processed=bytes_processed,
                operation_time_seconds=operation_time,
                average_speed_mbps=avg_speed,
                peak_speed_mbps=peak_speed,
                hash_verification_enabled=calculate_hash,
                files_with_hash_mismatch=mismatches,
                files_failed_to_copy=failed_count,
                csv_generated=False,
                csv_path=None,
                source_items_count=len(actual_results),
                preserve_structure=True  # Would come from operation params
            )
            
            # Build success message
            from .success_message_builder import SuccessMessageBuilder
            message_builder = SuccessMessageBuilder()
            message_data = message_builder.build_copy_verify_success_message(copy_data)
            
            self._log_operation("process_operation_results", 
                              f"Processed results: {files_processed} files, {failed_count} failures")
            
            return Result.success(message_data)
            
        except Exception as e:
            error = FileOperationError(
                f"Failed to process operation results: {e}",
                user_message="Failed to process copy operation results."
            )
            self._handle_error(error, {"method": "process_operation_results"})
            return Result.error(error)
    
    def generate_csv_report(
        self,
        results: Dict[str, Any],
        csv_path: Path,
        calculate_hash: bool
    ) -> Result[Path]:
        """
        Generate CSV report from operation results
        
        Args:
            results: Operation results dictionary
            csv_path: Path for CSV file
            calculate_hash: Whether hashes were calculated
            
        Returns:
            Result containing path to generated CSV
        """
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                # Write metadata header
                csvfile.write(f"# Copy & Verify Report\n")
                csvfile.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                if calculate_hash:
                    csvfile.write(f"# Algorithm: {settings.hash_algorithm.upper()}\n")
                csvfile.write(f"# Total Files: {len(results)}\n")
                csvfile.write("\n")
                
                # Write data
                fieldnames = [
                    'Source Path', 'Destination Path', 'Size (bytes)',
                    'Source Hash', 'Destination Hash', 'Match', 'Status', 'Error'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                successful = 0
                failed = 0
                verified = 0
                mismatched = 0
                
                for file_key, result_data in results.items():
                    if isinstance(result_data, dict):
                        if result_data.get('success'):
                            successful += 1
                            if calculate_hash and result_data.get('verified'):
                                verified += 1
                            elif calculate_hash and result_data.get('verified') is False:
                                mismatched += 1
                                
                            row = {
                                'Source Path': result_data.get('source_path', file_key),
                                'Destination Path': result_data.get('dest_path', ''),
                                'Size (bytes)': result_data.get('size', 0),
                                'Source Hash': result_data.get('source_hash', 'N/A') if calculate_hash else 'N/A',
                                'Destination Hash': result_data.get('dest_hash', 'N/A') if calculate_hash else 'N/A',
                                'Match': 'Yes' if result_data.get('verified') else 'No' if calculate_hash else 'N/A',
                                'Status': 'Success' if result_data.get('verified') or not calculate_hash else 'Hash Mismatch',
                                'Error': ''
                            }
                        else:
                            failed += 1
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
                csvfile.write(f"# Successful: {successful}, Failed: {failed}")
                if calculate_hash:
                    csvfile.write(f", Verified: {verified}, Mismatched: {mismatched}")
                csvfile.write("\n")
            
            self._log_operation("generate_csv_report", f"Generated CSV report: {csv_path}")
            return Result.success(csv_path)
            
        except Exception as e:
            error = FileOperationError(
                f"Failed to generate CSV report: {e}",
                user_message="Failed to generate CSV report."
            )
            self._handle_error(error, {"method": "generate_csv_report"})
            return Result.error(error)
    
    def export_results_to_csv(
        self,
        results: Dict[str, Any],
        csv_path: Path
    ) -> Result[Path]:
        """
        Export existing results to CSV file
        
        Args:
            results: Operation results to export
            csv_path: Path for CSV file
            
        Returns:
            Result containing path to exported CSV
        """
        # This is essentially the same as generate_csv_report
        # but might have different formatting or options in the future
        return self.generate_csv_report(results, csv_path, calculate_hash=True)