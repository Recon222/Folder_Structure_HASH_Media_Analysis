# Forensic Transcoder - Data Models

## Overview

All models use Python `@dataclass` for clean, declarative definitions with built-in validation, JSON serialization, and type safety through enums.

## Models Index

1. **TranscodeSettings** - Transcode configuration (30+ parameters)
2. **ConcatenateSettings** - Concatenation configuration (20+ parameters)
3. **ProcessingResult** - Operation outcome tracking
4. **BatchProcessingStatistics** - Batch operation aggregation
5. **VideoAnalysis** - FFprobe metadata extraction
6. **AudioStreamInfo** - Audio stream metadata
7. **SubtitleStreamInfo** - Subtitle stream metadata

---

## 1. TranscodeSettings

**File**: `models/transcode_settings.py`

### Purpose
Complete configuration for video transcoding operations, including output format, codec selection, quality settings, audio handling, and hardware acceleration.

### Class Definition

```python
@dataclass
class TranscodeSettings:
    # Output Configuration
    output_format: str = "mp4"
    output_directory: Optional[Path] = None
    output_filename_pattern: str = "{original_name}_transcoded.{ext}"
    overwrite_existing: bool = False

    # Video Codec
    video_codec: str = "libx264"

    # Quality Settings
    quality_preset: QualityPreset = QualityPreset.HIGH_FORENSIC
    crf: Optional[int] = None
    preset: Optional[str] = None
    tune: Optional[str] = None
    profile: Optional[str] = None
    level: Optional[str] = None

    # Resolution & Scaling
    output_width: Optional[int] = None
    output_height: Optional[int] = None
    scaling_algorithm: ScalingAlgorithm = ScalingAlgorithm.LANCZOS
    maintain_aspect_ratio: bool = True

    # Frame Rate
    target_fps: Optional[float] = None
    fps_method: FPSMethod = FPSMethod.AUTO
    analyze_vfr: bool = True

    # Audio Settings
    audio_codec: str = "copy"
    audio_bitrate: Optional[str] = None
    audio_sample_rate: Optional[int] = None
    audio_channels: Optional[int] = None

    # Hardware Acceleration
    use_hardware_encoder: bool = False
    use_hardware_decoder: bool = False
    gpu_index: int = 0

    # Advanced Video Settings
    pixel_format: Optional[str] = None
    color_space: Optional[str] = None
    color_range: Optional[str] = None
    bitrate: Optional[str] = None
    max_bitrate: Optional[str] = None
    buffer_size: Optional[str] = None

    # Metadata
    preserve_metadata: bool = True
    preserve_timestamps: bool = True
    copy_chapters: bool = True

    # Filters
    deinterlace: bool = False
    custom_video_filters: List[str] = field(default_factory=list)
    custom_audio_filters: List[str] = field(default_factory=list)

    # Processing Options
    max_parallel_jobs: int = 4
    two_pass_encoding: bool = False

    # Subtitle Handling
    copy_subtitles: bool = True
    burn_subtitles: bool = False
    subtitle_track: Optional[int] = None
```

### Validation (\_\_post_init\_\_)

```python
def __post_init__(self):
    # Path conversion
    if self.output_directory and not isinstance(self.output_directory, Path):
        self.output_directory = Path(self.output_directory)

    # CRF range validation
    if self.crf is not None:
        if not (0 <= self.crf <= 51):
            raise ValueError(f"CRF must be between 0 and 51, got {self.crf}")

    # FPS validation
    if self.target_fps is not None:
        if not (1.0 <= self.target_fps <= 240.0):
            raise ValueError(f"Target FPS must be between 1 and 240")

    # Resolution validation
    if self.output_width is not None and self.output_width <= 0:
        raise ValueError(f"Output width must be positive")
    if self.output_height is not None and self.output_height <= 0:
        raise ValueError(f"Output height must be positive")

    # Parallel jobs validation
    if self.max_parallel_jobs < 1:
        raise ValueError(f"max_parallel_jobs must be at least 1")
```

