# Current File Processing Pipelines: Non-Batch vs Batch Mode

## Executive Summary

The Folder Structure Utility implements two sophisticated file processing pipelines: **Non-Batch Mode** (single forensic operations) and **Batch Mode** (sequential processing of queued jobs). Both pipelines now utilize the same proven **FileController → FolderStructureThread** architecture, ensuring consistent forensic-grade file operations with comprehensive integrity verification through SHA-256 hashing. The recent architectural refactor eliminated critical data corruption issues by unifying both modes under a single, battle-tested file processing pipeline.

---

## Section 1: Natural Language Narrative

### Non-Batch Mode (Forensic Mode) Pipeline

The forensic mode pipeline represents the application's primary single-operation workflow, designed for processing individual evidence collections with maximum user control and real-time feedback.

#### User Journey Flow

1. **Form Completion**: User fills out forensic form fields (occurrence number, business details, timestamps)
2. **File Selection**: User selects individual files and/or complete folder hierarchies via drag-drop or browse
3. **Process Initiation**: User clicks "Process Files" button in Forensic tab
4. **ZIP Decision Point**: System prompts for ZIP preference if not previously set for this session
5. **Output Selection**: User selects destination directory via folder dialog
6. **Processing Phase**: Files are copied with real-time hash calculation and progress reporting
7. **Report Generation**: System automatically generates Time Offset, Technician Log, and Hash CSV reports
8. **ZIP Creation**: System creates multi-level ZIP archives if enabled
9. **Completion Dialog**: User receives comprehensive completion summary with file counts and paths

#### Technical Flow Diagram

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MainWindow    │    │  FileController  │    │FolderStructure  │
│process_forensic │───▶│process_forensic  │───▶│     Thread      │
│     _files      │    │     _files       │    │   (QThread)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                       │
         ▼                        ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  ZIP Prompt     │    │ Forensic Path    │    │ File Processing │
│  (if needed)    │    │ Builder          │    │ • Buffered Ops  │
└─────────────────┘    └──────────────────┘    │ • SHA-256 Hash  │
         │                        │            │ • fsync() Force │
         ▼                        ▼            └─────────────────┘
┌─────────────────┐    ┌──────────────────┐            │
│Output Directory │    │  Folder Creation │            ▼
│   Selection     │    │  (Occurrence/    │    ┌─────────────────┐
└─────────────────┘    │Business/DateTime)│    │   Progress &    │
         │              └──────────────────┘    │    Status       │
         ▼                        │            │   Reporting     │
┌─────────────────┐              ▼            └─────────────────┘
│   Processing    │    ┌──────────────────┐            │
│   Initiated     │───▶│ Thread Signals   │            ▼
└─────────────────┘    │ • progress       │    ┌─────────────────┐
                       │ • status         │───▶│ Operation       │
                       │ • finished       │    │ Complete        │
                       └──────────────────┘    └─────────────────┘
                                                       │
                                                       ▼
                            ┌──────────────────┐      ┌─────────────────┐
                            │ Report           │      │ ZIP Creation    │
                            │ Generation       │─────▶│ (Multi-level)   │
                            │ • Time Offset    │      │ • Root Level    │
                            │ • Technician Log │      │ • Location Level│
                            │ • Hash CSV       │      │ • DateTime Level│
                            └──────────────────┘      └─────────────────┘
