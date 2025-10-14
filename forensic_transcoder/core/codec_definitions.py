"""
Codec and format definitions.

Contains mappings of video/audio codecs, container formats, hardware encoders,
and compatibility rules for the forensic transcoder.
"""

from typing import Dict, List, Set, Optional
from dataclasses import dataclass


@dataclass
class CodecInfo:
    """Information about a video or audio codec."""
    name: str
    long_name: str
    codec_type: str  # 'video' or 'audio'
    is_hardware: bool = False
    supported_formats: List[str] = None  # Container formats that support this codec
    
    def __post_init__(self):
        if self.supported_formats is None:
            self.supported_formats = []


# === Video Codecs ===

VIDEO_CODECS: Dict[str, CodecInfo] = {
    # H.264 / AVC
    'libx264': CodecInfo(
        name='libx264',
        long_name='H.264 / AVC (software)',
        codec_type='video',
        is_hardware=False,
        supported_formats=['mp4', 'mkv', 'mov', 'avi', 'ts', 'flv']
    ),
    'h264_nvenc': CodecInfo(
        name='h264_nvenc',
        long_name='H.264 / AVC (NVIDIA NVENC)',
        codec_type='video',
        is_hardware=True,
        supported_formats=['mp4', 'mkv', 'mov', 'avi', 'ts']
    ),
    'h264_qsv': CodecInfo(
        name='h264_qsv',
        long_name='H.264 / AVC (Intel QSV)',
        codec_type='video',
        is_hardware=True,
        supported_formats=['mp4', 'mkv', 'mov', 'avi', 'ts']
    ),
    'h264_amf': CodecInfo(
        name='h264_amf',
        long_name='H.264 / AVC (AMD AMF)',
        codec_type='video',
        is_hardware=True,
        supported_formats=['mp4', 'mkv', 'mov', 'avi', 'ts']
    ),
    
    # H.265 / HEVC
    'libx265': CodecInfo(
        name='libx265',
        long_name='H.265 / HEVC (software)',
        codec_type='video',
        is_hardware=False,
        supported_formats=['mp4', 'mkv', 'mov', 'ts']
    ),
    'hevc_nvenc': CodecInfo(
        name='hevc_nvenc',
        long_name='H.265 / HEVC (NVIDIA NVENC)',
        codec_type='video',
        is_hardware=True,
        supported_formats=['mp4', 'mkv', 'mov', 'ts']
    ),
    'hevc_qsv': CodecInfo(
        name='hevc_qsv',
        long_name='H.265 / HEVC (Intel QSV)',
        codec_type='video',
        is_hardware=True,
        supported_formats=['mp4', 'mkv', 'mov', 'ts']
    ),
    'hevc_amf': CodecInfo(
        name='hevc_amf',
        long_name='H.265 / HEVC (AMD AMF)',
        codec_type='video',
        is_hardware=True,
        supported_formats=['mp4', 'mkv', 'mov', 'ts']
    ),
    
    # VP9
    'libvpx-vp9': CodecInfo(
        name='libvpx-vp9',
        long_name='VP9 (software)',
        codec_type='video',
        is_hardware=False,
        supported_formats=['webm', 'mkv']
    ),
    
    # AV1
    'libsvtav1': CodecInfo(
        name='libsvtav1',
        long_name='AV1 (SVT-AV1)',
        codec_type='video',
        is_hardware=False,
        supported_formats=['mp4', 'mkv', 'webm']
    ),
    'libaom-av1': CodecInfo(
        name='libaom-av1',
        long_name='AV1 (libaom)',
        codec_type='video',
        is_hardware=False,
        supported_formats=['mp4', 'mkv', 'webm']
    ),
    'av1_nvenc': CodecInfo(
        name='av1_nvenc',
        long_name='AV1 (NVIDIA NVENC)',
        codec_type='video',
        is_hardware=True,
        supported_formats=['mp4', 'mkv', 'webm']
    ),
    
    # ProRes
    'prores_ks': CodecInfo(
        name='prores_ks',
        long_name='Apple ProRes',
        codec_type='video',
        is_hardware=False,
        supported_formats=['mov']
    ),
    
    # Lossless
    'ffv1': CodecInfo(
        name='ffv1',
        long_name='FFV1 (lossless)',
        codec_type='video',
        is_hardware=False,
        supported_formats=['mkv', 'avi']
    ),
    'utvideo': CodecInfo(
        name='utvideo',
        long_name='Ut Video (lossless)',
        codec_type='video',
        is_hardware=False,
        supported_formats=['mkv', 'avi']
    ),
    
    # MPEG-4
    'mpeg4': CodecInfo(
        name='mpeg4',
        long_name='MPEG-4 Part 2',
        codec_type='video',
        is_hardware=False,
        supported_formats=['mp4', 'avi', 'mkv']
    ),
    
    # MJPEG
    'mjpeg': CodecInfo(
        name='mjpeg',
        long_name='Motion JPEG',
        codec_type='video',
        is_hardware=False,
        supported_formats=['avi', 'mov', 'mkv']
    ),
}