### Supporting Enums

#### QualityPreset
```python
class QualityPreset(Enum):
    LOSSLESS_FORENSIC = "lossless_forensic"  # CRF 0, mathematically lossless
    HIGH_FORENSIC = "high_forensic"          # CRF 18, visually lossless
    MEDIUM_FORENSIC = "medium_forensic"      # CRF 23, high quality
    WEB_DELIVERY = "web_delivery"            # CRF 28, web-optimized
    CUSTOM = "custom"                        # User-defined settings
```

#### FPSMethod
```python
class FPSMethod(Enum):
    DUPLICATE = "duplicate"      # Duplicate/drop frames (fps filter)
    PTS_ADJUST = "pts_adjust"    # Adjust timestamps (changes speed)
    AUTO = "auto"                # Service decides based on analysis
```

#### ScalingAlgorithm
```python
class ScalingAlgorithm(Enum):
    LANCZOS = "lanczos"    # Highest quality, slower
    BICUBIC = "bicubic"    # High quality, balanced
    BILINEAR = "bilinear"  # Fast, lower quality
    NEIGHBOR = "neighbor"  # Fastest, pixelated
    SPLINE = "spline"      # Smooth, good for downscaling
```

### Serialization

```python
def to_dict(self) -> dict:
    return {
        'output_format': self.output_format,
        'video_codec': self.video_codec,
        'quality_preset': self.quality_preset.value,  # Enum to string
        # ... all fields
    }

@classmethod
def from_dict(cls, data: dict) -> 'TranscodeSettings':
    # Convert enum strings back to enums
    if 'quality_preset' in data:
        data['quality_preset'] = QualityPreset(data['quality_preset'])
    # ... etc
    return cls(**data)
```

---

## 2. ConcatenateSettings

**File**: `models/concatenate_settings.py`

### Purpose
Configuration for joining multiple video files with optional re-encoding, transitions, and normalization.

### Class Definition (Condensed)

```python
@dataclass
class ConcatenateSettings:
    # Mode
    concatenation_mode: ConcatenationMode = ConcatenationMode.AUTO  # AUTO, MUX, TRANSCODE

    # Input/Output
    input_files: List[Path] = field(default_factory=list)
    maintain_input_order: bool = True
    output_file: Optional[Path] = None
    output_format: str = "mp4"
    overwrite_existing: bool = False

    # Normalization (for TRANSCODE mode)
    target_codec: str = "libx264"
    target_width: Optional[int] = None      # None = use highest from inputs
    target_height: Optional[int] = None
    target_fps: Optional[float] = None      # None = use most common FPS
    target_pixel_format: str = "yuv420p"

    # Quality (for TRANSCODE mode)
    crf: int = 18
    preset: str = "medium"

    # Audio
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    audio_sample_rate: int = 48000
    normalize_audio: bool = False

    # Transitions
    transition_type: TransitionType = TransitionType.NONE
    transition_duration: float = 0.5  # seconds

    # Slate/Gap Handling
    slate_position: SlatePosition = SlatePosition.GAPS_ONLY
    slate_duration: float = 2.0
    slate_text_template: str = "Gap: {duration}"
    slate_background_color: str = "black"
    slate_text_color: str = "white"
    slate_font_size: int = 48

    # Hardware
    use_hardware_encoder: bool = False
    use_hardware_decoder: bool = False
    gpu_index: int = 0

    # Advanced
    preserve_metadata: bool = True
    preserve_chapters: bool = True
    two_pass_encoding: bool = False
    require_exact_match: bool = False         # For MUX mode validation
    allow_minor_differences: bool = True
    create_intermediate_files: bool = False
    intermediate_directory: Optional[Path] = None
```

### Supporting Enums

