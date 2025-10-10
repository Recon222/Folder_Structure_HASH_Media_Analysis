#!/usr/bin/env python3
"""
Media analysis module for the Folder Structure Application
Provides FFprobe integration for extracting metadata from media files
"""

from .ffprobe_binary_manager import FFProbeBinaryManager
from .ffprobe_wrapper import FFProbeWrapper
from .metadata_normalizer import MetadataNormalizer

__all__ = [
    'FFProbeBinaryManager',
    'FFProbeWrapper',
    'MetadataNormalizer'
]