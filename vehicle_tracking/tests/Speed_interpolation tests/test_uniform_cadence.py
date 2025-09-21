#!/usr/bin/env python3
"""
Test script to verify uniform cadence passthrough optimization
Tests that 1 Hz data passes through unchanged
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vehicle_tracking.services.vehicle_tracking_service import VehicleTrackingService
from vehicle_tracking.models.vehicle_tracking_models import (
    VehicleData, GPSPoint, VehicleTrackingSettings
)

def test_uniform_cadence_passthrough():
    """Test that 1 Hz data passes through unchanged"""

    # Create perfect 1 Hz data
    base = datetime(2024, 1, 1, 10, 0, 0)
    points = [
        GPSPoint(
            latitude=45.4215 + i * 0.0001,
            longitude=-75.6972 + i * 0.0001,
            timestamp=base + timedelta(seconds=i),
            speed_kmh=30 + i % 10
        )
        for i in range(100)  # 100 seconds of 1 Hz data
    ]

    vehicle = VehicleData(
        vehicle_id="test_1hz",
        source_file=Path("test_1hz.csv"),
        gps_points=points
    )

    # Test with 1-second interpolation
    service = VehicleTrackingService()
    settings = VehicleTrackingSettings(
        interpolation_enabled=True,
        interpolation_interval_seconds=1.0
    )

    # Perform interpolation
    result = service.interpolate_path(vehicle, settings)

    if result.success:
        output = result.value

        # Verify no extra points were added
        assert len(output.gps_points) == len(points), \
            f"Expected {len(points)} points, got {len(output.gps_points)}"

        # Verify all points are original (not interpolated)
        interpolated_count = sum(1 for p in output.gps_points if p.is_interpolated)
        assert interpolated_count == 0, \
            f"Expected 0 interpolated points, got {interpolated_count}"

        # Verify time gaps remain 1 second
        gaps = []
        for i in range(1, len(output.gps_points)):
            gap = (output.gps_points[i].timestamp - output.gps_points[i-1].timestamp).total_seconds()
            gaps.append(gap)

        assert all(abs(g - 1.0) < 0.001 for g in gaps), \
            f"Gaps not uniform: {gaps[:5]}..."

        print("[SUCCESS] 1 Hz data passed through unchanged!")
        print(f"  Input: {len(points)} points")
        print(f"  Output: {len(output.gps_points)} points")
        print(f"  Interpolated: {interpolated_count}")
        print(f"  Gap variance: {sum((g - 1.0)**2 for g in gaps) / len(gaps) if gaps else 0:.6f}")

    else:
        print(f"[FAIL] {result.error}")

def test_non_uniform_interpolation():
    """Test that non-uniform data gets interpolated"""

    # Create uneven data
    base = datetime(2024, 1, 1, 10, 0, 0)
    points = [
        GPSPoint(45.4215, -75.6972, base, speed_kmh=30),
        GPSPoint(45.4220, -75.6968, base + timedelta(seconds=7), speed_kmh=35),
        GPSPoint(45.4225, -75.6964, base + timedelta(seconds=17), speed_kmh=40),
        GPSPoint(45.4230, -75.6960, base + timedelta(seconds=22), speed_kmh=32),
        GPSPoint(45.4235, -75.6956, base + timedelta(seconds=30), speed_kmh=30),
    ]

    vehicle = VehicleData(
        vehicle_id="test_uneven",
        source_file=Path("test_uneven.csv"),
        gps_points=points
    )

    # Test with 2-second interpolation
    service = VehicleTrackingService()
    settings = VehicleTrackingSettings(
        interpolation_enabled=True,
        interpolation_interval_seconds=2.0
    )

    result = service.interpolate_path(vehicle, settings)

    if result.success:
        output = result.value
        interpolated_count = sum(1 for p in output.gps_points if p.is_interpolated)

        print("\n[SUCCESS] Non-uniform data interpolated!")
        print(f"  Input: {len(points)} points")
        print(f"  Output: {len(output.gps_points)} points")
        print(f"  Interpolated: {interpolated_count}")

        # Check grid quantization
        gaps = []
        for i in range(1, min(10, len(output.gps_points))):
            gap = (output.gps_points[i].timestamp - output.gps_points[i-1].timestamp).total_seconds()
            gaps.append(gap)

        variance = sum((g - 2.0)**2 for g in gaps) / len(gaps) if gaps else 0
        print(f"  First 10 gaps: {[f'{g:.3f}' for g in gaps]}")
        print(f"  Gap variance: {variance:.6f} (should be near 0)")

        assert variance < 0.001, "Grid quantization not working - gaps have variance"

    else:
        print(f"[FAIL] {result.error}")

if __name__ == "__main__":
    print("=" * 60)
    print("UNIFORM CADENCE PASSTHROUGH TEST")
    print("=" * 60)

    test_uniform_cadence_passthrough()
    test_non_uniform_interpolation()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)