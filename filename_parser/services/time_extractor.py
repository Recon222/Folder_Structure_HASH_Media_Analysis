"""
Time extraction service for converting pattern matches to time data.

This service converts validated PatternMatch results into structured TimeData
objects with all time/date components properly organized.
"""

from typing import Optional
from filename_parser.models.pattern_models import PatternMatch
from filename_parser.models.time_models import TimeData
from core.logger import logger


class TimeExtractor:
    """
    Service for extracting time data from pattern matches.

    Converts validated pattern matches into structured TimeData objects,
    handling various component combinations (time-only, datetime, etc.).
    """

    def extract(self, pattern_match: PatternMatch) -> Optional[TimeData]:
        """
        Extract time data from a validated pattern match.

        Args:
            pattern_match: Validated PatternMatch object

        Returns:
            TimeData object or None if extraction failed
        """
        if not pattern_match.valid:
            logger.warning(
                f"Cannot extract from invalid pattern match: {pattern_match.validation_errors}"
            )
            return None

        components = pattern_match.components

        # Validate required time components
        if "hours" not in components:
            logger.error("Missing required 'hours' component")
            return None
        if "minutes" not in components:
            logger.error("Missing required 'minutes' component")
            return None
        if "seconds" not in components:
            logger.error("Missing required 'seconds' component")
            return None

        # Extract required time components
        hours = components["hours"]
        minutes = components["minutes"]
        seconds = components["seconds"]

        # Extract optional frame/millisecond component
        frames = 0
        milliseconds = 0
        is_milliseconds = False

        if "milliseconds" in components:
            milliseconds = components["milliseconds"]
            is_milliseconds = True
            logger.debug(f"Extracted milliseconds: {milliseconds}")
        elif "frames" in components:
            frames = components["frames"]
            is_milliseconds = False
            logger.debug(f"Extracted frames: {frames}")

        # Extract optional date components
        year = components.get("year")
        month = components.get("month")
        day = components.get("day")

        # Extract optional camera/channel information
        channel = components.get("channel")
        camera_id = components.get("camera_id")

        # Additional validation
        if not self._validate_time(hours, minutes, seconds):
            logger.error(
                f"Invalid time values: {hours:02d}:{minutes:02d}:{seconds:02d}"
            )
            return None

        if year is not None and month is not None and day is not None:
            if not self._validate_date(year, month, day):
                logger.error(
                    f"Invalid date values: {year:04d}-{month:02d}-{day:02d}"
                )
                return None

        # Create TimeData object
        time_data = TimeData(
            hours=hours,
            minutes=minutes,
            seconds=seconds,
            frames=frames,
            milliseconds=milliseconds,
            is_milliseconds=is_milliseconds,
            year=year,
            month=month,
            day=day,
            channel=channel,
            camera_id=camera_id,
        )

        logger.info(
            f"Extracted time data: {time_data.time_string}"
            + (f" on {time_data.date_string}" if time_data.has_date() else "")
        )

        return time_data

    def _validate_time(self, hours: int, minutes: int, seconds: int) -> bool:
        """
        Validate time components.

        Args:
            hours: Hours (0-23)
            minutes: Minutes (0-59)
            seconds: Seconds (0-59)

        Returns:
            True if valid, False otherwise
        """
        if not (0 <= hours <= 23):
            return False
        if not (0 <= minutes <= 59):
            return False
        if not (0 <= seconds <= 59):
            return False
        return True

    def _validate_date(self, year: int, month: int, day: int) -> bool:
        """
        Validate date components.

        Args:
            year: Year (2000-2099)
            month: Month (1-12)
            day: Day (1-31)

        Returns:
            True if valid, False otherwise
        """
        if not (2000 <= year <= 2099):
            return False
        if not (1 <= month <= 12):
            return False
        if not (1 <= day <= 31):
            return False

        # Additional day validation based on month
        days_in_month = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        if day > days_in_month[month - 1]:
            return False

        # February leap year check
        if month == 2 and day == 29:
            # Simple leap year check
            if year % 4 != 0 or (year % 100 == 0 and year % 400 != 0):
                return False

        return True
