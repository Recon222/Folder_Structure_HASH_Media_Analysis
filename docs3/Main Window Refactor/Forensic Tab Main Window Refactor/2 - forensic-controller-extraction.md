# ForensicController Extraction - Complete Implementation Guide

## Overview

This document provides a **complete rip-and-replace implementation** for extracting ForensicController from MainWindow. No backward compatibility needed - we're doing a clean extraction.

**Total Estimated Time:** 4-6 hours  
**Risk Level:** Medium (core functionality refactor)  
**Rollback Strategy:** Git revert at any checkpoint

---

## Pre-Flight Checklist

### Before Starting
```bash
# 1. Ensure clean git state
git status  # Should show no changes
git checkout -b refactor/extract-forensic-controller

# 2. Run existing tests to establish baseline
.venv/Scripts/python.exe main.py
# Test forensic tab functionality:
# - Add form data
# - Select files
# - Click Process Files
# - Verify it works

# 3. Create a test job for verification
# Prepare:
# - Sample files in a test folder
# - Known form data values to use
# - Expected output structure
```

### Success Criteria
✅ Forensic tab processes files correctly  
✅ Progress bar updates during processing  
✅ Reports generate successfully  
✅ ZIP archives create when enabled  
✅ Success dialog shows with correct information  
✅ Batch processing still works (uses same workflow)  
✅ No business logic remains in MainWindow  

---

## Phase 1: Create ForensicController [30 minutes]

### Step 1.1: Create the Controller File

**File:** `controllers/forensic_controller.py`

