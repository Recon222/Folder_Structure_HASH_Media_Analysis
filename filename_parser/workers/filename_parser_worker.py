#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename Parser Worker - Thread handling for batch filename parsing operations.

This worker orchestrates the BatchProcessorService to parse multiple video files,
extract time information, and write SMPTE timecode metadata with parallel processing support.
"""

from typing import List
from pathlib import Path
import logging

from PySide6.QtCore import Signal

from core.workers.base_worker import BaseWorkerThread
from core.result_types import Result
from core.exceptions import FileOperationError

from filename_parser.models.filename_parser_models import FilenameParserSettings
from filename_parser.models.processing_result import ProcessingStatistics
from filename_parser.services.batch_processor_service import BatchProcessorService

# Module logger
logger = logging.getLogger(__name__)


class FilenameParserWorker(BaseWorkerThread):
    """
    Worker thread for batch filename parsing operations.

    Orchestrates the BatchProcessorService to parse multiple video files,
    extract time information, and write SMPTE timecode metadata with
    parallel processing support.

    Follows the unified signal pattern with Result-based error handling
    and proper cancellation support.
    """

    # Unified signal pattern (as per CLAUDE.md)
    result_ready = Signal(Result)  # Result[ProcessingStatistics]
    progress_update = Signal(int, str)  # (percentage, message)

    def __init__(
        self,
        files: List[Path],
        settings: FilenameParserSettings,
        batch_service: BatchProcessorService
    ):
        """
        Initialize the filename parser worker.

        Args:
            files: List of video file paths to process
            settings: Processing settings (pattern, FPS, time offset, etc.)
            batch_service: Injected batch processor service
        """
        super().__init__()

        self.files = files
        self.settings = settings
        self.batch_service = batch_service

        # Set descriptive operation name
        file_count = len(files) if files else 0
        self.set_operation_name(f"Filename Parsing ({file_count} files)")

    def execute(self) -> Result[ProcessingStatistics]:
        """
        Execute batch filename parsing operation.

        Orchestrates the BatchProcessorService to process all files,
        handling progress updates and cancellation gracefully.

        Returns:
            Result containing ProcessingStatistics with success/failure counts
            and individual file results, or error if operation failed
        """
        try:
            logger.info(f"Starting filename parsing for {len(self.files)} files")
            logger.debug(f"Settings: pattern_id={self.settings.pattern_id}, "
                            f"detect_fps={self.settings.detect_fps}, "
                            f"export_csv={self.settings.export_csv}")

            # Check for pause before starting
            self.check_pause()

            # Initial progress
            self.emit_progress(0, "Starting filename parsing...")

            # Call batch processor service with progress callback
            # The service handles all business logic including:
            # - Filename parsing
            # - Frame rate detection
            # - SMPTE timecode conversion
            # - FFmpeg metadata writing
            # - CSV export
            result = self.batch_service.process_files(
                self.files,
                self.settings,
                progress_callback=self._emit_progress
            )

            # Log results
            if result.success:
                stats = result.value
                logger.info(
                    f"Parsing complete: {stats.successful} successful, "
                    f"{stats.failed} failed, {stats.skipped} skipped"
                )
                logger.debug(
                    f"Performance: {stats.total_processing_time:.2f}s total, "
                    f"{stats.average_processing_time:.3f}s avg, "
                    f"{stats.files_per_second:.2f} files/s"
                )
            else:
                logger.error(f"Parsing failed: {result.error}")

            return result

        except Exception as e:
            logger.error(f"Unexpected error in filename parser worker: {e}", exc_info=True)
            return Result.error(
                FileOperationError(
                    f"Unexpected error during filename parsing: {e}",
                    user_message="An unexpected error occurred during filename parsing.",
                    context={
                        "file_count": len(self.files),
                        "error": str(e),
                        "pattern_id": self.settings.pattern_id
                    }
                )
            )

    def _emit_progress(self, percentage: int, message: str):
        """
        Emit progress update signal and check for cancellation.

        This method is passed as a callback to the BatchProcessorService,
        allowing it to report progress back to the UI thread.

        Args:
            percentage: Progress percentage (0-100)
            message: Progress message describing current operation
        """
        # Emit progress signal to UI
        self.progress_update.emit(percentage, message)

        # Check for cancellation during progress updates
        # This allows responsive cancellation even during long operations
        self.check_cancellation()

    def cancel(self):
        """
        Cancel the current filename parsing operation.

        Notifies both the worker thread and the BatchProcessorService
        about cancellation to ensure graceful shutdown.
        """
        logger.info("Filename parsing cancellation requested")

        # Tell the service to cancel processing
        # The service will stop its internal loops and cleanup
        self.batch_service.cancel_processing()

        # Call base class cancel to set cancellation flags
        super().cancel()
