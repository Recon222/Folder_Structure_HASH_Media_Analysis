# Forensic Transcoder - Integration Guide

## Quick Start Integration

### Minimum Integration (3 lines)
```python
from forensic_transcoder import ForensicTranscoderTab

tab = ForensicTranscoderTab()
tab_widget.addTab(tab, "Video Transcoder")
```

### Recommended Integration (8 lines)
```python
from forensic_transcoder import ForensicTranscoderTab

# Create tab
self.transcoder_tab = ForensicTranscoderTab()

# Connect logging (optional but recommended)
self.transcoder_tab.log_message.connect(self.handle_log_message)

# Add to application
self.tabs.addTab(self.transcoder_tab, "Video Transcoder")
```

---

## Prerequisites

### Required Dependencies
```python
# requirements.txt
PySide6>=6.4.0  # Qt framework
# That's it. No other Python packages required.
```

### External Binaries
- **FFmpeg**: Required for transcoding
- **FFprobe**: Required for video analysis

The module automatically detects binaries in:
1. Project `bin/` directory (bundled)
2. System PATH
3. Common installation locations

If binaries are not found, the user will see an error when trying to use the feature.

---

## Integration into Main Application

### Current Implementation (main_window.py)

**Lines 150-157**:
```python
# Forensic Transcoder tab (independent plugin)
try:
    from forensic_transcoder import ForensicTranscoderTab
    self.transcoder_tab = ForensicTranscoderTab()
    self.transcoder_tab.log_message.connect(self.log)
    self.tabs.addTab(self.transcoder_tab, "Video Transcoder")
except ImportError as e:
    logger.debug(f"Forensic Transcoder module not available: {e}")
```

**Why try/except?**
- Graceful degradation if module is missing
- Optional feature that doesn't break main app
- Clean logging of availability

---

## Signal Interface

### Outgoing Signals (Module → Application)

```python
class ForensicTranscoderTab(QWidget):
    # Only 1 signal crosses module boundary
    log_message = Signal(str)  # For status messages and logging

    def __init__(self):
        # Module emits log messages:
        self.log_message.emit("Transcode started")
        self.log_message.emit(f"Processing {len(files)} files")
        self.log_message.emit("Operation completed successfully")
```

### How to Connect

```python
# In your main window:
self.transcoder_tab.log_message.connect(self.log)
# or
self.transcoder_tab.log_message.connect(self.status_bar.showMessage)
# or
self.transcoder_tab.log_message.connect(lambda msg: print(f"[Transcoder] {msg}"))
```

---

## Optional Enhancements

### 1. Error Handler Integration

**Current State**: Module has standalone error handling via QMessageBox

**Enhancement**: Connect to main app's ErrorHandler

```python
from core.error_handler import get_error_handler
from core.exceptions import FSAError

# In ForensicTranscoderTab._on_error:
def _on_error(self, error_message: str):
    # Instead of QMessageBox.critical()
    error = FSAError(
        f"Transcode error: {error_message}",
        user_message=error_message,
        component="ForensicTranscoder"
    )
    get_error_handler().handle_error(error, {'operation': 'transcode'})
```

**Benefit**: Unified error notifications across application

### 2. Settings Persistence

**Current State**: Settings are transient (reset on app restart)

**Enhancement**: Integrate with SettingsManager

```python
from core.settings_manager import settings

class ForensicTranscoderTab:
    def __init__(self):
        # Load saved settings
        self._load_saved_settings()

    def _load_saved_settings(self):
        last_codec = settings.value("transcoder/last_codec", "libx264")
        self.transcode_settings.codec_combo.setCurrentText(last_codec)
        # ... load other preferences

    def _on_transcode_complete(self, result):
        # Save preferences
        settings.setValue("transcoder/last_codec", self.codec_combo.currentText())
        settings.sync()
```

**Benefit**: User preferences persist across sessions

### 3. Status Bar Integration

**Current State**: Module emits log messages

**Enhancement**: Dedicated status bar connection

```python
# Add status_message signal to ForensicTranscoderTab
class ForensicTranscoderTab(QWidget):
    log_message = Signal(str)
    status_message = Signal(str)  # NEW

    def _on_progress_update(self, percentage, message):
        # Emit to status bar
        self.status_message.emit(f"Transcoding: {percentage:.0f}% - {message}")

# In MainWindow:
self.transcoder_tab.status_message.connect(self.status_bar.showMessage)
```

