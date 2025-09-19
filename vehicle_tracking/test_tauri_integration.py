#!/usr/bin/env python3
"""
Test script for Tauri integration
"""

import sys
import os
from pathlib import Path
import time
from datetime import datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from vehicle_tracking.services.tauri_bridge_service import TauriBridgeService
from vehicle_tracking.models.vehicle_tracking_models import (
    VehicleTrackingResult, VehicleData, GPSPoint, AnimationData,
    VehicleColor
)


def create_mock_data():
    """Create mock vehicle tracking data for testing"""

    # Create some GPS points for testing
    points1 = [
        GPSPoint(
            latitude=45.4215,
            longitude=-75.6972,
            timestamp=datetime(2024, 1, 1, 10, 0, i),
            speed_kmh=30.0 + i * 2
        )
        for i in range(10)
    ]

    points2 = [
        GPSPoint(
            latitude=45.4215 + i * 0.001,
            longitude=-75.6972 + i * 0.002,
            timestamp=datetime(2024, 1, 1, 10, 0, i),
            speed_kmh=25.0 + i * 1.5
        )
        for i in range(10)
    ]

    # Create vehicle data
    vehicle1 = VehicleData(
        vehicle_id="vehicle_1",
        source_file=Path("test_vehicle_1.csv"),
        label="Test Vehicle 1",
        color=VehicleColor.BLUE,
        gps_points=points1
    )

    vehicle2 = VehicleData(
        vehicle_id="vehicle_2",
        source_file=Path("test_vehicle_2.csv"),
        label="Test Vehicle 2",
        color=VehicleColor.RED,
        gps_points=points2
    )

    # Create animation data
    animation_data = AnimationData(
        vehicles=[vehicle1, vehicle2],
        timeline_start=datetime(2024, 1, 1, 10, 0, 0),
        timeline_end=datetime(2024, 1, 1, 10, 0, 9)
    )

    # Create tracking result
    result = VehicleTrackingResult(
        vehicles_processed=2,
        total_points_processed=20,
        processing_time_seconds=1.5,
        vehicle_data=[vehicle1, vehicle2],
        animation_data=animation_data
    )

    return result


def test_standalone_bridge():
    """Test the bridge without Qt"""
    print("=" * 60)
    print("TAURI INTEGRATION TEST")
    print("=" * 60)

    # Create mock data
    print("\n1. Creating mock vehicle data...")
    mock_result = create_mock_data()
    print(f"   [OK] Created {len(mock_result.vehicle_data)} vehicles")

    # Start bridge
    print("\n2. Starting Tauri bridge service...")
    bridge = TauriBridgeService()
    result = bridge.start()

    if not result.success:
        print(f"   [FAILED] Failed to start bridge: {result.error}")
        return

    print(f"   [OK] WebSocket server running on port {result.value}")
    print("   [OK] Tauri application should be launching...")

    # Wait for connection
    print("\n3. Waiting for Tauri to connect...")
    time.sleep(3)

    # Send test data
    print("\n4. Sending vehicle data to map...")
    if mock_result.animation_data:
        # Convert to the format the JavaScript expects
        vehicle_data_for_js = {
            "vehicles": []
        }

        # Convert each vehicle to the expected format
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

        # Add timeline info
        if mock_result.animation_data:
            vehicle_data_for_js["startTime"] = mock_result.animation_data.timeline_start.isoformat()
            vehicle_data_for_js["endTime"] = mock_result.animation_data.timeline_end.isoformat()

        send_result = bridge.send_vehicle_data(vehicle_data_for_js)

        if send_result.success:
            print("   [OK] Vehicle data sent successfully")
        else:
            print(f"   [FAILED] Failed to send data: {send_result.error}")

    print("\n5. Controls test (press Enter to continue between commands)...")

    # Test controls
    commands = [
        ("Play animation", "control", "play"),
        ("Pause animation", "control", "pause"),
        ("Stop animation", "control", "stop"),
        ("Play again", "control", "play")
    ]

    for description, cmd_type, command in commands:
        input(f"\n   Press Enter to: {description}")
        result = bridge.send_command(cmd_type, command)
        if result.success:
            print(f"   [OK] {description} command sent")
        else:
            print(f"   [FAILED] Failed: {result.error}")

    # Keep running
    print("\n" + "=" * 60)
    print("Map is running. Press Enter to stop and exit...")
    print("=" * 60)
    input()

    # Shutdown
    print("\n6. Shutting down...")
    bridge.shutdown()
    print("   [OK] Bridge shutdown complete")
    print("\nTest completed!")


def test_with_qt():
    """Test with Qt window"""
    from PySide6.QtWidgets import QApplication
    from vehicle_tracking.ui.components.vehicle_map_window import VehicleMapWindow

    print("=" * 60)
    print("TAURI QT INTEGRATION TEST")
    print("=" * 60)

    app = QApplication(sys.argv)

    # Create mock data
    print("Creating mock vehicle data...")
    mock_result = create_mock_data()

    # Create and show window
    print("Opening control panel window...")
    window = VehicleMapWindow(mock_result)
    window.show()

    # Run Qt event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--qt":
        test_with_qt()
    else:
        test_standalone_bridge()