```python
#!/usr/bin/env python3
"""
Forensic Controller - Orchestrates forensic file processing operations
Extracted from MainWindow to follow SOA architecture
"""

from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog

from .base_controller import BaseController
from .workflow_controller import WorkflowController
from .report_controller import ReportController
from .zip_controller import ZipController
from core.models import FormData
from core.result_types import Result, FileOperationResult, ReportGenerationResult, ArchiveOperationResult
from core.exceptions import UIError, FileOperationError, ErrorSeverity
from core.error_handler import handle_error
from core.logger import logger
from core.settings_manager import settings
from ui.dialogs.zip_prompt import ZipPromptDialog
from ui.dialogs.success_dialog import SuccessDialog


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
        
        # Operation state
        self.file_thread = None
        self.zip_thread = None
        self.operation_active = False
        
        # Results storage
        self.file_operation_result = None
        self.file_operation_results = {}  # Legacy format for reports
        self.reports_generated = None
        self.zip_operation_result = None
        self.output_directory = None
        self.last_output_directory = None
        
        self._log_operation("initialized", "ForensicController ready")
    
    def set_zip_controller(self, zip_controller: ZipController):
        """Inject ZIP controller dependency"""
        self.zip_controller = zip_controller
        self.report_controller.zip_controller = zip_controller
    
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
            
            # Get hash preference
            if calculate_hash is None:
                calculate_hash = settings.calculate_hashes
            
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
    
    def on_operation_finished(self, result: Result) -> Result[None]:
        """
        Handle operation completion
        
        Args:
            result: Operation result from worker thread
            
        Returns:
            Result indicating completion handling success
        """
        try:
            self.operation_active = False
            
            if result.success:
                # Store results
                self.file_operation_result = result.value if hasattr(result, 'value') else result
                
                # Convert to legacy format for report generation
                if isinstance(self.file_operation_result, FileOperationResult):
                    self.file_operation_results = {
                        'operation': {
                            'dest_path': str(self.file_operation_result.dest_path),
                            'files_processed': self.file_operation_result.files_processed,
                            'bytes_processed': self.file_operation_result.bytes_processed
                        }
                    }
                
                # Store in workflow controller for success message
                self.workflow_controller.store_operation_results(
                    file_result=self.file_operation_result
                )
                
                self._log_operation("operation_completed", "File operation successful")
                
                # Check if reports should be generated
                if self._should_generate_reports():
                    return self.generate_reports()
                elif self._should_create_zip():
                    return self._create_zip_archives()
                else:
                    return self._show_completion()
                    
            else:
                # Handle failure
                message = result.error.user_message if result.error else "Operation failed"
                error = UIError(
                    f"Operation failed: {message}",
                    user_message=f"The operation could not be completed:\n\n{message}",
                    component="ForensicController"
                )
                handle_error(error, {'operation': 'forensic_file_processing'})
                return Result.error(error)
                
        except Exception as e:
            error = FileOperationError(
                f"Failed to handle operation completion: {e}",
                user_message="Error processing operation results."
            )
            self._handle_error(error, {'method': 'on_operation_finished'})
            return Result.error(error)
    
    def generate_reports(self) -> Result[None]:
        """Generate reports based on settings"""
        try:
            if not self.file_operation_result:
                self._log_operation("report_generation_skipped", "No file operation result", "warning")
                return self._check_next_step()
            
            # Determine base path
            base_forensic_path = None
            if hasattr(self.file_operation_result, 'dest_path'):
                base_forensic_path = Path(self.file_operation_result.dest_path)
            elif hasattr(self.file_operation_result, 'output_directory'):
                base_forensic_path = Path(self.file_operation_result.output_directory)
            
            if not base_forensic_path:
                self._log_operation("report_generation_failed", "Cannot determine output path", "error")
                return self._check_next_step()
            
            # Generate reports
            report_results = self.report_controller.generate_all_reports(
                form_data=self.workflow_controller.current_operation.form_data 
                    if hasattr(self.workflow_controller, 'current_operation') else FormData(),
                file_results=self.file_operation_results,
                output_dir=base_forensic_path / "Reports",
                generate_time_offset=settings.generate_time_offset_pdf,
                generate_upload_log=settings.generate_upload_log_pdf,
                generate_hash_csv=settings.calculate_hashes
            )
            
            # Store results
            self.reports_generated = report_results
            self.workflow_controller.store_operation_results(
                report_results=report_results
            )
            
            self._log_operation("reports_generated", f"{len(report_results)} reports created")
            
            return self._check_next_step()
            
        except Exception as e:
            error = UIError(
                f"Report generation failed: {e}",
                user_message="Failed to generate reports. Please check permissions.",
                component="ForensicController"
            )
            handle_error(error, {'operation': 'report_generation'})
            return Result.error(error)
    
    def _create_zip_archives(self) -> Result[None]:
        """Create ZIP archives if enabled"""
        try:
            if not self.zip_controller:
                return self._show_completion()
            
            # Find occurrence folder
            occurrence_result = self.workflow_controller.path_service.find_occurrence_folder(
                self.output_directory,
                self.output_directory
            )
            
            if not occurrence_result.success:
                error = UIError(
                    f"Failed to find occurrence folder: {occurrence_result.error.message}",
                    user_message=occurrence_result.error.user_message,
                    component="ForensicController"
                )
                handle_error(error, {'operation': 'zip_occurrence_folder'})
                return Result.error(error)
            
            occurrence_folder = occurrence_result.value
            
            # Create ZIP thread
            self.zip_thread = self.zip_controller.create_zip_thread(
                occurrence_folder,
                self.output_directory,
                self.workflow_controller.current_operation.form_data 
                    if hasattr(self.workflow_controller, 'current_operation') else None
            )
            
            # Note: Caller will connect signals and start thread
            return Result.success(self.zip_thread)
            
        except Exception as e:
            error = UIError(
                f"ZIP creation failed: {e}",
                user_message="Failed to create ZIP archives.",
                component="ForensicController"
            )
            handle_error(error, {'operation': 'zip_creation'})
            return Result.error(error)
    
    def on_zip_finished(self, result: Result) -> Result[None]:
        """Handle ZIP operation completion"""
        try:
            self.zip_operation_result = result
            
            if result.success:
                self.workflow_controller.store_operation_results(
                    zip_result=result
                )
                self._log_operation("zip_completed", "ZIP archives created successfully")
            else:
                self._log_operation("zip_failed", str(result.error), "warning")
            
            return self._show_completion()
            
        except Exception as e:
            error = UIError(f"Failed to handle ZIP completion: {e}")
            self._handle_error(error, {'method': 'on_zip_finished'})
            return Result.error(error)
    
    def _show_completion(self) -> Result[None]:
        """Show final completion message"""
        try:
            # Build success message
            success_data = self.workflow_controller.build_success_message()
            
            # Show dialog (if parent widget available)
            if self.parent_widget:
                SuccessDialog.show_success_message(success_data, self.parent_widget)
            
            # Cleanup
            self.cleanup_operation_memory()
            
            return Result.success(None)
            
        except Exception as e:
            self._log_operation("completion_display_failed", str(e), "warning")
            # Still cleanup even if display fails
            self.cleanup_operation_memory()
            return Result.success(None)
    
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
            
            # Clear local references
            self.file_thread = None
            self.zip_thread = None
            self.file_operation_result = None
            self.file_operation_results = {}
            self.reports_generated = None
            self.zip_operation_result = None
            
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
    
    def _check_next_step(self) -> Result[None]:
        """Determine next step after reports"""
        if self._should_create_zip():
            return self._create_zip_archives()
        else:
            return self._show_completion()
    
    def cancel_operation(self) -> bool:
        """Cancel current operation if running"""
        cancelled = False
        
        if self.file_thread and self.file_thread.isRunning():
            self.file_thread.cancel()
            cancelled = True
            
        if self.zip_thread and self.zip_thread.isRunning():
            self.zip_thread.cancel()
            cancelled = True
            
        if cancelled:
            self._log_operation("operation_cancelled", "User cancelled operation")
            
        return cancelled
```

