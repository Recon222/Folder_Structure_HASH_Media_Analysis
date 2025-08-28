#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
User Settings Dialog for configuring application preferences
"""

from core.settings_manager import SettingsManager
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QCheckBox,
    QDialogButtonBox, QLabel, QSpinBox, QHBoxLayout,
    QTabWidget, QWidget, QLineEdit, QFormLayout
)


class UserSettingsDialog(QDialog):
    """Dialog for configuring user preferences"""
    
    def __init__(self, settings: SettingsManager, parent=None):
        """Initialize user settings dialog
        
        Args:
            settings: SettingsManager instance for storing preferences
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
        
        # Create tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Create tabs
        self._create_general_tab()
        self._create_analyst_tab()
        self._create_documentation_tab()
        self._create_performance_tab()
        
        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def _create_general_tab(self):
        """Create the general settings tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        
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
        tab.setLayout(layout)
        self.tabs.addTab(tab, "General")
    
    def _create_analyst_tab(self):
        """Create the analyst/technician settings tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Analyst Information group
        analyst_group = QGroupBox("Analyst/Technician Information")
        analyst_layout = QFormLayout()
        
        # Name field
        self.tech_name_edit = QLineEdit()
        self.tech_name_edit.setPlaceholderText("Enter your full name")
        analyst_layout.addRow("Name:", self.tech_name_edit)
        
        # Badge number field
        self.badge_edit = QLineEdit()
        self.badge_edit.setPlaceholderText("Enter your badge number")
        analyst_layout.addRow("Badge #:", self.badge_edit)
        
        analyst_group.setLayout(analyst_layout)
        layout.addWidget(analyst_group)
        
        # Info label
        info_label = QLabel(
            "This information will be automatically included in:\n"
            "• Upload receipts (always)\n"
            "• Time offset documents (when checkbox is selected)\n\n"
            "The information is saved and will persist between sessions."
        )
        info_label.setStyleSheet("color: gray; font-size: 10pt;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        layout.addStretch()
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Analyst/Technician")
    
    def _create_documentation_tab(self):
        """Create the documentation settings tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # PDF Generation group
        pdf_group = QGroupBox("PDF Document Generation")
        pdf_layout = QVBoxLayout()
        
        # Checkboxes for each PDF type
        self.generate_time_offset_check = QCheckBox("Generate Time Offset Report")
        self.generate_time_offset_check.setToolTip(
            "Automatically generate a time offset report PDF after file operations"
        )
        pdf_layout.addWidget(self.generate_time_offset_check)
        
        self.generate_upload_log_check = QCheckBox("Generate Upload Log")
        self.generate_upload_log_check.setToolTip(
            "Automatically generate an upload log PDF after file operations"
        )
        pdf_layout.addWidget(self.generate_upload_log_check)
        
        pdf_group.setLayout(pdf_layout)
        layout.addWidget(pdf_group)
        
        # File Integrity group
        integrity_group = QGroupBox("File Integrity Verification")
        integrity_layout = QVBoxLayout()
        
        # Combined hash calculation and CSV generation
        self.generate_hash_csv_check = QCheckBox("Calculate SHA-256 hashes and generate verification CSV")
        self.generate_hash_csv_check.setToolTip(
            "Enable SHA-256 hash calculation during file copy and\n"
            "automatically generate a CSV file with verification results.\n"
            "Disabling this will improve copy speed but forensic\n"
            "integrity verification will not be available."
        )
        integrity_layout.addWidget(self.generate_hash_csv_check)
        
        # Hash info
        hash_info = QLabel(
            "Note: SHA-256 hashing ensures forensic integrity but may\n"
            "slow down file operations on large datasets."
        )
        hash_info.setStyleSheet("color: gray; font-size: 10pt;")
        hash_info.setWordWrap(True)
        integrity_layout.addWidget(hash_info)
        
        integrity_group.setLayout(integrity_layout)
        layout.addWidget(integrity_group)
        
        # Info label
        info_label = QLabel(
            "These settings control which documents are automatically generated\n"
            "after file operations complete. Documents will be saved in the\n"
            "Documents folder within your output directory.\n\n"
            "Note: Documents are generated immediately after file copying\n"
            "completes to ensure accurate timestamps."
        )
        info_label.setStyleSheet("color: gray; font-size: 10pt;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        layout.addStretch()
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Documentation")
    
    def _create_performance_tab(self):
        """Create Performance tab for advanced performance settings"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # High-Performance Mode group
        perf_mode_group = QGroupBox("High-Performance Mode")
        perf_mode_layout = QVBoxLayout()
        
        # Performance mode information (always enabled)
        buffered_ops_label = QLabel("✅ High-performance buffered operations: Always Enabled")
        buffered_ops_label.setToolTip(
            "High-performance operations are now always enabled for optimal performance:\n"
            "• Small files (<1MB): Direct copy for speed\n"
            "• Medium files (1-100MB): Buffered streaming\n"
            "• Large files (>100MB): Large buffer streaming"
        )
        buffered_ops_label.setStyleSheet("color: #2e7d32; font-weight: bold;")
        perf_mode_layout.addWidget(buffered_ops_label)
        
        # Performance info label
        info_label = QLabel(
            "When enabled, the application will use:\n"
            "• Intelligent file size detection\n"
            "• Streaming copy for large files\n"
            "• Byte-level progress reporting\n"
            "• Memory-efficient operations"
        )
        info_label.setStyleSheet("color: gray; font-size: 9pt; margin-left: 20px;")
        perf_mode_layout.addWidget(info_label)
        
        perf_mode_group.setLayout(perf_mode_layout)
        layout.addWidget(perf_mode_group)
        
        # Buffer Size group (existing, but enhanced)
        buffer_group = QGroupBox("Buffer Configuration")
        buffer_layout = QVBoxLayout()
        
        # Buffer size setting
        buffer_size_layout = QHBoxLayout()
        buffer_label = QLabel("File copy buffer size:")
        buffer_size_layout.addWidget(buffer_label)
        
        self.perf_buffer_spin = QSpinBox()
        self.perf_buffer_spin.setMinimum(8)
        self.perf_buffer_spin.setMaximum(10240)
        self.perf_buffer_spin.setSingleStep(256)
        self.perf_buffer_spin.setSuffix(" KB")
        self.perf_buffer_spin.setToolTip(
            "Buffer size for streaming operations.\n"
            "• 8-512 KB: Good for many small files\n"
            "• 512-2048 KB: Balanced (recommended)\n"
            "• 2048-10240 KB: Best for large files\n"
            "Default: 1024 KB"
        )
        buffer_size_layout.addWidget(self.perf_buffer_spin)
        buffer_size_layout.addStretch()
        
        buffer_layout.addLayout(buffer_size_layout)
        
        # Buffer size recommendation label
        rec_label = QLabel(
            "Larger buffers improve performance for large files but use more memory.\n"
            "The system automatically adjusts buffer usage based on file size."
        )
        rec_label.setStyleSheet("color: gray; font-size: 9pt;")
        rec_label.setWordWrap(True)
        buffer_layout.addWidget(rec_label)
        
        buffer_group.setLayout(buffer_layout)
        layout.addWidget(buffer_group)
        
        # Performance Monitoring group
        monitor_group = QGroupBox("Performance Monitoring")
        monitor_layout = QVBoxLayout()
        
        monitor_info = QLabel(
            "Access real-time performance monitoring from:\n"
            "Settings → Performance Monitor\n\n"
            "Monitor shows:\n"
            "• Real-time transfer speeds\n"
            "• File size distribution\n"
            "• Performance graphs\n"
            "• Detailed metrics report"
        )
        monitor_info.setStyleSheet("color: gray; font-size: 9pt;")
        monitor_layout.addWidget(monitor_info)
        
        monitor_group.setLayout(monitor_layout)
        layout.addWidget(monitor_group)
        
        layout.addStretch()
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Performance")
        
    def _load_settings(self):
        """Load current settings into the dialog"""
        
        # Performance tab settings
        # (Buffered operations are now always enabled)
        # Convert buffer size from bytes to KB for display
        buffer_size_kb = self.settings.copy_buffer_size // 1024
        self.perf_buffer_spin.setValue(buffer_size_kb)
        
        # UI behavior
        self.auto_scroll_check.setChecked(
            bool(self.settings.get('auto_scroll_log', True))
        )
        self.confirm_exit_check.setChecked(
            bool(self.settings.get('confirm_exit_with_operations', True))
        )
        
        # Analyst/Technician info
        self.tech_name_edit.setText(
            self.settings.get('technician_name', '')
        )
        self.badge_edit.setText(
            self.settings.get('badge_number', '')
        )
        
        # Documentation settings - Use properties like working ZIP/buffer settings
        self.generate_time_offset_check.setChecked(
            self.settings.generate_time_offset_pdf
        )
        self.generate_upload_log_check.setChecked(
            self.settings.generate_upload_log_pdf
        )
        # Use calculate_hashes as the main setting for hash/CSV generation
        self.generate_hash_csv_check.setChecked(
            self.settings.calculate_hashes
        )
        
    def save_settings(self):
        """Save settings when dialog is accepted"""
        
        # Performance tab settings
        # Buffered operations are now always enabled (no setting needed)
        # Convert KB to bytes for storage
        buffer_size_bytes = self.perf_buffer_spin.value() * 1024
        self.settings.set('COPY_BUFFER_SIZE', buffer_size_bytes)
        
        # UI behavior
        self.settings.set('auto_scroll_log', self.auto_scroll_check.isChecked())
        self.settings.set('confirm_exit_with_operations', self.confirm_exit_check.isChecked())
        
        # Analyst/Technician info
        self.settings.set('technician_name', self.tech_name_edit.text())
        self.settings.set('badge_number', self.badge_edit.text())
        
        # Documentation settings - Use canonical keys since properties don't have setters
        self.settings.set('TIME_OFFSET_PDF', self.generate_time_offset_check.isChecked())
        self.settings.set('UPLOAD_LOG_PDF', self.generate_upload_log_check.isChecked())
        # Single setting controls both hash calculation and CSV generation
        self.settings.set('CALCULATE_HASHES', self.generate_hash_csv_check.isChecked())
        self.settings.set('HASH_CSV', self.generate_hash_csv_check.isChecked())
    
    def accept(self):
        """Override accept to save settings before closing"""
        self.save_settings()
        super().accept()