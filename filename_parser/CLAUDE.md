# CLAUDE.md - Filename Parser Module

## Project Overview

**Filename Parser** - A self-contained PySide6 module for forensic video file analysis. Extracts SMPTE timecodes from filenames, detects frame rates, writes metadata with FFmpeg, and generates synchronized multicam timeline videos from CCTV/DVR footage.

**Status**: Production-ready modular feature integrated as a tab in the main HASH Media Analysis application.

## Working with the Project Architect

**IMPORTANT**: The project owner is a **non-coding architect** who provides high-level ideas and direction, but NOT detailed implementation guidance.

### Key Principles:

1. **Ideas are Starting Points, Not Final Answers**
   - Treat user suggestions as proposals to evaluate, not commands to blindly follow
   - User ideas may be architecturally sound OR misguided—your job is to determine which
   - **Challenge bad ideas respectfully** with technical reasoning

2. **Professional Objectivity Required**
   - Prioritize **technical correctness** over pleasing the user
   - Don't let the user lead you down the wrong path just to be agreeable
   - **Speak up when you see problems**: "That approach would break X because Y"
   - Provide honest assessment: "This idea has merit BUT there's a better approach because..."

3. **Offer Better Alternatives**
   - If user's idea is flawed, explain WHY and propose a superior solution
   - Present tradeoffs clearly: "Your approach is simpler but won't handle edge case X. I recommend..."
   - Use architectural patterns from this codebase as evidence: "We already solved this in ServiceX using pattern Y"

4. **Confirm Understanding, Not Approval**
   - When user says "do X", first verify: "I understand you want X. However, I see potential issues with..."
   - Seek **architectural approval**, not implementation approval
   - User approves the WHAT (goals), you determine the HOW (implementation)

