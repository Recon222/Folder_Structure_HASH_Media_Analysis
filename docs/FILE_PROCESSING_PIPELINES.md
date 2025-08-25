# File Processing Pipelines: Non-Batch vs Batch Mode

## Executive Summary

The Folder Structure Utility implements two distinct but related file processing pipelines: **Non-Batch Mode** (single forensic operations) and **Batch Mode** (sequential processing of multiple jobs). While both pipelines share core components and achieve similar outcomes, they differ significantly in their execution flow, error handling, and user interaction patterns.

---

## Section 1: Natural Language Narrative

### Non-Batch Mode (Forensic Mode) Pipeline

The forensic mode pipeline represents the application's primary single-operation workflow designed for processing individual evidence collections.

#### User Journey Flow

1. **Initiation**: User fills out the forensic form, selects files/folders, and clicks "Process Files"
2. **Pre-flight Validation**: The system validates form data and file selections
3. **ZIP Decision Point**: If ZIP settings require prompting, user makes a choice that applies to this single operation
4. **Output Selection**: User selects where to save the processed files
5. **Processing Phase**: Files are copied with hash calculation in a background thread
6. **Post-processing**: Reports are generated and ZIP archives created based on user preferences
7. **Completion**: User receives a completion dialog with operation summary

#### Technical Flow Diagram

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MainWindow    │    │  FileController  │    │FolderStructure  │
│process_forensic │───▶│process_forensic  │───▶│     Thread      │
│     _files      │    │     _files       │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                                               │
         ▼                                               ▼
┌─────────────────┐                              ┌─────────────────┐
│  ZIP Prompt     │                              │  File Copying   │
│  (if needed)    │                              │  (Buffered or   │
└─────────────────┘                              │   Legacy Mode)  │
         │                                       └─────────────────┘
         ▼                                               │
┌─────────────────┐                                     ▼
│Output Directory │                              ┌─────────────────┐
│   Selection     │                              │   Operation     │
└─────────────────┘                              │   Complete      │
         │                                       └─────────────────┘
         ▼                                               │
┌─────────────────┐    ┌──────────────────┐            ▼
│   Processing    │───▶│ Report           │    ┌─────────────────┐
│   Starts        │    │ Generation       │───▶│ ZIP Creation    │
└─────────────────┘    └──────────────────┘    │  (if enabled)   │
                                               └─────────────────┘
```

### Batch Mode Pipeline

The batch mode pipeline enables processing multiple forensic jobs sequentially with minimal user intervention.

#### User Journey Flow

1. **Job Creation**: User creates multiple jobs by configuring forms and adding them to the queue
2. **Batch Initiation**: User clicks "Start Batch Processing"
3. **Global ZIP Decision**: If ZIP settings require prompting, user makes a choice that applies to ALL jobs in the batch
4. **Sequential Processing**: System processes each job independently in order
5. **Per-Job Operations**: For each job: file copying → report generation → ZIP creation
6. **Batch Completion**: User receives summary of all jobs processed

#### Technical Flow Diagram

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│BatchQueueWidget │    │BatchProcessor    │    │  Job Queue      │
│_start_processing│───▶│     Thread       │───▶│  Processing     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       │                       ▼
┌─────────────────┐              │               ┌─────────────────┐
│  ZIP Prompt     │              │               │   For Each Job: │
│  (ONCE for all  │              │               │                 │
│      jobs)      │              │               │ • File Copying  │
└─────────────────┘              │               │ • Report Gen    │
         │                       │               │ • ZIP Creation  │
         ▼                       ▼               └─────────────────┘
┌─────────────────┐    ┌──────────────────┐            │
│   Validation    │    │  _process_       │            ▼
│  (All Jobs)     │───▶│  forensic_job    │    ┌─────────────────┐
└─────────────────┘    │   (per job)      │───▶│ Next Job or     │
                       └──────────────────┘    │   Complete      │
                                               └─────────────────┘
```

### Key Behavioral Differences

#### Scope and Scale
- **Non-Batch**: Single operation with immediate user feedback
- **Batch**: Multiple operations with aggregate progress reporting

