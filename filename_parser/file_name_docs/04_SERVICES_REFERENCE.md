# Services Reference - Complete Service Catalog

## Service Organization

The Filename Parser contains **20+ specialized services** organized by responsibility.

## Pattern System Services

### PatternMatcher
**File**: `services/pattern_matcher.py`

**Purpose**: Match filenames against regex patterns with component extraction and validation.

**Key Methods**:
```python
def match(filename: str, pattern_id: Optional[str] = None) -> Optional[PatternMatch]:
    """
    Match filename against patterns (monolithic or two-phase).
    Returns: PatternMatch with components dict and validation status
    """

def validate_components(components: dict, pattern: PatternDefinition) -> tuple[bool, List[str]]:
    """
    Validate extracted components against pattern constraints.
    Returns: (is_valid, error_messages)
    """
```

**Usage**:
```python
matcher = PatternMatcher()
result = matcher.match("CH01-20171215143022.DAV")
# result.pattern.name = "Dahua NVR Standard"
# result.components = {"channel": 1, "year": 2017, "month": 12, ...}
```

---

### PatternLibrary
**File**: `services/pattern_library.py`

**Purpose**: Manages collection of 15+ built-in patterns with priority ordering.

**Key Methods**:
```python
def get_all_patterns() -> List[PatternDefinition]:
    """Get all patterns sorted by priority (high → low)"""

def get_pattern(pattern_id: str) -> Optional[PatternDefinition]:
    """Get specific pattern by ID"""

def search_patterns(query: str = None, category: str = None, ...) -> List[PatternDefinition]:
    """Search patterns by criteria"""
```

---

### TimeExtractor
**File**: `services/time_extractor.py`

**Purpose**: Convert component dictionaries to TimeData objects.

**Key Methods**:
```python
def extract(pattern_match: PatternMatch) -> Optional[TimeData]:
    """
    Convert {"year": 2024, "month": 1, "hours": 14, ...} → TimeData
    Handles missing components, validates ranges
    """
```

---

### ComponentExtractor
**File**: `services/component_extractor.py`

**Purpose**: Two-phase fallback extraction when regex patterns fail.

**Key Methods**:
```python
def extract_best_components(filename: str) -> tuple[Optional[DateComponent], Optional[TimeComponent]]:
    """
    Extract date and time independently with confidence scoring.
    Tries multiple formats, returns best match with confidence.
    """
```

---

### SMPTEConverter
**File**: `services/smpte_converter.py`

**Purpose**: Convert TimeData + FPS → SMPTE timecode (HH:MM:SS:FF).

**Key Methods**:
```python
def convert_to_smpte(time_data: TimeData, fps: float) -> Optional[str]:
    """
    Convert TimeData to SMPTE timecode.
    Returns: "14:30:25:15" (HH:MM:SS:FF)
    """

def apply_time_offset(smpte: str, offset_dict: dict, fps: float) -> Optional[str]:
    """Apply DVR time offset correction (behind/ahead)"""
```

---

## Core Processing Services

### FilenameParserService
**File**: `services/filename_parser_service.py`

**Purpose**: Orchestrates pattern → time → SMPTE workflow.

**Key Methods**:
```python
def parse_filename(filename: str, pattern_id: Optional[str] = None,
                  fps: Optional[float] = None,
                  time_offset: Optional[dict] = None) -> Result[ParseResult]:
    """
    Complete parsing pipeline:
    1. PatternMatcher.match()
    2. TimeExtractor.extract()
    3. SMPTEConverter.convert_to_smpte()
    4. (Optional) SMPTEConverter.apply_time_offset()
    Returns: Result[ParseResult] with all metadata
    """
```

---

### BatchProcessorService
**File**: `services/batch_processor_service.py`

**Purpose**: Multi-file processing with parallel frame rate detection.

**Key Methods**:
```python
def process_files(files: List[Path], settings: FilenameParserSettings,
                 progress_callback: Optional[Callable] = None) -> Result[ProcessingStatistics]:
    """
    Process multiple files in batch:
    1. Detect frame rates (parallel)
    2. Parse filenames (sequential)
    3. Write metadata (sequential)
    4. Export CSV (if enabled)
    Returns: ProcessingStatistics with per-file results
    """
```

**Orchestration Flow**:
```
BatchProcessorService
  ├─► FrameRateService (parallel detection)
  ├─► FilenameParserService (per file)
  ├─► FFmpegMetadataWriterService (per file)
  └─► CSVExportService (batch export)
```

---

### FrameRateService
**File**: `services/frame_rate_service.py`

**Purpose**: Detect video frame rates using FFprobe (parallel execution).

**Key Methods**:
```python
def detect_batch_frame_rates(files: List[Path], use_default_on_failure: bool = True,
                            progress_callback: Optional[Callable] = None) -> dict[Path, float]:
    """
    Parallel frame rate detection using ThreadPoolExecutor.
    Returns: {file_path: fps} dictionary
    """

def extract_video_metadata(file_path: Path, smpte_timecode: str,
                          camera_path: str) -> Result[VideoMetadata]:
    """
    Extract complete video metadata:
    - Resolution, codec, duration, bitrate
    - First frame PTS (sub-second accuracy)
    - Calculate ISO8601 start/end times
    """
```

