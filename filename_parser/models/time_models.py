"""
Data models for time data and parsing results.

This module defines type-safe structures for representing extracted time
information and complete parsing results.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime

from filename_parser.models.pattern_models import PatternDefinition, PatternMatch


@dataclass
class TimeData:
    """
    Extracted and validated time/date information.

    This structure holds all time components extracted from a filename,
    with clear separation between required and optional fields.
    """

    # Required time components (HH:MM:SS)
    hours: int
    minutes: int
    seconds: int

    # Optional frame/millisecond component
    frames: int = 0
    milliseconds: int = 0
    is_milliseconds: bool = False  # True if frames field is actually milliseconds

    # Optional date components
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None

    # Optional camera/channel information
    channel: Optional[int] = None
    camera_id: Optional[str] = None

    # Formatted representations
    time_string: Optional[str] = None  # HH:MM:SS or HH:MM:SS.mmm
    date_string: Optional[str] = None  # YYYY-MM-DD

    def __post_init__(self):
        """Generate formatted strings if not provided."""
        if self.time_string is None:
            if self.is_milliseconds and self.milliseconds > 0:
                self.time_string = f"{self.hours:02d}:{self.minutes:02d}:{self.seconds:02d}.{self.milliseconds:03d}"
            elif not self.is_milliseconds and self.frames > 0:
                self.time_string = f"{self.hours:02d}:{self.minutes:02d}:{self.seconds:02d}:{self.frames:02d}"
            else:
                self.time_string = f"{self.hours:02d}:{self.minutes:02d}:{self.seconds:02d}"

        if self.date_string is None and self.has_date():
            self.date_string = f"{self.year:04d}-{self.month:02d}-{self.day:02d}"

    def has_date(self) -> bool:
        """Check if date information is present."""
        return self.year is not None and self.month is not None and self.day is not None

    def has_frames(self) -> bool:
        """Check if frame information is present."""
        return not self.is_milliseconds and self.frames > 0

    def has_milliseconds(self) -> bool:
        """Check if millisecond information is present."""
        return self.is_milliseconds and self.milliseconds > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        result = {
            "hours": self.hours,
            "minutes": self.minutes,
            "seconds": self.seconds,
            "frames": self.frames if not self.is_milliseconds else 0,
            "milliseconds": self.milliseconds if self.is_milliseconds else 0,
            "is_milliseconds": self.is_milliseconds,
            "original_time": self.time_string,
            "has_date": self.has_date(),
        }

        if self.has_date():
            result.update({
                "year": self.year,
                "month": self.month,
                "day": self.day,
                "date_string": self.date_string,
                "original_datetime": f"{self.date_string} {self.time_string}",
            })

        if self.channel is not None:
            result["channel"] = self.channel

        if self.camera_id is not None:
            result["camera_id"] = self.camera_id

        return result


@dataclass
class ParseResult:
    """
    Complete result of parsing a filename.

    Contains the pattern that matched, extracted time data, and optional
    SMPTE timecode after conversion.
    """

    # Input
    filename: str

    # Pattern matching result
    pattern: PatternDefinition
    pattern_match: PatternMatch

    # Extracted time data
    time_data: TimeData

    # SMPTE timecode (populated after conversion)
    smpte_timecode: Optional[str] = None

    # Frame rate used for conversion
    frame_rate: Optional[float] = None

    # Time offset applied (if any)
    time_offset_applied: bool = False
    time_offset_direction: Optional[str] = None  # "ahead" or "behind"
    time_offset_hours: int = 0
    time_offset_minutes: int = 0
    time_offset_seconds: int = 0

    # Processing metadata
    success: bool = True
    error_message: Optional[str] = None
    warnings: list[str] = field(default_factory=list)

    # Timestamps
    parsed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "filename": self.filename,
            "pattern_id": self.pattern.id,
            "pattern_name": self.pattern.name,
            "time_data": self.time_data.to_dict(),
            "smpte_timecode": self.smpte_timecode,
            "frame_rate": self.frame_rate,
            "time_offset_applied": self.time_offset_applied,
            "time_offset_direction": self.time_offset_direction,
            "time_offset_hours": self.time_offset_hours,
            "time_offset_minutes": self.time_offset_minutes,
            "time_offset_seconds": self.time_offset_seconds,
            "success": self.success,
            "error_message": self.error_message,
            "warnings": self.warnings,
        }
