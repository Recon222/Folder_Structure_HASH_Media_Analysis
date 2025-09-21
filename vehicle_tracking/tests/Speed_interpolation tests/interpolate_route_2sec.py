#!/usr/bin/env python3
"""
Interpolate route data to 2-second intervals using the same method as the vehicle tracking app
This creates ground truth data with known speeds for testing
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import csv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vehicle_tracking.services.vehicle_tracking_service import VehicleTrackingService
from vehicle_tracking.models.vehicle_tracking_models import (
    VehicleData, GPSPoint, VehicleTrackingSettings
)

def interpolate_route():
    """Interpolate the route to 2-second intervals"""

    print("=" * 80)
    print("ROUTE INTERPOLATION TO 2-SECOND INTERVALS")
    print("=" * 80)

    # Load the original route
    service = VehicleTrackingService()
    input_path = Path("vehicle_tracking/belsize_to_bayview_route.csv")
    output_path = Path("vehicle_tracking/belsize_to_bayview_interpolated_2sec.csv")

    # Parse the CSV file
    settings = VehicleTrackingSettings(
        interpolation_enabled=False  # First load without interpolation
    )

    result = service.parse_csv_file(input_path, settings)

    if not result.success:
        print(f"[ERROR] Failed to parse CSV: {result.error}")
        return

    vehicle_data = result.value
    original_points = vehicle_data.gps_points

    print(f"\nOriginal route:")
    print(f"  Points: {len(original_points)}")
    print(f"  Start: {original_points[0].timestamp}")
    print(f"  End: {original_points[-1].timestamp}")

    # Calculate original time gaps
    time_gaps = []
    for i in range(1, len(original_points)):
        gap = (original_points[i].timestamp - original_points[i-1].timestamp).total_seconds()
        time_gaps.append(gap)

    if time_gaps:
        avg_gap = sum(time_gaps) / len(time_gaps)
        print(f"  Average gap: {avg_gap:.1f} seconds")
        print(f"  Min gap: {min(time_gaps):.0f} seconds")
        print(f"  Max gap: {max(time_gaps):.0f} seconds")

    # Now interpolate to 2-second intervals
    settings.interpolation_enabled = True
    settings.interpolation_interval_seconds = 2.0  # 2-second intervals

    interpolated_result = service.interpolate_path(vehicle_data, settings)

    if not interpolated_result.success:
        print(f"[ERROR] Interpolation failed: {interpolated_result.error}")
        return

    interpolated_data = interpolated_result.value
    interp_points = interpolated_data.gps_points

    print(f"\nInterpolated route (2-second intervals):")
    print(f"  Points: {len(interp_points)}")
    print(f"  Start: {interp_points[0].timestamp}")
    print(f"  End: {interp_points[-1].timestamp}")

    # Verify 2-second spacing
    interp_gaps = []
    for i in range(1, min(20, len(interp_points))):
        gap = (interp_points[i].timestamp - interp_points[i-1].timestamp).total_seconds()
        interp_gaps.append(gap)

    if interp_gaps:
        print(f"  Time spacing verification (first 20):")
        print(f"    All gaps = 2.0s: {all(abs(g - 2.0) < 0.001 for g in interp_gaps)}")
        print(f"    Variance: {sum((g - 2.0)**2 for g in interp_gaps) / len(interp_gaps):.6f}")

    # Calculate speeds for each interpolated point
    print(f"\n" + "=" * 80)
    print("CALCULATING GROUND TRUTH SPEEDS")
    print("-" * 80)

    # Use haversine formula for accurate distance calculation
    from math import radians, sin, cos, sqrt, atan2

    def haversine_distance(lat1, lon1, lat2, lon2):
        """Calculate distance between two points in meters"""
        R = 6371000  # Earth radius in meters

        lat1, lon1 = radians(lat1), radians(lon1)
        lat2, lon2 = radians(lat2), radians(lon2)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))

        return R * c

    # Calculate speed for each point
    ground_truth_speeds = []
    for i in range(len(interp_points)):
        if i == 0:
            # First point - use speed from second point
            if len(interp_points) > 1:
                dist = haversine_distance(
                    interp_points[0].latitude, interp_points[0].longitude,
                    interp_points[1].latitude, interp_points[1].longitude
                )
                time_diff = (interp_points[1].timestamp - interp_points[0].timestamp).total_seconds()
                speed_kmh = (dist / time_diff) * 3.6 if time_diff > 0 else 0
            else:
                speed_kmh = 0
        else:
            # Calculate speed from previous point
            dist = haversine_distance(
                interp_points[i-1].latitude, interp_points[i-1].longitude,
                interp_points[i].latitude, interp_points[i].longitude
            )
            time_diff = (interp_points[i].timestamp - interp_points[i-1].timestamp).total_seconds()
            speed_kmh = (dist / time_diff) * 3.6 if time_diff > 0 else 0

        ground_truth_speeds.append(speed_kmh)

    # Show speed statistics
    non_zero_speeds = [s for s in ground_truth_speeds if s > 0.1]
    if non_zero_speeds:
        print(f"Speed statistics (excluding stops):")
        print(f"  Average: {sum(non_zero_speeds)/len(non_zero_speeds):.1f} km/h")
        print(f"  Min: {min(non_zero_speeds):.1f} km/h")
        print(f"  Max: {max(non_zero_speeds):.1f} km/h")

    # Write to CSV with ground truth speeds
    print(f"\n" + "=" * 80)
    print("WRITING INTERPOLATED DATA WITH GROUND TRUTH SPEEDS")
    print("-" * 80)

    with open(output_path, 'w', newline='') as csvfile:
        fieldnames = ['timestamp', 'latitude', 'longitude', 'speed_kmh', 'is_interpolated', 'ground_truth_speed_kmh']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for i, point in enumerate(interp_points):
            writer.writerow({
                'timestamp': point.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'latitude': point.latitude,
                'longitude': point.longitude,
                'speed_kmh': '',  # Leave empty for the app to calculate
                'is_interpolated': 'True' if point.is_interpolated else 'False',
                'ground_truth_speed_kmh': f"{ground_truth_speeds[i]:.2f}"
            })

    print(f"Written {len(interp_points)} points to: {output_path}")

    # Show first few and last few points as examples
    print(f"\nFirst 5 points:")
    for i in range(min(5, len(interp_points))):
        p = interp_points[i]
        print(f"  {p.timestamp.strftime('%H:%M:%S')}: "
              f"({p.latitude:.6f}, {p.longitude:.6f}) "
              f"Speed: {ground_truth_speeds[i]:.1f} km/h "
              f"{'[Interpolated]' if p.is_interpolated else '[Original]'}")

    print(f"\nLast 5 points:")
    for i in range(max(0, len(interp_points)-5), len(interp_points)):
        p = interp_points[i]
        print(f"  {p.timestamp.strftime('%H:%M:%S')}: "
              f"({p.latitude:.6f}, {p.longitude:.6f}) "
              f"Speed: {ground_truth_speeds[i]:.1f} km/h "
              f"{'[Interpolated]' if p.is_interpolated else '[Original]'}")

    print(f"\n" + "=" * 80)
    print("INTERPOLATION COMPLETE")
    print("=" * 80)
    print(f"\nGround truth dataset created with:")
    print(f"  - {len(interp_points)} total points")
    print(f"  - 2-second intervals")
    print(f"  - Known speeds for each point")
    print(f"  - Ready for testing at: {output_path}")

if __name__ == "__main__":
    interpolate_route()