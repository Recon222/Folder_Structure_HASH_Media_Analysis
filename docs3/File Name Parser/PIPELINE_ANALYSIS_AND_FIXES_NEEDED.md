# Timeline Pipeline Analysis & Required Fixes

**Date:** 2025-10-08
**Analysis Type:** Deep Dive - Current Implementation vs GPT-5 Plan
**Status:** 🔴 CRITICAL ISSUES IDENTIFIED

---

## Executive Summary

The implementation has **fundamental architectural mismatches** between the old frame-based timeline calculator and the new GPT-5 single-pass approach. This is causing:

1. ❌ False overlap detection (detecting overlaps for sequential motion clips from same camera)
2. ❌ Incorrect segment counts (way higher than clip count due to atomic interval over-segmentation)
3. ❌ Rendering failures (likely from mismatched data being passed to FFmpeg builder)

**Root Cause:** The codebase has **TWO COMPETING PIPELINE SYSTEMS** running simultaneously:
- **Old System:** `TimelineCalculatorService` with frame-based positioning, gap detection, overlap detection, segment building
- **New System:** `FFmpegTimelineBuilder` with atomic interval approach, expecting simple Clip list

The old system is **pre-processing** the timeline before passing to the new system, causing data corruption.

---

## Current Pipeline Flow (BROKEN)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. FilenameParserTab: User Selects Files                    │
│    - Stores: self.selected_files (List[Path])              │
│    - Stores: self.last_parsing_results (List[Dict])        │
│      Format: {'filename', 'smpte_timecode', 'source_file'}  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. TimelineController.validate_videos()                     │
│    - Input: List[Path], List[Dict] (parsing results)       │
│    - Uses: VideoMetadataExtractor to get duration/fps      │
│    - Converts SMPTE → ISO8601 using _smpte_to_iso8601()   │
│    - Calculates end_time = start_time + duration           │
│    - Output: List[VideoMetadata] with:                     │
│      • smpte_timecode (HH:MM:SS:FF)                        │
│      • start_time (ISO8601 string) ✅                       │
│      • end_time (ISO8601 string) ✅                         │
│      • duration_seconds (float from ffprobe) ✅             │
│      • frame_rate (float from ffprobe) ✅                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. TimelineController.calculate_timeline() ⚠️ PROBLEM      │
│    - Calls: TimelineCalculatorService.calculate_timeline() │
│    - This is OLD FRAME-BASED SYSTEM!!!                      │
│    - Does:                                                   │
│      1. Position videos on sequence timeline (frame nums)   │
│      2. Detect gaps (range merging)                         │
│      3. ❌ Detect overlaps (_detect_overlaps) BUG!          │
│      4. Build segments (video/gap/overlap)                  │
│    - Output: Timeline object with:                          │
│      • videos (List[VideoMetadata]) - now with start_frame/ │
│        end_frame added                                       │
│      • gaps (List[Gap])                                     │
│      • overlaps (List[OverlapGroup]) ← FALSE POSITIVES!     │
│      • segments (List[TimelineSegment]) ← OVER-SEGMENTED!   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. TimelineController.start_rendering()                     │
│    - Passes: Timeline object (with corrupt data)            │
│    - Creates: TimelineRenderWorker                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. MulticamRendererService.render_timeline() ⚠️ MISMATCH   │
│    - OLD signature: render_timeline(timeline, settings)     │
│    - NEW signature: render_timeline(videos, settings)       │
│    - Expects: List[VideoMetadata] but receives Timeline!    │
│    - Does:                                                   │
│      1. _videos_to_clips() - converts to Clip objects       │
│      2. Calls FFmpegTimelineBuilder.build_command()         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. FFmpegTimelineBuilder.build_command() 🔁 RE-PROCESSING  │
│    - Receives: List[Clip] with ISO8601 times                │
│    - Does:                                                   │
│      1. _normalize_clip_times() - convert to seconds        │
│      2. _build_atomic_intervals() - DUPLICATE WORK!         │
│      3. _segments_from_intervals() - DUPLICATE OVERLAP!     │
│      4. _emit_ffmpeg_argv() - generate command              │
└─────────────────────────────────────────────────────────────┘
```

---

## Critical Bug #1: False Overlap Detection

### Location
`filename_parser/services/timeline_calculator_service.py:_detect_overlaps()`

### The Problem

```python
def _detect_overlaps(self, videos: List[VideoMetadata], sequence_fps: float):
    """Detect overlaps using interval sweep algorithm"""

    # For each interval between time points
    for i in range(len(sorted_time_points) - 1):
        interval_start = sorted_time_points[i]
        interval_end = sorted_time_points[i + 1]

        # Find clips active in this interval
        active_clips = []
        for video in videos:
            if video.start_frame <= interval_start and video.end_frame > interval_start:
                active_clips.append(video)

        # ❌ BUG: If multiple clips active, it's an overlap
        if len(active_clips) > 1:
            # Creates OverlapGroup even if clips are from SAME camera!
            overlap_groups.append(...)
