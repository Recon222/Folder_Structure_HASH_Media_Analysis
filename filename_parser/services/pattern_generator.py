"""
Smart pattern generator service.

This service provides intelligent pattern generation from user selections,
with semantic understanding of what components represent (HHMMSS vs YYMMDD, etc.).
"""

import re
from typing import Optional, Tuple, List, Dict
from filename_parser.models.pattern_models import PatternDefinition, TimeComponentDefinition
from core.logger import logger


class PatternGenerator:
    """
    Intelligent pattern generator with semantic understanding.

    Analyzes user-selected text and generates self-describing patterns
    with guidance about what each component represents.
    """

    def analyze_selection(
        self, filename: str, selection_start: int, selection_end: int
    ) -> Dict[str, any]:
        """
        Analyze a user selection and provide semantic interpretation.

        Args:
            filename: Full filename
            selection_start: Selection start position
            selection_end: Selection end position

        Returns:
            Dictionary with analysis results
        """
        selected_text = filename[selection_start:selection_end]
        context_before = filename[max(0, selection_start - 15):selection_start]
        context_after = filename[selection_end:min(len(filename), selection_end + 15)]

        logger.debug(
            f"Analyzing selection: '{selected_text}' "
            f"(before: '{context_before[-10:]}', after: '{context_after[:10]}')"
        )

        # Detect what the selection represents
        interpretation = self._interpret_selection(selected_text)

        # Detect format
        format_type = self._detect_format(selected_text)

        # Check for standard suffix patterns
        is_suffix_pattern = self._is_suffix_pattern(filename, selection_start, selection_end)

        # Generate suggested pattern
        suggested_pattern = self._generate_pattern(
            selected_text,
            context_before,
            context_after,
            interpretation,
            format_type,
            is_suffix_pattern,
        )

        return {
            "selected_text": selected_text,
            "interpretation": interpretation,
            "format_type": format_type,
            "is_suffix_pattern": is_suffix_pattern,
            "suggested_pattern": suggested_pattern,
            "context_before": context_before,
            "context_after": context_after,
        }

    def _interpret_selection(self, text: str) -> str:
        """
        Interpret what the selected text represents.

        Args:
            text: Selected text

        Returns:
            Interpretation string (e.g., "HHMMSS", "YYYYMMDD_HHMMSS", etc.)
        """
        clean_text = "".join(c for c in text if c.isalnum())

        # Check for date + time patterns (12 digits)
        if clean_text.isdigit() and len(clean_text) == 12:
            # Could be YYYYMMDDHHMMSS or MMDDYYHHMMSS
            # Try to disambiguate based on first digits
            if clean_text[:4] >= "2000":
                return "YYYYMMDD_HHMMSS"
            elif int(clean_text[:2]) <= 12:  # Likely month
                return "MMDDYY_HHMMSS"
            else:
                return "UNKNOWN_12_DIGITS"

        # Check for time with milliseconds (9 digits)
        if clean_text.isdigit() and len(clean_text) == 9:
            return "HHMMSS_mmm"

        # Check for time only (6 digits)
        if clean_text.isdigit() and len(clean_text) == 6:
            # Could be HHMMSS or YYMMDD
            hours_candidate = int(clean_text[:2])
            if hours_candidate <= 23:
                # Likely time
                return "HHMMSS"
            else:
                # Likely date (YYMMDD)
                return "YYMMDD"

        # Check for time only (4 digits - HHMM)
        if clean_text.isdigit() and len(clean_text) == 4:
            return "HHMM"

        # Check for delimited patterns
        if ":" in text and text.count(":") >= 2:
            if "." in text:
                return "HH:MM:SS.mmm"
            else:
                return "HH:MM:SS"

        if "-" in text and len(text.split("-")) >= 3:
            return "HH-MM-SS"

        if "_" in text and len(text.split("_")) >= 3:
            # Could be date or time
            parts = text.split("_")
            if len(parts[0]) == 2 and int(parts[0]) <= 23:
                return "HH_MM_SS"
            elif len(parts[0]) == 4:
                return "YYYY_MM_DD"
            else:
                return "DELIMITED_UNKNOWN"

        return "UNKNOWN"

    def _detect_format(self, text: str) -> str:
        """
        Detect the format type of selected text.

        Args:
            text: Selected text

        Returns:
            Format type string
        """
        # Remove non-alphanumeric for analysis
        clean_text = "".join(c for c in text if c.isalnum())

        # Digit-only patterns
        if clean_text.isdigit():
            length = len(clean_text)
            if length == 12:
                return "12-digit (Date+Time)"
            elif length == 9:
                return "9-digit (HHMMSS+milliseconds)"
            elif length == 6:
                return "6-digit (HHMMSS or YYMMDD)"
            elif length == 4:
                return "4-digit (HHMM)"
            else:
                return f"{length}-digit sequence"

        # Delimited patterns
        if ":" in text:
            count = text.count(":")
            if count == 3:
                return "HH:MM:SS:FF (SMPTE)"
            elif count == 2:
                return "HH:MM:SS"
            else:
                return "Colon-delimited"

        if "-" in text:
            return "Dash-delimited"

        if "_" in text:
            return "Underscore-delimited"

        if "." in text:
            return "Dot-delimited"

        return "Unknown format"

    def _is_suffix_pattern(
        self, filename: str, selection_start: int, selection_end: int
    ) -> bool:
        """
        Check if selection is part of a standardized suffix pattern (_C.mp4).

        Args:
            filename: Full filename
            selection_start: Selection start position
            selection_end: Selection end position

        Returns:
            True if suffix pattern detected
        """
        # Check if filename ends with _C.mp4 (case-insensitive)
        if not re.search(r"_C\.(mp4|MP4)$", filename):
            return False

        # Check if selection is near the end before _C
        remaining_text = filename[selection_end:]
        if "_C" in remaining_text and len(remaining_text) < 10:
            return True

        return False

    def _generate_pattern(
        self,
        selected_text: str,
        context_before: str,
        context_after: str,
        interpretation: str,
        format_type: str,
        is_suffix: bool,
    ) -> str:
        """
        Generate a regex pattern based on analysis.

        Args:
            selected_text: Selected text
            context_before: Text before selection
            context_after: Text after selection
            interpretation: Semantic interpretation
            format_type: Format type
            is_suffix: Whether it's a suffix pattern

        Returns:
            Regex pattern string
        """
        # Generate timestamp pattern based on interpretation
        timestamp_pattern = self._create_timestamp_pattern(
            selected_text, interpretation
        )

        # If suffix pattern, create suffix-specific pattern
        if is_suffix and "_C" in context_after:
            # Check if date is included
            if "_" in selected_text and len(selected_text.split("_")) == 2:
                # Likely YYMMDD_HHMMSS format
                return r"_(\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_C$"
            else:
                # Time only
                return rf"_\d{{6}}_{timestamp_pattern}_C$"

        # Context-aware pattern generation
        delimiter_before = self._find_delimiter(context_before, at_end=True)
        delimiter_after = self._find_delimiter(context_after, at_end=False)

        # Build pattern with context
        pattern_parts = [".*"]

        if delimiter_before:
            pattern_parts.append(re.escape(delimiter_before))

        pattern_parts.append(timestamp_pattern)

        if delimiter_after:
            pattern_parts.append(re.escape(delimiter_after))

        if not delimiter_after:
            pattern_parts.append(".*")

        return "".join(pattern_parts)

    def _create_timestamp_pattern(
        self, text: str, interpretation: str
    ) -> str:
        """
        Create regex pattern for timestamp based on interpretation.

        Args:
            text: Selected text
            interpretation: Semantic interpretation

        Returns:
            Regex pattern for timestamp
        """
        patterns = {
            "HHMMSS": r"(\d{2})(\d{2})(\d{2})",
            "HHMMSS_mmm": r"(\d{2})(\d{2})(\d{2})(\d{3})",
            "HH:MM:SS": r"(\d{2}):(\d{2}):(\d{2})",
            "HH:MM:SS.mmm": r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})",
            "HH-MM-SS": r"(\d{2})-(\d{2})-(\d{2})",
            "HH_MM_SS": r"(\d{2})_(\d{2})_(\d{2})",
            "HHMM": r"(\d{2})(\d{2})",
            "YYYYMMDD_HHMMSS": r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})",
            "MMDDYY_HHMMSS": r"(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})",
            "YYMMDD": r"(\d{2})(\d{2})(\d{2})",
        }

        return patterns.get(interpretation, re.escape(text))

    def _find_delimiter(self, context: str, at_end: bool) -> str:
        """
        Find delimiter character in context.

        Args:
            context: Context text
            at_end: Whether to look at end (True) or start (False)

        Returns:
            Delimiter character or empty string
        """
        delimiters = ["_", "-", ":", ".", " "]

        if at_end and context:
            if context[-1] in delimiters:
                return context[-1]
        elif not at_end and context:
            if context[0] in delimiters:
                return context[0]

        return ""

    def test_pattern(
        self, pattern: str, filename: str
    ) -> Tuple[bool, Optional[List[str]]]:
        """
        Test a generated pattern against a filename.

        Args:
            pattern: Regex pattern to test
            filename: Filename to test against

        Returns:
            Tuple of (success, extracted_groups)
        """
        try:
            match = re.search(pattern, filename)
            if match:
                return True, list(match.groups())
            else:
                return False, None
        except re.error as e:
            logger.error(f"Invalid regex pattern: {e}")
            return False, None
