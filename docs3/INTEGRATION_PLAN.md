# SMPTE Filename Parser - Integration and Refactoring Plan

**Goal**: Transform the standalone SMPTE Filename Parser application into a modular, loosely-coupled feature integrated into the Folder Structure Utility, following the vehicle tracking architecture pattern.

**Status**: Pre-integration planning phase
**Target Integration Pattern**: Vehicle Tracking module (minimal coupling, self-contained)
**Complexity**: Large-scale refactor (~150+ files across multiple subsystems)

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Target Architecture](#target-architecture)
4. [Integration Phases](#integration-phases)
5. [Detailed Implementation Plan](#detailed-implementation-plan)
6. [Testing Strategy](#testing-strategy)
7. [Risk Assessment](#risk-assessment)
8. [Success Criteria](#success-criteria)

---

## Executive Summary

### What We're Building
A self-contained **Filename Parser** module that:
- Parses video filenames to extract timestamps (HHMMSS, YYYY-MM-DD patterns)
- Converts extracted time to SMPTE timecode format (HH:MM:SS:FF)
- Writes timecode metadata to video files using FFmpeg
- Supports batch processing with progress tracking
- Integrates seamlessly as a new tab in the main forensic application

### Integration Philosophy
**"Vehicle Tracking Clone"** - The integration will mirror the vehicle tracking pattern:
- ✅ Self-contained module structure (`filename_parser/`)
- ✅ Minimal core dependencies (BaseController, BaseService, Result objects)
- ✅ Optional service registration (graceful degradation if unavailable)
- ✅ No modifications to existing forensic/batch/media analysis features
- ✅ ~30 lines of integration code in main application

### Key Metrics
- **Lines of Code**: ~8,000+ (existing standalone app)
- **Integration Complexity**: HIGH (but manageable with phased approach)
- **Estimated Effort**: 3-5 days full-time work
- **Risk Level**: MEDIUM (well-defined architecture, existing functional code)

---

## Current State Analysis

### Standalone Application Structure
```
stand_alone_file_name_parser_/
├── app.py                          # Entry point
├── config.py                       # Global configuration
├── core/
│   ├── binary_manager.py           # FFmpeg/FFprobe detection
│   ├── constants.py                # App constants
│   ├── file_utils.py               # File operations
│   ├── format_mapper.py            # Video format conversions
│   ├── logging_config.py           # Logging setup
│   ├── time_utils.py               # Time/SMPTE utilities
│   └── validation.py               # Input validation
├── models/
│   ├── pattern_models.py           # Pattern definitions, PatternMatch
│   ├── time_models.py              # TimeData, ParseResult
│   └── processing_result.py        # ProcessingResult, ProcessingStatistics
├── services/
│   ├── filename_parser_service.py  # Core parsing orchestrator
│   ├── pattern_matcher.py          # Regex pattern matching
│   ├── time_extractor.py           # Time extraction from matches
│   ├── smpte_converter.py          # SMPTE timecode conversion
│   ├── pattern_generator.py        # Custom pattern generation
│   ├── pattern_library.py          # Built-in pattern collection
│   ├── frame_rate_service.py       # FPS detection via FFprobe
│   ├── ffmpeg_metadata_writer_service.py  # FFmpeg integration
│   ├── batch_processor_service.py  # Batch orchestration
│   ├── csv_export_service.py       # Results export
│   ├── parallel_ffmpeg_service.py  # Parallel processing
│   └── gpu_service.py              # GPU detection (unused?)
├── workers/
│   ├── batch_worker.py             # QThread batch processor
│   └── frame_rate_worker.py        # QThread FPS detection
├── ui/
│   ├── main_window.py              # Standalone UI (1200+ lines!)
│   └── pattern_generator_dialog.py # Pattern creation dialog
└── tests/
    ├── test_filename_parser.py
    ├── test_frame_rate.py
    └── test_metadata_writer.py
```

### Core Functionality Map

#### 1. **Filename Parsing Pipeline**
```
Filename → Pattern Match → Time Extraction → SMPTE Conversion → FFmpeg Write
```

**Example Flow:**
```
Input:  "camera01_20240115_143025.dav"
Match:  Embedded_Time pattern → groups: [2024, 01, 15, 14, 30, 25]
Extract: TimeData(year=2024, month=1, day=15, hours=14, minutes=30, seconds=25)
Convert: SMPTE at 29.97fps → "14:30:25:00"
Write:   FFmpeg → "camera01_20240115_143025_TC_14302500.mp4"
```

#### 2. **Pattern Library (20+ Built-in Patterns)**
- `Embedded_Time`: `_20240115_143025_` → 14:30:25:00
- `HH_MM_SS`: `16_38_20` → 16:38:20:00
- `HHMMSS`: `163820` → 16:38:20:00
- `Dahua_NVR_Standard`: DVR-specific formats
- `ISO8601_Filename`: ISO date-time formats
- Custom patterns (user-defined regex)

#### 3. **FFmpeg Integration**
- Binary detection (PATH and common locations)
- Format conversion (DAV, H264, H265 → MP4)
- Metadata writing (XMP + timecode track)
- Parallel processing support

#### 4. **Unique Features**
- **Pattern Generator Dialog**: Interactive regex pattern creation from filename selections
- **Time Offset Adjustment**: Timezone correction (e.g., "5 hours behind")
- **Mirrored Output Structure**: Maintain directory hierarchy in output location
- **GPU Service**: CUDA/OpenCL detection (minimal usage currently)

---

## Target Architecture

### Module Structure (Post-Integration)
```
filename_parser/                    # NEW: Self-contained module
├── __init__.py                     # Module exports
├── filename_parser_interfaces.py   # Local service interfaces
├── controllers/
│   ├── __init__.py
│   └── filename_parser_controller.py  # Inherits BaseController
├── services/
│   ├── __init__.py
│   ├── filename_parser_service.py     # Inherits BaseService
│   ├── pattern_matcher.py
│   ├── time_extractor.py
│   ├── smpte_converter.py
│   ├── pattern_generator.py
│   ├── pattern_library.py
│   ├── frame_rate_service.py
│   ├── ffmpeg_metadata_writer_service.py
│   ├── batch_processor_service.py
│   ├── csv_export_service.py
│   └── success_builders/
│       ├── __init__.py
│       └── filename_parser_success.py  # Success message builder
├── workers/
│   ├── __init__.py
│   ├── filename_parser_worker.py       # Inherits BaseWorkerThread
│   └── frame_rate_worker.py
├── models/
│   ├── __init__.py
│   ├── filename_parser_models.py       # Core models
│   ├── pattern_models.py
│   └── time_models.py
├── ui/
│   ├── __init__.py
│   ├── filename_parser_tab.py          # Main tab (similar to VehicleTrackingTab)
│   └── components/
│       ├── __init__.py
│       ├── pattern_generator_dialog.py
│       ├── pattern_selector_widget.py
│       └── time_offset_widget.py
├── core/
│   ├── __init__.py
│   ├── binary_manager.py               # FFmpeg/FFprobe detection
│   ├── format_mapper.py
│   └── time_utils.py                   # SMPTE utilities
└── tests/
    ├── __init__.py
    ├── test_filename_parser_service.py
    ├── test_pattern_matching.py
    └── test_smpte_conversion.py
```

### Integration Points (Minimal Coupling)

#### 1. **Main Application** (`ui/main_window.py`)
```python
# Lines 133-137 (after Vehicle Tracking tab)
from filename_parser.ui.filename_parser_tab import FilenameParserTab
self.filename_parser_tab = FilenameParserTab(self.form_data)  # Optional FormData
self.filename_parser_tab.log_message.connect(self.log)
self.filename_parser_tab.status_message.connect(self.status_bar.showMessage)
self.tabs.addTab(self.filename_parser_tab, "Filename Parser")
```

#### 2. **Service Registration** (`core/services/service_config.py`)
```python
# Optional registration (graceful fallback)
try:
    from filename_parser.services.filename_parser_service import FilenameParserService
    from filename_parser.filename_parser_interfaces import IFilenameParserService
    register_service(IFilenameParserService, FilenameParserService())
    logger.info("Filename parser module registered successfully")
except ImportError:
    logger.debug("Filename parser module not available - skipping registration")
```

#### 3. **Core Dependencies Used**
```python
from core.workers.base_worker import BaseWorkerThread
from core.result_types import Result
from core.exceptions import ValidationError, FileOperationError
from core.logger import logger
from core.models import FormData  # Optional
from core.services.base_service import BaseService
from core.services.success_message_data import SuccessMessageData
from controllers.base_controller import BaseController
```

#### 4. **NO Dependencies On**
- ❌ Forensic tab
- ❌ Batch processing tab
- ❌ Hashing tab
- ❌ Media analysis tab
- ❌ Vehicle tracking tab
- ❌ Copy & Verify tab

---

## Integration Phases

### **PHASE 1: Foundation Setup** (Day 1 - Morning)
**Goal**: Create module skeleton and migrate core models

#### Tasks:
1. ✅ Create `filename_parser/` directory structure
2. ✅ Copy and adapt models:
   - `pattern_models.py` → no changes needed (self-contained)
   - `time_models.py` → no changes needed
   - Create `filename_parser_models.py` (aggregates ProcessingResult, FilenameParserSettings)
3. ✅ Create `filename_parser_interfaces.py`:
   - `IFilenameParserService` (primary interface)
   - `IPatternLibraryService` (pattern management)
   - `IFFmpegBinaryService` (FFmpeg detection)
4. ✅ Migrate core utilities:
   - `core/binary_manager.py` → `filename_parser/core/binary_manager.py`
   - `core/format_mapper.py` → `filename_parser/core/format_mapper.py`
   - `core/time_utils.py` → `filename_parser/core/time_utils.py`
   - Remove `core/constants.py` → integrate into models
   - Remove `core/logging_config.py` → use main app logger
   - Remove `core/validation.py` → use main app ValidationService

**Success Criteria**:
- Module structure created
- Models importable without errors
- No external dependencies outside core/

---

### **PHASE 2: Service Layer Migration** (Day 1 - Afternoon)

#### Tasks:
1. ✅ Refactor `filename_parser_service.py`:
   - Inherit from `BaseService`
   - Return `Result` objects instead of exceptions
   - Remove log_callback → use `self.logger`
   - Implement `IFilenameParserService` interface

2. ✅ Migrate sub-services (minimal changes):
   - `pattern_matcher.py` → standalone utility (no BaseService needed)
   - `time_extractor.py` → standalone utility
   - `smpte_converter.py` → standalone utility
   - `pattern_generator.py` → standalone utility
   - `pattern_library.py` → could become `PatternLibraryService(BaseService)`

3. ✅ Refactor `frame_rate_service.py`:
   - Use `binary_manager` instead of hardcoded paths
   - Return `Result[float]` instead of `Tuple[bool, float, str]`
   - Add to service registry (optional)

4. ✅ Refactor `ffmpeg_metadata_writer_service.py`:
   - Inherit from `BaseService`
   - Use `Result` objects
   - Remove `app_state` dependency
   - Simplify output directory logic

5. ✅ Refactor `batch_processor_service.py`:
   - Use dependency injection for services
   - Return `Result[ProcessingStatistics]`
   - Remove callback registry → use progress_callback parameter

**Success Criteria**:
- All services inherit BaseService (where appropriate)
- All methods return Result objects
- Services can be instantiated independently
- No circular dependencies

---

### **PHASE 3: Worker Layer Migration** (Day 2 - Morning)

#### Tasks:
1. ✅ Create `FilenameParserWorker(BaseWorkerThread)`:
   - Replace `BatchWorker` callback system with unified signals
   - Signals:
     - `result_ready = Signal(Result)`
     - `progress_update = Signal(int, str)`
   - `execute()` method returns `Result[ProcessingStatistics]`

2. ✅ Create `FrameRateWorker(BaseWorkerThread)`:
   - Replace existing worker
   - Unified signal pattern
   - Return `Result[Dict[str, float]]` (file → fps mapping)

3. ✅ Remove callback complexity:
   - Delete `register_callback()` methods
   - Delete `unregister_all_callbacks()`
   - Use standard worker signals exclusively

**Success Criteria**:
- Workers follow unified signal architecture
- No custom callback systems
- Workers can be cancelled cleanly
- Result objects propagate errors correctly

---

### **PHASE 4: Controller Layer** (Day 2 - Afternoon)

#### Tasks:
1. ✅ Create `FilenameParserController(BaseController)`:
   ```python
   class FilenameParserController(BaseController):
       def __init__(self):
           super().__init__("FilenameParserController")
           self._parser_service = None
           self._frame_rate_service = None
           self._batch_service = None
           self.current_worker = None

       def parse_files(
           self,
           files: List[Path],
           settings: FilenameParserSettings,
           progress_callback: Optional[Callable] = None
       ) -> Result[ProcessingStatistics]:
           """Orchestrate batch filename parsing"""
           pass

       def detect_frame_rates(
           self,
           files: List[Path],
           progress_callback: Optional[Callable] = None
       ) -> Result[Dict[str, float]]:
           """Detect frame rates for files"""
           pass

       def cancel_operation(self):
           """Cancel current worker"""
           if self.current_worker:
               self.current_worker.cancel()
   ```

2. ✅ Implement service injection:
   - Use `self._get_service(IFilenameParserService)` pattern
   - Lazy initialization with error handling
   - Graceful degradation if services unavailable

**Success Criteria**:
- Controller has no direct service instantiation
- All operations return Result objects
- Worker lifecycle managed correctly
- Cancellation works cleanly

---

### **PHASE 5: UI Development** (Day 3 - Full Day)

#### 5.1: Main Tab Structure
```python
class FilenameParserTab(QWidget):
    # Signals
    log_message = Signal(str)
    status_message = Signal(str)

    def __init__(self, form_data: Optional[FormData] = None, parent=None):
        super().__init__(parent)
        self.controller = FilenameParserController()
        self.form_data = form_data  # Optional for report generation
        self.operation_active = False
        self.current_worker = None
        self.selected_files: List[Path] = []
        self.frame_rates: Dict[str, float] = {}

        self._create_ui()
        self._connect_signals()
```

#### 5.2: UI Layout (Two-Column Splitter)
```
┌─────────────────────────────────────────────────────────────┐
│  HEADER: 🎬 Filename Parser                                 │
│  Extract SMPTE timecode from video filenames                │
├─────────────────────┬───────────────────────────────────────┤
│ LEFT PANEL (45%)    │ RIGHT PANEL (55%)                     │
│                     │                                       │
│ FILES TO PROCESS    │ PATTERN SELECTION                     │
│ ┌─────────────────┐ │ ┌───────────────────────────────────┐│
│ │ [Add Files]     │ │ │ Pattern: [Combo ▼] [Generator...] ││
│ │ [Add Folder]    │ │ │ Preview: _20240115_143025_        ││
│ │ [Clear]         │ │ │ Match: ✓ 14:30:25 (2024-01-15)   ││
│ └─────────────────┘ │ └───────────────────────────────────┘│
│                     │                                       │
│ ┌─────────────────┐ │ FRAME RATE SETTINGS                  │
│ │ FilesPanel      │ │ ┌───────────────────────────────────┐│
│ │ (reusable from  │ │ │ ☑ Auto-detect from files         ││
│ │ main app)       │ │ │ Manual: [29.97 fps ▼]            ││
│ │                 │ │ │ [Detect Frame Rates]             ││
│ │ 📄 video1.dav   │ │ └───────────────────────────────────┘│
│ │ 📄 video2.mp4   │ │                                       │
│ │ 📄 video3.h264  │ │ TIME OFFSET (Optional)               │
│ └─────────────────┘ │ ┌───────────────────────────────────┐│
│                     │ │ ☑ Enable offset                   ││
│ Files: 3            │ │ Direction: (●) Behind ( ) Ahead   ││
│                     │ │ Hours: [0] Minutes: [0] Secs: [0] ││
│                     │ └───────────────────────────────────┘│
│                     │                                       │
│                     │ OUTPUT SETTINGS                       │
│                     │ ┌───────────────────────────────────┐│
│                     │ │ (●) Local subdirectory            ││
│                     │ │ ( ) Mirrored structure            ││
│                     │ │ Base directory: [Browse...]       ││
│                     │ └───────────────────────────────────┘│
│                     │                                       │
│                     │ [▶ Process Files]  [⏹ Cancel]       │
│                     │ Progress: ████████░░░░ 65%           │
└─────────────────────┴───────────────────────────────────────┘
│ CONSOLE                                                      │
│ ┌──────────────────────────────────────────────────────────┐│
│ │ LogConsole (reusable from main app)                      ││
│ │ [INFO] Processing camera01.dav...                        ││
│ │ [INFO] Matched pattern: Embedded_Time                    ││
│ │ [INFO] SMPTE timecode: 14:30:25:00 @ 29.97fps            ││
│ │ [SUCCESS] Output: camera01_TC_14302500.mp4               ││
│ └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

#### 5.3: Reusable Components
- ✅ Use `FilesPanel` from main app (already supports files & folders)
- ✅ Use `LogConsole` from main app
- ✅ Use `ElidedLabel` for long paths
- ✅ Create `PatternSelectorWidget` (combo + preview + generator button)
- ✅ Create `TimeOffsetWidget` (enable checkbox + direction + spinboxes)
- ✅ Create `OutputStructureWidget` (radio buttons + directory selector)

#### 5.4: Pattern Generator Dialog
- ✅ Migrate `pattern_generator_dialog.py` with minimal changes
- Update to use `AdobeTheme` instead of custom styling
- Integrate with `PatternGenerator` service

#### Tasks:
1. Create `FilenameParserTab` shell
2. Build left panel (file selection)
3. Build right panel sections (pattern, FPS, offset, output)
4. Create custom widgets (PatternSelectorWidget, TimeOffsetWidget)
5. Implement signal connections
6. Add progress tracking
7. Migrate pattern generator dialog

**Success Criteria**:
- Tab displays correctly in main window
- All widgets functional
- Signals connected properly
- Styling matches main app (Carolina Blue theme)

---

### **PHASE 6: Success Messages & Reports** (Day 4 - Morning)

#### Tasks:
1. ✅ Create `FilenameParserSuccessBuilder(BaseService)`:
   ```python
   def build_processing_success(
       self,
       total_files: int,
       successful: int,
       failed: int,
       skipped: int,
       processing_time: float,
       format_conversions: int,
       output_directory: Path
   ) -> SuccessMessageData:
       """Build rich success message for processing operation"""
       pass
   ```

2. ✅ Create success message data structure:
   ```python
   @dataclass
   class FilenameParserOperationData:
       total_files: int
       successful_files: int
       failed_files: int
       skipped_files: int
       processing_time: float
       average_time_per_file: float
       format_conversions: int
       output_directory: str
       patterns_matched: Dict[str, int]  # pattern_name → count
   ```

3. ✅ Integrate with `SuccessDialog`:
   - Display processing statistics
   - Show performance metrics
   - List output directory

4. ✅ CSV Export Integration:
   - Reuse existing `CSVExportService`
   - Export to `output/OccurrenceNumber/Documents/` if FormData available
   - Otherwise export to processing directory

**Success Criteria**:
- Success messages display correctly
- CSV export works
- Reports saved to correct location

---

### **PHASE 7: Service Registration & Testing** (Day 4 - Afternoon)

#### 7.1: Service Registration
```python
# core/services/interfaces.py
class IFilenameParserService(IService):
    """Interface for filename parser service"""

    @abstractmethod
    def parse_filename(
        self,
        filename: str,
        pattern_id: Optional[str] = None,
        fps: Optional[float] = None,
        time_offset: Optional[Dict[str, Any]] = None
    ) -> Result[ParseResult]:
        """Parse filename and extract time information"""
        pass
```

```python
# core/services/service_config.py (lines 82-92)
# ✅ FILENAME PARSER SERVICE: Optional module with graceful fallback
try:
    from filename_parser.services.filename_parser_service import FilenameParserService
    from filename_parser.filename_parser_interfaces import IFilenameParserService
    register_service(IFilenameParserService, FilenameParserService())
    logger.info("Filename parser module registered successfully")
except ImportError as e:
    # Filename parser module not available - graceful degradation
    logger.debug(f"Filename parser module not available: {e}")
    logger.debug("Filename parser module not available - skipping registration")
```

#### 7.2: Integration Testing
1. ✅ Test tab loads in main window
2. ✅ Test file selection (files and folders)
3. ✅ Test pattern matching with various formats
4. ✅ Test frame rate detection
5. ✅ Test batch processing
6. ✅ Test cancellation
7. ✅ Test error handling
8. ✅ Test success messages
9. ✅ Test CSV export

#### 7.3: Unit Testing
1. ✅ Pattern matching tests (`test_pattern_matching.py`)
2. ✅ Time extraction tests (`test_time_extraction.py`)
3. ✅ SMPTE conversion tests (`test_smpte_conversion.py`)
4. ✅ FFmpeg integration tests (`test_ffmpeg_service.py`)
5. ✅ Batch processing tests (`test_batch_processing.py`)

**Success Criteria**:
- Module loads without errors when available
- App runs correctly when module not available
- All integration tests pass
- Unit tests provide >80% coverage

---

### **PHASE 8: Polish & Documentation** (Day 5)

#### Tasks:
1. ✅ Documentation:
   - Create `filename_parser/README.md`
   - Document pattern syntax
   - Add examples
   - Update main `CLAUDE.md`

2. ✅ Error handling polish:
   - User-friendly error messages
   - Error notification integration
   - Validation improvements

3. ✅ Performance optimization:
   - Parallel FFmpeg processing verification
   - Progress reporting accuracy
   - Memory usage testing

4. ✅ UI polish:
   - Tooltips for all controls
   - Keyboard shortcuts
   - Accessibility improvements

5. ✅ Code cleanup:
   - Remove old/unused files
   - Remove debug logging
   - Code formatting (black)
   - Type hints verification

**Success Criteria**:
- Documentation complete
- No console errors
- Professional UX
- Code passes linting

---

## Detailed Implementation Plan

### Critical Design Decisions

#### 1. **Pattern Library Architecture**

**Option A: Service-Based (Recommended)**
```python
class PatternLibraryService(BaseService, IPatternLibraryService):
    """Manages pattern definitions with caching and search"""

    def get_all_patterns(self) -> List[PatternDefinition]:
        """Return all built-in patterns"""
        return self._patterns

    def search_patterns(
        self,
        query: str = None,
        category: str = None
    ) -> List[PatternDefinition]:
        """Search patterns by criteria"""
        pass

    def add_custom_pattern(
        self,
        pattern: PatternDefinition
    ) -> Result[None]:
        """Add user-defined pattern"""
        pass
```

**Option B: Static Utility (Current)**
```python
# pattern_library.py
BUILT_IN_PATTERNS = [
    PatternDefinition(id="embedded_time", ...),
    PatternDefinition(id="hh_mm_ss", ...),
    ...
]

def get_all_patterns() -> List[PatternDefinition]:
    return BUILT_IN_PATTERNS
```

**Recommendation**: Keep Option B (static utility) for simplicity, unless custom pattern persistence is needed.

---

#### 2. **FFmpeg Binary Management**

**Integration with Media Analysis Tab:**
The media analysis tab already has FFprobe detection. Should we:
- **Option A**: Share binary detection logic
- **Option B**: Keep filename_parser self-contained with own detection

**Recommendation**: Option B (self-contained) for module independence, but extract common detection logic to `core/binary_detection/` if future consolidation needed.

---

#### 3. **FormData Integration**

**Should filename parser use FormData?**
- ✅ **YES** - For CSV export path generation (output/OccurrenceNumber/Documents/)
- ✅ **YES** - For report metadata (technician info, occurrence number)
- ⚠️ **OPTIONAL** - Tab should work without FormData

**Pattern:**
```python
def __init__(self, form_data: Optional[FormData] = None, parent=None):
    self.form_data = form_data

def _get_export_directory(self) -> Path:
    if self.form_data and self.form_data.occurrence_number:
        return Path(f"output/{self.form_data.occurrence_number}/Documents")
    else:
        return Path("output/filename_parser_exports")
```

---

#### 4. **Configuration Management**

**Standalone app uses `config.py` + JSON storage. Main app uses `SettingsManager`.**

**Recommendation**: Convert to SettingsManager for consistency
```python
# Settings to migrate:
- default_pattern (str)
- recent_patterns (List[str])
- detect_fps (bool)
- default_fps (float)
- use_mirrored_structure (bool)
- base_output_directory (str)
- time_offset settings (Dict)
```

**Implementation:**
```python
class FilenameParserTab:
    def _load_settings(self) -> FilenameParserSettings:
        settings = SettingsManager()
        return FilenameParserSettings(
            default_pattern=settings.get("filename_parser/default_pattern", "embedded_time"),
            detect_fps=settings.get("filename_parser/detect_fps", True),
            default_fps=settings.get("filename_parser/default_fps", 29.97),
            ...
        )

    def _save_settings(self):
        settings = SettingsManager()
        settings.set("filename_parser/default_pattern", self.current_pattern)
        settings.set("filename_parser/detect_fps", self.detect_fps_check.isChecked())
        ...
```

---

### Code Transformation Examples

#### Before: Standalone Service
```python
class FilenameParserService:
    def __init__(self, log_callback: Optional[Callable[[str, str], None]] = None):
        self.log_callback = log_callback
        self.matcher = PatternMatcher()
        self.extractor = TimeExtractor()
        self.converter = SMPTEConverter()
        logger.info("FilenameParserService initialized")

    def parse(
        self,
        filename: str,
        pattern_id: Optional[str] = None,
        fps: Optional[float] = None,
        time_offset: Optional[Dict[str, Any]] = None
    ) -> Optional[ParseResult]:
        """Returns ParseResult or None on error"""
        self._log(f"Parsing filename: '{filename}'", "debug")

        pattern_match = self.matcher.match(filename, pattern_id)
        if not pattern_match or not pattern_match.valid:
            self._log(f"No valid pattern match", "error")
            return None  # ❌ Loses error context

        time_data = self.extractor.extract(pattern_match)
        if not time_data:
            self._log(f"Failed to extract time data", "error")
            return None  # ❌ No error details

        # ... more processing
        return result

    def _log(self, message: str, level: str = "info"):
        if self.log_callback:
            self.log_callback(message, level)
```

#### After: Integrated Service
```python
class FilenameParserService(BaseService, IFilenameParserService):
    """Service for parsing filenames and extracting time/date information"""

    def __init__(self):
        super().__init__("FilenameParserService")  # Auto-logging
        self.matcher = PatternMatcher()
        self.extractor = TimeExtractor()
        self.converter = SMPTEConverter()
        self.logger.info("FilenameParserService initialized")

    def parse_filename(
        self,
        filename: str,
        pattern_id: Optional[str] = None,
        fps: Optional[float] = None,
        time_offset: Optional[Dict[str, Any]] = None
    ) -> Result[ParseResult]:
        """
        Parse filename and extract time information

        Returns:
            Result containing ParseResult or error with full context
        """
        try:
            self.logger.debug(f"Parsing filename: '{filename}'")

            # Step 1: Pattern matching
            pattern_match = self.matcher.match(filename, pattern_id)
            if not pattern_match or not pattern_match.valid:
                return Result.error(
                    ValidationError(
                        f"No valid pattern match for '{filename}'",
                        user_message="Could not match filename pattern. Try selecting a different pattern.",
                        context={"filename": filename, "pattern_id": pattern_id}
                    )
                )

            # Step 2: Time extraction
            time_data = self.extractor.extract(pattern_match)
            if not time_data:
                return Result.error(
                    ValidationError(
                        f"Failed to extract time data from match",
                        user_message="Could not extract valid time data from filename.",
                        context={"filename": filename, "pattern": pattern_match.pattern.name}
                    )
                )

            # Step 3: SMPTE conversion
            smpte_timecode = None
            if fps:
                smpte_result = self.converter.convert_to_smpte(time_data, fps)
                if not smpte_result:
                    self.logger.warning("SMPTE conversion failed")
                else:
                    smpte_timecode = smpte_result

            # Build result
            result = ParseResult(
                filename=filename,
                pattern=pattern_match.pattern,
                pattern_match=pattern_match,
                time_data=time_data,
                smpte_timecode=smpte_timecode,
                frame_rate=fps
            )

            self.logger.info(
                f"Successfully parsed: {time_data.time_string}"
                + (f" → {smpte_timecode}" if smpte_timecode else "")
            )

            return Result.success(result)  # ✅ Rich error context

        except Exception as e:
            return Result.error(
                FileOperationError(
                    f"Unexpected error parsing filename: {e}",
                    user_message="An unexpected error occurred while parsing the filename.",
                    context={"filename": filename, "error": str(e)}
                )
            )
```

---

#### Before: Standalone Worker
```python
class BatchWorker(QObject):
    # Custom signals
    progress = Signal(dict)
    file_started = Signal(dict)
    file_finished = Signal(dict)
    finished = Signal(dict)
    error = Signal(dict)

    def run(self):
        try:
            # Register callbacks
            self.batch_processor_service.register_callback("progress", self._on_progress)
            self.batch_processor_service.register_callback("file_start", self._on_file_start)
            # ... more callbacks

            # Start processing
            self.batch_processor_service.process_files(
                self.files,
                self.pattern_key,
                # ... many parameters
            )
        except Exception as e:
            self.error.emit({
                "error_message": str(e),
                "traceback": traceback.format_exc(),
            })

    def _on_progress(self, data):
        """Handle progress callback"""
        if not self.is_stopped:
            self.progress.emit(data)
```

#### After: Integrated Worker
```python
class FilenameParserWorker(BaseWorkerThread):
    """Worker for batch filename parsing operations"""

    # Unified signals (inherited from BaseWorkerThread)
    # result_ready = Signal(Result)
    # progress_update = Signal(int, str)

    def __init__(
        self,
        files: List[Path],
        settings: FilenameParserSettings,
        batch_service: BatchProcessorService
    ):
        super().__init__("FilenameParserWorker")
        self.files = files
        self.settings = settings
        self.batch_service = batch_service

    def execute(self) -> Result[ProcessingStatistics]:
        """
        Execute batch processing

        Returns:
            Result containing ProcessingStatistics or error
        """
        try:
            # Simple progress callback
            def progress_callback(percent: int, message: str):
                if not self.is_cancelled():
                    self.progress_update.emit(percent, message)

            # Process files
            result = self.batch_service.process_files(
                files=self.files,
                settings=self.settings,
                progress_callback=progress_callback
            )

            return result  # ✅ Clean Result object

        except Exception as e:
            return Result.error(
                FileOperationError(
                    f"Batch processing failed: {e}",
                    user_message="An error occurred during batch processing.",
                    context={"file_count": len(self.files), "error": str(e)}
                )
            )
```

---

#### Before: Standalone UI
```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 1200+ lines of mixed UI and business logic
        self.selected_files = []
        self.frame_rates = {}
        self.processing_results = {}

        # Direct service instantiation
        self.filename_parser_service = FilenameParserService(log_callback=self.log)
        self.frame_rate_service = FrameRateService(log_callback=self.log)
        self.metadata_writer_service = FFmpegMetadataWriterService(log_callback=self.log)
        self.batch_processor_service = BatchProcessorService(
            filename_parser_service=self.filename_parser_service,
            frame_rate_service=self.frame_rate_service,
            metadata_writer_service=self.metadata_writer_service,
            log_callback=self.log
        )

        # Massive UI setup
        self.setup_file_section(main_layout)
        self.setup_pattern_section(main_layout)
        # ... 10 more sections
```

#### After: Integrated Tab
```python
class FilenameParserTab(QWidget):
    """Tab for filename parsing and SMPTE timecode operations"""

    # Signals
    log_message = Signal(str)
    status_message = Signal(str)

    def __init__(self, form_data: Optional[FormData] = None, parent=None):
        super().__init__(parent)

        # Controller handles all orchestration
        self.controller = FilenameParserController()

        # Optional form data reference
        self.form_data = form_data

        # State
        self.operation_active = False
        self.current_worker = None
        self.selected_files: List[Path] = []
        self.frame_rates: Dict[str, float] = {}
        self.settings = self._load_settings()

        # UI setup
        self._create_ui()
        self._connect_signals()

    def _create_ui(self):
        """Create tab UI (300 lines max)"""
        layout = QVBoxLayout(self)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._create_file_panel())
        splitter.addWidget(self._create_settings_panel())
        splitter.setSizes([450, 550])
        layout.addWidget(splitter)

        # Console
        layout.addWidget(self._create_console_section())

    def _on_process_clicked(self):
        """Handle process button click"""
        if self.operation_active:
            return

        # Validate
        if not self.selected_files:
            self.log_message.emit("[ERROR] No files selected")
            return

        # Build settings
        settings = FilenameParserSettings(
            pattern_id=self.pattern_combo.currentData(),
            fps=self._get_selected_fps(),
            time_offset=self._get_time_offset(),
            use_mirrored_structure=self.mirrored_output_radio.isChecked(),
            base_output_directory=Path(self.output_dir_input.text())
        )

        # Start worker
        self.operation_active = True
        self.current_worker = self.controller.start_batch_processing(
            files=self.selected_files,
            settings=settings
        )

        # Connect signals
        self.current_worker.result_ready.connect(self._on_processing_complete)
        self.current_worker.progress_update.connect(self._on_progress_update)
        self.current_worker.start()

    def _on_processing_complete(self, result: Result):
        """Handle processing completion"""
        self.operation_active = False

        if result.is_success:
            stats = result.value

            # Build success message
            success_builder = get_service(IFilenameParserSuccessService)
            message_data = success_builder.build_processing_success(
                total_files=stats.total_files,
                successful=stats.successful,
                failed=stats.failed,
                skipped=stats.skipped,
                processing_time=stats.total_processing_time,
                format_conversions=stats.format_conversions,
                output_directory=self.settings.base_output_directory
            )

            # Show success dialog
            SuccessDialog.show_success_message(message_data, self)
        else:
            # Error notification
            self.log_message.emit(f"[ERROR] {result.error.user_message}")
```

---

## Testing Strategy

### Unit Tests

#### Pattern Matching Tests
```python
class TestPatternMatching:
    def test_embedded_time_pattern(self):
        """Test embedded timestamp pattern"""
        matcher = PatternMatcher()

        filename = "camera01_20240115_143025.dav"
        match = matcher.match(filename, "embedded_time")

        assert match is not None
        assert match.valid
        assert match.components["year"] == 2024
        assert match.components["month"] == 1
        assert match.components["day"] == 15
        assert match.components["hours"] == 14
        assert match.components["minutes"] == 30
        assert match.components["seconds"] == 25

    def test_hh_mm_ss_pattern(self):
        """Test HH_MM_SS pattern"""
        matcher = PatternMatcher()

        filename = "video_16_38_20.mp4"
        match = matcher.match(filename, "hh_mm_ss")

        assert match is not None
        assert match.components["hours"] == 16
        assert match.components["minutes"] == 38
        assert match.components["seconds"] == 20

    def test_invalid_filename(self):
        """Test filename with no matching pattern"""
        matcher = PatternMatcher()

        filename = "random_video_file.mp4"
        match = matcher.match(filename)

        assert match is None
```

#### SMPTE Conversion Tests
```python
class TestSMPTEConversion:
    def test_basic_conversion(self):
        """Test basic time to SMPTE conversion"""
        converter = SMPTEConverter()

        time_data = TimeData(hours=14, minutes=30, seconds=25)
        smpte = converter.convert_to_smpte(time_data, fps=29.97)

        assert smpte == "14:30:25:00"

    def test_time_offset_behind(self):
        """Test time offset adjustment (behind)"""
        converter = SMPTEConverter()

        timecode = "14:30:25:00"
        offset = {"direction": "behind", "hours": 5, "minutes": 0, "seconds": 0}

        adjusted = converter.apply_time_offset_from_dict(timecode, offset)
        assert adjusted == "09:30:25:00"

    def test_time_offset_ahead(self):
        """Test time offset adjustment (ahead)"""
        converter = SMPTEConverter()

        timecode = "14:30:25:00"
        offset = {"direction": "ahead", "hours": 2, "minutes": 30, "seconds": 0}

        adjusted = converter.apply_time_offset_from_dict(timecode, offset)
        assert adjusted == "17:00:25:00"
```

#### Service Tests
```python
class TestFilenameParserService:
    def test_parse_with_embedded_time(self):
        """Test full parsing pipeline"""
        service = FilenameParserService()

        result = service.parse_filename(
            filename="camera01_20240115_143025.dav",
            pattern_id="embedded_time",
            fps=29.97
        )

        assert result.is_success
        parse_result = result.value
        assert parse_result.time_data.hours == 14
        assert parse_result.time_data.minutes == 30
        assert parse_result.time_data.seconds == 25
        assert parse_result.smpte_timecode == "14:30:25:00"

    def test_parse_with_invalid_pattern(self):
        """Test parsing with non-matching pattern"""
        service = FilenameParserService()

        result = service.parse_filename(
            filename="random_video.mp4",
            pattern_id="embedded_time"
        )

        assert result.is_error
        assert isinstance(result.error, ValidationError)
        assert "pattern match" in result.error.user_message.lower()
```

### Integration Tests

```python
class TestFilenameParserIntegration:
    def test_full_workflow(self, tmp_path):
        """Test complete workflow from file selection to metadata writing"""
        # Setup
        controller = FilenameParserController()
        test_files = [create_test_video(tmp_path, "test_20240115_143025.mp4")]

        settings = FilenameParserSettings(
            pattern_id="embedded_time",
            fps=29.97,
            detect_fps=False,
            use_mirrored_structure=False
        )

        # Execute
        result = controller.parse_files(test_files, settings)

        # Verify
        assert result.is_success
        stats = result.value
        assert stats.successful == 1
        assert stats.failed == 0

        # Check output file exists
        output_file = tmp_path / "timecoded" / "test_20240115_143025_TC_14302500.mp4"
        assert output_file.exists()

    def test_batch_processing_with_errors(self, tmp_path):
        """Test batch processing with some invalid files"""
        controller = FilenameParserController()

        test_files = [
            create_test_video(tmp_path, "valid_20240115_143025.mp4"),
            create_test_video(tmp_path, "invalid_filename.mp4"),
            create_test_video(tmp_path, "another_20240115_150000.mp4"),
        ]

        settings = FilenameParserSettings(pattern_id="embedded_time", fps=29.97)
        result = controller.parse_files(test_files, settings)

        assert result.is_success
        stats = result.value
        assert stats.successful == 2
        assert stats.failed == 1
```

---

## Risk Assessment

### High-Risk Areas

#### 1. **FFmpeg Integration Conflicts** (MEDIUM RISK)
**Issue**: Both media_analysis_tab and filename_parser use FFmpeg/FFprobe
**Mitigation**:
- Keep separate binary detection in each module
- Consider future consolidation to `core/binary_detection/`
- Document FFmpeg version requirements

#### 2. **UI Layout Complexity** (MEDIUM RISK)
**Issue**: Original standalone UI is 1200+ lines, complex collapsible sections
**Mitigation**:
- Break into reusable components (PatternSelectorWidget, TimeOffsetWidget)
- Use Qt Designer for complex layouts (optional)
- Extensive UI testing on different screen sizes

#### 3. **Pattern Library Persistence** (LOW RISK)
**Issue**: Custom patterns need storage mechanism
**Mitigation**:
- Use SettingsManager for pattern storage
- Validate patterns before saving
- Provide import/export functionality

#### 4. **Worker Thread Lifecycle** (LOW RISK)
**Issue**: Ensuring proper cleanup of workers
**Mitigation**:
- Use BaseWorkerThread cleanup mechanisms
- Test cancellation extensively
- Use resource coordinator for tracking

### Low-Risk Areas
- ✅ Pattern matching logic (well-tested, self-contained)
- ✅ SMPTE conversion utilities (pure functions)
- ✅ Service layer architecture (clear dependencies)
- ✅ Model definitions (dataclasses, no complex logic)

---

## Success Criteria

### Functional Requirements
- ✅ Tab loads without errors in main application
- ✅ Can parse filenames with 20+ built-in patterns
- ✅ Auto-detects frame rates using FFprobe
- ✅ Writes SMPTE timecode metadata using FFmpeg
- ✅ Batch processes multiple files with progress tracking
- ✅ Supports time offset adjustment
- ✅ Supports mirrored output directory structure
- ✅ Exports results to CSV
- ✅ Shows success messages with statistics
- ✅ Handles errors gracefully with user-friendly messages

### Non-Functional Requirements
- ✅ Module can be removed without breaking main app
- ✅ No dependencies on other tabs (forensic, batch, etc.)
- ✅ Follows unified Result-based error handling
- ✅ Uses standard Qt signal patterns
- ✅ Integrates with main app logging system
- ✅ Matches Carolina Blue theme styling
- ✅ Responsive UI (doesn't freeze during processing)
- ✅ Memory efficient (doesn't leak workers)

### Code Quality
- ✅ Follows PEP 8 style guidelines
- ✅ Type hints on all public methods
- ✅ Docstrings on all classes and methods
- ✅ Unit test coverage >80%
- ✅ No circular dependencies
- ✅ Clean separation of concerns (MVC)

### Documentation
- ✅ README.md in filename_parser/ module
- ✅ Pattern syntax documentation
- ✅ Integration guide for developers
- ✅ User guide for end users
- ✅ Updated main CLAUDE.md

---

## Migration Checklist

### Phase 1: Foundation
- [ ] Create `filename_parser/` directory structure
- [ ] Copy models (pattern_models.py, time_models.py, processing_result.py)
- [ ] Create filename_parser_models.py (FilenameParserSettings)
- [ ] Create filename_parser_interfaces.py
- [ ] Migrate core utilities (binary_manager, format_mapper, time_utils)
- [ ] Remove dependencies on standalone config.py

### Phase 2: Services
- [ ] Refactor FilenameParserService → inherit BaseService
- [ ] Update pattern_matcher, time_extractor, smpte_converter (utilities)
- [ ] Refactor FrameRateService → Result objects
- [ ] Refactor FFmpegMetadataWriterService → Result objects
- [ ] Refactor BatchProcessorService → dependency injection
- [ ] Remove callback systems

### Phase 3: Workers
- [ ] Create FilenameParserWorker(BaseWorkerThread)
- [ ] Create FrameRateWorker(BaseWorkerThread)
- [ ] Implement unified signals (result_ready, progress_update)
- [ ] Remove old BatchWorker callback system

### Phase 4: Controller
- [ ] Create FilenameParserController(BaseController)
- [ ] Implement service injection
- [ ] Implement worker lifecycle management
- [ ] Add cancellation support

### Phase 5: UI
- [ ] Create FilenameParserTab shell
- [ ] Build file selection panel (reuse FilesPanel)
- [ ] Build pattern selection widget
- [ ] Build frame rate settings widget
- [ ] Build time offset widget
- [ ] Build output structure widget
- [ ] Build console section (reuse LogConsole)
- [ ] Migrate pattern generator dialog
- [ ] Connect all signals
- [ ] Add progress tracking

### Phase 6: Success Messages
- [ ] Create FilenameParserSuccessBuilder
- [ ] Create FilenameParserOperationData
- [ ] Integrate with SuccessDialog
- [ ] Implement CSV export

### Phase 7: Integration
- [ ] Add IFilenameParserService to core/services/interfaces.py
- [ ] Add service registration to service_config.py
- [ ] Add tab to main_window.py (4 lines)
- [ ] Test graceful degradation when module unavailable

### Phase 8: Testing
- [ ] Unit tests for pattern matching
- [ ] Unit tests for SMPTE conversion
- [ ] Unit tests for services
- [ ] Integration tests for full workflow
- [ ] UI tests for tab functionality
- [ ] Error handling tests
- [ ] Performance tests

### Phase 9: Polish
- [ ] Write README.md
- [ ] Document pattern syntax
- [ ] Add tooltips
- [ ] Add keyboard shortcuts
- [ ] Error message review
- [ ] Code formatting (black)
- [ ] Type hints verification
- [ ] Remove debug logging

### Phase 10: Validation
- [ ] Test with real video files (DAV, H264, MP4)
- [ ] Test all built-in patterns
- [ ] Test custom pattern generation
- [ ] Test batch processing (100+ files)
- [ ] Test cancellation mid-process
- [ ] Test error scenarios (invalid files, FFmpeg unavailable)
- [ ] Test on different Windows versions
- [ ] Memory leak testing (long-running batch jobs)

---

## Appendix

### A. Pattern Library Examples

#### Embedded Time Pattern
```python
PatternDefinition(
    id="embedded_time",
    name="Embedded Timestamp",
    description="Extracts timestamp from _YYYYMMDD_HHMMSS_ format",
    example="camera01_20240115_143025.dav",
    regex=r"_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_",
    components=[
        TimeComponentDefinition("year", 1, 1900, 2100),
        TimeComponentDefinition("month", 2, 1, 12),
        TimeComponentDefinition("day", 3, 1, 31),
        TimeComponentDefinition("hours", 4, 0, 23),
        TimeComponentDefinition("minutes", 5, 0, 59),
        TimeComponentDefinition("seconds", 6, 0, 59),
    ],
    category="security_camera",
    has_date=True,
    has_milliseconds=False,
    priority=80,
)
```

#### HH_MM_SS Pattern
```python
PatternDefinition(
    id="hh_mm_ss",
    name="HH_MM_SS",
    description="Matches time in HH_MM_SS format with underscores",
    example="video_16_38_20.mp4",
    regex=r"(\d{2})_(\d{2})_(\d{2})",
    components=[
        TimeComponentDefinition("hours", 1, 0, 23),
        TimeComponentDefinition("minutes", 2, 0, 59),
        TimeComponentDefinition("seconds", 3, 0, 59),
    ],
    category="generic",
    has_date=False,
    has_milliseconds=False,
    priority=50,
)
```

### B. FilenameParserSettings Model
```python
@dataclass
class FilenameParserSettings:
    """Settings for filename parsing operations"""

    # Pattern selection
    pattern_id: Optional[str] = None  # None = auto-detect
    custom_pattern: Optional[str] = None  # Custom regex if pattern_id is "custom"

    # Frame rate
    detect_fps: bool = True
    fps_override: Optional[float] = None  # Manual FPS if not detecting

    # Time offset
    enable_time_offset: bool = False
    time_offset_direction: str = "behind"  # "behind" or "ahead"
    time_offset_hours: int = 0
    time_offset_minutes: int = 0
    time_offset_seconds: int = 0

    # Output structure
    use_mirrored_structure: bool = False
    base_output_directory: Optional[Path] = None

    # Processing options
    export_csv: bool = True
    csv_output_path: Optional[Path] = None

    def get_time_offset_dict(self) -> Optional[Dict[str, Any]]:
        """Get time offset as dictionary for service"""
        if not self.enable_time_offset:
            return None

        return {
            "direction": self.time_offset_direction,
            "hours": self.time_offset_hours,
            "minutes": self.time_offset_minutes,
            "seconds": self.time_offset_seconds,
        }
```

### C. Service Interface Definitions
```python
# filename_parser/filename_parser_interfaces.py

class IFilenameParserService(IService):
    """Interface for filename parser service"""

    @abstractmethod
    def parse_filename(
        self,
        filename: str,
        pattern_id: Optional[str] = None,
        fps: Optional[float] = None,
        time_offset: Optional[Dict[str, Any]] = None
    ) -> Result[ParseResult]:
        """Parse filename and extract time information"""
        pass

    @abstractmethod
    def get_available_patterns(self) -> List[PatternDefinition]:
        """Get all available patterns"""
        pass

    @abstractmethod
    def search_patterns(
        self,
        query: str = None,
        category: str = None
    ) -> List[PatternDefinition]:
        """Search patterns by criteria"""
        pass


class IFrameRateService(IService):
    """Interface for frame rate detection service"""

    @abstractmethod
    def detect_frame_rate(
        self,
        file_path: Path,
        progress_callback: Optional[Callable] = None
    ) -> Result[float]:
        """Detect frame rate from video file"""
        pass

    @abstractmethod
    def detect_frame_rates_batch(
        self,
        file_paths: List[Path],
        progress_callback: Optional[Callable] = None
    ) -> Result[Dict[str, float]]:
        """Detect frame rates for multiple files"""
        pass


class IFFmpegMetadataWriterService(IService):
    """Interface for FFmpeg metadata writing service"""

    @abstractmethod
    def write_smpte_metadata(
        self,
        video_path: Path,
        smpte_timecode: str,
        fps: float,
        output_directory: Optional[Path] = None
    ) -> Result[Path]:
        """Write SMPTE timecode to video file"""
        pass

    @abstractmethod
    def is_ffmpeg_available(self) -> bool:
        """Check if FFmpeg is available"""
        pass


class IBatchProcessorService(IService):
    """Interface for batch processing service"""

    @abstractmethod
    def process_files(
        self,
        files: List[Path],
        settings: FilenameParserSettings,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Result[ProcessingStatistics]:
        """Process multiple files in batch"""
        pass

    @abstractmethod
    def cancel_processing(self):
        """Cancel current batch processing"""
        pass
```

---

## Conclusion

This integration plan provides a comprehensive roadmap for transforming the standalone SMPTE Filename Parser into a modular, loosely-coupled feature of the Folder Structure Utility. By following the vehicle tracking architecture pattern, we ensure:

1. **Minimal Coupling**: ~30 lines of integration code in main app
2. **Self-Contained**: All functionality isolated in `filename_parser/` module
3. **Professional Quality**: Follows FSA architectural patterns (Result objects, BaseController, BaseService)
4. **Maintainable**: Clear separation of concerns, comprehensive testing
5. **Extensible**: Service interfaces allow future enhancements

**Estimated Effort**: 3-5 days full-time work
**Risk Level**: MEDIUM (manageable with phased approach)
**Complexity**: HIGH (but well-defined with existing functional code)

The phased approach allows for incremental validation, reducing risk and ensuring quality at each step. The result will be a feature that seamlessly integrates with the existing forensic application while maintaining the ability to operate independently if needed.
