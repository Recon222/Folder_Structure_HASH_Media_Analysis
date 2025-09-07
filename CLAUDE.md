# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Folder Structure Utility - A PySide6 application for professional file organization and evidence management, primarily used in forensic/law enforcement contexts. Features enterprise-grade architecture with advanced performance optimization, unified error handling, comprehensive reporting capabilities, and production-ready code quality.

## Recent Updates

### ExifTool Integration with Geolocation Visualization (ENHANCED)
- **Complete forensic metadata extraction** using ExifTool for GPS, device ID, and temporal analysis
- **Interactive map visualization** with QWebEngineView and Leaflet for location data
- **Thumbnail extraction** - Embedded EXIF thumbnails displayed in map popups with base64 encoding
- **HEIC/HEIF support** - Dynamic thumbnail generation using pillow-heif for modern iPhone formats
- **Privacy controls** - GPS obfuscation with configurable precision levels
- **KML export** - Google Earth compatible with device-based grouping
- **Batch processing** - Optimized with parallel execution and command caching
- **Device tracking** - Multiple serial number sources for identification

## Commands

### Development & Testing

**IMPORTANT**: Always use the project's virtual environment for testing and running the application:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
.venv/Scripts/python.exe main.py

# Run all tests
.venv/Scripts/python.exe -m pytest tests/ -v

# Run specific test files
.venv/Scripts/python.exe -m pytest tests/test_batch_processing.py -v
.venv/Scripts/python.exe -m pytest tests/test_files_panel.py -v
.venv/Scripts/python.exe -m pytest tests/test_performance.py -v

# Run template system tests
.venv/Scripts/python.exe -m pytest tests/test_template_*.py -v

# Run service layer tests  
.venv/Scripts/python.exe -m pytest tests/services/ -v

# Run integration tests
.venv/Scripts/python.exe -m pytest tests/test_*_integration.py -v

# Alternative: Run individual test files directly (for tests with built-in runners)
.venv/Scripts/python.exe tests/test_files_panel.py

# Format code (if black installed)
black . --line-length 100

# Lint code (if flake8 installed)
flake8 . --max-line-length 100
```

**Note**: The project uses a Windows virtual environment located at `.venv/`. Always use `.venv/Scripts/python.exe` to ensure access to PySide6 and other required dependencies.

## Architecture Overview

### Core Application Flow
1. **main.py** creates MainWindow with tabs (Forensic, Batch Processing, Hashing, Copy & Verify)
2. **Service layer configured** with dependency injection during initialization
3. User inputs are bound to **FormData** model via lambda connections
4. **Controllers** orchestrate operations through service layer (WorkflowController, CopyVerifyController, etc.)
5. **Services** handle all business logic: PathService, FileOperationService, CopyVerifyService, etc.
6. File operations execute in **QThread** subclasses with unified Result-based architecture
7. **Success messages** built by SuccessMessageService using aggregated operation results

### Key Architectural Patterns

#### 3-Tier Service-Oriented Architecture
- **Presentation Layer**: UI components (MainWindow, tabs, dialogs) handle user interaction
- **Controller Layer**: Thin orchestration layer (WorkflowController, ReportController, HashController, CopyVerifyController)
- **Service Layer**: Business logic services with dependency injection (PathService, FileOperationService, CopyVerifyService, etc.)
- **Clean separation**: Controllers coordinate, Services implement, UI presents
- **Dependency injection**: All services discoverable through ServiceRegistry for testing and modularity

#### Unified Workflow System
- **Single WorkflowController** handles both forensic and batch processing workflows
- **Batch processing** uses same forensic workflow for multiple jobs sequentially
- **No code duplication** between different processing modes
- **Consistent validation, path building, and error handling** across all workflows

#### Single FormData Instance Pattern
- MainWindow creates one FormData instance shared across all components
- UI widgets bind directly via lambdas: `lambda t: setattr(self.form_data, 'field', t)`
- No complex state management or observers needed

#### Thread Architecture (Nuclear Migration Complete)
```python
# NEW: All worker threads use unified Result-based pattern:
result_ready = Signal(Result)       # ✅ UNIFIED
progress_update = Signal(int, str)  # ✅ UNIFIED

