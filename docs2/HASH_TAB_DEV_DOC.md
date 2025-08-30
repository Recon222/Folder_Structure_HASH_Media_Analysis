# Hash Tab Development Documentation

## Table of Contents
1. [Executive Overview](#executive-overview) - Non-technical summary
2. [Developer Technical Reference](#developer-technical-reference) - Implementation details

---

## Executive Overview

### Purpose
The Hash Tab provides professional-grade file integrity verification for forensic and evidence management workflows. It calculates cryptographic hashes (SHA-256, SHA-1, MD5) and compares files between source and target locations to detect modifications, corruption, or tampering.

### Key Capabilities
- **Single Hash Operation**: Calculate hashes for selected files/folders
- **Bidirectional Hash Verification**: Compare source vs target files to detect mismatches and missing files
- **Missing File Detection**: Identifies files missing from either source or target locations
- **Multiple Algorithms**: SHA-256, SHA-1, MD5 support
- **Real-time Progress**: Live updates during processing with detailed file counts
- **Comprehensive Reporting**: CSV exports with complete verification results including missing files
- **Intelligent Error Detection**: Distinguishes between hash mismatches and missing files

### User Interface Design
The Hash Tab uses a modern three-column layout:

**Column 1: Single Hash Operation**
- File/folder selection panel
- Algorithm choice
- Calculate button
- File count display

**Column 2: Hash Verification**  
- Source files panel (left side)
- Target files panel (right side)
- Verify button
- Comparison status

**Column 3: Results & Export**
- Operation status cards with visual indicators
- Performance metrics (speed, file counts)
- One-click CSV export buttons
- Session statistics

**Bottom: Processing Console**
- Real-time progress bar with percentage
- Detailed operation logs
- Status messages and error notifications

### Data Flow
1. **File Selection**: User selects files/folders via drag-drop or browse
2. **Algorithm Selection**: Choose hash algorithm from header dropdown
3. **Operation Launch**: Click Calculate or Verify to start processing
4. **Background Processing**: QThread workers handle hash calculations
5. **Progress Updates**: Real-time UI updates via Qt signals
6. **Results Display**: Status cards show completion with metrics
7. **Export Options**: CSV generation with detailed hash data

### Key Benefits
- **Lightning Fast**: Optimized for large file sets (tested with 229 files, 30GB)
- **Forensic Grade**: Suitable for evidence integrity verification
- **User Friendly**: Clear visual feedback and detailed error messages
- **Professional**: Enterprise-quality reporting and documentation
- **Reliable**: Robust error handling and recovery mechanisms

---

## Developer Technical Reference

### Architecture Overview

#### Core Components
```
ui/tabs/hashing_tab.py          - Main UI implementation
core/workers/hash_worker.py     - Background processing threads
core/hash_operations.py         - Bidirectional comparison algorithms
core/hash_reports.py           - CSV report generation with missing file support
controllers/hash_controller.py - Operation coordination
core/exceptions.py            - Hash-specific error types
```

#### Thread Architecture
- **SingleHashWorker**: Calculates hashes for file lists using `BufferedHashOperations`
- **VerificationWorker**: Compares source/target hashes using `HashComparisonOperations`
- **Unified Signals**: `result_ready(Result)` and `progress_update(int, str)`
- **Result Objects**: All operations return `Result[HashOperationResult]` instead of boolean patterns

#### UI Component Structure
```python
class HashingTab(QWidget):
    # Three-panel vertical layout
    _create_header_bar()           # Algorithm selection, status, controls
    _create_operations_section()   # Three-column operations
    _create_console_section()      # Progress and logging

class OperationStatusCard(QFrame):
    # Visual status display with export integration
    set_operation_data()           # Updates status, metrics, export availability
    
class ResultsManagementPanel(QFrame):
    # Operation history and session statistics
    update_operation_status()      # Coordinates status card updates
```

#### Hash Processing Pipeline
```python
# Single Hash Operation Flow
1. FilesPanel.get_all_items() → List[Path]
2. HashController.start_single_hash_operation(paths, algorithm)
3. SingleHashWorker.execute() → Result[HashOperationResult]
4. BufferedHashOperations.hash_files_parallel()
5. Result emission via unified signal system
6. UI updates via _on_single_hash_result()

# Bidirectional Verification Operation Flow  
1. Source/Target FilesPanel → List[Path] each
2. HashController.start_verification_operation(source, target, algorithm)
3. VerificationWorker.execute() → Result[HashOperationResult] 
4. HashComparisonOperations.verify_hashes() with bidirectional comparison
5. Phase 1: Source→Target comparison (missing targets, hash mismatches)
6. Phase 2: Target→Source comparison (missing sources)
7. Comprehensive verification results with detailed categorization
8. Enhanced error messages with file-specific details and missing file reports
```

#### Error Handling System
```python
# Enhanced HashVerificationError with detailed reporting
class HashVerificationError(FSAError):
    # Supports file-specific context (file paths, hashes)
    # Generates user-friendly messages with mismatch details
    # Distinguishes between hash mismatches and missing files
    
def _create_detailed_verification_message():
    # Produces comprehensive error reports including:
    # - File names of mismatched files with hash comparisons
    # - Source/target hash values (truncated for readability)
    # - Missing target files (files in source but not target)
    # - Missing source files (files in target but not source)
    # - Files with processing errors (permissions, corruption)
    # - Actionable recommendations for remediation
    # - Separate sections for different error types
```

#### Key Libraries and Dependencies
- **PySide6**: Qt-based UI framework with signal/slot architecture
- **hashlib**: Python standard library for hash calculations
- **pathlib**: Modern path handling and file operations  
- **threading**: QThread-based background processing
- **csv**: Report generation and data export
- **datetime**: Timestamp and performance metrics

#### Performance Optimizations
- **Intelligent Buffering**: Adaptive buffer sizes based on file characteristics
- **Parallel Processing**: Multi-threaded hash calculations when beneficial
- **Progress Throttling**: UI updates limited to prevent flooding
- **Memory Management**: Streaming operations for large files
- **Result Caching**: Operation results maintained for export without recalculation

#### Configuration and Settings
```python
# Algorithm Selection
settings.hash_algorithm = 'sha256'|'sha1'|'md5'

# UI State Management  
operation_active: bool          # Prevents concurrent operations
current_operation_type: str     # Tracks 'single_hash'|'verification'
current_*_results: dict        # Cached results for export
```

#### Signal/Slot Connections
```python
# Unified progress reporting
worker.progress_update.connect(self._on_progress_update)
worker.result_ready.connect(self._on_*_result)

# UI event handling
algorithm_combo.currentTextChanged.connect(self._on_algorithm_changed)
*_files_panel.files_changed.connect(self._update_*_state)
results_panel.export_requested.connect(self._handle_export_request)
```

#### CSV Export Format
```csv
file_path,algorithm,hash_value,file_size,status,error_message,timestamp
/path/to/file.txt,sha256,a1b2c3...,1024,success,,2025-08-29T08:30:00Z
/missing/file.txt,sha256,,0,missing_target,No target file found,2025-08-29T08:30:01Z
/extra/file.txt,sha256,d4e5f6...,2048,missing_source,No source file found,2025-08-29T08:30:02Z
```

#### Bidirectional Verification Results
Verification operations produce comprehensive results including:
- **Hash Matches**: Files with identical hashes in source and target
- **Hash Mismatches**: Files present in both locations but with different hashes
- **Missing Targets**: Files in source location but missing from target
- **Missing Sources**: Files in target location but missing from source
- **Processing Errors**: Files that couldn't be processed due to access/corruption issues

#### Testing and Validation
- **Bidirectional Hash Verification**: Tested with 229 vs 228 file datasets (30GB)
- **Missing File Detection**: Accurately identifies missing files in either direction
- **Hash Mismatch Detection**: Correctly identifies transcoded/modified files
- **Error Categorization**: Distinguishes between hash mismatches and missing files
- **Comprehensive Reporting**: CSV exports include all verification results with proper status
- **Error Recovery**: Graceful handling of permission errors, missing files, processing failures
- **Performance**: Processes large datasets with real-time feedback
- **UI Responsiveness**: Non-blocking operations with progress indicators
- **Export Functionality**: Results available for export even when verification fails

#### Future Enhancements
- **Additional Algorithms**: BLAKE2, SHA-3 support
- **Batch Templates**: Save/load common verification scenarios  
- **Advanced Filtering**: File type/size-based processing options
- **Integration**: Export to external forensic tools
- **Performance Profiles**: Optimization modes for different hardware