#!/usr/bin/env python3
"""
Vehicle Map Widget - Qt wrapper for vehicle tracking map

Provides QWebEngineView integration with JavaScript bridge for vehicle animation.
Follows patterns from GeoVisualizationWidget.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from PySide6.QtCore import Qt, QUrl, Signal, Slot, QObject
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QToolBar,
    QLabel, QComboBox, QPushButton, QSlider,
    QMessageBox, QSplitter, QGroupBox, QCheckBox
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtGui import QAction, QIcon

# Import models
from vehicle_tracking.models.vehicle_tracking_models import (
    VehicleData, AnimationData, VehicleTrackingSettings
)

# Import services
from vehicle_tracking.services.map_template_service import MapTemplateService

from core.logger import logger
from core.result_types import Result


class VehicleMapBridge(QObject):
    """
    Bridge for Qt-JavaScript communication
    
    Handles bidirectional communication between Qt and the map JavaScript.
    """
    
    # Signals to JavaScript
    loadVehiclesSignal = Signal(str)  # JSON vehicle data
    controlSignal = Signal(str)  # Animation control commands
    seekSignal = Signal(float)  # Seek to timestamp
    speedSignal = Signal(float)  # Playback speed
    styleSignal = Signal(str)  # Map style change
    
    # Signals from JavaScript
    vehicleClicked = Signal(str)  # Vehicle ID clicked
    animationStateChanged = Signal(str)  # playing/paused/stopped
    timeUpdate = Signal(float)  # Current animation time
    mapReady = Signal()  # Map initialized and ready
    errorOccurred = Signal(str)  # JavaScript errors
    
    def __init__(self):
        super().__init__()
    
    @Slot(str)
    def onVehicleClick(self, vehicle_id: str):
        """Handle vehicle marker click from JavaScript"""
        self.vehicleClicked.emit(vehicle_id)
    
    @Slot(str)
    def onAnimationState(self, state: str):
        """Handle animation state change from JavaScript"""
        self.animationStateChanged.emit(state)
    
    @Slot(float)
    def onTimeUpdate(self, timestamp: float):
        """Handle time update from JavaScript"""
        self.timeUpdate.emit(timestamp)
    
    @Slot()
    def onMapReady(self):
        """Handle map ready signal from JavaScript"""
        self.mapReady.emit()
    
    @Slot(str)
    def onError(self, error_message: str):
        """Handle JavaScript errors"""
        logger.error(f"JavaScript error: {error_message}")
        self.errorOccurred.emit(error_message)
    
    def loadVehicles(self, vehicle_data: Dict[str, Any]):
        """Send vehicle data to JavaScript"""
        try:
            json_data = json.dumps(vehicle_data, default=str)
            self.loadVehiclesSignal.emit(json_data)
        except Exception as e:
            logger.error(f"Error sending vehicle data: {e}")
    
    def sendControl(self, command: str):
        """Send control command to JavaScript"""
        self.controlSignal.emit(command)
    
    def seekToTime(self, timestamp: float):
        """Seek animation to specific time"""
        self.seekSignal.emit(timestamp)
    
    def setSpeed(self, speed: float):
        """Set playback speed"""
        self.speedSignal.emit(speed)
    
    def setStyle(self, style: str):
        """Change map style"""
        self.styleSignal.emit(style)


class VehicleMapWidget(QWidget):
    """
    Vehicle map visualization widget
    
    Displays interactive map with animated vehicle tracking using QWebEngineView.
    """
    
    # Signals
    vehicleSelected = Signal(str)  # Emitted when vehicle clicked
    animationFinished = Signal()  # Emitted when animation completes
    exportRequested = Signal(str)  # Export format requested
    
    def __init__(self, parent=None):
        """
        Initialize vehicle map widget
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Web components
        self.web_view = QWebEngineView()
        self.web_channel = QWebChannel()
        self.map_bridge = VehicleMapBridge()
        
        # Services
        self.template_service = MapTemplateService()
        
        # State
        self.current_vehicles: List[VehicleData] = []
        self.current_animation: Optional[AnimationData] = None
        self.current_provider: str = "leaflet"
        self._map_loaded: bool = False
        self._pending_data: Optional[Dict[str, Any]] = None
        
        # Settings
        self.settings = VehicleTrackingSettings()
        
        # Create UI
        self._create_ui()
        self._setup_web_channel()
        self._connect_signals()
        
        # Load default map template
        self._load_map_template()
    
    def _create_ui(self):
        """Create the widget UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create toolbar
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # Create control panel
        control_panel = self._create_control_panel()
        
        # Create splitter for map and controls
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.web_view)
        splitter.addWidget(control_panel)
        splitter.setSizes([600, 100])
        
        layout.addWidget(splitter)
        
        # Status bar
        self.status_label = QLabel("Initializing map...")
        self.status_label.setStyleSheet("padding: 5px; background: #f0f0f0;")
        layout.addWidget(self.status_label)
    
    def _create_toolbar(self) -> QToolBar:
        """Create map toolbar"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        
        # Map provider selector
        provider_label = QLabel("Map Provider: ")
        toolbar.addWidget(provider_label)
        
        self.provider_combo = QComboBox()
        available_providers = self.template_service.get_available_providers()
        for provider in available_providers:
            display_name = self.template_service.get_provider_display_name(provider)
            self.provider_combo.addItem(display_name, provider)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        toolbar.addWidget(self.provider_combo)
        
        toolbar.addSeparator()
        
        # Animation controls
        self.play_action = QAction("▶ Play", self)
        self.play_action.triggered.connect(self.play_animation)
        toolbar.addAction(self.play_action)
        
        self.pause_action = QAction("⏸ Pause", self)
        self.pause_action.triggered.connect(self.pause_animation)
        self.pause_action.setEnabled(False)
        toolbar.addAction(self.pause_action)
        
        self.stop_action = QAction("⏹ Stop", self)
        self.stop_action.triggered.connect(self.stop_animation)
        toolbar.addAction(self.stop_action)
        
        toolbar.addSeparator()
        
        # Zoom controls
        zoom_in_action = QAction("🔍+", self)
        zoom_in_action.setToolTip("Zoom In")
        zoom_in_action.triggered.connect(self._zoom_in)
        toolbar.addAction(zoom_in_action)
        
        zoom_out_action = QAction("🔍-", self)
        zoom_out_action.setToolTip("Zoom Out")
        zoom_out_action.triggered.connect(self._zoom_out)
        toolbar.addAction(zoom_out_action)
        
        fit_action = QAction("⊡", self)
        fit_action.setToolTip("Fit All Vehicles")
        fit_action.triggered.connect(self._fit_all_vehicles)
        toolbar.addAction(fit_action)
        
        toolbar.addSeparator()
        
        # Export menu
        export_action = QAction("📤 Export", self)
        export_action.triggered.connect(self._show_export_menu)
        toolbar.addAction(export_action)
        
        return toolbar
    
    def _create_control_panel(self) -> QWidget:
        """Create animation control panel"""
        panel = QGroupBox("Animation Controls")
        layout = QHBoxLayout(panel)
        
        # Speed control
        layout.addWidget(QLabel("Speed:"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1x", "2x", "5x", "10x"])
        self.speed_combo.setCurrentIndex(1)  # Default to 1x
        self.speed_combo.currentTextChanged.connect(self._on_speed_changed)
        layout.addWidget(self.speed_combo)
        
        layout.addSpacing(20)
        
        # Time slider
        layout.addWidget(QLabel("Timeline:"))
        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setEnabled(False)
        self.time_slider.valueChanged.connect(self._on_time_slider_changed)
        layout.addWidget(self.time_slider, stretch=1)
        
        # Time display
        self.time_label = QLabel("00:00:00")
        self.time_label.setStyleSheet("font-family: monospace; font-weight: bold;")
        layout.addWidget(self.time_label)
        
        layout.addSpacing(20)
        
        # Options
        self.show_trails_check = QCheckBox("Show Trails")
        self.show_trails_check.setChecked(True)
        self.show_trails_check.toggled.connect(self._on_trails_toggled)
        layout.addWidget(self.show_trails_check)
        
        self.cluster_check = QCheckBox("Cluster Markers")
        self.cluster_check.setChecked(False)
        self.cluster_check.toggled.connect(self._on_clustering_toggled)
        layout.addWidget(self.cluster_check)
        
        return panel
    
    def _setup_web_channel(self):
        """Set up Qt-JavaScript communication channel"""
        self.web_channel.registerObject("bridge", self.map_bridge)
        self.web_view.page().setWebChannel(self.web_channel)
    
    def _connect_signals(self):
        """Connect internal signals"""
        # Bridge signals
        self.map_bridge.vehicleClicked.connect(self._on_vehicle_clicked)
        self.map_bridge.animationStateChanged.connect(self._on_animation_state_changed)
        self.map_bridge.timeUpdate.connect(self._on_time_update)
        self.map_bridge.mapReady.connect(self._on_map_ready)
        self.map_bridge.errorOccurred.connect(self._on_js_error)
        
        # Web view signals
        self.web_view.loadFinished.connect(self._on_load_finished)
    
    def _load_map_template(self):
        """Load the map template HTML"""
        try:
            self.status_label.setText(f"Loading {self.current_provider} map...")
            
            # Get template from service
            result = self.template_service.load_template(self.current_provider, "map")
            
            if result.success:
                # Load HTML into web view
                self.web_view.setHtml(result.value)
                logger.info(f"Loaded {self.current_provider} map template")
            else:
                # Show error and fall back to basic HTML
                error_msg = result.error.user_message if result.error else "Failed to load template"
                logger.error(f"Template loading failed: {error_msg}")
                self.status_label.setText(f"Error: {error_msg}")
                
                # Load fallback
                self._load_fallback_template()
                
        except Exception as e:
            logger.error(f"Error loading map template: {e}")
            self.status_label.setText(f"Error loading map: {str(e)}")
            self._load_fallback_template()
    
    def _load_fallback_template(self):
        """Load a basic fallback template"""
        fallback_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Map Error</title></head>
        <body style="display: flex; align-items: center; justify-content: center; height: 100vh;">
            <div style="text-align: center;">
                <h2>Map Loading Error</h2>
                <p>Failed to load map template. Please check your configuration.</p>
            </div>
        </body>
        </html>
        """
        self.web_view.setHtml(fallback_html)
    
    def load_vehicle_data(
        self,
        vehicles: List[VehicleData],
        animation_data: Optional[AnimationData] = None
    ):
        """
        Load vehicle data into the map

        Args:
            vehicles: List of vehicle data
            animation_data: Optional animation data
        """
        try:
            self.current_vehicles = vehicles
            self.current_animation = animation_data

            # Prepare data for JavaScript
            vehicle_dict = {
                'vehicles': [self._vehicle_to_dict(v) for v in vehicles]
            }

            if animation_data:
                vehicle_dict['animation_data'] = self._animation_to_dict(animation_data)

            logger.info(f"Prepared vehicle data: {len(vehicle_dict['vehicles'])} vehicles")
            logger.info(f"Map loaded status: {self._map_loaded}")

            # If map is ready, send data immediately
            if self._map_loaded:
                logger.info("Sending data to JavaScript via bridge...")
                self.map_bridge.loadVehicles(vehicle_dict)
                self.status_label.setText(f"Loaded {len(vehicles)} vehicles")

                # Also try direct JavaScript injection as backup
                import json
                # Properly escape JSON for safe JavaScript execution
                vehicle_json = json.dumps(vehicle_dict, ensure_ascii=True)
                # Use JSON.parse to safely parse the JSON string in JavaScript
                js_code = f"if (window.vehicleMap) {{ window.vehicleMap.loadVehicles(JSON.parse({json.dumps(vehicle_json)})); console.log('Data sent directly to map'); }}"
                self.web_view.page().runJavaScript(js_code)

                # Enable timeline if we have animation data
                if animation_data:
                    self._setup_timeline(animation_data)
            else:
                # Store data to send when map is ready
                logger.info("Map not ready, storing data for later...")
                self._pending_data = vehicle_dict
                self.status_label.setText("Waiting for map to initialize...")

        except Exception as e:
            logger.error(f"Error loading vehicle data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.status_label.setText(f"Error: {str(e)}")
    
    def _vehicle_to_dict(self, vehicle: VehicleData) -> Dict[str, Any]:
        """Convert VehicleData to dictionary for JavaScript"""
        return {
            'vehicle_id': vehicle.vehicle_id,
            'label': vehicle.label or vehicle.vehicle_id,
            'color': vehicle.color.value if vehicle.color else '#0066CC',
            'gps_points': [
                {
                    'latitude': p.latitude,
                    'longitude': p.longitude,
                    'timestamp': p.timestamp.isoformat(),
                    'speed': p.speed_kmh or p.calculated_speed_kmh,
                    'interpolated': p.is_interpolated
                }
                for p in vehicle.gps_points
            ] if vehicle.gps_points else []
        }
    
    def _animation_to_dict(self, animation: AnimationData) -> Dict[str, Any]:
        """Convert AnimationData to dictionary for JavaScript"""
        result = {
            'timeline_start': animation.timeline_start.isoformat() if animation.timeline_start else None,
            'timeline_end': animation.timeline_end.isoformat() if animation.timeline_end else None,
            'total_duration_seconds': animation.total_duration_seconds
        }
        
        # Include GeoJSON if available
        if animation.feature_collection:
            result['feature_collection'] = animation.feature_collection
        
        return result
    
    def _setup_timeline(self, animation_data: AnimationData):
        """Set up timeline slider for animation"""
        if animation_data.timeline_start and animation_data.timeline_end:
            # Convert to timestamps
            start_ts = animation_data.timeline_start.timestamp()
            end_ts = animation_data.timeline_end.timestamp()
            
            # Configure slider
            self.time_slider.setMinimum(int(start_ts))
            self.time_slider.setMaximum(int(end_ts))
            self.time_slider.setValue(int(start_ts))
            self.time_slider.setEnabled(True)
    
    def play_animation(self):
        """Start animation playback"""
        self.map_bridge.sendControl("play")
        self.play_action.setEnabled(False)
        self.pause_action.setEnabled(True)
    
    def pause_animation(self):
        """Pause animation playback"""
        self.map_bridge.sendControl("pause")
        self.play_action.setEnabled(True)
        self.pause_action.setEnabled(False)
    
    def stop_animation(self):
        """Stop animation and reset to start"""
        self.map_bridge.sendControl("stop")
        self.play_action.setEnabled(True)
        self.pause_action.setEnabled(False)
        
        if self.current_animation and self.current_animation.timeline_start:
            self.time_slider.setValue(int(self.current_animation.timeline_start.timestamp()))
    
    def clear_vehicles(self):
        """Clear all vehicles from the map"""
        self.map_bridge.sendControl("clear")
        self.current_vehicles.clear()
        self.current_animation = None
        self.status_label.setText("Map cleared")
    
    def focus_vehicle(self, vehicle_id: str):
        """Focus map on specific vehicle"""
        # Send focus command via bridge
        self.web_view.page().runJavaScript(
            f"if (window.vehicleMap) vehicleMap.focusVehicle('{vehicle_id}');"
        )
    
    # Event handlers
    
    def _on_map_ready(self):
        """Handle map ready signal"""
        self._map_loaded = True
        self.status_label.setText("Map ready")
        logger.info("Map is ready - setting _map_loaded to True")

        # Send pending data if any
        if self._pending_data:
            logger.info(f"Sending pending data: {len(self._pending_data.get('vehicles', []))} vehicles")
            self.map_bridge.loadVehicles(self._pending_data)
            self._pending_data = None
    
    def _on_load_finished(self, ok: bool):
        """Handle web view load finished"""
        if ok:
            logger.info("Map template loaded successfully")
        else:
            logger.error("Failed to load map template")
            self.status_label.setText("Map loading failed")
    
    def _on_vehicle_clicked(self, vehicle_id: str):
        """Handle vehicle marker click"""
        self.vehicleSelected.emit(vehicle_id)
        logger.info(f"Vehicle selected: {vehicle_id}")
    
    def _on_animation_state_changed(self, state: str):
        """Handle animation state change"""
        if state == "finished":
            self.animationFinished.emit()
            self.play_action.setEnabled(True)
            self.pause_action.setEnabled(False)
    
    def _on_time_update(self, timestamp: float):
        """Handle animation time update"""
        # Update slider without triggering valueChanged
        self.time_slider.blockSignals(True)
        self.time_slider.setValue(int(timestamp))
        self.time_slider.blockSignals(False)
        
        # Update time label
        dt = datetime.fromtimestamp(timestamp)
        self.time_label.setText(dt.strftime("%H:%M:%S"))
    
    def _on_time_slider_changed(self, value: int):
        """Handle manual timeline slider change"""
        if self.time_slider.isSliderDown():
            # User is dragging slider
            self.map_bridge.seekToTime(float(value))
    
    def _on_speed_changed(self, speed_text: str):
        """Handle speed combo change"""
        speed = float(speed_text.replace('x', ''))
        self.map_bridge.setSpeed(speed)
    
    def _on_provider_changed(self, index: int):
        """Handle map provider change"""
        if index >= 0:
            provider = self.provider_combo.itemData(index)
            if provider != self.current_provider:
                self.current_provider = provider
                self._map_loaded = False
                self._load_map_template()
    
    def _on_trails_toggled(self, checked: bool):
        """Handle trail visibility toggle"""
        # Send to JavaScript
        self.web_view.page().runJavaScript(
            f"if (window.vehicleMap) vehicleMap.setTrailsVisible({str(checked).lower()});"
        )
    
    def _on_clustering_toggled(self, checked: bool):
        """Handle marker clustering toggle"""
        # Send to JavaScript
        self.web_view.page().runJavaScript(
            f"if (window.vehicleMap) vehicleMap.setClusteringEnabled({str(checked).lower()});"
        )
    
    def _on_js_error(self, error: str):
        """Handle JavaScript errors"""
        self.status_label.setText(f"Map error: {error}")
    
    # Map control methods
    
    def _zoom_in(self):
        """Zoom in the map"""
        self.web_view.page().runJavaScript(
            "if (window.vehicleMap && window.vehicleMap.map) vehicleMap.map.zoomIn();"
        )
    
    def _zoom_out(self):
        """Zoom out the map"""
        self.web_view.page().runJavaScript(
            "if (window.vehicleMap && window.vehicleMap.map) vehicleMap.map.zoomOut();"
        )
    
    def _fit_all_vehicles(self):
        """Fit map to show all vehicles"""
        self.web_view.page().runJavaScript(
            "if (window.vehicleMap) vehicleMap.fitMapToVehicles();"
        )
    
    def _show_export_menu(self):
        """Show export options"""
        # This would show a menu for KML, GeoJSON, CSV export
        self.exportRequested.emit("KML")  # For now, just emit KML
    
    def cleanup(self):
        """Clean up resources"""
        self.clear_vehicles()
        self.template_service.clear_all_cache()