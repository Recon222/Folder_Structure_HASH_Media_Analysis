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
from typing import Optional
import logging

from core.models import FormData
from ui.components import FormPanel, FilesPanel, LogConsole, TemplateSelector
from core.services.service_registry import get_service
from core.services.interfaces import IResourceManagementService, ResourceType


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
        
        # Processing state management
        self.processing_active = False
        self.current_thread = None  # Will hold FolderStructureThread reference
        self.is_paused = False
        
        # Resource management
        self._resource_manager = None
        self._worker_resource_id = None
        self.logger = logging.getLogger(__name__)
        
        # Register with ResourceManagementService
        self._register_with_resource_manager()
        
        self._create_ui()
        self._connect_signals()
    
    def _register_with_resource_manager(self):
        """Register this tab with the resource management service"""
        try:
            self._resource_manager = get_service(IResourceManagementService)
            if self._resource_manager:
                self._resource_manager.register_component(
                    self, 
                    "ForensicTab", 
                    "tab"
                )
                # Register cleanup callback
                self._resource_manager.register_cleanup(
                    self,
                    self._cleanup_resources,
                    priority=10
                )
                self.logger.info("ForensicTab registered with ResourceManagementService")
        except Exception as e:
            self.logger.warning(f"Could not register ForensicTab with ResourceManagementService: {e}")
            self._resource_manager = None
        
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
        
        # Process button (left) - green like batch tab
        self.process_btn = QPushButton("Process Files")
        self.process_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; min-width: 120px; }")
        button_layout.addWidget(self.process_btn)
        
        # Pause button (middle) - disabled initially, blue when active  
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setEnabled(False)
        button_layout.addWidget(self.pause_btn)
        
        # Cancel button (right) - red like batch tab
        self.cancel_btn = QPushButton("Cancel") 
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        button_layout.addWidget(self.cancel_btn)
        
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
        
        # Control buttons
        self.pause_btn.clicked.connect(self._pause_processing)
        self.cancel_btn.clicked.connect(self._cancel_processing)
        
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
    
    def _update_ui_for_processing_state(self):
        """Update UI elements based on processing state"""
        # Process button: enabled when not processing
        self.process_btn.setEnabled(not self.processing_active)
        
        # Pause button: enabled when processing, blue when active
        self.pause_btn.setEnabled(self.processing_active)
        if self.processing_active:
            if self.is_paused:
                self.pause_btn.setText("Resume")
                self.pause_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; }")
            else:
                self.pause_btn.setText("Pause")
                self.pause_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; }")
        else:
            self.pause_btn.setText("Pause")
            self.pause_btn.setStyleSheet("")  # Reset to default
        
        # Cancel button: enabled when processing
        self.cancel_btn.setEnabled(self.processing_active)
    
    def set_processing_state(self, active: bool, thread=None):
        """Set processing state and update UI
        
        Args:
            active: Whether processing is active
            thread: Current thread reference (FolderStructureThread)
        """
        self.processing_active = active
        
        # Handle resource tracking for the worker thread
        if active and thread:
            # Release any existing worker resource before tracking new one
            self._release_worker_resource()
            
            # Track the new worker thread
            self.current_thread = thread
            if self._resource_manager:
                self._worker_resource_id = self._resource_manager.track_resource(
                    self,
                    ResourceType.WORKER,
                    thread,
                    metadata={
                        'type': 'FolderStructureThread',
                        'cleanup_func': lambda w: w.cancel() if w and w.isRunning() else None
                    }
                )
                self.logger.debug(f"Tracked FolderStructureThread worker: {self._worker_resource_id}")
        else:
            # Processing stopped - release worker resource
            self._release_worker_resource()
            self.current_thread = None
            self.is_paused = False  # Reset pause state when processing stops
            
        self._update_ui_for_processing_state()
    
    def set_paused_state(self, paused: bool):
        """Set paused state and update UI
        
        Args:
            paused: Whether processing is paused
        """
        self.is_paused = paused
        self._update_ui_for_processing_state()
    
    def _pause_processing(self):
        """Handle pause/resume button click"""
        if not self.current_thread or not self.processing_active:
            return
            
        if self.is_paused:
            # Resume processing
            if hasattr(self.current_thread, 'resume'):
                self.current_thread.resume()
            self.set_paused_state(False)
            self.log_message.emit("Resumed forensic processing")
        else:
            # Pause processing  
            if hasattr(self.current_thread, 'pause'):
                self.current_thread.pause()
            self.set_paused_state(True)
            self.log_message.emit("Paused forensic processing")
    
    def _cancel_processing(self):
        """Handle cancel button click"""
        if not self.current_thread or not self.processing_active:
            return
            
        # Cancel the current operation
        if hasattr(self.current_thread, 'cancel'):
            self.current_thread.cancel()
        elif hasattr(self.current_thread, 'cancelled'):
            # Fallback to direct flag setting
            self.current_thread.cancelled = True
            
        self.log_message.emit("Cancelled forensic processing - operation will stop soon")
        
        # Note: The actual state reset will happen when the thread finishes
        # and calls the completion handlers in MainWindow
    
    def _on_template_changed(self, template_id: str):
        """Handle template selection change"""
        template_name = self.template_selector.template_combo.currentText()
        self.log(f"Template changed to: {template_name} ({template_id})")
    
    def _cleanup_resources(self):
        """Clean up tab-specific resources (called by ResourceManagementService)"""
        self.logger.info("Cleaning up ForensicTab resources")
        
        # Cancel any running operation
        if self.current_thread:
            if hasattr(self.current_thread, 'cancel'):
                self.current_thread.cancel()
            # Release the worker resource
            self._release_worker_resource()
            self.current_thread = None
        
        # Reset state
        self.processing_active = False
        self.is_paused = False
        
        # Clear log console if it has a clear method
        if hasattr(self.log_console, 'clear'):
            self.log_console.clear()
        
        self.logger.info("ForensicTab cleanup complete")
    
    def _release_worker_resource(self):
        """Helper to release tracked worker resource"""
        if self._worker_resource_id and self._resource_manager:
            self._resource_manager.release_resource(self, self._worker_resource_id)
            self._worker_resource_id = None
            self.logger.debug("Released worker resource")
        
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