**Benefit**: Real-time status without cluttering logs

---

## Customization Options

### 1. Custom Forensic Presets

Add agency-specific quality presets:

**File**: `forensic_transcoder/core/preset_definitions.py`

```python
FORENSIC_PRESETS = {
    # ... existing presets

    QualityPreset.AGENCY_STANDARD: ForensicPresetDefinition(
        preset_name=QualityPreset.AGENCY_STANDARD,
        description="Agency XYZ Standard",
        crf_h264=20,
        crf_h265=22,
        preset="medium",
        audio_codec="aac",
        audio_bitrate="192k",
        use_case="Standard for Agency XYZ evidence preservation"
    ),
}
```

### 2. Custom Output Paths

Override default output path generation:

**File**: `forensic_transcoder/services/transcode_service.py`

```python
def _generate_output_path(self, input_file: Path, settings: TranscodeSettings) -> Path:
    # Custom logic for your organization
    if settings.output_directory is None:
        # Use agency-specific structure
        settings.output_directory = Path("/forensic_output") / datetime.now().strftime("%Y-%m-%d")

    # ... rest of method
```

### 3. Branding

Customize UI text and icons:

**File**: `forensic_transcoder/ui/forensic_transcoder_tab.py`

```python
def _create_file_panel(self) -> QGroupBox:
    panel = QGroupBox("📁 Video Files to Process")  # Change icon/text
    # ...

# Change button labels
self.start_btn = QPushButton("▶️ Start Processing")  # Customize
```

---

## Testing Integration

### Unit Test Example

```python
import pytest
from PySide6.QtWidgets import QApplication
from forensic_transcoder import ForensicTranscoderTab

@pytest.fixture
def qapp():
    app = QApplication([])
    yield app
    app.quit()

def test_tab_creation(qapp):
    """Test that tab can be created"""
    tab = ForensicTranscoderTab()
    assert tab is not None
    assert hasattr(tab, 'log_message')

def test_signal_emission(qapp, qtbot):
    """Test that log_message signal works"""
    tab = ForensicTranscoderTab()

    with qtbot.waitSignal(tab.log_message, timeout=1000) as blocker:
        tab._log("INFO", "Test message")

    assert blocker.signal_triggered
```

### Integration Test

```python
def test_full_integration(qapp):
    """Test integration with main window"""
    from ui.main_window import MainWindow

    window = MainWindow()

    # Check tab was added
    tab_count = window.tabs.count()
    transcoder_tab_found = False

    for i in range(tab_count):
        if window.tabs.tabText(i) == "Video Transcoder":
            transcoder_tab_found = True
            break

    assert transcoder_tab_found, "Forensic Transcoder tab not found"
```

---

## Deployment Considerations

### 1. Binary Distribution

**Option A**: Bundle FFmpeg with application
```
your_app/
├── bin/
│   ├── ffmpeg.exe    # Windows
│   ├── ffprobe.exe
│   └── ffmpeg        # Linux/macOS
└── forensic_transcoder/
```

**Option B**: User installs FFmpeg separately
- Provide installation instructions
- Module auto-detects in PATH

### 2. Module Distribution

**Option A**: Include in main app
```
your_app/
├── forensic_transcoder/
│   ├── __init__.py
│   ├── models/
│   ├── services/
│   └── ui/
└── main.py
```

**Option B**: Separate package
```bash
# Install as package
pip install forensic-transcoder

# In your app
from forensic_transcoder import ForensicTranscoderTab
```

### 3. Documentation

Provide users with:
- FFmpeg installation guide
- Supported formats list
- Quality preset explanations
- Troubleshooting tips

---

## Troubleshooting Common Issues

### Issue 1: FFmpeg Not Found

**Symptom**: Error "FFmpeg not found" on module load

**Solution**:
```python
# Check binary detection
from forensic_transcoder.core.binary_manager import binary_manager
ffmpeg_path, ffprobe_path = binary_manager.find_binaries(force_refresh=True)
print(f"FFmpeg: {ffmpeg_path}")
print(f"FFprobe: {ffprobe_path}")

# If None, install FFmpeg or bundle binaries
```

### Issue 2: Signal Not Connecting

**Symptom**: Log messages not appearing in main window

