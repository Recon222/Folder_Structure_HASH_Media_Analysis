#!/usr/bin/env python3
"""Quick non-interactive test for Tauri integration"""

import sys
import os
from pathlib import Path
import time
from datetime import datetime, timedelta

sys.path.append(str(Path(__file__).parent.parent))

from vehicle_tracking.services.tauri_bridge_service import TauriBridgeService
from vehicle_tracking.models.vehicle_tracking_models import (
    VehicleTrackingResult, VehicleData, GPSPoint, AnimationData,
    VehicleColor
)

def create_mock_data():
    """Create mock vehicle tracking data for testing"""
    points1 = [
        GPSPoint(
            latitude=45.4215 + i * 0.001,  # Move north gradually
            longitude=-75.6972 + i * 0.002,  # Move east gradually
            timestamp=datetime(2024, 1, 1, 10, 0, 0) + timedelta(seconds=i * 30),  # 30 seconds apart
            speed_kmh=30.0 + i * 2
        )
        for i in range(10)
    ]

    vehicle1 = VehicleData(
        vehicle_id="vehicle_1",
        source_file=Path("test_vehicle_1.csv"),
        label="Test Vehicle 1",
        color=VehicleColor.BLUE,
        gps_points=points1
    )

    animation_data = AnimationData(
        vehicles=[vehicle1],
        timeline_start=datetime(2024, 1, 1, 10, 0, 0),
        timeline_end=datetime(2024, 1, 1, 10, 0, 0) + timedelta(seconds=9 * 30)  # Match the last point
    )

    result = VehicleTrackingResult(
        vehicles_processed=1,
        total_points_processed=10,
        processing_time_seconds=0.5,
        vehicle_data=[vehicle1],
        animation_data=animation_data
    )
    
    return result

print("TAURI QUICK TEST")
print("=" * 40)

# Create mock data
print("Creating vehicle data...")
mock_result = create_mock_data()

# Start bridge
print("Starting Tauri bridge...")
bridge = TauriBridgeService()
result = bridge.start()

if not result.success:
    print(f"FAILED: {result.error}")
    sys.exit(1)

print(f"WebSocket server on port: {result.value}")
print("Tauri window should open now...")
print("")
print("Check if you see:")
print("1. The Mapbox token modal")
print("2. After entering token, the map")
print("")
print("Waiting 10 seconds for you to test...")

# Give time to test
time.sleep(10)

# Send data
if mock_result.vehicle_data:
    # Convert to the format the JavaScript expects
    vehicle_data_for_js = {
        "vehicles": []
    }

    for vehicle in mock_result.vehicle_data:
        vehicle_obj = {
            "id": vehicle.vehicle_id,
            "label": vehicle.label or vehicle.vehicle_id,
            "color": vehicle.color.value if vehicle.color else "#0099ff",
            "gps_points": [
                {
                    "latitude": point.latitude,
                    "longitude": point.longitude,
                    "timestamp": point.timestamp.isoformat(),
                    "speed": point.speed_kmh or 0
                }
                for point in vehicle.gps_points
            ]
        }
        vehicle_data_for_js["vehicles"].append(vehicle_obj)

    if mock_result.animation_data:
        vehicle_data_for_js["startTime"] = mock_result.animation_data.timeline_start.isoformat()
        vehicle_data_for_js["endTime"] = mock_result.animation_data.timeline_end.isoformat()

    bridge.send_vehicle_data(vehicle_data_for_js)
    print("Vehicle data sent")

print("Keeping alive for 20 more seconds...")
time.sleep(20)

bridge.shutdown()
print("Test complete!")
