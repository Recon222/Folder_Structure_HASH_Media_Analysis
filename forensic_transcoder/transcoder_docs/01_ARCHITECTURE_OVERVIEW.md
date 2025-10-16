# Forensic Transcoder - Architecture Overview

## Module Philosophy

The Forensic Transcoder is designed as a **completely independent plugin** that can be dropped into any PySide6 application. It demonstrates enterprise-grade architecture with:

- **Zero coupling** to parent application infrastructure
- **Self-contained** binary management, settings, and business logic
- **Signal-based** communication for integration
- **SOA layering** with clear separation of concerns

## Architectural Layers

### Layer 1: Data Models (`models/`)

**Purpose**: Type-safe data structures with validation

```
models/
├── transcode_settings.py      # TranscodeSettings, QualityPreset, FPSMethod, ScalingAlgorithm
├── concatenate_settings.py    # ConcatenateSettings, ConcatenationMode, TransitionType
├── processing_result.py       # ProcessingResult, BatchProcessingStatistics
└── video_analysis.py          # VideoAnalysis, AudioStreamInfo, SubtitleStreamInfo
```

**Characteristics**:
- All models use `@dataclass` for clean, declarative definitions
- Enum-based constants for type safety (no magic strings)
- Built-in validation in `__post_init__` methods
- JSON serialization support (`to_dict`/`from_dict`)
- No external dependencies

### Layer 2: Core Infrastructure (`core/`)

**Purpose**: Foundation services and definitions

```
core/
├── binary_manager.py          # FFmpegBinaryManager (singleton)
├── codec_definitions.py       # Codec metadata and capabilities
└── preset_definitions.py      # Forensic quality presets
```

**Key Component**: `FFmpegBinaryManager`
- Singleton pattern for binary detection
- Platform-aware PATH searching (Windows/macOS/Linux)
- Caching to avoid repeated filesystem lookups
- Version detection and validation
- Searches: local `bin/` → PATH → common install locations

### Layer 3: Services (`services/`)

**Purpose**: Business logic and external tool orchestration

```
services/
├── transcode_service.py       # TranscodeService - FFmpeg transcoding
├── concatenate_service.py     # ConcatenateService - Video joining
├── video_analyzer_service.py  # VideoAnalyzerService - FFprobe analysis
└── ffmpeg_command_builder.py  # FFmpegCommandBuilder - Command generation
```

**Service Responsibilities**:
- `TranscodeService`: Execute single/batch transcode operations
- `ConcatenateService`: Join multiple videos (mux or transcode mode)
- `VideoAnalyzerService`: Extract metadata with FFprobe
- `FFmpegCommandBuilder`: Translate settings → FFmpeg commands

**Design Pattern**: All services are stateless (except for `_cancelled` flags)

### Layer 4: Controllers (`controllers/`)

**Purpose**: Workflow orchestration and worker lifecycle management

```
controllers/
├── transcoder_controller.py   # TranscoderController
└── concatenate_controller.py  # ConcatenateController
```

**Controller Responsibilities**:
- Create and manage QThread workers
- Forward signals between workers and UI
- Implement cancellation logic
- Provide clean interface for UI layer
- Handle worker cleanup (`deleteLater()`)

**Pattern**: Controllers inherit `QObject` for signal support

### Layer 5: Workers (`workers/`)

**Purpose**: Background thread execution for blocking operations

```
workers/
├── transcode_worker.py        # TranscodeWorker (QThread)
└── concatenate_worker.py      # ConcatenateWorker (QThread)
```

**Worker Pattern**:
```python
class TranscodeWorker(QThread):
    # Unified signals
    progress_update = Signal(float, str)  # percentage, message
    result_ready = Signal(object)          # ProcessingResult or BatchProcessingStatistics
    error = Signal(str)                    # error message

    def run(self):
        # Execute service operations in background
        pass

    def cancel(self):
        # Graceful cancellation
        pass
```

### Layer 6: UI Components (`ui/`)

**Purpose**: User interface with zero business logic

```
ui/
├── forensic_transcoder_tab.py      # Main tab widget (coordinator only)
├── transcode_settings_widget.py    # Transcode configuration form
└── concatenate_settings_widget.py  # Concatenation configuration form
```

