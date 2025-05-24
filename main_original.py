#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Folder Structure Utility - A clean, simple approach to organized file management

No over-engineering, just functionality.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from PySide6.QtCore import Qt, QThread, Signal, QSettings, QDateTime
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QGroupBox, QPushButton, QLabel, QLineEdit, QComboBox,
    QDateTimeEdit, QListWidget, QTabWidget, QTextEdit, QProgressBar,
    QStatusBar, QFileDialog, QMessageBox, QSplitter, QSpinBox
)

# Import our clean business logic modules
from core.models import FormData
from core.templates import FolderTemplate, FolderBuilder
from core.file_ops import FileOperations
from core.pdf_gen import PDFGenerator
from core.workers import FileOperationThread, FolderStructureThread
from utils.zip_utils import ZipUtility, ZipSettings
from ui.custom_template_widget import CustomTemplateWidget


class MainWindow(QMainWindow):
    """Main application window - clean and simple"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize data
        self.form_data = FormData()
        self.selected_files: List[Path] = []
        self.selected_folders: List[Path] = []  # Track selected folders
        self.settings = QSettings('FolderStructureUtility', 'Settings')
        self.file_operation_results = {}  # Store results for PDF generation
        
        # Set up UI
        self.setWindowTitle("Folder Structure Utility")
        self.resize(1200, 800)
        
        self._setup_ui()
        self._setup_style()
        self._load_settings()
        
        # Show ready
        self.status_bar.showMessage("Ready")
        
    def _setup_ui(self):
        """Create the UI - all in one place, no complex bindings"""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Create menu bar
        self._create_menu_bar()
        
        # Create tab widget
        self.tabs = QTabWidget()
        
        # Forensic Mode tab
        self.forensic_tab = self._create_forensic_tab()
        self.tabs.addTab(self.forensic_tab, "Forensic Mode")
        
        # Custom Mode tab - using the new widget
        self.custom_template_widget = CustomTemplateWidget(
            self.settings, 
            self.form_data,
            self
        )
        
        # Connect signals
        self.custom_template_widget.create_tab_requested.connect(self.create_custom_tab)
        self.custom_template_widget.process_requested.connect(self.process_custom_structure)
        
        self.tabs.addTab(self.custom_template_widget, "Custom Mode")
        
        # Add tabs to layout
        layout.addWidget(self.tabs)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
    def _create_forensic_tab(self):
        """Create the forensic mode tab - your original design"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Main splitter
        splitter = QSplitter(Qt.Vertical)
        
        # Upper section: Form and Files
        upper_widget = QWidget()
        upper_layout = QHBoxLayout(upper_widget)
        
        # Form panel (left)
        form_panel = self._create_form_panel()
        upper_layout.addWidget(form_panel)
        
        # Files panel (right)
        files_panel = self._create_files_panel()
        upper_layout.addWidget(files_panel)
        
        # Log console (bottom)
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumHeight(150)
        
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
        self.process_btn.clicked.connect(self.process_forensic_files)
        button_layout.addWidget(self.process_btn)
        
        layout.addLayout(button_layout)
        
        return widget
        
    def _create_form_panel(self):
        """Create the form input panel"""
        group = QGroupBox("Case Information")
        layout = QGridLayout()
        
        # Row 0: Occurrence Number
        layout.addWidget(QLabel("Occurrence #:"), 0, 0)
        self.occ_number = QLineEdit()
        self.occ_number.textChanged.connect(lambda t: setattr(self.form_data, 'occurrence_number', t))
        layout.addWidget(self.occ_number, 0, 1)
        
        # Row 1: Business Name
        layout.addWidget(QLabel("Business Name:"), 1, 0)
        self.business_name = QLineEdit()
        self.business_name.textChanged.connect(lambda t: setattr(self.form_data, 'business_name', t))
        layout.addWidget(self.business_name, 1, 1)
        
        # Row 2: Location Address
        layout.addWidget(QLabel("Address:"), 2, 0)
        self.location_address = QLineEdit()
        self.location_address.textChanged.connect(lambda t: setattr(self.form_data, 'location_address', t))
        layout.addWidget(self.location_address, 2, 1)
        
        # Row 3: Extraction Times
        layout.addWidget(QLabel("Extraction Start:"), 3, 0)
        self.extraction_start = QDateTimeEdit(QDateTime.currentDateTime())
        self.extraction_start.setCalendarPopup(True)
        self.extraction_start.dateTimeChanged.connect(lambda dt: setattr(self.form_data, 'extraction_start', dt))
        layout.addWidget(self.extraction_start, 3, 1)
        # Initialize form data with current value
        self.form_data.extraction_start = self.extraction_start.dateTime()
        
        layout.addWidget(QLabel("Extraction End:"), 4, 0)
        self.extraction_end = QDateTimeEdit(QDateTime.currentDateTime())
        self.extraction_end.setCalendarPopup(True)
        self.extraction_end.dateTimeChanged.connect(lambda dt: setattr(self.form_data, 'extraction_end', dt))
        layout.addWidget(self.extraction_end, 4, 1)
        # Initialize form data with current value
        self.form_data.extraction_end = self.extraction_end.dateTime()
        
        # Row 5: Time Offset
        layout.addWidget(QLabel("Time Offset:"), 5, 0)
        offset_layout = QHBoxLayout()
        self.time_offset = QSpinBox()
        self.time_offset.setRange(-9999, 9999)
        self.time_offset.setSuffix(" minutes")
        self.time_offset.valueChanged.connect(lambda v: setattr(self.form_data, 'time_offset', v))
        offset_layout.addWidget(self.time_offset)
        
        self.calc_offset_btn = QPushButton("Calculate")
        self.calc_offset_btn.clicked.connect(self.calculate_time_offset)
        offset_layout.addWidget(self.calc_offset_btn)
        layout.addLayout(offset_layout, 5, 1)
        
        # Row 6: DVR Time
        layout.addWidget(QLabel("DVR Time:"), 6, 0)
        self.dvr_time = QDateTimeEdit(QDateTime.currentDateTime())
        self.dvr_time.setCalendarPopup(True)
        self.dvr_time.dateTimeChanged.connect(lambda dt: setattr(self.form_data, 'dvr_time', dt))
        layout.addWidget(self.dvr_time, 6, 1)
        # Initialize form data
        self.form_data.dvr_time = self.dvr_time.dateTime()
        
        # Row 7: Real Time
        layout.addWidget(QLabel("Real Time:"), 7, 0)
        self.real_time = QDateTimeEdit(QDateTime.currentDateTime())
        self.real_time.setCalendarPopup(True)
        self.real_time.dateTimeChanged.connect(lambda dt: setattr(self.form_data, 'real_time', dt))
        layout.addWidget(self.real_time, 7, 1)
        # Initialize form data
        self.form_data.real_time = self.real_time.dateTime()
        
        # Row 8: Technician Info
        layout.addWidget(QLabel("Technician:"), 8, 0)
        self.tech_name = QLineEdit()
        self.tech_name.textChanged.connect(lambda t: setattr(self.form_data, 'technician_name', t))
        layout.addWidget(self.tech_name, 8, 1)
        
        layout.addWidget(QLabel("Badge #:"), 9, 0)
        self.badge_number = QLineEdit()
        self.badge_number.textChanged.connect(lambda t: setattr(self.form_data, 'badge_number', t))
        layout.addWidget(self.badge_number, 9, 1)
        
        # Row 10: Upload Timestamp
        layout.addWidget(QLabel("Upload Time:"), 10, 0)
        self.upload_timestamp = QDateTimeEdit(QDateTime.currentDateTime())
        self.upload_timestamp.setCalendarPopup(True)
        self.upload_timestamp.dateTimeChanged.connect(lambda dt: setattr(self.form_data, 'upload_timestamp', dt))
        layout.addWidget(self.upload_timestamp, 10, 1)
        # Initialize form data
        self.form_data.upload_timestamp = self.upload_timestamp.dateTime()
        
        group.setLayout(layout)
        return group
        
    def _create_files_panel(self):
        """Create the files selection panel"""
        group = QGroupBox("Files to Process")
        layout = QVBoxLayout()
        
        # File list
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.file_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.add_files_btn = QPushButton("Add Files")
        self.add_files_btn.clicked.connect(self.add_files)
        btn_layout.addWidget(self.add_files_btn)
        
        self.add_folder_btn = QPushButton("Add Folder")
        self.add_folder_btn.clicked.connect(self.add_folder)
        btn_layout.addWidget(self.add_folder_btn)
        
        self.remove_files_btn = QPushButton("Remove")
        self.remove_files_btn.clicked.connect(self.remove_files)
        btn_layout.addWidget(self.remove_files_btn)
        
        layout.addLayout(btn_layout)
        
        group.setLayout(layout)
        return group
        
    def _create_custom_tab(self):
        """Create the custom mode tab with template builder"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Template selection
        template_group = QGroupBox("Folder Structure Template")
        template_layout = QVBoxLayout()
        
        # Template dropdown
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("Template:"))
        self.template_combo = QComboBox()
        self.template_combo.addItems([
            "Law Enforcement (Default)",
            "Medical Records",
            "Legal Documents",
            "Media Production",
            "Custom..."
        ])
        select_layout.addWidget(self.template_combo)
        template_layout.addLayout(select_layout)
        
        # Template builder
        builder_label = QLabel("Folder Structure:")
        template_layout.addWidget(builder_label)
        
        self.template_list = QListWidget()
        self.template_list.addItem("/{occurrence_number}/")
        self.template_list.addItem("  /{business_name} @ {location_address}/")
        self.template_list.addItem("    /{extraction_start} - {extraction_end}/")
        template_layout.addWidget(self.template_list)
        
        # Available fields
        fields_layout = QHBoxLayout()
        fields_layout.addWidget(QLabel("Available Fields:"))
        for field in ["occurrence_number", "business_name", "date", "time"]:
            btn = QPushButton(f"{{{field}}}")
            btn.setMaximumWidth(150)
            fields_layout.addWidget(btn)
        fields_layout.addStretch()
        template_layout.addLayout(fields_layout)
        
        template_group.setLayout(template_layout)
        layout.addWidget(template_group)
        
        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout()
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(100)
        self.preview_text.setPlainText("=� 2024-001\n  =� ACME Corp @ 123 Main St\n    =� 2024-01-15_1000 - 2024-01-15_1200\n      =� (your files will go here)")
        preview_layout.addWidget(self.preview_text)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.process_custom_btn = QPushButton("Process with Custom Structure")
        self.process_custom_btn.clicked.connect(self.process_custom_files)
        btn_layout.addWidget(self.process_custom_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        return widget
        
    def _create_menu_bar(self):
        """Create the menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        load_action = QAction("Load JSON", self)
        load_action.triggered.connect(self.load_json)
        file_menu.addAction(load_action)
        
        save_action = QAction("Save JSON", self)
        save_action.triggered.connect(self.save_json)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Settings menu
        settings_menu = menubar.addMenu("Settings")
        
        user_settings_action = QAction("User Settings", self)
        user_settings_action.triggered.connect(self.show_user_settings)
        settings_menu.addAction(user_settings_action)
        
        zip_settings_action = QAction("ZIP Settings", self)
        zip_settings_action.triggered.connect(self.show_zip_settings)
        settings_menu.addAction(zip_settings_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def _setup_style(self):
        """Apply Carolina Blue theme - the OG dark aesthetic"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            
            QGroupBox {
                font-weight: bold;
                border: 2px solid #4B9CD3;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #1e1e1e;
                color: #ffffff;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #7BAFD4;
                background-color: #1e1e1e;
            }
            
            QPushButton {
                background-color: #4B9CD3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 100px;
            }
            
            QPushButton:hover {
                background-color: #7BAFD4;
            }
            
            QPushButton:pressed {
                background-color: #13294B;
            }
            
            QPushButton:disabled {
                background-color: #3a3a3a;
                color: #666666;
            }
            
            QLineEdit, QComboBox, QSpinBox, QDateTimeEdit {
                padding: 5px;
                border: 1px solid #4B9CD3;
                border-radius: 3px;
                background-color: #1e1e1e;
                color: #ffffff;
            }
            
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateTimeEdit:focus {
                border: 2px solid #7BAFD4;
                background-color: #252525;
            }
            
            QComboBox::drop-down {
                border: none;
            }
            
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #7BAFD4;
                margin-right: 5px;
            }
            
            QListWidget {
                border: 1px solid #4B9CD3;
                border-radius: 3px;
                background-color: #1e1e1e;
                color: #ffffff;
                selection-background-color: #4B9CD3;
            }
            
            QListWidget::item:selected {
                background-color: #4B9CD3;
                color: #ffffff;
            }
            
            QTextEdit {
                border: 1px solid #4B9CD3;
                border-radius: 3px;
                background-color: #1e1e1e;
                color: #ffffff;
            }
            
            QLabel {
                color: #ffffff;
                background-color: transparent;
            }
            
            QProgressBar {
                border: 1px solid #4B9CD3;
                border-radius: 3px;
                text-align: center;
                background-color: #1e1e1e;
                color: #ffffff;
            }
            
            QProgressBar::chunk {
                background-color: #4B9CD3;
                border-radius: 3px;
            }
            
            QTabWidget::pane {
                border: 1px solid #4B9CD3;
                background-color: #1e1e1e;
            }
            
            QTabBar::tab {
                background-color: #2b2b2b;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
                border: 1px solid #4B9CD3;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            
            QTabBar::tab:selected {
                background-color: #4B9CD3;
                color: #ffffff;
            }
            
            QTabBar::tab:!selected {
                margin-top: 2px;
            }
            
            QStatusBar {
                background-color: #13294B;
                color: #ffffff;
                border-top: 1px solid #4B9CD3;
            }
            
            QMenuBar {
                background-color: #1e1e1e;
                color: #ffffff;
                border-bottom: 1px solid #4B9CD3;
            }
            
            QMenuBar::item {
                padding: 5px 10px;
                background-color: transparent;
            }
            
            QMenuBar::item:selected {
                background-color: #4B9CD3;
            }
            
            QMenu {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #4B9CD3;
            }
            
            QMenu::item {
                padding: 5px 20px;
            }
            
            QMenu::item:selected {
                background-color: #4B9CD3;
            }
            
            QSplitter::handle {
                background-color: #4B9CD3;
                height: 2px;
            }
            
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 12px;
                border: none;
            }
            
            QScrollBar::handle:vertical {
                background-color: #4B9CD3;
                min-height: 20px;
                border-radius: 6px;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            
            QDateTimeEdit::drop-down {
                border: none;
            }
            
            QDateTimeEdit::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #7BAFD4;
                margin-right: 5px;
            }
            
            QCheckBox {
                color: #ffffff;
            }
            
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
                border: 1px solid #4B9CD3;
                background-color: #1e1e1e;
                border-radius: 2px;
            }
            
            QCheckBox::indicator:checked {
                background-color: #4B9CD3;
            }
            
            QDialogButtonBox QPushButton {
                min-width: 80px;
            }
        """)
        
    def _load_settings(self):
        """Load saved settings"""
        # Load technician info
        self.tech_name.setText(self.settings.value('technician_name', ''))
        self.badge_number.setText(self.settings.value('badge_number', ''))
        
    def add_files(self):
        """Add files to process"""
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "All Files (*.*)")
        for file in files:
            path = Path(file)
            if path not in self.selected_files:
                self.selected_files.append(path)
                self.file_list.addItem(f"📄 {path.name}")
        self.log(f"Added {len(files)} files")
        
    def add_folder(self):
        """Add entire folder structure with all subdirectories and files"""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            folder_path = Path(folder)
            
            # Add the folder itself to track
            if folder_path not in self.selected_folders:
                self.selected_folders.append(folder_path)
                self.file_list.addItem(f"📁 {folder_path.name}/ (entire folder structure)")
                
                # Count total files for logging
                file_count = sum(1 for _ in folder_path.rglob('*') if _.is_file())
                self.log(f"Added folder '{folder_path.name}' with {file_count} files")
            
    def remove_files(self):
        """Remove selected files or folders"""
        for item in self.file_list.selectedItems():
            row = self.file_list.row(item)
            item_text = item.text()
            self.file_list.takeItem(row)
            
            # Determine if it's a file or folder and remove from appropriate list
            if item_text.startswith("📄"):
                # It's a file - remove from selected_files
                if row < len(self.selected_files):
                    self.selected_files.pop(row)
            elif item_text.startswith("📁"):
                # It's a folder - find and remove from selected_folders
                for i, folder in enumerate(self.selected_folders):
                    if folder.name in item_text:
                        self.selected_folders.pop(i)
                        break
                        
        self.log("Removed selected items")
        
    def calculate_time_offset(self):
        """Calculate time offset between DVR and real time"""
        if self.form_data.dvr_time and self.form_data.real_time:
            offset_seconds = self.form_data.dvr_time.secsTo(self.form_data.real_time)
            offset_minutes = offset_seconds // 60
            self.time_offset.setValue(offset_minutes)
            self.log(f"Calculated offset: {offset_minutes} minutes")
            
    def process_forensic_files(self):
        """Process files using forensic folder structure"""
        # Validate form
        errors = self.form_data.validate()
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return
            
        if not self.selected_files and not self.selected_folders:
            QMessageBox.warning(self, "No Files", "Please select files or folders to process")
            return
            
        # Ask user where to save the output
        output_dir = QFileDialog.getExistingDirectory(
            self, 
            "Select Output Location", 
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if not output_dir:
            return  # User cancelled
            
        # Store the output directory for later use (ZIP files)
        self.output_directory = Path(output_dir)
        
        # Build folder structure in the selected location
        folder_path = self.build_forensic_structure(self.output_directory)
        
        # Prepare all files to copy (including folder structures)
        all_items = []
        
        # Add individual files
        for file in self.selected_files:
            all_items.append(('file', file, file.name))
            
        # Add folders with their complete structure
        for folder in self.selected_folders:
            all_items.append(('folder', folder, None))
        
        # Start file operation thread
        self.file_thread = FolderStructureThread(all_items, folder_path)
        self.file_thread.progress.connect(self.update_progress)
        self.file_thread.status.connect(self.log)
        self.file_thread.finished.connect(self.on_operation_finished)
        
        # Disable UI and show progress
        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        
        self.file_thread.start()
        
    def build_forensic_structure(self, base_path: Path = None) -> Path:
        """Build the forensic folder structure"""
        if base_path:
            # Create the structure in the specified base path
            occurrence_path = base_path / self.form_data.occurrence_number
            
            # Level 2: Business @ Address or just Address
            if self.form_data.business_name:
                level2 = f"{self.form_data.business_name} @ {self.form_data.location_address}"
            else:
                level2 = self.form_data.location_address
                
            # Level 3: Date range
            if self.form_data.extraction_start and self.form_data.extraction_end:
                start = self.form_data.extraction_start.toString("yyyy-MM-dd_HHmm")
                end = self.form_data.extraction_end.toString("yyyy-MM-dd_HHmm")
                level3 = f"{start} - {end}"
            else:
                from datetime import datetime
                now = datetime.now().strftime("%Y-%m-%d_%H%M")
                level3 = f"{now} - {now}"
                
            # Clean path parts
            from core.templates import FolderTemplate
            level2 = FolderTemplate._sanitize_path_part(None, level2)
            level3 = FolderTemplate._sanitize_path_part(None, level3)
            
            # Combine
            full_path = occurrence_path / level2 / level3
            full_path.mkdir(parents=True, exist_ok=True)
            
            self.log(f"Created folder structure: {full_path}")
            return full_path
        else:
            # Use the core function
            folder_path = FolderBuilder.build_forensic_structure(self.form_data)
            self.log(f"Created folder structure: {folder_path}")
            return folder_path
        
    def process_custom_files(self):
        """Process files using custom folder structure"""
        QMessageBox.information(self, "Coming Soon", 
                              "Custom folder structure processing will be implemented next!")
                              
    def create_custom_tab(self, name: str, template_levels: List[str]):
        """Create a new tab with a custom template"""
        # Create a widget for the new tab
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # Show the template structure
        info_group = QGroupBox(f"Template: {name}")
        info_layout = QVBoxLayout()
        
        structure_text = QTextEdit()
        structure_text.setReadOnly(True)
        structure_text.setMaximumHeight(100)
        
        # Display the structure
        preview_lines = []
        for i, level in enumerate(template_levels):
            indent = "  " * i
            preview_lines.append(f"{indent}📁 {level}")
        structure_text.setPlainText("\n".join(preview_lines))
        
        info_layout.addWidget(structure_text)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Add file selection (reuse from forensic tab)
        files_panel = self._create_files_panel()
        layout.addWidget(files_panel)
        
        # Process button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        process_btn = QPushButton(f"Process with {name} Structure")
        process_btn.clicked.connect(lambda: self.process_with_custom_template(template_levels))
        btn_layout.addWidget(process_btn)
        layout.addLayout(btn_layout)
        
        # Add the new tab
        self.tabs.addTab(tab_widget, name)
        
        # Switch to the new tab
        self.tabs.setCurrentWidget(tab_widget)
        
        QMessageBox.information(self, "Tab Created", 
                              f"New tab '{name}' has been created!\n\n"
                              "You can now use this template directly from its own tab.")
                              
    def process_custom_structure(self, template_levels: List[str]):
        """Process files with a custom template structure"""
        # Validate form
        errors = self.form_data.validate()
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return
            
        if not self.selected_files and not self.selected_folders:
            QMessageBox.warning(self, "No Files", "Please select files or folders to process")
            return
            
        # Ask for output location
        output_dir = QFileDialog.getExistingDirectory(
            self, 
            "Select Output Location", 
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if not output_dir:
            return
            
        self.output_directory = Path(output_dir)
        
        # Create the custom structure
        template = FolderTemplate("Custom", "Custom Structure", template_levels)
        folder_path = self.output_directory / template.build_path(self.form_data)
        folder_path.mkdir(parents=True, exist_ok=True)
        
        self.log(f"Created custom folder structure: {folder_path}")
        
        # Process files (same as forensic)
        all_items = []
        for file in self.selected_files:
            all_items.append(('file', file, file.name))
        for folder in self.selected_folders:
            all_items.append(('folder', folder, None))
            
        self.file_thread = FolderStructureThread(all_items, folder_path)
        self.file_thread.progress.connect(self.update_progress)
        self.file_thread.status.connect(self.log)
        self.file_thread.finished.connect(self.on_operation_finished)
        
        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        
        self.file_thread.start()
        
    def process_with_custom_template(self, template_levels: List[str]):
        """Process files with a specific custom template"""
        self.process_custom_structure(template_levels)
        
    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)
        
    def on_operation_finished(self, success, message, results):
        """Handle operation completion"""
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        
        if success:
            # Store results for potential PDF generation
            self.file_operation_results = results
            
            # Ask user if they want to generate reports
            reply = QMessageBox.question(self, "Generate Reports?",
                                       "Files copied successfully!\n\n"
                                       "Would you like to generate PDF reports?",
                                       QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.generate_reports()
            else:
                QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Error", message)
            
        self.log(message)
        
    def generate_reports(self):
        """Generate PDF reports and hash verification CSV"""
        try:
            # Get the output directory (same as where files were copied)
            output_dir = Path(list(self.file_operation_results.values())[0]['dest_path']).parent
            
            # Initialize PDF generator
            try:
                pdf_gen = PDFGenerator()
            except ImportError:
                QMessageBox.warning(self, "PDF Generation", 
                                  "ReportLab not installed. Install with: pip install reportlab")
                return
                
            # Generate time offset report if offset exists
            if self.form_data.time_offset != 0:
                time_report_path = output_dir / "Time_Offset_Report.pdf"
                if pdf_gen.generate_time_offset_report(self.form_data, time_report_path):
                    self.log(f"Generated: {time_report_path.name}")
                    
            # Generate technician log
            tech_log_path = output_dir / "Technician_Log.pdf"
            if pdf_gen.generate_technician_log(self.form_data, tech_log_path):
                self.log(f"Generated: {tech_log_path.name}")
                
            # Generate hash verification CSV
            hash_csv_path = output_dir / "Hash_Verification.csv"
            if pdf_gen.generate_hash_verification_csv(self.file_operation_results, hash_csv_path):
                self.log(f"Generated: {hash_csv_path.name}")
                
            # Ask about ZIP creation
            create_zip = self.settings.value('zip_at_root', True, type=bool) or \
                        self.settings.value('zip_at_location', False, type=bool) or \
                        self.settings.value('zip_at_datetime', False, type=bool)
                        
            if create_zip:
                reply = QMessageBox.question(self, "Create ZIP Archive?",
                                           "Would you like to create ZIP archive(s)?",
                                           QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.create_zip_archives(output_dir)
                    
            QMessageBox.information(self, "Reports Generated", 
                                  f"Reports have been saved to:\n{output_dir}")
                                  
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate reports: {str(e)}")
            
    def create_zip_archives(self, base_path: Path):
        """Create ZIP archives based on settings"""
        try:
            import zipfile
            
            # Get settings
            settings = ZipSettings()
            settings.compression_level = self.settings.value('zip_compression_level', zipfile.ZIP_STORED)
            settings.create_at_root = self.settings.value('zip_at_root', True, type=bool)
            settings.create_at_location = self.settings.value('zip_at_location', False, type=bool)
            settings.create_at_datetime = self.settings.value('zip_at_datetime', False, type=bool)
            
            # Set output path to be alongside the folder structure (in the parent directory)
            # The base_path is the datetime folder, so we go up to get the occurrence folder
            root_folder = base_path.parents[1]  # This is the occurrence number folder
            settings.output_path = self.output_directory  # Save ZIPs in the main output directory
            
            # Create ZIP utility with progress
            self.progress_bar.setVisible(True)
            zip_util = ZipUtility(
                progress_callback=lambda pct, msg: (
                    self.progress_bar.setValue(pct),
                    self.log(msg)
                )
            )
            
            # Create archives
            created = zip_util.create_multi_level_archives(root_folder, settings)
            
            self.progress_bar.setVisible(False)
            
            if created:
                self.log(f"Created {len(created)} ZIP archive(s)")
                # Show where the ZIPs were saved
                zip_names = [z.name for z in created]
                QMessageBox.information(self, "ZIP Archives Created", 
                                      f"Created {len(created)} ZIP archive(s) in:\n{self.output_directory}\n\n"
                                      f"Files:\n" + "\n".join(zip_names))
            else:
                self.log("No ZIP archives created")
                
        except Exception as e:
            self.progress_bar.setVisible(False)
            QMessageBox.critical(self, "ZIP Error", f"Failed to create ZIP: {str(e)}")
        
    def log(self, message):
        """Add message to log console"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_console.append(f"[{timestamp}] {message}")
        self.status_bar.showMessage(message, 3000)
        
    def load_json(self):
        """Load form data from JSON"""
        file, _ = QFileDialog.getOpenFileName(self, "Load JSON", "", "JSON Files (*.json)")
        if file:
            try:
                import json
                with open(file, 'r') as f:
                    data = json.load(f)
                self.form_data = FormData.from_dict(data)
                # Update UI fields
                self.occ_number.setText(self.form_data.occurrence_number)
                self.business_name.setText(self.form_data.business_name)
                self.location_address.setText(self.form_data.location_address)
                self.tech_name.setText(self.form_data.technician_name)
                self.badge_number.setText(self.form_data.badge_number)
                if self.form_data.extraction_start:
                    self.extraction_start.setDateTime(self.form_data.extraction_start)
                if self.form_data.extraction_end:
                    self.extraction_end.setDateTime(self.form_data.extraction_end)
                self.log(f"Loaded data from {Path(file).name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load JSON: {str(e)}")
                
    def save_json(self):
        """Save form data to JSON"""
        file, _ = QFileDialog.getSaveFileName(self, "Save JSON", "", "JSON Files (*.json)")
        if file:
            try:
                import json
                with open(file, 'w') as f:
                    json.dump(self.form_data.to_dict(), f, indent=2)
                self.log(f"Saved data to {Path(file).name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save JSON: {str(e)}")
                
    def show_user_settings(self):
        """Show user settings dialog"""
        QMessageBox.information(self, "User Settings", "User settings dialog coming soon!")
        
    def show_zip_settings(self):
        """Show ZIP settings dialog"""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QCheckBox
        import zipfile
        
        dialog = QDialog(self)
        dialog.setWindowTitle("ZIP Settings")
        dialog.setModal(True)
        
        layout = QVBoxLayout()
        
        # Compression level
        comp_group = QGroupBox("Compression Level")
        comp_layout = QVBoxLayout()
        
        self.comp_combo = QComboBox()
        self.comp_combo.addItems(["No Compression (Fastest)", "Compressed (Smaller)"])
        comp_value = self.settings.value('zip_compression', 0)
        self.comp_combo.setCurrentIndex(comp_value)
        comp_layout.addWidget(self.comp_combo)
        
        comp_group.setLayout(comp_layout)
        layout.addWidget(comp_group)
        
        # Create levels
        level_group = QGroupBox("Create ZIP at Levels")
        level_layout = QVBoxLayout()
        
        self.zip_root_check = QCheckBox("Root Level (entire structure)")
        self.zip_root_check.setChecked(self.settings.value('zip_at_root', True, type=bool))
        level_layout.addWidget(self.zip_root_check)
        
        self.zip_location_check = QCheckBox("Location Level (per location)")
        self.zip_location_check.setChecked(self.settings.value('zip_at_location', False, type=bool))
        level_layout.addWidget(self.zip_location_check)
        
        self.zip_datetime_check = QCheckBox("DateTime Level (per time range)")
        self.zip_datetime_check.setChecked(self.settings.value('zip_at_datetime', False, type=bool))
        level_layout.addWidget(self.zip_datetime_check)
        
        level_group.setLayout(level_layout)
        layout.addWidget(level_group)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec() == QDialog.Accepted:
            # Save settings
            comp_level = 0 if self.comp_combo.currentIndex() == 0 else zipfile.ZIP_DEFLATED
            self.settings.setValue('zip_compression', self.comp_combo.currentIndex())
            self.settings.setValue('zip_compression_level', comp_level)
            self.settings.setValue('zip_at_root', self.zip_root_check.isChecked())
            self.settings.setValue('zip_at_location', self.zip_location_check.isChecked())
            self.settings.setValue('zip_at_datetime', self.zip_datetime_check.isChecked())
            self.log("ZIP settings saved")
        
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About", 
                         "Folder Structure Utility v2.0\n\n"
                         "A clean, simple approach to organized file management.\n\n"
                         "No over-engineering, just functionality.")
        
    def closeEvent(self, event):
        """Save settings on close"""
        self.settings.setValue('technician_name', self.tech_name.text())
        self.settings.setValue('badge_number', self.badge_number.text())
        event.accept()


def main():
    """Application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("Folder Structure Utility")
    app.setOrganizationName("Simple Software")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()