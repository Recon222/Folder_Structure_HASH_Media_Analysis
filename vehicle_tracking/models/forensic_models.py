"""
Forensic models for vehicle tracking with court-defensible speed calculation.

This module provides data structures for forensically sound speed tracking
that avoids interpolated speeds and maintains clear certainty indicators.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

from .vehicle_tracking_models import GPSPoint


class SpeedCertainty(Enum):
    """
    Speed calculation certainty based on time gap between GPS points.
    Used for court-defensible speed reporting.
    """
    HIGH = "high"        # Δt ≤ 5s - Reliable for forensic use
    MEDIUM = "medium"    # 5 < Δt ≤ 10s - Acceptable with caveat
    LOW = "low"          # 10 < Δt ≤ 30s - Questionable accuracy
    UNKNOWN = "unknown"  # Δt > 30s - No speed calculation (gap too large)


@dataclass
class SegmentSpeed:
    """
    Speed information for a single GPS segment.

    Represents the average speed between two observed GPS points.
    No interpolation or acceleration assumptions are made.
    """
    speed_kmh: Optional[float]  # None for temporal conflicts or unknown gaps
    certainty: SpeedCertainty
    distance_m: float
    time_seconds: float  # Actual time difference (could be 0 for conflicts)
    gap_type: Optional[str] = None  # 'stop', 'gap', 'temporal_conflict', 'stop/coalesced', 'normal'

    def is_valid(self) -> bool:
        """Check if this segment has a valid calculable speed."""
        return self.speed_kmh is not None and self.gap_type not in ['temporal_conflict', 'gap']

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'speed_kmh': self.speed_kmh,
            'certainty': self.certainty.value,
            'distance_m': self.distance_m,
            'time_seconds': self.time_seconds,
            'gap_type': self.gap_type
        }


@dataclass
class GPSSegment:
    """
    A segment between two observed GPS points.

    This is the fundamental unit of forensic speed calculation.
    Each segment has ONE constant speed that applies to all
    interpolated points within it.
    """
    start_point: GPSPoint
    end_point: GPSPoint
    segment_speed: SegmentSpeed
    interpolated_points: List[GPSPoint] = field(default_factory=list)

    @property
    def segment_id(self) -> Optional[int]:
        """Get the segment ID if set on points."""
        return self.start_point.segment_id

    @property
    def duration(self) -> float:
        """Get segment duration in seconds."""
        return self.segment_speed.time_seconds

    @property
    def is_gap(self) -> bool:
        """Check if this segment represents a gap in data."""
        return self.segment_speed.gap_type == 'gap'

    @property
    def is_conflict(self) -> bool:
        """Check if this segment has a temporal conflict."""
        return self.segment_speed.gap_type == 'temporal_conflict'

    @property
    def is_stop(self) -> bool:
        """Check if this segment represents a stop."""
        return self.segment_speed.gap_type in ['stop', 'stop/coalesced']

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'start_point': self.start_point.to_dict(),
            'end_point': self.end_point.to_dict(),
            'segment_speed': self.segment_speed.to_dict(),
            'interpolated_count': len(self.interpolated_points),
            'segment_id': self.segment_id
        }


@dataclass
class ForensicSpeedAnalysis:
    """
    Complete forensic speed analysis for a vehicle.

    Contains all segments and analysis metadata for court presentation.
    """
    vehicle_id: str
    segments: List[GPSSegment]
    total_distance_m: float
    total_duration_s: float
    average_speed_kmh: Optional[float]
    max_speed_kmh: Optional[float]
    min_speed_kmh: Optional[float]

    # Analysis quality metrics
    high_certainty_count: int = 0
    medium_certainty_count: int = 0
    low_certainty_count: int = 0
    unknown_count: int = 0

    # Anomaly counts
    gap_count: int = 0
    conflict_count: int = 0
    stop_count: int = 0

    def calculate_metrics(self):
        """Calculate analysis metrics from segments."""
        valid_speeds = []

        for segment in self.segments:
            # Count certainty levels
            if segment.segment_speed.certainty == SpeedCertainty.HIGH:
                self.high_certainty_count += 1
            elif segment.segment_speed.certainty == SpeedCertainty.MEDIUM:
                self.medium_certainty_count += 1
            elif segment.segment_speed.certainty == SpeedCertainty.LOW:
                self.low_certainty_count += 1
            else:
                self.unknown_count += 1

            # Count anomalies
            if segment.is_gap:
                self.gap_count += 1
            elif segment.is_conflict:
                self.conflict_count += 1
            elif segment.is_stop:
                self.stop_count += 1

            # Collect valid speeds
            if segment.segment_speed.is_valid():
                valid_speeds.append(segment.segment_speed.speed_kmh)

        # Calculate speed statistics
        if valid_speeds:
            self.average_speed_kmh = sum(valid_speeds) / len(valid_speeds)
            self.max_speed_kmh = max(valid_speeds)
            self.min_speed_kmh = min(valid_speeds)

        # Calculate totals
        self.total_distance_m = sum(s.segment_speed.distance_m for s in self.segments)
        self.total_duration_s = sum(s.segment_speed.time_seconds for s in self.segments
                                   if not s.is_conflict)  # Don't count conflicts in duration

    @property
    def reliability_score(self) -> float:
        """
        Calculate reliability score (0-1) based on certainty distribution.
        Higher score = more reliable data for forensic use.
        """
        total = len(self.segments)
        if total == 0:
            return 0.0

        # Weight: HIGH=1.0, MEDIUM=0.6, LOW=0.3, UNKNOWN=0
        score = (self.high_certainty_count * 1.0 +
                self.medium_certainty_count * 0.6 +
                self.low_certainty_count * 0.3) / total

        return min(1.0, score)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'vehicle_id': self.vehicle_id,
            'total_distance_m': self.total_distance_m,
            'total_duration_s': self.total_duration_s,
            'average_speed_kmh': self.average_speed_kmh,
            'max_speed_kmh': self.max_speed_kmh,
            'min_speed_kmh': self.min_speed_kmh,
            'reliability_score': self.reliability_score,
            'certainty_distribution': {
                'high': self.high_certainty_count,
                'medium': self.medium_certainty_count,
                'low': self.low_certainty_count,
                'unknown': self.unknown_count
            },
            'anomalies': {
                'gaps': self.gap_count,
                'conflicts': self.conflict_count,
                'stops': self.stop_count
            },
            'segment_count': len(self.segments)
        }