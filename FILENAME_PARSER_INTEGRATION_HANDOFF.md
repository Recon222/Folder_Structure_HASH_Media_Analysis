# Filename Parser Integration - Handoff Document

**Date**: 2025-10-06
**Branch**: File-Name-Parser
**Status**: Phase 1-2 PARTIALLY COMPLETE (Foundation + Core Models)
**Next Agent**: Continue from Phase 2 (Service Layer Migration)

---

## What Was Completed

### ✅ **Phase 0: Critical Bug Fix**
- **Fixed parallel processing FPS bug** in `stand_alone_file_name_parser_/services/batch_processor_service.py`
  - **Issue**: Line 356 referenced `fps_map` before it was defined (line 403)
  - **Solution**: Moved FPS detection to Step 1 (before parsing loop) and updated step numbering
  - **Files Modified**: `batch_processor_service.py` lines 340-415

### ✅ **Phase 1: Foundation Setup (COMPLETE)**
Created module directory structure:
```
filename_parser/
├── __init__.py
├── filename_parser_interfaces.py          # Service interfaces ✅
├── controllers/
│   └── __init__.py
├── services/
│   ├── __init__.py
│   └── success_builders/
│       └── __init__.py
├── workers/
│   └── __init__.py
├── models/
│   ├── __init__.py
│   ├── pattern_models.py                  # ✅ TimeComponentDefinition, PatternDefinition, PatternMatch
│   ├── time_models.py                     # ✅ TimeData, ParseResult
│   ├── processing_result.py               # ✅ ProcessingResult, ProcessingStatistics, ProcessingStatus enum
│   └── filename_parser_models.py          # ✅ FilenameParserSettings
├── ui/
│   ├── __init__.py
│   └── components/
│       └── __init__.py
├── core/
│   ├── __init__.py
│   ├── binary_manager.py                  # ✅ FFmpegBinaryManager (updated imports)
│   ├── format_mapper.py                   # ✅ FormatMapper (copied unchanged)
│   └── time_utils.py                      # ✅ SMPTE utilities (copied unchanged)
└── tests/
    └── __init__.py
```

### ✅ **Key Architectural Decisions Made**
1. **ProcessingStatus enum** moved into `processing_result.py` (no separate constants file)
2. **Imports fixed** in all model files to use `filename_parser.models.*` paths
3. **binary_manager.py** updated to use `from core.logger import logger` (main app logger)
4. **FilenameParserSettings** includes fields for FormData integration and parallel processing

---

## What's Next: Phase 2 - Service Layer Migration

### 📋 **TODO**: Migrate and Refactor Services

#### **Priority 1: Pattern Library Service (Simple Copy)**
**File**: `filename_parser/services/pattern_library.py`
- Copy from: `stand_alone_file_name_parser_/services/pattern_library.py`
- **NO CHANGES NEEDED** - This is a static utility with built-in pattern definitions
- Contains 20+ pattern definitions (Embedded_Time, HH_MM_SS, HHMMSS, Dahua_NVR_Standard, etc.)

#### **Priority 2: Utility Services (Minimal Changes)**
These are **stateless utilities** and don't need to inherit BaseService:

1. **pattern_matcher.py** - Copy unchanged
   - `PatternMatcher.match(filename, pattern_id)` returns `PatternMatch`

2. **time_extractor.py** - Copy unchanged
   - `TimeExtractor.extract(pattern_match)` returns `TimeData`

3. **smpte_converter.py** - Copy unchanged
   - `SMPTEConverter.convert_to_smpte(time_data, fps)` returns SMPTE string
   - `SMPTEConverter.apply_time_offset_from_dict(timecode, offset)` returns adjusted SMPTE

4. **pattern_generator.py** - Copy unchanged
   - Used by pattern generator dialog UI

#### **Priority 3: Refactor FilenameParserService** ⚠️ **CRITICAL**
**File**: `filename_parser/services/filename_parser_service.py`
**Status**: NEEDS REFACTORING

**Current Issues**:
- Uses `log_callback` pattern (deprecated)
- Returns `Optional[ParseResult]` instead of `Result[ParseResult]`
- No BaseService inheritance

