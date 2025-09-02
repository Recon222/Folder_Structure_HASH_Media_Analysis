#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copy & Verify Tab - Direct file/folder copying with hash verification
No form validation, no templates - just source to destination with integrity checking
"""

from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QCheckBox, QFileDialog, QProgressBar, QSplitter,
    QLineEdit, QMessageBox
)
from PySide6.QtGui import QFont

from ui.components import FilesPanel, LogConsole
from ui.components.elided_label import ElidedLabel
from ui.dialogs.success_dialog import SuccessDialog
from core.services.success_message_builder import SuccessMessageBuilder
from core.services.success_message_data import CopyVerifyOperationData
from core.settings_manager import settings
from core.logger import logger
from core.exceptions import UIError, ErrorSeverity
from core.error_handler import handle_error


class CopyVerifyTab(QWidget):
    """Direct copy and verify operations without form dependencies"""
    
    # Signals
    log_message = Signal(str)
    status_message = Signal(str)
    
    def __init__(self, parent=None):
        """Initialize the Copy & Verify tab"""
        super().__init__(parent)
        
        # State
        self.operation_active = False
        self.current_worker = None
        self.last_results = None
        self.destination_path = None
        self.is_paused = False
        
        self._create_ui()
        self._connect_signals()
        
    def _create_ui(self):
        """Create the tab UI with two-column layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Header
        header = self._create_header()
        layout.addWidget(header)
        
        # Main content splitter
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)
        
        # Left panel - Source and destination selection
        left_panel = self._create_selection_panel()
        main_splitter.addWidget(left_panel)
        
        # Right panel - Options and progress
        right_panel = self._create_options_panel()
        main_splitter.addWidget(right_panel)
        
        # Set splitter proportions (45/55) - give more space to options panel
        main_splitter.setSizes([450, 550])
        layout.addWidget(main_splitter)
        
        # Console section
        console_group = self._create_console_section()
        layout.addWidget(console_group)
        
    def _create_header(self) -> QGroupBox:
        """Create header with title and status"""
        header = QGroupBox("Copy & Verify Operations")
        header_layout = QHBoxLayout(header)
        
        # Title and description
        title_layout = QVBoxLayout()
        title_label = QLabel("🔄 Direct Copy with Hash Verification")
        title_label.setFont(self._get_title_font())
        title_layout.addWidget(title_label)
        
        desc_label = QLabel("Copy files and folders directly from source to destination with optional hash verification")
        desc_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        desc_label.setWordWrap(True)
        title_layout.addWidget(desc_label)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        # Status indicator
        self.status_indicator = QLabel("🟢 Ready")
        self.status_indicator.setStyleSheet("color: #28a745; font-weight: bold;")
        header_layout.addWidget(self.status_indicator)
        
        return header
        
    def _create_selection_panel(self) -> QGroupBox:
        """Create source and destination selection panel"""
        panel = QGroupBox("File Selection")
        layout = QVBoxLayout(panel)
        
        # Source files section
        source_label = QLabel("📁 Source Files and Folders:")
        source_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(source_label)
        
        self.files_panel = FilesPanel(show_remove_selected=True, compact_buttons=False)
        self.files_panel.setMinimumHeight(250)
        layout.addWidget(self.files_panel)
        
        # File count
        self.file_count_label = QLabel("No files selected")
        self.file_count_label.setStyleSheet("color: #6c757d; font-size: 10px; margin: 4px;")
        layout.addWidget(self.file_count_label)
        
        # Destination section
        dest_label = QLabel("📂 Destination Folder:")
        dest_label.setStyleSheet("font-weight: bold; margin-top: 12px;")
        layout.addWidget(dest_label)
        
        dest_layout = QHBoxLayout()
        self.dest_path_edit = QLineEdit()
        self.dest_path_edit.setPlaceholderText("Select destination folder...")
        self.dest_path_edit.setReadOnly(True)
        dest_layout.addWidget(self.dest_path_edit)
        
        self.browse_dest_btn = QPushButton("Browse...")
        self.browse_dest_btn.clicked.connect(self._browse_destination)
        dest_layout.addWidget(self.browse_dest_btn)
        
        layout.addLayout(dest_layout)
        
        # Destination info
        self.dest_info_label = ElidedLabel("No destination selected", max_width=400)
        self.dest_info_label.setStyleSheet("color: #6c757d; font-size: 10px; margin: 4px;")
        layout.addWidget(self.dest_info_label)
        
        return panel
        
    def _create_options_panel(self) -> QGroupBox:
        """Create options and control panel"""
        panel = QGroupBox("Options & Control")
        layout = QVBoxLayout(panel)
        
        # Copy options
        options_label = QLabel("⚙️ Copy Options:")
        options_label.setStyleSheet("font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(options_label)
        
        self.preserve_structure_check = QCheckBox("Preserve folder structure")
        self.preserve_structure_check.setChecked(True)
        self.preserve_structure_check.setToolTip(
            "Maintain the original folder hierarchy when copying folders"
        )
        layout.addWidget(self.preserve_structure_check)
        
        self.calculate_hashes_check = QCheckBox("Calculate and verify hashes")
        self.calculate_hashes_check.setChecked(True)
        self.calculate_hashes_check.setToolTip(
            "Calculate SHA-256 hashes for source and destination files to verify integrity"
        )
        layout.addWidget(self.calculate_hashes_check)
        
        self.generate_csv_check = QCheckBox("Generate CSV report")
        self.generate_csv_check.setChecked(True)
        self.generate_csv_check.setToolTip(
            "Create a CSV file with hash verification results"
        )
        layout.addWidget(self.generate_csv_check)
        
        # CSV output path
        csv_layout = QHBoxLayout()
        csv_layout.addWidget(QLabel("CSV Path:"))
        self.csv_path_edit = QLineEdit()
        self.csv_path_edit.setPlaceholderText("Optional - will prompt if not specified")
        csv_layout.addWidget(self.csv_path_edit)
        
        self.browse_csv_btn = QPushButton("...")
        self.browse_csv_btn.setFixedWidth(30)
        self.browse_csv_btn.clicked.connect(self._browse_csv_path)
        csv_layout.addWidget(self.browse_csv_btn)
        
        layout.addLayout(csv_layout)
        
        # Hash algorithm info
        algorithm = settings.hash_algorithm.upper()
        algo_label = QLabel(f"Hash Algorithm: {algorithm}")
        algo_label.setStyleSheet("color: #6c757d; font-size: 10px; margin-top: 8px;")
        layout.addWidget(algo_label)
        
        layout.addStretch()
        
        # Progress section
        progress_label = QLabel("📊 Operation Progress:")
        progress_label.setStyleSheet("font-weight: bold; margin-top: 12px;")
        layout.addWidget(progress_label)
        
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
        layout.addWidget(self.progress_bar)
        
        self.progress_label = ElidedLabel("Ready to copy files", max_width=350)
        self.progress_label.setStyleSheet("color: #495057; font-size: 11px;")
        layout.addWidget(self.progress_label)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.copy_btn = QPushButton("🚀 Start Copy")
        self.copy_btn.setEnabled(False)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        button_layout.addWidget(self.copy_btn)
        
        self.pause_btn = QPushButton("⏸️ Pause")
        self.pause_btn.setEnabled(False)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        button_layout.addWidget(self.pause_btn)
        
        self.cancel_btn = QPushButton("🛑 Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        button_layout.addWidget(self.cancel_btn)
        
        self.export_csv_btn = QPushButton("📄 Export CSV")
        self.export_csv_btn.setEnabled(False)
        self.export_csv_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        button_layout.addWidget(self.export_csv_btn)
        
        layout.addLayout(button_layout)
        
        return panel
        
    def _create_console_section(self) -> QGroupBox:
        """Create console output section"""
        console_group = QGroupBox("📋 Operation Log")
        console_layout = QVBoxLayout(console_group)
        
        self.log_console = LogConsole()
        self.log_console.setMaximumHeight(150)
        console_layout.addWidget(self.log_console)
        
        return console_group
        
    def _get_title_font(self) -> QFont:
        """Get title font"""
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        return font
        
    def _connect_signals(self):
        """Connect all signals"""
        # Files panel
        self.files_panel.files_changed.connect(self._update_ui_state)
        self.files_panel.log_message.connect(self._log)
        
        # Destination path
        self.dest_path_edit.textChanged.connect(self._update_ui_state)
        
        # Options
        self.calculate_hashes_check.toggled.connect(self._on_hash_option_changed)
        self.generate_csv_check.toggled.connect(self._on_csv_option_changed)
        
        # Buttons
        self.copy_btn.clicked.connect(self._start_copy_operation)
        self.pause_btn.clicked.connect(self._pause_operation)
        self.cancel_btn.clicked.connect(self._cancel_operation)
        self.export_csv_btn.clicked.connect(self._export_csv)
        
    def _browse_destination(self):
        """Browse for destination folder"""
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Select Destination Folder",
            str(Path.home())
        )
        
        if folder:
            self.destination_path = Path(folder)
            self.dest_path_edit.setText(str(self.destination_path))
            self.dest_info_label.setText(f"Destination: {folder}")
            self._log(f"Destination set to: {folder}")
            
    def _browse_csv_path(self):
        """Browse for CSV output path"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save CSV Report",
            f"copy_verify_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            self.csv_path_edit.setText(file_path)
            
    def _on_hash_option_changed(self, checked: bool):
        """Handle hash calculation option change"""
        self.generate_csv_check.setEnabled(checked)
        self.csv_path_edit.setEnabled(checked and self.generate_csv_check.isChecked())
        self.browse_csv_btn.setEnabled(checked and self.generate_csv_check.isChecked())
        
        if not checked:
            self.generate_csv_check.setChecked(False)
            
    def _on_csv_option_changed(self, checked: bool):
        """Handle CSV generation option change"""
        self.csv_path_edit.setEnabled(checked)
        self.browse_csv_btn.setEnabled(checked)
        
    def _update_ui_state(self):
        """Update UI state based on current selections"""
        files, folders = self.files_panel.get_all_items()
        total_items = len(files) + len(folders)
        
        # Update file count
        if total_items == 0:
            self.file_count_label.setText("No files selected")
        else:
            self.file_count_label.setText(
                f"{total_items} items selected ({len(files)} files, {len(folders)} folders)"
            )
        
        # Enable copy button if we have files and destination
        has_files = total_items > 0
        has_destination = bool(self.dest_path_edit.text())
        
        self.copy_btn.setEnabled(
            has_files and has_destination and not self.operation_active
        )
        
    def _start_copy_operation(self):
        """Start the copy and verify operation"""
        try:
            # Get source items
            files, folders = self.files_panel.get_all_items()
            source_items = files + folders
            
            if not source_items:
                self._show_error("No files or folders selected")
                return
                
            if not self.destination_path:
                self._show_error("No destination folder selected")
                return
                
            # Check if destination exists
            if not self.destination_path.exists():
                reply = QMessageBox.question(
                    self,
                    "Create Destination",
                    f"Destination folder does not exist:\n{self.destination_path}\n\nCreate it?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    try:
                        self.destination_path.mkdir(parents=True, exist_ok=True)
                    except Exception as e:
                        self._show_error(f"Failed to create destination folder: {e}")
                        return
                else:
                    return
                    
            # Get CSV path if specified
            csv_path = None
            if self.generate_csv_check.isChecked() and self.calculate_hashes_check.isChecked():
                if self.csv_path_edit.text():
                    csv_path = Path(self.csv_path_edit.text())
                else:
                    # Prompt for CSV path
                    file_path, _ = QFileDialog.getSaveFileName(
                        self,
                        "Save CSV Report",
                        f"copy_verify_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        "CSV Files (*.csv);;All Files (*)"
                    )
                    if file_path:
                        csv_path = Path(file_path)
                        
            # Create and start worker
            from core.workers.copy_verify_worker import CopyVerifyWorker
            
            self.current_worker = CopyVerifyWorker(
                source_items=source_items,
                destination=self.destination_path,
                preserve_structure=self.preserve_structure_check.isChecked(),
                calculate_hash=self.calculate_hashes_check.isChecked(),
                csv_path=csv_path
            )
            
            # Connect signals
            self.current_worker.progress_update.connect(self._on_progress_update)
            self.current_worker.result_ready.connect(self._on_operation_complete)
            
            # Update UI state
            self._set_operation_active(True)
            
            # Start operation
            self.current_worker.start()
            
            self._log(f"Starting copy operation to {self.destination_path}")
            
        except Exception as e:
            self._log(f"Error starting operation: {e}")
            self._show_error(f"Failed to start copy operation: {e}")
            self._set_operation_active(False)
            
    def _pause_operation(self):
        """Pause or resume the current operation"""
        if not self.current_worker or not self.current_worker.isRunning():
            return
            
        if self.is_paused:
            # Resume operation
            self.current_worker.resume()
            self.is_paused = False
            self.pause_btn.setText("⏸️ Pause")
            self.pause_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
            """)
            self._log("Operation resumed")
            self.status_indicator.setText("🟡 Processing")
            self.status_indicator.setStyleSheet("color: #ffc107; font-weight: bold;")
        else:
            # Pause operation
            self.current_worker.pause()
            self.is_paused = True
            self.pause_btn.setText("▶️ Resume")
            self.pause_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FF9800;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #F57C00;
                }
            """)
            self._log("Operation paused")
            self.status_indicator.setText("⏸️ Paused")
            self.status_indicator.setStyleSheet("color: #FF9800; font-weight: bold;")
    
    def _cancel_operation(self):
        """Cancel the current operation"""
        if self.current_worker and self.current_worker.isRunning():
            self._log("Cancelling operation...")
            self.current_worker.cancel()
            self.cancel_btn.setEnabled(False)
            # Reset pause state if paused
            if self.is_paused:
                self.is_paused = False
                self.pause_btn.setText("⏸️ Pause")
            
    def _on_progress_update(self, percentage: int, message: str):
        """Handle progress updates"""
        self.progress_bar.setValue(percentage)
        self.progress_label.setText(message)
        
        # Log significant messages
        if percentage % 20 == 0 or "Verifying" in message:
            self._log(f"Progress: {percentage}% - {message}")
            
    def _on_operation_complete(self, result):
        """Handle operation completion"""
        from core.result_types import Result
        
        self._set_operation_active(False)
        
        if result.success:
            self.last_results = result.value
            
            # Extract metrics from result
            files_processed = getattr(result.value, 'files_processed', 0) if hasattr(result.value, 'files_processed') else getattr(result, 'files_processed', 0)
            bytes_processed = getattr(result.value, 'bytes_processed', 0) if hasattr(result.value, 'bytes_processed') else getattr(result, 'bytes_processed', 0)
            
            # Extract timing and speed info from metadata if available
            operation_time = 0
            avg_speed = 0
            peak_speed = 0
            if hasattr(result, 'metadata') and result.metadata:
                operation_time = result.metadata.get('duration_seconds', 0)
            
            # Count total files attempted and failures
            total_attempted = len(self.last_results) if self.last_results else 0
            failed_count = 0
            mismatches = 0
            
            if isinstance(self.last_results, dict):
                for file_key, file_data in self.last_results.items():
                    if isinstance(file_data, dict):
                        if not file_data.get('success', True):
                            failed_count += 1
                        elif file_data.get('verified') is False:
                            mismatches += 1
            
            # Calculate average speed if we have time and bytes
            if operation_time > 0 and bytes_processed > 0:
                avg_speed = (bytes_processed / (1024 * 1024)) / operation_time
            
            # Build CopyVerifyOperationData
            copy_data = CopyVerifyOperationData(
                files_copied=files_processed,
                bytes_processed=bytes_processed,
                operation_time_seconds=operation_time,
                average_speed_mbps=avg_speed,
                peak_speed_mbps=peak_speed if peak_speed > 0 else avg_speed,
                hash_verification_enabled=self.calculate_hashes_check.isChecked(),
                files_with_hash_mismatch=mismatches,
                files_failed_to_copy=failed_count,
                csv_generated=False,  # Will be set to True if CSV was generated
                csv_path=None,  # Will be set if CSV was generated
                source_items_count=total_attempted,
                preserve_structure=self.preserve_structure_check.isChecked()
            )
            
            # Check if CSV was generated (if path was specified)
            if self.csv_path_edit.text():
                csv_path = Path(self.csv_path_edit.text())
                if csv_path.exists():
                    copy_data.csv_generated = True
                    copy_data.csv_path = csv_path
            
            # Use success message builder
            message_builder = SuccessMessageBuilder()
            message_data = message_builder.build_copy_verify_success_message(copy_data)
            
            # Log the summary
            self._log(message_data.to_display_message())
            
            # Enable CSV export if we have results
            self.export_csv_btn.setEnabled(bool(self.last_results))
            
            # Show success dialog using the success message system
            SuccessDialog.show_success_message(message_data, self)
            
        else:
            error_msg = "Copy operation failed"
            if hasattr(result, 'error') and result.error:
                error_msg = result.error.user_message or str(result.error)
                
            self._log(f"❌ {error_msg}")
            self._show_error(error_msg)
            
    def _export_csv(self):
        """Export results to CSV"""
        if not self.last_results:
            self._show_error("No results available to export")
            return
            
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export CSV Report",
                f"copy_verify_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV Files (*.csv);;All Files (*)"
            )
            
            if file_path:
                # Generate CSV from results
                import csv
                
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = [
                        'Source Path', 'Destination Path', 'Size (bytes)',
                        'Source Hash', 'Destination Hash', 'Match', 'Status'
                    ]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    # Write header
                    writer.writeheader()
                    
                    # Write data
                    for file_name, file_data in self.last_results.items():
                        if isinstance(file_data, dict) and file_data.get('success'):
                            writer.writerow({
                                'Source Path': file_data.get('source_path', ''),
                                'Destination Path': file_data.get('dest_path', ''),
                                'Size (bytes)': file_data.get('size', 0),
                                'Source Hash': file_data.get('source_hash', 'N/A'),
                                'Destination Hash': file_data.get('dest_hash', 'N/A'),
                                'Match': 'Yes' if file_data.get('verified') else 'No',
                                'Status': 'Success' if file_data.get('verified') else 'Hash Mismatch'
                            })
                            
                self._log(f"CSV report exported to: {file_path}")
                
                # Create a simple success message for CSV export
                export_data = CopyVerifyOperationData(
                    files_copied=len([d for d in self.last_results.values() if isinstance(d, dict) and d.get('success')]),
                    bytes_processed=0,
                    csv_generated=True,
                    csv_path=Path(file_path)
                )
                
                # Build a simple success message for CSV export
                export_message_data = SuccessMessageBuilder().build_copy_verify_success_message(export_data)
                export_message_data.title = "CSV Export Complete!"
                export_message_data.summary_lines = [
                    f"✅ Report exported successfully",
                    f"📄 File: {Path(file_path).name}",
                    f"📁 Location: {Path(file_path).parent}"
                ]
                
                SuccessDialog.show_success_message(export_message_data, self)
                
        except Exception as e:
            self._log(f"Failed to export CSV: {e}")
            self._show_error(f"Failed to export CSV: {e}")
            
    def _set_operation_active(self, active: bool):
        """Set operation active state"""
        self.operation_active = active
        
        # Update UI elements
        self.copy_btn.setEnabled(not active and bool(self.dest_path_edit.text()))
        self.pause_btn.setEnabled(active)
        self.cancel_btn.setEnabled(active)
        self.browse_dest_btn.setEnabled(not active)
        self.files_panel.setEnabled(not active)
        self.preserve_structure_check.setEnabled(not active)
        self.calculate_hashes_check.setEnabled(not active)
        self.generate_csv_check.setEnabled(not active and self.calculate_hashes_check.isChecked())
        
        # Reset pause state when operation ends
        if not active:
            self.is_paused = False
            self.pause_btn.setText("⏸️ Pause")
            self.pause_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
                QPushButton:disabled {
                    background-color: #6c757d;
                }
            """)
        
        # Update status
        if active:
            self.status_indicator.setText("🟡 Processing")
            self.status_indicator.setStyleSheet("color: #ffc107; font-weight: bold;")
            self.progress_bar.setVisible(True)
            self.status_message.emit("Copy operation in progress...")
        else:
            self.status_indicator.setText("🟢 Ready")
            self.status_indicator.setStyleSheet("color: #28a745; font-weight: bold;")
            self.progress_bar.setVisible(False)
            self.progress_bar.setValue(0)
            self.progress_label.setText("Ready to copy files")
            self.status_message.emit("Ready")
            
    def _log(self, message: str):
        """Log a message"""
        self.log_console.log(message)
        self.log_message.emit(message)
        logger.info(f"[CopyVerifyTab] {message}")
        
    def _show_error(self, message: str):
        """Show error message with appropriate severity based on content"""
        
        # Determine severity based on error type
        severity = ErrorSeverity.WARNING  # Default
        
        message_lower = message.lower()
        
        # Critical system issues → CRITICAL
        if any(phrase in message_lower for phrase in [
            "unexpected error", "critical", "system error"
        ]):
            severity = ErrorSeverity.CRITICAL
        
        # Operation failures → ERROR  
        elif any(phrase in message_lower for phrase in [
            "failed to", "cannot", "error occurred", "exception"
        ]):
            severity = ErrorSeverity.ERROR
        
        # User input/validation errors → WARNING (default)
        # This includes: "no files", "no folder", "select", "no results", "not specified"
        
        error = UIError(
            message,
            user_message=message,
            component="CopyVerifyTab",
            severity=severity
        )
        handle_error(error, {'operation': 'copy_verify'})
        
    def cancel_current_operation(self):
        """Cancel current operation if running"""
        if self.operation_active:
            self._cancel_operation()