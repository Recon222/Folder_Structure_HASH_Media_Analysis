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
- psutil >= 5.9.0 (System monitoring)
- Python 3.7+
- Optional: hashwise (for accelerated parallel hashing)

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
- **Performance Optimization Modules (New):**
  - `adaptive_performance.py`: Master controller for performance optimization
  - `adaptive_file_operations.py`: Adaptive file copying with priority modes
  - `disk_analyzer.py`: Disk type detection (SSD/HDD/NVMe) and benchmarking
  - `workload_analyzer.py`: Dynamic threshold calculation and file grouping
  - `numa_optimizer.py`: NUMA topology detection and CPU affinity
  - `thermal_manager.py`: CPU temperature monitoring and throttling
  - `storage_optimizer.py`: Storage queue depth and I/O monitoring

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

### Dynamic Tab Creation from Templates
Custom templates can spawn persistent tabs:
1. CustomTemplateWidget emits `create_tab_requested`
2. MainWindow creates simplified tab with FilesPanel + process button
3. Each tab maintains independent file selection state

### Report Output Reorganization
Reports follow specific directory structure:
- Files: `output/OccurrenceNumber/Business @ Address/DateTime/`
- Reports: `output/OccurrenceNumber/Documents/`
- ZIP created at occurrence level to include both

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

## Advanced Performance Optimization Architecture

### Adaptive Performance Controller
The `AdaptivePerformanceController` orchestrates all optimizations:
- Analyzes hardware (disk type, NUMA topology, CPU temperature)
- Profiles workload characteristics (file sizes, types, patterns)
- Selects optimal configuration (workers, buffer sizes, priorities)
- Learns from performance history to improve future operations

### Three Optimization Modes
1. **LATENCY**: Minimize response time
   - Limited workers (max 4)
   - Small buffers (256KB max)
   - Immediate file processing
   
2. **THROUGHPUT**: Maximize total processing speed
   - Maximum workers (based on hardware)
   - Large buffers (up to 10MB)
   - Batch processing by file size
   
3. **BALANCED**: Adaptive approach
   - Dynamic worker allocation
   - Mixed strategies based on file sizes

### Hardware-Aware Optimizations
- **Disk Detection**: Identifies SSD/HDD/NVMe and adjusts parallelism
  - NVMe: Up to 32 workers
  - SSD: Up to 16 workers  
  - HDD: Max 2 workers (avoids seek thrashing)
  
- **NUMA Support**: Distributes work across CPU nodes for memory locality
- **Thermal Management**: Reduces workers when CPU temperature is high
- **I/O Monitoring**: Adjusts queue depth based on storage load

### Dynamic File Grouping
Files are categorized by adaptive thresholds:
- **Tiny** (<1MB): Maximum parallelism, batched processing
- **Small**: High parallelism
- **Medium**: Moderate parallelism
- **Large**: Limited parallelism
- **Huge** (>1GB): Sequential processing, memory-mapped I/O

### Performance Learning
The system tracks operation metrics and learns optimal configurations:
```python
# Metrics tracked per operation
{
    'file_size': size,
    'duration': time,
    'efficiency': score,
    'config': {...}
}
```

### Integration with Existing Architecture
- Adaptive operations can replace standard FileOperations
- Progress callbacks remain compatible
- Thread cancellation supported
- Hash calculation optimized with Hashwise when available