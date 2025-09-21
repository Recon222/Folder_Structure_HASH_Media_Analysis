#!/usr/bin/env python3
"""
Compare calculated speeds with provided reference speeds
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

def compare_speeds():
    """Compare calculated speeds with reference speeds"""

    # Reference speeds from the user (in order)
    reference_speeds = [
        34.4, 31.7, 6.4, 24.9, 24.5, 16.4, 14.3, 9.2, 7.7, 8.0,
        9.2, 11.7, 16.3, 18.5, 18.2, 16.9, 15.9, 15.4, 11.7, 6.9,
        6.4, 6.1, 8.0, 13.4, 16.3, 21.6, 24.1, 28.6, 28.6, 34.3,
        31.2, 35.9, 35.9, 2.4, 33.3, 33.3, 29.8, 25.1, 22.4, 18.2,
        13.4, 10.6, 5.5, 2.3, 5.0, 9.0, 15.4, 17.2, 22.4, 26.7,
        29.6, 32.2, 36.9, 36.7, 34.9, 36.2, 30.6, 27.8, 24.5, 23.5,
        16.9, 14.3, 14.3, 13.4, 5.6, 5.0, 9.0, 8.0, 11.6, 17.2,
        19.8, 22.4, 22.4, 25.1, 23.5, 25.1, 24.9, 23.3, 25.1, 24.5,
        25.6, 23.5, 18.8, 11.6, 8.2, 5.5, 8.0, 8.0, 2.7, 2.7,
        2.7, 1.6, 5.1, 1.1, 1.6, 21.7, 17.9, 10.5, 13.5, 14.8,
        15.9, 25.6, 24.9, 27.7, 30.4, 34.9, 34.1, 37.5, 36.9, 33.8,
        35.2, 28.8, 22.7, 22.7, 18.8, 15.4, 11.4, 7.4, 3.2, 6.4,
        12.7, 16.3, 20.0, 26.7, 31.4, 35.2, 2.3, 38.0, 36.2, 34.3,
        31.4, 25.4, 20.1, 16.1, 15.3, 14.8, 11.4, 10.1, 8.7, 10.1,
        8.9, 13.8, 16.3, 16.6, 20.3, 16.6, 21.1, 21.7, 23.0, 27.2,
        25.9, 27.8, 26.7, 25.1, 27.7, 28.6, 31.5, 6.0, 30.4, 33.8,
        31.5, 30.6, 29.1, 31.2, 36.0, 33.8, 37.8, 27.7, 17.5, 16.3,
        24.0, 29.0, 29.8, 33.3, 36.2, 38.8, 40.7, 43.8, 43.0, 43.5,
        41.8, 43.5, 40.9, 42.3, 37.0, 37.2, 30.9, 22.7, 30.7, 16.4,
        11.7, 5.1
    ]

    print("=" * 80)
    print("POINT-BY-POINT SPEED COMPARISON")
    print("=" * 80)

    # Load the CSV file
    service = VehicleTrackingService()
    csv_path = Path("vehicle_tracking/Speed test.csv")

    if not csv_path.exists():
        print(f"[ERROR] File not found: {csv_path}")
        return

    # Parse without interpolation to get raw data
    settings = VehicleTrackingSettings(
        interpolation_enabled=False,
        interpolation_interval_seconds=1.0
    )

    result = service.parse_csv_file(csv_path, settings)

    if not result.success:
        print(f"[ERROR] Failed to parse CSV: {result.error}")
        return

    vehicle_data = result.value
    points = vehicle_data.gps_points

    # Filter out invalid points (empty rows)
    valid_points = [p for p in points if p.latitude != 0 and p.longitude != 0]

    print(f"\nData Summary:")
    print(f"  Valid GPS points: {len(valid_points)}")
    print(f"  Reference speeds: {len(reference_speeds)}")

    # Calculate speeds between consecutive points
    calculated_speeds = []
    for i in range(1, len(valid_points)):
        p1 = valid_points[i-1]
        p2 = valid_points[i]

        dist = haversine_distance(p1.latitude, p1.longitude, p2.latitude, p2.longitude)
        time_diff = (p2.timestamp - p1.timestamp).total_seconds()

        if time_diff > 0:
            speed_kmh = (dist / time_diff) * 3.6
        else:
            # Handle duplicate timestamps (0 time difference)
            speed_kmh = 0.0  # or could use previous speed

        calculated_speeds.append(speed_kmh)

    # Compare speeds
    print("\n" + "=" * 80)
    print(f"{'Index':<6} {'Time':<20} {'Calc (km/h)':<12} {'Ref (km/h)':<12} {'Diff':<12} {'Status':<10}")
    print("-" * 80)

    matches = 0
    total_error = 0
    large_errors = []

    for i in range(min(len(calculated_speeds), len(reference_speeds))):
        calc_speed = calculated_speeds[i]
        ref_speed = reference_speeds[i]
        diff = calc_speed - ref_speed

        # Consider it a match if within 1 km/h
        is_match = abs(diff) < 1.0
        if is_match:
            matches += 1
            status = "MATCH"
        else:
            status = "DIFFER"

        total_error += abs(diff)

        # Track large errors
        if abs(diff) > 5.0:
            large_errors.append((i, calc_speed, ref_speed, diff))

        # Print first 20 and any with large errors
        if i < 20 or abs(diff) > 5.0:
            timestamp = valid_points[i+1].timestamp.strftime("%H:%M:%S")
            print(f"{i+1:<6} {timestamp:<20} {calc_speed:>11.1f} {ref_speed:>11.1f} {diff:>11.1f} {status:<10}")

    # Print summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)

    comparison_count = min(len(calculated_speeds), len(reference_speeds))
    avg_error = total_error / comparison_count if comparison_count > 0 else 0

    print(f"\nTotal points compared: {comparison_count}")
    print(f"Exact matches (within 1 km/h): {matches} ({matches/comparison_count*100:.1f}%)")
    print(f"Average absolute error: {avg_error:.2f} km/h")

    if calculated_speeds:
        print(f"\nCalculated speeds:")
        print(f"  Min: {min(calculated_speeds):.1f} km/h")
        print(f"  Max: {max(calculated_speeds):.1f} km/h")
        print(f"  Average: {sum(calculated_speeds)/len(calculated_speeds):.1f} km/h")

    print(f"\nReference speeds:")
    print(f"  Min: {min(reference_speeds):.1f} km/h")
    print(f"  Max: {max(reference_speeds):.1f} km/h")
    print(f"  Average: {sum(reference_speeds)/len(reference_speeds):.1f} km/h")

    if large_errors:
        print(f"\n" + "=" * 80)
        print(f"LARGE DISCREPANCIES (> 5 km/h difference)")
        print("-" * 80)
        for idx, calc, ref, diff in large_errors[:10]:  # Show first 10
            timestamp = valid_points[idx+1].timestamp.strftime("%H:%M:%S")
            print(f"Point {idx+1} at {timestamp}: Calc={calc:.1f}, Ref={ref:.1f}, Diff={diff:.1f}")

    # Check for pattern in errors
    print(f"\n" + "=" * 80)
    print("ERROR PATTERN ANALYSIS")
    print("-" * 80)

    # Check if there's a systematic offset
    if calculated_speeds and reference_speeds:
        errors = [calculated_speeds[i] - reference_speeds[i]
                 for i in range(min(len(calculated_speeds), len(reference_speeds)))]
        avg_signed_error = sum(errors) / len(errors)

        if abs(avg_signed_error) > 1.0:
            print(f"Systematic offset detected: {avg_signed_error:+.2f} km/h")
            print("Calculated speeds are systematically",
                  "HIGHER" if avg_signed_error > 0 else "LOWER",
                  "than reference")
        else:
            print("No significant systematic offset detected")

if __name__ == "__main__":
    compare_speeds()