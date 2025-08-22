# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Folder Structure Utility - A PySide6 application for professional file organization and evidence management, primarily used in forensic/law enforcement contexts. Features optimized file operations with optional buffering, batch processing, and comprehensive reporting capabilities.

## Commands

### Development & Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py

# Run specific tests
python -m pytest tests/test_batch_processing.py -v
python -m pytest tests/test_files_panel.py -v
python -m pytest tests/test_performance.py -v

# Format code (if black installed)
black . --line-length 100

# Lint code (if flake8 installed)
flake8 . --max-line-length 100
```

## Architecture Overview

### Core Application Flow
1. **main.py** creates MainWindow with tabs (Forensic, Batch Processing)
2. User inputs are bound to **FormData** model via lambda connections
3. File operations execute in **QThread** subclasses to maintain UI responsiveness
4. Operations use either standard or **BufferedFileOperations** based on settings
5. Results generate PDFs (Time Offset, Technician Log, Hash CSV) and optional ZIP archives

### Key Architectural Patterns

#### Single FormData Instance Pattern
- MainWindow creates one FormData instance shared across all components
- UI widgets bind directly via lambdas: `lambda t: setattr(self.form_data, 'field', t)`
- No complex state management or observers needed

#### Thread Architecture
```python
# All worker threads follow this pattern:
finished = Signal(bool, str, dict)  # success, message, results
progress = Signal(int)
status = Signal(str)
```
- FileOperationThread handles file copying with hash calculation
- FolderStructureThread creates folder hierarchies
- BatchProcessorThread processes queued jobs sequentially
- ZipOperationThread creates multi-level archives

#### Dual-Signal Progress Reporting
Workers emit paired signals for UI updates:
```python
lambda pct, msg: (self.progress.emit(pct), self.status.emit(msg))
```

#### Settings Management
- **SettingsManager** singleton handles all QSettings storage
- Stores: technician info, ZIP preferences, performance settings
- Platform-specific storage (Registry/plist/.config)

### Module Structure

**core/**
- `models.py`: FormData dataclass with validation and JSON serialization
- `templates.py`: FolderTemplate system for dynamic path generation
- `file_ops.py`: Standard file operations with SHA-256 hashing
- `buffered_file_ops.py`: High-performance buffered operations with metrics
- `pdf_gen.py`: Report generation (uses reportlab)
- `batch_queue.py`: Queue management for batch processing
- `settings_manager.py`: Centralized settings with QSettings
- `workers/`: QThread implementations for async operations

**controllers/**
- `file_controller.py`: File selection and operation coordination
- `folder_controller.py`: Folder structure creation logic
- `report_controller.py`: PDF report generation control

**ui/**
- `main_window.py`: Main window with tab management
- `components/`: Reusable widgets (FormPanel, FilesPanel, LogConsole, BatchQueueWidget)
- `tabs/`: Tab implementations (ForensicTab, BatchTab)
- `dialogs/`: Settings and configuration dialogs
- `styles/carolina_blue.py`: Theme definition

**utils/**
- `zip_utils.py`: Multi-level ZIP creation with compression settings

### Important Implementation Details

#### Path Building & Sanitization
- ForensicPathBuilder creates standardized folder structures
- Template system uses Python format strings: `{occurrence_number}`, `{business_name}`
- Law enforcement templates use military date format: `{extraction_start}` = `30JUL25_2312`
- Path sanitization removes invalid characters for cross-platform compatibility

#### File Operation Modes
1. **Standard Mode**: Sequential copying with real-time hash calculation
2. **Buffered Mode**: High-performance with adaptive buffer sizing (256KB-10MB)
3. Both modes support cancellation via `cancelled` flag
4. **Forensic-Grade Integrity**: All modes use `os.fsync()` after file copying to ensure complete disk writes

#### Hash Verification
- Optional SHA-256 calculation during copy
- Failures logged but don't block operations
- CSV report generated only if hashes calculated
- Accelerated with hashwise library when available

#### Batch Processing
- Jobs queued with independent FormData instances
- Sequential processing with automatic recovery
- Each job generates complete folder structure and reports
- Recovery system persists queue state across sessions

#### Report Generation
- **Time Offset Sheet**: Documents DVR time discrepancies
- **Technician Log**: Processing details and file inventory
- **Hash CSV**: File integrity verification data
- Reports saved to `output/OccurrenceNumber/Documents/`

### Testing & Sample Data

Test with provided JSON files:
- `sample_dev_data.json`: Complete form data with all fields
- `sample_dev_data2.json`: Alternative test dataset
- `sample_no_business.json`: Minimal data without business info

Load via: File → Load Form Data

### Performance Considerations

- **Buffer Sizing**: Automatically adjusts based on file sizes (256KB for small, up to 10MB for large)
- **Thread Safety**: All UI updates via Qt signals, no direct cross-thread access
- **Memory Management**: Streaming operations for large files prevent memory exhaustion
- **Progress Granularity**: Updates throttled to prevent UI flooding

### Common Development Tasks

#### Adding a New Report Type
1. Extend PDFGenerator in `core/pdf_gen.py`
2. Add generation method to ReportController
3. Update UI to trigger report generation

#### Adding a New Tab
1. Create tab class in `ui/tabs/`
2. Emit signals for process_requested and log_message
3. Add to MainWindow._setup_ui()
4. Connect signals for processing and logging

#### Modifying Form Fields
1. Update FormData in `core/models.py`
2. Update FormPanel UI in `ui/components/form_panel.py`
3. Update template format dict in `core/templates.py`
4. Update JSON loading/saving in FormData.to_dict/from_dict