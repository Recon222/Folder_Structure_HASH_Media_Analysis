#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZIP Settings Dialog for configuring compression options and ZIP behavior
"""

import zipfile
from core.settings_manager import SettingsManager
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QComboBox,
    QRadioButton, QDialogButtonBox, QButtonGroup
)


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
        
        self.setWindowTitle("ZIP Settings")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setFixedHeight(350)
        
        # Create UI
        self._create_ui()
        
        # Load current settings
        self._load_settings()
        
    def _create_ui(self):
        """Create the dialog UI"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
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
        
        # ZIP Creation Behavior group
        behavior_group = QGroupBox("ZIP Creation Behavior")
        behavior_layout = QVBoxLayout()
        
        self.zip_behavior_group = QButtonGroup()
        self.zip_behavior_group.setExclusive(True)
        
        self.zip_enabled_radio = QRadioButton("Enable ZIP Creation")
        self.zip_enabled_radio.setToolTip("Always create ZIP archives")
        behavior_layout.addWidget(self.zip_enabled_radio)
        self.zip_behavior_group.addButton(self.zip_enabled_radio)
        
        self.zip_disabled_radio = QRadioButton("Disable ZIP Creation")
        self.zip_disabled_radio.setToolTip("Never create ZIP archives")
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
        
        # ZIP Archive Level group
        level_group = QGroupBox("ZIP Archive Level")
        level_layout = QVBoxLayout()
        
        self.zip_level_group = QButtonGroup()
        self.zip_level_group.setExclusive(True)
        
        self.root_level_radio = QRadioButton("Root Level (entire structure)")
        self.root_level_radio.setToolTip("Creates single ZIP of entire occurrence folder")
        level_layout.addWidget(self.root_level_radio)
        self.zip_level_group.addButton(self.root_level_radio)
        
        self.location_level_radio = QRadioButton("Location Level (per location folder)")
        self.location_level_radio.setToolTip("Creates ZIP of each location folder")
        level_layout.addWidget(self.location_level_radio)
        self.zip_level_group.addButton(self.location_level_radio)
        
        self.datetime_level_radio = QRadioButton("DateTime Level (per time range folder)")
        self.datetime_level_radio.setToolTip("Creates ZIP of each datetime folder")
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
        
        # ZIP behavior - use new settings
        zip_enabled = self.settings.zip_enabled
        if zip_enabled == 'enabled':
            self.zip_enabled_radio.setChecked(True)
        elif zip_enabled == 'disabled':
            self.zip_disabled_radio.setChecked(True)
        else:  # 'prompt'
            self.zip_prompt_radio.setChecked(True)
            
        # ZIP level - use new settings
        zip_level = self.settings.zip_level
        if zip_level == 'root':
            self.root_level_radio.setChecked(True)
        elif zip_level == 'location':
            self.location_level_radio.setChecked(True)
        else:  # 'datetime'
            self.datetime_level_radio.setChecked(True)
            
        # Update enable/disable state
        self._on_zip_behavior_changed()
        
    def _on_zip_behavior_changed(self):
        """Handle ZIP behavior radio button changes"""
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
        
        # ZIP behavior - use new settings keys
        if self.zip_enabled_radio.isChecked():
            zip_enabled = 'enabled'
        elif self.zip_disabled_radio.isChecked():
            zip_enabled = 'disabled'
        else:  # prompt radio
            zip_enabled = 'prompt'
            
        self.settings.set('ZIP_ENABLED', zip_enabled)
        
        # ZIP level - use new settings keys
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