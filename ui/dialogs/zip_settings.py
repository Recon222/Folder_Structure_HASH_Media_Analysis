#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZIP Settings Dialog for configuring compression options and ZIP behavior
"""

import zipfile
from core.settings_manager import SettingsManager
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QComboBox, QLabel,
    QRadioButton, QDialogButtonBox, QButtonGroup, QHBoxLayout
)
from PySide6.QtCore import Qt
from utils.zip_utils import ArchiveMethod


class ZipSettingsDialog(QDialog):
    """Dialog for configuring ZIP compression settings and behavior"""
    
    def __init__(self, settings: SettingsManager, parent=None):
        """Initialize ZIP settings dialog
        
        Args:
            settings: SettingsManager instance for storing preferences
            parent: Parent widget
        """
        super().__init__(parent)
        self.settings = settings
        
        self.setWindowTitle("Archive Settings")
        self.setModal(True)
        self.setMinimumWidth(550)  # Increased width to accommodate performance text
        self.setFixedHeight(580)  # Increased height for better spacing in archive method section
        
        # Create UI
        self._create_ui()
        
        # Load current settings
        self._load_settings()
        
    def _create_ui(self):
        """Create the dialog UI"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Archive Method group (highest priority - at top)
        method_group = QGroupBox("Archive Method")
        method_layout = QVBoxLayout()  # No custom spacing - match other sections
        
        self.archive_method_group = QButtonGroup()
        self.archive_method_group.setExclusive(True)
        
        # Native 7zip option (default)
        self.native_7zip_radio = QRadioButton("Native 7-Zip (Fastest)")
        self.native_7zip_radio.setToolTip("7-14x faster using native 7za.exe (2,000-4,000 MB/s). Creates .zip archives.")
        method_layout.addWidget(self.native_7zip_radio)
        self.archive_method_group.addButton(self.native_7zip_radio)
        
        # Add performance label for 7zip
        native_perf_label = QLabel("   → Expected: 2,000-4,000 MB/s | Format: .zip")
        native_perf_label.setStyleSheet("color: #2E8B57; font-size: 11px; font-style: italic;")
        method_layout.addWidget(native_perf_label)
        
        # Buffered Python option
        self.buffered_python_radio = QRadioButton("Buffered Python (Fast)")
        self.buffered_python_radio.setToolTip("High-performance Python implementation (290 MB/s). Creates .zip archives.")
        method_layout.addWidget(self.buffered_python_radio)
        self.archive_method_group.addButton(self.buffered_python_radio)
        
        # Add performance label for buffered
        buffered_perf_label = QLabel("   → Expected: 290 MB/s | Format: .zip")
        buffered_perf_label.setStyleSheet("color: #4682B4; font-size: 11px; font-style: italic;")
        method_layout.addWidget(buffered_perf_label)
        
        # Auto selection option
        self.auto_method_radio = QRadioButton("Automatic Selection")
        self.auto_method_radio.setToolTip("Automatically selects the best available method for optimal performance.")
        method_layout.addWidget(self.auto_method_radio)
        self.archive_method_group.addButton(self.auto_method_radio)
        
        # Add auto info label
        auto_info_label = QLabel("   → Uses Native 7-Zip if available, falls back to Buffered Python")
        auto_info_label.setStyleSheet("color: #696969; font-size: 11px; font-style: italic;")
        method_layout.addWidget(auto_info_label)
        
        # Connect method change signal
        self.native_7zip_radio.toggled.connect(self._on_archive_method_changed)
        self.buffered_python_radio.toggled.connect(self._on_archive_method_changed)
        self.auto_method_radio.toggled.connect(self._on_archive_method_changed)
        
        method_group.setLayout(method_layout)
        layout.addWidget(method_group)
        
        # Compression level group
        comp_group = QGroupBox("Compression Level")
        comp_layout = QVBoxLayout()
        
        self.comp_combo = QComboBox()
        self.comp_combo.addItems([
            "No Compression (Fastest)",
            "Compressed (Smaller)"
        ])
        comp_layout.addWidget(self.comp_combo)
        
        comp_group.setLayout(comp_layout)
        layout.addWidget(comp_group)
        
        # Archive Creation Behavior group
        behavior_group = QGroupBox("Archive Creation Behavior")
        behavior_layout = QVBoxLayout()
        
        self.zip_behavior_group = QButtonGroup()
        self.zip_behavior_group.setExclusive(True)
        
        self.zip_enabled_radio = QRadioButton("Enable Archive Creation")
        self.zip_enabled_radio.setToolTip("Always create archives")
        behavior_layout.addWidget(self.zip_enabled_radio)
        self.zip_behavior_group.addButton(self.zip_enabled_radio)
        
        self.zip_disabled_radio = QRadioButton("Disable Archive Creation")
        self.zip_disabled_radio.setToolTip("Never create archives")
        behavior_layout.addWidget(self.zip_disabled_radio)
        self.zip_behavior_group.addButton(self.zip_disabled_radio)
        
        self.zip_prompt_radio = QRadioButton("Prompt Each Time")
        self.zip_prompt_radio.setToolTip("Ask before each operation")
        behavior_layout.addWidget(self.zip_prompt_radio)
        self.zip_behavior_group.addButton(self.zip_prompt_radio)
        
        # Connect behavior change signal
        self.zip_disabled_radio.toggled.connect(self._on_zip_behavior_changed)
        
        behavior_group.setLayout(behavior_layout)
        layout.addWidget(behavior_group)
        
        # Archive Level group
        level_group = QGroupBox("Archive Level")
        level_layout = QVBoxLayout()
        
        self.zip_level_group = QButtonGroup()
        self.zip_level_group.setExclusive(True)
        
        self.root_level_radio = QRadioButton("Root Level (entire structure)")
        self.root_level_radio.setToolTip("Creates single archive of entire occurrence folder")
        level_layout.addWidget(self.root_level_radio)
        self.zip_level_group.addButton(self.root_level_radio)
        
        self.location_level_radio = QRadioButton("Location Level (per location folder)")
        self.location_level_radio.setToolTip("Creates archive of each location folder")
        level_layout.addWidget(self.location_level_radio)
        self.zip_level_group.addButton(self.location_level_radio)
        
        self.datetime_level_radio = QRadioButton("DateTime Level (per time range folder)")
        self.datetime_level_radio.setToolTip("Creates archive of each datetime folder")
        level_layout.addWidget(self.datetime_level_radio)
        self.zip_level_group.addButton(self.datetime_level_radio)
        
        level_group.setLayout(level_layout)
        layout.addWidget(level_group)
        
        # Store level group for enable/disable logic
        self.level_group_widget = level_group
        
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
        # Compression level
        comp_value = self.settings.get('ZIP_COMPRESSION', 0)
        self.comp_combo.setCurrentIndex(comp_value)
        
        # Archive method - load from settings
        archive_method = self.settings.archive_method
        if archive_method == 'native_7zip':
            self.native_7zip_radio.setChecked(True)
        elif archive_method == 'buffered_python':
            self.buffered_python_radio.setChecked(True)
        else:  # 'auto'
            self.auto_method_radio.setChecked(True)
            
        # Archive behavior - use new settings
        zip_enabled = self.settings.zip_enabled
        if zip_enabled == 'enabled':
            self.zip_enabled_radio.setChecked(True)
        elif zip_enabled == 'disabled':
            self.zip_disabled_radio.setChecked(True)
        else:  # 'prompt'
            self.zip_prompt_radio.setChecked(True)
            
        # Archive level - use new settings
        zip_level = self.settings.zip_level
        if zip_level == 'root':
            self.root_level_radio.setChecked(True)
        elif zip_level == 'location':
            self.location_level_radio.setChecked(True)
        else:  # 'datetime'
            self.datetime_level_radio.setChecked(True)
            
        # Update enable/disable state
        self._on_zip_behavior_changed()
        self._on_archive_method_changed()
        
    def _on_archive_method_changed(self):
        """Handle archive method radio button changes"""
        # Could add method-specific UI updates here
        # For now, just log the change
        method = self._get_selected_archive_method()
        if hasattr(self, 'settings'):
            # Preview the change (could show estimated performance)
            pass
    
    def _get_selected_archive_method(self) -> str:
        """Get currently selected archive method"""
        if self.native_7zip_radio.isChecked():
            return 'native_7zip'
        elif self.buffered_python_radio.isChecked():
            return 'buffered_python'
        else:
            return 'auto'
    
    def _on_zip_behavior_changed(self):
        """Handle archive behavior radio button changes"""
        disabled = self.zip_disabled_radio.isChecked()
        
        # Enable/disable the level options based on behavior choice
        self.root_level_radio.setEnabled(not disabled)
        self.location_level_radio.setEnabled(not disabled)
        self.datetime_level_radio.setEnabled(not disabled)
        self.level_group_widget.setEnabled(not disabled)
        
    def save_settings(self):
        """Save settings when dialog is accepted"""
        # Compression level
        comp_index = self.comp_combo.currentIndex()
        comp_level = 0 if comp_index == 0 else zipfile.ZIP_DEFLATED
        
        self.settings.set('ZIP_COMPRESSION', comp_index)
        self.settings.set('ZIP_COMPRESSION_LEVEL', comp_level)
        
        # Archive method - save to settings
        archive_method = self._get_selected_archive_method()
        self.settings.archive_method = archive_method
        
        # Archive behavior - use new settings keys
        if self.zip_enabled_radio.isChecked():
            zip_enabled = 'enabled'
        elif self.zip_disabled_radio.isChecked():
            zip_enabled = 'disabled'
        else:  # prompt radio
            zip_enabled = 'prompt'
            
        self.settings.set('ZIP_ENABLED', zip_enabled)
        
        # Archive level - use new settings keys
        if self.root_level_radio.isChecked():
            zip_level = 'root'
        elif self.location_level_radio.isChecked():
            zip_level = 'location'
        else:  # datetime radio
            zip_level = 'datetime'
            
        self.settings.set('ZIP_LEVEL', zip_level)
        
        # Sync settings to disk
        self.settings.sync()
    
    def accept(self):
        """Override accept to save settings"""
        self.save_settings()
        super().accept()