```

### Why It's Wrong

The algorithm checks if **multiple clips** are active at a given time, but **NEVER checks if they're from different cameras**.

**Example Scenario:**
- Camera A has motion detection clips:
  - `A02_0001.mp4`: 13:00:00 → 13:00:30 (30 seconds)
  - `A02_0002.mp4`: 13:00:35 → 13:01:05 (30 seconds)
  - `A02_0003.mp4`: 13:01:10 → 13:01:40 (30 seconds)

**What Happens:**
1. Timeline calculator positions these sequentially (correct)
2. `_detect_overlaps()` processes intervals between time points
3. At `t=13:00:30`, clip 1 ends. Next time point is `t=13:00:35`
4. Between these points, NO clips active (5 second gap)
5. **BUT**: The algorithm might incorrectly identify overlaps due to frame boundary rounding errors

**Real Issue:** The algorithm was designed for multicam timelines where overlaps are EXPECTED (cameras recording simultaneously). For single-camera motion detection footage, this creates false positives.

### What GPT-5 Does Differently

GPT-5's approach handles this correctly because:
1. **Clips are pre-grouped by camera** (`cam_id` field)
2. Overlaps only occur when clips from **DIFFERENT cameras** have overlapping time ranges
3. **Gaps are implicit** - just missing time ranges, not explicitly detected

---

## Critical Bug #2: Over-Segmentation

### Location
`filename_parser/services/timeline_calculator_service.py:_build_segments()`

### The Problem

```python
def _build_segments(self, videos, gaps, overlaps):
    """Build segments with overlap handling"""

    segments = []
    processed_overlaps = set()

    for video in videos:
        for overlap in overlaps:
            # ❌ Video is in overlap if it's active during overlap period
            if (video.start_frame <= overlap.start_frame and
                video.end_frame > overlap.start_frame):

                # Create overlap segment
                segments.append(overlap_segment)

                # ❌ Split video into pre-overlap, overlap, post-overlap
                if video.start_frame < overlap.start_frame:
                    segments.append(pre_segment)  # Before overlap

                if video.end_frame > overlap.end_frame:
                    segments.append(post_segment)  # After overlap
```

### Why It's Wrong

For a simple timeline with 10 clips from one camera:
1. False overlap detection creates ~8 "overlaps" (due to frame rounding)
2. Each video gets split into 3 segments (pre-overlap, overlap, post-overlap)
3. **Result:** 10 clips → 30+ segments!

### What GPT-5 Does

GPT-5 doesn't "build segments" at this stage. It just:
1. Passes raw clip list to `_build_atomic_intervals()`
2. Atomic intervals are created from time boundaries
3. Segments are classified as gap/single/overlap based on **active clip count at that moment**

The key difference: **No pre-processing, no splitting, just direct interval analysis.**

---

## Critical Bug #3: Signature Mismatch

### Location
`filename_parser/services/multicam_renderer_service.py:render_timeline()`

### The Problem

**OLD Signature (still being called):**
```python
def render_timeline(
    self,
    timeline: Timeline,  # ← Expects Timeline object
    settings: RenderSettings,
    progress_callback
):
```

**NEW Implementation:**
```python
def render_timeline(
    self,
    videos: List[VideoMetadata],  # ← Expects List[VideoMetadata]
    settings: RenderSettings,
    progress_callback
):
    clips = self._videos_to_clips(videos)
    command = self.builder.build_command(clips, settings, output_path)
