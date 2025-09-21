"""
Forensic speed calculator for court-defensible vehicle tracking.

This module calculates segment-based speeds without interpolation,
ensuring all speed values are directly based on observed GPS points.
"""

import math
from typing import List, Optional, Tuple, Dict, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass

from ..models.vehicle_tracking_models import GPSPoint
from ..models.forensic_models import SpeedCertainty, SegmentSpeed, GPSSegment


class ForensicSpeedCalculator:
    """
    Calculates forensically defensible speeds for GPS segments.

    Key principles:
    - One speed per segment (no interpolation)
    - Temporal conflicts produce None speed
    - Metric projection is mandatory for accuracy
    - Clear certainty indicators based on time gaps
    """

    MIN_TIME_DELTA = 0.5  # Minimum credible time between points (seconds)

    def __init__(self, settings=None):
        """
        Initialize calculator with settings.

        Args:
            settings: Dictionary of settings including:
                - high_certainty_threshold_s: Max seconds for HIGH certainty (default 5)
                - medium_certainty_threshold_s: Max seconds for MEDIUM certainty (default 10)
                - max_gap_threshold_s: Max seconds before marking as gap (default 30)
        """
        self.settings = settings or {}
        self.high_threshold = self.settings.get('high_certainty_threshold_s', 5.0)
        self.medium_threshold = self.settings.get('medium_certainty_threshold_s', 10.0)
        self.max_gap_threshold = self.settings.get('max_gap_threshold_s', 30.0)

    def calculate_segment_speeds(
        self,
        points: List[GPSPoint],
        to_metric: Callable,  # MANDATORY - no Optional
        to_wgs84: Callable   # MANDATORY - no Optional
    ) -> List[GPSSegment]:
        """
        Calculate speeds using MANDATORY metric projection.

        No fallback to Haversine - metric projection required for forensic accuracy.

        Args:
            points: List of GPS points (must be pre-processed/coalesced)
            to_metric: Transformer function to convert WGS84 to metric coordinates
            to_wgs84: Transformer function to convert metric to WGS84 (for verification)

        Returns:
            List of GPSSegments with forensic speed calculations

        Raises:
            ValueError: If metric projection is not provided
        """
        if not to_metric or not to_wgs84:
            raise ValueError("Metric projection is mandatory for forensic speed calculation")

        segments = []

        for i in range(len(points) - 1):
            segment = self._create_segment(
                points[i], points[i + 1],
                to_metric, to_wgs84,
                segment_index=i
            )
            segments.append(segment)

        return segments

    def _create_segment(
        self,
        start: GPSPoint,
        end: GPSPoint,
        to_metric: Callable,
        to_wgs84: Callable,
        segment_index: int = 0
    ) -> GPSSegment:
        """
        Create segment with metric-accurate distance.

        Metric projection is MANDATORY - no fallbacks.

        Args:
            start: Starting GPS point
            end: Ending GPS point
            to_metric: Metric projection transformer
            to_wgs84: Inverse transformer (for verification)
            segment_index: Index of this segment

        Returns:
            GPSSegment with forensic speed calculation
        """
        # Calculate distance using mandatory metric projection
        distance_m = self._metric_distance(start, end, to_metric)

        # Calculate time difference
        time_diff = (end.timestamp - start.timestamp).total_seconds()

        # Enhanced duplicate timestamp handling
        if time_diff == 0:
            if start.latitude == end.latitude and start.longitude == end.longitude:
                # Same location - already coalesced in preprocessing
                # This shouldn't happen if preprocessing was done
                gap_type = "stop/coalesced"
                speed_kmh = 0  # Definitive stop
                certainty = SpeedCertainty.HIGH
            else:
                # Different locations - temporal conflict
                # DO NOT fabricate time delta or speed
                gap_type = "temporal_conflict"
                speed_kmh = None  # No speed calculation possible
                certainty = SpeedCertainty.LOW
                # Keep time_diff as 0 for accurate reporting
        else:
            gap_type = "normal"
            certainty = self._determine_certainty(time_diff)

            # Calculate speed only for non-conflict segments
            if certainty == SpeedCertainty.UNKNOWN:
                # Gap too large - don't calculate speed
                speed_kmh = None
                gap_type = "gap"
            else:
                # Valid segment - calculate speed
                speed_kmh = (distance_m / time_diff) * 3.6  # Convert m/s to km/h

                # Check for stops (minimal movement)
                if distance_m < 5.0 and time_diff > 5.0:  # Less than 5m in 5+ seconds
                    gap_type = "stop"
                    speed_kmh = 0  # Override to 0 for stops

        # Set segment IDs on points
        start.segment_id = segment_index
        end.segment_id = segment_index

        return GPSSegment(
            start_point=start,
            end_point=end,
            segment_speed=SegmentSpeed(
                speed_kmh=speed_kmh,
                certainty=certainty,
                distance_m=distance_m,
                time_seconds=time_diff,  # Keep actual time_diff (could be 0)
                gap_type=gap_type
            )
        )

    def _metric_distance(
        self,
        a: GPSPoint,
        b: GPSPoint,
        to_metric: Callable
    ) -> float:
        """
        Calculate distance in meters using metric projection.

        This ensures exact match with interpolation geometry.

        Args:
            a: First GPS point
            b: Second GPS point
            to_metric: Metric projection transformer

        Returns:
            Distance in meters
        """
        x0, y0 = to_metric(a.longitude, a.latitude)
        x1, y1 = to_metric(b.longitude, b.latitude)
        return math.hypot(x1 - x0, y1 - y0)

    def _determine_certainty(self, time_diff: float) -> SpeedCertainty:
        """
        Determine certainty based on time gap.

        Forensic reliability decreases with larger time gaps.

        Args:
            time_diff: Time difference in seconds

        Returns:
            SpeedCertainty enum value
        """
        if time_diff <= self.high_threshold:
            return SpeedCertainty.HIGH
        elif time_diff <= self.medium_threshold:
            return SpeedCertainty.MEDIUM
        elif time_diff <= self.max_gap_threshold:
            return SpeedCertainty.LOW
        else:
            return SpeedCertainty.UNKNOWN

    def analyze_segments(
        self,
        segments: List[GPSSegment]
    ) -> Dict[str, Any]:
        """
        Analyze segments for forensic reporting.

        Provides statistics and quality metrics for court presentation.

        Args:
            segments: List of calculated segments

        Returns:
            Dictionary with analysis results
        """
        analysis = {
            'total_segments': len(segments),
            'valid_segments': 0,
            'gap_segments': 0,
            'conflict_segments': 0,
            'stop_segments': 0,
            'certainty_distribution': {
                'high': 0,
                'medium': 0,
                'low': 0,
                'unknown': 0
            },
            'speed_statistics': {
                'min_kmh': None,
                'max_kmh': None,
                'avg_kmh': None
            },
            'distance_statistics': {
                'total_m': 0,
                'avg_segment_m': None
            },
            'time_statistics': {
                'total_s': 0,
                'avg_segment_s': None
            }
        }

        valid_speeds = []

        for segment in segments:
            # Count segment types
            if segment.is_gap:
                analysis['gap_segments'] += 1
            elif segment.is_conflict:
                analysis['conflict_segments'] += 1
            elif segment.is_stop:
                analysis['stop_segments'] += 1
            elif segment.segment_speed.is_valid():
                analysis['valid_segments'] += 1
                valid_speeds.append(segment.segment_speed.speed_kmh)

            # Count certainty levels
            certainty = segment.segment_speed.certainty.value
            analysis['certainty_distribution'][certainty] += 1

            # Accumulate distance and time
            analysis['distance_statistics']['total_m'] += segment.segment_speed.distance_m

            # Only count time for non-conflict segments
            if not segment.is_conflict:
                analysis['time_statistics']['total_s'] += segment.segment_speed.time_seconds

        # Calculate statistics
        if valid_speeds:
            analysis['speed_statistics']['min_kmh'] = min(valid_speeds)
            analysis['speed_statistics']['max_kmh'] = max(valid_speeds)
            analysis['speed_statistics']['avg_kmh'] = sum(valid_speeds) / len(valid_speeds)

        if segments:
            analysis['distance_statistics']['avg_segment_m'] = (
                analysis['distance_statistics']['total_m'] / len(segments)
            )
            analysis['time_statistics']['avg_segment_s'] = (
                analysis['time_statistics']['total_s'] / len(segments)
            )

        # Calculate forensic reliability score
        total = len(segments)
        if total > 0:
            # Weight: HIGH=1.0, MEDIUM=0.6, LOW=0.3, UNKNOWN=0
            reliability = (
                analysis['certainty_distribution']['high'] * 1.0 +
                analysis['certainty_distribution']['medium'] * 0.6 +
                analysis['certainty_distribution']['low'] * 0.3
            ) / total
            analysis['forensic_reliability_score'] = round(reliability, 3)
        else:
            analysis['forensic_reliability_score'] = 0.0

        return analysis