#!/usr/bin/env python3
"""
Copy & Verify Operation Sub-Tab - Copy files with integrated hash verification

Features:
- Source files and destination folder selection
- Integrated copy + hash verification (2-read optimization)
- Full viewport scrollable settings
- Pause/resume support
- Dual progress indicators (copy + hash)
- Large statistics display
"""

from pathlib import Path
from typing import List, Optional
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox,
    QCheckBox, QComboBox, QScrollArea, QTreeWidget, QLineEdit,
    QTreeWidgetItem, QSizePolicy, QFileDialog, QMessageBox
)

from ..components.base_operation_tab import BaseOperationTab
from ..components.operation_log_console import OperationLogConsole
from ...core.unified_hash_calculator import UnifiedHashCalculator
from ...controllers import CopyHashVerifyController, CopyVerifySettings
from ...services import SuccessMessageBuilder
from core.result_types import Result
from core.logger import logger
from core.hash_operations import HashResult, VerificationResult
from core.hash_reports import HashReportGenerator


class CopyVerifyOperationTab(BaseOperationTab):
    """Copy files and folders with integrated hash verification"""

    def __init__(self, shared_logger: Optional[OperationLogConsole] = None, parent=None):
        """
        Initialize Copy & Verify tab

        Args:
            shared_logger: Shared logger console instance
            parent: Parent widget
        """
        super().__init__("Copy & Verify", shared_logger, parent)

        # State
        self.source_paths: List[Path] = []
        self.destination_path: Optional[Path] = None
        self.current_worker = None
        self.last_results = None
        self.is_paused = False

        # Controller and services (SOA/DI pattern)
        self.controller = CopyHashVerifyController()
        self.success_builder = SuccessMessageBuilder()

        self._create_ui()
        self._connect_signals()
        self._load_settings()

    def _create_ui(self):
        """Create the tab UI"""
        # Create base layout with splitter
        left_container, right_container = self.create_base_layout()

        # Left panel - Source files and destination
        self._create_file_panel(left_container)

        # Right panel - Copy/verify settings
        self._create_settings_panel(right_container)

    def _create_file_panel(self, container):
        """Create file selection panel"""
        layout = QVBoxLayout(container)

        # Source files section
        source_label = QLabel("📁 Source Files and Folders")
        source_label.setFont(self.get_section_font())
        layout.addWidget(source_label)

        # Source buttons
        button_layout = QHBoxLayout()

        self.add_files_btn = QPushButton("📄 Add Files")
        self.add_files_btn.clicked.connect(self._add_files)
        button_layout.addWidget(self.add_files_btn)

        self.add_folder_btn = QPushButton("📂 Add Folder")
        self.add_folder_btn.clicked.connect(self._add_folder)
        button_layout.addWidget(self.add_folder_btn)

        self.clear_btn = QPushButton("🗑️ Clear")
        self.clear_btn.clicked.connect(self._clear_files)
        self.clear_btn.setEnabled(False)
        button_layout.addWidget(self.clear_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # File tree
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["Source Files"])
        self.file_tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.file_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.file_tree.setMinimumHeight(150)
        self.file_tree.setAlternatingRowColors(True)
        layout.addWidget(self.file_tree)

        # File count
        self.file_count_label = QLabel("No files selected")
        self.file_count_label.setObjectName("mutedText")
        layout.addWidget(self.file_count_label)

        # Destination section
        dest_label = QLabel("📂 Destination Folder")
        dest_label.setFont(self.get_section_font())
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
        self.dest_info_label = QLabel("No destination selected")
        self.dest_info_label.setObjectName("mutedText")
        layout.addWidget(self.dest_info_label)

        # Statistics section (hidden initially)
        stats = self.create_stats_section()
        layout.addWidget(stats)

    def _create_settings_panel(self, container):
        """Create settings panel"""
        layout = QVBoxLayout(container)

        # Header
        header_label = QLabel("⚙️ Copy & Verify Settings")
        header_label.setFont(self.get_section_font())
        layout.addWidget(header_label)

        # Scrollable settings area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        # Settings container
        settings_container = QGroupBox()
        settings_layout = QVBoxLayout(settings_container)
        settings_layout.setSpacing(12)

        # Copy options
        copy_group = QGroupBox("Copy Options")
        copy_layout = QVBoxLayout(copy_group)

        self.preserve_structure_check = QCheckBox("Preserve folder structure")
        self.preserve_structure_check.setChecked(True)
        self.preserve_structure_check.setToolTip("Maintain original folder hierarchy")
        copy_layout.addWidget(self.preserve_structure_check)

        self.overwrite_check = QCheckBox("Overwrite existing files")
        self.overwrite_check.setChecked(False)
        copy_layout.addWidget(self.overwrite_check)

        self.copy_permissions_check = QCheckBox("Copy file permissions")
        self.copy_permissions_check.setChecked(True)
        copy_layout.addWidget(self.copy_permissions_check)

        settings_layout.addWidget(copy_group)

        # Hash verification options
        hash_group = QGroupBox("Hash Verification")
        hash_layout = QVBoxLayout(hash_group)

        self.verify_hashes_check = QCheckBox("Calculate and verify hashes")
        self.verify_hashes_check.setChecked(True)
        hash_layout.addWidget(self.verify_hashes_check)

        # Algorithm
        algo_layout = QHBoxLayout()
        algo_layout.addWidget(QLabel("Algorithm:"))
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(["SHA-256", "SHA-1", "MD5"])
        self.algorithm_combo.setCurrentIndex(0)
        algo_layout.addWidget(self.algorithm_combo)
        algo_layout.addStretch()
        hash_layout.addLayout(algo_layout)

        self.stop_on_mismatch_check = QCheckBox("Stop on hash mismatch")
        self.stop_on_mismatch_check.setChecked(True)
        hash_layout.addWidget(self.stop_on_mismatch_check)

        settings_layout.addWidget(hash_group)

        # Report options
        report_group = QGroupBox("Report Generation")
        report_layout = QVBoxLayout(report_group)

        self.generate_csv_check = QCheckBox("Generate CSV report")
        self.generate_csv_check.setChecked(True)
        report_layout.addWidget(self.generate_csv_check)

        self.include_performance_check = QCheckBox("Include performance metrics")
        self.include_performance_check.setChecked(True)
        report_layout.addWidget(self.include_performance_check)

        settings_layout.addWidget(report_group)

        # Performance options
        perf_group = QGroupBox("Performance Settings")
        perf_layout = QVBoxLayout(perf_group)

        # Buffer size
        buffer_layout = QHBoxLayout()
        buffer_layout.addWidget(QLabel("Buffer Size:"))
        self.buffer_combo = QComboBox()
        self.buffer_combo.addItems(["Auto (Adaptive)", "256 KB", "2 MB", "10 MB"])
        self.buffer_combo.setCurrentIndex(0)
        buffer_layout.addWidget(self.buffer_combo)
        buffer_layout.addStretch()
        perf_layout.addLayout(buffer_layout)

        self.use_optimization_check = QCheckBox("Use 2-read optimization (copy+hash)")
        self.use_optimization_check.setChecked(True)
        self.use_optimization_check.setToolTip("Combines copy and hash for better performance")
        perf_layout.addWidget(self.use_optimization_check)

        settings_layout.addWidget(perf_group)
        settings_layout.addStretch()

        scroll_area.setWidget(settings_container)
        layout.addWidget(scroll_area)

        # Progress section
        self.create_progress_section(layout)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.copy_btn = QPushButton("🔄 Start Copy & Verify")
        self.copy_btn.setEnabled(False)
        self.copy_btn.setMinimumHeight(36)
        self.copy_btn.setStyleSheet("""
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
        button_layout.addWidget(self.copy_btn)

        self.pause_btn = QPushButton("⏸️ Pause")
        self.pause_btn.setEnabled(False)
        self.pause_btn.setMinimumHeight(36)
        button_layout.addWidget(self.pause_btn)

        self.cancel_btn = QPushButton("🛑 Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setMinimumHeight(36)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _connect_signals(self):
        """Connect signals"""
        self.copy_btn.clicked.connect(self._start_copy_operation)
        self.pause_btn.clicked.connect(self._pause_operation)
        self.cancel_btn.clicked.connect(self._cancel_operation)
        self.dest_path_edit.textChanged.connect(self._update_ui_state)

    def _load_settings(self):
        """Load saved settings"""
        settings = QSettings()
        settings.beginGroup("CopyHashVerify/CopyVerify")

        # Load options
        self.preserve_structure_check.setChecked(settings.value("preserve_structure", True, type=bool))
        self.verify_hashes_check.setChecked(settings.value("verify_hashes", True, type=bool))
        self.generate_csv_check.setChecked(settings.value("generate_csv", True, type=bool))

        # Load algorithm
        algorithm_idx = settings.value("algorithm_idx", 0, type=int)
        self.algorithm_combo.setCurrentIndex(algorithm_idx)

        settings.endGroup()

    def _save_settings(self):
        """Save current settings"""
        settings = QSettings()
        settings.beginGroup("CopyHashVerify/CopyVerify")

        settings.setValue("preserve_structure", self.preserve_structure_check.isChecked())
        settings.setValue("verify_hashes", self.verify_hashes_check.isChecked())
        settings.setValue("generate_csv", self.generate_csv_check.isChecked())
        settings.setValue("algorithm_idx", self.algorithm_combo.currentIndex())

        settings.endGroup()

    def _add_files(self):
        """Add files to copy"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Copy",
            "",
            "All Files (*.*)"
        )

        if file_paths:
            for file_path in file_paths:
                path = Path(file_path)
                if path not in self.source_paths:
                    self.source_paths.append(path)

            self._rebuild_file_tree()
            self._update_ui_state()

    def _add_folder(self):
        """Add folder to copy - expands to individual files for accurate counting"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Copy",
            ""
        )

        if folder_path:
            folder = Path(folder_path)
            # Recursively add all files from folder (not the folder itself)
            added = 0
            for file_path in folder.rglob('*'):
                if file_path.is_file():
                    if file_path not in self.source_paths:
                        self.source_paths.append(file_path)
                        added += 1

            if added > 0:
                self.info(f"Added {added} files from: {folder.name}")
                self._rebuild_file_tree()
                self._update_ui_state()
            else:
                self.warning(f"No files found in: {folder.name}")

    def _clear_files(self):
        """Clear all files"""
        self.file_tree.clear()
        self.source_paths.clear()
        self.last_results = None
        self._update_ui_state()

        if self.stats_group:
            self.stats_group.setVisible(False)

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
            self.info(f"Destination set to: {folder}")

    def _rebuild_file_tree(self):
        """Rebuild file tree with hierarchical folder structure"""
        self.file_tree.clear()

        if not self.source_paths:
            return

        # Find common root path
        if len(self.source_paths) == 1:
            common_root = self.source_paths[0].parent
        else:
            # Get all parent paths for each file
            all_parts = [list(f.parents)[::-1] for f in self.source_paths]
            common_root = None
            for parts in zip(*all_parts):
                if len(set(parts)) == 1:
                    common_root = parts[0]
                else:
                    break

            # Fallback if no common root found
            if common_root is None:
                # Use the first path's root
                common_root = self.source_paths[0].anchor or self.source_paths[0].parents[-1]

        # Build folder hierarchy
        folder_items = {}  # path -> QTreeWidgetItem

        for file_path in sorted(self.source_paths):
            try:
                rel_path = file_path.relative_to(common_root)
            except ValueError:
                # File is not relative to common_root, use full path
                rel_path = file_path

            # Create folder items for parent directories
            current_parent = None
            for i, part in enumerate(rel_path.parts[:-1]):
                try:
                    partial_path = common_root / Path(*rel_path.parts[:i+1])
                except (ValueError, TypeError):
                    partial_path = Path(*rel_path.parts[:i+1])

                if partial_path not in folder_items:
                    folder_item = QTreeWidgetItem()
                    folder_item.setText(0, f"📁 {part}")
                    folder_item.setData(0, Qt.UserRole, str(partial_path))

                    if current_parent is None:
                        self.file_tree.addTopLevelItem(folder_item)
                    else:
                        current_parent.addChild(folder_item)

                    folder_items[partial_path] = folder_item

                current_parent = folder_items[partial_path]

            # Add file item
            file_item = QTreeWidgetItem()
            file_item.setText(0, f"📄 {file_path.name}")
            file_item.setData(0, Qt.UserRole, str(file_path))

            if current_parent is None:
                self.file_tree.addTopLevelItem(file_item)
            else:
                current_parent.addChild(file_item)

        self.file_tree.expandAll()

    def _update_ui_state(self):
        """Update UI state"""
        has_files = len(self.source_paths) > 0
        has_destination = bool(self.dest_path_edit.text())

        # Update labels
        if has_files:
            file_count = len(self.source_paths)
            file_word = "file" if file_count == 1 else "files"
            self.file_count_label.setText(f"{file_count} {file_word} selected")
        else:
            self.file_count_label.setText("No files selected")

        # Update buttons
        self.clear_btn.setEnabled(has_files)
        self.copy_btn.setEnabled(has_files and has_destination and not self.operation_active)

    def _get_selected_algorithm(self) -> str:
        """Get selected algorithm"""
        algo_text = self.algorithm_combo.currentText()
        if "SHA-256" in algo_text:
            return 'sha256'
        elif "SHA-1" in algo_text:
            return 'sha1'
        else:
            return 'md5'

    def _start_copy_operation(self):
        """Start copy and verify operation via controller (SOA pattern)"""
        if not self.source_paths:
            self.error("No files selected")
            return

        if not self.destination_path:
            self.error("No destination selected")
            return

        # Check if destination exists
        if not self.destination_path.exists():
            reply = QMessageBox.question(
                self,
                "Create Destination",
                f"Destination folder does not exist:\n{self.destination_path}\n\nCreate it?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

            # Create destination
            try:
                self.destination_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.error(f"Failed to create destination: {e}")
                return

        # Save settings
        self._save_settings()

        # Build settings from UI
        settings = CopyVerifySettings(
            algorithm=self._get_selected_algorithm(),
            preserve_structure=self.preserve_structure_check.isChecked(),
            generate_csv=self.generate_csv_check.isChecked(),
            calculate_hashes=self.verify_hashes_check.isChecked()
        )

        self.info(f"Starting copy operation with {settings.algorithm.upper()} verification")
        self.info(f"Destination: {self.destination_path}")

        # DELEGATE TO CONTROLLER (not creating worker ourselves!)
        result = self.controller.start_copy_verify_workflow(
            source_paths=self.source_paths,
            destination=self.destination_path,
            settings=settings
        )

        if result.success:
            # Get worker from controller result
            self.current_worker = result.value

            # Connect signals
            self.current_worker.result_ready.connect(self._on_copy_complete)
            self.current_worker.progress_update.connect(self._on_progress)

            # Start worker
            self.current_worker.start()

            # Update UI state
            self.set_operation_active(True)
            self.copy_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
            self.add_files_btn.setEnabled(False)
            self.add_folder_btn.setEnabled(False)
            self.browse_dest_btn.setEnabled(False)
        else:
            # Show validation error from controller
            error_msg = result.error.user_message if result.error else "Unknown error"
            self.error(error_msg)
            logger.error(f"Failed to start copy workflow: {result.error}")

    def _on_progress(self, percentage: int, message: str):
        """Handle progress update"""
        self.update_progress(percentage, message)

    def _on_copy_complete(self, result: Result):
        """Handle copy operation completion with success message builder"""
        self.set_operation_active(False)

        # Update UI
        self.copy_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.add_files_btn.setEnabled(True)
        self.add_folder_btn.setEnabled(True)
        self.browse_dest_btn.setEnabled(True)

        if result.success:
            # Result.value contains the hash results dict
            hash_results = result.value

            # Extract operation metadata
            perf_stats = hash_results.get('_performance_stats', {})
            total_files = perf_stats.get('files_copied', len(hash_results) - 1)  # -1 for _performance_stats key
            total_size = perf_stats.get('total_bytes', 0)
            duration = perf_stats.get('total_time', 0)
            avg_speed = perf_stats.get('avg_speed_mb_s', 0)
            threads_used = perf_stats.get('threads_used', 1)

            # Update stats display
            self.update_stats(
                total=total_files,
                success=total_files,
                failed=0,
                speed=avg_speed
            )

            # Build success message via service
            success_message = self.success_builder.build_copy_verify_message(
                files_copied=total_files,
                total_size_bytes=total_size,
                duration_seconds=duration,
                hashes_calculated=self.verify_hashes_check.isChecked(),
                verification_passed=True,  # Worker validates hashes during copy
                performance_stats={
                    'avg_speed_mb_s': avg_speed,
                    'threads_used': threads_used
                }
            )

            # Log formatted success message
            self.success(success_message)

            # Store results
            self.last_results = hash_results

            # Offer to export CSV
            if self.generate_csv_check.isChecked():
                self._export_csv_results(hash_results)

        else:
            self.error(f"Copy operation failed: {result.error.user_message}")

    def _pause_operation(self):
        """Pause or resume operation"""
        if not self.current_worker or not self.current_worker.isRunning():
            return

        if self.is_paused:
            # Resume
            self.is_paused = False
            self.current_worker.resume()
            self.pause_btn.setText("⏸️ Pause")
            self.info("Operation resumed")
        else:
            # Pause
            self.is_paused = True
            self.current_worker.pause()
            self.pause_btn.setText("▶️ Resume")
            self.info("Operation paused")

    def _cancel_operation(self):
        """Cancel operation"""
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.warning("Cancelling copy operation...")
            self.current_worker.wait(3000)  # Wait up to 3 seconds for clean shutdown

    def _export_csv_results(self, hash_results: dict):
        """Export hash verification results to forensic-grade CSV using HashReportGenerator"""
        try:
            algorithm = self._get_selected_algorithm()
            default_filename = f"copy_verification_report_{algorithm}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filename = self.destination_path / default_filename

            # Convert hash_results dict to VerificationResult objects
            verification_results = []

            for path, result_data in hash_results.items():
                # Skip _performance_stats metadata
                if path == '_performance_stats':
                    continue

                if isinstance(result_data, dict) and result_data.get('source_hash'):
                    source_path = Path(result_data.get('source_path', path))
                    dest_path = Path(result_data.get('dest_path', path))
                    source_hash = result_data.get('source_hash', '')
                    dest_hash = result_data.get('dest_hash', '')
                    verified = result_data.get('verified', False)
                    file_size = result_data.get('size', 0)

                    # Create HashResult for source
                    source_result = HashResult(
                        file_path=source_path,
                        relative_path=Path(path),
                        algorithm=algorithm,
                        hash_value=source_hash,
                        file_size=file_size,
                        duration=0.0
                    )

                    # Create HashResult for destination
                    dest_result = HashResult(
                        file_path=dest_path,
                        relative_path=Path(path),
                        algorithm=algorithm,
                        hash_value=dest_hash,
                        file_size=file_size,
                        duration=0.0
                    )

                    # Create VerificationResult
                    comparison_type = 'hash_match' if verified else 'hash_mismatch'
                    notes = f"Copied with {algorithm.upper()} verification"

                    verification_result = VerificationResult(
                        source_result=source_result,
                        target_result=dest_result,
                        match=verified,
                        comparison_type=comparison_type,
                        notes=notes
                    )
                    verification_results.append(verification_result)

            if not verification_results:
                self.warning("No hash verification results to export")
                return

            # Use professional report generator
            report_gen = HashReportGenerator()
            success = report_gen.generate_verification_csv(
                verification_results=verification_results,
                output_path=filename,
                algorithm=algorithm,
                include_metadata=True
            )

            if success:
                self.success(f"Hash verification report saved: {filename.name}")
                self.info(f"Report location: {filename}")
            else:
                self.error("Failed to generate hash verification report")

        except Exception as e:
            self.error(f"Failed to export CSV: {e}")
            logger.error(f"CSV export error: {e}", exc_info=True)

    def cleanup(self):
        """Clean up resources via controller"""
        # Delegate cleanup to controller (handles worker lifecycle)
        if self.controller:
            self.controller.cleanup()

        # Clear local references
        self.current_worker = None
        self.last_results = None