---

### FFmpegMetadataWriterService
**File**: `services/ffmpeg_metadata_writer_service.py`

**Purpose**: Write SMPTE timecode to video metadata using FFmpeg.

**Key Methods**:
```python
def write_metadata(input_path: Path, output_path: Path, smpte_timecode: str,
                  lossless: bool = True) -> Result[Path]:
    """
    Write SMPTE timecode to video file:
    - Lossless: Copy codecs, no re-encode
    - Re-encode: Convert to forensic-compatible format if needed
    Returns: Result[output_path]
    """
```

---

## Timeline & Rendering Services

### FFmpegTimelineBuilder
**File**: `services/ffmpeg_timeline_builder.py`

**Purpose**: GPT-5 single-pass FFmpeg command generation.

**Key Methods**:
```python
def build_command(clips: List[Clip], settings: RenderSettings,
                 output_path: Path, timeline_is_absolute: bool = True) -> Tuple[List[str], str]:
    """
    Build complete FFmpeg command for timeline rendering:
    1. Normalize clip times to seconds from t0
    2. Build atomic intervals
    3. Classify intervals → segments (GAP/SINGLE/OVERLAP)
    4. Emit FFmpeg command with filter script file
    Returns: (argv list, filter_script_path)
    """

def estimate_argv_length(clips: List[Clip], settings: RenderSettings,
                        with_hwaccel: bool = False) -> int:
    """Estimate command line length before building (for batch decision)"""
```

**Algorithm Steps**:
1. `_normalize_clip_times()` - ISO8601 → seconds from earliest
2. `_build_atomic_intervals()` - Collect time boundaries, create intervals
3. `_segments_from_intervals()` - Classify as GAP/SINGLE/OVERLAP
4. `_emit_ffmpeg_argv()` - Generate command + filter script

---

### MulticamRendererService
**File**: `services/multicam_renderer_service.py`

**Purpose**: Orchestrates timeline rendering with batch fallback.

**Key Methods**:
```python
def render_timeline(videos: List[VideoMetadata], settings: RenderSettings,
                   progress_callback: Optional[Callable] = None) -> Result[Path]:
    """
    Render timeline video:
    1. Convert VideoMetadata → Clips
    2. Estimate argv length
    3. Route to single-pass or batch rendering
    4. Execute FFmpeg and monitor progress
    Returns: Result[output_path]
    """
```

**Routing Logic**:
```python
if estimated_length < 28,000:
    return _render_single_pass()
else:
    return _render_in_batches()  # Timeline-aware splitting
```

---

### TimelineCalculatorService
**File**: `services/timeline_calculator_service.py`

**Purpose**: Detect gaps and overlaps in video timeline.

**Key Methods**:
```python
def calculate_timeline(videos: List[VideoMetadata], sequence_fps: float = 30.0,
                      min_gap_seconds: float = 5.0) -> Result[Timeline]:
    """
    Analyze timeline for gaps and overlaps:
    Returns: Timeline with gap_periods and overlap_periods lists
    """
```

---

### SlateGeneratorService
**File**: `services/slate_generator_service.py`

**Purpose**: Generate gap slate text with user-configurable templates.

**Key Methods**:
```python
def generate_slate_text(gap_start: datetime, gap_end: datetime,
                       duration_seconds: float, settings: RenderSettings) -> str:
    """
    Format gap slate text using templates:
    - time_only: "GAP from 19:30:00 to 19:35:00"
    - date_time: "GAP: Tue 21 May 19:30:00 → ..."
    - duration_multiline: Multiline with expanded duration
    """
```

---

### VideoMetadataExtractor
**File**: `services/video_metadata_extractor.py`

**Purpose**: Extract complete video metadata via FFprobe.

**Key Methods**:
```python
def extract(file_path: Path, smpte_timecode: Optional[str] = None,
           camera_path: Optional[str] = None) -> Result[VideoMetadata]:
    """
    Extract complete metadata:
    - Resolution, codec, pixel format, bitrate
    - Duration in seconds
    - First frame PTS (sub-second offset)
    - First frame type (I/P/B) and keyframe status
    Returns: VideoMetadata with all fields populated
    """
```

---

### VideoNormalizationService
**File**: `services/video_normalization_service.py`

**Purpose**: Normalize video resolution/FPS for timeline consistency.

**Key Methods**:
```python
def normalize_video(input_path: Path, output_path: Path,
                   target_resolution: tuple[int, int],
                   target_fps: float) -> Result[Path]:
    """
    Normalize video to target specs:
    - Scale to resolution
    - Convert frame rate
    - Pad to aspect ratio (black bars)
    """
```

---

## Export & Output Services