```

**What's Being Called:**
```python
# In TimelineRenderWorker
result = self.renderer_service.render_timeline(
    self.timeline,  # ← Timeline object (WRONG!)
    self.settings,
    progress_callback=self._on_progress
)
```

**Result:** Either:
1. Python type error (if caught by type checker)
2. Runtime error when trying to iterate `Timeline` as `List[VideoMetadata]`
3. AttributeError when accessing `video.start_time` on Timeline object

---

## Data Flow Issues - Metadata Extraction

### When Metadata is Extracted

**Current Flow:**
1. **Filename Parsing** (Phase 1 - User clicks "Parse Filenames")
   - Extracts: SMPTE timecode from filename
   - Stores: `self.last_parsing_results` (just filename + timecode)
   - **Does NOT extract:** duration, fps, resolution

2. **Timeline Validation** (Phase 2 - User clicks "Generate Timeline")
   - Calls: `VideoMetadataExtractor.extract_metadata()` for EACH file
   - Extracts: duration, fps, resolution, codecs via ffprobe
   - Calculates: start_time (ISO8601), end_time (ISO8601)

### The Problem

**Metadata extraction happens twice:**
1. Once during parsing (just timecode)
2. Again during timeline validation (full metadata)

**This causes:**
- Slow timeline generation (re-probing all files)
- CSV export doesn't have duration/fps/end_time
- User can't preview timeline data before rendering

### Your Proposed Solution ✅

> "Move the reporting of all metadata to CSV extraction...all of metadata extraction and calculation should be done just after parsing the file names"

**This is CORRECT.** Here's why:

1. **Single Extraction Point:** Extract everything once during parsing
2. **Rich CSV Export:** Include all metadata (timecode, duration, fps, start_time, end_time)
3. **JSON Timeline Export:** Provide GPT-5-compatible JSON for review/editing
4. **Faster Timeline Generation:** No re-probing during rendering

---

## Correct Pipeline (GPT-5 Approach)

### Simplified Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Selects Files                                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Parse Filenames + Extract ALL Metadata (SINGLE PASS)     │
│    For each file:                                            │
│      - Parse filename → SMPTE timecode                      │
│      - Run ffprobe → duration, fps, resolution              │
│      - Calculate:                                            │
│        • start_time = SMPTE as ISO8601                      │
│        • end_time = start_time + duration                   │
│        • camera_id = extract from path/filename             │
│    Output: List[VideoMetadata] with EVERYTHING populated    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Store Results + Export Options                           │
│    - Store: self.video_metadata_list                        │
│    - Enable:                                                 │
│      • Export CSV (with duration, fps, end_time)            │
│      • Export JSON Timeline (GPT-5 format)                  │
│      • Generate Timeline Video button                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. User Reviews CSV/JSON (Optional)                         │
│    - Can see timeline structure before rendering            │
│    - Can edit JSON externally if needed                     │
│    - Can import edited JSON back                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. User Clicks "Generate Timeline Video"                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. MulticamRendererService.render_timeline()                │
│    - Input: List[VideoMetadata] (already complete)          │
│    - Does:                                                   │
│      1. Convert to Clip objects                             │
│      2. Call FFmpegTimelineBuilder.build_command()          │
│      3. Execute FFmpeg                                       │
│    - NO timeline calculation, NO gap detection here!        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. FFmpegTimelineBuilder.build_command()                    │
│    - Input: List[Clip] with ISO8601 times                  │
│    - Does:                                                   │
│      1. Normalize times to seconds                          │
│      2. Build atomic intervals (gaps/overlaps auto-detected)│
│      3. Create segments (slate/single/overlap)              │
│      4. Generate single FFmpeg command                       │
└─────────────────────────────────────────────────────────────┘
```

