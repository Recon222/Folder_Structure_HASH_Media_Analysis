"""
Time and frame calculation utilities for SMPTE timecode operations.

This module provides functions for manipulating time, frames, and SMPTE timecodes,
including conversion between different formats and applying time offsets.
"""

import re
import math
from typing import Dict, Tuple, Optional, Union, Any


def milliseconds_to_frames(milliseconds: int, fps: float) -> int:
    """
    Convert milliseconds to frame number based on frame rate.

    Args:
        milliseconds: Millisecond value (0-999)
        fps: Frames per second

    Returns:
        Frame number (0 to fps-1)
    """
    if milliseconds < 0 or milliseconds > 999:
        # Clamp to valid range
        milliseconds = max(0, min(999, milliseconds))

    # Calculate frames
    frames_float = (milliseconds / 1000.0) * fps
    frames = round(frames_float)

    # Handle edge case where rounding puts us at exactly fps
    if frames == round(fps):
        frames = 0
        # Note: We don't increment seconds here because that's handled by the caller

    return frames


def frames_to_milliseconds(frames: int, fps: float) -> int:
    """
    Convert frame number to milliseconds based on frame rate.

    Args:
        frames: Frame number (0 to fps-1)
        fps: Frames per second

    Returns:
        Millisecond value (0-999)
    """
    if frames < 0 or frames >= math.ceil(fps):
        # Clamp to valid range
        frames = max(0, min(math.ceil(fps) - 1, frames))

    # Calculate milliseconds
    milliseconds = round((frames / fps) * 1000.0)

    # Ensure result is within valid range
    return max(0, min(999, milliseconds))


def format_smpte(hours: int, minutes: int, seconds: int, frames: int) -> str:
    """
    Format time components as SMPTE timecode.

    Args:
        hours: Hours component (0-23)
        minutes: Minutes component (0-59)
        seconds: Seconds component (0-59)
        frames: Frames component (0 to fps-1)

    Returns:
        SMPTE timecode string (HH:MM:SS:FF)
    """
    # Normalize values
    hours = max(0, min(23, hours))
    minutes = max(0, min(59, minutes))
    seconds = max(0, min(59, seconds))
    frames = max(0, min(99, frames))  # Allow up to 99 for high frame rate formats

    # Format as SMPTE timecode
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


def parse_smpte(timecode: str) -> Optional[Dict[str, int]]:
    """
    Parse SMPTE timecode into components.

    Args:
        timecode: SMPTE timecode string (HH:MM:SS:FF)

    Returns:
        Dictionary with hours, minutes, seconds, frames, or None if invalid
    """
    if not timecode:
        return None

    # Check format using regex (HH:MM:SS:FF)
    match = re.match(r"^([0-2]\d):([0-5]\d):([0-5]\d):([0-6]\d)$", timecode)
    if not match:
        return None

    try:
        hours, minutes, seconds, frames = map(int, match.groups())

        return {"hours": hours, "minutes": minutes, "seconds": seconds, "frames": frames}
    except ValueError:
        return None


def apply_time_offset(smpte_timecode: str, time_offset: Dict[str, Any]) -> Optional[str]:
    """
    Apply time offset to SMPTE timecode.

    Args:
        smpte_timecode: SMPTE timecode string (HH:MM:SS:FF)
        time_offset: Dictionary with hours, minutes, seconds offset values
                     and direction ("ahead" or "behind")

    Returns:
        Adjusted SMPTE timecode string or None if invalid
    """
    # Parse original timecode
    components = parse_smpte(smpte_timecode)
    if not components:
        return None

    # Return original if no offset or offset values are all zero
    if not time_offset or all(time_offset.get(k, 0) == 0 for k in ["hours", "minutes", "seconds"]):
        return smpte_timecode

    # Extract components
    hours = components["hours"]
    minutes = components["minutes"]
    seconds = components["seconds"]
    frames = components["frames"]

    # Get direction - default to "behind" if not specified
    direction = time_offset.get("direction", "behind")

    # Apply offset based on direction
    if direction == "behind":
        # If DVR time is behind real time, add the offset to get real time
        hours += time_offset.get("hours", 0)
        minutes += time_offset.get("minutes", 0)
        seconds += time_offset.get("seconds", 0)
    else:  # direction == "ahead"
        # If DVR time is ahead of real time, subtract the offset to get real time
        hours -= time_offset.get("hours", 0)
        minutes -= time_offset.get("minutes", 0)
        seconds -= time_offset.get("seconds", 0)

    # Normalize time components
    while seconds >= 60:
        seconds -= 60
        minutes += 1
    while seconds < 0:
        seconds += 60
        minutes -= 1

    while minutes >= 60:
        minutes -= 60
        hours += 1
    while minutes < 0:
        minutes += 60
        hours -= 1

    hours = hours % 24

    # Format result as SMPTE timecode
    return format_smpte(hours, minutes, seconds, frames)


