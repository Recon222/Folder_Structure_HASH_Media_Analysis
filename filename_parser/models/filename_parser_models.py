"""
Filename Parser specific models and settings.

This module contains settings and configuration models for the filename parser module.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path


@dataclass
class FilenameParserSettings:
    """Settings for filename parsing operations"""

    # Pattern selection
    pattern_id: Optional[str] = None  # None = auto-detect
    custom_pattern: Optional[str] = None  # Custom regex if pattern_id is "custom"

    # Frame rate
    detect_fps: bool = True
    fps_override: Optional[float] = None  # Manual FPS if not detecting

    # Time offset
    enable_time_offset: bool = False
    time_offset_direction: str = "behind"  # "behind" or "ahead"
    time_offset_hours: int = 0
    time_offset_minutes: int = 0
    time_offset_seconds: int = 0

    # Output structure
    use_mirrored_structure: bool = False
    base_output_directory: Optional[Path] = None

    # Processing options
    write_metadata: bool = False  # Whether to write SMPTE to files (default: parse only)
    export_csv: bool = False  # CSV export is manual action after parsing
    csv_output_path: Optional[Path] = None

    # Parallel processing
    use_parallel_processing: bool = True
    max_workers: int = 4

    def get_time_offset_dict(self) -> Optional[Dict[str, Any]]:
        """
        Get time offset as dictionary for service.

        Returns:
            Dictionary with offset configuration or None if disabled
        """
        if not self.enable_time_offset:
            return None

        return {
            "direction": self.time_offset_direction,
            "hours": self.time_offset_hours,
            "minutes": self.time_offset_minutes,
            "seconds": self.time_offset_seconds,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "pattern_id": self.pattern_id,
            "custom_pattern": self.custom_pattern,
            "detect_fps": self.detect_fps,
            "fps_override": self.fps_override,
            "enable_time_offset": self.enable_time_offset,
            "time_offset_direction": self.time_offset_direction,
            "time_offset_hours": self.time_offset_hours,
            "time_offset_minutes": self.time_offset_minutes,
            "time_offset_seconds": self.time_offset_seconds,
            "use_mirrored_structure": self.use_mirrored_structure,
            "base_output_directory": str(self.base_output_directory) if self.base_output_directory else None,
            "write_metadata": self.write_metadata,
            "export_csv": self.export_csv,
            "csv_output_path": str(self.csv_output_path) if self.csv_output_path else None,
            "use_parallel_processing": self.use_parallel_processing,
            "max_workers": self.max_workers,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FilenameParserSettings":
        """Create from dictionary."""
        base_output = data.get("base_output_directory")
        csv_output = data.get("csv_output_path")

        return cls(
            pattern_id=data.get("pattern_id"),
            custom_pattern=data.get("custom_pattern"),
            detect_fps=data.get("detect_fps", True),
            fps_override=data.get("fps_override"),
            enable_time_offset=data.get("enable_time_offset", False),
            time_offset_direction=data.get("time_offset_direction", "behind"),
            time_offset_hours=data.get("time_offset_hours", 0),
            time_offset_minutes=data.get("time_offset_minutes", 0),
            time_offset_seconds=data.get("time_offset_seconds", 0),
            use_mirrored_structure=data.get("use_mirrored_structure", False),
            base_output_directory=Path(base_output) if base_output else None,
            write_metadata=data.get("write_metadata", False),
            export_csv=data.get("export_csv", True),
            csv_output_path=Path(csv_output) if csv_output else None,
            use_parallel_processing=data.get("use_parallel_processing", True),
            max_workers=data.get("max_workers", 4),
        )
