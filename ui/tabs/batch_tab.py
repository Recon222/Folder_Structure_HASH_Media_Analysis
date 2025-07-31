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
    QSplitter, QGroupBox, QMessageBox, QFileDialog, QLabel,
    QComboBox
)

from core.models import FormData
from ui.components import FormPanel, FilesPanel, LogConsole
from ui.components.batch_queue_widget import BatchQueueWidget


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
        layout.addWidget(main_splitter)
        
        # Left side: Job setup panel
        job_setup_widget = self._create_job_setup_panel()
        main_splitter.addWidget(job_setup_widget)
        
        # Right side: Batch queue
        self.batch_queue_widget = BatchQueueWidget(self)
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
                padding: 8px 16px;
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
                padding: 8px 16px;
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
        
        self.clear_form_btn = QPushButton("Clear Form")
        actions_layout.addWidget(self.clear_form_btn)
        
        actions_layout.addStretch()
        
        self.load_template_btn = QPushButton("Load Template...")
        actions_layout.addWidget(self.load_template_btn)
        
        layout.addLayout(actions_layout)
        
        # Output directory status
        self.output_status_label = QLabel("Output Directory: Not set")
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
        
        # Form validation
        self.form_data.occurrence_number = ""  # Reset to trigger validation updates
        
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
                    padding: 8px 16px;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            
            # Update status label
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
            QMessageBox.warning(
                self, "Validation Error", 
                "Please fix the following errors before adding to queue:\n\n" + 
                "\n".join(f"• {error}" for error in errors)
            )
            return
            
        # Validate files/folders
        if not self.files_panel.selected_files and not self.files_panel.selected_folders:
            QMessageBox.warning(
                self, "No Files Selected",
                "Please select at least one file or folder to process."
            )
            return
            
        # Check if output directory is set
        if not self.output_directory:
            QMessageBox.warning(
                self, "No Output Directory",
                "Please set an output directory first using the 'Set Output Directory' button."
            )
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
        
        self.log_message.emit(f"Added current configuration to batch queue")
        
    def _clear_form(self):
        """Clear the form and files"""
        reply = QMessageBox.question(
            self, "Clear Form",
            "Clear all form data and selected files?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Clear form data
            self.form_data.occurrence_number = ""
            self.form_data.business_name = ""
            self.form_data.location_address = ""
            self.form_data.time_offset = ""
            self.form_data.extraction_start = None
            self.form_data.extraction_end = None
            self.form_data.dvr_time = None
            self.form_data.real_time = None
            self.form_data.upload_timestamp = None
            
            # Clear files
            self.files_panel.clear()
            
            self.log_message.emit("Cleared form and file selection")
            
    def _load_template(self):
        """Load a job template"""
        # TODO: Implement template loading functionality
        QMessageBox.information(
            self, "Load Template",
            "Template loading functionality will be implemented in a future update."
        )
        
    def get_batch_queue_widget(self) -> BatchQueueWidget:
        """Get the batch queue widget"""
        return self.batch_queue_widget
        
    def get_files_panel(self) -> FilesPanel:
        """Get the files panel"""
        return self.files_panel
        
    def get_form_panel(self) -> FormPanel:
        """Get the form panel"""
        return self.form_panel