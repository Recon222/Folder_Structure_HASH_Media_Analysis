#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
User Settings Dialog for configuring application preferences
"""

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QCheckBox,
    QDialogButtonBox, QLabel, QSpinBox, QHBoxLayout
)


class UserSettingsDialog(QDialog):
    """Dialog for configuring user preferences"""
    
    def __init__(self, settings: QSettings, parent=None):
        """Initialize user settings dialog
        
        Args:
            settings: QSettings instance for storing preferences
            parent: Parent widget
        """
        super().__init__(parent)
        self.settings = settings
        
        self.setWindowTitle("User Settings")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        # Create UI
        self._create_ui()
        
        # Load current settings
        self._load_settings()
        
    def _create_ui(self):
        """Create the dialog UI"""
        layout = QVBoxLayout()
        
        # File Operations group
        file_group = QGroupBox("File Operations")
        file_layout = QVBoxLayout()
        
        # Hash verification toggle
        self.hash_check = QCheckBox("Calculate SHA-256 hashes during file copy")
        self.hash_check.setToolTip(
            "Enable hash calculation for file integrity verification.\n"
            "Disabling this will significantly speed up file copying\n"
            "but won't provide integrity verification."
        )
        file_layout.addWidget(self.hash_check)
        
        # Hash verification info
        hash_info = QLabel(
            "Note: Disabling hash calculation will improve performance\n"
            "but forensic integrity verification will not be available."
        )
        hash_info.setStyleSheet("color: gray; font-size: 10pt;")
        hash_info.setWordWrap(True)
        file_layout.addWidget(hash_info)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # Performance group
        perf_group = QGroupBox("Performance")
        perf_layout = QVBoxLayout()
        
        # Buffer size setting
        buffer_layout = QHBoxLayout()
        buffer_label = QLabel("File copy buffer size (KB):")
        buffer_layout.addWidget(buffer_label)
        
        self.buffer_spin = QSpinBox()
        self.buffer_spin.setMinimum(64)
        self.buffer_spin.setMaximum(8192)
        self.buffer_spin.setSingleStep(64)
        self.buffer_spin.setSuffix(" KB")
        self.buffer_spin.setToolTip(
            "Larger buffer sizes may improve performance for large files.\n"
            "Default: 1024 KB"
        )
        buffer_layout.addWidget(self.buffer_spin)
        buffer_layout.addStretch()
        
        perf_layout.addLayout(buffer_layout)
        
        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)
        
        # UI Behavior group
        ui_group = QGroupBox("User Interface")
        ui_layout = QVBoxLayout()
        
        self.auto_scroll_check = QCheckBox("Auto-scroll log console")
        self.auto_scroll_check.setToolTip(
            "Automatically scroll to the bottom of the log console\n"
            "when new messages are added."
        )
        ui_layout.addWidget(self.auto_scroll_check)
        
        self.confirm_exit_check = QCheckBox("Confirm before closing with active operations")
        self.confirm_exit_check.setToolTip(
            "Show a confirmation dialog when closing the application\n"
            "while file operations are in progress."
        )
        ui_layout.addWidget(self.confirm_exit_check)
        
        ui_group.setLayout(ui_layout)
        layout.addWidget(ui_group)
        
        layout.addStretch()
        
        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
        
    def _load_settings(self):
        """Load current settings into the dialog"""
        # File operations
        self.hash_check.setChecked(
            self.settings.value('calculate_hashes', True, type=bool)
        )
        
        # Performance
        self.buffer_spin.setValue(
            self.settings.value('copy_buffer_size', 1024, type=int)
        )
        
        # UI behavior
        self.auto_scroll_check.setChecked(
            self.settings.value('auto_scroll_log', True, type=bool)
        )
        self.confirm_exit_check.setChecked(
            self.settings.value('confirm_exit_with_operations', True, type=bool)
        )
        
    def save_settings(self):
        """Save settings when dialog is accepted"""
        # File operations
        self.settings.setValue('calculate_hashes', self.hash_check.isChecked())
        
        # Performance
        self.settings.setValue('copy_buffer_size', self.buffer_spin.value())
        
        # UI behavior
        self.settings.setValue('auto_scroll_log', self.auto_scroll_check.isChecked())
        self.settings.setValue('confirm_exit_with_operations', self.confirm_exit_check.isChecked())