```

### Batch Mode Pipeline

The batch mode pipeline enables processing multiple forensic jobs sequentially with minimal user intervention, optimized for high-volume evidence processing scenarios.

#### User Journey Flow

1. **Job Creation**: User creates multiple jobs by filling forms and adding files to each job
2. **Queue Management**: User reviews, reorders, and validates jobs in the batch queue
3. **Batch Initiation**: User clicks "Start Batch Processing" button
4. **Global ZIP Decision**: System prompts once for ZIP preference that applies to entire batch
5. **Automated Processing**: System processes each job sequentially without further user input
6. **Per-Job Operations**: For each job: file copying → report generation → ZIP creation
7. **Progress Monitoring**: User sees dual progress bars (current job + overall batch)
8. **Error Isolation**: Individual job failures don't halt the entire batch
9. **Batch Completion**: User receives summary of all processed jobs with success/failure counts

#### Technical Flow Diagram

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│BatchQueueWidget │    │BatchProcessor    │    │  BatchJob       │
│_start_processing│───▶│     Thread       │───▶│  Queue          │
└─────────────────┘    │   (QThread)      │    │  Processing     │
         │              └──────────────────┘    └─────────────────┘
         ▼                        │                       │
┌─────────────────┐              │                       ▼
│  ZIP Prompt     │              │               ┌─────────────────┐
│  (ONCE for all  │              │               │   For Each Job: │
│      jobs)      │              │               │                 │
└─────────────────┘              │               │ FileController  │
         │                       ▼               │       ↓         │
         ▼               ┌──────────────────┐    │FolderStructure  │
┌─────────────────┐     │_process_forensic │    │    Thread       │
│   Validation    │────▶│     _job         │    │   (sync exec)   │
│  (All Jobs)     │     │  (per job)       │    └─────────────────┘
└─────────────────┘     └──────────────────┘            │
         │                        │                     ▼
         ▼                        ▼             ┌─────────────────┐
┌─────────────────┐    ┌──────────────────┐    │ Job Operations: │
│ BatchProcessor  │    │_execute_folder   │    │ • File Copy     │
│    Started      │───▶│_thread_sync      │    │ • Hash Verify   │
└─────────────────┘    │  (QEventLoop)    │    │ • Report Gen    │
                       └──────────────────┘    │ • ZIP Create    │
                                │              └─────────────────┘
                                ▼                       │
                       ┌──────────────────┐            ▼
                       │ Job Complete     │    ┌─────────────────┐
                       │ Next Job or      │───▶│ Progress Update │
                       │ Batch Done       │    │ • Job Level     │
                       └──────────────────┘    │ • Batch Level   │
                                               └─────────────────┘
```

### Key Behavioral Differences

#### Unified Processing Core
- **Both Modes**: Now use identical `FileController → FolderStructureThread` pipeline
- **Both Modes**: Same forensic-grade file operations with SHA-256 hashing
- **Both Modes**: Identical security validation and integrity checks

#### User Interaction Patterns
- **Non-Batch**: Interactive prompts throughout process (output directory, ZIP preferences)
- **Batch**: Front-loaded configuration, then autonomous execution

#### Progress Reporting Philosophy
- **Non-Batch**: Detailed real-time progress with performance metrics
- **Batch**: Scaled progress reporting (0-80% files, 80-90% reports, 90-100% ZIP)

#### Error Recovery Strategy
- **Non-Batch**: Halt-on-error with user intervention required
- **Batch**: Error isolation with per-job failure tracking and continued processing

---

## Section 2: Developer Documentation

### Non-Batch Mode Technical Implementation

#### Entry Point: `MainWindow.process_forensic_files()`

**Location**: `ui/main_window.py:178`

```python
def process_forensic_files(self):
    """Main entry point for forensic file processing"""
    # Phase 1: Pre-flight validation
    errors = self.form_data.validate()
    if errors:
        QMessageBox.warning(self, "Validation Error", "\n".join(errors))
        return
        
    # Phase 2: File/folder collection
    files, folders = self.files_panel.get_all_items()
    if not files and not folders:
        QMessageBox.warning(self, "No Files", "Please select files or folders to process.")
        return
        
    # Phase 3: ZIP preference resolution (front-loaded)
    if self.zip_controller.should_prompt_user():
        choice = ZipPromptDialog.prompt_user(self)
        self.zip_controller.set_session_choice(
            choice['create_zip'], 
            choice['remember_for_session']
        )
    
    # Phase 4: Output directory selection
    output_dir = QFileDialog.getExistingDirectory(
        self, "Select Output Directory", 
        str(Path.home())
    )
    if not output_dir:
        return
    
    self.output_directory = Path(output_dir)
    
    # Phase 5: Performance monitoring initialization
    calculate_hash = self.settings.calculate_hashes
    perf_monitor = self.performance_monitor if hasattr(self, 'performance_monitor') else None
    
    # Phase 6: FileController delegation
    self.file_thread = self.file_controller.process_forensic_files(
        self.form_data, files, folders, self.output_directory, 
        calculate_hash, perf_monitor
    )
    
    # Phase 7: Signal connection and thread initiation
    self.file_thread.progress.connect(self.update_progress)
    self.file_thread.status.connect(self.log)
    self.file_thread.finished.connect(self.on_operation_finished)
    self.file_thread.metrics_updated.connect(self._on_metrics_updated)
    
    self.file_thread.start()
    self._set_operation_active(True)
```

