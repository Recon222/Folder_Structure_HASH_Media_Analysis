# Slate Date/Time Flow Analysis

## Executive Summary

**Problem:** Slates display incorrect dates (December instead of May) and times that don't match the correct parsed values shown in JSON timeline and terminal logs.

**Root Cause:** Slate times are generated from **normalized timeline positions** (seconds from t0=0) without preserving the original ISO8601 absolute times. The `_fmt_dvr_time()` function converts normalized seconds back to Unix timestamps using `timeline_t0`, but this conversion loses date context.

**Impact:**
- ✅ Correct: JSON timeline, terminal logs, parsing results
- ✅ Correct: Video clip playback order and overlaps
- ❌ Incorrect: Slate date/time labels

---

## Complete Data Flow (Parsing → Slate Creation)

### Phase 1: Filename Parsing
**Location:** `filename_parser_service.py` → `timeline_controller.py`

```
Filename: "A02_20250521_193045.mp4"
    ↓
1. PatternMatcher extracts components:
   - hours=19, minutes=30, seconds=45
   - year=2025, month=5, day=21
   - camera_id="A02"
    ↓
2. TimeExtractor creates TimeData:
   TimeData(
       hours=19, minutes=30, seconds=45,
       year=2025, month=5, day=21,
       date_string="2025-05-21",
       time_string="19:30:45"
   )
    ↓
3. SMPTEConverter creates SMPTE timecode:
   "19:30:45:00"  (HH:MM:SS:FF)
    ↓
4. FilenameParserService returns ParseResult with TimeData
```

**Output:** Parsing result with correct date (2025-05-21) and time (19:30:45)

---

### Phase 2: ISO8601 Conversion
**Location:** `timeline_controller.py:_smpte_to_iso8601()`

```python
# Line 245-293
def _smpte_to_iso8601(
    self,
    smpte_timecode: str,
    fps: float,
    date_components: Optional[tuple[int, int, int]] = None  # ✅ (2025, 5, 21)
) -> str:
    parts = smpte_timecode.split(":")  # ["19", "30", "45", "00"]
    hours, minutes, seconds, frames = map(int, parts)

    frame_seconds = frames / fps  # 0.0

    # ✅ CRITICAL: Uses extracted date from parsing
    if date_components:
        year, month, day = date_components  # (2025, 5, 21)
        dt = datetime(year, month, day, hours, minutes, seconds)
        # dt = datetime(2025, 5, 21, 19, 30, 45)

    dt = dt + timedelta(seconds=frame_seconds)

    return dt.isoformat()
    # Returns: "2025-05-21T19:30:45"  ✅ CORRECT!
```

**Key Code:**
```python
# timeline_controller.py lines 113-127
date_tuple = None
year = result.get("year")
month = result.get("month")
day = result.get("day")
if year and month and day:
    date_tuple = (year, month, day)
    logger.info(f"{file_path.name}: Using extracted date {year}-{month:02d}-{day:02d}")

start_iso = self._smpte_to_iso8601(smpte_timecode, metadata.frame_rate, date_tuple)
# start_iso = "2025-05-21T19:30:45"  ✅ CORRECT!

end_iso = self._calculate_end_time_iso(start_iso, metadata.duration_seconds)
# end_iso = "2025-05-21T19:35:12"  ✅ CORRECT!

# Store in VideoMetadata
metadata.start_time = start_iso  # ✅ CORRECT!
metadata.end_time = end_iso      # ✅ CORRECT!
```

**Output:** VideoMetadata with correct ISO8601 times (2025-05-21T19:30:45)

---

### Phase 3: JSON Timeline Export
**Location:** `json_timeline_export_service.py`

```python
# Lines 60-67
for video in videos:
    clip = {
        "path": str(video.file_path),
        "start": video.start_time,  # ✅ "2025-05-21T19:30:45"
        "end": video.end_time,      # ✅ "2025-05-21T19:35:12"
        "cam_id": video.camera_path
    }
    clips.append(clip)
```