**UI Design Principles**:
- **Pure presentation**: No business logic in UI
- **Signal-based**: All actions delegated via signals
- **Form binding**: Settings widgets → Model objects
- **Progress tracking**: Real-time updates via controller signals

## Component Interaction Flow

### Transcode Operation Flow

```
User Action (UI)
    ↓
ForensicTranscoderTab._on_start_processing()
    ↓
TranscoderController.start_transcode(files, settings)
    ↓
    Creates TranscodeWorker(files, settings)
    ↓
    Connects signals: progress_update, result_ready, error
    ↓
    worker.start()  # Launches QThread
    ↓
TranscodeWorker.run()
    ↓
    Creates TranscodeService()
    ↓
    service.transcode_file() or service.transcode_batch()
        ↓
        Analyzes input: VideoAnalyzerService.analyze_video()
        ↓
        Builds command: FFmpegCommandBuilder.build_transcode_command()
        ↓
        Executes: subprocess.Popen(['ffmpeg', ...])
        ↓
        Parses progress from stderr
        ↓
        Emits progress_update signals
        ↓
        Returns ProcessingResult
    ↓
Worker emits result_ready(result)
    ↓
Controller forwards to UI
    ↓
ForensicTranscoderTab._on_transcode_complete(result)
    ↓
Shows success dialog or error message
```

### Command Building Flow

```
User configures settings (UI)
    ↓
TranscodeSettingsWidget.get_settings() → TranscodeSettings
    ↓
FFmpegCommandBuilder.build_transcode_command(
    input_file,
    output_file,
    settings,
    input_analysis  # Optional VideoAnalysis
)
    ↓
    Analyzes settings.quality_preset
    ↓
    Maps to codec-specific CRF/preset values
    ↓
    Builds command array:
        - Hardware decoder args
        - Input file
        - Video codec + quality settings
        - Video filters (scale, fps, deinterlace)
        - Audio settings
        - Subtitle handling
        - Metadata preservation
        - Hardware encoder options
        - Output format
    ↓
Returns (command_array, formatted_string)
```

## Signal Architecture

### Signal Flow Diagram

```
ForensicTranscoderTab (UI)
    ↓ (method call)
TranscoderController
    ↓ (creates)
TranscodeWorker (QThread)
    ↓ (executes)
TranscodeService
    ↓ (emits)
progress_update(percentage, message)
    ↑ (forwards)
TranscoderController.progress_update
    ↑ (connects to)
ForensicTranscoderTab._on_progress_update()
    ↑ (updates)
UI Progress Bar + Label
```

### Main Application Integration

```
MainWindow
    ↓ (creates)
ForensicTranscoderTab
    ↓ (connects)
log_message signal
    ↑ (emits to)
MainWindow.log(message)
    ↑ (displays in)
StatusBar
```

**Only 1 signal crosses module boundary**: `log_message: Signal(str)`

## Independence Demonstration

### No Shared Infrastructure

The module does NOT use:
- ❌ Main app's `ErrorHandler`
- ❌ Main app's `ServiceRegistry`
- ❌ Main app's `SettingsManager`
- ❌ Main app's `Result` objects (has own `ProcessingResult`)
- ❌ Main app's `logger` (uses print/signals)

### Self-Contained Systems

1. **Binary Management**: Own `FFmpegBinaryManager` singleton
2. **Settings Models**: Own dataclass definitions
3. **Error Handling**: Try/except with signal emission
4. **Logging**: Via `log_message` signal to parent
5. **State Management**: Local instance variables only

### Portability Test

To use in another application:
```python
# Copy entire forensic_transcoder/ directory
# In your PySide6 app:

from forensic_transcoder import ForensicTranscoderTab

tab = ForensicTranscoderTab()
tab.log_message.connect(your_log_handler)
your_tab_widget.addTab(tab, "Transcoder")

# Done. No other dependencies required.
```

## Threading Model

### Thread Safety Design

1. **UI Thread**: All Qt widgets and signal connections
2. **Worker Threads**: FFmpeg subprocess execution
3. **Signal Communication**: Thread-safe Qt signal/slot mechanism

### Worker Lifecycle

