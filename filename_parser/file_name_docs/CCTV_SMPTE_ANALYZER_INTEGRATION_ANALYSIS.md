# CCTV SMPTE Analyzer Integration Analysis

## Executive Summary

**Purpose:** Integrate frame-accurate SMPTE timecode calculation from `cctv_smpte_analyzer.py` into the existing timeline rendering pipeline to achieve sub-second precision for CCTV motion-activated clips.

**Key Benefits:**
- ✅ **Frame-accurate start times** - Accounts for I-frame alignment and PTS offsets
- ✅ **Precise end times** - Calculates from first_frame_pts + duration (not just duration)
- ✅ **Better overlap synchronization** - Tighter alignment when cameras trigger simultaneously
- ✅ **Forensic accuracy** - Sub-second precision for evidence-grade timelines

**Current State:**
- ❌ Start time based solely on filename timestamp (accurate to second only)
- ❌ End time calculated as `start_time + duration` (ignores frame offset)
- ❌ Overlaps can be slightly misaligned (visible when side-by-side)

**Target State:**
- ✅ Start time with frame-level offset (e.g., "14:23:00:10" = 14:23:00 + 10 frames)
- ✅ End time calculated from `first_frame_pts + duration` for precision
- ✅ Overlaps perfectly synchronized frame-to-frame

---

## Deep Dive: cctv_smpte_analyzer.py

### Core Algorithm

The `CCTVSMPTEAnalyzer` class implements a **meta-algorithm** combining GPT and Perplexity approaches for frame-accurate timecode calculation WITHOUT OCR dependency.

### Key Methods

#### 1. **parse_start_time()**
**Purpose:** Extract timestamp from filename (accurate to second)

```python
# Supports multiple CCTV filename formats
patterns = [
    (r'(\d{8})_(\d{6})', "%Y%m%d_%H%M%S"),           # 20251009_142300
    (r'(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})',...)  # 2025-10-09_14-23-00
]

# Returns datetime object
return datetime.datetime(2025, 10, 9, 14, 23, 0)  # Accurate to SECOND only
```

**Assessment:**
- ✅ **Keep:** Already implemented in our codebase via pattern matching
- ✅ **Benefit:** Handles multiple formats
- ⚠️ **Limitation:** Only gives whole-second accuracy (e.g., 14:23:00)

---

#### 2. **extract_video_metadata()**
**Purpose:** Get PTS (Presentation Timestamp) data from first 100 frames using FFprobe

```python
# Extract both stream and frame data
cmd = [
    ffprobe, "-v", "error",
    "-show_streams",    # Stream metadata (codec, fps, duration)
    "-show_frames",     # Frame-level PTS data
    "-read_intervals", f"%+{frame_limit}",  # First 100 frames only
    "-of", "json"
]

# Returns:
{
    "stream_info": {
        "codec_name": "h264",
        "r_frame_rate": "30000/1001",  # Rational frame rate
        "duration": "30.5"              # Total duration in seconds
    },
    "frames": [
        {
            "pkt_pts_time": "0.333333",  # ⚠️ KEY: Sub-second offset!
            "pict_type": "I",            # Frame type (I/P/B)
            "key_frame": 1               # Is this an I-frame?
        },
        # ... more frames
    ]
}
```

**Assessment:**
- ✅ **CRITICAL VALUE:** `pkt_pts_time` of first frame = sub-second offset
- ✅ **Example:** If `pkt_pts_time = 0.333333` at 30fps → frame 10 of second
- ✅ **Keep:** This is the MISSING PIECE in our current implementation
- ❌ **Drop:** We don't need 100 frames - just first frame PTS is enough

**Why PTS Matters:**

```
Filename says: "Cam1_20251009_142300.mp4" → 14:23:00
But video starts at frame 10 of that second!

Current calculation:
  start_time = 14:23:00 (from filename)
  ❌ WRONG - Video doesn't start at frame 0!

Correct calculation (with PTS):
  start_time = 14:23:00 + first_frame_pts (0.333333s)
            = 14:23:00.333333
            = 14:23:00:10 in SMPTE @ 30fps
  ✅ CORRECT - Accounts for I-frame alignment!
```

