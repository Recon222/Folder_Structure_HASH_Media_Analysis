#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZIP Settings Dialog for configuring compression options
"""

import zipfile
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QComboBox,
    QCheckBox, QDialogButtonBox
)


class ZipSettingsDialog(QDialog):
    """Dialog for configuring ZIP compression settings"""
    
    def __init__(self, settings: QSettings, parent=None):
        """Initialize ZIP settings dialog
        
        Args:
            settings: QSettings instance for storing preferences
            parent: Parent widget
        """
        super().__init__(parent)
        self.settings = settings
        
        self.setWindowTitle("ZIP Settings")
        self.setModal(True)
        self.setMinimumWidth(300)
        
        # Create UI
        self._create_ui()
        
        # Load current settings
        self._load_settings()
        
    def _create_ui(self):
        """Create the dialog UI"""
        layout = QVBoxLayout()
        
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
        
        # Create levels group
        level_group = QGroupBox("Create ZIP at Levels")
        level_layout = QVBoxLayout()
        
        self.zip_root_check = QCheckBox("Root Level (entire structure)")
        level_layout.addWidget(self.zip_root_check)
        
        self.zip_location_check = QCheckBox("Location Level (per location)")
        level_layout.addWidget(self.zip_location_check)
        
        self.zip_datetime_check = QCheckBox("DateTime Level (per time range)")
        level_layout.addWidget(self.zip_datetime_check)
        
        level_group.setLayout(level_layout)
        layout.addWidget(level_group)
        
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
        comp_value = self.settings.value('zip_compression', 0)
        self.comp_combo.setCurrentIndex(comp_value)
        
        # ZIP levels
        self.zip_root_check.setChecked(
            self.settings.value('zip_at_root', True, type=bool)
        )
        self.zip_location_check.setChecked(
            self.settings.value('zip_at_location', False, type=bool)
        )
        self.zip_datetime_check.setChecked(
            self.settings.value('zip_at_datetime', False, type=bool)
        )
        
    def save_settings(self):
        """Save settings when dialog is accepted"""
        # Compression level
        comp_index = self.comp_combo.currentIndex()
        comp_level = 0 if comp_index == 0 else zipfile.ZIP_DEFLATED
        
        self.settings.setValue('zip_compression', comp_index)
        self.settings.setValue('zip_compression_level', comp_level)
        
        # ZIP levels
        self.settings.setValue('zip_at_root', self.zip_root_check.isChecked())
        self.settings.setValue('zip_at_location', self.zip_location_check.isChecked())
        self.settings.setValue('zip_at_datetime', self.zip_datetime_check.isChecked())