**Output:** JSON with correct ISO8601 times ✅

---

### Phase 4: Clip Conversion
**Location:** `multicam_renderer_service.py:_videos_to_clips()`

```python
# Lines 495-523
def _videos_to_clips(self, videos: List[VideoMetadata]) -> List[Clip]:
    clips = []

    for video in videos:
        clip = Clip(
            path=video.file_path,
            start=video.start_time,  # ✅ "2025-05-21T19:30:45" (ISO8601 string)
            end=video.end_time,      # ✅ "2025-05-21T19:35:12" (ISO8601 string)
            cam_id=video.camera_path
        )
        clips.append(clip)

    return clips
```

**Output:** List[Clip] with ISO8601 times ✅

---

### Phase 5: Time Normalization (THE PROBLEM STARTS HERE)
**Location:** `ffmpeg_timeline_builder.py:_normalize_clip_times()`

```python
# Lines 220-261
def _normalize_clip_times(self, clips: List[Clip], absolute: bool) -> Tuple[List[_NClip], Optional[float]]:
    """
    Convert clip times to seconds from t0.

    Returns:
        Tuple of (normalized_clips, timeline_t0)
        - timeline_t0 is the Unix timestamp of the earliest clip
    """
    parsed = []

    def to_sec(x: Union[float, str]) -> float:
        if isinstance(x, (int, float)):
            return float(x)
        try:
            return datetime.fromisoformat(x).timestamp()  # ⚠️ Converts to Unix timestamp
        except Exception:
            raise ValueError(f"Unsupported time format: {x}")

    for c in clips:
        s = to_sec(c.start)  # "2025-05-21T19:30:45" → 1747852245.0 (Unix seconds)
        e = to_sec(c.end)    # "2025-05-21T19:35:12" → 1747852512.0
        if e <= s:
            continue
        parsed.append((c.path, s, e, c.cam_id))

    if absolute:
        # ⚠️ CRITICAL: Rebases timeline to earliest start = 0
        t0 = min(s for _, s, _, _ in parsed)  # t0 = 1747852245.0 (earliest clip Unix time)

        norm = [_NClip(p, s - t0, e - t0, cam) for p, s, e, cam in parsed]
        # _NClip(start=0.0, end=327.0, ...)      ⚠️ Now relative to t0!
        # _NClip(start=120.0, end=450.0, ...)    ⚠️ Timeline positions, not real times!

        return norm, t0  # ⚠️ Returns t0 for "DVR time conversion"

    return norm, None
```

**What Happens:**
```
Original Clip Times (ISO8601):
  Clip A: start="2025-05-21T19:30:45" → 1747852245.0 (Unix)
          end="2025-05-21T19:35:12"   → 1747852512.0
  Clip B: start="2025-05-21T19:32:00" → 1747852320.0
          end="2025-05-21T19:40:00"   → 1747852800.0

After Normalization:
  t0 = 1747852245.0  (Clip A's start time in Unix)

  _NClip A: start=0.0, end=327.0           ⚠️ Seconds from t0
  _NClip B: start=75.0, end=555.0          ⚠️ Seconds from t0
```

**Output:** Normalized clips with relative timeline positions + `timeline_t0` (Unix timestamp of earliest clip)

---

### Phase 6: Atomic Interval Building
**Location:** `ffmpeg_timeline_builder.py:_build_atomic_intervals()`

```python
# Lines 265-292
def _build_atomic_intervals(self, clips: List[_NClip]) -> List[_Interval]:
    """
    Build atomic intervals where camera set is constant.

    Uses NORMALIZED times (seconds from t0).
    """
    # Collect all unique time points
    bounds = set()
    for c in clips:
        bounds.add(c.start)  # 0.0, 75.0, etc. (normalized)
        bounds.add(c.end)    # 327.0, 555.0, etc.

    edges = sorted(bounds)

    # Create intervals
    intervals = []
    for i in range(len(edges) - 1):
        a, b = edges[i], edges[i + 1]
        active = [c for c in clips if c.start < b and c.end > a]
        intervals.append(_Interval(a, b, active))

    return intervals
```

