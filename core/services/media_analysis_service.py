#!/usr/bin/env python3
"""
Media Analysis Service - Business logic for media file analysis
Implements IMediaAnalysisService interface with full SOA compliance
"""

import time
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from .interfaces import IMediaAnalysisService
from .base_service import BaseService
from ..models import FormData
from ..media_analysis_models import (
    MediaAnalysisSettings, MediaAnalysisResult, MediaMetadata
)
from ..result_types import Result
from ..exceptions import (
    ValidationError, MediaAnalysisError, FFProbeNotFoundError,
    MediaExtractionError, MediaReportError
)
from ..media.ffprobe_binary_manager import FFProbeBinaryManager
from ..media.ffprobe_wrapper import FFProbeWrapper
from ..media.metadata_normalizer import MetadataNormalizer
from ..logger import logger


class MediaAnalysisService(BaseService, IMediaAnalysisService):
    """Service for media analysis operations"""
    
    def __init__(self):
        """Initialize media analysis service"""
        super().__init__("MediaAnalysisService")
        
        # Initialize FFprobe components
        self.ffprobe_manager = FFProbeBinaryManager()
        self.ffprobe_wrapper = None
        self.normalizer = MetadataNormalizer()
        
        # Initialize FFprobe wrapper if binary is available
        if self.ffprobe_manager.is_available():
            try:
                self.ffprobe_wrapper = FFProbeWrapper(
                    self.ffprobe_manager.get_binary_path()
                )
                logger.info(f"MediaAnalysisService initialized with FFprobe at {self.ffprobe_manager.binary_path}")
            except Exception as e:
                logger.error(f"Failed to initialize FFprobe wrapper: {e}")
                self.ffprobe_wrapper = None
        else:
            logger.warning("MediaAnalysisService initialized without FFprobe - media analysis unavailable")
    
    def validate_media_files(self, paths: List[Path]) -> Result[List[Path]]:
        """
        Validate and filter media files from provided paths
        
        Args:
            paths: List of file/folder paths to validate
            
        Returns:
            Result containing list of valid file paths or error
        """
        try:
            # Check FFprobe availability first
            if not self.ffprobe_wrapper:
                return Result.error(
                    FFProbeNotFoundError(
                        "FFprobe not available",
                        user_message="FFprobe is required for media analysis. Please install FFmpeg."
                    )
                )
            
            # Validate input
            if not paths:
                return Result.error(
                    ValidationError(
                        {"paths": "No files or folders specified"},
                        user_message="Please select files or folders to analyze."
                    )
                )
            
            # Collect all files (expand directories)
            valid_files = []
            for path in paths:
                if not path.exists():
                    logger.warning(f"Path does not exist: {path}")
                    continue
                
                if path.is_file():
                    valid_files.append(path)
                elif path.is_dir():
                    # Recursively find all files in directory
                    # Common media extensions for faster filtering (optional)
                    media_extensions = {
                        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm',
                        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a',
                        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff',
                        '.3gp', '.m4v', '.mpg', '.mpeg', '.vob', '.ts', '.mts'
                    }
                    
                    for file_path in path.rglob('*'):
                        if file_path.is_file():
                            # Optionally filter by extension for performance
                            # But FFprobe can identify any media file
                            valid_files.append(file_path)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_files = []
            for f in valid_files:
                if f not in seen:
                    seen.add(f)
                    unique_files.append(f)
            
            if not unique_files:
                return Result.error(
                    ValidationError(
                        {"paths": "No valid files found"},
                        user_message="No files found in the selected items."
                    )
                )
            
            self._log_operation("validate_media_files", f"Found {len(unique_files)} files to analyze")
            return Result.success(unique_files)
            
        except Exception as e:
            error = MediaAnalysisError(
                f"Failed to validate media files: {e}",
                user_message="Failed to validate selected files."
            )
            self._handle_error(error)
            return Result.error(error)
    
    def analyze_media_files(
        self,
        files: List[Path],
        settings: MediaAnalysisSettings,
        progress_callback: Optional[Callable] = None
    ) -> Result[MediaAnalysisResult]:
        """
        Analyze media files and extract metadata
        
        Args:
            files: List of media file paths to analyze
            settings: Analysis settings and field preferences
            progress_callback: Optional callback for progress updates
            
        Returns:
            Result containing MediaAnalysisResult or error
        """
        try:
            if not self.ffprobe_wrapper:
                return Result.error(
                    FFProbeNotFoundError(
                        "FFprobe not available for analysis"
                    )
                )
            
            if not files:
                return Result.error(
                    ValidationError(
                        {"files": "No files to analyze"},
                        user_message="No files provided for analysis."
                    )
                )
            
            self._log_operation("analyze_media_files", f"Starting analysis of {len(files)} files")
            start_time = time.time()
            
            # Extract metadata in parallel using FFprobe wrapper with optimized commands
            raw_results = self.ffprobe_wrapper.extract_batch(
                files,
                settings=settings,  # Pass settings for optimized extraction
                max_workers=settings.max_workers,
                progress_callback=progress_callback
            )
            
            # Process and normalize results
            metadata_list = []
            errors = []
            successful = 0
            failed = 0
            skipped = 0
            
            for file_path, extraction_result in raw_results.items():
                if extraction_result.success:
                    try:
                        raw_data = extraction_result.value
                        
                        # Check if frame data exists (for GOP analysis)
                        frame_data = raw_data.get('frames', [])
                        
                        # Normalize the raw metadata
                        normalized = self.normalizer.normalize(
                            raw_data,
                            file_path
                        )
                        
                        # Analyze frame data if present and enabled
                        if frame_data and hasattr(settings, 'frame_analysis_fields') and settings.frame_analysis_fields.enabled:
                            self.normalizer.analyze_frame_data(frame_data, normalized)
                        
                        # Add performance metrics if available
                        if '_extraction_time' in raw_data:
                            normalized.extraction_time = raw_data['_extraction_time']
                        if '_command_complexity' in raw_data:
                            normalized.command_complexity = raw_data['_command_complexity']
                        
                        # No need to filter fields - we only extracted what was requested!
                        # The command builder already optimized the extraction
                        
                        metadata_list.append(normalized)
                        successful += 1
                        
                    except Exception as e:
                        logger.warning(f"Failed to normalize metadata for {file_path.name}: {e}")
                        errors.append(f"{file_path.name}: Failed to process metadata")
                        failed += 1
                else:
                    # Check if it's a non-media file (expected) or actual error
                    error_msg = str(extraction_result.error)
                    if "not a valid media file" in error_msg.lower() or "not a media file" in error_msg.lower():
                        if not settings.skip_non_media:
                            # Include non-media files as skipped
                            errors.append(f"{file_path.name}: Not a media file")
                        skipped += 1
                        logger.debug(f"Skipped non-media file: {file_path.name}")
                    else:
                        # Actual error
                        errors.append(f"{file_path.name}: {extraction_result.error.user_message}")
                        failed += 1
                        logger.warning(f"Extraction error for {file_path.name}: {extraction_result.error}")
            
            processing_time = time.time() - start_time
            
            # Create result object
            result = MediaAnalysisResult(
                total_files=len(files),
                successful=successful,
                failed=failed,
                skipped=skipped,
                metadata_list=metadata_list,
                processing_time=processing_time,
                errors=errors[:100]  # Limit error list to prevent memory issues
            )
            
            self._log_operation("analyze_media_files", 
                              f"Analysis complete: {successful} successful, {failed} failed, {skipped} skipped")
            
            return Result.success(result)
            
        except Exception as e:
            error = MediaAnalysisError(
                f"Media analysis failed: {e}",
                user_message="An error occurred during media analysis."
            )
            self._handle_error(error)
            return Result.error(error)
    
    def generate_analysis_report(
        self,
        results: MediaAnalysisResult,
        output_path: Path,
        form_data: Optional[FormData] = None
    ) -> Result[Path]:
        """
        Generate PDF report from analysis results using ReportLab
        
        Args:
            results: Media analysis results to report
            output_path: Path where report should be saved
            form_data: Optional form data for case information
            
        Returns:
            Result containing report path or error
        """
        try:
            # Import ReportLab components
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create document
            doc = SimpleDocTemplate(str(output_path), pagesize=letter)
            story = []
            styles = getSampleStyleSheet()
            
            # Add custom styles
            styles.add(ParagraphStyle(
                name='CustomTitle',
                parent=styles['Title'],
                fontSize=16,
                spaceAfter=12,
                alignment=1  # Center
            ))
            
            styles.add(ParagraphStyle(
                name='CustomHeader',
                parent=styles['Heading2'],
                fontSize=12,
                textColor=colors.HexColor('#003366'),
                spaceAfter=6
            ))
            
            # Title
            story.append(Paragraph("Media Analysis Report", styles['CustomTitle']))
            story.append(Spacer(1, 0.2*inch))
            
            # Add timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            story.append(Paragraph(f"Generated: {timestamp}", styles['Normal']))
            story.append(Spacer(1, 0.3*inch))
            
            # Analysis Summary
            story.append(Paragraph("Analysis Summary", styles['CustomHeader']))
            
            summary = results.get_summary()
            summary_data = [
                ['Total Files Analyzed:', str(summary['total_files'])],
                ['Media Files Found:', str(summary['successful'])],
                ['Non-Media Files:', str(summary['skipped'])],
                ['Failed:', str(summary['failed'])],
                ['Processing Time:', f"{summary['processing_time']:.1f} seconds"],
                ['Success Rate:', f"{summary['success_rate']:.1f}%"]
            ]
            
            summary_table = Table(summary_data, colWidths=[2*inch, 4*inch])
            summary_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Format statistics
            format_stats = results.get_format_statistics()
            if format_stats:
                story.append(Paragraph("File Formats", styles['CustomHeader']))
                
                format_data = [[format_name, f"{count} files"] 
                              for format_name, count in sorted(format_stats.items())]
                
                if format_data:
                    format_table = Table(format_data, colWidths=[2*inch, 4*inch])
                    format_table.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ]))
                    story.append(format_table)
                    story.append(Spacer(1, 0.2*inch))
            
            # Codec statistics
            codec_stats = results.get_codec_statistics()
            if codec_stats.get('video_codecs'):
                story.append(Paragraph("Video Codecs", styles['CustomHeader']))
                
                video_data = [[codec, f"{count} files"] 
                             for codec, count in sorted(codec_stats['video_codecs'].items())]
                
                if video_data:
                    video_table = Table(video_data, colWidths=[2*inch, 4*inch])
                    video_table.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ]))
                    story.append(video_table)
                    story.append(Spacer(1, 0.2*inch))
            
            if codec_stats.get('audio_codecs'):
                story.append(Paragraph("Audio Codecs", styles['CustomHeader']))
                
                audio_data = [[codec, f"{count} files"] 
                             for codec, count in sorted(codec_stats['audio_codecs'].items())]
                
                if audio_data:
                    audio_table = Table(audio_data, colWidths=[2*inch, 4*inch])
                    audio_table.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ]))
                    story.append(audio_table)
                    story.append(Spacer(1, 0.2*inch))
            
            # File details (limited to prevent huge PDFs)
            if results.metadata_list:
                story.append(Paragraph("File Details", styles['CustomHeader']))
                
                # Create table data for file details
                file_detail_data = []
                for metadata in results.metadata_list[:50]:  # Limit to 50 files
                    # File name row
                    file_detail_data.append([
                        Paragraph(f"<b>{metadata.file_path.name}</b>", styles['Normal']),
                        ''
                    ])
                    
                    # Format (only if available)
                    if metadata.format:
                        file_detail_data.append([
                            '  Format:',
                            metadata.format
                        ])
                    
                    # Size (separate line)
                    file_detail_data.append([
                        '  Size:',
                        metadata.get_file_size_string()
                    ])
                    
                    # Duration (only if available)
                    if metadata.duration:
                        file_detail_data.append([
                            '  Duration:',
                            metadata.get_duration_string()
                        ])
                    
                    # Video info - broken down into separate lines
                    if metadata.has_video:
                        # Video codec
                        if metadata.video_codec:
                            file_detail_data.append([
                                '  Video Codec:',
                                metadata.video_codec
                            ])
                        
                        # Resolution
                        if metadata.resolution:
                            file_detail_data.append([
                                '  Resolution:',
                                metadata.get_resolution_string()
                            ])
                        
                        # Frame rate
                        if metadata.frame_rate:
                            file_detail_data.append([
                                '  Frame Rate:',
                                f"{metadata.frame_rate:.1f} fps"
                            ])
                    
                    # Audio info
                    if metadata.has_audio and metadata.audio_codec:
                        audio_info = f"{metadata.audio_codec}"
                        if metadata.sample_rate:
                            audio_info += f" @ {metadata.sample_rate} Hz"
                        if metadata.channel_layout:
                            audio_info += f" ({metadata.channel_layout})"
                        file_detail_data.append(['  Audio:', audio_info])
                    
                    # Enhanced Aspect Ratios (NEW)
                    if metadata.display_aspect_ratio:
                        file_detail_data.append(['  Display Aspect Ratio:', metadata.display_aspect_ratio])
                    if metadata.sample_aspect_ratio:
                        file_detail_data.append(['  Sample Aspect Ratio:', metadata.sample_aspect_ratio])
                    if metadata.pixel_aspect_ratio:
                        file_detail_data.append(['  Pixel Aspect Ratio:', metadata.pixel_aspect_ratio])
                    
                    # Color Information
                    if metadata.color_space:
                        file_detail_data.append(['  Color Space:', metadata.color_space])
                    if metadata.color_range:
                        file_detail_data.append(['  Color Range:', metadata.color_range])
                    if metadata.color_transfer:
                        file_detail_data.append(['  Color Transfer:', metadata.color_transfer])
                    if metadata.color_primaries:
                        file_detail_data.append(['  Color Primaries:', metadata.color_primaries])
                    
                    # Advanced Video Properties
                    if metadata.profile:
                        file_detail_data.append(['  Profile:', metadata.profile])
                    if metadata.level:
                        file_detail_data.append(['  Level:', metadata.level])
                    if metadata.pixel_format:
                        file_detail_data.append(['  Pixel Format:', metadata.pixel_format])
                    
                    # Bitrate Information
                    if metadata.bitrate:
                        file_detail_data.append(['  Overall Bitrate:', f"{metadata.bitrate:,} bps"])
                    if metadata.video_bitrate:
                        file_detail_data.append(['  Video Bitrate:', f"{metadata.video_bitrate:,} bps"])
                    if metadata.audio_bitrate:
                        file_detail_data.append(['  Audio Bitrate:', f"{metadata.audio_bitrate:,} bps"])
                    
                    # Audio Details
                    if metadata.bit_depth:
                        file_detail_data.append(['  Audio Bit Depth:', f"{metadata.bit_depth} bits"])
                    
                    # GOP Structure & Frame Analysis (NEW)
                    if metadata.gop_size:
                        file_detail_data.append(['  GOP Size:', str(metadata.gop_size)])
                    if metadata.keyframe_interval:
                        file_detail_data.append(['  Keyframe Interval:', f"{metadata.keyframe_interval:.2f} seconds"])
                    if metadata.i_frame_count:
                        file_detail_data.append(['  I-Frames:', str(metadata.i_frame_count)])
                    if metadata.p_frame_count:
                        file_detail_data.append(['  P-Frames:', str(metadata.p_frame_count)])
                    if metadata.b_frame_count:
                        file_detail_data.append(['  B-Frames:', str(metadata.b_frame_count)])
                    
                    # Date Information
                    if metadata.creation_date:
                        file_detail_data.append(['  Creation Date:', metadata.creation_date.strftime("%Y-%m-%d %H:%M:%S")])
                    if metadata.modification_date:
                        file_detail_data.append(['  Modified Date:', metadata.modification_date.strftime("%Y-%m-%d %H:%M:%S")])
                    
                    # Location Information (if enabled)
                    if metadata.gps_latitude is not None and metadata.gps_longitude is not None:
                        file_detail_data.append(['  GPS Coordinates:', f"{metadata.gps_latitude:.6f}, {metadata.gps_longitude:.6f}"])
                    if metadata.location_name:
                        file_detail_data.append(['  Location:', metadata.location_name])
                    
                    # Device Information (if enabled)
                    if metadata.device_make:
                        file_detail_data.append(['  Device Make:', metadata.device_make])
                    if metadata.device_model:
                        file_detail_data.append(['  Device Model:', metadata.device_model])
                    if metadata.software:
                        file_detail_data.append(['  Software:', metadata.software])
                    
                    # Additional Metadata
                    if metadata.title:
                        file_detail_data.append(['  Title:', metadata.title])
                    if metadata.artist:
                        file_detail_data.append(['  Artist:', metadata.artist])
                    if metadata.album:
                        file_detail_data.append(['  Album:', metadata.album])
                    if metadata.comment:
                        # Limit comment length to prevent PDF overflow
                        comment_text = metadata.comment[:100] + "..." if len(metadata.comment) > 100 else metadata.comment
                        file_detail_data.append(['  Comment:', comment_text])
                    
                    # Add spacing between files
                    file_detail_data.append(['', ''])
                
                if file_detail_data:
                    detail_table = Table(file_detail_data, colWidths=[1.5*inch, 4.5*inch])
                    detail_table.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ]))
                    story.append(detail_table)
            
            # Errors section
            if results.errors:
                story.append(Spacer(1, 0.3*inch))
                story.append(Paragraph("Processing Errors", styles['CustomHeader']))
                
                error_text = '<br/>'.join([f"• {error}" for error in results.errors[:30]])
                story.append(Paragraph(error_text, styles['Normal']))
            
            # Build PDF
            doc.build(story)
            
            self._log_operation("generate_analysis_report", f"Report saved to {output_path}")
            return Result.success(output_path)
            
        except Exception as e:
            error = MediaReportError(
                f"Failed to generate PDF report: {e}",
                report_path=str(output_path),
                user_message="Failed to generate analysis report."
            )
            self._handle_error(error)
            return Result.error(error)
    
    def export_to_csv(
        self,
        results: MediaAnalysisResult,
        output_path: Path
    ) -> Result[Path]:
        """
        Export analysis results to CSV format
        
        Args:
            results: Media analysis results to export
            output_path: Path where CSV should be saved
            
        Returns:
            Result containing CSV path or error
        """
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Define CSV columns - now includes ALL fields
            fieldnames = [
                'File Path', 'File Name', 'File Size', 'Format', 'Duration',
                # Video Fields
                'Video Codec', 'Resolution', 'Frame Rate', 
                'Display Aspect Ratio', 'Sample Aspect Ratio', 'Pixel Aspect Ratio',
                'Color Space', 'Color Range', 'Color Transfer', 'Color Primaries',
                'Profile', 'Level', 'Pixel Format',
                # Bitrate Fields
                'Overall Bitrate', 'Video Bitrate', 'Audio Bitrate',
                # Audio Fields
                'Audio Codec', 'Sample Rate', 'Channels', 'Channel Layout', 'Bit Depth',
                # GOP Structure
                'GOP Size', 'Keyframe Interval', 'I-Frames', 'P-Frames', 'B-Frames',
                # Dates
                'Creation Date', 'Modification Date',
                # Device & Location
                'Device Make', 'Device Model', 'Software',
                'GPS Latitude', 'GPS Longitude', 'Location Name',
                # Additional Metadata
                'Title', 'Artist', 'Album', 'Comment'
            ]
            
            # Write CSV
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for metadata in results.metadata_list:
                    row = {
                        'File Path': str(metadata.file_path),
                        'File Name': metadata.file_path.name,
                        'File Size': metadata.get_file_size_string(),
                        'Format': metadata.format or '',
                        'Duration': metadata.get_duration_string(),
                        # Video Fields
                        'Video Codec': metadata.video_codec or '',
                        'Resolution': metadata.get_resolution_string() if metadata.resolution else '',
                        'Frame Rate': f"{metadata.frame_rate:.2f}" if metadata.frame_rate else '',
                        'Display Aspect Ratio': metadata.display_aspect_ratio or '',
                        'Sample Aspect Ratio': metadata.sample_aspect_ratio or '',
                        'Pixel Aspect Ratio': metadata.pixel_aspect_ratio or '',
                        'Color Space': metadata.color_space or '',
                        'Color Range': metadata.color_range or '',
                        'Color Transfer': metadata.color_transfer or '',
                        'Color Primaries': metadata.color_primaries or '',
                        'Profile': metadata.profile or '',
                        'Level': metadata.level or '',
                        'Pixel Format': metadata.pixel_format or '',
                        # Bitrate Fields
                        'Overall Bitrate': str(metadata.bitrate) if metadata.bitrate else '',
                        'Video Bitrate': str(metadata.video_bitrate) if metadata.video_bitrate else '',
                        'Audio Bitrate': str(metadata.audio_bitrate) if metadata.audio_bitrate else '',
                        # Audio Fields
                        'Audio Codec': metadata.audio_codec or '',
                        'Sample Rate': str(metadata.sample_rate) if metadata.sample_rate else '',
                        'Channels': str(metadata.channels) if metadata.channels else '',
                        'Channel Layout': metadata.channel_layout or '',
                        'Bit Depth': str(metadata.bit_depth) if metadata.bit_depth else '',
                        # GOP Structure
                        'GOP Size': str(metadata.gop_size) if metadata.gop_size else '',
                        'Keyframe Interval': f"{metadata.keyframe_interval:.2f}" if metadata.keyframe_interval else '',
                        'I-Frames': str(metadata.i_frame_count) if metadata.i_frame_count else '',
                        'P-Frames': str(metadata.p_frame_count) if metadata.p_frame_count else '',
                        'B-Frames': str(metadata.b_frame_count) if metadata.b_frame_count else '',
                        # Dates
                        'Creation Date': metadata.creation_date.isoformat() if metadata.creation_date else '',
                        'Modification Date': metadata.modification_date.isoformat() if metadata.modification_date else '',
                        # Device & Location
                        'Device Make': metadata.device_make or '',
                        'Device Model': metadata.device_model or '',
                        'Software': metadata.software or '',
                        'GPS Latitude': str(metadata.gps_latitude) if metadata.gps_latitude is not None else '',
                        'GPS Longitude': str(metadata.gps_longitude) if metadata.gps_longitude is not None else '',
                        'Location Name': metadata.location_name or '',
                        # Additional Metadata
                        'Title': metadata.title or '',
                        'Artist': metadata.artist or '',
                        'Album': metadata.album or '',
                        'Comment': metadata.comment[:100] if metadata.comment else ''
                    }
                    writer.writerow(row)
            
            self._log_operation("export_to_csv", f"CSV exported to {output_path}")
            return Result.success(output_path)
            
        except Exception as e:
            error = MediaReportError(
                f"Failed to export CSV: {e}",
                report_path=str(output_path),
                user_message="Failed to export results to CSV."
            )
            self._handle_error(error)
            return Result.error(error)
    
    def get_ffprobe_status(self) -> Dict[str, Any]:
        """
        Get FFprobe availability and version status
        
        Returns:
            Dictionary with ffprobe status information
        """
        return self.ffprobe_manager.get_status_info()