"""
Forensic Transcoder data models.

This package contains all data models and enums used throughout the application.
"""

from .transcode_settings import (
    TranscodeSettings,
    QualityPreset,
    FPSMethod,
    ScalingAlgorithm,
)

from .concatenate_settings import (
    ConcatenateSettings,
    ConcatenationMode,
    TransitionType,
    SlatePosition,
)

from .video_analysis import (
    VideoAnalysis,
    AudioStreamInfo,
    SubtitleStreamInfo,
    StreamType,
    FrameRateType,
)

from .processing_result import (
    ProcessingResult,
    BatchProcessingStatistics,
    ProcessingStatus,
    ProcessingType,
)

__all__ = [
    # Transcode settings
    'TranscodeSettings',
    'QualityPreset',
    'FPSMethod',
    'ScalingAlgorithm',
    
    # Concatenate settings
    'ConcatenateSettings',
    'ConcatenationMode',
    'TransitionType',
    'SlatePosition',
    
    # Video analysis
    'VideoAnalysis',
    'AudioStreamInfo',
    'SubtitleStreamInfo',
    'StreamType',
    'FrameRateType',
    
    # Processing results
    'ProcessingResult',
    'BatchProcessingStatistics',
    'ProcessingStatus',
    'ProcessingType',
]
