#!/usr/bin/env python3
"""
Test script for Vehicle Tracking Tab UI
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget
from vehicle_tracking.ui.vehicle_tracking_tab import VehicleTrackingTab

def main():
    """Test the Vehicle Tracking tab UI"""
    app = QApplication(sys.argv)

    # Create main window
    window = QMainWindow()
    window.setWindowTitle("Vehicle Tracking Tab Test")
    window.resize(1200, 800)

    # Create tab widget
    tab_widget = QTabWidget()

    # Add vehicle tracking tab
    vehicle_tab = VehicleTrackingTab()
    tab_widget.addTab(vehicle_tab, "Vehicle Tracking")

    # Set as central widget
    window.setCentralWidget(tab_widget)

    # Show window
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()