#### File Processing Orchestration: `FileController.process_forensic_files()`

**Location**: `controllers/file_controller.py:22`

```python
def process_forensic_files(
    self,
    form_data: FormData,
    files: List[Path],
    folders: List[Path],
    output_directory: Path,
    calculate_hash: bool = True,
    performance_monitor = None
) -> FolderStructureThread:
    """Process files using forensic folder structure"""
    
    # Phase 1: Forensic folder structure creation
    folder_path = self._build_forensic_structure(form_data, output_directory)
    
    # Phase 2: Item preparation with structure preservation
    all_items = self._prepare_items(files, folders)
    
    # Phase 3: Thread creation with performance monitoring
    thread = FolderStructureThread(all_items, folder_path, calculate_hash, performance_monitor)
    self.current_operation = thread
    return thread

def _build_forensic_structure(self, form_data: FormData, base_path: Path) -> Path:
    """Build the forensic folder structure using ForensicPathBuilder"""
    return ForensicPathBuilder.create_forensic_structure(base_path, form_data)
    
def _prepare_items(
    self,
    files: List[Path],
    folders: List[Path]
) -> List[Tuple[str, Path, Optional[str]]]:
    """Prepare all items for copying with structure preservation"""
    all_items = []
    
    # Individual files with direct naming
    for file in files:
        all_items.append(('file', file, file.name))
        
    # Folders with complete hierarchy preservation
    for folder in folders:
        all_items.append(('folder', folder, None))
        
    return all_items
```

#### Core File Operations: `FolderStructureThread.run()`

**Location**: `core/workers/folder_operations.py:37`

```python
def run(self):
    """Copy files and folders preserving structure with forensic integrity"""
    try:
        results = {}
        total_files = []
        empty_dirs = []  # Track empty directories separately
        
        # Phase 1: File discovery and structure analysis
        for item_type, path, relative in self.items:
            if item_type == 'file':
                total_files.append((path, relative))
            elif item_type == 'folder':
                # Recursive discovery with hierarchy preservation
                for item_path in path.rglob('*'):
                    relative_path = item_path.relative_to(path.parent)
                    if item_path.is_file():
                        total_files.append((item_path, relative_path))
                    elif item_path.is_dir():
                        empty_dirs.append(relative_path)
        
        if not total_files:
            self.finished.emit(True, "No files to copy", {})
            return
            
        # Phase 2: Performance optimization selection
        total_size = sum(f[0].stat().st_size for f in total_files if f[0].exists())
        
        if self.settings.use_buffered_operations:
            self.status.emit("[HIGH-PERFORMANCE MODE] Using buffered file operations")
            self._copy_with_buffering(total_files, total_size, results, empty_dirs)
            return
        else:
            # Phase 3: Legacy sequential processing
            self._copy_with_legacy_mode(total_files, total_size, results, empty_dirs)
            
    except Exception as e:
        self.finished.emit(False, f"Error: {str(e)}", {})

def _copy_with_buffering(self, total_files: List[Tuple], total_size: int, results: dict, empty_dirs: List[Path]):
    """High-performance buffered file operations with adaptive optimization"""
    
    # Phase 1: Empty directory creation
    directories_created = 0
    if empty_dirs:
        for dir_path in empty_dirs:
            dest_dir = self.destination / dir_path
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                directories_created += 1
                self.status.emit(f"Created directory: {dir_path}")
            except Exception as e:
                self.status.emit(f"Failed to create directory {dir_path}: {e}")
    
    # Phase 2: BufferedFileOperations initialization
    buffered_ops = BufferedFileOperations(
        progress_callback=lambda pct, msg: (
            self.progress.emit(pct),
            self.status.emit(msg)
        ),
        metrics_callback=self._handle_metrics_update
    )
    
    # Phase 3: Performance metrics initialization
    buffered_ops.metrics.total_files = len(total_files)
    buffered_ops.metrics.total_bytes = total_size
    buffered_ops.metrics.total_directories = len(empty_dirs)
    buffered_ops.metrics.directories_created = directories_created
    buffered_ops.metrics.start_time = time.time()
    
    # Phase 4: Individual file processing with security validation
    for idx, (source_file, relative_path) in enumerate(total_files):
        if self.cancelled:
            buffered_ops.cancel()
            self.finished.emit(False, "Operation cancelled", results)
            return
        
        try:
            dest_file = self.destination / relative_path
            
            # SECURITY: Path traversal validation
            dest_resolved = dest_file.resolve()
            base_resolved = self.destination.resolve()
            if not str(dest_resolved).startswith(str(base_resolved)):
                raise ValueError(f"Security: Path traversal detected for {relative_path}")
            
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            
            # High-performance buffered copy with hash calculation
            copy_result = buffered_ops.copy_file_buffered(
                source_file,
                dest_file,
                calculate_hash=self.calculate_hash
            )
            
            # Results storage with integrity verification
            results[str(relative_path)] = {
                'source_path': str(source_file),
                'dest_path': str(dest_file),
                'source_hash': copy_result.get('source_hash', ''),
                'dest_hash': copy_result.get('dest_hash', ''),
                'verified': copy_result.get('verified', True),
                'size': source_file.stat().st_size
            }
            
            if copy_result.get('success'):
                buffered_ops.metrics.files_processed += 1
                
        except Exception as e:
            self.status.emit(f"Error copying {source_file.name}: {str(e)}")
            buffered_ops.metrics.errors.append(str(e))
    
    # Phase 5: Final metrics calculation and reporting
    buffered_ops.metrics.end_time = time.time()
    buffered_ops.metrics.calculate_summary()
    
    final_msg = f"Successfully copied {buffered_ops.metrics.files_processed}/{buffered_ops.metrics.total_files} files"
    if buffered_ops.metrics.total_directories > 0:
        final_msg += f" and created {buffered_ops.metrics.directories_created}/{buffered_ops.metrics.total_directories} folders"
    
    self.finished.emit(True, final_msg, results)
```

