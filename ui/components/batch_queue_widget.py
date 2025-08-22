#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch queue widget for managing batch processing jobs
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional
import uuid

from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QTableWidgetItem, QPushButton, 
    QProgressBar, QLabel, QMessageBox, QFileDialog,
    QHeaderView, QMenu, QSplitter, QTextEdit,
    QCheckBox, QComboBox
)
from PySide6.QtGui import QAction, QFont

from core.batch_queue import BatchQueue
from core.models import BatchJob
from core.workers.batch_processor import BatchProcessorThread
from core.batch_recovery import BatchRecoveryManager


class BatchQueueWidget(QWidget):
    """Widget for managing the batch processing queue"""
    
    # Signals
    log_message = Signal(str)
    queue_status_changed = Signal(str)  # Status message for status bar
    
    def __init__(self, parent=None):
        super().__init__(parent)
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
        
        self.add_current_btn = QPushButton("Add Current Job")
        self.add_current_btn.setToolTip("Add current form configuration as a new job")
        queue_controls.addWidget(self.add_current_btn)
        
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
            "Job Name", "Occurrence #", "Files", "Status", "Duration", "Template", "Actions"
        ])
        
        # Configure table
        header = self.queue_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Job Name
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Occurrence
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Files
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Status
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Duration
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Template
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Actions
        
        self.queue_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.queue_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.queue_table.customContextMenuRequested.connect(self._show_context_menu)
        self.queue_table.itemSelectionChanged.connect(self._on_selection_changed)
        
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
        
        self.current_job_label = QLabel("Ready to process")
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
        self.add_current_btn.clicked.connect(self._add_current_job)
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
        
    def _add_current_job(self):
        """Add current configuration as a new job - to be connected by parent"""
        # This will be connected to a method in the parent that has access to current form data
        pass
        
    def add_job_from_current(self, form_data, files: List[Path], folders: List[Path], 
                           output_directory: Path, template_type: str = "forensic"):
        """Add a job from current form configuration"""
        import copy
        
        job = BatchJob(
            job_name=f"{form_data.occurrence_number} - {datetime.now().strftime('%H:%M:%S')}",
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
            QMessageBox.warning(self, "Invalid Job", str(e))
            
    def _remove_selected_jobs(self):
        """Remove selected jobs from queue"""
        selected_rows = set()
        for item in self.queue_table.selectedItems():
            selected_rows.add(item.row())
            
        if not selected_rows:
            return
            
        # Confirm deletion
        count = len(selected_rows)
        reply = QMessageBox.question(
            self, "Remove Jobs",
            f"Remove {count} job(s) from the queue?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Remove jobs (in reverse order to avoid index issues)
            for row in sorted(selected_rows, reverse=True):
                if row < len(self.batch_queue.jobs):
                    job = self.batch_queue.jobs[row]
                    self.batch_queue.remove_job(job.job_id)
                    
    def _clear_queue(self):
        """Clear all jobs from queue"""
        if not self.batch_queue.jobs:
            return
            
        reply = QMessageBox.question(
            self, "Clear Queue",
            "Remove all jobs from the queue?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.batch_queue.clear_queue()
            self.log_message.emit("Cleared batch queue")
            
    def _save_queue(self):
        """Save queue to file"""
        if not self.batch_queue.jobs:
            QMessageBox.information(self, "Save Queue", "Queue is empty - nothing to save")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Batch Queue",
            f"batch_queue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                self.batch_queue.save_to_file(Path(file_path))
                self.log_message.emit(f"Saved batch queue to {file_path}")
                QMessageBox.information(self, "Save Successful", f"Queue saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Failed", f"Failed to save queue:\n{e}")
                
    def _load_queue(self):
        """Load queue from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Batch Queue", "",
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                self.batch_queue.load_from_file(Path(file_path))
                self.log_message.emit(f"Loaded batch queue from {file_path}")
                QMessageBox.information(self, "Load Successful", 
                                      f"Loaded {len(self.batch_queue.jobs)} jobs from:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Load Failed", f"Failed to load queue:\n{e}")
                
    def _start_processing(self):
        """Start batch processing"""
        pending_jobs = self.batch_queue.get_pending_jobs()
        if not pending_jobs:
            QMessageBox.information(self, "No Jobs", "No pending jobs to process")
            return
            
        # Handle ZIP prompt before starting batch processing
        main_window = self.parent()
        if hasattr(main_window, 'zip_controller') and main_window.zip_controller.should_prompt_user():
            from ui.dialogs.zip_prompt import ZipPromptDialog
            choice = ZipPromptDialog.prompt_user(self)
            main_window.zip_controller.set_session_choice(
                choice['create_zip'], 
                choice['remember_for_session']
            )
            
        # Validate all jobs first
        validation = self.batch_queue.validate_all_jobs()
        if validation['invalid_jobs']:
            invalid_count = len(validation['invalid_jobs'])
            reply = QMessageBox.question(
                self, "Invalid Jobs Found",
                f"{invalid_count} job(s) have validation errors. Continue with valid jobs only?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
                
        # Create and start processor thread
        self.processor_thread = BatchProcessorThread(self.batch_queue, self.parent())
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
            
        reply = QMessageBox.question(
            self, "Cancel Processing",
            "Cancel batch processing? Current job will be marked as failed.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.processor_thread.cancel()
            self.log_message.emit("Cancelled batch processing")
            
    def _connect_processor_signals(self):
        """Connect processor thread signals"""
        if not self.processor_thread:
            return
            
        self.processor_thread.job_started.connect(self._on_job_started)
        self.processor_thread.job_progress.connect(self._on_job_progress)
        self.processor_thread.job_completed.connect(self._on_job_completed)
        self.processor_thread.queue_progress.connect(self._on_queue_progress)
        self.processor_thread.queue_completed.connect(self._on_queue_completed)
        
    def _on_job_started(self, job_id: str, job_name: str):
        """Handle job started signal"""
        self.current_job_label.setText(f"Processing: {job_name}")
        self.current_job_progress.setVisible(True)
        self.current_job_progress.setValue(0)
        self.log_message.emit(f"Started job: {job_name}")
        
    def _on_job_progress(self, job_id: str, percentage: int, message: str):
        """Handle job progress signal"""
        if percentage >= 0:
            self.current_job_progress.setValue(percentage)
        if message:
            self.current_job_label.setText(f"Processing: {message}")
            
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
        
    def _on_queue_completed(self, total: int, successful: int, failed: int):
        """Handle queue completion signal"""
        self.processing_active = False
        self.recovery_manager.set_processing_active(False)
        self._update_ui_for_processing_state()
        
        self.current_job_label.setText("Batch processing completed")
        self.current_job_progress.setVisible(False)
        self.overall_progress.setVisible(False)
        
        # Show completion message
        message = f"Batch processing completed!\n\n"
        message += f"Total jobs: {total}\n"
        message += f"Successful: {successful}\n"
        message += f"Failed: {failed}"
        
        QMessageBox.information(self, "Batch Complete", message)
        self.log_message.emit(f"Batch processing completed: {successful}/{total} successful")
        self.queue_status_changed.emit("Ready")
        
    def _update_ui_for_processing_state(self):
        """Update UI elements based on processing state"""
        self.start_batch_btn.setEnabled(not self.processing_active)
        self.pause_btn.setEnabled(self.processing_active)
        self.cancel_btn.setEnabled(self.processing_active)
        
        # Disable queue modification during processing
        self.add_current_btn.setEnabled(not self.processing_active)
        self.remove_btn.setEnabled(not self.processing_active and self.queue_table.selectionModel().hasSelection())
        self.clear_btn.setEnabled(not self.processing_active)
        
    def _on_selection_changed(self):
        """Handle table selection changes"""
        has_selection = self.queue_table.selectionModel().hasSelection()
        self.remove_btn.setEnabled(has_selection and not self.processing_active)
        
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
        QMessageBox.information(self, "Edit Job", "Job editing not yet implemented")
        
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
                
            QMessageBox.information(self, "Job Details", details)
            
    def _refresh_table(self):
        """Refresh the queue table"""
        self.queue_table.setRowCount(len(self.batch_queue.jobs))
        
        for row, job in enumerate(self.batch_queue.jobs):
            # Job Name
            name_item = QTableWidgetItem(job.job_name)
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
            
            # Actions (placeholder for now)
            actions_item = QTableWidgetItem("...")
            self.queue_table.setItem(row, 6, actions_item)
            
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