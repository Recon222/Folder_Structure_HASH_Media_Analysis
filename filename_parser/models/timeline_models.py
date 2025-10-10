"""
Timeline data models for multicam video generation.

This module defines type-safe data structures for representing video timelines,
including metadata, positions, gaps, overlaps, and rendering settings.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Literal
from pathlib import Path
from enum import Enum


class LayoutType(str, Enum):
    """Multicam layout strategies for different camera counts."""

    SINGLE = "single"              # 1 camera (Phase 1)
    SIDE_BY_SIDE = "side_by_side"  # 2 cameras horizontal (Phase 2)
    TRIPLE_SPLIT = "triple_split"  # 3 cameras: 2 top, 1 bottom (Phase 3)
    GRID_2X2 = "grid_2x2"          # 4 cameras in 2x2 grid (Phase 3)
    GRID_3X2 = "grid_3x2"          # 6 cameras in 3x2 grid (Phase 3)


@dataclass
class VideoMetadata:
    """
    Comprehensive video metadata for timeline processing.

    Contains all information needed for video normalization,
    timeline positioning, and multicam layout generation.
    """

    # File information
    file_path: Path
    filename: str

    # Timing information (for GPT-5 timeline builder)
    smpte_timecode: str      # From filename parser (HH:MM:SS:FF) - START time
    start_time: Optional[str] = None  # ISO 8601 string (e.g., "2025-05-21T14:30:00")
    end_time: Optional[str] = None    # ISO 8601 string (start_time + duration_seconds)
    frame_rate: float = 30.0          # Native FPS (e.g., 29.97, 30.0)
    duration_seconds: float = 0.0     # Real-world duration from ffprobe
    duration_frames: int = 0          # Duration in native frames

    # Video specifications
    width: int = 1920               # Resolution width
    height: int = 1080              # Resolution height
    codec: str = "h264"             # Video codec (e.g., "h264")
    pixel_format: str = "yuv420p"   # Pixel format (e.g., "yuv420p")
    video_bitrate: int = 5000000    # Video bitrate in bits/sec
    video_profile: Optional[str] = None  # Codec profile (e.g., "high")

    # Audio specifications
    audio_codec: Optional[str] = None     # Audio codec (e.g., "aac")
    audio_bitrate: Optional[int] = None   # Audio bitrate in bits/sec
    sample_rate: Optional[int] = None     # Audio sample rate (e.g., 48000)

    # Camera organization
    camera_path: str = ""    # e.g., "Location1/Camera2" (from parent directories)

    # Timeline position (populated by TimelineCalculatorService)
    start_frame: int = 0     # Start position on timeline (sequence frames)
    end_frame: int = 0       # End position on timeline (sequence frames)
    duration_seq: int = 0    # Duration in sequence frames

    # Frame-accurate timing and diagnostics (NEW for CCTV SMPTE integration)
    first_frame_pts: float = 0.0              # Sub-second offset (e.g., 0.333333)
    first_frame_type: Optional[str] = None    # "I", "P", or "B" frame type
    first_frame_is_keyframe: bool = False     # Closed GOP indicator (True if I-frame)


@dataclass
class TimelinePosition:
    """
    Position of a video segment on the timeline.

    Represents where a video appears in the final chronological timeline,
    including both frame-based and timecode-based representations.
    """

    start_frame: int         # Relative to earliest video (sequence frames)
    end_frame: int           # Relative to earliest video (sequence frames)
    duration_frames: int     # Duration in sequence frames
    start_timecode: str      # SMPTE format (HH:MM:SS:FF)
    end_timecode: str        # SMPTE format (HH:MM:SS:FF)


@dataclass
class Gap:
    """
    Represents a gap in coverage where no camera has footage.

    Gaps are detected by the TimelineCalculatorService and filled
    with slate videos showing the missing time range.
    """

    # Timeline position
    start_frame: int         # Gap start (sequence frames)
    end_frame: int           # Gap end (sequence frames)
    duration_frames: int     # Gap duration (sequence frames)
    duration_seconds: float  # Gap duration (real-world time)

    # Timecode information
    start_timecode: str      # SMPTE format (HH:MM:SS:FF)
    end_timecode: str        # SMPTE format (HH:MM:SS:FF)

    # Generated slate
    slate_video_path: Optional[Path] = None  # Path to generated slate video


@dataclass
class OverlapGroup:
    """
    Represents overlapping cameras with simultaneous footage.

    When multiple cameras have footage during the same time period,
    they are grouped together and a multicam layout is generated.

    Phase 1: Not used (single camera only)
    Phase 2+: Used for side-by-side and grid layouts
    """

    # Timeline position
    start_frame: int         # Overlap start (sequence frames)
    end_frame: int           # Overlap end (sequence frames)
    duration_frames: int     # Overlap duration (sequence frames)

    # Cameras in this overlap
    videos: List[VideoMetadata] = field(default_factory=list)

    # Layout configuration
    layout_type: LayoutType = LayoutType.SINGLE

    # Generated output
    output_video_path: Optional[Path] = None  # Path to generated multicam video


@dataclass
class TimelineSegment:
    """
    A segment of the timeline (single video, gap, or overlap).

    The timeline is divided into ordered segments, each representing
    a distinct period with specific content (footage or gap).
    """

    # Segment classification
    segment_type: Literal["video", "gap", "overlap"]

    # Timeline position
    start_frame: int
    end_frame: int
    duration_frames: int

    # Content (one of these will be populated based on segment_type)
    video: Optional[VideoMetadata] = None
    gap: Optional[Gap] = None
    overlap: Optional[OverlapGroup] = None

    # Final output path (points to original video, slate, or generated layout)
    output_video_path: Optional[Path] = None


@dataclass
class Timeline:
    """
    Complete timeline representation with all segments.

    This is the main data structure produced by TimelineCalculatorService
    and consumed by MulticamRendererService for video generation.
    """

    # Source data
    videos: List[VideoMetadata] = field(default_factory=list)

    # Timeline structure
    segments: List[TimelineSegment] = field(default_factory=list)
    gaps: List[Gap] = field(default_factory=list)
    overlaps: List[OverlapGroup] = field(default_factory=list)

    # Timeline metadata
    earliest_timecode: str = "00:00:00:00"  # SMPTE format
    latest_timecode: str = "00:00:00:00"    # SMPTE format
    total_duration_frames: int = 0          # Total timeline duration (sequence frames)
    total_duration_seconds: float = 0.0     # Total timeline duration (real-world time)
    sequence_fps: float = 30.0              # Normalized timeline FPS


@dataclass
class RenderSettings:
    """
    Settings for multicam video rendering.

    Configures output video specifications, slate appearance,
    and performance optimizations.
    """

    # Output video settings
    output_resolution: tuple[int, int] = (1920, 1080)
    output_fps: float = 30.0
    output_codec: str = "hevc_nvenc"  # Use NVENC for hardware encoding
    output_pixel_format: str = "yuv420p"
    video_bitrate: str = "5M"
    audio_codec: str = "aac"
    audio_bitrate: str = "128k"

    # Audio handling mode (copy, drop, or transcode)
    audio_handling: str = "copy"  # "copy", "drop", or "transcode"

    # Slate settings
    slate_duration_seconds: int = 5
    slate_background_color: str = "#1a1a1a"  # Dark gray
    slate_text_color: str = "white"
    slate_font_size: int = 48
    slate_text_template: str = "GAP: {start} → {end}  (Δ {duration})"  # Legacy field, replaced by preset system

    # Slate text customization (NEW)
    slate_label_preset: str = "gap"  # "gap", "nothing_of_interest", "motion_gap", "chronology_gap", "custom"
    slate_label_custom: str = ""     # Used when preset = "custom"
    slate_time_format: str = "time_only"  # "time_only", "date_time", "duration_multiline"

    # Multi-camera overlap settings (GPT-5 approach)
    split_mode: Literal["side_by_side", "stacked"] = "side_by_side"
    split_alignment: Literal["top", "center", "bottom", "left", "right"] = "center"

    # Performance settings
    use_hardware_accel: bool = False
    hardware_accel_type: Optional[str] = None  # "nvenc", "qsv", "vaapi"
    threads: int = 0  # 0 = auto-detect

    # Three-tier performance system
    use_hardware_decode: bool = False  # GPU decode (NVDEC) - faster but increases argv
    use_batch_rendering: bool = False  # Split into batches for large datasets
    batch_size: int = 150  # Max inputs per batch (stay under Windows argv limit)
    keep_batch_temp_files: bool = False  # Preserve temp files for debugging batch rendering

    # Output paths
    output_directory: Path = Path(".")
    output_filename: str = "multicam_timeline.mp4"


# Slate label presets (user-facing text options)
SLATE_LABEL_PRESETS = {
    "gap": "GAP",
    "nothing_of_interest": "Nothing of Interest",
    "motion_gap": "Motion Gap",
    "chronology_gap": "Gap in Chronology",
    "custom": "[Custom]"  # Placeholder, uses slate_label_custom field
}

# Time format display styles for slate text
SLATE_TIME_FORMATS = {
    "time_only": {
        "name": "HH:MM:SS only",
        "example": "19:35:00 to 19:40:15\nDuration: 5m 15s"
    },
    "date_time": {
        "name": "Full Date & Time",
        "example": "Tue 21 May 19:35:00 → Tue 21 May 19:40:15  (Δ 5m 15s)"
    },
    "duration_multiline": {
        "name": "Multiline Duration",
        "example": "19:35:00 to 19:40:15\nTotal Duration = 5 min 15 sec"
    }
}