#### Post-Processing: `MainWindow.on_operation_finished()`

**Location**: `ui/main_window.py:252`

```python
def on_operation_finished(self, success: bool, message: str, results: dict):
    """Handle operation completion with comprehensive post-processing"""
    
    self._set_operation_active(False)
    
    if success:
        # Phase 1: Result storage and metrics
        self.file_operation_results = results
        files_copied = len([r for r in results.values() if isinstance(r, dict) and 'error' not in r])
        
        # Phase 2: Report generation coordination
        reports_output_dir = self.output_directory / self.form_data.occurrence_number / "Documents"
        reports_output_dir.mkdir(parents=True, exist_ok=True)
        
        generated_reports = self.report_controller.generate_reports(
            self.form_data,
            results,
            reports_output_dir,
            generate_time_offset=self.settings.generate_time_offset_pdf,
            generate_upload_log=self.settings.generate_upload_log_pdf,
            generate_hash_csv=self.settings.generate_hash_csv
        )
        
        self.report_generation_results = generated_reports
        
        # Phase 3: ZIP creation (if enabled)
        if self.zip_controller.should_create_zip():
            self.create_zip_archives(self.output_directory)
        else:
            self.show_final_completion_message()
    else:
        QMessageBox.critical(self, "Operation Failed", f"File processing failed:\n\n{message}")

def show_final_completion_message(self):
    """Display comprehensive completion summary"""
    
    files_copied = len([r for r in self.file_operation_results.values() 
                       if isinstance(r, dict) and 'error' not in r])
    
    reports_generated = len(self.report_generation_results) if hasattr(self, 'report_generation_results') else 0
    
    zip_info = ""
    if hasattr(self, 'zip_creation_results') and self.zip_creation_results:
        zip_count = len(self.zip_creation_results.get('created_archives', []))
        zip_info = f"\n• ZIP Archives: {zip_count} created"
    
    message = f"""Operation completed successfully!

Summary:
• Files Copied: {files_copied}
• Reports Generated: {reports_generated}{zip_info}

Output Location:
{self.output_directory}"""
    
    QMessageBox.information(self, "Operation Complete", message)
```

### Batch Mode Technical Implementation

#### Entry Point: `BatchQueueWidget._start_processing()`

**Location**: `ui/components/batch_queue_widget.py:317`

