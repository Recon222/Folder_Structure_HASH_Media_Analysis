#!/usr/bin/env python3
"""
Data models for media analysis operations
Defines structures for settings, metadata, and results
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any


class FileReferenceFormat(Enum):
    """How to display file paths in reports"""
    FULL_PATH = "full_path"
    PARENT_AND_NAME = "parent_name"
    NAME_ONLY = "name_only"


@dataclass
class MetadataFieldGroup:
    """Group of metadata fields with enable state"""
    enabled: bool = True
    fields: Dict[str, bool] = field(default_factory=dict)
    
    def is_field_enabled(self, field_name: str) -> bool:
        """Check if a specific field is enabled"""
        return self.enabled and self.fields.get(field_name, True)


@dataclass
class MediaAnalysisSettings:
    """Settings for media analysis operation"""
    # Field groups
    general_fields: MetadataFieldGroup = field(default_factory=lambda: MetadataFieldGroup(
        enabled=True,
        fields={
            "format": True,
            "duration": True,
            "file_size": True,
            "bitrate": True,
            "creation_date": True
        }
    ))
    
    video_fields: MetadataFieldGroup = field(default_factory=lambda: MetadataFieldGroup(
        enabled=True,
        fields={
            "video_codec": True,
            "resolution": True,
            "frame_rate": True,
            "aspect_ratio": True,
            "color_space": True
        }
    ))
    
    audio_fields: MetadataFieldGroup = field(default_factory=lambda: MetadataFieldGroup(
        enabled=True,
        fields={
            "audio_codec": True,
            "sample_rate": True,
            "channels": True,
            "bit_depth": True
        }
    ))
    
    creation_fields: MetadataFieldGroup = field(default_factory=lambda: MetadataFieldGroup(
        enabled=True,
        fields={
            "creation_date": True,
            "modification_date": True,
            "encoding_date": True
        }
    ))
    
    location_fields: MetadataFieldGroup = field(default_factory=lambda: MetadataFieldGroup(
        enabled=False,  # Disabled by default for privacy
        fields={
            "gps_latitude": True,
            "gps_longitude": True,
            "location_name": True
        }
    ))
    
    device_fields: MetadataFieldGroup = field(default_factory=lambda: MetadataFieldGroup(
        enabled=True,
        fields={
            "device_make": True,
            "device_model": True,
            "software": True
        }
    ))
    
    # Advanced Video Analysis (NEW) - Off by default for performance
    advanced_video_fields: MetadataFieldGroup = field(default_factory=lambda: MetadataFieldGroup(
        enabled=False,
        fields={
            "profile": False,
            "level": False,
            "pixel_format": False,
            "sample_aspect_ratio": False,
            "pixel_aspect_ratio": False,
            "color_range": False,
            "color_transfer": False,
            "color_primaries": False
        }
    ))
    
    # GOP & Frame Analysis (NEW) - Very expensive, off by default
    frame_analysis_fields: MetadataFieldGroup = field(default_factory=lambda: MetadataFieldGroup(
        enabled=False,
        fields={
            "gop_structure": False,
            "keyframe_interval": False,
            "frame_type_distribution": False,
            "i_frame_count": False,
            "p_frame_count": False,
            "b_frame_count": False
        }
    ))
    
    # Display options
    file_reference_format: FileReferenceFormat = FileReferenceFormat.FULL_PATH
    
    # Processing options
    skip_non_media: bool = True
    timeout_seconds: float = 5.0
    max_workers: int = 8
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary for persistence"""
        return {
            "general_fields": {
                "enabled": self.general_fields.enabled,
                "fields": self.general_fields.fields
            },
            "video_fields": {
                "enabled": self.video_fields.enabled,
                "fields": self.video_fields.fields
            },
            "audio_fields": {
                "enabled": self.audio_fields.enabled,
                "fields": self.audio_fields.fields
            },
            "creation_fields": {
                "enabled": self.creation_fields.enabled,
                "fields": self.creation_fields.fields
            },
            "location_fields": {
                "enabled": self.location_fields.enabled,
                "fields": self.location_fields.fields
            },
            "device_fields": {
                "enabled": self.device_fields.enabled,
                "fields": self.device_fields.fields
            },
            "advanced_video_fields": {
                "enabled": self.advanced_video_fields.enabled,
                "fields": self.advanced_video_fields.fields
            },
            "frame_analysis_fields": {
                "enabled": self.frame_analysis_fields.enabled,
                "fields": self.frame_analysis_fields.fields
            },
            "file_reference_format": self.file_reference_format.value,
            "skip_non_media": self.skip_non_media,
            "timeout_seconds": self.timeout_seconds,
            "max_workers": self.max_workers
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MediaAnalysisSettings':
        """Create settings from dictionary"""
        settings = cls()
        
        if "general_fields" in data:
            settings.general_fields = MetadataFieldGroup(
                enabled=data["general_fields"].get("enabled", True),
                fields=data["general_fields"].get("fields", {})
            )
        
        if "video_fields" in data:
            settings.video_fields = MetadataFieldGroup(
                enabled=data["video_fields"].get("enabled", True),
                fields=data["video_fields"].get("fields", {})
            )
        
        if "audio_fields" in data:
            settings.audio_fields = MetadataFieldGroup(
                enabled=data["audio_fields"].get("enabled", True),
                fields=data["audio_fields"].get("fields", {})
            )
        
        if "creation_fields" in data:
            settings.creation_fields = MetadataFieldGroup(
                enabled=data["creation_fields"].get("enabled", True),
                fields=data["creation_fields"].get("fields", {})
            )
        
        if "location_fields" in data:
            settings.location_fields = MetadataFieldGroup(
                enabled=data["location_fields"].get("enabled", False),
                fields=data["location_fields"].get("fields", {})
            )
        
        if "device_fields" in data:
            settings.device_fields = MetadataFieldGroup(
                enabled=data["device_fields"].get("enabled", True),
                fields=data["device_fields"].get("fields", {})
            )
        
        if "advanced_video_fields" in data:
            settings.advanced_video_fields = MetadataFieldGroup(
                enabled=data["advanced_video_fields"].get("enabled", False),
                fields=data["advanced_video_fields"].get("fields", {})
            )
        
        if "frame_analysis_fields" in data:
            settings.frame_analysis_fields = MetadataFieldGroup(
                enabled=data["frame_analysis_fields"].get("enabled", False),
                fields=data["frame_analysis_fields"].get("fields", {})
            )
        
        if "file_reference_format" in data:
            try:
                settings.file_reference_format = FileReferenceFormat(data["file_reference_format"])
            except ValueError:
                pass  # Keep default
        
        settings.skip_non_media = data.get("skip_non_media", True)
        settings.timeout_seconds = data.get("timeout_seconds", 5.0)
        settings.max_workers = data.get("max_workers", 8)
        
        return settings


@dataclass
class MediaMetadata:
    """Normalized metadata for a single media file"""
    file_path: Path
    file_size: int
    
    # General information
    format: Optional[str] = None
    format_long: Optional[str] = None
    duration: Optional[float] = None  # in seconds
    bitrate: Optional[int] = None  # in bits per second
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    
    # Video stream information
    has_video: bool = False
    video_codec: Optional[str] = None
    video_codec_long: Optional[str] = None
    resolution: Optional[Tuple[int, int]] = None  # (width, height)
    frame_rate: Optional[float] = None
    aspect_ratio: Optional[str] = None  # Display aspect ratio (DAR)
    color_space: Optional[str] = None
    video_bitrate: Optional[int] = None
    
    # Enhanced Aspect Ratio Support (NEW)
    sample_aspect_ratio: Optional[str] = None  # SAR
    pixel_aspect_ratio: Optional[str] = None   # PAR (usually same as SAR)
    display_aspect_ratio: Optional[str] = None  # DAR (more explicit than aspect_ratio)
    
    # Advanced Video Properties (NEW)
    profile: Optional[str] = None
    level: Optional[str] = None
    pixel_format: Optional[str] = None
    color_range: Optional[str] = None
    color_transfer: Optional[str] = None
    color_primaries: Optional[str] = None
    
    # GOP Structure & Frame Analysis (NEW)
    gop_size: Optional[int] = None
    keyframe_interval: Optional[float] = None  # Average seconds between keyframes
    i_frame_count: Optional[int] = None
    p_frame_count: Optional[int] = None
    b_frame_count: Optional[int] = None
    frame_type_distribution: Optional[Dict[str, int]] = None
    
    # Audio stream information
    has_audio: bool = False
    audio_codec: Optional[str] = None
    audio_codec_long: Optional[str] = None
    sample_rate: Optional[int] = None  # in Hz
    channels: Optional[int] = None
    channel_layout: Optional[str] = None  # e.g., "stereo", "5.1"
    audio_bitrate: Optional[int] = None
    bit_depth: Optional[int] = None
    
    # Location information (EXIF/metadata)
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    location_name: Optional[str] = None
    
    # Device information
    device_make: Optional[str] = None
    device_model: Optional[str] = None
    software: Optional[str] = None
    
    # Additional metadata
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    comment: Optional[str] = None
    
    # Raw data for debugging/advanced use
    raw_json: Optional[Dict] = None
    error: Optional[str] = None
    
    # Performance Metrics (NEW)
    extraction_time: Optional[float] = None  # Time taken to extract metadata
    command_complexity: Optional[int] = None  # Number of fields requested
    
    def get_display_path(self, format_type: FileReferenceFormat) -> str:
        """Get formatted path for display based on settings"""
        if format_type == FileReferenceFormat.NAME_ONLY:
            return self.file_path.name
        elif format_type == FileReferenceFormat.PARENT_AND_NAME:
            return f"{self.file_path.parent.name}/{self.file_path.name}"
        else:  # FULL_PATH
            return str(self.file_path)
    
    def get_duration_string(self) -> str:
        """Get formatted duration string (HH:MM:SS)"""
        if self.duration is None:
            return "N/A"
        
        hours = int(self.duration // 3600)
        minutes = int((self.duration % 3600) // 60)
        seconds = int(self.duration % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    def get_resolution_string(self) -> str:
        """Get formatted resolution string"""
        if self.resolution:
            return f"{self.resolution[0]}x{self.resolution[1]}"
        return "N/A"
    
    def get_file_size_string(self) -> str:
        """Get human-readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"


@dataclass
class MediaAnalysisResult:
    """Results from media analysis operation"""
    total_files: int
    successful: int
    failed: int
    skipped: int
    metadata_list: List[MediaMetadata]
    processing_time: float
    errors: List[str]
    
    # Performance metrics
    files_per_second: float = 0.0
    average_extraction_time: float = 0.0
    
    def __post_init__(self):
        """Calculate performance metrics"""
        if self.processing_time > 0 and self.total_files > 0:
            self.files_per_second = self.total_files / self.processing_time
            self.average_extraction_time = self.processing_time / self.total_files
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics"""
        return {
            "total_files": self.total_files,
            "successful": self.successful,
            "failed": self.failed,
            "skipped": self.skipped,
            "success_rate": (self.successful / self.total_files * 100) if self.total_files > 0 else 0,
            "processing_time": self.processing_time,
            "files_per_second": self.files_per_second,
            "error_count": len(self.errors)
        }
    
    def get_format_statistics(self) -> Dict[str, int]:
        """Get statistics by file format"""
        format_counts = {}
        for metadata in self.metadata_list:
            if metadata.format:
                format_counts[metadata.format] = format_counts.get(metadata.format, 0) + 1
        return format_counts
    
    def get_codec_statistics(self) -> Dict[str, Dict[str, int]]:
        """Get statistics by codec type"""
        stats = {
            "video_codecs": {},
            "audio_codecs": {}
        }
        
        for metadata in self.metadata_list:
            if metadata.video_codec:
                stats["video_codecs"][metadata.video_codec] = \
                    stats["video_codecs"].get(metadata.video_codec, 0) + 1
            if metadata.audio_codec:
                stats["audio_codecs"][metadata.audio_codec] = \
                    stats["audio_codecs"].get(metadata.audio_codec, 0) + 1
        
        return stats