**Required Changes**:
```python
from core.services.base_service import BaseService
from core.result_types import Result
from core.exceptions import ValidationError, FileOperationError
from filename_parser.filename_parser_interfaces import IFilenameParserService

class FilenameParserService(BaseService, IFilenameParserService):
    def __init__(self):
        super().__init__("FilenameParserService")  # Auto-logging via self.logger
        self.matcher = PatternMatcher()
        self.extractor = TimeExtractor()
        self.converter = SMPTEConverter()
        self.generator = PatternGenerator()

    def parse_filename(
        self,
        filename: str,
        pattern_id: Optional[str] = None,
        fps: Optional[float] = None,
        time_offset: Optional[Dict[str, Any]] = None
    ) -> Result[ParseResult]:
        """Parse filename and extract time information"""
        try:
            self.logger.debug(f"Parsing filename: '{filename}'")

            # Step 1: Match pattern
            pattern_match = self.matcher.match(filename, pattern_id)
            if not pattern_match or not pattern_match.valid:
                return Result.error(
                    ValidationError(
                        f"No valid pattern match for '{filename}'",
                        user_message="Could not match filename pattern. Try selecting a different pattern.",
                        context={"filename": filename, "pattern_id": pattern_id}
                    )
                )

            # Step 2: Extract time data
            time_data = self.extractor.extract(pattern_match)
            if not time_data:
                return Result.error(
                    ValidationError(
                        f"Failed to extract time data from match",
                        user_message="Could not extract valid time data from filename.",
                        context={"filename": filename, "pattern": pattern_match.pattern.name}
                    )
                )

            # Step 3: SMPTE conversion (if fps provided)
            smpte_timecode = None
            if fps:
                smpte_timecode = self.converter.convert_to_smpte(time_data, fps)
                if not smpte_timecode:
                    self.logger.warning("SMPTE conversion failed")

                # Step 4: Apply time offset (if provided)
                if smpte_timecode and time_offset:
                    adjusted_timecode = self.converter.apply_time_offset_from_dict(
                        smpte_timecode, time_offset
                    )
                    if adjusted_timecode:
                        smpte_timecode = adjusted_timecode

            # Build ParseResult
            result = ParseResult(
                filename=filename,
                pattern=pattern_match.pattern,
                pattern_match=pattern_match,
                time_data=time_data,
                smpte_timecode=smpte_timecode,
                frame_rate=fps,
            )

            # Add time offset metadata
            if time_offset and smpte_timecode:
                result.time_offset_applied = True
                result.time_offset_direction = time_offset.get("direction", "behind")
                result.time_offset_hours = time_offset.get("hours", 0)
                result.time_offset_minutes = time_offset.get("minutes", 0)
                result.time_offset_seconds = time_offset.get("seconds", 0)

            self.logger.info(
                f"Successfully parsed: {time_data.time_string}"
                + (f" → {smpte_timecode}" if smpte_timecode else "")
            )

            return Result.success(result)

        except Exception as e:
            return Result.error(
                FileOperationError(
                    f"Unexpected error parsing filename: {e}",
                    user_message="An unexpected error occurred while parsing the filename.",
                    context={"filename": filename, "error": str(e)}
                )
            )
```

**See Integration Plan lines 749-870** for complete transformation example.

#### **Priority 4: Refactor FrameRateService** ⚠️ **MODERATE COMPLEXITY**
**File**: `filename_parser/services/frame_rate_service.py`
**Status**: NEEDS SIGNIFICANT REFACTORING

**Current Issues**:
- Returns tuples `(bool, float, str)` instead of `Result` objects
- Uses `log_callback` pattern
- Direct hardcoded paths to ffprobe

**Required Changes**:
1. Inherit from `BaseService`
2. Use `binary_manager` from `filename_parser.core.binary_manager`
3. Return `Result[float]` for single file, `Dict[str, float]` for batch
4. Remove all `log_callback` usage, use `self.logger`

**Key Methods to Refactor**:
```python
def detect_frame_rate(self, file_path: Path) -> Result[float]:
    """Detect frame rate from video file"""
    # Check ffprobe availability
    if not binary_manager.is_ffprobe_available():
        return Result.error(
            FileOperationError(
                "FFprobe not available",
                user_message="FFprobe is required for frame rate detection. Please install FFmpeg.",
                context={"file_path": str(file_path)}
            )
        )

    # Use binary_manager.get_ffprobe_path()
    # Run ffprobe command
    # Return Result.success(fps) or Result.error(...)
```

#### **Priority 5: Refactor FFmpegMetadataWriterService** ⚠️ **HIGH COMPLEXITY**
**File**: `filename_parser/services/ffmpeg_metadata_writer_service.py`
**Status**: NEEDS MAJOR REFACTORING

