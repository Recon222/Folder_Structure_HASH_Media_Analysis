# Forensic Transcoder - UI Components

## UI Design Philosophy

The UI layer follows strict separation of concerns:
- **Zero business logic** in UI components
- **Pure presentation** - delegates all operations to controllers
- **Signal-based coordination** for decoupling
- **Form binding** to settings models

---

## Component Hierarchy

```
ForensicTranscoderTab (Main coordinator)
    ├── File Selection Panel (QTreeWidget)
    ├── Settings Tabs (QTabWidget)
    │   ├── TranscodeSettingsWidget
    │   └── ConcatenateSettingsWidget
    ├── Action Buttons (dynamic swap)
    ├── FFmpeg Command Display (QTextEdit)
    └── Console Log (QTextEdit)
```

---

## 1. ForensicTranscoderTab

**File**: `ui/forensic_transcoder_tab.py`
**Purpose**: Main coordinator widget - orchestrates UI, controllers, and user interactions

### Responsibilities
- File selection management
- Settings tab switching
- Controller lifecycle
- Progress display
- Result presentation

### Key Components

#### File Selection (Hierarchical Tree)
```python
self.file_tree = QTreeWidget()
self.file_tree.setHeaderLabels(["Video Files"])
self.file_tree.setAlternatingRowColors(True)

def _rebuild_file_tree(self):
    # Finds common root path
    # Builds folder hierarchy
    # Displays: 📁 Folder / 🎥 video.mp4
```

#### Settings Tabs
```python
self.settings_tabs = QTabWidget()

# Tab 1: Transcode
transcode_tab = QScrollArea()
transcode_tab.setWidget(TranscodeSettingsWidget())

# Tab 2: Concatenate
concatenate_tab = QScrollArea()
concatenate_tab.setWidget(ConcatenateSettingsWidget())
```

#### Dynamic Action Buttons
```python
# Transcode buttons
self.build_command_btn = QPushButton("🔨 Build Command")
self.start_btn = QPushButton("▶️ Start Processing")
self.cancel_btn = QPushButton("⏹️ Cancel")

# Concatenate buttons (separate set, swapped on tab change)
self.concat_build_btn = QPushButton("🔨 Build Concat Command")
self.concat_start_btn = QPushButton("🔗 Start Concatenation")
self.concat_cancel_btn = QPushButton("⏹️ Cancel")

def _on_settings_tab_changed(self, index: int):
    if index == 0:
        self._show_transcode_buttons()
    elif index == 1:
        self._show_concatenate_buttons()
```

### UI Event Handlers (No Business Logic)

```python
def _on_select_files(self):
    """File dialog → update self.selected_files → rebuild tree"""
    files, _ = QFileDialog.getOpenFileNames(...)
    if files:
        self.selected_files = [Path(f) for f in files]
        self._update_file_selection_ui()

def _on_build_command(self):
    """Get settings → build command → display"""
    current_tab = self.settings_tabs.currentIndex()
    if current_tab == 0:
        self._build_transcode_command()
    elif current_tab == 1:
        self._build_concatenate_command()

def _on_start_processing(self):
    """Delegate to controller"""
    current_tab = self.settings_tabs.currentIndex()
    if current_tab == 0:
        self._start_transcode()
    elif current_tab == 1:
        self._start_concatenate()
```

### Controller Delegation

```python
def _start_transcode(self):
    settings = self.transcode_settings.get_settings()
    self._set_processing_state(True)

    # Delegate to controller
    self.transcoder_controller.start_transcode(
        input_files=self.selected_files,
        settings=settings
    )

    self.log_message.emit(f"Started transcoding {len(self.selected_files)} file(s)")
```

### Signal Handlers (Update UI Only)

```python
def _on_progress_update(self, percentage: float, message: str):
    """Update progress bar and label"""
    self.progress_bar.setValue(int(percentage))
    self.progress_label.setText(message)

def _on_transcode_complete(self, result):
    """Show success/failure dialog"""
    self._set_processing_state(False)

    if isinstance(result, ProcessingResult):
        if result.is_success:
            QMessageBox.information(self, "Success", f"Output: {result.output_file}")
        else:
            QMessageBox.warning(self, "Failed", f"Error: {result.error_message}")

    elif isinstance(result, BatchProcessingStatistics):
        QMessageBox.information(
            self, "Batch Complete",
            f"Successful: {result.successful}/{result.total_files}"
        )
```

### State Management (UI Only)

```python
def _set_processing_state(self, is_processing: bool):
    """Enable/disable buttons during processing"""
    self.add_files_btn.setEnabled(not is_processing)
    self.clear_files_btn.setEnabled(not is_processing and len(self.selected_files) > 0)
    self.build_command_btn.setEnabled(not is_processing)
    self.settings_tabs.setEnabled(not is_processing)

    self.start_btn.setEnabled(not is_processing)
    self.cancel_btn.setEnabled(is_processing)

    if is_processing:
        self.progress_bar.setValue(0)
        self.progress_label.setText("Starting...")
```

