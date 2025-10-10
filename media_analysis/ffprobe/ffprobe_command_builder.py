#!/usr/bin/env python3
"""
FFprobe command builder for optimized metadata extraction
Dynamically builds commands based on user-selected fields only
Following the pattern established by ForensicCommandBuilder
"""

from pathlib import Path
from typing import List, Dict, Any, Set, Tuple
from core.logger import logger


class FFProbeCommandBuilder:
    """
    Builds optimized FFprobe commands based on user settings
    Pattern follows ForensicCommandBuilder for consistency
    """
    
    # Comprehensive field mappings to FFprobe parameters
    FIELD_MAPPINGS = {
        # General Information
        'format': {
            'format': ['format_name', 'format_long_name'],
            'stream': []
        },
        'duration': {
            'format': ['duration'],
            'stream': ['duration']  # Some formats have stream duration
        },
        'file_size': {
            'format': ['size'],
            'stream': []
        },
        'bitrate': {
            'format': ['bit_rate'],
            'stream': []
        },
        'creation_date': {
            'format': [],
            'tags': ['creation_time', 'date', 'com.apple.quicktime.creationdate']
        },
        
        # Video Stream Properties
        'video_codec': {
            'format': [],
            'stream': ['codec_name', 'codec_long_name', 'codec_tag_string']
        },
        'resolution': {
            'format': [],
            'stream': ['width', 'height']
        },
        'frame_rate': {
            'format': [],
            'stream': ['avg_frame_rate', 'r_frame_rate', 'time_base']
        },
        'aspect_ratio': {
            'format': [],
            'stream': ['display_aspect_ratio', 'sample_aspect_ratio', 'sar']
        },
        'color_space': {
            'format': [],
            'stream': ['color_space', 'color_range', 'color_transfer', 'color_primaries', 'pix_fmt']
        },
        
        # Advanced Video Properties
        'profile': {
            'format': [],
            'stream': ['profile', 'level']
        },
        'bit_depth': {
            'format': [],
            'stream': ['bits_per_raw_sample', 'bits_per_sample']
        },
        'sample_aspect_ratio': {
            'format': [],
            'stream': ['sample_aspect_ratio', 'sar']
        },
        'pixel_aspect_ratio': {
            'format': [],
            'stream': ['sar', 'sample_aspect_ratio']
        },
        'pixel_format': {
            'format': [],
            'stream': ['pix_fmt']
        },
        'color_range': {
            'format': [],
            'stream': ['color_range']
        },
        'color_transfer': {
            'format': [],
            'stream': ['color_transfer']
        },
        'color_primaries': {
            'format': [],
            'stream': ['color_primaries']
        },
        'level': {
            'format': [],
            'stream': ['level']
        },
        
        # Audio Stream Properties
        'audio_codec': {
            'format': [],
            'stream': ['codec_name', 'codec_long_name']
        },
        'sample_rate': {
            'format': [],
            'stream': ['sample_rate']
        },
        'channels': {
            'format': [],
            'stream': ['channels', 'channel_layout']
        },
        'audio_bit_depth': {
            'format': [],
            'stream': ['bits_per_sample', 'bits_per_raw_sample']
        },
        
        # Location Data
        'gps_coordinates': {
            'format': [],
            'tags': ['location', 'com.apple.quicktime.location.ISO6709', 'location-eng']
        },
        'gps_latitude': {
            'format': [],
            'tags': ['location', 'com.apple.quicktime.location.ISO6709']
        },
        'gps_longitude': {
            'format': [],
            'tags': ['location', 'com.apple.quicktime.location.ISO6709']
        },
        'location_name': {
            'format': [],
            'tags': ['location-eng', 'location_name']
        },
        
        # Device Information
        'device_make': {
            'format': [],
            'tags': ['make', 'com.apple.quicktime.make']
        },
        'device_model': {
            'format': [],
            'tags': ['model', 'com.apple.quicktime.model']
        },
        'software': {
            'format': [],
            'tags': ['software', 'encoder', 'com.apple.quicktime.software']
        }
    }
    
    # Special fields requiring frame analysis
    FRAME_ANALYSIS_FIELDS = {
        'gop_structure', 'keyframe_interval', 'frame_type_distribution',
        'i_frame_count', 'p_frame_count', 'b_frame_count'
    }
    
    def __init__(self):
        """Initialize command builder with caching"""
        self._command_cache = {}
        self._cache_hits = 0
        self._cache_misses = 0
        logger.debug("FFProbeCommandBuilder initialized")
    
    def build_command(
        self, 
        binary_path: Path, 
        file_path: Path,
        settings: Any  # MediaAnalysisSettings
    ) -> List[str]:
        """
        Build optimized FFprobe command based on user settings
        
        Args:
            binary_path: Path to ffprobe binary
            file_path: Path to media file to analyze
            settings: User's selected metadata fields
            
        Returns:
            Command line arguments list
        """
        # Start with base command
        cmd = [
            str(binary_path),
            '-v', 'quiet',
            '-print_format', 'json'
        ]
        
        # Collect required fields from settings
        format_fields, stream_fields, needs_tags, needs_frames = self._collect_required_fields(settings)
        
        # Build show_entries parameters
        if format_fields or needs_tags:
            if needs_tags:
                format_fields.add('tags')
            if format_fields:
                cmd.extend(['-show_entries', f'format={",".join(sorted(format_fields))}'])
        
        if stream_fields:
            # Always include codec_type to identify stream types
            stream_fields.add('codec_type')
            stream_fields.add('index')  # For stream identification
            cmd.extend(['-show_entries', f'stream={",".join(sorted(stream_fields))}'])
        
        # Add frame analysis if needed (expensive operation)
        if needs_frames:
            cmd.extend(self._build_frame_analysis_params())
        
        # Add the file path
        cmd.append(str(file_path))
        
        logger.debug(f"Built command with {len(stream_fields)} stream fields, "
                    f"{len(format_fields)} format fields, frames={needs_frames}")
        
        return cmd
    
    def _collect_required_fields(
        self, 
        settings: Any
    ) -> Tuple[Set[str], Set[str], bool, bool]:
        """
        Collect all required fields based on settings
        
        Returns:
            Tuple of (format_fields, stream_fields, needs_tags, needs_frames)
        """
        format_fields = set()
        stream_fields = set()
        needs_tags = False
        needs_frames = False
        
        # Process each field group
        field_groups = [
            'general_fields', 'video_fields', 'audio_fields', 
            'location_fields', 'device_fields'
        ]
        
        # Add new field groups if they exist
        if hasattr(settings, 'advanced_video_fields'):
            field_groups.append('advanced_video_fields')
        if hasattr(settings, 'frame_analysis_fields'):
            field_groups.append('frame_analysis_fields')
        
        for field_group_name in field_groups:
            field_group = getattr(settings, field_group_name, None)
            if not field_group:
                continue
            
            # Check if field group is enabled
            if hasattr(field_group, 'enabled') and not field_group.enabled:
                continue
            
            # Process fields
            if hasattr(field_group, 'fields'):
                for field_name, enabled in field_group.fields.items():
                    if not enabled:
                        continue
                    
                    # Check if this requires frame analysis
                    if field_name in self.FRAME_ANALYSIS_FIELDS:
                        needs_frames = True
                        continue
                    
                    # Get field mapping
                    if field_name in self.FIELD_MAPPINGS:
                        mapping = self.FIELD_MAPPINGS[field_name]
                        
                        # Add format fields
                        if 'format' in mapping:
                            format_fields.update(mapping['format'])
                        
                        # Add stream fields
                        if 'stream' in mapping:
                            stream_fields.update(mapping['stream'])
                        
                        # Check if tags needed
                        if 'tags' in mapping and mapping['tags']:
                            needs_tags = True
        
        return format_fields, stream_fields, needs_tags, needs_frames
    
    def _build_frame_analysis_params(self) -> List[str]:
        """Build parameters for frame-level analysis (GOP, keyframes, etc.)"""
        return [
            '-select_streams', 'v:0',  # First video stream only
            '-show_entries', 'frame=pict_type,key_frame,coded_picture_number,pkt_pts_time,pkt_dts_time',
            '-read_intervals', '%+#200'  # Analyze first 200 frames (balanced performance)
        ]
    
    def build_simple_command(self, binary_path: Path, file_path: Path) -> List[str]:
        """Build minimal command for quick format/duration check"""
        return [
            str(binary_path),
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_entries', 'format=format_name,duration,size',
            str(file_path)
        ]
    
    def get_optimization_info(self) -> Dict[str, Any]:
        """Get optimization statistics (similar to 7zip command builder)"""
        return {
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'cache_hit_rate': self._cache_hits / max(1, self._cache_hits + self._cache_misses),
            'cached_patterns': len(self._command_cache)
        }
    
    def estimate_performance_improvement(self, fields_requested: int, total_fields: int = 25) -> Dict[str, Any]:
        """
        Estimate performance improvement based on field selection
        
        Args:
            fields_requested: Number of fields user wants
            total_fields: Total possible fields
            
        Returns:
            Performance estimates
        """
        # Based on research: ~20ms for all fields, ~8ms for minimal
        full_extraction_time = 20  # ms per file
        minimal_extraction_time = 8  # ms per file
        
        # Linear interpolation for requested fields
        time_per_field = (full_extraction_time - minimal_extraction_time) / total_fields
        estimated_time = minimal_extraction_time + (fields_requested * time_per_field)
        
        improvement_percent = (1 - estimated_time / full_extraction_time) * 100
        
        return {
            'fields_requested': fields_requested,
            'total_possible_fields': total_fields,
            'estimated_time_ms': estimated_time,
            'full_extraction_time_ms': full_extraction_time,
            'improvement_percent': improvement_percent,
            'data_reduction_percent': (1 - fields_requested / total_fields) * 100
        }