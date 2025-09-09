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
from core.exceptions import UIError
from core.error_handler import handle_error
from ui.tabs.forensic_success import ForensicSuccessBuilder
from ui.dialogs.success_dialog import SuccessDialog


class ForensicTab(QWidget):
    """Forensic mode tab for law enforcement evidence processing"""
    
    # Signals
    log_message = Signal(str)
    template_changed = Signal(str)  # template_id
    operation_started = Signal()  # New signal for MainWindow
    operation_completed = Signal()  # New signal for MainWindow
    progress_update = Signal(int, str)  # Forward progress to MainWindow
    
    def __init__(self, form_data: FormData, parent=None):
        """Initialize forensic tab with controller
        
        Args:
            form_data: FormData instance to bind to
            parent: Parent widget (MainWindow)
        """
        super().__init__(parent)
        self.form_data = form_data
        self.main_window = parent  # Store reference to MainWindow
        
        # Initialize controller
        self.controller = ForensicController(self)
        
        # Initialize success builder
        self.success_builder = ForensicSuccessBuilder()
        
        # Inject ZIP controller if available from MainWindow
        if hasattr(parent, 'zip_controller'):
            self.controller.set_zip_controller(parent.zip_controller)
        
        # Processing state
        self.processing_active = False
        self.current_thread = None
        self.is_paused = False
        self.logger = logging.getLogger(__name__)
        
        # Create UI
        self._create_ui()
        self._connect_signals()
    
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
        """Handle operation completion - SIMPLIFIED"""
        try:
            # Let controller handle EVERYTHING internally
            self.controller.on_operation_finished(result)
            
            # Controller will call set_processing_state(False) when done
            # We don't need to do anything else here
            
        except Exception as e:
            self.logger.error(f"Error in operation completion: {e}")
            self.set_processing_state(False)
            self.operation_completed.emit()
    
    def log(self, message: str):
        """Log message to console and emit signal"""
        self.log_console.log(message)
        self.log_message.emit(message)
        
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
            # Notify MainWindow
            self.operation_completed.emit()
    
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
    
    def _on_template_changed(self, template_id: str):
        """Handle template selection change"""
        template_name = self.template_selector.template_combo.currentText()
        self.log(f"Template changed to: {template_name}")
    
    def on_forensic_operation_complete(self, file_result, report_results, zip_result):
        """
        Handle forensic operation completion - called by ForensicController
        This is where the tab takes ownership of success message building
        
        Args:
            file_result: FileOperationResult from file processing
            report_results: Dict of report generation results
            zip_result: ArchiveOperationResult from ZIP creation
        """
        try:
            # Build success message using our local builder
            success_data = self.success_builder.create_success_message(
                file_result=file_result,
                report_results=report_results,
                zip_result=zip_result
            )
            
            # Show success dialog
            SuccessDialog.show_success_message(success_data, self)
            
            self.log("Forensic processing completed successfully!")
            
        except Exception as e:
            self.logger.error(f"Error showing success message: {e}")
            self.log("Operation completed but could not show success dialog")
    
    def cleanup(self):
        """Simple cleanup that delegates to controller"""
        self.logger.info("Cleaning up ForensicTab")
        
        # Cancel any running operations and clean up controller
        if self.controller:
            self.controller.cancel_operation()
            self.controller.cleanup()
        
        # Clear thread reference
        self.current_thread = None
        
        self.logger.info("ForensicTab cleanup complete")