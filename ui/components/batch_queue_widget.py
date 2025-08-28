#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch queue widget for managing batch processing jobs
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional
import time
import uuid

from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QTableWidgetItem, QPushButton, 
    QProgressBar, QLabel, QFileDialog,
    QHeaderView, QMenu, QSplitter, QTextEdit,
    QCheckBox, QComboBox, QSizePolicy
)
from PySide6.QtGui import QAction, QFont, QIcon

from core.batch_queue import BatchQueue
from core.models import BatchJob
from core.workers.batch_processor import BatchProcessorThread
from core.batch_recovery import BatchRecoveryManager
from core.exceptions import UIError, ErrorSeverity
from core.error_handler import handle_error
from ui.dialogs.success_dialog import SuccessDialog
from ui.components.elided_label import ElidedLabel


class BatchQueueWidget(QWidget):
    """Widget for managing the batch processing queue"""
    
    # Signals
    log_message = Signal(str)
    queue_status_changed = Signal(str)  # Status message for status bar
    processing_state_changed = Signal(bool)  # Emit when processing state changes
    
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window  # Store reference to MainWindow
        self.batch_queue = BatchQueue()
        self.processor_thread: Optional[BatchProcessorThread] = None
        self.processing_active = False
        self.stats_timer = QTimer()
        
        # Initialize recovery manager
        self.recovery_manager = BatchRecoveryManager(auto_save_interval=300)  # 5 minutes
        self.recovery_manager.set_batch_queue(self.batch_queue)
        self.recovery_manager.start_monitoring()
        
        self._setup_ui()
        self._connect_signals()
        
        # Auto-refresh timer
        self.stats_timer.timeout.connect(self._update_statistics)
        self.stats_timer.start(1000)  # Update every second
        
        # Check for recovery on startup
        self._check_recovery_on_startup()
        
    def _setup_ui(self):
        """Create the UI layout"""
        layout = QVBoxLayout(self)
        
        # Split view: Queue table (top) | Controls and progress (bottom)
        splitter = QSplitter(Qt.Vertical)
        # CRITICAL FIX: Prevent splitter from collapsing/expanding unexpectedly
        splitter.setChildrenCollapsible(False)
        splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(splitter)
        
        # Queue table section
        queue_section = self._create_queue_section()
        splitter.addWidget(queue_section)
        
        # Control and progress section
        control_section = self._create_control_section()
        splitter.addWidget(control_section)
        
        # Set splitter proportions (70% queue, 30% controls)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        
    def _create_queue_section(self) -> QGroupBox:
        """Create the queue table section"""
        section = QGroupBox("Batch Queue")
        layout = QVBoxLayout(section)
        
        # Queue management buttons
        queue_controls = QHBoxLayout()
        
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.setEnabled(False)
        queue_controls.addWidget(self.remove_btn)
        
        self.clear_btn = QPushButton("Clear Queue")
        queue_controls.addWidget(self.clear_btn)
        
        queue_controls.addStretch()
        
        self.save_queue_btn = QPushButton("Save Queue...")
        queue_controls.addWidget(self.save_queue_btn)
        
        self.load_queue_btn = QPushButton("Load Queue...")
        queue_controls.addWidget(self.load_queue_btn)
        
        layout.addLayout(queue_controls)
        
        # Queue table
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(7)
        self.queue_table.setHorizontalHeaderLabels([
            "Job Name", "Occurrence #", "Files", "Status", "Duration", "Template", "Edit"
        ])
        
        # CRITICAL FIX: Configure table to prevent window expansion
        header = self.queue_table.horizontalHeader()
        # Change from Stretch to Fixed to prevent window expansion from long job names
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # Job Name - Fixed width
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Occurrence
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Files
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Status
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Duration
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Template
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Edit
        
        # Set fixed widths to prevent expansion
        self.queue_table.setColumnWidth(0, 250)  # Job Name - reasonable fixed width
        
        # Enable horizontal scroll instead of window expansion
        self.queue_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Prevent table from expanding beyond its container
        self.queue_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self.queue_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.queue_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.queue_table.customContextMenuRequested.connect(self._show_context_menu)
        self.queue_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.queue_table.itemClicked.connect(self._on_item_clicked)
        
        layout.addWidget(self.queue_table)
        
        return section
        
    def _create_control_section(self) -> QGroupBox:
        """Create the control and progress section"""
        section = QGroupBox("Batch Processing Control")
        layout = QVBoxLayout(section)
        
        # Processing controls
        processing_controls = QHBoxLayout()
        
        self.start_batch_btn = QPushButton("Start Batch Processing")
        self.start_batch_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        processing_controls.addWidget(self.start_batch_btn)
        
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setEnabled(False)
        processing_controls.addWidget(self.pause_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        processing_controls.addWidget(self.cancel_btn)
        
        processing_controls.addStretch()
        
        # Settings
        self.auto_save_cb = QCheckBox("Auto-save progress")
        self.auto_save_cb.setChecked(True)
        processing_controls.addWidget(self.auto_save_cb)
        
        layout.addLayout(processing_controls)
        
        # Progress display
        progress_layout = QVBoxLayout()
        
        # Overall progress
        overall_label = QLabel("Overall Progress:")
        overall_label.setFont(QFont("", 9, QFont.Bold))
        progress_layout.addWidget(overall_label)
        
        self.overall_progress = QProgressBar()
        self.overall_progress.setVisible(False)
        progress_layout.addWidget(self.overall_progress)
        
        # Current job progress
        current_label = QLabel("Current Job:")
        current_label.setFont(QFont("", 9, QFont.Bold))
        progress_layout.addWidget(current_label)
        
        # CRITICAL FIX: Use ElidedLabel to prevent window expansion from long job names
        self.current_job_label = ElidedLabel("Ready to process", max_width=500)
        self.current_job_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        progress_layout.addWidget(self.current_job_label)
        
        self.current_job_progress = QProgressBar()
        self.current_job_progress.setVisible(False)
        progress_layout.addWidget(self.current_job_progress)
        
        # Statistics
        stats_label = QLabel("Statistics:")
        stats_label.setFont(QFont("", 9, QFont.Bold))
        progress_layout.addWidget(stats_label)
        
        self.stats_label = QLabel("0 jobs queued, 0 completed, 0 failed")
        progress_layout.addWidget(self.stats_label)
        
        layout.addLayout(progress_layout)
        
        return section
        
    def _connect_signals(self):
        """Connect widget signals"""
        # Button connections
        self.remove_btn.clicked.connect(self._remove_selected_jobs)
        self.clear_btn.clicked.connect(self._clear_queue)
        self.save_queue_btn.clicked.connect(self._save_queue)
        self.load_queue_btn.clicked.connect(self._load_queue)
        
        self.start_batch_btn.clicked.connect(self._start_processing)
        self.pause_btn.clicked.connect(self._pause_processing)
        self.cancel_btn.clicked.connect(self._cancel_processing)
        
        # Queue signals
        self.batch_queue.queue_changed.connect(self._refresh_table)
        self.batch_queue.job_added.connect(lambda job: self.log_message.emit(f"Added job: {job.job_name}"))
        self.batch_queue.job_removed.connect(lambda job_id: self.log_message.emit(f"Removed job: {job_id}"))
        
    def _build_job_name(self, form_data) -> str:
        """Build job name from occurrence number, business name, and address"""
        parts = [form_data.occurrence_number]
        
        if form_data.business_name:
            parts.append(form_data.business_name)
        
        if form_data.location_address:
            parts.append(form_data.location_address)
        
        return " - ".join(parts)

    def add_job_from_current(self, form_data, files: List[Path], folders: List[Path], 
                           output_directory: Path, template_type: str = "forensic"):
        """Add a job from current form configuration"""
        import copy
        
        job = BatchJob(
            job_name=self._build_job_name(form_data),
            form_data=copy.deepcopy(form_data),
            files=files.copy(),
            folders=folders.copy(),
            output_directory=output_directory,
            template_type=template_type
        )
        
        try:
            self.batch_queue.add_job(job)
            self.log_message.emit(f"Added job '{job.job_name}' to batch queue")
        except ValueError as e:
            error = UIError(
                f"Invalid job: {str(e)}",
                user_message=f"Cannot add job: {str(e)}",
                component="BatchQueueWidget",
                severity=ErrorSeverity.WARNING
            )
            handle_error(error, {'operation': 'add_job_validation'})
            
    def _remove_selected_jobs(self):
        """Remove selected jobs from queue"""
        selected_rows = set()
        for item in self.queue_table.selectedItems():
            selected_rows.add(item.row())
            
        if not selected_rows:
            return
            
        # Nuclear migration: Convert to immediate action with warning notification
        count = len(selected_rows)
        
        # Remove jobs (in reverse order to avoid index issues)
        for row in sorted(selected_rows, reverse=True):
            if row < len(self.batch_queue.jobs):
                job = self.batch_queue.jobs[row]
                self.batch_queue.remove_job(job.job_id)
        
        # Show warning notification about the action taken
        warning_error = UIError(
            f"Removed {count} job(s) from queue",
            user_message=f"Successfully removed {count} job(s) from the batch queue.",
            component="BatchQueueWidget",
            severity=ErrorSeverity.WARNING
        )
        handle_error(warning_error, {'operation': 'remove_jobs', 'count': count})
                    
    def _clear_queue(self):
        """Clear all jobs from queue"""
        if not self.batch_queue.jobs:
            return
        
        # Nuclear migration: Convert to immediate action with warning notification
        job_count = len(self.batch_queue.jobs)
        self.batch_queue.clear_queue()
        
        # Show warning notification about the action taken
        warning_error = UIError(
            f"Cleared all {job_count} jobs from queue",
            user_message=f"Successfully removed all {job_count} job(s) from the batch queue.",
            component="BatchQueueWidget",
            severity=ErrorSeverity.WARNING
        )
        handle_error(warning_error, {'operation': 'clear_queue', 'job_count': job_count})
        
        self.log_message.emit("Cleared batch queue")
            
    def _save_queue(self):
        """Save queue to file"""
        if not self.batch_queue.jobs:
            error = UIError(
                "Queue is empty - nothing to save",
                user_message="No jobs in queue to save.",
                component="BatchQueueWidget",
                severity=ErrorSeverity.INFO
            )
            handle_error(error, {'operation': 'save_queue_validation'})
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Batch Queue",
            f"batch_queue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                start_time = time.time()
                self.batch_queue.save_to_file(Path(file_path))
                duration = time.time() - start_time
                
                self.log_message.emit(f"Saved batch queue to {file_path}")
                
                # ✅ NEW: Use proper success dialog instead of abusing error system
                from core.services.success_message_builder import SuccessMessageBuilder
                from core.services.success_message_data import QueueOperationData
                from ui.dialogs.success_dialog import SuccessDialog
                
                # Create operation data
                queue_data = QueueOperationData(
                    operation_type='save',
                    file_path=Path(file_path),
                    job_count=len(self.batch_queue.jobs),
                    file_size_bytes=Path(file_path).stat().st_size if Path(file_path).exists() else 0,
                    duration_seconds=duration
                )
                
                # Build success message
                message_builder = SuccessMessageBuilder()
                message_data = message_builder.build_queue_save_success_message(queue_data)
                
                # Show proper success dialog
                SuccessDialog.show_success_message(message_data, self)
            except Exception as e:
                error = UIError(
                    f"Queue save failed: {str(e)}",
                    user_message="Failed to save queue. Please check folder permissions and try again.",
                    component="BatchQueueWidget"
                )
                handle_error(error, {'operation': 'save_queue_error'})
                
    def _load_queue(self):
        """Load queue from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Batch Queue", "",
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                original_count = len(self.batch_queue.jobs)
                start_time = time.time()
                self.batch_queue.load_from_file(Path(file_path))
                duration = time.time() - start_time
                new_count = len(self.batch_queue.jobs)
                loaded_jobs = new_count - original_count  # Calculate actual loaded
                
                self.log_message.emit(f"Loaded batch queue from {file_path}")
                
                # ✅ NEW: Use proper success dialog instead of abusing error system
                from core.services.success_message_builder import SuccessMessageBuilder
                from core.services.success_message_data import QueueOperationData
                from ui.dialogs.success_dialog import SuccessDialog
                
                # Create operation data
                queue_data = QueueOperationData(
                    operation_type='load',
                    file_path=Path(file_path),
                    job_count=loaded_jobs,
                    file_size_bytes=Path(file_path).stat().st_size if Path(file_path).exists() else 0,
                    duration_seconds=duration,
                    duplicate_jobs_skipped=max(0, (original_count + loaded_jobs) - new_count)
                )
                
                # Build success message
                message_builder = SuccessMessageBuilder()
                message_data = message_builder.build_queue_load_success_message(queue_data)
                
                # Show proper success dialog
                SuccessDialog.show_success_message(message_data, self)
                
                # Update UI to show new jobs
                self._refresh_table()
            except Exception as e:
                error = UIError(
                    f"Queue load failed: {str(e)}",
                    user_message="Failed to load queue file. Please check the file format and try again.",
                    component="BatchQueueWidget"
                )
                handle_error(error, {'operation': 'load_queue_error'})
                
    def _start_processing(self):
        """Start batch processing"""
        pending_jobs = self.batch_queue.get_pending_jobs()
        if not pending_jobs:
            error = UIError(
                "No pending jobs to process",
                user_message="No jobs in queue to process. Add some jobs first.",
                component="BatchQueueWidget",
                severity=ErrorSeverity.WARNING
            )
            handle_error(error, {'operation': 'process_validation'})
            return
            
        # Handle ZIP prompt before starting batch processing
        if self.main_window and hasattr(self.main_window, 'zip_controller'):
            if self.main_window.zip_controller.should_prompt_user():
                from ui.dialogs.zip_prompt import ZipPromptDialog
                choice = ZipPromptDialog.prompt_user(self)
                self.main_window.zip_controller.set_session_choice(
                    choice['create_zip'], 
                    choice['remember_for_session']
                )
            
        # Validate all jobs first
        validation = self.batch_queue.validate_all_jobs()
        if validation['invalid_jobs']:
            invalid_count = len(validation['invalid_jobs'])
            
            # Nuclear migration: Auto-proceed with valid jobs and show warning notification
            warning_error = UIError(
                f"Found {invalid_count} invalid job(s) - proceeding with valid jobs only",
                user_message=f"Found {invalid_count} job(s) with validation errors. Processing will continue with valid jobs only. Check the log for details.",
                component="BatchQueueWidget",
                severity=ErrorSeverity.WARNING
            )
            handle_error(warning_error, {'operation': 'batch_validation', 'invalid_count': invalid_count, 'valid_count': len(validation['valid_jobs'])})
                
        # Create and start processor thread
        self.processor_thread = BatchProcessorThread(self.batch_queue, self.main_window)
        self._connect_processor_signals()
        
        self.processing_active = True
        self.recovery_manager.set_processing_active(True)
        self._update_ui_for_processing_state()
        
        self.processor_thread.start()
        self.log_message.emit(f"Started batch processing of {len(pending_jobs)} jobs")
        
    def _pause_processing(self):
        """Pause/resume batch processing"""
        if not self.processor_thread:
            return
            
        if self.processor_thread.is_paused():
            self.processor_thread.resume()
            self.pause_btn.setText("Pause")
            self.log_message.emit("Resumed batch processing")
        else:
            self.processor_thread.pause()
            self.pause_btn.setText("Resume")
            self.log_message.emit("Paused batch processing")
            
    def _cancel_processing(self):
        """Cancel batch processing"""
        if not self.processor_thread:
            return
            
        # Nuclear migration: Convert to immediate action with warning notification
        self.processor_thread.cancel()
        
        # Show warning notification about the cancellation
        warning_error = UIError(
            "Batch processing cancelled",
            user_message="Batch processing has been cancelled. Current job will be marked as failed.",
            component="BatchQueueWidget",
            severity=ErrorSeverity.WARNING
        )
        handle_error(warning_error, {'operation': 'cancel_processing'})
        
        self.log_message.emit("Cancelled batch processing")
            
    def _connect_processor_signals(self):
        """Connect processor thread signals"""
        if not self.processor_thread:
            return
            
        self.processor_thread.job_started.connect(self._on_job_started)
        self.processor_thread.job_progress.connect(self._on_job_progress)
        self.processor_thread.job_completed.connect(self._on_job_completed)
        self.processor_thread.queue_progress.connect(self._on_queue_progress)
        
        # NEW: Connect unified result signal for enhanced success messages
        self.processor_thread.result_ready.connect(self._on_batch_result_ready)
        
    def _on_job_started(self, job_id: str, job_name: str):
        """Handle job started signal"""
        self.current_job_label.setText(job_name)
        self.current_job_progress.setVisible(True)
        self.current_job_progress.setValue(0)
        self.log_message.emit(f"Started job: {job_name}")
        
    def _on_job_progress(self, job_id: str, percentage: int, message: str):
        """Handle job progress signal"""
        if percentage >= 0:
            self.current_job_progress.setValue(percentage)
        if message:
            self.current_job_label.setText(message)
            
    def _on_job_completed(self, job_id: str, success: bool, message: str, results):
        """Handle job completed signal"""
        job = self.batch_queue.get_job_by_id(job_id)
        if job:
            status = "✓ Completed" if success else "✗ Failed"
            self.log_message.emit(f"Job '{job.job_name}' {status}: {message}")
            
    def _on_queue_progress(self, completed: int, total: int):
        """Handle queue progress signal"""
        self.overall_progress.setVisible(True)
        self.overall_progress.setMaximum(total)
        self.overall_progress.setValue(completed)
        self.queue_status_changed.emit(f"Batch: {completed}/{total} jobs completed")
        
    def _on_batch_result_ready(self, result):
        """Handle batch result with enhanced success message support (NEW)"""
        from core.result_types import Result
        from core.services.success_message_builder import SuccessMessageBuilder
        from core.services.success_message_data import EnhancedBatchOperationData
        
        # Handle UI state updates (moved from _on_queue_completed)
        self.processing_active = False
        self.recovery_manager.set_processing_active(False)
        self._update_ui_for_processing_state()
        
        # Clear batch operation choice from ZIP controller
        if self.main_window and hasattr(self.main_window, 'zip_controller'):
            self.main_window.zip_controller.clear_batch_operation_choice()
        
        self.current_job_label.setText("Batch processing completed")
        self.current_job_progress.setVisible(False)
        self.overall_progress.setVisible(False)
        self.queue_status_changed.emit("Ready")
        
        try:
            if not isinstance(result, Result):
                # Fallback to legacy handler if result format is unexpected
                return
                
            if result.success:
                # Check if we have enhanced batch data in metadata
                if (result.metadata and 
                    'enhanced_batch_data' in result.metadata and 
                    isinstance(result.metadata['enhanced_batch_data'], EnhancedBatchOperationData)):
                    
                    # Use enhanced success message
                    enhanced_data = result.metadata['enhanced_batch_data']
                    message_builder = SuccessMessageBuilder()
                    message_data = message_builder.build_enhanced_batch_success_message(enhanced_data)
                    
                    # Show enhanced success dialog
                    SuccessDialog.show_success_message(
                        message_data, 
                        self.main_window if hasattr(self, 'main_window') and self.main_window else None
                    )
                    
                    self.log_message.emit(
                        f"Enhanced batch processing completed: {enhanced_data.successful_jobs}/"
                        f"{enhanced_data.total_jobs} successful, "
                        f"{enhanced_data.total_files_processed} files processed"
                    )
                    
                else:
                    # Fall back to basic batch data if available
                    if result.metadata:
                        total_jobs = result.metadata.get('total_jobs', 0)
                        successful_jobs = result.metadata.get('successful_jobs', 0) 
                        failed_jobs = result.metadata.get('failed_jobs', 0)
                        
                        from core.services.success_message_data import BatchOperationData
                        basic_data = BatchOperationData(
                            total_jobs=total_jobs,
                            successful_jobs=successful_jobs,
                            failed_jobs=failed_jobs,
                            processing_time_seconds=0  # Not available in basic metadata
                        )
                        
                        message_builder = SuccessMessageBuilder()
                        message_data = message_builder.build_batch_success_message(basic_data)
                        
                        SuccessDialog.show_success_message(
                            message_data,
                            self.main_window if hasattr(self, 'main_window') and self.main_window else None
                        )
                    
            else:
                # Handle batch processing errors
                error_msg = result.error.user_message if result.error else "Batch processing failed"
                self.log_message.emit(f"Batch processing failed: {error_msg}")
                
                # Show error via error notification system instead of success dialog
                if result.error:
                    from core.error_handler import handle_error
                    handle_error(result.error, {'component': 'batch_queue_widget', 'operation': 'batch_processing'})
                    
        except Exception as e:
            # If anything goes wrong with enhanced processing, log and continue
            self.log_message.emit(f"Enhanced batch success processing failed: {e}")
            # Let legacy handler take over
        
    def _update_ui_for_processing_state(self):
        """Update UI elements based on processing state"""
        self.start_batch_btn.setEnabled(not self.processing_active)
        self.pause_btn.setEnabled(self.processing_active)
        self.cancel_btn.setEnabled(self.processing_active)
        
        # Disable queue modification during processing
        self.remove_btn.setEnabled(not self.processing_active and self.queue_table.selectionModel().hasSelection())
        self.clear_btn.setEnabled(not self.processing_active)
        
        # Emit signal to parent to update external buttons (like "Add to Queue")
        self.processing_state_changed.emit(self.processing_active)
        
    def _on_selection_changed(self):
        """Handle table selection changes"""
        has_selection = self.queue_table.selectionModel().hasSelection()
        self.remove_btn.setEnabled(has_selection and not self.processing_active)
        
    def _on_item_clicked(self, item):
        """Handle item clicks - show context menu for edit column"""
        if item.column() == 6:  # Edit column
            # Select the row first
            self.queue_table.selectRow(item.row())
            
            # Get the item position and show context menu
            item_rect = self.queue_table.visualItemRect(item)
            position = item_rect.center()
            self._show_context_menu(position)
        
    def _show_context_menu(self, position):
        """Show context menu for queue table"""
        if not self.queue_table.itemAt(position):
            return
            
        menu = QMenu(self)
        
        if not self.processing_active:
            edit_action = QAction("Edit Job", self)
            edit_action.triggered.connect(self._edit_selected_job)
            menu.addAction(edit_action)
            
            duplicate_action = QAction("Duplicate Job", self)
            duplicate_action.triggered.connect(self._duplicate_selected_job)
            menu.addAction(duplicate_action)
            
            menu.addSeparator()
            
            remove_action = QAction("Remove Job", self)
            remove_action.triggered.connect(self._remove_selected_jobs)
            menu.addAction(remove_action)
            
        view_details_action = QAction("View Details", self)
        view_details_action.triggered.connect(self._view_job_details)
        menu.addAction(view_details_action)
        
        menu.exec_(self.queue_table.mapToGlobal(position))
        
    def _edit_selected_job(self):
        """Edit selected job"""
        # TODO: Implement job editing dialog
        error = UIError(
            "Job editing not yet implemented",
            user_message="Job editing feature is not yet available.",
            component="BatchQueueWidget",
            severity=ErrorSeverity.INFO
        )
        handle_error(error, {'operation': 'edit_job_not_implemented'})
        
    def _duplicate_selected_job(self):
        """Duplicate selected job"""
        current_row = self.queue_table.currentRow()
        if 0 <= current_row < len(self.batch_queue.jobs):
            original_job = self.batch_queue.jobs[current_row]
            
            # Create a copy with new ID and name
            import copy
            new_job = copy.deepcopy(original_job)
            new_job.job_id = str(uuid.uuid4())
            new_job.job_name = f"{original_job.job_name} (Copy)"
            new_job.status = "pending"
            new_job.start_time = None
            new_job.end_time = None
            new_job.error_message = ""
            
            self.batch_queue.add_job(new_job)
            
    def _view_job_details(self):
        """View detailed job information"""
        current_row = self.queue_table.currentRow()
        if 0 <= current_row < len(self.batch_queue.jobs):
            job = self.batch_queue.jobs[current_row]
            
            details = f"Job Details for: {job.job_name}\n\n"
            details += f"Job ID: {job.job_id}\n"
            details += f"Occurrence Number: {job.form_data.occurrence_number}\n"
            details += f"Status: {job.status}\n"
            details += f"Template Type: {job.template_type}\n"
            details += f"Files: {len(job.files)}\n"
            details += f"Folders: {len(job.folders)}\n"
            
            if job.start_time:
                details += f"Started: {job.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            if job.end_time:
                details += f"Completed: {job.end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            if job.error_message:
                details += f"Error: {job.error_message}\n"
                
            success_error = UIError(
                "Job details requested",
                user_message=details,
                component="BatchQueueWidget",
                severity=ErrorSeverity.INFO
            )
            handle_error(success_error, {'operation': 'job_details_display'})
            
    def _refresh_table(self):
        """Refresh the queue table"""
        self.queue_table.setRowCount(len(self.batch_queue.jobs))
        
        for row, job in enumerate(self.batch_queue.jobs):
            # Job Name - CRITICAL FIX: Truncate long names to prevent table expansion
            display_name = job.job_name
            if len(display_name) > 35:  # Truncate very long names
                display_name = display_name[:32] + "..."
            
            name_item = QTableWidgetItem(display_name)
            name_item.setToolTip(job.job_name)  # Show full name on hover
            self.queue_table.setItem(row, 0, name_item)
            
            # Occurrence Number
            occ_item = QTableWidgetItem(job.form_data.occurrence_number)
            self.queue_table.setItem(row, 1, occ_item)
            
            # File Count
            file_count = job.get_file_count()
            files_item = QTableWidgetItem(str(file_count))
            self.queue_table.setItem(row, 2, files_item)
            
            # Status
            status_item = QTableWidgetItem(job.status.title())
            if job.status == "completed":
                status_item.setText("✓ Completed")
            elif job.status == "failed":
                status_item.setText("✗ Failed")
            elif job.status == "processing":
                status_item.setText("⚙ Processing")
            else:
                status_item.setText("⏳ Pending")
            self.queue_table.setItem(row, 3, status_item)
            
            # Duration
            duration = job.get_duration()
            if duration:
                duration_text = f"{duration:.1f}s"
            else:
                duration_text = "-"
            duration_item = QTableWidgetItem(duration_text)
            self.queue_table.setItem(row, 4, duration_item)
            
            # Template
            template_item = QTableWidgetItem(job.template_type.title())
            self.queue_table.setItem(row, 5, template_item)
            
            # Edit button with pencil icon
            edit_item = QTableWidgetItem("✏️")
            edit_item.setTextAlignment(Qt.AlignCenter)
            edit_item.setToolTip("Click to open job menu")
            self.queue_table.setItem(row, 6, edit_item)
            
        self._update_statistics()
        
    def _update_statistics(self):
        """Update statistics display"""
        stats = self.batch_queue.get_statistics()
        stats_text = f"{stats['total']} jobs queued, {stats['completed']} completed, {stats['failed']} failed"
        self.stats_label.setText(stats_text)
        
    def _check_recovery_on_startup(self):
        """Check for recovery data on startup"""
        # Use QTimer to delay the check until after UI is fully initialized
        QTimer.singleShot(1000, self._do_recovery_check)
        
    def _do_recovery_check(self):
        """Perform the actual recovery check"""
        try:
            if self.recovery_manager.prompt_recovery(self):
                self.log_message.emit("Batch queue recovered from previous session")
            
        except Exception as e:
            print(f"Error during recovery check: {e}")
            
    def get_queue(self) -> BatchQueue:
        """Get the batch queue instance"""
        return self.batch_queue
        
    def get_recovery_manager(self) -> BatchRecoveryManager:
        """Get the recovery manager instance"""
        return self.recovery_manager