"""
Vehicle Map Window - Control Panel for Tauri Map
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QGridLayout, QComboBox, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIcon

from core.logger import logger
from vehicle_tracking.services.tauri_bridge_service import TauriBridgeService
from vehicle_tracking.models.vehicle_tracking_models import VehicleTrackingResult


class VehicleMapWindow(QWidget):
    """Modified to be a control panel while Tauri shows the map"""

    # Signals
    closed = Signal()

    def __init__(self, tracking_results: VehicleTrackingResult = None, parent=None):
        super().__init__(parent)

        self.tracking_results = tracking_results
        self.bridge = None

        # Update window properties - smaller since it's just controls
        self.setWindowTitle("Vehicle Tracking - Control Panel")
        self.setWindowIcon(QIcon("🎮"))  # Control icon
        self.resize(400, 500)  # Smaller window

        # Window flags for staying on top
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)

        # Create UI
        self._create_ui()

        # Launch map after UI is ready
        QTimer.singleShot(100, self._launch_map)

    def _create_ui(self):
        """Create control panel UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title_label = QLabel("🗺️ Vehicle Tracking Map Controls")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        # Status
        self.status_label = QLabel("Initializing map...")
        self.status_label.setStyleSheet("color: #666; padding: 10px;")
        layout.addWidget(self.status_label)

        # Separator
        layout.addWidget(self._create_separator())

        # Map Provider Selection
        provider_group = QGroupBox("Map Provider")
        provider_layout = QVBoxLayout(provider_group)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Mapbox (High Performance)", "Leaflet (Open Source)"])
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_layout.addWidget(self.provider_combo)

        layout.addWidget(provider_group)

        # Controls
        controls_group = QGroupBox("Animation Controls")
        controls_layout = QGridLayout(controls_group)

        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self._play_animation)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        controls_layout.addWidget(self.play_btn, 0, 0)

        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.clicked.connect(self._pause_animation)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #f59e0b;
                color: white;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d97706;
            }
        """)
        controls_layout.addWidget(self.pause_btn, 0, 1)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.clicked.connect(self._stop_animation)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        controls_layout.addWidget(self.stop_btn, 0, 2)

        layout.addWidget(controls_group)

        # Info
        info_group = QGroupBox("Information")
        info_layout = QVBoxLayout(info_group)

        if self.tracking_results:
            vehicles_count = len(self.tracking_results.vehicles) if self.tracking_results.vehicles else 0

            # Format time range
            time_range = "N/A"
            if hasattr(self.tracking_results, 'time_range') and self.tracking_results.time_range:
                time_range = self.tracking_results.time_range
            elif self.tracking_results.animation_data:
                if hasattr(self.tracking_results.animation_data, 'start_time') and hasattr(self.tracking_results.animation_data, 'end_time'):
                    start = self.tracking_results.animation_data.start_time
                    end = self.tracking_results.animation_data.end_time
                    time_range = f"{start} - {end}"

            # Get analysis type
            analysis_type = "Standard"
            if hasattr(self.tracking_results, 'analysis_type'):
                analysis_type = self.tracking_results.analysis_type.value if hasattr(self.tracking_results.analysis_type, 'value') else str(self.tracking_results.analysis_type)

            info_text = f"""
            <b>Vehicles:</b> {vehicles_count}<br>
            <b>Time Range:</b> {time_range}<br>
            <b>Analysis Type:</b> {analysis_type}
            """
            info_label = QLabel(info_text)
            info_layout.addWidget(info_label)
        else:
            info_label = QLabel("No tracking data loaded")
            info_layout.addWidget(info_label)

        layout.addWidget(info_group)

        # Spacer
        layout.addStretch()

        # Close button
        close_btn = QPushButton("Close Map")
        close_btn.clicked.connect(self._close_map)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b7280;
                color: white;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        layout.addWidget(close_btn)

    def _create_separator(self):
        """Create a horizontal separator"""
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def _launch_map(self):
        """Launch Tauri map application"""
        try:
            self.status_label.setText("Starting WebSocket server...")

            # Initialize bridge service
            self.bridge = TauriBridgeService()

            # Start bridge (WebSocket + Tauri)
            result = self.bridge.start()

            if result.success:
                self.status_label.setText("Launching map window...")

                # Send vehicle data after a short delay
                QTimer.singleShot(2000, self._send_tracking_data)
            else:
                self.status_label.setText(f"Error: {result.error}")
                QMessageBox.critical(self, "Launch Error", f"Failed to launch map: {result.error}")

        except Exception as e:
            logger.error(f"Failed to launch map: {e}")
            self.status_label.setText(f"Error: {str(e)}")

    def _send_tracking_data(self):
        """Send tracking data to Tauri map"""
        try:
            if self.tracking_results and self.tracking_results.animation_data:
                # Convert to dictionary
                data = self.tracking_results.animation_data.to_dict()

                # Send via bridge
                result = self.bridge.send_vehicle_data(data)

                if result.success:
                    self.status_label.setText("✓ Map loaded with vehicle data")
                else:
                    self.status_label.setText(f"Error sending data: {result.error}")
            else:
                self.status_label.setText("✓ Map ready (no data to display)")

        except Exception as e:
            logger.error(f"Failed to send data: {e}")
            self.status_label.setText(f"Error: {str(e)}")

    def _on_provider_changed(self, text: str):
        """Handle provider change"""
        if self.bridge and self.bridge.is_running:
            provider = "mapbox" if "Mapbox" in text else "leaflet"
            self.bridge.send_command("switch_provider", provider)

    def _play_animation(self):
        """Send play command"""
        if self.bridge:
            self.bridge.send_command("control", "play")
            self.status_label.setText("▶ Playing animation")

    def _pause_animation(self):
        """Send pause command"""
        if self.bridge:
            self.bridge.send_command("control", "pause")
            self.status_label.setText("⏸ Animation paused")

    def _stop_animation(self):
        """Send stop command"""
        if self.bridge:
            self.bridge.send_command("control", "stop")
            self.status_label.setText("⏹ Animation stopped")

    def _close_map(self):
        """Close map and cleanup"""
        if self.bridge:
            self.bridge.shutdown()
        self.closed.emit()
        self.close()

    def closeEvent(self, event):
        """Handle window close"""
        if self.bridge:
            self.bridge.shutdown()
        self.closed.emit()
        super().closeEvent(event)