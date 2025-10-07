"""
Multicam renderer service - orchestrates the entire rendering pipeline

This service coordinates all other services to generate the final timeline video:
1. Generate slates for gaps
2. Prepare timeline segments
3. Concatenate all segments into final video

Phase 1: Single camera with gap slates
Phase 2+: Will add multicam layout generation
"""

import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Callable

from core.services.base_service import BaseService
from core.result_types import Result
from core.exceptions import FileOperationError

from filename_parser.models.timeline_models import Timeline, RenderSettings, TimelineSegment
from filename_parser.services.slate_generator_service import SlateGeneratorService
from filename_parser.services.ffmpeg_command_builder_service import FFmpegCommandBuilderService


class MulticamRendererService(BaseService):
    """
    Orchestrates multicam timeline video generation.

    Phase 1: Single camera with gap slates
    Phase 2+: Will add multicam layout generation
    """

    def __init__(self):
        super().__init__("MulticamRendererService")
        self.slate_gen = SlateGeneratorService()
        self.cmd_builder = FFmpegCommandBuilderService()

    def render_timeline(
        self,
        timeline: Timeline,
        settings: RenderSettings,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Result[Path]:
        """
        Render timeline to final video.

        Workflow:
        1. Generate slate videos for all gaps (10-30%)
        2. Prepare segments (point to original videos or slates) (30-40%)
        3. Concatenate all segments into final video (40-100%)

        Args:
            timeline: Calculated timeline with segments
            settings: Render settings
            progress_callback: Optional progress callback (percentage, message)

        Returns:
            Result containing output video path or error
        """
        try:
            self.logger.info("Starting timeline render")

            # Create temp directory for intermediate files
            with tempfile.TemporaryDirectory(prefix="multicam_render_") as temp_dir:
                temp_path = Path(temp_dir)

                # Step 1: Generate slates for gaps (10-30%)
                if progress_callback:
                    progress_callback(10, "Generating gap slates...")

                slate_result = self._generate_slates(timeline, settings, temp_path)
                if not slate_result.success:
                    return slate_result

                if progress_callback:
                    progress_callback(30, "Gap slates generated")

                # Step 2: Prepare segments (30-40%)
                if progress_callback:
                    progress_callback(35, "Preparing timeline segments...")

                segments = self._prepare_segments(timeline, settings)

                if progress_callback:
                    progress_callback(40, "Segments prepared")

                # Step 3: Concatenate all segments (40-95%)
                if progress_callback:
                    progress_callback(45, "Concatenating timeline segments...")

                output_path = settings.output_directory / settings.output_filename
                concat_result = self._concatenate_segments(
                    segments,
                    settings,
                    output_path,
                    temp_path,
                    progress_callback
                )

                if not concat_result.success:
                    return concat_result

                if progress_callback:
                    progress_callback(100, "Timeline render complete")

                self.logger.info(f"Timeline rendered successfully: {output_path}")
                return Result.success(output_path)

        except Exception as e:
            self.logger.error(f"Timeline render failed: {e}", exc_info=True)
            return Result.error(
                FileOperationError(
                    f"Timeline render failed: {e}",
                    user_message="Failed to render timeline video",
                    context={"error": str(e)}
                )
            )

    def _generate_slates(
        self,
        timeline: Timeline,
        settings: RenderSettings,
        temp_path: Path
    ) -> Result[None]:
        """
        Generate slate videos for all gaps.

        Creates 5-second title cards showing gap duration and timecodes.
        """
        for i, gap in enumerate(timeline.gaps):
            slate_path = temp_path / f"slate_gap_{i:03d}.mp4"

            self.logger.debug(f"Generating slate {i+1}/{len(timeline.gaps)}: {slate_path.name}")

            result = self.slate_gen.generate_slate(gap, settings, slate_path)
            if not result.success:
                return result

            # Store slate path in gap (mutates gap object)
            gap.slate_video_path = slate_path

        self.logger.info(f"Generated {len(timeline.gaps)} gap slates")
        return Result.success(None)

    def _prepare_segments(
        self,
        timeline: Timeline,
        settings: RenderSettings
    ) -> List[TimelineSegment]:
        """
        Prepare segments for concatenation.

        Phase 1: Map video segments to source files, gap segments to slates
        Phase 2+: Will generate multicam layouts for overlap segments
        """
        prepared = []

        for segment in timeline.segments:
            if segment.segment_type == "video":
                # Use original source video
                segment.output_video_path = segment.video.file_path
                prepared.append(segment)

            elif segment.segment_type == "gap":
                # Use generated slate
                segment.output_video_path = segment.gap.slate_video_path
                prepared.append(segment)

            # Phase 2+: Will handle "overlap" segments

        self.logger.info(f"Prepared {len(prepared)} segments for concatenation")
        return prepared

    def _concatenate_segments(
        self,
        segments: List[TimelineSegment],
        settings: RenderSettings,
        output_path: Path,
        temp_path: Path,
        progress_callback: Optional[Callable]
    ) -> Result[Path]:
        """
        Concatenate all segments into final video.

        Uses FFmpeg concat demuxer for fast stream copying (no re-encoding).
        """
        concat_list_path = temp_path / "concat_list.txt"

        # Build FFmpeg command
        cmd = self.cmd_builder.build_concat_command(
            segments,
            settings,
            output_path,
            concat_list_path
        )

        self.logger.debug(f"FFmpeg concat command: {' '.join(cmd)}")

        try:
            # Execute FFmpeg with progress monitoring
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Monitor progress (FFmpeg writes progress to stderr)
            stderr_lines = []
            for line in process.stderr:
                stderr_lines.append(line)

                # Basic progress indication (FFmpeg output parsing is complex)
                if progress_callback and "time=" in line:
                    # Simple progress: increment from 50% to 95%
                    # TODO: Calculate actual percentage based on total duration
                    progress_callback(70, "Concatenating...")

            process.wait()

            if process.returncode != 0:
                stderr = "".join(stderr_lines)
                self.logger.error(f"FFmpeg concatenation failed: {stderr}")
                return Result.error(
                    FileOperationError(
                        f"FFmpeg concatenation failed: {stderr[:500]}",
                        user_message="Failed to concatenate timeline segments",
                        context={"stderr": stderr[:1000]}
                    )
                )

            self.logger.info(f"Concatenation complete: {output_path}")
            return Result.success(output_path)

        except Exception as e:
            self.logger.error(f"Concatenation failed: {e}", exc_info=True)
            return Result.error(
                FileOperationError(
                    f"Concatenation error: {e}",
                    user_message="Failed to concatenate timeline segments",
                    context={"error": str(e)}
                )
            )
