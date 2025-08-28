#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch Tab - Batch processing interface for multiple jobs
"""

from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSplitter, QGroupBox, QFileDialog, QLabel,
    QComboBox, QSizePolicy
)

from core.models import FormData
from ui.components import FormPanel, FilesPanel, LogConsole
from ui.components.batch_queue_widget import BatchQueueWidget
from ui.components.elided_label import PathLabel
from core.exceptions import UIError, ErrorSeverity
from core.error_handler import handle_error


class BatchTab(QWidget):
    """Batch processing tab for managing multiple jobs"""
    
    # Signals
    log_message = Signal(str)
    status_message = Signal(str)
    
    def __init__(self, form_data: FormData, parent=None):
        """Initialize batch tab
        
        Args:
            form_data: FormData instance to bind to
            parent: Parent widget (should be MainWindow)
        """
        super().__init__(parent)
        self.form_data = form_data
        self.main_window = parent
        self.output_directory = None  # Dedicated output directory for batch tab
        
        self._create_ui()
        self._connect_signals()
        
    def _create_ui(self):
        """Create the tab UI"""
        layout = QVBoxLayout(self)
        
        # Main splitter: Job Setup (left) | Batch Queue (right)
        main_splitter = QSplitter(Qt.Horizontal)
        # CRITICAL FIX: Prevent splitter from collapsing/expanding due to content
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(main_splitter)
        
        # Left side: Job setup panel
        job_setup_widget = self._create_job_setup_panel()
        main_splitter.addWidget(job_setup_widget)
        
        # Right side: Batch queue
        self.batch_queue_widget = BatchQueueWidget(self, main_window=self.main_window)
        main_splitter.addWidget(self.batch_queue_widget)
        
        # Set splitter proportions (40% setup, 60% queue)
        main_splitter.setStretchFactor(0, 4)
        main_splitter.setStretchFactor(1, 6)
        
    def _create_job_setup_panel(self) -> QWidget:
        """Create the job setup panel"""
        job_setup = QGroupBox("Job Configuration")
        layout = QVBoxLayout(job_setup)
        
        # Vertical splitter for form and files
        splitter = QSplitter(Qt.Vertical)
        # CRITICAL FIX: Prevent form/files splitter from expanding due to content
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter)
        
        # Form panel
        self.form_panel = FormPanel(self.form_data)
        splitter.addWidget(self.form_panel)
        
        # Files panel
        self.files_panel = FilesPanel()
        splitter.addWidget(self.files_panel)
        
        # Set proportions (60% form, 40% files)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)
        
        
        # Job actions
        actions_layout = QHBoxLayout()
        
        self.set_output_btn = QPushButton("Set Output Directory...")
        self.set_output_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                padding: 8px 6px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        actions_layout.addWidget(self.set_output_btn)
        
        self.add_to_queue_btn = QPushButton("Add to Batch Queue")
        self.add_to_queue_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 8px 6px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """)
        actions_layout.addWidget(self.add_to_queue_btn)
        
        self.clear_form_btn = QPushButton("Clear Form/Files")
        actions_layout.addWidget(self.clear_form_btn)
        
        actions_layout.addStretch()
        
        self.load_template_btn = QPushButton("Load Template...")
        actions_layout.addWidget(self.load_template_btn)
        
        layout.addLayout(actions_layout)
        
        # Output directory status - CRITICAL FIX: Use PathLabel to prevent expansion
        self.output_status_label = PathLabel("Output Directory: Not set", max_width=450)
        self.output_status_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-style: italic;
                padding: 4px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: #F5F5F5;
            }
        """)
        # Prevent this label from expanding the parent widget
        self.output_status_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.output_status_label)
        
        return job_setup
        
    def _connect_signals(self):
        """Connect widget signals"""
        # Job setup actions
        self.set_output_btn.clicked.connect(self._set_output_directory)
        self.add_to_queue_btn.clicked.connect(self._add_current_to_queue)
        self.clear_form_btn.clicked.connect(self._clear_form)
        self.load_template_btn.clicked.connect(self._load_template)
        
        # Forward signals from components
        self.files_panel.log_message.connect(self.log_message.emit)
        self.batch_queue_widget.log_message.connect(self.log_message.emit)
        self.batch_queue_widget.queue_status_changed.connect(self.status_message.emit)
        
        # Handle processing state changes to update button states
        self.batch_queue_widget.processing_state_changed.connect(self._on_processing_state_changed)
        
        # Form validation
        self.form_data.occurrence_number = ""  # Reset to trigger validation updates
        
    def _on_processing_state_changed(self, is_processing: bool):
        """Handle processing state changes from batch queue widget"""
        self.add_to_queue_btn.setEnabled(not is_processing)
        
    def _set_output_directory(self):
        """Set the output directory for batch processing"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory for Batch Processing",
            str(self.output_directory) if self.output_directory else "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.output_directory = Path(directory)
            self.set_output_btn.setText(f"Change Output Directory")
            self.set_output_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    padding: 8px 6px;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            
            # Update status label - CRITICAL FIX: Properly handle long directory paths
            self.output_status_label.setText(f"Output Directory: {self.output_directory}")
            self.output_status_label.setStyleSheet("""
                QLabel {
                    color: #2E7D32;
                    font-weight: bold;
                    padding: 4px;
                    border: 1px solid #4CAF50;
                    border-radius: 4px;
                    background-color: #E8F5E8;
                }
            """)
            
            self.log_message.emit(f"Set batch output directory to: {self.output_directory}")
        
    def _add_current_to_queue(self):
        """Add current form configuration to batch queue"""
        # Validate form data
        errors = self.form_data.validate()
        if errors:
            error = UIError(
                f"Batch job validation failed: {', '.join(errors)}",
                user_message="Please fix the following errors before adding to queue:\n\n" + "\n".join(f"• {error}" for error in errors),
                component="BatchTab",
                severity=ErrorSeverity.WARNING
            )
            handle_error(error, {'operation': 'batch_job_validation', 'field_count': len(errors)})
            return
            
        # Validate files/folders
        if not self.files_panel.selected_files and not self.files_panel.selected_folders:
            error = UIError(
                "No files selected for batch job",
                user_message="Please select at least one file or folder to process.",
                component="BatchTab",
                severity=ErrorSeverity.WARNING
            )
            handle_error(error, {'operation': 'batch_file_selection'})
            return
            
        # Check if output directory is set
        if not self.output_directory:
            error = UIError(
                "No output directory set for batch job",
                user_message="Please set an output directory first using the 'Set Output Directory' button.",
                component="BatchTab",
                severity=ErrorSeverity.WARNING
            )
            handle_error(error, {'operation': 'batch_output_directory'})
            return
            
        # Always use forensic mode
        template_type = "forensic"
                
        # Add job to queue
        self.batch_queue_widget.add_job_from_current(
            form_data=self.form_data,
            files=self.files_panel.selected_files,
            folders=self.files_panel.selected_folders,
            output_directory=self.output_directory,
            template_type=template_type
        )
        
        # Clear the files panel after successfully adding to queue
        # This prevents files from accumulating and being added to subsequent jobs
        self.files_panel.clear_all()
        
        self.log_message.emit(f"Added current configuration to batch queue and cleared file selection")
        
    def _clear_form(self):
        """Clear the form and files"""
        # Nuclear migration: Convert to immediate action with success notification
        # Clear form data using model method
        self.form_data.clear()
        
        # Refresh UI from cleared model
        self.form_panel.load_from_data(self.form_data)
            
        # Clear files
        self.files_panel.clear()
        
        # Show success notification
        success_error = UIError(
            "Form and file selection cleared",
            user_message="Form data and file selection have been cleared successfully.",
            component="BatchTab",
            severity=ErrorSeverity.INFO
        )
        handle_error(success_error, {'operation': 'clear_form'})
        
        self.log_message.emit("Cleared form and file selection")
            
    def _load_template(self):
        """Load a job template"""
        # TODO: Implement template loading functionality
        error = UIError(
            "Template loading not yet implemented",
            user_message="Template loading functionality will be implemented in a future update.",
            component="BatchTab",
            severity=ErrorSeverity.INFO
        )
        handle_error(error, {'operation': 'load_template_not_implemented'})
        
    def get_batch_queue_widget(self) -> BatchQueueWidget:
        """Get the batch queue widget"""
        return self.batch_queue_widget
        
    def get_files_panel(self) -> FilesPanel:
        """Get the files panel"""
        return self.files_panel
        
    def get_form_panel(self) -> FormPanel:
        """Get the form panel"""
        return self.form_panel