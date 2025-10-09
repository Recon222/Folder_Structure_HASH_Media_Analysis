"""
Video Metadata Extractor Service

Comprehensive FFprobe-based metadata extraction for timeline building.
Pulls all required data in one pass: duration, frame rate, PTS, resolution, codecs.

Following GPT-5's best practices for robust duration calculation.
"""

import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from fractions import Fraction
from dataclasses import dataclass

from filename_parser.core.binary_manager import binary_manager
from core.logger import logger


@dataclass
class VideoProbeData:
    """Complete video metadata from ffprobe."""

    # File info
    file_path: Path
    file_size_bytes: int

    # Duration (primary field - already in seconds)
    duration_seconds: float

    # Frame rate (as float)
    frame_rate: float

    # Resolution
    width: int
    height: int

    # Codec info
    codec_name: str
    codec_long_name: str
    pixel_format: str

    # Timing details (for advanced use)
    time_base: Optional[str] = None
    start_pts: Optional[int] = None
    duration_ts: Optional[int] = None
    nb_frames: Optional[int] = None

    # Container info
    format_name: str = ""
    format_long_name: str = ""
    bit_rate: Optional[int] = None

    # Success flag
    success: bool = True
    error_message: str = ""


class VideoMetadataExtractor:
    """
    Extract comprehensive video metadata using ffprobe.

    Optimized single-pass extraction of all needed fields:
    - Duration (with fallback logic per GPT-5 recommendations)
    - Frame rate (rational parsing)
    - Resolution, codecs, pixel format
    - PTS/time_base for advanced timing
    """

    def __init__(self):
        self.logger = logger

    def extract_metadata(self, file_path: Path) -> VideoProbeData:
        """
        Extract all video metadata in one ffprobe call.

        Args:
            file_path: Path to video file

        Returns:
            VideoProbeData with all extracted fields
        """
        ffprobe_path = binary_manager.get_ffprobe_path()

        if not ffprobe_path:
            return VideoProbeData(
                file_path=file_path,
                file_size_bytes=0,
                duration_seconds=0.0,
                frame_rate=0.0,
                width=0,
                height=0,
                codec_name="",
                codec_long_name="",
                pixel_format="",
                success=False,
                error_message="FFprobe not available"
            )

        try:
            # Comprehensive ffprobe command - get both format and stream data
            cmd = [
                ffprobe_path,
                "-v", "error",
                "-probesize", "100M",          # Probe deeper for weird containers
                "-analyzeduration", "100M",
                "-show_format",                # Container-level info
                "-show_streams",               # Stream-level info
                "-select_streams", "v:0",      # First video stream only
                "-of", "json",                 # JSON output
                str(file_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=10  # 10 second timeout
            )

            if result.returncode != 0:
                return self._error_result(
                    file_path,
                    f"FFprobe failed: {result.stderr[:200]}"
                )

            # Parse JSON
            data = json.loads(result.stdout)

            # Extract data
            return self._parse_probe_data(file_path, data)

        except subprocess.TimeoutExpired:
            return self._error_result(file_path, "FFprobe timeout (>10s)")
        except json.JSONDecodeError as e:
            return self._error_result(file_path, f"JSON parse error: {e}")
        except Exception as e:
            return self._error_result(file_path, f"Unexpected error: {e}")

    def _parse_probe_data(self, file_path: Path, data: Dict[str, Any]) -> VideoProbeData:
        """Parse ffprobe JSON output."""

        # Get format (container) data
        fmt = data.get("format", {})

        # Get video stream data
        streams = data.get("streams", [])
        if not streams:
            return self._error_result(file_path, "No video streams found")

        video_stream = streams[0]

        # Extract duration using GPT-5's fallback logic
        duration_seconds = self._extract_duration(fmt, video_stream)

        # Extract frame rate
        frame_rate = self._extract_frame_rate(video_stream)

        # Extract resolution
        width = video_stream.get("width", 0)
        height = video_stream.get("height", 0)

        # Extract codec info
        codec_name = video_stream.get("codec_name", "")
        codec_long_name = video_stream.get("codec_long_name", "")
        pixel_format = video_stream.get("pix_fmt", "yuv420p")

        # Extract timing details
        time_base = video_stream.get("time_base")
        start_pts = video_stream.get("start_pts")
        duration_ts = video_stream.get("duration_ts")
        nb_frames = video_stream.get("nb_frames")

        # Convert nb_frames to int if present
        if nb_frames is not None:
            try:
                nb_frames = int(nb_frames)
            except (ValueError, TypeError):
                nb_frames = None

        # Extract container info
        format_name = fmt.get("format_name", "")
        format_long_name = fmt.get("format_long_name", "")
        bit_rate = fmt.get("bit_rate")
        if bit_rate:
            try:
                bit_rate = int(bit_rate)
            except (ValueError, TypeError):
                bit_rate = None

        # Get file size
        file_size = file_path.stat().st_size if file_path.exists() else 0

        return VideoProbeData(
            file_path=file_path,
            file_size_bytes=file_size,
            duration_seconds=duration_seconds,
            frame_rate=frame_rate,
            width=width,
            height=height,
            codec_name=codec_name,
            codec_long_name=codec_long_name,
            pixel_format=pixel_format,
            time_base=time_base,
            start_pts=start_pts,
            duration_ts=duration_ts,
            nb_frames=nb_frames,
            format_name=format_name,
            format_long_name=format_long_name,
            bit_rate=bit_rate,
            success=True
        )

    def _extract_duration(self, fmt: Dict, stream: Dict) -> float:
        """
        Extract duration using GPT-5's recommended fallback logic.

        Priority:
        1. format.duration (most reliable, already in seconds)
        2. stream.duration (seconds)
        3. duration_ts * time_base (calculated)
        4. nb_frames / fps (last resort)
        """
        # 1. Try container duration first
        if fmt.get("duration"):
            try:
                return float(fmt["duration"])
            except (ValueError, TypeError):
                pass

        # 2. Try stream duration
        if stream.get("duration"):
            try:
                return float(stream["duration"])
            except (ValueError, TypeError):
                pass

        # 3. Try duration_ts * time_base
        if stream.get("duration_ts") is not None and stream.get("time_base"):
            try:
                duration_ts = int(stream["duration_ts"])
                time_base_str = stream["time_base"]

                # Parse time_base as fraction (e.g., "1/90000")
                time_base = self._parse_rational(time_base_str)
                if time_base:
                    return float(duration_ts * time_base)
            except (ValueError, TypeError):
                pass

        # 4. Last resort: nb_frames / fps
        if stream.get("nb_frames") and (stream.get("avg_frame_rate") or stream.get("r_frame_rate")):
            try:
                nb_frames = int(stream["nb_frames"])
                fps = self._extract_frame_rate(stream)
                if fps > 0:
                    return nb_frames / fps
            except (ValueError, TypeError, ZeroDivisionError):
                pass

        # Fallback: 0 (unknown)
        self.logger.warning(f"Could not determine duration for video, using 0")
        return 0.0

    def _extract_frame_rate(self, stream: Dict) -> float:
        """
        Extract frame rate from stream data.

        Priority:
        1. r_frame_rate (constant frame rate - more accurate)
        2. avg_frame_rate (average for VFR)
        """
        # Try r_frame_rate first
        r_frame_rate = stream.get("r_frame_rate")
        if r_frame_rate:
            fps = self._parse_rational(r_frame_rate)
            if fps and fps > 0:
                return float(fps)

        # Fallback to avg_frame_rate
        avg_frame_rate = stream.get("avg_frame_rate")
        if avg_frame_rate:
            fps = self._parse_rational(avg_frame_rate)
            if fps and fps > 0:
                return float(fps)

        self.logger.warning("Could not determine frame rate, using 30.0 as fallback")
        return 30.0

    def _parse_rational(self, rational_str: str) -> Optional[Fraction]:
        """
        Parse rational number string (e.g., "30000/1001", "1/90000").

        Args:
            rational_str: Rational number as string

        Returns:
            Fraction or None if parsing fails
        """
        try:
            if "/" in rational_str:
                num, den = rational_str.split("/")
                return Fraction(int(num), int(den))
            else:
                # Sometimes it's just an integer
                return Fraction(int(rational_str), 1)
        except (ValueError, ZeroDivisionError):
            return None

    def _error_result(self, file_path: Path, error_message: str) -> VideoProbeData:
        """Create error result."""
        self.logger.error(f"Metadata extraction failed for {file_path.name}: {error_message}")

        return VideoProbeData(
            file_path=file_path,
            file_size_bytes=0,
            duration_seconds=0.0,
            frame_rate=0.0,
            width=0,
            height=0,
            codec_name="",
            codec_long_name="",
            pixel_format="",
            success=False,
            error_message=error_message
        )
