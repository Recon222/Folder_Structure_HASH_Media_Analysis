"""
Filename Parser Service - Clean orchestrator for pattern-based parsing.

This service coordinates pattern matching, time extraction, and SMPTE conversion
using focused, single-responsibility components.
"""

from typing import Optional, Dict, Any, List

from core.services.base_service import BaseService
from core.result_types import Result
from core.exceptions import ValidationError, FileOperationError

from filename_parser.filename_parser_interfaces import IFilenameParserService
from filename_parser.models.time_models import TimeData, ParseResult
from filename_parser.models.pattern_models import PatternDefinition
from filename_parser.services.pattern_matcher import PatternMatcher
from filename_parser.services.time_extractor import TimeExtractor
from filename_parser.services.smpte_converter import SMPTEConverter
from filename_parser.services.pattern_generator import PatternGenerator
from filename_parser.services.pattern_library import pattern_library


class FilenameParserService(BaseService, IFilenameParserService):
    """
    Orchestrator service for filename parsing.

    Coordinates pattern matching, time extraction, and SMPTE conversion
    using specialized sub-services.
    """

    def __init__(self):
        """Initialize the filename parser service."""
        super().__init__("FilenameParserService")

        # Initialize sub-services
        self.matcher = PatternMatcher()
        self.extractor = TimeExtractor()
        self.converter = SMPTEConverter()
        self.generator = PatternGenerator()

        self.logger.info("FilenameParserService initialized")

    def parse_filename(
        self,
        filename: str,
        pattern_id: Optional[str] = None,
        fps: Optional[float] = None,
        time_offset: Optional[Dict[str, Any]] = None,
    ) -> Result[ParseResult]:
        """
        Parse a filename and extract time/date information.

        Args:
            filename: Filename to parse (with or without path)
            pattern_id: Optional specific pattern ID to use
            fps: Optional frame rate for SMPTE conversion
            time_offset: Optional time offset to apply

        Returns:
            Result containing ParseResult or error
        """
        try:
            self.logger.debug(f"Parsing filename: '{filename}'")

            # Step 1: Match pattern
            pattern_match = self.matcher.match(filename, pattern_id)
            if not pattern_match or not pattern_match.valid:
                return Result.error(
                    ValidationError(
                        f"No valid pattern match for '{filename}'",
                        user_message="Could not match filename pattern. Try selecting a different pattern.",
                        context={"filename": filename, "pattern_id": pattern_id}
                    )
                )

            self.logger.info(
                f"Matched pattern: '{pattern_match.pattern.name}' (ID: {pattern_match.pattern.id})"
            )

            # Step 2: Extract time data
            time_data = self.extractor.extract(pattern_match)
            if not time_data:
                return Result.error(
                    ValidationError(
                        f"Failed to extract time data from match",
                        user_message="Could not extract valid time data from filename.",
                        context={"filename": filename, "pattern": pattern_match.pattern.name}
                    )
                )

            # Step 3: Convert to SMPTE (if fps provided)
            smpte_timecode = None
            if fps:
                smpte_timecode = self.converter.convert_to_smpte(time_data, fps)
                if not smpte_timecode:
                    self.logger.warning("SMPTE conversion failed")

                # Step 4: Apply time offset (if provided and SMPTE conversion succeeded)
                if smpte_timecode and time_offset:
                    adjusted_timecode = self.converter.apply_time_offset_from_dict(
                        smpte_timecode, time_offset
                    )
                    if adjusted_timecode:
                        smpte_timecode = adjusted_timecode

            # Build ParseResult
            result = ParseResult(
                filename=filename,
                pattern=pattern_match.pattern,
                pattern_match=pattern_match,
                time_data=time_data,
                smpte_timecode=smpte_timecode,
                frame_rate=fps,
            )

            # Add time offset metadata if applied
            if time_offset and smpte_timecode:
                result.time_offset_applied = True
                result.time_offset_direction = time_offset.get("direction", "behind")
                result.time_offset_hours = time_offset.get("hours", 0)
                result.time_offset_minutes = time_offset.get("minutes", 0)
                result.time_offset_seconds = time_offset.get("seconds", 0)

            self.logger.info(
                f"Successfully parsed: {time_data.time_string}"
                + (f" → {smpte_timecode}" if smpte_timecode else "")
            )

            return Result.success(result)

        except Exception as e:
            return Result.error(
                FileOperationError(
                    f"Unexpected error parsing filename: {e}",
                    user_message="An unexpected error occurred while parsing the filename.",
                    context={"filename": filename, "error": str(e)}
                )
            )

    def get_available_patterns(self) -> List[PatternDefinition]:
        """
        Get all available patterns.

        Returns:
            List of PatternDefinition objects
        """
        return pattern_library.get_all_patterns()

    def get_pattern(self, pattern_id: str) -> Optional[PatternDefinition]:
        """
        Get a specific pattern by ID.

        Args:
            pattern_id: Pattern identifier

        Returns:
            PatternDefinition or None if not found
        """
        return pattern_library.get_pattern(pattern_id)

    def search_patterns(
        self,
        query: str = None,
        category: str = None,
        has_date: bool = None,
        has_milliseconds: bool = None,
    ) -> List[PatternDefinition]:
        """
        Search patterns by criteria.

        Args:
            query: Search in name/description
            category: Filter by category
            has_date: Filter by date presence
            has_milliseconds: Filter by milliseconds presence

        Returns:
            List of matching PatternDefinition objects
        """
        return pattern_library.search_patterns(
            query=query,
            category=category,
            has_date=has_date,
            has_milliseconds=has_milliseconds,
        )

    def analyze_selection(
        self, filename: str, selection_start: int, selection_end: int
    ) -> Dict[str, any]:
        """
        Analyze a user selection for pattern generation.

        Args:
            filename: Full filename
            selection_start: Selection start position
            selection_end: Selection end position

        Returns:
            Dictionary with analysis results
        """
        return self.generator.analyze_selection(
            filename, selection_start, selection_end
        )

    def test_pattern(self, pattern: str, filename: str) -> tuple[bool, Optional[List[str]]]:
        """
        Test a regex pattern against a filename.

        Args:
            pattern: Regex pattern to test
            filename: Filename to test against

        Returns:
            Tuple of (success, extracted_groups)
        """
        return self.generator.test_pattern(pattern, filename)