---

#### 3. **calculate_frame_rate()**
**Purpose:** Calculate FPS from PTS intervals (detects VFR)

```python
# Calculate intervals between consecutive frames
intervals = []
for i in range(1, min(len(frames), 50)):
    t_prev = float(frames[i-1]["pkt_pts_time"])
    t_curr = float(frames[i]["pkt_pts_time"])
    delta = t_curr - t_prev
    if delta > 0:
        intervals.append(delta)

# Average FPS
avg_interval = sum(intervals) / len(intervals)
fps = 1.0 / avg_interval

# Detect variable frame rate
variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
is_variable = variance > (0.001 * avg_interval)  # VFR if >0.1% variance
```

**Assessment:**
- ✅ **Keep:** More accurate than stream metadata alone
- ✅ **Detects VFR:** Important for forensic accuracy
- ⚠️ **Our current code:** Uses `r_frame_rate` (constant FPS assumed)
- ✅ **Benefit:** Statistical FPS calculation catches encoding anomalies

---

#### 4. **analyze_gop_structure()**
**Purpose:** Validate GOP consistency (I-frame pattern)

```python
# Find all I-frames (keyframes)
i_frame_indices = []
for idx, frame in enumerate(frames):
    if frame.get("pict_type") == "I" and frame.get("key_frame") == 1:
        i_frame_indices.append(idx)

# Calculate GOP lengths
gop_lengths = []
for j in range(1, len(i_frame_indices)):
    gop_lengths.append(i_frame_indices[j] - i_frame_indices[j-1])

# Check consistency
gop_consistent = (len(set(gop_lengths)) <= 1)  # All GOPs same length?

# Create pattern visualization
gop_pattern = "".join([frame.get("pict_type", "?") for frame in frames[:50]])
# Example: "IPPPPPPPPPPPIPPPPPPPPPPP..." (GOP=12 for h264)
```

**Assessment:**
- ❌ **Drop for core workflow:** GOP analysis is nice-to-have, not required
- ✅ **Keep for reliability scoring:** Helps detect edited/corrupted files
- ⚠️ **Current code:** We don't analyze GOP at all
- 💡 **Use case:** Add to CSV export as diagnostic column

**Why GOP Matters for Forensics:**
- **Closed GOP** (starts with I-frame): Video can be decoded from start ✅
- **Open GOP** (starts with P/B-frame): Video depends on previous footage ⚠️
- **Inconsistent GOP**: Possible editing or corruption 🚩

---

#### 5. **detect_timing_anomalies()**
**Purpose:** Find frame timing irregularities (dropped frames, glitches)

```python
expected_duration = 1.0 / fps  # e.g., 0.033333s at 30fps

for i in range(1, len(pts_list)):
    interval = pts_list[i] - pts_list[i-1]
    deviation = abs(interval - expected_duration)

    if deviation > (expected_duration * 0.02):  # 2% threshold
        anomalies.append(
            f"Timing irregularity between frames {i-1}-{i}: "
            f"interval={interval:.6f}s (expected {expected_duration:.6f}s)"
        )
```

**Assessment:**
- ✅ **Keep for diagnostics:** Detects dropped frames and encoding issues
- ❌ **Not required for timeline:** Don't block on anomalies
- 💡 **Use case:** Log warnings for user review
- ✅ **Example:** "Frame 15-16: gap of 0.067s (expected 0.033s) - possible dropped frame"

---

#### 6. **compute_timecodes()** ⭐ CRITICAL
**Purpose:** Convert filename timestamp + PTS offset → SMPTE timecode

