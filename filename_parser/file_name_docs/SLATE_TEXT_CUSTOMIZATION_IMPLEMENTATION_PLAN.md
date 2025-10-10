# Slate Text Customization - Phase-by-Phase Implementation Plan

**Date:** 2025-01-10
**Feature:** Configurable Gap Slate Text Labels and Time Formatting
**Status:** 📋 READY FOR IMPLEMENTATION
**Estimated Time:** 2-3 hours

---

## Executive Summary

This feature adds user-configurable text labels and time formatting for gap slates in timeline videos. Users can choose from preset phrases or create custom labels, plus select their preferred time display format.

### User Requirements

**Current State:**
```
GAP: Tue 21 May 19:35:00 → Tue 21 May 19:40:15  (Δ 5m 15s)
```

**Desired Flexibility:**
```
Nothing of Interest from 19:35:00 to 19:40:15
Total Duration = 5 min 15 sec

Motion Gap from 19:35:00 to 19:40:15
Total Duration = 5 min 15 sec

Gap in Chronology from 19:35:00 to 19:40:15
Total Duration = 5 min 15 sec

[Custom Text] from 19:35:00 to 19:40:15
Total Duration = 5 min 15 sec
```

---

## Architecture Overview

### Components to Modify

```
1. RenderSettings (Data Model)
   - Add slate_label_preset: str
   - Add slate_label_custom: str
   - Add slate_time_format: str

2. FFmpegTimelineBuilder (Slate Generation)
   - Update _segments_from_intervals() to use templates
   - Add _format_slate_text() method for template rendering
   - Support multiple time format styles

3. FilenameParserTab (UI)
   - Add "Slate Appearance" section under Timeline Parameters
   - Add label preset dropdown
   - Add custom text input (enabled when "Custom" selected)
   - Add time format dropdown

4. Settings Persistence (Optional Phase 4)
   - Store preferences in QSettings
   - Restore on tab initialization
```

---

## Phase 1: Data Model Updates

### File: `filename_parser/models/timeline_models.py`

**Location:** RenderSettings dataclass (starting around line 189)

**Changes:**

```python
@dataclass
class RenderSettings:
    """Settings for multicam video rendering."""

    # ... existing fields ...

    # Slate settings (existing)
    slate_duration_seconds: int = 5
    slate_background_color: str = "#1a1a1a"
    slate_text_color: str = "white"
    slate_font_size: int = 48

    # NEW: Slate text customization
    slate_label_preset: str = "gap"  # "gap", "nothing_of_interest", "motion_gap", "chronology_gap", "custom"
    slate_label_custom: str = ""     # Used when preset = "custom"
    slate_time_format: str = "time_only"  # "time_only", "date_time", "duration_multiline"

    # ... rest of existing fields ...
```

**Preset Label Definitions (add as module-level dict below RenderSettings):**

```python
# Slate label presets (user-facing text)
SLATE_LABEL_PRESETS = {
    "gap": "GAP",
    "nothing_of_interest": "Nothing of Interest",
    "motion_gap": "Motion Gap",
    "chronology_gap": "Gap in Chronology",
    "custom": "[Custom]"  # Placeholder, uses slate_label_custom
}

# Time format display styles
SLATE_TIME_FORMATS = {
    "time_only": {
        "name": "HH:MM:SS only",
        "example": "19:35:00 to 19:40:15\nDuration: 5m 15s"
    },
    "date_time": {
        "name": "Full Date & Time",
        "example": "Tue 21 May 19:35:00 to Tue 21 May 19:40:15\nDuration: 5m 15s"
    },
    "duration_multiline": {
        "name": "Multiline Duration",
        "example": "19:35:00 to 19:40:15\nTotal Duration = 5 min 15 sec"
    }
}
```

**Validation Logic (optional, add to RenderSettings.__post_init__ if exists):**

```python
def __post_init__(self):
    # Validate slate label preset
    if self.slate_label_preset not in SLATE_LABEL_PRESETS:
        logger.warning(f"Invalid slate_label_preset '{self.slate_label_preset}', defaulting to 'gap'")
        self.slate_label_preset = "gap"

    # Validate time format
    if self.slate_time_format not in SLATE_TIME_FORMATS:
        logger.warning(f"Invalid slate_time_format '{self.slate_time_format}', defaulting to 'time_only'")
        self.slate_time_format = "time_only"
```

