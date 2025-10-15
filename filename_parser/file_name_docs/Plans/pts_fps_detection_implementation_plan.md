# PTS-Based Frame Rate Detection: Implementation Plan

## Executive Summary

This document provides a complete, phase-by-phase implementation plan for adding **PTS-based frame rate detection** as a user-selectable option in the Filename Parser feature. This addresses the critical issue where DVR systems report incorrect frame rates in container metadata (e.g., claiming 25fps when actual PTS timing is 12.5fps).

**Implementation Complexity**: Medium (6-8 hours including testing)
**Files Modified**: 6 core files
**New Files**: 1 test file
**Backward Compatibility**: Full (existing metadata-based detection remains default)

---

## Table of Contents

1. [Technical Background](#technical-background)
2. [Phase 1: Core PTS Detection Logic](#phase-1)
3. [Phase 2: Service Layer Integration](#phase-2)
4. [Phase 3: Settings Model Update](#phase-3)
5. [Phase 4: UI Controls](#phase-4)
6. [Phase 5: Integration & Testing](#phase-5)
7. [Verification Checklist](#verification)

---

## Technical Background {#technical-background}

### The Problem

CCTV DVR systems often write **incorrect frame rates** to video container metadata:

```python
# Container claims:
container["avg_frame_rate"] = "25/1"  # 25 fps

# But PTS timing reveals:
frame_0_pts = 0.000000
frame_1_pts = 0.080000  # 80ms gap
# Real FPS = 1 / 0.080 = 12.5 fps (NOT 25!)
```

**Impact**: Videos play at wrong speed in most players (only VLC/MPV respect PTS).

### The Solution

**Calculate TRUE frame rate from PTS deltas**:

```python
# Sample N frames
pts_samples = [0.000, 0.080, 0.160, 0.240, 0.320]  # First 5 frames

# Calculate average inter-frame interval
intervals = [pts_samples[i+1] - pts_samples[i] for i in range(len(pts_samples)-1)]
avg_interval = sum(intervals) / len(intervals)  # 0.080

# Calculate true FPS
true_fps = 1.0 / avg_interval  # 12.5 fps
```

### User Experience

Add dropdown in UI:
```
Frame Rate Detection Method: [PTS Timing (Accurate) ▼]
                             [Metadata (Fast)        ]
                             [Override: ___ fps      ]
```

---

## Phase 1: Core PTS Detection Logic {#phase-1}

### 1.1 Add PTS Sampling to VideoMetadataExtractor

**File**: `filename_parser/services/video_metadata_extractor.py`

**Location**: Add new method after `_extract_first_frame_data()`

```python
def _calculate_pts_based_fps(
    self,
    file_path: Path,
    sample_count: int = 30
) -> Optional[float]:
    """
    Calculate TRUE frame rate by measuring PTS deltas between frames.
    
    This method samples multiple frames and calculates the average inter-frame
    interval from PTS timing, which is more accurate than container metadata
    for CCTV/DVR files where declared FPS is often wrong.
    
    Args:
        file_path: Path to video file
        sample_count: Number of frames to sample (default: 30)
                     More samples = more accurate, but slower
    
    Returns:
        Calculated FPS from PTS timing, or None if calculation failed
    
    Algorithm:
        1. Use FFprobe to extract PTS for first N frames
        2. Calculate inter-frame intervals (PTS deltas)
        3. Average the intervals to get mean frame time
        4. FPS = 1 / mean_frame_time
    
    Example:
        Frame 0: pts_time=0.000000
        Frame 1: pts_time=0.033367 (29.97fps → ~0.033s interval)
        Frame 2: pts_time=0.066733
        ...
        Average interval: 0.033367s → FPS = 29.97
    """
    ffprobe_path = binary_manager.get_ffprobe_path()
    
    if not ffprobe_path:
        self.logger.warning("FFprobe not available for PTS-based FPS detection")
        return None
    
    try:
        # FFprobe command to extract PTS for first N frames
        # read_intervals="%+#N" reads first N frames
        cmd = [
            ffprobe_path,
            "-v", "error",
            "-select_streams", "v:0",  # First video stream
            "-read_intervals", f"%+#{sample_count}",  # Read first N frames
            "-show_entries", "frame=pts_time",  # Only PTS time field
            "-of", "json",
            str(file_path)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=10  # 10 second timeout for frame sampling
        )
        
        if result.returncode != 0:
            self.logger.warning(f"FFprobe frame sampling failed: {result.stderr[:200]}")
            return None
        
        # Parse JSON
        data = json.loads(result.stdout)
        frames = data.get("frames", [])
        
        if len(frames) < 2:
            self.logger.warning(
                f"{file_path.name}: Insufficient frames for PTS calculation (got {len(frames)}, need >= 2). "
                f"File may be too short, corrupted, or using codec without PTS support. "
                f"Falling back to container metadata."
            )
            return None
        
        # Extract PTS times
        pts_times = []
        for frame in frames:
            pts_time = frame.get("pts_time")
            if pts_time is not None:
                try:
                    pts_times.append(float(pts_time))
                except (ValueError, TypeError):
                    continue
        
        if len(pts_times) < 2:
            self.logger.warning(
                f"{file_path.name}: Could not parse PTS times from frames. "
                f"Video may use old codec without PTS data or file is damaged. "
                f"Falling back to container metadata."
            )
            return None

        # Calculate inter-frame intervals (PTS deltas)
        intervals = []
        for i in range(len(pts_times) - 1):
            interval = pts_times[i + 1] - pts_times[i]
            if interval > 0:  # Sanity check (ignore zero/negative intervals)
                intervals.append(interval)
        
        if not intervals:
            self.logger.warning(
                f"{file_path.name}: No valid PTS intervals found (all intervals were zero or negative). "
                f"Video stream may be damaged or use non-standard timing. "
                f"Falling back to container metadata."
            )
            return None
        
        # Calculate average interval
        avg_interval = sum(intervals) / len(intervals)
        
        # Calculate FPS
        calculated_fps = 1.0 / avg_interval
        
        # Sanity check (reasonable FPS range)
        if calculated_fps < 1.0 or calculated_fps > 240.0:
            self.logger.warning(
                f"Calculated FPS {calculated_fps:.2f} outside valid range [1-240], "
                f"rejecting PTS-based detection"
            )
            return None
        
        self.logger.info(
            f"PTS-based FPS: {calculated_fps:.3f} fps "
            f"(sampled {len(intervals)} intervals, avg={avg_interval:.6f}s)"
        )
        
        return calculated_fps
    
    except subprocess.TimeoutExpired:
        self.logger.warning("PTS sampling timeout (>10s)")
        return None
    except json.JSONDecodeError as e:
        self.logger.warning(f"JSON parse error in PTS sampling: {e}")
        return None
    except Exception as e:
        self.logger.warning(f"Unexpected error in PTS sampling: {e}")
        return None
```

### 1.2 Add FPS Detection Method Enum

**File**: `filename_parser/services/video_metadata_extractor.py`

**Location**: Add at top of file after imports

```python
from enum import Enum

class FPSDetectionMethod(str, Enum):
    """Frame rate detection method selection."""
    METADATA = "metadata"  # Use container r_frame_rate/avg_frame_rate (fast, may be wrong)
    PTS_TIMING = "pts_timing"  # Calculate from PTS deltas (accurate, slower)
    OVERRIDE = "override"  # Use user-specified FPS
```

### 1.3 Update extract_metadata() Signature

**File**: `filename_parser/services/video_metadata_extractor.py`

**Location**: Modify existing `extract_metadata()` method signature and add fps_method parameter

**BEFORE**:
```python
def extract_metadata(self, file_path: Path) -> VideoProbeData:
    """Extract all video metadata in one ffprobe call."""
    # ... ffprobe execution ...

    return self._parse_probe_data(probe_data)
```

**AFTER**:
```python
def extract_metadata(
    self,
    file_path: Path,
    fps_method: FPSDetectionMethod = FPSDetectionMethod.METADATA,
    fps_override: Optional[float] = None
) -> VideoProbeData:
    """
    Extract all video metadata in one ffprobe call.

    Args:
        file_path: Path to video file
        fps_method: Method for frame rate detection
        fps_override: Manual FPS override (used if fps_method=OVERRIDE)

    Returns:
        VideoProbeData with all extracted fields
    """
    # ... ffprobe execution ...

    # Pass parameters to parsing method
    return self._parse_probe_data(
        probe_data,
        file_path,
        fps_method,
        fps_override
    )
```

### 1.4 Update _parse_probe_data() Method Signature

**File**: `filename_parser/services/video_metadata_extractor.py`

**Location**: Update `_parse_probe_data()` method signature and frame rate extraction logic

**FIND METHOD SIGNATURE**:
```python
def _parse_probe_data(
    self,
    probe_data: dict
) -> VideoProbeData:
```

**REPLACE WITH**:
```python
def _parse_probe_data(
    self,
    probe_data: dict,
    file_path: Path,
    fps_method: FPSDetectionMethod = FPSDetectionMethod.METADATA,
    fps_override: Optional[float] = None
) -> VideoProbeData:
    """
    Parse ffprobe data and extract metadata.

    Args:
        probe_data: Raw ffprobe JSON data
        file_path: Path to video file (needed for PTS calculation)
        fps_method: Frame rate detection method
        fps_override: Manual FPS override value

    Returns:
        VideoProbeData with all extracted fields
    """
```

**THEN FIND THIS CODE** (around line 100 in the method):
```python
# Extract frame rate
frame_rate = self._extract_frame_rate(video_stream)
```

**REPLACE WITH**:
```python
# Extract frame rate using selected method
if fps_method == FPSDetectionMethod.OVERRIDE and fps_override:
    # User-specified override
    frame_rate = fps_override
    self.logger.info(f"Using override FPS: {frame_rate}")

elif fps_method == FPSDetectionMethod.PTS_TIMING:
    # Calculate from PTS deltas
    pts_fps = self._calculate_pts_based_fps(file_path)
    
    if pts_fps:
        frame_rate = pts_fps
        self.logger.info(f"Using PTS-calculated FPS: {frame_rate:.3f}")
    else:
        # Fallback to metadata if PTS calculation fails
        frame_rate = self._extract_frame_rate(video_stream)
        self.logger.warning(
            f"PTS calculation failed, falling back to metadata FPS: {frame_rate}"
        )

else:  # FPSDetectionMethod.METADATA (default)
    # Use container metadata (r_frame_rate/avg_frame_rate)
    frame_rate = self._extract_frame_rate(video_stream)
    self.logger.debug(f"Using metadata FPS: {frame_rate}")
```

### 1.5 Add VideoProbeData FPS Method Field

**File**: `filename_parser/services/video_metadata_extractor.py`

**Location**: Update `VideoProbeData` dataclass

**FIND**:
```python
@dataclass
class VideoProbeData:
    """Complete video metadata from ffprobe."""
    
    # ... existing fields ...
    
    # Success flag
    success: bool = True
    error_message: str = ""
```

**ADD BEFORE `success` field**:
```python
    # FPS detection metadata (NEW)
    fps_detection_method: str = "metadata"  # "metadata", "pts_timing", or "override"
```

### 1.6 Set FPS Detection Method in Return

**File**: `filename_parser/services/video_metadata_extractor.py`

**Location**: Update the `return VideoProbeData(...)` statement in `_parse_probe_data()`

**FIND**:
```python
return VideoProbeData(
    file_path=file_path,
    file_size_bytes=file_size,
    duration_seconds=duration_seconds,
    frame_rate=frame_rate,
    # ... other fields ...
    success=True
)
```

**ADD FIELD**:
```python
return VideoProbeData(
    file_path=file_path,
    file_size_bytes=file_size,
    duration_seconds=duration_seconds,
    frame_rate=frame_rate,
    fps_detection_method=fps_method.value,  # ADD THIS LINE
    # ... other fields ...
    success=True
)
```

---

## Phase 2: Service Layer Integration {#phase-2}

### 2.1 Update FrameRateService Method Signatures

**File**: `filename_parser/services/frame_rate_service.py`

**Location**: Add fps_method parameter to detection methods

**2.1.1 Update detect_frame_rate()**

**FIND**:
```python
def detect_frame_rate(
    self,
    file_path: Path,
    progress_callback: Optional[Callable] = None
) -> Result[float]:
```

**REPLACE WITH**:
```python
def detect_frame_rate(
    self,
    file_path: Path,
    progress_callback: Optional[Callable] = None,
    fps_method: str = "metadata",
    fps_override: Optional[float] = None
) -> Result[float]:
    """
    Detect frame rate from video file.
    
    Args:
        file_path: Path to video file
        progress_callback: Optional progress callback
        fps_method: Detection method ("metadata", "pts_timing", or "override")
        fps_override: Manual FPS override (used if fps_method="override")
    
    Returns:
        Result containing frame rate or error
    """
```

**2.1.2 Update detect_batch_frame_rates()**

**FIND**:
```python
def detect_batch_frame_rates(
    self,
    file_paths: List[Path],
    use_default_on_failure: bool = True,
    progress_callback: Optional[Callable] = None,
) -> Dict[str, float]:
```

**REPLACE WITH**:
```python
def detect_batch_frame_rates(
    self,
    file_paths: List[Path],
    use_default_on_failure: bool = True,
    progress_callback: Optional[Callable] = None,
    fps_method: str = "metadata",
    fps_override: Optional[float] = None
) -> Dict[str, float]:
    """
    Detect frame rates for multiple files in parallel.
    
    Args:
        file_paths: List of file paths
        use_default_on_failure: Use default FPS on detection failure
        progress_callback: Optional progress callback
        fps_method: Detection method ("metadata", "pts_timing", or "override")
        fps_override: Manual FPS override (used if fps_method="override")
    
    Returns:
        Dictionary mapping file paths to frame rates
    """
```

### 2.2 Update FrameRateService Implementation

**File**: `filename_parser/services/frame_rate_service.py`

**2.2.1 Import FPSDetectionMethod**

**FIND** (at top of file):
```python
from filename_parser.services.video_metadata_extractor import VideoMetadataExtractor
```

**REPLACE WITH**:
```python
from filename_parser.services.video_metadata_extractor import (
    VideoMetadataExtractor,
    FPSDetectionMethod
)
```

**2.2.2 Update _detect_single() to use VideoMetadataExtractor**

**FIND** the `_detect_single()` method (uses direct FFprobe call)

**REPLACE ENTIRE METHOD**:
```python
def _detect_single(
    self,
    file_path: str,
    fps_method: str = "metadata",
    fps_override: Optional[float] = None
) -> FrameRateResult:
    """
    Detect frame rate for a single file using VideoMetadataExtractor.
    
    This now delegates to VideoMetadataExtractor which handles both
    metadata-based and PTS-based detection.
    
    Args:
        file_path: Path to video file
        fps_method: Detection method string
        fps_override: Manual FPS override
    
    Returns:
        FrameRateResult with detection outcome
    """
    # Validate file exists
    if not os.path.exists(file_path):
        return FrameRateResult(
            file_path=file_path,
            success=False,
            error_message="File not found"
        )
    
    # Convert string method to enum
    try:
        method_enum = FPSDetectionMethod(fps_method)
    except ValueError:
        self.logger.warning(f"Invalid FPS method '{fps_method}', using metadata")
        method_enum = FPSDetectionMethod.METADATA
    
    # Use VideoMetadataExtractor for detection
    extractor = VideoMetadataExtractor()
    probe_data = extractor.extract_metadata(
        Path(file_path),
        fps_method=method_enum,
        fps_override=fps_override
    )
    
    if not probe_data.success:
        return FrameRateResult(
            file_path=file_path,
            success=False,
            error_message=probe_data.error_message
        )
    
    # Normalize FPS to standard values
    normalized_fps = self.normalize_frame_rate(probe_data.frame_rate)
    
    return FrameRateResult(
        file_path=file_path,
        success=True,
        frame_rate=normalized_fps,
        method=probe_data.fps_detection_method
    )
```

**2.2.3 Update Batch Detection to Pass Parameters**

**FIND** the parallel execution loop in `detect_batch_frame_rates()`:

```python
with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
    futures = {
        executor.submit(self._detect_single, str(path)): path
        for path in file_paths
    }
```

**REPLACE WITH**:
```python
with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
    futures = {
        executor.submit(
            self._detect_single,
            str(path),
            fps_method,
            fps_override
        ): path
        for path in file_paths
    }
```

### 2.3 Update BatchProcessorService

**File**: `filename_parser/services/batch_processor_service.py`

**FIND** the frame rate detection section in `process_files()`:

```python
# Step 1: Detect frame rates if needed
fps_map = {}
if settings.detect_fps and not settings.fps_override:
    self.logger.info("Detecting frame rates...")
    if progress_callback:
        progress_callback(5, "Detecting frame rates...")
    
    fps_map = self._frame_rate_service.detect_batch_frame_rates(
        files,
        use_default_on_failure=True,
        progress_callback=lambda curr, total: self._emit_progress(
            curr, total, len(files), 5, 20, progress_callback, "Detecting frame rates"
        ),
    )
```

**REPLACE WITH**:
```python
# Step 1: Detect frame rates if needed
fps_map = {}
if settings.detect_fps and not settings.fps_override:
    self.logger.info(f"Detecting frame rates using method: {settings.fps_detection_method}")
    if progress_callback:
        progress_callback(5, "Detecting frame rates...")
    
    fps_map = self._frame_rate_service.detect_batch_frame_rates(
        files,
        use_default_on_failure=True,
        progress_callback=lambda curr, total: self._emit_progress(
            curr, total, len(files), 5, 20, progress_callback, "Detecting frame rates"
        ),
        fps_method=settings.fps_detection_method,
        fps_override=settings.fps_override
    )
```

---

## Phase 3: Settings Model Update {#phase-3}

### 3.1 Add FPS Detection Method Field

**File**: `filename_parser/models/filename_parser_models.py`

**FIND** the `FilenameParserSettings` class definition:

```python
@dataclass
class FilenameParserSettings:
    """Settings for filename parser operations."""
    
    # Pattern selection
    pattern_id: Optional[str] = "auto"
    custom_pattern: Optional[str] = None
    
    # Frame rate settings
    detect_fps: bool = True
    fps_override: Optional[float] = None
```

**ADD FIELD after `detect_fps`**:
```python
    # Pattern selection
    pattern_id: Optional[str] = "auto"
    custom_pattern: Optional[str] = None
    
    # Frame rate settings
    detect_fps: bool = True
    fps_detection_method: str = "metadata"  # "metadata", "pts_timing", or "override"
    fps_override: Optional[float] = None
```

### 3.2 Update Serialization Methods

**File**: `filename_parser/models/filename_parser_models.py`

**3.2.1 Update to_dict()**

**FIND**:
```python
def to_dict(self) -> Dict[str, Any]:
    """Convert to dictionary for serialization."""
    return {
        "pattern_id": self.pattern_id,
        "custom_pattern": self.custom_pattern,
        "detect_fps": self.detect_fps,
        "fps_override": self.fps_override,
```

**ADD FIELD**:
```python
def to_dict(self) -> Dict[str, Any]:
    """Convert to dictionary for serialization."""
    return {
        "pattern_id": self.pattern_id,
        "custom_pattern": self.custom_pattern,
        "detect_fps": self.detect_fps,
        "fps_detection_method": self.fps_detection_method,  # ADD THIS
        "fps_override": self.fps_override,
```

**3.2.2 Update from_dict()**

**FIND**:
```python
@classmethod
def from_dict(cls, data: Dict[str, Any]) -> "FilenameParserSettings":
    """Create from dictionary."""
    return cls(
        pattern_id=data.get("pattern_id"),
        custom_pattern=data.get("custom_pattern"),
        detect_fps=data.get("detect_fps", True),
        fps_override=data.get("fps_override"),
```

**ADD FIELD**:
```python
@classmethod
def from_dict(cls, data: Dict[str, Any]) -> "FilenameParserSettings":
    """Create from dictionary."""
    return cls(
        pattern_id=data.get("pattern_id"),
        custom_pattern=data.get("custom_pattern"),
        detect_fps=data.get("detect_fps", True),
        fps_detection_method=data.get("fps_detection_method", "metadata"),  # ADD THIS
        fps_override=data.get("fps_override"),
```

---

## Phase 4: UI Controls {#phase-4}

### 4.1 Add FPS Method Dropdown to UI

**File**: `filename_parser/ui/filename_parser_tab.py`

**FIND** the `_create_fps_section()` method (creates "Frame Rate" settings group)

**4.1.1 Add Detection Method Dropdown**

**FIND** this section (around line 450):
```python
def _create_fps_section(self) -> QGroupBox:
    """Create frame rate settings section"""
    group = QGroupBox("🎯 Frame Rate")
    layout = QVBoxLayout(group)
    
    # Auto-detect checkbox
    self.detect_fps_check = QCheckBox("Auto-detect frame rates")
    self.detect_fps_check.setChecked(True)
    self.detect_fps_check.toggled.connect(self._on_fps_detect_toggled)
    layout.addWidget(self.detect_fps_check)
```

**ADD AFTER the checkbox** (before fps_override section):
```python
    # Detection method dropdown (NEW)
    method_layout = QHBoxLayout()
    method_layout.addWidget(QLabel("Detection Method:"))
    
    self.fps_method_combo = QComboBox()
    self.fps_method_combo.setObjectName("fpsMethodCombo")
    self.fps_method_combo.addItem("📊 Container Metadata (Fast)", "metadata")
    self.fps_method_combo.addItem("⏱️ PTS Timing (Accurate)", "pts_timing")
    self.fps_method_combo.setCurrentIndex(0)  # Default to metadata
    self.fps_method_combo.setEnabled(True)  # Always enabled when detect_fps is checked
    
    # Tooltip explaining the difference
    self.fps_method_combo.setToolTip(
        "<b>Frame Rate Detection Method:</b><br><br>"
        "<b>Container Metadata (Fast):</b><br>"
        "• Reads r_frame_rate/avg_frame_rate from file<br>"
        "• Instant detection, no processing<br>"
        "• May be INCORRECT for CCTV/DVR files<br>"
        "• DVRs often stamp wrong FPS (e.g., 25fps when actual is 12.5fps)<br><br>"
        "<b>PTS Timing (Accurate):</b><br>"
        "• Calculates FPS from frame timestamps (PTS deltas)<br>"
        "• Measures ACTUAL playback rate<br>"
        "• Slower (~1-2s per file)<br>"
        "• Recommended for forensic/CCTV workflows<br>"
        "• Matches VLC/MPV playback behavior"
    )
    
    method_layout.addWidget(self.fps_method_combo)
    method_layout.addStretch()
    layout.addLayout(method_layout)
```

**4.1.2 Update FPS Override Section**

**FIND** the FPS override section:
```python
# FPS override
override_layout = QHBoxLayout()
override_layout.addWidget(QLabel("Override FPS:"))

self.fps_override_spin = QDoubleSpinBox()
self.fps_override_spin.setRange(1.0, 240.0)
self.fps_override_spin.setValue(29.97)
self.fps_override_spin.setDecimals(3)
self.fps_override_spin.setSuffix(" fps")
self.fps_override_spin.setEnabled(False)
```

**ADD AFTER fps_override_spin setup**:
```python
# Update tooltip to mention PTS method
self.fps_override_spin.setToolTip(
    "Manually specify frame rate (disables auto-detection).<br>"
    "Use this when both metadata and PTS detection fail."
)
```

### 4.2 Connect Detection Method to Toggle Logic

**File**: `filename_parser/ui/filename_parser_tab.py`

**FIND** the `_on_fps_detect_toggled()` method:

```python
def _on_fps_detect_toggled(self, checked: bool):
    """Handle FPS auto-detect toggle"""
    self.fps_override_spin.setEnabled(not checked)
```

**REPLACE WITH**:
```python
def _on_fps_detect_toggled(self, checked: bool):
    """Handle FPS auto-detect toggle"""
    self.fps_override_spin.setEnabled(not checked)
    self.fps_method_combo.setEnabled(checked)  # Enable method selection when detecting
    
    # If unchecked, we're using override - change combo to "override" mode
    if not checked:
        # Visually indicate override mode (optional - just for UX)
        self.fps_method_combo.setToolTip("Using manual FPS override")
```

### 4.3 Update _build_settings() to Read Method

**File**: `filename_parser/ui/filename_parser_tab.py`

**FIND** the `_build_settings()` method section for FPS:

```python
def _build_settings(self):
    """Build settings from UI controls"""
    # ... pattern selection ...
    
    # Frame rate settings
    self.settings.detect_fps = self.detect_fps_check.isChecked()
    self.settings.fps_override = self.fps_override_spin.value() if not self.detect_fps_check.isChecked() else None
```

**REPLACE WITH**:
```python
def _build_settings(self):
    """Build settings from UI controls"""
    # ... pattern selection ...
    
    # Frame rate settings
    self.settings.detect_fps = self.detect_fps_check.isChecked()
    
    if self.detect_fps_check.isChecked():
        # Auto-detection enabled - use selected method
        self.settings.fps_detection_method = self.fps_method_combo.currentData()
        self.settings.fps_override = None
    else:
        # Manual override
        self.settings.fps_detection_method = "override"
        self.settings.fps_override = self.fps_override_spin.value()
```

### 4.4 Add Visual Feedback for PTS Detection

**File**: `filename_parser/ui/filename_parser_tab.py`

**FIND** the `_on_progress()` method:

```python
def _on_progress(self, percentage: int, message: str):
    """Handle progress updates from worker"""
    self.progress_bar.setValue(percentage)
    self.progress_label.setText(message)
```

**ADD AFTER** (to show which method is being used):
```python
    # Show detection method in first progress message
    if percentage == 5 and "frame rate" in message.lower():
        method_name = {
            "metadata": "Container Metadata",
            "pts_timing": "PTS Timing",
            "override": "Manual Override"
        }.get(self.settings.fps_detection_method, "Unknown")
        
        enhanced_message = f"{message} ({method_name})"
        self.progress_label.setText(enhanced_message)
```

---

## Phase 5: Integration & Testing {#phase-5}

### 5.1 Validation & Fallback Behavior

**Already Implemented**: The system has graceful fallbacks:

1. **PTS calculation fails** → Falls back to metadata
2. **Metadata missing** → Falls back to default (29.97)
3. **Override out of range** → Validation error

**No additional code needed** - existing error handling covers these cases.

### 5.2 Update ProcessingResult Model

**File**: `filename_parser/models/processing_result.py`

**FIND** the `ProcessingResult` dataclass definition:

```python
@dataclass
class ProcessingResult:
    """Result of processing a single file."""

    # ... existing fields ...
    frame_rate: Optional[float] = None
    parsed_time: Optional[str] = None
```

**ADD FIELDS** (after frame_rate):
```python
    # ... existing fields ...
    frame_rate: Optional[float] = None
    fps_detection_method: Optional[str] = None  # "metadata", "pts_timing", or "override"
    fps_fallback_occurred: bool = False  # True if PTS detection failed and fell back to metadata
    parsed_time: Optional[str] = None
```

### 5.3 Update BatchProcessorService to Populate FPS Method

**File**: `filename_parser/services/batch_processor_service.py`

**FIND** the section where VideoMetadataExtractor is called (in `_process_single_file()`):

```python
# Step 2: Extract full video metadata using VideoMetadataExtractor
video_probe_data = self._metadata_extractor.extract_metadata(file_path)
```

**REPLACE WITH**:
```python
# Step 2: Extract full video metadata using VideoMetadataExtractor
from filename_parser.services.video_metadata_extractor import FPSDetectionMethod

# Convert string method to enum for extractor
try:
    method_enum = FPSDetectionMethod(settings.fps_detection_method)
except ValueError:
    method_enum = FPSDetectionMethod.METADATA

video_probe_data = self._metadata_extractor.extract_metadata(
    file_path,
    fps_method=method_enum,
    fps_override=settings.fps_override
)
```

**THEN FIND** the ProcessingResult creation (around line 340):

```python
return ProcessingResult(
    source_file=str(file_path),
    filename=file_path.name,
    status=ProcessingStatus.SUCCESS,
    success=True,
    output_file=str(output_path),
    frame_rate=fps,
    parsed_time=parsed.time_data.time_string,
```

**ADD FIELDS**:
```python
return ProcessingResult(
    source_file=str(file_path),
    filename=file_path.name,
    status=ProcessingStatus.SUCCESS,
    success=True,
    output_file=str(output_path),
    frame_rate=fps,
    fps_detection_method=video_probe_data.fps_detection_method,  # ADD THIS
    fps_fallback_occurred=(
        settings.fps_detection_method == "pts_timing" and
        video_probe_data.fps_detection_method == "metadata"
    ),  # ADD THIS - detects when PTS fell back to metadata
    parsed_time=parsed.time_data.time_string,
```

### 5.4 CSV Export Update

**File**: `filename_parser/services/csv_export_service.py`

**FIND** the CSV column headers:

```python
fieldnames = [
    "filename",
    "source_file_path",
    "camera_id",
    "smpte_timecode",
    "start_time_iso",
    "end_time_iso",
    "duration_seconds",
    "frame_rate",
```

**ADD FIELDS**:
```python
fieldnames = [
    "filename",
    "source_file_path",
    "camera_id",
    "smpte_timecode",
    "start_time_iso",
    "end_time_iso",
    "duration_seconds",
    "frame_rate",
    "fps_detection_method",  # ADD THIS - shows how FPS was detected
    "fps_fallback_occurred",  # ADD THIS - flags when PTS detection failed
```

**Purpose**: The `fps_fallback_occurred` field helps forensic analysts quickly identify files where:
- PTS timing method was requested but failed
- System fell back to container metadata (potentially inaccurate)
- Manual review may be needed for critical cases

**Example CSV Output**:
```csv
filename,frame_rate,fps_detection_method,fps_fallback_occurred
camera1.mp4,29.97,pts_timing,false
camera2.mp4,25.00,metadata,true
camera3.mp4,15.00,override,false
```

### 5.5 Update VideoProbeData Model

**File**: `filename_parser/services/video_metadata_extractor.py`

**FIND** the `VideoProbeData` dataclass (where we added `fps_detection_method`):

```python
@dataclass
class VideoProbeData:
    """Complete video metadata from ffprobe."""

    # ... existing fields ...
    fps_detection_method: str = "metadata"
    success: bool = True
```

**ADD FIELD** (after fps_detection_method):
```python
@dataclass
class VideoProbeData:
    """Complete video metadata from ffprobe."""

    # ... existing fields ...
    fps_detection_method: str = "metadata"
    fps_fallback_occurred: bool = False  # ADD THIS - tracks if PTS detection failed
    success: bool = True
```

**THEN UPDATE** the return statement in `_parse_probe_data()` to set this flag:

**FIND**:
```python
return VideoProbeData(
    file_path=file_path,
    file_size_bytes=file_size,
    duration_seconds=duration_seconds,
    frame_rate=frame_rate,
    fps_detection_method=fps_method.value,
    # ... other fields ...
    success=True
)
```

**REPLACE WITH**:
```python
# Determine if fallback occurred (user requested PTS but got metadata)
fps_fallback = (fps_method == FPSDetectionMethod.PTS_TIMING and
                fps_detection_method_used == "metadata")

return VideoProbeData(
    file_path=file_path,
    file_size_bytes=file_size,
    duration_seconds=duration_seconds,
    frame_rate=frame_rate,
    fps_detection_method=fps_method.value,
    fps_fallback_occurred=fps_fallback,  # ADD THIS
    # ... other fields ...
    success=True
)
```

**NOTE**: You'll need to track the actual method used. Update the frame rate extraction section:

**In Phase 1.4, update the frame rate extraction logic to track the method**:

```python
# Extract frame rate using selected method
fps_detection_method_used = fps_method.value  # Track what we actually used

if fps_method == FPSDetectionMethod.OVERRIDE and fps_override:
    # User-specified override
    frame_rate = fps_override
    fps_detection_method_used = "override"
    self.logger.info(f"Using override FPS: {frame_rate}")

elif fps_method == FPSDetectionMethod.PTS_TIMING:
    # Calculate from PTS deltas
    pts_fps = self._calculate_pts_based_fps(file_path)

    if pts_fps:
        frame_rate = pts_fps
        fps_detection_method_used = "pts_timing"
        self.logger.info(f"Using PTS-calculated FPS: {frame_rate:.3f}")
    else:
        # Fallback to metadata if PTS calculation fails
        frame_rate = self._extract_frame_rate(video_stream)
        fps_detection_method_used = "metadata"  # Fell back!
        self.logger.warning(
            f"PTS calculation failed, falling back to metadata FPS: {frame_rate}"
        )

else:  # FPSDetectionMethod.METADATA (default)
    # Use container metadata (r_frame_rate/avg_frame_rate)
    frame_rate = self._extract_frame_rate(video_stream)
    fps_detection_method_used = "metadata"
    self.logger.debug(f"Using metadata FPS: {frame_rate}")
```

### 5.6 Logging Enhancements

**File**: `filename_parser/services/batch_processor_service.py`

**FIND** the per-file processing logging:

```python
self.logger.info(f"Processing {file_path.name} with fps={fps}")
```

**ENHANCE WITH**:
```python
fallback_note = " (FALLBACK: PTS failed)" if video_probe_data.fps_fallback_occurred else ""
self.logger.info(
    f"Processing {file_path.name} with fps={fps:.3f} "
    f"(method: {video_probe_data.fps_detection_method}){fallback_note}"
)
```

### 5.7 Performance Monitoring

**File**: `filename_parser/services/video_metadata_extractor.py`

**Location**: Add performance logging to `_calculate_pts_based_fps()` method

**FIND** the successful FPS calculation log:

```python
self.logger.info(
    f"PTS-based FPS: {calculated_fps:.3f} fps "
    f"(sampled {len(intervals)} intervals, avg={avg_interval:.6f}s)"
)
```

**REPLACE WITH**:
```python
import time  # Add at top of file if not present

# At start of _calculate_pts_based_fps():
start_time = time.time()

# ... (rest of method) ...

# At successful completion:
elapsed = time.time() - start_time
self.logger.info(
    f"PTS-based FPS: {calculated_fps:.3f} fps "
    f"(sampled {len(intervals)} intervals, avg={avg_interval:.6f}s, "
    f"detection time: {elapsed:.2f}s)"
)
```

---

## Phase 6: Testing Strategy {#testing-strategy}

### 6.1 Unit Test Creation

**Create New File**: `filename_parser/tests/test_pts_fps_detection.py`

```python
"""
Unit tests for PTS-based frame rate detection.

Tests cover:
1. PTS calculation from sample frames
2. Fallback behavior when PTS fails
3. Method selection logic
4. Integration with batch processing
"""

import pytest
from pathlib import Path
from filename_parser.services.video_metadata_extractor import (
    VideoMetadataExtractor,
    FPSDetectionMethod
)


class TestPTSFPSDetection:
    """Test PTS-based frame rate detection."""
    
    def test_pts_calculation_30fps(self):
        """Test PTS calculation for standard 30fps video."""
        # This would need a test video file with known FPS
        # For now, this is a placeholder
        pass
    
    def test_pts_calculation_variable_rate(self):
        """Test PTS calculation handles irregular intervals."""
        pass
    
    def test_fallback_to_metadata(self):
        """Test fallback when PTS calculation fails."""
        pass
    
    def test_method_selection(self):
        """Test correct method is used based on setting."""
        pass
```

### 6.2 Integration Test Scenarios

**Test Files Needed**:

1. **metadata_correct.mp4**: Container FPS matches PTS timing
   - Expected: Both methods return same FPS
   
2. **metadata_wrong.mp4**: Container claims 25fps, PTS reveals 12.5fps
   - Expected: Metadata returns 25, PTS returns 12.5
   
3. **vfr_video.mp4**: Variable frame rate
   - Expected: PTS returns average, metadata may fail
   
4. **corrupted.mp4**: Damaged file
   - Expected: Graceful failure, fallback to default

### 6.3 Manual Testing Checklist

**Execution**: After implementation, manually test these scenarios:

```markdown
### Manual Test Plan

- [ ] **Default Behavior (Metadata)**
  - Select files
  - Ensure "Container Metadata" is selected
  - Process files
  - Verify fast processing (<1s per file)
  - Check CSV shows `fps_detection_method: metadata`

- [ ] **PTS Timing Method**
  - Select files
  - Choose "PTS Timing (Accurate)"
  - Process files
  - Verify slower processing (~2s per file)
  - Check CSV shows `fps_detection_method: pts_timing`
  - Compare FPS results with metadata method

- [ ] **Manual Override**
  - Uncheck "Auto-detect"
  - Set override to 15.0 fps
  - Process files
  - Verify all files report 15.0 fps
  - Check CSV shows `fps_detection_method: override`

- [ ] **Fallback Behavior**
  - Use PTS method on corrupted file
  - Verify falls back to metadata
  - Check console logs for fallback message

- [ ] **UI State Management**
  - Toggle auto-detect on/off
  - Verify method combo enables/disables correctly
  - Verify override spinner enables/disables correctly

- [ ] **Batch Processing**
  - Mix 100 files (some 30fps, some 25fps, some 12fps)
  - Use PTS method
  - Verify correct FPS detected for each
  - Check processing speed (should be ~2s per file)

- [ ] **Timeline Rendering**
  - Parse files with PTS method
  - Generate timeline video
  - Verify playback is smooth (correct FPS used)
```

---

## Verification Checklist {#verification}

### Code Changes Summary

```markdown
### Files Modified (6 total)

1. ✅ filename_parser/services/video_metadata_extractor.py
   - Added _calculate_pts_based_fps() method with performance logging
   - Added FPSDetectionMethod enum
   - Updated extract_metadata() signature with fps_method/fps_override parameters
   - Updated _parse_probe_data() signature to accept file_path, fps_method, fps_override
   - Updated frame rate extraction logic with method selection
   - Added fps_detection_method field to VideoProbeData

2. ✅ filename_parser/services/frame_rate_service.py
   - Updated detect_frame_rate() signature with fps_method/fps_override
   - Updated detect_batch_frame_rates() signature with fps_method/fps_override
   - Refactored _detect_single() to use VideoMetadataExtractor
   - Added fps_method/fps_override parameter passing in parallel execution

3. ✅ filename_parser/services/batch_processor_service.py
   - Updated frame rate detection to pass fps_method
   - Added FPSDetectionMethod enum import
   - Updated VideoMetadataExtractor calls with method selection
   - Updated ProcessingResult creation to include fps_detection_method
   - Enhanced logging with detection method info

4. ✅ filename_parser/models/filename_parser_models.py
   - Added fps_detection_method field to FilenameParserSettings
   - Updated to_dict() serialization
   - Updated from_dict() deserialization

5. ✅ filename_parser/models/processing_result.py
   - Added fps_detection_method field to ProcessingResult dataclass
   - Added fps_fallback_occurred field for forensic audit tracking

6. ✅ filename_parser/ui/filename_parser_tab.py
   - Added fps_method_combo dropdown with tooltips
   - Updated _on_fps_detect_toggled() logic for method combo
   - Updated _build_settings() to read method selection
   - Added visual feedback in progress updates

7. ✅ filename_parser/services/csv_export_service.py
   - Added fps_detection_method to CSV fieldnames
   - Added fps_fallback_occurred to CSV fieldnames for audit trail
```

### Functional Requirements

```markdown
### User Experience

✅ User can select FPS detection method from dropdown:
   - Container Metadata (Fast) [default]
   - PTS Timing (Accurate)

✅ User can manually override FPS (disables auto-detection)

✅ Settings persist across sessions (serialization)

✅ Progress indicator shows which method is being used

✅ CSV export includes detection method used

### Technical Requirements

✅ PTS-based detection samples 30 frames (configurable)

✅ Calculates average inter-frame interval

✅ FPS = 1 / average_interval

✅ Sanity checks (1-240 fps range)

✅ Fallback to metadata if PTS fails

✅ Parallel processing maintained (ThreadPoolExecutor)

✅ Backward compatible (metadata remains default)

### Performance Requirements

✅ Metadata method: <1s per file (no change)

✅ PTS method: ~2s per file (acceptable for accuracy)

✅ Batch processing: parallelized across files

✅ No memory leaks (FFprobe subprocess cleanup)
```

---

## Rollout Plan

### Phase 1: Development (You Are Here)
- Implement all code changes above
- Run unit tests
- Manual smoke testing

### Phase 2: Beta Testing
- Deploy to test environment
- Process known problematic DVR files
- Compare PTS vs metadata FPS results
- Verify timeline playback accuracy

### Phase 3: Documentation
- Update user guide with new dropdown
- Add tooltip explanations
- Create troubleshooting guide

### Phase 4: Production Deployment
- Merge to main branch
- Update changelog
- Notify users of new feature

---

## Expected Outcomes

### Before Implementation
```
DVR file: camera_2025_05_21_143045.mp4
Container FPS: 25.0 (WRONG!)
Playback: Too fast (2x speed in most players)
Timeline: Drift/desync issues
```

### After Implementation (PTS Method)
```
DVR file: camera_2025_05_21_143045.mp4
Container FPS: 25.0
PTS-calculated FPS: 12.5 (CORRECT!)
Playback: Smooth, accurate speed
Timeline: Perfect synchronization
```

---

## Forensic Audit Trail

### Purpose

The `fps_fallback_occurred` field provides critical forensic audit information by tracking when PTS-based detection fails and the system falls back to container metadata. This is essential for:

1. **Quality Assurance**: Identifying files that may have inaccurate frame rates
2. **Manual Review**: Flagging videos requiring forensic analyst attention
3. **Chain of Custody**: Documenting detection method limitations
4. **Batch Analysis**: Quickly filtering problematic files from large datasets

### How It Works

```python
# Scenario 1: Successful PTS Detection
User selects: "PTS Timing (Accurate)"
System detects: PTS timing successfully
Result:
  fps_detection_method = "pts_timing"
  fps_fallback_occurred = false
  ✅ High confidence in frame rate accuracy

# Scenario 2: PTS Detection Failure
User selects: "PTS Timing (Accurate)"
System detects: PTS failed (old codec/damaged file)
System falls back: Uses container metadata
Result:
  fps_detection_method = "metadata"
  fps_fallback_occurred = true
  ⚠️  Low confidence - manual review recommended

# Scenario 3: Metadata Method (User Choice)
User selects: "Container Metadata (Fast)"
System detects: Container metadata
Result:
  fps_detection_method = "metadata"
  fps_fallback_occurred = false
  ✅ User explicitly chose this method
```

### CSV Analysis Example

Forensic analysts can filter CSV exports to find problematic files:

```python
import pandas as pd

# Load results
df = pd.read_csv("processing_results.csv")

# Find files where PTS detection failed
fallback_files = df[df['fps_fallback_occurred'] == True]

print(f"Found {len(fallback_files)} files requiring manual review:")
print(fallback_files[['filename', 'frame_rate', 'fps_detection_method']])

# These files may have:
# - Old codecs without PTS data
# - Corrupted video streams
# - Non-standard timing
# → Recommend manual frame rate verification
```

### Log Output Example

```log
INFO: Detecting frame rates using method: pts_timing
INFO: PTS-based FPS: 29.970 fps (sampled 29 intervals, avg=0.033367s, detection time: 1.23s)
INFO: Processing camera1.mp4 with fps=29.970 (method: pts_timing)

WARNING: camera2.mp4: Could not parse PTS times from frames. Video may use old codec without PTS data or file is damaged. Falling back to container metadata.
WARNING: PTS calculation failed, falling back to metadata FPS: 25.0
INFO: Processing camera2.mp4 with fps=25.000 (method: metadata) (FALLBACK: PTS failed)
```

---

## FAQ for Implementation

**Q: Why 30 frame samples?**
A: Balance between accuracy and speed. 30 samples = 1 second of video at 30fps = statistically reliable.

**Q: What if PTS starts at boot time (71723s)?**  
A: Doesn't matter! We calculate **intervals** (delta between frames), not absolute PTS values.

**Q: Performance impact?**  
A: Metadata: instant. PTS: ~2s per file (FFprobe reads 30 frames). Acceptable for accuracy.

**Q: Does this support VFR?**  
A: Partially. PTS method calculates **average** FPS. True VFR support requires frame-by-frame scheduling (future enhancement).

**Q: Backward compatibility?**  
A: 100%. Metadata remains default. Existing workflows unchanged.

**Q: What if both methods fail?**
A: Falls back to FrameRateService.DEFAULT_FRAME_RATE (29.97).

**Q: Why track fallbacks separately from detection method?**
A: Forensic transparency. `fps_detection_method="metadata"` could mean:
1. User explicitly chose metadata method (normal)
2. PTS method failed and fell back (requires attention)

The `fps_fallback_occurred` flag distinguishes these cases for audit purposes.

**Q: How do I identify problematic files in a batch?**
A: Filter CSV by `fps_fallback_occurred=true`. These files had PTS detection failures and may need manual frame rate verification.

---

## Success Criteria

✅ **User can select detection method from dropdown**  
✅ **PTS method calculates FPS from frame timing**  
✅ **Fallback to metadata if PTS fails**  
✅ **CSV export shows detection method used**  
✅ **Performance: PTS method completes within 2s per file**  
✅ **Backward compatible: metadata remains default**  
✅ **No regressions in existing workflows**

---

## Next Steps

**Immediate Actions**:
1. Execute Phase 1 code changes (VideoMetadataExtractor)
2. Execute Phase 2 service updates (FrameRateService)
3. Execute Phase 3 model changes (FilenameParserSettings)
4. Execute Phase 4 UI controls (FilenameParserTab)
5. Execute Phase 5 integration (BatchProcessorService)
6. Run manual tests from checklist

**Post-Implementation**:
1. Create test video files with known FPS mismatches
2. Run batch processing tests (100+ files)
3. Verify timeline rendering accuracy
4. Document findings in user guide

---

## Conclusion

This implementation adds **forensic-grade frame rate detection** to the Filename Parser feature, solving the critical CCTV DVR metadata problem. The PTS-based method calculates TRUE frame rates from video timing, ensuring accurate playback and timeline synchronization.

**Key Benefits**:
- ✅ Solves DVR FPS misreporting (25fps stamped on 12fps files)
- ✅ User-selectable (experts can choose PTS, novices use metadata)
- ✅ Graceful fallbacks (never fails completely)
- ✅ Backward compatible (no workflow disruption)
- ✅ Performance optimized (parallel processing maintained)

**Implementation Time**: 6-8 hours for experienced developer (including testing and edge case handling)

**Risk**: Low (fallback behavior ensures no regressions, backward compatible)

**Impact**: High (fixes critical forensic accuracy issue for DVR/CCTV workflows)

---

## Performance Characteristics

### Expected Processing Times

**Metadata Method (Default)**:
- Single file: <100ms
- 100 files (parallel, 4 workers): ~2-3 seconds
- 500 files (parallel, 4 workers): ~10-15 seconds

**PTS Timing Method**:
- Single file: ~1-2 seconds (FFprobe samples 30 frames)
- 100 files (parallel, 4 workers): ~50 seconds
- 500 files (parallel, 4 workers): ~250 seconds (4.2 minutes)

**Performance Notes**:
- PTS method is ~10-20x slower than metadata
- Acceptable trade-off for forensic accuracy
- Parallel processing maintained across all methods
- Large datasets benefit from 4-worker parallelism

### Batch Processing Recommendations

**Small Datasets (<50 files)**:
- Either method acceptable
- PTS method completes in <30 seconds

**Medium Datasets (50-200 files)**:
- Metadata: Near-instant (<10s)
- PTS: ~60-120 seconds (acceptable for forensic work)

**Large Datasets (>200 files)**:
- Consider metadata method for initial scan
- Use PTS method for problematic files only
- Or use PTS method overnight for batch processing

---

**Ready to execute? Start with Phase 1, VideoMetadataExtractor changes. Good luck! 🚀**
