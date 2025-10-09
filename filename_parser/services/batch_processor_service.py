"""
Batch Processor Service for handling multiple file operations.

This service manages batch processing of video files, coordinating parsing,
frame rate detection, and SMPTE timecode writing using injected services.
"""

import os
import time
import re
from typing import List, Optional, Callable, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

from core.services.base_service import BaseService
from core.result_types import Result
from core.exceptions import ValidationError, FileOperationError

from filename_parser.filename_parser_interfaces import (
    IBatchProcessorService,
    IFilenameParserService,
    IFrameRateService,
    IFFmpegMetadataWriterService,
)
from filename_parser.models.filename_parser_models import FilenameParserSettings
from filename_parser.models.processing_result import (
    ProcessingResult,
    ProcessingStatistics,
    ProcessingStatus,
)
from filename_parser.services.csv_export_service import CSVExportService
from filename_parser.services.video_metadata_extractor import VideoMetadataExtractor


class BatchProcessorService(BaseService, IBatchProcessorService):
    """
    Service for batch processing multiple video files.

    Coordinates filename parsing, frame rate detection, and metadata writing
    for multiple files with progress tracking and comprehensive error handling.
    """

    def __init__(
        self,
        parser_service: IFilenameParserService,
        frame_rate_service: IFrameRateService,
        metadata_writer_service: IFFmpegMetadataWriterService,
        csv_export_service: CSVExportService,
    ):
        """
        Initialize batch processor with service dependencies.

        Args:
            parser_service: Filename parser service
            frame_rate_service: Frame rate detection service
            metadata_writer_service: FFmpeg metadata writer service
            csv_export_service: CSV export service
        """
        super().__init__("BatchProcessorService")

        # Injected services
        self._parser_service = parser_service
        self._frame_rate_service = frame_rate_service
        self._metadata_writer_service = metadata_writer_service
        self._csv_export_service = csv_export_service

        # NEW: Video metadata extractor for timeline rendering
        self._metadata_extractor = VideoMetadataExtractor()

        # Processing state
        self._processing = False
        self._cancelled = False

    def process_files(
        self,
        files: List[Path],
        settings: FilenameParserSettings,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Result[ProcessingStatistics]:
        """
        Process multiple files in batch mode.

        Args:
            files: List of video file paths to process
            settings: Processing settings
            progress_callback: Optional callback(percentage, message)

        Returns:
            Result containing ProcessingStatistics or error
        """
        if not files:
            return Result.error(
                ValidationError(
                    "No files provided for batch processing",
                    user_message="Please select files to process.",
                    context={"file_count": 0}
                )
            )

        if self._processing:
            return Result.error(
                ValidationError(
                    "Batch processing already in progress",
                    user_message="A batch operation is already running. Please wait for it to complete.",
                    context={}
                )
            )

        # Validate services are available
        if not self._parser_service:
            return Result.error(
                FileOperationError(
                    "Parser service not available",
                    user_message="Filename parser service is not configured.",
                    context={}
                )
            )

        if not self._metadata_writer_service or not self._metadata_writer_service.is_ffmpeg_available():
            return Result.error(
                FileOperationError(
                    "FFmpeg not available",
                    user_message="FFmpeg is required for batch processing. Please install FFmpeg.",
                    context={}
                )
            )

        try:
            self._processing = True
            self._cancelled = False
            start_time = time.time()

            self.logger.info(f"Starting batch processing of {len(files)} files")

            # Step 1: Detect frame rates if needed
            fps_map = {}
            if settings.detect_fps and not settings.fps_override:
                self.logger.info("Detecting frame rates...")
                if progress_callback:
                    progress_callback(5, "Detecting frame rates...")

                fps_map = self._frame_rate_service.detect_batch_frame_rates(
                    files,
                    use_default_on_failure=True,
                    progress_callback=lambda curr, total: self._emit_progress(
                        curr, total, len(files), 5, 20, progress_callback, "Detecting frame rates"
                    ),
                )
                self.logger.info(f"Frame rate detection complete: {len(fps_map)} files")

            # Step 2: Parse filenames and process files
            results = []
            processed_count = 0
            error_count = 0

            for i, file_path in enumerate(files):
                if self._cancelled:
                    self.logger.info("Batch processing cancelled by user")
                    break

                # Update progress
                progress_pct = 20 + int((i / len(files)) * 70)  # 20-90%
                if progress_callback:
                    progress_callback(progress_pct, f"Processing: {file_path.name}")

                # Process single file
                result = self._process_single_file(
                    file_path,
                    settings,
                    fps_map.get(str(file_path), settings.fps_override or 29.97),
                )

                results.append(result)
                if result.success:
                    processed_count += 1
                else:
                    error_count += 1
                    self.logger.warning(f"Failed to process {file_path.name}: {result.error_message}")

            # Step 3: Export CSV if requested
            csv_path = None
            if settings.export_csv and results:
                if progress_callback:
                    progress_callback(90, "Exporting CSV...")

                csv_success, csv_path = self._csv_export_service.export_results(
                    [r.to_dict() for r in results],
                    str(settings.csv_output_path) if settings.csv_output_path else None,
                    include_metadata=True,
                )
                if csv_success:
                    self.logger.info(f"CSV exported to: {csv_path}")
                else:
                    self.logger.warning(f"CSV export failed: {csv_path}")

            # Build statistics
            end_time = time.time()
            stats = ProcessingStatistics()
            stats.calculate_from_results(results)
            stats.start_time = datetime.fromtimestamp(start_time)
            stats.end_time = datetime.fromtimestamp(end_time)

            if progress_callback:
                progress_callback(100, "Complete")

            self.logger.info(
                f"Batch processing complete: {processed_count} success, {error_count} errors"
            )

            return Result.success(stats)

        except Exception as e:
            self.logger.error(f"Unexpected error during batch processing: {e}", exc_info=True)
            return Result.error(
                FileOperationError(
                    f"Unexpected error during batch processing: {e}",
                    user_message="An unexpected error occurred during batch processing.",
                    context={"error": str(e)}
                )
            )
        finally:
            self._processing = False

    def _process_single_file(
        self,
        file_path: Path,
        settings: FilenameParserSettings,
        fps: float,
    ) -> ProcessingResult:
        """
        Process a single file.

        Args:
            file_path: Path to video file
            settings: Processing settings
            fps: Frame rate to use

        Returns:
            ProcessingResult for this file
        """
        start_time = datetime.now()

        try:
            # Step 1: Parse filename
            parse_result = self._parser_service.parse_filename(
                file_path.name,
                pattern_id=settings.pattern_id,
                fps=fps,
                time_offset=settings.get_time_offset_dict(),
            )

            if not parse_result.success:
                return ProcessingResult(
                    source_file=str(file_path),
                    filename=file_path.name,
                    status=ProcessingStatus.FAILED,
                    success=False,
                    frame_rate=fps,
                    error_message=parse_result.error.user_message if parse_result.error else "Parse failed",
                    start_time=start_time,
                    end_time=datetime.now(),
                )

            parsed = parse_result.value

            # Step 2: Extract full video metadata using VideoMetadataExtractor
            video_probe_data = self._metadata_extractor.extract_metadata(file_path)

            # Step 3: Extract date components from parsed filename
            date_tuple = None
            if parsed.time_data.year and parsed.time_data.month and parsed.time_data.day:
                date_tuple = (
                    parsed.time_data.year,
                    parsed.time_data.month,
                    parsed.time_data.day
                )
                self.logger.info(
                    f"{file_path.name}: Extracted date {parsed.time_data.year}-"
                    f"{parsed.time_data.month:02d}-{parsed.time_data.day:02d}"
                )

            # Step 4: Calculate timeline timestamps (ISO8601)
            start_time_iso = self._smpte_to_iso8601(parsed.smpte_timecode, fps, date_tuple)
            end_time_iso = self._calculate_end_time_iso(start_time_iso, video_probe_data.duration_seconds)

            # Step 4: Extract camera ID
            camera_id = self._extract_camera_id(file_path)

            # Step 5: Write metadata (ONLY if write_metadata is True)
            output_path = None
            if settings.write_metadata:
                project_root = None
                if settings.use_mirrored_structure and settings.base_output_directory:
                    # Use parent of file as project root (simplified)
                    project_root = str(file_path.parent)

                write_result = self._metadata_writer_service.write_smpte_metadata(
                    file_path,
                    parsed.smpte_timecode,
                    fps,
                    project_root,
                )

                if not write_result.success:
                    return ProcessingResult(
                        source_file=str(file_path),
                        filename=file_path.name,
                        status=ProcessingStatus.FAILED,
                        success=False,
                        frame_rate=fps,
                        parsed_time=parsed.time_data.time_string,
                        smpte_timecode=parsed.smpte_timecode,
                        pattern_used=parsed.pattern.name,
                        year=parsed.time_data.year,
                        month=parsed.time_data.month,
                        day=parsed.time_data.day,
                        error_message=write_result.error.user_message if write_result.error else "Write failed",
                        start_time=start_time,
                        end_time=datetime.now(),
                    )

                output_path = write_result.value

            # Success - return complete metadata for timeline rendering
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            return ProcessingResult(
                source_file=str(file_path),
                filename=file_path.name,
                status=ProcessingStatus.SUCCESS,
                success=True,
                output_file=str(output_path),
                frame_rate=fps,
                parsed_time=parsed.time_data.time_string,
                smpte_timecode=parsed.smpte_timecode,
                pattern_used=parsed.pattern.name,
                year=parsed.time_data.year,
                month=parsed.time_data.month,
                day=parsed.time_data.day,
                time_offset_applied=parsed.time_offset_applied,
                time_offset_direction=parsed.time_offset_direction,
                time_offset_hours=parsed.time_offset_hours,
                time_offset_minutes=parsed.time_offset_minutes,
                time_offset_seconds=parsed.time_offset_seconds,
                processing_time=processing_time,
                start_time=start_time,
                end_time=end_time,
                # NEW: Full video metadata for timeline rendering
                duration_seconds=video_probe_data.duration_seconds,
                start_time_iso=start_time_iso,
                end_time_iso=end_time_iso,
                camera_id=camera_id,
                width=video_probe_data.width,
                height=video_probe_data.height,
                codec=video_probe_data.codec_name,
                pixel_format=video_probe_data.pixel_format,
                video_bitrate=video_probe_data.bit_rate or 0,
            )

        except Exception as e:
            self.logger.error(f"Error processing {file_path.name}: {e}")
            return ProcessingResult(
                source_file=str(file_path),
                filename=file_path.name,
                status=ProcessingStatus.FAILED,
                success=False,
                frame_rate=fps,
                error_message=str(e),
                start_time=start_time,
                end_time=datetime.now(),
            )

    def cancel_processing(self):
        """Cancel current batch processing."""
        if self._processing:
            self._cancelled = True
            self.logger.info("Cancellation requested")

    def is_processing(self) -> bool:
        """Check if batch processing is currently running."""
        return self._processing

    def _emit_progress(
        self,
        current: int,
        total: int,
        file_count: int,
        start_pct: int,
        end_pct: int,
        callback: Optional[Callable],
        message: str,
    ):
        """
        Emit progress within a range.

        Args:
            current: Current item
            total: Total items
            file_count: Total file count
            start_pct: Starting percentage
            end_pct: Ending percentage
            callback: Progress callback
            message: Progress message
        """
        if callback and total > 0:
            pct_range = end_pct - start_pct
            pct = start_pct + int((current / total) * pct_range)
            callback(pct, f"{message}: {current}/{file_count}")

    def _extract_camera_id(self, file_path: Path) -> str:
        """
        Extract camera identifier from path or filename.

        Strategies (in priority order):
        1. Check parent directory name (e.g., "A02", "Camera_1")
        2. Check filename prefix (e.g., "A02_20250521.mp4")
        3. Fall back to parent directory path

        Examples:
            D:/footage/A02/A02_file.mp4 → "A02"
            D:/footage/Camera_1/video.mp4 → "Camera_1"
            D:/footage/20250521/file.mp4 → "20250521"

        Args:
            file_path: Path to video file

        Returns:
            Camera identifier string
        """
        # Strategy 1: Parent directory name
        parent_name = file_path.parent.name

        # Check if parent looks like camera ID (2-4 chars, alphanumeric)
        if re.match(r'^[A-Z]\d{2,3}$', parent_name):
            return parent_name

        # Check if parent contains "Camera" or "Cam"
        if 'camera' in parent_name.lower() or 'cam' in parent_name.lower():
            return parent_name

        # Strategy 2: Filename prefix
        filename = file_path.stem

        # Check for pattern like "A02_" at start
        match = re.match(r'^([A-Z]\d{2,3})_', filename)
        if match:
            return match.group(1)

        # Strategy 3: Fall back to parent directory name
        return parent_name

    def _smpte_to_iso8601(
        self,
        smpte_timecode: str,
        fps: float,
        date_components: Optional[tuple[int, int, int]] = None
    ) -> str:
        """
        Convert SMPTE timecode to ISO8601 string.

        Args:
            smpte_timecode: SMPTE format (HH:MM:SS:FF)
            fps: Frame rate for frame-to-second conversion
            date_components: Optional (year, month, day) tuple from filename parsing

        Returns:
            ISO8601 string (e.g., "2025-05-21T14:30:25.500")

        Note:
            If date_components not provided, falls back to system date with warning.
        """
        try:
            parts = smpte_timecode.split(":")
            if len(parts) != 4:
                self.logger.warning(f"Invalid SMPTE format: {smpte_timecode}, using as-is")
                return smpte_timecode

            hours, minutes, seconds, frames = map(int, parts)

            # Convert frames to decimal seconds
            frame_seconds = frames / fps if fps > 0 else 0

            # Create datetime using extracted date or system date fallback
            if date_components:
                year, month, day = date_components
                dt = datetime(year, month, day, hours, minutes, seconds)
                self.logger.debug(f"Using extracted date: {year}-{month:02d}-{day:02d}")
            else:
                # Fallback for files without date (legacy support)
                today = datetime.now().date()
                dt = datetime.combine(today, datetime.min.time())
                dt = dt.replace(hour=hours, minute=minutes, second=seconds)
                self.logger.warning(
                    f"No date extracted from filename, using system date: {today} "
                    f"(this may be incorrect for forensic analysis)"
                )

            dt = dt + timedelta(seconds=frame_seconds)

            return dt.isoformat()

        except Exception as e:
            self.logger.warning(f"Error converting SMPTE {smpte_timecode}: {e}")
            return smpte_timecode

    def _calculate_end_time_iso(self, start_iso: str, duration_seconds: float) -> str:
        """
        Calculate end time from start time + duration.

        Args:
            start_iso: ISO8601 start time
            duration_seconds: Duration in seconds

        Returns:
            ISO8601 end time
        """
        try:
            start_dt = datetime.fromisoformat(start_iso)
            end_dt = start_dt + timedelta(seconds=duration_seconds)
            return end_dt.isoformat()
        except Exception as e:
            self.logger.warning(f"Error calculating end time: {e}")
            return start_iso