# OLD patterns completely removed:
# finished = Signal(bool, str, dict)  ❌ REMOVED
# progress = Signal(int)              ❌ REMOVED  
# status = Signal(str)                ❌ REMOVED
```
- **FileOperationThread**: File copying with comprehensive error handling and Result objects
- **FolderStructureThread**: Folder hierarchies with unified signal system
- **BatchProcessorThread**: Sequential job processing with Result aggregation
- **ZipOperationThread**: Multi-level archives with Result-based error reporting
- **HashWorkers** (SingleHashWorker, VerificationWorker): Dedicated hash calculation threads
- **CopyVerifyWorker**: Direct copy operations with hash verification and performance tracking

#### Unified Progress Reporting
All workers use consistent progress reporting:
```python
# Unified progress signal pattern
self.progress_update.emit(percentage, status_message)

# Progress callbacks in services
progress_callback(percentage, message)
```

#### Settings Management
- **SettingsManager** singleton handles all QSettings storage
- Stores: technician info, ZIP preferences, performance settings
- Platform-specific storage (Registry/plist/.config)

#### Hybrid Archive System
- **3-Tier Performance Hierarchy**: Native 7zip (2000-4000 MB/s) > Buffered Python (290 MB/s) > Legacy Python (150 MB/s)
- **Automatic Fallback**: Ensures compatibility when 7za.exe unavailable
- **ZipController Session Management**: Three-tier choice priority (current operation > batch operation > session override > settings)
- **ZipUtility Integration**: Seamless method switching with performance metrics collection

#### Error Handling Infrastructure
- **ErrorHandler**: Thread-safe error routing from worker threads to main thread via Qt signals
- **AppLogger**: Qt signal integration for real-time UI logging with singleton pattern
- **Error Statistics**: Automatic tracking by severity with export capabilities and recent error storage (100 max)
- **UI Integration**: Callback registry system for error notifications with registration/unregistration support

### Module Structure

**core/**
- `models.py`: FormData and BatchJob dataclasses with validation and JSON serialization
- `path_utils.py`: PathSanitizer and ForensicPathBuilder with enterprise-grade security
- `buffered_file_ops.py`: High-performance buffered operations with adaptive metrics (file_ops.py removed)
- `buffered_zip_ops.py`: High-performance ZIP operations with buffered I/O
- `pdf_gen.py`: Report generation with Result objects (uses reportlab)
- `batch_queue.py`: Queue management for batch processing with recovery
- `batch_recovery.py`: Batch job recovery and state persistence
- `hash_operations.py`: Dedicated hash calculation operations with Result integration
- `hash_reports.py`: Hash verification CSV report generation
- `settings_manager.py`: Centralized settings with comprehensive validation
- `result_types.py`: **Enterprise Result object system** replacing boolean returns
- `exceptions.py`: **Thread-aware exception hierarchy** with context preservation
- `error_handler.py`: **Thread-safe centralized error handling** with Qt signal routing and UI callback registry
- `logger.py`: **Centralized logging with Qt signal support** and singleton pattern for UI integration
- `template_validator.py`: Template validation and schema enforcement
- `template_path_builder.py`: Template-based path construction
- `template_schema.py`: Template schema definitions and validation rules
- `workers/`: QThread implementations with unified Result-based architecture
- `exiftool/`: **ExifTool integration for forensic metadata extraction** (NEW)
  - `exiftool_binary_manager.py`: Binary detection and validation
  - `exiftool_command_builder.py`: Optimized command generation with caching and thumbnail extraction flags
  - `exiftool_wrapper.py`: Batch processing with parallel execution
  - `exiftool_normalizer.py`: Metadata normalization, GPS extraction, and thumbnail processing (base64 prefix handling, HEIC support)
  - `exiftool_models.py`: Data models for GPS, device, temporal data with thumbnail fields

**controllers/**
- `base_controller.py`: **Service injection foundation** with error handling and logging
- `workflow_controller.py`: **Unified orchestration engine** replacing FileController + FolderController
- `report_controller.py`: **PDF report generation with service layer integration** and backward compatibility
- `hash_controller.py`: **Enhanced hash operations** with service integration and validation
- `zip_controller.py`: **ZIP archive management** with session state and settings (preserved)
- `copy_verify_controller.py`: **Copy & Verify orchestration** with full SOA compliance

**ui/**
- `main_window.py`: Main window with tab management and error notification system
- `components/`: Reusable widgets with simplified state management
  - `files_panel.py`: **Refactored** with clean FileEntry dataclass and single source of truth
  - `form_panel.py`, `log_console.py`, `batch_queue_widget.py`: Enhanced with Result integration
  - `error_notification_system.py`: **Non-modal error notifications** with auto-dismiss
  - `elided_label.py`: **Text truncation widgets** preventing UI expansion from long file paths
  - `geo/`: **Geolocation visualization components** (NEW)
    - `geo_visualization_widget.py`: Interactive map with QWebEngineView and thumbnail display support
    - `geo_bridge.py`: Qt/JavaScript communication bridge with thumbnail data handling
    - `map_template.py`: Leaflet-based HTML map template with base64 thumbnail rendering in popups
- `tabs/`: Tab implementations (ForensicTab, BatchTab, HashingTab, CopyVerifyTab, MediaAnalysisTab)
- `dialogs/`: Settings and configuration dialogs
  - `success_dialog.py`: **Enterprise success celebrations** with native Result object support
  - `template_management_dialog.py`: Template management UI with import/export
  - `template_import_dialog.py`: Template import wizard with validation
  - `performance_monitor.py`: **Real-time performance monitoring** with metrics export and tabbed interface
  - `about_dialog.py`: Application information and version display
  - Various settings dialogs with improved error handling
- `styles/carolina_blue.py`: Theme definition

**core/services/**
- `service_registry.py`: **Enterprise dependency injection system** with thread-safe service management
- `base_service.py`: Foundation service class with logging and error handling
- `file_operation_service.py`: Business logic for file operations and validation
- `report_service.py`: Report generation service with Result integration
- `archive_service.py`: Archive creation and management service
- `path_service.py`: Path building and validation service
- `validation_service.py`: Comprehensive data validation service
- `template_management_service.py`: Template import/export and management
- `copy_verify_service.py`: **Copy & Verify business logic** with path validation and performance metrics
- `success_message_builder.py`: **Business logic service** for constructing success messages from Result objects
- `success_message_data.py`: **Type-safe data structures** for success message content and operation metadata
- `interfaces.py`: Service interface definitions and contracts (including ICopyVerifyService)
- `service_config.py`: Service configuration and initialization

**utils/**
- `zip_utils.py`: **Hybrid archive system** with 3-tier performance hierarchy (Native 7zip > Buffered Python > Legacy fallback)

**core/native_7zip/** (Native 7-Zip Integration)
- `__init__.py`: Package initialization for native 7zip components
- `binary_manager.py`: 7za.exe detection, validation, and integrity checking
- `command_builder.py`: **System-aware 7zip command optimization** for Windows forensic workloads with hardware analysis
- `controller.py`: Main controller for native 7zip operations with subprocess management

**templates/**
- `folder_templates.json`: **Built-in template configurations** (default_forensic, rcmp_basic, agency_basic)
- `samples/`: Template examples for advanced features and agency-specific configurations

**Project Dependencies**
- `requirements.txt`: **Core dependencies** - PySide6>=6.4.0, reportlab>=3.6.12, psutil>=5.9.0, hashwise>=0.1.0, pillow>=9.0.0, pillow-heif>=0.13.0 (for HEIC support)

### Important Implementation Details

#### Path Building & Sanitization
- ForensicPathBuilder creates standardized folder structures
- Uses Python format strings internally: `{occurrence_number}`, `{business_name}`
- Law enforcement format uses military date format: `30JUL25_2312`
- Comprehensive path sanitization removes invalid characters for cross-platform compatibility

#### File Operation Architecture (Consolidated)
1. **Unified System**: Single `BufferedFileOperations` class (legacy file_ops.py removed)
2. **Intelligent Buffering**: Adaptive buffer sizing (256KB-10MB) based on file size categories
3. **Performance Metrics**: Comprehensive tracking with PerformanceMetrics dataclass
4. **Result Objects**: All operations return `FileOperationResult` with type-safe error handling
5. **Thread-Safe Cancellation**: Event-based cancellation system with `cancelled` flag and `cancel_event`
6. **Forensic-Grade Integrity**: All operations use `os.fsync()` after file copying to ensure complete disk writes

#### Hash Verification & Operations
- **Integrated Hash Calculation**: Optional SHA-256 during copy operations with streaming support
- **Dedicated Hash Tab**: Standalone hashing functionality with SingleHashWorker and VerificationWorker
- **Result-Based Error Handling**: Hash failures return `HashVerificationError` with context
- **Accelerated Processing**: Uses hashwise library when available for parallel hashing
- **CSV Generation**: Hash verification CSV reports with comprehensive file integrity data
- **Validation**: Hash operations include comprehensive path and algorithm validation

#### Batch Processing (Enhanced)
- **Queue Management**: BatchQueue with comprehensive job validation and recovery
- **Independent Jobs**: Each job has isolated FormData instance preventing cross-contamination  
- **Result Aggregation**: BatchProcessorThread uses Result objects for error aggregation
- **Recovery System**: Queue state persists across application restarts with automatic recovery
- **Progress Tracking**: Individual job progress with overall batch completion metrics
- **Error Handling**: Continuation on individual job failures with comprehensive error reporting

#### Report Generation (Result-Based)
- **Time Offset Sheet**: Documents DVR time discrepancies with enhanced formatting
- **Technician Log**: Processing details and file inventory with comprehensive metadata
- **Hash CSV**: File integrity verification data with Result-based generation
- **Report Organization**: Reports saved to `output/OccurrenceNumber/Documents/` with consistent structure
- **Error Handling**: All report generation returns `ReportGenerationResult` objects
- **ZIP Integration**: Optional archive creation with configurable compression levels

#### Native 7-Zip Archive Integration (Hybrid System)
- **Performance**: Achieves 1,071 MB/s (3.7x improvement over 290 MB/s baseline)
- **Format**: Creates .zip files using native 7za.exe with -tzip flag for compatibility
- **Fallback**: Graceful degradation to BufferedZipOperations when 7za.exe unavailable
- **Settings**: ArchiveMethod enum with NATIVE_7ZIP (default), BUFFERED_PYTHON, AUTO modes
- **Binary Management**: Automatic detection and validation of 7za.exe in bin/ directory
- **Thread Optimization**: Capped at 16 threads for ZIP format compatibility
- **Command Building**: Simplified parameter set removing problematic 7z-specific flags
- **Result Integration**: All operations return ArchiveOperationResult with comprehensive error context

#### Media Analysis & Thumbnail Extraction
- **ExifTool Integration**: Forensic metadata extraction with `-b` flag for base64 thumbnail output
- **Dual Extraction Approach**: Native EXIF thumbnails for JPEG/RAW, dynamic generation for HEIC/HEIF
- **Base64 Processing**: Automatic stripping of ExifTool's "base64:" prefix for proper display
- **HEIC Support**: Uses pillow-heif to register HEIF opener with PIL for thumbnail generation
- **Map Popup Display**: Thumbnails embedded as base64 data URIs in Leaflet map popups
- **Fallback Chain**: ThumbnailImage → PreviewImage → JpgFromRaw → HEIC generation
- **Size Optimization**: Generated thumbnails limited to 200x200 pixels with LANCZOS resampling
- **Memory Management**: Thumbnails stored in ExifToolMetadata objects, cleared with metadata

### Testing & Sample Data

Test with provided JSON files:
- `sample_dev_data.json`: Complete form data with all fields
- `sample_dev_data2.json`: Alternative test dataset
- `sample_no_business.json`: Minimal data without business info

Load via: File → Load Form Data

### Performance Considerations

- **Intelligent Buffer Sizing**: Automatically adjusts based on file size categories (256KB for small, up to 10MB for large files)
- **Thread Safety**: All UI updates via Qt signals with unified Result-based error propagation
- **Memory Management**: Streaming operations for large files prevent memory exhaustion
- **Performance Metrics**: Real-time tracking with PerformanceMetrics dataclass including speed sampling
- **Progress Optimization**: Updates throttled to prevent UI flooding while maintaining responsiveness
- **Resource Monitoring**: CPU and memory usage monitoring integrated into status display

### Enterprise Architecture Features

#### Result Objects System
```python
# All operations return Result objects instead of boolean/exception patterns
def operation() -> Result[DataType]:
    try:
        # operation logic
        return Result.success(data)
    except Exception as e:
        error = FSAError("message", user_message="friendly message")
        return Result.error(error)