# === Audio Codecs ===

AUDIO_CODECS: Dict[str, CodecInfo] = {
    'aac': CodecInfo(
        name='aac',
        long_name='AAC (Advanced Audio Coding)',
        codec_type='audio',
        supported_formats=['mp4', 'mkv', 'mov', 'ts']
    ),
    'libmp3lame': CodecInfo(
        name='libmp3lame',
        long_name='MP3 (LAME)',
        codec_type='audio',
        supported_formats=['mp3', 'mp4', 'mkv', 'avi']
    ),
    'libopus': CodecInfo(
        name='libopus',
        long_name='Opus',
        codec_type='audio',
        supported_formats=['webm', 'mkv', 'ogg']
    ),
    'libvorbis': CodecInfo(
        name='libvorbis',
        long_name='Vorbis',
        codec_type='audio',
        supported_formats=['webm', 'mkv', 'ogg']
    ),
    'ac3': CodecInfo(
        name='ac3',
        long_name='Dolby Digital (AC-3)',
        codec_type='audio',
        supported_formats=['mp4', 'mkv', 'mov', 'ts']
    ),
    'flac': CodecInfo(
        name='flac',
        long_name='FLAC (lossless)',
        codec_type='audio',
        supported_formats=['flac', 'mkv']
    ),
    'pcm_s16le': CodecInfo(
        name='pcm_s16le',
        long_name='PCM signed 16-bit (uncompressed)',
        codec_type='audio',
        supported_formats=['wav', 'avi', 'mov']
    ),
}


# === Container Formats ===

@dataclass
class FormatInfo:
    """Information about a container format."""
    name: str
    long_name: str
    extensions: List[str]
    default_video_codec: str
    default_audio_codec: str
    supports_chapters: bool = True
    supports_metadata: bool = True


CONTAINER_FORMATS: Dict[str, FormatInfo] = {
    'mp4': FormatInfo(
        name='mp4',
        long_name='MPEG-4 Part 14',
        extensions=['mp4', 'm4v'],
        default_video_codec='libx264',
        default_audio_codec='aac',
        supports_chapters=True,
        supports_metadata=True
    ),
    'mkv': FormatInfo(
        name='matroska',
        long_name='Matroska',
        extensions=['mkv'],
        default_video_codec='libx264',
        default_audio_codec='aac',
        supports_chapters=True,
        supports_metadata=True
    ),
    'mov': FormatInfo(
        name='mov',
        long_name='QuickTime / MOV',
        extensions=['mov', 'qt'],
        default_video_codec='libx264',
        default_audio_codec='aac',
        supports_chapters=True,
        supports_metadata=True
    ),
    'avi': FormatInfo(
        name='avi',
        long_name='AVI (Audio Video Interleaved)',
        extensions=['avi'],
        default_video_codec='mpeg4',
        default_audio_codec='libmp3lame',
        supports_chapters=False,
        supports_metadata=False
    ),
    'webm': FormatInfo(
        name='webm',
        long_name='WebM',
        extensions=['webm'],
        default_video_codec='libvpx-vp9',
        default_audio_codec='libopus',
        supports_chapters=True,
        supports_metadata=True
    ),
}


# === Hardware Encoder Availability ===

HARDWARE_ENCODER_FLAGS: Dict[str, List[str]] = {
    'nvenc': ['h264_nvenc', 'hevc_nvenc', 'av1_nvenc'],
    'qsv': ['h264_qsv', 'hevc_qsv'],
    'amf': ['h264_amf', 'hevc_amf'],
}


# === Codec Presets ===