```python
def _start_processing(self):
    """Initiate batch processing with comprehensive validation"""
    
    # Phase 1: Queue validation
    pending_jobs = self.batch_queue.get_pending_jobs()
    if not pending_jobs:
        QMessageBox.information(self, "No Jobs", "No pending jobs to process")
        return
        
    # Phase 2: Global ZIP preference resolution (applies to entire batch)
    if self.main_window and hasattr(self.main_window, 'zip_controller'):
        if self.main_window.zip_controller.should_prompt_user():
            from ui.dialogs.zip_prompt import ZipPromptDialog
            choice = ZipPromptDialog.prompt_user(self)
            self.main_window.zip_controller.set_session_choice(
                choice['create_zip'], 
                choice['remember_for_session']
            )
            
    # Phase 3: Comprehensive job validation
    validation = self.batch_queue.validate_all_jobs()
    if validation['invalid_jobs']:
        invalid_count = len(validation['invalid_jobs'])
        QMessageBox.warning(
            self, "Invalid Jobs", 
            f"Found {invalid_count} invalid jobs. Please review and fix before processing."
        )
        return
    
    # Phase 4: Batch processor creation and initialization
    self.processor_thread = BatchProcessorThread(self.batch_queue, self.main_window)
    self._connect_processor_signals()
    
    # Phase 5: UI state management
    self._set_processing_state(True)
    self.processor_thread.start()
```

#### Sequential Job Processing: `BatchProcessorThread.run()`

**Location**: `core/workers/batch_processor.py:43`

```python
def run(self):
    """Process all jobs in the queue with comprehensive error isolation"""
    
    pending_jobs = self.batch_queue.get_pending_jobs()
    total_jobs = len(pending_jobs)
    completed = 0
    successful = 0
    failed = 0
    
    if total_jobs == 0:
        self.queue_completed.emit(0, 0, 0)
        return
        
    # Main processing loop with error isolation
    while True:
        if self.cancelled:
            break
            
        # Pause handling
        while self.pause_requested and not self.cancelled:
            self.msleep(100)
            
        # Get next job
        job = self.batch_queue.get_next_pending_job()
        if not job:
            break  # No more pending jobs
            
        # Individual job processing with complete error isolation
        try:
            self.job_started.emit(job.job_id, job.job_name)
            job.status = "processing"
            job.start_time = datetime.now()
            self.current_job = job
            
            self.batch_queue.update_job(job)
            
            # Core processing using proven FileController pipeline
            success, message, results = self._process_forensic_job(job)
            
            job.end_time = datetime.now()
            
            if success:
                job.status = "completed"
                successful += 1
                self.job_completed.emit(job.job_id, True, message, results)
            else:
                job.status = "failed"
                job.error_message = message
                failed += 1
                self.job_completed.emit(job.job_id, False, message, results)
                
        except Exception as e:
            # Exception isolation - don't halt entire batch
            job.status = "failed"
            job.error_message = str(e)
            job.end_time = datetime.now()
            failed += 1
            self.job_completed.emit(job.job_id, False, str(e), None)
            
        # Queue state management
        self.batch_queue.update_job(job)
        self.current_job = None
        
        completed += 1
        self.queue_progress.emit(completed, total_jobs)
    
    # Final completion signal
    self.queue_completed.emit(total_jobs, successful, failed)
```

#### Individual Job Processing: `BatchProcessorThread._process_forensic_job()`

**Location**: `core/workers/batch_processor.py:193`

