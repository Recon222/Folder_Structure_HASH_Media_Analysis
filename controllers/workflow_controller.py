#!/usr/bin/env python3
"""
Workflow controller - orchestrates complete processing workflows
"""
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base_controller import BaseController
from core.resource_coordinators import WorkerResourceCoordinator
from core.models import FormData
from core.services.interfaces import IPathService, IFileOperationService, IValidationService, ISuccessMessageService
from core.workers import FolderStructureThread
from core.result_types import Result, FileOperationResult, ArchiveOperationResult
from core.exceptions import FileOperationError
from core.services.success_message_data import SuccessMessageData

class WorkflowController(BaseController):
    """Orchestrates complete file processing workflows"""
    
    def __init__(self):
        super().__init__("WorkflowController")
        self.current_operation: Optional[FolderStructureThread] = None
        self._current_operation_id: Optional[str] = None
        
        # Service dependencies (injected)
        self._path_service = None
        self._file_service = None  
        self._validation_service = None
        self._success_message_service = None
        
        # Result storage for success message integration
        self._last_file_result = None
        self._last_report_results = None
        self._last_zip_result = None
    
    def _create_resource_coordinator(self, component_id: str) -> WorkerResourceCoordinator:
        """Use WorkerResourceCoordinator for thread management"""
        return WorkerResourceCoordinator(component_id)
    
    @property
    def path_service(self) -> IPathService:
        """Lazy load path service"""
        if self._path_service is None:
            self._path_service = self._get_service(IPathService)
        return self._path_service
    
    @property
    def file_service(self) -> IFileOperationService:
        """Lazy load file operation service"""
        if self._file_service is None:
            self._file_service = self._get_service(IFileOperationService)
        return self._file_service
    
    @property
    def validation_service(self) -> IValidationService:
        """Lazy load validation service"""
        if self._validation_service is None:
            self._validation_service = self._get_service(IValidationService)
        return self._validation_service
    
    @property
    def success_message_service(self) -> ISuccessMessageService:
        """Lazy load success message service"""
        if self._success_message_service is None:
            self._success_message_service = self._get_service(ISuccessMessageService)
        return self._success_message_service
    
    def process_forensic_workflow(
        self,
        form_data: FormData,
        files: List[Path],
        folders: List[Path],
        output_directory: Path,
        calculate_hash: bool = True,
        performance_monitor = None
    ) -> Result[FolderStructureThread]:
        """
        Process complete forensic workflow
        
        This method orchestrates the entire forensic processing workflow:
        1. Validates form data and file paths
        2. Builds forensic folder structure
        3. Creates worker thread for file processing
        
        Returns:
            Result containing FolderStructureThread or error
        """
        try:
            self._log_operation("process_forensic_workflow", 
                              f"files: {len(files)}, folders: {len(folders)}")
            
            # Step 1: Validate form data
            validation_result = self.validation_service.validate_form_data(form_data)
            if not validation_result.success:
                return Result.error(validation_result.error)
            
            # Step 2: Validate file paths
            all_paths = files + folders
            if all_paths:  # Only validate if paths provided
                path_validation_result = self.validation_service.validate_file_paths(all_paths)
                if not path_validation_result.success:
                    return Result.error(path_validation_result.error)
            else:
                error = FileOperationError(
                    "No files or folders provided for processing",
                    user_message="Please select files or folders to process."
                )
                self._handle_error(error, {'method': 'process_forensic_workflow'})
                return Result.error(error)
            
            # Step 3: Build forensic structure
            path_result = self.path_service.build_forensic_path(form_data, output_directory)
            if not path_result.success:
                return Result.error(path_result.error)
            
            forensic_path = path_result.value
            
            # Step 4: Prepare items for processing
            all_items = self._prepare_workflow_items(files, folders)
            
            # Step 5: Create worker thread
            thread = FolderStructureThread(
                all_items, 
                forensic_path, 
                calculate_hash, 
                performance_monitor
            )
            
            self.current_operation = thread
            
            # Track worker with resource coordinator
            if self.resources:
                self._current_operation_id = self.resources.track_worker(
                    thread,
                    name=f"forensic_workflow_{datetime.now():%H%M%S}"
                )
            
            self._log_operation("workflow_thread_created", f"destination: {forensic_path}")
            
            return Result.success(thread)
            
        except Exception as e:
            error = FileOperationError(
                f"Workflow orchestration failed: {e}",
                user_message="Failed to start processing workflow. Please check your inputs."
            )
            self._handle_error(error, {'method': 'process_forensic_workflow'})
            return Result.error(error)
    
    def _prepare_workflow_items(
        self, 
        files: List[Path], 
        folders: List[Path]
    ) -> List[tuple]:
        """Prepare items for workflow processing"""
        all_items = []
        
        # Add individual files
        for file in files:
            all_items.append(('file', file, file.name))
            
        # Add folders with their complete structure
        for folder in folders:
            all_items.append(('folder', folder, None))
            
        return all_items
    
    def process_batch_workflow(
        self,
        batch_jobs: List['BatchJob'],
        base_output_directory: Path,
        calculate_hash: bool = True
    ) -> Result[List[Dict]]:
        """
        Process batch workflow - unified system for both forensic and batch
        
        This method processes multiple jobs using the same forensic workflow.
        Both forensic tab and batch tab use the same underlying system.
        
        Args:
            batch_jobs: List of BatchJob instances to process
            base_output_directory: Base output directory
            calculate_hash: Whether to calculate hashes
            
        Returns:
            Result containing list of job results
        """
        try:
            self._log_operation("process_batch_workflow", f"{len(batch_jobs)} jobs")
            
            batch_results = []
            
            for job in batch_jobs:
                # Each batch job uses the same forensic workflow
                job_result = self.process_forensic_workflow(
                    form_data=job.form_data,
                    files=job.files,
                    folders=job.folders,
                    output_directory=base_output_directory,
                    calculate_hash=calculate_hash
                )
                
                batch_results.append({
                    'job_id': job.id,
                    'success': job_result.success,
                    'error': job_result.error if not job_result.success else None,
                    'thread': job_result.value if job_result.success else None
                })
                
                # Early exit on critical failures if desired
                if not job_result.success and hasattr(job_result.error, 'severity'):
                    from core.exceptions import ErrorSeverity
                    if job_result.error.severity == ErrorSeverity.CRITICAL:
                        self._log_operation("batch_workflow_critical_failure", job.id, "error")
                        break
            
            self._log_operation("batch_workflow_completed", f"{len(batch_results)} jobs processed")
            return Result.success(batch_results)
            
        except Exception as e:
            error = FileOperationError(
                f"Batch workflow failed: {e}",
                user_message="Batch processing failed. Please check individual job configurations."
            )
            self._handle_error(error, {'method': 'process_batch_workflow'})
            return Result.error(error)
    
    def cancel_current_workflow(self) -> bool:
        """Cancel the current workflow if running"""
        if self.current_operation and self.current_operation.isRunning():
            self._log_operation("cancel_workflow_requested")
            self.current_operation.cancel()
            # Clear references - coordinator handles cleanup
            self.current_operation = None
            self._current_operation_id = None
            return True
        # Clear references even if not running
        self.current_operation = None
        self._current_operation_id = None
        return False
    
    def get_current_workflow_status(self) -> Dict[str, Any]:
        """Get current workflow status information"""
        if not self.current_operation:
            return {"status": "idle", "operation": None}
        
        return {
            "status": "running" if self.current_operation.isRunning() else "completed",
            "operation": self.current_operation.__class__.__name__,
            "can_cancel": self.current_operation.isRunning()
        }
    
    # ✅ SUCCESS MESSAGE INTEGRATION METHODS
    
    def store_operation_results(
        self,
        file_result: Optional[FileOperationResult] = None,
        report_results: Optional[Dict] = None,
        zip_result: Optional[ArchiveOperationResult] = None
    ):
        """Store operation results for success message building"""
        if file_result is not None:
            self._last_file_result = file_result
        if report_results is not None:
            self._last_report_results = report_results
        if zip_result is not None:
            self._last_zip_result = zip_result
    
    def build_success_message(
        self,
        file_result: Optional[FileOperationResult] = None,
        report_results: Optional[Dict] = None,
        zip_result: Optional[ArchiveOperationResult] = None
    ) -> SuccessMessageData:
        """
        Build success message for completed workflow using service layer
        
        Uses stored results if parameters not provided, enabling flexible usage
        from UI components that may call this at different times.
        """
        # Use provided results or fall back to stored results
        file_result = file_result or self._last_file_result
        report_results = report_results or self._last_report_results
        zip_result = zip_result or self._last_zip_result
        
        # DEBUG: Log what we're passing to the service
        self.logger.debug(f"DEBUG WorkflowController: file_result type = {type(file_result)}")
        self.logger.debug(f"DEBUG WorkflowController: report_results type = {type(report_results)}")
        self.logger.debug(f"DEBUG WorkflowController: zip_result type = {type(zip_result)}")
        if file_result:
            self.logger.debug(f"DEBUG WorkflowController: file_result has files_processed? {hasattr(file_result, 'files_processed')}")
        
        return self.success_message_service.build_forensic_success_message(
            file_result, report_results, zip_result
        )
    
    def clear_stored_results(self):
        """Clear stored results to prevent memory leaks"""
        self._last_file_result = None
        self._last_report_results = None
        self._last_zip_result = None
        self._log_operation("results_cleared", "Stored operation results cleared")
    
    def cleanup_operation_resources(
        self,
        file_thread=None,
        zip_thread=None,
        operation_results=None,
        performance_data=None
    ) -> Result[None]:
        """
        Clean up all operation resources and memory
        
        This method encapsulates the memory cleanup logic previously in MainWindow.
        It handles thread cleanup, result clearing, and garbage collection.
        
        Args:
            file_thread: File operation thread to clean up
            zip_thread: ZIP operation thread to clean up
            operation_results: Dictionary of operation results to clear
            performance_data: Performance data to clear
            
        Returns:
            Result indicating success or failure
        """
        try:
            self._log_operation("cleanup_operation_resources", "Starting comprehensive cleanup")
            
            # Clean up thread references and disconnect signals
            if file_thread:
                try:
                    # Disconnect all signals to break Qt reference cycles
                    if hasattr(file_thread, 'progress_update'):
                        file_thread.progress_update.disconnect()
                    if hasattr(file_thread, 'result_ready'):
                        file_thread.result_ready.disconnect()
                    
                    # Wait for thread to finish if still running
                    if file_thread.isRunning():
                        file_thread.wait(1000)  # Wait up to 1 second
                        
                    self._log_operation("file_thread_cleaned", "File thread cleaned up")
                except Exception as e:
                    self._log_operation("file_thread_cleanup_error", str(e), "warning")
            
            if zip_thread:
                try:
                    if hasattr(zip_thread, 'progress_update'):
                        zip_thread.progress_update.disconnect()
                    if hasattr(zip_thread, 'result_ready'):
                        zip_thread.result_ready.disconnect()
                        
                    if zip_thread.isRunning():
                        zip_thread.wait(1000)
                        
                    self._log_operation("zip_thread_cleaned", "ZIP thread cleaned up")
                except Exception as e:
                    self._log_operation("zip_thread_cleanup_error", str(e), "warning")
            
            # Clear stored results in controller
            self.clear_stored_results()
            
            # Clear current operation reference
            if self.current_operation:
                self.current_operation = None
                self._log_operation("current_operation_cleared", "Current operation reference cleared")
            
            # Force garbage collection to clean up any remaining cycles
            import gc
            gc.collect()
            
            self._log_operation("cleanup_complete", "Memory cleanup completed - optimized for next operation")
            return Result.success(None)
            
        except Exception as e:
            error = FileOperationError(
                f"Failed to clean up operation resources: {e}",
                user_message="Warning: Some resources may not have been cleaned up properly."
            )
            self._handle_error(error, {'method': 'cleanup_operation_resources'})
            return Result.error(error)
    
    def cleanup(self) -> None:
        """Clean up all resources"""
        # Cancel any running operation
        if self.current_operation and self.current_operation.isRunning():
            self.cancel_current_workflow()
        
        # Let resource coordinator handle cleanup
        if self.resources:
            self.resources.cleanup_all()
        
        # Clear references
        self.current_operation = None
        self._current_operation_id = None