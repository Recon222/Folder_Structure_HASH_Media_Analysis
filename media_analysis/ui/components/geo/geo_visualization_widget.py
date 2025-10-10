#!/usr/bin/env python3
"""
GeoVisualizationWidget - Interactive map for GPS data visualization
Uses QWebEngineView with Leaflet for forensic media location analysis
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QToolBar, QSplitter, QMessageBox
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtGui import QAction, QIcon

from .geo_bridge import GeoBridge
from .map_template import MAP_HTML_TEMPLATE
from media_analysis.exiftool.exiftool_models import ExifToolMetadata, GPSData
from core.logger import logger
from core.settings_manager import settings


class GeoVisualizationWidget(QWidget):
    """
    Interactive map visualization for GPS data
    Displays media file locations on an interactive web map
    """
    
    # Signals
    file_selected = Signal(str)  # Emitted when marker clicked
    export_requested = Signal(str, str)  # format, output_path
    
    def __init__(self, parent=None):
        """
        Initialize the geo visualization widget
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Web components
        self.web_view = QWebEngineView()
        
        # Connect to console messages for debugging
        from PySide6.QtWebEngineCore import QWebEnginePage
        
        # Override the javaScriptConsoleMessage method
        page = self.web_view.page()
        page.javaScriptConsoleMessage = self._handle_console_message
        
        self.web_channel = QWebChannel()
        self.geo_bridge = GeoBridge()
        
        # State
        self.current_metadata: List[ExifToolMetadata] = []
        self._map_loaded = False
        
        self._create_ui()
        self._setup_web_channel()
        self._connect_signals()
        self._load_map()
    
    def _create_ui(self):
        """Create the widget UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create toolbar
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # Add web view
        layout.addWidget(self.web_view)
        
        # Status bar
        self.status_label = QLabel("Map initializing...")
        self.status_label.setMaximumHeight(20)
        layout.addWidget(self.status_label)
    
    def _create_toolbar(self) -> QToolBar:
        """
        Create map toolbar with controls
        
        Returns:
            Configured toolbar
        """
        toolbar = QToolBar()
        toolbar.setMovable(False)
        
        # View controls
        toolbar.addAction("🗺️ Map", lambda: self._set_map_type('roadmap'))
        toolbar.addAction("🛰️ Satellite", lambda: self._set_map_type('satellite'))
        toolbar.addAction("🏔️ Terrain", lambda: self._set_map_type('terrain'))
        toolbar.addSeparator()
        
        # Zoom controls
        toolbar.addAction("➕ Zoom In", self._zoom_in)
        toolbar.addAction("➖ Zoom Out", self._zoom_out)
        toolbar.addAction("🔄 Fit All", self._fit_all_markers)
        toolbar.addSeparator()
        
        # Export options
        toolbar.addAction("💾 Export HTML", lambda: self._export('html'))
        toolbar.addAction("🌍 Export KML", lambda: self._export('kml'))
        toolbar.addAction("🌐 Open in Browser", self._open_in_browser)
        toolbar.addSeparator()
        
        # Tools
        toolbar.addAction("📍 Show All", self._show_all_markers)
        toolbar.addAction("🔍 Search", self._search_location)
        toolbar.addAction("📊 Statistics", self._show_statistics)
        
        return toolbar
    
    def _setup_web_channel(self):
        """Setup Qt WebChannel for JavaScript communication"""
        # Register bridge object
        self.web_channel.registerObject("geoBridge", self.geo_bridge)
        
        # Set channel on page
        self.web_view.page().setWebChannel(self.web_channel)
        
        logger.info("WebChannel configured with geoBridge")
    
    def _handle_console_message(self, level, message, line, source):
        """Handle JavaScript console messages for debugging"""
        level_str = {0: "INFO", 1: "WARNING", 2: "ERROR"}.get(level, "DEBUG")
        logger.info(f"[JS {level_str}] {message} (line {line})")
        if source:
            logger.info(f"  Source: {source}")
    
    def _connect_signals(self):
        """Connect internal signals"""
        # Bridge signals
        self.geo_bridge.marker_clicked.connect(self._on_marker_clicked)
        self.geo_bridge.map_clicked.connect(self._on_map_clicked)
        self.geo_bridge.map_ready.connect(self._on_map_ready)
        self.geo_bridge.bounds_changed.connect(self._on_bounds_changed)
        self.geo_bridge.export_requested.connect(self._on_export_requested)
    
    def _load_map(self):
        """Load the map HTML template"""
        try:
            # Get map provider preference
            provider = settings.get('map_provider', 'leaflet')
            
            # Get QWebChannel JS script content
            qwebchannel_js = """
            var QWebChannel = QWebChannel || (function() {
                console.warn('QWebChannel not available, using stub');
                return function(transport, callback) {
                    callback({ objects: {} });
                };
            })();
            """
            
            # Try to load the actual QWebChannel script
            try:
                from PySide6.QtCore import QFile, QIODevice
                qrc_file = QFile(":/qtwebchannel/qwebchannel.js")
                if qrc_file.open(QIODevice.ReadOnly):
                    qwebchannel_js = str(qrc_file.readAll(), 'utf-8')
                    qrc_file.close()
                    logger.info("Loaded QWebChannel script from Qt resources")
            except Exception as e:
                logger.warning(f"Could not load QWebChannel script: {e}")
            
            # Prepare HTML with provider and inject QWebChannel script
            html_content = MAP_HTML_TEMPLATE.replace(
                '{{MAP_PROVIDER}}', provider
            ).replace(
                '<script src="qrc:///qtwebchannel/qwebchannel.js"></script>',
                f'<script>{qwebchannel_js}</script>'
            )
            
            # Load HTML directly without base URL to avoid resource conflicts
            self.web_view.setHtml(html_content)
            
            logger.info(f"Map HTML loaded with provider: {provider}")
            
        except Exception as e:
            logger.error(f"Failed to load map: {e}")
            self.status_label.setText(f"Map load failed: {str(e)}")
    
    def add_media_locations(self, metadata_list: List[ExifToolMetadata]):
        """
        Add media file locations to the map
        
        Args:
            metadata_list: List of ExifToolMetadata with GPS data
        """
        self.current_metadata = metadata_list
        
        # Debug logging
        logger.info(f"ADD_MEDIA_LOCATIONS: Received {len(metadata_list)} metadata objects")
        for metadata in metadata_list:
            logger.info(f"  - {metadata.file_path.name}: has_thumbnail={metadata.thumbnail_base64 is not None}")
        
        # Convert to marker format
        markers = []
        for metadata in metadata_list:
            if metadata.has_gps and metadata.gps_data:
                marker = self._metadata_to_marker(metadata)
                if marker:
                    markers.append(marker)
        
        if markers:
            # Clear existing and add new
            self.geo_bridge.clear_markers()
            self.geo_bridge.add_markers(markers)
            
            # Update map if loaded
            if self._map_loaded:
                self._update_map_markers()
            
            self.status_label.setText(f"Displaying {len(markers)} locations")
            logger.info(f"Added {len(markers)} markers to map")
        else:
            self.status_label.setText("No GPS data found in files")
    
    def _metadata_to_marker(self, metadata: ExifToolMetadata) -> Optional[Dict[str, Any]]:
        """
        Convert metadata to marker dictionary
        
        Args:
            metadata: ExifToolMetadata object
            
        Returns:
            Marker dictionary or None
        """
        if not metadata.gps_data:
            return None
        
        lat, lon = metadata.gps_data.to_decimal_degrees()
        
        marker = {
            'lat': lat,
            'lon': lon,
            'path': str(metadata.file_path),
            'filename': metadata.file_path.name,
            'type': self._get_file_type(metadata),
            'device': metadata.device_info.get_display_name() if metadata.device_info else 'Unknown',
            'device_id': metadata.device_info.get_primary_id() if metadata.device_info else None
        }
        
        # Add temporal data
        if metadata.temporal_data:
            timestamp = metadata.temporal_data.get_primary_timestamp()
            if timestamp:
                marker['time'] = timestamp.isoformat()
                marker['time_display'] = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        # Add additional GPS data
        if metadata.gps_data.altitude:
            marker['altitude'] = metadata.gps_data.altitude
        if metadata.gps_data.speed:
            marker['speed'] = metadata.gps_data.speed
        if metadata.gps_data.direction:
            marker['direction'] = metadata.gps_data.direction
        
        # Add thumbnail if available
        if metadata.thumbnail_base64:
            logger.info(f"ADDING THUMBNAIL to marker for {metadata.file_path.name}, type: {metadata.thumbnail_type}")
            marker['thumbnail'] = metadata.thumbnail_base64
            marker['thumbnail_type'] = metadata.thumbnail_type
        else:
            logger.debug(f"No thumbnail available for {metadata.file_path.name}")
        
        return marker
    
    def _get_file_type(self, metadata: ExifToolMetadata) -> str:
        """
        Determine file type for icon selection
        
        Args:
            metadata: File metadata
            
        Returns:
            File type string
        """
        if metadata.file_extension:
            ext = metadata.file_extension.lower()
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.heic']:
                return 'photo'
            elif ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv']:
                return 'video'
        
        # Check MIME type
        if metadata.mime_type:
            if 'image' in metadata.mime_type:
                return 'photo'
            elif 'video' in metadata.mime_type:
                return 'video'
        
        return 'file'
    
    def _update_map_markers(self):
        """Send marker update to JavaScript"""
        if self._map_loaded:
            # Get markers JSON
            markers_json = self.geo_bridge.get_markers_json()
            
            # Execute JavaScript to update markers
            js_code = f"window.mapController.updateMarkers({markers_json});"
            self.web_view.page().runJavaScript(js_code)
    
    def _on_map_ready(self):
        """Handle map ready signal"""
        self._map_loaded = True
        self.status_label.setText("Map ready")
        logger.info("Map initialized and ready")
        
        # Update markers if we have any
        if self.geo_bridge.get_marker_count() > 0:
            self._update_map_markers()
    
    def _on_marker_clicked(self, file_path: str):
        """
        Handle marker click
        
        Args:
            file_path: Path of associated file
        """
        logger.debug(f"Marker clicked: {file_path}")
        self.file_selected.emit(file_path)
    
    def _on_map_clicked(self, lat: float, lon: float):
        """
        Handle map click
        
        Args:
            lat: Latitude
            lon: Longitude
        """
        self.status_label.setText(f"Location: {lat:.6f}, {lon:.6f}")
    
    def _on_bounds_changed(self, min_lat: float, min_lon: float, max_lat: float, max_lon: float):
        """Handle map bounds change"""
        # Could be used for dynamic loading of markers
        pass
    
    def _on_export_requested(self, format_type: str):
        """
        Handle export request
        
        Args:
            format_type: Export format
        """
        self.export_requested.emit(format_type, '')
    
    def _set_map_type(self, map_type: str):
        """Change map type"""
        if self._map_loaded:
            js_code = f"window.mapController.setMapType('{map_type}');"
            self.web_view.page().runJavaScript(js_code)
    
    def _zoom_in(self):
        """Zoom in on map"""
        if self._map_loaded:
            self.web_view.page().runJavaScript("window.mapController.zoomIn();")
    
    def _zoom_out(self):
        """Zoom out on map"""
        if self._map_loaded:
            self.web_view.page().runJavaScript("window.mapController.zoomOut();")
    
    def _fit_all_markers(self):
        """Fit map to show all markers"""
        if self._map_loaded:
            self.web_view.page().runJavaScript("window.mapController.fitAllMarkers();")
    
    def _show_all_markers(self):
        """Show all markers"""
        if self._map_loaded:
            self.web_view.page().runJavaScript("window.mapController.showAllMarkers();")
    
    def _search_location(self):
        """Search for location (placeholder)"""
        # Could implement geocoding search
        QMessageBox.information(self, "Search", "Location search not yet implemented")
    
    def _show_statistics(self):
        """Show GPS statistics"""
        if not self.current_metadata:
            QMessageBox.information(self, "Statistics", "No data to analyze")
            return
        
        # Calculate statistics
        gps_count = sum(1 for m in self.current_metadata if m.has_gps)
        device_count = len(set(
            m.device_info.get_primary_id() 
            for m in self.current_metadata 
            if m.device_info and m.device_info.get_primary_id()
        ))
        
        stats_text = f"""GPS Statistics:
        
