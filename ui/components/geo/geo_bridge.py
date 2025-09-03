#!/usr/bin/env python3
"""
GeoBridge - Qt/JavaScript bridge for map communication
Enables bidirectional communication between Python and web map
"""

from typing import List, Dict, Any, Optional
from PySide6.QtCore import QObject, Slot, Signal
import json

from core.logger import logger
from core.settings_manager import settings


class GeoBridge(QObject):
    """
    Bridge between Python and JavaScript map
    Handles all communication with the web-based map component
    """
    
    # Signals for Python-side events
    marker_clicked = Signal(str)  # file_path
    map_clicked = Signal(float, float)  # lat, lon
    export_requested = Signal(str)  # format
    map_ready = Signal()  # Map finished loading
    bounds_changed = Signal(float, float, float, float)  # min_lat, min_lon, max_lat, max_lon
    
    def __init__(self):
        """Initialize the geo bridge"""
        super().__init__()
        self._markers = []
        self._current_bounds = None
        self._map_loaded = False
        logger.info("GeoBridge initialized")
    
    @Slot()
    def on_map_ready(self):
        """Called when JavaScript map is fully loaded"""
        self._map_loaded = True
        logger.info("Map ready signal received from JavaScript")
        self.map_ready.emit()
    
    @Slot(str)
    def on_marker_click(self, file_path: str):
        """
        Handle marker click from JavaScript
        
        Args:
            file_path: Path of the file associated with clicked marker
        """
        logger.debug(f"Marker clicked: {file_path}")
        self.marker_clicked.emit(file_path)
    
    @Slot(float, float)
    def on_map_click(self, lat: float, lon: float):
        """
        Handle map click from JavaScript
        
        Args:
            lat: Latitude of click location
            lon: Longitude of click location
        """
        logger.debug(f"Map clicked at: {lat}, {lon}")
        self.map_clicked.emit(lat, lon)
    
    @Slot(float, float, float, float)
    def on_bounds_change(self, min_lat: float, min_lon: float, max_lat: float, max_lon: float):
        """
        Handle map bounds change from JavaScript
        
        Args:
            min_lat: Minimum latitude
            min_lon: Minimum longitude
            max_lat: Maximum latitude
            max_lon: Maximum longitude
        """
        self._current_bounds = (min_lat, min_lon, max_lat, max_lon)
        self.bounds_changed.emit(min_lat, min_lon, max_lat, max_lon)
    
    @Slot(str)
    def request_export(self, format_type: str):
        """
        Handle export request from JavaScript
        
        Args:
            format_type: Export format (html, kml, etc.)
        """
        logger.info(f"Export requested: {format_type}")
        self.export_requested.emit(format_type)
    
    @Slot(str, result=str)
    def get_api_key(self, provider: str) -> str:
        """
        Securely provide API key to JavaScript
        
        Args:
            provider: Map provider name
            
        Returns:
            API key for the provider
        """
        # Get from secure settings
        api_keys = settings.get('map_api_keys', {})
        key = api_keys.get(provider, '')
        
        if not key and provider == 'leaflet':
            # Leaflet/OpenStreetMap doesn't need API key
            return ''
        
        return key
    
    @Slot(result=str)
    def get_map_provider(self) -> str:
        """
        Get current map provider preference
        
        Returns:
            Map provider name
        """
        return settings.get('map_provider', 'leaflet')
    
    @Slot(result=str)
    def get_tile_server(self) -> str:
        """
        Get custom tile server URL if configured
        
        Returns:
            Tile server URL or empty string
        """
        return settings.get('custom_tile_server', '')
    
    @Slot(result=bool)
    def get_clustering_enabled(self) -> bool:
        """
        Check if marker clustering is enabled
        
        Returns:
            True if clustering should be used
        """
        return settings.get('map_clustering', True)
    
    @Slot(result=int)
    def get_privacy_level(self) -> int:
        """
        Get GPS privacy level setting
        
        Returns:
            Privacy level (0=exact, 1=building, 2=block, 3=neighborhood)
        """
        return settings.get('gps_privacy_level', 0)
    
    def add_markers(self, markers: List[Dict[str, Any]]):
        """
        Add markers to the map from Python
        
        Args:
            markers: List of marker dictionaries with lat, lon, path, etc.
        """
        self._markers.extend(markers)
        # Markers will be sent when JavaScript requests them
        logger.info(f"Added {len(markers)} markers to bridge")
    
    @Slot(result=str)
    def get_markers_json(self) -> str:
        """
        Get all markers as JSON for JavaScript
        
        Returns:
            JSON string of marker data
        """
        return json.dumps(self._markers)
    
    def clear_markers(self):
        """Clear all markers"""
        self._markers.clear()
        logger.debug("Markers cleared")
    
    def get_marker_count(self) -> int:
        """Get current number of markers"""
        return len(self._markers)
    
    def is_map_loaded(self) -> bool:
        """Check if map is loaded and ready"""
        return self._map_loaded