### Key Differences

| Aspect | Current (Broken) | Correct (GPT-5) |
|--------|-----------------|-----------------|
| **Metadata Extraction** | Twice (parse + validate) | Once (during parse) |
| **Timeline Calculation** | Separate service (frame-based) | Built into FFmpeg builder (time-based) |
| **Gap Detection** | Pre-processed by calculator | Implicit in atomic intervals |
| **Overlap Detection** | Pre-processed (buggy) | Automatic in atomic intervals |
| **Segment Building** | Pre-processed (over-segmented) | Generated by builder from intervals |
| **Data Passed to Renderer** | Timeline object (complex) | List[VideoMetadata] (simple) |

---

## Required Fixes

### Fix #1: Consolidate Metadata Extraction ⭐ PRIORITY 1

**Goal:** Extract all metadata once during filename parsing.

**Files to Modify:**
- `filename_parser/services/batch_processor_service.py`
- `filename_parser/models/processing_result.py`
- `filename_parser/ui/filename_parser_tab.py`

**Changes:**

1. **Enhance ProcessingResult model:**
```python
@dataclass
class ProcessingResult:
    """Result from parsing a single file - now includes full metadata"""

    # Existing fields
    success: bool
    filename: str
    source_file: Path
    smpte_timecode: Optional[str] = None

    # NEW: Full video metadata
    duration_seconds: float = 0.0
    frame_rate: float = 0.0
    start_time: Optional[str] = None  # ISO8601
    end_time: Optional[str] = None    # ISO8601
    camera_id: Optional[str] = None
    width: int = 0
    height: int = 0
    codec: str = ""

    # Errors
    error_message: str = ""
```

2. **Modify BatchProcessorService to extract metadata:**
```python
def process_file(self, file_path: Path):
    """Process single file - extract timecode AND metadata"""

    # Step 1: Parse filename for timecode
    parse_result = self.parser.parse_filename(filename)

    # Step 2: Extract video metadata via ffprobe
    metadata = self.metadata_extractor.extract_metadata(file_path)

    # Step 3: Calculate start_time and end_time
    start_time = self._smpte_to_iso8601(parse_result.smpte_timecode, metadata.frame_rate)
    end_time = self._calculate_end_time(start_time, metadata.duration_seconds)

    # Step 4: Extract camera_id
    camera_id = self._extract_camera_id(file_path)

    # Return complete result
    return ProcessingResult(
        success=True,
        filename=filename,
        source_file=file_path,
        smpte_timecode=parse_result.smpte_timecode,
        duration_seconds=metadata.duration_seconds,
        frame_rate=metadata.frame_rate,
        start_time=start_time,
        end_time=end_time,
        camera_id=camera_id,
        width=metadata.width,
        height=metadata.height,
        codec=metadata.codec_name
    )
```

3. **Store complete results in UI:**
```python
# In FilenameParserTab
def _on_processing_complete(self, result: Result):
    if result.success:
        stats = result.value

        # Store COMPLETE results (not just timecodes)
        self.video_metadata_list = []

        for item in stats.results:
            if item.success:
                metadata = VideoMetadata(
                    file_path=item.source_file,
                    filename=item.filename,
                    smpte_timecode=item.smpte_timecode,
                    start_time=item.start_time,
                    end_time=item.end_time,
                    frame_rate=item.frame_rate,
                    duration_seconds=item.duration_seconds,
                    camera_path=item.camera_id,
                    width=item.width,
                    height=item.height,
                    codec=item.codec
                )
                self.video_metadata_list.append(metadata)
```

---

### Fix #2: Remove TimelineCalculatorService from Rendering Path ⭐ PRIORITY 1

**Goal:** Stop using old frame-based timeline calculation for rendering.

**Files to Modify:**
- `filename_parser/controllers/timeline_controller.py`
- `filename_parser/ui/filename_parser_tab.py`

**Changes:**