---

## Phase 2: Slate Generation Logic

### File: `filename_parser/services/ffmpeg_timeline_builder.py`

#### Step 2.1: Add Slate Text Formatter Method

**Location:** Add after `_fmt_iso_time()` method (around line 703)

```python
def _format_slate_text(
    self,
    gap_start_dt: datetime,
    gap_end_dt: datetime,
    duration_seconds: float,
    settings: RenderSettings
) -> str:
    """
    Format gap slate text using user-configured templates.

    Args:
        gap_start_dt: Gap start datetime
        gap_end_dt: Gap end datetime
        duration_seconds: Duration in seconds
        settings: Render settings with slate customization

    Returns:
        Formatted slate text string
    """
    from filename_parser.models.timeline_models import SLATE_LABEL_PRESETS

    # Determine label text
    if settings.slate_label_preset == "custom":
        label = settings.slate_label_custom if settings.slate_label_custom else "GAP"
    else:
        label = SLATE_LABEL_PRESETS.get(settings.slate_label_preset, "GAP")

    # Format times based on selected format
    if settings.slate_time_format == "time_only":
        # HH:MM:SS only
        start_str = gap_start_dt.strftime("%H:%M:%S")
        end_str = gap_end_dt.strftime("%H:%M:%S")
        duration_str = self._fmt_dur(duration_seconds)
        text = f"{label} from {start_str} to {end_str}\nDuration: {duration_str}"

    elif settings.slate_time_format == "date_time":
        # Full date & time (current behavior)
        start_str = self._fmt_iso_time(gap_start_dt.isoformat())
        end_str = self._fmt_iso_time(gap_end_dt.isoformat())
        duration_str = self._fmt_dur(duration_seconds)
        text = f"{label}: {start_str} → {end_str}  (Δ {duration_str})"

    elif settings.slate_time_format == "duration_multiline":
        # Multiline with expanded duration format
        start_str = gap_start_dt.strftime("%H:%M:%S")
        end_str = gap_end_dt.strftime("%H:%M:%S")
        duration_str = self._fmt_dur_expanded(duration_seconds)
        text = f"{label} from {start_str} to {end_str}\nTotal Duration = {duration_str}"

    else:
        # Fallback to original format
        start_str = self._fmt_iso_time(gap_start_dt.isoformat())
        end_str = self._fmt_iso_time(gap_end_dt.isoformat())
        duration_str = self._fmt_dur(duration_seconds)
        text = f"{label}: {start_str} → {end_str}  (Δ {duration_str})"

    return text
```

#### Step 2.2: Add Expanded Duration Formatter

**Location:** Add after `_fmt_dur()` method (around line 686)

```python
def _fmt_dur_expanded(self, d: float) -> str:
    """
    Format duration as expanded human-readable text.

    Examples:
        - 75 seconds → "1 min 15 sec"
        - 3665 seconds → "1 hr 1 min 5 sec"
        - 90 seconds → "1 min 30 sec"

    Args:
        d: Duration in seconds

    Returns:
        Formatted duration string
    """
    d = max(0, int(round(d)))
    h = d // 3600
    m = (d % 3600) // 60
    s = d % 60

    parts = []
    if h == 1:
        parts.append("1 hr")
    elif h > 1:
        parts.append(f"{h} hrs")

    if m == 1:
        parts.append("1 min")
    elif m > 1 or (h and s):
        parts.append(f"{m} min")

    if s == 1:
        parts.append("1 sec")
    elif s > 1 or (not h and not m):
        parts.append(f"{s} sec")

    return " ".join(parts)
```

#### Step 2.3: Update Gap Slate Generation

**Location:** `_segments_from_intervals()` method, around line 393-394

**Replace:**
```python
# Format as readable text
text = f"GAP: {self._fmt_iso_time(gap_start_dt.isoformat())} → {self._fmt_iso_time(gap_end_dt.isoformat())}  (Δ {self._fmt_dur(t1 - t0)})"
```