Files with GPS: {gps_count}
Unique devices: {device_count}
Total files: {len(self.current_metadata)}
        """
        
        QMessageBox.information(self, "GPS Statistics", stats_text)
    
    def _export(self, format_type: str):
        """
        Export map in specified format
        
        Args:
            format_type: Export format (html, kml)
        """
        self.export_requested.emit(format_type, '')
    
    def _open_in_browser(self):
        """Open current map in external browser"""
        if self._map_loaded:
            # Export as HTML and open
            self._export('html')
            # The actual opening would be handled by the controller
    
    def export_html(self, output_path: Path) -> bool:
        """
        Export map as standalone HTML
        
        Args:
            output_path: Path to save HTML
            
        Returns:
            True if successful
        """
        try:
            # Get current markers
            markers_json = self.geo_bridge.get_markers_json()
            
            # Create standalone HTML
            html = MAP_HTML_TEMPLATE.replace(
                '{{MAP_PROVIDER}}', 'leaflet'
            ).replace(
                'const MARKERS_DATA = undefined;', 
                f'const MARKERS_DATA = {markers_json};'
            )
            
            # Write to file
            output_path.write_text(html, encoding='utf-8')
            
            logger.info(f"Map exported to HTML: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export HTML: {e}")
            return False
    
    def clear_map(self):
        """Clear all markers from map"""
        self.geo_bridge.clear_markers()
        self.current_metadata.clear()
        
        if self._map_loaded:
            self.web_view.page().runJavaScript("window.mapController.clearMarkers();")
        
        self.status_label.setText("Map cleared")