"""
Forensic quality preset definitions.

Defines quality presets optimized for forensic video analysis, balancing
evidence preservation with file size and processing speed.
"""

from dataclasses import dataclass
from typing import Optional, Dict
from ..models.transcode_settings import QualityPreset


@dataclass
class ForensicPresetDefinition:
    """
    Definition of a forensic quality preset.
    
    Maps a quality level to specific FFmpeg encoding parameters optimized
    for forensic use cases.
    """
    preset_name: QualityPreset
    description: str
    
    # Video quality
    crf_h264: int  # CRF for H.264
    crf_h265: int  # CRF for H.265
    preset: str    # Encoding speed preset
    
    # Audio settings
    audio_codec: str
    audio_bitrate: str
    
    # Advanced
    tune: Optional[str] = None
    profile: Optional[str] = None
    pixel_format: str = "yuv420p"
    
    # Use case description
    use_case: str = ""
    
    def get_crf_for_codec(self, codec: str) -> int:
        """Get appropriate CRF value for codec."""
        if 'h264' in codec.lower():
            return self.crf_h264
        elif 'hevc' in codec.lower() or 'h265' in codec.lower():
            return self.crf_h265
        else:
            # Default to H.264 CRF for other codecs
            return self.crf_h264


# === Forensic Preset Definitions ===

FORENSIC_PRESETS: Dict[QualityPreset, ForensicPresetDefinition] = {
    QualityPreset.LOSSLESS_FORENSIC: ForensicPresetDefinition(
        preset_name=QualityPreset.LOSSLESS_FORENSIC,
        description="Mathematically lossless - Maximum quality preservation",
        crf_h264=0,  # Lossless
        crf_h265=0,  # Lossless
        preset="slow",
        audio_codec="flac",
        audio_bitrate="",  # N/A for lossless
        pixel_format="yuv420p",
        use_case=(
            "Critical evidence requiring perfect preservation. "
            "Large file sizes. Use for master archives or when disk space is unlimited."
        )
    ),
    
    QualityPreset.HIGH_FORENSIC: ForensicPresetDefinition(
        preset_name=QualityPreset.HIGH_FORENSIC,
        description="Visually lossless - Imperceptible quality loss",
        crf_h264=18,  # Visually lossless
        crf_h265=20,  # HEVC is more efficient
        preset="medium",
        audio_codec="aac",
        audio_bitrate="192k",
        tune="film",
        profile="high",
        pixel_format="yuv420p",
        use_case=(
            "Recommended for most forensic work. Excellent quality with reasonable file sizes. "
            "Suitable for court presentation and detailed analysis."
        )
    ),
    
    QualityPreset.MEDIUM_FORENSIC: ForensicPresetDefinition(
        preset_name=QualityPreset.MEDIUM_FORENSIC,
        description="High quality - Minor compression artifacts",
        crf_h264=23,  # Good quality
        crf_h265=25,
        preset="medium",
        audio_codec="aac",
        audio_bitrate="128k",
        tune="film",
        profile="main",
        pixel_format="yuv420p",
        use_case=(
            "Balanced quality and file size. Suitable for working copies and general review. "
            "Small compression artifacts may be visible on close inspection."
        )
    ),
    
    QualityPreset.WEB_DELIVERY: ForensicPresetDefinition(
        preset_name=QualityPreset.WEB_DELIVERY,
        description="Optimized for web streaming and sharing",
        crf_h264=28,  # Moderate quality
        crf_h265=30,
        preset="fast",
        audio_codec="aac",
        audio_bitrate="128k",
        profile="main",
        pixel_format="yuv420p",
        use_case=(
            "For sharing via email, web portals, or streaming. "
            "Smaller files with acceptable quality for general viewing."
        )
    ),
}


# === Hardware Encoder Preset Mappings ===
# Hardware encoders use different preset names, so we map forensic presets to hardware presets

NVENC_PRESET_MAPPING: Dict[QualityPreset, str] = {
    QualityPreset.LOSSLESS_FORENSIC: "p7",  # Highest quality (slowest)
    QualityPreset.HIGH_FORENSIC: "p6",      # Very high quality
    QualityPreset.MEDIUM_FORENSIC: "p5",    # Balanced
    QualityPreset.WEB_DELIVERY: "p3",       # Faster, lower quality
}

QSV_PRESET_MAPPING: Dict[QualityPreset, str] = {
    QualityPreset.LOSSLESS_FORENSIC: "veryslow",
    QualityPreset.HIGH_FORENSIC: "slow",
    QualityPreset.MEDIUM_FORENSIC: "medium",
    QualityPreset.WEB_DELIVERY: "fast",
}