**With:**
```python
# Format slate text using user-configured template
text = self._format_slate_text(
    gap_start_dt=gap_start_dt,
    gap_end_dt=gap_end_dt,
    duration_seconds=(t1 - t0),
    settings=settings
)
```

---

## Phase 3: UI Implementation

### File: `filename_parser/ui/filename_parser_tab.py`

#### Step 3.1: Add Slate Appearance Group

**Location:** In `_create_timeline_settings_tab()`, after Timeline Parameters Group (around line 676)

**Add New Section:**

```python
        layout.addWidget(params_group)

        # ============== NEW: Slate Appearance Group ==============
        slate_group = QGroupBox("🎨 Slate Appearance")
        slate_layout = QGridLayout(slate_group)
        slate_layout.setColumnStretch(1, 1)  # Make second column expandable

        # Row 0: Slate Label Preset
        slate_layout.addWidget(QLabel("Slate Label:"), 0, 0)
        self.slate_label_combo = QComboBox()
        self.slate_label_combo.addItem("GAP", "gap")
        self.slate_label_combo.addItem("Nothing of Interest", "nothing_of_interest")
        self.slate_label_combo.addItem("Motion Gap", "motion_gap")
        self.slate_label_combo.addItem("Gap in Chronology", "chronology_gap")
        self.slate_label_combo.addItem("Custom...", "custom")
        self.slate_label_combo.setToolTip(
            "<b>Choose the text label displayed on gap slates.</b><br><br>"
            "Select 'Custom...' to enter your own text."
        )
        self.slate_label_combo.currentIndexChanged.connect(self._toggle_custom_slate_label)
        slate_layout.addWidget(self.slate_label_combo, 0, 1)

        # Row 1: Custom Slate Label Input (hidden by default)
        slate_layout.addWidget(QLabel("Custom Label:"), 1, 0)
        self.slate_label_custom_input = QLineEdit()
        self.slate_label_custom_input.setPlaceholderText("Enter custom label text...")
        self.slate_label_custom_input.setEnabled(False)
        self.slate_label_custom_input.setToolTip(
            "Enter your custom slate label text.<br>"
            "Example: 'No Activity', 'Coverage Gap', etc."
        )
        slate_layout.addWidget(self.slate_label_custom_input, 1, 1)

        # Row 2: Time Format
        slate_layout.addWidget(QLabel("Time Format:"), 2, 0)
        self.slate_time_format_combo = QComboBox()
        self.slate_time_format_combo.addItem("HH:MM:SS only", "time_only")
        self.slate_time_format_combo.addItem("Full Date & Time", "date_time")
        self.slate_time_format_combo.addItem("Multiline Duration", "duration_multiline")
        self.slate_time_format_combo.setToolTip(
            "<b>Choose how times are displayed on gap slates.</b><br><br>"
            "<b>HH:MM:SS only:</b><br>"
            "19:35:00 to 19:40:15<br>"
            "Duration: 5m 15s<br><br>"
            "<b>Full Date & Time:</b><br>"
            "Tue 21 May 19:35:00 → Tue 21 May 19:40:15  (Δ 5m 15s)<br><br>"
            "<b>Multiline Duration:</b><br>"
            "19:35:00 to 19:40:15<br>"
            "Total Duration = 5 min 15 sec"
        )
        slate_layout.addWidget(self.slate_time_format_combo, 2, 1)

        # Row 3: Preview (optional - shows how slate will look)
        slate_preview_label = QLabel(
            "ℹ️  Preview updates when rendering starts"
        )
        slate_preview_label.setWordWrap(True)
        slate_preview_label.setStyleSheet(
            "color: #6c757d; font-size: 10px; padding: 4px 8px; "
            "background-color: #f8f9fa; border-radius: 3px; margin-top: 4px;"
        )
        slate_layout.addWidget(slate_preview_label, 3, 0, 1, 2)

        layout.addWidget(slate_group)
        # ============== END: Slate Appearance Group ==============

        # Performance Settings Group (existing - no changes)
        perf_group = QGroupBox("⚡ Performance Settings")
        ...
```

