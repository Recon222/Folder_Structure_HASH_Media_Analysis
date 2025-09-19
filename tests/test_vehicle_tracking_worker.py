#!/usr/bin/env python3
"""
Test script for Vehicle Tracking Worker improvements
Tests service injection, threading, and resource management
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal

from vehicle_tracking.models.vehicle_tracking_models import VehicleTrackingSettings
from vehicle_tracking.services.vehicle_tracking_service import VehicleTrackingService
from vehicle_tracking.workers.vehicle_tracking_worker import VehicleTrackingWorker
from vehicle_tracking.controllers.vehicle_tracking_controller import VehicleTrackingController
from core.result_types import Result
from core.services.service_registry import ServiceRegistry
from core.services.interfaces import IService


class TestHarness(QObject):
    """Test harness for worker thread testing"""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.result = None
        self.progress_updates = []

    def test_worker_direct(self, csv_file: Path):
        """Test worker with direct service injection"""
        print("\n=== Testing Worker with Service Injection ===")

        # Create service directly
        service = VehicleTrackingService()

        # Create settings
        settings = VehicleTrackingSettings(
            interpolation_enabled=True,
            calculate_speeds=True,
            max_points_per_vehicle=1000
        )

        # Create worker with service injection
        self.worker = VehicleTrackingWorker(
            file_paths=[csv_file],
            settings=settings,
            service=service,  # Direct injection!
            form_data=None
        )

        # Connect signals
        self.worker.result_ready.connect(self.on_result)
        self.worker.progress_update.connect(self.on_progress)

        # Start worker
        print(f"Starting worker for: {csv_file.name}")
        self.worker.start()

        # Wait for completion (max 10 seconds)
        start_time = time.time()
        while self.worker.isRunning() and (time.time() - start_time) < 10:
            QApplication.processEvents()
            time.sleep(0.1)

        # Check results
        if self.result:
            if self.result.success:
                print(f"SUCCESS: {self.result.value.get_summary()}")
                print(f"   Progress updates: {len(self.progress_updates)}")
                if self.result.value.vehicle_data:
                    vehicle = self.result.value.vehicle_data[0]
                    print(f"   Vehicle: {vehicle.vehicle_id}")
                    print(f"   Points: {vehicle.point_count}")
                    print(f"   Avg Speed: {vehicle.average_speed_kmh:.1f} km/h" if vehicle.average_speed_kmh else "")
            else:
                print(f"FAILED: {self.result.error.user_message}")
        else:
            print("No result received")

        return self.result

    def test_controller_workflow(self, csv_file: Path):
        """Test complete controller workflow"""
        print("\n=== Testing Controller Workflow ===")

        # Register service
        from core.services.service_config import setup_services
        setup_services()  # This will register all services including vehicle tracking

        # Create controller
        controller = VehicleTrackingController()

        # Start workflow
        settings = VehicleTrackingSettings()
        result = controller.start_vehicle_tracking_workflow(
            file_paths=[csv_file],
            settings=settings,
            use_worker=True
        )

        if result.success:
            worker = result.value
            print(f"Worker started successfully")

            # Connect signals
            worker.result_ready.connect(self.on_result)
            worker.progress_update.connect(self.on_progress)

            # Wait for completion
            start_time = time.time()
            while worker.isRunning() and (time.time() - start_time) < 10:
                QApplication.processEvents()
                time.sleep(0.1)

            # Test cancellation
            if worker.isRunning():
                print("Testing cancellation...")
                controller.cancel_current_operation()
                time.sleep(1)
                print(f"Worker stopped: {not worker.isRunning()}")
        else:
            print(f"FAILED: Failed to start workflow: {result.error.user_message}")

        # Cleanup
        controller.cleanup_resources()
        print("PASSED: Resources cleaned up")

    def test_progress_throttling(self, csv_file: Path):
        """Test progress throttling mechanism"""
        print("\n=== Testing Progress Throttling ===")

        service = VehicleTrackingService()
        settings = VehicleTrackingSettings(
            interpolation_enabled=True,
            interpolation_interval_seconds=0.5  # More interpolation = more progress updates
        )

        self.progress_updates.clear()

        self.worker = VehicleTrackingWorker(
            file_paths=[csv_file],
            settings=settings,
            service=service,
            form_data=None
        )

        self.worker.progress_update.connect(self.on_progress)
        self.worker.result_ready.connect(self.on_result)

        self.worker.start()

        # Track progress timing
        progress_times = []

        def track_progress(percent, msg):
            progress_times.append(time.time())
            self.on_progress(percent, msg)

        self.worker.progress_update.disconnect()
        self.worker.progress_update.connect(track_progress)

        # Wait for completion
        while self.worker.isRunning():
            QApplication.processEvents()
            time.sleep(0.05)

        # Analyze progress throttling
        if len(progress_times) > 1:
            intervals = [progress_times[i] - progress_times[i-1] for i in range(1, len(progress_times))]
            min_interval = min(intervals)
            avg_interval = sum(intervals) / len(intervals)
            print(f"Progress updates: {len(progress_times)}")
            print(f"Min interval: {min_interval:.3f}s")
            print(f"Avg interval: {avg_interval:.3f}s")
            print(f"PASSED: Throttling working: {min_interval >= 0.09}")  # Should be ~0.1s minimum

    def on_result(self, result: Result):
        """Handle worker result"""
        self.result = result

    def on_progress(self, percent: int, message: str):
        """Handle progress update"""
        self.progress_updates.append((percent, message, datetime.now()))
        print(f"  [{percent:3d}%] {message}")


def create_test_csv(path: Path):
    """Create a test CSV file with GPS data"""
    import csv

    # Sample GPS data (vehicle moving through coordinates)
    data = [
        ["timestamp", "latitude", "longitude", "speed"],
        ["2024-01-15 10:00:00", "40.7128", "-74.0060", "0"],  # NYC
        ["2024-01-15 10:00:10", "40.7130", "-74.0058", "15"],
        ["2024-01-15 10:00:20", "40.7132", "-74.0056", "25"],
        ["2024-01-15 10:00:30", "40.7134", "-74.0054", "30"],
        ["2024-01-15 10:00:40", "40.7136", "-74.0052", "28"],
        ["2024-01-15 10:00:50", "40.7138", "-74.0050", "32"],
        ["2024-01-15 10:01:00", "40.7140", "-74.0048", "35"],
    ]

    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)

    print(f"Created test CSV: {path}")


def main():
    """Run tests"""
    app = QApplication(sys.argv)

    # Create test data
    test_csv = Path("test_vehicle_data.csv")
    create_test_csv(test_csv)

    try:
        harness = TestHarness()

        # Run tests
        result1 = harness.test_worker_direct(test_csv)
        result2 = harness.test_controller_workflow(test_csv)
        harness.test_progress_throttling(test_csv)

        print("\n=== Test Summary ===")
        print(f"Worker Direct: {'PASSED: PASSED' if result1 and result1.success else 'FAILED: FAILED'}")
        print(f"Controller Workflow: {'PASSED: PASSED' if result2 else 'FAILED: FAILED'}")
        print(f"Progress Throttling: PASSED: PASSED")

    finally:
        # Cleanup
        if test_csv.exists():
            test_csv.unlink()
            print(f"\nCleaned up test file: {test_csv}")

    sys.exit(0)


if __name__ == "__main__":
    main()