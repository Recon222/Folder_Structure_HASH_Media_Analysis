"""
Pattern library for filename parsing.

This module contains all predefined patterns for extracting time and date
information from video filenames, organized by category with self-describing
component definitions.
"""

from typing import List, Optional, Dict
from filename_parser.models.pattern_models import PatternDefinition, TimeComponentDefinition

# Constants moved here to avoid external dependency
MAX_HOURS = 23
MAX_MINUTES = 59
MAX_SECONDS = 59
MAX_MILLISECONDS = 999


class PatternLibrary:
    """
    Repository of filename parsing patterns.

    Provides access to predefined patterns and methods for searching/filtering.
    """

    def __init__(self):
        """Initialize the pattern library with all predefined patterns."""
        self._patterns: List[PatternDefinition] = []
        self._patterns_by_id: Dict[str, PatternDefinition] = {}
        self._load_patterns()

    def _load_patterns(self):
        """Load all predefined patterns into the library."""
        patterns = [
            # ================================================================
            # DVR - Dahua Patterns
            # ================================================================
            PatternDefinition(
                id="dahua_nvr_standard",
                name="Dahua NVR Standard",
                description="Dahua NVR standard format with date range and channel",
                example="NPV-CH01-MAIN-20171215143022-20171215143522.DAV",
                regex=r".*CH(\d+).*(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})-",
                components=[
                    TimeComponentDefinition("channel", 1, 1, 999, optional=False),
                    TimeComponentDefinition("year", 2, 2000, 2099),
                    TimeComponentDefinition("month", 3, 1, 12),
                    TimeComponentDefinition("day", 4, 1, 31),
                    TimeComponentDefinition("hours", 5, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 6, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 7, 0, MAX_SECONDS),
                ],
                category=PatternCategory.DVR_DAHUA.value,
                priority=90,
                has_date=True,
                has_milliseconds=False,
                tags=["dahua", "nvr", "channel", "date", "dual_timestamp"],
            ),

            # ================================================================
            # Compact Timestamp Patterns (HHMMSS variations)
            # ================================================================
            PatternDefinition(
                id="hhmmss_compact",
                name="HHMMSS Compact",
                description="6-digit compact time format",
                example="video_161048.mp4",
                regex=r"(\d{2})(\d{2})(\d{2})(?!\d)",
                components=[
                    TimeComponentDefinition("hours", 1, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 2, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 3, 0, MAX_SECONDS),
                ],
                category=PatternCategory.COMPACT_TIMESTAMP.value,
                priority=40,
                has_date=False,
                has_milliseconds=False,
                tags=["compact", "time_only"],
            ),

            PatternDefinition(
                id="hhmmssmmm_compact",
                name="HHMMSSmmm Compact",
                description="9-digit compact time with milliseconds",
                example="cam-03JAN24_161325038.mp4",
                regex=r"(\d{2})(\d{2})(\d{2})(\d{3})(?!\d)",
                components=[
                    TimeComponentDefinition("hours", 1, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 2, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 3, 0, MAX_SECONDS),
                    TimeComponentDefinition("milliseconds", 4, 0, MAX_MILLISECONDS),
                ],
                category=PatternCategory.COMPACT_TIMESTAMP.value,
                priority=45,
                has_date=False,
                has_milliseconds=True,
                tags=["compact", "milliseconds"],
            ),

            # ================================================================
            # Delimited Timestamp Patterns
            # ================================================================
            PatternDefinition(
                id="hh_mm_ss_underscore",
                name="HH_MM_SS",
                description="Time with underscore separators",
                example="2645 Battleford Ch14 16_38_20_C.mp4",
                regex=r"(\d{1,2})_(\d{2})_(\d{2})(?:_[A-Za-z0-9])?",
                components=[
                    TimeComponentDefinition("hours", 1, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 2, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 3, 0, MAX_SECONDS),
                ],
                category=PatternCategory.DELIMITED_TIMESTAMP.value,
                priority=50,
                has_date=False,
                has_milliseconds=False,
                tags=["delimited", "underscore"],
            ),

            PatternDefinition(
                id="hh_mm_ss_mmm_underscore",
                name="HH_MM_SS_mmm",
                description="Time with milliseconds, underscore separators",
                example="video_16_38_20_123.mp4",
                regex=r"(\d{1,2})_(\d{2})_(\d{2})_(\d{2,3})",
                components=[
                    TimeComponentDefinition("hours", 1, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 2, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 3, 0, MAX_SECONDS),
                    TimeComponentDefinition("milliseconds", 4, 0, MAX_MILLISECONDS),
                ],
                category=PatternCategory.DELIMITED_TIMESTAMP.value,
                priority=52,
                has_date=False,
                has_milliseconds=True,
                tags=["delimited", "underscore", "milliseconds"],
            ),

            PatternDefinition(
                id="hh_mm_ss_dash",
                name="HH-MM-SS",
                description="Time with dash separators",
                example="video-16-10-48.mp4",
                regex=r"(\d{2})-(\d{2})-(\d{2})(?:-(\d{2,3}))?",
                components=[
                    TimeComponentDefinition("hours", 1, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 2, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 3, 0, MAX_SECONDS),
                    TimeComponentDefinition("milliseconds", 4, 0, MAX_MILLISECONDS, optional=True),
                ],
                category=PatternCategory.DELIMITED_TIMESTAMP.value,
                priority=48,
                has_date=False,
                has_milliseconds=False,  # Optional
                tags=["delimited", "dash"],
            ),

            PatternDefinition(
                id="hh_mm_ss_colon",
                name="HH:MM:SS",
                description="Time with colon separators",
                example="video_16:10:48.mp4",
                regex=r"(\d{2}):(\d{2}):(\d{2})(?::(\d{2,3}))?",
                components=[
                    TimeComponentDefinition("hours", 1, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 2, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 3, 0, MAX_SECONDS),
                    TimeComponentDefinition("milliseconds", 4, 0, MAX_MILLISECONDS, optional=True),
                ],
                category=PatternCategory.DELIMITED_TIMESTAMP.value,
                priority=46,
                has_date=False,
                has_milliseconds=False,  # Optional
                tags=["delimited", "colon"],
            ),

            PatternDefinition(
                id="hh_mm_ss_dot",
                name="HH.MM.SS",
                description="Time with dot separators",
                example="video.16.10.48.mp4",
                regex=r"(\d{2})\.(\d{2})\.(\d{2})(?:\.(\d{2,3}))?",
                components=[
                    TimeComponentDefinition("hours", 1, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 2, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 3, 0, MAX_SECONDS),
                    TimeComponentDefinition("milliseconds", 4, 0, MAX_MILLISECONDS, optional=True),
                ],
                category=PatternCategory.DELIMITED_TIMESTAMP.value,
                priority=44,
                has_date=False,
                has_milliseconds=False,  # Optional
                tags=["delimited", "dot"],
            ),

            # ================================================================
            # ISO DateTime Patterns
            # ================================================================
            PatternDefinition(
                id="yyyymmdd_hhmmss",
                name="YYYYMMDD_HHMMSS",
                description="ISO-style date and time compact",
                example="20230101_123045_CH01.mp4",
                regex=r"(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})",
                components=[
                    TimeComponentDefinition("year", 1, 2000, 2099),
                    TimeComponentDefinition("month", 2, 1, 12),
                    TimeComponentDefinition("day", 3, 1, 31),
                    TimeComponentDefinition("hours", 4, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 5, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 6, 0, MAX_SECONDS),
                ],
                category=PatternCategory.ISO_DATETIME.value,
                priority=70,
                has_date=True,
                has_milliseconds=False,
                tags=["iso", "datetime", "compact"],
            ),

            PatternDefinition(
                id="yyyymmdd_hhmmssmmm",
                name="YYYYMMDD_HHMMSSmmm",
                description="ISO-style date and time with milliseconds",
                example="20230101_123045678.mp4",
                regex=r"(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})(\d{3})",
                components=[
                    TimeComponentDefinition("year", 1, 2000, 2099),
                    TimeComponentDefinition("month", 2, 1, 12),
                    TimeComponentDefinition("day", 3, 1, 31),
                    TimeComponentDefinition("hours", 4, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 5, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 6, 0, MAX_SECONDS),
                    TimeComponentDefinition("milliseconds", 7, 0, MAX_MILLISECONDS),
                ],
                category=PatternCategory.ISO_DATETIME.value,
                priority=72,
                has_date=True,
                has_milliseconds=True,
                tags=["iso", "datetime", "milliseconds"],
            ),

            PatternDefinition(
                id="yyyy_mm_dd_hh_mm_ss",
                name="YYYY-MM-DD HH:MM:SS",
                description="ISO-style delimited date and time",
                example="2023-01-01_16-30-45.mp4",
                regex=r"(\d{4})[-/_](\d{2})[-/_](\d{2})[_ ](\d{2})[:_](\d{2})[:_](\d{2})",
                components=[
                    TimeComponentDefinition("year", 1, 2000, 2099),
                    TimeComponentDefinition("month", 2, 1, 12),
                    TimeComponentDefinition("day", 3, 1, 31),
                    TimeComponentDefinition("hours", 4, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 5, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 6, 0, MAX_SECONDS),
                ],
                category=PatternCategory.ISO_DATETIME.value,
                priority=68,
                has_date=True,
                has_milliseconds=False,
                tags=["iso", "datetime", "delimited"],
            ),

            # ================================================================
            # DVR Generic - _C.mp4 Suffix Patterns
            # ================================================================
            PatternDefinition(
                id="suffix_time_c",
                name="Suffix Time Only (_C)",
                description="Standardized suffix with time only before _C.mp4",
                example="file_yymmdd_161048_C.mp4",
                regex=r"_\d{6}_(\d{2})(\d{2})(\d{2})_C(?:\.|$)",
                components=[
                    TimeComponentDefinition("hours", 1, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 2, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 3, 0, MAX_SECONDS),
                ],
                category=PatternCategory.DVR_GENERIC.value,
                priority=60,
                has_date=False,
                has_milliseconds=False,
                tags=["suffix", "c_suffix", "standardized"],
            ),

            PatternDefinition(
                id="suffix_time_ms_c",
                name="Suffix Time with MS (_C)",
                description="Standardized suffix with time and milliseconds before _C.mp4",
                example="file_yymmdd_161048123_C.mp4",
                regex=r"_\d{6}_(\d{2})(\d{2})(\d{2})(\d{3})_C(?:\.|$)",
                components=[
                    TimeComponentDefinition("hours", 1, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 2, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 3, 0, MAX_SECONDS),
                    TimeComponentDefinition("milliseconds", 4, 0, MAX_MILLISECONDS),
                ],
                category=PatternCategory.DVR_GENERIC.value,
                priority=62,
                has_date=False,
                has_milliseconds=True,
                tags=["suffix", "c_suffix", "milliseconds"],
            ),

            PatternDefinition(
                id="suffix_datetime_c",
                name="Suffix DateTime (_C)",
                description="Standardized suffix with date and time before _C.mp4",
                example="file_240103_161048_C.mp4",
                regex=r"_(\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_C(?:\.|$)",
                components=[
                    TimeComponentDefinition("year", 1, 0, 99),  # YY format
                    TimeComponentDefinition("month", 2, 1, 12),
                    TimeComponentDefinition("day", 3, 1, 31),
                    TimeComponentDefinition("hours", 4, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 5, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 6, 0, MAX_SECONDS),
                ],
                category=PatternCategory.DVR_GENERIC.value,
                priority=64,
                has_date=True,
                has_milliseconds=False,
                tags=["suffix", "c_suffix", "datetime"],
            ),

            PatternDefinition(
                id="suffix_datetime_ms_c",
                name="Suffix DateTime with MS (_C)",
                description="Standardized suffix with date, time, and milliseconds before _C.mp4",
                example="file_240103_161048123_C.mp4",
                regex=r"_(\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})(\d{3})_C(?:\.|$)",
                components=[
                    TimeComponentDefinition("year", 1, 0, 99),  # YY format
                    TimeComponentDefinition("month", 2, 1, 12),
                    TimeComponentDefinition("day", 3, 1, 31),
                    TimeComponentDefinition("hours", 4, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 5, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 6, 0, MAX_SECONDS),
                    TimeComponentDefinition("milliseconds", 7, 0, MAX_MILLISECONDS),
                ],
                category=PatternCategory.DVR_GENERIC.value,
                priority=66,
                has_date=True,
                has_milliseconds=True,
                tags=["suffix", "c_suffix", "datetime", "milliseconds"],
            ),

            PatternDefinition(
                id="time_before_c",
                name="Time Before _C",
                description="6-digit time immediately before _C suffix",
                example="file_161048_C.mp4",
                regex=r"(\d{2})(\d{2})(\d{2})_C(?:\.|$)",
                components=[
                    TimeComponentDefinition("hours", 1, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 2, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 3, 0, MAX_SECONDS),
                ],
                category=PatternCategory.DVR_GENERIC.value,
                priority=55,
                has_date=False,
                has_milliseconds=False,
                tags=["c_suffix"],
            ),

            PatternDefinition(
                id="mmddyyhhmmss_before_c",
                name="MMDDYYHHMMSS Before _C",
                description="12-digit date/time (MMDDYY + HHMMSS) before _C suffix",
                example="file_010524102942_C.mp4",
                regex=r"(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})_C(?:\.|$)",
                components=[
                    TimeComponentDefinition("month", 1, 1, 12),
                    TimeComponentDefinition("day", 2, 1, 31),
                    TimeComponentDefinition("year", 3, 0, 99),  # YY format
                    TimeComponentDefinition("hours", 4, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 5, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 6, 0, MAX_SECONDS),
                ],
                category=PatternCategory.DVR_GENERIC.value,
                priority=58,
                has_date=True,
                has_milliseconds=False,
                tags=["c_suffix", "mmddyy"],
            ),

            # ================================================================
            # Embedded Timestamp Patterns
            # ================================================================
            PatternDefinition(
                id="embedded_time_location_channel",
                name="Embedded Time (Location/Channel)",
                description="Time embedded in filename with location and channel info",
                example="2645 Battleford Ch14 16_38_20_C.mp4",
                regex=r".*?\s(\d{1,2})_(\d{2})_(\d{2})(?:_[A-Za-z0-9])?\.",
                components=[
                    TimeComponentDefinition("hours", 1, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 2, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 3, 0, MAX_SECONDS),
                ],
                category=PatternCategory.EMBEDDED_TIMESTAMP.value,
                priority=35,
                has_date=False,
                has_milliseconds=False,
                tags=["embedded", "location", "flexible"],
            ),

            PatternDefinition(
                id="embedded_time_flexible",
                name="Flexible Embedded Time",
                description="Flexible pattern for time anywhere in filename",
                example="camera_161048_recording.mp4",
                regex=r".*?(\d{1,2})[-_.]?(\d{2})[-_.]?(\d{2})(?:[-_.]?(\d{2,3}))?",
                components=[
                    TimeComponentDefinition("hours", 1, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 2, 0, MAX_MINUTES),
                    TimeComponentDefinition("seconds", 3, 0, MAX_SECONDS),
                    TimeComponentDefinition("milliseconds", 4, 0, MAX_MILLISECONDS, optional=True),
                ],
                category=PatternCategory.EMBEDDED_TIMESTAMP.value,
                priority=10,  # Low priority - very generic, use as fallback
                has_date=False,
                has_milliseconds=False,  # Optional
                tags=["embedded", "flexible", "fallback"],
            ),

            # ================================================================
            # Military Time Pattern
            # ================================================================
            PatternDefinition(
                id="military_time",
                name="Military Time",
                description="Military time format (e.g., 1630hrs, 1630h)",
                example="recording_1630hrs.mp4",
                regex=r"(\d{2})(\d{2})(?:hrs?|h)",
                components=[
                    TimeComponentDefinition("hours", 1, 0, MAX_HOURS),
                    TimeComponentDefinition("minutes", 2, 0, MAX_MINUTES),
                ],
                category=PatternCategory.COMPACT_TIMESTAMP.value,
                priority=42,
                has_date=False,
                has_milliseconds=False,
                tags=["military", "compact"],
            ),
        ]

        # Load patterns into library
        for pattern in patterns:
            self.add_pattern(pattern)

    def add_pattern(self, pattern: PatternDefinition) -> None:
        """
        Add a pattern to the library.

        Args:
            pattern: PatternDefinition to add
        """
        self._patterns.append(pattern)
        self._patterns_by_id[pattern.id] = pattern

        # Sort patterns by priority (descending)
        self._patterns.sort(key=lambda p: p.priority, reverse=True)

    def get_pattern(self, pattern_id: str) -> Optional[PatternDefinition]:
        """
        Get a pattern by ID.

        Args:
            pattern_id: Pattern identifier

        Returns:
            PatternDefinition or None if not found
        """
        return self._patterns_by_id.get(pattern_id)

    def get_all_patterns(self) -> List[PatternDefinition]:
        """
        Get all patterns sorted by priority.

        Returns:
            List of all PatternDefinition objects
        """
        return self._patterns.copy()

    def get_patterns_by_category(self, category: str) -> List[PatternDefinition]:
        """
        Get all patterns in a specific category.

        Args:
            category: Category to filter by

        Returns:
            List of matching PatternDefinition objects
        """
        return [p for p in self._patterns if p.category == category]

    def search_patterns(
        self,
        query: str = None,
        category: str = None,
        has_date: bool = None,
        has_milliseconds: bool = None,
        tags: List[str] = None,
    ) -> List[PatternDefinition]:
        """
        Search patterns by various criteria.

        Args:
            query: Search in name/description
            category: Filter by category
            has_date: Filter by date presence
            has_milliseconds: Filter by milliseconds presence
            tags: Filter by tags (any match)

        Returns:
            List of matching PatternDefinition objects
        """
        results = self._patterns.copy()

        if query:
            query_lower = query.lower()
            results = [
                p
                for p in results
                if query_lower in p.name.lower() or query_lower in p.description.lower()
            ]

        if category:
            results = [p for p in results if p.category == category]

        if has_date is not None:
            results = [p for p in results if p.has_date == has_date]

        if has_milliseconds is not None:
            results = [p for p in results if p.has_milliseconds == has_milliseconds]

        if tags:
            results = [p for p in results if any(tag in p.tags for tag in tags)]

        return results


# Global pattern library instance
pattern_library = PatternLibrary()
