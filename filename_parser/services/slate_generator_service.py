"""
Slate generator service - creates gap title cards using FFmpeg lavfi

This service generates video slates (title cards) for timeline gaps where
no camera has coverage. Slates display gap duration and timecode information.
"""

import subprocess
from pathlib import Path
from typing import Optional

from core.services.base_service import BaseService
from core.result_types import Result
from core.exceptions import FileOperationError

from filename_parser.models.timeline_models import Gap, RenderSettings
from filename_parser.core.binary_manager import binary_manager


class SlateGeneratorService(BaseService):
    """Service for generating gap slates with FFmpeg lavfi color source."""

    def __init__(self):
        super().__init__("SlateGeneratorService")

    def generate_slate(
        self,
        gap: Gap,
        settings: RenderSettings,
        output_path: Path
    ) -> Result[Path]:
        """
        Generate a slate video for a gap in coverage.

        Uses FFmpeg's lavfi color source with drawtext filters to create
        a professional-looking title card showing gap information.

        Args:
            gap: Gap information (timecodes, duration)
            settings: Render settings (resolution, codec, slate appearance)
            output_path: Where to save slate video

        Returns:
            Result containing output path or error
        """
        if not binary_manager.is_ffmpeg_available():
            return Result.error(
                FileOperationError(
                    "FFmpeg not available",
                    user_message="FFmpeg is required. Please install FFmpeg."
                )
            )

        try:
            self.logger.info(
                f"Generating slate for gap: {gap.start_timecode} → {gap.end_timecode}"
            )

            # Format duration nicely (e.g., "5m 30s" or "2h 15m 30s")
            duration_str = self._format_duration(gap.duration_seconds)

            # Build FFmpeg command
            cmd = self._build_slate_command(
                gap=gap,
                settings=settings,
                output_path=output_path,
                duration_str=duration_str
            )

            self.logger.debug(f"FFmpeg slate command: {' '.join(cmd)}")

            # Execute FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30  # Slate generation should be quick
            )

            self.logger.info(f"Slate generated: {output_path}")
            return Result.success(output_path)

        except subprocess.CalledProcessError as e:
            self.logger.error(f"FFmpeg slate generation failed: {e.stderr}")
            return Result.error(
                FileOperationError(
                    f"Slate generation failed: {e.stderr}",
                    user_message=f"Failed to create gap slate",
                    context={"gap": gap, "error": e.stderr}
                )
            )
        except subprocess.TimeoutExpired:
            self.logger.error("FFmpeg slate generation timed out")
            return Result.error(
                FileOperationError(
                    "Slate generation timed out",
                    user_message="Failed to create gap slate (timeout)",
                    context={"gap": gap}
                )
            )
        except Exception as e:
            self.logger.error(f"Unexpected slate generation error: {e}", exc_info=True)
            return Result.error(
                FileOperationError(
                    f"Unexpected error generating slate: {e}",
                    user_message="Failed to create gap slate",
                    context={"gap": gap, "error": str(e)}
                )
            )

    def _build_slate_command(
        self,
        gap: Gap,
        settings: RenderSettings,
        output_path: Path,
        duration_str: str
    ) -> list[str]:
        """
        Build FFmpeg command for slate generation.

        Creates a solid color background with multi-line text overlay
        showing gap information.
        """
        width, height = settings.output_resolution

        # Build drawtext filters for multi-line slate
        # Each drawtext filter adds one line of text
        drawtext_filters = [
            # Line 1: "NO COVERAGE" (red, large)
            f"drawtext=text='NO COVERAGE':"
            f"fontsize=64:"
            f"fontcolor=#ff4d4f:"
            f"x=(w-text_w)/2:"
            f"y=280",

            # Line 2: Gap duration (white, medium) - CLARIFIED WORDING
            f"drawtext=text='Real-World Time Gap\\: {duration_str}':"
            f"fontsize=32:"
            f"fontcolor=white:"
            f"x=(w-text_w)/2:"
            f"y=380",

            # Line 3: From time (gray, small)
            f"drawtext=text='From\\: {self._escape_colons(gap.start_timecode)} (Real Time)':"
            f"fontsize=24:"
            f"fontcolor=#8c8c8c:"
            f"x=(w-text_w)/2:"
            f"y=460",

            # Line 4: To time (gray, small)
            f"drawtext=text='To\\:   {self._escape_colons(gap.end_timecode)} (Real Time)':"
            f"fontsize=24:"
            f"fontcolor=#8c8c8c:"
            f"x=(w-text_w)/2:"
            f"y=500"
        ]

        # Combine all drawtext filters with commas
        vf_filter = ",".join(drawtext_filters)

        # Build complete FFmpeg command
        cmd = [
            binary_manager.get_ffmpeg_path(),
            # Input: lavfi color source (solid color video)
            "-f", "lavfi",
            "-i", f"color=c={settings.slate_background_color}:s={width}x{height}:"
                  f"d={settings.slate_duration_seconds}",
            # Video filter: add text overlays
            "-vf", vf_filter,
            # Output settings
            "-pix_fmt", settings.output_pixel_format,
            "-c:v", settings.output_codec,
            "-b:v", settings.video_bitrate,
            "-r", str(settings.output_fps),
            "-y",  # Overwrite output file
            str(output_path)
        ]

        return cmd

    def _format_duration(self, seconds: float) -> str:
        """
        Format duration as human-readable string.

        Examples:
            45 seconds → "45s"
            90 seconds → "1m 30s"
            3665 seconds → "1h 1m 5s"
        """
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        secs = int(seconds % 60)

        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:  # Always show seconds if nothing else
            parts.append(f"{secs}s")

        return " ".join(parts)

    def _escape_colons(self, timecode: str) -> str:
        """
        Escape colons for FFmpeg drawtext filter.

        FFmpeg's drawtext filter uses ':' as a separator, so literal
        colons in text must be escaped with backslash.
        """
        return timecode.replace(":", "\\:")