```python
def _process_forensic_job(self, job: BatchJob) -> tuple[bool, str, Any]:
    """Process a forensic mode job using proven FileController pipeline"""
    try:
        # Phase 1: Input validation
        if not self.main_window:
            return False, "Main window reference not available", None
            
        if not job.files and not job.folders:
            return False, "No valid files or folders to process", None
            
        # Phase 2: Proven FileController pipeline integration
        file_controller = FileController()
        folder_thread = file_controller.process_forensic_files(
            job.form_data,
            job.files,
            job.folders, 
            Path(job.output_directory),
            calculate_hash=settings.calculate_hashes,
            performance_monitor=None  # Simplified for batch mode
        )
        
        # Phase 3: Synchronous execution within batch thread
        success, message, results = self._execute_folder_thread_sync(folder_thread)
        
        if not success:
            logger.error(f"Job {job.job_id} ({job.job_name}) file operations failed: {message}")
            logger.info(f"Job details - Files: {len(job.files)}, Folders: {len(job.folders)}, Output: {job.output_directory}")
            return False, f"File operations failed: {message}", None
            
        # Phase 4: Results integrity validation
        if not self._validate_copy_results(results, job):
            logger.error(f"Job {job.job_id} ({job.job_name}) failed integrity validation")
            return False, "File integrity validation failed", None
        
        # Phase 5: Output path calculation
        output_path = Path(job.output_directory) / self._build_folder_path(job, "forensic")
        
        # Phase 6: Scaled progress reporting
        if self.current_job:
            self.job_progress.emit(self.current_job.job_id, 80, "Generating reports...")
        
        # Phase 7: Report generation
        report_results = self._generate_reports(job, output_path, results)
        
        if self.current_job:
            self.job_progress.emit(self.current_job.job_id, 90, "Creating ZIP archives...")
        
        # Phase 8: ZIP creation
        zip_results = self._create_zip_archives(job, output_path)
        
        # Phase 9: Memory-efficient result summarization
        file_summary = {
            'files_processed': len([r for r in results.values() if isinstance(r, dict) and 'error' not in r]),
            'total_size': sum(r.get('size', 0) for r in results.values() if isinstance(r, dict)),
            'verification_passed': all(r.get('verified', True) for r in results.values() if isinstance(r, dict) and 'size' in r)
        }
        
        if self.current_job:
            self.job_progress.emit(self.current_job.job_id, 100, f"Job completed - {file_summary['files_processed']} files processed")
        
        return True, f"Job completed successfully. {file_summary['files_processed']} files processed.", {
            'file_summary': file_summary,
            'report_results': report_results,
            'zip_results': zip_results,
            'output_path': output_path
        }
        
    except Exception as e:
        logger.error(f"Job {job.job_id} ({getattr(job, 'job_name', 'Unknown')}) failed with exception: {e}", exc_info=True)
        logger.info(f"Failed job details - Files: {len(getattr(job, 'files', []))}, Folders: {len(getattr(job, 'folders', []))}")
        return False, f"Unexpected error: {e}", None
```

#### Synchronous Thread Execution: `BatchProcessorThread._execute_folder_thread_sync()`

**Location**: `core/workers/batch_processor.py:110`

```python
def _execute_folder_thread_sync(self, folder_thread: FolderStructureThread) -> tuple[bool, str, Dict]:
    """Execute FolderStructureThread synchronously within batch thread using QEventLoop"""
    
    # Phase 1: Event loop setup for synchronous execution
    loop = QEventLoop()
    result_container = {'success': False, 'message': '', 'results': {}}
    
    # Phase 2: Result capture handler
    def on_thread_finished(success: bool, message: str, results: Dict):
        result_container.update({
            'success': success,
            'message': message, 
            'results': results
        })
        loop.quit()
    
    # Phase 3: Progress forwarding with scaling (file operations = 0-80% of job)
    def on_thread_progress(pct: int):
        job_file_progress = int(pct * 0.8)
        if self.current_job:
            self.job_progress.emit(self.current_job.job_id, job_file_progress, f"Copying files... {pct}%")
            
    def on_thread_status(msg: str):
        if self.current_job:
            self.job_progress.emit(self.current_job.job_id, -1, msg)
    
    # Phase 4: Signal connections
    folder_thread.finished.connect(on_thread_finished)
    folder_thread.progress.connect(on_thread_progress) 
    folder_thread.status.connect(on_thread_status)
    
    # Phase 5: Cancellation monitoring
    def check_cancellation():
        if self.cancelled:
            logger.info(f"Cancelling folder thread for job {getattr(self.current_job, 'job_id', 'Unknown')}")
            folder_thread.cancel()
            loop.quit()
    
    # Phase 6: Thread execution with cancellation monitoring
    folder_thread.start()
    
    cancel_timer = QTimer()
    cancel_timer.timeout.connect(check_cancellation)
    cancel_timer.start(100)  # Check every 100ms
    
    loop.exec()  # Synchronous wait
    
    cancel_timer.stop()
    
    return result_container['success'], result_container['message'], result_container['results']
```

#### Results Validation: `BatchProcessorThread._validate_copy_results()`

**Location**: `core/workers/batch_processor.py:162`

