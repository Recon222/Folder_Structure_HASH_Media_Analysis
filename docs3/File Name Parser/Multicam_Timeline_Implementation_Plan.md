# Multicam Timeline Video Generation - Implementation Plan

**Project:** Seamless Multicam Timeline Video Generation
**Architecture:** Service-Oriented with Worker Pattern
**Timeline:** 8-10 weeks (4 phases)
**Date:** 2025-10-07

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Phase 1: Foundation - Single Camera with Slates (MVP)](#phase-1-foundation---single-camera-with-slates-mvp)
3. [Phase 2: Dual-Camera Side-by-Side](#phase-2-dual-camera-side-by-side)
4. [Phase 3: Multi-Camera Grids (3-6 cameras)](#phase-3-multi-camera-grids-3-6-cameras)
5. [Phase 4: Optimization & Production Ready](#phase-4-optimization--production-ready)
6. [Testing Strategy](#testing-strategy)
7. [Deployment Checklist](#deployment-checklist)

---

## Architecture Overview

### Component Hierarchy

```
filename_parser/
├── models/
│   ├── timeline_models.py           # NEW: Timeline, Gap, Overlap, Segment models
│   ├── video_metadata.py            # NEW: Comprehensive video metadata
│   └── multicam_settings.py         # NEW: Rendering settings
│
├── services/
│   ├── timeline_calculator_service.py    # NEW: Gap/overlap detection
│   ├── ffmpeg_command_builder_service.py # NEW: Command generation
│   ├── video_normalization_service.py    # NEW: Pre-processing
│   ├── slate_generator_service.py        # NEW: Gap slate creation
│   ├── multicam_renderer_service.py      # NEW: Main orchestration
│   └── frame_rate_service.py             # ENHANCE: Add full metadata extraction
│
├── workers/
│   └── multicam_render_worker.py         # NEW: Background rendering thread
│
├── controllers/
│   └── multicam_controller.py            # NEW: UI orchestration
│
└── ui/
    └── multicam_render_tab.py            # NEW: UI (or extend FilenameParserTab)
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. File Selection + Camera Organization (Parent Directory)     │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Filename Parsing (FilenameParserService) ✅ EXISTING         │
│    → Extract SMPTE timecodes from filenames                     │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Metadata Extraction (FrameRateService - ENHANCED)            │
│    → FPS, resolution, codec, duration, pixel format             │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Timeline Calculation (TimelineCalculatorService) NEW         │
│    → Position files chronologically                             │
│    → Detect gaps (no coverage)                                  │
│    → Detect overlaps (multiple cameras)                         │
│    → Assign layout strategies                                   │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Video Normalization (VideoNormalizationService) NEW          │
│    → Convert all videos to common specs (1080p30, h264, yuv420p)│
│    → Enable concat demuxer compatibility                        │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. Slate Generation (SlateGeneratorService) NEW                 │
│    → Create 5-second slates for each gap                        │
│    → Display gap duration and timecodes                         │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. Multicam Layout Generation (MulticamRendererService) NEW     │
│    → Generate xstack commands for overlaps                      │
│    → Create side-by-side / grid layouts                         │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. Final Concatenation (MulticamRendererService) NEW            │
│    → Use concat demuxer for seamless joining                    │
│    → Generate final timeline video                              │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
                   ✅ Final Video Output
```

---

## Phase 1: Foundation - Single Camera with Slates (MVP)

**Duration:** 2-3 weeks
**Goal:** Process single-camera timeline with gap slates (no multi-cam yet)

### Why Start Here?
- Validates timeline calculation algorithms
- Tests slate generation
- Establishes FFmpeg integration patterns
- Provides immediate user value (automated gap visualization)

### 1.1 Create Timeline Models (Day 1-2)

**File:** `filename_parser/models/timeline_models.py`

```python
"""
Timeline data models for multicam video generation.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Literal
from pathlib import Path
from enum import Enum


class LayoutType(str, Enum):
    """Multicam layout strategies"""
    SINGLE = "single"  # One camera (Phase 1)
    SIDE_BY_SIDE = "side_by_side"  # 2 cameras horizontal (Phase 2)
    TRIPLE_SPLIT = "triple_split"  # 3 cameras (Phase 3)
    GRID_2X2 = "grid_2x2"  # 4 cameras (Phase 3)
    GRID_3X2 = "grid_3x2"  # 6 cameras (Phase 3)


@dataclass
class VideoMetadata:
    """Comprehensive video metadata for processing"""
    file_path: Path
    filename: str

    # Timing
    smpte_timecode: str  # From filename parser
    frame_rate: float
    duration_seconds: float
    duration_frames: int

    # Video specs
    width: int
    height: int
    codec: str
    pixel_format: str
    video_bitrate: int
    video_profile: Optional[str] = None

    # Audio specs
    audio_codec: Optional[str] = None
    audio_bitrate: Optional[int] = None
    sample_rate: Optional[int] = None

    # Camera organization
    camera_path: str  # e.g., "Location1/Camera2" (from parent directories)


@dataclass
class TimelinePosition:
    """Position of a video on the timeline"""
    start_frame: int  # Relative to earliest video
    end_frame: int
    duration_frames: int
    start_timecode: str  # SMPTE format
    end_timecode: str


@dataclass
class Gap:
    """Represents a gap in coverage (no camera has footage)"""
    start_frame: int
    end_frame: int
    duration_frames: int
    duration_seconds: float
    start_timecode: str
    end_timecode: str
    slate_video_path: Optional[Path] = None  # Generated slate


@dataclass
class OverlapGroup:
    """Represents overlapping cameras (multiple cameras active simultaneously)"""
    start_frame: int
    end_frame: int
    duration_frames: int
    videos: List[VideoMetadata]  # Cameras active in this period
    layout_type: LayoutType
    output_video_path: Optional[Path] = None  # Generated multicam segment


@dataclass
class TimelineSegment:
    """A segment of the timeline (single camera, gap, or overlap)"""
    segment_type: Literal["video", "gap", "overlap"]
    start_frame: int
    end_frame: int
    duration_frames: int

    # For video segments
    video: Optional[VideoMetadata] = None

    # For gap segments
    gap: Optional[Gap] = None

    # For overlap segments
    overlap: Optional[OverlapGroup] = None

    # Generated output
    output_video_path: Optional[Path] = None


@dataclass
class Timeline:
    """Complete timeline representation"""
    videos: List[VideoMetadata]  # All source videos
    segments: List[TimelineSegment]  # Ordered segments
    gaps: List[Gap]
    overlaps: List[OverlapGroup]

    # Timeline metadata
    earliest_timecode: str  # SMPTE
    latest_timecode: str
    total_duration_frames: int
    total_duration_seconds: float
    sequence_fps: float = 30.0  # Normalized timeline FPS


@dataclass
class RenderSettings:
    """Settings for multicam video rendering"""
    output_resolution: tuple[int, int] = (1920, 1080)
    output_fps: float = 30.0
    output_codec: str = "libx264"
    output_pixel_format: str = "yuv420p"
    video_bitrate: str = "5M"
    audio_codec: str = "aac"
    audio_bitrate: str = "128k"

    # Slate settings
    slate_duration_seconds: int = 5
    slate_background_color: str = "#1a1a1a"
    slate_text_color: str = "white"
    slate_font_size: int = 48

    # Performance
    use_hardware_accel: bool = False
    hardware_accel_type: Optional[str] = None  # "nvenc", "qsv", "vaapi"
    threads: int = 0  # 0 = auto

    # Output
    output_directory: Path = Path(".")
    output_filename: str = "multicam_timeline.mp4"
```

### 1.2 Enhance FrameRateService (Day 2-3)

**File:** `filename_parser/services/frame_rate_service.py` (MODIFY EXISTING)

```python
"""
Enhanced frame rate service with comprehensive metadata extraction.
"""
import json
import subprocess
from pathlib import Path
from typing import Optional

from core.services.base_service import BaseService
from core.result_types import Result
from core.exceptions import FileOperationError

from filename_parser.models.timeline_models import VideoMetadata
from filename_parser.core.binary_manager import binary_manager


class FrameRateService(BaseService):
    """Enhanced service for video metadata extraction."""

    # ... existing methods ...

    def extract_video_metadata(
        self,
        file_path: Path,
        smpte_timecode: str,
        camera_path: str
    ) -> Result[VideoMetadata]:
        """
        Extract comprehensive video metadata using FFprobe.

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
            # Single FFprobe call for all metadata
            cmd = [
                binary_manager.get_ffprobe_path(),
                "-v", "error",
                "-show_entries",
                "stream=codec_name,width,height,r_frame_rate,pix_fmt,profile,bit_rate,sample_rate,channels",
                "-show_entries", "format=duration",
                "-of", "json",
                str(file_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
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
            num, den = map(int, r_frame_rate.split("/"))
            fps = num / den if den != 0 else 30.0

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
        except Exception as e:
            return Result.error(
                FileOperationError(
                    f"Unexpected error extracting metadata: {e}",
                    user_message=f"Failed to analyze {file_path.name}",
                    context={"file_path": str(file_path), "error": str(e)}
                )
            )
```

### 1.3 Create TimelineCalculatorService (Day 3-5)

**File:** `filename_parser/services/timeline_calculator_service.py`

```python
"""
Timeline calculation service - implements algorithms from Timeline_Calculation_Deep_Dive.md
"""
import math
from typing import List, Optional
from dataclasses import replace

from core.services.base_service import BaseService
from core.result_types import Result
from core.exceptions import ValidationError

from filename_parser.models.timeline_models import (
    VideoMetadata,
    Timeline,
    TimelineSegment,
    Gap,
    OverlapGroup,
    LayoutType,
    TimelinePosition
)
from filename_parser.services.smpte_converter import SMPTEConverter


class TimelineCalculatorService(BaseService):
    """
    Calculates chronological timeline with gap and overlap detection.

    Implements algorithms from Timeline_Calculation_Deep_Dive.md
    """

    def __init__(self):
        super().__init__("TimelineCalculatorService")
        self.converter = SMPTEConverter()

    def calculate_timeline(
        self,
        videos: List[VideoMetadata],
        sequence_fps: float = 30.0,
        min_gap_seconds: float = 5.0
    ) -> Result[Timeline]:
        """
        Calculate chronological timeline from video metadata.

        Args:
            videos: List of video metadata with SMPTE timecodes
            sequence_fps: Target timeline frame rate
            min_gap_seconds: Minimum gap duration to report

        Returns:
            Result containing Timeline or error
        """
        if not videos:
            return Result.error(
                ValidationError(
                    "No videos provided",
                    user_message="Please select video files to process."
                )
            )

        try:
            self.logger.info(f"Calculating timeline for {len(videos)} videos at {sequence_fps}fps")

            # Step 1: Convert timecodes to timeline positions
            positioned_videos = self._position_videos(videos, sequence_fps)

            # Step 2: Sort by start frame
            positioned_videos.sort(key=lambda v: self._get_start_frame(v))

            # Step 3: Detect gaps
            gaps = self._detect_gaps(positioned_videos, sequence_fps, min_gap_seconds)

            # Step 4: Detect overlaps (Phase 2+, return empty for Phase 1)
            overlaps = []  # Phase 1: Single camera only

            # Step 5: Build segments
            segments = self._build_segments(positioned_videos, gaps, overlaps)

            # Step 6: Calculate timeline metadata
            earliest_video = positioned_videos[0]
            latest_video = max(positioned_videos, key=lambda v: self._get_end_frame(v))

            timeline = Timeline(
                videos=positioned_videos,
                segments=segments,
                gaps=gaps,
                overlaps=overlaps,
                earliest_timecode=self._get_timecode(earliest_video),
                latest_timecode=self._get_end_timecode(latest_video),
                total_duration_frames=self._get_end_frame(latest_video),
                total_duration_seconds=self._get_end_frame(latest_video) / sequence_fps,
                sequence_fps=sequence_fps
            )

            self.logger.info(
                f"Timeline calculated: {len(segments)} segments, "
                f"{len(gaps)} gaps, {len(overlaps)} overlaps"
            )

            return Result.success(timeline)

        except Exception as e:
            self.logger.error(f"Timeline calculation failed: {e}", exc_info=True)
            return Result.error(
                ValidationError(
                    f"Timeline calculation failed: {e}",
                    user_message="Failed to calculate timeline. Check video timecodes.",
                    context={"error": str(e)}
                )
            )

    def _position_videos(
        self,
        videos: List[VideoMetadata],
        sequence_fps: float
    ) -> List[VideoMetadata]:
        """
        Convert SMPTE timecodes to timeline frame positions.

        Uses time-based calculation (from Timeline_Calculation_Deep_Dive.md)
        to preserve accuracy across different frame rates.
        """
        positioned = []

        # Convert all timecodes to absolute seconds
        for video in videos:
            # Convert SMPTE to seconds
            absolute_seconds = self.converter.timecode_to_seconds(
                video.smpte_timecode,
                video.frame_rate
            )

            # Store as extended metadata (hack: use dict to add fields temporarily)
            video_dict = video.__dict__.copy()
            video_dict["_absolute_seconds"] = absolute_seconds
            video_dict["_duration_seconds"] = video.duration_frames / video.frame_rate

            positioned.append(video.__class__(**video_dict))

        # Find earliest timecode
        earliest_seconds = min(v._absolute_seconds for v in positioned)

        # Calculate timeline positions
        for video in positioned:
            # Offset from earliest
            seconds_offset = video._absolute_seconds - earliest_seconds

            # Convert to sequence frames (time-based, not frame-based!)
            start_frame = round(seconds_offset * sequence_fps)
            duration_seq = round(video._duration_seconds * sequence_fps)
            end_frame = start_frame + duration_seq

            # Store positions (hack: add more fields)
            video._start_frame = start_frame
            video._end_frame = end_frame
            video._duration_seq = duration_seq

        return positioned

    def _detect_gaps(
        self,
        videos: List[VideoMetadata],
        sequence_fps: float,
        min_gap_seconds: float
    ) -> List[Gap]:
        """
        Detect gaps in coverage using range merging algorithm.

        Implementation from Timeline_Calculation_Deep_Dive.md:
        1. Collect coverage ranges
        2. Merge overlapping ranges
        3. Find gaps between merged ranges
        """
        if len(videos) < 2:
            return []  # No gaps possible with 0-1 videos

        min_gap_frames = math.ceil(min_gap_seconds * sequence_fps)

        # Step 1: Collect coverage ranges
        ranges = [(self._get_start_frame(v), self._get_end_frame(v)) for v in videos]

        # Step 2: Merge overlapping ranges
        merged = self._merge_ranges(ranges)

        # Step 3: Find gaps
        gaps = []
        for i in range(len(merged) - 1):
            gap_start = merged[i][1]
            gap_end = merged[i + 1][0]
            gap_duration = gap_end - gap_start

            if gap_duration >= min_gap_frames:
                gap = Gap(
                    start_frame=gap_start,
                    end_frame=gap_end,
                    duration_frames=gap_duration,
                    duration_seconds=gap_duration / sequence_fps,
                    start_timecode=self._frames_to_timecode(gap_start, sequence_fps),
                    end_timecode=self._frames_to_timecode(gap_end, sequence_fps)
                )
                gaps.append(gap)

        return gaps

    def _merge_ranges(self, ranges: List[tuple[int, int]]) -> List[tuple[int, int]]:
        """
        Merge overlapping/adjacent ranges.

        Algorithm from Timeline_Calculation_Deep_Dive.md
        """
        if not ranges:
            return []

        sorted_ranges = sorted(ranges)
        merged = [sorted_ranges[0]]

        for current in sorted_ranges[1:]:
            previous = merged[-1]

            if current[0] > previous[1]:
                # Gap: add as separate range
                merged.append(current)
            elif current[1] > previous[1]:
                # Overlap: extend previous range
                merged[-1] = (previous[0], current[1])
            # else: current fully contained, skip

        return merged

    def _build_segments(
        self,
        videos: List[VideoMetadata],
        gaps: List[Gap],
        overlaps: List[OverlapGroup]
    ) -> List[TimelineSegment]:
        """
        Build ordered list of timeline segments (videos + gaps).

        Phase 1: Only video and gap segments (no overlaps yet)
        """
        segments = []

        # Create video segments
        for video in videos:
            segment = TimelineSegment(
                segment_type="video",
                start_frame=self._get_start_frame(video),
                end_frame=self._get_end_frame(video),
                duration_frames=self._get_duration(video),
                video=video
            )
            segments.append(segment)

        # Create gap segments
        for gap in gaps:
            segment = TimelineSegment(
                segment_type="gap",
                start_frame=gap.start_frame,
                end_frame=gap.end_frame,
                duration_frames=gap.duration_frames,
                gap=gap
            )
            segments.append(segment)

        # Sort by start frame
        segments.sort(key=lambda s: s.start_frame)

        return segments

    # Helper methods
    def _get_start_frame(self, video: VideoMetadata) -> int:
        return getattr(video, "_start_frame", 0)

    def _get_end_frame(self, video: VideoMetadata) -> int:
        return getattr(video, "_end_frame", 0)

    def _get_duration(self, video: VideoMetadata) -> int:
        return getattr(video, "_duration_seq", 0)

    def _get_timecode(self, video: VideoMetadata) -> str:
        return video.smpte_timecode

    def _get_end_timecode(self, video: VideoMetadata) -> str:
        end_frame = self._get_end_frame(video)
        return self._frames_to_timecode(end_frame, 30.0)

    def _frames_to_timecode(self, frames: int, fps: float) -> str:
        """Convert frame count to SMPTE timecode"""
        total_seconds = frames / fps
        hours = int(total_seconds / 3600)
        minutes = int((total_seconds % 3600) / 60)
        seconds = int(total_seconds % 60)
        frames_part = round((total_seconds - int(total_seconds)) * fps)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames_part:02d}"
```

### 1.4 Create SlateGeneratorService (Day 5-6)

**File:** `filename_parser/services/slate_generator_service.py`

```python
"""
Slate generator service - creates gap title cards using FFmpeg lavfi
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
    """Service for generating gap slates with FFmpeg lavfi color source"""

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

        Args:
            gap: Gap information
            settings: Render settings
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

            # Format duration nicely
            duration_str = self._format_duration(gap.duration_seconds)

            # Build FFmpeg command
            cmd = self._build_slate_command(
                gap=gap,
                settings=settings,
                output_path=output_path,
                duration_str=duration_str
            )

            # Execute FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
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
        """Build FFmpeg command for slate generation"""
        width, height = settings.output_resolution

        # Build drawtext filters for multi-line slate
        drawtext_filters = [
            # Title
            f"drawtext=text='NO COVERAGE':"
            f"fontsize=64:"
            f"fontcolor=#ff4d4f:"
            f"x=(w-text_w)/2:"
            f"y=300",

            # Duration
            f"drawtext=text='Gap Duration\\: {duration_str}':"
            f"fontsize=32:"
            f"fontcolor=white:"
            f"x=(w-text_w)/2:"
            f"y=400",

            # Timecodes
            f"drawtext=text='Start\\: {self._escape_colons(gap.start_timecode)}  |  End\\: {self._escape_colons(gap.end_timecode)}':"
            f"fontsize=24:"
            f"fontcolor=#6b6b6b:"
            f"x=(w-text_w)/2:"
            f"y=500"
        ]

        vf_filter = ",".join(drawtext_filters)

        cmd = [
            binary_manager.get_ffmpeg_path(),
            "-f", "lavfi",
            "-i", f"color=c={settings.slate_background_color}:s={width}x{height}:d={settings.slate_duration_seconds}",
            "-vf", vf_filter,
            "-pix_fmt", settings.output_pixel_format,
            "-c:v", settings.output_codec,
            "-b:v", settings.video_bitrate,
            "-r", str(settings.output_fps),
            "-y",  # Overwrite output
            str(output_path)
        ]

        return cmd

    def _format_duration(self, seconds: float) -> str:
        """Format duration as human-readable string"""
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    def _escape_colons(self, timecode: str) -> str:
        """Escape colons for FFmpeg drawtext filter"""
        return timecode.replace(":", "\\:")
```

### 1.5 Create FFmpegCommandBuilderService (Day 6-7)

**File:** `filename_parser/services/ffmpeg_command_builder_service.py`

```python
"""
FFmpeg command builder service - generates FFmpeg command strings programmatically
"""
from pathlib import Path
from typing import List

from core.services.base_service import BaseService

from filename_parser.models.timeline_models import TimelineSegment, RenderSettings
from filename_parser.core.binary_manager import binary_manager


class FFmpegCommandBuilderService(BaseService):
    """Service for building FFmpeg command strings"""

    def __init__(self):
        super().__init__("FFmpegCommandBuilderService")

    def build_concat_command(
        self,
        segments: List[TimelineSegment],
        settings: RenderSettings,
        output_path: Path,
        concat_list_path: Path
    ) -> list[str]:
        """
        Build FFmpeg concat demuxer command.

        Args:
            segments: Ordered timeline segments (with output_video_path set)
            settings: Render settings
            output_path: Final output video path
            concat_list_path: Temporary file for concat list

        Returns:
            FFmpeg command as list of strings
        """
        # Create concat list file
        self._write_concat_list(segments, concat_list_path)

        cmd = [
            binary_manager.get_ffmpeg_path(),
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_path),
            "-c", "copy",  # Stream copy (no re-encode!)
            "-y",  # Overwrite output
            str(output_path)
        ]

        return cmd

    def _write_concat_list(
        self,
        segments: List[TimelineSegment],
        concat_list_path: Path
    ):
        """Write concat demuxer list file"""
        with open(concat_list_path, "w") as f:
            for segment in segments:
                if segment.output_video_path and segment.output_video_path.exists():
                    # Escape single quotes in path
                    path_str = str(segment.output_video_path).replace("'", "'\\''")
                    f.write(f"file '{path_str}'\n")
```

### 1.6 Create MulticamRendererService (Day 7-10)

**File:** `filename_parser/services/multicam_renderer_service.py`

```python
"""
Multicam renderer service - orchestrates the entire rendering pipeline
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
        """Generate slate videos for all gaps"""
        for i, gap in enumerate(timeline.gaps):
            slate_path = temp_path / f"slate_gap_{i:03d}.mp4"

            result = self.slate_gen.generate_slate(gap, settings, slate_path)
            if not result.success:
                return result

            # Store slate path in gap
            gap.slate_video_path = slate_path

        return Result.success(None)

    def _prepare_segments(
        self,
        timeline: Timeline,
        settings: RenderSettings
    ) -> List[TimelineSegment]:
        """
        Prepare segments for concatenation.

        Phase 1: Map video segments to source files, gap segments to slates
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

        return prepared

    def _concatenate_segments(
        self,
        segments: List[TimelineSegment],
        settings: RenderSettings,
        output_path: Path,
        temp_path: Path,
        progress_callback: Optional[Callable]
    ) -> Result[Path]:
        """Concatenate all segments into final video"""
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

            # Monitor progress (FFmpeg writes to stderr)
            for line in process.stderr:
                if progress_callback:
                    # Parse FFmpeg progress (simplified)
                    if "time=" in line:
                        # Extract progress from FFmpeg output
                        # TODO: Calculate percentage based on total duration
                        progress_callback(50, "Concatenating...")

            process.wait()

            if process.returncode != 0:
                stderr = process.stderr.read() if process.stderr else "Unknown error"
                return Result.error(
                    FileOperationError(
                        f"FFmpeg concatenation failed: {stderr}",
                        user_message="Failed to concatenate timeline segments",
                        context={"stderr": stderr}
                    )
                )

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
```

### 1.7 Testing Phase 1 (Day 10-12)

**Create test cases:**

1. **Single video, no gaps** - Should output identical to source
2. **Two videos with gap** - Should output video + slate + video
3. **Three videos with multiple gaps** - Should handle multiple slates
4. **Different frame rates** - Should normalize to common FPS
5. **Different resolutions** - Should scale consistently

---

## Phase 2: Dual-Camera Side-by-Side

**Duration:** 2 weeks
**Goal:** Detect overlaps and generate side-by-side layouts

### 2.1 Enhance TimelineCalculatorService (Day 1-3)

**File:** `filename_parser/services/timeline_calculator_service.py` (MODIFY)

Add overlap detection algorithm from Timeline_Calculation_Deep_Dive.md:

```python
def _detect_overlaps(
    self,
    videos: List[VideoMetadata],
    sequence_fps: float
) -> List[OverlapGroup]:
    """
    Detect overlapping cameras using interval sweep algorithm.

    Implementation from Timeline_Calculation_Deep_Dive.md
    """
    if len(videos) < 2:
        return []  # No overlaps possible

    # Step 1: Collect all time points (start/end frames)
    time_points = set()
    for video in videos:
        time_points.add(self._get_start_frame(video))
        time_points.add(self._get_end_frame(video))

    sorted_time_points = sorted(time_points)

    # Step 2: Process each interval
    overlap_groups = []
    for i in range(len(sorted_time_points) - 1):
        interval_start = sorted_time_points[i]
        interval_end = sorted_time_points[i + 1]

        # Find active videos in this interval
        active_videos = []
        for video in videos:
            if (self._get_start_frame(video) <= interval_start and
                self._get_end_frame(video) > interval_start):
                active_videos.append(video)

        # If multiple videos active, it's an overlap
        if len(active_videos) >= 2:
            # Check if can merge with previous group
            if (overlap_groups and
                overlap_groups[-1].end_frame == interval_start and
                set(v.file_path for v in overlap_groups[-1].videos) ==
                set(v.file_path for v in active_videos)):
                # Same cameras: extend previous group
                overlap_groups[-1].end_frame = interval_end
            else:
                # Different cameras: create new group
                layout_type = self._determine_layout(len(active_videos))
                overlap = OverlapGroup(
                    start_frame=interval_start,
                    end_frame=interval_end,
                    duration_frames=interval_end - interval_start,
                    videos=sorted(active_videos, key=lambda v: v.camera_path),
                    layout_type=layout_type
                )
                overlap_groups.append(overlap)

    return overlap_groups

def _determine_layout(self, num_cameras: int) -> LayoutType:
    """Determine layout strategy based on camera count"""
    if num_cameras == 1:
        return LayoutType.SINGLE
    elif num_cameras == 2:
        return LayoutType.SIDE_BY_SIDE
    elif num_cameras == 3:
        return LayoutType.TRIPLE_SPLIT
    elif num_cameras == 4:
        return LayoutType.GRID_2X2
    elif num_cameras >= 5:
        return LayoutType.GRID_3X2
    else:
        return LayoutType.SINGLE
```

### 2.2 Create MulticamLayoutService (Day 3-6)

**File:** `filename_parser/services/multicam_layout_service.py`

```python
"""
Multicam layout service - generates side-by-side and grid layouts using FFmpeg xstack
"""
import subprocess
from pathlib import Path
from typing import List

from core.services.base_service import BaseService
from core.result_types import Result
from core.exceptions import FileOperationError

from filename_parser.models.timeline_models import OverlapGroup, RenderSettings, LayoutType
from filename_parser.core.binary_manager import binary_manager


class MulticamLayoutService(BaseService):
    """Service for generating multicam split-screen layouts"""

    def __init__(self):
        super().__init__("MulticamLayoutService")

    def generate_layout(
        self,
        overlap: OverlapGroup,
        settings: RenderSettings,
        output_path: Path
    ) -> Result[Path]:
        """
        Generate multicam layout for overlapping cameras.

        Args:
            overlap: Overlap group with videos and layout type
            settings: Render settings
            output_path: Where to save layout video

        Returns:
            Result containing output path or error
        """
        if overlap.layout_type == LayoutType.SIDE_BY_SIDE:
            return self._generate_side_by_side(overlap, settings, output_path)
        # Phase 3: Add grid layouts
        else:
            return Result.error(
                FileOperationError(
                    f"Layout type {overlap.layout_type} not yet implemented",
                    user_message="This multicam layout is not yet supported"
                )
            )

    def _generate_side_by_side(
        self,
        overlap: OverlapGroup,
        settings: RenderSettings,
        output_path: Path
    ) -> Result[Path]:
        """Generate side-by-side (2-camera horizontal) layout"""
        if len(overlap.videos) != 2:
            return Result.error(
                FileOperationError(
                    f"Side-by-side requires 2 cameras, got {len(overlap.videos)}",
                    user_message="Invalid camera count for side-by-side layout"
                )
            )

        try:
            self.logger.info(f"Generating side-by-side layout: {output_path}")

            # Extract overlap portion from each video
            cam1, cam2 = overlap.videos[0], overlap.videos[1]

            # Calculate trim points (in seconds)
            start_offset_1 = (overlap.start_frame - cam1._start_frame) / settings.output_fps
            start_offset_2 = (overlap.start_frame - cam2._start_frame) / settings.output_fps
            duration = overlap.duration_frames / settings.output_fps

            # Build FFmpeg command
            cmd = [
                binary_manager.get_ffmpeg_path(),
                "-ss", str(start_offset_1), "-i", str(cam1.file_path), "-t", str(duration),
                "-ss", str(start_offset_2), "-i", str(cam2.file_path), "-t", str(duration),
                "-filter_complex",
                f"[0:v]scale={settings.output_resolution[0]//2}:{settings.output_resolution[1]}[left];"
                f"[1:v]scale={settings.output_resolution[0]//2}:{settings.output_resolution[1]}[right];"
                f"[left][right]hstack=inputs=2[v]",
                "-map", "[v]",
                "-c:v", settings.output_codec,
                "-b:v", settings.video_bitrate,
                "-pix_fmt", settings.output_pixel_format,
                "-r", str(settings.output_fps),
                "-y",
                str(output_path)
            ]

            self.logger.debug(f"FFmpeg side-by-side command: {' '.join(cmd)}")

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            self.logger.info(f"Side-by-side layout generated: {output_path}")
            return Result.success(output_path)

        except subprocess.CalledProcessError as e:
            self.logger.error(f"FFmpeg layout generation failed: {e.stderr}")
            return Result.error(
                FileOperationError(
                    f"Layout generation failed: {e.stderr}",
                    user_message="Failed to create multicam layout",
                    context={"error": e.stderr}
                )
            )
        except Exception as e:
            self.logger.error(f"Unexpected layout generation error: {e}", exc_info=True)
            return Result.error(
                FileOperationError(
                    f"Unexpected error: {e}",
                    user_message="Failed to create multicam layout",
                    context={"error": str(e)}
                )
            )
```

### 2.3 Update MulticamRendererService (Day 6-8)

Modify `_prepare_segments()` to generate multicam layouts for overlap segments:

```python
def _prepare_segments(
    self,
    timeline: Timeline,
    settings: RenderSettings,
    temp_path: Path,
    progress_callback: Optional[Callable]
) -> Result[List[TimelineSegment]]:
    """
    Prepare segments - now includes multicam layout generation
    """
    prepared = []
    layout_service = MulticamLayoutService()

    for i, segment in enumerate(timeline.segments):
        if segment.segment_type == "video":
            segment.output_video_path = segment.video.file_path
            prepared.append(segment)

        elif segment.segment_type == "gap":
            segment.output_video_path = segment.gap.slate_video_path
            prepared.append(segment)

        elif segment.segment_type == "overlap":
            # NEW: Generate multicam layout
            if progress_callback:
                progress_callback(
                    40 + (i / len(timeline.segments)) * 50,
                    f"Generating multicam layout {i+1}..."
                )

            layout_path = temp_path / f"layout_overlap_{i:03d}.mp4"
            layout_result = layout_service.generate_layout(
                segment.overlap,
                settings,
                layout_path
            )

            if not layout_result.success:
                return layout_result

            segment.output_video_path = layout_path
            prepared.append(segment)

    return Result.success(prepared)
```

### 2.4 Testing Phase 2 (Day 8-10)

Test cases:
1. **Two cameras, partial overlap** - Should create side-by-side segment
2. **Two cameras, full overlap** - Entire timeline side-by-side
3. **Three cameras, pairwise overlaps** - Multiple layout segments
4. **Overlap + gaps** - Mix of layouts and slates

---

## Phase 3: Multi-Camera Grids (3-6 cameras)

**Duration:** 2-3 weeks
**Goal:** Support 3-6 camera grid layouts

### 3.1 Implement Grid Layouts (Day 1-7)

Extend `MulticamLayoutService` with:
- Triple split (2 top, 1 bottom)
- 2x2 grid (4 cameras)
- 3x2 grid (6 cameras)

Use FFmpeg `xstack` filter for custom positioning.

### 3.2 Testing Phase 3 (Day 7-10)

Test with real forensic footage scenarios.

---

## Phase 4: Optimization & Production Ready

**Duration:** 2 weeks
**Goal:** Performance optimization and polish

### 4.1 GPU Acceleration (Day 1-3)

Implement hardware encoder support:
- NVIDIA NVENC (h264_nvenc)
- Intel QuickSync (h264_qsv)
- Auto-detection and fallback

### 4.2 Segment Caching (Day 3-5)

Cache generated segments to avoid re-rendering unchanged portions.

### 4.3 Progress Tracking (Day 5-7)

Improve FFmpeg progress parsing for accurate percentage display.

### 4.4 Final Testing & Documentation (Day 7-14)

- Comprehensive test suite
- User documentation
- Performance benchmarks

---

## Testing Strategy

### Unit Tests

```python
# tests/test_timeline_calculator.py
def test_single_video_no_gaps():
    """Timeline with one video should have no gaps"""

def test_two_videos_with_gap():
    """Gap detection between two videos"""

def test_overlap_detection():
    """Detect when two cameras overlap"""

# tests/test_slate_generator.py
def test_slate_generation():
    """Generate gap slate with correct text"""

# tests/test_multicam_layout.py
def test_side_by_side_layout():
    """Generate 2-camera side-by-side"""
```

### Integration Tests

```python
# tests/test_multicam_integration.py
def test_complete_timeline_render():
    """End-to-end timeline rendering"""

def test_mixed_segments():
    """Timeline with videos, gaps, and overlaps"""
```

### Performance Tests

Benchmark with:
- 2-hour timeline, 4 cameras
- Various resolutions (720p, 1080p, 4K)
- Different hardware configurations

---

## Deployment Checklist

### Pre-Deployment
- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Performance benchmarks meet targets
- [ ] Documentation complete
- [ ] FFmpeg dependency documented

### Deployment
- [ ] Merge to main branch
- [ ] Tag release (v1.0.0-multicam)
- [ ] Update CLAUDE.md
- [ ] User training materials

### Post-Deployment
- [ ] Monitor user feedback
- [ ] Track performance metrics
- [ ] Bug fixes and optimizations

---

## Timeline Summary

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1 | 2-3 weeks | Single camera with slates (MVP) |
| Phase 2 | 2 weeks | Dual-camera side-by-side |
| Phase 3 | 2-3 weeks | Multi-camera grids (3-6 cameras) |
| Phase 4 | 2 weeks | Optimization & production ready |
| **Total** | **8-10 weeks** | **Fully functional multicam timeline generator** |

---

## Success Criteria

✅ **Phase 1 Complete When:**
- Can process single-camera timeline
- Gaps replaced with 5-second slates
- Slates display timecode information
- Output is seamless MP4

✅ **Phase 2 Complete When:**
- Detects 2-camera overlaps
- Generates side-by-side layouts
- Integrates layouts into timeline

✅ **Phase 3 Complete When:**
- Supports 3-6 camera grids
- Automatic layout selection
- All layouts work correctly

✅ **Phase 4 Complete When:**
- GPU acceleration working
- Segment caching functional
- Performance meets benchmarks
- Documentation complete

---

**Ready to start? Begin with Phase 1, Day 1: Create Timeline Models** 🚀
