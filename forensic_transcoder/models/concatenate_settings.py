"""
Concatenate settings data model.

Defines configuration parameters for video concatenation jobs.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
from enum import Enum


class ConcatenationMode(Enum):
    """Concatenation processing modes."""
    AUTO = "auto"  # Automatically decide based on spec analysis
    MUX = "mux"  # Fast mux (no re-encode) - requires matching specs
    TRANSCODE = "transcode"  # Re-encode all clips to match specs


class TransitionType(Enum):
    """Transition effects between clips."""
    NONE = "none"  # Hard cut
    FADE = "fade"  # Crossfade
    DISSOLVE = "dissolve"  # Dissolve transition
    WIPE = "wipe"  # Wipe transition


class SlatePosition(Enum):
    """Where to insert slates for gaps/markers."""
    NONE = "none"  # No slates
    GAPS_ONLY = "gaps_only"  # Only for time gaps
    ALL_TRANSITIONS = "all_transitions"  # Between every clip


@dataclass
class ConcatenateSettings:
    """
    Configuration for video concatenation job.
    
    This model contains all parameters needed to configure concatenation of multiple
    video files, including mode selection (mux vs transcode), normalization specs,
    transition effects, and output settings.
    """
    
    # === Concatenation Mode ===
    concatenation_mode: ConcatenationMode = ConcatenationMode.AUTO
    
    # === Input Files ===
    input_files: List[Path] = field(default_factory=list)
    maintain_input_order: bool = True  # If False, allow reordering for optimization
    
    # === Output Configuration ===
    output_file: Optional[Path] = None
    output_format: str = "mp4"
    overwrite_existing: bool = False
    
    # === Normalization Settings (for transcode mode) ===
    target_codec: str = "libx264"
    target_width: Optional[int] = None  # None = use highest resolution from inputs
    target_height: Optional[int] = None
    target_fps: Optional[float] = None  # None = use most common FPS from inputs
    target_pixel_format: str = "yuv420p"
    
    # === Quality Settings (for transcode mode) ===
    crf: int = 18  # High quality default for forensic use
    preset: str = "medium"
    
    # === Audio Settings ===
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    audio_sample_rate: int = 48000
    normalize_audio: bool = False  # Match audio levels across clips
    
    # === Transition Effects ===
    transition_type: TransitionType = TransitionType.NONE
    transition_duration: float = 0.5  # Duration in seconds
    
    # === Slate/Gap Handling ===
    slate_position: SlatePosition = SlatePosition.GAPS_ONLY
    slate_duration: float = 2.0  # Duration of slate in seconds
    slate_text_template: str = "Gap: {duration}"  # Template for slate text
    slate_background_color: str = "black"
    slate_text_color: str = "white"
    slate_font_size: int = 48
    
    # === Hardware Acceleration ===
    use_hardware_encoder: bool = False
    use_hardware_decoder: bool = False
    gpu_index: int = 0
    
    # === Advanced Options ===
    preserve_metadata: bool = True
    preserve_chapters: bool = True
    two_pass_encoding: bool = False  # For transcode mode
    
    # === Spec Matching Analysis ===
    require_exact_match: bool = False  # If True, fail if specs don't match (for mux mode)
    allow_minor_differences: bool = True  # Allow small fps/resolution differences
    
    # === Processing ===
    create_intermediate_files: bool = False  # Keep intermediate normalized clips
    intermediate_directory: Optional[Path] = None
    
    def __post_init__(self):
        """Validate settings after initialization."""
        # Ensure paths are Path objects
        if self.output_file and not isinstance(self.output_file, Path):
            self.output_file = Path(self.output_file)
        
        if self.intermediate_directory and not isinstance(self.intermediate_directory, Path):
            self.intermediate_directory = Path(self.intermediate_directory)
        
        # Convert input file strings to Path objects
        self.input_files = [
            Path(f) if not isinstance(f, Path) else f 
            for f in self.input_files
        ]
        
        # Validate transition duration
        if self.transition_duration < 0:
            raise ValueError(f"Transition duration must be non-negative, got {self.transition_duration}")
        
        # Validate slate duration
        if self.slate_duration < 0:
            raise ValueError(f"Slate duration must be non-negative, got {self.slate_duration}")
        
        # Validate CRF
        if not (0 <= self.crf <= 51):
            raise ValueError(f"CRF must be between 0 and 51, got {self.crf}")
        
        # Validate target FPS if provided
        if self.target_fps is not None:
            if not (1.0 <= self.target_fps <= 240.0):
                raise ValueError(f"Target FPS must be between 1 and 240, got {self.target_fps}")
        
        # Validate resolution if provided
        if self.target_width is not None and self.target_width <= 0:
            raise ValueError(f"Target width must be positive, got {self.target_width}")
        if self.target_height is not None and self.target_height <= 0:
            raise ValueError(f"Target height must be positive, got {self.target_height}")
        
        # Validate at least 2 input files for concatenation
        if len(self.input_files) < 2:
            raise ValueError(f"Concatenation requires at least 2 input files, got {len(self.input_files)}")
    
    def to_dict(self) -> dict:
        """Convert settings to dictionary for serialization."""
        return {
            'concatenation_mode': self.concatenation_mode.value,
            'input_files': [str(f) for f in self.input_files],
            'maintain_input_order': self.maintain_input_order,
            'output_file': str(self.output_file) if self.output_file else None,
            'output_format': self.output_format,
            'overwrite_existing': self.overwrite_existing,
            'target_codec': self.target_codec,
            'target_width': self.target_width,
            'target_height': self.target_height,
            'target_fps': self.target_fps,
            'target_pixel_format': self.target_pixel_format,
            'crf': self.crf,
            'preset': self.preset,
            'audio_codec': self.audio_codec,
            'audio_bitrate': self.audio_bitrate,
            'audio_sample_rate': self.audio_sample_rate,
            'normalize_audio': self.normalize_audio,
            'transition_type': self.transition_type.value,
            'transition_duration': self.transition_duration,
            'slate_position': self.slate_position.value,
            'slate_duration': self.slate_duration,
            'slate_text_template': self.slate_text_template,
            'slate_background_color': self.slate_background_color,
            'slate_text_color': self.slate_text_color,
            'slate_font_size': self.slate_font_size,
            'use_hardware_encoder': self.use_hardware_encoder,
            'use_hardware_decoder': self.use_hardware_decoder,
            'gpu_index': self.gpu_index,
            'preserve_metadata': self.preserve_metadata,
            'preserve_chapters': self.preserve_chapters,
            'two_pass_encoding': self.two_pass_encoding,
            'require_exact_match': self.require_exact_match,
            'allow_minor_differences': self.allow_minor_differences,
            'create_intermediate_files': self.create_intermediate_files,
            'intermediate_directory': str(self.intermediate_directory) if self.intermediate_directory else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ConcatenateSettings':
        """Create settings from dictionary."""
        # Convert enum strings back to enums
        if 'concatenation_mode' in data:
            data['concatenation_mode'] = ConcatenationMode(data['concatenation_mode'])
        if 'transition_type' in data:
            data['transition_type'] = TransitionType(data['transition_type'])
        if 'slate_position' in data:
            data['slate_position'] = SlatePosition(data['slate_position'])
        
        # Convert path strings back to Path objects
        if 'output_file' in data and data['output_file']:
            data['output_file'] = Path(data['output_file'])
        if 'intermediate_directory' in data and data['intermediate_directory']:
            data['intermediate_directory'] = Path(data['intermediate_directory'])
        if 'input_files' in data:
            data['input_files'] = [Path(f) for f in data['input_files']]
        
        return cls(**data)
