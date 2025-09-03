#!/usr/bin/env python3
"""
ExifTool integration package for forensic metadata extraction
Provides GPS extraction, device identification, and temporal analysis
"""

from .exiftool_binary_manager import ExifToolBinaryManager
from .exiftool_command_builder import ExifToolForensicCommandBuilder
from .exiftool_wrapper import ExifToolWrapper
from .exiftool_normalizer import ExifToolNormalizer
from .exiftool_models import (
    GPSData,
    ExifToolMetadata,
    ExifToolAnalysisResult,
    ExifToolSettings,
    DeviceInfo,
    TemporalData
)

__all__ = [
    'ExifToolBinaryManager',
    'ExifToolForensicCommandBuilder', 
    'ExifToolWrapper',
    'ExifToolNormalizer',
    'GPSData',
    'ExifToolMetadata',
    'ExifToolAnalysisResult',
    'ExifToolSettings',
    'DeviceInfo',
    'TemporalData'
]