#### User Interaction
- **Non-Batch**: User makes decisions throughout the process (output directory, ZIP preferences)
- **Batch**: User makes decisions upfront, then system runs autonomously

#### Error Handling
- **Non-Batch**: Errors halt the operation and require user intervention
- **Batch**: Errors are logged per-job, failed jobs are marked, successful jobs continue

#### Progress Reporting
- **Non-Batch**: Real-time progress of single operation with detailed metrics
- **Batch**: Dual progress indicators (current job progress + overall batch progress)

---

## Section 2: Developer Documentation

### Non-Batch Mode Technical Implementation

#### Entry Point: `MainWindow.process_forensic_files()`

**Location**: `ui/main_window.py:187`

```python
def process_forensic_files(self):
    """Main entry point for forensic file processing"""
    # 1. Validate form data
    if not self.form_data.validate():
        return
        
    # 2. Get file/folder selections
    files, folders = self.get_selected_items()
    
    # 3. Handle ZIP prompt BEFORE operations
    if self.zip_controller.should_prompt_user():
        choice = ZipPromptDialog.prompt_user(self)
        self.zip_controller.set_session_choice(
            choice['create_zip'], 
            choice['remember_for_session']
        )
    
    # 4. Get output directory from user
    output_dir = QFileDialog.getExistingDirectory(...)
    
    # 5. Delegate to file controller
    self.file_thread = self.file_controller.process_forensic_files(
        self.form_data, files, folders, self.output_directory, 
        calculate_hash, perf_monitor
    )
```

#### File Processing: `FileController.process_forensic_files()`

**Location**: `controllers/file_controller.py:22`

```python
def process_forensic_files(self, form_data, files, folders, output_directory, calculate_hash, performance_monitor):
    """Process files using forensic folder structure"""
    # 1. Build forensic directory structure
    folder_path = self._build_forensic_structure(form_data, output_directory)
    
    # 2. Prepare items for processing
    all_items = self._prepare_items(files, folders)
    
    # 3. Create and return processing thread
    thread = FolderStructureThread(all_items, folder_path, calculate_hash, performance_monitor)
    return thread
```

#### Core File Operations: `FolderStructureThread.run()`

**Location**: `core/workers/folder_operations.py:37`

```python
def run(self):
    """Copy files and folders preserving structure"""
    # 1. Collect all files to process (expand folders recursively)
    total_files = []
    for item_type, path, relative in self.items:
        if item_type == 'file':
            total_files.append((path, relative))
        elif item_type == 'folder':
            for item_path in path.rglob('*'):
                if item_path.is_file():
                    total_files.append((item_path, relative_path))
    
    # 2. Choose processing method
    if self.settings.use_buffered_operations:
        self._copy_with_buffering(total_files, total_size, results, empty_dirs)
    else:
        # Legacy sequential copying with individual hash calculation
        for source_file, relative_path in total_files:
            # Copy file, calculate hashes, store results
            shutil.copy2(source_file, dest_file)
            # Force disk sync for forensic integrity
            with open(dest_file, 'rb+') as f:
                os.fsync(f.fileno())
```

#### Post-Processing: `MainWindow.on_operation_finished()`

**Location**: `ui/main_window.py:252`

```python
def on_operation_finished(self, success, message, results):
    """Handle operation completion"""
    if success:
        # 1. Store results
        self.file_operation_results = results
        
        # 2. Generate reports via ReportController
        generated = self.report_controller.generate_reports(
            self.form_data, results, reports_output_dir, 
            generate_time_offset, generate_upload_log, generate_hash_csv
        )
        
        # 3. Create ZIP archives if enabled
        if self.zip_controller.should_create_zip():
            self.create_zip_archives(original_output_dir)
        else:
            self.show_final_completion_message()
```

### Batch Mode Technical Implementation

#### Entry Point: `BatchQueueWidget._start_processing()`

**Location**: `ui/components/batch_queue_widget.py:316`

