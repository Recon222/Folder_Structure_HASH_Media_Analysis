#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Media Analysis Interfaces - Service contracts for media analysis functionality

Defines the interfaces that media analysis services must implement.
These are duplicated here for module self-containment while still being
compatible with the main application's service registry.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict, Any

from core.result_types import Result


class IMediaAnalysisService(ABC):
    """Interface for media analysis operations using FFprobe"""

    @abstractmethod
    def analyze_files(
        self,
        file_paths: List[Path],
        settings: Any,  # MediaAnalysisSettings
        progress_callback: Optional[callable] = None
    ) -> Result:
        """
        Analyze media files and extract metadata using FFprobe

        Args:
            file_paths: List of media file paths to analyze
            settings: Analysis settings configuration
            progress_callback: Optional callback for progress updates

        Returns:
            Result object containing MediaAnalysisResult or error
        """
        pass


class IMediaAnalysisSuccessService(ABC):
    """Interface for building media analysis success messages"""

    @abstractmethod
    def build_ffprobe_message(self, operation_data: Any) -> Any:
        """Build success message for FFprobe operation"""
        pass

    @abstractmethod
    def build_exiftool_message(self, operation_data: Any) -> Any:
        """Build success message for ExifTool operation"""
        pass