```python
def _validate_copy_results(self, results: Dict, job: BatchJob) -> bool:
    """Comprehensive validation of file operation results"""
    
    # Phase 1: Expected file count calculation
    expected_file_count = len([f for f in job.files if f.exists()])
    for folder in job.folders:
        if folder.exists():
            expected_file_count += len([f for f in folder.rglob('*') if f.is_file()])
    
    # Phase 2: Actual file count verification (exclude performance stats)
    actual_file_count = len([
        r for key, r in results.items() 
        if isinstance(r, dict) and key != '_performance_stats' and 'error' not in r
    ])
    
    if actual_file_count != expected_file_count:
        logger.error(f"File count mismatch: expected {expected_file_count}, got {actual_file_count}")
        return False
        
    # Phase 3: Hash verification validation (if enabled)
    if settings.calculate_hashes:
        failed_verifications = [
            path for path, result in results.items()
            if isinstance(result, dict) and path != '_performance_stats' and not result.get('verified', True)
        ]
        if failed_verifications:
            logger.error(f"Hash verification failed for {len(failed_verifications)} files: {failed_verifications[:5]}")
            return False
    
    return True
```

### Key Architectural Differences

#### Unified Processing Core

Both modes now utilize the identical `FileController → FolderStructureThread` pipeline, ensuring:
- **Consistent forensic-grade file operations**
- **Identical security validation (path traversal prevention)**
- **Same SHA-256 hash calculation and verification**
- **Identical performance optimization (buffered vs legacy modes)**
- **Same `os.fsync()` integrity enforcement**

#### Threading Model Comparison

**Non-Batch Mode**:
- **Main Thread**: UI interactions, ZIP prompting, output directory selection
- **FolderStructureThread**: Direct file copying and hash calculation
- **Report Generation**: Synchronous on main thread after file operations
- **ZIP Thread** (optional): Asynchronous ZIP archive creation

**Batch Mode**:
- **Main Thread**: UI interactions, batch setup, global ZIP prompting
- **BatchProcessorThread**: Sequential job orchestration
- **Per-Job Execution**: Synchronous `FolderStructureThread` via `QEventLoop`
- **Inline Operations**: Reports and ZIP creation within batch thread

#### Progress Reporting Architecture

**Non-Batch Mode**:
```python
# Direct signal connection from file operations
self.file_thread.progress.connect(self.update_progress)  # 0-100% file operations
# Separate progress for reports and ZIP
```

**Batch Mode**:
```python
# Scaled progress reporting
def on_thread_progress(pct: int):
    job_file_progress = int(pct * 0.8)  # File operations = 0-80%
    # Reports = 80-90%, ZIP = 90-100%
```

#### Error Handling Philosophy

**Non-Batch Mode**:
- **Halt-on-error**: Any failure stops the entire operation
- **User intervention required**: Error dialogs require user acknowledgment
- **Single point of failure**: One error affects entire process

**Batch Mode**:
- **Error isolation**: Individual job failures don't halt batch
- **Automatic recovery**: Failed jobs marked, successful jobs continue
- **Aggregate reporting**: Final summary shows success/failure counts

#### State Management Patterns

**Non-Batch Mode**:
```python
# Single operation state
self.file_operation_results = results  # Stored in MainWindow
self.output_directory = user_selected_path  # Interactive selection
```

**Batch Mode**:
```python
# Per-job state management
job.status = "processing"  # Individual job tracking
job.output_directory = pre_configured_path  # No user interaction during batch
# Results processed immediately, not stored long-term
```

### Performance Characteristics

#### Memory Usage Patterns

**Non-Batch Mode**:
- **Lower baseline**: Single operation memory footprint
- **Result retention**: Full results held until completion dialog
- **Performance monitoring**: Optional detailed metrics collection

**Batch Mode**:
- **Higher baseline**: Job queue + current operation
- **Result summarization**: Full results processed immediately, only summaries retained
- **Memory efficiency**: Aggressive cleanup after each job

#### I/O Optimization Strategies

**Both Modes** (now identical):
- **Buffered Operations**: Adaptive buffer sizing (256KB-10MB)
- **Security Validation**: Path traversal checks for every file
- **Forensic Integrity**: `os.fsync()` after every file copy
- **Hash Calculation**: Optional SHA-256 with Hashwise acceleration

#### Concurrency Characteristics

**Non-Batch Mode**:
- **File + ZIP Concurrency**: File operations and ZIP creation can overlap
- **Report Blocking**: Reports generated synchronously after file operations

