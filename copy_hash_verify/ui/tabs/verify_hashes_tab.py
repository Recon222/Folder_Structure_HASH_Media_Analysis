#!/usr/bin/env python3
"""
Verify Hashes Sub-Tab - Bidirectional hash verification

Features:
- Source and target file panels
- Full viewport scrollable settings
- Bidirectional verification
- Mismatch detection and reporting
- Large statistics display
"""

from pathlib import Path
from typing import List, Optional
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox,
    QCheckBox, QRadioButton, QButtonGroup, QComboBox, QScrollArea, QTreeWidget,
    QTreeWidgetItem, QSizePolicy, QFileDialog, QSplitter
)

from ..components.base_operation_tab import BaseOperationTab
from ..components.operation_log_console import OperationLogConsole
from ...core.unified_hash_calculator import UnifiedHashCalculator
from core.result_types import Result
from core.logger import logger


class VerifyHashesTab(BaseOperationTab):
    """Verify hashes between source and target files"""

    def __init__(self, shared_logger: Optional[OperationLogConsole] = None, parent=None):
        """
        Initialize Verify Hashes tab

        Args:
            shared_logger: Shared logger console instance
            parent: Parent widget
        """
        super().__init__("Verify Hashes", shared_logger, parent)

        # State
        self.source_paths: List[Path] = []
        self.target_paths: List[Path] = []
        self.current_worker = None
        self.last_results = None
        self.hash_calculator = None

        self._create_ui()
        self._connect_signals()
        self._load_settings()

    def _create_ui(self):
        """Create the tab UI"""
        # Create base layout with splitter
        left_container, right_container = self.create_base_layout()

        # Left panel - Source and target file selection
        self._create_file_panels(left_container)

        # Right panel - Verification settings
        self._create_settings_panel(right_container)

    def _create_file_panels(self, container):
        """Create source and target file panels"""
        layout = QVBoxLayout(container)

        # Header
        header_label = QLabel("📁 Files to Verify")
        header_label.setFont(self.get_section_font())
        layout.addWidget(header_label)

        # Source and target splitter
        files_splitter = QSplitter(Qt.Vertical)
        files_splitter.setChildrenCollapsible(False)

        # Source panel
        source_panel = self._create_source_panel()
        files_splitter.addWidget(source_panel)

        # Target panel
        target_panel = self._create_target_panel()
        files_splitter.addWidget(target_panel)

        # Equal sizes
        files_splitter.setSizes([200, 200])

        layout.addWidget(files_splitter)

        # Count label
        self.count_label = QLabel("No files selected")
        self.count_label.setObjectName("mutedText")
        layout.addWidget(self.count_label)

        # Statistics section (hidden initially)
        stats = self.create_stats_section()
        layout.addWidget(stats)

    def _create_source_panel(self) -> QGroupBox:
        """Create source files panel"""
        panel = QGroupBox("Source Files")
        layout = QVBoxLayout(panel)

        # Buttons
        button_layout = QHBoxLayout()

        self.source_add_files_btn = QPushButton("📄 Add Files")
        self.source_add_files_btn.clicked.connect(lambda: self._add_files('source'))
        button_layout.addWidget(self.source_add_files_btn)

        self.source_add_folder_btn = QPushButton("📂 Add Folder")
        self.source_add_folder_btn.clicked.connect(lambda: self._add_folder('source'))
        button_layout.addWidget(self.source_add_folder_btn)

        self.source_clear_btn = QPushButton("🗑️")
        self.source_clear_btn.setFixedWidth(30)
        self.source_clear_btn.clicked.connect(lambda: self._clear_files('source'))
        self.source_clear_btn.setEnabled(False)
        button_layout.addWidget(self.source_clear_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Tree
        self.source_tree = QTreeWidget()
        self.source_tree.setHeaderLabels(["Source Files"])
        self.source_tree.setAlternatingRowColors(True)
        self.source_tree.setMinimumHeight(100)
        layout.addWidget(self.source_tree)

        return panel

    def _create_target_panel(self) -> QGroupBox:
        """Create target files panel"""
        panel = QGroupBox("Target Files")
        layout = QVBoxLayout(panel)

        # Buttons
        button_layout = QHBoxLayout()

        self.target_add_files_btn = QPushButton("📄 Add Files")
        self.target_add_files_btn.clicked.connect(lambda: self._add_files('target'))
        button_layout.addWidget(self.target_add_files_btn)

        self.target_add_folder_btn = QPushButton("📂 Add Folder")
        self.target_add_folder_btn.clicked.connect(lambda: self._add_folder('target'))
        button_layout.addWidget(self.target_add_folder_btn)

        self.target_clear_btn = QPushButton("🗑️")
        self.target_clear_btn.setFixedWidth(30)
        self.target_clear_btn.clicked.connect(lambda: self._clear_files('target'))
        self.target_clear_btn.setEnabled(False)
        button_layout.addWidget(self.target_clear_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Tree
        self.target_tree = QTreeWidget()
        self.target_tree.setHeaderLabels(["Target Files"])
        self.target_tree.setAlternatingRowColors(True)
        self.target_tree.setMinimumHeight(100)
        layout.addWidget(self.target_tree)

        return panel

    def _create_settings_panel(self, container):
        """Create verification settings panel"""
        layout = QVBoxLayout(container)

        # Header
        header_label = QLabel("⚙️ Verification Settings")
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

        # Algorithm selection
        algo_group = QGroupBox("Hash Algorithm")
        algo_layout = QVBoxLayout(algo_group)

        self.algo_button_group = QButtonGroup()

        self.sha256_radio = QRadioButton("SHA-256 (Recommended)")
        self.sha256_radio.setChecked(True)
        self.algo_button_group.addButton(self.sha256_radio, 0)
        algo_layout.addWidget(self.sha256_radio)

        self.sha1_radio = QRadioButton("SHA-1")
        self.algo_button_group.addButton(self.sha1_radio, 1)
        algo_layout.addWidget(self.sha1_radio)

        self.md5_radio = QRadioButton("MD5 (Legacy)")
        self.algo_button_group.addButton(self.md5_radio, 2)
        algo_layout.addWidget(self.md5_radio)

        # Connect algorithm change signal
        self.algo_button_group.buttonClicked.connect(self._on_algorithm_changed)

        settings_layout.addWidget(algo_group)

        # Verification options
        verify_group = QGroupBox("Verification Options")
        verify_layout = QVBoxLayout(verify_group)

        self.bidirectional_check = QCheckBox("Bidirectional verification")
        self.bidirectional_check.setChecked(True)
        self.bidirectional_check.setToolTip("Verify both source→target and target→source")
        verify_layout.addWidget(self.bidirectional_check)

        self.stop_on_first_check = QCheckBox("Stop on first mismatch")
        self.stop_on_first_check.setChecked(False)
        verify_layout.addWidget(self.stop_on_first_check)

        self.show_matches_check = QCheckBox("Show matching files in report")
        self.show_matches_check.setChecked(True)
        verify_layout.addWidget(self.show_matches_check)

        settings_layout.addWidget(verify_group)

        # Report options
        report_group = QGroupBox("Report Generation")
        report_layout = QVBoxLayout(report_group)

        self.generate_csv_check = QCheckBox("Generate verification CSV report")
        self.generate_csv_check.setChecked(True)
        report_layout.addWidget(self.generate_csv_check)

        self.include_matched_check = QCheckBox("Include matched files in CSV")
        self.include_matched_check.setChecked(True)
        report_layout.addWidget(self.include_matched_check)

        self.include_missing_check = QCheckBox("Include missing files in CSV")
        self.include_missing_check.setChecked(True)
        report_layout.addWidget(self.include_missing_check)

        settings_layout.addWidget(report_group)
        settings_layout.addStretch()

        scroll_area.setWidget(settings_container)
        layout.addWidget(scroll_area)

        # Progress section
        self.create_progress_section(layout)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.verify_btn = QPushButton("🔍 Verify Hashes")
        self.verify_btn.setEnabled(False)
        self.verify_btn.setMinimumHeight(36)
        self.verify_btn.setStyleSheet("""
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
        button_layout.addWidget(self.verify_btn)

        self.cancel_btn = QPushButton("🛑 Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setMinimumHeight(36)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _connect_signals(self):
        """Connect signals"""
        self.verify_btn.clicked.connect(self._start_verification)
        self.cancel_btn.clicked.connect(self._cancel_operation)

    def _load_settings(self):
        """Load saved settings"""
        settings = QSettings()
        settings.beginGroup("CopyHashVerify/VerifyHashes")

        # Load algorithm
        algorithm = settings.value("algorithm", "sha256")
        if algorithm == "sha256":
            self.sha256_radio.setChecked(True)
        elif algorithm == "sha1":
            self.sha1_radio.setChecked(True)
        else:
            self.md5_radio.setChecked(True)

        # Load options
        self.bidirectional_check.setChecked(settings.value("bidirectional", True, type=bool))
        self.generate_csv_check.setChecked(settings.value("generate_csv", True, type=bool))

        settings.endGroup()

    def _save_settings(self):
        """Save current settings"""
        settings = QSettings()
        settings.beginGroup("CopyHashVerify/VerifyHashes")

        # Save algorithm
        if self.sha256_radio.isChecked():
            settings.setValue("algorithm", "sha256")
        elif self.sha1_radio.isChecked():
            settings.setValue("algorithm", "sha1")
        else:
            settings.setValue("algorithm", "md5")

        # Save options
        settings.setValue("bidirectional", self.bidirectional_check.isChecked())
        settings.setValue("generate_csv", self.generate_csv_check.isChecked())

        settings.endGroup()

    def _on_algorithm_changed(self, button):
        """Handle algorithm change"""
        algorithm = self._get_selected_algorithm()
        self.info(f"Verification algorithm set to {algorithm.upper()}")

    def _add_files(self, panel_type: str):
        """Add files to source or target"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            f"Select {panel_type.title()} Files",
            "",
            "All Files (*.*)"
        )

        if file_paths:
            target_list = self.source_paths if panel_type == 'source' else self.target_paths
            for file_path in file_paths:
                path = Path(file_path)
                if path not in target_list:
                    target_list.append(path)

            self._rebuild_tree(panel_type)
            self._update_ui_state()

    def _add_folder(self, panel_type: str):
        """Add folder to source or target"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            f"Select {panel_type.title()} Folder",
            ""
        )

        if folder_path:
            path = Path(folder_path)
            target_list = self.source_paths if panel_type == 'source' else self.target_paths
            if path not in target_list:
                target_list.append(path)

            self._rebuild_tree(panel_type)
            self._update_ui_state()

    def _clear_files(self, panel_type: str):
        """Clear files from source or target"""
        if panel_type == 'source':
            self.source_tree.clear()
            self.source_paths.clear()
        else:
            self.target_tree.clear()
            self.target_paths.clear()

        self._update_ui_state()

    def _rebuild_tree(self, panel_type: str):
        """Rebuild tree for source or target"""
        tree = self.source_tree if panel_type == 'source' else self.target_tree
        paths = self.source_paths if panel_type == 'source' else self.target_paths

        tree.clear()

        for path in sorted(paths):
            item = QTreeWidgetItem()
            if path.is_file():
                item.setText(0, f"📄 {path.name}")
            else:
                item.setText(0, f"📁 {path.name}")
            item.setData(0, Qt.UserRole, str(path))
            tree.addTopLevelItem(item)

        tree.expandAll()

    def _update_ui_state(self):
        """Update UI state"""
        has_source = len(self.source_paths) > 0
        has_target = len(self.target_paths) > 0

        # Update labels
        self.count_label.setText(
            f"Source: {len(self.source_paths)} items | Target: {len(self.target_paths)} items"
        )

        # Update buttons
        self.source_clear_btn.setEnabled(has_source)
        self.target_clear_btn.setEnabled(has_target)
        self.verify_btn.setEnabled(has_source and has_target and not self.operation_active)

    def _get_selected_algorithm(self) -> str:
        """Get selected algorithm"""
        if self.sha256_radio.isChecked():
            return 'sha256'
        elif self.sha1_radio.isChecked():
            return 'sha1'
        else:
            return 'md5'

    def _start_verification(self):
        """Start hash verification"""
        if not self.source_paths or not self.target_paths:
            self.error("Both source and target files must be selected")
            return

        # Get algorithm
        algorithm = self._get_selected_algorithm()

        # Save settings
        self._save_settings()

        # Create hash calculator
        self.hash_calculator = UnifiedHashCalculator(
            algorithm=algorithm,
            progress_callback=self._on_progress,
            cancelled_check=lambda: self.hash_calculator.cancelled if self.hash_calculator else False
        )

        self.info(f"Starting hash verification with {algorithm.upper()}")
        self.set_operation_active(True)

        # Update UI
        self.verify_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        # Verify hashes
        result = self.hash_calculator.verify_hashes(self.source_paths, self.target_paths)

        # Handle result
        self._on_verification_complete(result)

    def _on_progress(self, percentage: int, message: str):
        """Handle progress update"""
        self.update_progress(percentage, message)

    def _on_verification_complete(self, result: Result):
        """Handle verification completion"""
        self.set_operation_active(False)

        # Update UI
        self.verify_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        if result.success:
            self.last_results = result.value
            total = len(result.value)
            matches = sum(1 for vr in result.value.values() if vr.match)
            mismatches = total - matches

            # Update statistics
            self.update_stats(
                total=total,
                success=matches,
                failed=mismatches,
                speed=0  # No speed for verification
            )

            if mismatches > 0:
                self.warning(f"Verification complete: {matches} matched, {mismatches} mismatched")
            else:
                self.success(f"Verification complete: All {matches} files matched!")

            # Offer to export CSV
            if self.generate_csv_check.isChecked():
                self._export_csv()

        else:
            self.error(f"Verification failed: {result.error.user_message}")

    def _cancel_operation(self):
        """Cancel operation"""
        if self.hash_calculator:
            self.hash_calculator.cancel()
            self.warning("Cancelling verification...")

    def _export_csv(self):
        """Export verification results to CSV"""
        if not self.last_results:
            self.error("No results to export")
            return

        algorithm = self._get_selected_algorithm()
        default_filename = f"verification_report_{algorithm}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Verification Report",
            default_filename,
            "CSV Files (*.csv);;All Files (*)"
        )

        if filename:
            try:
                # Write CSV
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"Source File,Target File,Match,{algorithm.upper()} Source,{algorithm.upper()} Target,Notes\n")
                    for path, ver_result in self.last_results.items():
                        source_name = ver_result.source_result.relative_path.name
                        target_name = ver_result.target_result.relative_path.name if ver_result.target_result else "N/A"
                        match = "MATCH" if ver_result.match else "MISMATCH"
                        source_hash = ver_result.source_result.hash_value
                        target_hash = ver_result.target_result.hash_value if ver_result.target_result else "N/A"
                        notes = ver_result.notes

                        f.write(f"{source_name},{target_name},{match},{source_hash},{target_hash},{notes}\n")

                self.success(f"Verification report exported to: {filename}")

            except Exception as e:
                self.error(f"Failed to export CSV: {e}")

    def cleanup(self):
        """Clean up resources"""
        if self.hash_calculator:
            self.hash_calculator.cancel()
        self.hash_calculator = None
        self.current_worker = None
        self.last_results = None
