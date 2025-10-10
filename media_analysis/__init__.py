#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Media Analysis Module - Forensic media file analysis with FFprobe and ExifTool

A self-contained, modular feature for extracting metadata from media files
using FFprobe (video/audio) and ExifTool (photos with GPS/EXIF data).

Features:
- FFprobe-based media metadata extraction
- ExifTool-based photo metadata and GPS extraction
- Interactive geolocation visualization with Leaflet maps
- Thumbnail extraction from EXIF data
- KML export for Google Earth
- CSV/JSON report generation

Architecture:
- Follows vehicle_tracking/ and filename_parser/ modular design
- Self-contained with optional registration in main app
- Clean service-oriented architecture with dependency injection
"""

__version__ = "1.0.0"
__author__ = "CFSA Development Team"

# Module-level imports for convenience
from .media_analysis_interfaces import (
    IMediaAnalysisService,
    IMediaAnalysisSuccessService
)

# Lazy import for MediaAnalysisTab to avoid circular imports
def __getattr__(name):
    if name == "MediaAnalysisTab":
        from .ui.media_analysis_tab import MediaAnalysisTab
        return MediaAnalysisTab
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "MediaAnalysisTab",
    "IMediaAnalysisService",
    "IMediaAnalysisSuccessService",
]


def register_services():
    """
    Register media analysis services with the application's service registry.

    This function is called automatically when the module is imported by main_window.py.
    It follows the optional registration pattern used by vehicle_tracking module.
    """
    from core.services import register_service, get_service
    from core.services.interfaces import IMediaAnalysisService, IMediaAnalysisSuccessService
    from core.logger import logger

    try:
        # Import implementations
        from .core.media_analysis_service import MediaAnalysisService
        from .core.media_analysis_success import MediaAnalysisSuccessBuilder

        # Register services
        register_service(IMediaAnalysisService, MediaAnalysisService())
        register_service(IMediaAnalysisSuccessService, MediaAnalysisSuccessBuilder())

        logger.info("Media Analysis module registered successfully")

    except Exception as e:
        logger.error(f"Failed to register Media Analysis services: {e}", exc_info=True)
        raise


# Auto-register when module is imported (optional module pattern)
try:
    register_services()
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(
        f"Media Analysis module loaded but service registration failed: {e}"
    )
