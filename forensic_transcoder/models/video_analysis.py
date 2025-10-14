"""
Video analysis data model.

Stores comprehensive metadata extracted from video files via FFprobe.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum


class StreamType(Enum):
    """Media stream types."""
    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"
    DATA = "data"


class FrameRateType(Enum):
    """Frame rate classification."""
    CONSTANT = "constant"  # CFR - Constant Frame Rate
    VARIABLE = "variable"  # VFR - Variable Frame Rate
    UNKNOWN = "unknown"


@dataclass
class AudioStreamInfo:
    """Information about an audio stream."""
    stream_index: int
    codec: str
    codec_long_name: str
    sample_rate: int
    channels: int
    channel_layout: Optional[str]
    bitrate: Optional[int]
    duration: Optional[float]


@dataclass
class SubtitleStreamInfo:
    """Information about a subtitle stream."""
    stream_index: int
    codec: str
    codec_long_name: str
    language: Optional[str]
    title: Optional[str]


@dataclass
class VideoAnalysis:
    """
    Comprehensive video file analysis results.
    
    Contains all metadata extracted from a video file including codec information,
    resolution, frame rate, audio streams, format details, and technical specifications.
    This data is used for compatibility checking, concatenation planning, and 
    transcode parameter determination.
    """
    
    # === File Information ===
    file_path: Path
    file_size: int  # Bytes
    format_name: str  # mp4, mkv, avi, etc.
    format_long_name: str  # Full format description
    
    # === Video Stream ===
    video_codec: str  # h264, hevc, vp9, etc.
    video_codec_long_name: str  # Full codec name
    width: int
    height: int
    pixel_format: str  # yuv420p, yuv422p, etc.
    
    # === Frame Rate ===
    fps: float  # Frames per second
    fps_string: str  # Original FPS string (e.g., "30000/1001")
    frame_rate_type: FrameRateType = FrameRateType.UNKNOWN
    avg_frame_rate: Optional[float] = None  # Average FPS (for VFR)
    
    # === Duration & Timing ===
    duration: float  # Total duration in seconds
    total_frames: Optional[int] = None
    start_time: Optional[float] = None  # Start time in seconds
    
    # === Bitrate ===
    overall_bitrate: Optional[int] = None  # Total bitrate in bps
    video_bitrate: Optional[int] = None  # Video stream bitrate
    
    # === Color & Format ===
    color_space: Optional[str] = None  # bt709, bt2020nc, etc.
    color_range: Optional[str] = None  # tv, pc
    color_primaries: Optional[str] = None
    color_transfer: Optional[str] = None
    
    # === Advanced Video Properties ===
    profile: Optional[str] = None  # Codec profile
    level: Optional[str] = None  # Codec level
    bit_depth: Optional[int] = None  # 8, 10, 12 bits
    has_b_frames: bool = False
    gop_size: Optional[int] = None  # Group of Pictures size
    
    # === Audio Streams ===
    audio_streams: List[AudioStreamInfo] = field(default_factory=list)
    
    # === Subtitle Streams ===
    subtitle_streams: List[SubtitleStreamInfo] = field(default_factory=list)
    
    # === Metadata ===
    creation_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # === Container Features ===
    has_chapters: bool = False
    chapter_count: int = 0
    
    # === Analysis Metadata ===
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    ffprobe_version: Optional[str] = None
    
    def __post_init__(self):
        """Ensure file_path is a Path object."""
        if not isinstance(self.file_path, Path):
            self.file_path = Path(self.file_path)
    
    @property
    def resolution_string(self) -> str:
        """Get resolution as string (e.g., '1920x1080')."""
        return f"{self.width}x{self.height}"
    
    @property
    def aspect_ratio(self) -> float:
        """Calculate aspect ratio."""
        return self.width / self.height if self.height > 0 else 0.0
    
    @property
    def duration_timedelta(self) -> timedelta:
        """Get duration as timedelta object."""
        return timedelta(seconds=self.duration)
    
    @property
    def has_audio(self) -> bool:
        """Check if file has audio streams."""
        return len(self.audio_streams) > 0
    
    @property
    def has_subtitles(self) -> bool:
        """Check if file has subtitle streams."""
        return len(self.subtitle_streams) > 0
    
    @property
    def is_vfr(self) -> bool:
        """Check if video has variable frame rate."""
        return self.frame_rate_type == FrameRateType.VARIABLE
    
    @property
    def is_hdr(self) -> bool:
        """Check if video is HDR (simple heuristic)."""
        if self.color_space in ['bt2020nc', 'bt2020c']:
            return True
        if self.color_transfer in ['smpte2084', 'arib-std-b67']:  # HDR10, HLG
            return True
        return False
    
    def get_spec_fingerprint(self) -> str:
        """
        Generate a fingerprint string for spec matching.
        
        Used to quickly compare if multiple videos have compatible specs
        for concatenation without re-encoding.
        
        Returns:
            String combining key specs: codec_widthxheight_fps_pixfmt
        """
        return (
            f"{self.video_codec}_"
            f"{self.width}x{self.height}_"
            f"{self.fps:.3f}_"
            f"{self.pixel_format}"
        )
    
    def is_compatible_with(self, other: 'VideoAnalysis', strict: bool = True) -> bool:
        """
        Check if this video is compatible with another for concatenation.
        
        Args:
            other: Another VideoAnalysis to compare with
            strict: If True, require exact match. If False, allow minor differences.
        
        Returns:
            True if videos can be concatenated without re-encoding
        """
        if strict:
            return (
                self.video_codec == other.video_codec and
                self.width == other.width and
                self.height == other.height and
                abs(self.fps - other.fps) < 0.01 and  # Allow tiny FPS difference
                self.pixel_format == other.pixel_format
            )
        else:
            # Allow minor FPS differences (within 1 fps)
            fps_compatible = abs(self.fps - other.fps) < 1.0
            
            # Same codec family
            codec_compatible = self.video_codec == other.video_codec
            
            # Same resolution
            resolution_compatible = (self.width == other.width and 
                                    self.height == other.height)
            
            return codec_compatible and resolution_compatible and fps_compatible
    
    def to_dict(self) -> dict:
        """Convert analysis to dictionary for serialization."""
        return {
            'file_path': str(self.file_path),
            'file_size': self.file_size,
            'format_name': self.format_name,
            'format_long_name': self.format_long_name,
            'video_codec': self.video_codec,
            'video_codec_long_name': self.video_codec_long_name,
            'width': self.width,
            'height': self.height,
            'pixel_format': self.pixel_format,
            'fps': self.fps,
            'fps_string': self.fps_string,
            'frame_rate_type': self.frame_rate_type.value,
            'avg_frame_rate': self.avg_frame_rate,
            'duration': self.duration,
            'total_frames': self.total_frames,
            'start_time': self.start_time,
            'overall_bitrate': self.overall_bitrate,
            'video_bitrate': self.video_bitrate,
            'color_space': self.color_space,
            'color_range': self.color_range,
            'color_primaries': self.color_primaries,
            'color_transfer': self.color_transfer,
            'profile': self.profile,
            'level': self.level,
            'bit_depth': self.bit_depth,
            'has_b_frames': self.has_b_frames,
            'gop_size': self.gop_size,
            'audio_streams': [
                {
                    'stream_index': s.stream_index,
                    'codec': s.codec,
                    'codec_long_name': s.codec_long_name,
                    'sample_rate': s.sample_rate,
                    'channels': s.channels,
                    'channel_layout': s.channel_layout,
                    'bitrate': s.bitrate,
                    'duration': s.duration,
                }
                for s in self.audio_streams
            ],
            'subtitle_streams': [
                {
                    'stream_index': s.stream_index,
                    'codec': s.codec,
                    'codec_long_name': s.codec_long_name,
                    'language': s.language,
                    'title': s.title,
                }
                for s in self.subtitle_streams
            ],
            'creation_time': self.creation_time.isoformat() if self.creation_time else None,
            'metadata': self.metadata,
            'has_chapters': self.has_chapters,
            'chapter_count': self.chapter_count,
            'analysis_timestamp': self.analysis_timestamp.isoformat(),
            'ffprobe_version': self.ffprobe_version,
        }