AMF_PRESET_MAPPING: Dict[QualityPreset, str] = {
    QualityPreset.LOSSLESS_FORENSIC: "quality",
    QualityPreset.HIGH_FORENSIC: "quality",
    QualityPreset.MEDIUM_FORENSIC: "balanced",
    QualityPreset.WEB_DELIVERY: "speed",
}


# === CRF Adjustments for Hardware Encoders ===
# Hardware encoders may need different CRF values for equivalent quality

NVENC_CRF_ADJUSTMENT = 0  # NVENC CRF maps 1:1 with software
QSV_CRF_ADJUSTMENT = -3   # QSV needs lower CRF for similar quality (more aggressive)
AMF_CRF_ADJUSTMENT = -2   # AMF needs slightly lower CRF


# === Utility Functions ===

def get_preset_definition(preset: QualityPreset) -> ForensicPresetDefinition:
    """
    Get the definition for a forensic quality preset.
    
    Args:
        preset: QualityPreset enum value
    
    Returns:
        ForensicPresetDefinition for the preset
    
    Raises:
        KeyError: If preset is CUSTOM (custom presets don't have definitions)
    """
    if preset == QualityPreset.CUSTOM:
        raise ValueError("CUSTOM preset does not have a predefined definition")
    
    return FORENSIC_PRESETS[preset]


def get_preset_for_codec(preset: QualityPreset, codec: str) -> str:
    """
    Get the appropriate preset string for a given codec.
    
    For software codecs, returns the standard preset name.
    For hardware codecs, returns the mapped hardware-specific preset.
    
    Args:
        preset: QualityPreset enum value
        codec: Codec name (e.g., 'libx264', 'h264_nvenc')
    
    Returns:
        Preset string appropriate for the codec
    """
    if preset == QualityPreset.CUSTOM:
        return "medium"  # Default for custom
    
    # Hardware encoder mappings
    if 'nvenc' in codec.lower():
        return NVENC_PRESET_MAPPING.get(preset, "p5")
    elif 'qsv' in codec.lower():
        return QSV_PRESET_MAPPING.get(preset, "medium")
    elif 'amf' in codec.lower():
        return AMF_PRESET_MAPPING.get(preset, "balanced")
    
    # Software encoder - use standard preset
    preset_def = FORENSIC_PRESETS.get(preset)
    return preset_def.preset if preset_def else "medium"


def get_crf_for_preset(preset: QualityPreset, codec: str) -> int:
    """
    Get the appropriate CRF value for a preset and codec combination.
    
    Applies codec-specific adjustments for hardware encoders.
    
    Args:
        preset: QualityPreset enum value
        codec: Codec name
    
    Returns:
        CRF value
    """
    if preset == QualityPreset.CUSTOM:
        return 23  # Default CRF for custom
    
    preset_def = FORENSIC_PRESETS.get(preset)
    if not preset_def:
        return 23  # Safe default
    
    base_crf = preset_def.get_crf_for_codec(codec)
    
    # Apply hardware encoder adjustments
    if 'nvenc' in codec.lower():
        return max(0, base_crf + NVENC_CRF_ADJUSTMENT)
    elif 'qsv' in codec.lower():
        return max(0, base_crf + QSV_CRF_ADJUSTMENT)
    elif 'amf' in codec.lower():
        return max(0, base_crf + AMF_CRF_ADJUSTMENT)
    
    return base_crf


def get_audio_settings_for_preset(preset: QualityPreset) -> tuple[str, str]:
    """
    Get audio codec and bitrate for a preset.
    
    Args:
        preset: QualityPreset enum value
    
    Returns:
        Tuple of (audio_codec, audio_bitrate)
    """
    if preset == QualityPreset.CUSTOM:
        return ("aac", "192k")
    
    preset_def = FORENSIC_PRESETS.get(preset)
    if not preset_def:
        return ("aac", "192k")
    
    return (preset_def.audio_codec, preset_def.audio_bitrate)


def get_all_preset_names() -> list[str]:
    """Get list of all forensic preset names (excluding CUSTOM)."""
    return [
        preset.value 
        for preset in QualityPreset 
        if preset != QualityPreset.CUSTOM
    ]


def get_preset_description(preset: QualityPreset) -> str:
    """
    Get human-readable description of a preset.
    
    Args:
        preset: QualityPreset enum value
    
    Returns:
        Description string
    """
    if preset == QualityPreset.CUSTOM:
        return "Custom settings defined by user"
    
    preset_def = FORENSIC_PRESETS.get(preset)
    return preset_def.description if preset_def else "Unknown preset"


def get_preset_use_case(preset: QualityPreset) -> str:
    """
    Get use case description for a preset.
    
    Args:
        preset: QualityPreset enum value
    
    Returns:
        Use case description string
    """
    if preset == QualityPreset.CUSTOM:
        return "User-defined parameters for specific requirements"
    
    preset_def = FORENSIC_PRESETS.get(preset)
    return preset_def.use_case if preset_def else ""
