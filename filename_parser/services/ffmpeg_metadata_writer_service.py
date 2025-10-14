"""
FFmpeg Metadata Writer Service - Write SMPTE timecode to video files.

This service handles writing SMPTE timecode metadata to video files using FFmpeg,
with support for format conversion and mirrored directory structures.
"""

import os
import re
import subprocess
from typing import Optional
from pathlib import Path

from core.services.base_service import BaseService
from core.result_types import Result
from core.exceptions import FileOperationError, ValidationError

from filename_parser.filename_parser_interfaces import IFFmpegMetadataWriterService
from filename_parser.core.binary_manager import binary_manager
from filename_parser.core.format_mapper import FormatMapper


class FFmpegMetadataWriterService(BaseService, IFFmpegMetadataWriterService):
    """
    Service for writing SMPTE metadata to video files using FFmpeg.

    Uses FFmpeg to write both a timecode track and XMP metadata directly
    to output files with proper format conversion when needed.
    """

    def __init__(self):
        """Initialize the FFmpeg metadata writer service."""
        super().__init__("FFmpegMetadataWriterService")

        # Ensure FFmpeg is available
        binary_manager.find_binaries()

        if binary_manager.is_ffmpeg_available():
            self.logger.info(f"FFmpeg available: {binary_manager.get_ffmpeg_path()}")
        else:
            self.logger.warning("FFmpeg not found - metadata writing unavailable")

        # Default output configuration
        self.output_directory = "timecoded"  # Default subfolder name

    def write_smpte_metadata(
        self,
        video_path: Path,
        smpte_timecode: str,
        fps: float,
        project_root: Optional[str] = None
    ) -> Result[Path]:
        """
        Write SMPTE timecode to a video file using FFmpeg.

        This method uses FFmpeg to write both a timecode track and XMP metadata
        directly to a new output file. Output location is calculated based on
        whether a project root is provided (mirrored structure).

        Args:
            video_path: Path to the video file
            smpte_timecode: SMPTE timecode string (HH:MM:SS:FF)
            fps: Frame rate of the video
            project_root: Optional root directory for mirrored structure

        Returns:
            Result containing output file Path or error
        """
        # Validate FFmpeg availability
        if not binary_manager.is_ffmpeg_available():
            return Result.error(
                FileOperationError(
                    "FFmpeg not available",
                    user_message="FFmpeg is required for metadata writing. Please install FFmpeg.",
                    context={"video_path": str(video_path)}
                )
            )

        # Validate parameters
        if not video_path.exists():
            return Result.error(
                FileOperationError(
                    f"File not found: {video_path}",
                    user_message=f"Video file not found: {video_path.name}",
                    context={"video_path": str(video_path)}
                )
            )

        if not smpte_timecode or not self._is_valid_smpte_format(smpte_timecode):
            return Result.error(
                ValidationError(
                    f"Invalid SMPTE timecode format: {smpte_timecode}",
                    user_message="SMPTE timecode must be in HH:MM:SS:FF format.",
                    context={"timecode": smpte_timecode}
                )
            )

        if fps <= 0:
            return Result.error(
                ValidationError(
                    f"Invalid frame rate: {fps}",
                    user_message="Frame rate must be positive.",
                    context={"fps": fps}
                )
            )

        try:
            # Determine output directory
            if project_root:
                # Mirrored structure: maintain relative path from project root
                rel_path = video_path.parent.relative_to(project_root)
                output_dir = Path(project_root) / "timecoded" / rel_path
                self.logger.info(f"Using mirrored structure: {output_dir}")
            else:
                # Local structure: create subfolder in same directory
                output_dir = video_path.parent / self.output_directory
                self.logger.info(f"Using local subdirectory: {output_dir}")

            # Create output directory
            output_dir.mkdir(parents=True, exist_ok=True)

            # Format timecode for filename (HHmmssff)
            tc_filename = smpte_timecode.replace(":", "")

            # Determine output format (may need conversion)
            output_ext, was_converted = FormatMapper.get_output_format(str(video_path))
            if was_converted:
                format_info = FormatMapper.get_format_info(str(video_path))
                self.logger.info(f"Format conversion: {format_info['reason']}")

            # Build output filename
            output_filename = f"{video_path.stem}_TC_{tc_filename}{output_ext}"
            output_path = output_dir / output_filename

            self.logger.info(f"Writing timecode to: {output_path}")

            # Build FFmpeg command - try copy mode first (fast)
            ffmpeg_path = binary_manager.get_ffmpeg_path()
            cmd = [
                ffmpeg_path,
                "-i", str(video_path),
                "-c", "copy",  # Copy streams without re-encoding
                "-timecode", smpte_timecode,  # Add timecode track
                "-metadata:s:v:0", f"xmp:Timecode={smpte_timecode}",  # XMP metadata
                "-movflags", "use_metadata_tags",  # Ensure metadata tags used
                "-y",  # Overwrite if exists
                str(output_path),
            ]

            self.logger.debug(f"FFmpeg command (copy mode): {' '.join(cmd)}")

            # Execute FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,  # 2 minute timeout
            )

            # Check for errors and detect audio codec incompatibility
            if result.returncode != 0:
                stderr_lower = result.stderr.lower()

                # Check if error is due to incompatible audio codec
                is_audio_codec_error = (
                    "codec not currently supported in container" in stderr_lower or
                    "could not find tag for codec" in stderr_lower or
                    "pcm_mulaw" in stderr_lower
                )

                if is_audio_codec_error:
                    self.logger.warning("Copy mode failed due to incompatible audio codec - retrying with audio re-encoding")

                    # Retry with audio re-encoding to AAC
                    cmd_reencode = [
                        ffmpeg_path,
                        "-i", str(video_path),
                        "-c:v", "copy",  # Copy video stream (no re-encoding)
                        "-c:a", "aac",   # Re-encode audio to AAC (MP4-compatible)
                        "-b:a", "64k",   # 64 kbps audio bitrate (matches typical CCTV)
                        "-timecode", smpte_timecode,
                        "-metadata:s:v:0", f"xmp:Timecode={smpte_timecode}",
                        "-movflags", "use_metadata_tags",
                        "-y",
                        str(output_path),
                    ]

                    self.logger.debug(f"FFmpeg command (re-encode audio): {' '.join(cmd_reencode)}")

                    result = subprocess.run(
                        cmd_reencode,
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=120,
                    )

                    if result.returncode != 0:
                        error_msg = result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr
                        self.logger.error(f"FFmpeg failed even with audio re-encoding (returncode {result.returncode}): {error_msg}")
                        return Result.error(
                            FileOperationError(
                                f"FFmpeg error (returncode {result.returncode}): {error_msg}",
                                user_message="Failed to write timecode metadata even after re-encoding audio.",
                                context={
                                    "video_path": str(video_path),
                                    "output_path": str(output_path),
                                    "returncode": result.returncode,
                                    "full_stderr": result.stderr
                                }
                            )
                        )
                    else:
                        self.logger.info("Successfully wrote timecode with audio re-encoding")
                else:
                    # Not an audio codec error - return original error
                    error_msg = result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr
                    self.logger.error(f"FFmpeg failed (returncode {result.returncode}): {error_msg}")
                    return Result.error(
                        FileOperationError(
                            f"FFmpeg error (returncode {result.returncode}): {error_msg}",
                            user_message="Failed to write timecode metadata. FFmpeg reported an error.",
                            context={
                                "video_path": str(video_path),
                                "output_path": str(output_path),
                                "returncode": result.returncode,
                                "full_stderr": result.stderr
                            }
                        )
                    )

            # Verify output file exists and has content
            if not output_path.exists() or output_path.stat().st_size == 0:
                return Result.error(
                    FileOperationError(
                        "Output file is missing or empty",
                        user_message="The output file was not created successfully.",
                        context={"output_path": str(output_path)}
                    )
                )

            self.logger.info(f"Successfully wrote timecode to: {output_path}")
            return Result.success(output_path)

        except subprocess.TimeoutExpired:
            return Result.error(
                FileOperationError(
                    "FFmpeg operation timed out",
                    user_message="The operation took too long and was cancelled.",
                    context={"video_path": str(video_path)}
                )
            )
        except Exception as e:
            return Result.error(
                FileOperationError(
                    f"Unexpected error writing timecode: {e}",
                    user_message="An unexpected error occurred while writing the timecode.",
                    context={"video_path": str(video_path), "error": str(e)}
                )
            )

    def is_ffmpeg_available(self) -> bool:
        """
        Check if FFmpeg is available.

        Returns:
            True if FFmpeg is available
        """
        return binary_manager.is_ffmpeg_available()

    def set_output_directory(self, directory_name: str) -> None:
        """
        Set the output directory name for local structure.

        Args:
            directory_name: Name of the output subdirectory (default: "timecoded")
        """
        self.output_directory = directory_name
        self.logger.debug(f"Output directory set to: {directory_name}")

    def _is_valid_smpte_format(self, timecode: str) -> bool:
        """
        Validate SMPTE timecode format.

        Args:
            timecode: Timecode string to validate

        Returns:
            True if valid SMPTE format (HH:MM:SS:FF)
        """
        pattern = r"^([0-2]\d):([0-5]\d):([0-5]\d):([0-6]\d)$"
        return bool(re.match(pattern, timecode))

    def remove_timecode(self, video_path: Path) -> Result[Path]:
        """
        Remove timecode from a video file.

        Creates a new file without the timecode metadata.

        Args:
            video_path: Path to the video file

        Returns:
            Result containing output file Path or error
        """
        if not binary_manager.is_ffmpeg_available():
            return Result.error(
                FileOperationError(
                    "FFmpeg not available",
                    user_message="FFmpeg is required for this operation.",
                    context={"video_path": str(video_path)}
                )
            )

        if not video_path.exists():
            return Result.error(
                FileOperationError(
                    f"File not found: {video_path}",
                    user_message=f"Video file not found: {video_path.name}",
                    context={"video_path": str(video_path)}
                )
            )

        try:
            # Create output directory
            output_dir = video_path.parent / "notimecode"
            output_dir.mkdir(parents=True, exist_ok=True)

            # Build output filename
            output_filename = f"{video_path.stem}_notimecode{video_path.suffix}"
            output_path = output_dir / output_filename

            self.logger.info(f"Removing timecode, output: {output_path}")

            # Build FFmpeg command
            ffmpeg_path = binary_manager.get_ffmpeg_path()
            cmd = [
                ffmpeg_path,
                "-i", str(video_path),
                "-c", "copy",
                "-map_metadata", "0",
                "-metadata", "timecode=",  # Clear timecode
                "-y",
                str(output_path),
            ]

            # Execute
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )

            if result.returncode != 0:
                error_msg = result.stderr[:500]
                return Result.error(
                    FileOperationError(
                        f"FFmpeg error: {error_msg}",
                        user_message="Failed to remove timecode metadata.",
                        context={"video_path": str(video_path)}
                    )
                )

            self.logger.info(f"Timecode removed: {output_path}")
            return Result.success(output_path)

        except Exception as e:
            return Result.error(
                FileOperationError(
                    f"Error removing timecode: {e}",
                    user_message="An unexpected error occurred.",
                    context={"video_path": str(video_path), "error": str(e)}
                )
            )