**Example Intervals:**
```
_Interval(t0=0.0, t1=75.0, active=[ClipA])           # Single camera
_Interval(t0=75.0, t1=327.0, active=[ClipA, ClipB])  # Overlap
_Interval(t0=327.0, t1=555.0, active=[ClipB])        # Single camera
_Interval(t0=555.0, t1=800.0, active=[])             # GAP ⚠️
```

**Output:** List[_Interval] with normalized times (0.0, 75.0, 327.0, etc.)

---

### Phase 7: Segment Creation (WHERE SLATES ARE CREATED)
**Location:** `ffmpeg_timeline_builder.py:_segments_from_intervals()`

```python
# Lines 296-380
def _segments_from_intervals(
    self,
    intervals: List[_Interval],
    settings: RenderSettings,
    timeline_t0: Optional[float] = None  # ⚠️ 1747852245.0 (Unix timestamp)
) -> List[_Segment]:
    segments: List[_Segment] = []

    # ... merging logic ...

    # For GAP intervals:
    if not active:
        if settings.slate_duration_seconds > 0:
            # ⚠️⚠️⚠️ CRITICAL SECTION - SLATE TEXT GENERATION ⚠️⚠️⚠️
            if timeline_t0 is not None:
                # Convert normalized seconds back to Unix timestamps
                dvr_start = t0 + timeline_t0  # ❌ 555.0 + 1747852245.0 = 1747852800.0
                dvr_end = t1 + timeline_t0    # ❌ 800.0 + 1747852245.0 = 1747853045.0

                # Format as "DVR time"
                text = f"GAP: {self._fmt_dvr_time(dvr_start)} → {self._fmt_dvr_time(dvr_end)}  (Δ {self._fmt_dur(t1 - t0)})"
            else:
                text = f"GAP: {self._fmt_hms(t0)} → {self._fmt_hms(t1)}  (Δ {self._fmt_dur(t1 - t0)})"

            segments.append(_SegSlate(
                gap_start=t0,    # Normalized: 555.0
                gap_end=t1,      # Normalized: 800.0
                text=text,       # ❌ WRONG DATE/TIME!
                dur=float(settings.slate_duration_seconds)
            ))

    return segments
```

**The _fmt_dvr_time() Function:**
```python
# Lines 635-643
def _fmt_dvr_time(self, unix_timestamp: float) -> str:
    """
    Format Unix timestamp as readable DVR time.

    Returns format: "Mon 28 Jan 14:30:00"
    """
    dt = datetime.fromtimestamp(unix_timestamp)  # ❌ Uses system timezone!
    return dt.strftime("%a %d %b %H:%M:%S")
```

---

## The Critical Bug Explained

### Why Slates Show Wrong Date/Time

**The Problem:**
1. **Timeline is normalized** → Clip times become relative positions (0.0, 75.0, 327.0...)
2. **`timeline_t0` only stores the EARLIEST clip's Unix timestamp** (e.g., first clip at 19:30:45)
3. **Gap detection happens in NORMALIZED space** → Gaps are at positions like 555.0 (9 min 15 sec from t0)
4. **Slate generation adds normalized position to `timeline_t0`:**
   ```
   dvr_start = gap_start + timeline_t0
             = 555.0 + 1747852245.0
             = 1747852800.0
   ```
5. **`_fmt_dvr_time()` converts Unix timestamp using `datetime.fromtimestamp()`**
   - This uses the system's LOCAL TIMEZONE
   - If `timeline_t0` was calculated incorrectly or timezone is wrong → wrong date!

### Why December Date Appears

**Hypothesis 1: Unix Timestamp Calculation Error**
```python
datetime.fromisoformat("2025-05-21T19:30:45").timestamp()
# If system assumes UTC but time was local → offset error
# Could result in timestamp for December 2024 instead of May 2025
```