```python
def compute_timecodes(
    self,
    start_dt: datetime.datetime,  # From filename: 2025-10-09 14:23:00
    pts_offset: float,             # From first frame: 0.333333s
    fps: float                     # Frame rate: 30.0
) -> Tuple[str, float, float]:
    # Convert datetime to seconds since midnight
    base_seconds = (
        start_dt.hour * 3600 +     # 14 * 3600 = 50400
        start_dt.minute * 60 +     # 23 * 60 = 1380
        start_dt.second            # 0
    )  # = 51780 seconds

    # Add PTS offset for precise start
    precise_start = base_seconds + pts_offset  # 51780 + 0.333333 = 51780.333333

    # Extract SMPTE components
    hours = int(precise_start // 3600) % 24        # 14
    minutes = int((precise_start % 3600) // 60)    # 23
    seconds = int(precise_start % 60)              # 0

    # Calculate frame number within current second
    fractional = precise_start - int(precise_start)  # 0.333333
    frame_number = int(round(fractional * fps))      # round(0.333333 * 30) = 10

    # Handle frame wrapping (frame 30 at 30fps → next second)
    if frame_number >= int(round(fps)):
        frame_number = 0
        seconds += 1
        # ... handle minute/hour wrapping

    # Format SMPTE timecode
    timecode = f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frame_number:02d}"
    # Returns: "14:23:00:10"

    return timecode, pts_offset, pts_offset * fps
```

**Assessment:**
- ✅ ⭐ **KEEP THIS ENTIRE METHOD** - Core algorithm we need!
- ✅ **Benefits:**
  - Frame-accurate start time (not just whole seconds)
  - Handles frame wrapping correctly
  - Returns both SMPTE string and numeric offsets
- ⚠️ **Current code:** We do `datetime(year, month, day, hours, mins, secs).isoformat()`
  - This gives "14:23:00" (no frame offset!)
  - Missing the critical `+ pts_offset` step

**End Time Calculation (From Analyzer):**

```python
# Calculate end timecode from duration
duration = float(stream_info.get("duration", 0))  # Total video duration

if duration > 0:
    end_pts = first_frame_pts + duration  # ✅ CRITICAL: Add to PTS, not datetime!
    end_tc, _, _ = self.compute_timecodes(start_dt, end_pts, fps)
    # Returns end timecode accounting for start offset
```

**vs. Current Code:**

```python
# Current (timeline_controller.py):
start_iso = self._smpte_to_iso8601(smpte, fps, date_tuple)
# "2025-10-09T14:23:00"  ❌ No PTS offset!

end_iso = self._calculate_end_time_iso(start_iso, duration)
# start_dt + timedelta(seconds=duration)
# ❌ WRONG: Assumes start is at frame 0, but it's actually frame 10!
```

**Correct Calculation:**

```
Video actual times:
  First frame PTS: 0.333333s (frame 10 @ 30fps)
  Duration: 30.5s (from FFprobe)

Current calculation:
  start = 14:23:00 (filename)
  end = 14:23:00 + 30.5s = 14:23:30.5  ❌ WRONG

Correct calculation:
  start = 14:23:00 + 0.333333s = 14:23:00.333 (frame 10)
  end = 14:23:00 + 0.333333 + 30.5 = 14:23:30.833  ✅ CORRECT

Difference: 0.333s misalignment!
  At 30fps, this is 10 frames of error - very visible in overlaps!
```

---

#### 7. **calculate_reliability_score()**
**Purpose:** Quality assessment (0-100 score)

**Scoring Factors:**
1. **Closed GOP** (25 pts): First frame is I-frame → can decode from start
2. **Constant Frame Rate** (25 pts): No VFR detected
3. **Consistent GOP** (25 pts): All GOPs same length
4. **Sufficient I-frames** (25 pts): At least 2 keyframes found

**Assessment:**
- ✅ **Keep for diagnostics:** Helpful for user confidence
- ❌ **Don't block on low scores:** Motion cameras may have open GOP
- 💡 **Use case:** Add to CSV as `reliability_score` column
- ⚠️ **Our workflow:** Currently no quality scoring

---

## What to Keep vs. Drop

### ✅ KEEP (Essential for Frame Accuracy)

| Component | Why Keep | Integration Priority |
|-----------|----------|---------------------|
| **First frame PTS extraction** | ⭐ Critical for sub-second start time | HIGH |
| **compute_timecodes()** | ⭐ Core algorithm for SMPTE with frame offset | HIGH |
| **End time = first_pts + duration** | ⭐ Fixes misalignment in overlaps | HIGH |
| **PTS-based FPS calculation** | More accurate than stream metadata | MEDIUM |
| **VFR detection** | Important for forensic validation | MEDIUM |
| **Timing anomaly detection** | Diagnostic logging for dropped frames | LOW |
| **GOP analysis** | Forensic quality validation | LOW |
| **Reliability scoring** | User confidence metric | LOW |

