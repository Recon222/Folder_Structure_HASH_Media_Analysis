"""
Timeline calculation service - implements algorithms from Timeline_Calculation_Deep_Dive.md

This service calculates chronological timeline positions from video metadata,
detects gaps in coverage, and prepares data for multicam layout generation.
"""

import math
from typing import List, Optional, Tuple
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

    Implements algorithms from Timeline_Calculation_Deep_Dive.md:
    - Time-based positioning (preserves accuracy across frame rates)
    - Range merging for gap detection (O(N log N))
    - Interval sweep for overlap detection (O(N log N) typical case)

    Phase 1: Gap detection only (single camera)
    Phase 2+: Will add overlap detection for multicam
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

        Uses time-based calculations (not frame-based) to preserve accuracy
        across different native frame rates.

        Args:
            videos: List of video metadata with SMPTE timecodes
            sequence_fps: Target timeline frame rate (default 30.0)
            min_gap_seconds: Minimum gap duration to report (default 5.0)

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

            # Step 1: Convert timecodes to timeline positions (time-based, not frame-based!)
            positioned_videos = self._position_videos(videos, sequence_fps)

            # Step 2: Sort by start frame
            positioned_videos.sort(key=lambda v: v.start_frame)

            # Step 3: Detect gaps
            gaps = self._detect_gaps(positioned_videos, sequence_fps, min_gap_seconds)

            # Step 4: Detect overlaps (Phase 2+, return empty for Phase 1)
            overlaps = []  # Phase 1: Single camera only

            # Step 5: Build segments
            segments = self._build_segments(positioned_videos, gaps, overlaps)

            # Step 6: Calculate timeline metadata
            earliest_video = positioned_videos[0]
            latest_video = max(positioned_videos, key=lambda v: v.end_frame)

            timeline = Timeline(
                videos=positioned_videos,
                segments=segments,
                gaps=gaps,
                overlaps=overlaps,
                earliest_timecode=earliest_video.smpte_timecode,
                latest_timecode=self._calculate_end_timecode(latest_video, sequence_fps),
                total_duration_frames=latest_video.end_frame,
                total_duration_seconds=latest_video.end_frame / sequence_fps,
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

        Critical: This uses seconds as an intermediate representation, NOT frames,
        to avoid cumulative rounding errors.
        """
        # Convert all timecodes to absolute seconds
        video_times = []
        for video in videos:
            # Convert SMPTE to seconds (preserves precision)
            absolute_seconds = self._timecode_to_seconds(
                video.smpte_timecode,
                video.frame_rate
            )
            video_times.append((video, absolute_seconds))

        # Find earliest timecode
        earliest_seconds = min(seconds for _, seconds in video_times)

        # Calculate timeline positions
        positioned = []
        for video, absolute_seconds in video_times:
            # Time offset from earliest (in seconds)
            seconds_offset = absolute_seconds - earliest_seconds

            # Convert to sequence frames with rounding (not truncation!)
            start_frame = round(seconds_offset * sequence_fps)

            # Calculate duration in sequence frames (time-based)
            duration_seconds = video.duration_frames / video.frame_rate
            duration_seq = round(duration_seconds * sequence_fps)
            end_frame = start_frame + duration_seq

            # Create updated metadata with timeline positions
            positioned_video = replace(
                video,
                start_frame=start_frame,
                end_frame=end_frame,
                duration_seq=duration_seq
            )
            positioned.append(positioned_video)

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

        Complexity: O(N log N) for sorting
        """
        if len(videos) < 2:
            return []  # No gaps possible with 0-1 videos

        min_gap_frames = math.ceil(min_gap_seconds * sequence_fps)

        # Step 1: Collect coverage ranges
        ranges = [(v.start_frame, v.end_frame) for v in videos]

        # Step 2: Merge overlapping ranges
        merged = self._merge_ranges(ranges)

        # Step 3: Find gaps between merged ranges
        gaps = []
        for i in range(len(merged) - 1):
            gap_start = merged[i][1]  # End of current range
            gap_end = merged[i + 1][0]  # Start of next range
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

    def _merge_ranges(self, ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """
        Merge overlapping/adjacent ranges.

        Algorithm from Timeline_Calculation_Deep_Dive.md:
        - Sort ranges by start position
        - Iterate and merge when ranges overlap or touch
        - Return consolidated coverage ranges

        Complexity: O(N log N) for sorting
        """
        if not ranges:
            return []

        sorted_ranges = sorted(ranges)  # Sort by start frame
        merged = [sorted_ranges[0]]

        for current in sorted_ranges[1:]:
            previous = merged[-1]

            if current[0] > previous[1]:
                # Gap between ranges: add as separate
                merged.append(current)
            elif current[1] > previous[1]:
                # Overlaps or touches: extend previous range
                merged[-1] = (previous[0], current[1])
            # else: current is fully contained in previous, skip

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
        Phase 2+: Will include overlap segments
        """
        segments = []

        # Create video segments
        for video in videos:
            segment = TimelineSegment(
                segment_type="video",
                start_frame=video.start_frame,
                end_frame=video.end_frame,
                duration_frames=video.duration_seq,
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

    def _timecode_to_seconds(self, timecode: str, fps: float) -> float:
        """
        Convert SMPTE timecode to absolute seconds.

        Uses floating-point precision to preserve accuracy.
        """
        try:
            hours, minutes, seconds, frames = map(int, timecode.split(':'))
            total_seconds = hours * 3600 + minutes * 60 + seconds
            return total_seconds + (frames / fps)
        except Exception as e:
            self.logger.warning(f"Error parsing timecode {timecode}: {e}")
            return 0.0

    def _frames_to_timecode(self, frames: int, fps: float) -> str:
        """
        Convert frame count to SMPTE timecode.

        Handles rounding edge cases to prevent invalid timecodes.
        """
        total_seconds = frames / fps
        hours = int(total_seconds / 3600)
        minutes = int((total_seconds % 3600) / 60)
        seconds = int(total_seconds % 60)
        frames_part = round((total_seconds - int(total_seconds)) * fps)

        # Handle rounding edge case (e.g., 29.99 fps rounds to 30)
        if frames_part >= fps:
            frames_part = 0
            seconds += 1
            if seconds >= 60:
                seconds = 0
                minutes += 1
                if minutes >= 60:
                    minutes = 0
                    hours += 1

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames_part:02d}"

    def _calculate_end_timecode(self, video: VideoMetadata, fps: float) -> str:
        """Calculate the end timecode of a video on the timeline."""
        return self._frames_to_timecode(video.end_frame, fps)