H264_PRESETS = ['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow']
H265_PRESETS = ['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow']
NVENC_PRESETS = ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7']  # p1=fastest, p7=slowest/best
QSV_PRESETS = ['veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow']


CODEC_PRESETS: Dict[str, List[str]] = {
    'libx264': H264_PRESETS,
    'libx265': H265_PRESETS,
    'h264_nvenc': NVENC_PRESETS,
    'hevc_nvenc': NVENC_PRESETS,
    'h264_qsv': QSV_PRESETS,
    'hevc_qsv': QSV_PRESETS,
    'h264_amf': ['speed', 'balanced', 'quality'],
    'hevc_amf': ['speed', 'balanced', 'quality'],
}


# === Codec Tuning Options ===

CODEC_TUNE_OPTIONS: Dict[str, List[str]] = {
    'libx264': ['film', 'animation', 'grain', 'stillimage', 'fastdecode', 'zerolatency'],
    'libx265': ['grain', 'fastdecode', 'zerolatency'],
}


# === Codec Profiles ===

CODEC_PROFILES: Dict[str, List[str]] = {
    'libx264': ['baseline', 'main', 'high', 'high10', 'high422', 'high444'],
    'libx265': ['main', 'main10', 'main444-8', 'main444-10'],
    'h264_nvenc': ['baseline', 'main', 'high', 'high444p'],
    'hevc_nvenc': ['main', 'main10', 'rext'],
}


# === Pixel Formats ===

PIXEL_FORMATS = [
    'yuv420p',    # 8-bit 4:2:0 (most common)
    'yuv422p',    # 8-bit 4:2:2
    'yuv444p',    # 8-bit 4:4:4
    'yuv420p10le', # 10-bit 4:2:0
    'yuv422p10le', # 10-bit 4:2:2
    'yuv444p10le', # 10-bit 4:4:4
    'rgb24',      # 24-bit RGB
    'rgba',       # 32-bit RGBA
    'gray',       # Grayscale
]


# === Utility Functions ===

def get_video_codec_info(codec_name: str) -> Optional[CodecInfo]:
    """Get information about a video codec."""
    return VIDEO_CODECS.get(codec_name)


def get_audio_codec_info(codec_name: str) -> Optional[CodecInfo]:
    """Get information about an audio codec."""
    return AUDIO_CODECS.get(codec_name)


def get_format_info(format_name: str) -> Optional[FormatInfo]:
    """Get information about a container format."""
    return CONTAINER_FORMATS.get(format_name)


def is_hardware_codec(codec_name: str) -> bool:
    """Check if codec is hardware-accelerated."""
    codec_info = get_video_codec_info(codec_name)
    return codec_info.is_hardware if codec_info else False


def get_compatible_formats(codec_name: str) -> List[str]:
    """Get list of container formats compatible with a codec."""
    codec_info = get_video_codec_info(codec_name)
    return codec_info.supported_formats if codec_info else []


def is_codec_format_compatible(codec_name: str, format_name: str) -> bool:
    """Check if codec is compatible with container format."""
    compatible_formats = get_compatible_formats(codec_name)
    return format_name in compatible_formats


def get_available_presets(codec_name: str) -> List[str]:
    """Get available presets for a codec."""
    return CODEC_PRESETS.get(codec_name, [])


def get_available_tune_options(codec_name: str) -> List[str]:
    """Get available tune options for a codec."""
    return CODEC_TUNE_OPTIONS.get(codec_name, [])


def get_available_profiles(codec_name: str) -> List[str]:
    """Get available profiles for a codec."""
    return CODEC_PROFILES.get(codec_name, [])


def get_all_video_codecs() -> List[str]:
    """Get list of all available video codec names."""
    return list(VIDEO_CODECS.keys())


def get_all_audio_codecs() -> List[str]:
    """Get list of all available audio codec names."""
    return list(AUDIO_CODECS.keys())


def get_all_formats() -> List[str]:
    """Get list of all available container format names."""
    return list(CONTAINER_FORMATS.keys())


def get_hardware_codecs() -> List[str]:
    """Get list of all hardware-accelerated video codecs."""
    return [name for name, info in VIDEO_CODECS.items() if info.is_hardware]


def get_software_codecs() -> List[str]:
    """Get list of all software video codecs."""
    return [name for name, info in VIDEO_CODECS.items() if not info.is_hardware]
