"""
SMPTE timecode conversion service.

This service handles conversion of time data to SMPTE timecode format
and application of time offsets.
"""

import math
from typing import Optional, Dict, Any
from filename_parser.models.time_models import TimeData
from filename_parser.core.time_utils import milliseconds_to_frames, apply_time_offset as apply_offset_util
from core.logger import logger


def is_valid_frame_rate(fps: float) -> bool:
    """Validate frame rate is within reasonable bounds."""
    return 1.0 <= fps <= 240.0


class SMPTEConverter:
    """
    Service for converting time data to SMPTE timecode.

    Handles conversion from TimeData to SMPTE format (HH:MM:SS:FF)
    and application of time offsets.
    """

    def convert_to_smpte(
        self, time_data: TimeData, fps: float = 30.0
    ) -> Optional[str]:
        """
        Convert time data to SMPTE timecode format (HH:MM:SS:FF).

        Args:
            time_data: TimeData object with time components
            fps: Frames per second for SMPTE calculation

        Returns:
            SMPTE timecode string or None if conversion failed
        """
        if not is_valid_frame_rate(fps):
            logger.error(f"Invalid frame rate for SMPTE conversion: {fps}")
            return None

        logger.debug(
            f"Converting to SMPTE: {time_data.time_string} at {fps} fps"
        )

        # Extract time components
        hours = time_data.hours
        minutes = time_data.minutes
        seconds = time_data.seconds

        # Handle millisecond to frame conversion if needed
        if time_data.is_milliseconds and time_data.milliseconds > 0:
            milliseconds = time_data.milliseconds
            logger.debug(
                f"Converting {milliseconds}ms to frames at {fps} fps"
            )
            frames = milliseconds_to_frames(milliseconds, fps)
            logger.debug(f"Converted to {frames} frames")
        else:
            frames = time_data.frames

        # Normalize frames if they exceed the frame rate
        max_frames = math.ceil(fps) - 1
        if frames > max_frames:
            logger.warning(
                f"Frame number {frames} exceeds maximum {max_frames} for {fps} fps"
            )

            # Carry over to seconds
            seconds += frames // math.ceil(fps)
            frames = frames % math.ceil(fps)

            # Normalize time components
            if seconds >= 60:
                minutes += seconds // 60
                seconds = seconds % 60

            if minutes >= 60:
                hours += minutes // 60
                minutes = minutes % 60

            hours = hours % 24

            logger.debug(
                f"Adjusted time: {hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"
            )

        # Format as SMPTE timecode
        smpte_timecode = f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

        logger.info(f"Converted to SMPTE timecode: {smpte_timecode}")
        return smpte_timecode

    def apply_time_offset(
        self,
        smpte_timecode: str,
        offset_hours: int = 0,
        offset_minutes: int = 0,
        offset_seconds: int = 0,
        direction: str = "behind",
    ) -> Optional[str]:
        """
        Apply time offset to a SMPTE timecode.

        Args:
            smpte_timecode: SMPTE timecode string (HH:MM:SS:FF)
            offset_hours: Hours to offset
            offset_minutes: Minutes to offset
            offset_seconds: Seconds to offset
            direction: "behind" (add offset) or "ahead" (subtract offset)

        Returns:
            Adjusted SMPTE timecode or None if application failed
        """
        # Check if any offset is non-zero
        has_offset = (
            offset_hours > 0 or offset_minutes > 0 or offset_seconds > 0
        )

        if not has_offset:
            logger.debug("No time offset to apply, returning original timecode")
            return smpte_timecode

        logger.debug(
            f"Applying time offset: {offset_hours}h {offset_minutes}m {offset_seconds}s "
            f"({direction}) to {smpte_timecode}"
        )

        # Build offset dictionary for core utility
        time_offset = {
            "hours": offset_hours,
            "minutes": offset_minutes,
            "seconds": offset_seconds,
            "direction": direction,
        }

        try:
            adjusted_timecode = apply_offset_util(smpte_timecode, time_offset)

            if adjusted_timecode:
                logger.info(
                    f"Applied time offset: {smpte_timecode} -> {adjusted_timecode}"
                )
                return adjusted_timecode
            else:
                logger.error("Time offset application failed")
                return None

        except Exception as e:
            logger.error(f"Error applying time offset: {str(e)}")
            return None

    def apply_time_offset_from_dict(
        self, smpte_timecode: str, time_offset: Dict[str, Any]
    ) -> Optional[str]:
        """
        Apply time offset using a dictionary configuration.

        Args:
            smpte_timecode: SMPTE timecode string
            time_offset: Dictionary with hours, minutes, seconds, direction

        Returns:
            Adjusted SMPTE timecode or None if application failed
        """
        if not time_offset:
            return smpte_timecode

        return self.apply_time_offset(
            smpte_timecode,
            offset_hours=time_offset.get("hours", 0),
            offset_minutes=time_offset.get("minutes", 0),
            offset_seconds=time_offset.get("seconds", 0),
            direction=time_offset.get("direction", "behind"),
        )