1. **Remove calculate_timeline() call:**
```python
# OLD (in FilenameParserTab._start_timeline_rendering)
timeline_result = self.timeline_controller.calculate_timeline(
    videos=video_metadata_list,
    sequence_fps=self.timeline_fps_spin.value(),
    min_gap_seconds=self.timeline_min_gap_spin.value()
)
timeline = timeline_result.value

# NEW
# Don't call calculate_timeline() at all!
# Just pass video_metadata_list directly to renderer
```

2. **Simplify TimelineController:**
```python
def start_rendering(
    self,
    videos: List[VideoMetadata],  # ← Direct input
    settings: RenderSettings
) -> Result[TimelineRenderWorker]:
    """Start rendering with video metadata list"""

    # Skip timeline calculation - let FFmpegTimelineBuilder handle it
    worker = TimelineRenderWorker(videos, settings, self.renderer_service)
    worker.start()
    return Result.success(worker)
```

3. **Update Worker signature:**
```python
class TimelineRenderWorker(QThread):
    def __init__(
        self,
        videos: List[VideoMetadata],  # ← Not Timeline object
        settings: RenderSettings,
        renderer_service
    ):
        self.videos = videos
        self.settings = settings
        self.renderer_service = renderer_service

    def run(self):
        result = self.renderer_service.render_timeline(
            self.videos,  # ← Pass list directly
            self.settings,
            progress_callback=self._on_progress
        )
```

---

### Fix #3: Enhanced CSV Export ⭐ PRIORITY 2

**Goal:** Export complete metadata including duration, end_time, camera_id.

**File to Modify:**
- `filename_parser/services/csv_export_service.py`

**Changes:**

```python
def export_results(self, results: List[ProcessingResult], output_path: Path):
    """Export parsing results with FULL metadata to CSV"""

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Enhanced header
        writer.writerow([
            'Filename',
            'Source File',
            'Camera ID',
            'SMPTE Timecode',
            'Start Time (ISO8601)',
            'End Time (ISO8601)',
            'Duration (seconds)',
            'Frame Rate',
            'Resolution',
            'Codec',
            'Status'
        ])

        for result in results:
            writer.writerow([
                result.filename,
                str(result.source_file),
                result.camera_id or 'Unknown',
                result.smpte_timecode or 'N/A',
                result.start_time or 'N/A',
                result.end_time or 'N/A',
                f"{result.duration_seconds:.2f}",
                f"{result.frame_rate:.2f}",
                f"{result.width}x{result.height}",
                result.codec,
                'Success' if result.success else f'Failed: {result.error_message}'
            ])
```

---

### Fix #4: JSON Timeline Export ⭐ PRIORITY 2

**Goal:** Export GPT-5-compatible JSON for human review and editing.

**New File:**
- `filename_parser/services/json_timeline_export_service.py`

**Implementation:**

```python
"""
JSON Timeline Export Service

Exports timeline data in GPT-5-compatible format.
Allows users to review, edit, and re-import timeline data.
"""

import json
from pathlib import Path
from typing import List
from datetime import datetime

from filename_parser.models.timeline_models import VideoMetadata
from core.result_types import Result
from core.exceptions import FileOperationError


class JSONTimelineExportService:
    """Export timeline data as GPT-5-compatible JSON"""

    def export_timeline(
        self,
        videos: List[VideoMetadata],
        output_path: Path
    ) -> Result[None]:
        """
        Export timeline as JSON array of clips.

        Format matches GPT-5 specification:
        [
          {
            "path": "D:\\path\\to\\video.mp4",
            "start": "2025-05-21T13:00:00",
            "end": "2025-05-21T13:00:30",
            "cam_id": "A02"
          },
          ...
        ]
        """
        try:
            clips = []

            for video in videos:
                clip = {
                    "path": str(video.file_path),
                    "start": video.start_time,
                    "end": video.end_time,
                    "cam_id": video.camera_path or "Unknown"
                }
                clips.append(clip)

            # Sort by start time for readability
            clips.sort(key=lambda c: c['start'])

            # Write JSON
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(clips, f, indent=2)

            return Result.success(None)

        except Exception as e:
            return Result.error(
                FileOperationError(
                    f"Failed to export JSON: {e}",
                    user_message="Could not export timeline JSON"
                )
            )

    def import_timeline(self, json_path: Path) -> Result[List[VideoMetadata]]:
        """Import timeline from JSON (for advanced users)"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                clips = json.load(f)

            videos = []
            for clip in clips:
                # Convert back to VideoMetadata
                # (Implementation depends on needs)
                pass

            return Result.success(videos)

        except Exception as e:
            return Result.error(
                FileOperationError(
                    f"Failed to import JSON: {e}",
                    user_message="Could not import timeline JSON"
                )
            )
```

