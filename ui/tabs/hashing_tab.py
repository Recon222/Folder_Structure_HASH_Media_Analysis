#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hashing Tab - Interface for file hashing and verification operations
"""

from pathlib import Path
from typing import List, Optional, Dict, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSplitter,
    QGroupBox, QComboBox, QLabel, QFileDialog, QMessageBox,
    QProgressBar, QFrame
)

from controllers.hash_controller import HashController
from core.settings_manager import settings
from core.hash_reports import HashReportGenerator
from core.logger import logger
from ui.components import FilesPanel, LogConsole


class HashingTab(QWidget):
    """Hashing tab for file hash operations and verification"""
    
    # Signals
    log_message = Signal(str)
    status_message = Signal(str)
    
    def __init__(self, parent=None):
        """Initialize hashing tab"""
        super().__init__(parent)
        
        # Controllers and utilities
        self.hash_controller = HashController()
        self.report_generator = HashReportGenerator()
        
        # Current operation results
        self.current_single_results = None
        self.current_verification_results = None
        
        # UI state
        self.operation_active = False
        
        self._create_ui()
        self._connect_signals()
        self._load_settings()
        
    def _create_ui(self):
        """Create the tab UI"""
        layout = QVBoxLayout(self)
        
        # Algorithm selection section
        algorithm_group = QGroupBox("Hash Algorithm")
        algorithm_layout = QHBoxLayout(algorithm_group)
        
        algorithm_layout.addWidget(QLabel("Algorithm:"))
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(["SHA-256", "MD5"])
        algorithm_layout.addWidget(self.algorithm_combo)
        algorithm_layout.addStretch()
        
        layout.addWidget(algorithm_group)
        
        # Main content splitter (operations on left, console on right)
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left side: Operations
        operations_widget = QWidget()
        operations_layout = QVBoxLayout(operations_widget)
        
        # Single Hash Section
        single_hash_group = self._create_single_hash_section()
        operations_layout.addWidget(single_hash_group)
        
        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        operations_layout.addWidget(separator)
        
        # Verification Section
        verification_group = self._create_verification_section()
        operations_layout.addWidget(verification_group)
        
        # Right side: Console
        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        
        console_layout.addWidget(QLabel("Processing Console:"))
        self.log_console = LogConsole()
        self.log_console.setMinimumHeight(400)  # Make it large
        console_layout.addWidget(self.log_console)
        
        # Add to splitter
        main_splitter.addWidget(operations_widget)
        main_splitter.addWidget(console_widget)
        main_splitter.setStretchFactor(0, 1)  # Operations section
        main_splitter.setStretchFactor(1, 1)  # Console section (equal weight)
        
        layout.addWidget(main_splitter)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
    def _create_single_hash_section(self) -> QGroupBox:
        """Create single hash operation section"""
        group = QGroupBox("Single Hash Operation")
        layout = QVBoxLayout(group)
        
        # Description
        desc_label = QLabel("Select files or folders to calculate hashes. Folders will be processed recursively.")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Files panel
        self.single_files_panel = FilesPanel()
        self.single_files_panel.setMaximumHeight(200)
        layout.addWidget(self.single_files_panel)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.single_hash_btn = QPushButton("Calculate Hashes")
        self.single_hash_btn.setEnabled(False)
        button_layout.addWidget(self.single_hash_btn)
        
        self.export_single_csv_btn = QPushButton("Export CSV")
        self.export_single_csv_btn.setEnabled(False)
        button_layout.addWidget(self.export_single_csv_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        return group
        
    def _create_verification_section(self) -> QGroupBox:
        """Create verification operation section"""
        group = QGroupBox("Hash Verification")
        layout = QVBoxLayout(group)
        
        # Description
        desc_label = QLabel("Select source and target files/folders to compare their hashes.")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Source and target panels
        panels_layout = QHBoxLayout()
        
        # Source panel
        source_widget = QWidget()
        source_layout = QVBoxLayout(source_widget)
        source_layout.addWidget(QLabel("Source Files/Folders:"))
        self.source_files_panel = FilesPanel()
        self.source_files_panel.setMaximumHeight(150)
        source_layout.addWidget(self.source_files_panel)
        
        # Target panel
        target_widget = QWidget()
        target_layout = QVBoxLayout(target_widget)
        target_layout.addWidget(QLabel("Target Files/Folders:"))
        self.target_files_panel = FilesPanel()
        self.target_files_panel.setMaximumHeight(150)
        target_layout.addWidget(self.target_files_panel)
        
        panels_layout.addWidget(source_widget)
        panels_layout.addWidget(target_widget)
        layout.addLayout(panels_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.verify_hashes_btn = QPushButton("Verify Hashes")
        self.verify_hashes_btn.setEnabled(False)
        button_layout.addWidget(self.verify_hashes_btn)
        
        self.export_verification_csv_btn = QPushButton("Export CSV")
        self.export_verification_csv_btn.setEnabled(False)
        button_layout.addWidget(self.export_verification_csv_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        return group
        
    def _connect_signals(self):
        """Connect internal signals"""
        # Algorithm change
        self.algorithm_combo.currentTextChanged.connect(self._on_algorithm_changed)
        
        # Files panel changes
        self.single_files_panel.files_changed.connect(self._update_single_hash_button_state)
        self.single_files_panel.log_message.connect(self._log)
        
        self.source_files_panel.files_changed.connect(self._update_verification_button_state)
        self.source_files_panel.log_message.connect(self._log)
        
        self.target_files_panel.files_changed.connect(self._update_verification_button_state)
        self.target_files_panel.log_message.connect(self._log)
        
        # Operation buttons
        self.single_hash_btn.clicked.connect(self._start_single_hash_operation)
        self.verify_hashes_btn.clicked.connect(self._start_verification_operation)
        
        # Export buttons
        self.export_single_csv_btn.clicked.connect(self._export_single_hash_csv)
        self.export_verification_csv_btn.clicked.connect(self._export_verification_csv)
        
    def _load_settings(self):
        """Load settings and set initial state"""
        # Set algorithm from settings
        algorithm = settings.hash_algorithm
        if algorithm == 'sha256':
            self.algorithm_combo.setCurrentText("SHA-256")
        elif algorithm == 'md5':
            self.algorithm_combo.setCurrentText("MD5")
            
    def _on_algorithm_changed(self, algorithm_text: str):
        """Handle algorithm selection change"""
        algorithm = algorithm_text.lower().replace('-', '')
        settings.hash_algorithm = algorithm
        self._log(f"Hash algorithm changed to {algorithm_text}")
        
    def _update_single_hash_button_state(self):
        """Update single hash button enabled state"""
        files, folders = self.single_files_panel.get_all_items()
        has_items = len(files) > 0 or len(folders) > 0
        self.single_hash_btn.setEnabled(has_items and not self.operation_active)
        
    def _update_verification_button_state(self):
        """Update verification button enabled state"""
        source_files, source_folders = self.source_files_panel.get_all_items()
        target_files, target_folders = self.target_files_panel.get_all_items()
        
        has_source = len(source_files) > 0 or len(source_folders) > 0
        has_target = len(target_files) > 0 or len(target_folders) > 0
        
        self.verify_hashes_btn.setEnabled(has_source and has_target and not self.operation_active)
        
    def _start_single_hash_operation(self):
        """Start single hash operation"""
        try:
            # Get files and folders
            files, folders = self.single_files_panel.get_all_items()
            all_paths = files + folders
            
            if not all_paths:
                QMessageBox.warning(self, "No Files Selected", "Please select files or folders to hash.")
                return
                
            # Get algorithm
            algorithm = settings.hash_algorithm
            
            # Start operation
            self._log(f"Starting single hash operation with {algorithm.upper()} on {len(all_paths)} items...")
            self._set_operation_active(True)
            
            # Create and start worker
            worker = self.hash_controller.start_single_hash_operation(all_paths, algorithm)
            worker.progress.connect(self.progress_bar.setValue)
            worker.status.connect(self._log)
            worker.finished.connect(self._on_single_hash_finished)
            worker.start()
            
        except Exception as e:
            self._log(f"Error starting single hash operation: {e}")
            QMessageBox.critical(self, "Operation Error", f"Failed to start hash operation:\n{str(e)}")
            self._set_operation_active(False)
            
    def _start_verification_operation(self):
        """Start verification operation"""
        try:
            # Get source files and folders
            source_files, source_folders = self.source_files_panel.get_all_items()
            source_paths = source_files + source_folders
            
            # Get target files and folders
            target_files, target_folders = self.target_files_panel.get_all_items()
            target_paths = target_files + target_folders
            
            if not source_paths:
                QMessageBox.warning(self, "No Source Files", "Please select source files or folders.")
                return
                
            if not target_paths:
                QMessageBox.warning(self, "No Target Files", "Please select target files or folders.")
                return
                
            # Get algorithm
            algorithm = settings.hash_algorithm
            
            # Start operation
            self._log(f"Starting verification operation with {algorithm.upper()}...")
            self._log(f"Source: {len(source_paths)} items, Target: {len(target_paths)} items")
            self._set_operation_active(True)
            
            # Create and start worker
            worker = self.hash_controller.start_verification_operation(source_paths, target_paths, algorithm)
            worker.progress.connect(self.progress_bar.setValue)
            worker.status.connect(self._log)
            worker.finished.connect(self._on_verification_finished)
            worker.start()
            
        except Exception as e:
            self._log(f"Error starting verification operation: {e}")
            QMessageBox.critical(self, "Operation Error", f"Failed to start verification operation:\n{str(e)}")
            self._set_operation_active(False)
            
    def _on_single_hash_finished(self, success: bool, message: str, results: Optional[Dict]):
        """Handle single hash operation completion"""
        self._set_operation_active(False)
        
        if success:
            self.current_single_results = results
            self.export_single_csv_btn.setEnabled(True)
            
            # Log summary
            if results and 'summary' in results:
                summary = results['summary']
                self._log(f"Operation completed: {summary['successful_files']}/{summary['total_files']} files processed")
                if summary['failed_files'] > 0:
                    self._log(f"Failed files: {summary['failed_files']}")
                self._log(f"Total size: {summary['total_size_mb']:.1f} MB")
                self._log(f"Processing time: {summary['duration_seconds']:.1f} seconds")
                if summary['average_speed_mbps'] > 0:
                    self._log(f"Average speed: {summary['average_speed_mbps']:.1f} MB/s")
            
            self._log("Single hash operation completed successfully!")
            QMessageBox.information(self, "Operation Complete", message)
        else:
            self._log(f"Single hash operation failed: {message}")
            QMessageBox.critical(self, "Operation Failed", f"Hash operation failed:\n{message}")
            
    def _on_verification_finished(self, success: bool, message: str, results: Optional[Dict]):
        """Handle verification operation completion"""
        self._set_operation_active(False)
        
        if success:
            self.current_verification_results = results
            self.export_verification_csv_btn.setEnabled(True)
            
            # Log summary
            if results and 'summary' in results:
                summary = results['summary']
                self._log(f"Verification completed: {summary['matches']}/{summary['total_comparisons']} files match")
                if summary['mismatches'] > 0:
                    self._log(f"Mismatches: {summary['mismatches']}")
                if summary['missing_targets'] > 0:
                    self._log(f"Missing targets: {summary['missing_targets']}")
                if summary['source_errors'] + summary['target_errors'] > 0:
                    self._log(f"Errors: {summary['source_errors'] + summary['target_errors']}")
                self._log(f"Processing time: {summary['duration_seconds']:.1f} seconds")
                if summary['average_speed_mbps'] > 0:
                    self._log(f"Average speed: {summary['average_speed_mbps']:.1f} MB/s")
                    
            self._log("Verification operation completed successfully!")
            QMessageBox.information(self, "Verification Complete", message)
        else:
            self._log(f"Verification operation failed: {message}")
            QMessageBox.critical(self, "Operation Failed", f"Verification operation failed:\n{message}")
            
    def _export_single_hash_csv(self):
        """Export single hash results to CSV"""
        if not self.current_single_results:
            QMessageBox.warning(self, "No Results", "No hash results to export.")
            return
            
        try:
            # Get save location
            algorithm = settings.hash_algorithm
            default_filename = self.report_generator.get_default_filename('hash', algorithm)
            
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Save Hash Report",
                default_filename,
                "CSV Files (*.csv);;All Files (*)"
            )
            
            if not filename:
                return
                
            # Generate report
            results = self.current_single_results['results']
            success = self.report_generator.generate_single_hash_csv(
                results, Path(filename), algorithm
            )
            
            if success:
                self._log(f"Hash report exported to: {filename}")
                QMessageBox.information(self, "Export Complete", f"Hash report saved to:\n{filename}")
            else:
                self._log("Failed to export hash report")
                QMessageBox.critical(self, "Export Failed", "Failed to export hash report.")
                
        except Exception as e:
            self._log(f"Error exporting hash report: {e}")
            QMessageBox.critical(self, "Export Error", f"Error exporting report:\n{str(e)}")
            
    def _export_verification_csv(self):
        """Export verification results to CSV"""
        if not self.current_verification_results:
            QMessageBox.warning(self, "No Results", "No verification results to export.")
            return
            
        try:
            # Get save location
            algorithm = settings.hash_algorithm
            default_filename = self.report_generator.get_default_filename('verification', algorithm)
            
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Save Verification Report",
                default_filename,
                "CSV Files (*.csv);;All Files (*)"
            )
            
            if not filename:
                return
                
            # Generate report
            results = self.current_verification_results['verification_results']
            success = self.report_generator.generate_verification_csv(
                results, Path(filename), algorithm
            )
            
            if success:
                self._log(f"Verification report exported to: {filename}")
                QMessageBox.information(self, "Export Complete", f"Verification report saved to:\n{filename}")
            else:
                self._log("Failed to export verification report")
                QMessageBox.critical(self, "Export Failed", "Failed to export verification report.")
                
        except Exception as e:
            self._log(f"Error exporting verification report: {e}")
            QMessageBox.critical(self, "Export Error", f"Error exporting report:\n{str(e)}")
            
    def _set_operation_active(self, active: bool):
        """Set operation active state and update UI"""
        self.operation_active = active
        
        # Update progress bar
        self.progress_bar.setVisible(active)
        if not active:
            self.progress_bar.setValue(0)
            
        # Update button states
        self._update_single_hash_button_state()
        self._update_verification_button_state()
        
        # Update algorithm combo
        self.algorithm_combo.setEnabled(not active)
        
        # Emit status
        if active:
            self.status_message.emit("Hash operation in progress...")
        else:
            self.status_message.emit("Ready")
            
    def _log(self, message: str):
        """Log a message to console and emit signal"""
        self.log_console.log(message)
        self.log_message.emit(message)
        
    def cancel_current_operation(self):
        """Cancel current operation if running"""
        if self.hash_controller.is_operation_running():
            self._log("Cancelling current hash operation...")
            self.hash_controller.cancel_current_operation()
            self._set_operation_active(False)