### ❌ DROP (Not Needed)

| Component | Why Drop |
|-----------|----------|
| **100-frame analysis** | Only need first frame PTS (massive speedup) |
| **GOP pattern visualization** | Nice-to-have, not required for timeline |
| **Filename pattern matching** | Already have comprehensive pattern library |
| **Error handling boilerplate** | Our codebase has unified Result objects |

---

## Integration Strategy

### Current Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ CURRENT WORKFLOW (Whole-Second Accuracy)                   │
├─────────────────────────────────────────────────────────────┤
│ 1. Filename parsing → TimeData(hours, mins, secs)         │
│    "A02_20251009_142300.mp4" → (14, 23, 0)                │
│                                                             │
│ 2. SMPTE conversion → "14:23:00:00"                        │
│    ❌ Assumes start at frame 0!                             │
│                                                             │
│ 3. ISO8601 conversion → "2025-10-09T14:23:00"             │
│    datetime(year, month, day, 14, 23, 0).isoformat()      │
│                                                             │
│ 4. Duration extraction → 30.5s (FFprobe)                   │
│                                                             │
│ 5. End time calculation:                                   │
│    end = start + timedelta(seconds=30.5)                  │
│    = "2025-10-09T14:23:30.5"                              │
│    ❌ WRONG: Doesn't account for start frame offset!       │
└─────────────────────────────────────────────────────────────┘
```

### Proposed Enhanced Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ ENHANCED WORKFLOW (Frame-Accurate)                         │
├─────────────────────────────────────────────────────────────┤
│ 1. Filename parsing → TimeData(hours, mins, secs, date)   │
│    "A02_20251009_142300.mp4" → (14, 23, 0) + (2025,10,9) │
│                                                             │
│ 2. ✅ NEW: FFprobe first frame PTS extraction              │
│    → first_frame_pts = 0.333333s                          │
│    → fps = 30.0 (PTS-derived)                             │
│    → duration = 30.5s                                      │
│                                                             │
│ 3. ✅ NEW: Frame-accurate SMPTE calculation                │
│    base_smpte = "14:23:00:00" (from filename)             │
│    frame_offset = round(0.333333 * 30) = 10 frames        │
│    start_smpte = "14:23:00:10"  ✅ CORRECT!               │
│                                                             │
│ 4. ✅ NEW: Frame-accurate ISO8601 conversion               │
│    start_iso = "2025-10-09T14:23:00.333333"              │
│    (datetime + timedelta(seconds=first_frame_pts))        │
│                                                             │
│ 5. ✅ CORRECTED: End time from first_pts + duration        │
│    end_pts = 0.333333 + 30.5 = 30.833333                 │
│    end_iso = "2025-10-09T14:23:30.833333"  ✅ CORRECT!    │
└─────────────────────────────────────────────────────────────┘
```

---

## Code Integration Points

### 1. **VideoMetadataExtractor** (NEW: Add PTS Extraction)

**File:** `filename_parser/services/video_metadata_extractor.py`

**Current:** Extracts duration, fps, resolution from stream metadata

**Enhancement:** Add first frame PTS extraction

```python
# In extract_metadata() method:
def extract_metadata(self, file_path: Path) -> VideoProbeData:
    # ... existing stream extraction ...

    # ✅ NEW: Extract first frame PTS for frame-accurate start time
    first_frame_pts = self._extract_first_frame_pts(file_path)

    return VideoProbeData(
        # ... existing fields ...
        first_frame_pts=first_frame_pts,  # ✅ NEW FIELD
        # ... rest ...
    )

def _extract_first_frame_pts(self, file_path: Path) -> float:
    """
    Extract PTS (Presentation Timestamp) of first frame.

    This gives sub-second offset for frame-accurate start time.

    Returns:
        First frame PTS in seconds (e.g., 0.333333 for frame 10 @ 30fps)
    """
    ffprobe_path = binary_manager.get_ffprobe_path()
    if not ffprobe_path:
        return 0.0

    try:
        cmd = [
            ffprobe_path,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_frames",
            "-read_intervals", "%+#1",  # ✅ ONLY FIRST FRAME (fast!)
            "-of", "json",
            str(file_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        data = json.loads(result.stdout)
        frames = data.get("frames", [])

        if frames:
            # Get PTS of first frame
            pts_time = frames[0].get("pkt_pts_time")
            if pts_time is not None:
                return float(pts_time)

        return 0.0  # Fallback if no PTS

    except Exception as e:
        self.logger.warning(f"Could not extract first frame PTS: {e}")
        return 0.0
```