**UI Integration:**

```python
# In FilenameParserTab, add button to export layout
self.export_json_timeline_btn = QPushButton("📄 Export Timeline JSON")
self.export_json_timeline_btn.clicked.connect(self._export_json_timeline)
self.export_json_timeline_btn.setEnabled(False)

def _export_json_timeline(self):
    """Export timeline data as JSON"""
    if not self.video_metadata_list:
        return

    file_path, _ = QFileDialog.getSaveFileName(
        self,
        "Export Timeline JSON",
        f"timeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        "JSON Files (*.json)"
    )

    if file_path:
        result = self.json_export_service.export_timeline(
            self.video_metadata_list,
            Path(file_path)
        )

        if result.success:
            self._log("SUCCESS", f"Timeline JSON exported: {file_path}")
        else:
            self._log("ERROR", f"Export failed: {result.error.user_message}")
```

---

### Fix #5: Camera ID Extraction ⭐ PRIORITY 3

**Goal:** Intelligently extract camera identifier from path or filename.

**Location:** Multiple services need this

**Implementation:**

```python
def extract_camera_id(self, file_path: Path) -> str:
    """
    Extract camera identifier from path or filename.

    Strategies (in order):
    1. Check parent directory name (e.g., "A02", "Camera_1")
    2. Check filename prefix (e.g., "A02_20250521.mp4")
    3. Fall back to parent dir path

    Examples:
        D:/footage/A02/A02_file.mp4 → "A02"
        D:/footage/Camera_1/video.mp4 → "Camera_1"
        D:/footage/20250521/file.mp4 → "20250521" (date as camera)
    """
    # Strategy 1: Parent directory
    parent_name = file_path.parent.name

    # Check if parent looks like camera ID (2-4 chars, alphanumeric)
    if re.match(r'^[A-Z]\d{2,3}$', parent_name):
        return parent_name

    # Check if parent contains "Camera" or "Cam"
    if 'camera' in parent_name.lower() or 'cam' in parent_name.lower():
        return parent_name

    # Strategy 2: Filename prefix
    filename = file_path.stem

    # Check for pattern like "A02_" at start
    match = re.match(r'^([A-Z]\d{2,3})_', filename)
    if match:
        return match.group(1)

    # Strategy 3: Fall back to parent directory
    return parent_name
```

---

## File Structure Changes Summary

### Files to Delete/Deprecate
- ❌ `TimelineCalculatorService._detect_overlaps()` method
- ❌ `TimelineCalculatorService._build_segments()` method (old approach)
- Keep calculator for legacy compatibility but don't use in render path

### Files to Modify
1. ✏️ `ProcessingResult` model - add full metadata fields
2. ✏️ `BatchProcessorService` - extract metadata during parse
3. ✏️ `FilenameParserTab` - store complete VideoMetadata list
4. ✏️ `TimelineController` - remove calculate_timeline from render path
5. ✏️ `TimelineRenderWorker` - accept List[VideoMetadata] not Timeline
6. ✏️ `MulticamRendererService` - already correct signature, just wire it up
7. ✏️ `CSVExportService` - add metadata columns

### Files to Create
1. ➕ `JSONTimelineExportService` - GPT-5 format export/import
2. ➕ Helper functions for camera ID extraction

---

## Migration Strategy

