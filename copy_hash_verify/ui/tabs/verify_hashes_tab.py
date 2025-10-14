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
from ...controllers.hash_verification_controller import HashVerificationController, HashVerificationSettings
from ...services.success_message_builder import SuccessMessageBuilder
from core.result_types import Result
from core.logger import logger
from core.hash_reports import HashReportGenerator


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

        # Controller and services (SOA/DI pattern)
        self.controller = HashVerificationController()
        self.success_builder = SuccessMessageBuilder()

        # State
        self.source_paths: List[Path] = []
        self.target_paths: List[Path] = []
        self.current_worker = None
        self.last_results = None

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

        # Performance Information (NEW)
        perf_group = QGroupBox("Performance Information")
        perf_layout = QVBoxLayout(perf_group)

        # Source storage detection
        source_storage_layout = QHBoxLayout()
        source_storage_layout.addWidget(QLabel("Source Storage:"))
        self.source_storage_label = QLabel("Not detected")
        self.source_storage_label.setObjectName("mutedText")
        self.source_storage_label.setToolTip("Detected storage type and recommended thread count")
        source_storage_layout.addWidget(self.source_storage_label)
        source_storage_layout.addStretch()
        perf_layout.addLayout(source_storage_layout)

        # Target storage detection
        target_storage_layout = QHBoxLayout()
        target_storage_layout.addWidget(QLabel("Target Storage:"))
        self.target_storage_label = QLabel("Not detected")
        self.target_storage_label.setObjectName("mutedText")
        self.target_storage_label.setToolTip("Detected storage type and recommended thread count")
        target_storage_layout.addWidget(self.target_storage_label)
        target_storage_layout.addStretch()
        perf_layout.addLayout(target_storage_layout)

        # Parallel processing info (read-only)
        self.parallel_info_label = QLabel("Parallel processing: Enabled (auto-detect)")
        self.parallel_info_label.setObjectName("mutedText")
        self.parallel_info_label.setToolTip(
            "Both sources will be hashed simultaneously with optimal thread allocation.\n"
            "NVMe drives: 16+ threads | SATA SSD: 8 threads | External SSD: 4 threads | HDD: 1 thread"
        )
        perf_layout.addWidget(self.parallel_info_label)

        settings_layout.addWidget(perf_group)
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
        """Add folder to source or target - expands to individual files for accurate counting"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            f"Select {panel_type.title()} Folder",
            ""
        )

        if folder_path:
            folder = Path(folder_path)
            target_list = self.source_paths if panel_type == 'source' else self.target_paths

            # Recursively add all files from folder (not the folder itself)
            added = 0
            for file_path in folder.rglob('*'):
                if file_path.is_file():
                    if file_path not in target_list:
                        target_list.append(file_path)
                        added += 1

            self._rebuild_tree(panel_type)
            self._update_ui_state()

            if added > 0:
                self.info(f"Added {added} file(s) to {panel_type} from folder")

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
        """Rebuild tree with hierarchical folder structure for source or target"""
        tree = self.source_tree if panel_type == 'source' else self.target_tree
        paths = self.source_paths if panel_type == 'source' else self.target_paths

        tree.clear()

        if not paths:
            return

        # Find common root path
        if len(paths) == 1:
            common_root = paths[0].parent
        else:
            # Find common ancestor
            all_parts = [list(f.parents)[::-1] for f in paths]
            common_root = None
            for parts in zip(*all_parts):
                if len(set(parts)) == 1:
                    common_root = parts[0]
                else:
                    break

        if common_root is None:
            common_root = Path("/")

        # Build folder hierarchy
        folder_items = {}  # Path -> QTreeWidgetItem

        for file_path in sorted(paths):
            # Get relative path from common root
            try:
                rel_path = file_path.relative_to(common_root)
            except ValueError:
                # File not under common root, use full path
                rel_path = file_path

            # Create folder items for all parent directories
            current_parent = None
            for i, part in enumerate(rel_path.parts[:-1]):
                # Build path up to this level
                partial_path = common_root / Path(*rel_path.parts[:i+1])

                if partial_path not in folder_items:
                    # Create folder item
                    folder_item = QTreeWidgetItem()
                    folder_item.setText(0, f"📁 {part}")
                    folder_item.setData(0, Qt.UserRole, str(partial_path))

                    if current_parent is None:
                        tree.addTopLevelItem(folder_item)
                    else:
                        current_parent.addChild(folder_item)

                    folder_items[partial_path] = folder_item

                current_parent = folder_items[partial_path]

            # Add file item
            file_item = QTreeWidgetItem()
            file_item.setText(0, f"📄 {file_path.name}")
            file_item.setData(0, Qt.UserRole, str(file_path))

            if current_parent is None:
                tree.addTopLevelItem(file_item)
            else:
                current_parent.addChild(file_item)

        # Expand all folders by default
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

        # Update storage detection
        if has_source:
            self._update_source_storage_detection()
        else:
            self.source_storage_label.setText("Not detected")

        if has_target:
            self._update_target_storage_detection()
        else:
            self.target_storage_label.setText("Not detected")

    def _update_source_storage_detection(self):
        """Update source storage detection display"""
        if not self.source_paths:
            self.source_storage_label.setText("Not detected")
            return

        # Use first path for detection
        first_path = self.source_paths[0]

        # Delegate to controller
        result = self.controller.detect_storage(first_path)

        if result.success:
            info = result.value

            # Calculate optimal threads using ThreadCalculator
            from ...utils.thread_calculator import ThreadCalculator
            calculator = ThreadCalculator()
            threads = calculator.calculate_optimal_threads(
                source_info=info,
                dest_info=None,
                file_count=len(self.source_paths),
                operation_type="hash"
            )

            # Format display with color coding
            display_text = f"{info.drive_type.value} on {info.drive_letter} | {threads} threads"

            # Color code by confidence
            if info.confidence > 0.8:
                color = "#28a745"  # Green
            elif info.confidence > 0.6:
                color = "#ffc107"  # Yellow
            else:
                color = "#6c757d"  # Gray

            self.source_storage_label.setText(display_text)
            self.source_storage_label.setStyleSheet(f"color: {color};")

            # Update tooltip with technical details
            tooltip = (
                f"Drive Type: {info.drive_type.value}\n"
                f"Bus Type: {info.bus_type.name}\n"
                f"Recommended Threads: {threads}\n"
                f"File Count: {len(self.source_paths)}\n"
                f"Detection Method: {info.detection_method}\n"
                f"Confidence: {info.confidence:.0%}"
            )
            self.source_storage_label.setToolTip(tooltip)

        else:
            self.source_storage_label.setText(f"Detection failed")
            self.source_storage_label.setStyleSheet("color: #dc3545;")  # Red
            logger.debug(f"Source storage detection failed: {result.error.user_message}")

    def _update_target_storage_detection(self):
        """Update target storage detection display"""
        if not self.target_paths:
            self.target_storage_label.setText("Not detected")
            return

        # Use first path for detection
        first_path = self.target_paths[0]

        # Delegate to controller
        result = self.controller.detect_storage(first_path)

        if result.success:
            info = result.value

            # Calculate optimal threads using ThreadCalculator
            from ...utils.thread_calculator import ThreadCalculator
            calculator = ThreadCalculator()
            threads = calculator.calculate_optimal_threads(
                source_info=info,
                dest_info=None,
                file_count=len(self.target_paths),
                operation_type="hash"
            )

            # Format display with color coding
            display_text = f"{info.drive_type.value} on {info.drive_letter} | {threads} threads"

            # Color code by confidence
            if info.confidence > 0.8:
                color = "#28a745"  # Green
            elif info.confidence > 0.6:
                color = "#ffc107"  # Yellow
            else:
                color = "#6c757d"  # Gray

            self.target_storage_label.setText(display_text)
            self.target_storage_label.setStyleSheet(f"color: {color};")

            # Update tooltip with technical details
            tooltip = (
                f"Drive Type: {info.drive_type.value}\n"
                f"Bus Type: {info.bus_type.name}\n"
                f"Recommended Threads: {threads}\n"
                f"File Count: {len(self.target_paths)}\n"
                f"Detection Method: {info.detection_method}\n"
                f"Confidence: {info.confidence:.0%}"
            )
            self.target_storage_label.setToolTip(tooltip)

        else:
            self.target_storage_label.setText(f"Detection failed")
            self.target_storage_label.setStyleSheet("color: #dc3545;")  # Red
            logger.debug(f"Target storage detection failed: {result.error.user_message}")

    def _get_selected_algorithm(self) -> str:
        """Get selected algorithm"""
        if self.sha256_radio.isChecked():
            return 'sha256'
        elif self.sha1_radio.isChecked():
            return 'sha1'
        else:
            return 'md5'

    def _start_verification(self):
        """Start hash verification in background thread"""
        if not self.source_paths or not self.target_paths:
            self.error("Both source and target files must be selected")
            return

        # Get algorithm
        algorithm = self._get_selected_algorithm()

        # Save settings
        self._save_settings()

        # Create settings object
        settings = HashVerificationSettings(
            algorithm=algorithm,
            enable_parallel=True,  # Always enabled
            max_workers_override=None,  # Auto-detect
            generate_csv=self.generate_csv_check.isChecked(),
            include_metadata=True
        )

        self.info(f"Starting hash verification with {algorithm.upper()}")
        self.set_operation_active(True)

        # Update UI
        self.verify_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        # Delegate to controller
        result = self.controller.start_verification_workflow(
            source_paths=self.source_paths,
            target_paths=self.target_paths,
            settings=settings
        )

        if result.success:
            # Controller returns worker
            self.current_worker = result.value
            self.current_worker.progress_update.connect(self._on_progress)
            self.current_worker.result_ready.connect(self._on_verification_complete)
            self.current_worker.start()
        else:
            # Workflow failed to start
            self.set_operation_active(False)
            self.error(f"Failed to start verification: {result.error.user_message}")
            self.verify_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)

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

            # NEW: Count all four categories
            matches = sum(1 for vr in result.value.values() if vr.match)
            mismatches = sum(1 for vr in result.value.values() if vr.comparison_type == 'hash_mismatch')
            missing_target = sum(1 for vr in result.value.values() if vr.comparison_type == 'missing_target')
            missing_source = sum(1 for vr in result.value.values() if vr.comparison_type == 'missing_source')

            # Extract metrics from Result metadata (NEW: parallel verification includes metrics)
            combined_speed = 0
            source_speed = 0
            target_speed = 0

            if result.metadata:
                # Get individual drive speeds
                source_speed = result.metadata.get('source_speed_mbps', 0)
                target_speed = result.metadata.get('target_speed_mbps', 0)
                combined_speed = result.metadata.get('effective_speed_mbps', 0)

                # Fallback calculation if parallel metadata not available
                if combined_speed == 0 and 'source_metrics' in result.metadata and 'target_metrics' in result.metadata:
                    source_metrics = result.metadata.get('source_metrics')
                    target_metrics = result.metadata.get('target_metrics')

                    if source_metrics and target_metrics:
                        source_speed = source_metrics.average_speed_mbps if source_metrics else 0
                        target_speed = target_metrics.average_speed_mbps if target_metrics else 0

                        total_bytes = (
                            (source_metrics.processed_bytes if source_metrics else 0) +
                            (target_metrics.processed_bytes if target_metrics else 0)
                        )
                        total_duration = max(
                            source_metrics.duration if source_metrics else 0,
                            target_metrics.duration if target_metrics else 0
                        )
                        if total_duration > 0:
                            combined_speed = (total_bytes / (1024 * 1024)) / total_duration

            # Update statistics with proper null safety
            self.update_stats(
                total=total,
                success=matches,
                failed=mismatches + missing_target + missing_source,  # All non-matches are "failures"
                speed=combined_speed
            )

            # NEW: Detailed summary with all four categories
            self.success("=" * 60)
            self.success("VERIFICATION COMPLETE")
            self.success("=" * 60)
            self.success(f"Matched:              {matches:>4}")
            if mismatches > 0:
                self.warning(f"Mismatched:           {mismatches:>4}  (Hash differs)")
            else:
                self.success(f"Mismatched:           {mismatches:>4}")

            if missing_target > 0:
                self.warning(f"Missing from Target:  {missing_target:>4}  (In source only)")
            else:
                self.success(f"Missing from Target:  {missing_target:>4}")

            if missing_source > 0:
                self.warning(f"Missing from Source:  {missing_source:>4}  (In target only)")
            else:
                self.success(f"Missing from Source:  {missing_source:>4}")

            self.success(f"{'─' * 60}")
            self.success(f"Total Files:          {total:>4}")

            # Performance metrics
            if source_speed > 0 or target_speed > 0:
                self.success(f"\nPERFORMANCE:")
                if source_speed > 0:
                    self.info(f"  Source Hashing Speed: {source_speed:>8.1f} MB/s")
                if target_speed > 0:
                    self.info(f"  Target Hashing Speed: {target_speed:>8.1f} MB/s")
                if combined_speed > 0:
                    self.info(f"  Combined Throughput:  {combined_speed:>8.1f} MB/s")

            self.success("=" * 60)

            # Offer to export CSV
            if self.generate_csv_check.isChecked():
                self._export_csv()

        else:
            self.error(f"Verification failed: {result.error.user_message}")

    def _cancel_operation(self):
        """Cancel operation"""
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.warning("Cancelling hash verification...")
            self.current_worker.wait(3000)  # Wait up to 3 seconds for clean shutdown

    def _export_csv(self):
        """Export verification results to CSV using professional HashReportGenerator"""
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
                # Convert dict to list of VerificationResult objects
                verification_results_list = list(self.last_results.values())

                # Use professional report generator
                report_gen = HashReportGenerator()

                success = report_gen.generate_verification_csv(
                    verification_results=verification_results_list,
                    output_path=Path(filename),
                    algorithm=algorithm,
                    include_metadata=True
                )

                if success:
                    self.success(f"Verification report exported: {Path(filename).name}")
                    self.info(f"Report location: {filename}")
                else:
                    self.error("Failed to generate verification report")

            except Exception as e:
                self.error(f"Failed to export CSV: {e}")

    def cleanup(self):
        """Clean up resources"""
        if self.controller:
            self.controller.cleanup()
        self.current_worker = None
        self.last_results = None
