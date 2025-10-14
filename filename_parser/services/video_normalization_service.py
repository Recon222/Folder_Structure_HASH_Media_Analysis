"""
Video Normalization Service - Pre-process videos for concat compatibility

This service normalizes videos to ensure they can be concatenated with
FFmpeg's concat demuxer (fast, no re-encode) instead of concat filter (slow).

Normalization ensures all videos have:
- Same codec (h264)
- Same resolution (1920x1080)
- Same frame rate (30fps)
- Same pixel format (yuv420p)
"""

import subprocess
from pathlib import Path
from typing import List, Optional

from core.services.base_service import BaseService
from core.result_types import Result
from core.exceptions import FileOperationError

from filename_parser.models.timeline_models import VideoMetadata, RenderSettings
from filename_parser.core.binary_manager import binary_manager


class VideoNormalizationService(BaseService):
    """
    Service for normalizing videos to common specifications.

    Enables fast concat demuxer usage by ensuring all videos match.
    """

    def __init__(self):
        super().__init__("VideoNormalizationService")

    def normalize_video(
        self,
        video: VideoMetadata,
        settings: RenderSettings,
        output_path: Path
    ) -> Result[Path]:
        """
        Normalize video to match render settings.

        Args:
            video: Source video metadata
            settings: Target render settings
            output_path: Where to save normalized video

        Returns:
            Result containing output path or error
        """
        if not binary_manager.is_ffmpeg_available():
            return Result.error(
                FileOperationError(
                    "FFmpeg not available",
                    user_message="FFmpeg is required for video normalization."
                )
            )

        # Check if normalization is needed
        if self._needs_normalization(video, settings):
            self.logger.info(f"Normalizing {video.filename} to common specs")
            return self._perform_normalization(video, settings, output_path)
        else:
            self.logger.debug(f"{video.filename} already matches specs, skipping normalization")
            # Return original file path (no normalization needed)
            return Result.success(video.file_path)

    def _needs_normalization(self, video: VideoMetadata, settings: RenderSettings) -> bool:
        """Check if video needs normalization."""
        target_width, target_height = settings.output_resolution

        return (
            video.codec != settings.output_codec.replace("lib", "") or  # h264 vs libx264
            video.width != target_width or
            video.height != target_height or
            abs(video.frame_rate - settings.output_fps) > 0.01 or
            video.pixel_format != settings.output_pixel_format
        )

    def _perform_normalization(
        self,
        video: VideoMetadata,
        settings: RenderSettings,
        output_path: Path
    ) -> Result[Path]:
        """Perform FFmpeg normalization."""
        try:
            width, height = settings.output_resolution

            cmd = [
                binary_manager.get_ffmpeg_path(),
                "-i", str(video.file_path),
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                       f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                       f"setsar=1,fps={settings.output_fps}",
                "-c:v", settings.output_codec,
                "-b:v", settings.video_bitrate,
                "-pix_fmt", settings.output_pixel_format,
                "-c:a", settings.audio_codec if video.audio_codec else "copy",
                "-b:a", settings.audio_bitrate if video.audio_codec else None,
                "-y",  # Overwrite
                str(output_path)
            ]

            # Remove None values
            cmd = [arg for arg in cmd if arg is not None]

            self.logger.debug(f"Normalization command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            self.logger.info(f"Video normalized: {output_path}")
            return Result.success(output_path)

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Normalization failed: {e.stderr}")
            return Result.error(
                FileOperationError(
                    f"Video normalization failed: {e.stderr}",
                    user_message=f"Failed to normalize {video.filename}",
                    context={"video": video.filename, "error": e.stderr}
                )
            )
        except Exception as e:
            self.logger.error(f"Unexpected normalization error: {e}", exc_info=True)
            return Result.error(
                FileOperationError(
                    f"Unexpected error normalizing video: {e}",
                    user_message=f"Failed to normalize {video.filename}",
                    context={"video": video.filename, "error": str(e)}
                )
            )
