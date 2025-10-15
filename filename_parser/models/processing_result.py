"""
Data models for file processing results.

This module defines type-safe data structures for tracking
file processing outcomes, performance metrics, and error information.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ProcessingStatus(str, Enum):
    """Status of file processing operations."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ProcessingResult:
    """
    Result of processing a single video file.

    Contains all information about the processing operation including
    success status, timecode information, performance metrics, and errors.
    """

    # Input information
    source_file: str
    filename: str

    # Processing status
    status: ProcessingStatus
    success: bool

    # Output information
    output_file: Optional[str] = None
    smpte_timecode: Optional[str] = None

    # Metadata (basic)
    frame_rate: Optional[float] = None
    fps_detection_method: Optional[str] = None  # "metadata", "pts_timing", or "override"
    fps_fallback_occurred: bool = False  # True if PTS detection failed and fell back to metadata
    pattern_used: Optional[str] = None
    parsed_time: Optional[str] = None

    # Date components (extracted from filename)
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None

    # NEW: Full video metadata for timeline rendering (GPT-5 approach)
    duration_seconds: float = 0.0
    start_time_iso: Optional[str] = None  # ISO8601 format (e.g., "2025-05-21T14:30:00")
    end_time_iso: Optional[str] = None    # ISO8601 format (start + duration)
    camera_id: Optional[str] = None       # Extracted from path/filename
    width: int = 0
    height: int = 0
    codec: str = ""
    pixel_format: str = ""
    video_bitrate: int = 0

    # Frame-accurate timing fields (CCTV SMPTE integration)
    first_frame_pts: float = 0.0              # Sub-second offset (e.g., 0.297222)
    first_frame_type: Optional[str] = None    # "I", "P", or "B" frame type
    first_frame_is_keyframe: bool = False     # Closed GOP indicator

    # Conversion information
    format_converted: bool = False
    format_conversion_reason: Optional[str] = None
    original_extension: Optional[str] = None
    output_extension: Optional[str] = None

    # Time offset tracking
    time_offset_applied: bool = False
    time_offset_direction: Optional[str] = None
    time_offset_hours: int = 0
    time_offset_minutes: int = 0
    time_offset_seconds: int = 0

    # Performance metrics
    processing_time: float = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # Error information
    error_message: Optional[str] = None
    error_details: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "source_file": self.source_file,
            "filename": self.filename,
            "status": self.status.value
            if isinstance(self.status, ProcessingStatus)
            else self.status,
            "success": self.success,
            "output_file": self.output_file,
            "smpte_timecode": self.smpte_timecode,
            "frame_rate": self.frame_rate,
            "fps_detection_method": self.fps_detection_method,
            "fps_fallback_occurred": self.fps_fallback_occurred,
            "pattern_used": self.pattern_used,
            "parsed_time": self.parsed_time,
            # Date components
            "year": self.year,
            "month": self.month,
            "day": self.day,
            # Full video metadata
            "duration_seconds": self.duration_seconds,
            "start_time_iso": self.start_time_iso,
            "end_time_iso": self.end_time_iso,
            "camera_id": self.camera_id,
            "width": self.width,
            "height": self.height,
            "codec": self.codec,
            "pixel_format": self.pixel_format,
            "video_bitrate": self.video_bitrate,
            # Frame-accurate timing fields
            "first_frame_pts": self.first_frame_pts,
            "first_frame_type": self.first_frame_type,
            "first_frame_is_keyframe": self.first_frame_is_keyframe,
            # Conversion info
            "format_converted": self.format_converted,
            "format_conversion_reason": self.format_conversion_reason,
            "original_extension": self.original_extension,
            "output_extension": self.output_extension,
            "time_offset_applied": self.time_offset_applied,
            "time_offset_direction": self.time_offset_direction,
            "time_offset_hours": self.time_offset_hours,
            "time_offset_minutes": self.time_offset_minutes,
            "time_offset_seconds": self.time_offset_seconds,
            "processing_time": self.processing_time,
            "error_message": self.error_message,
            "error_details": self.error_details,
        }


@dataclass
class ProcessingStatistics:
    """
    Aggregate statistics for batch processing operations.

    Tracks overall performance, success rates, and processing metrics
    across multiple files.
    """

    total_files: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0

    total_processing_time: float = 0.0
    average_processing_time: float = 0.0
    min_processing_time: float = 0.0
    max_processing_time: float = 0.0

    files_per_second: float = 0.0

    format_conversions: int = 0

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    results: List[ProcessingResult] = field(default_factory=list)

    def calculate_from_results(self, results: List[ProcessingResult]) -> None:
        """
        Calculate statistics from a list of processing results.

        Args:
            results: List of ProcessingResult objects
        """
        self.results = results
        self.total_files = len(results)

        if not results:
            return

        # Count statuses
        self.successful = sum(1 for r in results if r.success)
        self.failed = sum(
            1 for r in results if not r.success and r.status == ProcessingStatus.FAILED
        )
        self.skipped = sum(1 for r in results if r.status == ProcessingStatus.SKIPPED)

        # Calculate processing times
        processing_times = [r.processing_time for r in results if r.processing_time > 0]
        if processing_times:
            self.total_processing_time = sum(processing_times)
            self.average_processing_time = self.total_processing_time / len(processing_times)
            self.min_processing_time = min(processing_times)
            self.max_processing_time = max(processing_times)

            if self.total_processing_time > 0:
                self.files_per_second = len(processing_times) / self.total_processing_time

        # Count format conversions
        self.format_conversions = sum(1 for r in results if r.format_converted)

        # Set time boundaries
        start_times = [r.start_time for r in results if r.start_time]
        end_times = [r.end_time for r in results if r.end_time]

        if start_times:
            self.start_time = min(start_times)
        if end_times:
            self.end_time = max(end_times)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "total_files": self.total_files,
            "successful": self.successful,
            "failed": self.failed,
            "skipped": self.skipped,
            "total_processing_time": self.total_processing_time,
            "average_processing_time": self.average_processing_time,
            "min_processing_time": self.min_processing_time,
            "max_processing_time": self.max_processing_time,
            "files_per_second": self.files_per_second,
            "format_conversions": self.format_conversions,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }

    def __str__(self) -> str:
        """Human-readable statistics summary."""
        return (
            f"Processed {self.total_files} files: "
            f"{self.successful} successful, {self.failed} failed, {self.skipped} skipped | "
            f"Avg: {self.average_processing_time:.2f}s/file | "
            f"Throughput: {self.files_per_second:.2f} files/sec"
        )
