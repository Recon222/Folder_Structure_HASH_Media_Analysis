#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch processor thread for processing multiple jobs sequentially

Nuclear migration complete - unified error handling and Result objects.
"""

import copy
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict

from PySide6.QtCore import Signal, QEventLoop, QTimer

# Nuclear migration imports
from .base_worker import BaseWorkerThread
from ..result_types import BatchOperationResult, Result
from ..exceptions import (
    BatchProcessingError, ValidationError, FileOperationError, 
    ErrorSeverity, FSAError
)
from ..error_handler import handle_error

# Existing imports
from ..batch_queue import BatchQueue
from ..models import BatchJob
from .folder_operations import FolderStructureThread
from ..path_utils import ForensicPathBuilder
from ..settings_manager import settings
from ..logger import logger
from controllers.workflow_controller import WorkflowController


class BatchProcessorThread(BaseWorkerThread):
    """
    Processes batch jobs sequentially with unified error handling
    
    NUCLEAR MIGRATION COMPLETE:
    - NEW: result_ready = Signal(Result)       ✅ UNIFIED (inherited)
    - NEW: progress_update = Signal(int, str)  ✅ UNIFIED (inherited)
    - PRESERVED: Custom batch-specific signals for UI coordination
    """
    
    # Custom batch-specific signals (preserved for batch UI coordination)
    job_started = Signal(str, str)  # job_id, job_name
    job_progress = Signal(str, int, str)  # job_id, percentage, message
    job_completed = Signal(str, bool, str, object)  # job_id, success, message, results
    queue_progress = Signal(int, int)  # completed_jobs, total_jobs
    queue_completed = Signal(int, int, int)  # total, successful, failed
    
    # Unified signals inherited from BaseWorkerThread:
    # result_ready = Signal(Result)      # Final batch operation result
    # progress_update = Signal(int, str) # Queue-level progress
    
    def __init__(self, batch_queue: BatchQueue, main_window=None):
        super().__init__()
        self.batch_queue = batch_queue
        self.main_window = main_window
        # cancelled is inherited from BaseWorkerThread
        self.pause_requested = False
        self.current_job = None
        self.current_worker_thread = None
        
        # Set descriptive operation name
        pending_count = len(batch_queue.get_pending_jobs()) if batch_queue else 0
        self.set_operation_name(f"Batch Processing ({pending_count} jobs)")
        
    def run(self):
        """Process all jobs in the queue with unified error handling"""
        try:
            # Initial validation
            if not self.batch_queue:
                error = ValidationError(
                    field_errors={"batch_queue": "Batch queue not available"},
                    user_message="Batch queue is not available for processing."
                )
                self.handle_error(error, {'stage': 'initialization'})
                self.emit_result(Result.error(error))
                return
                
            pending_jobs = self.batch_queue.get_pending_jobs()
            total_jobs = len(pending_jobs)
            completed = 0
            successful = 0
            failed = 0
            job_results = []
            
            # Enhanced data collection for rich success messages
            batch_start_time = datetime.now()
            total_files_processed = 0
            total_bytes_processed = 0
            speed_samples = []  # [(speed_mbps, job_name), ...]
            report_counts = defaultdict(int)  # {"time_offset": 4, "technician_log": 3}
            total_report_size = 0
            zip_archive_count = 0
            total_zip_size = 0
            failed_job_details = []
            output_directories = []
            
            if total_jobs == 0:
                # Empty queue - emit successful empty result
                self.queue_completed.emit(0, 0, 0)
                result = BatchOperationResult.create(
                    [], 
                    metadata={'message': 'No jobs to process'}
                )
                self.emit_result(result)
                return
                
            # Emit queue-level progress at start
            self.emit_progress(0, f"Starting batch processing of {total_jobs} jobs")
            
            while True:
                if self.cancelled:
                    break
                    
                # Handle pause
                while self.pause_requested and not self.cancelled:
                    self.msleep(100)
                    
                # Get next job
                job = self.batch_queue.get_next_pending_job()
                if not job:
                    break  # No more pending jobs
                    
                # Process the job
                try:
                    self.job_started.emit(job.job_id, job.job_name)
                    job.status = "processing"
                    job.start_time = datetime.now()
                    self.current_job = job
                    
                    # Update job in queue
                    self.batch_queue.update_job(job)
                
                    # Run the actual processing (always forensic mode) - now returns Result
                    job_result = self._process_forensic_job(job)
                    
                    job.end_time = datetime.now()
                    
                    # Handle Result object
                    if job_result.success:
                        job.status = "completed"
                        successful += 1
                        
                        # Extract and aggregate data from successful job
                        if job_result.value and isinstance(job_result.value, dict):
                            job_data = job_result.value
                            
                            # Aggregate file processing data
                            if 'file_summary' in job_data:
                                file_summary = job_data['file_summary']
                                total_files_processed += file_summary.get('files_processed', 0)
                                total_bytes_processed += file_summary.get('total_size', 0)
                            
                            # Collect speed data from metadata
                            if job_result.metadata and 'files_processed' in job_result.metadata:
                                # Calculate speed if we have timing data
                                if hasattr(job, 'start_time') and hasattr(job, 'end_time') and job.start_time and job.end_time:
                                    duration_seconds = (job.end_time - job.start_time).total_seconds()
                                    if duration_seconds > 0 and 'total_size' in job_data.get('file_summary', {}):
                                        size_mb = job_data['file_summary']['total_size'] / (1024 * 1024)
                                        speed_mbps = size_mb / duration_seconds
                                        speed_samples.append((speed_mbps, job.job_name))
                            
                            # Aggregate report data
                            if 'report_results' in job_data and job_data['report_results']:
                                for report_type, report_path in job_data['report_results'].items():
                                    report_counts[report_type] += 1
                                    # Try to get file size
                                    try:
                                        if isinstance(report_path, (str, Path)):
                                            report_file = Path(report_path)
                                            if report_file.exists():
                                                total_report_size += report_file.stat().st_size
                                    except:
                                        pass  # Size unavailable, continue
                            
                            # Aggregate ZIP data
                            if 'zip_results' in job_data and job_data['zip_results']:
                                zip_data = job_data['zip_results']
                                if 'created_archives' in zip_data and zip_data['created_archives']:
                                    zip_archive_count += len(zip_data['created_archives'])
                                    # Calculate total ZIP size
                                    for archive_path in zip_data['created_archives']:
                                        try:
                                            if Path(archive_path).exists():
                                                total_zip_size += Path(archive_path).stat().st_size
                                        except:
                                            pass  # Size unavailable, continue
                            
                            # Collect output directories
                            if 'output_path' in job_data:
                                output_dir = Path(job_data['output_path'])
                                if output_dir not in output_directories:
                                    output_directories.append(output_dir)
                        
                        job_results.append({
                            'success': True,
                            'job_id': job.job_id,
                            'job_name': job.job_name,
                            'result': job_result.value,
                            'metadata': job_result.metadata
                        })
                        # Keep existing signal for UI compatibility
                        self.job_completed.emit(job.job_id, True, "Job completed successfully", job_result.value)
                    else:
                        job.status = "failed"
                        job.error_message = job_result.error.user_message if job_result.error else "Unknown error"
                        failed += 1
                        
                        # Collect failed job details for rich error reporting
                        failed_job_details.append(f"Job '{job.job_name}' failed - {job.error_message}")
                        
                        job_results.append({
                            'success': False,
                            'job_id': job.job_id,
                            'job_name': job.job_name,
                            'error': job_result.error.user_message if job_result.error else "Unknown error",
                            'error_details': job_result.error
                        })
                        # Keep existing signal for UI compatibility
                        self.job_completed.emit(job.job_id, False, job.error_message, None)
                    
                except Exception as e:
                    # Fallback error handling for unexpected exceptions in job processing loop
                    job.status = "failed"
                    job.error_message = str(e)
                    job.end_time = datetime.now()
                    failed += 1
                    
                    # Collect failed job details for rich error reporting
                    failed_job_details.append(f"Job '{job.job_name}' failed - Unexpected error: {e}")
                    
                    job_results.append({
                        'success': False,
                        'job_id': job.job_id,
                        'job_name': job.job_name,
                        'error': f"Unexpected error: {e}",
                        'error_details': e
                    })
                    self.job_completed.emit(job.job_id, False, str(e), None)
                    
                # Update job in queue
                self.batch_queue.update_job(job)
                self.current_job = None
                
                completed += 1
                # Emit both queue-level and unified progress
                self.queue_progress.emit(completed, total_jobs)
                queue_progress_pct = int((completed / total_jobs) * 100) if total_jobs > 0 else 100
                self.emit_progress(queue_progress_pct, f"Processed {completed}/{total_jobs} jobs")
            
            # Emit final completion signals
            self.queue_completed.emit(total_jobs, successful, failed)
            
            # Calculate aggregate metrics
            batch_end_time = datetime.now()
            total_processing_time = (batch_end_time - batch_start_time).total_seconds()
            
            # Calculate aggregate and peak speeds
            aggregate_speed = 0
            peak_speed = 0
            peak_speed_job = ""
            if speed_samples:
                # Aggregate speed: total size / total time
                if total_processing_time > 0:
                    total_size_mb = total_bytes_processed / (1024 * 1024)
                    aggregate_speed = total_size_mb / total_processing_time
                
                # Peak speed: maximum from individual jobs
                peak_speed, peak_speed_job = max(speed_samples, key=lambda x: x[0])
            
            # Create enhanced batch data
            from core.services.success_message_data import EnhancedBatchOperationData
            enhanced_batch_data = EnhancedBatchOperationData(
                total_jobs=total_jobs,
                successful_jobs=successful,
                failed_jobs=failed,
                processing_time_seconds=total_processing_time,
                total_files_processed=total_files_processed,
                total_bytes_processed=total_bytes_processed,
                aggregate_speed_mbps=aggregate_speed,
                peak_speed_mbps=peak_speed,
                peak_speed_job_name=peak_speed_job,
                total_reports_generated=sum(report_counts.values()),
                report_breakdown=dict(report_counts),
                total_report_size_bytes=total_report_size,
                total_zip_archives=zip_archive_count,
                total_zip_size_bytes=total_zip_size,
                job_results=job_results,
                failed_job_summaries=failed_job_details,
                batch_output_directories=output_directories,
                batch_start_time=batch_start_time,
                batch_end_time=batch_end_time
            )
            
            # Create final BatchOperationResult and emit via unified result_ready signal
            batch_result = BatchOperationResult.create(
                job_results,
                metadata={
                    'total_jobs': total_jobs,
                    'successful_jobs': successful,
                    'failed_jobs': failed,
                    'success_rate': (successful / total_jobs * 100) if total_jobs > 0 else 100.0,
                    'operation_name': self.operation_name,
                    'enhanced_batch_data': enhanced_batch_data  # Include enhanced data for rich success messages
                }
            )
            
            # Final progress update
            if successful == total_jobs:
                self.emit_progress(100, f"All {total_jobs} jobs completed successfully")
            elif failed == total_jobs:
                self.emit_progress(100, f"All {total_jobs} jobs failed")
            else:
                self.emit_progress(100, f"Batch complete: {successful} successful, {failed} failed")
                
            # Emit the unified result
            self.emit_result(batch_result)
        
        except Exception as e:
            # Handle unexpected errors in the main run loop
            error = BatchProcessingError(
                job_id="batch_queue", 
                successes=successful, 
                failures=failed + 1,
                error_details=[str(e)],
                user_message="Batch processing encountered an unexpected error."
            )
            
            context = {
                'stage': 'main_processing_loop',
                'total_jobs': total_jobs,
                'completed': completed,
                'successful': successful,
                'failed': failed,
                'exception_type': e.__class__.__name__,
                'exception_str': str(e),
                'severity': 'critical'
            }
            
            self.handle_error(error, context)
            self.emit_result(Result.error(error))
        
    def _execute_folder_thread_sync(self, folder_thread: FolderStructureThread) -> tuple[bool, str, Dict]:
        """Execute FolderStructureThread synchronously within batch thread"""
        
        # Create event loop for synchronous execution
        loop = QEventLoop()
        result_container = {'success': False, 'message': '', 'results': {}}
        
        # Connect completion handler (NUCLEAR MIGRATION: Use Result objects)
        def on_thread_result(result):
            """Handle nuclear migration Result object"""
            from core.result_types import Result
            
            if isinstance(result, Result):
                # Handle error message safely
                if result.success:
                    message = "Operation completed"
                else:
                    # Check if error has user_message attribute (FSAError object)
                    if hasattr(result.error, 'user_message'):
                        message = result.error.user_message
                    elif hasattr(result.error, 'message'):
                        message = result.error.message
                    else:
                        message = str(result.error) if result.error else "Operation failed"
                
                result_container.update({
                    'success': result.success,
                    'message': message,
                    'results': result.value if result.value else {}
                })
            else:
                # Fallback for unexpected result format
                result_container.update({
                    'success': False,
                    'message': "Unexpected result format",
                    'results': {}
                })
            loop.quit()
        
        # Connect progress forwarding (NUCLEAR MIGRATION: Unified progress signal)
        def on_thread_progress_update(percentage: int, status_message: str):
            """Handle nuclear migration unified progress signal"""
            # Scale file progress to job level (0-80% of job)
            job_file_progress = int(percentage * 0.8)
            if self.current_job:
                self.job_progress.emit(self.current_job.job_id, job_file_progress, f"Copying files... {status_message}")
        
        # Wire up NEW nuclear migration signals
        folder_thread.result_ready.connect(on_thread_result)
        folder_thread.progress_update.connect(on_thread_progress_update)
        
        # Handle cancellation and timeout
        def check_cancellation():
            if self.cancelled:
                logger.info(f"Cancelling folder thread for job {getattr(self.current_job, 'job_id', 'Unknown')}")
                folder_thread.cancel()
                loop.quit()
        
        # Start and wait for completion
        folder_thread.start()
        
        # Periodically check for cancellation while waiting
        cancel_timer = QTimer()
        cancel_timer.timeout.connect(check_cancellation)
        cancel_timer.start(100)  # Check every 100ms
        
        loop.exec()  # Synchronous wait
        
        cancel_timer.stop()
        
        return result_container['success'], result_container['message'], result_container['results']

    def _validate_copy_results(self, results: Dict, job: BatchJob) -> bool:
        """Validate that all expected files were copied successfully"""
        
        # Calculate expected file count
        expected_file_count = len([f for f in job.files if f.exists()])
        for folder in job.folders:
            if folder.exists():
                expected_file_count += len([f for f in folder.rglob('*') if f.is_file()])
        
        # Check results count (exclude _performance_stats entry)
        actual_file_count = len([
            r for key, r in results.items() 
            if isinstance(r, dict) and key != '_performance_stats' and 'error' not in r
        ])
        
        if actual_file_count != expected_file_count:
            logger.error(f"File count mismatch: expected {expected_file_count}, got {actual_file_count}")
            return False
            
        # Check for hash verification failures if hashing is enabled
        if settings.calculate_hashes:
            failed_verifications = [
                path for path, result in results.items()
                if isinstance(result, dict) and path != '_performance_stats' and not result.get('verified', True)
            ]
            if failed_verifications:
                logger.error(f"Hash verification failed for {len(failed_verifications)} files: {failed_verifications[:5]}")  # Log first 5
                return False
        
        return True

    def _process_forensic_job(self, job: BatchJob) -> Result:
        """Process a forensic mode job with Result-based error handling"""
        try:
            # Validate inputs
            if not self.main_window:
                error = ValidationError(
                    field_errors={"main_window": "Main window reference not available"},
                    user_message="System error: Main window not available for batch processing."
                )
                self.handle_error(error, {'job_id': job.job_id, 'validation': 'main_window'})
                return Result.error(error)
                
            if not job.files and not job.folders:
                error = ValidationError(
                    field_errors={"files_folders": "No valid files or folders to process"},
                    user_message="No files or folders selected for processing."
                )
                self.handle_error(error, {'job_id': job.job_id, 'validation': 'empty_selection'})
                return Result.error(error)
                
            # Use proven WorkflowController pipeline with service integration
            workflow_controller = WorkflowController()
            workflow_result = workflow_controller.process_forensic_workflow(
                form_data=job.form_data,
                files=job.files,
                folders=job.folders, 
                output_directory=Path(job.output_directory),
                calculate_hash=settings.calculate_hashes,
                performance_monitor=None  # Simplified for batch mode
            )
            
            # Check workflow setup result
            if not workflow_result.success:
                # WorkflowController setup failed
                error = FileOperationError(
                    f"Workflow setup failed for job {job.job_id}: {workflow_result.error.message}",
                    user_message="Failed to setup file processing workflow. Please check form data and file paths.",
                    context={
                        'job_id': job.job_id,
                        'job_name': job.job_name,
                        'files_count': len(job.files),
                        'folders_count': len(job.folders),
                        'output_directory': job.output_directory
                    }
                )
                self.handle_error(error, {'stage': 'workflow_setup', 'job_id': job.job_id})
                return Result.error(error)
            
            # Extract thread from successful workflow result
            folder_thread = workflow_result.value
            
            # Execute synchronously within batch thread using proven forensic pipeline
            success, message, results = self._execute_folder_thread_sync(folder_thread)
            
            if not success:
                # Create specific error for file operations failure
                error = FileOperationError(
                    f"File operations failed for job {job.job_id}: {message}",
                    user_message="File copying failed. Please check permissions and disk space.",
                    context={
                        'job_id': job.job_id,
                        'job_name': job.job_name,
                        'files_count': len(job.files),
                        'folders_count': len(job.folders),
                        'output_directory': job.output_directory
                    }
                )
                self.handle_error(error, {'stage': 'file_operations', 'job_id': job.job_id})
                return Result.error(error)
                
            # Validate results integrity
            if not self._validate_copy_results(results, job):
                error = FileOperationError(
                    f"Job {job.job_id} failed file integrity validation",
                    user_message="File integrity validation failed. Some files may not have been copied correctly.",
                    context={'job_id': job.job_id, 'job_name': job.job_name}
                )
                self.handle_error(error, {'stage': 'integrity_validation', 'job_id': job.job_id})
                return Result.error(error)
            
            # Get the actual output path from the results (FileController creates the full structure)
            output_path = Path(job.output_directory) / self._build_folder_path(job, "forensic")
            
            # Update progress to 80% (file copying complete)
            if self.current_job:
                self.job_progress.emit(self.current_job.job_id, 80, "Generating reports...")
            
            # Generate reports if successful
            report_results = self._generate_reports(job, output_path, results)
            
            # Update progress to 90% (reports complete)
            if self.current_job:
                self.job_progress.emit(self.current_job.job_id, 90, "Creating ZIP archives...")
            
            # Handle ZIP creation if enabled
            zip_results = self._create_zip_archives(job, output_path)
            
            # Create memory-efficient summary instead of storing full results
            file_summary = {
                'files_processed': len([r for r in results.values() if isinstance(r, dict) and 'error' not in r]),
                'total_size': sum(r.get('size', 0) for r in results.values() if isinstance(r, dict)),
                'verification_passed': all(r.get('verified', True) for r in results.values() if isinstance(r, dict) and 'size' in r)
            }
            
            # Update progress to 100% (job complete)
            if self.current_job:
                self.job_progress.emit(self.current_job.job_id, 100, f"Job completed - {file_summary['files_processed']} files processed")
            
            # Create successful result with comprehensive job data
            job_result = {
                'job_id': job.job_id,
                'job_name': job.job_name,
                'file_summary': file_summary,
                'report_results': report_results,
                'zip_results': zip_results,
                'output_path': str(output_path)
            }
            
            return Result.success(
                job_result,
                metadata={
                    'files_processed': file_summary['files_processed'],
                    'total_size': file_summary['total_size'],
                    'verification_passed': file_summary['verification_passed'],
                    'job_id': job.job_id
                }
            )
            
        except FSAError as e:
            # FSA errors are already properly formatted
            self.handle_error(e, {'job_id': job.job_id, 'stage': 'job_processing'})
            return Result.error(e)
            
        except Exception as e:
            # Convert unexpected errors to BatchProcessingError
            error = BatchProcessingError(
                job_id=job.job_id,
                successes=0,
                failures=1,
                error_details=[str(e)],
                user_message=f"Unexpected error processing job {job.job_name}. Please try again."
            )
            
            context = {
                'job_id': job.job_id,
                'job_name': getattr(job, 'job_name', 'Unknown'),
                'files_count': len(getattr(job, 'files', [])),
                'folders_count': len(getattr(job, 'folders', [])),
                'exception_type': e.__class__.__name__,
                'exception_str': str(e),
                'severity': 'critical'
            }
            
            self.handle_error(error, context)
            return Result.error(error)
            
    def _build_folder_path(self, job: BatchJob, template_type: str) -> Path:
        """Build the folder path for the job without side effects"""
        if template_type == "forensic":
            # Use ForensicPathBuilder to build relative path without creating directories
            relative_path = ForensicPathBuilder.build_relative_path(job.form_data)
            # Return just the relative path - caller will combine with output directory
            return relative_path
        
    def _generate_reports(self, job: BatchJob, output_path: Path, file_results: Dict) -> Dict:
        """Generate reports for the job with correct API calls"""
        try:
            # Import PDF generator and use correct API
            from ..pdf_gen import PDFGenerator
            
            # Create reports directory - move to business/location level instead of occurrence level
            reports_dir = output_path.parent / "Documents"
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            # Create PDFGenerator instance (no constructor params)
            pdf_gen = PDFGenerator()
            generated_reports = {}
            
            # Generate time offset report if enabled and offset exists
            if settings.generate_time_offset_pdf and job.form_data.time_offset:
                time_offset_path = reports_dir / f"{job.form_data.occurrence_number}_TimeOffset.pdf"
                # Nuclear migration: handle Result objects
                result = pdf_gen.generate_time_offset_report(job.form_data, time_offset_path)
                if result.success:
                    generated_reports['time_offset'] = result.value
                    logger.info(f"Generated time offset report: {result.value}")
                else:
                    logger.warning(f"Failed to generate time offset report: {result.error.user_message if result.error else 'Unknown error'}")
                
            # Generate upload log if enabled
            if settings.generate_upload_log_pdf:
                upload_log_path = reports_dir / f"{job.form_data.occurrence_number}_UploadLog.pdf"
                # Nuclear migration: handle Result objects
                result = pdf_gen.generate_technician_log(job.form_data, upload_log_path)
                if result.success:
                    generated_reports['upload_log'] = result.value
                    logger.info(f"Generated upload log: {result.value}")
                else:
                    logger.warning(f"Failed to generate upload log: {result.error.user_message if result.error else 'Unknown error'}")
            
            # Generate hash CSV if enabled and we have hash results
            if settings.generate_hash_csv and file_results:
                # Check if any file has hash values (skip _performance_stats)
                has_hashes = any(
                    result.get('source_hash') or result.get('dest_hash')
                    for key, result in file_results.items()
                    if isinstance(result, dict) and key != '_performance_stats'
                )
                
                if has_hashes:
                    hash_csv_path = reports_dir / f"{job.form_data.occurrence_number}_Hashes.csv"
                    # Nuclear migration: handle Result objects
                    result = pdf_gen.generate_hash_verification_csv(file_results, hash_csv_path)
                    if result.success:
                        generated_reports['hash_csv'] = result.value
                        logger.info(f"Generated hash CSV: {result.value}")
                    else:
                        logger.warning(f"Failed to generate hash CSV: {result.error.user_message if result.error else 'Unknown error'}")
                
            return generated_reports
            
        except Exception as e:
            logger.warning(f"Failed to generate reports for job {job.job_id}: {e}")
            return {}
            
    def _create_zip_archives(self, job: BatchJob, output_path: Path) -> Dict:
        """Create ZIP archives for the job if enabled"""
        try:
            # Check if ZIP creation is enabled via the main window's zip controller
            if not self.main_window or not hasattr(self.main_window, 'zip_controller'):
                logger.debug("No main_window or zip_controller available for ZIP creation")
                return {}
                
            zip_controller = self.main_window.zip_controller
            
            # Check if we should create ZIP (this handles session overrides)
            try:
                should_create = zip_controller.should_create_zip()
                if not should_create:
                    logger.debug("ZIP creation disabled by user settings")
                    return {}
            except ValueError as e:
                # Prompt not resolved - skip ZIP creation in batch mode
                logger.debug(f"ZIP creation prompt not resolved in batch mode: {e}")
                return {}
            
            # Find the occurrence folder (go up from output_path to occurrence level)
            occurrence_folder = output_path.parent.parent  # output_path is datetime folder
            
            # Create ZIP synchronously using the controller's settings
            zip_thread = zip_controller.create_zip_thread(
                occurrence_folder,
                Path(job.output_directory),
                job.form_data
            )
            
            # Since we're in a thread already, we need to run this synchronously
            # We'll use the ZipUtility directly instead of the thread
            from utils.zip_utils import ZipUtility
            
            settings = zip_controller.get_zip_settings()
            settings.output_path = Path(job.output_directory)
            
            zip_util = ZipUtility(
                progress_callback=lambda pct, msg: self.job_progress.emit(
                    job.job_id, pct, f"Creating ZIP: {msg}"
                )
            )
            
            created_archives = zip_util.create_multi_level_archives(occurrence_folder, settings, job.form_data)
            
            return {
                'created_archives': created_archives,
                'settings': {
                    'compression_level': settings.compression_level,
                    'zip_level': zip_controller.settings.zip_level
                }
            }
            
        except Exception as e:
            # Make error visible to user via progress signal
            error_msg = f"ZIP creation failed: {e}"
            self.job_progress.emit(job.job_id, -1, error_msg)
            logger.warning(f"Failed to create ZIP archives for job {job.job_id}: {e}")
            return {'error': str(e)}
            
    def cancel(self):
        """Cancel the batch processing"""
        # Call base class cancel for unified cancellation
        super().cancel()
        
        # Cancel current worker thread if running
        if self.current_worker_thread:
            if hasattr(self.current_worker_thread, 'cancel'):
                self.current_worker_thread.cancel()
            elif hasattr(self.current_worker_thread, 'cancelled'):
                self.current_worker_thread.cancelled = True
                
    def pause(self):
        """Pause the batch processing"""
        self.pause_requested = True
        
    def resume(self):
        """Resume the batch processing"""
        self.pause_requested = False
        
    def is_paused(self) -> bool:
        """Check if processing is paused"""
        return self.pause_requested
        
    def get_current_job_id(self) -> str:
        """Get the ID of the currently processing job"""
        if self.current_job:
            return self.current_job.job_id
        return ""