**Why This Works:**
- `-read_intervals "%+#1"` = Read ONLY first frame (fast!)
- No need for 100 frames like analyzer does
- `pkt_pts_time` already in seconds (no math needed)

---

### 2. **VideoProbeData** (NEW: Add PTS Field)

**File:** `filename_parser/services/video_metadata_extractor.py`

**Enhancement:** Add PTS field to dataclass

```python
@dataclass
class VideoProbeData:
    """Complete video metadata from ffprobe."""

    # ... existing fields ...

    # ✅ NEW: Frame-accurate timing
    first_frame_pts: float = 0.0  # Sub-second offset of first frame

    # ✅ NEW: Optional diagnostic fields
    first_frame_type: Optional[str] = None  # "I", "P", or "B"
    first_frame_is_keyframe: bool = False   # True if I-frame
    frame_rate_variance: Optional[float] = None  # VFR detection
```

---

### 3. **TimelineController** (MODIFY: Use PTS in ISO8601 Conversion)

**File:** `filename_parser/controllers/timeline_controller.py`

**Current:** `_smpte_to_iso8601()` converts SMPTE to ISO without PTS

**Enhancement:** Add PTS offset to datetime calculation

```python
def _smpte_to_iso8601(
    self,
    smpte_timecode: str,
    fps: float,
    date_components: Optional[tuple[int, int, int]] = None,
    first_frame_pts: float = 0.0  # ✅ NEW PARAMETER
) -> str:
    """
    Convert SMPTE timecode to ISO8601 with frame-accurate offset.

    Args:
        smpte_timecode: SMPTE format (HH:MM:SS:FF)
        fps: Frame rate
        date_components: (year, month, day) from filename
        first_frame_pts: Sub-second offset of first frame (NEW!)

    Returns:
        ISO8601 string with frame-accurate timestamp
    """
    try:
        parts = smpte_timecode.split(":")
        hours, minutes, seconds, frames = map(int, parts)

        # Create base datetime
        if date_components:
            year, month, day = date_components
            dt = datetime(year, month, day, hours, minutes, seconds)
        else:
            # Fallback to system date
            today = datetime.now().date()
            dt = datetime.combine(today, datetime.min.time())
            dt = dt.replace(hour=hours, minute=minutes, second=seconds)

        # ✅ NEW: Add first frame PTS offset for frame accuracy
        dt = dt + timedelta(seconds=first_frame_pts)

        return dt.isoformat()

    except Exception as e:
        logger.warning(f"Error converting SMPTE: {e}")
        return smpte_timecode
```

**Call Site Update:**

```python
# In validate_videos() method (line 122):
# OLD:
start_iso = self._smpte_to_iso8601(smpte_timecode, metadata.frame_rate, date_tuple)

# ✅ NEW:
start_iso = self._smpte_to_iso8601(
    smpte_timecode,
    metadata.frame_rate,
    date_tuple,
    first_frame_pts=metadata.first_frame_pts  # Use PTS from probe!
)
```

---

### 4. **End Time Calculation** (FIX: Account for Start Offset)

**File:** `filename_parser/controllers/timeline_controller.py`

**Current Issue:**

```python
# Current code (line 123):
end_iso = self._calculate_end_time_iso(start_iso, metadata.duration_seconds)

def _calculate_end_time_iso(self, start_iso: str, duration_seconds: float) -> str:
    start_dt = datetime.fromisoformat(start_iso)
    end_dt = start_dt + timedelta(seconds=duration_seconds)
    return end_dt.isoformat()
```

