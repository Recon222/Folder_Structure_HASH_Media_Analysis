# Forensic Transcoder - Services Layer

## Overview

The services layer contains all business logic for video operations. Services are stateless (except cancellation flags) and handle FFmpeg/FFprobe orchestration.

## Service Architecture

```
Services (Stateless Business Logic)
    ↓
Subprocess (FFmpeg/FFprobe)
    ↓
Video Files
```

---

## 1. TranscodeService

**File**: `services/transcode_service.py`
**Purpose**: Execute single/batch video transcoding with FFmpeg

### Key Methods

#### transcode_file()
```python
def transcode_file(
    self,
    input_file: Path,
    output_file: Path,
    settings: TranscodeSettings,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> ProcessingResult
```

**Flow**:
1. Validate input file exists
2. Analyze input video (VideoAnalyzerService)
3. Build FFmpeg command (FFmpegCommandBuilder)
4. Validate command
5. Execute FFmpeg subprocess
6. Parse progress from stderr
7. Extract performance metrics
8. Return ProcessingResult

#### transcode_batch()
```python
def transcode_batch(
    self,
    input_files: List[Path],
    settings: TranscodeSettings,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> List[ProcessingResult]
```

**Flow**:
- Sequential processing of files
- Per-file progress mapping to overall percentage
- Cancellation check between files
- Returns list of ProcessingResult objects

### Progress Parsing

```python
def _parse_ffmpeg_progress(self, line: str, total_duration: float):
    # Parse FFmpeg stderr: time=00:01:23.45 speed=2.3x
    time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})', line)
    if time_match:
        # Calculate percentage, speed, ETA
        return (percentage, speed, eta_string)
```

### Performance Metrics Extraction

```python
def _extract_performance_metrics(self, stderr_lines: List[str], result: ProcessingResult):
    # Extract from FFmpeg output:
    # - encoding_speed (e.g., 2.3x realtime)
    # - frames_processed
    # - average_fps
```

---

## 2. ConcatenateService

**File**: `services/concatenate_service.py`
**Purpose**: Join multiple videos (mux or transcode mode)

### Concatenation Modes

1. **MUX Mode**: Fast, no re-encode
   - Requires identical codec/resolution/fps
   - Uses FFmpeg concat demuxer
   - ~10x faster than transcode

2. **TRANSCODE Mode**: Re-encode all clips
   - Normalizes all videos to target specs
   - Uses filter_complex for scaling/fps
   - Handles incompatible inputs

### Key Methods

#### concatenate_videos()
```python
def concatenate_videos(
    self,
    settings: ConcatenateSettings,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> ProcessingResult
```

**Flow**:
1. Analyze all input files
2. Check compatibility (is_compatible_with())
3. Determine mode (AUTO selects mux/transcode)
4. Execute appropriate concatenation
5. Return ProcessingResult

#### Mode Selection Logic

```python
def _determine_concat_mode(settings, analyses):
    if settings.concatenation_mode != AUTO:
        return settings.concatenation_mode

    # Check if all files compatible
    first = analyses[0]
    for analysis in analyses[1:]:
        if not first.is_compatible_with(analysis, strict=not settings.allow_minor_differences):
            return TRANSCODE

    return MUX
```

---

## 3. VideoAnalyzerService

**File**: `services/video_analyzer_service.py`
**Purpose**: Extract metadata from video files using FFprobe

### Key Methods

#### analyze_video()
```python
def analyze_video(self, file_path: Path) -> VideoAnalysis
```

**Extraction Process**:
1. Run FFprobe with JSON output
2. Parse format information
3. Find video/audio/subtitle streams
4. Extract detailed properties:
   - Resolution, codec, pixel format
   - Frame rate (CFR vs VFR detection)
   - Color space, bit depth
   - Audio streams
   - Subtitle streams
   - Metadata, chapters
5. Return VideoAnalysis object

#### analyze_batch()
```python
def analyze_batch(self, file_paths: List[Path]) -> List[VideoAnalysis]
```

