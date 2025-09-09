#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hashing Success Module - Success message building for hash operations.

This module is specific to the HashingTab and contains all logic for
building success messages for hash operations. It's completely self-contained
and only depends on the generic infrastructure (SuccessMessageData).
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
from core.services.success_message_data import SuccessMessageData
from core.success_utilities import (
    SuccessFormatters, 
    PerformanceFormatter,
    MessageLineBuilder
)


class HashingSuccessBuilder:
    """
    Success message builder specific to hash operations.
    
    This class contains all the business logic for creating success messages
    for the HashingTab. It's completely independent of any central service.
    """
    
    def build_single_hash_success(
        self,
        files_processed: int,
        total_size: int,
        duration: float,
        algorithm: str = "SHA-256",
        csv_path: Optional[Path] = None
    ) -> SuccessMessageData:
        """
        Build success message for single hash calculation.
        
        Args:
            files_processed: Number of files hashed
            total_size: Total bytes processed
            duration: Time taken in seconds
            algorithm: Hash algorithm used
            csv_path: Path to exported CSV report (if any)
            
        Returns:
            SuccessMessageData ready for display
        """
        summary_lines = []
        
        # Main success line
        summary_lines.append(
            MessageLineBuilder.success_line(
                f"Calculated {algorithm} hashes for {SuccessFormatters.pluralize(files_processed, 'file')}"
            )
        )
        
        # Size processed
        if total_size > 0:
            size_str = SuccessFormatters.format_file_size(total_size)
            summary_lines.append(
                MessageLineBuilder.metric_line("Total size", size_str)
            )
        
        # Processing time
        if duration > 0:
            time_str = SuccessFormatters.format_duration(duration)
            summary_lines.append(
                MessageLineBuilder.time_line(f"Processing time: {time_str}")
            )
            
            # Processing speed
            if total_size > 0:
                speed = total_size / duration
                speed_str = SuccessFormatters.format_speed(speed)
                summary_lines.append(
                    MessageLineBuilder.metric_line("Speed", speed_str)
                )
        
        # CSV export info
        if csv_path:
            summary_lines.append("")  # Add spacing
            summary_lines.append(
                MessageLineBuilder.file_line(f"Report saved: {csv_path.name}")
            )
        
        # Build performance data dictionary
        perf_data = {}
        if duration > 0:
            perf_data = {
                'files_processed': files_processed,
                'total_size_mb': total_size / (1024 * 1024),
                'total_time_seconds': duration,
                'average_speed_mbps': (total_size / (1024 * 1024)) / duration if duration > 0 else 0
            }
        
        return SuccessMessageData(
            title=f"{algorithm} Hash Calculation Complete!",
            summary_lines=summary_lines,
            output_location=str(csv_path.parent) if csv_path else None,
            celebration_emoji="🔒",
            performance_data=perf_data
        )
    
    def build_verification_success(
        self,
        total_files: int,
        passed: int,
        failed: int,
        duration: float,
        algorithm: str = "SHA-256",
        csv_path: Optional[Path] = None
    ) -> SuccessMessageData:
        """
        Build success message for hash verification.
        
        Args:
            total_files: Total files checked
            passed: Files that passed verification
            failed: Files that failed verification
            duration: Time taken in seconds
            algorithm: Hash algorithm used
            csv_path: Path to exported CSV report (if any)
            
        Returns:
            SuccessMessageData ready for display
        """
        summary_lines = []
        
        # Main result line
        if failed == 0:
            summary_lines.append(
                MessageLineBuilder.success_line(
                    f"All {total_files} files passed {algorithm} verification"
                )
            )
            emoji = "✅"
            title = "Hash Verification Complete!"
        else:
            summary_lines.append(
                MessageLineBuilder.warning_line(
                    f"{passed}/{total_files} files passed verification"
                )
            )
            summary_lines.append(
                MessageLineBuilder.error_line(
                    f"{failed} files failed verification"
                )
            )
            emoji = "⚠️"
            title = "Hash Verification Complete - Issues Found"
        
        # Success rate
        if total_files > 0:
            success_rate = (passed / total_files) * 100
            summary_lines.append(
                MessageLineBuilder.metric_line(
                    "Success rate",
                    SuccessFormatters.format_percentage(passed, total_files)
                )
            )
        
        # Processing time
        if duration > 0:
            time_str = SuccessFormatters.format_duration(duration)
            summary_lines.append(
                MessageLineBuilder.time_line(f"Verification time: {time_str}")
            )
            
            # Files per second
            if total_files > 0:
                files_per_sec = total_files / duration
                summary_lines.append(
                    MessageLineBuilder.metric_line(
                        "Speed",
                        f"{files_per_sec:.1f} files/second"
                    )
                )
        
        # CSV export info
        if csv_path:
            summary_lines.append("")  # Add spacing
            summary_lines.append(
                MessageLineBuilder.file_line(f"Report saved: {csv_path.name}")
            )
            summary_lines.append(
                MessageLineBuilder.info_line(
                    "Review the CSV for detailed verification results"
                )
            )
        
        return SuccessMessageData(
            title=title,
            summary_lines=summary_lines,
            output_location=str(csv_path.parent) if csv_path else None,
            celebration_emoji=emoji,
            raw_data={
                'total_files': total_files,
                'passed': passed,
                'failed': failed,
                'algorithm': algorithm
            }
        )
    
    def build_export_success(
        self,
        export_type: str,
        file_path: Path,
        record_count: int
    ) -> SuccessMessageData:
        """
        Build success message for CSV export operations.
        
        Args:
            export_type: Type of export ('single_hash' or 'verification')
            file_path: Path to the exported file
            record_count: Number of records exported
            
        Returns:
            SuccessMessageData ready for display
        """
        summary_lines = []
        
        # Main success line
        if export_type == 'single_hash':
            title = "Hash Report Exported!"
            summary_lines.append(
                MessageLineBuilder.success_line(
                    f"Exported {record_count} hash records to CSV"
                )
            )
        else:  # verification
            title = "Verification Report Exported!"
            summary_lines.append(
                MessageLineBuilder.success_line(
                    f"Exported {record_count} verification results to CSV"
                )
            )
        
        # File details
        summary_lines.append(
            MessageLineBuilder.file_line(f"Filename: {file_path.name}")
        )
        
        # File size if available
        if file_path.exists():
            size = file_path.stat().st_size
            size_str = SuccessFormatters.format_file_size(size)
            summary_lines.append(
                MessageLineBuilder.metric_line("File size", size_str)
            )
        
        summary_lines.append("")  # Add spacing
        summary_lines.append(
            MessageLineBuilder.info_line("File ready for review or archival")
        )
        
        return SuccessMessageData(
            title=title,
            summary_lines=summary_lines,
            output_location=str(file_path.parent),
            celebration_emoji="💾"
        )