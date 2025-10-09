# CCTV Timeline Builder - Complete Technical Documentation

**Version:** 1.0.0
**Date:** October 9, 2025
**Author:** Forensic Development Team
**Status:** Production Ready

---

## Table of Contents

- [Section 1: Technical Walkthrough (Non-Technical)](#section-1-technical-walkthrough)
  - [Overview](#overview)
  - [The Big Picture](#the-big-picture)
  - [Step-by-Step Process](#step-by-step-process)
  - [Performance System](#performance-system)
- [Section 2: Senior Developer Documentation](#section-2-senior-developer-documentation)
  - [Architecture Overview](#architecture-overview)
  - [Data Flow Pipeline](#data-flow-pipeline)
  - [Core Components](#core-components)
  - [Implementation Details](#implementation-details)
  - [Performance Optimization](#performance-optimization)
  - [Testing & Validation](#testing--validation)

---

# Section 1: Technical Walkthrough

*For investigators, project managers, and anyone who wants to understand what this system does without diving into code.*

## Overview

The CCTV Timeline Builder automatically creates seamless video timelines from hundreds of individual CCTV clips. Think of it like assembling a jigsaw puzzle, but instead of pieces, you have video files with timestamps in their names.

**What it solves:**
- Manually reviewing 300+ separate video files is tedious
- Traditional video editors crash with large file counts
- Gaps in coverage go unnoticed
- Multi-camera synchronization is manual and error-prone

**What you get:**
- One continuous timeline video showing all footage chronologically
- Visual slates showing gaps ("No coverage from 2:15 PM to 2:47 PM")
- Multi-camera split-screen when multiple cameras recorded simultaneously
- Handles 195 files in 12 minutes, unlimited files with batch mode

---

## The Big Picture

```
INPUT                    PROCESSING                   OUTPUT
─────                    ──────────                   ──────

📁 Folder of Videos      1. Parse filenames          📹 timeline.mp4
                            ↓
A02_20250521140357.mp4   2. Extract timestamps       [One continuous video]
A02_20250521140638.mp4      ↓                        ├─ Camera A02: 14:03:57
A04_20250521141205.mp4   3. Build timeline           ├─ GAP SLATE: 30 seconds
      ...                   ↓                        ├─ Camera A02: 14:10:15
(195 files)              4. Detect gaps/overlaps     └─ Split: A02 | A04: 14:12:05
                            ↓
                         5. Render video
                            ↓
                         ✅ Complete!
```

---

## Step-by-Step Process

### **Step 1: Filename Parsing**

**What happens:**
The system reads video filenames and extracts the exact time each recording started.

**Example:**
```
Filename: A02_20250521140357.mp4
         ↓
Parsed as:
- Camera: A02
- Date: May 21, 2025
- Time: 14:03:57 (2:03:57 PM)
```

**Why it matters:**
CCTV systems embed timestamps in filenames. By parsing these, we know exactly when each clip belongs in the timeline—no guesswork.

---

### **Step 2: Metadata Extraction**

**What happens:**
The system uses FFprobe (a video analysis tool) to get technical details about each video.

**Information extracted:**
- Duration (how long is the clip?)
- Resolution (1920x1080, 1280x720, etc.)
- Frame rate (30 fps, 29.97 fps, etc.)
- Codec (H.264, H.265, etc.)

**Why it matters:**
Videos from different cameras or times may have different technical specs. We need to know these to normalize everything into one consistent timeline.

---

### **Step 3: Timeline Construction**

**What happens:**
The system arranges all clips chronologically and detects patterns.

**Timeline Analysis:**
```
Time:     14:00    14:05    14:10    14:15    14:20
          │        │        │        │        │
Camera A: ████████████████─────────────████████████
Camera B: ─────────────████████████████████─────────

Result:
├─ 14:00-14:08: Camera A (single)
├─ 14:08-14:10: GAP (no coverage)
├─ 14:10-14:15: Camera A + B (split-screen)
└─ 14:15-14:20: Camera B (single)
```

**Patterns detected:**
1. **Single camera segments** - Only one camera has footage
2. **Gaps** - No cameras have footage (coverage gap)
3. **Overlaps** - Multiple cameras recorded simultaneously

---

### **Step 4: Slate Generation**

**What happens:**
For gaps in coverage, the system creates 5-second "slate" videos showing the missing time range.

**Gap Slate Example:**
```
┌─────────────────────────────────────┐
│                                     │
│   GAP: 14:08:35 → 14:10:12          │
│   (Δ 1m 37s)                        │
│                                     │
│   [No camera coverage during        │
│    this time period]                │
│                                     │
└─────────────────────────────────────┘
```

**Why it matters:**
Investigators need to know when coverage is missing. A visual indicator is much clearer than just jumping forward in time.

---

### **Step 5: Multi-Camera Layouts**

**What happens:**
When multiple cameras recorded at the same time, the system creates split-screen layouts.

**Split-Screen Options:**

**Side-by-Side:**
```
┌─────────────┬─────────────┐
│   Camera    │   Camera    │
│     A02     │     A04     │
│             │             │
│  [Video 1]  │  [Video 2]  │
│             │             │
└─────────────┴─────────────┘
```

**Stacked:**
```
┌───────────────────────────┐
│       Camera A02          │
│       [Video 1]           │
├───────────────────────────┤
│       Camera A04          │
│       [Video 2]           │
└───────────────────────────┘
```

---

### **Step 6: Video Rendering**

**What happens:**
FFmpeg (professional video processing software) combines everything into one final video.

**Rendering Pipeline:**
```
1. Normalize each clip:
   ├─ Convert to consistent frame rate (30 fps)
   ├─ Scale to output resolution (1920x1080)
   ├─ Pad with letterboxing if aspect ratios differ
   └─ Convert to consistent pixel format

2. Concatenate segments:
   ├─ Clip 1 (2min 31s)
   ├─ Gap slate (5s)
   ├─ Clip 2 (1min 18s)
   ├─ Split-screen segment (3min 42s)
   └─ ... (continues)

3. Encode final output:
   └─ H.265 (HEVC) with NVENC (GPU encoding)
```

**Performance:**
- 195 files → 3-hour timeline
- Render time: **12 minutes** (15x realtime)
- GPU encoding: 48% utilization

---

## Performance System

The system has a **three-tier performance and safety system** to handle different scenarios:

### **Tier 1: GPU Hardware Decode (Optional)**

**What it does:**
Uses your graphics card (GPU) to decode video instead of the CPU.

**When to use:**
- Small to medium datasets (< 200 files)
- You want maximum speed (~30% faster)

**When NOT to use:**
- Large datasets (> 200 files)
- Deep folder structures with long file paths

**Status:** Currently disabled due to GPU/CPU filter compatibility issues. Can be implemented if needed.

---

### **Tier 2: Batch Rendering (Optional)**

**What it does:**
Splits large datasets into smaller batches, renders each separately, then combines them.

**How it works:**
```
336 files → Split into batches
├─ Batch 1: Files 1-150 → Render → batch_001.mp4
├─ Batch 2: Files 151-300 → Render → batch_002.mp4
└─ Batch 3: Files 301-336 → Render → batch_003.mp4

Then: Combine all batches → final_timeline.mp4
```

**When to use:**
- Investigations with 250+ files
- You hit a "[WinError 206]" error

**Performance impact:**
- Adds ~10-15% to render time
- But handles unlimited files

---

### **Tier 3: Auto-Fallback (Always On)**

**What it does:**
Automatically detects if your command will fail and switches to batch mode.

**How it works:**
```
Before rendering:
├─ Estimate command length
├─ If > 29,000 characters (90% of Windows limit)
│  ├─ Log warning
│  └─ Enable batch mode automatically
└─ Proceed with rendering
```

**Why it matters:**
Windows has a hard limit on how long commands can be. Without auto-fallback, large datasets would just crash. With it, the system adapts automatically.

---

## Real-World Examples

### **Example 1: Single Camera, No Gaps**

**Input:**
- 50 files from Camera A02
- Continuous recording (no gaps)
- Total duration: 1 hour 15 minutes

**Process:**
1. Parse 50 filenames → Extract timestamps
2. Build timeline → 50 sequential segments
3. Render → One continuous video

**Output:**
- `timeline.mp4` (1hr 15min)
- Render time: ~5 minutes
- No slates (no gaps)

---

### **Example 2: Two Cameras with Gaps**

**Input:**
- 195 files from Cameras A02 and A04
- Some overlap, some gaps
- Total span: 3 hours

**Process:**
1. Parse 195 filenames
2. Detect:
   - 141 gaps (coverage holes)
   - 53 overlaps (both cameras recording)
   - 195 single-camera segments
3. Generate 141 gap slates
4. Render with split-screen for overlaps

**Output:**
- `timeline.mp4` (3hrs)
- Render time: 12 minutes
- 141 gap slates inserted
- 53 split-screen segments

---

### **Example 3: Large Investigation (336 Files)**

**Input:**
- 336 files from 2 cameras
- Some very long paths (deep folders)
- Command would exceed Windows limit

**Process:**
1. Parse 336 filenames
2. Auto-fallback detects command too long
3. Split into 3 batches:
   - Batch 1: 150 files
   - Batch 2: 150 files
   - Batch 3: 36 files
4. Render each batch
5. Concatenate batches

**Output:**
- `timeline.mp4` (variable duration)
- Render time: ~20-25 minutes
- No errors (auto-fallback prevented crash)

---

## Key Benefits

### **For Investigators**

✅ **Single Timeline View**
- No more clicking through 300 files
- Continuous playback from start to finish
- Easy to scrub through hours of footage

✅ **Gap Awareness**
- Immediate visual indicator of missing coverage
- Timestamp ranges clearly shown
- Know exactly when you have/don't have footage

✅ **Multi-Camera Sync**
- See multiple angles simultaneously
- No guessing which clips overlap
- Synchronized perfectly by timestamp

---

### **For Technical Teams**

✅ **Scalability**
- Handles 195 files: 12 minutes
- Handles 336 files: ~25 minutes (batch mode)
- Handles 1000+ files: auto-batch prevents errors

✅ **Performance**
- GPU encoding (NVENC): 15x realtime
- Optimized for forensic workloads
- Minimal disk I/O (temp files cleaned automatically)

✅ **Reliability**
- Auto-fallback prevents crashes
- Comprehensive error logging
- Graceful failure with user-friendly messages

---

## Common Questions

### **Q: What if my filenames don't match the pattern?**

**A:** The system supports multiple filename patterns:
- Dahua NVR Standard
- Compact timestamps (HHMMSS)
- ISO 8601 formats
- Military date formats
- Auto-detect mode (tries all patterns)

If your format isn't supported, you can generate a custom pattern using the built-in Pattern Generator.

---

### **Q: Can I change the output resolution?**

**A:** Yes! Supported resolutions:
- 1920x1080 (1080p) - Default
- 1280x720 (720p)
- 3840x2160 (4K)
- 2560x1440 (1440p)

Higher resolutions = larger file size and longer render time.

---

### **Q: What if rendering fails?**

**A:** The system has multiple fallback mechanisms:

1. **Auto-fallback activates** if command too long
2. **Batch mode** available as manual override
3. **Error logs** show exactly what went wrong
4. **User-friendly messages** (no cryptic error codes)

If all else fails, check the log file:
`C:\Users\[YourName]\.folder_structure_utility\logs\app_YYYYMMDD.log`

---

### **Q: Does it work with non-CCTV footage?**

**A:** Yes, but with caveats:

✅ **Works if:**
- Filenames contain timestamps
- Videos are H.264 or H.265
- Files are in a supported format (MP4, AVI, MOV)

❌ **May not work if:**
- Filenames have no timestamps
- Videos are heavily compressed or corrupted
- File formats are exotic (ProRes RAW, etc.)

---

# Section 2: Senior Developer Documentation

*For developers, architects, and technical leads who need to understand the implementation details, extend functionality, or maintain the codebase.*

---

## Architecture Overview

### **Design Philosophy**

The CCTV Timeline Builder follows a **service-oriented architecture** with clear separation of concerns:

1. **Presentation Layer** - PySide6 UI (FilenameParserTab)
2. **Controller Layer** - Thin orchestration (TimelineController)
3. **Service Layer** - Business logic (MulticamRendererService, FFmpegTimelineBuilder)
4. **Model Layer** - Type-safe data structures (VideoMetadata, RenderSettings)

**Key principles:**
- Single Responsibility Principle
- Dependency Injection
- Result Objects (no exceptions for control flow)
- Immutable data structures where possible

---

### **Technology Stack**

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **UI Framework** | PySide6 | 6.4+ | Qt6 bindings for Python |
| **Video Processing** | FFmpeg | N-119294 | Video encoding/decoding/filtering |
| **Video Analysis** | FFprobe | (bundled) | Metadata extraction |
| **Language** | Python | 3.11+ | Application runtime |
| **Concurrency** | QThread | (PySide6) | Background processing |
| **Logging** | Python logging | stdlib | Centralized logging with Qt signals |

---

### **Core Design Patterns**

#### **1. Result Objects Pattern**

All operations return `Result[T]` instead of raising exceptions:

```python
from core.result_types import Result
from core.exceptions import FileOperationError

def operation() -> Result[OutputType]:
    try:
        # ... operation logic
        return Result.success(data)
    except Exception as e:
        error = FileOperationError(
            "Technical error message",
            user_message="User-friendly message",
            context={"additional": "data"}
        )
        return Result.error(error)
```

**Benefits:**
- Explicit error handling in type signatures
- No hidden control flow
- Easy to compose operations
- Separates technical and user-facing error messages

---

#### **2. Atomic Interval Algorithm (GPT-5 Approach)**

Instead of frame-based calculations, we use **time-based atomic intervals**:

```python
# Collect all unique time boundaries
bounds = {clip.start, clip.end for clip in clips}
edges = sorted(bounds)

# Create intervals where camera set is constant
for i in range(len(edges) - 1):
    t0, t1 = edges[i], edges[i + 1]
    active_cameras = [c for c in clips if c.start < t1 and c.end > t0]
    intervals.append(Interval(t0, t1, active_cameras))
```

**Advantages over frame-based:**
- No frame rate conversion issues
- Handles variable frame rate (VFR) content
- No cumulative rounding errors
- Works with ISO 8601 timestamps directly

---

#### **3. Three-Tier Performance System**

Cascading optimization layers with automatic fallback:

```python
# Tier 1: Hardware Decode (optional, user-controlled)
if settings.use_hardware_decode:
    add_hwaccel_flags()  # GPU decode

# Tier 2: Batch Rendering (optional, user-controlled)
if settings.use_batch_rendering:
    render_in_batches()

# Tier 3: Auto-Fallback (always on, transparent)
estimated_length = estimate_argv_length()
if estimated_length > SAFE_THRESHOLD:
    logger.warning("Auto-enabling batch mode")
    render_in_batches()
else:
    render_single_pass()
```

---

## Data Flow Pipeline

### **End-to-End Flow Diagram**

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERACTION                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. FILE SELECTION (FilenameParserTab)                           │
│    - User selects folder containing video files                 │
│    - UI builds file list with preview                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. FILENAME PARSING (FilenameParserController)                  │
│    ├─ PatternMatcher.detect_pattern(filename)                  │
│    ├─ SMPTEParser.parse(filename, pattern)                     │
│    └─ Returns: smpte_timecode (HH:MM:SS:FF)                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. METADATA EXTRACTION (VideoMetadataExtractor)                 │
│    ├─ FFprobe analysis (single pass):                          │
│    │  ├─ duration_seconds (format.duration)                    │
│    │  ├─ frame_rate (r_frame_rate)                            │
│    │  ├─ resolution (width, height)                           │
│    │  ├─ codec (codec_name)                                   │
│    │  └─ pixel_format (pix_fmt)                               │
│    ├─ SMPTE → ISO 8601 conversion:                            │
│    │  └─ start_time + duration = end_time                     │
│    └─ Camera ID extraction from path                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. TIMELINE CONSTRUCTION (FFmpegTimelineBuilder)                │
│    ├─ _normalize_clip_times():                                 │
│    │  └─ Convert ISO 8601 → seconds from t0                   │
│    ├─ _build_atomic_intervals():                              │
│    │  ├─ Collect time boundaries: {clip.start, clip.end}     │
│    │  └─ Create intervals where camera set is constant       │
│    ├─ _segments_from_intervals():                             │
│    │  ├─ Merge adjacent intervals (same cameras)             │
│    │  ├─ Classify: SINGLE | OVERLAP | GAP                    │
│    │  └─ Generate slate specs for gaps                       │
│    └─ Returns: List[Segment]                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. COMMAND GENERATION (FFmpegTimelineBuilder)                   │
│    ├─ _emit_ffmpeg_argv():                                     │
│    │  ├─ Build -i inputs for video segments                   │
│    │  ├─ Generate slate filters in filtergraph                │
│    │  ├─ Apply normalization (scale, pad, fps, format)        │
│    │  ├─ Create split-screen layouts (xstack)                 │
│    │  ├─ Concatenate all segments (concat filter)             │
│    │  └─ Write filtergraph to temp file                       │
│    └─ Returns: (argv, filter_script_path)                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. RENDERING (MulticamRendererService)                          │
│    ├─ estimate_argv_length() → Check Windows limits            │
│    ├─ Decision: Single-pass or batch?                          │
│    │                                                            │
│    ├─ SINGLE-PASS PATH:                                        │
│    │  ├─ subprocess.Popen(ffmpeg_command)                     │
│    │  ├─ Monitor stderr for progress                          │
│    │  └─ Wait for completion                                  │
│    │                                                            │
│    └─ BATCH PATH:                                              │
│       ├─ Split clips into batches (150 each)                   │
│       ├─ Render each batch to temp file                        │
│       ├─ Concatenate batches (FFmpeg concat demuxer)           │
│       └─ Clean up temp files                                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. OUTPUT                                                        │
│    └─ timeline.mp4 (H.265/HEVC, 1920x1080, 30fps)             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### **Component 1: FilenameParserController**

**Responsibility:** Parse CCTV filenames to extract SMPTE timecodes.

**Key Methods:**

```python
class FilenameParserController:
    def parse_files(
        self,
        file_paths: List[Path],
        settings: FilenameParserSettings
    ) -> Result[ProcessingStatistics]:
        """
        Parse batch of video files to extract timestamps.

        Args:
            file_paths: List of video file paths
            settings: Parser settings (pattern, fps, offset, etc.)

        Returns:
            Result containing statistics or error
        """
```

**Data Flow:**

```python
# Input
file_path = Path("D:/A02/A02_20250521140357.mp4")

# Pattern Detection
pattern = PatternMatcher.detect("20250521140357")  # → "embedded_time"

# SMPTE Parsing
smpte = SMPTEParser.parse("20250521140357", pattern)
# → "14:03:57:00" (HH:MM:SS:FF)

# Output
ProcessingResult(
    filename="A02_20250521140357.mp4",
    smpte_timecode="14:03:57:00",
    success=True
)
```

---

### **Component 2: VideoMetadataExtractor**

**Responsibility:** Extract comprehensive video metadata using FFprobe in a single pass.

**Implementation:**

```python
class VideoMetadataExtractor:
    def extract_metadata(self, file_path: Path) -> VideoProbeData:
        """
        Extract all video metadata in one FFprobe call.

        Uses comprehensive probe with both format and stream data:
        - Format: Container-level info (duration, bitrate)
        - Streams: Video stream info (resolution, fps, codec)

        Returns:
            VideoProbeData with all extracted fields
        """
        cmd = [
            ffprobe,
            "-v", "error",
            "-probesize", "100M",
            "-analyzeduration", "100M",
            "-show_format",
            "-show_streams",
            "-select_streams", "v:0",
            "-of", "json",
            str(file_path)
        ]

        # Parse JSON and extract with fallback logic
        return self._parse_probe_data(file_path, json_data)
```

**Duration Extraction (GPT-5 Fallback Logic):**

```python
def _extract_duration(self, fmt: Dict, stream: Dict) -> float:
    """
    Priority-based duration extraction:
    1. format.duration (most reliable)
    2. stream.duration
    3. duration_ts * time_base (calculated)
    4. nb_frames / fps (last resort)
    """
    # Try container duration first
    if fmt.get("duration"):
        return float(fmt["duration"])

    # Try stream duration
    if stream.get("duration"):
        return float(stream["duration"])

    # Calculate from duration_ts
    if stream.get("duration_ts") and stream.get("time_base"):
        duration_ts = int(stream["duration_ts"])
        time_base = self._parse_rational(stream["time_base"])
        return float(duration_ts * time_base)

    # Last resort: frame count / fps
    if stream.get("nb_frames"):
        nb_frames = int(stream["nb_frames"])
        fps = self._extract_frame_rate(stream)
        return nb_frames / fps

    return 0.0  # Unknown
```

---

### **Component 3: FFmpegTimelineBuilder**

**Responsibility:** Generate FFmpeg commands using atomic interval algorithm.

**Core Algorithm:**

```python
def build_command(
    self,
    clips: List[Clip],
    settings: RenderSettings,
    output_path: Path,
    timeline_is_absolute: bool = True
) -> Tuple[List[str], str]:
    """
    Build complete FFmpeg command for timeline rendering.

    Process:
    1. Normalize clip times to seconds from t0
    2. Build atomic intervals (time boundaries)
    3. Create segments from intervals (classify + merge)
    4. Emit FFmpeg command (argv + filter script)

    Returns:
        Tuple of (argv list, filter_script_path)
    """
    # Step 1: Normalize times
    norm_clips = self._normalize_clip_times(clips, absolute=timeline_is_absolute)

    # Step 2: Atomic intervals
    intervals = self._build_atomic_intervals(norm_clips)

    # Step 3: Segments
    segments = self._segments_from_intervals(intervals, settings)

    # Step 4: FFmpeg command
    argv, filter_script = self._emit_ffmpeg_argv(segments, settings, output_path)

    return argv, filter_script
```

**Atomic Interval Construction:**

```python
def _build_atomic_intervals(self, clips: List[_NClip]) -> List[_Interval]:
    """
    Build atomic intervals using boundary decomposition.

    Algorithm:
    1. Collect all time boundaries (start/end of clips)
    2. Sort boundaries chronologically
    3. For each pair of adjacent boundaries:
       - Find clips active in that interval
       - Create interval with active camera set

    Example:
        Clip A: [0, 10)
        Clip B: [5, 15)

        Boundaries: {0, 5, 10, 15}

        Intervals:
        - [0, 5): {A}
        - [5, 10): {A, B}
        - [10, 15): {B}
    """
    # Collect unique boundaries
    bounds = set()
    for clip in clips:
        bounds.add(clip.start)
        bounds.add(clip.end)

    edges = sorted(bounds)

    # Create intervals
    intervals = []
    for i in range(len(edges) - 1):
        t0, t1 = edges[i], edges[i + 1]

        # Find active clips
        active = [c for c in clips if c.start < t1 and c.end > t0]

        intervals.append(_Interval(t0, t1, active))

    return intervals
```

**Segment Classification:**

```python
def _segments_from_intervals(
    self,
    intervals: List[_Interval],
    settings: RenderSettings
) -> List[_Segment]:
    """
    Convert intervals to renderable segments.

    Process:
    1. Merge adjacent intervals with same camera set
    2. Classify as: GAP, SINGLE, OVERLAP
    3. Generate segment specs

    Classification:
    - GAP: len(active) == 0 → Generate slate
    - SINGLE: len(active) == 1 → Single camera
    - OVERLAP: len(active) >= 2 → Split-screen
    """
    segments = []

    i = 0
    while i < len(intervals):
        # Merge adjacent intervals with same cameras
        j = i + 1
        while j < len(intervals) and same_cameras(intervals[j], intervals[i]):
            j += 1

        merged = Interval(intervals[i].t0, intervals[j-1].t1, intervals[i].active)

        # Classify
        if not merged.active:
            # GAP
            segments.append(_SegSlate(merged.t0, merged.t1, slate_text))
        elif len(merged.active) == 1:
            # SINGLE
            segments.append(_SegSingle(merged.active[0], merged.t0, merged.t1))
        else:
            # OVERLAP (take first two cameras)
            segments.append(_SegOverlap2(
                merged.active[0],
                merged.active[1],
                merged.t0,
                merged.t1
            ))

        i = j

    return segments
```

---

### **Component 4: MulticamRendererService**

**Responsibility:** Orchestrate FFmpeg execution with three-tier performance system.

**Three-Tier Decision Tree:**

```python
def render_timeline(
    self,
    videos: List[VideoMetadata],
    settings: RenderSettings,
    progress_callback: Optional[Callable] = None
) -> Result[Path]:
    """
    Render timeline with three-tier optimization system.

    Tier 1: Hardware Decode (optional)
        - User enables via checkbox
        - Adds -hwaccel cuda flags
        - ~30% faster but increases argv

    Tier 2: Batch Rendering (optional)
        - User enables via checkbox
        - Splits into 150-clip batches
        - Handles unlimited files

    Tier 3: Auto-Fallback (automatic)
        - Estimates argv length
        - Auto-enables batch if > 29K chars
        - Logs warning, prevents crash
    """
    clips = self._videos_to_clips(videos)

    # Estimate argv length
    estimated_length = self.builder.estimate_argv_length(
        clips,
        settings,
        with_hwaccel=settings.use_hardware_decode
    )

    # Auto-fallback decision
    needs_batching = estimated_length > self.builder.SAFE_ARGV_THRESHOLD
    use_batching = settings.use_batch_rendering or needs_batching

    if needs_batching and not settings.use_batch_rendering:
        self.logger.warning(
            f"Command length ({estimated_length} chars) approaching limit. "
            f"Auto-enabling batch rendering..."
        )

    # Route to appropriate method
    if use_batching:
        return self._render_in_batches(videos, clips, settings, progress_callback)
    else:
        return self._render_single_pass(clips, settings, progress_callback)
```

**Batch Rendering Implementation:**

```python
def _render_in_batches(
    self,
    videos: List[VideoMetadata],
    clips: List[Clip],
    settings: RenderSettings,
    progress_callback: Optional[Callable] = None
) -> Result[Path]:
    """
    Render timeline in multiple batches.

    Process:
    1. Split clips into batches (150 each)
    2. Render each batch to temp file
    3. Concatenate batches using FFmpeg concat demuxer
    4. Clean up temp files

    Example (336 clips):
        Batch 1: clips[0:150] → batch_001.mp4
        Batch 2: clips[150:300] → batch_002.mp4
        Batch 3: clips[300:336] → batch_003.mp4

        Concat: batch_001.mp4 + batch_002.mp4 + batch_003.mp4 → final.mp4
    """
    # Split into batches
    batches = self._split_clips_into_batches(clips, settings)

    # Create temp directory
    temp_dir = Path(tempfile.mkdtemp(prefix="timeline_batch_"))
    batch_files = []

    try:
        # Render each batch
        for i, batch_clips in enumerate(batches, 1):
            batch_output = temp_dir / f"batch_{i:03d}.mp4"

            # Create batch settings (disable batching within batch)
            batch_settings = dataclasses.replace(
                settings,
                output_directory=temp_dir,
                output_filename=batch_output.name,
                use_batch_rendering=False
            )

            # Render this batch
            result = self._render_single_pass(batch_clips, batch_settings, None)
            if not result.success:
                return result

            batch_files.append(batch_output)

        # Concatenate batches
        final_output = settings.output_directory / settings.output_filename
        return self._concatenate_batches(batch_files, final_output)

    finally:
        # Cleanup
        for batch_file in batch_files:
            batch_file.unlink()
        temp_dir.rmdir()
```

**FFmpeg Concat Demuxer:**

```python
def _concatenate_batches(
    self,
    batch_files: List[Path],
    output_path: Path
) -> Result[Path]:
    """
    Concatenate batch files using FFmpeg concat demuxer.

    Uses stream copy (-c copy) for instant concatenation
    without re-encoding (< 1 second for 3 batches).

    Concat file format:
        file 'C:\Temp\batch_001.mp4'
        file 'C:\Temp\batch_002.mp4'
        file 'C:\Temp\batch_003.mp4'
    """
    # Create concat list file
    concat_file = batch_files[0].parent / "concat_list.txt"

    with open(concat_file, 'w') as f:
        for batch_file in batch_files:
            f.write(f"file '{batch_file.absolute()}'\n")

    # Build concat command
    command = [
        ffmpeg, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",  # Stream copy (no re-encode)
        str(output_path)
    ]

    # Execute
    process = subprocess.run(command, capture_output=True, text=True)

    if process.returncode != 0:
        return Result.error(...)

    concat_file.unlink()
    return Result.success(output_path)
```

---

## Implementation Details

### **FFmpeg Command Structure**

**Single-Pass Command Example (195 clips):**

```bash
ffmpeg -y \
  # Input 1
  -ss 0.000000 -t 151.866333 -i "D:\A02\A02_20250521140357.mp4" \
  # Input 2
  -ss 0.000000 -t 61.000000 -i "D:\A02\A02_20250521140638.mp4" \
  # ... (193 more inputs)

  # Filter script (avoids argv length issues)
  -filter_complex_script "C:\Temp\tmp_filter.fffilter" \

  # Map output
  -map "[vout]" \
  -vsync 0 \
  -an \

  # NVENC encoder settings
  -c:v hevc_nvenc \
  -preset p5 \
  -cq 20 \
  -rc vbr_hq \
  -b:v 0 \
  -g 60 \
  -bf 2 \
  -spatial-aq 1 \
  -temporal-aq 1 \

  # Output
  "D:\Output\timeline.mp4"
```

**Filter Script Contents:**

```
# Slate (generated in filtergraph)
color=size=1920x1080:rate=30:duration=5 [sl0];
[sl0] drawtext=text='GAP\\: 14\\:08\\:35 → 14\\:10\\:12  (Δ 1m37s)':x=(w-tw)/2:y=(h-th)/2:fontsize=54:fontcolor=white:box=1:boxcolor=black@0.5 [s0];

# Single camera segment
[1:v] settb=AVTB,setpts=PTS-STARTPTS,fps=30:round=near,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,format=yuv420p [s1];

# Two-camera overlap (split-screen)
[2:v] settb=AVTB,setpts=PTS-STARTPTS,fps=30:round=near,scale=960:1080:force_original_aspect_ratio=decrease,pad=960:1080:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,format=yuv420p [pa2];
[3:v] settb=AVTB,setpts=PTS-STARTPTS,fps=30:round=near,scale=960:1080:force_original_aspect_ratio=decrease,pad=960:1080:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,format=yuv420p [pb2];
[pa2][pb2] xstack=inputs=2:layout=0_0|w0_0:fill=black [s2];

# ... (more segments)

# Concatenate all segments
[s0][s1][s2]...[sN] concat=n=N:v=1:a=0 [vout]
```

---

### **Filter Chain Breakdown**

**Normalization Chain (per input):**

```
[N:v]                          # Input N, video stream
settb=AVTB,                    # Set timebase to AV_TIME_BASE
setpts=PTS-STARTPTS,           # Reset PTS to start at 0
fps=30:round=near,             # Convert to 30 fps (round to nearest)
scale=1920:1080:force_original_aspect_ratio=decrease,  # Scale down if needed
pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,        # Letterbox if needed
setsar=1,                      # Set sample aspect ratio to 1:1
format=yuv420p                 # Convert to yuv420p pixel format
[sN]                           # Output label
```

**Why each step matters:**

1. **settb=AVTB** - Normalizes timebase for consistent timing
2. **setpts=PTS-STARTPTS** - Ensures each segment starts at t=0
3. **fps=30:round=near** - Converts variable frame rates to constant 30 fps
4. **scale** - Resizes to target resolution, preserving aspect ratio
5. **pad** - Adds letterboxing (black bars) to fill frame
6. **setsar=1** - Fixes anamorphic/stretched video
7. **format=yuv420p** - Ensures encoder-compatible pixel format

---

### **Split-Screen Layout Generation**

**Side-by-Side (2 cameras):**

```
# Pane dimensions
pane_w = 1920 / 2 = 960
pane_h = 1080

# Normalize each camera to pane size
[N:v] scale=960:1080:...,pad=960:1080:... [paneA]
[M:v] scale=960:1080:...,pad=960:1080:... [paneB]

# Stack side-by-side
[paneA][paneB] xstack=inputs=2:layout=0_0|w0_0:fill=black [output]
#                                        ↑
#                           Layout: Left(0,0) | Right(w0,0)
```

**Stacked (2 cameras):**

```
# Pane dimensions
pane_w = 1920
pane_h = 1080 / 2 = 540

# Normalize each camera
[N:v] scale=1920:540:...,pad=1920:540:... [paneA]
[M:v] scale=1920:540:...,pad=1920:540:... [paneB]

# Stack vertically
[paneA][paneB] xstack=inputs=2:layout=0_0|0_h0:fill=black [output]
#                                        ↑
#                           Layout: Top(0,0) | Bottom(0,h0)
```

---

### **Argv Length Estimation**

**Formula:**

```python
def estimate_argv_length(clips, settings, with_hwaccel=False):
    # Base command
    base = len(ffmpeg_path) + 50  # -y, -filter_complex_script, etc.

    # Encoding options
    encoding = 150  # NVENC settings

    # Count inputs
    inputs = 0
    path_length = 0
    for clip in clips:
        inputs += 1
        path_length += len(str(clip.path))

    # Per-input overhead
    if with_hwaccel:
        # -hwaccel cuda -hwaccel_output_format cuda -ss X -t X -i <path>
        per_input = 75  # chars (not including path)
    else:
        # -ss X -t X -i <path>
        per_input = 30  # chars (not including path)

    flags = inputs * per_input

    # Total
    total = base + encoding + flags + path_length + (inputs * 2)  # spaces

    return total
```

**Example Calculation (195 files):**

```
Base:     200 chars
Encoding: 150 chars
Inputs:   301 (195 single + 106 from overlaps)
Paths:    301 × 30 chars = 9,030 chars
Flags:    301 × 30 = 9,030 chars
Spaces:   301 × 2 = 602 chars

TOTAL:    200 + 150 + 9,030 + 9,030 + 602 = 19,012 chars
```

**With Hardware Decode:**

```
Flags:    301 × 75 = 22,575 chars (instead of 9,030)

TOTAL:    200 + 150 + 9,030 + 22,575 + 602 = 32,557 chars
         ↑
         Dangerously close to 32,768 limit!
```

---

## Performance Optimization

### **Benchmarks**

| Dataset | Files | Duration | Render Time | Speed | GPU Util |
|---------|-------|----------|-------------|-------|----------|
| Small | 50 | 1hr 15min | 5 min | 15x | 45% |
| Medium | 195 | 3hr 0min | 12 min | 15x | 48% |
| Large | 336 | 5hr 30min | 22 min | 15x | 50% |

**Notes:**
- GPU utilization is NVENC encode only (CPU decode)
- Hardware decode disabled due to filter compatibility
- Batch mode adds ~10% overhead (from concat operation)

---

### **Optimization Strategies**

#### **1. Single-Pass Metadata Extraction**

**Before:**
```python
# Parse phase
for file in files:
    smpte = parse_filename(file)

# Validation phase (separate ffprobe call!)
for file in files:
    metadata = extract_metadata(file)
```

**After (50% faster):**
```python
# Combined phase (one ffprobe call)
for file in files:
    smpte = parse_filename(file)
    metadata = extract_metadata(file)  # Same pass!
    end_time = start_time + metadata.duration
```

---

#### **2. Filter Script File**

**Before (hits Windows limit at ~20 files):**
```bash
ffmpeg ... -filter_complex "[0:v]scale=...[v0];[1:v]scale=...[v1];..."
                          ↑
                  Entire filtergraph in command line
```

**After (scales to 1000+ files):**
```bash
ffmpeg ... -filter_complex_script /tmp/filter.fffilter
                                  ↑
                      Filtergraph in temp file (no size limit)
```

---

#### **3. NVENC Encoding Settings**

**Optimized for forensic CCTV:**

```python
"-c:v", "hevc_nvenc",    # H.265 encoder (better compression than H.264)
"-preset", "p5",         # Performance preset 5 (balanced)
"-cq", "20",             # Constant quality 20 (visually lossless)
"-rc", "vbr_hq",         # Variable bitrate (high quality)
"-b:v", "0",             # No max bitrate (quality-based)
"-g", "60",              # GOP size: 60 frames (2 seconds @ 30fps)
"-bf", "2",              # B-frames: 2 (compression efficiency)
"-spatial-aq", "1",      # Spatial AQ (improves quality in complex areas)
"-temporal-aq", "1",     # Temporal AQ (improves motion quality)
```

**Why these settings:**
- **CQ 20** balances quality and file size (visually indistinguishable from lossless)
- **VBR HQ** allows variable bitrate for consistent quality
- **GOP 60** enables seeking every 2 seconds
- **Spatial/Temporal AQ** critical for CCTV (often low-light, motion blur)

---

### **Memory Management**

**Temp File Cleanup:**

```python
filter_script_path = None
try:
    # Render operation
    command, filter_script_path = self.builder.build_command(...)
    subprocess.run(command)
    return Result.success(output_path)
finally:
    # Always clean up, even on error
    if filter_script_path:
        try:
            os.unlink(filter_script_path)
        except OSError as e:
            logger.warning(f"Could not remove temp file: {e}")
```

**Batch Temp Directory:**

```python
temp_dir = Path(tempfile.mkdtemp(prefix="timeline_batch_"))
batch_files = []

try:
    # Render batches
    for i, batch in enumerate(batches):
        batch_output = temp_dir / f"batch_{i:03d}.mp4"
        render_batch(batch, batch_output)
        batch_files.append(batch_output)

    # Concatenate
    concat_result = concatenate_batches(batch_files, final_output)

finally:
    # Cleanup (always runs)
    for batch_file in batch_files:
        if batch_file.exists():
            batch_file.unlink()

    if temp_dir.exists():
        temp_dir.rmdir()
```

---

## Testing & Validation

### **Unit Tests**

**Key Test Cases:**

```python
def test_atomic_interval_construction():
    """Test atomic interval algorithm with overlaps and gaps."""
    clips = [
        Clip(path="A.mp4", start=0, end=10, cam_id="A02"),
        Clip(path="B.mp4", start=5, end=15, cam_id="A04"),
    ]

    intervals = builder._build_atomic_intervals(clips)

    assert len(intervals) == 3
    assert intervals[0].t0 == 0 and intervals[0].t1 == 5
    assert len(intervals[0].active) == 1  # Only A

    assert intervals[1].t0 == 5 and intervals[1].t1 == 10
    assert len(intervals[1].active) == 2  # A and B

    assert intervals[2].t0 == 10 and intervals[2].t1 == 15
    assert len(intervals[2].active) == 1  # Only B


def test_argv_length_estimation():
    """Test argv length estimation accuracy."""
    clips = [Clip(...) for _ in range(195)]

    estimated = builder.estimate_argv_length(clips, settings, with_hwaccel=False)

    # Build actual command and measure
    argv, _ = builder.build_command(clips, settings, output_path)
    actual = len(' '.join(argv))

    # Estimate should be within 5% of actual
    assert abs(estimated - actual) / actual < 0.05


def test_batch_splitting():
    """Test batch splitting stays under limits."""
    clips = [Clip(...) for _ in range(336)]

    batches = service._split_clips_into_batches(clips, settings)

    assert len(batches) == 3
    assert len(batches[0]) == 150
    assert len(batches[1]) == 150
    assert len(batches[2]) == 36

    # Verify each batch stays under limit
    for batch in batches:
        estimated = builder.estimate_argv_length(batch, settings)
        assert estimated < builder.SAFE_ARGV_THRESHOLD
```

---

### **Integration Tests**

**Real-World Scenarios:**

```python
def test_single_camera_no_gaps():
    """Test 50 sequential clips from one camera."""
    files = generate_test_files(count=50, cameras=["A02"], gaps=False)

    result = controller.parse_and_render(files, settings)

    assert result.success
    assert result.value.exists()
    assert get_video_duration(result.value) == approx(expected_duration)


def test_two_cameras_with_gaps():
    """Test 195 files with gaps and overlaps."""
    files = generate_test_files(
        count=195,
        cameras=["A02", "A04"],
        gaps=True,
        overlaps=True
    )

    result = controller.parse_and_render(files, settings)

    assert result.success
    # Verify gap slates present
    assert count_slates(result.value) == expected_gap_count
    # Verify split-screens present
    assert count_split_screens(result.value) == expected_overlap_count


def test_large_dataset_auto_fallback():
    """Test 336 files triggers auto-fallback."""
    files = generate_test_files(count=336, cameras=["A02", "A04"])

    with LogCapture() as logs:
        result = controller.parse_and_render(files, settings)

    assert result.success
    # Verify auto-fallback was triggered
    assert "Auto-enabling batch rendering" in logs.output
    # Verify batch mode used
    assert "Rendering batch 1 of 3" in logs.output
```

---

### **Performance Testing**

**Benchmarking Script:**

```python
import time
from pathlib import Path

def benchmark_rendering(file_count: int, cameras: int):
    """Benchmark rendering performance."""

    # Generate test dataset
    files = generate_test_files(count=file_count, cameras=[f"A{i:02d}" for i in range(cameras)])

    # Parse filenames
    start = time.time()
    parse_result = controller.parse_files(files, settings)
    parse_time = time.time() - start

    # Render timeline
    start = time.time()
    render_result = controller.render_timeline(parse_result.value, render_settings)
    render_time = time.time() - start

    # Calculate metrics
    output_duration = get_video_duration(render_result.value)
    output_size = render_result.value.stat().st_size / (1024 * 1024)  # MB

    print(f"""
    Benchmark Results:
    ─────────────────────────────────────
    Files:           {file_count}
    Cameras:         {cameras}
    Parse Time:      {parse_time:.1f}s
    Render Time:     {render_time:.1f}s
    Output Duration: {output_duration:.1f}s
    Output Size:     {output_size:.1f} MB
    Speed:           {output_duration / render_time:.1f}x realtime
    """)


# Run benchmarks
benchmark_rendering(50, 1)    # Small dataset
benchmark_rendering(195, 2)   # Medium dataset
benchmark_rendering(336, 2)   # Large dataset
```

---

## Deployment Considerations

### **System Requirements**

**Minimum:**
- CPU: Intel i5 / AMD Ryzen 5 (4 cores)
- RAM: 8 GB
- GPU: NVIDIA GTX 1050 (optional, for NVENC)
- Disk: 50 GB free (temp files + output)

**Recommended:**
- CPU: Intel i7 / AMD Ryzen 7 (8 cores)
- RAM: 16 GB
- GPU: NVIDIA RTX 3060 or better (for NVENC)
- Disk: 200 GB free (large investigations)

---

### **FFmpeg Binary Management**

**Binary Detection:**

```python
class BinaryManager:
    """Manage FFmpeg binary detection and validation."""

    def get_ffmpeg_path(self) -> Optional[Path]:
        """
        Locate FFmpeg binary.

        Search order:
        1. ./bin/ffmpeg.exe (bundled)
        2. C:\ffmpeg\bin\ffmpeg.exe (common install)
        3. System PATH

        Returns:
            Path to FFmpeg or None if not found
        """
        # Check bundled
        bundled = Path(__file__).parent.parent / "bin" / "ffmpeg.exe"
        if bundled.exists():
            return bundled

        # Check common install
        common = Path("C:/ffmpeg/bin/ffmpeg.exe")
        if common.exists():
            return common

        # Check PATH
        import shutil
        system = shutil.which("ffmpeg")
        if system:
            return Path(system)

        return None
```

---

### **Error Handling Strategy**

**Layered Error Handling:**

```python
# Layer 1: Technical errors (for logs)
class FileOperationError(FSAError):
    """Technical error with full context."""
    def __init__(
        self,
        message: str,                  # Technical details
        user_message: str,             # User-friendly explanation
        context: Optional[Dict] = None # Additional data
    ):
        self.message = message
        self.user_message = user_message
        self.context = context or {}


# Layer 2: Result objects (for control flow)
def operation() -> Result[OutputType]:
    try:
        # ... operation
        return Result.success(data)
    except Exception as e:
        error = FileOperationError(
            f"FFmpeg failed: {e}",
            user_message="Video rendering failed. Check log for details.",
            context={"returncode": process.returncode, "stderr": stderr}
        )
        return Result.error(error)


# Layer 3: UI error display
result = controller.render_timeline(videos, settings)
if not result.success:
    QMessageBox.critical(
        self,
        "Rendering Failed",
        result.error.user_message  # User-friendly message only
    )
    logger.error(
        result.error.message,      # Technical details to log
        extra=result.error.context
    )
```

---

## Future Enhancements

### **Planned Features**

1. **GPU Filter Chain**
   - Implement `scale_cuda` for hardware decode
   - Keep frames in GPU memory entire pipeline
   - Expected: 20-30% performance improvement

2. **Smart Batch Splitting**
   - Split at gap boundaries instead of arbitrary counts
   - Preserve natural scene breaks
   - Reduces artifacts at batch boundaries

3. **Progress Estimation**
   - Parse FFmpeg stderr for actual progress
   - Show time remaining instead of percentage
   - More accurate completion estimates

4. **Advanced Split-Screen Layouts**
   - Support 3-4 camera grids (2x2)
   - Customizable camera positions
   - Picture-in-picture mode

5. **Export Formats**
   - MP4 (current)
   - WebM (for web playback)
   - Blu-ray compatible (M2TS)
   - Frame sequence (PNG/JPEG)

---

### **Known Limitations**

1. **Hardware Decode Disabled**
   - GPU/CPU filter compatibility issues
   - Requires filter chain refactor
   - Workaround: Use CPU decode (still fast)

2. **Batch Overhead**
   - ~10-15% additional render time
   - Required for large datasets
   - Concat operation is trivial but adds I/O

3. **Windows-Specific Argv Limits**
   - 32,768 character hard limit
   - Auto-fallback mitigates
   - Linux/Mac have much higher limits

4. **CCTV-Specific Assumptions**
   - Assumes H.264/H.265 codecs
   - Assumes 16:9 or 4:3 aspect ratios
   - May not work with exotic formats

---

## Appendix: Data Models

### **VideoMetadata**

```python
@dataclass
class VideoMetadata:
    """Comprehensive video metadata for timeline processing."""

    # File information
    file_path: Path
    filename: str

    # Timing (ISO 8601 format)
    smpte_timecode: str              # HH:MM:SS:FF (start time)
    start_time: Optional[str] = None # ISO 8601 string
    end_time: Optional[str] = None   # ISO 8601 string
    frame_rate: float = 30.0         # Native FPS
    duration_seconds: float = 0.0    # Real-world duration
    duration_frames: int = 0         # Duration in frames

    # Video specs
    width: int = 1920
    height: int = 1080
    codec: str = "h264"
    pixel_format: str = "yuv420p"
    video_bitrate: int = 5000000

    # Camera organization
    camera_path: str = ""            # e.g., "A02" or "Location/Camera"

    # Timeline position (computed)
    start_frame: int = 0
    end_frame: int = 0
    duration_seq: int = 0
```

---

### **RenderSettings**

```python
@dataclass
class RenderSettings:
    """Settings for timeline video rendering."""

    # Output video settings
    output_resolution: tuple[int, int] = (1920, 1080)
    output_fps: float = 30.0
    output_codec: str = "hevc_nvenc"
    output_pixel_format: str = "yuv420p"
    video_bitrate: str = "5M"

    # Slate settings
    slate_duration_seconds: int = 5
    slate_background_color: str = "#1a1a1a"
    slate_text_color: str = "white"
    slate_font_size: int = 48

    # Multi-camera settings
    split_mode: Literal["side_by_side", "stacked"] = "side_by_side"
    split_alignment: Literal["top", "center", "bottom"] = "center"

    # Three-tier performance system
    use_hardware_decode: bool = False  # Tier 1: GPU decode
    use_batch_rendering: bool = False  # Tier 2: Batch mode
    batch_size: int = 150              # Clips per batch

    # Output paths
    output_directory: Path = Path(".")
    output_filename: str = "timeline.mp4"
```

---

## Glossary

**Atomic Interval** - A time interval where the set of active cameras remains constant. Forms the basis of the timeline construction algorithm.

**Argv** - Argument vector; the list of command-line arguments passed to a program. Windows limits this to 32,768 characters.

**Batch Rendering** - Process of splitting large datasets into smaller groups, rendering each separately, then concatenating the results.

**CCTV** - Closed-Circuit Television; security camera systems that record video continuously or on motion detection.

**FFmpeg** - Industry-standard open-source tool for video processing, encoding, decoding, and filtering.

**FFprobe** - Companion tool to FFmpeg for extracting metadata from media files.

**Filtergraph** - FFmpeg's internal representation of video/audio processing pipelines. Consists of filters connected by labeled streams.

**GPU Encoding** - Using graphics card (GPU) dedicated hardware for video encoding instead of CPU. Much faster than software encoding.

**NVENC** - NVIDIA Encoder; hardware video encoder built into NVIDIA GPUs. Supports H.264 and H.265 encoding at high speed.

**PTS** - Presentation Timestamp; indicates when a video frame should be displayed. Critical for synchronization.

**Result Object** - Design pattern where functions return a `Result[T]` type containing either a success value or an error, instead of throwing exceptions.

**SMPTE Timecode** - Society of Motion Picture and Television Engineers timecode format (HH:MM:SS:FF). Industry standard for frame-accurate timing.

**Split-Screen** - Video layout showing multiple camera feeds simultaneously, either side-by-side or stacked vertically.

**Slate** - Static video frame with text overlay, used to indicate gaps in coverage or provide context information.

**Timeline** - Chronological arrangement of video clips, gaps, and overlaps representing the complete time span of an investigation.

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-10-09 | Forensic Dev Team | Initial release |

---

**End of Documentation**

*For questions, issues, or feature requests, contact the development team or refer to the project repository.*