def timestamp_to_seconds(timestamp: str) -> Optional[float]:
    """
    Convert timestamp (HH:MM:SS) to total seconds.

    Args:
        timestamp: Timestamp string in format HH:MM:SS

    Returns:
        Total seconds as float or None if invalid format
    """
    if not timestamp:
        return None

    # Match HH:MM:SS format
    match = re.match(r"^(\d{1,2}):(\d{1,2}):(\d{1,2})$", timestamp)
    if not match:
        return None

    try:
        hours, minutes, seconds = map(int, match.groups())
        total_seconds = hours * 3600 + minutes * 60 + seconds
        return float(total_seconds)
    except ValueError:
        return None


def seconds_to_timestamp(seconds: float) -> str:
    """
    Convert total seconds to timestamp (HH:MM:SS).

    Args:
        seconds: Total seconds as float

    Returns:
        Timestamp string in format HH:MM:SS
    """
    # Ensure non-negative
    seconds = max(0, seconds)

    # Convert to time components
    hours = int(seconds // 3600)
    seconds %= 3600
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)

    # Format as timestamp
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def validate_time_components(
    hours: int, minutes: int, seconds: int, frames: Optional[int] = None
) -> bool:
    """
    Validate time components are within valid ranges.

    Args:
        hours: Hours value
        minutes: Minutes value
        seconds: Seconds value
        frames: Optional frames value

    Returns:
        True if valid, False otherwise
    """
    if not (0 <= hours <= 23):
        return False

    if not (0 <= minutes <= 59):
        return False

    if not (0 <= seconds <= 59):
        return False

    if frames is not None and not (0 <= frames <= 99):  # Allow up to 99 for high frame rates
        return False

    return True


def timecode_to_seconds(timecode: str, fps: float) -> float:
    """
    Convert SMPTE timecode to total seconds with subsecond precision.

    This is critical for timeline calculations as it preserves accuracy
    across frame rate conversions using time-based (not frame-based) calculations.

    Args:
        timecode: SMPTE timecode string (HH:MM:SS:FF)
        fps: Frames per second

    Returns:
        Total seconds as float with subsecond precision

    Example:
        >>> timecode_to_seconds("14:32:18:05", 12.0)
        52338.4166...  # 14*3600 + 32*60 + 18 + (5/12)
    """
    components = parse_smpte(timecode)
    if not components:
        raise ValueError(f"Invalid SMPTE timecode format: {timecode}")

    hours = components["hours"]
    minutes = components["minutes"]
    seconds = components["seconds"]
    frames = components["frames"]

    # Convert to total seconds with frame precision
    total_seconds = hours * 3600 + minutes * 60 + seconds

    # Add fractional seconds from frames
    # This preserves subsecond precision critical for timeline calculations
    total_seconds += frames / fps

    return total_seconds


def frames_to_timecode(frames: int, fps: float) -> str:
    """
    Convert frame count to SMPTE timecode.

    Handles rounding edge cases properly to ensure frame counts
    never exceed fps-1 in the frames field.

    Args:
        frames: Total frame count
        fps: Frames per second

    Returns:
        SMPTE timecode string (HH:MM:SS:FF)

    Example:
        >>> frames_to_timecode(628061, 12.0)
        "14:32:18:05"
    """
    # Calculate total seconds
    total_seconds = frames / fps

    # Extract time components
    hours = int(total_seconds / 3600)
    remaining = total_seconds % 3600
    minutes = int(remaining / 60)
    seconds = int(remaining % 60)

    # Calculate frame component with proper rounding
    fractional_seconds = total_seconds - int(total_seconds)
    frames_part = round(fractional_seconds * fps)

    # Handle rounding edge case where frames_part == fps
    if frames_part >= fps:
        frames_part = 0
        seconds += 1

        # Cascade carries
        if seconds >= 60:
            seconds = 0
            minutes += 1

        if minutes >= 60:
            minutes = 0
            hours += 1

        # Wrap hours at 24
        hours = hours % 24

    return format_smpte(hours, minutes, seconds, frames_part)


def seconds_to_timecode(seconds: float, fps: float) -> str:
    """
    Convert seconds to SMPTE timecode.

    Convenience function that converts seconds to frame count then to timecode.

    Args:
        seconds: Time in seconds
        fps: Frames per second

    Returns:
        SMPTE timecode string (HH:MM:SS:FF)
    """
    frames = round(seconds * fps)
    return frames_to_timecode(frames, fps)