#### Step 3.2: Add Custom Label Toggle Handler

**Location:** Event Handlers section, around line 870 (after `_toggle_output_structure`)

```python
    def _toggle_custom_slate_label(self, index):
        """Toggle custom slate label input based on dropdown selection"""
        selected_data = self.slate_label_combo.currentData()
        is_custom = (selected_data == "custom")
        self.slate_label_custom_input.setEnabled(is_custom)

        # Auto-focus the input when custom is selected
        if is_custom:
            self.slate_label_custom_input.setFocus()
```

#### Step 3.3: Update Timeline Settings Builder

**Location:** `_build_timeline_settings()` method, around line 1340

**Find this section:**
```python
        # Build RenderSettings
        settings = RenderSettings(
            output_directory=Path(self.timeline_output_dir_input.text()),
            output_filename=self.timeline_filename_input.text(),
            output_fps=self.timeline_fps_spin.value(),
            output_resolution=resolution,
            slate_duration_seconds=5,  # Fixed for now
            use_hardware_decode=self.timeline_hwdecode_check.isChecked(),
            use_batch_rendering=self.timeline_batch_check.isChecked(),
            keep_batch_temp_files=self.timeline_keep_temp_check.isChecked()
        )
```

**Replace with:**
```python
        # Build RenderSettings
        settings = RenderSettings(
            output_directory=Path(self.timeline_output_dir_input.text()),
            output_filename=self.timeline_filename_input.text(),
            output_fps=self.timeline_fps_spin.value(),
            output_resolution=resolution,
            slate_duration_seconds=5,  # Fixed for now

            # NEW: Slate customization settings
            slate_label_preset=self.slate_label_combo.currentData(),
            slate_label_custom=self.slate_label_custom_input.text(),
            slate_time_format=self.slate_time_format_combo.currentData(),

            use_hardware_decode=self.timeline_hwdecode_check.isChecked(),
            use_batch_rendering=self.timeline_batch_check.isChecked(),
            keep_batch_temp_files=self.timeline_keep_temp_check.isChecked()
        )
```

---

## Phase 4: Settings Persistence (Optional Enhancement)

### File: `filename_parser/ui/filename_parser_tab.py`

#### Step 4.1: Load Saved Settings on Init

**Location:** `__init__()` method, after `self.timeline_settings = RenderSettings()` (around line 74)

```python
        # Settings
        self.settings = FilenameParserSettings()
        self.timeline_settings = RenderSettings()

        # NEW: Load saved slate preferences
        self._load_slate_preferences()
```

#### Step 4.2: Implement Load Method

**Location:** Add new method in Settings section (around line 947, near `_build_settings`)

```python
    def _load_slate_preferences(self):
        """Load saved slate customization preferences from QSettings"""
        from PySide6.QtCore import QSettings

        settings = QSettings("ForensicApp", "FilenameParser")

        # Load slate label preset (default: "gap")
        saved_label_preset = settings.value("slate/label_preset", "gap")

        # Load custom label text (default: empty)
        saved_custom_text = settings.value("slate/label_custom", "")

        # Load time format (default: "time_only")
        saved_time_format = settings.value("slate/time_format", "time_only")

        # Apply to timeline settings
        self.timeline_settings.slate_label_preset = saved_label_preset
        self.timeline_settings.slate_label_custom = saved_custom_text
        self.timeline_settings.slate_time_format = saved_time_format
```

#### Step 4.3: Apply Loaded Settings to UI

**Location:** In `_create_timeline_settings_tab()`, after creating the slate widgets

```python
        # Apply saved preferences to UI (after creating all slate widgets)
        # Set label preset
        label_index = self.slate_label_combo.findData(self.timeline_settings.slate_label_preset)
        if label_index >= 0:
            self.slate_label_combo.setCurrentIndex(label_index)

        # Set custom label text
        self.slate_label_custom_input.setText(self.timeline_settings.slate_label_custom)

        # Set time format
        format_index = self.slate_time_format_combo.findData(self.timeline_settings.slate_time_format)
        if format_index >= 0:
            self.slate_time_format_combo.setCurrentIndex(format_index)
```