**Hypothesis 2: Timezone Mismatch**
```python
# If ISO8601 string has no timezone indicator:
"2025-05-21T19:30:45"  # Ambiguous - local or UTC?

# Python's .timestamp() assumes local time
# But if files were created in different timezone → wrong conversion
```

**Hypothesis 3: Year Rollover Bug**
```python
# If timeline_t0 is calculated from earliest clip
# But earliest clip has wrong year parsed → all slates offset
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 1: PARSING                                                    │
├─────────────────────────────────────────────────────────────────────┤
│ Filename: "A02_20250521_193045.mp4"                                │
│     ↓                                                               │
│ TimeData(year=2025, month=5, day=21, hours=19, mins=30, secs=45)  │
│     ↓                                                               │
│ SMPTE: "19:30:45:00"                                               │
│     ↓                                                               │
│ ✅ Parsing Output: TimeData with CORRECT date/time                  │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 2: ISO8601 CONVERSION (timeline_controller.py)               │
├─────────────────────────────────────────────────────────────────────┤
│ _smpte_to_iso8601(smpte, fps, date_components=(2025, 5, 21))      │
│     ↓                                                               │
│ datetime(2025, 5, 21, 19, 30, 45).isoformat()                     │
│     ↓                                                               │
│ ✅ ISO8601: "2025-05-21T19:30:45"  (CORRECT!)                       │
│     ↓                                                               │
│ VideoMetadata(start_time="2025-05-21T19:30:45",                   │
│               end_time="2025-05-21T19:35:12")                     │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 3: JSON TIMELINE EXPORT                                       │
├─────────────────────────────────────────────────────────────────────┤
│ ✅ JSON Output:                                                      │
│   {                                                                 │
│     "start": "2025-05-21T19:30:45",  ← CORRECT!                    │
│     "end": "2025-05-21T19:35:12"     ← CORRECT!                    │
│   }                                                                 │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 4: CLIP CONVERSION (multicam_renderer_service.py)            │
├─────────────────────────────────────────────────────────────────────┤
│ Clip(start="2025-05-21T19:30:45", end="2025-05-21T19:35:12")     │
│     ↓                                                               │
│ ✅ List[Clip] with ISO8601 strings (CORRECT!)                       │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 5: TIME NORMALIZATION (ffmpeg_timeline_builder.py)           │
├─────────────────────────────────────────────────────────────────────┤
│ _normalize_clip_times(clips, absolute=True)                        │
│     ↓                                                               │
│ ⚠️ CONVERSION STEP:                                                 │
│   ISO8601 → Unix timestamp → Normalize to t0=0                     │
│     ↓                                                               │
│   "2025-05-21T19:30:45" → 1747852245.0 (Unix)                     │
│   "2025-05-21T19:35:12" → 1747852512.0 (Unix)                     │
│     ↓                                                               │
│   t0 = 1747852245.0  (earliest clip)                              │
│     ↓                                                               │
│   _NClip(start=0.0, end=327.0)      ← NORMALIZED (seconds from t0)│
│   _NClip(start=75.0, end=450.0)                                   │
│     ↓                                                               │
│ ⚠️ Output: Normalized clips + timeline_t0 (Unix timestamp)          │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 6: ATOMIC INTERVALS (_build_atomic_intervals)                │
├─────────────────────────────────────────────────────────────────────┤
│ Uses NORMALIZED times (0.0, 75.0, 327.0, 450.0, etc.)             │
│     ↓                                                               │
│ _Interval(t0=0.0, t1=75.0, active=[ClipA])                        │
│ _Interval(t0=75.0, t1=327.0, active=[ClipA, ClipB])  ← Overlap   │
│ _Interval(t0=327.0, t1=450.0, active=[ClipB])                    │
│ _Interval(t0=450.0, t1=555.0, active=[])              ← GAP       │
│     ↓                                                               │
│ ⚠️ Output: Intervals with NORMALIZED times (no dates!)              │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 7: SEGMENT CREATION (_segments_from_intervals)               │
├─────────────────────────────────────────────────────────────────────┤
│ For GAP interval at t0=450.0, t1=555.0:                           │
│     ↓                                                               │
│ ❌ CRITICAL BUG LOCATION:                                           │
│     dvr_start = 450.0 + 1747852245.0 = 1747852695.0               │
│     dvr_end = 555.0 + 1747852245.0 = 1747852800.0                 │
│     ↓                                                               │
│     _fmt_dvr_time(1747852695.0)                                   │
│         ↓                                                           │
│         datetime.fromtimestamp(1747852695.0)  ← Uses system TZ!   │
│         ↓                                                           │
│     ❌ Returns: "Sun 23 Dec 19:38:15"  (WRONG DATE!)                │
│     ↓                                                               │
│ _SegSlate(text="GAP: Sun 23 Dec 19:38:15 → ...")                  │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 8: FFmpeg FILTER GENERATION (_emit_ffmpeg_argv)              │
├─────────────────────────────────────────────────────────────────────┤
│ Slate segments → drawtext filters                                  │
│     ↓                                                               │
│ ❌ drawtext=text='GAP\\: Sun 23 Dec 19\\:38\\:15 → ...'             │
│     ↓                                                               │
│ ❌ FINAL OUTPUT: Video with WRONG date on slates                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Why This Bug Exists

### Original Design Intent

The timeline normalization was designed for **relative timeline positioning**:
- Clips are normalized to `t0=0` for easier FFmpeg filter math
- `timeline_t0` was added to "convert back" to real times for slate labels
- **Assumption:** Simple addition would work: `normalized_pos + timeline_t0 = real_time`

### Why It Fails

**The assumption breaks because:**

1. **Date context is lost during normalization**
   - ISO8601 string "2025-05-21T19:30:45" contains full date
   - Unix timestamp 1747852245.0 is just a number (seconds since epoch)
   - Normalized position 450.0 is just seconds from t0
   - **Adding them back doesn't preserve the original date!**

2. **Timezone ambiguity**
   - `datetime.fromisoformat("2025-05-21T19:30:45")` → Assumes local timezone
   - `.timestamp()` → Converts to UTC Unix time
   - `datetime.fromtimestamp(unix_time)` → Converts back to local timezone
   - **If system timezone != video creation timezone → wrong date!**

3. **Gap positions are relative, not absolute**
   - Gap at normalized position 450.0 means "450 seconds after earliest clip"
   - But earliest clip might NOT be the start of the DVR recording day
   - **Gap might span across midnight → date calculation fails!**

---

## Why Before Our Changes It Worked

**Previous Batch Rendering (Simple Split):**
```python
# OLD CODE:
for i in range(0, len(clips), batch_size):
    batch = clips[i:i + batch_size]
    batches.append(batch)