### Step 1.2: Update Controller Imports

**File:** `controllers/__init__.py`

Add ForensicController to imports:

```python
# Service-oriented controllers
from .base_controller import BaseController
from .workflow_controller import WorkflowController
from .report_controller import ReportController
from .hash_controller import HashController
from .zip_controller import ZipController
from .forensic_controller import ForensicController  # ADD THIS

__all__ = [
    'BaseController', 'WorkflowController', 'ReportController', 
    'HashController', 'ZipController', 'ForensicController'  # ADD THIS
]
```

### 🧪 **Test Point 1.1:** Verify Controller Creation
```python
# In Python console:
from controllers import ForensicController
controller = ForensicController()
print(f"Controller created: {controller}")
# Should print: Controller created: <ForensicController object>
```

---

## Phase 2: Update ForensicTab [45 minutes]

### Step 2.1: Refactor ForensicTab to Use Controller

**File:** `ui/tabs/forensic_tab.py`

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Forensic Tab - Law enforcement mode interface
Now with proper controller integration following SOA architecture
"""

from pathlib import Path
from typing import Optional
import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSplitter, QProgressBar
)

from core.models import FormData
from ui.components import FormPanel, FilesPanel, LogConsole, TemplateSelector
from controllers.forensic_controller import ForensicController
from core.services.service_registry import get_service
from core.services.interfaces import IResourceManagementService, ResourceType
from core.exceptions import UIError
from core.error_handler import handle_error


class ForensicTab(QWidget):
    """Forensic mode tab for law enforcement evidence processing"""
    
    # Signals
    log_message = Signal(str)
    template_changed = Signal(str)  # template_id
    operation_started = Signal()  # New signal for MainWindow
    operation_completed = Signal()  # New signal for MainWindow
    progress_update = Signal(int, str)  # Forward progress to MainWindow
    
    def __init__(self, form_data: FormData, parent=None):
        """
        Initialize forensic tab with controller
        
        Args:
            form_data: FormData instance to bind to
            parent: Parent widget (MainWindow)
        """
        super().__init__(parent)
        self.form_data = form_data
        self.main_window = parent  # Store reference to MainWindow
        
        # Initialize controller
        self.controller = ForensicController(self)
        
        # Inject ZIP controller if available from MainWindow
        if hasattr(parent, 'zip_controller'):
            self.controller.set_zip_controller(parent.zip_controller)
        
        # Processing state
        self.processing_active = False
        self.current_thread = None
        self.is_paused = False
        
        # Resource management
        self._resource_manager = None
        self._controller_resource_id = None
        self._worker_resource_id = None
        self.logger = logging.getLogger(__name__)
        
        # Register with ResourceManagementService
        self._register_with_resource_manager()
        
        # Create UI
        self._create_ui()
        self._connect_signals()
    
    def _register_with_resource_manager(self):
        """Register this tab and its controller with resource management"""
        try:
            self._resource_manager = get_service(IResourceManagementService)
            if self._resource_manager:
                # Register tab
                self._resource_manager.register_component(
                    self, 
                    "ForensicTab", 
                    "tab"
                )
                
                # Track controller as resource
                self._controller_resource_id = self._resource_manager.track_resource(
                    self,
                    ResourceType.CUSTOM,
                    self.controller,
                    metadata={'type': 'ForensicController'}
                )
                
                # Register cleanup
                self._resource_manager.register_cleanup(
                    self,
                    self._cleanup_resources,
                    priority=10
                )
                
                self.logger.info("ForensicTab and controller registered with ResourceManagementService")
                
        except Exception as e:
            self.logger.warning(f"Could not register with ResourceManagementService: {e}")
            self._resource_manager = None
    
    def _create_ui(self):
        """Create the tab UI with integrated progress bar"""
        layout = QVBoxLayout(self)
        
        # Template selector at top
        self.template_selector = TemplateSelector()
        layout.addWidget(self.template_selector)
        
        # Main splitter
        splitter = QSplitter(Qt.Vertical)
        
        # Upper section: Form and Files
        upper_widget = QWidget()
        upper_layout = QHBoxLayout(upper_widget)
        
        # Form panel (left)
        self.form_panel = FormPanel(self.form_data)
        upper_layout.addWidget(self.form_panel)
        
        # Files panel (right)
        self.files_panel = FilesPanel()
        upper_layout.addWidget(self.files_panel)
        
        # Log console (bottom)
        self.log_console = LogConsole()
        
        # Add to splitter
        splitter.addWidget(upper_widget)
        splitter.addWidget(self.log_console)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Process button
        self.process_btn = QPushButton("Process Files")
        self.process_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; min-width: 120px; }")
        button_layout.addWidget(self.process_btn)
        
        # Pause button
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setEnabled(False)
        button_layout.addWidget(self.pause_btn)
        
        # Cancel button
        self.cancel_btn = QPushButton("Cancel") 
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """Connect internal signals"""
        # Process button triggers controller
        self.process_btn.clicked.connect(self._process_requested)
        
        # Control buttons
        self.pause_btn.clicked.connect(self._pause_processing)
        self.cancel_btn.clicked.connect(self._cancel_processing)
        
        # Template selector
        self.template_selector.template_changed.connect(self.template_changed)
        self.template_selector.template_changed.connect(self._on_template_changed)
        
        # Form panel signals
        self.form_panel.calculate_offset_requested.connect(
            lambda: self.log(f"Calculated offset: {self.form_data.time_offset}")
        )
        
        # Files panel signals
        self.files_panel.log_message.connect(self.log)
    
    def _process_requested(self):
        """Handle process button click - delegate to controller"""
        try:
            # Get files and folders
            files = self.files_panel.get_files()
            folders = self.files_panel.get_folders()
            
            # Get performance monitor from MainWindow if available
            perf_monitor = None
            if self.main_window and hasattr(self.main_window, 'performance_monitor'):
                perf_monitor = self.main_window.performance_monitor
            
            # Start processing via controller
            result = self.controller.process_forensic_files(
                form_data=self.form_data,
                files=files,
                folders=folders,
                performance_monitor=perf_monitor
            )
            
            if result.success:
                # Store thread reference
                self.current_thread = result.value
                
                # Connect thread signals
                self.current_thread.progress_update.connect(self._on_progress_update)
                self.current_thread.result_ready.connect(self._on_operation_finished)
                
                # Track thread as resource
                if self._resource_manager:
                    self._worker_resource_id = self._resource_manager.track_resource(
                        self,
                        ResourceType.WORKER,
                        self.current_thread,
                        metadata={'type': 'FolderStructureThread'}
                    )
                
                # Update UI state
                self.set_processing_state(True)
                
                # Notify MainWindow
                self.operation_started.emit()
                
                # Start thread
                self.current_thread.start()
                
                self.log("Started forensic file processing")
            else:
                # Error already handled by controller
                self.log(f"Failed to start processing: {result.error.user_message}")
                
        except Exception as e:
            error = UIError(
                f"Failed to start processing: {e}",
                user_message="Could not start file processing. Please try again."
            )
            handle_error(error, {'component': 'ForensicTab'})
    
    def _on_progress_update(self, percentage: int, message: str):
        """Handle progress updates from thread"""
        self.progress_bar.setValue(percentage)
        if message:
            self.log(message)
        # Forward to MainWindow
        self.progress_update.emit(percentage, message)
    
    def _on_operation_finished(self, result):
        """Handle operation completion"""
        try:
            # Let controller handle the result
            completion_result = self.controller.on_operation_finished(result)
            
            # Check if we need to handle reports or ZIP
            if completion_result.success and isinstance(completion_result.value, type(None)):
                # Normal completion - controller handled everything
                pass
            elif hasattr(completion_result, 'value') and completion_result.value:
                # Controller returned a ZIP thread to start
                if hasattr(completion_result.value, 'progress_update'):
                    # It's a ZIP thread
                    self._start_zip_operation(completion_result.value)
                    return  # Don't reset state yet
            
            # Reset UI state
            self.set_processing_state(False)
            
            # Notify MainWindow
            self.operation_completed.emit()
            
            self.log("Forensic processing completed")
            
        except Exception as e:
            self.logger.error(f"Error handling operation completion: {e}")
            self.set_processing_state(False)
            self.operation_completed.emit()
    
    def _start_zip_operation(self, zip_thread):
        """Start ZIP creation thread"""
        try:
            # Store new thread
            self.current_thread = zip_thread
            
            # Connect signals
            zip_thread.progress_update.connect(self._on_progress_update)
            zip_thread.result_ready.connect(self._on_zip_finished)
            
            # Track as resource
            if self._resource_manager and self._worker_resource_id:
                # Release previous worker first
                self._resource_manager.release_resource(self, self._worker_resource_id)
                
            if self._resource_manager:
                self._worker_resource_id = self._resource_manager.track_resource(
                    self,
                    ResourceType.WORKER,
                    zip_thread,
                    metadata={'type': 'ZipOperationThread'}
                )
            
            # Start thread
            zip_thread.start()
            
            self.log("Creating ZIP archives...")
            
        except Exception as e:
            self.logger.error(f"Failed to start ZIP operation: {e}")
            self.set_processing_state(False)
            self.operation_completed.emit()
    
    def _on_zip_finished(self, result):
        """Handle ZIP completion"""
        try:
            # Let controller handle it
            self.controller.on_zip_finished(result)
            
            # Reset UI state
            self.set_processing_state(False)
            
            # Notify MainWindow
            self.operation_completed.emit()
            
        except Exception as e:
            self.logger.error(f"Error handling ZIP completion: {e}")
            self.set_processing_state(False)
            self.operation_completed.emit()
    
    def set_processing_state(self, active: bool):
        """Update UI for processing state"""
        self.processing_active = active
        
        # Update buttons
        self.process_btn.setEnabled(not active)
        self.pause_btn.setEnabled(active)
        self.cancel_btn.setEnabled(active)
        
        # Update progress bar
        self.progress_bar.setVisible(active)
        if not active:
            self.progress_bar.setValue(0)
            self.is_paused = False
            self.pause_btn.setText("Pause")
            self.pause_btn.setStyleSheet("")
    
    def _pause_processing(self):
        """Handle pause button click"""
        if not self.current_thread or not self.processing_active:
            return
        
        if self.is_paused:
            # Resume
            if hasattr(self.current_thread, 'resume'):
                self.current_thread.resume()
            self.is_paused = False
            self.pause_btn.setText("Pause")
            self.pause_btn.setStyleSheet("")
            self.log("Resumed processing")
        else:
            # Pause
            if hasattr(self.current_thread, 'pause'):
                self.current_thread.pause()
            self.is_paused = True
            self.pause_btn.setText("Resume")
            self.pause_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; }")
            self.log("Paused processing")
    
    def _cancel_processing(self):
        """Handle cancel button click"""
        if self.controller.cancel_operation():
            self.log("Cancelling operation...")
            self.set_processing_state(False)
            self.operation_completed.emit()
    
    def _on_template_changed(self, template_id: str):
        """Handle template selection change"""
        template_name = self.template_selector.template_combo.currentText()
        self.log(f"Template changed to: {template_name}")
    
    def log(self, message: str):
        """Log message to console and emit signal"""
        self.log_console.log(message)
        self.log_message.emit(message)
    
    def _cleanup_resources(self):
        """Clean up tab resources"""
        self.logger.info("Cleaning up ForensicTab resources")
        
        # Cancel any running operation
        self.controller.cancel_operation()
        
        # Clean up controller resources
        self.controller.cleanup_operation_memory()
        
        # Release tracked resources
        if self._resource_manager:
            if self._worker_resource_id:
                self._resource_manager.release_resource(self, self._worker_resource_id)
            if self._controller_resource_id:
                self._resource_manager.release_resource(self, self._controller_resource_id)
        
        self.logger.info("ForensicTab cleanup complete")
    
    # Properties for backward compatibility with MainWindow
    @property
    def form_panel(self):
        return self.form_panel
    
    @property
    def files_panel(self):
        return self.files_panel
    
    @property
    def log_console(self):
        return self.log_console
    
    @property
    def process_btn(self):
        return self.process_btn
```

### 🧪 **Test Point 2.1:** Verify Tab Integration
```python
# Run the application
.venv/Scripts/python.exe main.py

# Test:
1. Open Forensic tab
2. Verify all UI components appear
3. Check that process button is enabled
4. Verify template selector works
# Should see no errors in console
```

---

## Phase 3: Clean Up MainWindow [45 minutes]

### Step 3.1: Remove Forensic Logic from MainWindow

**File:** `ui/main_window.py`

Remove these methods entirely:
- `process_forensic_files()`
- `on_operation_finished()`
- `generate_reports()`
- `create_zip_archives()`
- `on_zip_finished()`
- `show_final_completion_message()`
- `cleanup_operation_memory()`

Remove these attributes from `__init__`:
- `self.file_thread`
- `self.zip_thread`
- `self.file_operation_result`
- `self.file_operation_results`
- `self.reports_generated`
- `self.zip_operation_result`

### Step 3.2: Update MainWindow Signal Connections

**File:** `ui/main_window.py`

In `_create_forensic_tab()` method, update to:

```python
def _create_forensic_tab(self):
    """Create the forensic mode tab with controller"""
    forensic_tab = ForensicTab(self.form_data, parent=self)
    
    # Connect signals for UI coordination only
    forensic_tab.log_message.connect(self.log)
    forensic_tab.template_changed.connect(self._on_template_changed)
    forensic_tab.operation_started.connect(self._on_forensic_operation_started)
    forensic_tab.operation_completed.connect(self._on_forensic_operation_completed)
    forensic_tab.progress_update.connect(self.update_progress_with_status)
    
    # Store references for UI access only
    self.form_panel = forensic_tab.form_panel
    self.files_panel = forensic_tab.files_panel
    self.log_console = forensic_tab.log_console
    self.process_btn = forensic_tab.process_btn
    
    return forensic_tab
```

### Step 3.3: Add UI Coordination Methods

**File:** `ui/main_window.py`

Add these simple UI coordination methods:

```python
def _on_forensic_operation_started(self):
    """Handle forensic operation start - UI coordination only"""
    self.progress_bar.setVisible(True)
    self.operation_active = True
    
    # Start performance monitor if available
    if hasattr(self, 'performance_monitor') and self.performance_monitor:
        if hasattr(self.performance_monitor, 'start_monitoring'):
            self.performance_monitor.start_monitoring()

def _on_forensic_operation_completed(self):
    """Handle forensic operation completion - UI coordination only"""
    self.progress_bar.setVisible(False)
    self.progress_bar.setValue(0)
    self.operation_active = False
    
    # Stop performance monitor if running
    if hasattr(self, 'performance_monitor') and self.performance_monitor:
        if hasattr(self.performance_monitor, 'stop_monitoring'):
            self.performance_monitor.stop_monitoring()

def update_progress_with_status(self, percentage: int, message: str):
    """Update progress bar and log status - UI only"""
    self.progress_bar.setValue(percentage)
    if message:
        self.log(message)
```

### Step 3.4: Clean Up Imports

**File:** `ui/main_window.py`

Remove unused imports:
```python
# REMOVE these:
from core.workers import FolderStructureThread
from core.workers.zip_operations import ZipOperationThread
from ui.dialogs.success_dialog import SuccessDialog  # If not used elsewhere
from ui.dialogs.zip_prompt import ZipPromptDialog  # Moved to controller
```

### 🧪 **Test Point 3.1:** Verify MainWindow Cleanup
```python
# Check that MainWindow no longer has forensic methods:
grep -n "process_forensic_files\|on_operation_finished\|generate_reports" ui/main_window.py
# Should return nothing or only the signal connections

# Run application:
.venv/Scripts/python.exe main.py
# Should start without errors
```

---

## Phase 4: Integration Testing [30 minutes]

### Step 4.1: Test Basic Forensic Processing

```python
# Test procedure:
1. Start application
2. Go to Forensic tab
3. Fill in form:
   - Occurrence: TEST-001
   - Business: Test Company
   - Location: Test Location
   - Badge: 12345
   - Technician: Test User
4. Select test files
5. Click Process Files
6. Select output directory
7. Verify:
   - Progress bar appears
   - Files are copied
   - Folder structure is created
   - Success dialog appears
```

### Step 4.2: Test Report Generation

```python
# Enable reports in Settings:
1. Settings > User Settings
2. Enable Time Offset PDF
3. Enable Upload Log PDF
4. Process files again
5. Verify reports are created in Reports folder
```

### Step 4.3: Test ZIP Creation

```python
# Test ZIP functionality:
1. Settings > ZIP Settings
2. Enable ZIP creation
3. Process files
4. Verify ZIP prompt appears
5. Choose to create ZIP
6. Verify ZIP is created
```

### Step 4.4: Test Batch Processing

```python
# Verify batch still works:
1. Go to Batch tab
2. Add jobs to queue
3. Process batch
4. Verify it still uses the workflow correctly
# This tests that WorkflowController still works independently
```

### 🧪 **Test Point 4.1:** Complete Functionality Test
```bash
# Run full test suite if available:
.venv/Scripts/python.exe -m pytest tests/test_forensic_*.py -v

# Or manual test checklist:
✅ Form validation works
✅ File selection works
✅ Output directory selection works
✅ Progress bar updates
✅ Files are copied correctly
✅ Folder structure is created
✅ Reports generate when enabled
✅ ZIP creates when enabled
✅ Success dialog shows
✅ Cancel button works
✅ Pause/Resume works
✅ Batch processing still works
```

---

## Phase 5: Final Cleanup & Optimization [30 minutes]

### Step 5.1: Update ThreadManagementService

**File:** `core/services/thread_management_service.py`

Update the `discover_active_threads` method to check ForensicTab's controller instead of MainWindow:

```python
def discover_active_threads(self, app_components: Dict[str, Any]) -> Result[List[ThreadInfo]]:
    """Discover all active threads in the application"""
    try:
        threads = []
        
        # Check forensic tab threads (NOW IN CONTROLLER)
        forensic_tab = app_components.get('forensic_tab')
        if forensic_tab and hasattr(forensic_tab, 'controller'):
            controller = forensic_tab.controller
            
            # Check file thread
            if hasattr(controller, 'file_thread') and controller.file_thread:
                if controller.file_thread.isRunning():
                    threads.append(ThreadInfo(
                        name="Forensic file operations",
                        thread=controller.file_thread,
                        state=ThreadState.RUNNING,
                        can_cancel=True,
                        description="Forensic file processing"
                    ))
            
            # Check ZIP thread
            if hasattr(controller, 'zip_thread') and controller.zip_thread:
                if controller.zip_thread.isRunning():
                    threads.append(ThreadInfo(
                        name="ZIP operations",
                        thread=controller.zip_thread,
                        state=ThreadState.RUNNING,
                        can_cancel=True,
                        description="Archive creation"
                    ))
        
        # ... rest of the method unchanged
```

### Step 5.2: Update MainWindow closeEvent

**File:** `ui/main_window.py`

Update `closeEvent` to pass forensic_tab instead of main_window:

```python
def closeEvent(self, event):
    """Properly clean up all threads before closing"""
    # ... existing code ...
    
    # Update app_components to include forensic_tab
    app_components = {
        'forensic_tab': getattr(self, 'forensic_tab', None),  # CHANGED
        'batch_tab': getattr(self, 'batch_tab', None),
        'hashing_tab': getattr(self, 'hashing_tab', None)
    }
    
    # ... rest of method unchanged
```

### 🧪 **Test Point 5.1:** Verify Thread Management
```python
# Test shutdown:
1. Start processing files
2. While processing, close the application
3. Verify it prompts about active operations
4. Verify threads are properly terminated
```

---

## Phase 6: Verification & Documentation [15 minutes]

### Step 6.1: Final Verification Checklist

```bash
# Architecture verification:
✅ No forensic business logic in MainWindow
✅ ForensicController handles all forensic operations
✅ ForensicTab owns and manages its controller
✅ Resource management properly integrated
✅ Thread management updated
✅ All signals properly connected

# Functionality verification:
✅ Form validation works
✅ File processing works
✅ Report generation works
✅ ZIP creation works
✅ Success messages display
✅ Progress tracking works
✅ Cancel/Pause work
✅ Batch processing unaffected
```

### Step 6.2: Update Documentation

Add a comment to `CLAUDE.md`:

```markdown
## Recent Refactoring: ForensicController Extraction

The Forensic tab now follows the same SOA pattern as other tabs:
- **ForensicController** handles all business logic
- **ForensicTab** manages UI and owns the controller
- **MainWindow** only provides UI coordination
- All forensic operations are self-contained in the controller
```

---

## Rollback Points

If issues arise, you can rollback at these git checkpoints:

```bash
# After Phase 1 (Controller created):
git add controllers/forensic_controller.py controllers/__init__.py
git commit -m "feat: Create ForensicController"

# After Phase 2 (Tab updated):
git add ui/tabs/forensic_tab.py
git commit -m "feat: Update ForensicTab to use controller"

# After Phase 3 (MainWindow cleaned):
git add ui/main_window.py
git commit -m "feat: Remove forensic logic from MainWindow"

# After Phase 4-6 (Complete):
git add -A
git commit -m "feat: Complete ForensicController extraction"
```

---

## Success Metrics

The refactoring is successful when:

1. **No forensic business logic remains in MainWindow** ✅
2. **ForensicTab owns and manages ForensicController** ✅
3. **All functionality works as before** ✅
4. **Resource management is properly integrated** ✅
5. **Architecture is consistent across all tabs** ✅

---

## Post-Implementation Notes

After successful implementation:

1. **Run full test suite** to ensure nothing broke
2. **Test edge cases** like network drives, large files
3. **Monitor memory usage** during operations
4. **Update any documentation** that references the old structure
5. **Consider applying same pattern** to any remaining inconsistencies

This refactoring establishes a clean, consistent architecture that will greatly simplify the resource management implementation and future plugin system migration.