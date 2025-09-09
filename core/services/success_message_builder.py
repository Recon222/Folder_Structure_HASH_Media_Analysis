#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Success Message Builder - Pure business logic for building success messages.

This service class contains all the business logic for constructing success messages
from operation results, completely separated from UI concerns. It accepts Result objects
directly and produces SuccessMessageData objects for UI consumption.
"""

from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import logging

from core.result_types import (
    Result, FileOperationResult, ReportGenerationResult, ArchiveOperationResult
)
from core.services.success_message_data import (
    SuccessMessageData, HashOperationData, CopyVerifyOperationData, 
    MediaAnalysisOperationData, ExifToolOperationData
)


class SuccessMessageBuilder:
    """
    Pure business logic service for building success messages.
    
    This class contains no UI dependencies and focuses solely on the business logic
    of constructing appropriate success messages from operation results.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def build_forensic_success_message(
        self,
        file_result: FileOperationResult,
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
        summary_lines.append(f"✓ Copied {file_result.files_processed} files")
        
        # Performance summary (check metadata for duration if needed)
        duration = file_result.duration_seconds
        if duration == 0 and hasattr(file_result, 'metadata'):
            duration = file_result.metadata.get('duration_seconds', 0)
        
        if file_result.files_processed > 0 and duration > 0:
            perf_summary = self._build_performance_summary(file_result)
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
        
        # Extract performance data
        perf_data = self._extract_performance_dict(file_result)
        
        return SuccessMessageData(
            title="Operation Complete!",
            summary_lines=summary_lines,
            output_location=output_location,
            celebration_emoji="✅",
            performance_data=perf_data,
            raw_data={
                'file_result': file_result,
                'report_results': report_results,
                'zip_result': zip_result
            }
        )
    
    def build_hash_verification_success_message(
        self,
        hash_data: HashOperationData
    ) -> SuccessMessageData:
        """
        Build hash verification success message.
        
        Args:
            hash_data: Hash operation results
            
        Returns:
            SuccessMessageData for hash verification success
        """
        summary_lines = [
            f"✓ Verified {hash_data.files_verified} files",
            f"🔒 Algorithm: {hash_data.hash_algorithm}",
            f"⏱️ Verification time: {hash_data.verification_time_seconds:.1f} seconds"
        ]
        
        if hash_data.failed_verifications > 0:
            success_rate = hash_data.get_success_rate()
            summary_lines.append(f"⚠️ Failed verifications: {hash_data.failed_verifications}")
            summary_lines.append(f"📊 Success rate: {success_rate:.1f}%")
        
        if hash_data.csv_file_path:
            summary_lines.append(f"📄 CSV report: {hash_data.csv_file_path.name}")
        
        return SuccessMessageData(
            title="Hash Verification Complete!",
            summary_lines=summary_lines,
            output_location=str(hash_data.csv_file_path) if hash_data.csv_file_path else None,
            celebration_emoji="🔒",
            raw_data={'hash_data': hash_data}
        )
    
    def build_copy_verify_success_message(
        self,
        copy_data: CopyVerifyOperationData
    ) -> SuccessMessageData:
        """
        Build copy & verify operation success message.
        
        Args:
            copy_data: Copy & verify operation results
            
        Returns:
            SuccessMessageData for copy & verify success display
        """
        summary_lines = []
        
        # Main operation summary
        if copy_data.files_failed_to_copy > 0:
            total_attempted = copy_data.files_copied + copy_data.files_failed_to_copy
            summary_lines.append(f"⚠️ Copied {copy_data.files_copied}/{total_attempted} files ({copy_data.get_size_display()})")
            summary_lines.append(f"❌ {copy_data.files_failed_to_copy} files failed to copy")
        else:
            summary_lines.append(f"✅ Successfully copied {copy_data.files_copied} files ({copy_data.get_size_display()})")
        
        # Hash verification summary
        if copy_data.hash_verification_enabled:
            summary_lines.append("")  # Add spacing
            if copy_data.files_with_hash_mismatch > 0:
                summary_lines.append(f"⚠️ Hash Verification Issues:")
                summary_lines.append(f"  • {copy_data.files_with_hash_mismatch} files had hash mismatches")
                verified_count = copy_data.files_copied - copy_data.files_with_hash_mismatch
                if verified_count > 0:
                    summary_lines.append(f"  • {verified_count} files verified successfully")
            else:
                summary_lines.append(f"✅ All file hashes verified successfully")
        
        # Performance summary - show if we have any timing data at all
        if copy_data.operation_time_seconds > 0.001 and copy_data.bytes_processed > 0:
            summary_lines.append("")  # Add spacing
            summary_lines.append("📊 Performance Summary:")
            
            # Show time with appropriate precision
            if copy_data.operation_time_seconds < 1:
                summary_lines.append(f"  • Time: {copy_data.operation_time_seconds:.3f} seconds")
            else:
                summary_lines.append(f"  • Time: {copy_data.operation_time_seconds:.1f} seconds")
            
            if copy_data.average_speed_mbps > 0:
                summary_lines.append(f"  • Average speed: {copy_data.average_speed_mbps:.1f} MB/s")
            
            if copy_data.peak_speed_mbps > 0 and copy_data.peak_speed_mbps != copy_data.average_speed_mbps:
                summary_lines.append(f"  • Peak speed: {copy_data.peak_speed_mbps:.1f} MB/s")
        
        # CSV report info
        if copy_data.csv_generated and copy_data.csv_path:
            summary_lines.append("")  # Add spacing
            summary_lines.append(f"📄 CSV report saved: {copy_data.csv_path.name}")
        
        # Operation details
        if copy_data.preserve_structure:
            summary_lines.append("")  # Add spacing
            summary_lines.append("ℹ️ Folder structure preserved during copy")
        
        # Determine title and emoji based on results
        if copy_data.has_issues:
            if copy_data.files_failed_to_copy > 0:
                title = "Copy Operation Completed with Errors"
                emoji = "⚠️"
            else:
                title = "Copy Complete - Hash Verification Issues"
                emoji = "⚠️"
        else:
            title = "Copy & Verify Complete!"
            emoji = "✅"
        
        # Build performance data dictionary for compatibility
        perf_data = {}
        if copy_data.operation_time_seconds > 0:
            perf_data = {
                'files_processed': copy_data.files_copied,
                'bytes_processed': copy_data.bytes_processed,
                'total_time_seconds': copy_data.operation_time_seconds,
                'average_speed_mbps': copy_data.average_speed_mbps,
                'peak_speed_mbps': copy_data.peak_speed_mbps,
                'total_size_mb': copy_data.bytes_processed / (1024 * 1024)
            }
        
        return SuccessMessageData(
            title=title,
            summary_lines=summary_lines,
            output_location=str(copy_data.csv_path.parent) if copy_data.csv_path else None,
            celebration_emoji=emoji,
            performance_data=perf_data,
            raw_data={'copy_data': copy_data}
        )
    
    
    # Private helper methods
    
    def _build_performance_summary(self, file_result: FileOperationResult) -> str:
        """Build performance summary from file operation result."""
        # Check for duration in metadata if not in main attributes
        duration = file_result.duration_seconds
        if duration == 0 and hasattr(file_result, 'metadata'):
            duration = file_result.metadata.get('duration_seconds', 0)
        
        if not (file_result.files_processed > 0 and duration > 0):
            return ""
        
        # Calculate speed if not available
        avg_speed = file_result.average_speed_mbps
        if avg_speed == 0 and duration > 0:
            avg_speed = (file_result.bytes_processed / (1024 * 1024)) / duration
        
        lines = [
            f"Files: {file_result.files_processed}",
            f"Size: {file_result.bytes_processed / (1024 * 1024):.1f} MB",
            f"Time: {duration:.1f} seconds",
            f"Average Speed: {avg_speed:.1f} MB/s"
        ]
        
        # Add peak speed if available
        if hasattr(file_result, 'peak_speed_mbps') and file_result.peak_speed_mbps:
            lines.append(f"Peak Speed: {file_result.peak_speed_mbps:.1f} MB/s")
        
        # Add mode if available
        if hasattr(file_result, 'optimization_mode'):
            lines.append(f"Mode: {file_result.optimization_mode}")
        
        return "📊 Performance Summary:\n" + "\n".join(lines)
    
    def _build_report_summary(
        self, 
        report_results: Dict[str, ReportGenerationResult]
    ) -> List[str]:
        """Build report generation summary from results."""
        successful_reports = []
        
        for report_type, result in report_results.items():
            if result.success:
                # Get file size in KB
                file_size_kb = result.file_size_bytes / 1024 if result.file_size_bytes > 0 else 0
                report_name = self._get_report_display_name(report_type)
                
                if file_size_kb > 0:
                    successful_reports.append(f"  • {report_name} ({file_size_kb:.0f} KB)")
                else:
                    successful_reports.append(f"  • {report_name}")
        
        if successful_reports:
            return [f"✓ Generated {len(successful_reports)} reports"] + successful_reports
        
        return []
    
    def _build_zip_summary(self, zip_result: ArchiveOperationResult) -> str:
        """Build ZIP archive summary from results."""
        if not zip_result.success or not hasattr(zip_result, 'archives_created'):
            return ""
        
        # archives_created is an int, not a list
        archive_count = zip_result.archives_created if zip_result.archives_created else 1
        total_size_mb = zip_result.total_compressed_size / (1024 * 1024) if zip_result.total_compressed_size else 0
        
        if total_size_mb > 0:
            return f"✓ Created {archive_count} ZIP archive(s) ({total_size_mb:.1f} MB)"
        else:
            return f"✓ Created {archive_count} ZIP archive(s)"
    
    def _extract_output_location(self, file_result: FileOperationResult) -> Optional[str]:
        """Extract output location from file operation result."""
        if hasattr(file_result, 'output_directory') and file_result.output_directory:
            return str(file_result.output_directory)
        
        # Fallback: try to extract from file paths
        if hasattr(file_result, 'value') and file_result.value:
            if isinstance(file_result.value, dict):
                for path_data in file_result.value.values():
                    if isinstance(path_data, dict) and 'dest_path' in path_data:
                        return str(Path(path_data['dest_path']).parent)
        
        return None
    
    def _extract_performance_dict(self, file_result: FileOperationResult) -> Dict[str, Any]:
        """Extract performance data as dictionary for compatibility."""
        if not (file_result.files_processed > 0 and file_result.duration_seconds > 0):
            return {}
        
        result = {
            'files_processed': file_result.files_processed,
            'bytes_processed': file_result.bytes_processed,
            'total_time_seconds': file_result.duration_seconds,
            'average_speed_mbps': file_result.average_speed_mbps,
            'total_size_mb': file_result.bytes_processed / (1024 * 1024),
            'peak_speed_mbps': getattr(file_result, 'peak_speed_mbps', file_result.average_speed_mbps),
            'mode': getattr(file_result, 'optimization_mode', 'Balanced')
        }
        return result
    
    def build_media_analysis_success_message(
        self, 
        analysis_data: 'MediaAnalysisOperationData'
    ) -> SuccessMessageData:
        """
        Build success message for media analysis operations.
        
        Args:
            analysis_data: Media analysis operation data
            
        Returns:
            SuccessMessageData configured for media analysis success
        """
        # Build primary message
        primary_message = f"Successfully analyzed {analysis_data.media_files_found} media files"
        
        # Build details list
        details = []
        
        # Analysis statistics
        details.append(f"✓ Analyzed {analysis_data.total_files} total files")
        details.append(f"✓ Found {analysis_data.media_files_found} media files")
        
        if analysis_data.non_media_files > 0:
            details.append(f"✓ Skipped {analysis_data.non_media_files} non-media files")
        
        if analysis_data.failed_files > 0:
            details.append(f"⚠ {analysis_data.failed_files} files failed to process")
        
        # Format statistics
        if analysis_data.format_counts:
            top_formats = analysis_data.get_top_formats(3)
            if top_formats:
                format_str = ", ".join([f"{fmt}: {count}" for fmt, count in top_formats])
                details.append(f"✓ Top formats: {format_str}")
        
        # Performance metrics
        if analysis_data.processing_time_seconds > 0:
            details.append(f"✓ Processing time: {analysis_data.get_processing_time_string()}")
            
            if analysis_data.files_per_second > 0:
                details.append(f"✓ Speed: {analysis_data.files_per_second:.1f} files/second")
        
        # Total media duration
        if analysis_data.total_duration_seconds > 0:
            details.append(f"✓ Total media duration: {analysis_data.get_total_duration_string()}")
        
        # Total file size
        if analysis_data.total_file_size_bytes > 0:
            size_gb = analysis_data.get_total_size_gb()
            if size_gb >= 1.0:
                details.append(f"✓ Total size: {size_gb:.2f} GB")
            else:
                size_mb = analysis_data.total_file_size_bytes / (1024**2)
                details.append(f"✓ Total size: {size_mb:.1f} MB")
        
        # Report generation
        if analysis_data.report_path:
            details.append(f"✓ Report saved: {analysis_data.report_path.name}")
        
        if analysis_data.csv_path:
            details.append(f"✓ CSV exported: {analysis_data.csv_path.name}")
        
        # Build metadata
        metadata = {
            'operation_type': 'media_analysis',
            'total_files': analysis_data.total_files,
            'media_files': analysis_data.media_files_found,
            'success_rate': analysis_data.get_success_rate(),
            'processing_time': analysis_data.processing_time_seconds
        }
        
        # Add output location if report was generated
        output_location = None
        if analysis_data.report_path:
            output_location = str(analysis_data.report_path.parent)
        
        return SuccessMessageData(
            title="Media Analysis Complete! 🎬",
            summary_lines=[primary_message] + details,
            output_location=output_location,
            celebration_emoji="🎉",
            performance_data={
                'files_per_second': analysis_data.files_per_second,
                'processing_time': analysis_data.processing_time_seconds
            },
            raw_data=metadata
        )
    
    def build_exiftool_success_message(
        self,
        exiftool_data: ExifToolOperationData
    ) -> SuccessMessageData:
        """
        Build success message for ExifTool metadata extraction.
        
        Args:
            exiftool_data: ExifTool operation data
            
        Returns:
            SuccessMessageData configured for ExifTool success
        """
        # Build primary message
        primary_message = f"ExifTool extracted metadata from {exiftool_data.successful} files"
        
        # Build details list
        details = []
        
        # Analysis statistics
        details.append(f"✓ Processed {exiftool_data.total_files} total files")
        
        if exiftool_data.failed > 0:
            details.append(f"⚠️ Failed to process {exiftool_data.failed} files")
        
        # GPS and location data
        if exiftool_data.gps_count > 0:
            details.append(f"📍 Found GPS data in {exiftool_data.gps_count} files")
            if exiftool_data.unique_locations > 0:
                details.append(f"📍 {exiftool_data.unique_locations} unique locations identified")
        
        # Device information
        if exiftool_data.device_count > 0:
            details.append(f"📱 Identified {exiftool_data.device_count} unique devices")
            
            # Show top devices
            top_devices = exiftool_data.get_top_devices(2)
            for device, count in top_devices:
                details.append(f"  • {device}: {count} files")
        
        # Date range
        date_range = exiftool_data.get_date_range_string()
        if date_range != "No dates found":
            details.append(f"📅 Date range: {date_range}")
        
        # Forensic findings
        if exiftool_data.has_forensic_findings:
            details.append("")  # Spacing
            details.append("🔍 Forensic Findings:")
            
            if exiftool_data.clock_skew_detected > 0:
                details.append(f"  • Clock skew detected in {exiftool_data.clock_skew_detected} files")
            
            if exiftool_data.metadata_tampering_detected > 0:
                details.append(f"  • Potential tampering in {exiftool_data.metadata_tampering_detected} files")
            
            if exiftool_data.edited_files > 0:
                details.append(f"  • {exiftool_data.edited_files} files show editing history")
        
        # Thumbnails
        if exiftool_data.thumbnail_count > 0:
            details.append(f"✓ Extracted {exiftool_data.thumbnail_count} thumbnails")
        
        # Processing time
        time_str = exiftool_data.get_processing_time_string()
        details.append(f"⏱️ Processing time: {time_str}")
        
        # Export information
        if exiftool_data.csv_path:
            details.append(f"✓ CSV exported: {exiftool_data.csv_path.name}")
        
        if exiftool_data.kml_path:
            details.append(f"✓ KML exported: {exiftool_data.kml_path.name}")
        
        # Build metadata
        metadata = {
            'operation_type': 'exiftool_analysis',
            'total_files': exiftool_data.total_files,
            'successful': exiftool_data.successful,
            'gps_count': exiftool_data.gps_count,
            'device_count': exiftool_data.device_count,
            'success_rate': exiftool_data.get_success_rate()
        }
        
        # Add output location if exports were created
        output_location = None
        if exiftool_data.csv_path:
            output_location = str(exiftool_data.csv_path.parent)
        elif exiftool_data.kml_path:
            output_location = str(exiftool_data.kml_path.parent)
        
        # Choose emoji based on findings
        if exiftool_data.has_forensic_findings:
            emoji = "🔍"  # Forensic findings detected
        elif exiftool_data.gps_count > 0:
            emoji = "📍"  # GPS data found
        else:
            emoji = "📷"  # Standard metadata extraction
        
        return SuccessMessageData(
            title="ExifTool Analysis Complete!",
            summary_lines=[primary_message] + details,
            output_location=output_location,
            celebration_emoji=emoji,
            performance_data={
                'files_per_second': exiftool_data.files_per_second,
                'processing_time': exiftool_data.processing_time
            },
            raw_data=metadata
        )
    
    def _get_report_display_name(self, report_type: str) -> str:
        """Convert report type to display-friendly name."""
        display_names = {
            'time_offset': 'Time Offset Report',
            'technician_log': 'Technician Log',
            'hash_csv': 'Hash Verification CSV',
            'upload_log': 'Upload Log',
            'processing_summary': 'Processing Summary'
        }
        
        return display_names.get(report_type, report_type.replace('_', ' ').title())