**Batch Mode**:
- **Sequential Job Processing**: Jobs processed one at a time
- **Inline Operations**: File, report, and ZIP operations sequential per job
- **No Inter-Job Concurrency**: Simplified threading model

### Code Reuse Analysis

#### Shared Components (100% Reuse)

1. **FileController**: Both modes use identical file processing orchestration
2. **FolderStructureThread**: Same core file operations with forensic integrity
3. **FormData Model**: Identical form validation and data structures
4. **ForensicPathBuilder**: Same folder structure creation logic
5. **BufferedFileOperations**: Identical high-performance file copying
6. **PDFGenerator**: Same report generation (Time Offset, Technician Log, Hash CSV)
7. **ZipController/ZipUtility**: Same ZIP creation logic
8. **Settings Management**: Both respect identical user preferences

#### Divergent Components

1. **User Interaction Flow**:
   - Non-batch: Interactive prompts throughout process
   - Batch: Front-loaded configuration, autonomous execution

2. **Progress Reporting**:
   - Non-batch: Direct progress signals with detailed metrics
   - Batch: Scaled progress with dual-level reporting

3. **Error Recovery**:
   - Non-batch: User-driven error recovery
   - Batch: Automatic error isolation and continuation

4. **Result Management**:
   - Non-batch: Full result retention for user display
   - Batch: Immediate processing with summary retention

### Integration Points and Dependencies

#### MainWindow Dependencies

**Both Modes Require**:
- Form data access (`self.form_data`)
- Settings management (`self.settings`)
- ZIP controller access (`self.zip_controller`)
- Progress reporting via Qt signals
- Centralized logging coordination

#### Settings Dependencies

**Both Modes Respect**:
- `use_buffered_operations`: Performance mode selection
- `calculate_hashes`: SHA-256 verification toggle
- `generate_time_offset_pdf`: Time offset report toggle
- `generate_upload_log_pdf`: Technician log toggle
- `generate_hash_csv`: Hash verification CSV toggle
- ZIP preferences: Creation settings and compression levels

#### External Dependencies

**Both Modes Require**:
- **PySide6**: Qt framework for UI and threading
- **ReportLab**: PDF generation engine
- **pathlib**: Cross-platform path handling
- **hashlib**: SHA-256 hash calculation
- **Hashwise** (optional): Accelerated hash calculation

### Critical Implementation Details

#### Recent Refactor Impact

The batch processing mode underwent a critical refactor to eliminate data corruption issues:

**Previous Architecture** (Broken):
```
BatchProcessorThread → _copy_items_sync() → Inline file operations
```

**Current Architecture** (Proven):
```
BatchProcessorThread → FileController → FolderStructureThread
```

This change ensures both modes use the identical, battle-tested file processing pipeline.

#### Security Measures

**Path Traversal Prevention** (Both Modes):
```python
# Security validation in FolderStructureThread
dest_resolved = dest_file.resolve()
base_resolved = self.destination.resolve()
if not str(dest_resolved).startswith(str(base_resolved)):
    raise ValueError(f"Security: Path traversal detected for {relative_path}")
```

#### Forensic Compliance Features

**Integrity Enforcement** (Both Modes):
```python
# Force disk sync after each file copy
with open(dest_file, 'rb+') as f:
    os.fsync(f.fileno())  # Ensures complete write to disk
```

**Hash Verification** (Both Modes):
```python
# SHA-256 calculation during copy
source_hash = self._calculate_file_hash(source_file)
dest_hash = self._calculate_file_hash(dest_file)  
verified = source_hash == dest_hash
```

**Audit Trail Generation**:
- Complete technician logs with timestamps
- File inventory with hash verification
- Time offset documentation for DVR evidence

---

## Conclusion

The current file processing architecture represents a mature, forensically-compliant system optimized for law enforcement evidence management. The recent refactor successfully unified both processing modes under a single, proven pipeline while maintaining their distinct user experience patterns:

- **Non-Batch Mode** excels at interactive, single-operation processing with detailed user feedback
- **Batch Mode** provides autonomous, high-volume processing with robust error isolation

Both modes now share identical core file operations, ensuring consistent forensic integrity, security validation, and performance optimization across all use cases. This architecture provides a solid foundation for future enhancements while maintaining the reliability required for critical evidence management workflows.