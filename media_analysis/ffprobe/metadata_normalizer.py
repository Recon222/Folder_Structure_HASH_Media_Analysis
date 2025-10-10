#!/usr/bin/env python3
"""
Metadata normalizer for converting raw FFprobe output
Transforms raw JSON data into structured MediaMetadata objects
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
import re

from ..core.media_analysis_models import MediaMetadata, MediaAnalysisSettings
from core.logger import logger


class MetadataNormalizer:
    """Normalizes raw FFprobe output to MediaMetadata objects"""
    
    # Codec name mappings for user-friendly display
    VIDEO_CODEC_MAP = {
        'h264': 'H.264/AVC',
        'hevc': 'H.265/HEVC',
        'h265': 'H.265/HEVC',
        'mpeg4': 'MPEG-4',
        'vp8': 'VP8',
        'vp9': 'VP9',
        'av1': 'AV1',
        'mpeg2video': 'MPEG-2',
        'mjpeg': 'Motion JPEG',
        'prores': 'ProRes',
        'dnxhd': 'DNxHD',
        'theora': 'Theora'
    }
    
    AUDIO_CODEC_MAP = {
        'aac': 'AAC',
        'mp3': 'MP3',
        'ac3': 'AC-3 (Dolby Digital)',
        'eac3': 'E-AC-3 (Dolby Digital Plus)',
        'dts': 'DTS',
        'flac': 'FLAC',
        'vorbis': 'Vorbis',
        'opus': 'Opus',
        'pcm_s16le': 'PCM 16-bit',
        'pcm_s24le': 'PCM 24-bit',
        'mp2': 'MP2',
        'wmav2': 'WMA v2',
        'alac': 'ALAC (Apple Lossless)'
    }
    
    def normalize(self, raw_metadata: Dict, file_path: Path) -> MediaMetadata:
        """
        Convert raw FFprobe JSON to normalized MediaMetadata
        
        Args:
            raw_metadata: Raw JSON dict from FFprobe
            file_path: Path to the media file
            
        Returns:
            Normalized MediaMetadata object
        """
        # Get file size from filesystem if not in metadata
        try:
            file_size = file_path.stat().st_size if file_path.exists() else 0
        except:
            file_size = 0
        
        metadata = MediaMetadata(file_path=file_path, file_size=file_size)
        
        # Store raw JSON for debugging
        metadata.raw_json = raw_metadata
        
        # Extract format information
        self._extract_format_info(raw_metadata.get('format', {}), metadata)
        
        # Extract stream information
        streams = raw_metadata.get('streams', [])
        for stream in streams:
            codec_type = stream.get('codec_type', '').lower()
            
            if codec_type == 'video':
                self._extract_video_info(stream, metadata)
            elif codec_type == 'audio':
                self._extract_audio_info(stream, metadata)
        
        # Extract metadata tags (can be in format or streams)
        self._extract_metadata_tags(raw_metadata, metadata)
        
        return metadata
    
    def _extract_format_info(self, format_data: Dict, metadata: MediaMetadata):
        """Extract container format information"""
        if not format_data:
            return
        
        # Use file extension as format (uppercase, without dot)
        file_ext = metadata.file_path.suffix.upper().lstrip('.')
        if file_ext:
            metadata.format = file_ext
        else:
            # Fallback to cleaned format name if no extension
            metadata.format = self._clean_format_name(format_data.get('format_name', ''))
        
        metadata.format_long = format_data.get('format_long_name', '')
        
        # Duration and bitrate
        try:
            metadata.duration = float(format_data.get('duration', 0))
        except (ValueError, TypeError):
            metadata.duration = None
        
        try:
            metadata.bitrate = int(format_data.get('bit_rate', 0))
        except (ValueError, TypeError):
            metadata.bitrate = None
        
        # File size from format (more accurate than filesystem sometimes)
        try:
            size = int(format_data.get('size', 0))
            if size > 0:
                metadata.file_size = size
        except (ValueError, TypeError):
            pass
        
        # Extract dates from format tags
        tags = format_data.get('tags', {})
        self._extract_dates_from_tags(tags, metadata)
    
    def _extract_video_info(self, stream: Dict, metadata: MediaMetadata):
        """Extract video stream information"""
        metadata.has_video = True
        
        # Codec information
        codec_name = stream.get('codec_name', '').lower()
        metadata.video_codec = self.VIDEO_CODEC_MAP.get(codec_name, codec_name.upper() if codec_name else 'Unknown')
        metadata.video_codec_long = stream.get('codec_long_name', '')
        
        # Resolution
        width = stream.get('width')
        height = stream.get('height')
        if width and height:
            try:
                metadata.resolution = (int(width), int(height))
            except (ValueError, TypeError):
                pass
        
        # Frame rate
        frame_rate_str = stream.get('avg_frame_rate') or stream.get('r_frame_rate')
        if frame_rate_str:
            metadata.frame_rate = self._parse_framerate(frame_rate_str)
        
        # Aspect ratios (Enhanced support)
        metadata.aspect_ratio = stream.get('display_aspect_ratio')  # Keep existing for compatibility
        metadata.display_aspect_ratio = stream.get('display_aspect_ratio')  # DAR
        metadata.sample_aspect_ratio = stream.get('sample_aspect_ratio')  # SAR
        metadata.pixel_aspect_ratio = stream.get('sar', stream.get('sample_aspect_ratio'))  # PAR
        
        # Color space and pixel format
        metadata.color_space = stream.get('color_space')
        metadata.pixel_format = stream.get('pix_fmt')
        metadata.color_range = stream.get('color_range')
        metadata.color_transfer = stream.get('color_transfer')
        metadata.color_primaries = stream.get('color_primaries')
        
        # Advanced video properties
        metadata.profile = stream.get('profile')
        metadata.level = stream.get('level')
        
        # Bit depth
        bits = stream.get('bits_per_raw_sample') or stream.get('bits_per_sample')
        if bits:
            try:
                metadata.bit_depth = int(bits)
            except (ValueError, TypeError):
                pass
        if not metadata.color_space:
            # Try to infer from pixel format
            pix_fmt = stream.get('pix_fmt', '')
            if 'yuv420p10' in pix_fmt:
                metadata.color_space = 'BT.2020 (10-bit)'
            elif 'yuv420p' in pix_fmt:
                metadata.color_space = 'BT.709'
        
        # Video bitrate
        try:
            metadata.video_bitrate = int(stream.get('bit_rate', 0))
        except (ValueError, TypeError):
            pass
    
    def _extract_audio_info(self, stream: Dict, metadata: MediaMetadata):
        """Extract audio stream information"""
        metadata.has_audio = True
        
        # Codec information
        codec_name = stream.get('codec_name', '').lower()
        metadata.audio_codec = self.AUDIO_CODEC_MAP.get(codec_name, codec_name.upper() if codec_name else 'Unknown')
        metadata.audio_codec_long = stream.get('codec_long_name', '')
        
        # Sample rate
        try:
            metadata.sample_rate = int(stream.get('sample_rate', 0))
        except (ValueError, TypeError):
            pass
        
        # Channels
        try:
            metadata.channels = int(stream.get('channels', 0))
        except (ValueError, TypeError):
            pass
        
        # Channel layout
        metadata.channel_layout = stream.get('channel_layout')
        if not metadata.channel_layout and metadata.channels:
            # Infer from channel count
            channel_layouts = {
                1: 'mono',
                2: 'stereo',
                6: '5.1',
                8: '7.1'
            }
            metadata.channel_layout = channel_layouts.get(metadata.channels, f'{metadata.channels} channels')
        
        # Audio bitrate
        try:
            metadata.audio_bitrate = int(stream.get('bit_rate', 0))
        except (ValueError, TypeError):
            pass
        
        # Bit depth
        try:
            bits = stream.get('bits_per_sample')
            if bits:
                metadata.bit_depth = int(bits)
        except (ValueError, TypeError):
            pass
    
    def _extract_metadata_tags(self, raw_metadata: Dict, metadata: MediaMetadata):
        """Extract metadata tags from format and streams"""
        # Check format tags
        format_tags = raw_metadata.get('format', {}).get('tags', {})
        self._process_tags(format_tags, metadata)
        
        # Check stream tags (especially for video files with EXIF)
        for stream in raw_metadata.get('streams', []):
            stream_tags = stream.get('tags', {})
            self._process_tags(stream_tags, metadata)
    
    def _process_tags(self, tags: Dict[str, str], metadata: MediaMetadata):
        """Process metadata tags dictionary"""
        if not tags:
            return
        
        # Use case-insensitive key lookup
        tags_lower = {k.lower(): v for k, v in tags.items()}
        
        # Title, artist, album
        metadata.title = metadata.title or tags_lower.get('title')
        metadata.artist = metadata.artist or tags_lower.get('artist')
        metadata.album = metadata.album or tags_lower.get('album')
        metadata.comment = metadata.comment or tags_lower.get('comment')
        
        # Device information
        metadata.device_make = metadata.device_make or tags_lower.get('make') or tags_lower.get('com.apple.quicktime.make')
        metadata.device_model = metadata.device_model or tags_lower.get('model') or tags_lower.get('com.apple.quicktime.model')
        metadata.software = metadata.software or tags_lower.get('software') or tags_lower.get('com.apple.quicktime.software')
        
        # GPS coordinates
        self._extract_gps_from_tags(tags_lower, metadata)
        
        # Additional dates
        self._extract_dates_from_tags(tags_lower, metadata)
    
    def _extract_gps_from_tags(self, tags: Dict[str, str], metadata: MediaMetadata):
        """Extract GPS coordinates from tags"""
        # Try different GPS tag formats
        gps_patterns = [
            ('location', r'([-+]?\d+\.?\d*)\s*([-+]?\d+\.?\d*)'),  # "location: +40.1234-073.5678"
            ('com.apple.quicktime.location.iso6709', r'([-+]?\d+\.?\d*)([-+]?\d+\.?\d*)'),  # Apple format
            ('gps', r'([-+]?\d+\.?\d*)[,\s]+([-+]?\d+\.?\d*)')  # Generic GPS
        ]
        
        for tag_name, pattern in gps_patterns:
            if tag_name in tags:
                match = re.search(pattern, tags[tag_name])
                if match:
                    try:
                        metadata.gps_latitude = float(match.group(1))
                        metadata.gps_longitude = float(match.group(2))
                        break
                    except (ValueError, IndexError):
                        pass
        
        # Also check for separate lat/lon tags
        if not metadata.gps_latitude:
            for lat_key in ['gps_latitude', 'latitude', 'lat']:
                if lat_key in tags:
                    try:
                        metadata.gps_latitude = float(tags[lat_key])
                        break
                    except ValueError:
                        pass
        
        if not metadata.gps_longitude:
            for lon_key in ['gps_longitude', 'longitude', 'lon', 'lng']:
                if lon_key in tags:
                    try:
                        metadata.gps_longitude = float(tags[lon_key])
                        break
                    except ValueError:
                        pass
    
    def _extract_dates_from_tags(self, tags: Dict[str, str], metadata: MediaMetadata):
        """Extract various dates from tags"""
        # Creation date
        creation_keys = ['creation_time', 'date', 'datetime', 'datetimeoriginal', 
                        'com.apple.quicktime.creationdate']
        for key in creation_keys:
            if key in tags and not metadata.creation_date:
                metadata.creation_date = self._parse_date(tags[key])
                if metadata.creation_date:
                    break
        
        # Modification date
        mod_keys = ['modification_time', 'modifydate', 'datetimedigitized']
        for key in mod_keys:
            if key in tags and not metadata.modification_date:
                metadata.modification_date = self._parse_date(tags[key])
                if metadata.modification_date:
                    break
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string from various formats"""
        if not date_str:
            return None
        
        # Common date formats in media files
        date_formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',  # ISO format with microseconds
            '%Y-%m-%dT%H:%M:%SZ',      # ISO format
            '%Y-%m-%d %H:%M:%S',       # Simple format
            '%Y:%m:%d %H:%M:%S',       # EXIF format
            '%Y-%m-%d',                # Date only
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        # Try to parse just the date part if time parsing fails
        try:
            date_part = date_str.split('T')[0].split(' ')[0]
            if '-' in date_part:
                return datetime.strptime(date_part, '%Y-%m-%d')
            elif ':' in date_part:
                return datetime.strptime(date_part, '%Y:%m:%d')
        except:
            pass
        
        return None
    
    def _parse_framerate(self, rate_str: str) -> Optional[float]:
        """Parse frame rate from fraction string (e.g., '30000/1001')"""
        if not rate_str or rate_str == '0/0':
            return None
        
        try:
            if '/' in rate_str:
                num, den = rate_str.split('/')
                if int(den) != 0:
                    return float(num) / float(den)
            else:
                return float(rate_str)
        except (ValueError, ZeroDivisionError):
            return None
    
    def _clean_format_name(self, format_name: str) -> str:
        """Clean up format name for display"""
        if not format_name:
            return 'Unknown'
        
        # Take first format if comma-separated
        format_name = format_name.split(',')[0]
        
        # Common format mappings
        format_map = {
            'mov': 'QuickTime',
            'mp4': 'MP4',
            'matroska': 'MKV',
            'webm': 'WebM',
            'avi': 'AVI',
            'mpegts': 'MPEG-TS',
            'flv': 'Flash Video',
            'ogg': 'Ogg',
            'asf': 'ASF/WMV',
            'mp3': 'MP3',
            'wav': 'WAV',
            'flac': 'FLAC'
        }
        
        return format_map.get(format_name.lower(), format_name.upper())
    
    def apply_field_filter(self, metadata: MediaMetadata, settings: MediaAnalysisSettings) -> MediaMetadata:
        """
        Apply field filtering based on user settings
        Sets disabled fields to None
        
        Args:
            metadata: Full metadata object
            settings: User settings for field visibility
            
        Returns:
            Filtered metadata object
        """
        # General fields
        if not settings.general_fields.is_field_enabled('format'):
            metadata.format = None
            metadata.format_long = None
        if not settings.general_fields.is_field_enabled('duration'):
            metadata.duration = None
        if not settings.general_fields.is_field_enabled('bitrate'):
            metadata.bitrate = None
        if not settings.general_fields.is_field_enabled('creation_date'):
            metadata.creation_date = None
        
        # Video fields
        if not settings.video_fields.enabled:
            metadata.has_video = False
            metadata.video_codec = None
            metadata.video_codec_long = None
            metadata.resolution = None
            metadata.frame_rate = None
            metadata.aspect_ratio = None
            metadata.color_space = None
            metadata.video_bitrate = None
        else:
            if not settings.video_fields.is_field_enabled('video_codec'):
                metadata.video_codec = None
                metadata.video_codec_long = None
            if not settings.video_fields.is_field_enabled('resolution'):
                metadata.resolution = None
            if not settings.video_fields.is_field_enabled('frame_rate'):
                metadata.frame_rate = None
            if not settings.video_fields.is_field_enabled('aspect_ratio'):
                metadata.aspect_ratio = None
            if not settings.video_fields.is_field_enabled('color_space'):
                metadata.color_space = None
        
        # Audio fields
        if not settings.audio_fields.enabled:
            metadata.has_audio = False
            metadata.audio_codec = None
            metadata.audio_codec_long = None
            metadata.sample_rate = None
            metadata.channels = None
            metadata.channel_layout = None
            metadata.audio_bitrate = None
            metadata.bit_depth = None
        else:
            if not settings.audio_fields.is_field_enabled('audio_codec'):
                metadata.audio_codec = None
                metadata.audio_codec_long = None
            if not settings.audio_fields.is_field_enabled('sample_rate'):
                metadata.sample_rate = None
            if not settings.audio_fields.is_field_enabled('channels'):
                metadata.channels = None
                metadata.channel_layout = None
            if not settings.audio_fields.is_field_enabled('bit_depth'):
                metadata.bit_depth = None
        
        # Location fields
        if not settings.location_fields.enabled:
            metadata.gps_latitude = None
            metadata.gps_longitude = None
            metadata.location_name = None
        
        # Device fields
        if not settings.device_fields.enabled:
            metadata.device_make = None
            metadata.device_model = None
            metadata.software = None
    
    def analyze_frame_data(self, frames: List[Dict], metadata: MediaMetadata):
        """
        Analyze frame-level data for GOP structure and keyframe intervals
        
        Args:
            frames: List of frame dictionaries from FFprobe
            metadata: MediaMetadata object to populate
        """
        if not frames:
            return
        
        frame_types = {'I': 0, 'P': 0, 'B': 0, '?': 0}
        keyframe_times = []
        last_keyframe_number = 0
        gop_sizes = []
        
        for frame in frames:
            # Count frame types
            pict_type = frame.get('pict_type', '?')
            if pict_type in frame_types:
                frame_types[pict_type] += 1
            else:
                frame_types['?'] += 1
            
            # Track keyframes
            if frame.get('key_frame') == 1:
                pts_time = frame.get('pkt_pts_time')
                if pts_time:
                    try:
                        keyframe_times.append(float(pts_time))
                    except (ValueError, TypeError):
                        pass
                
                # Calculate GOP size
                frame_number = frame.get('coded_picture_number', 0)
                if frame_number and last_keyframe_number > 0:
                    gop_sizes.append(frame_number - last_keyframe_number)
                last_keyframe_number = frame_number
        
        # Store frame type counts
        metadata.i_frame_count = frame_types['I']
        metadata.p_frame_count = frame_types['P']
        metadata.b_frame_count = frame_types['B']
        
        # Store distribution, excluding unknowns if all are unknown
        if sum(v for k, v in frame_types.items() if k != '?') > 0:
            metadata.frame_type_distribution = {k: v for k, v in frame_types.items() if v > 0 and k != '?'}
        
        # Calculate average keyframe interval
        if len(keyframe_times) > 1:
            intervals = [keyframe_times[i+1] - keyframe_times[i] 
                        for i in range(len(keyframe_times)-1)]
            if intervals:
                metadata.keyframe_interval = sum(intervals) / len(intervals)
        
        # Calculate average GOP size
        if gop_sizes:
            metadata.gop_size = int(sum(gop_sizes) / len(gop_sizes))
        
        return metadata