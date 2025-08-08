# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Folder Structure Utility - A PySide6 (Qt) application for professional file organization and evidence management. The app is designed for Forensic Mode (law enforcement) evidence processing with efficient file operations and batch processing capabilities.

## Commands

### Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Development Tools
```bash
# Install development tools (recommended)
pip install flake8 black

# Format code
black .

# Lint code
flake8 .
```

### Testing
```bash
# Run integration test for batch processing
python test_batch_integration.py

# Note: No automated test suite currently implemented
# Manual testing required for all changes
```

### Dependencies
- PySide6 >= 6.4.0 (Qt UI framework)
- reportlab >= 3.6.12 (PDF generation)
- psutil >= 5.9.0 (System monitoring)
- Python 3.7+
- hashwise >= 0.1.0 (for accelerated parallel hashing)

## Architecture Overview

### Core Application Flow
1. **main.py** initializes MainWindow with tabs for Forensic mode and Batch Processing
2. User fills FormData fields which are bound to UI widgets via lambda connections
3. File operations use parallel hashing when available via hashwise library
4. Operations run in separate QThreads (FileOperationThread, FolderStructureThread) to maintain UI responsiveness
5. Results trigger PDF generation and optional ZIP creation

### Key Architectural Patterns

#### Data Binding
The app uses direct attribute binding between UI widgets and FormData model:
```python
self.occ_number.textChanged.connect(lambda t: setattr(self.form_data, 'occurrence_number', t))
```

#### Thread Architecture
- File copying operations run in QThread subclasses
- Progress signals update UI via Qt signal/slot mechanism
- Thread classes bridge business logic to UI without coupling

#### Template System
- FolderTemplate class handles forensic folder structure path building
- Uses standardized law enforcement folder hierarchy

#### Error Handling
- Worker threads emit error signals for graceful error propagation
- Main window displays QMessageBox for user-facing errors
- File operation errors are logged to the console widget
- Hash verification failures are reported but don't stop the operation

### Module Responsibilities

