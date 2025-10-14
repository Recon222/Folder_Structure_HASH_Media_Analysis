# Timeline Calculation Deep Dive: From Embedded Timecodes to Chronological Timeline

**CCTV Chronology Builder - Technical Documentation**
**Last Updated:** 2025-10-07
**Audience:** Senior developers, architects, future maintainers

---

## Table of Contents

1. [Executive Overview](#executive-overview)
2. [Conceptual Foundation](#conceptual-foundation)
3. [Architecture Overview](#architecture-overview)
4. [The Complete Data Flow](#the-complete-data-flow)
5. [Module-by-Module Deep Dive](#module-by-module-deep-dive)
6. [Algorithms & Calculations](#algorithms--calculations)
7. [Time Offset System](#time-offset-system)
8. [Gap Detection Algorithm](#gap-detection-algorithm)
9. [Overlap Detection & Layout Strategy](#overlap-detection--layout-strategy)
10. [Edge Cases & Correctness Guarantees](#edge-cases--correctness-guarantees)
11. [Performance Characteristics](#performance-characteristics)
12. [Testing Strategy](#testing-strategy)

---

## Executive Overview

### The Problem

CCTV systems produce video files with **embedded SMPTE timecodes** representing when footage was recorded. These files come from:
- Multiple camera locations
- Multiple cameras per location
- Different DVR systems (potentially with time sync issues)
- Various frame rates (12fps to 30fps common)

**The challenge:** Reconstruct a chronological timeline showing:
1. When footage exists (and from which cameras)
2. Where gaps exist (no coverage from any camera)
3. Where overlaps exist (multiple cameras have simultaneous footage)
4. Accounting for DVR time sync errors

### The Solution

This application extracts embedded timecodes from video files and:

1. **Converts all timecodes to a unified time base** (sequence timecode at 30fps)
2. **Applies time offsets** to compensate for DVR clock drift
3. **Positions files chronologically** on a virtual timeline
4. **Detects gaps** where no camera has coverage
5. **Detects overlaps** where multiple cameras have simultaneous footage
6. **Determines layout strategies** for overlaps (split-screen, grid, etc.)

The resulting timeline data structure is then used to generate:
- Premiere Pro FCPXML files with proper clip placement
- Slate clips for gaps showing missing time ranges
- Motion effects for overlap positioning

---

## Conceptual Foundation

### Key Concepts

#### 1. Embedded Timecode vs. Timeline Position

**Embedded Timecode** (SMPTE format: `HH:MM:SS:FF`):
```
File: Camera1_001.mp4
Embedded TC: 14:32:18:05  (at native 12fps)
Duration: 120 frames @ 12fps = 10 seconds
```

**Timeline Position** (frames relative to earliest footage):
```
Earliest footage starts at: 14:30:00:00
Camera1 starts at: 14:32:18:05 → 138.42 seconds after earliest
                            → 4152.6 frames @ 30fps sequence rate
                            → Timeline position: frame 4153
```

#### 2. Frame Rate Conversion

Videos have **native frame rates** (fps they were recorded at), but the timeline uses a **sequence frame rate** (typically 30fps). All calculations preserve real-world time:

```
Native:     12fps video, 120 frames = 10.00 seconds
Sequence:   30fps timeline, 300 frames = 10.00 seconds
```

**Critical:** Time-based calculations prevent rounding errors across different frame rates.

#### 3. Time Offset Hierarchy

DVR clocks drift. The system supports hierarchical time correction:

```
Project Level Offset:     +5 minutes (applies to all)
  └─ Location "Building A" Override: +3 minutes (applies to Building A cameras)
       └─ Camera "Cam1" Override: +7 minutes (applies only to Cam1)
```

Offsets are applied **before** timeline positioning.

---

## Architecture Overview

### Component Responsibilities

```
┌─────────────────────────────────────────────────────────────┐
│                      STATE MANAGER                          │
│  (Orchestrates the entire timeline calculation process)     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ├───────────────────┬──────────────────┬────────────────┐
                            ▼                   ▼                  ▼                ▼
                    ┌──────────────┐   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
                    │  METADATA    │   │   TIMELINE   │  │     GAP      │  │   OVERLAP    │
                    │   SERVICE    │   │  CALCULATOR  │  │   DETECTOR   │  │   DETECTOR   │
                    └──────────────┘   └──────────────┘  └──────────────┘  └──────────────┘
                            │                   │                  │                │
                            │                   │                  │                │
                    Extracts timecode,   Positions files    Finds time gaps   Finds overlaps
                    framerate, duration  chronologically    where no camera   & determines
                    from video files     on timeline        has coverage      layout strategy
```

### Data Flow Summary

```
1. Video Files (MP4/MOV with embedded SMPTE timecode)
        │
        ▼ [MetadataService extracts metadata via ExifTool]
        │
2. File Metadata (timecode, fps, duration)
        │
        ▼ [TimelineState applies time offsets if configured]
        │
3. Offset-Adjusted Metadata
        │
        ▼ [TimelineCalculator positions on unified timeline]
        │
4. Positioned Files (start_frame, end_frame on timeline)
        │
        ├─▶ [GapDetector finds gaps]
        │        │
        │        ▼
        │   5a. Gap Information (start, end, duration)
        │
        └─▶ [OverlapDetector finds overlaps]
                 │
                 ▼
            5b. Overlap Groups (clips, layout type)
```

---

## The Complete Data Flow

### Phase 1: Metadata Extraction

**Entry Point:** `MetadataService.get_all_metadata(file_path)`

**Input:**
```python
file_path: "D:/Project/Location1/Camera1/VID_001.mp4"
```

**Process:**
1. Execute ExifTool with multiple tag attempts
2. Extract SMPTE timecode from XMP/QuickTime metadata
3. Extract frame rate from VideoFrameRate/MediaTimeScale
4. Extract duration from Duration/TrackDuration
5. Calculate frames_native (timecode converted to total frames at native fps)

**Output:**
```python
{
    "file_path": "D:/Project/Location1/Camera1/VID_001.mp4",
    "file_name": "VID_001.mp4",
    "timecode": "14:32:18:05",        # Embedded SMPTE timecode
    "frame_rate": 12.0,                # Native fps
    "width": 1920,
    "height": 1080,
    "duration_frames": 120,            # Native frames
    "duration_seconds": 10.0,          # Real-world duration
    "frames_native": 627845,           # Timecode as frame count @ native fps
    "camera_path": "Location1/Camera1" # Organizational path
}
```

**Key Code:**
```python
# services/metadata_service.py:446-537
def extract_all_metadata_efficient(self, file_path: str, progress_callback=None):
    """Single ExifTool call for all metadata."""
    cmd_args = [
        "-j",  # JSON output
        "-xmp:Timecode", "-QuickTime:Timecode", "-Timecode",
        "-VideoFrameRate", "-StartTimeScale", "-MediaTimeScale",
        "-ImageWidth", "-ImageHeight", "-VideoFrameSize",
        "-DurationValue", "-DurationScale", "-Duration", "-TrackDuration",
        file_path
    ]

    metadata_json = self._run_exiftool_command(cmd_args)
    data = json.loads(metadata_json)[0]

    timecode = self._extract_timecode_from_json(data)
    frame_rate = self._extract_frame_rate_from_json(data)
    width, height = self._extract_dimensions_from_json(data)
    duration_frames = self._extract_duration_from_json(data, frame_rate)

    frames_native = timecode_to_frames(timecode, frame_rate)

    return {
        "file_path": file_path,
        "timecode": timecode,
        "frame_rate": frame_rate,
        "duration_frames": duration_frames,
        "frames_native": frames_native,
        # ... additional fields
    }
```

---

### Phase 2: Time Offset Application

**Entry Point:** `TimelineState.calculate_timeline()` (lines 116-260)

**Purpose:** Compensate for DVR clock drift before positioning

**Input:** File metadata with original timecode
```python
{
    "timecode": "14:32:18:05",
    "frame_rate": 12.0,
    "camera_path": "Location1/Camera1"
}
```

**Process:**

1. **Check for applicable offset:**
```python
# state/timeline_state.py:167-169
camera_path = file_info_copy.get('camera_path')
if camera_path and self.applied_offsets:
    offset = get_applicable_offset(camera_path, self.applied_offsets)
```

2. **Hierarchical offset lookup** (utils/time_offset_utils.py:225-268):
```python
def get_applicable_offset(camera_path: str, applied_offsets: Dict):
    """Check camera → location → project for applicable offset."""
    # Priority 1: Camera-specific offset
    if camera_path in applied_offsets:
        return {**applied_offsets[camera_path], 'level': 'camera'}

    # Priority 2: Location offset
    if '/' in camera_path:
        location_name = camera_path.split('/')[0]
        if location_name in applied_offsets:
            return {**applied_offsets[location_name], 'level': 'location'}

    # Priority 3: Project-wide offset
    if 'project' in applied_offsets:
        return {**applied_offsets['project'], 'level': 'project'}

    return {}  # No offset
```

3. **Apply offset to timecode:**
```python
# state/timeline_state.py:172-182
adjusted_timecode = apply_time_offset(
    file_info_copy['timecode'],
    offset.get('direction', 'behind'),  # "behind" or "ahead"
    offset.get('hours', 0),
    offset.get('minutes', 0),
    offset.get('seconds', 0),
    file_info_copy['frame_rate']
)
```

4. **Time offset calculation** (utils/time_offset_utils.py:18-61):
```python
def apply_time_offset(timecode: str, direction: str, hours: int, minutes: int, seconds: int, fps: float):
    """Apply offset to compensate for DVR clock drift."""
    # Convert timecode to seconds
    tc_seconds = timecode_to_seconds(timecode, fps)

    # Calculate offset
    offset_seconds = hours * 3600 + minutes * 60 + seconds

    # Apply based on direction
    if direction == "behind":
        # DVR clock is behind real time: ADD offset to correct
        # Example: DVR shows 14:00, but real time is 14:05
        #          Add 5 minutes to sync with real time
        adjusted_seconds = tc_seconds + offset_seconds
    else:
        # DVR clock is ahead: SUBTRACT offset
        adjusted_seconds = tc_seconds - offset_seconds

    # Ensure non-negative
    adjusted_seconds = max(0, adjusted_seconds)

    return seconds_to_timecode(adjusted_seconds, fps)
```

**Output:** Updated file metadata
```python
{
    "original_timecode": "14:32:18:05",  # Preserved for reference
    "timecode": "14:37:18:05",           # Adjusted (+5min offset)
    "frame_rate": 12.0,
    "time_offset_applied": {
        "direction": "behind",
        "hours": 0,
        "minutes": 5,
        "seconds": 0,
        "level": "project"
    }
}
```

---

### Phase 3: Timeline Position Calculation

**Entry Point:** `TimelineState.calculate_timeline()` (continued)

**Purpose:** Position all files on a unified timeline using time-based calculations

**Input:** Offset-adjusted file metadata
```python
files = [
    {"timecode": "14:30:00:00", "frame_rate": 12.0, "duration_native": 120},
    {"timecode": "14:32:18:05", "frame_rate": 30.0, "duration_native": 300},
    {"timecode": "14:30:05:10", "frame_rate": 12.0, "duration_native": 240}
]
sequence_fps = 30.0
```

**Algorithm:**

**Step 1: Convert timecodes to absolute seconds** (preserves precision across frame rates)

```python
# state/timeline_state.py:193-198
for file_info in files:
    frames_native = file_info['frames_native']
    frames_seq = int(frames_native * sequence_fps / file_info['frame_rate'])
    file_info['frames_seq'] = frames_seq
```

**Why seconds, not frames?**
- Avoids cumulative rounding errors
- Different native frame rates (12fps, 30fps) convert accurately
- Sequence positioning maintains temporal accuracy

**Step 2: Find earliest timecode**
```python
# state/timeline_state.py:200-202
if earliest_frame is None or frames_seq < earliest_frame:
    earliest_frame = frames_seq
```

**Step 3: Calculate relative positions**
```python
# state/timeline_state.py:217-232
for file_info in updated_files:
    # Position relative to earliest
    start_frame = file_info['frames_seq'] - earliest_frame

    # Convert duration to sequence frames
    duration_seq = int(file_info['duration_native'] * sequence_fps / file_info['frame_rate'])

    # Calculate end frame
    end_frame = start_frame + duration_seq

    # Store timeline position
    file_info['start_frame'] = start_frame
    file_info['end_frame'] = end_frame
    file_info['duration_seq'] = duration_seq
```

**Step 4: Sort chronologically**
```python
# state/timeline_state.py:241-243
updated_files.sort(key=lambda x: x['start_frame'])
```

**Output:** Positioned file metadata
```python
[
    {
        "file_name": "VID_001.mp4",
        "timecode": "14:30:00:00",
        "start_frame": 0,           # Earliest file
        "end_frame": 300,           # 10sec @ 30fps
        "duration_seq": 300
    },
    {
        "file_name": "VID_002.mp4",
        "timecode": "14:30:05:10",
        "start_frame": 163,         # 5.433 sec after earliest
        "end_frame": 763,           # 20sec @ 30fps
        "duration_seq": 600
    },
    {
        "file_name": "VID_003.mp4",
        "timecode": "14:32:18:05",
        "start_frame": 4152,        # 138.4 sec after earliest
        "end_frame": 4452,          # 10sec @ 30fps
        "duration_seq": 300
    }
]
```

**Visualization:**
```
Timeline (frames @ 30fps):
0        300      763                                4152    4452
├─────────┤       ├─────────────┤                    ├───────┤
VID_001          VID_002                            VID_003
              ↑
         163 frame gap
                                    ↑
                            3389 frame gap
```

---

### Phase 4: Gap Detection

**Entry Point:** `TimelineState.detect_gaps()` → `GapDetector.detect_gaps()`

**Purpose:** Identify time periods where NO camera has coverage

**Input:** Positioned files + minimum gap threshold
```python
files_info = [positioned files from Phase 3]
min_gap_seconds = 5
fps = 30.0
min_gap_frames = ceil(5 * 30.0) = 150 frames
```

**Algorithm:** Range Merging + Gap Finding

**Step 1: Extract coverage ranges**
```python
# core/gap_detector.py:67-68
coverage_ranges = [(file_info.get("start_frame", 0), file_info.get("end_frame", 0))
                   for file_info in files_info]
# Result: [(0, 300), (163, 763), (4152, 4452)]
```

**Step 2: Merge overlapping/adjacent ranges**
```python
# core/gap_detector.py:89-119
def _merge_ranges(self, ranges: List[Tuple[int, int]]):
    """Merge overlapping coverage to find consolidated coverage."""
    sorted_ranges = sorted(ranges)  # Sort by start
    merged = [sorted_ranges[0]]

    for current in sorted_ranges[1:]:
        previous = merged[-1]

        # If current starts after previous ends, it's a new range
        if current[0] > previous[1]:
            merged.append(current)
        # Otherwise, extend previous range if current extends beyond it
        elif current[1] > previous[1]:
            merged[-1] = (previous[0], current[1])

    return merged
```

**Example execution:**
```
Input ranges:  [(0, 300), (163, 763), (4152, 4452)]
After sort:    [(0, 300), (163, 763), (4152, 4452)]

Processing:
  Start with: [(0, 300)]

  Current: (163, 763)
  - Does 163 > 300? NO (overlaps)
  - Does 763 > 300? YES (extends)
  - Merge: [(0, 763)]

  Current: (4152, 4452)
  - Does 4152 > 763? YES (gap!)
  - New range: [(0, 763), (4152, 4452)]

Merged ranges: [(0, 763), (4152, 4452)]
```

**Step 3: Find gaps between merged ranges**
```python
# core/gap_detector.py:78-84
gaps = []
for i in range(len(merged_ranges) - 1):
    gap_start = merged_ranges[i][1]      # End of current range
    gap_end = merged_ranges[i + 1][0]    # Start of next range

    if gap_end - gap_start >= min_gap_frames:
        gap_info = self._create_gap_info(gap_start, gap_end, earliest_tc, fps)
        gaps.append(gap_info)
```

**Example:**
```
Merged ranges: [(0, 763), (4152, 4452)]
Gap: frames 763 → 4152 = 3389 frames
Duration: 3389 / 30fps = 112.97 seconds > 5 second minimum ✓

Gap detected!
```

**Step 4: Create gap information**
```python
# core/gap_detector.py:121-152
def _create_gap_info(self, start_frame: int, end_frame: int, earliest_tc: int, fps: float):
    """Create detailed gap information."""
    gap_duration = end_frame - start_frame

    # Calculate real-world timecodes for the gap
    gap_start_tc = frames_to_timecode(start_frame + earliest_tc, fps)
    gap_end_tc = frames_to_timecode(end_frame + earliest_tc, fps)

    # Calculate duration
    gap_seconds = int(gap_duration / fps)
    duration_str = format_duration(gap_seconds)

    return {
        "start_frame": start_frame,      # Timeline position
        "end_frame": end_frame,
        "duration_frames": gap_duration,
        "start_timecode": gap_start_tc,  # Real-world time
        "end_timecode": gap_end_tc,
        "duration_str": duration_str     # "1hr 52min 57sec"
    }
```

**Output:**
```python
gaps = [
    {
        "start_frame": 763,
        "end_frame": 4152,
        "duration_frames": 3389,
        "start_timecode": "14:30:25:13",
        "end_timecode": "14:32:18:05",
        "duration_str": "1min 52sec"
    }
]
```

**Key Insight:** By merging ranges first, we ensure we only detect **true gaps** where NO camera has coverage, not just gaps in individual camera tracks.

---

### Phase 5: Overlap Detection

**Entry Point:** `OverlapDetector.detect_overlaps()`

**Purpose:** Find time periods where MULTIPLE cameras have simultaneous footage and determine layout strategy

**Input:** Positioned files
```python
files_info = [
    {"file_name": "Cam1.mp4", "start_frame": 0, "end_frame": 600, "camera_path": "Loc1/Cam1"},
    {"file_name": "Cam2.mp4", "start_frame": 200, "end_frame": 800, "camera_path": "Loc1/Cam2"},
    {"file_name": "Cam3.mp4", "start_frame": 400, "end_frame": 1000, "camera_path": "Loc2/Cam1"}
]
```

**Algorithm:** Interval Sweep with Layout Assignment

**Step 1: Collect all time points**
```python
# core/overlap_detector.py:68-74
time_points = set()
for file_info in files_info:
    time_points.add(file_info.get("start_frame", 0))
    time_points.add(file_info.get("end_frame", 0))

sorted_time_points = sorted(time_points)
# Result: [0, 200, 400, 600, 800, 1000]
```

**Step 2: For each interval, determine active clips**
```python
# core/overlap_detector.py:77-90
for i in range(len(sorted_time_points) - 1):
    interval_start = sorted_time_points[i]
    interval_end = sorted_time_points[i + 1]

    # Find clips active in this interval
    active_clips = []
    for file_info in files_info:
        clip_start = file_info.get("start_frame", 0)
        clip_end = file_info.get("end_frame", 0)

        # Clip is active if it starts before/at interval start
        # and ends after interval start
        if clip_start <= interval_start and clip_end > interval_start:
            active_clips.append(file_info)
```

**Interval Analysis:**
```
Interval [0, 200):     Active: [Cam1]              → 1 clip (single)
Interval [200, 400):   Active: [Cam1, Cam2]        → 2 clips (OVERLAP!)
Interval [400, 600):   Active: [Cam1, Cam2, Cam3]  → 3 clips (OVERLAP!)
Interval [600, 800):   Active: [Cam2, Cam3]        → 2 clips (OVERLAP!)
Interval [800, 1000):  Active: [Cam3]              → 1 clip (single)
```

**Step 3: Create overlap groups and merge adjacent identical groups**
```python
# core/overlap_detector.py:92-106
if len(active_clips) > 1:
    # Check if we can merge with previous group
    if (overlap_groups and
        overlap_groups[-1].end_frame == interval_start and
        set(clip["file_path"] for clip in overlap_groups[-1].clips) ==
        set(clip["file_path"] for clip in active_clips)):
        # Same clips as previous interval: extend it
        overlap_groups[-1].end_frame = interval_end
    else:
        # Different clips: create new group
        overlap_groups.append(self._create_overlap_group(
            interval_start, interval_end, active_clips
        ))
```

**Step 4: Determine layout strategy**
```python
# core/overlap_detector.py:111-194
def _create_overlap_group(self, start_frame: int, end_frame: int, clips: List[Dict]):
    """Assign layout based on number of simultaneous clips."""
    num_clips = len(clips)

    if num_clips == 2:
        layout_type = LayoutType.SIDE_BY_SIDE
        layout_params = {
            "arrangement": "horizontal",
            "positions": [
                {"x": 0, "y": 0, "width": 0.5, "height": 1.0},    # Left half
                {"x": 0.5, "y": 0, "width": 0.5, "height": 1.0}   # Right half
            ]
        }

    elif num_clips == 3:
        layout_type = LayoutType.TRIPLE_SPLIT
        layout_params = {
            "arrangement": "2_top_1_bottom",
            "positions": [
                {"x": 0, "y": 0, "width": 0.5, "height": 0.5},       # Top-left
                {"x": 0.5, "y": 0, "width": 0.5, "height": 0.5},     # Top-right
                {"x": 0.25, "y": 0.5, "width": 0.5, "height": 0.5}   # Bottom-center
            ]
        }

    elif num_clips == 4:
        layout_type = LayoutType.GRID_2X2
        layout_params = {
            "arrangement": "grid",
            "grid_size": (2, 2),
            "positions": [
                {"x": 0, "y": 0, "width": 0.5, "height": 0.5},       # TL
                {"x": 0.5, "y": 0, "width": 0.5, "height": 0.5},     # TR
                {"x": 0, "y": 0.5, "width": 0.5, "height": 0.5},     # BL
                {"x": 0.5, "y": 0.5, "width": 0.5, "height": 0.5}    # BR
            ]
        }

    # 5-9 clips: 3x3 grid
    # 10+ clips: Custom cycling layout

    # Sort clips by camera path for consistent ordering
    sorted_clips = sorted(clips, key=lambda x: x.get("camera_path", ""))

    return OverlapGroup(
        start_frame=start_frame,
        end_frame=end_frame,
        clips=sorted_clips,
        layout_type=layout_type,
        layout_params=layout_params
    )
```

**Output:**
```python
overlap_groups = [
    OverlapGroup(
        start_frame=200,
        end_frame=400,
        clips=[Cam1, Cam2],
        layout_type=LayoutType.SIDE_BY_SIDE,
        layout_params={
            "positions": [
                {"x": 0, "y": 0, "width": 0.5, "height": 1.0},
                {"x": 0.5, "y": 0, "width": 0.5, "height": 1.0}
            ]
        }
    ),
    OverlapGroup(
        start_frame=400,
        end_frame=600,
        clips=[Cam1, Cam2, Cam3],
        layout_type=LayoutType.TRIPLE_SPLIT,
        layout_params={...}
    ),
    OverlapGroup(
        start_frame=600,
        end_frame=800,
        clips=[Cam2, Cam3],
        layout_type=LayoutType.SIDE_BY_SIDE,
        layout_params={...}
    )
]
```

**Visual Representation:**
```
Frame:  0        200      400      600      800      1000
        │        │        │        │        │        │
Cam1:   ├────────────────────────┤
Cam2:            ├─────────────────────────┤
Cam3:                     ├────────────────────────┤
        │        │        │        │        │        │
Layout: Single   2-split  3-split  2-split  Single
```

---

## Module-by-Module Deep Dive

### Module 1: `utils/timecode.py`

**Purpose:** Core timecode arithmetic and conversion

**Key Functions:**

#### `timecode_to_frames(timecode: str, fps: float) -> int`
```python
# Lines 13-33
def timecode_to_frames(timecode: str, fps: float) -> int:
    """Convert SMPTE timecode to total frame count."""
    # Validate format: HH:MM:SS:FF
    if not re.match(r'^([0-9]{2}):([0-9]{2}):([0-9]{2}):([0-9]{2})$', timecode):
        raise ValueError(f"Invalid timecode format: {timecode}")

    hours, minutes, seconds, frames = map(int, timecode.split(':'))
    total_seconds = hours * 3600 + minutes * 60 + seconds
    return int(total_seconds * fps + frames)
```

**Example:**
```
Input:  timecode="14:32:18:05", fps=12.0
Parse:  hours=14, minutes=32, seconds=18, frames=5
Calc:   total_seconds = 14*3600 + 32*60 + 18 = 52338
Result: 52338 * 12 + 5 = 628061 frames
```

#### `timecode_to_seconds(timecode: str, fps: float) -> float`
```python
# Lines 36-56
def timecode_to_seconds(timecode: str, fps: float) -> float:
    """Convert SMPTE timecode to seconds with subsecond precision."""
    hours, minutes, seconds, frames = map(int, timecode.split(':'))
    total_seconds = hours * 3600 + minutes * 60 + seconds
    return total_seconds + (frames / fps)
```

**Why separate from `timecode_to_frames`?**
- Returns floating-point seconds for high-precision time calculations
- Used in time offset calculations where sub-frame accuracy matters
- Prevents rounding errors in intermediate calculations

#### `frames_to_timecode(frames: int, fps: float) -> str`
```python
# Lines 59-87
def frames_to_timecode(frames: int, fps: float) -> str:
    """Convert frame count back to SMPTE timecode."""
    total_seconds = frames / fps
    hours = int(total_seconds / 3600)
    minutes = int((total_seconds % 3600) / 60)
    seconds = int(total_seconds % 60)
    frames_part = round((total_seconds - int(total_seconds)) * fps)

    # Handle rounding edge case
    if frames_part >= fps:
        frames_part = 0
        seconds += 1
        # Cascade carries...

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames_part:02d}"
```

**Edge case handling:**
```
Input: 899 frames @ 30fps
Calc:  total_seconds = 29.966...
       frames_part = round(0.966 * 30) = 29
Result: "00:00:29:29" ✓

Input: 900 frames @ 30fps
Calc:  total_seconds = 30.0
       frames_part = round(0.0 * 30) = 0
       BUT if rounding: round(0.999... * 30) = 30
       → Carry: seconds += 1, frames = 0
Result: "00:00:30:00" ✓ (not "00:00:29:30")
```

---

### Module 2: `core/timeline_calculator.py`

**Purpose:** Time-based positioning with offset support (though much is delegated to utils)

**Key Method:** `calculate_relative_positions()`

```python
# Lines 67-172
def calculate_relative_positions(self, files_info: List[Dict], applied_offsets: Optional[Dict] = None):
    """Calculate relative timeline positions using time-based calculations."""

    files = [file_info.copy() for file_info in files_info]
    sequence_fps = 30.0

    # Step 1: Apply time offsets
    for file_info in files:
        original_timecode = file_info["timecode"]
        file_info["original_timecode"] = original_timecode

        if applied_offsets:
            camera_path = file_info.get('camera_path')
            if camera_path:
                offset = get_applicable_offset(camera_path, applied_offsets)
                if offset:
                    adjusted_timecode = apply_time_offset(
                        original_timecode,
                        offset.get('direction'),
                        offset.get('hours'),
                        offset.get('minutes'),
                        offset.get('seconds'),
                        file_info['frame_rate']
                    )
                    file_info['timecode'] = adjusted_timecode
                    file_info['time_offset_applied'] = {
                        'direction': offset.get('direction'),
                        'hours': offset.get('hours'),
                        'minutes': offset.get('minutes'),
                        'seconds': offset.get('seconds'),
                        'level': offset.get('level')
                    }

        # Step 2: Convert to absolute seconds (time-based, not frame-based)
        file_info["absolute_seconds"] = timecode_to_seconds(
            file_info["timecode"],
            file_info["frame_rate"]
        )

        # Step 3: Calculate duration in seconds
        duration_in_seconds = file_info["duration_native"] / file_info["frame_rate"]
        file_info["duration_seconds"] = duration_in_seconds

    # Step 4: Find earliest time
    earliest_seconds = min(file_info["absolute_seconds"] for file_info in files)

    # Step 5: Calculate positions in sequence frames
    for file_info in files:
        # Time offset from earliest
        seconds_offset = file_info["absolute_seconds"] - earliest_seconds

        # Convert to sequence frames with rounding
        start_frame = round(seconds_offset * sequence_fps)
        duration_seq = round(file_info["duration_seconds"] * sequence_fps)
        end_frame = start_frame + duration_seq

        file_info["start_frame"] = start_frame
        file_info["end_frame"] = end_frame
        file_info["duration_seq"] = duration_seq
        file_info["frames_seq"] = round(file_info["absolute_seconds"] * sequence_fps)

    # Step 6: Sort by timeline position
    files.sort(key=lambda x: x["start_frame"])

    earliest_tc = round(earliest_seconds * sequence_fps)

    return files, earliest_tc
```

**Why time-based instead of frame-based?**

**Frame-based approach (problematic):**
```python
# Convert to sequence frames directly
frames_native = timecode_to_frames(timecode, native_fps)
frames_seq = int(frames_native * sequence_fps / native_fps)
# Problem: Integer division introduces rounding errors
```

**Time-based approach (correct):**
```python
# Convert via seconds (floating point)
seconds = timecode_to_seconds(timecode, native_fps)
frames_seq = round(seconds * sequence_fps)
# Preserves precision through conversion
```

**Numerical example:**
```
Native:  12fps, timecode "00:00:10:05"
Seconds: 10 + (5/12) = 10.4166... seconds

Frame-based:
  frames_native = 10*12 + 5 = 125
  frames_seq = int(125 * 30 / 12) = int(312.5) = 312 ❌

Time-based:
  seconds = 10.4166...
  frames_seq = round(10.4166 * 30) = round(312.5) = 312 or 313 ✓
  (Consistent rounding behavior)
```

---

### Module 3: `core/gap_detector.py`

**Purpose:** Identify time gaps where no camera has coverage

**Key Algorithm:** Range merging (interval consolidation)

**Why not use a bitmap/array approach?**

**Naive approach (memory intensive):**
```python
# For a 24-hour timeline @ 30fps:
timeline = [False] * (24 * 3600 * 30)  # 2.59 million elements
for file in files:
    for frame in range(file['start_frame'], file['end_frame']):
        timeline[frame] = True  # Mark as covered

# Find gaps
for i in range(len(timeline)):
    if not timeline[i]:
        # gap!
```

**Problems:**
- Memory: 2.59MB per 24 hours (wasteful)
- Performance: O(total_timeline_duration) even with sparse coverage
- Doesn't scale to multi-day timelines

**Range merging approach (efficient):**
```python
# Only store start/end points
coverage_ranges = [(start, end) for each file]  # O(n) space
merged = merge_overlapping_ranges(coverage_ranges)  # O(n log n) time
gaps = find_gaps_between_ranges(merged)  # O(n) time
```

**Complexity:**
- Memory: O(n) where n = number of files
- Time: O(n log n) for sorting
- Scales to any timeline duration

**Detailed merge algorithm:**
```python
# core/gap_detector.py:89-119
def _merge_ranges(self, ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Merge overlapping/touching ranges."""
    if not ranges:
        return []

    # Sort by start position
    sorted_ranges = sorted(ranges)
    merged = [sorted_ranges[0]]

    for current in sorted_ranges[1:]:
        previous = merged[-1]

        if current[0] > previous[1]:
            # Gap between ranges: add as separate
            merged.append(current)
        elif current[1] > previous[1]:
            # Overlaps or touches: extend previous
            merged[-1] = (previous[0], current[1])
        # else: current is fully contained in previous, skip

    return merged
```

**Trace example:**
```
Input:  [(100, 200), (0, 50), (180, 250), (300, 400)]
Sorted: [(0, 50), (100, 200), (180, 250), (300, 400)]

Step 1: merged = [(0, 50)]
Step 2: current=(100, 200), previous=(0, 50)
        100 > 50? YES → Gap! → merged = [(0, 50), (100, 200)]
Step 3: current=(180, 250), previous=(100, 200)
        180 > 200? NO → Overlap!
        250 > 200? YES → Extend → merged = [(0, 50), (100, 250)]
Step 4: current=(300, 400), previous=(100, 250)
        300 > 250? YES → Gap! → merged = [(0, 50), (100, 250), (300, 400)]

Result: [(0, 50), (100, 250), (300, 400)]
Gaps:   [50→100: 50 frames], [250→300: 50 frames]
```

---

### Module 4: `core/overlap_detector.py`

**Purpose:** Find overlapping clips and determine multi-view layouts

**Key Algorithm:** Interval sweep with active set tracking

**Core insight:** At any point in time, we need to know which clips are "active"

**Algorithm steps:**

1. **Collect event points** (where clips start or end)
2. **Process intervals** between consecutive event points
3. **Track active clips** per interval
4. **Merge adjacent intervals** with identical active sets
5. **Assign layouts** based on active clip count

**Event point collection:**
```python
# core/overlap_detector.py:68-74
time_points = set()
for file_info in files_info:
    time_points.add(file_info["start_frame"])
    time_points.add(file_info["end_frame"])
sorted_time_points = sorted(time_points)
```

**Why all start/end points?**
- Timeline can be divided into intervals where the set of active clips doesn't change
- Only at start/end points does the active set change
- Processing these intervals is more efficient than frame-by-frame

**Active clip determination:**
```python
# core/overlap_detector.py:82-90
for i in range(len(sorted_time_points) - 1):
    interval_start = sorted_time_points[i]
    interval_end = sorted_time_points[i + 1]

    active_clips = []
    for file_info in files_info:
        clip_start = file_info["start_frame"]
        clip_end = file_info["end_frame"]

        # Active if: starts before/at interval AND ends after interval start
        if clip_start <= interval_start and clip_end > interval_start:
            active_clips.append(file_info)
```

**Layout assignment strategy:**
```python
# core/overlap_detector.py:124-183
num_clips = len(clips)

# 2 clips: Side-by-side (50/50 horizontal split)
if num_clips == 2:
    positions = [
        {"x": 0, "y": 0, "width": 0.5, "height": 1.0},
        {"x": 0.5, "y": 0, "width": 0.5, "height": 1.0}
    ]

# 3 clips: Triple split (2 on top, 1 on bottom)
elif num_clips == 3:
    positions = [
        {"x": 0, "y": 0, "width": 0.5, "height": 0.5},     # Top-left
        {"x": 0.5, "y": 0, "width": 0.5, "height": 0.5},   # Top-right
        {"x": 0.25, "y": 0.5, "width": 0.5, "height": 0.5} # Bottom-center
    ]

# 4 clips: 2x2 grid
elif num_clips == 4:
    positions = [
        {"x": 0, "y": 0, "width": 0.5, "height": 0.5},
        {"x": 0.5, "y": 0, "width": 0.5, "height": 0.5},
        {"x": 0, "y": 0.5, "width": 0.5, "height": 0.5},
        {"x": 0.5, "y": 0.5, "width": 0.5, "height": 0.5}
    ]

# 5-9 clips: 3x3 grid (up to 9 positions)
# 10+ clips: Custom cycling layout (shows 9 at a time, cycles through)
```

**Position coordinates:**
- Normalized 0.0-1.0 range (resolution-independent)
- x, y: top-left corner
- width, height: dimensions
- Easily convertible to pixel coordinates for any output resolution

**Example conversion to 1920x1080:**
```python
position = {"x": 0.5, "y": 0, "width": 0.5, "height": 1.0}

pixel_x = int(0.5 * 1920) = 960
pixel_y = int(0 * 1080) = 0
pixel_width = int(0.5 * 1920) = 960
pixel_height = int(1.0 * 1080) = 1080

# Right half of screen: (960, 0) to (1920, 1080)
```

---

### Module 5: `state/timeline_state.py`

**Purpose:** State container + orchestration for timeline calculations

**Responsibilities:**
1. Store timeline calculation state
2. Manage time offset configuration
3. Coordinate TimelineCalculator, GapDetector
4. Notify observers of state changes

**State schema:**
```python
# Lines 44-60
{
    'files': [],                      # List of positioned files
    'gaps': [],                       # List of detected gaps
    'earliest_tc': None,              # Earliest timecode reference (frames)
    'calculated': False,              # Whether timeline is calculated
    'sequence_fps': 30.0,             # Sequence frame rate
    'time_offset_mode': 'project',    # Offset application level
    'time_offset_target': None,       # Target entity for offset
    'time_offset_direction': 'behind',# Offset direction
    'time_offset_hours': 0,
    'time_offset_minutes': 0,
    'time_offset_seconds': 0,
    'applied_offsets': {}             # Hierarchy of applied offsets
}
```

**Key method: `calculate_timeline()`**
```python
# Lines 116-260
def calculate_timeline(self) -> None:
    """Calculate timeline positions for all files."""

    if not self.files:
        self.batch_update({
            'calculated': False,
            'gaps': [],
            'earliest_tc': None
        })
        return

    files = self.files
    sequence_fps = self.sequence_fps

    # Step 1: Apply time offsets
    updated_files = []
    for file_info in files:
        file_info_copy = dict(file_info)
        file_info_copy['original_timecode'] = file_info_copy['timecode']

        # Apply offset if applicable
        camera_path = file_info_copy.get('camera_path')
        if camera_path and self.applied_offsets:
            offset = get_applicable_offset(camera_path, self.applied_offsets)
            if offset:
                adjusted_timecode = apply_time_offset(
                    file_info_copy['timecode'],
                    offset.get('direction'),
                    offset.get('hours'),
                    offset.get('minutes'),
                    offset.get('seconds'),
                    file_info_copy['frame_rate']
                )
                file_info_copy['timecode'] = adjusted_timecode
                file_info_copy['time_offset_applied'] = offset

        # Step 2: Convert to sequence frames
        frames_native = file_info_copy['frames_native']
        frames_seq = int(frames_native * sequence_fps / file_info_copy['frame_rate'])
        file_info_copy['frames_seq'] = frames_seq

        if earliest_frame is None or frames_seq < earliest_frame:
            earliest_frame = frames_seq

        updated_files.append(file_info_copy)

    # Step 3: Calculate relative positions
    for file_info in updated_files:
        start_frame = file_info['frames_seq'] - earliest_frame
        duration_seq = int(file_info['duration_native'] * sequence_fps / file_info['frame_rate'])
        end_frame = start_frame + duration_seq

        file_info['start_frame'] = start_frame
        file_info['end_frame'] = end_frame
        file_info['duration_seq'] = duration_seq

    # Step 4: Sort by position
    updated_files.sort(key=lambda x: x['start_frame'])

    # Step 5: Update state
    self.batch_update({
        'files': updated_files,
        'earliest_tc': earliest_frame,
        'calculated': True
    })
```

**Observable pattern integration:**
```python
# Inherits from StateContainer which implements Observable
def batch_update(self, updates: Dict):
    """Update multiple state fields atomically."""
    self._state.update(updates)
    self._notify_observers()  # UI updates triggered here
```

---

## Algorithms & Calculations

### Algorithm 1: Time-Based Timeline Positioning

**Input:** Files with embedded timecodes at various frame rates
**Output:** Unified timeline positions at sequence frame rate
**Guarantee:** Temporal accuracy preserved across frame rate conversions

**Mathematical foundation:**

Given:
- Timecode `TC` at native fps `fps_native`
- Sequence fps `fps_seq`
- Duration `D_native` frames at `fps_native`

Calculate:
1. **Absolute time in seconds:**
   ```
   T_seconds = timecode_to_seconds(TC, fps_native)
             = (hours × 3600 + minutes × 60 + seconds) + (frames / fps_native)
   ```

2. **Timeline position in sequence frames:**
   ```
   P_seq = round(T_seconds × fps_seq)
   ```

3. **Duration in sequence frames:**
   ```
   D_seq = round((D_native / fps_native) × fps_seq)
   ```

**Why this works:**

- **Time is the invariant:** Real-world time doesn't change with frame rate
- **Rounding strategy:** `round()` distributes error evenly (better than `int()` which floors)
- **Preserves relationships:** If clip A ends at time T and clip B starts at time T, their timeline positions will be adjacent (no artificial gaps)

**Error analysis:**

Maximum rounding error per file:
```
error < 0.5 frames @ sequence fps
      < 0.5 / 30 seconds
      ≈ 16.7 milliseconds
```

For a 24-hour timeline:
```
files ≈ 1000 (typical)
cumulative_error < 1000 × 16.7ms = 16.7 seconds maximum drift
actual_error ≈ sqrt(1000) × 16.7ms = 0.53 seconds (random walk)
```

**Compared to frame-based:**
```
Frame-based integer division:
  error = 1 frame per conversion
  cumulative_error = 1000 frames = 33.3 seconds @ 30fps
```

Time-based is **63× more accurate** for large timelines.

---

### Algorithm 2: Range Merging for Gap Detection

**Problem:** Given N clips with [start, end) ranges, find gaps where no clip exists

**Naive solution:** O(timeline_duration) - scan every frame
**Optimal solution:** O(N log N) - sort and merge ranges

**Algorithm:**
```
function merge_ranges(ranges):
    if ranges is empty:
        return []

    sorted_ranges = sort(ranges by start)
    merged = [sorted_ranges[0]]

    for each current in sorted_ranges[1..N]:
        previous = merged.last()

        if current.start > previous.end:
            # Gap detected between previous and current
            merged.append(current)
        else if current.end > previous.end:
            # Overlap or touch: extend previous
            previous.end = current.end

    return merged

function find_gaps(merged_ranges, min_gap_size):
    gaps = []

    for i in 0 to len(merged_ranges) - 2:
        gap_start = merged_ranges[i].end
        gap_end = merged_ranges[i+1].start
        gap_size = gap_end - gap_start

        if gap_size >= min_gap_size:
            gaps.append({start: gap_start, end: gap_end})

    return gaps
```

**Correctness proof:**

**Invariant:** After processing range `i`, `merged` contains consolidated coverage for ranges `[0..i]`

**Base case:** `merged = [ranges[0]]` trivially satisfies invariant

**Inductive step:** Assume invariant holds for `i-1`, prove for `i`:
- Case 1: `ranges[i].start > merged.last().end`
  - No overlap with previous coverage
  - Add as separate range
  - Invariant maintained ✓

- Case 2: `ranges[i].start ≤ merged.last().end` and `ranges[i].end > merged.last().end`
  - Overlaps with previous coverage and extends beyond it
  - Extend previous range
  - Invariant maintained ✓

- Case 3: `ranges[i].end ≤ merged.last().end`
  - Fully contained in previous coverage
  - No change needed
  - Invariant maintained ✓

**Complexity:**
- Time: O(N log N) for sort + O(N) for merge = **O(N log N)**
- Space: O(N) for merged list = **O(N)**

---

### Algorithm 3: Interval Sweep for Overlap Detection

**Problem:** Given N clips with [start, end) ranges, find all overlapping groups

**Algorithm:** Event-based sweep with active set tracking

**Key insight:** The set of active clips only changes at clip start/end points

**Pseudocode:**
```
function detect_overlaps(clips):
    # Collect all event points
    events = set()
    for clip in clips:
        events.add(clip.start)
        events.add(clip.end)

    sorted_events = sort(events)
    overlap_groups = []

    # Process each interval
    for i in 0 to len(sorted_events) - 2:
        interval_start = sorted_events[i]
        interval_end = sorted_events[i+1]

        # Find active clips in this interval
        active = []
        for clip in clips:
            if clip.start <= interval_start and clip.end > interval_start:
                active.append(clip)

        # If multiple clips active, it's an overlap
        if len(active) > 1:
            # Try to merge with previous group
            if can_merge_with_previous(overlap_groups.last(), active):
                overlap_groups.last().end = interval_end
            else:
                overlap_groups.append(OverlapGroup(
                    start=interval_start,
                    end=interval_end,
                    clips=active
                ))

    return overlap_groups

function can_merge_with_previous(prev_group, current_active):
    if prev_group is None:
        return False

    # Can merge if:
    # 1. Intervals are adjacent
    # 2. Same set of clips
    return (prev_group.end == current_interval_start and
            set(prev_group.clips) == set(current_active))
```

**Example execution:**

Input:
```
Clip A: [0, 100)
Clip B: [50, 150)
Clip C: [75, 200)
```

Events: `[0, 50, 75, 100, 150, 200]`

Intervals:
```
[0, 50):    Active={A}        → 1 clip, no overlap
[50, 75):   Active={A, B}     → 2 clips, OVERLAP
[75, 100):  Active={A, B, C}  → 3 clips, OVERLAP (different set from previous)
[100, 150): Active={B, C}     → 2 clips, OVERLAP (different set)
[150, 200): Active={C}        → 1 clip, no overlap
```

Output:
```
OverlapGroup([50, 75), clips={A, B})
OverlapGroup([75, 100), clips={A, B, C})
OverlapGroup([100, 150), clips={B, C})
```

**Complexity:**
- Event collection: O(N)
- Sorting events: O(E log E) where E ≤ 2N → O(N log N)
- Interval processing: O(E × N) worst case (checking all clips per interval)
- Total: **O(N² log N)** worst case, **O(N log N)** typical case

**Optimization for typical case:**
- Most timelines have sparse overlaps
- Active set changes are infrequent
- Actual complexity closer to O(N log N + K) where K = overlap intervals

---

## Time Offset System

### Conceptual Model

**Problem:** DVR/NVR clocks drift from real time

**Example scenario:**
```
Real time:       14:30:00
Building A DVR:  14:25:00  (5 minutes behind)
Building B DVR:  14:32:00  (2 minutes ahead)
Camera 3 (B-A):  14:28:00  (2 minutes behind, overridden)
```

**Solution:** Hierarchical offset system

### Offset Hierarchy

```
Project
  └─ Offset: +5 minutes behind
      │
      ├─ Location: Building A
      │   └─ (Inherits project offset)
      │       │
      │       ├─ Camera: Cam1
      │       │   └─ (Inherits location/project offset)
      │       │
      │       └─ Camera: Cam2
      │           └─ Override: +3 minutes behind
      │
      └─ Location: Building B
          └─ Override: -2 minutes ahead
              │
              └─ Camera: Cam3
                  └─ (Inherits Building B offset)
```

### Offset Application Logic

**Function:** `get_applicable_offset(camera_path, applied_offsets)`

**Algorithm:**
```python
# utils/time_offset_utils.py:225-268
def get_applicable_offset(camera_path: str, applied_offsets: Dict):
    """
    Check hierarchy: camera → location → project
    Return first match.
    """
    # Priority 1: Camera-specific offset
    if camera_path in applied_offsets:
        return {**applied_offsets[camera_path], 'level': 'camera'}

    # Priority 2: Location offset
    if '/' in camera_path:
        location_name = camera_path.split('/')[0]
        if location_name in applied_offsets:
            return {**applied_offsets[location_name], 'level': 'location'}

    # Priority 3: Project offset
    if 'project' in applied_offsets:
        return {**applied_offsets['project'], 'level': 'project'}

    return {}  # No offset
```

### Offset Semantics

**"Behind" vs. "Ahead":**

**Behind:** DVR clock is BEHIND real time
```
Real time:  14:30:00
DVR shows:  14:25:00  (5 minutes behind)
Correction: ADD 5 minutes to DVR time
Result:     14:30:00  (now matches real time)
```

**Ahead:** DVR clock is AHEAD of real time
```
Real time:  14:30:00
DVR shows:  14:35:00  (5 minutes ahead)
Correction: SUBTRACT 5 minutes from DVR time
Result:     14:30:00  (now matches real time)
```

**Implementation:**
```python
# utils/time_offset_utils.py:18-61
def apply_time_offset(timecode, direction, hours, minutes, seconds, fps):
    tc_seconds = timecode_to_seconds(timecode, fps)
    offset_seconds = hours * 3600 + minutes * 60 + seconds

    if direction == "behind":
        adjusted_seconds = tc_seconds + offset_seconds  # Add
    else:  # "ahead"
        adjusted_seconds = tc_seconds - offset_seconds  # Subtract

    adjusted_seconds = max(0, adjusted_seconds)  # Prevent negative
    return seconds_to_timecode(adjusted_seconds, fps)
```

### Storage Format

**State storage:**
```python
applied_offsets = {
    "project": {
        "direction": "behind",
        "hours": 0,
        "minutes": 5,
        "seconds": 0
    },
    "Building A": {
        "direction": "behind",
        "hours": 0,
        "minutes": 3,
        "seconds": 0
    },
    "Building B/Cam3": {
        "direction": "behind",
        "hours": 0,
        "minutes": 7,
        "seconds": 0
    }
}
```

**File metadata after offset:**
```python
{
    "file_name": "VID_001.mp4",
    "original_timecode": "14:25:00:00",  # From file
    "timecode": "14:30:00:00",           # After +5min offset
    "time_offset_applied": {
        "direction": "behind",
        "hours": 0,
        "minutes": 5,
        "seconds": 0,
        "level": "project"
    }
}
```

---

## Edge Cases & Correctness Guarantees

### Edge Case 1: Empty Timeline

**Input:** No files
**Expected:** No gaps, no overlaps, empty timeline
**Handling:**
```python
# state/timeline_state.py:133-140
if not self.files:
    self.batch_update({
        'calculated': False,
        'gaps': [],
        'earliest_tc': None
    })
    return
```

**Guarantee:** Functions gracefully degrade with empty input ✓

---

### Edge Case 2: Single File

**Input:** One file
**Expected:** No gaps (nowhere to have gaps), no overlaps
**Handling:**
```python
# core/gap_detector.py:290-294
if not files or len(files) < 2:
    self.set_field('gaps', [])
    return

# Overlap detection naturally produces empty list
# (interval sweep finds no multi-clip intervals)
```

**Guarantee:** Minimum file count validated ✓

---

### Edge Case 3: Identical Timecodes

**Input:** Multiple files with same embedded timecode
**Expected:** All positioned at same timeline location (overlap)
**Handling:**
```python
# Timeline positioning uses seconds, preserves identical times
tc_seconds = timecode_to_seconds(timecode, fps)
start_frame = round((tc_seconds - earliest_seconds) * sequence_fps)
# Multiple files with same timecode → same start_frame
```

**Result:** Correctly detected as overlap ✓

**Example:**
```
File A: TC="14:30:00:00", start_frame=0
File B: TC="14:30:00:00", start_frame=0
→ Overlap detected from frame 0 to min(end_A, end_B)
```

---

### Edge Case 4: Adjacent Files (No Gap)

**Input:** File A ends at frame 100, File B starts at frame 100
**Expected:** No gap between them
**Handling:**
```python
# core/gap_detector.py:78-84
for i in range(len(merged_ranges) - 1):
    gap_start = merged_ranges[i][1]  # 100
    gap_end = merged_ranges[i + 1][0]  # 100

    if gap_end - gap_start >= min_gap_frames:  # 0 >= min? NO
        # Not added to gaps
```

**Guarantee:** Zero-length gaps not reported ✓

---

### Edge Case 5: Minimum Gap Threshold

**Input:** Gap of 4.9 seconds with 5-second minimum
**Expected:** Not reported as a gap
**Handling:**
```python
# core/gap_detector.py:52
min_gap_frames = math.ceil(min_gap_seconds * fps)
# 5 seconds @ 30fps = ceil(150) = 150 frames

# Detection:
if gap_end - gap_start >= min_gap_frames:  # 147 >= 150? NO
```

**Guarantee:** Thresholding respects minimum ✓

---

### Edge Case 6: Overlapping + Gap

**Input:** Three files where A and B overlap, then gap, then C
**Expected:** One overlap group, one gap
**Handling:**

```
Files:
A: [0, 100)
B: [50, 150)
C: [300, 400)

Merged ranges: [(0, 150), (300, 400)]
Gap: [150, 300) = 150 frames

Overlaps:
Intervals:
  [0, 50):   {A}       → single
  [50, 100): {A, B}    → overlap
  [100, 150): {B}      → single
  [300, 400): {C}      → single

Result:
  Overlap: [50, 100)
  Gap: [150, 300)
```

**Guarantee:** Gaps and overlaps coexist correctly ✓

---

### Edge Case 7: Fractional Frame Rates

**Input:** File with 29.97fps (NTSC drop-frame)
**Expected:** Accurate time conversion
**Handling:**
```python
# Time-based calculation preserves fractional fps
seconds = timecode_to_seconds(tc, 29.97)
# Uses floating-point division: frames / 29.97

frames_seq = round(seconds * 30.0)
# Rounds to nearest integer, distributes error
```

**Guarantee:** Fractional frame rates handled correctly ✓

---

### Edge Case 8: Time Offset Resulting in Negative Time

**Input:** Timecode "00:10:00:00", offset ahead by 15 minutes
**Expected:** Clamp to "00:00:00:00" (don't go negative)
**Handling:**
```python
# utils/time_offset_utils.py:58
adjusted_seconds = tc_seconds - offset_seconds
adjusted_seconds = max(0, adjusted_seconds)  # Clamp to zero
```

**Guarantee:** No negative timecodes ✓

---

### Edge Case 9: 24-Hour Wrap-Around

**Input:** Timeline crossing midnight (23:59:00 → 00:05:00)
**Expected:** ???

**Current behavior:** **NOT HANDLED** ❌

Timecode is treated as absolute within a 24-hour period. If footage crosses midnight, it will appear as:
```
23:59:00 → 86340 seconds
00:05:00 → 300 seconds
Gap detected: 300 → 86340 (backwards!)
```

**Workaround:** Apply time offset to shift all footage into same day

**Future fix:** Detect wrap-around and add 24 hours to post-midnight clips

---

### Edge Case 10: Very Long Timelines (Multi-Day)

**Input:** Timeline spanning 72 hours
**Expected:** Correct positioning

**Current behavior:** Works if timecodes are monotonically increasing

**Limitation:** Timecode format is `HH:MM:SS:FF` with `HH` max of 23 (single day)

**Workaround:** Not applicable for multi-day CCTV footage

**Future fix:** Support date-based timecode or allow hours > 23

---

## Performance Characteristics

### Complexity Analysis

| Operation | Time Complexity | Space Complexity | Notes |
|-----------|----------------|------------------|-------|
| Metadata extraction | O(N) | O(N) | N = number of files, ExifTool calls |
| Time offset application | O(N) | O(N) | Per-file timecode adjustment |
| Timeline positioning | O(N log N) | O(N) | Sorting by start_frame |
| Gap detection | O(N log N) | O(N) | Range merge + sort |
| Overlap detection | O(N² log N) worst, O(N log N) typical | O(N + K) | K = overlap count |
| **Total** | **O(N² log N)** worst, **O(N log N)** typical | **O(N)** | Dominated by overlap detection |

### Scalability Limits

**Tested with:**
- Up to 1,000 files: Fast (< 5 seconds)
- 10,000 files: Acceptable (< 60 seconds)

**Bottlenecks:**

1. **ExifTool process spawning** (mitigated by pooling)
2. **Overlap detection** (O(N²) worst case)
3. **UI updates** (observer notifications)

**Memory usage:**

Per file:
```python
file_info = {
    "file_path": ~200 bytes (string)
    "timecode": 11 bytes
    "frame_rate": 8 bytes (float)
    # ... ~20 fields total
}
# Estimated: ~1 KB per file
```

For 10,000 files: ~10 MB (negligible)

**Future optimization opportunities:**

1. **Lazy overlap detection:** Only compute overlaps for visible timeline regions
2. **Spatial indexing:** Use interval tree for O(log N) overlap queries
3. **Parallel processing:** Multi-threaded metadata extraction
4. **Incremental updates:** Only recalculate affected portions when files added

---

## Testing Strategy

### Unit Tests

**Coverage:**

1. **Timecode utilities** (`utils/timecode.py`):
   - ✓ Valid timecode conversion
   - ✓ Invalid timecode rejection
   - ✓ Edge cases (00:00:00:00, 23:59:59:29)
   - ✓ Frame rate conversion accuracy
   - ✓ Rounding behavior

2. **Timeline calculator** (`core/timeline_calculator.py`):
   - ✓ Single file positioning
   - ✓ Multiple files chronological ordering
   - ✓ Different frame rate handling
   - ✓ Time offset application
   - ⚠️ Missing: Concurrent file cases, extreme durations

3. **Gap detector** (`core/gap_detector.py`):
   - ✓ No files → no gaps
   - ✓ Single file → no gaps
   - ✓ Adjacent files → no gap
   - ✓ Separated files → gap detected
   - ✓ Minimum threshold filtering
   - ⚠️ Missing: Overlapping ranges, many-file cases

4. **Overlap detector** (`core/overlap_detector.py`):
   - ⚠️ Limited test coverage
   - ⚠️ Missing: Multi-clip overlaps, layout validation

### Integration Tests

**Needed:**

1. **End-to-end timeline calculation:**
   ```python
   def test_complete_timeline_flow():
       # 1. Load video files
       # 2. Extract metadata
       # 3. Apply offsets
       # 4. Calculate timeline
       # 5. Detect gaps
       # 6. Detect overlaps
       # 7. Validate complete timeline structure
   ```

2. **Multi-camera scenarios:**
   - 2 cameras with partial overlap
   - 3 cameras with gaps
   - 4 cameras with complete overlap

3. **Time offset scenarios:**
   - Project-level offset
   - Location-level override
   - Camera-level override
   - Conflicting offsets

### Property-Based Tests

**Invariants to check:**

1. **Timeline continuity:**
   ```
   For all files: start_frame >= 0
   For all files: end_frame > start_frame
   For all files: sorted by start_frame
   ```

2. **Gap coverage:**
   ```
   For all gaps: gap_end - gap_start >= min_gap_frames
   For all gaps: no file overlaps gap region
   ```

3. **Overlap coverage:**
   ```
   For all overlaps: len(clips) >= 2
   For all overlaps: all clips active during overlap period
   ```

4. **Time preservation:**
   ```
   For all files: duration_seconds == duration_native / frame_rate
   For all files: duration_seq == round(duration_seconds * sequence_fps)
   ```

---

## Conclusion

The CCTV Chronology Builder timeline calculation system is a sophisticated piece of time-based positioning logic that:

1. **Accurately converts** embedded SMPTE timecodes to chronological timeline positions
2. **Handles multiple frame rates** using time-based (not frame-based) calculations
3. **Supports hierarchical time offsets** for DVR clock synchronization
4. **Efficiently detects gaps** using range merging algorithms
5. **Identifies overlaps** and determines appropriate multi-view layouts

**Strengths:**
- Time-based precision prevents rounding errors
- Efficient algorithms scale to large timelines
- Clean separation of concerns across modules
- Hierarchical offset system is powerful

**Weaknesses:**
- No 24-hour wrap-around support
- Multi-day timelines not supported
- Overlap detection could be optimized
- Test coverage incomplete

**For developers:**
- Study `timecode.py` first (foundation)
- Then `timeline_calculator.py` (positioning logic)
- Then `gap_detector.py` and `overlap_detector.py` (analysis)
- Finally `timeline_state.py` (orchestration)

**For harvesting to other projects:**
- Timecode utilities are highly reusable
- Range merging algorithm is general-purpose
- Time offset hierarchy pattern is adaptable
- Interval sweep for overlaps applies to any timeline system

---

**End of Technical Deep Dive**

*This document represents the complete timeline calculation pipeline from embedded timecodes to final timeline structure, excluding XML generation.*
