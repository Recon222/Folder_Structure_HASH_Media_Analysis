#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Forensic Tab - Law enforcement mode interface
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSplitter
)

from core.models import FormData
from ui.components import FormPanel, FilesPanel, LogConsole


class ForensicTab(QWidget):
    """Forensic mode tab for law enforcement evidence processing"""
    
    # Signals
    process_requested = Signal()
    log_message = Signal(str)
    
    def __init__(self, form_data: FormData, parent=None):
        """Initialize forensic tab
        
        Args:
            form_data: FormData instance to bind to
            parent: Parent widget
        """
        super().__init__(parent)
        self.form_data = form_data
        
        self._create_ui()
        self._connect_signals()
        
    def _create_ui(self):
        """Create the tab UI"""
        layout = QVBoxLayout(self)
        
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
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.process_btn = QPushButton("Process Files")
        button_layout.addWidget(self.process_btn)
        
        layout.addLayout(button_layout)
        
    def _connect_signals(self):
        """Connect internal signals"""
        # Form panel signals
        self.form_panel.calculate_offset_requested.connect(
            lambda: self.log_console.log(f"Calculated offset: {self.form_data.time_offset} minutes")
        )
        
        # Files panel signals
        self.files_panel.log_message.connect(self.log)
        
        # Process button
        self.process_btn.clicked.connect(self.process_requested)
        
    def log(self, message: str):
        """Log a message to the console and emit signal
        
        Args:
            message: Message to log
        """
        self.log_console.log(message)
        self.log_message.emit(message)
        
    def get_selected_files(self):
        """Get files and folders from the files panel
        
        Returns:
            Tuple of (files_list, folders_list)
        """
        return self.files_panel.get_files(), self.files_panel.get_folders()
        
    def set_process_button_enabled(self, enabled: bool):
        """Enable or disable the process button
        
        Args:
            enabled: Whether to enable the button
        """
        self.process_btn.setEnabled(enabled)