"""
Multicam Renderer Service (GPT-5 Single-Pass Approach)

Clean, simple orchestration of FFmpeg timeline rendering.
Uses FFmpegTimelineBuilder for single-pass command generation.

No normalization. No intermediate files. Just one beautiful FFmpeg command.
"""

from pathlib import Path
from typing import List, Optional, Callable

from core.result_types import Result
from core.exceptions import FileOperationError
from core.logger import logger

from filename_parser.models.timeline_models import VideoMetadata, RenderSettings
from filename_parser.services.ffmpeg_timeline_builder import FFmpegTimelineBuilder, Clip


class MulticamRendererService:
    """
    Orchestrates multicam timeline rendering using GPT-5's single-pass approach.

    Responsibilities:
    1. Convert VideoMetadata list to Clip list (for timeline builder)
    2. Call FFmpegTimelineBuilder to generate command
    3. Execute FFmpeg command
    4. Report progress

    No more normalization, no more segment preparation, no more complexity.
    """

    def __init__(self):
        self.logger = logger
        self.builder = FFmpegTimelineBuilder()

    def render_timeline(
        self,
        videos: List[VideoMetadata],
        settings: RenderSettings,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Result[Path]:
        """
        Render timeline video using single-pass FFmpeg.

        Args:
            videos: List of video metadata with start_time/end_time populated
            settings: Render settings
            progress_callback: Optional progress reporting (percentage, message)

        Returns:
            Result containing output path or error
        """
        if not videos:
            return Result.error(
                FileOperationError(
                    "No videos provided",
                    user_message="Please select video files to render."
                )
            )

        filter_script_path = None
        try:
            if progress_callback:
                progress_callback(5, "Preparing timeline...")

            # Convert VideoMetadata to Clip objects
            clips = self._videos_to_clips(videos)

            if progress_callback:
                progress_callback(10, "Building FFmpeg command...")

            # Build output path
            output_path = settings.output_directory / settings.output_filename

            # Generate FFmpeg command using GPT-5 atomic interval approach
            # Returns (command, filter_script_path) tuple
            command, filter_script_path = self.builder.build_command(
                clips=clips,
                settings=settings,
                output_path=output_path,
                timeline_is_absolute=True  # Using ISO8601 times
            )

            # Log the command (argv only, not the huge filter script)
            self.logger.info("FFmpeg command generated (using filter script file)")
            self.logger.debug(f"Command: {' '.join(command[:20])}...")  # First 20 args only

            if progress_callback:
                progress_callback(15, "Rendering timeline (this may take several minutes)...")

            # Execute FFmpeg command
            import subprocess

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Monitor progress (FFmpeg writes to stderr)
            stderr_lines = []
            for line in process.stderr:
                stderr_lines.append(line)

                # Parse FFmpeg progress
                if "time=" in line and progress_callback:
                    # TODO: Parse actual progress from FFmpeg output
                    # For now, just show we're processing
                    progress_callback(50, "Rendering timeline...")

            returncode = process.wait()

            if returncode != 0:
                error_output = "\n".join(stderr_lines[-20:])  # Last 20 lines
                return Result.error(
                    FileOperationError(
                        f"FFmpeg failed with code {returncode}",
                        user_message="Video rendering failed. Check log for details.",
                        context={"ffmpeg_error": error_output}
                    )
                )

            if progress_callback:
                progress_callback(100, "Timeline rendering complete!")

            self.logger.info(f"Timeline rendered successfully: {output_path}")
            return Result.success(output_path)

        except Exception as e:
            self.logger.exception("Timeline rendering failed")
            return Result.error(
                FileOperationError(
                    f"Rendering error: {e}",
                    user_message=f"Timeline rendering failed: {str(e)}"
                )
            )
        finally:
            # PHASE 1: Clean up temp filter script file
            if filter_script_path:
                try:
                    import os
                    os.unlink(filter_script_path)
                    self.logger.debug(f"Cleaned up filter script: {filter_script_path}")
                except OSError as e:
                    self.logger.warning(f"Could not remove filter script: {e}")

    def _videos_to_clips(self, videos: List[VideoMetadata]) -> List[Clip]:
        """
        Convert VideoMetadata objects to Clip objects for timeline builder.

        Args:
            videos: List of video metadata

        Returns:
            List of Clip objects with ISO8601 times
        """
        clips = []

        for video in videos:
            if not video.start_time or not video.end_time:
                self.logger.warning(
                    f"Video {video.filename} missing start_time or end_time, skipping"
                )
                continue

            clip = Clip(
                path=video.file_path,
                start=video.start_time,  # ISO8601 string
                end=video.end_time,      # ISO8601 string
                cam_id=video.camera_path  # Camera identifier
            )
            clips.append(clip)

        self.logger.info(f"Converted {len(clips)} videos to clips for timeline builder")
        return clips
