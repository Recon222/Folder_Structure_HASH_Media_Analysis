#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch processor thread for processing multiple jobs sequentially
"""

import copy
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import shutil
import os

from PySide6.QtCore import QThread, Signal

from ..batch_queue import BatchQueue
from ..models import BatchJob
from ..file_ops import FileOperations
from ..buffered_file_ops import BufferedFileOperations, PerformanceMetrics
from ..templates import FolderBuilder
from .file_operations import FileOperationThread
from .folder_operations import FolderStructureThread
from ..path_utils import ForensicPathBuilder, PathSanitizer
from ..settings_manager import settings
from ..logger import logger


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
        
    def _process_forensic_job(self, job: BatchJob) -> tuple[bool, str, Any]:
        """Process a forensic mode job"""
        try:
            # Create folder structure for forensic mode
            if not self.main_window:
                return False, "Main window reference not available", None
                
            # Build the folder path
            relative_path = self._build_folder_path(job, "forensic")
            
            # Create the full output path (job.output_directory is a string)
            output_path = Path(job.output_directory) / relative_path
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Prepare items for copying (files and folders)
            items_to_copy = []
            
            # Add individual files
            for file_path in job.files:
                if file_path.exists():
                    items_to_copy.append(('file', file_path, file_path.name))
                    
            # Add folders
            for folder_path in job.folders:
                if folder_path.exists():
                    items_to_copy.append(('folder', folder_path, folder_path.name))
                    
            if not items_to_copy:
                return False, "No valid files or folders to process", None
                
            # Process files using folder operations thread
            success, message, results = self._copy_items_sync(items_to_copy, output_path, job)
            
            if success:
                # Generate reports if successful
                report_results = self._generate_reports(job, output_path, results)
                
                # Handle ZIP creation if enabled
                zip_results = self._create_zip_archives(job, output_path)
                
                return True, f"Job completed successfully. {len(results)} files processed.", {
                    'file_results': results,
                    'report_results': report_results,
                    'zip_results': zip_results,
                    'output_path': output_path
                }
            else:
                return False, message, results
                
        except Exception as e:
            return False, f"Error processing forensic job: {e}", None
            
                    
            if not items_to_copy:
                return False, "No valid files or folders to process", None
                
            # Process files
            success, message, results = self._copy_items_sync(items_to_copy, output_path, job)
            
            if success:
                return True, f"Custom job completed successfully. {len(results)} files processed.", {
                    'file_results': results,
                    'output_path': output_path
                }
            else:
                return False, message, results
                
        except Exception as e:
            return False, f"Error processing custom job: {e}", None
            
    def _build_folder_path(self, job: BatchJob, template_type: str) -> Path:
        """Build the folder path for the job without side effects"""
        if template_type == "forensic":
            # Use ForensicPathBuilder to build relative path without creating directories
            relative_path = ForensicPathBuilder.build_relative_path(job.form_data)
            # Return just the relative path - caller will combine with output directory
            return relative_path
        
    def _copy_items_sync(self, items_to_copy: List[tuple], destination: Path, job: BatchJob) -> tuple[bool, str, Dict]:
        """Copy items synchronously with progress reporting using FileOperations directly"""
        try:
            # Create destination directory
            destination.mkdir(parents=True, exist_ok=True)
            
            # Choose file operations based on settings
            if settings.use_buffered_operations:
                # Use high-performance buffered operations
                file_ops = BufferedFileOperations(
                    progress_callback=lambda pct, msg: self.job_progress.emit(
                        self.current_index, pct, msg
                    )
                )
            else:
                # Use legacy file operations
                file_ops = FileOperations()
            
            results = {}
            
            # Collect all files to process
            all_files = []
            for item_type, path, relative in items_to_copy:
                if item_type == 'file':
                    all_files.append((path, relative))
                elif item_type == 'folder':
                    # Get all files in folder recursively
                    for file_path in path.rglob('*'):
                        if file_path.is_file():
                            # Preserve folder structure
                            relative_path = file_path.relative_to(path.parent)
                            all_files.append((file_path, relative_path))
            
            if not all_files:
                return True, "No files to copy", {}
            
            # Calculate total size for progress
            total_size = sum(f[0].stat().st_size for f in all_files if f[0].exists())
            copied_size = 0
            
            # Copy each file
            for idx, (source_file, relative_path) in enumerate(all_files):
                if self.cancelled:
                    return False, "Operation cancelled", results
                
                try:
                    # Create destination path preserving structure
                    dest_file = destination / relative_path
                    
                    # SECURITY: Validate destination stays within bounds
                    dest_validated = PathSanitizer.validate_destination(dest_file, destination)
                    dest_validated.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Emit status
                    self.job_progress.emit(
                        job.job_id,  # Use job's ID instead of non-existent current_index
                        int((idx / len(all_files)) * 100),
                        f"Copying: {relative_path.name}"
                    )
                    
                    # Use buffered copy if available
                    if settings.use_buffered_operations:
                        # Use buffered copy for better performance
                        copy_result = file_ops.copy_file_buffered(
                            source_file, 
                            dest_validated,
                            calculate_hash=settings.calculate_hashes
                        )
                        source_hash = copy_result.get('source_hash', '')
                        dest_hash = copy_result.get('dest_hash', '')
                        verified = copy_result.get('verified', True)
                    else:
                        # Legacy method
                        source_hash = ""
                        if settings.calculate_hashes:
                            source_hash = file_ops._calculate_file_hash(source_file)
                        
                        # Copy file
                        shutil.copy2(source_file, dest_validated)
                        
                        # Force flush to disk to ensure complete write (fixes VLC playback issue)
                        with open(dest_validated, 'rb+') as f:
                            os.fsync(f.fileno())
                        
                        # Calculate destination hash
                        dest_hash = ""
                        verified = True
                        if settings.calculate_hashes:
                            dest_hash = file_ops._calculate_file_hash(dest_validated)
                            verified = source_hash == dest_hash
                    
                    # Store results
                    results[str(dest_validated)] = {
                        'source': str(source_file),
                        'destination': str(dest_validated),
                        'size': source_file.stat().st_size,
                        'source_hash': source_hash,
                        'dest_hash': dest_hash,
                        'verified': verified
                    }
                    
                    # Update progress
                    copied_size += source_file.stat().st_size
                    
                except Exception as e:
                    logger.error(f"Failed to copy {source_file}: {e}")
                    results[str(source_file)] = {
                        'error': str(e),
                        'source': str(source_file),
                        'verified': False
                    }
            
            # Add performance stats
            results['_performance_stats'] = {
                'total_files': len(all_files),
                'total_size': total_size,
                'files_copied': len([r for r in results.values() if isinstance(r, dict) and 'error' not in r])
            }
            
            success_count = results['_performance_stats']['files_copied']
            return True, f"Successfully copied {success_count}/{len(all_files)} files", results
                
        except Exception as e:
            logger.error(f"Batch copy failed: {e}", exc_info=True)
            return False, f"Error copying files: {e}", {}
        finally:
            self.current_worker_thread = None
            
    def _generate_reports(self, job: BatchJob, output_path: Path, file_results: Dict) -> Dict:
        """Generate reports for the job with correct API calls"""
        try:
            # Import PDF generator and use correct API
            from ..pdf_gen import PDFGenerator
            
            # Create reports directory
            reports_dir = output_path.parent.parent / "Documents"
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
            print(f"Warning: Failed to generate reports for job {job.job_id}: {e}")
            return {}
            
    def _create_zip_archives(self, job: BatchJob, output_path: Path) -> Dict:
        """Create ZIP archives for the job if enabled"""
        print(f"[DEBUG] _create_zip_archives called for job {job.job_id}")
        try:
            # Check if ZIP creation is enabled via the main window's zip controller
            if not self.main_window or not hasattr(self.main_window, 'zip_controller'):
                print(f"[DEBUG] No main_window or zip_controller available")
                return {}
                
            zip_controller = self.main_window.zip_controller
            print(f"[DEBUG] Got zip_controller: {zip_controller}")
            
            # Check if we should create ZIP (this handles session overrides)
            try:
                should_create = zip_controller.should_create_zip()
                print(f"[DEBUG] should_create_zip() returned: {should_create}")
                if not should_create:
                    return {}
            except ValueError as e:
                # Prompt not resolved - skip ZIP creation in batch mode
                print(f"[DEBUG] ValueError in should_create_zip: {e}")
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
            
            created_archives = zip_util.create_multi_level_archives(occurrence_folder, settings)
            
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
            print(f"Warning: Failed to create ZIP archives for job {job.job_id}: {e}")
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