```python
def _start_processing(self):
    """Start batch processing"""
    # 1. Get pending jobs
    pending_jobs = self.batch_queue.get_pending_jobs()
    
    # 2. Handle ZIP prompt ONCE for entire batch
    if self.main_window and hasattr(self.main_window, 'zip_controller'):
        if self.main_window.zip_controller.should_prompt_user():
            choice = ZipPromptDialog.prompt_user(self)
            self.main_window.zip_controller.set_session_choice(
                choice['create_zip'], choice['remember_for_session']
            )
    
    # 3. Validate all jobs
    validation = self.batch_queue.validate_all_jobs()
    
    # 4. Create and start processor thread
    self.processor_thread = BatchProcessorThread(self.batch_queue, self.main_window)
    self.processor_thread.start()
```

#### Batch Processing Loop: `BatchProcessorThread.run()`

**Location**: `core/workers/batch_processor.py:47`

```python
def run(self):
    """Process all jobs in the queue"""
    while True:
        # 1. Get next pending job
        job = self.batch_queue.get_next_pending_job()
        if not job:
            break
            
        # 2. Process the job
        try:
            self.job_started.emit(job.job_id, job.job_name)
            success, message, results = self._process_forensic_job(job)
            
            if success:
                job.status = "completed"
                self.job_completed.emit(job.job_id, True, message, results)
            else:
                job.status = "failed"
                self.job_completed.emit(job.job_id, False, message, results)
                
        except Exception as e:
            job.status = "failed"
            self.job_completed.emit(job.job_id, False, str(e), None)
```

#### Per-Job Processing: `BatchProcessorThread._process_forensic_job()`

**Location**: `core/workers/batch_processor.py:114`

```python
def _process_forensic_job(self, job):
    """Process a forensic mode job"""
    # 1. Build folder structure
    relative_path = self._build_folder_path(job, "forensic")
    output_path = Path(job.output_directory) / relative_path
    
    # 2. Copy files directly (inline, not via FileController)
    success, message, results = self._copy_items_sync(items_to_copy, output_path, job)
    
    if success:
        # 3. Generate reports (inline)
        report_results = self._generate_reports(job, output_path, results)
        
        # 4. Create ZIP archives (inline)
        zip_results = self._create_zip_archives(job, output_path)
        
        return True, f"Job completed successfully. {len(results)} files processed.", {
            'file_results': results,
            'report_results': report_results,
            'zip_results': zip_results
        }
```

#### Batch File Operations: `BatchProcessorThread._copy_items_sync()`

**Location**: `core/workers/batch_processor.py:192`

```python
def _copy_items_sync(self, items_to_copy, destination, job):
    """Copy items synchronously with progress reporting"""
    # Choose operation mode
    if settings.use_buffered_operations:
        file_ops = BufferedFileOperations(progress_callback=...)
    else:
        file_ops = FileOperations()
    
    # Process all files
    for source_file, relative_path in all_files:
        # Create destination with structure preservation
        dest_file = destination / relative_path
        
        # Security validation
        dest_validated = PathSanitizer.validate_destination(dest_file, destination)
        
        # Copy with chosen method
        if settings.use_buffered_operations:
            copy_result = file_ops.copy_file_buffered(source_file, dest_validated, calculate_hash)
        else:
            shutil.copy2(source_file, dest_validated)
            # Force disk sync
            with open(dest_validated, 'rb+') as f:
                os.fsync(f.fileno())
```

### Key Architectural Differences

#### Threading Model

**Non-Batch Mode**:
- Main Thread: UI interactions, ZIP prompting, output directory selection
- File Thread (`FolderStructureThread`): File copying and hash calculation
- ZIP Thread (optional): ZIP archive creation
- Report generation: Synchronous on main thread after file operations

**Batch Mode**:
- Main Thread: UI interactions, batch setup
- Batch Thread (`BatchProcessorThread`): Sequential job processing
- All operations (file, reports, ZIP) happen inline within batch thread
- No separate threads for individual operations

#### Error Propagation