```python
class ConcatenationMode(Enum):
    AUTO = "auto"            # Decide based on spec analysis
    MUX = "mux"              # Fast, no re-encode (requires matching specs)
    TRANSCODE = "transcode"  # Re-encode all to match specs

class TransitionType(Enum):
    NONE = "none"          # Hard cut
    FADE = "fade"          # Crossfade
    DISSOLVE = "dissolve"  # Dissolve effect
    WIPE = "wipe"          # Wipe transition

class SlatePosition(Enum):
    NONE = "none"                    # No slates
    GAPS_ONLY = "gaps_only"          # Only for time gaps
    ALL_TRANSITIONS = "all_transitions"  # Between every clip
```

### Validation

```python
def __post_init__(self):
    # Path conversion
    if self.output_file and not isinstance(self.output_file, Path):
        self.output_file = Path(self.output_file)

    # Validate at least 2 input files
    if len(self.input_files) < 2:
        raise ValueError("Concatenation requires at least 2 input files")

    # Validate durations
    if self.transition_duration < 0:
        raise ValueError("Transition duration must be non-negative")
    if self.slate_duration < 0:
        raise ValueError("Slate duration must be non-negative")

    # Validate CRF, FPS, resolution (similar to TranscodeSettings)
```

---

## 3. ProcessingResult

**File**: `models/processing_result.py`

### Purpose
Track the outcome, timing, and statistics of a single video processing operation.

### Class Definition

```python
@dataclass
class ProcessingResult:
    # Operation Info
    processing_type: ProcessingType
    input_file: Path
    output_file: Optional[Path] = None

    # Status
    status: ProcessingStatus = ProcessingStatus.IN_PROGRESS

    # Timing
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # File Information
    input_size_bytes: Optional[int] = None
    output_size_bytes: Optional[int] = None
    compression_ratio: Optional[float] = None  # output / input

    # Performance Metrics
    encoding_speed: Optional[float] = None  # Multiplier (e.g., 2.3x realtime)
    average_fps: Optional[float] = None
    frames_processed: Optional[int] = None

    # Error Handling
    error_message: Optional[str] = None
    error_code: Optional[int] = None
    error_details: Optional[str] = None  # Stack trace

    # Warnings
    warnings: List[str] = field(default_factory=list)

    # FFmpeg Data
    ffmpeg_command: Optional[str] = None
    ffmpeg_output: Optional[str] = None  # Full stderr for debugging
```

### Status Management Methods

```python
def mark_complete(self, status: ProcessingStatus = ProcessingStatus.SUCCESS):
    self.status = status
    self.end_time = datetime.now()
    if self.start_time and self.end_time:
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
    if self.input_size_bytes and self.output_size_bytes:
        self.compression_ratio = self.output_size_bytes / self.input_size_bytes

def mark_failed(self, error_message: str, error_code: Optional[int] = None):
    self.status = ProcessingStatus.FAILED
    self.error_message = error_message
    self.error_code = error_code
    self.mark_complete(ProcessingStatus.FAILED)

def mark_cancelled(self):
    self.status = ProcessingStatus.CANCELLED
    self.mark_complete(ProcessingStatus.CANCELLED)

def add_warning(self, warning: str):
    self.warnings.append(warning)
```

### Computed Properties

```python
@property
def is_success(self) -> bool:
    return self.status == ProcessingStatus.SUCCESS

@property
def is_failed(self) -> bool:
    return self.status == ProcessingStatus.FAILED

@property
def is_complete(self) -> bool:
    return self.status in [SUCCESS, FAILED, CANCELLED, SKIPPED]

@property
def duration_formatted(self) -> str:
    """Returns '00:02:34' format"""
    if not self.duration_seconds:
        return "00:00:00"
    hours = int(self.duration_seconds // 3600)
    minutes = int((self.duration_seconds % 3600) // 60)
    seconds = int(self.duration_seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

@property
def compression_percent(self) -> Optional[float]:
    """Output size as percentage of input (e.g., 65.5%)"""
    if self.compression_ratio is None:
        return None
    return self.compression_ratio * 100.0

@property
def size_saved_bytes(self) -> Optional[int]:
    """Bytes saved (negative if file grew)"""
    if self.input_size_bytes is None or self.output_size_bytes is None:
        return None
    return self.input_size_bytes - self.output_size_bytes
```

