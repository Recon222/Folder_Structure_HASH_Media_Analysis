#!/usr/bin/env python3
"""
Test script to verify interpolation with real GPS data
Tests speed calculations and interpolation accuracy
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vehicle_tracking.services.vehicle_tracking_service import VehicleTrackingService
from vehicle_tracking.models.vehicle_tracking_models import VehicleTrackingSettings

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance between two points in meters"""
    R = 6371000  # Earth radius in meters

    lat1, lon1 = radians(lat1), radians(lon1)
    lat2, lon2 = radians(lat2), radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c

def analyze_real_data():
    """Analyze the real Speed test.csv file"""
    print("=" * 60)
    print("REAL GPS DATA SPEED ANALYSIS")
    print("=" * 60)

    # Load the CSV file
    service = VehicleTrackingService()
    csv_path = Path("vehicle_tracking/realistic_reverse_route_simulation3-no speedSpeed.csv")

    if not csv_path.exists():
        print(f"[ERROR] File not found: {csv_path}")
        return

    # Parse with minimal settings first to see raw data
    settings = VehicleTrackingSettings(
        interpolation_enabled=False,  # Disable interpolation initially
        interpolation_interval_seconds=1.0
    )

    result = service.parse_csv_file(csv_path, settings)

    if not result.success:
        print(f"[ERROR] Failed to parse CSV: {result.error}")
        return

    vehicle_data = result.value
    points = vehicle_data.gps_points

    # Filter out invalid points (empty rows at the end)
    valid_points = [p for p in points if p.latitude != 0 and p.longitude != 0]

    print(f"\nOriginal Data:")
    print(f"  Total rows: {len(points)}")
    print(f"  Valid GPS points: {len(valid_points)}")

    if len(valid_points) < 2:
        print("[ERROR] Not enough valid GPS points")
        return

    # Analyze time spacing in original data
    time_gaps = []
    for i in range(1, len(valid_points)):
        gap = (valid_points[i].timestamp - valid_points[i-1].timestamp).total_seconds()
        time_gaps.append(gap)

    if time_gaps:
        avg_gap = sum(time_gaps) / len(time_gaps)
        min_gap = min(time_gaps)
        max_gap = max(time_gaps)
        print(f"\nTime spacing in original data:")
        print(f"  Average: {avg_gap:.2f}s")
        print(f"  Min: {min_gap:.2f}s")
        print(f"  Max: {max_gap:.2f}s")

    # Calculate speeds from raw data
    print(f"\nSpeed Analysis (Raw Data):")
    speeds = []
    for i in range(1, min(20, len(valid_points))):
        p1 = valid_points[i-1]
        p2 = valid_points[i]

        dist = haversine_distance(p1.latitude, p1.longitude, p2.latitude, p2.longitude)
        time_diff = (p2.timestamp - p1.timestamp).total_seconds()

        if time_diff > 0:
            speed_kmh = (dist / time_diff) * 3.6
            speeds.append(speed_kmh)
            if i <= 5:  # Show first few
                print(f"  Point {i-1} -> {i}: {dist:.2f}m in {time_diff:.1f}s = {speed_kmh:.1f} km/h")

    if speeds:
        avg_speed = sum(speeds) / len(speeds)
        print(f"\n  Average speed: {avg_speed:.1f} km/h")
        print(f"  Min speed: {min(speeds):.1f} km/h")
        print(f"  Max speed: {max(speeds):.1f} km/h")

    # Now test with interpolation
    print("\n" + "=" * 60)
    print("TESTING WITH INTERPOLATION")
    print("=" * 60)

    # Enable interpolation
    settings.interpolation_enabled = True
    settings.interpolation_interval_seconds = 1.0  # 1 second intervals

    # Re-parse and interpolate
    interpolated_result = service.interpolate_path(vehicle_data, settings)

    if not interpolated_result.success:
        print(f"[ERROR] Interpolation failed: {interpolated_result.error}")
        return

    interpolated_data = interpolated_result.value
    interp_points = interpolated_data.gps_points

    print(f"\nInterpolation Results:")
    print(f"  Original points: {len(valid_points)}")
    print(f"  Interpolated points: {len(interp_points)}")

    # Check time spacing after interpolation
    interp_gaps = []
    for i in range(1, min(20, len(interp_points))):
        gap = (interp_points[i].timestamp - interp_points[i-1].timestamp).total_seconds()
        interp_gaps.append(gap)

    if interp_gaps:
        avg_interp_gap = sum(interp_gaps) / len(interp_gaps)
        gap_variance = sum((g - avg_interp_gap)**2 for g in interp_gaps) / len(interp_gaps)
        print(f"\nTime spacing after interpolation:")
        print(f"  Average: {avg_interp_gap:.3f}s")
        print(f"  Variance: {gap_variance:.6f} (should be ~0)")
        print(f"  All gaps equal to 1s: {all(abs(g - 1.0) < 0.001 for g in interp_gaps)}")

    # Calculate speeds from interpolated data
    interp_speeds = []
    for i in range(1, min(20, len(interp_points))):
        p1 = interp_points[i-1]
        p2 = interp_points[i]

        dist = haversine_distance(p1.latitude, p1.longitude, p2.latitude, p2.longitude)
        time_diff = (p2.timestamp - p1.timestamp).total_seconds()

        if time_diff > 0:
            speed_kmh = (dist / time_diff) * 3.6
            interp_speeds.append(speed_kmh)

    if interp_speeds:
        avg_interp_speed = sum(interp_speeds) / len(interp_speeds)
        print(f"\nSpeed Analysis (Interpolated):")
        print(f"  Average speed: {avg_interp_speed:.1f} km/h")
        print(f"  Min speed: {min(interp_speeds):.1f} km/h")
        print(f"  Max speed: {max(interp_speeds):.1f} km/h")
        print(f"  Speed variance: {sum((s - avg_interp_speed)**2 for s in interp_speeds) / len(interp_speeds):.2f}")

    # Check for uniform cadence passthrough
    print(f"\n" + "=" * 60)
    print("UNIFORM CADENCE CHECK")
    print("=" * 60)

    # Check if original data was already uniform
    is_uniform = all(abs(g - 1.0) < 0.1 for g in time_gaps) if time_gaps else False
    print(f"Original data uniform (1Hz): {is_uniform}")

    if is_uniform and len(interp_points) == len(valid_points):
        print("[SUCCESS] Uniform cadence passthrough working - no unnecessary interpolation!")
    elif not is_uniform and len(interp_points) > len(valid_points):
        print("[SUCCESS] Non-uniform data properly interpolated to 1Hz!")

    # Summary
    print(f"\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"[OK] Parsed {len(valid_points)} valid GPS points")
    print(f"[OK] Detected average speed: {avg_speed:.1f} km/h" if speeds else "[FAIL] Could not calculate speed")
    print(f"[OK] Interpolation created uniform 1Hz data" if interp_gaps else "[FAIL] No interpolation performed")

if __name__ == "__main__":
    analyze_real_data()