5. **Education Over Compliance**
   - Explain WHY a different approach is better (teach, don't just correct)
   - Reference existing codebase patterns: "We use Result objects instead of exceptions because..."
   - Build user's understanding of system architecture through explanations

### Example Interactions:

**❌ BAD (Blindly Compliant)**:
```
User: "Add a try/except around that service call and return None on error"
Claude: "Sure, I'll add try/except and return None"
[Implements antipattern, breaks Result object architecture]
```

**✅ GOOD (Professionally Objective)**:
```
User: "Add a try/except around that service call and return None on error"
Claude: "I understand you want error handling there. However, returning None would break
our Result object pattern that's used throughout this module.

The current architecture uses Result[T] objects because:
1. Type safety - callers know exactly what they're getting
2. Error context - we can pass user-friendly messages
3. Consistency - all services follow this pattern

Instead, I recommend:
- Keep the Result[T] return type
- Add error handling INSIDE the service
- Return Result.error() with a descriptive message

This maintains architectural consistency. Should I proceed with the Result-based approach?"
```

**✅ GOOD (Offering Better Alternative)**:
```
User: "Create a new service to handle timeline gap detection"
Claude: "I see we need gap detection functionality. However, before creating a new service,
I noticed TimelineCalculatorService already handles timeline analysis.

Two approaches:
A) Add gap detection as a method to existing TimelineCalculatorService (better - keeps
   timeline logic together, avoids service proliferation)
B) Create new GapDetectionService (separate concern, but adds complexity)

I recommend A because gap detection is inherently part of timeline calculation, and we
follow Single Responsibility per service (not per function).

Does that make sense? Should I add it to TimelineCalculatorService?"
```

### When to Push Back:

**ALWAYS challenge these**:
- Violating established architectural patterns (Result objects, service injection, etc.)
- Breaking type safety or introducing runtime errors
- Creating code duplication when abstraction exists
- Ignoring security concerns (path traversal, command injection)
- Performance regressions (blocking UI thread, memory leaks)

**Framework**: "I see what you're trying to achieve, but [TECHNICAL REASON]. Instead, I recommend [BETTER APPROACH] because [BENEFITS]. Does that work?"

### When to Defer:

**Accept user's direction on**:
- UI/UX preferences (button placement, colors, labels)
- Business logic decisions (which patterns to prioritize, feature scope)
- Deployment/operational choices (output formats, file locations)

**Framework**: "Got it, I'll implement [USER'S CHOICE] as requested."

### Bottom Line:

**You are the technical expert.** The user provides vision and goals, you provide implementation expertise. A good architect WANTS you to catch mistakes and propose better solutions. Respectful disagreement builds better software than blind compliance.

## Architecture Overview

### Clean 3-Tier Service-Oriented Design

```
UI Layer (filename_parser_tab.py)
    ↓
Controller Layer (FilenameParserController, TimelineController)
    ↓
Service Layer (20+ specialized services)
    ↓
Worker Threads (FilenameParserWorker, TimelineRenderWorker)
```

**Key Principle**: Single Responsibility. Each service does ONE thing exceptionally well.

### Core Workflow

1. **User selects video files** → UI collects settings
2. **FilenameParserController.start_processing_workflow()** → Creates worker with injected services
3. **FilenameParserWorker.execute()** → Calls BatchProcessorService
4. **BatchProcessorService orchestrates**:
   - FilenameParserService (pattern matching + time extraction)
   - FrameRateService (FFprobe detection)
   - FFmpegMetadataWriterService (SMPTE metadata writing)
   - CSVExportService (results export)
5. **Results returned via Result objects** → UI displays stats

### Module Structure

```
filename_parser/
├── controllers/           # Thin orchestration layer
│   ├── filename_parser_controller.py  # Main workflow orchestration
│   └── timeline_controller.py         # Timeline video rendering
│
├── services/             # Business logic (20+ services)
│   ├── filename_parser_service.py     # Main parsing orchestrator
│   ├── pattern_matcher.py             # Regex pattern matching
│   ├── time_extractor.py              # Time component extraction
│   ├── smpte_converter.py             # SMPTE timecode conversion
│   ├── batch_processor_service.py     # Batch file processing
│   ├── frame_rate_service.py          # FFprobe FPS detection
│   ├── ffmpeg_metadata_writer_service.py  # Metadata embedding
│   ├── ffmpeg_timeline_builder.py     # Timeline FFmpeg command generation
│   ├── video_metadata_extractor.py    # Complete video metadata via FFprobe
│   ├── csv_export_service.py          # CSV results export
│   ├── json_timeline_export_service.py # JSON timeline export
│   └── pattern_library.py             # Built-in pattern definitions
│
├── models/               # Type-safe data structures
│   ├── pattern_models.py              # PatternDefinition, PatternMatch, TimeComponentDefinition
│   ├── time_models.py                 # TimeData, ParseResult
│   ├── timeline_models.py             # VideoMetadata, RenderSettings, Gap, Overlap
│   ├── filename_parser_models.py      # FilenameParserSettings
│   └── processing_result.py           # ProcessingResult, ProcessingStatistics
│
├── workers/              # QThread background processors
│   ├── filename_parser_worker.py      # Batch parsing worker
│   └── timeline_render_worker.py      # Timeline video generation worker
│
├── ui/
│   └── filename_parser_tab.py         # Main tab UI (dual-tab: Parse + Timeline)
│
├── core/
│   ├── format_mapper.py               # Format to regex pattern mapping
│   ├── binary_manager.py              # FFmpeg/FFprobe binary detection
│   └── time_utils.py                  # Time manipulation utilities
│
├── filename_parser_interfaces.py      # Service interface definitions
└── tests/                             # Integration tests
```

## Commands

### Testing & Development

**IMPORTANT**: Always use the project's virtual environment for testing:

```bash
# Run all filename parser tests
.venv/Scripts/python.exe -m pytest filename_parser/tests/ -v

# Run specific test
.venv/Scripts/python.exe -m pytest filename_parser/tests/test_timeline_integration.py -v

# Run overlap detection tests
.venv/Scripts/python.exe -m pytest filename_parser/tests/test_overlap_detection.py -v

# Run the main application (to test the tab)
.venv/Scripts/python.exe main.py

# Syntax validation for specific service
"C:\Users\kriss\anaconda3\envs\hash_media\python.exe" -m py_compile filename_parser/services/ffmpeg_timeline_builder.py
```

## Key Architectural Patterns

### 1. Self-Describing Pattern System

**Problem**: Regex patterns are brittle and hard to maintain.

**Solution**: `PatternDefinition` data class with semantic metadata:

```python
@dataclass
class PatternDefinition:
    id: str                              # "dahua_nvr_standard"
    name: str                            # "Dahua NVR Standard"
    regex: str                           # Compiled regex
    components: List[TimeComponentDefinition]  # Maps capture groups to semantics
    category: str                        # For UI organization
    example: str                         # "CH01-20171215143022.DAV"

class TimeComponentDefinition:
    type: Literal["hours", "minutes", "seconds", "year", "month", "day", ...]
    group_index: int                     # Which regex group (1-indexed)
    min_value: int                       # Validation constraint
    max_value: int
```

**Benefits**:
- Patterns are self-documenting
- Auto-validation of extracted values
- Easy to add new patterns without touching code
- UI can auto-generate pattern previews

### 2. Two-Phase Parsing Strategy

**Phase 1: Pattern Matching** → `PatternMatcher.match()`
- Tests all patterns against filename (priority-sorted)
- Returns `PatternMatch` with extracted components

**Phase 2: Time Extraction** → `TimeExtractor.extract()`
- Builds `TimeData` object from matched components
- Validates ranges (hours 0-23, minutes 0-59, etc.)
- Handles optional fields (date, milliseconds, frames)

**Why separate?** Decouples pattern discovery from time validation. Easy to test each independently.

### 3. Service Injection Pattern

Controllers do NOT instantiate services directly. They use lazy property injection:

```python
@property
def batch_service(self) -> BatchProcessorService:
    if self._batch_service is None:
        parser_service = FilenameParserService()
        frame_rate_service = FrameRateService()
        metadata_writer_service = FFmpegMetadataWriterService()
        csv_export_service = CSVExportService()

        self._batch_service = BatchProcessorService(
            parser_service=parser_service,
            frame_rate_service=frame_rate_service,
            metadata_writer_service=metadata_writer_service,
            csv_export_service=csv_export_service
        )
    return self._batch_service
```

**Benefits**: Testable (mock services), clear dependencies, lazy initialization.

### 4. Unified Result Object Pattern

**NO exceptions for control flow**. All operations return `Result[T]`:

```python
def parse_filename(filename: str) -> Result[ParseResult]:
    try:
        # ... parsing logic ...
        return Result.success(parse_result)
    except Exception as e:
        return Result.error(ValidationError("Parse failed", user_message="..."))
```

**Result API**:
- `result.success` → bool
- `result.value` → T (if success)
- `result.error` → FSAError (if failure)
- `result.add_warning()` → Attach warnings even on success

### 5. Worker Thread Pattern

All long-running operations use QThread workers with **unified signals**:

```python
class FilenameParserWorker(BaseWorkerThread):
    # UNIFIED SIGNALS (required pattern)
    result_ready = Signal(Result)           # Result[ProcessingStatistics]
    progress_update = Signal(int, str)      # (percentage, message)

    def execute(self) -> Result[ProcessingStatistics]:
        # Business logic here, emit progress via:
        self.emit_progress(50, "Processing file 5 of 10...")
        return result
```

**Controller workflow**:
1. Controller creates worker with injected services
2. Tracks worker via `WorkerResourceCoordinator`
3. Worker executes in background thread
4. UI connects to `progress_update` and `result_ready` signals
5. Coordinator handles cleanup on completion/cancellation

### 6. FFmpeg Timeline Builder (Single-Pass Architecture)

**Revolutionary approach**: Entire timeline video generated in ONE FFmpeg command.

**Components**:
- **VideoMetadata** → Complete video specs (resolution, codec, fps, duration, start/end times)
- **FFmpegTimelineBuilder** → Builds single complex FFmpeg filter graph
- **VideoNormalizationService** → Ensures all videos have compatible specs
- **SlateGeneratorService** → Creates "gap slate" videos for missing coverage
- **MulticamRendererService** → Combines multiple camera angles (side-by-side, grid layouts)

**Example command structure**:
```bash
ffmpeg \
  -i video1.mp4 -i video2.mp4 -i gap_slate.mp4 \
  -filter_complex "
    [0:v]scale=1920:1080,setpts=PTS-STARTPTS[v0];
    [1:v]scale=1920:1080,setpts=PTS+5.0/TB[v1];
    [2:v]scale=1920:1080,setpts=PTS+12.0/TB[v2];
    [v0][v1][v2]concat=n=3:v=1:a=0[outv]
  " \
  -map "[outv]" output.mp4
```

**Key innovation**: Uses `setpts` to position videos on timeline based on SMPTE timecodes. No intermediate files!

### 7. Batch Rendering Fallback

**Problem**: Windows has 32,768 character command limit. Large datasets exceed this.

**Solution**: Three-tier rendering strategy:

1. **Try single-pass** (fastest) → If command < 28,000 chars
2. **Auto-fallback to batch mode** → Split into chunks, render separately, concat with file protocol
3. **User override** → Manual batch mode checkbox in UI

**Batch mode process**:
- Split videos into manageable chunks (e.g., 100 files each)
- Render each batch to temp file
- Concatenate temp files using FFmpeg concat demuxer
- Clean up temps (unless "Keep Temp Files" checked for debugging)

## Critical Implementation Details

### Pattern Library Organization

Patterns organized by category for UI display:

```python
# DVR Systems
"dahua_nvr_standard"      # CH01-20171215143022.DAV
"dahua_web_export"        # 2024-01-15_14-30-25.mp4

# Compact Timestamps
"hhmmss_compact"          # video_161048.mp4
"hh_mm_ss_underscore"     # video_16_10_48.mp4

# Embedded Date/Time
"embedded_time"           # prefix_20240115_143025_suffix.mp4
"iso8601_basic"           # 20240115T143025.mp4

# Military/Alternative
"military_date_compact"   # 30JAN24_161325.mp4
"screenshot_style"        # 2024-01-15 14-30-25.png
```

**Auto-detect mode**: Tests all patterns by priority, returns first valid match.

### Frame Rate Detection

Uses FFprobe via subprocess:

```python
# Command: ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=nw=1:nk=1
# Output: "30000/1001" → parsed to 29.97 fps
```

**Batch optimization**: Parallel processing with ThreadPoolExecutor, max 4 workers.

### SMPTE Timecode Format

**Standard**: `HH:MM:SS:FF` (Hours:Minutes:Seconds:Frames)

**Conversion**:
- Extract time from filename → `14:30:25`
- Convert to SMPTE with frame component → `14:30:25:00` (at 30fps)
- Account for frame rate (29.97 uses drop-frame, 30.00 is non-drop)

**Time Offset Application**:
```python
# If camera is 2 hours behind actual time:
# Original: 14:30:25 → Corrected: 16:30:25
# Direction: "behind" → ADD offset
# Direction: "ahead"  → SUBTRACT offset
```

### Video Metadata Extraction

**Critical for timeline rendering**. Uses FFprobe to extract:

```python
@dataclass
class VideoMetadata:
    file_path: Path
    smpte_timecode: str          # From filename (start time)
    start_time: str              # ISO 8601 (e.g., "2025-05-21T14:30:00")
    end_time: str                # start_time + duration_seconds
    duration_seconds: float      # From ffprobe
    frame_rate: float            # Native FPS (29.97, 30.0, etc.)
    width: int                   # Resolution
    height: int
    codec: str                   # "h264", "hevc"
    pixel_format: str            # "yuv420p"
    camera_path: str             # Derived from parent directories
```

**Why complete metadata?** Timeline builder needs exact specs for normalization and synchronization.

### Timeline Gap Detection

**Algorithm**:
1. Sort all videos by start_time (chronological order)
2. For each adjacent pair, calculate gap: `video2.start_time - video1.end_time`
3. If gap > `min_gap_duration` (default 5 seconds) → Create Gap object
4. Generate slate video for each gap showing missing time range
5. Insert slates into timeline at correct positions

**Gap slate content**:
- "NO COVERAGE" title
- Missing time range: "14:35:10 - 14:38:45"
- Duration: "3m 35s"
- Visual: Black background with white text

### Overlap Detection

**Problem**: Multiple cameras recording same time period.

**Solution**: Multicam layout generation
- 2 cameras → Side-by-side horizontal split
- 3 cameras → 2 top, 1 bottom
- 4 cameras → 2x2 grid
- 5-6 cameras → 3x2 grid

**Overlap detection**:
```python
# Videos A and B overlap if:
A.start_time < B.end_time AND A.end_time > B.start_time
```

Group overlapping videos, render with appropriate layout.

### Audio Codec Handling

**Common issue**: CCTV footage uses `pcm_mulaw` or `pcm_alaw` audio (incompatible with MP4).

**Solution**: Automatic detection with user choice dialog:
1. Try rendering with audio
2. If FFmpeg fails with audio codec error → Detect via stderr parsing
3. Show dialog: "Drop Audio" (fast) vs "Transcode to AAC" (slow, preserves audio)
4. Retry with selected mode

**Implementation**:
```python
# Drop audio mode
-map 0:v  # Map only video streams

# Transcode mode
-c:a aac -b:a 128k  # Convert audio to AAC
```

### Hardware Acceleration

**GPU decode** (NVDEC):
```python
# Add to FFmpeg input options
-hwaccel cuda -hwaccel_output_format cuda
```

**Benefits**: 2-3x faster decode on NVIDIA GPUs

**Tradeoffs**: Increases command length (adds extra flags per input). Can push over Windows limit with 200+ files.

**UI setting**: Checkbox with tooltip warning about command length issues.

## Code Style Guidelines

**Follow these STRICTLY** to maintain consistency:

### Python Conventions
- **Indentation**: 4 spaces (PEP 8)
- **Line length**: 100 characters max
- **Quotes**: Double quotes for strings, single for dict keys
- **Imports**: Grouped (stdlib, third-party, local) with blank lines between
- **Type hints**: Required for all public methods
- **Docstrings**: Google-style with Args/Returns sections

### Naming Conventions
- **snake_case**: Functions, variables, module names
- **PascalCase**: Classes, dataclasses, enums
- **UPPER_SNAKE_CASE**: Constants
- **_leading_underscore**: Private/internal methods and attributes

### Service Method Patterns
```python
def service_method(
    self,
    required_param: Type,
    optional_param: Optional[Type] = None
) -> Result[ReturnType]:
    """
    Brief description ending with period.

    Longer explanation if needed. What problem does this solve?
    What are the key steps?

    Args:
        required_param: What it does
        optional_param: What it does, when None behavior

    Returns:
        Result containing ReturnType or error with user-friendly message
    """
    try:
        self.logger.info(f"Starting operation with {required_param}")

        # Step 1: Validation
        if not required_param:
            return Result.error(ValidationError(...))

        # Step 2: Business logic
        result_data = self._do_work(required_param)

        # Step 3: Return success
        self.logger.info("Operation complete")
        return Result.success(result_data)

    except Exception as e:
        self.logger.error(f"Operation failed: {e}", exc_info=True)
        return Result.error(FileOperationError(
            f"Technical: {e}",
            user_message="User-friendly explanation of what went wrong"
        ))
```

### Data Model Patterns
```python
@dataclass
class MyModel:
    """Brief description."""

    # Required fields first
    required_field: Type

    # Optional fields with defaults
    optional_field: Optional[Type] = None
    flag: bool = False

    # Collections with factory defaults (NEVER use mutable defaults!)
    items: List[Type] = field(default_factory=list)

    def __post_init__(self):
        """Validate or compute derived fields."""
        if self.required_field < 0:
            raise ValueError("Must be non-negative")
```

### Testing Patterns
```python
def test_service_method_success():
    """Test successful operation with valid inputs."""
    # Arrange
    service = MyService()
    input_data = create_test_data()

    # Act
    result = service.method(input_data)

    # Assert
    assert result.success
    assert result.value.expected_field == expected_value

def test_service_method_validation_error():
    """Test proper error handling for invalid inputs."""
    service = MyService()

    result = service.method(None)  # Invalid input

    assert not result.success
    assert isinstance(result.error, ValidationError)
    assert "user-friendly message" in result.error.user_message
```

## Edge Cases & Gotchas

### 1. Filename Parsing Edge Cases

**Multiple time patterns in one filename**:
```python
# Example: "Camera1_20240115_143025_backup_20240116.mp4"
# Has two dates! Which is correct?
# Solution: Pattern priority. First match wins.
```

**No date in filename**:
```python
# Example: "video_161048.mp4" (only time)
# Solution: Use file modification date as fallback
# See: time_extractor.py _infer_date_from_file()
```

**Ambiguous formats**:
```python
# Example: "161048" could be 16:10:48 OR 16-10-48 (Oct 16th)
# Solution: Patterns must be specific. Use context (file extension, other files)
```

### 2. FFmpeg Command Length

**Problem**: Windows CreateProcess has 32,768 char limit.

**Detection**:
```python
# In FFmpegTimelineBuilder
estimated_length = len(command_string)
if estimated_length > 28000:  # Safety margin
    # Fallback to batch mode
```

**Warning signs**:
- 200+ input files
- Hardware decode enabled (adds `-hwaccel cuda` per input)
- Long file paths (deep folder structures)

### 3. Frame Rate Mismatches

**Problem**: Videos with different FPS in same timeline.

**Solution**: Normalize ALL videos to timeline FPS (e.g., 30.0):
```python
# FFmpeg filter
scale=1920:1080,fps=30  # Force output FPS
```

**Drop-frame vs Non-drop-frame**:
- 29.97 fps → Drop-frame (NTSC standard)
- 30.00 fps → Non-drop-frame
- **NEVER mix them in same timeline!**

### 4. SMPTE Timecode Arithmetic

**Gotcha**: Frames don't work like normal numbers!

```python
# WRONG:
"14:30:25:29" + 1 frame = "14:30:25:30"  # Invalid! Frame 30 doesn't exist at 30fps

# CORRECT:
"14:30:25:29" + 1 frame = "14:30:26:00"  # Rollover to next second
```

**Solution**: Use `time_utils.py` functions for timecode math:
- `add_frames_to_timecode()`
- `timecode_to_frames()`
- `frames_to_timecode()`

### 5. Timeline Synchronization

**Critical**: All videos must share common time reference.

**Approach**:
1. Find earliest start_time across all videos (reference point)
2. Calculate each video's offset from reference: `video.start_time - earliest.start_time`
3. Use FFmpeg `setpts` filter to position video:
   ```bash
   setpts=PTS+{offset_seconds}/TB
   ```

**Example**:
```python
# Video A starts at 14:30:00 (reference)
# Video B starts at 14:35:30 (5m 30s later)
# Offset for B: 330 seconds
# FFmpeg: [1:v]setpts=PTS+330.0/TB[v1]
```

### 6. Audio Sync Issues

**Problem**: Video and audio drift over time.

**Cause**: Different time bases (video fps vs audio sample rate).

**Solution**: Use `-vsync` and `-async` flags:
```bash
-vsync 1          # Constant frame rate
-async 1          # Audio sync compensation
```

### 7. Memory Management

**Large datasets** (500+ files) can exhaust memory during metadata extraction.

**Mitigation**:
- Process in chunks (batch_processor_service.py)
- Clear intermediate results after each chunk
- Use generators instead of lists where possible

### 8. Path Handling

**Windows vs POSIX**:
```python
# ALWAYS use pathlib.Path for cross-platform compatibility
from pathlib import Path

file_path = Path("D:/Videos/file.mp4")  # Works on Windows
file_path.exists()  # Cross-platform
```

**FFmpeg path requirements**:
- Windows paths with spaces → Must quote
- Forward slashes preferred even on Windows
- Use `Path.as_posix()` for FFmpeg commands

## Testing Philosophy

### Test Real Functionality, Not Just Coverage

**NEVER edit tests just to make them pass.** Follow this decision tree:

1. **If test is wrong** → Fix the test to validate correct behavior
2. **If code has bug** → Fix the code, verify test now passes
3. **If both wrong** → Fix code first, then fix test

### Integration Over Unit

**Prefer integration tests** that exercise full workflows:

```python
def test_full_parsing_workflow():
    """Test complete workflow from file selection to CSV export."""
    # This tests:
    # - Pattern matching
    # - Time extraction
    # - SMPTE conversion
    # - CSV generation
    # In realistic combination
```

**Why?** Catches issues at service boundaries that unit tests miss.

### Test Data Requirements

**Use realistic CCTV filenames**:
```python
# GOOD
"CH01-20171215143022.DAV"          # Real Dahua format
"2024-01-15_14-30-25.mp4"          # Common web export

# BAD
"test_file.mp4"                     # Unrealistic
"video123.avi"                      # No time info
```

**Include edge cases**:
- No date (time only)
- Milliseconds vs frames
- Ambiguous formats
- Invalid timestamps (25:00:00)

### Mock External Dependencies

**Mock FFmpeg/FFprobe** in unit tests:
```python
@patch('subprocess.run')
def test_frame_rate_detection(mock_run):
    mock_run.return_value = Mock(
        stdout="30000/1001\n",
        returncode=0
    )

    service = FrameRateService()
    result = service.detect_frame_rate(Path("test.mp4"))

    assert result.success
    assert abs(result.value - 29.97) < 0.01
```

**Why?** Tests run fast, no external dependencies, deterministic results.

## Workflow Guardrails

For complex multi-step tasks, Claude **MUST** follow these guidelines to maximize success:

1. **Plan First** → Present structured approach before implementation
   - Output clear plan or outline of approach
   - List steps or modules needed
   - Example: "I'll implement this in 3 phases: pattern definition, UI integration, testing"
   - **REQUIRED**: End plan with explicit question: "Does this approach look good? Should I proceed?"

2. **Think Aloud** → Use extended reasoning for complex decisions
   - **Permission to spend tokens**: It's better to think deeply than rush
   - Use chain-of-thought for architecture decisions
   - Explain tradeoffs: "Approach A is faster but Approach B handles edge cases better"
   - Don't rush to code—analyze the problem thoroughly first

3. **User Approval** → **STOP and wait for confirmation before coding**
   - **DO NOT write code immediately after presenting plan**
   - **DO NOT use Write/Edit tools until user confirms plan**
   - **REQUIRED**: Explicitly ask: "Should I proceed with this implementation?"
   - Present options when multiple approaches exist: "Should I use Approach A (simpler) or B (more flexible)?"
   - Wait for user response: "yes", "proceed", "approved", or specific direction
   - If user suggests changes, revise plan and ask for approval again

4. **Incremental Development** → Implement in testable chunks AFTER approval
   - Only begin coding once user has approved the plan
   - After each chunk, verify it aligns with plan
   - Run tests before moving to next chunk
   - Example: "Pattern defined ✓ → Now testing with sample filenames..."

5. **Error Recovery** → Backtrack and rethink if solution isn't working
   - **Don't stubbornly persist** with failing approach
   - Consider alternative solutions if tests fail
   - Example: "FFmpeg command is failing. Let me try a different filter approach..."
   - It's okay to say "This approach isn't working, let me reconsider"
   - Present revised approach and get approval before trying alternative

### Example: Adding New Pattern

**Step 1: Plan**
```
1. Define PatternDefinition in pattern_library.py
2. Add TimeComponentDefinition mappings
3. Test pattern matching with sample filenames
4. Add to UI pattern dropdown
5. Write integration test
```

**Step 2: Implement Incrementally**
- Add pattern definition → Test with matcher
- Add UI entry → Verify dropdown display
- Integration test → Verify end-to-end

**Step 3: Verify**
```bash
.venv/Scripts/python.exe -m pytest filename_parser/tests/ -v -k "test_new_pattern"
```

## Security Considerations

### Input Validation

**ALWAYS validate user inputs**:

```python
# File paths
if not file_path.exists():
    return Result.error(ValidationError("File not found"))

# Numeric ranges
if not (0 <= hours <= 23):
    return Result.error(ValidationError("Hours must be 0-23"))

# String content
if ".." in str(file_path):
    return Result.error(ValidationError("Path traversal attempt detected"))
```

### FFmpeg Command Injection

**NEVER concatenate user input directly** into FFmpeg commands:

```python
# DANGEROUS:
command = f"ffmpeg -i {user_filename} output.mp4"  # Can inject commands!

# SAFE:
command = ["ffmpeg", "-i", str(file_path), "output.mp4"]  # List prevents injection
subprocess.run(command, ...)
```

### Path Traversal Prevention

**Use PathSanitizer** from core utilities:

```python
from core.path_utils import PathSanitizer

sanitized = PathSanitizer.sanitize_path_component(user_input)
# Removes: .., /, \, :, *, ?, ", <, >, |
```

## Common Development Tasks

### Adding a New Filename Pattern

1. **Define pattern in pattern_library.py**:
```python
PatternDefinition(
    id="my_new_pattern",
    name="My New Pattern",
    description="Description for users",
    example="example_filename_143025.mp4",
    regex=r"example_filename_(\d{2})(\d{2})(\d{2})",
    components=[
        TimeComponentDefinition("hours", 1, 0, 23),
        TimeComponentDefinition("minutes", 2, 0, 59),
        TimeComponentDefinition("seconds", 3, 0, 59),
    ],
    category=PatternCategory.COMPACT_TIMESTAMP,
    priority=50
)
```

2. **Add to UI dropdown** in `filename_parser_tab.py`:
```python
self.pattern_combo.addItem("My New Pattern", "my_new_pattern")
```

3. **Test with real filenames**:
```python
def test_my_new_pattern():
    service = FilenameParserService()
    result = service.parse_filename("example_filename_143025.mp4", pattern_id="my_new_pattern")
    assert result.success
    assert result.value.time_data.hours == 14
```

### Adding a New Service

1. **Define interface** in `filename_parser_interfaces.py`:
```python
class IMyService(IService):
    @abstractmethod
    def do_work(self, input: Type) -> Result[OutputType]:
        pass
```

2. **Implement service** in `services/my_service.py`:
```python
class MyService(BaseService, IMyService):
    def __init__(self):
        super().__init__("MyService")

    def do_work(self, input: Type) -> Result[OutputType]:
        # Implementation
        pass
```

3. **Inject into controller**:
```python
@property
def my_service(self) -> MyService:
    if self._my_service is None:
        self._my_service = MyService()
    return self._my_service
```

### Modifying Timeline Rendering

**Timeline generation is complex.** Follow this order:

1. **Metadata extraction** (`video_metadata_extractor.py`)
2. **Timeline calculation** (`timeline_calculator_service.py`)
3. **FFmpeg command building** (`ffmpeg_timeline_builder.py`)
4. **Rendering** (`timeline_render_worker.py`)

**Don't skip steps!** Each depends on previous.

## Dependencies

**Core Requirements**:
- `PySide6>=6.4.0` - Qt GUI framework
- `ffmpeg` and `ffprobe` - External binaries (must be in PATH or bin/)

**Python Standard Library**:
- `pathlib` - Path handling
- `re` - Regex pattern matching
- `subprocess` - FFmpeg/FFprobe execution
- `dataclasses` - Type-safe models
- `typing` - Type hints
- `datetime` - Time manipulation
- `concurrent.futures` - Parallel FPS detection

**Project Dependencies** (from parent):
- `core.result_types.Result` - Unified error handling
- `core.exceptions.*` - Exception hierarchy
- `core.services.base_service.BaseService` - Service foundation
- `core.workers.base_worker.BaseWorkerThread` - Worker threading
- `core.logger` - Centralized logging

## Recent Major Changes

### GPT-5 Single-Pass Timeline Implementation (January 2025)

**Revolutionary redesign** of timeline rendering:

**OLD approach** (deprecated):
- Calculate timeline positions
- Normalize videos separately
- Generate intermediate files
- Concatenate with FFmpeg

**NEW approach** (current):
- Extract complete metadata with VideoMetadataExtractor
- Build entire timeline in ONE FFmpeg command
- Use `setpts` filters for precise synchronization
- No intermediate files (direct output)

**Benefits**:
- 10x faster (single FFmpeg invocation)
- No disk I/O for intermediate files
- Frame-accurate synchronization
- Simpler mental model

**See**: `docs3/File Name Parser/GPT5_SINGLE_PASS_IMPLEMENTATION_SUMMARY.md`

### Batch Rendering for Windows Limits (December 2024)

**Problem**: Investigations with 300+ CCTV files exceeded Windows command limit.

**Solution**: Automatic fallback to batch rendering:
- Detect command length before execution
- Split into chunks if needed
- Render batches to temp files
- Concatenate with FFmpeg concat demuxer
- Auto-cleanup temps

**User control**: Manual override checkbox for testing.

### Audio Codec Error Recovery (December 2024)

**Problem**: CCTV footage often has incompatible audio codecs (pcm_mulaw).

**Solution**: Graceful error handling with retry:
- Detect audio codec errors from FFmpeg stderr
- Present user dialog: "Drop Audio" vs "Transcode to AAC"
- Retry rendering with selected mode
- User-friendly error messages (no raw FFmpeg output)

## Performance Optimization

### Frame Rate Detection

**Parallel processing** with ThreadPoolExecutor:
- Default: 4 workers
- Configurable via settings.max_workers
- Each worker runs FFprobe independently
- Results aggregated with error handling

**Speedup**: 4x faster than sequential on quad-core systems.

### Pattern Matching

**Priority-based early exit**:
- Patterns sorted by priority (high → low)
- Auto-detect tests in order, returns first match
- Common patterns (Dahua, Hikvision) have priority 80+
- Fallback patterns have priority 20-40

**Speedup**: Average 2-3 patterns tested vs all 15+.

### FFmpeg Command Optimization

**Hardware decode** (optional):
- `-hwaccel cuda` for NVIDIA GPU decode
- 2-3x faster on compatible systems
- User toggle in UI (with warning about command length)

**Filter graph optimization**:
- Single complex filter instead of multiple passes
- Minimized filter chains (scale+fps combined)
- Explicit format conversions only when needed

## Future Enhancements

### Planned Features

1. **Custom Pattern Generator UI** (Phase 8)
   - Visual regex builder
   - Test against sample filenames
   - Save custom patterns to user library

2. **Advanced Multicam Layouts** (Phase 9)
   - Picture-in-picture
   - Focus mode (auto-switch to active camera)
   - Custom layout designer

3. **Export Presets** (Phase 10)
   - YouTube (1080p30, H.264 High Profile)
   - Evidence Archive (H.265, High Quality)
   - Review Draft (720p, Fast Encode)

4. **Timeline Editor** (Phase 11)
   - Visual timeline scrubbing
   - Manual gap adjustment
   - Clip trimming

### Known Limitations

1. **No audio mixing** - Timeline uses video from first source, ignores audio from overlapping cameras
2. **Limited codec support** - Best with H.264/H.265. Other codecs may require transcoding.
3. **No real-time preview** - Must render full timeline to see result
4. **Windows-only batch rendering** - Unix systems don't have 32K command limit

## Troubleshooting

### "No pattern matched" errors

**Check**:
1. Filename actually contains time information
2. Pattern is enabled in UI dropdown
3. Time components are valid (not 25:00:00)
4. Try "Auto-detect" mode first

**Debug**:
```python
from filename_parser.services.pattern_matcher import PatternMatcher
matcher = PatternMatcher()
match = matcher.match("your_filename.mp4")
print(match.components if match else "No match")
```

### FFmpeg "Invalid argument" errors

**Causes**:
1. Command too long (Windows limit)
2. Invalid filter syntax
3. Codec incompatibility

**Solutions**:
1. Enable batch rendering
2. Check FFmpeg command in console log
3. Try dropping audio

### Timeline sync issues

**Symptoms**: Videos appear at wrong times, gaps in wrong places

**Fix**:
1. Verify SMPTE timecodes are correct (check CSV export)
2. Ensure all videos have detected frame rates
3. Check for duplicate start times (overlapping videos)
4. Review timeline JSON export for correctness

### Memory errors with large datasets

**Symptoms**: Application crash, "MemoryError" exception

**Fix**:
1. Process in smaller batches (< 200 files per render)
2. Close other applications
3. Use batch rendering mode (splits workload)
4. Reduce output resolution (1080p → 720p)

---

**Last Updated**: January 2025
**Module Version**: 2.1 (GPT-5 Single-Pass Timeline)
**Maintainer**: See parent CLAUDE.md