### Supporting Enums

```python
class ProcessingStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    IN_PROGRESS = "in_progress"

class ProcessingType(Enum):
    TRANSCODE = "transcode"
    CONCATENATE = "concatenate"
    ANALYSIS = "analysis"
```

---

## 4. BatchProcessingStatistics

**File**: `models/processing_result.py`

### Purpose
Aggregate results from multiple processing operations for batch reporting.

### Class Definition

```python
@dataclass
class BatchProcessingStatistics:
    total_files: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    cancelled: int = 0

    total_duration_seconds: float = 0.0
    total_input_size_bytes: int = 0
    total_output_size_bytes: int = 0

    results: List[ProcessingResult] = field(default_factory=list)
```

### Methods

```python
def add_result(self, result: ProcessingResult):
    """Add a processing result to statistics"""
    self.results.append(result)
    self.total_files += 1

    if result.status == ProcessingStatus.SUCCESS:
        self.successful += 1
    elif result.status == ProcessingStatus.FAILED:
        self.failed += 1
    # ... etc

    if result.duration_seconds:
        self.total_duration_seconds += result.duration_seconds
    if result.input_size_bytes:
        self.total_input_size_bytes += result.input_size_bytes
    if result.output_size_bytes:
        self.total_output_size_bytes += result.output_size_bytes
```

### Computed Properties

```python
@property
def success_rate(self) -> float:
    """Success rate as percentage"""
    if self.total_files == 0:
        return 0.0
    return (self.successful / self.total_files) * 100.0

@property
def average_compression_ratio(self) -> Optional[float]:
    if self.total_input_size_bytes == 0:
        return None
    return self.total_output_size_bytes / self.total_input_size_bytes

@property
def average_duration_seconds(self) -> float:
    if self.successful == 0:
        return 0.0
    return self.total_duration_seconds / self.successful

@property
def total_size_saved_bytes(self) -> int:
    return self.total_input_size_bytes - self.total_output_size_bytes
```

---

## 5. VideoAnalysis

**File**: `models/video_analysis.py`

### Purpose
Store comprehensive metadata extracted from video files via FFprobe, used for transcode decision-making and concatenation compatibility checks.

### Class Definition (Condensed)

```python
@dataclass
class VideoAnalysis:
    # File Information
    file_path: Path
    file_size: int
    format_name: str  # mp4, mkv, avi, etc.
    format_long_name: str

    # Video Stream
    video_codec: str  # h264, hevc, vp9
    video_codec_long_name: str
    width: int
    height: int
    pixel_format: str  # yuv420p, yuv422p, etc.

    # Frame Rate
    fps: float
    fps_string: str  # e.g., "30000/1001"
    frame_rate_type: FrameRateType = FrameRateType.UNKNOWN
    avg_frame_rate: Optional[float] = None
    total_frames: Optional[int] = None

    # Duration & Timing
    duration: float  # seconds
    start_time: Optional[float] = None

    # Bitrate
    overall_bitrate: Optional[int] = None
    video_bitrate: Optional[int] = None

    # Color & Format
    color_space: Optional[str] = None  # bt709, bt2020nc
    color_range: Optional[str] = None  # tv, pc
    color_primaries: Optional[str] = None
    color_transfer: Optional[str] = None

    # Advanced Properties
    profile: Optional[str] = None
    level: Optional[str] = None
    bit_depth: Optional[int] = None
    has_b_frames: bool = False
    gop_size: Optional[int] = None

    # Streams
    audio_streams: List[AudioStreamInfo] = field(default_factory=list)
    subtitle_streams: List[SubtitleStreamInfo] = field(default_factory=list)

    # Metadata
    creation_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    has_chapters: bool = False
    chapter_count: int = 0

    # Analysis Metadata
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    ffprobe_version: Optional[str] = None
```