```

#### Thread-Aware Error Handling
- **Centralized ErrorHandler**: Routes errors from worker threads to main thread via Qt signals
- **Context Preservation**: Errors maintain thread information, timestamps, and operation context
- **Error Statistics**: Automatic tracking and aggregation of errors by severity
- **User-Friendly Messages**: Separate technical and user-facing error messages

#### Simplified State Management
- **FilesPanel Refactor**: Single `List[FileEntry]` replaces complex multiple data structures  
- **Type Safety**: FileEntry dataclass with Literal types for 'file'/'folder'
- **No Synchronization Issues**: Single source of truth eliminates state consistency problems

#### Non-Modal Error Notifications
- **Auto-Dismissing Notifications**: Error messages appear without blocking UI interaction
- **Severity-Based Styling**: Visual indicators for different error severities
- **Queue Management**: Multiple errors handled gracefully with notification stacking

#### Enterprise Success Message System
- **Business Logic Separation**: `SuccessMessageBuilder` service handles message construction logic
- **Type-Safe Data Structures**: `SuccessMessageData` and operation-specific data classes
- **Native Result Object Support**: Direct acceptance of FileOperationResult, ReportGenerationResult objects
- **Rich Content Display**: Performance metrics, file counts, report summaries, ZIP archive details
- **Modal Celebrations**: Prominent success dialogs with Carolina Blue theming and celebration emojis

#### Template Management System
- **Template Import/Export**: JSON-based template sharing and backup with comprehensive validation
- **Template Validation**: Schema-based validation with comprehensive error reporting and user feedback
- **Template Path Building**: Dynamic path construction from template definitions with format string support
- **UI Integration**: Management dialog with import/export capabilities and template preview
- **Service Architecture**: Dedicated TemplateManagementService with full Result object integration
- **Schema Enforcement**: Template schema validation ensures data integrity and compatibility

### Common Development Tasks

#### Adding a New Report Type
1. Extend PDFGenerator in `core/pdf_gen.py` to return `ReportGenerationResult`
2. Add generation method to ReportController using Result objects
3. Update UI to handle Result objects and show appropriate error notifications

#### Adding a New Tab
1. Create tab class in `ui/tabs/` following Result object patterns
2. Emit unified signals: `process_requested` and `log_message`
3. Add to MainWindow._setup_ui() and connect Result-based signal handlers
4. Ensure proper error handling with ErrorNotificationManager integration

#### Adding a New Worker Thread  
1. Inherit from `FileWorkerThread` or `BaseWorkerThread` in `core/workers/`
2. Implement `execute()` method returning Result objects
3. Use unified signals: `result_ready = Signal(Result)` and `progress_update = Signal(int, str)`
4. Handle cancellation via `check_cancellation()` and `is_cancelled()`

#### Modifying Form Fields
1. Update FormData in `core/models.py` with proper validation
2. Update FormPanel UI in `ui/components/form_panel.py`
3. Update path building logic in `core/path_utils.py` if new fields are used in folder names
4. Update JSON serialization in FormData.to_dict/from_dict methods
5. Update validation logic if new fields require specific validation rules

#### Adding a New Success Message
1. Create operation-specific data class in `core/services/success_message_data.py`
2. Add business logic method to `SuccessMessageBuilder` that returns `SuccessMessageData`
3. Use `SuccessDialog.show_success_message(message_data, parent)` for display
4. **Total time: 3-4 minutes** following established patterns

## Testing and Debugging Philosophy

### CRITICAL: Proper Testing Standards

**NEVER edit tests just to make them pass.** When tests fail, follow this decision tree:

1. **If the test is wrong (testing incorrect behavior):**
   - Fix the test to properly validate the intended functionality
   - Document why the test was incorrect
   - Ensure the corrected test actually validates real functionality

2. **If the code has a bug:**
   - Fix the underlying code issue
   - Verify the fix resolves the root cause
   - Ensure tests validate actual functionality, not just pass

3. **If both test and code have issues:**
   - Fix the code first to implement correct behavior
   - Then fix the test to properly validate that behavior
   - Never compromise on functional correctness

### Test Integrity Guidelines

- **Tests must validate real functionality**, not just exercise code paths
- **Failing tests indicate problems** - investigate the root cause thoroughly
- **Quick fixes to tests are code smells** - they usually hide real issues
- **When in doubt, verify manually** - run the actual functionality being tested
- **Document test changes** - explain why a test needed modification

### Error Handling Testing Standards

- **Test actual error propagation**, not just error creation
- **Verify thread-safe error handling** across Qt worker threads
- **Test user-facing error messages** are appropriate and helpful
- **Validate type safety** with real operations and data flows
- **Test error context preservation** through the entire system

### Code Quality Standards

- **Functional correctness over cosmetic fixes**
- **Thread safety is non-negotiable** in Qt applications
- **Type safety must be enforced** - Result objects should prevent runtime errors
- **User experience matters** - error messages must be actionable and clear
- **Performance testing should use realistic data sizes** and scenarios
- As you create each feature or document use Memory MCP to:
  1. Add discovered components to the memory graph
  2. Track service interfaces and their implementations
  3. Record plugin conversion decisions and rationale
  4. Build a comprehensive dependency map
  5. Make sure the addition is not redundant and already included in the graph