"""
Data models for filename pattern matching.

This module defines type-safe data structures for pattern definitions,
time component extraction, and pattern matching results.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal, Pattern
from enum import Enum
import re


class PatternCategory(str, Enum):
    """Categories for organizing filename patterns"""
    DVR_DAHUA = "dvr_dahua"
    DVR_HIKVISION = "dvr_hikvision"
    DVR_GENERIC = "dvr_generic"
    COMPACT_TIMESTAMP = "compact_timestamp"
    DELIMITED_TIMESTAMP = "delimited_timestamp"
    EMBEDDED_TIMESTAMP = "embedded_timestamp"
    EMBEDDED_DATETIME = "embedded_datetime"
    ISO_DATETIME = "iso_datetime"
    ISO8601 = "iso8601"
    ALTERNATIVE = "alternative"
    CUSTOM = "custom"


@dataclass
class TimeComponentDefinition:
    """
    Definition of a time component within a regex pattern.

    This self-describing structure maps regex capture groups to semantic
    time components with built-in validation constraints.
    """

    # What this component represents
    type: Literal[
        "hours", "minutes", "seconds", "milliseconds", "frames",
        "year", "month", "day", "channel", "camera_id"
    ]

    # Which regex capture group (1-indexed)
    group_index: int

    # Validation constraints
    min_value: int
    max_value: int

    # Optional component (may not be present in all matches)
    optional: bool = False

    # Human-readable name for UI
    display_name: Optional[str] = None

    def __post_init__(self):
        """Set default display names if not provided."""
        if self.display_name is None:
            self.display_name = self.type.replace("_", " ").title()

    def validate(self, value: int) -> bool:
        """
        Validate that a value is within the allowed range.

        Args:
            value: The value to validate

        Returns:
            True if valid, False otherwise
        """
        return self.min_value <= value <= self.max_value


@dataclass
class PatternDefinition:
    """
    Self-describing pattern definition for filename parsing.

    This structure combines a regex pattern with semantic metadata about
    what each capture group represents and how to validate it.
    """

    # Unique identifier (e.g., "dahua_nvr_standard")
    id: str

    # Human-readable name
    name: str

    # Description for users
    description: str

    # Example filename that matches
    example: str

    # Compiled regex pattern
    regex: str

    # Time component definitions (maps capture groups to semantics)
    components: List[TimeComponentDefinition]

    # Category for organization
    category: str  # Will be PatternCategory enum value

    # Priority for matching (higher = checked first)
    priority: int = 50  # 0-100 scale

    # Whether pattern includes date information
    has_date: bool = False

    # Whether pattern includes milliseconds
    has_milliseconds: bool = False

    # Tags for searching/filtering
    tags: List[str] = field(default_factory=list)

    # Cached compiled regex
    _compiled: Optional[Pattern] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Compile the regex pattern on initialization."""
        try:
            self._compiled = re.compile(self.regex)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{self.regex}': {e}")

    @property
    def compiled(self) -> Pattern:
        """Get the compiled regex pattern."""
        if self._compiled is None:
            self._compiled = re.compile(self.regex)
        return self._compiled

    def match(self, filename: str) -> Optional[re.Match]:
        """
        Test if this pattern matches a filename.

        Args:
            filename: Filename to test

        Returns:
            Match object if successful, None otherwise
        """
        return self.compiled.search(filename)

    def get_component_by_type(self, component_type: str) -> Optional[TimeComponentDefinition]:
        """
        Get a component definition by its type.

        Args:
            component_type: Type to search for (e.g., "hours", "minutes")

        Returns:
            TimeComponentDefinition if found, None otherwise
        """
        for component in self.components:
            if component.type == component_type:
                return component
        return None

    def get_component_by_group(self, group_index: int) -> Optional[TimeComponentDefinition]:
        """
        Get a component definition by its capture group index.

        Args:
            group_index: Regex capture group index (1-indexed)

        Returns:
            TimeComponentDefinition if found, None otherwise
        """
        for component in self.components:
            if component.group_index == group_index:
                return component
        return None


@dataclass
class PatternMatch:
    """
    Result of matching a pattern against a filename.

    Contains both the raw regex match and the extracted semantic components.
    """

    # The pattern that matched
    pattern: PatternDefinition

    # Original filename
    filename: str

    # Raw regex match object (for debugging)
    match: re.Match

    # Extracted components as a dictionary
    # e.g., {"hours": 16, "minutes": 38, "seconds": 20, "frames": 0}
    components: Dict[str, int]

    # Validation results
    valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    def get(self, component_type: str, default: Any = None) -> Any:
        """
        Get a component value by type.

        Args:
            component_type: Component type (e.g., "hours")
            default: Default value if not found

        Returns:
            Component value or default
        """
        return self.components.get(component_type, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "pattern_id": self.pattern.id,
            "pattern_name": self.pattern.name,
            "filename": self.filename,
            "components": self.components,
            "valid": self.valid,
            "validation_errors": self.validation_errors,
        }
