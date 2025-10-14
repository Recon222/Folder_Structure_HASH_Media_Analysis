"""
Forensic Transcoder core utilities.

This package contains codec definitions, preset configurations, and
other foundational utilities used throughout the application.
"""

from .codec_definitions import (
    CodecInfo,
    FormatInfo,
    VIDEO_CODECS,
    AUDIO_CODECS,
    CONTAINER_FORMATS,
    PIXEL_FORMATS,
    get_video_codec_info,
    get_audio_codec_info,
    get_format_info,
    is_hardware_codec,
    get_compatible_formats,
    is_codec_format_compatible,
    get_available_presets,
    get_available_tune_options,
    get_available_profiles,
    get_all_video_codecs,
    get_all_audio_codecs,
    get_all_formats,
    get_hardware_codecs,
    get_software_codecs,
)

from .preset_definitions import (
    ForensicPresetDefinition,
    FORENSIC_PRESETS,
    get_preset_definition,
    get_preset_for_codec,
    get_crf_for_preset,
    get_audio_settings_for_preset,
    get_all_preset_names,
    get_preset_description,
    get_preset_use_case,
)

__all__ = [
    # Codec definitions
    'CodecInfo',
    'FormatInfo',
    'VIDEO_CODECS',
    'AUDIO_CODECS',
    'CONTAINER_FORMATS',
    'PIXEL_FORMATS',
    'get_video_codec_info',
    'get_audio_codec_info',
    'get_format_info',
    'is_hardware_codec',
    'get_compatible_formats',
    'is_codec_format_compatible',
    'get_available_presets',
    'get_available_tune_options',
    'get_available_profiles',
    'get_all_video_codecs',
    'get_all_audio_codecs',
    'get_all_formats',
    'get_hardware_codecs',
    'get_software_codecs',
    
    # Preset definitions
    'ForensicPresetDefinition',
    'FORENSIC_PRESETS',
    'get_preset_definition',
    'get_preset_for_codec',
    'get_crf_for_preset',
    'get_audio_settings_for_preset',
    'get_all_preset_names',
    'get_preset_description',
    'get_preset_use_case',
]