### Computed Properties

```python
@property
def resolution_string(self) -> str:
    return f"{self.width}x{self.height}"

@property
def aspect_ratio(self) -> float:
    return self.width / self.height if self.height > 0 else 0.0

@property
def has_audio(self) -> bool:
    return len(self.audio_streams) > 0

@property
def is_vfr(self) -> bool:
    """Check if variable frame rate"""
    return self.frame_rate_type == FrameRateType.VARIABLE

@property
def is_hdr(self) -> bool:
    """Simple HDR detection heuristic"""
    if self.color_space in ['bt2020nc', 'bt2020c']:
        return True
    if self.color_transfer in ['smpte2084', 'arib-std-b67']:  # HDR10, HLG
        return True
    return False
```

### Compatibility Checking

```python
def get_spec_fingerprint(self) -> str:
    """Generate fingerprint for quick matching"""
    return (
        f"{self.video_codec}_"
        f"{self.width}x{self.height}_"
        f"{self.fps:.3f}_"
        f"{self.pixel_format}"
    )

def is_compatible_with(self, other: 'VideoAnalysis', strict: bool = True) -> bool:
    """Check if videos can be concatenated without re-encoding"""
    if strict:
        return (
            self.video_codec == other.video_codec and
            self.width == other.width and
            self.height == other.height and
            abs(self.fps - other.fps) < 0.01 and
            self.pixel_format == other.pixel_format
        )
    else:
        # Allow minor FPS differences (within 1 fps)
        fps_compatible = abs(self.fps - other.fps) < 1.0
        codec_compatible = self.video_codec == other.video_codec
        resolution_compatible = (self.width == other.width and
                                self.height == other.height)
        return codec_compatible and resolution_compatible and fps_compatible
```

### Supporting Enums

```python
class FrameRateType(Enum):
    CONSTANT = "constant"  # CFR
    VARIABLE = "variable"  # VFR
    UNKNOWN = "unknown"

class StreamType(Enum):
    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"
    DATA = "data"
```

---

## 6. AudioStreamInfo

**File**: `models/video_analysis.py`

### Purpose
Metadata for a single audio stream within a video file.

```python
@dataclass
class AudioStreamInfo:
    stream_index: int
    codec: str
    codec_long_name: str
    sample_rate: int
    channels: int
    channel_layout: Optional[str]  # "stereo", "5.1", etc.
    bitrate: Optional[int]
    duration: Optional[float]
```

---

## 7. SubtitleStreamInfo

**File**: `models/video_analysis.py`

### Purpose
Metadata for a single subtitle stream within a video file.

```python
@dataclass
class SubtitleStreamInfo:
    stream_index: int
    codec: str
    codec_long_name: str
    language: Optional[str]  # ISO 639 code (e.g., "eng", "spa")
    title: Optional[str]     # Subtitle track name
```

---

## Model Design Patterns Summary

### Validation Strategy
All models validate in `__post_init__`:
- Path string → Path object conversion
- Range validation (CRF 0-51, FPS 1-240)
- Consistency checks (min 2 files for concatenation)
- Type enforcement through enums

### Serialization Pattern
Consistent `to_dict`/`from_dict` for persistence:
- Enums → strings in dict
- Paths → strings in dict
- Datetime → ISO format strings
- Restore types on `from_dict`

### Property Pattern
Extensive use of `@property` for computed values:
- Avoid storing derived data
- Always calculate from source fields
- Prevents stale data issues

### Type Safety
- All enums prevent magic strings
- Optional types are explicit
- Lists use `field(default_factory=list)` for safety

---

**Next**: [03_SERVICES_LAYER.md](./03_SERVICES_LAYER.md) - Service implementations
