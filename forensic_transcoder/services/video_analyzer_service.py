"""
Video analyzer service.

Uses FFprobe to extract comprehensive metadata from video files including
codec information, resolution, frame rate, audio streams, and format details.
"""

import json
import subprocess
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from ..models.video_analysis import (
    VideoAnalysis,
    AudioStreamInfo,
    SubtitleStreamInfo,
    FrameRateType,
)
from ..core.binary_manager import binary_manager


class VideoAnalyzerService:
    """
    Service for analyzing video files using FFprobe.
    
    Extracts complete metadata including video/audio/subtitle streams,
    format information, and technical specifications needed for
    transcoding decisions and concatenation compatibility checks.
    """
    
    def __init__(self):
        """Initialize the video analyzer service."""
        self.ffprobe_path = binary_manager.get_ffprobe_path()
        if not self.ffprobe_path:
            raise RuntimeError("FFprobe not found. Please ensure FFmpeg is installed.")
    
    def analyze_video(self, file_path: Path) -> VideoAnalysis:
        """
        Analyze a video file and extract comprehensive metadata.
        
        Args:
            file_path: Path to video file
        
        Returns:
            VideoAnalysis object with complete metadata
        
        Raises:
            FileNotFoundError: If file doesn't exist
            RuntimeError: If FFprobe fails to analyze the file
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Video file not found: {file_path}")
        
        # Get FFprobe output as JSON
        probe_data = self._run_ffprobe(file_path)
        
        # Extract format information
        format_info = probe_data.get('format', {})
        
        # Find video, audio, and subtitle streams
        streams = probe_data.get('streams', [])
        video_stream = self._find_video_stream(streams)
        audio_streams = self._extract_audio_streams(streams)
        subtitle_streams = self._extract_subtitle_streams(streams)
        
        if not video_stream:
            raise RuntimeError(f"No video stream found in file: {file_path}")
        
        # Extract video properties
        width = int(video_stream.get('width', 0))
        height = int(video_stream.get('height', 0))
        codec_name = video_stream.get('codec_name', 'unknown')
        codec_long_name = video_stream.get('codec_long_name', 'Unknown')
        pixel_format = video_stream.get('pix_fmt', 'unknown')
        
        # Extract frame rate
        fps, fps_string, frame_rate_type = self._extract_frame_rate(video_stream)
        
        # Extract duration
        duration = float(format_info.get('duration', 0.0))
        
        # Extract bitrates
        overall_bitrate = int(format_info.get('bit_rate', 0)) if format_info.get('bit_rate') else None
        video_bitrate = int(video_stream.get('bit_rate', 0)) if video_stream.get('bit_rate') else None
        
        # Extract color information
        color_space = video_stream.get('color_space')
        color_range = video_stream.get('color_range')
        color_primaries = video_stream.get('color_primaries')
        color_transfer = video_stream.get('color_transfer')
        
        # Extract codec profile/level
        profile = video_stream.get('profile')
        level = video_stream.get('level')
        
        # Advanced properties
        bit_depth = self._extract_bit_depth(video_stream)
        has_b_frames = video_stream.get('has_b_frames', 0) > 0
        gop_size = video_stream.get('gop_size')
        
        # Extract metadata
        tags = format_info.get('tags', {})
        creation_time = self._parse_creation_time(tags.get('creation_time'))
        
        # File information
        file_size = file_path.stat().st_size
        format_name = format_info.get('format_name', 'unknown')
        format_long_name = format_info.get('format_long_name', 'Unknown')
        
        # Calculate total frames
        total_frames = None
        if 'nb_frames' in video_stream:
            total_frames = int(video_stream['nb_frames'])
        elif duration > 0 and fps > 0:
            total_frames = int(duration * fps)
        
        # Check for chapters
        chapters = probe_data.get('chapters', [])
        has_chapters = len(chapters) > 0
        chapter_count = len(chapters)
        
        # Get start time
        start_time = float(video_stream.get('start_time', 0.0))
        
        # Get FFprobe version
        ffprobe_version = binary_manager.ffprobe_version
        
        # Average frame rate (for VFR detection)
        avg_frame_rate = None
        if 'avg_frame_rate' in video_stream and video_stream['avg_frame_rate'] != fps_string:
            avg_fps_parts = video_stream['avg_frame_rate'].split('/')
            if len(avg_fps_parts) == 2:
                try:
                    num = float(avg_fps_parts[0])
                    den = float(avg_fps_parts[1])
                    if den > 0:
                        avg_frame_rate = num / den
                except (ValueError, ZeroDivisionError):
                    pass
        
        return VideoAnalysis(
            file_path=file_path,
            file_size=file_size,
            format_name=format_name,
            format_long_name=format_long_name,
            video_codec=codec_name,
            video_codec_long_name=codec_long_name,
            width=width,
            height=height,
            pixel_format=pixel_format,
            fps=fps,
            fps_string=fps_string,
            frame_rate_type=frame_rate_type,
            avg_frame_rate=avg_frame_rate,
            duration=duration,
            total_frames=total_frames,
            start_time=start_time,
            overall_bitrate=overall_bitrate,
            video_bitrate=video_bitrate,
            color_space=color_space,
            color_range=color_range,
            color_primaries=color_primaries,
            color_transfer=color_transfer,
            profile=profile,
            level=str(level) if level is not None else None,
            bit_depth=bit_depth,
            has_b_frames=has_b_frames,
            gop_size=gop_size,
            audio_streams=audio_streams,
            subtitle_streams=subtitle_streams,
            creation_time=creation_time,
            metadata=tags,
            has_chapters=has_chapters,
            chapter_count=chapter_count,
            ffprobe_version=ffprobe_version,
        )
    
    def analyze_batch(self, file_paths: List[Path]) -> List[VideoAnalysis]:
        """
        Analyze multiple video files.
        
        Args:
            file_paths: List of paths to video files
        
        Returns:
            List of VideoAnalysis objects (failed analyses are skipped)
        """
        results = []
        for file_path in file_paths:
            try:
                analysis = self.analyze_video(file_path)
                results.append(analysis)
            except Exception as e:
                # Log error but continue with other files
                print(f"Failed to analyze {file_path}: {e}")
                continue
        
        return results
    
    def _run_ffprobe(self, file_path: Path) -> dict:
        """
        Run FFprobe and return parsed JSON output.
        
        Args:
            file_path: Path to video file
        
        Returns:
            Dictionary with FFprobe output
        
        Raises:
            RuntimeError: If FFprobe execution fails
        """
        cmd = [
            self.ffprobe_path,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            '-show_chapters',
            str(file_path)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            
            return json.loads(result.stdout)
        
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"FFprobe failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"FFprobe timed out analyzing: {file_path}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse FFprobe output: {e}")
    
    def _find_video_stream(self, streams: list) -> Optional[dict]:
        """Find the first video stream."""
        for stream in streams:
            if stream.get('codec_type') == 'video':
                return stream
        return None
    
    def _extract_audio_streams(self, streams: list) -> List[AudioStreamInfo]:
        """Extract information about all audio streams."""
        audio_streams = []
        
        for stream in streams:
            if stream.get('codec_type') == 'audio':
                audio_info = AudioStreamInfo(
                    stream_index=stream.get('index', 0),
                    codec=stream.get('codec_name', 'unknown'),
                    codec_long_name=stream.get('codec_long_name', 'Unknown'),
                    sample_rate=int(stream.get('sample_rate', 0)),
                    channels=int(stream.get('channels', 0)),
                    channel_layout=stream.get('channel_layout'),
                    bitrate=int(stream.get('bit_rate', 0)) if stream.get('bit_rate') else None,
                    duration=float(stream.get('duration', 0.0)) if stream.get('duration') else None,
                )
                audio_streams.append(audio_info)
        
        return audio_streams
    
    def _extract_subtitle_streams(self, streams: list) -> List[SubtitleStreamInfo]:
        """Extract information about all subtitle streams."""
        subtitle_streams = []
        
        for stream in streams:
            if stream.get('codec_type') == 'subtitle':
                tags = stream.get('tags', {})
                subtitle_info = SubtitleStreamInfo(
                    stream_index=stream.get('index', 0),
                    codec=stream.get('codec_name', 'unknown'),
                    codec_long_name=stream.get('codec_long_name', 'Unknown'),
                    language=tags.get('language'),
                    title=tags.get('title'),
                )
                subtitle_streams.append(subtitle_info)
        
        return subtitle_streams
    
    def _extract_frame_rate(self, video_stream: dict) -> tuple[float, str, FrameRateType]:
        """
        Extract frame rate from video stream.
        
        Returns:
            Tuple of (fps_float, fps_string, frame_rate_type)
        """
        fps_string = video_stream.get('r_frame_rate', '0/1')
        avg_fps_string = video_stream.get('avg_frame_rate', fps_string)
        
        # Calculate FPS
        fps = 0.0
        parts = fps_string.split('/')
        if len(parts) == 2:
            try:
                num = float(parts[0])
                den = float(parts[1])
                if den > 0:
                    fps = num / den
            except (ValueError, ZeroDivisionError):
                pass
        
        # Detect VFR
        frame_rate_type = FrameRateType.CONSTANT
        if fps_string != avg_fps_string:
            # If r_frame_rate differs from avg_frame_rate, it's likely VFR
            frame_rate_type = FrameRateType.VARIABLE
        
        return fps, fps_string, frame_rate_type
    
    def _extract_bit_depth(self, video_stream: dict) -> Optional[int]:
        """Extract bit depth from pixel format or stream info."""
        # Try to get from bits_per_raw_sample
        if 'bits_per_raw_sample' in video_stream:
            try:
                return int(video_stream['bits_per_raw_sample'])
            except (ValueError, TypeError):
                pass
        
        # Infer from pixel format
        pix_fmt = video_stream.get('pix_fmt', '')
        if '10le' in pix_fmt or '10be' in pix_fmt:
            return 10
        elif '12le' in pix_fmt or '12be' in pix_fmt:
            return 12
        elif '16le' in pix_fmt or '16be' in pix_fmt:
            return 16
        else:
            return 8  # Default assumption
    
    def _parse_creation_time(self, creation_time_str: Optional[str]) -> Optional[datetime]:
        """Parse creation time from metadata."""
        if not creation_time_str:
            return None
        
        try:
            # Try ISO format first
            return datetime.fromisoformat(creation_time_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return None