**Batch processing** with error tolerance:
- Analyzes each file independently
- Failed analyses are skipped (logged)
- Returns only successful analyses

### FFprobe Command

```python
def _run_ffprobe(self, file_path: Path) -> dict:
    cmd = [
        self.ffprobe_path,
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        '-show_chapters',
        str(file_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
    return json.loads(result.stdout)
```

### Frame Rate Detection

```python
def _extract_frame_rate(self, video_stream: dict):
    fps_string = video_stream.get('r_frame_rate', '0/1')
    avg_fps_string = video_stream.get('avg_frame_rate', fps_string)

    # Calculate FPS from fraction
    fps = float(parts[0]) / float(parts[1])

    # Detect VFR
    if fps_string != avg_fps_string:
        frame_rate_type = FrameRateType.VARIABLE
    else:
        frame_rate_type = FrameRateType.CONSTANT

    return fps, fps_string, frame_rate_type
```

---

## 4. FFmpegCommandBuilder

**File**: `services/ffmpeg_command_builder.py`
**Purpose**: Translate settings objects into FFmpeg command arrays

### Key Methods

#### build_transcode_command()
```python
def build_transcode_command(
    self,
    input_file: Path,
    output_file: Path,
    settings: TranscodeSettings,
    input_analysis: Optional[VideoAnalysis] = None
) -> Tuple[List[str], str]
```

**Returns**: `(command_array, formatted_string)`

**Command Building Flow**:
1. Start with FFmpeg binary path
2. Add hardware decoder args (if enabled)
3. Add input file
4. Add video codec
5. Apply quality settings (preset-based or custom)
6. Build video filters:
   - Deinterlace (yadif)
   - Scaling (lanczos/bicubic/etc)
   - FPS adjustment
   - Custom filters
7. Add pixel format, color space
8. Add audio settings (copy or re-encode)
9. Add subtitle handling
10. Add metadata preservation
11. Add hardware encoder options
12. Add output format and file

#### build_concatenate_command()
```python
def build_concatenate_command(
    self,
    settings: ConcatenateSettings,
    analyses: List[VideoAnalysis]
) -> Tuple[List[str], str]
```

**Modes**:
- **MUX**: Uses concat demuxer with file list
- **TRANSCODE**: Uses filter_complex for normalization

### Video Filter Building

```python
def _build_scale_filter(self, width, height, maintain_aspect, algorithm):
    algo = 'lanczos'  # or bicubic, bilinear, etc.

    if maintain_aspect:
        if width and not height:
            return f"scale={width}:-1:flags={algo}"
        elif height and not width:
            return f"scale=-1:{height}:flags={algo}"
        else:
            # Force with aspect ratio preservation
            return f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags={algo}"
    else:
        return f"scale={width}:{height}:flags={algo}"

def _build_fps_filter(self, target_fps, method):
    if method == FPSMethod.DUPLICATE:
        return f"fps={target_fps}:round=near"
    elif method == FPSMethod.PTS_ADJUST:
        return f"setpts=PTS*{target_fps}/TB"
    else:
        return f"fps={target_fps}:round=near"  # AUTO default
```

### Hardware Acceleration

```python
def _build_hardware_decoder_args(self, codec: str, gpu_index: int = 0):
    args = []
    if 'nvenc' in codec:
        args.extend(['-hwaccel', 'cuda'])
        args.extend(['-hwaccel_output_format', 'cuda'])
        if gpu_index > 0:
            args.extend(['-hwaccel_device', str(gpu_index)])
    elif 'qsv' in codec:
        args.extend(['-hwaccel', 'qsv'])
    elif 'amf' in codec:
        args.extend(['-hwaccel', 'auto'])
    return args
```

### Command Validation

