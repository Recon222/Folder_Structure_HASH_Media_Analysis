#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Success message builder for forensic operations.
This module is owned by the forensic tab and contains all logic
for building success messages from forensic operation results.
"""

from typing import Optional, Dict
from pathlib import Path
import logging

from core.services.success_message_data import SuccessMessageData
from core.result_types import FileOperationResult, ReportGenerationResult, ArchiveOperationResult


class ForensicSuccessBuilder:
    """
    Builds success messages for forensic operations.
    Contains all formatting logic specific to forensic processing.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def create_success_message(
        self,
        file_result: Optional[FileOperationResult] = None,
        report_results: Optional[Dict[str, ReportGenerationResult]] = None,
        zip_result: Optional[ArchiveOperationResult] = None
    ) -> SuccessMessageData:
        """
        Build comprehensive forensic operation success message.
        
        Args:
            file_result: File copying operation results
            report_results: Dictionary of report generation results
            zip_result: ZIP archive creation results
            
        Returns:
            SuccessMessageData object ready for UI display
        """
        summary_lines = []
        
        # File operation summary
        if file_result and file_result.success:
            summary_lines.append(f"✓ Copied {file_result.files_processed} files")
            
            # Add size information if available
            if file_result.bytes_processed > 0:
                size_gb = file_result.bytes_processed / (1024**3)
                if size_gb >= 1:
                    summary_lines.append(f"💾 Total size: {size_gb:.2f} GB")
                else:
                    size_mb = file_result.bytes_processed / (1024**2)
                    summary_lines.append(f"💾 Total size: {size_mb:.1f} MB")
            
            # Performance summary
            if file_result.duration_seconds > 0 and file_result.files_processed > 0:
                perf_summary = self._build_performance_summary(file_result)
                if perf_summary:
                    summary_lines.append(perf_summary)
        
        # Report generation summary
        if report_results:
            report_summary = self._build_report_summary(report_results)
            if report_summary:
                summary_lines.extend(report_summary)
        
        # ZIP archive summary
        if zip_result and zip_result.success:
            zip_summary = self._build_zip_summary(zip_result)
            if zip_summary:
                summary_lines.append(zip_summary)
        
        # Extract output location
        output_location = self._extract_output_location(file_result)
        
        # Extract performance data for dialog
        perf_data = self._extract_performance_dict(file_result) if file_result else {}
        
        # Default message if no operations
        if not summary_lines:
            summary_lines = ["✓ Operation completed successfully"]
        
        return SuccessMessageData(
            title="Forensic Processing Complete! 🔍",
            summary_lines=summary_lines,
            output_location=output_location,
            celebration_emoji="🎉",
            performance_data=perf_data,
            raw_data={
                'file_result': file_result,
                'report_results': report_results,
                'zip_result': zip_result
            }
        )
    
    def _build_performance_summary(self, file_result: FileOperationResult) -> Optional[str]:
        """Build performance summary line from file operation results."""
        try:
            # Calculate average speed
            if file_result.duration_seconds > 0 and file_result.bytes_processed > 0:
                speed_mbps = (file_result.bytes_processed / (1024 * 1024)) / file_result.duration_seconds
                
                # Format duration
                if file_result.duration_seconds >= 60:
                    minutes = file_result.duration_seconds / 60
                    time_str = f"{minutes:.1f} minutes"
                else:
                    time_str = f"{file_result.duration_seconds:.1f} seconds"
                
                return f"⚡ Performance: {speed_mbps:.1f} MB/s over {time_str}"
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Could not build performance summary: {e}")
            return None
    
    def _build_report_summary(self, report_results: Dict[str, ReportGenerationResult]) -> list:
        """Build report generation summary lines."""
        summary = []
        
        successful_reports = [
            name for name, result in report_results.items() 
            if result and result.success
        ]
        
        if successful_reports:
            summary.append(f"📄 Generated {len(successful_reports)} report(s):")
            for report_name in successful_reports:
                # Convert report key to display name
                display_name = self._format_report_name(report_name)
                summary.append(f"  • {display_name}")
        
        return summary
    
    def _build_zip_summary(self, zip_result: ArchiveOperationResult) -> Optional[str]:
        """Build ZIP archive summary line."""
        try:
            # Basic success message
            summary_parts = ["📦 Created ZIP archive"]
            
            # Add archive name if available from value (list of paths)
            if hasattr(zip_result, 'value') and zip_result.value and isinstance(zip_result.value, list):
                if len(zip_result.value) > 0:
                    archive_name = Path(zip_result.value[0]).name
                    summary_parts[0] = f"📦 Created archive: {archive_name}"
            
            # Add size if available
            if hasattr(zip_result, 'total_compressed_size') and zip_result.total_compressed_size > 0:
                size_mb = zip_result.total_compressed_size / (1024 * 1024)
                if size_mb >= 1024:
                    size_gb = size_mb / 1024
                    summary_parts.append(f"({size_gb:.1f} GB)")
                else:
                    summary_parts.append(f"({size_mb:.1f} MB)")
            
            return " ".join(summary_parts)
            
        except Exception as e:
            self.logger.debug(f"Could not build ZIP summary: {e}")
            return "📦 Created ZIP archive"
    
    def _extract_output_location(self, file_result: Optional[FileOperationResult]) -> Optional[str]:
        """Extract output location from file operation results."""
        if not file_result:
            return None
        
        try:
            # Try metadata first
            if hasattr(file_result, 'metadata') and file_result.metadata:
                if 'base_forensic_path' in file_result.metadata:
                    return str(file_result.metadata['base_forensic_path'])
                if 'output_directory' in file_result.metadata:
                    return str(file_result.metadata['output_directory'])
            
            # Try value dict
            if hasattr(file_result, 'value') and isinstance(file_result.value, dict):
                op_data = file_result.value.get('operation', {})
                if 'dest_path' in op_data:
                    return str(op_data['dest_path'])
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Could not extract output location: {e}")
            return None
    
    def _extract_performance_dict(self, file_result: Optional[FileOperationResult]) -> dict:
        """Extract performance data dictionary for success dialog."""
        if not file_result:
            return {}
        
        try:
            perf_data = {}
            
            if file_result.files_processed > 0:
                perf_data['files_processed'] = file_result.files_processed
            
            if file_result.bytes_processed > 0:
                perf_data['bytes_processed'] = file_result.bytes_processed
                perf_data['total_size_mb'] = file_result.bytes_processed / (1024 * 1024)
            
            if file_result.duration_seconds > 0:
                perf_data['total_time_seconds'] = file_result.duration_seconds
                
                # Calculate average speed
                if file_result.bytes_processed > 0:
                    speed_mbps = (file_result.bytes_processed / (1024 * 1024)) / file_result.duration_seconds
                    perf_data['average_speed_mbps'] = speed_mbps
            
            # Try to get peak speed from metadata
            if hasattr(file_result, 'metadata') and file_result.metadata:
                if 'peak_speed_mbps' in file_result.metadata:
                    perf_data['peak_speed_mbps'] = file_result.metadata['peak_speed_mbps']
            
            return perf_data
            
        except Exception as e:
            self.logger.debug(f"Could not extract performance data: {e}")
            return {}
    
    def _format_report_name(self, report_key: str) -> str:
        """Format report key into display name."""
        report_names = {
            'time_offset': 'Time Offset Report',
            'upload_log': 'Upload Log',
            'hash_csv': 'Hash Verification CSV',
            'technician_log': 'Technician Log',
            'dvr_log': 'DVR Time Log'
        }
        return report_names.get(report_key, report_key.replace('_', ' ').title())