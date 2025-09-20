#!/usr/bin/env python3
"""
Test script to verify interpolation timestamp fix
Tests that interpolated points are evenly spaced in time
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vehicle_tracking.services.vehicle_tracking_service import VehicleTrackingService
from vehicle_tracking.models.vehicle_tracking_models import (
    VehicleData, GPSPoint, VehicleTrackingSettings, InterpolationMethod
)

def create_test_data():
    """Create test GPS data with uneven time gaps"""
    points = [
        # 7-second gap
        GPSPoint(45.4215, -75.6972, datetime(2024, 1, 1, 10, 0, 0), speed_kmh=30),
        GPSPoint(45.4220, -75.6968, datetime(2024, 1, 1, 10, 0, 7), speed_kmh=35),

        # 10-second gap
        GPSPoint(45.4225, -75.6964, datetime(2024, 1, 1, 10, 0, 17), speed_kmh=40),

        # 5-second gap
        GPSPoint(45.4230, -75.6960, datetime(2024, 1, 1, 10, 0, 22), speed_kmh=32),

        # Test heading wraparound - from 359° to 1° should go forward through 0
        GPSPoint(45.4235, -75.6956, datetime(2024, 1, 1, 10, 0, 30), speed_kmh=30, heading=359),
        GPSPoint(45.4240, -75.6952, datetime(2024, 1, 1, 10, 0, 40), speed_kmh=28, heading=1),
    ]

    vehicle = VehicleData(
        vehicle_id="test_vehicle",
        source_file=Path("test.csv"),
        gps_points=points
    )

    return vehicle

def analyze_time_gaps(points):
    """Analyze time gaps between consecutive points"""
    gaps = []
    for i in range(1, len(points)):
        gap = (points[i].timestamp - points[i-1].timestamp).total_seconds()
        gaps.append(gap)
    return gaps

def test_interpolation():
    """Test the interpolation with various settings"""
    print("=" * 60)
    print("INTERPOLATION TIMESTAMP FIX TEST")
    print("=" * 60)

    # Create service and test data
    service = VehicleTrackingService()
    vehicle_data = create_test_data()

    # Test with 2-second interpolation
    settings = VehicleTrackingSettings(
        interpolation_enabled=True,
        interpolation_method=InterpolationMethod.LINEAR,
        interpolation_interval_seconds=2.0
    )

    print(f"\nOriginal points: {len(vehicle_data.gps_points)}")
    print("Original time gaps (seconds):", analyze_time_gaps(vehicle_data.gps_points))

    # Perform interpolation
    result = service.interpolate_path(vehicle_data, settings)

    if result.success:
        interpolated_data = result.value
        print(f"\nInterpolated points: {len(interpolated_data.gps_points)}")

        # Analyze time gaps
        gaps = analyze_time_gaps(interpolated_data.gps_points)
        print(f"Time gaps after interpolation: {len(gaps)} gaps")

        # Check if gaps are even
        print("\nDetailed gap analysis:")
        for i, gap in enumerate(gaps):
            status = "PASS" if abs(gap - gaps[0]) < 0.1 else "FAIL"
            print(f"  Gap {i+1}: {gap:.2f}s [{status}]")

        # Calculate variance to measure evenness
        avg_gap = sum(gaps) / len(gaps)
        variance = sum((g - avg_gap) ** 2 for g in gaps) / len(gaps)

        print(f"\nAverage gap: {avg_gap:.2f}s")
        print(f"Gap variance: {variance:.4f} (lower is better, 0 = perfectly even)")

        # Test heading interpolation
        print("\n" + "=" * 60)
        print("HEADING INTERPOLATION TEST")
        print("=" * 60)

        # Find points with heading
        heading_points = [p for p in interpolated_data.gps_points if p.heading is not None]
        if heading_points:
            print(f"\nPoints with heading: {len(heading_points)}")
            print("\nHeading progression (should smoothly go from 359° to 1° through 0°):")

            # Show last few points before and first few after the wraparound
            wraparound_start = None
            for i, p in enumerate(heading_points):
                if i > 0 and abs(heading_points[i-1].heading - 359) < 5:
                    wraparound_start = max(0, i - 3)
                    break

            if wraparound_start is not None:
                for i in range(wraparound_start, min(wraparound_start + 8, len(heading_points))):
                    p = heading_points[i]
                    marker = " <-- Wraparound here" if i > wraparound_start and heading_points[i-1].heading > 300 and p.heading < 60 else ""
                    interp_marker = " (interpolated)" if p.is_interpolated else " (original)"
                    print(f"  {p.timestamp.strftime('%H:%M:%S')}: {p.heading:.1f}°{interp_marker}{marker}")

        # Check if interpolation is working
        interpolated_count = sum(1 for p in interpolated_data.gps_points if p.is_interpolated)
        original_count = len(interpolated_data.gps_points) - interpolated_count

        print(f"\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Original points: {original_count}")
        print(f"Interpolated points: {interpolated_count}")
        print(f"Total points: {len(interpolated_data.gps_points)}")

        # Success criteria
        if variance < 0.01:  # Very low variance means even gaps
            print("\n[SUCCESS] Time gaps are evenly distributed!")
        else:
            print("\n[WARNING] Time gaps show some unevenness")

    else:
        print(f"\n[ERROR] Interpolation failed: {result.error}")

if __name__ == "__main__":
    test_interpolation()