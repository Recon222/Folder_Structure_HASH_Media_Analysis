#!/usr/bin/env python3
"""
Forensic Controller - Orchestrates forensic file processing operations
Extracted from MainWindow to follow SOA architecture
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog

from .base_controller import BaseController
from .workflow_controller import WorkflowController
from .report_controller import ReportController
from .zip_controller import ZipController
from core.resource_coordinators import WorkerResourceCoordinator
from core.models import FormData
from core.result_types import Result, FileOperationResult, ReportGenerationResult, ArchiveOperationResult
from core.exceptions import UIError, FileOperationError, ErrorSeverity
from core.error_handler import handle_error
from core.logger import logger
from core.settings_manager import settings
from ui.dialogs.zip_prompt import ZipPromptDialog
from ui.dialogs.success_dialog import SuccessDialog


class ForensicOperationState:
    """
    State container for multi-phase forensic operations
    Ensures state persistence across report → ZIP flow
    
    Phase Flow:
    files -> files_complete -> reports -> zip -> zip_complete -> complete
                           \-> complete (if no reports/zip)
                 \-> complete (on error)
    """
    
    def __init__(self):
        self.form_data = None
        self.file_result = None
        self.report_results = {}
        self.zip_result = None
        self.output_directory = None
        self.files = []
        self.folders = []
        self.start_time = None
        self.end_time = None
        self.phase_times = {
            'files': None,
            'reports': None,
            'zip': None
        }
        
    def clear(self):
        """Reset state for next operation"""
        self.__init__()
    
    def is_complete(self) -> bool:
        """Check if operation is fully complete"""
        return self.file_result is not None
    
    def record_phase_time(self, phase: str):
        """Record completion time for a phase"""
        if phase in self.phase_times:
            self.phase_times[phase] = datetime.now()


class ForensicController(BaseController):
    """
    Controller for forensic file processing operations
    Manages the complete forensic workflow from file selection to completion
    """
    
    def __init__(self, parent_widget=None):
        """
        Initialize forensic controller
        
        Args:
            parent_widget: Parent widget for dialogs (MainWindow or ForensicTab)
        """
        super().__init__("ForensicController")
        
        self.parent_widget = parent_widget
        
        # Controllers
        self.workflow_controller = WorkflowController()
        self.report_controller = ReportController()
        self.zip_controller = None  # Will be injected
        
        # Operation state - ENHANCED
        self.file_thread = None
        self.zip_thread = None
        self._file_thread_id = None
        self._zip_thread_id = None
        self.operation_active = False
        self.current_phase = None  # Track: 'files', 'reports', 'zip', 'complete', 'cancelled'
        
        # State management
        self.operation_state = ForensicOperationState()
        
        # Legacy format storage for compatibility
        self.file_operation_results = {}
        self.output_directory = None
        self.last_output_directory = None
        
        self._log_operation("initialized", "ForensicController ready")
    
    def _create_resource_coordinator(self, component_id: str) -> WorkerResourceCoordinator:
        """Use WorkerResourceCoordinator for managing file and zip threads"""
        return WorkerResourceCoordinator(component_id)
    
    def set_zip_controller(self, zip_controller: ZipController):
        """Inject ZIP controller dependency"""
        self.zip_controller = zip_controller
        self.report_controller.zip_controller = zip_controller
        self._log_operation("zip_controller_set", "ZIP controller injected")
    
    def process_forensic_files(
        self,
        form_data: FormData,
        files: List[Path],
        folders: List[Path],
        calculate_hash: bool = None,
        performance_monitor: Any = None
    ) -> Result[Any]:
        """
        Process files using forensic folder structure
        
        This is the main entry point for forensic processing, orchestrating:
        1. Validation
        2. Output directory selection
        3. ZIP prompt handling
        4. Workflow execution
        
        Returns:
            Result containing the started thread or error
        """
        try:
            self._log_operation("phase_transition", f"None -> validation")
            
            # Clear previous operation state
            self.operation_state.clear()
            self.operation_state.form_data = form_data
            self.operation_state.files = files
            self.operation_state.folders = folders
            self.operation_state.start_time = datetime.now()
            
            # Validate form
            errors = form_data.validate()
            if errors:
                error = UIError(
                    f"Form validation failed: {', '.join(errors)}", 
                    user_message=f"Please correct the following errors:\n\n• " + "\n• ".join(errors),
                    component="ForensicController"
                )
                handle_error(error, {'operation': 'form_validation', 'field_count': len(errors)})
                return Result.error(error)
            
            # Validate file selection
            if not files and not folders:
                error = UIError(
                    "No files selected for processing",
                    user_message="Please select files or folders to process before starting the operation.",
                    component="ForensicController"
                )
                handle_error(error, {'operation': 'file_selection_validation'})
                return Result.error(error)
            
            # Handle ZIP prompt if needed
            if self.zip_controller and self.zip_controller.should_prompt_user():
                choice = ZipPromptDialog.prompt_user(self.parent_widget)
                self.zip_controller.set_session_choice(
                    choice['create_zip'], 
                    choice['remember_for_session']
                )
            
            # Ask user for output directory
            output_dir = QFileDialog.getExistingDirectory(
                self.parent_widget, 
                "Select Output Location", 
                str(self.last_output_directory) if self.last_output_directory else "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            
            if not output_dir:
                return Result.error(UIError("Operation cancelled by user"))
            
            # Store output directory
            self.output_directory = Path(output_dir)
            self.last_output_directory = self.output_directory
            self.operation_state.output_directory = self.output_directory
            
            # Get hash preference
            if calculate_hash is None:
                calculate_hash = settings.calculate_hashes
            
            self._log_operation("phase_transition", "validation -> files")
            self.current_phase = 'files'
            
            # Start workflow
            workflow_result = self.workflow_controller.process_forensic_workflow(
                form_data=form_data,
                files=files,
                folders=folders,
                output_directory=self.output_directory,
                calculate_hash=calculate_hash,
                performance_monitor=performance_monitor
            )
            
            if not workflow_result.success:
                error = UIError(
                    f"Workflow setup failed: {workflow_result.error.message}",
                    user_message=workflow_result.error.user_message,
                    component="ForensicController"
                )
                handle_error(error, {'operation': 'workflow_setup'})
                return Result.error(error)
            
            # Store thread reference
            self.file_thread = workflow_result.value
            self.operation_active = True
            
            # Track file thread with resource coordinator
            if self.resources and self.file_thread:
                self._file_thread_id = self.resources.track_worker(
                    self.file_thread,
                    name=f"file_thread_{datetime.now():%H%M%S}"
                )
            
            self._log_operation("forensic_processing_started", 
                              f"Files: {len(files)}, Folders: {len(folders)}")
            
            return Result.success(self.file_thread)
            
        except Exception as e:
            error = FileOperationError(
                f"Forensic processing failed: {e}",
                user_message="Failed to start forensic processing. Please try again."
            )
            self._handle_error(error, {'method': 'process_forensic_files'})
            return Result.error(error)
    
    def on_operation_finished(self, result: Result) -> None:
        """
        Handle operation completion - manages everything internally
        
        Args:
            result: Operation result from worker thread
        """
        try:
            self.operation_active = False
            self._log_operation("phase_transition", f"{self.current_phase} -> files_complete")
            self.current_phase = 'files_complete'
            self.operation_state.record_phase_time('files')
            
            if result.success:
                # Store the result directly - it IS the FileOperationResult
                # FileOperationResult inherits from Result, so the result itself is what we need
                if result and isinstance(result, FileOperationResult):
                    self.operation_state.file_result = result
                    self._log_operation("file_result_stored", f"Stored {type(result).__name__} directly")
                elif result and result.value and isinstance(result.value, FileOperationResult):
                    # Fallback: if somehow wrapped, extract it
                    self.operation_state.file_result = result.value
                    self._log_operation("file_result_stored", f"Extracted FileOperationResult from wrapper")
                else:
                    self.operation_state.file_result = None
                    self._log_operation("file_result_error", f"Invalid result type: {type(result).__name__}", "error")
                
                # Validate we got the right type
                if self.operation_state.file_result and not isinstance(self.operation_state.file_result, FileOperationResult):
                    self._log_operation("type_validation_warning", 
                                      f"Expected FileOperationResult, got {type(self.operation_state.file_result).__name__}", 
                                      "warning")
                    # Try to extract if it's still wrapped somehow
                    if hasattr(self.operation_state.file_result, 'value'):
                        self._log_operation("unwrapping_attempt", "Attempting to unwrap nested Result object", "warning")
                        self.operation_state.file_result = self.operation_state.file_result.value
                
                # Convert for legacy report generation
                if isinstance(self.operation_state.file_result, FileOperationResult):
                    # Extract dest_path from metadata or value dict
                    dest_path = None
                    if self.operation_state.file_result.metadata and 'base_forensic_path' in self.operation_state.file_result.metadata:
                        dest_path = self.operation_state.file_result.metadata['base_forensic_path']
                    elif self.operation_state.file_result.value and isinstance(self.operation_state.file_result.value, dict):
                        op_data = self.operation_state.file_result.value.get('operation', {})
                        dest_path = op_data.get('dest_path', str(self.operation_state.output_directory))
                    else:
                        dest_path = str(self.operation_state.output_directory)
                    
                    self.file_operation_results = {
                        'operation': {
                            'dest_path': str(dest_path),
                            'files_processed': self.operation_state.file_result.files_processed,
                            'bytes_processed': self.operation_state.file_result.bytes_processed
                        }
                    }
                
                # Store in workflow controller
                self.workflow_controller.store_operation_results(
                    file_result=self.operation_state.file_result
                )
                
                self._log_operation("operation_completed", "File operation successful")
                
                # Progress through phases
                if self._should_generate_reports():
                    self._log_operation("phase_transition", "files_complete -> reports")
                    self.current_phase = 'reports'
                    self._generate_reports_phase()
                elif self._should_create_zip():
                    self._log_operation("phase_transition", "files_complete -> zip")
                    self.current_phase = 'zip'
                    self._create_zip_phase()
                else:
                    self._log_operation("phase_transition", "files_complete -> complete")
                    self.current_phase = 'complete'
                    self._complete_operation()
            else:
                self._handle_operation_failure(result)
                
        except Exception as e:
            self._log_operation("operation_handling_error", str(e), "error")
            self._complete_operation()
    
    def _generate_reports_phase(self):
        """Generate reports and continue flow"""
        try:
            # Generate reports synchronously (they're fast)
            if not self.operation_state.file_result:
                self._log_operation("report_generation_skipped", "No file operation result", "warning")
                self._check_next_phase()
                return
            
            base_path = self._determine_base_path()
            if not base_path:
                self._log_operation("report_generation_failed", "Cannot determine output path", "error")
                self._check_next_phase()
                return
            
            # Get form_data from stored state
            form_data = self.operation_state.form_data or FormData()
            
            # Generate reports using the correct method
            report_result = self.report_controller.generate_reports_with_path_determination(
                form_data=form_data,
                file_operation_result=self.operation_state.file_result,
                output_directory=self.output_directory,
                settings=settings
            )
            
            if report_result.success:
                # Extract results from the successful report generation
                report_data = report_result.value
                generated = report_data.get('reports', {})
                
                # Store results
                self.operation_state.report_results = generated
                self.workflow_controller.store_operation_results(report_results=generated)
                
                self._log_operation("reports_generated", f"{len(generated)} reports created")
            else:
                self._log_operation("report_generation_failed", str(report_result.error), "error")
            
            self.operation_state.record_phase_time('reports')
            
            # Continue flow
            self._check_next_phase()
            
        except Exception as e:
            self._log_operation("report_generation_error", str(e), "error")
            self._check_next_phase()
    
    def _create_zip_phase(self):
        """Create ZIP internally without returning thread"""
        try:
            if not self.zip_controller:
                self._log_operation("zip_skipped", "No ZIP controller available", "warning")
                self._complete_operation()
                return
            
            # Determine base path from file result
            base_path = self._determine_base_path()
            if not base_path:
                self._log_operation("zip_skipped", "Cannot determine base path", "warning")
                self._complete_operation()
                return
            
            # Find occurrence folder
            occurrence_result = self.workflow_controller.path_service.find_occurrence_folder(
                base_path,
                self.operation_state.output_directory
            )
            
            if not occurrence_result.success:
                self._log_operation("zip_folder_not_found", str(occurrence_result.error), "warning")
                self._complete_operation()
                return
            
            # Create ZIP thread
            self.zip_thread = self.zip_controller.create_zip_thread(
                occurrence_result.value,
                self.operation_state.output_directory,
                self.operation_state.form_data
            )
            
            # Track zip thread with resource coordinator
            if self.resources and self.zip_thread:
                self._zip_thread_id = self.resources.track_worker(
                    self.zip_thread,
                    name=f"zip_thread_{datetime.now():%H%M%S}"
                )
            
            # Connect signals INTERNALLY
            self.zip_thread.progress_update.connect(self._on_zip_progress)
            self.zip_thread.result_ready.connect(self._on_zip_finished_internal)
            
            # Start thread INTERNALLY
            self.zip_thread.start()
            
            # Notify UI if needed
            if self.parent_widget and hasattr(self.parent_widget, 'log'):
                self.parent_widget.log("Creating ZIP archives...")
                
        except Exception as e:
            self._log_operation("zip_creation_failed", str(e), "error")
            self._complete_operation()
    
    def _on_zip_progress(self, percentage: int, message: str):
        """Handle ZIP progress internally"""
        # Forward to parent if it has progress handling
        if self.parent_widget and hasattr(self.parent_widget, '_on_progress_update'):
            self.parent_widget._on_progress_update(percentage, message)
    
    def _on_zip_finished_internal(self, result: Result):
        """Handle ZIP completion internally"""
        self._log_operation("phase_transition", f"{self.current_phase} -> zip_complete")
        self.current_phase = 'zip_complete'
        self.operation_state.zip_result = result
        self.operation_state.record_phase_time('zip')
        
        if result.success:
            self.workflow_controller.store_operation_results(zip_result=result)
            self._log_operation("zip_completed", "Archives created successfully")
        else:
            self._log_operation("zip_failed", str(result.error), "warning")
        
        self._complete_operation()
    
    def _check_next_phase(self):
        """Determine and execute next phase"""
        if self.current_phase == 'reports' and self._should_create_zip():
            self._log_operation("phase_transition", "reports -> zip")
            self.current_phase = 'zip'
            self._create_zip_phase()
        else:
            self._log_operation("phase_transition", f"{self.current_phase} -> complete")
            self.current_phase = 'complete'
            self._complete_operation()
    
    def _complete_operation(self):
        """Complete the operation and show success"""
        try:
            self.operation_state.end_time = datetime.now()
            
            # Build and show success message
            success_data = self.workflow_controller.build_success_message()
            
            if self.parent_widget:
                SuccessDialog.show_success_message(success_data, self.parent_widget)
            
            # Notify UI of completion
            if self.parent_widget and hasattr(self.parent_widget, 'set_processing_state'):
                self.parent_widget.set_processing_state(False)
            
            # Log operation summary
            if self.operation_state.start_time and self.operation_state.end_time:
                duration = self.operation_state.end_time - self.operation_state.start_time
                self._log_operation("operation_complete", f"Total duration: {duration}")
            
            # Cleanup
            self.cleanup_operation_memory()
            
        except Exception as e:
            self._log_operation("completion_failed", str(e), "warning")
            # Still cleanup
            self.cleanup_operation_memory()
            # Ensure UI is reset
            if self.parent_widget and hasattr(self.parent_widget, 'set_processing_state'):
                self.parent_widget.set_processing_state(False)
    
    def _determine_base_path(self) -> Optional[Path]:
        """Determine base path for reports/ZIP"""
        if not self.operation_state.file_result:
            self._log_operation("base_path_fallback", "No file result, using output directory", "warning")
            return self.operation_state.output_directory
        
        file_result = self.operation_state.file_result
        
        # FileOperationResult has metadata that might contain base_forensic_path
        if isinstance(file_result, FileOperationResult):
            # First check metadata for base_forensic_path
            if file_result.metadata and 'base_forensic_path' in file_result.metadata:
                path = Path(file_result.metadata['base_forensic_path'])
                self._log_operation("base_path_found", f"Using base_forensic_path from metadata: {path}")
                return path
            
            # Check if there's a dest_path in the value dict
            if file_result.value and isinstance(file_result.value, dict):
                op_data = file_result.value.get('operation', {})
                if 'dest_path' in op_data:
                    path = Path(op_data['dest_path']).parent
                    self._log_operation("base_path_found", f"Using dest_path from operation data: {path}")
                    return path
        
        # Final fallback
        self._log_operation("base_path_final_fallback", f"Using output_directory fallback: {self.operation_state.output_directory}")
        return self.operation_state.output_directory
    
    def _handle_operation_failure(self, result: Result):
        """Handle operation failure"""
        message = result.error.user_message if result.error else "Operation failed"
        error = UIError(
            f"Operation failed: {message}",
            user_message=f"The operation could not be completed:\n\n{message}",
            component="ForensicController"
        )
        handle_error(error, {'operation': 'forensic_file_processing'})
        
        self._log_operation("phase_transition", f"{self.current_phase} -> failed")
        self.current_phase = 'failed'
        
        # Ensure UI is reset
        if self.parent_widget and hasattr(self.parent_widget, 'set_processing_state'):
            self.parent_widget.set_processing_state(False)
    
    def cleanup_operation_memory(self) -> Result[None]:
        """Clean up operation resources and memory"""
        try:
            # Delegate to workflow controller
            cleanup_result = self.workflow_controller.cleanup_operation_resources(
                file_thread=self.file_thread,
                zip_thread=self.zip_thread,
                operation_results=self.file_operation_results,
                performance_data=None
            )
            
            # Clear local references - coordinator handles cleanup
            self.file_thread = None
            self.zip_thread = None
            self._file_thread_id = None
            self._zip_thread_id = None
            self.file_operation_results = {}
            
            # Clear operation state
            self.operation_state.clear()
            
            # Clear workflow controller stored results
            self.workflow_controller.clear_stored_results()
            
            self._log_operation("memory_cleanup_completed", "Resources released")
            
            return cleanup_result
            
        except Exception as e:
            self._log_operation("cleanup_failed", str(e), "warning")
            return Result.success(None)  # Don't fail on cleanup
    
    def _should_generate_reports(self) -> bool:
        """Check if reports should be generated"""
        return (settings.generate_time_offset_pdf or 
                settings.generate_upload_log_pdf or 
                settings.calculate_hashes)
    
    def _should_create_zip(self) -> bool:
        """Check if ZIP should be created"""
        return self.zip_controller and self.zip_controller.should_create_zip()
    
    def cancel_operation(self) -> bool:
        """Cancel current operation if running"""
        cancelled = False
        
        self._log_operation("phase_transition", f"{self.current_phase} -> cancelled")
        self.current_phase = 'cancelled'
        
        if self.file_thread and self.file_thread.isRunning():
            self.file_thread.cancel()
            cancelled = True
            
        if self.zip_thread and self.zip_thread.isRunning():
            self.zip_thread.cancel()
            cancelled = True
        
        # Clear references - coordinator handles cleanup
        if cancelled:
            self.file_thread = None
            self.zip_thread = None
            self._file_thread_id = None
            self._zip_thread_id = None
            
        if cancelled:
            self._log_operation("operation_cancelled", "User cancelled operation")
            # Clear state
            self.operation_state.clear()
            
        return cancelled
    
    def cleanup(self) -> None:
        """Clean up all resources"""
        # Cancel any running operations
        self.cancel_operation()
        
        # Clean up operation memory
        self.cleanup_operation_memory()
        
        # Let resource coordinator handle cleanup
        if self.resources:
            self.resources.cleanup_all()
        
        # Clear all references
        self.file_thread = None
        self.zip_thread = None
        self._file_thread_id = None
        self._zip_thread_id = None