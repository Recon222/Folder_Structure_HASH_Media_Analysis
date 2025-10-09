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
from typing import List, Optional, Callable, Dict

from core.services.base_service import BaseService
from core.result_types import Result
from core.exceptions import FileOperationError

from filename_parser.models.timeline_models import Timeline, RenderSettings, TimelineSegment
from filename_parser.services.slate_generator_service import SlateGeneratorService
from filename_parser.services.ffmpeg_command_builder_service import FFmpegCommandBuilderService, AudioHandling
from filename_parser.services.video_normalization_service import VideoNormalizationService
from filename_parser.services.frame_rate_service import FrameRateService


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
        self.normalization_service = VideoNormalizationService()
        self.frame_rate_service = FrameRateService()

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

                # Step 2: Detect codec mismatches and prepare segments (30-50%)
                if progress_callback:
                    progress_callback(32, "Analyzing video codecs...")

                # CRITICAL: If slates exist, FORCE normalization
                # Slates are created with specific codec/fps/resolution settings
                # and FFmpeg concat demuxer requires identical specs for all inputs
                has_slates = len(timeline.gaps) > 0

                if has_slates:
                    self.logger.warning(
                        "Gap slates detected - forcing video normalization "
                        "to ensure concat compatibility with slate videos"
                    )
                    # Force normalization with slate-compatible specs
                    mismatch_analysis = {
                        'needs_normalization': True,
                        'codec_mismatch': True,
                        'resolution_mismatch': False,
                        'fps_mismatch': True,
                        'pixel_format_mismatch': False,
                        'target_specs': {
                            'codec': settings.output_codec.replace('lib', ''),  # libx264 -> h264
                            'width': settings.output_resolution[0],
                            'height': settings.output_resolution[1],
                            'frame_rate': settings.output_fps,
                            'pixel_format': settings.output_pixel_format
                        }
                    }
                else:
                    # No slates - normal codec detection
                    mismatch_analysis = self.frame_rate_service.detect_codec_mismatches(timeline.videos)

                if progress_callback:
                    progress_callback(35, "Preparing timeline segments...")

                segments_result = self._prepare_segments(
                    timeline,
                    settings,
                    temp_path,
                    mismatch_analysis,
                    progress_callback
                )
                if not segments_result.success:
                    return segments_result

                segments = segments_result.value

                if progress_callback:
                    progress_callback(50, "Segments prepared")

                # Step 3: Concatenate all segments (40-95%)
                if progress_callback:
                    progress_callback(45, "Concatenating timeline segments...")

                output_path = settings.output_directory / settings.output_filename

                # Map audio_handling string to enum
                audio_handling_map = {
                    "copy": AudioHandling.COPY,
                    "drop": AudioHandling.DROP,
                    "transcode": AudioHandling.TRANSCODE
                }
                audio_handling = audio_handling_map.get(
                    settings.audio_handling,
                    AudioHandling.COPY
                )

                concat_result = self._concatenate_segments(
                    segments,
                    settings,
                    output_path,
                    temp_path,
                    progress_callback,
                    audio_handling=audio_handling
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
        settings: RenderSettings,
        temp_path: Path,
        mismatch_analysis: Dict,
        progress_callback: Optional[Callable] = None
    ) -> Result[List[TimelineSegment]]:
        """
        Prepare segments for concatenation with conditional normalization.

        If codec/resolution/FPS mismatches are detected, normalizes videos
        to common specs before concatenation.

        Phase 1: Map video segments to source files (or normalized), gap segments to slates
        Phase 2+: Will generate multicam layouts for overlap segments
        """
        try:
            prepared = []
            needs_normalization = mismatch_analysis.get('needs_normalization', False)

            if needs_normalization:
                target_specs = mismatch_analysis['target_specs']
                self.logger.warning(
                    f"Codec mismatch detected - normalizing to: {target_specs['codec']} "
                    f"{target_specs['width']}x{target_specs['height']} @ {target_specs['frame_rate']}fps"
                )

            video_segment_count = sum(1 for s in timeline.segments if s.segment_type == "video")
            processed_videos = 0

            for segment in timeline.segments:
                if segment.segment_type == "video":
                    if needs_normalization:
                        # Normalize video to common specs
                        normalized_path = temp_path / f"normalized_{processed_videos:03d}.mp4"

                        if progress_callback:
                            progress_callback(
                                35 + int((processed_videos / video_segment_count) * 15),
                                f"Normalizing video {processed_videos + 1}/{video_segment_count}..."
                            )

                        # Build RenderSettings from target_specs dict
                        # VideoNormalizationService expects RenderSettings, not dict
                        target_settings = RenderSettings(
                            output_codec=f"lib{target_specs['codec']}",  # h264 -> libx264
                            output_resolution=(target_specs['width'], target_specs['height']),
                            output_fps=target_specs['frame_rate'],
                            output_pixel_format=target_specs['pixel_format'],
                            video_bitrate=settings.video_bitrate,
                            audio_codec=settings.audio_codec,
                            audio_bitrate=settings.audio_bitrate,
                            output_directory=temp_path,
                            output_filename=f"normalized_{processed_videos:03d}.mp4"
                        )

                        norm_result = self.normalization_service.normalize_video(
                            segment.video,       # VideoMetadata object (not file_path!)
                            target_settings,     # RenderSettings object (not dict!)
                            normalized_path
                        )

                        if not norm_result.success:
                            return Result.error(norm_result.error)

                        segment.output_video_path = normalized_path
                        processed_videos += 1
                    else:
                        # Use original source video (no mismatch)
                        segment.output_video_path = segment.video.file_path

                    prepared.append(segment)

                elif segment.segment_type == "gap":
                    # Use generated slate
                    segment.output_video_path = segment.gap.slate_video_path
                    prepared.append(segment)

                elif segment.segment_type == "overlap":
                    # Phase 2: Multicam overlap handling
                    # For now, use first camera in overlap group
                    # TODO: Implement side-by-side, grid layouts using FFmpeg complex filters
                    self.logger.warning(
                        f"Overlap detected ({len(segment.overlap.videos)} cameras) - "
                        f"using first camera only. Full multicam layout support coming in Phase 2."
                    )

                    # Use first video in the overlap group
                    primary_video = segment.overlap.videos[0]

                    if needs_normalization:
                        # Normalize primary video
                        normalized_path = temp_path / f"overlap_{segment.start_frame:08d}.mp4"

                        target_settings = RenderSettings(
                            output_codec=f"lib{target_specs['codec']}",
                            output_resolution=(target_specs['width'], target_specs['height']),
                            output_fps=target_specs['frame_rate'],
                            output_pixel_format=target_specs['pixel_format'],
                            video_bitrate=settings.video_bitrate,
                            audio_codec=settings.audio_codec,
                            audio_bitrate=settings.audio_bitrate,
                            output_directory=temp_path,
                            output_filename=f"overlap_{segment.start_frame:08d}.mp4"
                        )

                        norm_result = self.normalization_service.normalize_video(
                            primary_video,
                            target_settings,
                            normalized_path
                        )

                        if not norm_result.success:
                            return Result.error(norm_result.error)

                        segment.output_video_path = normalized_path
                    else:
                        segment.output_video_path = primary_video.file_path

                    prepared.append(segment)

            self.logger.info(
                f"Prepared {len(prepared)} segments "
                f"({processed_videos} normalized)" if needs_normalization else f"(no normalization needed)"
            )
            return Result.success(prepared)

        except Exception as e:
            return Result.error(
                FileOperationError(
                    f"Failed to prepare segments: {e}",
                    user_message="Failed to prepare timeline segments",
                    context={"error": str(e)}
                )
            )

    def _concatenate_segments(
        self,
        segments: List[TimelineSegment],
        settings: RenderSettings,
        output_path: Path,
        temp_path: Path,
        progress_callback: Optional[Callable],
        audio_handling: AudioHandling = AudioHandling.COPY
    ) -> Result[Path]:
        """
        Concatenate all segments into final video.

        Uses FFmpeg concat demuxer for fast stream copying (no re-encoding).
        Supports flexible audio handling for incompatible codecs.

        Args:
            audio_handling: How to handle audio (copy/drop/transcode)
        """
        concat_list_path = temp_path / "concat_list.txt"

        # Build FFmpeg command with audio handling
        cmd = self.cmd_builder.build_concat_command(
            segments,
            settings,
            output_path,
            concat_list_path,
            audio_handling=audio_handling
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

                # Detect audio codec incompatibility
                is_audio_error = any([
                    "Could not find tag for codec" in stderr,
                    "codec not currently supported in container" in stderr,
                    "pcm_mulaw" in stderr,
                    "pcm_alaw" in stderr,
                ])

                # Return error with audio codec detection flag
                return Result.error(
                    FileOperationError(
                        f"FFmpeg concatenation failed: {stderr[:500]}",
                        user_message="Failed to concatenate timeline segments",
                        context={
                            "stderr": stderr[:1000],
                            "is_audio_error": is_audio_error,
                            "full_stderr": stderr
                        }
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
