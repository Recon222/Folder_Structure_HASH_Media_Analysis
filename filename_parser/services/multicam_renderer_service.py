"""
Multicam Renderer Service (GPT-5 Single-Pass Approach)

Clean, simple orchestration of FFmpeg timeline rendering.
Uses FFmpegTimelineBuilder for single-pass command generation.

No normalization. No intermediate files. Just one beautiful FFmpeg command.
"""

from pathlib import Path
from typing import List, Optional, Callable
import tempfile
import subprocess

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

        try:
            if progress_callback:
                progress_callback(5, "Preparing timeline...")

            # Convert VideoMetadata to Clip objects
            clips = self._videos_to_clips(videos)

            # TIER 3: Auto-fallback safety net
            # Check if we need batch rendering (regardless of user setting)
            estimated_length = self.builder.estimate_argv_length(
                clips, settings, with_hwaccel=settings.use_hardware_decode
            )

            needs_batching = estimated_length > self.builder.SAFE_ARGV_THRESHOLD
            use_batching = settings.use_batch_rendering or needs_batching

            if needs_batching and not settings.use_batch_rendering:
                self.logger.warning(
                    f"Command length ({estimated_length} chars) approaching Windows limit "
                    f"({self.builder.WINDOWS_ARGV_LIMIT} chars). Automatically enabling batch "
                    f"rendering to prevent failure..."
                )

            # Route to appropriate rendering method
            if use_batching:
                return self._render_in_batches(videos, clips, settings, progress_callback)
            else:
                return self._render_single_pass(clips, settings, progress_callback)

        except Exception as e:
            self.logger.exception("Timeline rendering failed")
            return Result.error(
                FileOperationError(
                    f"Rendering error: {e}",
                    user_message=f"Timeline rendering failed: {str(e)}"
                )
            )

    def _render_single_pass(
        self,
        clips: List[Clip],
        settings: RenderSettings,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Result[Path]:
        """
        Render timeline in single pass (original implementation).

        Args:
            clips: List of video clips
            settings: Render settings
            progress_callback: Optional progress reporting

        Returns:
            Result containing output path or error
        """
        filter_script_path = None
        try:
            if progress_callback:
                progress_callback(10, "Building FFmpeg command...")

            # Build output path
            output_path = settings.output_directory / settings.output_filename

            # Generate FFmpeg command using GPT-5 atomic interval approach
            command, filter_script_path = self.builder.build_command(
                clips=clips,
                settings=settings,
                output_path=output_path,
                timeline_is_absolute=True
            )

            # Log command info
            self.logger.info("FFmpeg command generated (using filter script file)")
            self.logger.debug(f"Command: {' '.join(command[:20])}...")
            self.logger.debug(f"Command has {len(command)} arguments, {len(' '.join(command))} chars total")

            if progress_callback:
                progress_callback(15, "Rendering timeline (this may take several minutes)...")

            # Execute FFmpeg
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Monitor progress
            stderr_lines = []
            for line in process.stderr:
                stderr_lines.append(line)
                if "time=" in line and progress_callback:
                    progress_callback(50, "Rendering timeline...")

            returncode = process.wait()

            if returncode != 0:
                error_output = "\n".join(stderr_lines[-20:])
                self.logger.error(f"FFmpeg failed with return code {returncode}")
                self.logger.error(f"FFmpeg stderr (last 20 lines):\n{error_output}")
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
            self.logger.exception("Single-pass rendering failed")
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

    def _render_in_batches(
        self,
        videos: List[VideoMetadata],
        clips: List[Clip],
        settings: RenderSettings,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Result[Path]:
        """
        Render timeline in multiple batches to avoid Windows argv limits.

        Splits clips into batches, renders each separately, then concatenates.

        Args:
            videos: Original video metadata list
            clips: Clip list for timeline builder
            settings: Render settings
            progress_callback: Optional progress reporting

        Returns:
            Result containing final output path or error
        """
        try:
            self.logger.info(f"Batch rendering enabled: splitting {len(clips)} clips into batches")

            # Split clips into batches based on input count
            batches = self._split_clips_into_batches(clips, settings)
            self.logger.info(f"Created {len(batches)} batches for rendering")

            if progress_callback:
                progress_callback(10, f"Rendering {len(batches)} batches...")

            # Create temp directory for batch outputs
            temp_dir = Path(tempfile.mkdtemp(prefix="timeline_batch_"))
            batch_files = []

            try:
                # Render each batch
                for i, batch_clips in enumerate(batches, 1):
                    if progress_callback:
                        # Progress: 10-90% across all batches
                        batch_progress = 10 + int((i / len(batches)) * 80)
                        progress_callback(
                            batch_progress,
                            f"Rendering batch {i}/{len(batches)}..."
                        )

                    # Create batch output path
                    batch_output = temp_dir / f"batch_{i:03d}.mp4"

                    # Render this batch
                    batch_settings = RenderSettings(
                        output_directory=temp_dir,
                        output_filename=batch_output.name,
                        output_resolution=settings.output_resolution,
                        output_fps=settings.output_fps,
                        output_codec=settings.output_codec,
                        output_pixel_format=settings.output_pixel_format,
                        video_bitrate=settings.video_bitrate,
                        slate_duration_seconds=settings.slate_duration_seconds,
                        split_mode=settings.split_mode,
                        split_alignment=settings.split_alignment,
                        use_hardware_decode=settings.use_hardware_decode,
                        use_batch_rendering=False,  # Disable batching within batch
                        batch_size=settings.batch_size
                    )

                    result = self._render_single_pass(batch_clips, batch_settings, None)
                    if not result.success:
                        self.logger.error(f"Batch {i} failed: {result.error}")
                        return result

                    batch_files.append(batch_output)
                    self.logger.info(f"Batch {i}/{len(batches)} complete: {batch_output}")

                # Concatenate all batch files
                if progress_callback:
                    progress_callback(90, "Combining batches into final timeline...")

                final_output = settings.output_directory / settings.output_filename
                concat_result = self._concatenate_batches(batch_files, final_output)

                if not concat_result.success:
                    return concat_result

                if progress_callback:
                    progress_callback(100, "Batch rendering complete!")

                self.logger.info(f"Batch rendering complete: {final_output}")
                return Result.success(final_output)

            finally:
                # Cleanup temp files
                try:
                    for batch_file in batch_files:
                        if batch_file.exists():
                            batch_file.unlink()
                    temp_dir.rmdir()
                    self.logger.debug(f"Cleaned up temp batch directory: {temp_dir}")
                except Exception as e:
                    self.logger.warning(f"Could not clean up temp batch files: {e}")

        except Exception as e:
            self.logger.exception("Batch rendering failed")
            return Result.error(
                FileOperationError(
                    f"Batch rendering error: {e}",
                    user_message=f"Batch rendering failed: {str(e)}"
                )
            )

    def _split_clips_into_batches(
        self,
        clips: List[Clip],
        settings: RenderSettings
    ) -> List[List[Clip]]:
        """
        Split clips into batches that stay under argv limit.

        Args:
            clips: Full list of clips
            settings: Render settings (contains batch_size)

        Returns:
            List of clip batches
        """
        # For simplicity, just split by count
        # More sophisticated: split at gap boundaries
        batch_size = settings.batch_size
        batches = []

        for i in range(0, len(clips), batch_size):
            batch = clips[i:i + batch_size]
            batches.append(batch)

        return batches

    def _concatenate_batches(
        self,
        batch_files: List[Path],
        output_path: Path
    ) -> Result[Path]:
        """
        Concatenate batch outputs into final timeline using FFmpeg concat demuxer.

        Args:
            batch_files: List of batch output files
            output_path: Final output path

        Returns:
            Result with output path or error
        """
        try:
            # Create concat file list
            concat_file = batch_files[0].parent / "concat_list.txt"

            with open(concat_file, 'w') as f:
                for batch_file in batch_files:
                    # FFmpeg concat format: file 'path'
                    f.write(f"file '{batch_file.absolute()}'\n")

            # Build FFmpeg concat command
            from filename_parser.core.binary_manager import binary_manager
            ffmpeg = binary_manager.get_ffmpeg_path()

            command = [
                ffmpeg, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",  # Stream copy (no re-encode)
                str(output_path)
            ]

            self.logger.info(f"Concatenating {len(batch_files)} batches...")
            process = subprocess.run(
                command,
                capture_output=True,
                text=True
            )

            if process.returncode != 0:
                self.logger.error(f"FFmpeg concat failed: {process.stderr}")
                return Result.error(
                    FileOperationError(
                        f"Concat failed with code {process.returncode}",
                        user_message="Failed to combine batch outputs.",
                        context={"ffmpeg_error": process.stderr[-500:]}
                    )
                )

            # Cleanup concat file
            concat_file.unlink()

            self.logger.info(f"Batches concatenated successfully: {output_path}")
            return Result.success(output_path)

        except Exception as e:
            self.logger.exception("Batch concatenation failed")
            return Result.error(
                FileOperationError(
                    f"Concatenation error: {e}",
                    user_message=f"Failed to combine batches: {str(e)}"
                )
            )

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