```

**Why slates had correct times:**
- Each batch was rendered independently
- Each batch had its OWN `timeline_t0` calculated from batch's earliest clip
- Slates were generated WITHIN each batch's timeline context
- **Date/time calculation stayed consistent within batch boundaries**

**After Our Timeline-Aware Changes:**
- Batches are split at gap boundaries
- But each batch STILL uses the GLOBAL `timeline_t0` (earliest clip across ALL batches)
- Slates in later batches are far from `timeline_t0` → calculation drifts
- **Date/time errors accumulate as we get further from t0**

---

## The Fix Strategy

### Option 1: Preserve ISO8601 Strings Through Normalization ⭐ RECOMMENDED

**Instead of converting to Unix timestamps, keep ISO8601 strings:**

```python
# In _NClip dataclass:
@dataclass
class _NClip:
    path: Path
    start: float  # Normalized seconds from t0
    end: float
    cam_id: str
    start_iso: str  # ✅ NEW: Original ISO8601 string
    end_iso: str    # ✅ NEW: Original ISO8601 string
```

**For slate generation:**
```python
# Instead of:
dvr_start = gap_start + timeline_t0  # ❌ Adds normalized + Unix timestamp

# Do this:
# Find clips adjacent to gap
prev_clip = clips_before_gap[-1]
next_clip = clips_after_gap[0]