### Phase 1: Quick Fixes (1-2 hours)
1. Fix signature mismatch in `TimelineRenderWorker`
2. Bypass `calculate_timeline()` call in render path
3. Test rendering with direct VideoMetadata list

### Phase 2: Metadata Consolidation (2-3 hours)
1. Enhance `ProcessingResult` model
2. Modify `BatchProcessorService` to extract full metadata
3. Update `FilenameParserTab` to store complete data
4. Test CSV export with new fields

### Phase 3: JSON Export (1 hour)
1. Implement `JSONTimelineExportService`
2. Add UI button for JSON export
3. Test export format matches GPT-5 spec

### Phase 4: Camera ID Extraction (1 hour)
1. Implement camera ID extraction logic
2. Integrate into batch processor
3. Test with various folder structures

### Phase 5: Cleanup (1 hour)
1. Remove old timeline calculation from render path
2. Add deprecation warnings
3. Update documentation

**Total Estimated Time:** 6-8 hours

---

## Testing Strategy

### Test Case 1: Single Camera, Sequential Clips
```
Camera A02:
  - Video 1: 13:00:00 → 13:00:30 (30s)
  - Video 2: 13:00:35 → 13:01:05 (30s, 5s gap before)
  - Video 3: 13:01:10 → 13:01:40 (30s, 5s gap before)

Expected:
  - 3 single-camera segments
  - 2 gap slates (5s each)
  - 0 overlaps
  - Total segments: 5
```

### Test Case 2: Two Cameras, No Overlap
```
Camera A02:
  - Video 1: 13:00:00 → 13:00:30
Camera A04:
  - Video 1: 13:01:00 → 13:01:30

Expected:
  - 2 single-camera segments
  - 1 gap slate (30s)
  - 0 overlaps
  - Total segments: 3
```

### Test Case 3: Two Cameras, With Overlap
```
Camera A02:
  - Video 1: 13:00:00 → 13:03:00 (3 min)
Camera A04:
  - Video 1: 13:00:10 → 13:03:10 (3 min, 10s offset)

Expected:
  - 1 single segment (A02 alone, 10s)
  - 1 overlap segment (both cameras, 2m 50s)
  - 1 single segment (A04 alone, 10s)
  - 0 gaps
  - Total segments: 3
```

---

## Validation Checklist

Before considering the fix complete, verify:

- [ ] Metadata extracted once during parsing (not twice)
- [ ] CSV export includes duration, end_time, camera_id
- [ ] JSON export produces GPT-5-compatible format
- [ ] Timeline rendering doesn't call `TimelineCalculatorService`
- [ ] Worker receives `List[VideoMetadata]`, not `Timeline`
- [ ] MulticamRendererService receives correct data type
- [ ] FFmpegTimelineBuilder gets `List[Clip]` with ISO8601 times
- [ ] Single camera sequential clips produce correct segment count
- [ ] No false overlap detection for same-camera clips
- [ ] Real overlaps (different cameras) detected correctly
- [ ] Gaps detected correctly (implicit from missing time ranges)
- [ ] FFmpeg command generation succeeds
- [ ] Video rendering produces output file

---

## Conclusion

The current implementation suffers from **architectural layer violation** - the old frame-based timeline calculator is pre-processing data that the new GPT-5 atomic interval approach is designed to handle internally.

**The fix is conceptually simple:**
1. Extract all metadata once (during parsing)
2. Pass complete VideoMetadata list directly to renderer
3. Let FFmpegTimelineBuilder do its atomic interval magic
4. Remove old timeline calculation from render path

**Benefits of this approach:**
- ✅ Single metadata extraction (faster)
- ✅ Rich CSV export (duration, end times, camera IDs)
- ✅ JSON timeline export (human-readable, editable)
- ✅ Correct overlap detection (only different cameras)
- ✅ Correct segment counts (atomic intervals, not over-segmented)
- ✅ Simpler code flow (fewer layers)
- ✅ Matches GPT-5 design exactly

The old `TimelineCalculatorService` can remain for backward compatibility or future enhancements, but it should **not be in the rendering path** when using the GPT-5 approach.