#### Step 4.4: Save Preferences on Change

**Location:** Add new method in Settings section

```python
    def _save_slate_preferences(self):
        """Save slate customization preferences to QSettings"""
        from PySide6.QtCore import QSettings

        settings = QSettings("ForensicApp", "FilenameParser")

        # Save current selections
        settings.setValue("slate/label_preset", self.slate_label_combo.currentData())
        settings.setValue("slate/label_custom", self.slate_label_custom_input.text())
        settings.setValue("slate/time_format", self.slate_time_format_combo.currentData())

        logger.debug("Saved slate preferences to QSettings")
```

**Connect to widgets in `_create_timeline_settings_tab()`:**

```python
        # Connect save on change
        self.slate_label_combo.currentIndexChanged.connect(self._save_slate_preferences)
        self.slate_label_custom_input.textChanged.connect(self._save_slate_preferences)
        self.slate_time_format_combo.currentIndexChanged.connect(self._save_slate_preferences)
```

---

## Testing Plan

### Test Case 1: Preset Labels

**Steps:**
1. Parse video files with timestamps
2. Go to Timeline Video tab
3. Set "Slate Label" to "Nothing of Interest"
4. Set "Time Format" to "HH:MM:SS only"
5. Generate timeline video

**Expected Result:**
```
Nothing of Interest from 19:35:00 to 19:40:15
Duration: 5m 15s
```

---

### Test Case 2: Custom Label

**Steps:**
1. Set "Slate Label" to "Custom..."
2. Enter "No Activity Detected" in custom input
3. Set "Time Format" to "Multiline Duration"
4. Generate timeline video

**Expected Result:**
```
No Activity Detected from 19:35:00 to 19:40:15
Total Duration = 5 min 15 sec
```

---

### Test Case 3: Full Date & Time (Current Behavior)

**Steps:**
1. Set "Slate Label" to "GAP"
2. Set "Time Format" to "Full Date & Time"
3. Generate timeline video

**Expected Result:**
```
GAP: Tue 21 May 19:35:00 → Tue 21 May 19:40:15  (Δ 5m 15s)
```

---

### Test Case 4: Settings Persistence

**Steps:**
1. Set custom slate preferences
2. Close and reopen application
3. Return to Timeline Video tab

**Expected Result:**
- All slate settings restored to previous values
- Custom text preserved

---

### Test Case 5: Edge Cases

**Test 5a: Empty Custom Label**
- Select "Custom..." but leave input blank
- Should fall back to "GAP" label

**Test 5b: Very Long Custom Label**
- Enter 100+ character custom text
- Should render on slate (may wrap or truncate based on font size)

**Test 5c: Duration Edge Cases**
- 1 second gap → "1 sec"
- 1 minute gap → "1 min 0 sec" or "1 min"
- 1 hour gap → "1 hr 0 min 0 sec" or "1 hr"

---

## Implementation Checklist

### Phase 1: Data Model ✅
- [ ] Add fields to RenderSettings dataclass
- [ ] Define SLATE_LABEL_PRESETS dict
- [ ] Define SLATE_TIME_FORMATS dict
- [ ] Add validation in __post_init__ (optional)
- [ ] Test: Import timeline_models.py without errors

### Phase 2: Slate Generation ✅
- [ ] Add _format_slate_text() method
- [ ] Add _fmt_dur_expanded() method
- [ ] Update _segments_from_intervals() to call _format_slate_text()
- [ ] Test: Generate timeline with default settings (no UI changes yet)

### Phase 3: UI Implementation ✅
- [ ] Add Slate Appearance QGroupBox
- [ ] Add slate_label_combo (QComboBox)
- [ ] Add slate_label_custom_input (QLineEdit)
- [ ] Add slate_time_format_combo (QComboBox)
- [ ] Add _toggle_custom_slate_label() handler
- [ ] Update _build_timeline_settings() to pass new fields
- [ ] Test: UI displays correctly, dropdowns populate
- [ ] Test: Custom input enables/disables based on selection
- [ ] Test: Generate timeline with various combinations