**Current Issues**:
- Returns tuples `(bool, str)` instead of `Result[Path]`
- Uses `app_state` dependency (not available in main app)
- Complex output directory logic needs simplification
- Uses `log_callback` pattern

**Required Changes**:
1. Inherit from `BaseService`
2. Remove `app_state` dependency completely
3. Use `binary_manager` for FFmpeg path
4. Return `Result[Path]` (output file path)
5. Simplify output directory logic - remove `set_base_output_directory()` methods
6. Use `settings.base_output_directory` and `settings.use_mirrored_structure` directly

**Signature**:
```python
def write_smpte_metadata(
    self,
    video_path: Path,
    smpte_timecode: str,
    fps: float,
    project_root: Optional[str] = None
) -> Result[Path]:
    """Write SMPTE timecode metadata to video file"""
```

#### **Priority 6: Refactor BatchProcessorService** ⚠️ **HIGHEST COMPLEXITY**
**File**: `filename_parser/services/batch_processor_service.py`
**Status**: NEEDS COMPLETE OVERHAUL

**Current Issues**:
- Manual service instantiation instead of dependency injection
- Callback registry system (lines 92-104) should be removed
- Returns `bool` instead of `Result[ProcessingStatistics]`
- Progress callbacks inconsistent with main app patterns

**Required Changes**:
1. Inherit from `BaseService`
2. **Constructor dependency injection**:
   ```python
   def __init__(
       self,
       parser_service: IFilenameParserService,
       frame_rate_service: IFrameRateService,
       metadata_writer_service: IFFmpegMetadataWriterService,
       csv_export_service: CSVExportService
   ):
       super().__init__("BatchProcessorService")
       self._parser_service = parser_service
       self._frame_rate_service = frame_rate_service
       self._metadata_writer_service = metadata_writer_service
       self._csv_export_service = csv_export_service
   ```

3. **Method signature**:
   ```python
   def process_files(
       self,
       files: List[Path],
       settings: FilenameParserSettings,
       progress_callback: Optional[Callable[[int, str], None]] = None
   ) -> Result[ProcessingStatistics]:
   ```

4. **Remove callback registry** (lines 92-104) - use `progress_callback` parameter directly
5. **Return Result object** with `ProcessingStatistics` on success

---

## Important Deviations from Plan

### ✅ **Approved Deviations**
1. **ProcessingStatus enum** - Moved into `processing_result.py` instead of separate `constants.py`
   - **Reason**: Reduces module complexity, keeps related types together
   - **Impact**: None - enum is only used in processing_result.py

2. **Logger Import** - Using `from core.logger import logger` instead of `core.logging_config`
   - **Reason**: Main app uses unified `core.logger` module
   - **Impact**: None - same functionality, better consistency

### ⚠️ **Decisions Needed**
1. **CSV Export Service** - Should it inherit from BaseService?
   - **Current**: Standalone utility class
   - **Recommendation**: Keep as utility (no state, no dependencies)

2. **Parallel FFmpeg Service** - Complex service with subprocess management
   - **Current**: Separate service in standalone app
   - **Question**: Integrate or keep separate?
   - **Recommendation**: Migrate unchanged, refactor later if needed

---

## Testing Status

### ✅ **Verified Working**
- Directory structure created successfully
- All `__init__.py` files in place
- Model files import correctly (verified dataclass syntax)
- Interface definitions align with main app patterns

### ⚠️ **Not Yet Tested**
- Service imports (will test after migration)
- Worker thread integration
- UI component integration
- End-to-end workflow

---

## Key Files to Review

### **Integration Plan** (PRIMARY REFERENCE)
- **Location**: `docs3/INTEGRATION_PLAN.md`
- **Critical Sections**:
  - Lines 630-870: Service transformation examples
  - Lines 235-298: Service layer migration details
  - Lines 749-870: Before/After code comparisons

### **Standalone App Services** (SOURCE CODE)
- `stand_alone_file_name_parser_/services/`
  - `filename_parser_service.py` (213 lines) - **PRIORITY**
  - `frame_rate_service.py` - Detect FPS from videos
  - `ffmpeg_metadata_writer_service.py` - Write SMPTE metadata
  - `batch_processor_service.py` (931 lines) - **MOST COMPLEX**
  - `pattern_matcher.py` - Copy unchanged
  - `time_extractor.py` - Copy unchanged
  - `smpte_converter.py` - Copy unchanged
  - `pattern_library.py` - Copy unchanged
  - `pattern_generator.py` - Copy unchanged
  - `csv_export_service.py` - Copy unchanged (or refactor to BaseService)
  - `parallel_ffmpeg_service.py` - Copy unchanged initially