**core/**
- `models.py`: FormData dataclass with validation and JSON serialization
  - Includes `include_tech_in_offset` flag for selective technician info inclusion
- `templates.py`: FolderTemplate and FolderBuilder for path generation
- `file_ops.py`: FileOperations class with hash verification and parallel hashing support
- `pdf_gen.py`: PDFGenerator for reports
  - Time Offset Report (includes tech info when checkbox selected)
  - Upload Log (always includes tech info, no signature fields)
  - Hash CSV (SHA-256 verification results)
  - Uses "Prepared for upload on" timestamp format
- `workers/`: QThread subclasses for file and folder operations
- `batch_queue.py`: Queue management for batch processing
- `batch_recovery.py`: Recovery system for interrupted batch operations

**controllers/**
- `file_controller.py`: Handles file selection and operations
- `folder_controller.py`: Manages folder structure creation
- `report_controller.py`: Controls PDF report generation

**ui/**
- `main_window.py`: Main application window with tab management
- `components/`: Reusable UI components
  - `form_panel.py`: Form with Video Start/End times, includes tech info checkbox
  - `files_panel.py`: File and folder selection
  - `log_console.py`: Operation logging
  - `batch_queue_widget.py`: Batch job queue management
- `dialogs/`: Application dialogs
  - `user_settings.py`: Tabbed settings (General, Analyst/Technician, Documentation)
  - `zip_settings.py`: ZIP compression configuration
  - `about.py`: Application information
- `styles/`: Theme definitions (Carolina Blue color scheme)
- `tabs/`: Tab implementations (ForensicTab, BatchTab)

**utils/**
- `zip_utils.py`: Multi-level ZIP archive creation with compression settings

### Important Implementation Details

1. **Folder Structure Preservation**: When adding folders, the app preserves complete directory hierarchies using `path.rglob('*')`

2. **Hash Verification**: SHA-256 hashes calculated during copy for forensic integrity, with parallel processing via hashwise when available

3. **Path Sanitization**: FolderTemplate._sanitize_path_part() removes invalid characters for cross-platform compatibility

4. **ZIP Archive Levels**: Created alongside folder structures at root/location/datetime levels based on settings

6. **Batch Processing System**: Full queue-based batch processing with:
   - Save/load queue functionality
   - Pause/resume capabilities  
   - Crash recovery with auto-save
   - Sequential job processing with progress tracking

### UI State Management
- QSettings stores user preferences (technician info, ZIP settings)
- Form data can be saved/loaded as JSON for batch processing
- Progress bars show/hide based on operation state

### Persistent Settings (QSettings)
- Technician information (name, badge number) - stored in User Settings dialog
- ZIP compression preferences and levels
- Window geometry and state
- Last used directories
- Hash calculation preferences (combined with CSV generation)
- PDF generation preferences (time offset, upload log)
- UI behavior preferences (auto-scroll, exit confirmation)


### Sample Data
For testing and development, use the provided sample JSON files:
- `sample_dev_data.json` - Full form data example with all fields
- `sample_dev_data2.json` - Alternative test data set
- `sample_no_business.json` - Minimal data example without business info

Load these via File → Load Form Data in the application.

### Testing
Note: No automated test suite is currently implemented. Manual testing is required for all changes.

Integration test available for batch processing:
```bash
python test_batch_integration.py
```

## Key Architectural Patterns Not Obvious from File Structure

### Dual-Signal Progress Reporting
All worker threads emit paired `progress(int)` and `status(str)` signals using lambda pattern:
```python
lambda pct, msg: (self.progress.emit(pct), self.status.emit(msg))
```

### Thread Lifecycle Management
- MainWindow stores thread references as instance variables for proper cleanup
- `closeEvent` waits for all threads before closing
- Cancellation via `cancelled` flag, not thread termination
- Workers check cancellation flag in inner loops

### Component Signal Forwarding
Components forward signals to maintain loose coupling:
- ForensicTab → MainWindow signal chain
- Avoids direct component access
- Example: `self.log_message.connect(self.parent().log_message.emit)`

### Report Output Reorganization
Reports follow specific directory structure:
- Files: `output/OccurrenceNumber/Business @ Address/DateTime/`
- Reports: `output/OccurrenceNumber/Documents/`
- ZIP created at occurrence level to include both

### PDF Generation Behavior
- PDFs generate automatically after file copy (no user prompts)
- Generation controlled by Documentation tab settings in User Settings
- Timestamps use actual generation time for accuracy
- Upload Log shows Business before Location in details
- Technician info persists across sessions (User Settings → Analyst/Technician tab)

### Time Offset Format Flexibility
Handles both legacy (integer minutes) and new text formats:
- Legacy: `120` (minutes)
- New: `"DVR is 2 hr 0 min 0 sec AHEAD of realtime"`
- Auto-conversion on JSON load

### Worker Result Pattern
All workers follow consistent result propagation:
```python
finished = pyqtSignal(bool, str, object)  # success, message, results
```
Results stored in MainWindow enable operation chaining.

### Form Data as Central State
- Single FormData instance created in MainWindow
- Components bind via lambdas: `lambda t: setattr(self.form_data, 'field', t)`
- No complex state management needed
- JSON serialization preserves QDateTime objects
- Form fields include:
  - Video Start/End times (formerly Extraction Start/End)
  - Include tech info checkbox for time offset documents
  - No upload timestamp field (generated automatically in PDFs)

### Hash Verification Philosophy
Optional at multiple levels:
- Global user preference
- Thread parameter
- Failures logged but don't block operation
- CSV report only if hashes calculated

### Settings Storage Strategy
All settings in QSettings (no config files):
- Windows: Registry
- macOS: plist
- Linux: .config file
- Simplifies deployment but less portable

### Parallel Hashing with Hashwise
When hashwise is available, the application uses parallel hashing to significantly improve performance:
- Automatically detects and uses hashwise for batches of 4+ files
- Falls back to ThreadPoolExecutor for smaller batches
- Gracefully degrades to sequential hashing if neither is available
- SHA-256 is the default algorithm for forensic integrity