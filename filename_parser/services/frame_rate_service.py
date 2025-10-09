"""
Optimized Frame Rate Service with parallel FFprobe processing.

This service provides fast, accurate frame rate detection from video files
using parallel FFprobe execution for batch operations.
"""

import os
import json
import subprocess
from typing import Optional, List, Dict, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from core.services.base_service import BaseService
from core.result_types import Result
from core.exceptions import FileOperationError

from filename_parser.filename_parser_interfaces import IFrameRateService
from filename_parser.core.binary_manager import binary_manager
from filename_parser.services.video_metadata_extractor import VideoMetadataExtractor
from filename_parser.models.timeline_models import VideoMetadata


@dataclass
class FrameRateResult:
    """Result of frame rate detection for a single file."""

    file_path: str
    success: bool
    frame_rate: Optional[float] = None
    method: Optional[str] = None  # 'ffprobe', 'filename', 'default'
    error_message: Optional[str] = None


class FrameRateService(BaseService, IFrameRateService):
    """
    High-performance frame rate detection service.

    Uses parallel FFprobe execution for batch operations and provides
    fallback mechanisms for reliability.
    """

    # Standard frame rates for validation and normalization
    STANDARD_FRAME_RATES = {23.976, 24.0, 25.0, 29.97, 30.0, 50.0, 59.94, 60.0, 120.0}

    # Default fallback frame rate
    DEFAULT_FRAME_RATE = 29.97

    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize frame rate service.

        Args:
            max_workers: Max concurrent FFprobe processes (default: CPU count * 2)
        """
        super().__init__("FrameRateService")

        # Determine optimal worker count for I/O-bound FFprobe
        if max_workers is None:
            cpu_count = os.cpu_count() or 4
            self.max_workers = min(cpu_count * 2, 32)  # Cap at 32
        else:
            self.max_workers = max_workers

        # Ensure FFprobe is available
        binary_manager.find_binaries()

        if binary_manager.is_ffprobe_available():
            self.logger.info(f"FFprobe available: {binary_manager.get_ffprobe_path()}")
        else:
            self.logger.warning("FFprobe not found - frame rate detection will be limited")

    def detect_frame_rate(
        self,
        file_path: Path,
        progress_callback: Optional[Callable] = None
    ) -> Result[float]:
        """
        Detect frame rate from video file.

        Args:
            file_path: Path to video file
            progress_callback: Optional progress callback

        Returns:
            Result containing frame rate or error
        """
        # Check if FFprobe is available
        if not binary_manager.is_ffprobe_available():
            return Result.error(
                FileOperationError(
                    "FFprobe not available",
                    user_message="FFprobe is required for frame rate detection. Please install FFmpeg.",
                    context={"file_path": str(file_path)}
                )
            )

        # Check file exists
        if not file_path.exists():
            return Result.error(
                FileOperationError(
                    f"File not found: {file_path}",
                    user_message=f"Video file not found: {file_path.name}",
                    context={"file_path": str(file_path)}
                )
            )

        result = self._detect_single(str(file_path))

        if result.success and result.frame_rate:
            return Result.success(result.frame_rate)
        else:
            # Use default on failure
            self.logger.warning(f"Using default frame rate {self.DEFAULT_FRAME_RATE} for {file_path}")
            return Result.success(self.DEFAULT_FRAME_RATE)

    def detect_batch_frame_rates(
        self,
        file_paths: List[Path],
        use_default_on_failure: bool = True,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, float]:
        """
        Detect frame rates for multiple files in parallel.

        Args:
            file_paths: List of video file paths
            use_default_on_failure: Use default FPS for failed detections
            progress_callback: Optional callback(completed, total)

        Returns:
            Dictionary mapping file paths to frame rates
        """
        self.logger.info(f"Detecting frame rates for {len(file_paths)} files in parallel")

        results = {}
        completed = 0

        # Convert Path objects to strings
        str_paths = [str(fp) for fp in file_paths]

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_file = {executor.submit(self._detect_single, fp): fp for fp in str_paths}

            # Collect results as they complete
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()

                    if result.success and result.frame_rate:
                        results[file_path] = result.frame_rate
                    elif use_default_on_failure:
                        results[file_path] = self.DEFAULT_FRAME_RATE
                        self.logger.warning(f"Using default FPS for {file_path}: {result.error_message}")

                    completed += 1
                    if progress_callback:
                        progress_callback(completed, len(file_paths))

                except Exception as e:
                    self.logger.error(f"Error detecting FPS for {file_path}: {e}")
                    if use_default_on_failure:
                        results[file_path] = self.DEFAULT_FRAME_RATE
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, len(file_paths))

        self.logger.info(f"Frame rate detection complete: {len(results)}/{len(file_paths)} successful")
        return results

    def _detect_single(self, file_path: str) -> FrameRateResult:
        """
        Detect frame rate for a single file using best available method.

        Args:
            file_path: Path to video file

        Returns:
            FrameRateResult with detection outcome
        """
        # Validate file exists
        if not os.path.exists(file_path):
            return FrameRateResult(
                file_path=file_path, success=False, error_message="File not found"
            )

        # Try FFprobe (most accurate)
        if binary_manager.is_ffprobe_available():
            result = self._detect_with_ffprobe(file_path)
            if result.success:
                return result

        # Try filename extraction as fallback
        fps = self._extract_from_filename(file_path)
        if fps:
            return FrameRateResult(
                file_path=file_path, success=True, frame_rate=fps, method="filename"
            )

        # Failed all methods
        return FrameRateResult(
            file_path=file_path, success=False, error_message="All detection methods failed"
        )

    def _detect_with_ffprobe(self, file_path: str) -> FrameRateResult:
        """
        Detect frame rate using FFprobe.

        Args:
            file_path: Path to video file

        Returns:
            FrameRateResult
        """
        ffprobe_path = binary_manager.get_ffprobe_path()

        try:
            # Optimized FFprobe command - selective field extraction
            cmd = [
                ffprobe_path,
                "-v",
                "error",
                "-select_streams",
                "v:0",  # First video stream only
                "-show_entries",
                "stream=r_frame_rate,avg_frame_rate",
                "-of",
                "json",
                file_path,
            ]

            # Execute with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=5,  # 5 second timeout
            )

            if result.returncode != 0:
                return FrameRateResult(
                    file_path=file_path,
                    success=False,
                    error_message=f"FFprobe failed: {result.stderr[:200]}",
                )

            # Parse JSON output
            data = json.loads(result.stdout)
            streams = data.get("streams", [])

            if not streams:
                return FrameRateResult(
                    file_path=file_path, success=False, error_message="No video streams found"
                )

            video_stream = streams[0]

            # Try r_frame_rate first (constant frame rate - more accurate)
            fps = self._parse_frame_rate_fraction(video_stream.get("r_frame_rate"))
            if fps:
                normalized = self.normalize_frame_rate(fps)
                return FrameRateResult(
                    file_path=file_path,
                    success=True,
                    frame_rate=normalized,
                    method="ffprobe_r_frame_rate",
                )

            # Fallback to avg_frame_rate
            fps = self._parse_frame_rate_fraction(video_stream.get("avg_frame_rate"))
            if fps:
                normalized = self.normalize_frame_rate(fps)
                return FrameRateResult(
                    file_path=file_path,
                    success=True,
                    frame_rate=normalized,
                    method="ffprobe_avg_frame_rate",
                )

            return FrameRateResult(
                file_path=file_path,
                success=False,
                error_message="No valid frame rate in FFprobe output",
            )

        except subprocess.TimeoutExpired:
            return FrameRateResult(
                file_path=file_path, success=False, error_message="FFprobe timeout"
            )
        except json.JSONDecodeError as e:
            return FrameRateResult(
                file_path=file_path, success=False, error_message=f"JSON parse error: {e}"
            )
        except Exception as e:
            return FrameRateResult(
                file_path=file_path, success=False, error_message=f"Unexpected error: {e}"
            )

    def _parse_frame_rate_fraction(self, rate_str: Optional[str]) -> Optional[float]:
        """
        Parse FFprobe frame rate fraction (e.g., "30000/1001" -> 29.97).

        Args:
            rate_str: Frame rate string from FFprobe

        Returns:
            Frame rate as float or None
        """
        if not rate_str or rate_str == "0/0":
            return None

        try:
            if "/" in rate_str:
                numerator, denominator = map(int, rate_str.split("/"))
                if denominator == 0:
                    return None
                return numerator / denominator
            else:
                return float(rate_str)
        except (ValueError, ZeroDivisionError):
            return None

    def normalize_frame_rate(self, fps: float) -> float:
        """
        Normalize frame rate to standard values.

        Args:
            fps: Detected frame rate

        Returns:
            Normalized frame rate
        """
        # If already a standard rate, return as-is
        if fps in self.STANDARD_FRAME_RATES:
            return fps

        # Find closest standard rate within 0.1 fps
        for standard_fps in self.STANDARD_FRAME_RATES:
            if abs(fps - standard_fps) < 0.1:
                return standard_fps

        # Return original if no close match
        return fps

    def _extract_from_filename(self, file_path: str) -> Optional[float]:
        """
        Try to extract frame rate from filename.

        Args:
            file_path: Path to video file

        Returns:
            Extracted frame rate or None
        """
        import re

        filename = os.path.basename(file_path).lower()

        # Common patterns: "_30fps", "_29.97fps", "(30fps)", etc.
        patterns = [
            r"(\d+\.?\d*)fps",
            r"(\d+\.?\d*)_fps",
            r"fps_?(\d+\.?\d*)",
        ]

        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                try:
                    fps = float(match.group(1))
                    if 1.0 <= fps <= 240.0:  # Sanity check
                        return fps
                except ValueError:
                    continue

        return None

    def detect_codec_mismatches(
        self,
        video_metadata_list: List[VideoMetadata]
    ) -> Dict[str, any]:
        """
        Analyze video metadata to detect codec, resolution, or FPS mismatches.

        Args:
            video_metadata_list: List of VideoMetadata objects to analyze

        Returns:
            Dictionary with mismatch analysis:
            {
                'needs_normalization': bool,
                'codec_mismatch': bool,
                'resolution_mismatch': bool,
                'fps_mismatch': bool,
                'pixel_format_mismatch': bool,
                'target_specs': {...}  # Recommended normalization targets
            }
        """
        if not video_metadata_list:
            return {'needs_normalization': False}

        # Extract unique values for each property
        codecs = set(v.codec for v in video_metadata_list)
        resolutions = set((v.width, v.height) for v in video_metadata_list)
        fps_values = set(v.frame_rate for v in video_metadata_list)
        pix_fmts = set(v.pixel_format for v in video_metadata_list)

        codec_mismatch = len(codecs) > 1
        resolution_mismatch = len(resolutions) > 1
        fps_mismatch = len(fps_values) > 1
        pixel_format_mismatch = len(pix_fmts) > 1

        needs_normalization = any([
            codec_mismatch,
            resolution_mismatch,
            fps_mismatch,
            pixel_format_mismatch
        ])

        # Determine target specs (use most common or highest quality)
        target_codec = max(codecs, key=lambda c: sum(1 for v in video_metadata_list if v.codec == c))
        target_resolution = max(resolutions, key=lambda r: r[0] * r[1])  # Highest resolution
        target_fps = max(fps_values, key=lambda f: sum(1 for v in video_metadata_list if v.frame_rate == f))
        target_pix_fmt = max(pix_fmts, key=lambda p: sum(1 for v in video_metadata_list if v.pixel_format == p))

        self.logger.info(
            f"Codec analysis: {len(codecs)} codec(s), {len(resolutions)} resolution(s), "
            f"{len(fps_values)} FPS value(s) - Normalization needed: {needs_normalization}"
        )

        return {
            'needs_normalization': needs_normalization,
            'codec_mismatch': codec_mismatch,
            'resolution_mismatch': resolution_mismatch,
            'fps_mismatch': fps_mismatch,
            'pixel_format_mismatch': pixel_format_mismatch,
            'target_specs': {
                'codec': target_codec,
                'width': target_resolution[0],
                'height': target_resolution[1],
                'frame_rate': target_fps,
                'pixel_format': target_pix_fmt
            },
            'detected_values': {
                'codecs': list(codecs),
                'resolutions': [f"{w}x{h}" for w, h in resolutions],
                'fps_values': list(fps_values),
                'pixel_formats': list(pix_fmts)
            }
        }

    def extract_video_metadata(
        self,
        file_path: Path,
        smpte_timecode: str,
        camera_path: str
    ) -> Result[VideoMetadata]:
        """
        Extract comprehensive video metadata using FFprobe.

        This method extends the basic frame rate detection to extract all
        metadata needed for video normalization and timeline processing.

        Args:
            file_path: Path to video file
            smpte_timecode: SMPTE timecode from filename parser
            camera_path: Camera organization path (e.g., "Location1/Camera2")

        Returns:
            Result containing VideoMetadata or error
        """
        if not binary_manager.is_ffprobe_available():
            return Result.error(
                FileOperationError(
                    "FFprobe not available",
                    user_message="FFprobe is required. Please install FFmpeg.",
                    context={"file_path": str(file_path)}
                )
            )

        try:
            # Single FFprobe call for all metadata (efficient)
            cmd = [
                binary_manager.get_ffprobe_path(),
                "-v", "error",
                "-show_entries",
                "stream=codec_name,codec_type,width,height,r_frame_rate,pix_fmt,profile,bit_rate,sample_rate,channels",
                "-show_entries", "format=duration",
                "-of", "json",
                str(file_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=10  # 10 second timeout
            )

            data = json.loads(result.stdout)

            # Parse video stream
            video_stream = next(
                (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
                None
            )
            if not video_stream:
                return Result.error(
                    FileOperationError(
                        f"No video stream found in {file_path.name}",
                        user_message=f"Could not find video stream in {file_path.name}",
                        context={"file_path": str(file_path)}
                    )
                )

            # Parse audio stream (optional)
            audio_stream = next(
                (s for s in data.get("streams", []) if s.get("codec_type") == "audio"),
                None
            )

            # Calculate frame rate
            r_frame_rate = video_stream.get("r_frame_rate", "30/1")
            fps = self._parse_frame_rate_fraction(r_frame_rate)
            if fps is None:
                fps = self.DEFAULT_FRAME_RATE

            # Calculate duration
            duration_seconds = float(data.get("format", {}).get("duration", 0))
            duration_frames = int(duration_seconds * fps)

            # Build VideoMetadata
            metadata = VideoMetadata(
                file_path=file_path,
                filename=file_path.name,
                smpte_timecode=smpte_timecode,
                frame_rate=fps,
                duration_seconds=duration_seconds,
                duration_frames=duration_frames,
                width=int(video_stream.get("width", 1920)),
                height=int(video_stream.get("height", 1080)),
                codec=video_stream.get("codec_name", "h264"),
                pixel_format=video_stream.get("pix_fmt", "yuv420p"),
                video_bitrate=int(video_stream.get("bit_rate", 5000000)),
                video_profile=video_stream.get("profile"),
                audio_codec=audio_stream.get("codec_name") if audio_stream else None,
                audio_bitrate=int(audio_stream.get("bit_rate", 128000)) if audio_stream else None,
                sample_rate=int(audio_stream.get("sample_rate", 48000)) if audio_stream else None,
                camera_path=camera_path
            )

            return Result.success(metadata)

        except subprocess.CalledProcessError as e:
            return Result.error(
                FileOperationError(
                    f"FFprobe failed: {e.stderr}",
                    user_message=f"Could not extract metadata from {file_path.name}",
                    context={"file_path": str(file_path), "error": e.stderr}
                )
            )
        except subprocess.TimeoutExpired:
            return Result.error(
                FileOperationError(
                    f"FFprobe timeout for {file_path.name}",
                    user_message=f"Metadata extraction timed out for {file_path.name}",
                    context={"file_path": str(file_path)}
                )
            )
        except Exception as e:
            return Result.error(
                FileOperationError(
                    f"Unexpected error extracting metadata: {e}",
                    user_message=f"Failed to analyze {file_path.name}",
                    context={"file_path": str(file_path), "error": str(e)}
                )
            )