### **Main App Reference Files**
- `core/services/base_service.py` - Service foundation
- `core/result_types.py` - Result object patterns
- `core/exceptions.py` - Error types
- `core/logger.py` - Logging system
- `core/services/interfaces.py` - Where to add new interfaces

---

## Next Steps (In Order)

### **Phase 2: Service Layer (Cont'd)**

1. **Copy simple utilities** (10 minutes):
   ```bash
   cp stand_alone_file_name_parser_/services/pattern_library.py filename_parser/services/
   cp stand_alone_file_name_parser_/services/pattern_matcher.py filename_parser/services/
   cp stand_alone_file_name_parser_/services/time_extractor.py filename_parser/services/
   cp stand_alone_file_name_parser_/services/smpte_converter.py filename_parser/services/
   cp stand_alone_file_name_parser_/services/pattern_generator.py filename_parser/services/
   cp stand_alone_file_name_parser_/services/csv_export_service.py filename_parser/services/
   ```

2. **Refactor FilenameParserService** (30-45 minutes):
   - Use template from lines 789-870 of INTEGRATION_PLAN.md
   - Test imports: `from filename_parser.services.pattern_matcher import PatternMatcher`
   - Verify Result object returns work correctly
   - Add to `filename_parser/services/__init__.py`

3. **Refactor FrameRateService** (20-30 minutes):
   - Simpler than parser service
   - Main changes: Result objects, binary_manager usage
   - Test with actual video file

4. **Refactor FFmpegMetadataWriterService** (45-60 minutes):
   - Most complex due to FFmpeg subprocess management
   - Remove app_state references
   - Simplify output directory logic
   - Test actual metadata writing

5. **Refactor BatchProcessorService** (60-90 minutes):
   - Remove callback registry completely
   - Add dependency injection in constructor
   - Return `Result[ProcessingStatistics]`
   - Test with multiple files

### **Phase 3: Workers (Next Session)**
After Phase 2 is complete, proceed to worker migration:
- `FilenameParserWorker(BaseWorkerThread)`
- `FrameRateWorker(BaseWorkerThread)`
- Unified signal patterns (`result_ready`, `progress_update`)

---

## Critical Reminders

### ⚠️ **DO NOT**
1. **Don't modify pattern_matcher, time_extractor, smpte_converter** - They're stateless utilities
2. **Don't create new patterns** - Use integration plan examples verbatim
3. **Don't skip Result object refactoring** - This is non-negotiable for main app consistency
4. **Don't test until Phase 2 complete** - Services depend on each other

### ✅ **DO**
1. **Read integration plan lines 630-870** before starting service refactoring
2. **Use exact Result object patterns** from plan examples
3. **Test each service independently** after refactoring
4. **Update todo list** as you complete tasks
5. **Document any new deviations** from plan in this file

---

## Command Reference

### **Run Tests** (After Phase 2)
```bash
.venv/Scripts/python.exe -m pytest filename_parser/tests/ -v
```

### **Test Service Imports**
```python
from filename_parser.services.filename_parser_service import FilenameParserService
from filename_parser.services.frame_rate_service import FrameRateService
from filename_parser.models.filename_parser_models import FilenameParserSettings

# Test instantiation
service = FilenameParserService()
result = service.parse_filename("test_20240115_143025.mp4", fps=29.97)
print(result.is_success, result.value if result.is_success else result.error)
```

### **Verify Binary Manager**
```python
from filename_parser.core.binary_manager import binary_manager
print(f"FFmpeg: {binary_manager.get_ffmpeg_path()}")
print(f"FFprobe: {binary_manager.get_ffprobe_path()}")
```

---

## Estimated Time Remaining

- **Phase 2 (Services)**: 3-4 hours
- **Phase 3 (Workers)**: 2-3 hours
- **Phase 4 (Controller)**: 1-2 hours
- **Phase 5 (UI)**: 6-8 hours ⚠️ LARGEST EFFORT
- **Phase 6-8 (Integration + Testing)**: 4-5 hours

**Total Remaining**: 16-22 hours

---

## Questions for Next Agent

1. Should `CSVExportService` inherit from `BaseService` or remain a utility?
2. Should we consolidate FFmpeg detection with media_analysis_tab now or later?
3. Do we need pattern persistence (custom patterns) in MVP or defer to v2?

---

**Good luck! The foundation is solid. Focus on service Result object refactoring next.** 🚀