### Phase 4: Settings Persistence (Optional) ✅
- [ ] Add _load_slate_preferences() method
- [ ] Call from __init__()
- [ ] Add _save_slate_preferences() method
- [ ] Connect to widget signals
- [ ] Test: Settings persist across app restarts

---

## Visual Design Reference

**UI Layout (ASCII Art):**

```
┌─ Timeline Parameters ─────────────────────────────────────────┐
│ Timeline FPS:         [30.00 fps        ▼]                    │
│ Min Gap Duration:     [5.0 seconds      ▼]                    │
│ Output Resolution:    [1920x1080 (1080p)▼]                    │
└───────────────────────────────────────────────────────────────┘

┌─ 🎨 Slate Appearance ─────────────────────────────────────────┐
│ Slate Label:          [Nothing of Interest ▼]                 │
│ Custom Label:         [Enter custom label text...           ] │
│                       (disabled when not "Custom")             │
│ Time Format:          [HH:MM:SS only        ▼]                │
│                                                                │
│ ℹ️  Preview updates when rendering starts                     │
└───────────────────────────────────────────────────────────────┘

┌─ ⚡ Performance Settings ──────────────────────────────────────┐
│ ☐ Use GPU Hardware Decode (NVDEC)                             │
│ ☐ Use Batch Rendering for Large Datasets                      │
│ ☐ Keep Temp Files (Debugging)                                 │
│                                                                │
│ ℹ️  Auto-fallback: Batch mode activates automatically if...   │
└───────────────────────────────────────────────────────────────┘
```

---

## Code Style Patterns (From Existing UI)

### Pattern 1: QComboBox with Data

```python
self.combo_widget = QComboBox()
self.combo_widget.addItem("Display Text", "data_value")
self.combo_widget.addItem("Other Option", "other_value")
self.combo_widget.currentIndexChanged.connect(self._handler_method)
```

### Pattern 2: Conditional Input Enable/Disable

```python
def _toggle_feature(self, index):
    """Toggle dependent controls based on dropdown"""
    selected_data = self.combo_widget.currentData()
    is_enabled = (selected_data == "special_value")
    self.dependent_input.setEnabled(is_enabled)
```

### Pattern 3: QGridLayout for Settings

```python
group = QGroupBox("Section Title")
layout = QGridLayout(group)
layout.setColumnStretch(1, 1)  # Expand second column

layout.addWidget(QLabel("Setting:"), 0, 0)
layout.addWidget(self.setting_widget, 0, 1)
```

### Pattern 4: Tooltip with Examples

```python
widget.setToolTip(
    "<b>Main description.</b><br><br>"
    "<b>Option 1:</b><br>"
    "Example output line 1<br>"
    "Example output line 2<br><br>"
    "<b>Option 2:</b><br>"
    "Different example"
)
```

---

## Potential Issues & Solutions

### Issue 1: Multiline Slate Text Rendering

**Problem:** FFmpeg drawtext filter might not handle `\n` correctly in slate text

**Solution:**
- Test `\n` rendering first
- If broken, use two separate drawtext filters stacked vertically
- Alternative: Use `\\n` (escaped newline) or replace with space

**Code Example:**
```python
# If \n doesn't work, split into two lines
if '\n' in text:
    line1, line2 = text.split('\n', 1)
    # Generate two drawtext filters with different y positions
else:
    # Single line rendering
```

---

### Issue 2: Custom Text with Special Characters

**Problem:** User enters characters that break FFmpeg drawtext escaping

**Solution:**
- Already handled by `_escape_drawtext()` method
- Add extra validation in _format_slate_text() if needed

**Code Example:**
```python
# In _format_slate_text(), before returning:
text = self._escape_drawtext(text)
return text
```

---

### Issue 3: Very Long Custom Labels

**Problem:** User enters 200 character label that doesn't fit on slate

**Solution:**
- Add character limit to QLineEdit: `self.slate_label_custom_input.setMaxLength(50)`
- Or add warning in tooltip about recommended length

---

### Issue 4: QSettings Not Persisting

**Problem:** Settings don't save/load correctly

