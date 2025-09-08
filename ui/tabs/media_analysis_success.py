#!/usr/bin/env python3
"""
Success message builder for media analysis operations.
This module is owned by the media analysis tab/plugin.
Handles both FFprobe and ExifTool success messages.
"""

from typing import Optional
from pathlib import Path
from core.services.success_message_data import (
    SuccessMessageData, 
    MediaAnalysisOperationData,
    ExifToolOperationData
)


class MediaAnalysisSuccessBuilder:
    """Builds success messages for media analysis operations"""
    
    def build_media_analysis_success_message(
        self, 
        analysis_data: MediaAnalysisOperationData
    ) -> SuccessMessageData:
        """
        Build success message for media analysis operations (FFprobe).
        
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
        
        # Total duration if available
        if analysis_data.total_duration_seconds > 0:
            duration_str = analysis_data.get_total_duration_string()
            details.append(f"✓ Total media duration: {duration_str}")
        
        # Total file size
        if analysis_data.total_file_size_bytes > 0:
            size_gb = analysis_data.get_total_size_gb()
            if size_gb >= 1:
                size_str = f"{size_gb:.2f} GB"
            else:
                size_mb = size_gb * 1024
                size_str = f"{size_mb:.2f} MB"
            details.append(f"✓ Total size: {size_str}")
        
        # Report/export information
        if analysis_data.report_path:
            details.append(f"📄 Report saved: {analysis_data.report_path.name}")
        
        if analysis_data.csv_path:
            details.append(f"📊 CSV exported: {analysis_data.csv_path.name}")
        
        # Determine output location
        output_location = None
        if analysis_data.report_path:
            output_location = str(analysis_data.report_path.parent)
        elif analysis_data.csv_path:
            output_location = str(analysis_data.csv_path.parent)
        
        # Choose appropriate title and emoji
        if analysis_data.failed_files > 0:
            title = "Media Analysis Complete (with errors)"
            emoji = "⚠️"
        else:
            title = "Media Analysis Complete!"
            emoji = "🎬"
        
        return SuccessMessageData(
            title=title,
            summary_lines=details,
            output_location=output_location,
            celebration_emoji=emoji,
            raw_data={'analysis_data': analysis_data}
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
        if exiftool_data.earliest_date and exiftool_data.latest_date:
            details.append(f"📅 Date range: {exiftool_data.earliest_date.strftime('%Y-%m-%d')} to {exiftool_data.latest_date.strftime('%Y-%m-%d')}")
        
        # Performance
        if exiftool_data.processing_time > 0:
            details.append(f"⏱️ Processing time: {exiftool_data.processing_time:.1f} seconds")
        
        # Choose appropriate title and emoji
        if exiftool_data.failed > 0:
            title = "ExifTool Analysis Complete (with errors)"
            emoji = "⚠️"
        elif exiftool_data.gps_count > 0:
            title = "ExifTool Analysis Complete - GPS Data Found!"
            emoji = "📍"
        else:
            title = "ExifTool Analysis Complete!"
            emoji = "📸"
        
        return SuccessMessageData(
            title=title,
            summary_lines=details,
            celebration_emoji=emoji,
            raw_data={'exiftool_data': exiftool_data}
        )
    
    @staticmethod
    def build_csv_export_success(
        file_path: Path,
        record_count: int,
        export_type: str = "Media Analysis"
    ) -> SuccessMessageData:
        """
        Create success message for CSV export.
        
        Args:
            file_path: Path where CSV was saved
            record_count: Number of records exported
            export_type: Type of export (Media Analysis or ExifTool)
            
        Returns:
            SuccessMessageData for CSV export success
        """
        summary_lines = [
            f"✓ Exported {record_count} records to CSV",
            f"📁 Location: {file_path.parent}",
            f"📄 File: {file_path.name}"
        ]
        
        # Add file size if available
        try:
            if file_path.exists():
                size_bytes = file_path.stat().st_size
                if size_bytes < 1024:
                    size_str = f"{size_bytes} bytes"
                elif size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                summary_lines.append(f"💾 Size: {size_str}")
        except:
            pass  # Ignore if we can't get file size
        
        return SuccessMessageData(
            title=f"{export_type} CSV Export Complete!",
            summary_lines=summary_lines,
            celebration_emoji="📊",
            output_location=str(file_path.parent),
            raw_data={
                'operation': 'csv_export',
                'file_path': str(file_path),
                'record_count': record_count,
                'export_type': export_type
            }
        )
    
    @staticmethod
    def build_kml_export_success(
        file_path: Path,
        location_count: int,
        device_count: Optional[int] = None
    ) -> SuccessMessageData:
        """
        Create success message for KML export.
        
        Args:
            file_path: Path where KML was saved
            location_count: Number of GPS locations exported
            device_count: Optional number of unique devices
            
        Returns:
            SuccessMessageData for KML export success
        """
        summary_lines = [
            f"✓ Exported {location_count} GPS locations to KML",
            f"📁 Location: {file_path.parent}",
            f"📄 File: {file_path.name}"
        ]
        
        if device_count:
            summary_lines.append(f"📱 Grouped by {device_count} devices")
        
        summary_lines.append("")
        summary_lines.append("💡 You can open this file in Google Earth")
        
        return SuccessMessageData(
            title="KML Export Complete!",
            summary_lines=summary_lines,
            celebration_emoji="🌍",
            output_location=str(file_path.parent),
            raw_data={
                'operation': 'kml_export',
                'file_path': str(file_path),
                'location_count': location_count,
                'device_count': device_count
            }
        )
    
    @staticmethod
    def build_pdf_report_success(
        file_path: Path,
        page_count: Optional[int] = None,
        media_count: int = 0
    ) -> SuccessMessageData:
        """
        Create success message for PDF report generation.
        
        Args:
            file_path: Path where PDF was saved
            page_count: Optional number of pages in report
            media_count: Number of media files analyzed
            
        Returns:
            SuccessMessageData for PDF report success
        """
        summary_lines = [
            f"✓ Generated PDF report for {media_count} media files",
            f"📁 Location: {file_path.parent}",
            f"📄 File: {file_path.name}"
        ]
        
        if page_count:
            summary_lines.append(f"📑 Pages: {page_count}")
        
        # Add file size if available
        try:
            if file_path.exists():
                size_bytes = file_path.stat().st_size
                if size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                summary_lines.append(f"💾 Size: {size_str}")
        except:
            pass
        
        return SuccessMessageData(
            title="Media Analysis Report Generated!",
            summary_lines=summary_lines,
            celebration_emoji="📄",
            output_location=str(file_path.parent),
            raw_data={
                'operation': 'pdf_report',
                'file_path': str(file_path),
                'media_count': media_count,
                'page_count': page_count
            }
        )