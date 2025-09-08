#!/usr/bin/env python3
"""
Batch controller - manages batch processing operations and resources
"""
from pathlib import Path
from typing import Optional, List, Any
from datetime import datetime
import logging

from .base_controller import BaseController
from core.resource_coordinators import WorkerResourceCoordinator
from core.batch_queue import BatchQueue
from core.workers.batch_processor import BatchProcessorThread
from core.batch_recovery import BatchRecoveryManager
from core.result_types import Result
from core.exceptions import FileOperationError


class BatchController(BaseController):
    """Controller for batch processing operations"""
    
    def __init__(self):
        super().__init__("BatchController")
        
        # Core components
        self.batch_queue = BatchQueue()
        self.processor_thread: Optional[BatchProcessorThread] = None
        self._processor_thread_id: Optional[str] = None
        
        # Recovery manager
        self.recovery_manager = BatchRecoveryManager(auto_save_interval=300)  # 5 minutes
        self.recovery_manager.set_batch_queue(self.batch_queue)
        self.recovery_manager.start_monitoring()
        self._recovery_manager_id: Optional[str] = None
        
        # Track recovery manager as a resource
        if self.resources:
            self._recovery_manager_id = self.resources.track_resource(
                self.recovery_manager,
                name="batch_recovery_manager",
                cleanup_handler=lambda rm: rm.stop_monitoring() if rm else None
            )
    
    def _create_resource_coordinator(self, component_id: str) -> WorkerResourceCoordinator:
        """Use WorkerResourceCoordinator for thread management"""
        return WorkerResourceCoordinator(component_id)
    
    def start_batch_processing(self, main_window=None) -> Result[BatchProcessorThread]:
        """
        Start batch processing with pending jobs
        
        Args:
            main_window: Reference to main window for ZIP controller access
            
        Returns:
            Result containing BatchProcessorThread or error
        """
        try:
            # Check for pending jobs
            pending_jobs = self.batch_queue.get_pending_jobs()
            if not pending_jobs:
                error = FileOperationError(
                    "No pending jobs to process",
                    user_message="No jobs in queue to process. Add some jobs first."
                )
                self._handle_error(error, {'method': 'start_batch_processing'})
                return Result.error(error)
            
            # Validate all jobs
            validation = self.batch_queue.validate_all_jobs()
            if validation['invalid_jobs']:
                invalid_count = len(validation['invalid_jobs'])
                self.logger.warning(f"Found {invalid_count} invalid job(s), proceeding with valid jobs")
            
            # Create processor thread
            self.processor_thread = BatchProcessorThread(self.batch_queue, main_window)
            
            # Track with resource coordinator
            if self.resources:
                self._processor_thread_id = self.resources.track_worker(
                    self.processor_thread,
                    name=f"batch_processor_{datetime.now():%H%M%S}"
                )
            
            # Update recovery manager state
            self.recovery_manager.set_processing_active(True)
            
            self._log_operation("batch_processing_started", f"{len(pending_jobs)} jobs")
            
            return Result.success(self.processor_thread)
            
        except Exception as e:
            error = FileOperationError(
                f"Failed to start batch processing: {e}",
                user_message="Failed to start batch processing. Please check the log for details."
            )
            self._handle_error(error, {'method': 'start_batch_processing'})
            return Result.error(error)
    
    def pause_processing(self) -> Result[bool]:
        """Pause/resume batch processing"""
        if not self.processor_thread:
            return Result.error(FileOperationError("No active processing to pause"))
        
        try:
            if self.processor_thread.is_paused():
                self.processor_thread.resume()
                self._log_operation("batch_processing_resumed")
                return Result.success(False)  # False = not paused
            else:
                self.processor_thread.pause()
                self._log_operation("batch_processing_paused")
                return Result.success(True)  # True = paused
        except Exception as e:
            error = FileOperationError(f"Failed to pause/resume processing: {e}")
            self._handle_error(error, {'method': 'pause_processing'})
            return Result.error(error)
    
    def cancel_processing(self) -> Result[None]:
        """Cancel batch processing"""
        if not self.processor_thread:
            return Result.success(None)
        
        try:
            self.processor_thread.cancel()
            self.recovery_manager.set_processing_active(False)
            
            # Clear references - coordinator handles cleanup
            self.processor_thread = None
            self._processor_thread_id = None
            
            self._log_operation("batch_processing_cancelled")
            return Result.success(None)
            
        except Exception as e:
            error = FileOperationError(f"Failed to cancel processing: {e}")
            self._handle_error(error, {'method': 'cancel_processing'})
            return Result.error(error)
    
    def complete_processing(self) -> None:
        """Mark processing as complete and clean up"""
        self.recovery_manager.set_processing_active(False)
        # Clear references - coordinator handles cleanup
        self.processor_thread = None
        self._processor_thread_id = None
        self._log_operation("batch_processing_completed")
    
    def save_queue_to_file(self, file_path: Path) -> Result[None]:
        """Save batch queue to file"""
        try:
            self.batch_queue.save_to_file(file_path)
            self._log_operation("queue_saved", str(file_path))
            return Result.success(None)
        except Exception as e:
            error = FileOperationError(
                f"Failed to save queue: {e}",
                user_message="Failed to save queue. Please check folder permissions and try again."
            )
            self._handle_error(error, {'method': 'save_queue_to_file'})
            return Result.error(error)
    
    def load_queue_from_file(self, file_path: Path) -> Result[int]:
        """
        Load batch queue from file
        
        Returns:
            Result containing number of jobs loaded
        """
        try:
            jobs_loaded = self.batch_queue.load_from_file(file_path)
            self._log_operation("queue_loaded", f"{jobs_loaded} jobs from {file_path}")
            return Result.success(jobs_loaded)
        except Exception as e:
            error = FileOperationError(
                f"Failed to load queue: {e}",
                user_message="Failed to load queue. Please check the file is valid."
            )
            self._handle_error(error, {'method': 'load_queue_from_file'})
            return Result.error(error)
    
    def check_recovery(self) -> Optional[List[Any]]:
        """Check for recoverable jobs"""
        return self.recovery_manager.check_for_recovery()
    
    def recover_jobs(self, jobs: List[Any]) -> Result[int]:
        """Recover jobs from previous session"""
        try:
            recovered_count = self.recovery_manager.recover_jobs(jobs)
            self._log_operation("jobs_recovered", f"{recovered_count} jobs")
            return Result.success(recovered_count)
        except Exception as e:
            error = FileOperationError(f"Failed to recover jobs: {e}")
            self._handle_error(error, {'method': 'recover_jobs'})
            return Result.error(error)
    
    def get_queue(self) -> BatchQueue:
        """Get the batch queue instance"""
        return self.batch_queue
    
    def get_recovery_manager(self) -> BatchRecoveryManager:
        """Get the recovery manager instance"""
        return self.recovery_manager
    
    def is_processing_active(self) -> bool:
        """Check if processing is currently active"""
        return self.processor_thread is not None and self.processor_thread.isRunning()
    
    def cleanup(self) -> None:
        """Clean up all resources"""
        # Save queue state if there are pending jobs
        if self.batch_queue and self.batch_queue.jobs:
            self.recovery_manager._auto_save_state()
            self.logger.info(f"Saved batch queue state with {len(self.batch_queue.jobs)} jobs")
        
        # Cancel any active processing
        if self.is_processing_active():
            self.cancel_processing()
        
        # Stop recovery manager monitoring
        if self.recovery_manager:
            self.recovery_manager.stop_monitoring()
        
        # Let resource coordinator handle cleanup
        if self.resources:
            self.resources.cleanup_all()
        
        # Clear references
        self.processor_thread = None
        self._processor_thread_id = None
        self.recovery_manager = None
        self._recovery_manager_id = None