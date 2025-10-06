"""
Batch Processor Service for handling multiple file operations.

This service manages batch processing of video files, coordinating parsing,
frame rate detection, and SMPTE timecode writing using injected services.
"""

import os
import time
from typing import List, Optional, Callable, Dict, Any
from datetime import datetime
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

            if not parse_result.is_success:
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

            # Step 2: Write metadata
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

            if not write_result.is_success:
                return ProcessingResult(
                    source_file=str(file_path),
                    filename=file_path.name,
                    status=ProcessingStatus.FAILED,
                    success=False,
                    frame_rate=fps,
                    parsed_time=parsed.time_data.time_string,
                    smpte_timecode=parsed.smpte_timecode,
                    pattern_used=parsed.pattern.name,
                    error_message=write_result.error.user_message if write_result.error else "Write failed",
                    start_time=start_time,
                    end_time=datetime.now(),
                )

            output_path = write_result.value

            # Success
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
                time_offset_applied=parsed.time_offset_applied,
                time_offset_direction=parsed.time_offset_direction,
                time_offset_hours=parsed.time_offset_hours,
                time_offset_minutes=parsed.time_offset_minutes,
                time_offset_seconds=parsed.time_offset_seconds,
                processing_time=processing_time,
                start_time=start_time,
                end_time=end_time,
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
