"""
Timeline Controller - orchestrates multicam timeline video rendering

This controller coordinates the complete timeline rendering workflow:
1. Validation of source videos
2. Metadata extraction
3. Timeline calculation (gaps & overlaps)
4. Video rendering in background worker

Follows the established controller pattern from FilenameParserController.
"""

from pathlib import Path
from typing import List, Optional

from core.result_types import Result
from core.exceptions import ValidationError
from core.logger import logger

from filename_parser.models.timeline_models import (
    VideoMetadata,
    RenderSettings,
    Timeline
)
from filename_parser.services.frame_rate_service import FrameRateService
from filename_parser.services.timeline_calculator_service import TimelineCalculatorService
from filename_parser.services.multicam_renderer_service import MulticamRendererService
from filename_parser.workers.timeline_render_worker import TimelineRenderWorker


class TimelineController:
    """
    Controller for multicam timeline video rendering.

    Orchestrates services and manages background worker for rendering.
    Follows SOA pattern with dependency injection.
    """

    def __init__(self):
        """Initialize controller with service dependencies."""
        self.frame_rate_service = FrameRateService()
        self.timeline_service = TimelineCalculatorService()
        self.renderer_service = MulticamRendererService()

        self.current_worker: Optional[TimelineRenderWorker] = None

    def validate_videos(
        self,
        file_paths: List[Path],
        parsing_results: List[dict]
    ) -> Result[List[VideoMetadata]]:
        """
        Validate videos and extract comprehensive metadata.

        Args:
            file_paths: List of video file paths
            parsing_results: Filename parsing results with SMPTE timecodes

        Returns:
            Result containing list of VideoMetadata or error
        """
        if not file_paths:
            return Result.error(
                ValidationError(
                    "No video files provided",
                    user_message="Please select video files to process."
                )
            )

        if len(file_paths) != len(parsing_results):
            return Result.error(
                ValidationError(
                    f"Mismatch between file count ({len(file_paths)}) and parsing results ({len(parsing_results)})",
                    user_message="File parsing mismatch. Please re-parse files."
                )
            )

        logger.info(f"Validating {len(file_paths)} video files...")

        video_metadata_list: List[VideoMetadata] = []
        errors: List[str] = []

        for file_path, result in zip(file_paths, parsing_results):
            if not result.get("success"):
                errors.append(f"{file_path.name}: Failed to parse filename")
                continue

            # Extract SMPTE timecode from parsing result
            smpte_timecode = result.get("smpte_timecode")
            if not smpte_timecode:
                errors.append(f"{file_path.name}: No SMPTE timecode found")
                continue

            # Determine camera path from parent directories
            # e.g., "D:/Project/Location1/Camera2/video.mp4" -> "Location1/Camera2"
            camera_path = self._extract_camera_path(file_path)

            # Extract comprehensive metadata
            metadata_result = self.frame_rate_service.extract_video_metadata(
                file_path,
                smpte_timecode,
                camera_path
            )

            if not metadata_result.success:
                errors.append(f"{file_path.name}: {metadata_result.error.user_message}")
                continue

            video_metadata_list.append(metadata_result.value)

        if errors:
            error_summary = "\n".join(errors)
            return Result.error(
                ValidationError(
                    f"Validation failed for {len(errors)} file(s):\n{error_summary}",
                    user_message=f"Failed to validate {len(errors)} file(s). Check log for details.",
                    context={"errors": errors}
                )
            )

        logger.info(f"Validation complete: {len(video_metadata_list)} videos ready")
        return Result.success(video_metadata_list)

    def calculate_timeline(
        self,
        videos: List[VideoMetadata],
        sequence_fps: float = 30.0,
        min_gap_seconds: float = 5.0
    ) -> Result[Timeline]:
        """
        Calculate chronological timeline with gap detection.

        Args:
            videos: List of validated video metadata
            sequence_fps: Target timeline frame rate
            min_gap_seconds: Minimum gap duration to report

        Returns:
            Result containing Timeline or error
        """
        logger.info(f"Calculating timeline for {len(videos)} videos...")

        return self.timeline_service.calculate_timeline(
            videos,
            sequence_fps,
            min_gap_seconds
        )

    def start_rendering(
        self,
        timeline: Timeline,
        settings: RenderSettings
    ) -> Result[TimelineRenderWorker]:
        """
        Start timeline rendering in background worker.

        Args:
            timeline: Calculated timeline
            settings: Render settings

        Returns:
            Result containing worker instance or error
        """
        if self.current_worker and self.current_worker.isRunning():
            return Result.error(
                ValidationError(
                    "Rendering already in progress",
                    user_message="A render operation is already running. Please wait or cancel it."
                )
            )

        logger.info("Starting timeline render worker...")

        # Create worker
        self.current_worker = TimelineRenderWorker(
            timeline,
            settings,
            self.renderer_service
        )

        # Start worker (caller will connect signals)
        self.current_worker.start()

        return Result.success(self.current_worker)

    def cancel_rendering(self) -> bool:
        """
        Cancel currently running render operation.

        Returns:
            True if cancelled successfully, False if nothing to cancel
        """
        if self.current_worker and self.current_worker.isRunning():
            logger.info("Cancelling timeline render...")
            self.current_worker.cancel()
            self.current_worker.wait(5000)  # Wait up to 5 seconds
            return True

        return False

    def _extract_camera_path(self, file_path: Path) -> str:
        """
        Extract camera organization path from file path.

        Assumes structure: .../Location/Camera/video.mp4
        Returns: "Location/Camera"

        Args:
            file_path: Path to video file

        Returns:
            Camera path string
        """
        parts = file_path.parts
        if len(parts) >= 3:
            # Use last 2 parent directories
            return f"{parts[-3]}/{parts[-2]}"
        elif len(parts) >= 2:
            # Use last parent directory
            return parts[-2]
        else:
            # Fallback to filename without extension
            return file_path.stem
