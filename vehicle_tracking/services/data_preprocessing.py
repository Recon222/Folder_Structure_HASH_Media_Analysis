"""
Data preprocessing for forensic vehicle tracking.

This module handles preprocessing of GPS data before forensic analysis,
including coalescing same-location duplicates and data cleaning.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from ..models.vehicle_tracking_models import GPSPoint


def coalesce_same_location_duplicates(points: List[GPSPoint]) -> List[GPSPoint]:
    """
    Coalesce identical fixes at the same time/place into single anchors.

    Maintains count in metadata for forensic auditing.

    Purpose:
        Treat repeated same-location samples as confirmed stops,
        not data errors. This preserves forensic integrity by
        acknowledging that multiple readings at the same location
        confirm the vehicle was stationary.

    Args:
        points: List of GPS points to process

    Returns:
        List of GPS points with duplicates coalesced and metadata updated

    Example:
        If we have 3 identical points at time T:
        - Input: [A(T), A(T), A(T), B(T+5)]
        - Output: [A(T, metadata={'coalesced_count': 3}), B(T+5)]
    """
    if not points:
        return points

    coalesced = []
    i = 0

    while i < len(points):
        current = points[i]
        dup_count = 1
        j = i + 1

        # Find all duplicates at same time and location
        while (j < len(points) and
               points[j].timestamp == current.timestamp and
               points[j].latitude == current.latitude and
               points[j].longitude == current.longitude):
            dup_count += 1
            j += 1

        # Create coalesced point with metadata
        if dup_count > 1:
            # Preserve original point but add metadata
            current.metadata = current.metadata or {}
            current.metadata['coalesced_count'] = dup_count
            current.metadata['gap_type'] = 'stop/coalesced'
            current.is_observed = True

            # Log the coalescing for audit trail
            current.metadata['coalesce_note'] = (
                f"Coalesced {dup_count} identical samples at "
                f"{current.timestamp.isoformat()}"
            )

        coalesced.append(current)
        i = j

    return coalesced


def detect_and_mark_anomalies(
    points: List[GPSPoint],
    max_speed_kmh: float = 250.0,
    max_acceleration_g: float = 1.5
) -> List[GPSPoint]:
    """
    Detect and mark anomalous GPS points for forensic analysis.

    Anomalies include:
    - Impossible speeds (teleportation)
    - Extreme accelerations
    - GPS multipath errors

    Args:
        points: List of GPS points to analyze
        max_speed_kmh: Maximum believable speed in km/h
        max_acceleration_g: Maximum acceleration in g-forces

    Returns:
        List of GPS points with anomaly flags added

    Note:
        Points are marked but NOT removed - forensic principle
        is to preserve all data with appropriate annotations.
    """
    if len(points) < 2:
        return points

    # Constants
    EARTH_RADIUS_KM = 6371.0
    G_FORCE_MS2 = 9.81

    for i in range(len(points) - 1):
        current = points[i]
        next_point = points[i + 1]

        # Calculate time difference
        time_diff = (next_point.timestamp - current.timestamp).total_seconds()

        if time_diff <= 0:
            # This is a temporal conflict - will be handled elsewhere
            continue

        # Calculate distance (simple haversine for anomaly detection)
        from math import radians, sin, cos, atan2, sqrt

        lat1, lon1 = radians(current.latitude), radians(current.longitude)
        lat2, lon2 = radians(next_point.latitude), radians(next_point.longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance_km = EARTH_RADIUS_KM * c

        # Calculate speed
        speed_kmh = (distance_km / time_diff) * 3600 if time_diff > 0 else 0

        # Check for speed anomaly
        if speed_kmh > max_speed_kmh:
            current.is_anomaly = True
            next_point.is_anomaly = True

            # Add detailed metadata
            current.metadata = current.metadata or {}
            current.metadata['anomaly_type'] = 'excessive_speed'
            current.metadata['calculated_speed_kmh'] = speed_kmh
            current.metadata['threshold_kmh'] = max_speed_kmh
            current.metadata['severity'] = 'high' if speed_kmh > max_speed_kmh * 1.5 else 'medium'

            next_point.metadata = next_point.metadata or {}
            next_point.metadata['anomaly_type'] = 'excessive_speed'
            next_point.metadata['calculated_speed_kmh'] = speed_kmh

        # Check for acceleration anomaly (if we have previous speed)
        if i > 0 and hasattr(current, 'calculated_speed_kmh') and current.calculated_speed_kmh:
            speed_change_ms = ((speed_kmh - current.calculated_speed_kmh) / 3.6)
            acceleration_ms2 = abs(speed_change_ms / time_diff) if time_diff > 0 else 0
            acceleration_g = acceleration_ms2 / G_FORCE_MS2

            if acceleration_g > max_acceleration_g:
                current.metadata = current.metadata or {}
                current.metadata['acceleration_anomaly'] = True
                current.metadata['acceleration_g'] = acceleration_g
                current.metadata['max_acceleration_g'] = max_acceleration_g

        # Store calculated speed for next iteration
        next_point.calculated_speed_kmh = speed_kmh

    return points


def clean_and_validate_gps_data(
    points: List[GPSPoint],
    min_latitude: float = -90.0,
    max_latitude: float = 90.0,
    min_longitude: float = -180.0,
    max_longitude: float = 180.0
) -> List[GPSPoint]:
    """
    Clean and validate GPS data for forensic processing.

    Performs basic validation but preserves all data with flags.

    Args:
        points: List of GPS points to validate
        min_latitude: Minimum valid latitude
        max_latitude: Maximum valid latitude
        min_longitude: Minimum valid longitude
        max_longitude: Maximum valid longitude

    Returns:
        List of validated GPS points with invalid points marked

    Note:
        Invalid points are MARKED, not removed, to maintain
        forensic chain of custody.
    """
    validated = []

    for point in points:
        is_valid = True
        validation_errors = []

        # Check latitude bounds
        if not (min_latitude <= point.latitude <= max_latitude):
            is_valid = False
            validation_errors.append(f"Invalid latitude: {point.latitude}")

        # Check longitude bounds
        if not (min_longitude <= point.longitude <= max_longitude):
            is_valid = False
            validation_errors.append(f"Invalid longitude: {point.longitude}")

        # Check for null island (0,0) - common GPS error
        if point.latitude == 0.0 and point.longitude == 0.0:
            is_valid = False
            validation_errors.append("Null Island (0,0) - likely GPS error")

        # Mark invalid points but keep them
        if not is_valid:
            point.metadata = point.metadata or {}
            point.metadata['validation_failed'] = True
            point.metadata['validation_errors'] = validation_errors
            point.is_anomaly = True

        validated.append(point)

    return validated


def sort_and_deduplicate_points(
    points: List[GPSPoint],
    preserve_metadata: bool = True
) -> List[GPSPoint]:
    """
    Sort points by timestamp and remove exact duplicates.

    Args:
        points: List of GPS points to process
        preserve_metadata: If True, preserve metadata from duplicates

    Returns:
        Sorted list with exact duplicates removed

    Note:
        This is different from coalescing - this removes EXACT
        duplicates (same time, location, and all attributes).
        Use coalescing for same-location duplicates at same time.
    """
    if not points:
        return points

    # Sort by timestamp
    sorted_points = sorted(points, key=lambda p: p.timestamp)

    # Remove exact duplicates
    deduplicated = []
    seen = set()

    for point in sorted_points:
        # Create a unique key for this point
        key = (
            point.timestamp,
            point.latitude,
            point.longitude,
            point.speed_kmh,
            point.altitude,
            point.heading
        )

        if key not in seen:
            seen.add(key)
            deduplicated.append(point)
        elif preserve_metadata and point.metadata:
            # If duplicate has metadata, merge it
            existing_idx = len(deduplicated) - 1
            if existing_idx >= 0 and deduplicated[existing_idx].timestamp == point.timestamp:
                existing = deduplicated[existing_idx]
                existing.metadata = existing.metadata or {}
                existing.metadata.update(point.metadata or {})

    return deduplicated


def prepare_for_forensic_analysis(
    points: List[GPSPoint],
    settings: Optional[Dict[str, Any]] = None
) -> List[GPSPoint]:
    """
    Complete preprocessing pipeline for forensic GPS analysis.

    Applies all preprocessing steps in the correct order:
    1. Clean and validate
    2. Sort and deduplicate
    3. Coalesce same-location duplicates
    4. Detect and mark anomalies

    Args:
        points: Raw GPS points
        settings: Optional preprocessing settings

    Returns:
        Preprocessed GPS points ready for forensic analysis
    """
    if not points:
        return points

    settings = settings or {}

    # Step 1: Clean and validate
    points = clean_and_validate_gps_data(points)

    # Step 2: Sort and remove exact duplicates
    points = sort_and_deduplicate_points(points)

    # Step 3: Coalesce same-location duplicates
    points = coalesce_same_location_duplicates(points)

    # Step 4: Detect and mark anomalies
    max_speed = settings.get('max_speed_kmh', 250.0)
    max_accel = settings.get('max_acceleration_g', 1.5)
    points = detect_and_mark_anomalies(points, max_speed, max_accel)

    return points