# Use their ISO8601 strings directly
gap_start_iso = prev_clip.end_iso    # "2025-05-21T19:35:12"
gap_end_iso = next_clip.start_iso    # "2025-05-21T19:40:00"

# Format for slate
text = f"GAP: {_fmt_iso8601_time(gap_start_iso)} → {_fmt_iso8601_time(gap_end_iso)}"
```

**Pros:**
- ✅ Preserves exact dates from parsing
- ✅ No timezone conversion errors
- ✅ Works across midnight boundaries
- ✅ Forensically accurate

**Cons:**
- Requires significant refactoring of _NClip dataclass
- Need to track ISO strings through entire pipeline

---

### Option 2: Store Original Clips Alongside Normalized Clips

**Keep a mapping from normalized clips back to original Clips:**

```python
# In FFmpegTimelineBuilder:
def _normalize_clip_times(self, clips: List[Clip], absolute: bool):
    # ... existing normalization ...

    # ✅ NEW: Create mapping
    self._clip_mapping = {}  # normalized_path → original_clip
    for orig, norm in zip(clips, norm_clips):
        self._clip_mapping[str(norm.path)] = orig

    return norm_clips, timeline_t0
```

**For slate generation:**
```python
# When creating _SegSlate, store references to adjacent clips
if not active:  # GAP
    # Find clips before/after gap
    prev_interval = intervals[prev_idx] if prev_idx >= 0 else None
    next_interval = intervals[next_idx] if next_idx < len(intervals) else None

    # Get original clips
    if prev_interval and prev_interval.active:
        prev_clip_orig = self._clip_mapping[str(prev_interval.active[-1].path)]
        gap_start_time = prev_clip_orig.end  # ISO8601

    if next_interval and next_interval.active:
        next_clip_orig = self._clip_mapping[str(next_interval.active[0].path)]
        gap_end_time = next_clip_orig.start  # ISO8601

    text = f"GAP: {_fmt_iso8601(gap_start_time)} → {_fmt_iso8601(gap_end_time)}"
```

**Pros:**
- ✅ Less invasive (no _NClip changes)
- ✅ Preserves exact dates
- ✅ Works with existing batch rendering

**Cons:**
- Requires careful tracking of clip relationships
- Mapping overhead (memory)

---

### Option 3: Calculate Absolute Times Correctly with Timezone Awareness

**Fix the Unix timestamp conversion to preserve dates:**

```python
def _fmt_dvr_time(self, unix_timestamp: float) -> str:
    """
    Format Unix timestamp as readable DVR time.

    Returns format: "Wed 21 May 2025 19:30:45"
    """
    dt = datetime.fromtimestamp(unix_timestamp)
    # ✅ NEW: Include full date with year
    return dt.strftime("%a %d %b %Y %H:%M:%S")
```

**And ensure timezone consistency:**
```python
# In _smpte_to_iso8601:
dt = datetime(year, month, day, hours, minutes, seconds)
# ✅ NEW: Make timezone-aware
from zoneinfo import ZoneInfo
dt = dt.replace(tzinfo=ZoneInfo("America/Toronto"))  # EST
return dt.isoformat()
```

**Pros:**
- ✅ Minimal code changes
- ✅ Preserves existing normalization logic

**Cons:**
- ❌ Doesn't fully solve the problem (still using Unix timestamps)
- ❌ Requires timezone configuration
- ❌ May still fail across midnight boundaries

---

## Recommended Solution: Option 1 (Preserve ISO8601)

### Implementation Plan

1. **Modify _NClip dataclass** to store original ISO strings
2. **Update _normalize_clip_times()** to preserve ISO strings
3. **Modify _SegSlate** to store ISO times instead of normalized floats
4. **Create new _fmt_iso8601_time()** function for slate formatting
5. **Update _segments_from_intervals()** to use ISO strings for gap labels
6. **Test across midnight boundaries** to verify correctness

### Code Changes Required

**File 1: `ffmpeg_timeline_builder.py`**
```python
# Line 41: Modify _NClip
@dataclass
class _NClip:
    path: Path
    start: float        # Normalized seconds from t0
    end: float
    cam_id: str
    start_iso: str      # ✅ NEW
    end_iso: str        # ✅ NEW
