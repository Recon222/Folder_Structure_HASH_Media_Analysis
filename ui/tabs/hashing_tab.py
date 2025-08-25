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
    QGroupBox, QComboBox, QLabel, QFileDialog,
    QProgressBar, QFrame
)

from controllers.hash_controller import HashController
from core.settings_manager import settings
from core.hash_reports import HashReportGenerator
from core.logger import logger
from ui.components import FilesPanel, LogConsole
from core.exceptions import UIError, ErrorSeverity
from core.error_handler import handle_error


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
        
        # Main content splitter (operations on top, console on bottom)
        main_splitter = QSplitter(Qt.Vertical)
        
        # Top: Operations section (40% height)
        operations_widget = QWidget()
        operations_layout = QHBoxLayout(operations_widget)  # Side-by-side operations
        
        # Single Hash Section
        single_hash_group = self._create_single_hash_section()
        operations_layout.addWidget(single_hash_group)
        
        # Verification Section  
        verification_group = self._create_verification_section()
        operations_layout.addWidget(verification_group)
        
        # Bottom: Console section (60% height)
        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        console_layout.setContentsMargins(5, 5, 5, 5)  # Reduce margins
        console_layout.setSpacing(0)  # Remove spacing between label and console
        
        console_label = QLabel("Processing Console:")
        console_layout.addWidget(console_label)
        self.log_console = LogConsole()
        self.log_console.setMaximumHeight(16777215)  # Remove the 150px max height restriction
        self.log_console.setMinimumHeight(350)  # Large console
        console_layout.addWidget(self.log_console)
        
        # Add to vertical splitter
        main_splitter.addWidget(operations_widget)
        main_splitter.addWidget(console_widget)
        main_splitter.setStretchFactor(0, 2)  # Operations: 40% height
        main_splitter.setStretchFactor(1, 3)  # Console: 60% height
        
        # Set initial splitter sizes to enforce the ratio
        main_splitter.setSizes([400, 600])  # 40% / 60% split
        
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
        
        # Horizontal layout: files panel on left, buttons on right
        content_layout = QHBoxLayout()
        
        # Files panel - takes most of the space (compact buttons, no remove button)
        self.single_files_panel = FilesPanel(show_remove_selected=False, compact_buttons=True)
        self.single_files_panel.setMinimumHeight(120)  # Compact height
        content_layout.addWidget(self.single_files_panel, stretch=3)  # 75% of width
        
        # Buttons section on the right
        button_widget = QWidget()
        button_layout = QVBoxLayout(button_widget)
        button_layout.setContentsMargins(10, 0, 0, 0)  # Add some left margin
        
        self.single_hash_btn = QPushButton("Calculate Hashes")
        self.single_hash_btn.setEnabled(False)
        self.single_hash_btn.setMinimumWidth(120)
        button_layout.addWidget(self.single_hash_btn)
        
        self.export_single_csv_btn = QPushButton("Export CSV")
        self.export_single_csv_btn.setEnabled(False)
        self.export_single_csv_btn.setMinimumWidth(120)
        button_layout.addWidget(self.export_single_csv_btn)
        
        button_layout.addStretch()  # Push buttons to top
        content_layout.addWidget(button_widget, stretch=1)  # 25% of width
        
        layout.addLayout(content_layout)
        
        return group
        
    def _create_verification_section(self) -> QGroupBox:
        """Create verification operation section"""
        group = QGroupBox("Hash Verification")
        layout = QVBoxLayout(group)
        
        # Description
        desc_label = QLabel("Select source and target files/folders to compare their hashes.")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Horizontal layout: source panel on left, target panel on right
        panels_layout = QHBoxLayout()
        
        # Source panel
        source_widget = QWidget()
        source_layout = QVBoxLayout(source_widget)
        source_layout.setContentsMargins(0, 0, 5, 0)  # Small right margin
        source_layout.addWidget(QLabel("Source Files/Folders:"))
        self.source_files_panel = FilesPanel(show_remove_selected=False, compact_buttons=True)
        self.source_files_panel.setMinimumHeight(120)  # Compact height
        source_layout.addWidget(self.source_files_panel)
        
        # Target panel
        target_widget = QWidget()
        target_layout = QVBoxLayout(target_widget)
        target_layout.setContentsMargins(5, 0, 0, 0)  # Small left margin
        target_layout.addWidget(QLabel("Target Files/Folders:"))
        self.target_files_panel = FilesPanel(show_remove_selected=False, compact_buttons=True)
        self.target_files_panel.setMinimumHeight(120)  # Compact height
        target_layout.addWidget(self.target_files_panel)
        
        # Add both panels side by side with equal width
        panels_layout.addWidget(source_widget, stretch=1)
        panels_layout.addWidget(target_widget, stretch=1)
        
        layout.addLayout(panels_layout)
        
        # Buttons at the bottom
        button_layout = QHBoxLayout()
        
        self.verify_hashes_btn = QPushButton("Verify Hashes")
        self.verify_hashes_btn.setEnabled(False)
        self.verify_hashes_btn.setMinimumWidth(120)
        button_layout.addWidget(self.verify_hashes_btn)
        
        self.export_verification_csv_btn = QPushButton("Export CSV")
        self.export_verification_csv_btn.setEnabled(False)
        self.export_verification_csv_btn.setMinimumWidth(120)
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
                error = UIError(
                    "No files selected for hash operation",
                    user_message="Please select files or folders to hash before starting the operation.",
                    component="HashingTab"
                )
                handle_error(error, {'operation': 'hash_file_selection'})
                return
                
            # Get algorithm
            algorithm = settings.hash_algorithm
            
            # Start operation
            self._log(f"Starting single hash operation with {algorithm.upper()} on {len(all_paths)} items...")
            self._set_operation_active(True)
            
            # Create and start worker
            worker = self.hash_controller.start_single_hash_operation(all_paths, algorithm)
            # Nuclear migration: Use unified signals
            worker.progress_update.connect(lambda pct, msg: (
                self.progress_bar.setValue(pct), 
                self._log(msg) if not msg.startswith("Hashing") else None
            ))
            worker.result_ready.connect(self._on_single_hash_result)
            worker.start()
            
        except Exception as e:
            self._log(f"Error starting single hash operation: {e}")
            error = UIError(
                f"Hash operation startup failed: {str(e)}",
                user_message="Failed to start hash operation. Please check the selected files and try again.",
                component="HashingTab"
            )
            handle_error(error, {'operation': 'hash_start', 'algorithm': settings.hash_algorithm})
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
                error = UIError(
                    "No source files selected for verification",
                    user_message="Please select source files or folders for verification.",
                    component="HashingTab"
                )
                handle_error(error, {'operation': 'verification_source_selection'})
                return
                
            if not target_paths:
                error = UIError(
                    "No target files selected for verification",
                    user_message="Please select target files or folders for verification.",
                    component="HashingTab"
                )
                handle_error(error, {'operation': 'verification_target_selection'})
                return
                
            # Get algorithm
            algorithm = settings.hash_algorithm
            
            # Start operation
            self._log(f"Starting verification operation with {algorithm.upper()}...")
            self._log(f"Source: {len(source_paths)} items, Target: {len(target_paths)} items")
            self._set_operation_active(True)
            
            # Create and start worker
            worker = self.hash_controller.start_verification_operation(source_paths, target_paths, algorithm)
            # Nuclear migration: Use unified signals
            worker.progress_update.connect(lambda pct, msg: (
                self.progress_bar.setValue(pct), 
                self._log(msg) if not msg.startswith("Hashing") else None
            ))
            worker.result_ready.connect(self._on_verification_result)
            worker.start()
            
        except Exception as e:
            self._log(f"Error starting verification operation: {e}")
            error = UIError(
                f"Verification operation startup failed: {str(e)}",
                user_message="Failed to start verification operation. Please check the selected files and try again.",
                component="HashingTab"
            )
            handle_error(error, {'operation': 'verification_start', 'algorithm': settings.hash_algorithm})
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
            success_error = UIError(
                "Hash operation completed successfully",
                user_message=message,
                component="HashingTab",
                severity=ErrorSeverity.INFO
            )
            handle_error(success_error, {'operation': 'hash_completion'})
        else:
            self._log(f"Single hash operation failed: {message}")
            error = UIError(
                f"Hash operation failed: {message}",
                user_message="Hash operation could not complete successfully. Please check the log for details.",
                component="HashingTab"
            )
            handle_error(error, {'operation': 'hash_completion', 'severity': 'critical'})
            
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
            success_error = UIError(
                "Verification operation completed successfully",
                user_message=message,
                component="HashingTab",
                severity=ErrorSeverity.INFO
            )
            handle_error(success_error, {'operation': 'verification_completion'})
        else:
            self._log(f"Verification operation failed: {message}")
            error = UIError(
                f"Verification operation failed: {message}",
                user_message="Verification operation could not complete successfully. Please check the log for details.",
                component="HashingTab"
            )
            handle_error(error, {'operation': 'verification_completion', 'severity': 'critical'})
            
    def _on_single_hash_result(self, result):
        """Handle single hash operation completion (nuclear migration)"""
        from core.result_types import Result
        
        self._set_operation_active(False)
        
        if isinstance(result, Result):
            if result.success:
                self.current_single_results = result.value
                self.export_single_csv_btn.setEnabled(True)
                
                # Log summary from HashOperationResult
                if hasattr(result, 'files_hashed') and result.files_hashed > 0:
                    self._log(f"Operation completed: {result.files_hashed} files processed")
                    if hasattr(result, 'processing_time'):
                        self._log(f"Processing time: {result.processing_time:.1f} seconds")
                
                message = "Single hash operation completed successfully!"
                self._log(message)
                success_error = UIError(
                    "Hash operation completed successfully",
                    user_message=message,
                    component="HashingTab",
                    severity=ErrorSeverity.INFO
                )
                handle_error(success_error, {'operation': 'hash_result_completion'})
            else:
                error_msg = result.error.user_message if result.error and hasattr(result.error, 'user_message') else "Hash operation failed"
                self._log(f"Single hash operation failed: {error_msg}")
                error = UIError(
                    f"Hash operation failed: {error_msg}",
                    user_message="Hash operation encountered an error. Please check the log for details.",
                    component="HashingTab"
                )
                handle_error(error, {'operation': 'hash_result_error'})
        else:
            # Fallback for unexpected result format
            self._log("Single hash operation completed with unexpected result format")
            error = UIError(
                "Hash operation completed with unexpected result format",
                user_message="Hash operation completed but result format was unexpected. Results may not be available.",
                component="HashingTab",
                severity=ErrorSeverity.WARNING
            )
            handle_error(error, {'operation': 'hash_result_format'})
            
    def _on_verification_result(self, result):
        """Handle verification operation completion (nuclear migration)"""
        from core.result_types import Result
        
        self._set_operation_active(False)
        
        if isinstance(result, Result):
            if result.success:
                self.current_verification_results = result.value
                self.export_verification_csv_btn.setEnabled(True)
                
                # Log summary from HashOperationResult
                if hasattr(result, 'files_hashed') and result.files_hashed > 0:
                    self._log(f"Verification completed: {result.files_hashed} files processed")
                    if hasattr(result, 'verification_failures') and result.verification_failures > 0:
                        self._log(f"Mismatches: {result.verification_failures}")
                    if hasattr(result, 'processing_time'):
                        self._log(f"Processing time: {result.processing_time:.1f} seconds")
                
                message = "Verification operation completed successfully!"
                self._log(message)
                success_error = UIError(
                    "Verification operation completed successfully",
                    user_message=message,
                    component="HashingTab",
                    severity=ErrorSeverity.INFO
                )
                handle_error(success_error, {'operation': 'verification_completion'})
            else:
                error_msg = result.error.user_message if result.error and hasattr(result.error, 'user_message') else "Verification operation failed"
                self._log(f"Verification operation failed: {error_msg}")
                error = UIError(
                    f"Verification operation failed: {error_msg}",
                    user_message="Verification operation encountered an error. Please check the log for details.",
                    component="HashingTab"
                )
                handle_error(error, {'operation': 'verification_result_error'})
        else:
            # Fallback for unexpected result format
            self._log("Verification operation completed with unexpected result format")
            error = UIError(
                "Verification operation completed with unexpected result format",
                user_message="Verification operation completed but result format was unexpected. Results may not be available.",
                component="HashingTab",
                severity=ErrorSeverity.WARNING
            )
            handle_error(error, {'operation': 'verification_result_format'})
            
    def _export_single_hash_csv(self):
        """Export single hash results to CSV"""
        if not self.current_single_results:
            error = UIError(
                "No hash results available for export",
                user_message="No hash results to export. Please run a hash operation first.",
                component="HashingTab",
                severity=ErrorSeverity.WARNING
            )
            handle_error(error, {'operation': 'export_validation'})
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
                success_error = UIError(
                    f"Hash report exported successfully to {filename}",
                    user_message=f"Hash report saved to:\n{filename}",
                    component="HashingTab",
                    severity=ErrorSeverity.INFO
                )
                handle_error(success_error, {'operation': 'hash_export_success', 'filename': filename})
            else:
                self._log("Failed to export hash report")
                error = UIError(
                    "Hash report export failed",
                    user_message="Failed to export hash report. Please check folder permissions and try again.",
                    component="HashingTab"
                )
                handle_error(error, {'operation': 'hash_export'})
                
        except Exception as e:
            self._log(f"Error exporting hash report: {e}")
            error = UIError(
                f"Hash report export error: {str(e)}",
                user_message="Error occurred while exporting hash report. Please check permissions and try again.",
                component="HashingTab"
            )
            handle_error(error, {'operation': 'hash_export_error'})
            
    def _export_verification_csv(self):
        """Export verification results to CSV"""
        if not self.current_verification_results:
            error = UIError(
                "No verification results available for export",
                user_message="No verification results to export. Please run a verification operation first.",
                component="HashingTab",
                severity=ErrorSeverity.WARNING
            )
            handle_error(error, {'operation': 'verification_export_validation'})
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
            # With nuclear migration, verification results are in the result.value dict directly
            results = self.current_verification_results
            success = self.report_generator.generate_verification_csv_from_dict(
                results, Path(filename), algorithm
            )
            
            if success:
                self._log(f"Verification report exported to: {filename}")
                success_error = UIError(
                    f"Verification report exported successfully to {filename}",
                    user_message=f"Verification report saved to:\n{filename}",
                    component="HashingTab",
                    severity=ErrorSeverity.INFO
                )
                handle_error(success_error, {'operation': 'verification_export_success', 'filename': filename})
            else:
                self._log("Failed to export verification report")
                error = UIError(
                    "Verification report export failed",
                    user_message="Failed to export verification report. Please check folder permissions and try again.",
                    component="HashingTab"
                )
                handle_error(error, {'operation': 'verification_export_failed'})
                
        except Exception as e:
            self._log(f"Error exporting verification report: {e}")
            error = UIError(
                f"Verification report export error: {str(e)}",
                user_message="Error occurred while exporting verification report. Please check permissions and try again.",
                component="HashingTab"
            )
            handle_error(error, {'operation': 'verification_export_error'})
            
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