**This is ALREADY CORRECT if `start_iso` includes PTS offset!**

```
Example:
  start_iso = "2025-10-09T14:23:00.333333"  ← Already has PTS offset
  duration = 30.5

  end = start_dt + timedelta(seconds=30.5)
      = datetime.fromisoformat("2025-10-09T14:23:00.333333") + 30.5s
      = "2025-10-09T14:23:30.833333"  ✅ CORRECT!
```

**No changes needed!** Just ensure `start_iso` from step 3 includes PTS.

---

### 5. **VideoMetadata Model** (ADD: New Fields)

**File:** `filename_parser/models/timeline_models.py`

**Enhancement:** Add PTS and diagnostic fields

```python
@dataclass
class VideoMetadata:
    """Video metadata for timeline rendering."""

    # ... existing fields ...

    # ✅ NEW: Frame-accurate timing fields
    first_frame_pts: float = 0.0              # Sub-second offset
    first_frame_type: Optional[str] = None    # "I", "P", or "B"
    first_frame_is_keyframe: bool = False     # Closed GOP indicator

    # ✅ NEW: Quality/diagnostic fields
    frame_rate_variance: Optional[float] = None  # VFR detection
    timing_anomalies: int = 0                     # Count of frame timing issues
    reliability_score: Optional[int] = None       # 0-100 quality score
    gop_consistent: bool = True                   # GOP structure validation
```

---

### 6. **CSV Export** (ADD: New Columns)

**File:** `filename_parser/services/csv_export_service.py`

**Enhancement:** Add frame-accurate timing columns

```python
# In export_results() method:
if include_metadata:
    fieldnames = [
        # ... existing columns ...

        # ✅ NEW: Frame-accurate timing columns
        "first_frame_pts",            # Sub-second offset (e.g., 0.333333)
        "start_frame_number",         # Frame within second (e.g., 10)
        "first_frame_type",           # I/P/B frame type
        "first_frame_is_keyframe",    # True/False

        # ✅ NEW: Quality/diagnostic columns
        "frame_rate_variance",        # VFR detection
        "reliability_score",          # 0-100 quality score
        "gop_consistent",             # GOP validation
        "timing_anomalies_count",     # Number of frame timing issues
    ]

    # ... in row construction ...
    row.update({
        # ✅ NEW: Frame-accurate timing
        "first_frame_pts": f"{result.get('first_frame_pts', 0.0):.6f}",
        "start_frame_number": int(round(result.get('first_frame_pts', 0.0) * result.get('frame_rate', 30.0))),
        "first_frame_type": result.get('first_frame_type', 'N/A'),
        "first_frame_is_keyframe": result.get('first_frame_is_keyframe', False),

        # ✅ NEW: Quality metrics
        "frame_rate_variance": f"{result.get('frame_rate_variance', 0.0):.8f}" if result.get('frame_rate_variance') else "N/A",
        "reliability_score": result.get('reliability_score', 'N/A'),
        "gop_consistent": result.get('gop_consistent', True),
        "timing_anomalies_count": result.get('timing_anomalies', 0),
    })
```

---

## End Time Math Verification

### Analyzer's End Time Calculation

```python
# cctv_smpte_analyzer.py lines 659-669
duration = float(stream_info.get("duration", 0))  # 30.5s

if duration > 0:
    # ✅ CRITICAL: Add duration to first_frame_pts, NOT to datetime!
    end_pts = first_frame_pts + duration  # 0.333333 + 30.5 = 30.833333

    # Then convert PTS to timecode using same base datetime
    end_tc, _, _ = self.compute_timecodes(start_dt, end_pts, fps)
    # compute_timecodes(datetime(2025,10,9,14,23,0), 30.833333, 30.0)
    # Returns: "14:23:30:25" (30s + 25 frames @ 30fps)
```

### Our Current Calculation

```python
# timeline_controller.py lines 122-123
start_iso = self._smpte_to_iso8601(smpte, fps, date_tuple)
# Returns: "2025-10-09T14:23:00" ❌ Missing PTS offset!

end_iso = self._calculate_end_time_iso(start_iso, duration)
# Returns: "2025-10-09T14:23:30.5"

# Problem:
# If video starts at frame 10 (0.333s offset), but we calculate from 00:00,
# the end time is 0.333s too early!
```