---

## 2. TranscodeSettingsWidget

**File**: `ui/transcode_settings_widget.py`
**Purpose**: Form UI for transcode configuration

### Layout Structure

```
TranscodeSettingsWidget (QWidget)
    ├── Output Configuration (QGroupBox)
    │   ├── Format combo
    │   ├── Output directory + browse
    │   ├── Filename pattern
    │   └── Overwrite checkbox
    ├── Video Codec & Quality (QGroupBox)
    │   ├── Codec combo (with hardware filter)
    │   ├── Quality preset combo
    │   ├── CRF spin
    │   ├── Preset combo
    │   ├── Tune combo
    │   ├── Profile combo
    │   └── Hardware checkboxes
    ├── Resolution & Frame Rate (QGroupBox)
    │   ├── Width/Height spins
    │   ├── Maintain aspect checkbox
    │   ├── Scaling algorithm combo
    │   ├── Target FPS spin
    │   ├── FPS method combo
    │   └── Deinterlace checkbox
    ├── Audio Settings (QGroupBox)
    │   ├── Audio codec combo
    │   ├── Bitrate combo
    │   ├── Sample rate combo
    │   └── Channels combo
    └── Advanced Options (QGroupBox)
        ├── Pixel format combo
        ├── Two-pass checkbox
        ├── Metadata checkboxes
        ├── Subtitle checkboxes
        └── Max parallel jobs spin
```

### Dynamic UI Updates

```python
def _connect_signals(self):
    # Update codec-specific options when codec changes
    self.codec_combo.currentTextChanged.connect(self._on_codec_changed)

    # Update custom settings visibility when preset changes
    self.quality_preset_combo.currentTextChanged.connect(self._on_preset_changed)

def _on_codec_changed(self, codec: str):
    # Update encoding presets (ultrafast to veryslow)
    self.preset_combo.clear()
    self.preset_combo.addItems(get_available_presets(codec))

    # Update profiles (baseline, main, high)
    self.profile_combo.clear()
    self.profile_combo.addItem("(auto)")
    self.profile_combo.addItems(get_available_profiles(codec))

    # Update tune options (film, animation, grain, etc.)
    self.tune_combo.clear()
    self.tune_combo.addItem("(none)")
    self.tune_combo.addItems(get_available_tune_options(codec))

def _on_preset_changed(self, preset_name: str):
    if preset_name == "custom":
        self.preset_description_label.setText("Custom settings")
        return

    preset = QualityPreset(preset_name)
    description = get_preset_description(preset)
    self.preset_description_label.setText(description)
```

### Settings Extraction

```python
def get_settings(self) -> TranscodeSettings:
    """Convert UI values → TranscodeSettings object"""
    # Parse output directory
    output_dir = None
    if self.output_dir_edit.text().strip():
        output_dir = Path(self.output_dir_edit.text().strip())

    # Parse quality preset
    preset_text = self.quality_preset_combo.currentText()
    quality_preset = QualityPreset(preset_text) if preset_text != "custom" else QualityPreset.CUSTOM

    # Parse resolution (0 = source)
    width = self.width_spin.value() if self.width_spin.value() > 0 else None
    height = self.height_spin.value() if self.height_spin.value() > 0 else None

    # ... parse all other fields

    return TranscodeSettings(
        output_format=self.format_combo.currentText(),
        output_directory=output_dir,
        video_codec=self.codec_combo.currentText(),
        quality_preset=quality_preset,
        crf=self.crf_spin.value(),
        output_width=width,
        output_height=height,
        # ... all fields
    )
```

---

## 3. ConcatenateSettingsWidget

**File**: `ui/concatenate_settings_widget.py`
**Purpose**: Form UI for concatenation configuration

### Layout Structure

```
ConcatenateSettingsWidget (QWidget)
    ├── Concatenation Mode (QGroupBox)
    │   ├── Mode combo (AUTO, MUX, TRANSCODE)
    │   └── Mode description label
    ├── Target Specs (QGroupBox)
    │   ├── Target codec combo
    │   ├── Target resolution spins
    │   ├── Target FPS spin
    │   ├── CRF spin
    │   └── Preset combo
    ├── Audio Normalization (QGroupBox)
    │   ├── Audio codec combo
    │   ├── Bitrate combo
    │   ├── Sample rate combo
    │   └── Normalize checkbox
    └── Advanced (QGroupBox)
        ├── Transition type combo
        ├── Transition duration spin
        ├── Hardware acceleration checkboxes
        └── Intermediate files checkbox
```

### Settings Extraction