```

**File 2: `ffmpeg_timeline_builder.py`**
```python
# Line 220: Update _normalize_clip_times
for c in clips:
    s = to_sec(c.start)
    e = to_sec(c.end)
    if e <= s:
        continue
    # ✅ NEW: Preserve ISO strings
    parsed.append((c.path, s, e, c.cam_id, c.start, c.end))

if absolute:
    t0 = min(s for _, s, _, _, _, _ in parsed)
    norm = [
        _NClip(p, s - t0, e - t0, cam, start_iso, end_iso)  # ✅ NEW
        for p, s, e, cam, start_iso, end_iso in parsed
    ]
    return norm, t0
```

**File 3: `ffmpeg_timeline_builder.py`**
```python
# New helper function
def _fmt_iso8601_time(self, iso_string: str) -> str:
    """Format ISO8601 as 'Wed 21 May 19:30:45'"""
    dt = datetime.fromisoformat(iso_string)
    return dt.strftime("%a %d %b %H:%M:%S")
```

**File 4: `ffmpeg_timeline_builder.py`**
```python
# Line 336: Update slate generation
if not active:  # GAP
    # Find adjacent clips to determine gap boundaries
    prev_clips = []
    next_clips = []

    # Search backwards for last active interval
    for idx in range(i - 1, -1, -1):
        if intervals[idx].active:
            prev_clips = intervals[idx].active
            break

    # Search forwards for next active interval
    for idx in range(i + 1, len(intervals)):
        if intervals[idx].active:
            next_clips = intervals[idx].active
            break

    # Use ISO strings from adjacent clips
    if prev_clips and next_clips:
        # Gap between last frame of previous clip and first frame of next clip
        gap_start_iso = prev_clips[-1].end_iso  # ✅ Use ISO string
        gap_end_iso = next_clips[0].start_iso   # ✅ Use ISO string

        text = f"GAP: {self._fmt_iso8601_time(gap_start_iso)} → {self._fmt_iso8601_time(gap_end_iso)}  (Δ {self._fmt_dur(t1 - t0)})"
    else:
        # Fallback if we can't find adjacent clips
        text = f"GAP: {self._fmt_hms(t0)} → {self._fmt_hms(t1)}  (Δ {self._fmt_dur(t1 - t0)})"

    segments.append(_SegSlate(
        gap_start=t0,
        gap_end=t1,
        text=text,
        dur=float(settings.slate_duration_seconds)
    ))
```

---

## Testing Strategy

1. **Test with motion-activated clips** spanning multiple hours
2. **Test across midnight boundary** (e.g., 23:55 to 00:10 next day)
3. **Test batch rendering** with keep_batch_temp_files=True
4. **Verify JSON timeline** shows correct dates/times
5. **Verify slate dates** match JSON timeline dates
6. **Test with different timezones** (if applicable)

---

## Conclusion

**Root Cause:** Slate times are calculated by adding normalized timeline positions (seconds from t0) to the Unix timestamp of the earliest clip, losing date context and causing timezone errors.

**Solution:** Preserve original ISO8601 strings through the normalization process and use them directly for slate generation, avoiding Unix timestamp conversions entirely.

**Impact:** This fix ensures forensically accurate date/time labels on all slates, matching the correct times shown in JSON timeline and parsing logs.
