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
from ui.components import FormPanel, FilesPanel, LogConsole, TemplateSelector


class ForensicTab(QWidget):
    """Forensic mode tab for law enforcement evidence processing"""
    
    # Signals
    process_requested = Signal()
    log_message = Signal(str)
    template_changed = Signal(str)  # template_id
    
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
            lambda: self.log_console.log(f"Calculated offset: {self.form_data.time_offset}")
        )
        
        # Optional: Connect to form_data_changed for validation or live updates
        # self.form_panel.form_data_changed.connect(self._on_form_data_changed)
        
        # Files panel signals
        self.files_panel.log_message.connect(self.log)
        
        # Log console signals (optional: for external monitoring)
        # self.log_console.message_logged.connect(self._on_message_logged)
        # self.log_console.log_cleared.connect(self._on_log_cleared)
        
        # Process button
        self.process_btn.clicked.connect(self.process_requested)
        
        # Template selector signals
        self.template_selector.template_changed.connect(self.template_changed)
        self.template_selector.template_changed.connect(self._on_template_changed)
        
    def log(self, message: str):
        """Forward message to parent via signal
        
        Args:
            message: Message to log
        """
        # Don't log here - parent will handle it to avoid duplication
        # self.log_console.log(message)
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
    
    def _on_template_changed(self, template_id: str):
        """Handle template selection change"""
        template_name = self.template_selector.template_combo.currentText()
        self.log(f"Template changed to: {template_name} ({template_id})")
        
    # Example signal handlers (uncomment to use)
    """
    def _on_form_data_changed(self, field_name: str, value):
        '''Handle form data changes for validation or live updates
        
        Args:
            field_name: Name of the changed field
            value: New value
        '''
        # Example: Validate occurrence number format
        if field_name == 'occurrence_number':
            if value and not value.replace('-', '').isalnum():
                self.log(f"Warning: Occurrence number contains special characters")
        
        # Example: Auto-enable process button when required fields are filled
        if field_name in ['occurrence_number', 'technician_name']:
            can_process = bool(self.form_data.occurrence_number and 
                             self.form_data.technician_name and
                             self.files_panel.has_files())
            self.process_btn.setEnabled(can_process)
    
    def _on_message_logged(self, timestamp: str, message: str):
        '''Handle logged messages for external monitoring
        
        Args:
            timestamp: Time when message was logged
            message: The log message
        '''
        # Example: Could save to external log file or send to monitoring service
        pass
        
    def _on_log_cleared(self):
        '''Handle log clear events'''
        # Example: Could reset any message counters or states
        pass
    """