```python
def get_settings(
    self,
    input_files: List[Path],
    output_file: Path
) -> ConcatenateSettings:
    """Convert UI values → ConcatenateSettings object"""
    mode_text = self.mode_combo.currentText()
    concatenation_mode = ConcatenationMode(mode_text)

    target_width = self.width_spin.value() if self.width_spin.value() > 0 else None
    target_height = self.height_spin.value() if self.height_spin.value() > 0 else None
    target_fps = self.fps_spin.value() if self.fps_spin.value() > 0 else None

    return ConcatenateSettings(
        concatenation_mode=concatenation_mode,
        input_files=input_files,
        output_file=output_file,
        target_codec=self.codec_combo.currentText(),
        target_width=target_width,
        target_height=target_height,
        target_fps=target_fps,
        crf=self.crf_spin.value(),
        # ... all fields
    )
```

---

## UI Design Patterns

### Form Binding Pattern
```python
# UI Widget → Model Object (not bidirectional)
settings = self.settings_widget.get_settings()
# Returns fully populated TranscodeSettings/ConcatenateSettings
```

### Signal Emission Pattern
```python
# Only 1 signal crosses module boundary
self.log_message = Signal(str)

# Usage
self.log_message.emit("Transcode started")
self.log_message.emit(f"Processing {len(files)} files")
```

### Progress Display Pattern
```python
# Controller signals → UI updates
def _on_progress_update(self, percentage: float, message: str):
    self.progress_bar.setValue(int(percentage))
    self.progress_label.setText(message)
    self.progress_bar.setVisible(True)
    self.progress_label.setVisible(True)
```

### Error Display Pattern
```python
# Modal dialogs for errors
QMessageBox.critical(self, "Error", f"Failed: {error_message}")

# Non-modal for info
self.status_label.setText(f"✓ {success_message}")
```

### State Validation Pattern
```python
def _update_file_selection_ui(self):
    count = len(self.selected_files)

    if count == 0:
        self.clear_files_btn.setEnabled(False)
        self.build_command_btn.setEnabled(False)
    else:
        self.clear_files_btn.setEnabled(True)
        self.build_command_btn.setEnabled(True)

    self.file_count_label.setText(f"{count} file{'s' if count != 1 else ''} selected")
```

---

## Console Logging

### Formatted Log Messages
```python
def _log(self, level: str, message: str):
    """Log message to console with color coding"""
    from datetime import datetime
    timestamp = datetime.now().strftime("%H:%M:%S")

    colors = {
        "INFO": "#4B9CD3",
        "SUCCESS": "#52c41a",
        "WARNING": "#faad14",
        "ERROR": "#ff4d4f"
    }

    color = colors.get(level, "#e8e8e8")
    formatted = f'<span style="color: #6b6b6b;">{timestamp}</span> ' \
                f'<span style="color: {color}; font-weight: bold;">[{level}]</span> {message}'

    self.console.append(formatted)

    # Also emit to main window
    self.log_message.emit(f"[Transcoder] {message}")
```

---

## FFmpeg Command Display

### Editable Command Preview
```python
self.command_display = QTextEdit()
self.command_display.setReadOnly(False)  # User can edit before execution
self.command_display.setFont(QFont("Consolas", 9))
self.command_display.setPlaceholderText(
    "FFmpeg command will appear here after you configure settings.\n"
    "You can edit the command before executing."
)

# On command build
self.command_display.setPlainText(cmd_string)
self.current_command = cmd_string
```

### Command Validation Status
```python
self.command_status_label = QLabel("")
# On success
self.command_status_label.setText("✓ Command built successfully")
self.command_status_label.setStyleSheet("color: green;")
```

---

## UI Performance Considerations

### Scroll Areas for Long Forms
```python
scroll_area = QScrollArea()
scroll_area.setWidgetResizable(True)
scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
scroll_area.setWidget(TranscodeSettingsWidget())
```

### Tree Widget Optimization
```python
self.file_tree.setAlternatingRowColors(True)  # Visual clarity
self.file_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
self.file_tree.setMinimumHeight(200)

# Expandall by default for small trees
if len(self.selected_files) < 50:
    self.file_tree.expandAll()
```

### Progress Update Throttling
```python
# FFmpeg emits progress ~every 200ms
# Direct connection to UI is acceptable
# No additional throttling needed
```

---

## Accessibility Features

### Placeholder Text
```python
self.output_dir_edit.setPlaceholderText("Same as input (leave blank)")
self.fps_spin.setSpecialValueText("(source)")
self.width_spin.setSpecialValueText("(source)")
```

### Tooltips
```python
self.crf_spin.setToolTip("0 = lossless, 51 = worst quality. 18-23 recommended.")
self.two_pass_check.setToolTip("Slower encoding but better quality per bitrate")
```

### Status Messages
```python
self.file_count_label.setText("No files selected")
self.progress_label.setText("Ready")
```

---

**Next**: [05_INTEGRATION_GUIDE.md](./05_INTEGRATION_GUIDE.md) - How to integrate into other apps