### CSVExportService
**File**: `services/csv_export_service.py`

**Purpose**: Export processing results to CSV.

**Key Methods**:
```python
def export_results(results: List[ProcessingResult], output_path: Path) -> Result[Path]:
    """
    Export comprehensive CSV with columns:
    - Filename, SMPTE timecode, frame rate, pattern used
    - Date components (year, month, day)
    - Full video metadata (resolution, codec, duration)
    - Frame-accurate timing (first_frame_pts)
    - Processing status and errors
    """
```

---

### JSONTimelineExportService
**File**: `services/json_timeline_export_service.py`

**Purpose**: Export timeline data as JSON.

**Key Methods**:
```python
def export_timeline(videos: List[VideoMetadata], timeline: Timeline,
                   output_path: Path) -> Result[Path]:
    """
    Export JSON with:
    - Video list with metadata
    - Gap periods with timestamps
    - Overlap periods with camera lists
    - Timeline statistics
    """
```

---

## Utility Services

### FFmpegCommandBuilderService
**File**: `services/ffmpeg_command_builder_service.py`

**Purpose**: Build FFmpeg commands for various operations.

**Key Methods**:
```python
def build_metadata_write_command(input_path: Path, output_path: Path,
                                smpte: str, lossless: bool = True) -> List[str]:
    """Build FFmpeg command for metadata writing"""

def build_normalize_command(input_path: Path, output_path: Path,
                           resolution: tuple, fps: float) -> List[str]:
    """Build FFmpeg command for video normalization"""
```

---

### PatternGenerator
**File**: `services/pattern_generator.py`

**Purpose**: Help users create custom patterns (UI feature).

**Key Methods**:
```python
def analyze_selection(filename: str, selection_start: int, selection_end: int) -> dict:
    """Analyze user text selection and suggest pattern"""

def test_pattern(pattern: str, filename: str) -> tuple[bool, Optional[List[str]]]:
    """Test regex pattern against filename"""
```

---

## Service Dependency Graph

```
UI Layer (FilenameParserTab)
    │
    ├─► FilenameParserController
    │   └─► BatchProcessorService
    │       ├─► FilenameParserService
    │       │   ├─► PatternMatcher
    │       │   │   └─► PatternLibrary
    │       │   ├─► TimeExtractor
    │       │   │   └─► ComponentExtractor (fallback)
    │       │   └─► SMPTEConverter
    │       │
    │       ├─► FrameRateService
    │       │   └─► VideoMetadataExtractor
    │       │
    │       ├─► FFmpegMetadataWriterService
    │       │   └─► FFmpegCommandBuilderService
    │       │
    │       └─► CSVExportService
    │
    └─► TimelineController
        └─► MulticamRendererService
            ├─► FFmpegTimelineBuilder
            │   └─► SlateGeneratorService
            │
            ├─► TimelineCalculatorService
            │
            └─► VideoNormalizationService (if needed)
```

## Common Service Patterns

### Result Object Returns
All services return `Result[T]` for type-safe error handling:
```python
result = service.operation()
if result.success:
    data = result.value
else:
    logger.error(result.error.user_message)
```

### Progress Callbacks
Long-running operations accept progress callbacks:
```python
def process_files(files, progress_callback):
    for i, file in enumerate(files):
        progress_callback(percentage=int((i/len(files))*100),
                         message=f"Processing {file.name}...")
```

### Dependency Injection
Services receive dependencies via constructor:
```python
class BatchProcessorService:
    def __init__(self,
                 parser_service: IFilenameParserService,
                 frame_rate_service: IFrameRateService,
                 metadata_writer_service: IFFmpegMetadataWriterService,
                 csv_export_service: CSVExportService):
        self.parser = parser_service
        # ... inject all dependencies
```

## Performance Characteristics

| Service | Avg Time | Bottleneck |
|---------|----------|------------|
| PatternMatcher | ~0.5ms | Regex execution |
| ComponentExtractor | ~2-5ms | Multiple format tries |
| FrameRateService (single) | ~100ms | FFprobe subprocess |
| FrameRateService (batch 50) | ~2s | Parallel execution (4 workers) |
| FFmpegMetadataWriterService | ~200ms | FFmpeg lossless copy |
| FFmpegTimelineBuilder | ~0.5s | Command generation |
| MulticamRendererService | ~120s | FFmpeg rendering |

## Summary

**20+ specialized services** organized into:
- **Pattern System** (5 services): Pattern matching, validation, fallback
- **Core Processing** (4 services): Parsing, batch processing, frame rate, metadata
- **Timeline & Rendering** (5 services): FFmpeg commands, rendering, gap detection
- **Export & Output** (2 services): CSV, JSON
- **Utilities** (4+ services): Command building, normalization, pattern generation

**Key Design Principles**:
- Single Responsibility (each service does ONE thing)
- Result Objects (no exception-based control flow)
- Dependency Injection (testable, mockable)
- Progress Reporting (user visibility)
- Thread-Safe (no shared mutable state)
