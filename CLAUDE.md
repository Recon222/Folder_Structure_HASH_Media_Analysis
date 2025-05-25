# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Folder Structure Utility - A PySide6 (Qt) application for professional file organization and evidence management. The app has two main modes: Forensic Mode (law enforcement) and Custom Mode (flexible template building).

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

### Dependencies
- PySide6 >= 6.4.0 (Qt UI framework)
- reportlab >= 3.6.12 (PDF generation)
- Python 3.7+

## Architecture Overview

### Core Application Flow
1. **main.py** initializes MainWindow with tabs for Forensic and Custom modes
2. User fills FormData fields which are bound to UI widgets via lambda connections
3. File operations run in separate QThreads (FileOperationThread, FolderStructureThread) to maintain UI responsiveness
4. Results trigger PDF generation and optional ZIP creation

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
- FolderTemplate class handles dynamic path building with format strings
- Templates support nested folder structures via indentation
- Custom templates saved in QSettings for persistence

#### Error Handling
- Worker threads emit error signals for graceful error propagation
- Main window displays QMessageBox for user-facing errors
- File operation errors are logged to the console widget
- Hash verification failures are reported but don't stop the operation

### Module Responsibilities

**core/**
- `models.py`: FormData dataclass with validation and JSON serialization
- `templates.py`: FolderTemplate and FolderBuilder for path generation
- `file_ops.py`: FileOperations class with hash verification
- `pdf_gen.py`: PDFGenerator for reports (Time Offset, Technician Log, Hash CSV)
- `workers/`: QThread subclasses for file and folder operations

**controllers/**
- `file_controller.py`: Handles file selection and operations
- `folder_controller.py`: Manages folder structure creation
- `report_controller.py`: Controls PDF report generation

**ui/**
- `main_window.py`: Main application window with tab management
- `components/`: Reusable UI components (files panel, form panel, log console)
- `custom_template_widget.py`: Custom template builder with drag-drop support, live preview
- `styles/`: Theme definitions (Carolina Blue color scheme)

**utils/**
- `zip_utils.py`: Multi-level ZIP archive creation with compression settings

### Important Implementation Details

1. **Folder Structure Preservation**: When adding folders, the app preserves complete directory hierarchies using `path.rglob('*')`

2. **Hash Verification**: SHA-256 hashes calculated during copy for forensic integrity

3. **Path Sanitization**: FolderTemplate._sanitize_path_part() removes invalid characters for cross-platform compatibility

4. **Custom Mode Tab Creation**: Templates can be saved as new tabs via signal emission:
   ```python
   self.custom_template_widget.create_tab_requested.connect(self.create_custom_tab)
   ```

5. **ZIP Archive Levels**: Created alongside folder structures at root/location/datetime levels based on settings

### UI State Management
- QSettings stores user preferences (technician info, ZIP settings, custom templates)
- Form data can be saved/loaded as JSON for batch processing
- Progress bars show/hide based on operation state

### Persistent Settings (QSettings)
- Technician information (name, badge number)
- ZIP compression preferences and levels
- Custom templates and saved tabs
- Window geometry and state
- Last used directories

### Custom Mode Template Format
Templates use Python format strings with available fields:
- Form fields: {occurrence_number}, {business_name}, {location_address}, etc.
- Date/time: {date}, {time}, {year}, {month}, {day}
- Extraction times: {extraction_start}, {extraction_end}

Indentation in template editor determines folder hierarchy.

### Sample Data
For testing and development, use the provided sample JSON files:
- `sample_dev_data.json` - Full form data example with all fields
- `sample_dev_data2.json` - Alternative test data set
- `sample_no_business.json` - Minimal data example without business info

Load these via File → Load Form Data in the application.

### Testing
Note: No automated test suite is currently implemented. Manual testing is required for all changes.