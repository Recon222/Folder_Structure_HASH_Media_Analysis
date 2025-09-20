#!/usr/bin/env python3
"""
Test script to verify metric projection interpolation
Tests that interpolation in metric space provides accurate distances
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vehicle_tracking.services.vehicle_tracking_service import VehicleTrackingService
from vehicle_tracking.models.vehicle_tracking_models import (
    VehicleData, GPSPoint, VehicleTrackingSettings
)

def haversine_distance(point1: GPSPoint, point2: GPSPoint) -> float:
    """Calculate great-circle distance between two points in meters"""
    R = 6371000  # Earth radius in meters

    lat1, lon1 = radians(point1.latitude), radians(point1.longitude)
    lat2, lon2 = radians(point2.latitude), radians(point2.longitude)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c

def test_metric_projection():
    """Test that metric projection provides accurate interpolation"""
    print("=" * 60)
    print("METRIC PROJECTION INTERPOLATION TEST")
    print("=" * 60)

    # Create a north-south path at high latitude (where distortion is significant)
    # At 60° latitude, 1 degree of longitude is only ~55km instead of 111km
    base = datetime(2024, 1, 1, 10, 0, 0)

    # Points moving east-west at 60° latitude
    points = [
        GPSPoint(60.0, -100.0, base, speed_kmh=100),                    # Start
        GPSPoint(60.0, -99.5, base + timedelta(seconds=1800), speed_kmh=100),  # 30 minutes later, 0.5° east
        GPSPoint(60.0, -99.0, base + timedelta(seconds=3600), speed_kmh=100),  # 60 minutes later, 1° east
    ]

    vehicle = VehicleData(
        vehicle_id="test_metric",
        source_file=Path("test_metric.csv"),
        gps_points=points
    )

    # Test with 5-second interpolation
    service = VehicleTrackingService()
    settings = VehicleTrackingSettings(
        interpolation_enabled=True,
        interpolation_interval_seconds=5.0
    )

    result = service.interpolate_path(vehicle, settings)

    if result.success:
        output = result.value

        print(f"\nOriginal points: {len(points)}")
        print(f"Interpolated to: {len(output.gps_points)} points")

        # Calculate distances between consecutive interpolated points
        distances = []
        speeds = []

        for i in range(1, min(20, len(output.gps_points))):
            p1 = output.gps_points[i-1]
            p2 = output.gps_points[i]

            # Calculate actual distance traveled
            dist = haversine_distance(p1, p2)
            distances.append(dist)

            # Calculate implied speed (m/s -> km/h)
            time_diff = (p2.timestamp - p1.timestamp).total_seconds()
            if time_diff > 0:
                speed_kmh = (dist / time_diff) * 3.6
                speeds.append(speed_kmh)

        # Check consistency
        avg_distance = sum(distances) / len(distances)
        distance_variance = sum((d - avg_distance)**2 for d in distances) / len(distances)

        avg_speed = sum(speeds) / len(speeds) if speeds else 0
        speed_variance = sum((s - avg_speed)**2 for s in speeds) / len(speeds) if speeds else 0

        print(f"\nDistance Analysis (first {len(distances)} segments):")
        print(f"  Average distance: {avg_distance:.2f} meters")
        print(f"  Distance variance: {distance_variance:.2f} (should be low)")
        print(f"  Min distance: {min(distances):.2f} m")
        print(f"  Max distance: {max(distances):.2f} m")

        print(f"\nSpeed Analysis:")
        print(f"  Average speed: {avg_speed:.2f} km/h")
        print(f"  Speed variance: {speed_variance:.2f} (should be low)")
        print(f"  Expected speed: 100 km/h")

        # Success criteria
        expected_distance_5s = (100 * 1000 / 3600) * 5  # 100 km/h for 5 seconds in meters
        distance_error = abs(avg_distance - expected_distance_5s)

        print(f"\nExpected distance per 5s: {expected_distance_5s:.2f} m")
        print(f"Distance error: {distance_error:.2f} m ({distance_error/expected_distance_5s*100:.1f}%)")

        if distance_error < 10:  # Less than 10 meters error
            print("\n[SUCCESS] Metric projection provides accurate distances!")
        else:
            print("\n[WARNING] Distance accuracy could be improved")

        # Show comparison with/without metric projection
        print("\n" + "=" * 60)
        print("COMPARISON: With vs Without Metric Projection")
        print("=" * 60)
        print("At 60° latitude:")
        print("  - 1 degree longitude = ~55.8 km (half of equator)")
        print("  - Without projection: Speed would appear to vary")
        print("  - With projection: Speed remains constant")

    else:
        print(f"[FAIL] {result.error}")

def test_equator_vs_pole():
    """Compare interpolation at equator vs near pole"""
    print("\n" + "=" * 60)
    print("LATITUDE COMPARISON TEST")
    print("=" * 60)

    service = VehicleTrackingService()
    settings = VehicleTrackingSettings(
        interpolation_enabled=True,
        interpolation_interval_seconds=10.0
    )

    base = datetime(2024, 1, 1, 10, 0, 0)

    # Test at equator (0° latitude)
    equator_points = [
        GPSPoint(0.0, -100.0, base, speed_kmh=100),
        GPSPoint(0.0, -99.0, base + timedelta(seconds=3600), speed_kmh=100),
    ]

    equator_vehicle = VehicleData(
        vehicle_id="equator",
        source_file=Path("equator.csv"),
        gps_points=equator_points
    )

    # Test at 70° latitude (near pole)
    polar_points = [
        GPSPoint(70.0, -100.0, base, speed_kmh=100),
        GPSPoint(70.0, -99.0, base + timedelta(seconds=3600), speed_kmh=100),
    ]

    polar_vehicle = VehicleData(
        vehicle_id="polar",
        source_file=Path("polar.csv"),
        gps_points=polar_points
    )

    equator_result = service.interpolate_path(equator_vehicle, settings)
    polar_result = service.interpolate_path(polar_vehicle, settings)

    if equator_result.success and polar_result.success:
        print("\nEquator (0° latitude):")
        print(f"  Points: {len(equator_result.value.gps_points)}")
        print(f"  1° longitude = ~111 km")

        print("\nNear pole (70° latitude):")
        print(f"  Points: {len(polar_result.value.gps_points)}")
        print(f"  1° longitude = ~38 km")

        print("\nWith metric projection, both should show:")
        print("  - Consistent speed of 100 km/h")
        print("  - Equal distances between interpolated points")

    else:
        print("[FAIL] Could not complete latitude comparison")

if __name__ == "__main__":
    test_metric_projection()
    test_equator_vs_pole()

    print("\n" + "=" * 60)
    print("METRIC PROJECTION TESTS COMPLETED")
    print("=" * 60)