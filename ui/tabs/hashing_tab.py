#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hashing Tab - Professional interface for file hashing and verification operations
Redesigned with three-column layout and results management panel
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSplitter,
    QGroupBox, QComboBox, QLabel, QFileDialog, QProgressBar, 
    QFrame, QScrollArea, QSizePolicy, QTreeWidget, QTreeWidgetItem,
    QHeaderView
)
from PySide6.QtGui import QFont, QIcon

from controllers.hash_controller import HashController
from core.settings_manager import settings
from core.hash_reports import HashReportGenerator
from core.logger import logger
from ui.components import FilesPanel, LogConsole
from ui.components.elided_label import ElidedLabel
from core.exceptions import UIError, ErrorSeverity
from core.error_handler import handle_error


class OperationStatusCard(QFrame):
    """Card widget displaying operation status and results"""
    
    export_requested = Signal(str, dict)  # operation_type, results
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.operation_data = None
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the card UI"""
        self.setFrameStyle(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 8px;
                margin: 4px;
            }
            QFrame:hover {
                border-color: #4285f4;
                background-color: #f0f4ff;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # Header with icon and title
        header_layout = QHBoxLayout()
        self.status_icon = QLabel("⏳")
        self.status_icon.setFixedSize(16, 16)
        header_layout.addWidget(self.status_icon)
        
        self.title_label = QLabel("No Operation")
        self.title_label.setFont(self._get_bold_font())
        self.title_label.setStyleSheet("color: #212529; font-weight: bold;")  # Dark text for readability
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Details
        self.details_label = QLabel("Ready to start")
        self.details_label.setStyleSheet("color: #495057; font-size: 11px;")  # Darker gray for readability
        layout.addWidget(self.details_label)
        
        # Performance metrics
        self.metrics_label = QLabel("")
        self.metrics_label.setStyleSheet("color: #198754; font-size: 10px; font-family: monospace; font-weight: bold;")
        layout.addWidget(self.metrics_label)
        
        # Export button
        self.export_btn = QPushButton("📄 Export CSV")
        self.export_btn.setEnabled(False)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.export_btn.clicked.connect(self._on_export_clicked)
        layout.addWidget(self.export_btn)
        
    def _get_bold_font(self):
        """Get bold font for titles"""
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        return font
        
    def set_operation_data(self, operation_type: str, status: str, results: Optional[Dict] = None):
        """Set operation data and update display"""
        self.operation_data = {
            'type': operation_type,
            'status': status,
            'results': results,
            'timestamp': datetime.now()
        }
        self._update_display()
        
    def _update_display(self):
        """Update card display based on operation data"""
        if not self.operation_data:
            return
            
        op_type = self.operation_data['type']
        status = self.operation_data['status']
        results = self.operation_data['results']
        
        
        # Update icon and title based on status
        if status == 'completed':
            self.status_icon.setText("✅")
            self.title_label.setText(f"{op_type.title()}: Completed")
            self.export_btn.setEnabled(bool(results))
        elif status == 'failed':
            self.status_icon.setText("❌")
            self.title_label.setText(f"{op_type.title()}: Failed")
            # CRITICAL FIX: Enable export for failed operations that have results
            self.export_btn.setEnabled(bool(results))
        elif status == 'in_progress':
            self.status_icon.setText("⚙️")
            self.title_label.setText(f"{op_type.title()}: Processing...")
            self.export_btn.setEnabled(False)
        else:
            self.status_icon.setText("⏳")
            self.title_label.setText(f"{op_type.title()}: Ready")
            self.export_btn.setEnabled(False)
            
        # Update details
        if results:
            # Try multiple possible key names for files processed
            file_count = (results.get('files_processed', 0) or 
                         results.get('files_hashed', 0) or 
                         results.get('total_files', 0) or
                         len(results.get('results', [])) if isinstance(results.get('results'), list) else 0)
            
            if file_count > 0:
                self.details_label.setText(f"{file_count} files processed")
            else:
                self.details_label.setText("Processing completed")
            
            # Performance metrics - try multiple possible key names
            duration = (results.get('duration_seconds', 0) or 
                       results.get('processing_time', 0) or
                       results.get('elapsed_time', 0))
            
            speed = (results.get('average_speed_mbps', 0) or 
                    results.get('speed_mbps', 0) or
                    results.get('throughput_mbps', 0))
            
            # Show metrics if we have any performance data
            if duration > 0 or speed > 0:
                metrics_parts = []
                if duration > 0:
                    metrics_parts.append(f"⏱️ {duration:.1f}s")
                if speed > 0:
                    metrics_parts.append(f"🚀 {speed:.1f} MB/s")
                self.metrics_label.setText(" | ".join(metrics_parts))
            else:
                # Show something to indicate completion even without metrics
                self.metrics_label.setText("✅ Operation completed")
        else:
            self.details_label.setText("No results available")
            self.metrics_label.setText("")
            
    def _on_export_clicked(self):
        """Handle export button click"""
        if self.operation_data and self.operation_data['results']:
            self.export_requested.emit(
                self.operation_data['type'], 
                self.operation_data['results']
            )


class ResultsManagementPanel(QFrame):
    """Results management panel showing operation history and export options"""
    
    export_requested = Signal(str, dict)  # operation_type, results
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.operation_history = []
        
        # Session statistics tracking
        self.session_stats = {
            'total_files_processed': 0,
            'total_processing_time': 0.0,
            'total_data_processed_mb': 0.0,
            'operations_completed': 0
        }
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the results panel UI"""
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("📊 Results & Export")
        title_label.setFont(self._get_title_font())
        title_label.setStyleSheet("color: #6c757d; margin-bottom: 8px; font-weight: bold;")
        layout.addWidget(title_label)
        
        # Current operations cards
        self.single_hash_card = OperationStatusCard()
        self.single_hash_card.export_requested.connect(self.export_requested.emit)
        layout.addWidget(self.single_hash_card)
        
        self.verification_card = OperationStatusCard()
        self.verification_card.export_requested.connect(self.export_requested.emit)
        layout.addWidget(self.verification_card)
        
        # Quick stats
        stats_group = QGroupBox("Session Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self.total_files_label = QLabel("Files Processed: 0")
        self.total_time_label = QLabel("Total Time: 0s")
        self.avg_speed_label = QLabel("Avg Speed: 0 MB/s")
        
        for label in [self.total_files_label, self.total_time_label, self.avg_speed_label]:
            label.setStyleSheet("font-size: 11px; color: #495057;")  # Darker for better readability
            stats_layout.addWidget(label)
            
        layout.addWidget(stats_group)
        layout.addStretch()
        
    def _get_title_font(self):
        """Get title font"""
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        return font
        
    def update_operation_status(self, operation_type: str, status: str, results: Optional[Dict] = None):
        """Update operation status card"""
        if operation_type == 'single_hash':
            self.single_hash_card.set_operation_data(operation_type, status, results)
        elif operation_type == 'verification':
            self.verification_card.set_operation_data(operation_type, status, results)
            
        # Update session statistics
        if operation_type in ['single_hash', 'verification'] and status == 'completed' and results:
            self._add_to_session_stats(operation_type, results)
        
        self._update_session_stats()
        
    def _add_to_session_stats(self, operation_type: str, results: Dict):
        """Add operation results to session statistics"""
        try:
            # Extract metrics from results - handle multiple possible key names
            files_processed = (results.get('files_processed', 0) or 
                             results.get('files_hashed', 0) or 
                             results.get('total_files', 0) or
                             len(results.get('results', [])) if isinstance(results.get('results'), list) else 0)
            
            processing_time = (results.get('duration_seconds', 0) or 
                             results.get('processing_time', 0) or
                             results.get('elapsed_time', 0))
            
            # Try to get data processed in MB
            data_mb = results.get('total_size_mb', 0) or 0
            
            # Update session statistics
            self.session_stats['total_files_processed'] += files_processed
            self.session_stats['total_processing_time'] += processing_time
            self.session_stats['total_data_processed_mb'] += data_mb
            self.session_stats['operations_completed'] += 1
            
        except Exception as e:
            # If we can't extract metrics, at least increment operation count
            self.session_stats['operations_completed'] += 1
        
    def _update_session_stats(self):
        """Update session statistics display"""
        try:
            # Calculate average speed
            avg_speed = 0.0
            if self.session_stats['total_processing_time'] > 0 and self.session_stats['total_data_processed_mb'] > 0:
                avg_speed = self.session_stats['total_data_processed_mb'] / self.session_stats['total_processing_time']
            
            # Format time nicely
            total_time = self.session_stats['total_processing_time']
            if total_time < 60:
                time_str = f"{total_time:.1f}s"
            elif total_time < 3600:
                minutes = int(total_time // 60)
                seconds = int(total_time % 60)
                time_str = f"{minutes}m {seconds}s"
            else:
                hours = int(total_time // 3600)
                minutes = int((total_time % 3600) // 60)
                time_str = f"{hours}h {minutes}m"
            
            # Update labels
            self.total_files_label.setText(f"Files Processed: {self.session_stats['total_files_processed']}")
            self.total_time_label.setText(f"Total Time: {time_str}")
            self.avg_speed_label.setText(f"Avg Speed: {avg_speed:.1f} MB/s")
            
        except Exception as e:
            # Fallback to show at least basic stats
            self.total_files_label.setText(f"Files Processed: {self.session_stats.get('total_files_processed', 0)}")
            self.total_time_label.setText("Total Time: --")
            self.avg_speed_label.setText("Avg Speed: --")


class HashingTab(QWidget):
    """Professional hashing tab with three-column layout and results management"""
    
    # Signals
    log_message = Signal(str)
    status_message = Signal(str)
    
    def __init__(self, hash_controller: Optional[HashController] = None, parent=None):
        """Initialize the redesigned hashing tab"""
        super().__init__(parent)
        
        # Controllers and utilities
        self.hash_controller = hash_controller or HashController()
        self.report_generator = HashReportGenerator()
        
        # Current operation results
        self.current_single_results = None
        self.current_verification_results = None
        
        # UI state
        self.operation_active = False
        self.current_operation_type = None
        
        self._create_ui()
        self._connect_signals()
        self._load_settings()
        
    def _create_ui(self):
        """Create the professional three-panel UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # 1. UNIFIED HEADER BAR (10% height)
        header_bar = self._create_header_bar()
        layout.addWidget(header_bar)
        
        # 2. MAIN CONTENT SPLITTER (90% height)
        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.setChildrenCollapsible(False)  # Critical fix from batch tab
        main_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Operations section (60% of remaining height)
        operations_section = self._create_operations_section()
        main_splitter.addWidget(operations_section)
        
        # Console section (40% of remaining height) 
        console_section = self._create_console_section()
        main_splitter.addWidget(console_section)
        
        # Set splitter proportions (60% operations, 40% console)
        main_splitter.setStretchFactor(0, 6)
        main_splitter.setStretchFactor(1, 4)
        main_splitter.setSizes([400, 267])  # 60%/40% split
        
        layout.addWidget(main_splitter)
        
    def _create_header_bar(self) -> QGroupBox:
        """Create unified header bar with algorithm selection and global controls"""
        header_group = QGroupBox("Hash Operations Control")
        header_layout = QHBoxLayout(header_group)
        
        # Algorithm selection
        header_layout.addWidget(QLabel("Algorithm:"))
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(["SHA-256", "SHA-1", "MD5"])
        self.algorithm_combo.setMinimumWidth(100)
        header_layout.addWidget(self.algorithm_combo)
        
        header_layout.addWidget(QLabel("|"))  # Separator
        
        # Status indicator
        self.status_indicator = QLabel("🟢 Ready")
        self.status_indicator.setStyleSheet("color: #28a745; font-weight: bold;")
        header_layout.addWidget(self.status_indicator)
        
        header_layout.addStretch()
        
        # Global controls
        self.settings_btn = QPushButton("⚙️ Settings")
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        header_layout.addWidget(self.settings_btn)
        
        self.cancel_all_btn = QPushButton("🛑 Cancel All")
        self.cancel_all_btn.setEnabled(False)
        self.cancel_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        header_layout.addWidget(self.cancel_all_btn)
        
        return header_group
        
    def _create_operations_section(self) -> QWidget:
        """Create three-column operations section"""
        operations_widget = QWidget()
        operations_layout = QHBoxLayout(operations_widget)
        operations_layout.setSpacing(12)
        
        # Column 1: Single Hash Operation (33%)
        single_hash_section = self._create_single_hash_section()
        operations_layout.addWidget(single_hash_section, 1)
        
        # Column 2: Hash Verification (33%)
        verification_section = self._create_verification_section()
        operations_layout.addWidget(verification_section, 1)
        
        # Column 3: Results & Export (34%)
        self.results_panel = ResultsManagementPanel()
        self.results_panel.export_requested.connect(self._handle_export_request)
        operations_layout.addWidget(self.results_panel, 1)
        
        return operations_widget
        
    def _create_single_hash_section(self) -> QGroupBox:
        """Create single hash operation section"""
        group = QGroupBox("🔢 Single Hash Operation")
        group.setFont(self._get_section_font())
        layout = QVBoxLayout(group)
        
        # Description
        desc_label = QLabel("Calculate hashes for selected files and folders. Folders are processed recursively.")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #6c757d; font-size: 11px; margin-bottom: 8px;")
        layout.addWidget(desc_label)
        
        # Files panel with proper sizing
        self.single_files_panel = FilesPanel(show_remove_selected=False, compact_buttons=True)
        self.single_files_panel.setMinimumHeight(200)
        self.single_files_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.single_files_panel)
        
        # File count indicator
        self.single_count_label = QLabel("No files selected")
        self.single_count_label.setStyleSheet("font-size: 10px; color: #6c757d; margin: 4px;")
        layout.addWidget(self.single_count_label)
        
        # Action button
        self.single_hash_btn = QPushButton("🚀 Calculate Hashes")
        self.single_hash_btn.setEnabled(False)
        self.single_hash_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        layout.addWidget(self.single_hash_btn)
        
        return group
        
    def _create_verification_section(self) -> QGroupBox:
        """Create hash verification section"""
        group = QGroupBox("🔍 Hash Verification")
        group.setFont(self._get_section_font())
        layout = QVBoxLayout(group)
        
        # Description
        desc_label = QLabel("Compare hashes between source and target files to verify integrity.")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #6c757d; font-size: 11px; margin-bottom: 8px;")
        layout.addWidget(desc_label)
        
        # Source and target panels
        panels_layout = QHBoxLayout()
        
        # Source panel
        source_widget = QWidget()
        source_layout = QVBoxLayout(source_widget)
        source_layout.setContentsMargins(0, 0, 4, 0)
        
        source_label = QLabel("Source Files:")
        source_label.setStyleSheet("font-weight: bold; color: #495057; font-size: 10px;")
        source_layout.addWidget(source_label)
        
        self.source_files_panel = FilesPanel(show_remove_selected=False, compact_buttons=True)
        self.source_files_panel.setMinimumHeight(100)
        source_layout.addWidget(self.source_files_panel)
        
        # Target panel
        target_widget = QWidget()
        target_layout = QVBoxLayout(target_widget)
        target_layout.setContentsMargins(4, 0, 0, 0)
        
        target_label = QLabel("Target Files:")
        target_label.setStyleSheet("font-weight: bold; color: #495057; font-size: 10px;")
        target_layout.addWidget(target_label)
        
        self.target_files_panel = FilesPanel(show_remove_selected=False, compact_buttons=True)
        self.target_files_panel.setMinimumHeight(100)
        target_layout.addWidget(self.target_files_panel)
        
        # Add panels side by side
        panels_layout.addWidget(source_widget)
        panels_layout.addWidget(target_widget)
        layout.addLayout(panels_layout)
        
        # Count indicators
        self.verification_count_label = QLabel("No files selected")
        self.verification_count_label.setStyleSheet("font-size: 10px; color: #6c757d; margin: 4px;")
        layout.addWidget(self.verification_count_label)
        
        # Action button
        self.verify_hashes_btn = QPushButton("🔍 Verify Hashes")
        self.verify_hashes_btn.setEnabled(False)
        self.verify_hashes_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        layout.addWidget(self.verify_hashes_btn)
        
        return group
        
    def _create_console_section(self) -> QGroupBox:
        """Create enhanced console section with progress"""
        console_group = QGroupBox("📋 Processing Console")
        console_group.setFont(self._get_section_font())
        console_layout = QVBoxLayout(console_group)
        
        # Progress bar with operation info
        progress_layout = QHBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #dee2e6;
                border-radius: 8px;
                text-align: center;
                background-color: #f8f9fa;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 6px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = ElidedLabel("Ready to process files", max_width=200)
        self.progress_label.setStyleSheet("font-size: 11px; color: #6c757d; font-family: monospace;")
        progress_layout.addWidget(self.progress_label)
        
        console_layout.addLayout(progress_layout)
        
        # Log console
        self.log_console = LogConsole()
        self.log_console.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        console_layout.addWidget(self.log_console)
        
        return console_group
        
    def _get_section_font(self):
        """Get section header font"""
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        return font
        
    def _connect_signals(self):
        """Connect all internal signals"""
        # Header controls
        self.algorithm_combo.currentTextChanged.connect(self._on_algorithm_changed)
        self.settings_btn.clicked.connect(self._show_settings)
        self.cancel_all_btn.clicked.connect(self._cancel_all_operations)
        
        # Files panel changes
        self.single_files_panel.files_changed.connect(self._update_single_hash_state)
        self.single_files_panel.log_message.connect(self._log)
        
        self.source_files_panel.files_changed.connect(self._update_verification_state)
        self.source_files_panel.log_message.connect(self._log)
        
        self.target_files_panel.files_changed.connect(self._update_verification_state)
        self.target_files_panel.log_message.connect(self._log)
        
        # Operation buttons
        self.single_hash_btn.clicked.connect(self._start_single_hash_operation)
        self.verify_hashes_btn.clicked.connect(self._start_verification_operation)
        
    def _load_settings(self):
        """Load settings and set initial state"""
        algorithm = settings.hash_algorithm
        if algorithm == 'sha256':
            self.algorithm_combo.setCurrentText("SHA-256")
        elif algorithm == 'sha1':
            self.algorithm_combo.setCurrentText("SHA-1")
        elif algorithm == 'md5':
            self.algorithm_combo.setCurrentText("MD5")
            
    def _on_algorithm_changed(self, algorithm_text: str):
        """Handle algorithm selection change"""
        algorithm_map = {
            "SHA-256": "sha256",
            "SHA-1": "sha1", 
            "MD5": "md5"
        }
        algorithm = algorithm_map.get(algorithm_text, "sha256")
        settings.hash_algorithm = algorithm
        self._log(f"Hash algorithm changed to {algorithm_text}")
        
    def _update_single_hash_state(self):
        """Update single hash operation state"""
        files, folders = self.single_files_panel.get_all_items()
        total_count = len(files) + len(folders)
        
        if total_count == 0:
            self.single_count_label.setText("No files selected")
        else:
            self.single_count_label.setText(f"{total_count} items selected ({len(files)} files, {len(folders)} folders)")
            
        self.single_hash_btn.setEnabled(total_count > 0 and not self.operation_active)
        
    def _update_verification_state(self):
        """Update verification operation state"""
        source_files, source_folders = self.source_files_panel.get_all_items()
        target_files, target_folders = self.target_files_panel.get_all_items()
        
        source_count = len(source_files) + len(source_folders)
        target_count = len(target_files) + len(target_folders)
        
        if source_count == 0 and target_count == 0:
            self.verification_count_label.setText("No files selected")
        else:
            self.verification_count_label.setText(f"Source: {source_count} items | Target: {target_count} items")
            
        self.verify_hashes_btn.setEnabled(source_count > 0 and target_count > 0 and not self.operation_active)
        
    def _show_settings(self):
        """Show hash settings dialog"""
        # Placeholder for future settings dialog
        self._log("Hash settings dialog not yet implemented")
        
    def _cancel_all_operations(self):
        """Cancel all running operations"""
        if self.hash_controller.is_operation_running():
            self._log("Cancelling all hash operations...")
            self.hash_controller.cancel_current_operation()
            self._set_operation_active(False)
            
    def _start_single_hash_operation(self):
        """Start single hash operation"""
        try:
            files, folders = self.single_files_panel.get_all_items()
            all_paths = files + folders
            
            if not all_paths:
                self._show_error("No files selected for hash operation")
                return
                
            algorithm = settings.hash_algorithm
            
            # Get actual file count by expanding folders
            from core.hash_operations import HashOperations
            temp_hash_ops = HashOperations(algorithm)
            file_list = temp_hash_ops.discover_files(all_paths)
            file_count = len(file_list)
            
            self._log(f"Starting single hash operation with {algorithm.upper()} on {file_count} files...")
            
            # Update UI state
            self._set_operation_active(True, 'single_hash')
            self.results_panel.update_operation_status('single_hash', 'in_progress')
            
            # Start worker
            worker = self.hash_controller.start_single_hash_operation(all_paths, algorithm)
            worker.progress_update.connect(self._on_progress_update)
            worker.result_ready.connect(self._on_single_hash_result)
            worker.start()
            
        except Exception as e:
            self._log(f"Error starting single hash operation: {e}")
            self._show_error("Failed to start hash operation")
            self._set_operation_active(False)
            
    def _start_verification_operation(self):
        """Start verification operation"""
        try:
            source_files, source_folders = self.source_files_panel.get_all_items()
            target_files, target_folders = self.target_files_panel.get_all_items()
            
            source_paths = source_files + source_folders
            target_paths = target_files + target_folders
            
            if not source_paths:
                self._show_error("No source files selected for verification")
                return
                
            if not target_paths:
                self._show_error("No target files selected for verification")
                return
                
            algorithm = settings.hash_algorithm
            self._log(f"Starting verification operation with {algorithm.upper()}...")
            
            # Get actual file counts by expanding folders
            from core.hash_operations import HashOperations
            temp_hash_ops = HashOperations(algorithm)
            source_file_list = temp_hash_ops.discover_files(source_paths)
            target_file_list = temp_hash_ops.discover_files(target_paths)
            
            source_file_count = len(source_file_list)
            target_file_count = len(target_file_list)
            
            self._log(f"Source: {source_file_count} files, Target: {target_file_count} files")
            
            # Update UI state
            self._set_operation_active(True, 'verification')
            self.results_panel.update_operation_status('verification', 'in_progress')
            
            # Start worker
            worker = self.hash_controller.start_verification_operation(source_paths, target_paths, algorithm)
            worker.progress_update.connect(self._on_progress_update)
            worker.result_ready.connect(self._on_verification_result)
            worker.start()
            
        except Exception as e:
            self._log(f"Error starting verification operation: {e}")
            self._show_error("Failed to start verification operation")
            self._set_operation_active(False)
            
    def _on_progress_update(self, percentage: int, message: str):
        """Handle progress updates"""
        self.progress_bar.setValue(percentage)
        self.progress_label.setText(message)
        
        # Only log significant progress messages to avoid spam
        if not message.startswith("Hashing") or percentage % 20 == 0:
            self._log(f"Progress: {percentage}% - {message}")
            
    def _on_single_hash_result(self, result):
        """Handle single hash operation completion"""
        from core.result_types import Result
        
        self._set_operation_active(False)
        
        if isinstance(result, Result) and result.success:
            self.current_single_results = result.value
            self.results_panel.update_operation_status('single_hash', 'completed', result.value)
            self._log("Single hash operation completed successfully!")
        else:
            self.results_panel.update_operation_status('single_hash', 'failed')
            error_msg = result.error.user_message if hasattr(result, 'error') and result.error else "Hash operation failed"
            self._log(f"Single hash operation failed: {error_msg}")
            
    def _on_verification_result(self, result):
        """Handle verification operation completion"""
        from core.result_types import Result
        
        self._set_operation_active(False)
        
        if isinstance(result, Result) and result.success:
            self.current_verification_results = result.value
            self.results_panel.update_operation_status('verification', 'completed', result.value)
            self._log("Verification operation completed successfully!")
        else:
            # CRITICAL FIX: Failed verifications still have results - pass them to UI for export
            if isinstance(result, Result) and result.value:
                self.current_verification_results = result.value
                self.results_panel.update_operation_status('verification', 'failed', result.value)
            else:
                self.current_verification_results = {}
                self.results_panel.update_operation_status('verification', 'failed')
            
            error_msg = result.error.user_message if hasattr(result, 'error') and result.error else "Verification operation failed"
            self._log(f"Verification operation failed: {error_msg}")
            
    def _handle_export_request(self, operation_type: str, results: Dict):
        """Handle export request from results panel"""
        if operation_type == 'single_hash':
            self._export_single_hash_csv(results)
        elif operation_type == 'verification':
            self._export_verification_csv(results)
            
    def _export_single_hash_csv(self, results: Optional[Dict] = None):
        """Export single hash results to CSV"""
        results = results or self.current_single_results
        if not results:
            self._show_error("No hash results available for export")
            return
            
        try:
            algorithm = settings.hash_algorithm
            default_filename = f"hash_report_{algorithm}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save Hash Report", default_filename,
                "CSV Files (*.csv);;All Files (*)"
            )
            
            if filename:
                success = self.report_generator.generate_single_hash_csv(
                    results.get('results', []), Path(filename), algorithm
                )
                
                if success:
                    self._log(f"Hash report exported to: {filename}")
                else:
                    self._show_error("Failed to export hash report")
                    
        except Exception as e:
            self._log(f"Error exporting hash report: {e}")
            self._show_error("Error occurred while exporting hash report")
            
    def _export_verification_csv(self, results: Optional[Dict] = None):
        """Export verification results to CSV"""
        results = results or self.current_verification_results
        if not results:
            self._show_error("No verification results available for export")
            return
            
        try:
            algorithm = settings.hash_algorithm
            default_filename = f"verification_report_{algorithm}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save Verification Report", default_filename,
                "CSV Files (*.csv);;All Files (*)"
            )
            
            if filename:
                success = self.report_generator.generate_verification_csv_from_dict(
                    results, Path(filename), algorithm
                )
                
                if success:
                    self._log(f"Verification report exported to: {filename}")
                else:
                    self._show_error("Failed to export verification report")
                    
        except Exception as e:
            self._log(f"Error exporting verification report: {e}")
            self._show_error("Error occurred while exporting verification report")
            
    def _set_operation_active(self, active: bool, operation_type: Optional[str] = None):
        """Set operation active state and update UI"""
        self.operation_active = active
        self.current_operation_type = operation_type
        
        # Update status indicator
        if active:
            self.status_indicator.setText(f"🟡 Processing {operation_type or 'operation'}")
            self.status_indicator.setStyleSheet("color: #ffc107; font-weight: bold;")
            self.status_message.emit(f"Hash operation in progress...")
        else:
            self.status_indicator.setText("🟢 Ready")
            self.status_indicator.setStyleSheet("color: #28a745; font-weight: bold;")
            self.status_message.emit("Ready")
            
        # Update progress bar
        self.progress_bar.setVisible(active)
        if not active:
            self.progress_bar.setValue(0)
            self.progress_label.setText("Ready to process files")
            
        # Update button states
        self._update_single_hash_state()
        self._update_verification_state()
        
        # Update controls
        self.algorithm_combo.setEnabled(not active)
        self.cancel_all_btn.setEnabled(active)
        
    def _log(self, message: str):
        """Log a message to console and emit signal"""
        self.log_console.log(message)
        self.log_message.emit(message)
        
    def _show_error(self, message: str):
        """Show error message via error handling system"""
        error = UIError(
            message,
            user_message=message,
            component="HashingTab",
            severity=ErrorSeverity.WARNING
        )
        handle_error(error, {'operation': 'hash_operation'})
        
    def cancel_current_operation(self):
        """Cancel current operation if running"""
        if self.operation_active:
            self._cancel_all_operations()