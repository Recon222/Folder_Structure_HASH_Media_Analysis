"""
Transcode settings data model.

Defines configuration parameters for video transcoding jobs.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
from enum import Enum


class QualityPreset(Enum):
    """Forensic quality presets."""
    LOSSLESS_FORENSIC = "lossless_forensic"
    HIGH_FORENSIC = "high_forensic"
    MEDIUM_FORENSIC = "medium_forensic"
    WEB_DELIVERY = "web_delivery"
    CUSTOM = "custom"


class FPSMethod(Enum):
    """Frame rate adjustment methods."""
    DUPLICATE = "duplicate"  # Duplicate/drop frames to match target FPS
    PTS_ADJUST = "pts_adjust"  # Adjust presentation timestamps (changes speed)
    AUTO = "auto"  # Let service decide based on analysis


class ScalingAlgorithm(Enum):
    """Video scaling algorithms."""
    LANCZOS = "lanczos"
    BICUBIC = "bicubic"
    BILINEAR = "bilinear"
    NEIGHBOR = "neighbor"
    SPLINE = "spline"


@dataclass
class TranscodeSettings:
    """
    Configuration for video transcoding job.
    
    This model contains all parameters needed to configure a transcode operation,
    including output format, codec selection, quality settings, frame rate adjustments,
    audio handling, and hardware acceleration options.
    """
    
    # === Output Configuration ===
    output_format: str = "mp4"  # mp4, mkv, mov, avi, webm
    output_directory: Optional[Path] = None
    output_filename_pattern: str = "{original_name}_transcoded.{ext}"
    overwrite_existing: bool = False
    
    # === Video Codec ===
    video_codec: str = "libx264"  # libx264, libx265, hevc_nvenc, h264_nvenc, etc.
    
    # === Quality Settings ===
    quality_preset: QualityPreset = QualityPreset.HIGH_FORENSIC
    crf: Optional[int] = None  # Constant Rate Factor (0-51, lower = better quality)
    preset: Optional[str] = None  # Encoding speed preset (ultrafast to veryslow)
    tune: Optional[str] = None  # Tuning option (film, animation, grain, etc.)
    profile: Optional[str] = None  # Codec profile (baseline, main, high, etc.)
    level: Optional[str] = None  # Codec level (3.0, 3.1, 4.0, etc.)
    
    # === Resolution & Scaling ===
    output_width: Optional[int] = None
    output_height: Optional[int] = None
    scaling_algorithm: ScalingAlgorithm = ScalingAlgorithm.LANCZOS
    maintain_aspect_ratio: bool = True
    
    # === Frame Rate ===
    target_fps: Optional[float] = None
    fps_method: FPSMethod = FPSMethod.AUTO
    analyze_vfr: bool = True  # Detect variable frame rate
    
    # === Audio Settings ===
    audio_codec: str = "copy"  # copy, aac, mp3, opus, ac3
    audio_bitrate: Optional[str] = None  # 128k, 192k, 256k, 320k
    audio_sample_rate: Optional[int] = None  # 44100, 48000
    audio_channels: Optional[int] = None  # 1 (mono), 2 (stereo), 6 (5.1)
    
    # === Hardware Acceleration ===
    use_hardware_encoder: bool = False
    use_hardware_decoder: bool = False
    gpu_index: int = 0  # For multi-GPU systems
    
    # === Advanced Video Settings ===
    pixel_format: Optional[str] = None  # yuv420p, yuv420p10le, yuv444p, etc.
    color_space: Optional[str] = None  # bt709, bt2020nc, etc.
    color_range: Optional[str] = None  # tv, pc
    bitrate: Optional[str] = None  # For CBR/VBR modes: 5M, 10M, etc.
    max_bitrate: Optional[str] = None  # Maximum bitrate for VBR
    buffer_size: Optional[str] = None  # Rate control buffer size
    
    # === Metadata ===
    preserve_metadata: bool = True
    preserve_timestamps: bool = True
    copy_chapters: bool = True
    
    # === Filters ===
    deinterlace: bool = False
    custom_video_filters: List[str] = field(default_factory=list)
    custom_audio_filters: List[str] = field(default_factory=list)
    
    # === Processing Options ===
    max_parallel_jobs: int = 4  # For batch processing
    two_pass_encoding: bool = False
    
    # === Subtitle Handling ===
    copy_subtitles: bool = True
    burn_subtitles: bool = False
    subtitle_track: Optional[int] = None  # Which subtitle track to burn (if burn_subtitles=True)
    
    def __post_init__(self):
        """Validate settings after initialization."""
        # Ensure output_directory is Path object
        if self.output_directory and not isinstance(self.output_directory, Path):
            self.output_directory = Path(self.output_directory)
        
        # Validate CRF range
        if self.crf is not None:
            if not (0 <= self.crf <= 51):
                raise ValueError(f"CRF must be between 0 and 51, got {self.crf}")
        
        # Validate FPS
        if self.target_fps is not None:
            if not (1.0 <= self.target_fps <= 240.0):
                raise ValueError(f"Target FPS must be between 1 and 240, got {self.target_fps}")
        
        # Validate resolution
        if self.output_width is not None and self.output_width <= 0:
            raise ValueError(f"Output width must be positive, got {self.output_width}")
        if self.output_height is not None and self.output_height <= 0:
            raise ValueError(f"Output height must be positive, got {self.output_height}")
        
        # Validate parallel jobs
        if self.max_parallel_jobs < 1:
            raise ValueError(f"max_parallel_jobs must be at least 1, got {self.max_parallel_jobs}")
    
    def to_dict(self) -> dict:
        """Convert settings to dictionary for serialization."""
        return {
            'output_format': self.output_format,
            'output_directory': str(self.output_directory) if self.output_directory else None,
            'output_filename_pattern': self.output_filename_pattern,
            'overwrite_existing': self.overwrite_existing,
            'video_codec': self.video_codec,
            'quality_preset': self.quality_preset.value,
            'crf': self.crf,
            'preset': self.preset,
            'tune': self.tune,
            'profile': self.profile,
            'level': self.level,
            'output_width': self.output_width,
            'output_height': self.output_height,
            'scaling_algorithm': self.scaling_algorithm.value,
            'maintain_aspect_ratio': self.maintain_aspect_ratio,
            'target_fps': self.target_fps,
            'fps_method': self.fps_method.value,
            'analyze_vfr': self.analyze_vfr,
            'audio_codec': self.audio_codec,
            'audio_bitrate': self.audio_bitrate,
            'audio_sample_rate': self.audio_sample_rate,
            'audio_channels': self.audio_channels,
            'use_hardware_encoder': self.use_hardware_encoder,
            'use_hardware_decoder': self.use_hardware_decoder,
            'gpu_index': self.gpu_index,
            'pixel_format': self.pixel_format,
            'color_space': self.color_space,
            'color_range': self.color_range,
            'bitrate': self.bitrate,
            'max_bitrate': self.max_bitrate,
            'buffer_size': self.buffer_size,
            'preserve_metadata': self.preserve_metadata,
            'preserve_timestamps': self.preserve_timestamps,
            'copy_chapters': self.copy_chapters,
            'deinterlace': self.deinterlace,
            'custom_video_filters': self.custom_video_filters,
            'custom_audio_filters': self.custom_audio_filters,
            'max_parallel_jobs': self.max_parallel_jobs,
            'two_pass_encoding': self.two_pass_encoding,
            'copy_subtitles': self.copy_subtitles,
            'burn_subtitles': self.burn_subtitles,
            'subtitle_track': self.subtitle_track,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TranscodeSettings':
        """Create settings from dictionary."""
        # Convert enum strings back to enums
        if 'quality_preset' in data:
            data['quality_preset'] = QualityPreset(data['quality_preset'])
        if 'fps_method' in data:
            data['fps_method'] = FPSMethod(data['fps_method'])
        if 'scaling_algorithm' in data:
            data['scaling_algorithm'] = ScalingAlgorithm(data['scaling_algorithm'])
        if 'output_directory' in data and data['output_directory']:
            data['output_directory'] = Path(data['output_directory'])
        
        return cls(**data)
