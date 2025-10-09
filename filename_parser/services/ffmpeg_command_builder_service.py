"""
FFmpeg command builder service - generates FFmpeg command strings programmatically

This service builds FFmpeg commands for video concatenation and multicam layouts
without executing them. Provides clean separation between command generation and execution.
"""

from pathlib import Path
from typing import List, Optional
from enum import Enum

from core.services.base_service import BaseService

from filename_parser.models.timeline_models import TimelineSegment, RenderSettings
from filename_parser.core.binary_manager import binary_manager


class AudioHandling(str, Enum):
    """Audio handling strategy for concatenation"""
    COPY = "copy"          # Copy audio stream (default)
    DROP = "drop"          # Remove audio entirely
    TRANSCODE = "transcode"  # Re-encode to AAC


class FFmpegCommandBuilderService(BaseService):
    """Service for building FFmpeg command strings."""

    def __init__(self):
        super().__init__("FFmpegCommandBuilderService")

    def build_concat_command(
        self,
        segments: List[TimelineSegment],
        settings: RenderSettings,
        output_path: Path,
        concat_list_path: Path,
        audio_handling: AudioHandling = AudioHandling.COPY
    ) -> list[str]:
        """
        Build FFmpeg concat demuxer command with flexible audio handling.

        The concat demuxer is FAST (no re-encoding) but requires all
        input videos to have identical specifications (codec, resolution,
        fps, pixel format).

        Args:
            segments: Ordered timeline segments (with output_video_path set)
            settings: Render settings
            output_path: Final output video path
            concat_list_path: Temporary file for concat list
            audio_handling: How to handle audio (copy/drop/transcode)

        Returns:
            FFmpeg command as list of strings
        """
        # Create concat list file
        self._write_concat_list(segments, concat_list_path)

        self.logger.debug(f"Created concat list: {concat_list_path}")
        self.logger.info(f"Audio handling mode: {audio_handling.value}")

        cmd = [
            binary_manager.get_ffmpeg_path(),
            "-f", "concat",       # Use concat demuxer
            "-safe", "0",         # Allow absolute paths
            "-i", str(concat_list_path),
        ]

        # Audio handling strategy
        if audio_handling == AudioHandling.DROP:
            # Drop audio track entirely
            cmd.extend([
                "-c:v", "copy",   # Copy video
                "-an",            # No audio
            ])
            self.logger.info("Audio track will be dropped")

        elif audio_handling == AudioHandling.TRANSCODE:
            # Re-encode audio to AAC (MP4-compatible)
            cmd.extend([
                "-c:v", "copy",       # Copy video
                "-c:a", "aac",        # Encode audio to AAC
                "-b:a", "128k",       # Audio bitrate
                "-ar", "48000",       # Sample rate
            ])
            self.logger.info("Audio will be transcoded to AAC")

        else:  # AudioHandling.COPY (default)
            # Stream copy both video and audio
            cmd.extend([
                "-c", "copy",     # Copy both streams
            ])
            self.logger.info("Audio and video will be stream copied")

        cmd.extend([
            "-y",                 # Overwrite output
            str(output_path)
        ])

        return cmd

    def _write_concat_list(
        self,
        segments: List[TimelineSegment],
        concat_list_path: Path
    ):
        """
        Write concat demuxer list file.

        Format:
            file '/path/to/file1.mp4'
            file '/path/to/file2.mp4'
            file '/path/to/file3.mp4'

        Paths with single quotes are escaped by replacing ' with '\\''
        """
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for segment in segments:
                if segment.output_video_path and segment.output_video_path.exists():
                    # Escape single quotes in path (for FFmpeg safety)
                    path_str = str(segment.output_video_path).replace("'", "'\\''")
                    f.write(f"file '{path_str}'\n")

        self.logger.debug(f"Wrote {len(segments)} entries to concat list")
