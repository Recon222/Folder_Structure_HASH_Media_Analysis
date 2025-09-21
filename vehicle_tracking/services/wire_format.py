"""
Wire format converter for consistent data transmission in vehicle tracking.

This module ensures consistent units and types across the wire:
- Timestamps as epoch milliseconds (integers)
- Speeds in km/h (float) or null
- Distances in meters
- Monotonic indexing for UI anchor snapping
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from ..models.vehicle_tracking_models import VehicleData, GPSPoint
from ..models.forensic_models import GPSSegment


def to_wire_format(vehicle_data: VehicleData) -> Dict[str, Any]:
    """
    Convert vehicle data to consistent wire format for transmission.

    Enforces:
    - Timestamps as epoch milliseconds (integers)
    - Speeds in km/h (float) or null
    - Monotonic index for each point
    - Metadata about cadence and interval
    - Explicit unit declarations

    Args:
        vehicle_data: Vehicle data to convert

    Returns:
        Dictionary with wire format data ready for JSON serialization
    """
    points = []

    # Detect cadence type
    if len(vehicle_data.gps_points) > 1:
        intervals = []
        for i in range(1, len(vehicle_data.gps_points)):
            dt = (vehicle_data.gps_points[i].timestamp -
                  vehicle_data.gps_points[i-1].timestamp).total_seconds()
            intervals.append(dt * 1000)  # Convert to ms

        # Check if uniform
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            variance = sum((i - avg_interval)**2 for i in intervals) / len(intervals)
            cadence = "uniform" if variance < 10 else "mixed"  # 10ms variance threshold
            dt_ms = int(round(avg_interval))
        else:
            cadence = "raw"
            dt_ms = 0
    else:
        cadence = "raw"
        dt_ms = 0

    # Count point types
    observed_count = 0
    interpolated_count = 0
    gap_count = 0
    conflict_count = 0

    # Convert points with monotonic index
    for index, point in enumerate(vehicle_data.gps_points):
        # Timestamp as epoch milliseconds (integer)
        timestamp_ms = int(point.timestamp.timestamp() * 1000)

        # Determine point type
        is_observed = getattr(point, 'is_observed', True)
        is_interpolated = getattr(point, 'is_interpolated', False)
        is_gap = getattr(point, 'is_gap', False)

        # Count types
        if is_observed and not is_interpolated:
            observed_count += 1
        elif is_interpolated:
            interpolated_count += 1
        if is_gap:
            gap_count += 1

        # Check for conflicts in metadata
        if hasattr(point, 'metadata') and point.metadata:
            if point.metadata.get('conflict') == 'temporal_conflict':
                conflict_count += 1

        wire_point = {
            "index": index,  # Monotonic index for UI snapping
            "timestamp_ms": timestamp_ms,
            "latitude": point.latitude,
            "longitude": point.longitude,
            "speed_kmh": getattr(point, 'segment_speed_kmh', None),  # float or None
            "certainty": getattr(point, 'speed_certainty', None),
            "is_observed": is_observed,
            "is_interpolated": is_interpolated,
            "is_gap": is_gap,
            "segment_id": getattr(point, 'segment_id', None)
        }

        # Add metadata if present
        if hasattr(point, 'metadata') and point.metadata:
            wire_point["metadata"] = point.metadata

        # Optional fields with explicit units
        if hasattr(point, 'altitude') and point.altitude is not None:
            wire_point["altitude_m"] = point.altitude  # Ensure meters

        if hasattr(point, 'heading') and point.heading is not None:
            wire_point["heading_deg"] = point.heading  # Ensure degrees

        # Add anomaly flag if present
        if hasattr(point, 'is_anomaly') and point.is_anomaly:
            wire_point["is_anomaly"] = True

        points.append(wire_point)

    # Build metadata with explicit unit declarations
    meta = {
        "dt_ms": dt_ms,  # Average interval in milliseconds
        "cadence": cadence,  # "uniform", "mixed", or "raw"
        "total_points": len(points),
        "observed_points": observed_count,
        "interpolated_points": interpolated_count,
        "gap_points": gap_count,
        "conflict_points": conflict_count,
        "has_segment_speeds": getattr(vehicle_data, 'has_segment_speeds', False),
        "unit_speed": "km/h",  # Explicit unit declaration
        "unit_distance": "meters",
        "unit_timestamp": "epoch_ms",
        "unit_altitude": "meters",
        "unit_heading": "degrees"
    }

    # Add forensic metadata if available
    if hasattr(vehicle_data, 'segments') and vehicle_data.segments:
        meta["segment_count"] = len(vehicle_data.segments)

        # Count segment types
        segment_types = {
            'normal': 0,
            'gap': 0,
            'conflict': 0,
            'stop': 0
        }

        for segment in vehicle_data.segments:
            gap_type = segment.segment_speed.gap_type
            if gap_type == 'temporal_conflict':
                segment_types['conflict'] += 1
            elif gap_type == 'gap':
                segment_types['gap'] += 1
            elif gap_type in ['stop', 'stop/coalesced']:
                segment_types['stop'] += 1
            else:
                segment_types['normal'] += 1

        meta["segment_types"] = segment_types

    # Add speed statistics if available
    if hasattr(vehicle_data, 'average_speed_kmh') and vehicle_data.average_speed_kmh:
        meta["speed_stats"] = {
            "avg_kmh": vehicle_data.average_speed_kmh,
            "max_kmh": getattr(vehicle_data, 'max_speed_kmh', None),
            "min_kmh": getattr(vehicle_data, 'min_speed_kmh', None)
        }

    return {
        "vehicle_id": vehicle_data.vehicle_id,
        "points": points,
        "meta": meta
    }


def from_wire_format(payload: Dict[str, Any]) -> VehicleData:
    """
    Parse wire format back to VehicleData.

    Validates units and types to ensure data integrity.

    Args:
        payload: Wire format dictionary

    Returns:
        VehicleData object

    Raises:
        ValueError: If wire format validation fails
    """
    # Validate required fields
    if "vehicle_id" not in payload:
        raise ValueError("Missing required field: vehicle_id")
    if "points" not in payload:
        raise ValueError("Missing required field: points")
    if "meta" not in payload:
        raise ValueError("Missing required field: meta")

    # Validate unit declarations
    meta = payload["meta"]
    if meta.get("unit_timestamp") != "epoch_ms":
        raise ValueError(f"Unsupported timestamp unit: {meta.get('unit_timestamp')}")
    if meta.get("unit_speed") != "km/h":
        raise ValueError(f"Unsupported speed unit: {meta.get('unit_speed')}")

    points = []

    for i, wire_point in enumerate(payload["points"]):
        # Validate timestamp is integer milliseconds
        if "timestamp_ms" not in wire_point:
            raise ValueError(f"Point {i}: missing timestamp_ms")

        if not isinstance(wire_point["timestamp_ms"], int):
            raise ValueError(
                f"Point {i}: timestamp must be integer ms, "
                f"got {type(wire_point['timestamp_ms'])}"
            )

        # Validate monotonic index
        if wire_point.get("index", i) != i:
            logging.warning(
                f"Point {i}: index mismatch, expected {i} "
                f"got {wire_point.get('index')}"
            )

        # Convert timestamp back to datetime
        timestamp = datetime.fromtimestamp(wire_point["timestamp_ms"] / 1000.0)

        # Create GPS point
        point = GPSPoint(
            latitude=wire_point["latitude"],
            longitude=wire_point["longitude"],
            timestamp=timestamp
        )

        # Add forensic fields
        if "segment_speed_kmh" in wire_point:
            point.segment_speed_kmh = wire_point["segment_speed_kmh"]  # Already in km/h
        if "speed_certainty" in wire_point:
            point.speed_certainty = wire_point["speed_certainty"]
        if "segment_id" in wire_point:
            point.segment_id = wire_point["segment_id"]

        # Add observation flags
        point.is_observed = wire_point.get("is_observed", True)
        point.is_interpolated = wire_point.get("is_interpolated", False)
        point.is_gap = wire_point.get("is_gap", False)
        point.is_anomaly = wire_point.get("is_anomaly", False)

        # Add optional fields with units
        if "altitude_m" in wire_point:
            point.altitude = wire_point["altitude_m"]  # Already in meters
        if "heading_deg" in wire_point:
            point.heading = wire_point["heading_deg"]  # Already in degrees

        # Add metadata
        if "metadata" in wire_point:
            point.metadata = wire_point["metadata"]

        points.append(point)

    # Create vehicle data
    vehicle_data = VehicleData(
        vehicle_id=payload["vehicle_id"],
        source_file=None,  # Not transmitted over wire
        gps_points=points
    )

    # Add forensic metadata
    vehicle_data.has_segment_speeds = meta.get("has_segment_speeds", False)

    # Add speed statistics if present
    if "speed_stats" in meta:
        vehicle_data.average_speed_kmh = meta["speed_stats"].get("avg_kmh")
        vehicle_data.max_speed_kmh = meta["speed_stats"].get("max_kmh")
        vehicle_data.min_speed_kmh = meta["speed_stats"].get("min_kmh")

    return vehicle_data


def validate_wire_format(payload: Dict[str, Any]) -> List[str]:
    """
    Validate wire format for consistency and correctness.

    Args:
        payload: Wire format dictionary to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check required top-level fields
    if "vehicle_id" not in payload:
        errors.append("Missing required field: vehicle_id")
    if "points" not in payload:
        errors.append("Missing required field: points")
    if "meta" not in payload:
        errors.append("Missing required field: meta")

    if not errors:  # Only continue if basic structure is valid
        # Validate metadata
        meta = payload["meta"]

        # Check unit declarations
        if meta.get("unit_timestamp") != "epoch_ms":
            errors.append(f"Invalid timestamp unit: {meta.get('unit_timestamp')}")
        if meta.get("unit_speed") != "km/h":
            errors.append(f"Invalid speed unit: {meta.get('unit_speed')}")
        if meta.get("unit_distance") != "meters":
            errors.append(f"Invalid distance unit: {meta.get('unit_distance')}")

        # Check cadence
        if "cadence" in meta:
            if meta["cadence"] not in ["uniform", "mixed", "raw"]:
                errors.append(f"Invalid cadence: {meta['cadence']}")

        # Validate points
        points = payload["points"]
        if not isinstance(points, list):
            errors.append("Points must be a list")
        else:
            for i, point in enumerate(points):
                # Check required fields
                if "timestamp_ms" not in point:
                    errors.append(f"Point {i}: missing timestamp_ms")
                elif not isinstance(point["timestamp_ms"], int):
                    errors.append(f"Point {i}: timestamp_ms must be integer")

                if "latitude" not in point:
                    errors.append(f"Point {i}: missing latitude")
                if "longitude" not in point:
                    errors.append(f"Point {i}: missing longitude")

                # Check index is monotonic
                if "index" in point and point["index"] != i:
                    errors.append(f"Point {i}: non-monotonic index {point['index']}")

                # Validate speed if present
                if "speed_kmh" in point and point["speed_kmh"] is not None:
                    if not isinstance(point["speed_kmh"], (int, float)):
                        errors.append(f"Point {i}: speed_kmh must be number or null")
                    elif point["speed_kmh"] < 0:
                        errors.append(f"Point {i}: negative speed {point['speed_kmh']}")
                    elif point["speed_kmh"] > 300:
                        errors.append(f"Point {i}: excessive speed {point['speed_kmh']} km/h")

                # Validate certainty if present
                if "certainty" in point and point["certainty"] is not None:
                    if point["certainty"] not in ["high", "medium", "low", "unknown"]:
                        errors.append(f"Point {i}: invalid certainty {point['certainty']}")

    return errors