**Solution:**
- Verify QSettings organization/application names match
- Add debug logging to confirm save/load operations
- Test with `QSettings::fileName()` to check file location

---

## Performance Considerations

**Impact:** Minimal
- Template formatting adds ~1ms per gap slate
- UI has 3 additional widgets (negligible memory)
- QSettings I/O only on app start/setting change

**Optimization:** None needed for this feature

---

## Accessibility Considerations

1. **Tooltips:** All new controls have descriptive tooltips with examples
2. **Keyboard Navigation:** Tab order flows naturally through settings
3. **Screen Readers:** Labels properly associated with inputs
4. **Visual Indicators:** Custom input clearly shows enabled/disabled state

---

## Documentation Updates Needed

### User-Facing Documentation

1. **README.md / User Guide:**
   - Add section: "Customizing Gap Slate Appearance"
   - Include screenshots of slate customization UI
   - Show examples of each time format

2. **Tooltips (Already Included):**
   - Comprehensive examples in UI tooltips
   - No separate help file needed

### Developer Documentation

1. **CLAUDE.md:**
   - Update "Timeline Rendering" section
   - Document SLATE_LABEL_PRESETS dict
   - Document SLATE_TIME_FORMATS dict

2. **Code Comments:**
   - Already included in implementation snippets above

---

## Future Enhancements (Out of Scope)

### Enhancement 1: Live Preview
- Show real-time preview of slate text as user changes settings
- Requires rendering sample slate image in UI

### Enhancement 2: Font Customization
- Add font family dropdown
- Add font size spinbox
- Add font color picker

### Enhancement 3: Slate Duration Configuration
- Move `slate_duration_seconds` from hardcoded to UI spinbox
- Add to Slate Appearance group

### Enhancement 4: Template Presets
- Save/load complete slate style presets
- Import/export preset files (JSON)

### Enhancement 5: Background Image
- Allow user to upload custom slate background image
- Replace solid color with image overlay

---

## Estimated Implementation Time

| Phase | Task | Estimated Time |
|-------|------|----------------|
| Phase 1 | Data Model Updates | 15 minutes |
| Phase 2 | Slate Generation Logic | 30 minutes |
| Phase 3 | UI Implementation | 60 minutes |
| Phase 4 | Settings Persistence | 30 minutes |
| Testing | All test cases | 30 minutes |
| **Total** | | **~2.5-3 hours** |

---

## Success Criteria

✅ **Functional Requirements Met:**
- [ ] User can select from 4 preset labels
- [ ] User can enter custom label text
- [ ] User can select from 3 time formats
- [ ] Slate text renders correctly in timeline video
- [ ] Settings persist across app restarts

✅ **Quality Requirements Met:**
- [ ] UI matches existing design patterns
- [ ] No regression in timeline rendering
- [ ] Code follows project style guide
- [ ] All test cases pass

✅ **User Experience Requirements Met:**
- [ ] Feature is intuitive (no user manual needed)
- [ ] Tooltips provide clear guidance
- [ ] Custom input auto-focuses when selected
- [ ] Preview info helps user understand output

---

## Implementation Order (Step-by-Step)

### Session 1: Core Functionality (1.5 hours)

1. **Phase 1:** Data model updates (15 min)
   - Edit timeline_models.py
   - Test import

2. **Phase 2:** Slate generation (30 min)
   - Add _format_slate_text() method
   - Add _fmt_dur_expanded() method
   - Update _segments_from_intervals()
   - Test with hardcoded settings

3. **Phase 3:** UI basics (45 min)
   - Add Slate Appearance group
   - Add all widgets
   - Add toggle handler
   - Update settings builder
   - Test UI displays

### Session 2: Polish & Testing (1 hour)

4. **Phase 4:** Settings persistence (30 min)
   - Add load/save methods
   - Connect signals
   - Test persistence

5. **Testing:** All test cases (30 min)
   - Run all 5 test cases
   - Fix any bugs
   - Verify no regressions

---

**END OF IMPLEMENTATION PLAN**

Now go get some well-deserved sleep! When you wake up, you can implement this feature step-by-step following this plan. 😴🎉
