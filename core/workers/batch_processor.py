#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch processor thread for processing multiple jobs sequentially
"""

import copy
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from PySide6.QtCore import QThread, Signal, QEventLoop, QTimer

from ..batch_queue import BatchQueue
from ..models import BatchJob
from ..templates import FolderBuilder
from .folder_operations import FolderStructureThread
from ..path_utils import ForensicPathBuilder
from ..settings_manager import settings
from ..logger import logger
from controllers.file_controller import FileController


class BatchProcessorThread(QThread):
    """Processes batch jobs sequentially"""
    
    # Signals
    job_started = Signal(str, str)  # job_id, job_name
    job_progress = Signal(str, int, str)  # job_id, percentage, message
    job_completed = Signal(str, bool, str, object)  # job_id, success, message, results
    queue_progress = Signal(int, int)  # completed_jobs, total_jobs
    queue_completed = Signal(int, int, int)  # total, successful, failed
    
    def __init__(self, batch_queue: BatchQueue, main_window=None):
        super().__init__()
        self.batch_queue = batch_queue
        self.main_window = main_window
        self.cancelled = False
        self.pause_requested = False
        self.current_job = None
        self.current_worker_thread = None
        
    def run(self):
        """Process all jobs in the queue"""
        pending_jobs = self.batch_queue.get_pending_jobs()
        total_jobs = len(pending_jobs)
        completed = 0
        successful = 0
        failed = 0
        
        if total_jobs == 0:
            self.queue_completed.emit(0, 0, 0)
            return
            
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
                
                # Run the actual processing (always forensic mode)
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
                job.status = "failed"
                job.error_message = str(e)
                job.end_time = datetime.now()
                failed += 1
                self.job_completed.emit(job.job_id, False, str(e), None)
                
            # Update job in queue
            self.batch_queue.update_job(job)
            self.current_job = None
            
            completed += 1
            self.queue_progress.emit(completed, total_jobs)
            
        # Emit final completion
        self.queue_completed.emit(total_jobs, successful, failed)
        
    def _execute_folder_thread_sync(self, folder_thread: FolderStructureThread) -> tuple[bool, str, Dict]:
        """Execute FolderStructureThread synchronously within batch thread"""
        
        # Create event loop for synchronous execution
        loop = QEventLoop()
        result_container = {'success': False, 'message': '', 'results': {}}
        
        # Connect completion handler
        def on_thread_finished(success: bool, message: str, results: Dict):
            result_container.update({
                'success': success,
                'message': message, 
                'results': results
            })
            loop.quit()
        
        # Connect progress forwarding - scale file progress to job level (0-80% of job)
        def on_thread_progress(pct: int):
            job_file_progress = int(pct * 0.8)
            if self.current_job:
                self.job_progress.emit(self.current_job.job_id, job_file_progress, f"Copying files... {pct}%")
                
        def on_thread_status(msg: str):
            if self.current_job:
                self.job_progress.emit(self.current_job.job_id, -1, msg)
        
        # Wire up signals
        folder_thread.finished.connect(on_thread_finished)
        folder_thread.progress.connect(on_thread_progress) 
        folder_thread.status.connect(on_thread_status)
        
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

    def _process_forensic_job(self, job: BatchJob) -> tuple[bool, str, Any]:
        """Process a forensic mode job"""
        try:
            # Validate inputs
            if not self.main_window:
                return False, "Main window reference not available", None
                
            if not job.files and not job.folders:
                return False, "No valid files or folders to process", None
                
            # Use proven FileController pipeline instead of broken inline implementation
            file_controller = FileController()
            folder_thread = file_controller.process_forensic_files(
                job.form_data,
                job.files,
                job.folders, 
                Path(job.output_directory),
                calculate_hash=settings.calculate_hashes,
                performance_monitor=None  # Simplified for batch mode
            )
            
            # Execute synchronously within batch thread using proven forensic pipeline
            success, message, results = self._execute_folder_thread_sync(folder_thread)
            
            if not success:
                # Log detailed error information including job details
                logger.error(f"Job {job.job_id} ({job.job_name}) file operations failed: {message}")
                logger.info(f"Job details - Files: {len(job.files)}, Folders: {len(job.folders)}, Output: {job.output_directory}")
                return False, f"File operations failed: {message}", None
                
            # Validate results integrity
            if not self._validate_copy_results(results, job):
                logger.error(f"Job {job.job_id} ({job.job_name}) failed integrity validation")
                return False, "File integrity validation failed", None
            
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
            
            return True, f"Job completed successfully. {file_summary['files_processed']} files processed.", {
                'file_summary': file_summary,
                'report_results': report_results,
                'zip_results': zip_results,
                'output_path': output_path
            }
            
        except Exception as e:
            # Log full exception details for debugging
            logger.error(f"Job {job.job_id} ({getattr(job, 'job_name', 'Unknown')}) failed with exception: {e}", exc_info=True)
            logger.info(f"Failed job details - Files: {len(getattr(job, 'files', []))}, Folders: {len(getattr(job, 'folders', []))}")
            return False, f"Unexpected error: {e}", None
            
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
                # Correct API: generate_time_offset_report(form_data, output_path)
                if pdf_gen.generate_time_offset_report(job.form_data, time_offset_path):
                    generated_reports['time_offset'] = time_offset_path
                    logger.info(f"Generated time offset report: {time_offset_path}")
                
            # Generate upload log if enabled
            if settings.generate_upload_log_pdf:
                upload_log_path = reports_dir / f"{job.form_data.occurrence_number}_UploadLog.pdf"
                # Correct API: generate_technician_log(form_data, output_path)
                if pdf_gen.generate_technician_log(job.form_data, upload_log_path):
                    generated_reports['upload_log'] = upload_log_path
                    logger.info(f"Generated upload log: {upload_log_path}")
            
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
                    # Correct API: generate_hash_verification_csv(file_results, output_path)
                    if pdf_gen.generate_hash_verification_csv(file_results, hash_csv_path):
                        generated_reports['hash_csv'] = hash_csv_path
                        logger.info(f"Generated hash CSV: {hash_csv_path}")
                
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
        self.cancelled = True
        
        # Cancel current worker thread if running
        if self.current_worker_thread:
            if hasattr(self.current_worker_thread, 'cancelled'):
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