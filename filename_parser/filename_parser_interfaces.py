"""
Service interfaces for the filename parser module.

These interfaces define the contracts for services within the filename parser module,
allowing for dependency injection and testability.
"""

from abc import abstractmethod
from typing import List, Optional, Dict, Any, Callable
from pathlib import Path

from core.services.interfaces import IService
from core.result_types import Result
from filename_parser.models.pattern_models import PatternDefinition
from filename_parser.models.time_models import ParseResult
from filename_parser.models.processing_result import ProcessingStatistics
from filename_parser.models.filename_parser_models import FilenameParserSettings


class IFilenameParserService(IService):
    """Interface for filename parser service"""

    @abstractmethod
    def parse_filename(
        self,
        filename: str,
        pattern_id: Optional[str] = None,
        fps: Optional[float] = None,
        time_offset: Optional[Dict[str, Any]] = None
    ) -> Result[ParseResult]:
        """
        Parse filename and extract time information.

        Args:
            filename: Filename to parse
            pattern_id: Optional specific pattern ID to use
            fps: Optional frame rate for SMPTE conversion
            time_offset: Optional time offset to apply

        Returns:
            Result containing ParseResult or error
        """
        pass

    @abstractmethod
    def get_available_patterns(self) -> List[PatternDefinition]:
        """
        Get all available patterns.

        Returns:
            List of PatternDefinition objects
        """
        pass

    @abstractmethod
    def search_patterns(
        self,
        query: str = None,
        category: str = None
    ) -> List[PatternDefinition]:
        """
        Search patterns by criteria.

        Args:
            query: Search in name/description
            category: Filter by category

        Returns:
            List of matching PatternDefinition objects
        """
        pass


class IFrameRateService(IService):
    """Interface for frame rate detection service"""

    @abstractmethod
    def detect_frame_rate(
        self,
        file_path: Path,
        progress_callback: Optional[Callable] = None
    ) -> Result[float]:
        """
        Detect frame rate from video file.

        Args:
            file_path: Path to video file
            progress_callback: Optional progress callback

        Returns:
            Result containing frame rate or error
        """
        pass

    @abstractmethod
    def detect_batch_frame_rates(
        self,
        file_paths: List[Path],
        use_default_on_failure: bool = True,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, float]:
        """
        Detect frame rates for multiple files.

        Args:
            file_paths: List of file paths
            use_default_on_failure: Use default FPS on detection failure
            progress_callback: Optional progress callback

        Returns:
            Dictionary mapping file paths to frame rates
        """
        pass


class IFFmpegMetadataWriterService(IService):
    """Interface for FFmpeg metadata writing service"""

    @abstractmethod
    def write_smpte_metadata(
        self,
        video_path: Path,
        smpte_timecode: str,
        fps: float,
        project_root: Optional[str] = None
    ) -> Result[Path]:
        """
        Write SMPTE timecode to video file.

        Args:
            video_path: Path to video file
            smpte_timecode: SMPTE timecode string
            fps: Frame rate
            project_root: Optional project root for mirrored structure

        Returns:
            Result containing output file path or error
        """
        pass

    @abstractmethod
    def is_ffmpeg_available(self) -> bool:
        """
        Check if FFmpeg is available.

        Returns:
            True if FFmpeg is available
        """
        pass


class IBatchProcessorService(IService):
    """Interface for batch processing service"""

    @abstractmethod
    def process_files(
        self,
        files: List[Path],
        settings: FilenameParserSettings,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Result[ProcessingStatistics]:
        """
        Process multiple files in batch.

        Args:
            files: List of file paths
            settings: Processing settings
            progress_callback: Optional progress callback (percentage, message)

        Returns:
            Result containing ProcessingStatistics or error
        """
        pass

    @abstractmethod
    def cancel_processing(self):
        """Cancel current batch processing"""
        pass
