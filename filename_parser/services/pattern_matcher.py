"""
Pattern matching service for filename parsing.

This service handles matching filenames against patterns and validating
extracted components against their defined constraints.
"""

import os
from typing import Optional, List
from filename_parser.models.pattern_models import PatternDefinition, PatternMatch, TimeComponentDefinition
from filename_parser.services.pattern_library import pattern_library
from filename_parser.services.component_extractor import component_extractor
from core.logger import logger


class PatternMatcher:
    """
    Service for matching filenames against patterns with validation.

    Handles pattern matching, component extraction, and validation
    of extracted values against defined constraints.
    """

    def __init__(self):
        """Initialize the pattern matcher."""
        self.library = pattern_library

    def match(
        self, filename: str, pattern_id: Optional[str] = None
    ) -> Optional[PatternMatch]:
        """
        Match a filename against patterns.

        Args:
            filename: Filename to match (with or without path)
            pattern_id: Optional specific pattern ID to use

        Returns:
            PatternMatch if successful, None otherwise
        """
        # Extract basename (keep extension for universal matching)
        basename = os.path.basename(filename)

        logger.debug(f"Matching filename: '{basename}'")

        # If specific pattern requested, try only that one
        if pattern_id:
            pattern = self.library.get_pattern(pattern_id)
            if pattern:
                return self._try_pattern(basename, pattern)
            else:
                logger.warning(f"Pattern ID '{pattern_id}' not found in library")
                return None

        # Try all patterns in priority order
        for pattern in self.library.get_all_patterns():
            result = self._try_pattern(basename, pattern)
            if result and result.valid:
                logger.info(
                    f"Matched pattern '{pattern.name}' (ID: {pattern.id}) "
                    f"with priority {pattern.priority}"
                )
                return result

        logger.warning(f"No monolithic pattern matched filename: '{basename}'")

        # FALLBACK: Try two-phase component extraction
        logger.info("Attempting two-phase component extraction fallback...")
        return self._try_two_phase_extraction(basename)

    def match_multiple(
        self, filename: str, pattern_ids: List[str]
    ) -> Optional[PatternMatch]:
        """
        Try multiple specific patterns in order.

        Args:
            filename: Filename to match
            pattern_ids: List of pattern IDs to try in order

        Returns:
            First successful PatternMatch or None
        """
        basename = os.path.basename(filename)

        for pattern_id in pattern_ids:
            pattern = self.library.get_pattern(pattern_id)
            if pattern:
                result = self._try_pattern(basename, pattern)
                if result and result.valid:
                    return result

        return None

    def _try_pattern(
        self, basename: str, pattern: PatternDefinition
    ) -> Optional[PatternMatch]:
        """
        Try to match a single pattern against a filename.

        Args:
            basename: Filename without path (includes extension)
            pattern: Pattern to try

        Returns:
            PatternMatch if matched, None otherwise
        """
        # Try to match the pattern
        match = pattern.match(basename)
        if not match:
            logger.debug(f"Pattern '{pattern.id}' did not match")
            return None

        logger.debug(
            f"Pattern '{pattern.id}' matched with groups: {match.groups()}"
        )

        # Extract components
        components = {}
        validation_errors = []

        for comp_def in pattern.components:
            # Get the value from the capture group
            group_value = match.group(comp_def.group_index)

            # Handle optional components
            if group_value is None:
                if comp_def.optional:
                    logger.debug(
                        f"Optional component '{comp_def.type}' not present"
                    )
                    continue
                else:
                    error = f"Required component '{comp_def.type}' (group {comp_def.group_index}) is missing"
                    logger.warning(error)
                    validation_errors.append(error)
                    continue

            # Convert to integer
            try:
                value = int(group_value)
            except ValueError:
                error = f"Component '{comp_def.type}' has non-numeric value: '{group_value}'"
                logger.warning(error)
                validation_errors.append(error)
                continue

            # Validate against constraints
            if not comp_def.validate(value):
                error = (
                    f"Component '{comp_def.type}' value {value} is out of range "
                    f"({comp_def.min_value}-{comp_def.max_value})"
                )
                logger.warning(error)
                validation_errors.append(error)
                # Still include the value for debugging
                components[comp_def.type] = value
                continue

            # Store validated component
            components[comp_def.type] = value
            logger.debug(
                f"Extracted {comp_def.type}={value} from group {comp_def.group_index}"
            )

        # Handle YY format years (convert to full year)
        if "year" in components and components["year"] < 100:
            # Assume 20XX for years 00-99
            components["year"] = 2000 + components["year"]
            logger.debug(f"Converted 2-digit year to: {components['year']}")

        # Create PatternMatch result
        is_valid = len(validation_errors) == 0
        pattern_match = PatternMatch(
            pattern=pattern,
            filename=basename,
            match=match,
            components=components,
            valid=is_valid,
            validation_errors=validation_errors,
        )

        if is_valid:
            logger.debug(
                f"Successfully matched and validated pattern '{pattern.id}'"
            )
        else:
            logger.warning(
                f"Pattern '{pattern.id}' matched but validation failed: {validation_errors}"
            )

        return pattern_match

    def validate_components(
        self, components: dict, pattern: PatternDefinition
    ) -> tuple[bool, List[str]]:
        """
        Validate component values against a pattern's constraints.

        Args:
            components: Dictionary of component values
            pattern: Pattern definition with constraints

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        for comp_def in pattern.components:
            if comp_def.optional and comp_def.type not in components:
                continue

            if comp_def.type not in components:
                if not comp_def.optional:
                    errors.append(
                        f"Required component '{comp_def.type}' is missing"
                    )
                continue

            value = components[comp_def.type]

            if not comp_def.validate(value):
                errors.append(
                    f"Component '{comp_def.type}' value {value} is out of range "
                    f"({comp_def.min_value}-{comp_def.max_value})"
                )

        return len(errors) == 0, errors

    def _try_two_phase_extraction(self, basename: str) -> Optional[PatternMatch]:
        """
        Attempt two-phase component extraction as fallback.

        This method is called when monolithic pattern matching fails.
        It extracts date and time components independently, then combines them.

        Args:
            basename: The filename to parse

        Returns:
            PatternMatch if components extracted successfully, None otherwise
        """
        try:
            # Extract best date and time components
            best_date, best_time = component_extractor.extract_best_components(basename)

            if not best_time:
                logger.warning("Two-phase extraction failed: no valid time found")
                return None

            # Build component dictionary
            components = {
                "hours": best_time.hours,
                "minutes": best_time.minutes,
                "seconds": best_time.seconds,
            }

            if best_time.milliseconds > 0:
                components["milliseconds"] = best_time.milliseconds

            if best_date:
                components["year"] = best_date.year
                components["month"] = best_date.month
                components["day"] = best_date.day

            # Create synthetic pattern definition for two-phase match
            synthetic_pattern = PatternDefinition(
                id="two_phase_extraction",
                name="Two-Phase Extraction",
                description="Date and time extracted independently with smart heuristics",
                example=basename,
                regex="",  # No regex for two-phase
                components=[],  # No component definitions needed
                category="hybrid",
                priority=0,  # Lowest priority (fallback only)
                has_date=best_date is not None,
                has_milliseconds=best_time.milliseconds > 0,
                tags=["two_phase", "fallback", "smart_extraction"]
            )

            # Create PatternMatch
            match = PatternMatch(
                pattern=synthetic_pattern,
                components=components,
                raw_match="",  # No regex match for two-phase
                valid=True,
                validation_errors=[]
            )

            logger.info(
                f"✅ Two-phase extraction succeeded: "
                f"date={best_date.year}-{best_date.month:02d}-{best_date.day:02d} " if best_date else "date=None, "
                f"time={best_time.hours:02d}:{best_time.minutes:02d}:{best_time.seconds:02d} "
                f"(confidence: date={best_date.confidence:.2f}, time={best_time.confidence:.2f})" if best_date else f"(confidence: time={best_time.confidence:.2f})"
            )

            return match

        except Exception as e:
            logger.error(f"Two-phase extraction error: {e}")
            return None