```python
# Controller creates worker
self.worker = TranscodeWorker(files, settings, parent=self)

# Connect signals (thread-safe)
self.worker.progress_update.connect(self._on_progress_update)
self.worker.result_ready.connect(self._on_result_ready)
self.worker.finished.connect(self._on_worker_finished)

# Start background execution
self.worker.start()

# Cancellation
self.worker.cancel()  # Sets flag, service checks periodically

# Cleanup (on finished signal)
self.worker.deleteLater()
self.worker = None
```

### Progress Reporting

Workers emit progress as:
```python
progress_update.emit(percentage, message)
# percentage: 0.0 to 100.0
# message: "Analyzing file..." or "Encoding: 45.2% (speed: 2.3x)"
```

## Error Handling Strategy

### Three-Layer Error Handling

1. **Service Layer**: Try/except around FFmpeg execution
   ```python
   try:
       result = subprocess.run(cmd, ...)
   except subprocess.CalledProcessError as e:
       result.mark_failed(f"FFmpeg failed: {e.stderr}")
   ```

2. **Worker Layer**: Catches service exceptions, emits error signal
   ```python
   try:
       result = self.service.transcode_file(...)
   except Exception as e:
       self.error.emit(str(e))
   ```

3. **UI Layer**: Shows QMessageBox on error signal
   ```python
   def _on_error(self, error_message: str):
       QMessageBox.critical(self, "Error", error_message)
   ```

### Result Object Pattern

Instead of boolean returns or exceptions:
```python
result = ProcessingResult(
    processing_type=ProcessingType.TRANSCODE,
    input_file=input_file,
    output_file=output_file,
    status=ProcessingStatus.IN_PROGRESS
)

# Success
result.mark_complete(ProcessingStatus.SUCCESS)

# Failure
result.mark_failed(error_message, error_code)

# Cancellation
result.mark_cancelled()
```

## Configuration Management

### Settings Dataclasses

All configuration uses type-safe dataclasses:

```python
settings = TranscodeSettings(
    output_format="mp4",
    video_codec="libx264",
    quality_preset=QualityPreset.HIGH_FORENSIC,
    crf=18,
    preset="medium",
    # ... 30+ more fields
)
```

### Preset System

Forensic-optimized quality presets:
```python
FORENSIC_PRESETS = {
    QualityPreset.LOSSLESS_FORENSIC: ForensicPresetDefinition(
        crf_h264=0,  # Lossless
        preset="slow",
        audio_codec="flac",
        use_case="Critical evidence requiring perfect preservation"
    ),
    QualityPreset.HIGH_FORENSIC: ForensicPresetDefinition(
        crf_h264=18,  # Visually lossless
        preset="medium",
        use_case="Recommended for most forensic work"
    ),
    # ... more presets
}
```

## Performance Considerations

### Non-Blocking Operations

All FFmpeg operations run in QThread workers:
- UI remains responsive during long encodes
- Progress updates every ~200ms
- Cancellation without force-killing processes

### FFmpeg Progress Parsing

Real-time parsing of FFmpeg stderr:
```python
for line in process.stderr:
    # Parse: time=00:01:23.45 speed=2.3x
    progress_info = self._parse_ffmpeg_progress(line, duration)
    if progress_info:
        percentage, speed, eta = progress_info
        self.progress_update.emit(percentage, f"Encoding: {speed:.1f}x")
```

### Batch Processing

Sequential batch processing with per-file progress:
```python
for idx, input_file in enumerate(input_files):
    file_progress_start = (idx / total_files) * 100
    file_progress_range = (1 / total_files) * 100

    def file_progress_callback(file_pct: float, msg: str):
        overall_pct = file_progress_start + (file_pct / 100.0) * file_progress_range
        progress_callback(overall_pct, f"[{idx+1}/{total_files}] {msg}")
```

## Module Metrics

### Code Statistics
- **Total Lines**: ~2,500 (excluding comments/blanks)
- **Files**: 24 Python files
- **Classes**: 15+ dataclasses, 4 services, 2 controllers, 2 workers, 3 UI widgets
- **Signals**: 3 types (progress_update, result_ready, error/log_message)

### Complexity Analysis
- **Cyclomatic Complexity**: Low (most methods < 10 branches)
- **Dependencies**: PySide6, subprocess, json, pathlib (all stdlib except Qt)
- **External Binaries**: FFmpeg and FFprobe (detected at runtime)

---

**Next**: [02_DATA_MODELS.md](./02_DATA_MODELS.md) - Detailed model documentation