```python
def validate_command(self, cmd: List[str]) -> Tuple[bool, Optional[str]]:
    # Check command starts with ffmpeg
    if not (cmd[0].endswith('ffmpeg') or cmd[0].endswith('ffmpeg.exe')):
        return False, "Command must start with ffmpeg"

    # Check for input file
    if '-i' not in cmd:
        return False, "No input file specified"

    # Check for orphaned flags (flags without values)
    # Handles NO_VALUE_FLAGS like -y, -n, -sn
    # Handles negative numbers like -1 (map_metadata -1)

    return True, None
```

---

## Service Integration Patterns

### Error Handling Pattern

All services use try/except with ProcessingResult:

```python
try:
    # Execute operation
    process = subprocess.Popen(cmd, ...)
    # Parse output
    # ...
    result.mark_complete(ProcessingStatus.SUCCESS)
except subprocess.CalledProcessError as e:
    result.mark_failed(f"FFmpeg failed: {e.stderr}", e.returncode)
except Exception as e:
    result.mark_failed(str(e))

return result
```

### Progress Callback Pattern

Services accept optional callbacks:

```python
if progress_callback:
    progress_callback(percentage, message)
```

Workers provide lambda wrappers:

```python
def file_progress_callback(file_pct: float, msg: str):
    if progress_callback:
        overall_pct = file_progress_start + (file_pct / 100.0) * file_progress_range
        progress_callback(overall_pct, f"[{idx+1}/{total_files}] {msg}")
```

### Cancellation Pattern

Services check `self._cancelled` flag:

```python
def cancel(self):
    self._cancelled = True

def transcode_batch(self, ...):
    for input_file in input_files:
        if self._cancelled:
            result = ProcessingResult(status=ProcessingStatus.CANCELLED)
            results.append(result)
            continue
        # Process file
```

---

## Forensic Preset Integration

### Preset Definitions

**File**: `core/preset_definitions.py`

```python
FORENSIC_PRESETS = {
    QualityPreset.LOSSLESS_FORENSIC: ForensicPresetDefinition(
        crf_h264=0,  # Mathematically lossless
        preset="slow",
        audio_codec="flac",
        use_case="Critical evidence requiring perfect preservation"
    ),
    QualityPreset.HIGH_FORENSIC: ForensicPresetDefinition(
        crf_h264=18,  # Visually lossless
        preset="medium",
        audio_codec="aac",
        audio_bitrate="192k",
        use_case="Recommended for most forensic work"
    ),
    # ... more presets
}
```

### Usage in CommandBuilder

```python
if settings.quality_preset != QualityPreset.CUSTOM:
    preset = get_preset_for_codec(settings.quality_preset, settings.video_codec)
    crf = get_crf_for_preset(settings.quality_preset, settings.video_codec)
    cmd.extend(['-crf', str(crf)])
    cmd.extend(['-preset', preset])
else:
    # Use custom settings from TranscodeSettings
    if settings.crf is not None:
        cmd.extend(['-crf', str(settings.crf)])
```

---

## Binary Management

### FFmpegBinaryManager

**File**: `core/binary_manager.py`
**Pattern**: Singleton

```python
class FFmpegBinaryManager:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def find_binaries(self, force_refresh: bool = False):
        # Search order:
        # 1. Local bin/ directory (bundled)
        # 2. System PATH
        # 3. Common installation locations
        pass

    def get_ffmpeg_path(self) -> Optional[str]:
        if not self._validated:
            self.find_binaries()
        return self.ffmpeg_path

# Global instance
binary_manager = FFmpegBinaryManager()
```

### Search Strategy

```python
def _find_binary(self, binary_name: str) -> Optional[str]:
    # 1. Try local bin/ directory
    local_bin_path = self._find_in_local_bin(binary_name)
    if local_bin_path:
        return local_bin_path

    # 2. Try PATH
    path_result = self._find_in_path(binary_name)
    if path_result:
        return path_result

    # 3. Try common locations
    common_paths = self._get_common_paths(binary_name, system)
    for path in common_paths:
        if os.path.exists(path) and self._test_binary(path):
            return path

    return None
```

---

**Next**: [04_UI_COMPONENTS.md](./04_UI_COMPONENTS.md) - UI architecture