**Non-Batch Mode**:
```python
# Errors bubble up through signal chain and halt operation
self.file_thread.finished.connect(self.on_operation_finished)
# If error occurs, user sees dialog and can retry
```

**Batch Mode**:
```python
# Errors are captured per-job and logged
try:
    success, message, results = self._process_forensic_job(job)
except Exception as e:
    job.status = "failed"
    # Continue to next job rather than halt entire batch
```

#### State Management

**Non-Batch Mode**:
- Form data validated once before processing
- ZIP choice applies to single operation
- Output directory chosen interactively
- Results stored in MainWindow for later use

**Batch Mode**:
- Each job carries independent FormData
- ZIP choice applies to entire batch (with session management)
- Output directories pre-configured per job
- Results processed immediately per job

### Performance Characteristics

#### Memory Usage

**Non-Batch Mode**:
- Lower memory footprint (single operation)
- Results held in memory until operation complete
- Performance monitoring integration available

**Batch Mode**:
- Higher memory usage (job queue + current operation)
- Results processed and cleared per job
- Simplified performance reporting

#### I/O Patterns

**Non-Batch Mode**:
- Single destination directory structure
- Optimized for single large operation
- Full performance monitoring and adaptive buffering

**Batch Mode**:
- Multiple destination directories
- Optimized for multiple smaller operations  
- Simplified buffering logic per job

#### Concurrency

**Non-Batch Mode**:
- File operations + ZIP creation can run concurrently
- Report generation blocks until file operations complete

**Batch Mode**:
- All operations per job run sequentially
- Jobs themselves processed sequentially
- No inter-job concurrency

### Code Reuse Analysis

#### Shared Components

1. **FormData Model**: Both modes use identical form validation and data structures
2. **ForensicPathBuilder**: Both use same path building logic for folder structures
3. **BufferedFileOperations**: Both can use high-performance buffered copying
4. **PDFGenerator**: Both use same report generation classes
5. **ZipController**: Both use same ZIP creation logic (with different session management)
6. **Settings Management**: Both respect same user preferences

#### Divergent Components

1. **File Operation Orchestration**: 
   - Non-batch: `FolderStructureThread` (complex, full-featured)
   - Batch: `_copy_items_sync()` (simplified, inline)

2. **Progress Reporting**:
   - Non-batch: Single progress bar with detailed metrics
   - Batch: Dual progress (per-job + overall batch)

3. **Error Handling**:
   - Non-batch: Halt on error, user intervention required
   - Batch: Log and continue, aggregate error reporting

4. **Report Generation**:
   - Non-batch: Via `ReportController` with configurable output paths
   - Batch: Inline with predetermined paths per job

### Integration Points and Dependencies

#### Main Window Dependencies

Both modes depend on MainWindow for:
- Form data access (`self.form_data`)
- Settings access (`self.settings`)
- ZIP controller access (`self.zip_controller`) 
- UI progress updates (signals)
- Logging coordination

#### Settings Dependencies

Both modes respect:
- `use_buffered_operations`: Performance mode selection
- `calculate_hashes`: Hash verification toggle
- `generate_time_offset_pdf`: Time offset report toggle
- `generate_upload_log_pdf`: Upload log toggle  
- `generate_hash_csv`: Hash CSV toggle
- ZIP-related settings: Creation preferences and levels

#### External Tool Dependencies

Both modes require:
- **ReportLab**: PDF generation
- **Hashwise** (optional): Accelerated hash calculation
- **PySide6**: UI framework and threading
- **pathlib**: Cross-platform path handling

---

## Conclusion

The dual-pipeline architecture enables the Folder Structure Utility to serve both single-operation forensic processing and high-volume batch processing needs. While the pipelines share core business logic and respect identical user preferences, their execution patterns are optimized for their specific use cases:

- **Non-Batch Mode** prioritizes user interaction, detailed progress feedback, and error recovery
- **Batch Mode** prioritizes autonomy, throughput, and robust error isolation

Understanding these architectural differences is crucial for maintenance, debugging, and feature development, as changes to shared components may affect both pipelines while changes to pipeline-specific code affects only one mode.