### Corrected Calculation (After Integration)

```python
# With PTS integration:
start_iso = self._smpte_to_iso8601(smpte, fps, date_tuple, first_frame_pts=0.333333)
# Returns: "2025-10-09T14:23:00.333333" ✅ Includes PTS!

end_iso = self._calculate_end_time_iso(start_iso, duration)
# datetime.fromisoformat("2025-10-09T14:23:00.333333") + 30.5s
# Returns: "2025-10-09T14:23:30.833333" ✅ CORRECT!

# Verification:
# Start: 14:23:00.333 (frame 10)
# +Duration: 30.5s
# End: 14:23:30.833 (frame 25 of second 30)
# ✅ Math matches analyzer's approach!
```

**Conclusion:** Our end time calculation is **ALREADY CORRECT** - we just need to fix the start time to include PTS offset. The existing `_calculate_end_time_iso()` method doesn't need any changes.

---

## Implementation Roadmap

### Phase 1: Core PTS Integration (HIGH Priority)

**Estimated Time:** 2-3 hours

**Tasks:**
1. ✅ Add `first_frame_pts` field to `VideoProbeData` dataclass
2. ✅ Implement `_extract_first_frame_pts()` in `VideoMetadataExtractor`
3. ✅ Add `first_frame_pts` parameter to `_smpte_to_iso8601()`
4. ✅ Update call site in `validate_videos()` to pass PTS
5. ✅ Test with sample CCTV files

**Expected Result:**
- Frame-accurate start times (to the frame)
- Frame-accurate end times (automatically corrected)
- Better overlap synchronization

---

### Phase 2: Enhanced Metadata (MEDIUM Priority)

**Estimated Time:** 1-2 hours

**Tasks:**
1. ✅ Add diagnostic fields to `VideoProbeData` (frame type, keyframe flag)
2. ✅ Implement optional GOP analysis (closed vs open GOP)
3. ✅ Add frame rate variance calculation (VFR detection)
4. ✅ Update `VideoMetadata` model with new fields

**Expected Result:**
- Forensic quality validation
- VFR detection warnings
- Better user confidence in timeline accuracy

---

### Phase 3: CSV Export Enhancement (LOW Priority)

**Estimated Time:** 30 mins

**Tasks:**
1. ✅ Add new columns to CSV export
2. ✅ Update fieldnames list in `CSVExportService`
3. ✅ Populate new columns from result dictionaries

**Expected Result:**
- Comprehensive CSV with frame-accurate timing data
- Diagnostic columns for forensic review

---

### Phase 4: Testing & Validation

**Test Cases:**

1. **Single Camera, Closed GOP**
   - File: `Cam1_20251009_142300.mp4`
   - Expected: `first_frame_pts ≈ 0.0` (starts on I-frame)
   - Verify: Start SMPTE matches frame 0 or close to it

2. **Single Camera, Open GOP**
   - File: `Cam2_20251009_142305.mp4`
   - Expected: `first_frame_pts > 0.0` (starts mid-GOP)
   - Verify: Start SMPTE shows frame offset (e.g., :10)

3. **Two Cameras, Simultaneous Trigger**
   - Files: `Cam1_20251009_142300.mp4`, `Cam2_20251009_142300.mp4`
   - Both filename timestamps: 14:23:00
   - Expected: Different `first_frame_pts` values
   - Verify: Overlap timeline shows frame-accurate sync

4. **Variable Frame Rate Detection**
   - File: Motion-activated clip with VFR encoding
   - Expected: `frame_rate_variance > 0.001`
   - Verify: Warning logged about VFR

5. **Cross-Midnight Boundary**
   - File: `Cam1_20251009_235959.mp4`
   - Duration: 5 seconds
   - Expected: End time wraps to next day correctly

---

## Performance Impact

### Current Performance

```
Per-file metadata extraction: ~50-100ms
  - Stream metadata (FFprobe): ~40ms
  - Duration/FPS parsing: ~10ms
```

### After PTS Integration