**Solution**:
```python
# Ensure signal is connected BEFORE any operations
tab = ForensicTranscoderTab()
tab.log_message.connect(self.log)  # Connect first
self.tabs.addTab(tab, "Video Transcoder")  # Then add to UI
```

### Issue 3: UI Freezing

**Symptom**: UI becomes unresponsive during transcode

**Cause**: Worker thread not being created properly

**Solution**: Check controller is creating QThread:
```python
# In TranscoderController.start_transcode():
self.worker = TranscodeWorker(...)
self.worker.start()  # Ensure this is called
```

---

## Advanced Integration Scenarios

### Scenario 1: Automated Batch Processing

Integrate transcoder with file watcher:

```python
from PySide6.QtCore import QFileSystemWatcher
from forensic_transcoder.services.transcode_service import TranscodeService
from forensic_transcoder.models.transcode_settings import TranscodeSettings, QualityPreset

class AutoTranscoder:
    def __init__(self, watch_dir: str, output_dir: str):
        self.service = TranscodeService()
        self.settings = TranscodeSettings(
            quality_preset=QualityPreset.HIGH_FORENSIC,
            output_directory=Path(output_dir)
        )

        self.watcher = QFileSystemWatcher([watch_dir])
        self.watcher.fileChanged.connect(self.on_file_added)

    def on_file_added(self, file_path: str):
        result = self.service.transcode_file(
            Path(file_path),
            self.settings
        )
        print(f"Auto-transcode: {result.status}")
```

### Scenario 2: Command-Line Integration

Use services without UI:

```python
from pathlib import Path
from forensic_transcoder.services.transcode_service import TranscodeService
from forensic_transcoder.models.transcode_settings import TranscodeSettings, QualityPreset

def cli_transcode(input_file: str, output_file: str):
    service = TranscodeService()
    settings = TranscodeSettings(
        video_codec="libx264",
        quality_preset=QualityPreset.HIGH_FORENSIC
    )

    result = service.transcode_file(
        input_file=Path(input_file),
        output_file=Path(output_file),
        settings=settings,
        progress_callback=lambda pct, msg: print(f"{pct:.0f}%: {msg}")
    )

    if result.is_success:
        print(f"Success! Speed: {result.encoding_speed:.1f}x")
    else:
        print(f"Failed: {result.error_message}")

if __name__ == "__main__":
    import sys
    cli_transcode(sys.argv[1], sys.argv[2])
```

### Scenario 3: REST API Wrapper

Expose transcoder via API:

```python
from fastapi import FastAPI, BackgroundTasks
from forensic_transcoder.services.transcode_service import TranscodeService

app = FastAPI()
service = TranscodeService()

@app.post("/transcode")
async def transcode(
    input_file: str,
    output_file: str,
    quality: str = "high_forensic",
    background_tasks: BackgroundTasks
):
    def process():
        settings = TranscodeSettings(quality_preset=QualityPreset(quality))
        result = service.transcode_file(Path(input_file), Path(output_file), settings)
        # Store result in database

    background_tasks.add_task(process)
    return {"status": "started"}
```

---

## Migration from Other Solutions

### From Manual FFmpeg Scripts

**Before**:
```bash
ffmpeg -i input.mp4 -c:v libx264 -crf 18 -preset medium output.mp4
```

**After**:
```python
settings = TranscodeSettings(
    video_codec="libx264",
    crf=18,
    preset="medium"
)
result = service.transcode_file(input_file, output_file, settings)
```

### From HandBrake CLI

**Before**:
```bash
HandBrakeCLI -i input.mp4 -o output.mp4 --preset="High Profile"
```

**After**:
```python
settings = TranscodeSettings(
    quality_preset=QualityPreset.HIGH_FORENSIC  # Similar to High Profile
)
result = service.transcode_file(input_file, output_file, settings)
```

---

## Best Practices

1. **Always handle ImportError** for optional integration
2. **Connect log_message signal** for debugging
3. **Test with various video formats** before deployment
4. **Provide FFmpeg installation docs** to users
5. **Monitor worker thread lifecycle** in complex apps
6. **Use forensic presets** for evidence work
7. **Validate FFmpeg availability** at app startup
8. **Log all operations** for audit trails
9. **Test cancellation** behavior thoroughly
10. **Document integration** for your team

---

**Next**: [06_CODE_QUALITY_ANALYSIS.md](./06_CODE_QUALITY_ANALYSIS.md) - Code quality assessment
