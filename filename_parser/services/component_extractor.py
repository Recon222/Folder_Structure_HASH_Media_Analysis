"""
Component-based date/time extraction for filenames.

This module provides two-phase parsing as a fallback when monolithic pattern
matching fails. It extracts date and time components independently, then
combines them using smart heuristics for forensic-grade accuracy.
"""

import re
from typing import Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime
from core.logger import logger


@dataclass
class DateComponent:
    """Extracted date component with confidence score."""
    year: int
    month: int
    day: int
    position: int  # Character position in filename
    confidence: float  # 0.0 to 1.0
    pattern_name: str


@dataclass
class TimeComponent:
    """Extracted time component with confidence score."""
    hours: int
    minutes: int
    seconds: int
    milliseconds: int = 0
    position: int = 0  # Character position in filename
    confidence: float = 0.0  # 0.0 to 1.0
    pattern_name: str = ""


class ComponentExtractor:
    """
    Two-phase date/time extraction with intelligent heuristics.

    This extractor complements the monolithic pattern library by providing
    flexible, delimiter-agnostic component extraction when exact patterns fail.
    """

    # Date extraction patterns (ordered by preference)
    DATE_PATTERNS = [
        # YYYYMMDD (most common in DVR systems)
        (r"(\d{4})(\d{2})(\d{2})", "YYYYMMDD", "yyyymmdd"),
        # YYYY-MM-DD
        (r"(\d{4})-(\d{2})-(\d{2})", "YYYY-MM-DD", "yyyy_mm_dd_dash"),
        # YYYY/MM/DD
        (r"(\d{4})/(\d{2})/(\d{2})", "YYYY/MM/DD", "yyyy_mm_dd_slash"),
        # DDMMMYY (e.g., 21MAY25)
        (r"(\d{2})([A-Z]{3})(\d{2})", "DDMMMYY", "ddmmmyy"),
        # MMDDYYYY
        (r"(\d{2})(\d{2})(\d{4})", "MMDDYYYY", "mmddyyyy"),
        # DD-MM-YYYY
        (r"(\d{2})-(\d{2})-(\d{4})", "DD-MM-YYYY", "dd_mm_yyyy_dash"),
    ]

    # Time extraction patterns (ordered by preference)
    TIME_PATTERNS = [
        # HHMMSS (most common)
        (r"(\d{2})(\d{2})(\d{2})(?!\d)", "HHMMSS", "hhmmss_compact"),
        # HHMMSSMMM (with milliseconds)
        (r"(\d{2})(\d{2})(\d{2})(\d{3})(?!\d)", "HHMMSSMMM", "hhmmssmmm_compact"),
        # HH:MM:SS
        (r"(\d{2}):(\d{2}):(\d{2})", "HH:MM:SS", "hh_mm_ss_colon"),
        # HH_MM_SS
        (r"(\d{2})_(\d{2})_(\d{2})", "HH_MM_SS", "hh_mm_ss_underscore"),
        # HH-MM-SS
        (r"(\d{2})-(\d{2})-(\d{2})", "HH-MM-SS", "hh_mm_ss_dash"),
    ]

    # Month name mappings for DDMMMYY format
    MONTH_NAMES = {
        "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
        "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
    }

    def __init__(self):
        """Initialize the component extractor."""
        self.logger = logger

    def extract_date_components(self, filename: str) -> List[DateComponent]:
        """
        Extract all possible date components from filename.

        Args:
            filename: The filename to parse

        Returns:
            List of DateComponent objects, sorted by confidence (highest first)
        """
        components = []

        for pattern, pattern_name, pattern_id in self.DATE_PATTERNS:
            for match in re.finditer(pattern, filename):
                component = self._parse_date_match(
                    match, pattern_name, pattern_id, filename
                )
                if component:
                    components.append(component)

        # Sort by confidence (highest first)
        components.sort(key=lambda c: c.confidence, reverse=True)

        self.logger.debug(f"Extracted {len(components)} date candidates from '{filename}'")
        return components

    def extract_time_components(self, filename: str) -> List[TimeComponent]:
        """
        Extract all possible time components from filename.

        Args:
            filename: The filename to parse

        Returns:
            List of TimeComponent objects, sorted by confidence (highest first)
        """
        components = []

        for pattern, pattern_name, pattern_id in self.TIME_PATTERNS:
            for match in re.finditer(pattern, filename):
                component = self._parse_time_match(
                    match, pattern_name, pattern_id, filename
                )
                if component:
                    components.append(component)

        # Sort by confidence (highest first)
        components.sort(key=lambda c: c.confidence, reverse=True)

        self.logger.debug(f"Extracted {len(components)} time candidates from '{filename}'")
        return components

    def _parse_date_match(
        self,
        match: re.Match,
        pattern_name: str,
        pattern_id: str,
        filename: str
    ) -> Optional[DateComponent]:
        """
        Parse a regex match into a DateComponent.

        Returns None if the match is invalid (out of range values, etc.)
        """
        try:
            groups = match.groups()
            position = match.start()

            # Handle different date formats
            if pattern_id == "yyyymmdd":
                year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
            elif pattern_id == "yyyy_mm_dd_dash" or pattern_id == "yyyy_mm_dd_slash":
                year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
            elif pattern_id == "ddmmmyy":
                day = int(groups[0])
                month = self.MONTH_NAMES.get(groups[1].upper(), 0)
                year = 2000 + int(groups[2])  # Assume 2000s
            elif pattern_id == "mmddyyyy":
                month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
            elif pattern_id == "dd_mm_yyyy_dash":
                day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
            else:
                return None

            # Validate ranges
            if not (1 <= month <= 12):
                return None
            if not (1 <= day <= 31):
                return None

            # Calculate confidence using heuristics
            confidence = self._calculate_date_confidence(year, month, day, position, filename)

            return DateComponent(
                year=year,
                month=month,
                day=day,
                position=position,
                confidence=confidence,
                pattern_name=pattern_name
            )

        except (ValueError, IndexError) as e:
            self.logger.debug(f"Failed to parse date match: {e}")
            return None

    def _parse_time_match(
        self,
        match: re.Match,
        pattern_name: str,
        pattern_id: str,
        filename: str
    ) -> Optional[TimeComponent]:
        """
        Parse a regex match into a TimeComponent.

        Returns None if the match is invalid (out of range values, etc.)
        """
        try:
            groups = match.groups()
            position = match.start()

            # Extract time components
            hours = int(groups[0])
            minutes = int(groups[1])
            seconds = int(groups[2])
            milliseconds = int(groups[3]) if len(groups) > 3 and groups[3] else 0

            # Validate ranges
            if not (0 <= hours <= 23):
                return None
            if not (0 <= minutes <= 59):
                return None
            if not (0 <= seconds <= 59):
                return None
            if not (0 <= milliseconds <= 999):
                return None

            # Calculate confidence
            confidence = self._calculate_time_confidence(position, filename)

            return TimeComponent(
                hours=hours,
                minutes=minutes,
                seconds=seconds,
                milliseconds=milliseconds,
                position=position,
                confidence=confidence,
                pattern_name=pattern_name
            )

        except (ValueError, IndexError) as e:
            self.logger.debug(f"Failed to parse time match: {e}")
            return None

    def _calculate_date_confidence(
        self,
        year: int,
        month: int,
        day: int,
        position: int,
        filename: str
    ) -> float:
        """
        Calculate confidence score for a date component using forensic heuristics.

        Confidence factors:
        1. Year range (2020-2030 = high confidence)
        2. Position in filename (early = high confidence)
        3. Day validity (1-28 = very high, 29-31 = check month)

        Returns:
            Confidence score from 0.0 to 1.0
        """
        confidence = 0.5  # Base confidence

        # Factor 1: Year range heuristic (forensic DVR files)
        current_year = datetime.now().year
        min_year = current_year - 5
        max_year = current_year + 5

        if min_year <= year <= max_year:
            confidence += 0.3  # Recent years = high confidence
        elif 2000 <= year < min_year:
            confidence += 0.1  # Older but plausible
        else:
            confidence -= 0.3  # Suspicious year

        # Factor 2: Positional confidence (early in filename = more likely)
        relative_pos = position / max(len(filename), 1)
        if relative_pos < 0.3:
            confidence += 0.2  # Early position = high confidence
        elif relative_pos < 0.6:
            confidence += 0.1  # Middle position = medium confidence
        # else: no bonus for late position

        # Factor 3: Day validity check
        if 1 <= day <= 28:
            confidence += 0.1  # Always valid
        elif month in [1, 3, 5, 7, 8, 10, 12] and day <= 31:
            confidence += 0.05  # 31-day month
        elif month in [4, 6, 9, 11] and day <= 30:
            confidence += 0.05  # 30-day month
        elif month == 2 and day <= 29:
            confidence += 0.02  # February (leap year consideration)
        else:
            confidence -= 0.2  # Invalid day for month

        return max(0.0, min(1.0, confidence))  # Clamp to [0, 1]

    def _calculate_time_confidence(self, position: int, filename: str) -> float:
        """
        Calculate confidence score for a time component.

        Time is generally less ambiguous than date, so confidence is higher.

        Returns:
            Confidence score from 0.0 to 1.0
        """
        confidence = 0.7  # Base confidence (higher than date)

        # Positional bonus (time usually follows date)
        relative_pos = position / max(len(filename), 1)
        if 0.3 <= relative_pos <= 0.7:
            confidence += 0.2  # Middle position = likely after date
        elif relative_pos < 0.3:
            confidence += 0.1  # Early position = acceptable

        return max(0.0, min(1.0, confidence))  # Clamp to [0, 1]


    def extract_best_components(
        self,
        filename: str
    ) -> Tuple[Optional[DateComponent], Optional[TimeComponent]]:
        """
        Extract the best date and time components from filename.

        Uses intelligent heuristics to select the most likely correct components
        when multiple candidates are found.

        Args:
            filename: The filename to parse

        Returns:
            Tuple of (best_date, best_time), either can be None if not found
        """
        date_components = self.extract_date_components(filename)
        time_components = self.extract_time_components(filename)

        best_date = date_components[0] if date_components else None
        best_time = time_components[0] if time_components else None

        # Boost confidence if date and time are adjacent (common in DVR filenames)
        if best_date and best_time:
            distance = abs(best_date.position - best_time.position)
            # If within 14 characters of each other (e.g., "20250521175603")
            if distance <= 14:
                best_date.confidence = min(1.0, best_date.confidence + 0.1)
                best_time.confidence = min(1.0, best_time.confidence + 0.1)
                self.logger.debug(
                    f"Date and time adjacent (distance={distance}), "
                    f"boosted confidence to {best_date.confidence:.2f}"
                )

        if best_date:
            self.logger.info(
                f"Selected date: {best_date.year}-{best_date.month:02d}-{best_date.day:02d} "
                f"(confidence={best_date.confidence:.2f}, pattern={best_date.pattern_name})"
            )
        if best_time:
            self.logger.info(
                f"Selected time: {best_time.hours:02d}:{best_time.minutes:02d}:{best_time.seconds:02d} "
                f"(confidence={best_time.confidence:.2f}, pattern={best_time.pattern_name})"
            )

        return best_date, best_time


# Singleton instance
component_extractor = ComponentExtractor()
