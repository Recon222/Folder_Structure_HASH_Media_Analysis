#!/usr/bin/env python3
"""
Geolocation visualization components
Interactive map widgets for displaying GPS data from media files
"""

from .geo_visualization_widget import GeoVisualizationWidget
from .geo_bridge import GeoBridge

__all__ = ['GeoVisualizationWidget', 'GeoBridge']