```
Per-file metadata extraction: ~60-120ms (+10-20ms)
  - Stream metadata: ~40ms
  - First frame PTS extraction: ~20ms  ← NEW (single frame only!)
  - Duration/FPS parsing: ~10ms

Batch processing 336 files:
  - Current: 336 * 80ms = ~27s
  - Enhanced: 336 * 90ms = ~30s (+3s = 11% increase)

✅ ACCEPTABLE: Frame accuracy worth 11% performance cost
```

**Optimization:**
- Only extract first frame (not 100 like analyzer)
- Parallel processing already in place
- No blocking on slow I/O

---

## Risks & Mitigation

### Risk 1: PTS Not Available

**Scenario:** Some video formats don't have PTS in first frame

**Mitigation:**
```python
first_frame_pts = self._extract_first_frame_pts(file_path)
if first_frame_pts is None or first_frame_pts == 0.0:
    # Fallback to whole-second accuracy (current behavior)
    logger.warning(f"No PTS found for {file_path.name}, using whole-second timing")
    first_frame_pts = 0.0  # No offset
```

**Impact:** Graceful degradation to current behavior

---

### Risk 2: Corrupt Video Files

**Scenario:** FFprobe fails to extract frame data

**Mitigation:**
- Timeout after 5 seconds
- Catch all exceptions
- Return `0.0` as safe default
- Log warning for user review

**Impact:** No blocking errors, timeline still builds

---

### Risk 3: VFR Causing Drift

**Scenario:** Variable frame rate makes end time calculation inaccurate

**Mitigation:**
- Detect VFR via variance calculation
- Log warning in CSV export
- Add `reliability_score` to indicate confidence
- User can review flagged files manually

**Impact:** User aware of potential issues

---

## Summary & Recommendations

### ✅ What We're Adopting from Analyzer

1. **First frame PTS extraction** → Sub-second start time accuracy
2. **compute_timecodes() algorithm** → Frame-accurate SMPTE conversion
3. **PTS + duration end time** → Proper overlap synchronization
4. **VFR detection** → Forensic quality validation
5. **Reliability scoring** → User confidence metrics

### ❌ What We're Dropping

1. **100-frame analysis** → Only need first frame (performance)
2. **GOP pattern visualization** → Not required for timeline
3. **Complex error handling** → Use our Result objects
4. **Duplicate filename parsing** → Already have pattern library

### 🎯 Expected Improvements

**Before Integration:**
- Start time: 14:23:00 (whole second)
- End time: 14:23:30.5 (from duration)
- Overlap sync: ±1 second alignment
- Reliability: Unknown

**After Integration:**
- Start time: 14:23:00:10 (frame 10 @ 30fps) ✅
- End time: 14:23:30:25 (frame 25) ✅
- Overlap sync: Frame-perfect alignment ✅
- Reliability: 100/100 score (closed GOP, CFR) ✅

### 📊 New CSV Columns Summary

| Column Name | Type | Description | Forensic Value |
|------------|------|-------------|----------------|
| `first_frame_pts` | float | Sub-second offset (e.g., 0.333333) | Frame-accurate start time |
| `start_frame_number` | int | Frame within second (e.g., 10) | Quick visual reference |
| `first_frame_type` | str | "I", "P", or "B" | GOP analysis |
| `first_frame_is_keyframe` | bool | Closed vs open GOP | Decode validation |
| `frame_rate_variance` | float | VFR detection (e.g., 0.00001) | Encoding quality |
| `reliability_score` | int | 0-100 confidence score | Overall quality |
| `gop_consistent` | bool | Uniform GOP structure | Edit detection |
| `timing_anomalies_count` | int | Dropped frame count | Corruption detection |

---

## Next Steps

1. **Review this document** with user for approval
2. **Implement Phase 1** (PTS integration) - Core functionality
3. **Test with 336-clip dataset** to verify frame accuracy
4. **Implement Phase 2** (diagnostics) if desired
5. **Update slate generation** to use ISO8601 strings (separate task)

**Priority Order:**
1. Fix slate date/time issue (from previous analysis)
2. Integrate PTS for frame accuracy (this document)
3. Test full pipeline with real CCTV footage
4. Add CSV columns for forensic analysis
