#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch processor thread for processing multiple jobs sequentially
"""

import copy
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from PySide6.QtCore import QThread, Signal

from ..batch_queue import BatchQueue
from ..models import BatchJob
from ..file_ops import FileOperations
from ..templates import FolderBuilder
from .file_operations import FileOperationThread
from .folder_operations import FolderStructureThread


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
            
            # Create the full output path
            output_path = job.output_directory / relative_path
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
                return True, f"Job completed successfully. {len(results)} files processed.", {
                    'file_results': results,
                    'report_results': report_results,
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
        """Build the folder path for the job"""
        # Import here to avoid circular imports
        from ..templates import FolderTemplate, FolderBuilder
        
        if template_type == "forensic":
            # Use the static forensic structure method
            return FolderBuilder.build_forensic_structure(job.form_data)
        
    def _copy_items_sync(self, items_to_copy: List[tuple], destination: Path, job: BatchJob) -> tuple[bool, str, Dict]:
        """Copy items synchronously with progress reporting"""
        try:
            # Create a folder structure thread and run it synchronously
            folder_thread = FolderStructureThread(
                items=items_to_copy,
                destination=destination,
                calculate_hash=True  # Always calculate hashes for batch jobs
            )
            
            # Connect progress signals to forward to batch processor signals
            folder_thread.progress.connect(
                lambda pct: self.job_progress.emit(job.job_id, pct, f"Processing files...")
            )
            folder_thread.status.connect(
                lambda msg: self.job_progress.emit(job.job_id, -1, msg)
            )
            
            # Store reference for cancellation
            self.current_worker_thread = folder_thread
            
            # Run synchronously
            folder_thread.run()
            
            # Get results from the thread's finished signal
            # Since we're running synchronously, we need to check the results directly
            if hasattr(folder_thread, '_results'):
                return True, "Files copied successfully", folder_thread._results
            else:
                # Fallback - assume success if no exception was raised
                return True, "Files copied successfully", {}
                
        except Exception as e:
            return False, f"Error copying files: {e}", {}
        finally:
            self.current_worker_thread = None
            
    def _generate_reports(self, job: BatchJob, output_path: Path, file_results: Dict) -> Dict:
        """Generate reports for the job"""
        try:
            if not self.main_window:
                return {}
                
            # Import PDF generator
            from ..pdf_gen import PDFGenerator
            
            # Create reports directory
            reports_dir = output_path.parent.parent / "Documents"
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            pdf_gen = PDFGenerator(job.form_data)
            generated_reports = {}
            
            # Generate time offset report
            if job.form_data.time_offset:
                time_offset_path = reports_dir / f"{job.form_data.occurrence_number}_TimeOffset.pdf"
                pdf_gen.generate_time_offset_report(time_offset_path)
                generated_reports['time_offset'] = time_offset_path
                
            # Generate technician log
            tech_log_path = reports_dir / f"{job.form_data.occurrence_number}_TechnicianLog.pdf"
            pdf_gen.generate_technician_log(tech_log_path)
            generated_reports['technician_log'] = tech_log_path
            
            # Generate hash CSV if we have hash results
            if file_results and any('hash' in result for result in file_results.values()):
                hash_csv_path = reports_dir / f"{job.form_data.occurrence_number}_Hashes.csv"
                pdf_gen.generate_hash_csv(hash_csv_path, file_results)
                generated_reports['hash_csv'] = hash_csv_path
                
            return generated_reports
            
        except Exception as e:
            print(f"Warning: Failed to generate reports for job {job.job_id}: {e}")
            return {}
            
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