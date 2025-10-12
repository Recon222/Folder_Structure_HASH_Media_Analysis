#!/usr/bin/env python3
"""
Calculate Hashes Sub-Tab - Single hash calculation with full viewport settings

Features:
- Hierarchical file tree (like media analysis)
- Full viewport scrollable settings panel
- Multiple algorithm support
- CSV report generation
- Performance tuning options
- Large statistics display
"""

from pathlib import Path
from typing import List, Optional
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox,
    QCheckBox, QRadioButton, QButtonGroup, QComboBox, QSpinBox, QScrollArea, QTreeWidget,
    QTreeWidgetItem, QSizePolicy, QFileDialog, QMessageBox
)

from ..components.base_operation_tab import BaseOperationTab
from ..components.operation_log_console import OperationLogConsole
from ...core.unified_hash_calculator import UnifiedHashCalculator
from ...core.workers.hash_worker import HashWorker
from core.result_types import Result
from core.logger import logger
from core.hash_reports import HashReportGenerator


class CalculateHashesTab(BaseOperationTab):
    """Calculate hashes for files and folders with professional UI"""

    def __init__(self, shared_logger: Optional[OperationLogConsole] = None, parent=None):
        """
        Initialize Calculate Hashes tab

        Args:
            shared_logger: Shared logger console instance
            parent: Parent widget
        """
        super().__init__("Calculate Hashes", shared_logger, parent)

        # State
        self.selected_paths: List[Path] = []
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

        # Left panel - File selection
        self._create_file_panel(left_container)

        # Right panel - Settings and controls
        self._create_settings_panel(right_container)

    def _create_file_panel(self, container):
        """Create file selection panel"""
        layout = QVBoxLayout(container)

        # Header
        header_label = QLabel("📁 Files to Process")
        header_label.setFont(self.get_section_font())
        layout.addWidget(header_label)

        # File selection buttons
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

        # File tree widget (hierarchical display)
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["Files and Folders"])
        self.file_tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.file_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.file_tree.setMinimumHeight(200)
        self.file_tree.setAlternatingRowColors(True)
        layout.addWidget(self.file_tree)

        # File count label
        self.file_count_label = QLabel("No files selected")
        self.file_count_label.setObjectName("mutedText")
        layout.addWidget(self.file_count_label)

        # Statistics section (hidden initially)
        stats = self.create_stats_section()
        layout.addWidget(stats)

    def _create_settings_panel(self, container):
        """Create settings and control panel"""
        layout = QVBoxLayout(container)

        # Header
        header_label = QLabel("⚙️ Hash Settings")
        header_label.setFont(self.get_section_font())
        layout.addWidget(header_label)

        # Scrollable settings area (FULL VIEWPORT)
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

        # Output options
        output_group = QGroupBox("Output Options")
        output_layout = QVBoxLayout(output_group)

        self.generate_csv_check = QCheckBox("Generate CSV report")
        self.generate_csv_check.setChecked(True)
        output_layout.addWidget(self.generate_csv_check)

        self.include_metadata_check = QCheckBox("Include file metadata (size, dates)")
        self.include_metadata_check.setChecked(True)
        output_layout.addWidget(self.include_metadata_check)

        self.include_timestamps_check = QCheckBox("Include processing timestamps")
        self.include_timestamps_check.setChecked(False)
        output_layout.addWidget(self.include_timestamps_check)

        # CSV path
        csv_path_layout = QHBoxLayout()
        csv_path_layout.addWidget(QLabel("CSV Path:"))
        self.csv_path_edit = QLabel("(will prompt when saving)")
        self.csv_path_edit.setObjectName("mutedText")
        csv_path_layout.addWidget(self.csv_path_edit)
        csv_path_layout.addStretch()
        output_layout.addLayout(csv_path_layout)

        settings_layout.addWidget(output_group)

        # Performance options
        perf_group = QGroupBox("Performance Settings")
        perf_layout = QVBoxLayout(perf_group)

        # Enable parallel processing
        self.enable_parallel_check = QCheckBox("Enable parallel processing (storage-aware)")
        self.enable_parallel_check.setChecked(True)
        self.enable_parallel_check.setToolTip(
            "Automatically detects storage type (SSD/HDD) and optimizes thread count.\n"
            "NVMe SSD: 300-400% faster | SATA SSD: 150-230% faster | HDD: No degradation"
        )
        self.enable_parallel_check.stateChanged.connect(self._on_parallel_toggled)
        perf_layout.addWidget(self.enable_parallel_check)

        # Thread count override (manual control)
        workers_layout = QHBoxLayout()
        workers_layout.addWidget(QLabel("Thread Override:"))
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(0, 32)
        self.workers_spin.setValue(0)
        self.workers_spin.setSpecialValueText("Auto")
        self.workers_spin.setToolTip(
            "Manual thread count override (0 = Auto-detect based on storage type)\n"
            "Recommended: Leave at Auto for optimal performance"
        )
        workers_layout.addWidget(self.workers_spin)
        workers_layout.addStretch()
        perf_layout.addLayout(workers_layout)

        # Storage detection info (display only)
        self.storage_info_label = QLabel("Storage: Not detected yet")
        self.storage_info_label.setObjectName("mutedText")
        self.storage_info_label.setToolTip("Detected storage type and recommended thread count")
        perf_layout.addWidget(self.storage_info_label)

        settings_layout.addWidget(perf_group)
        settings_layout.addStretch()

        scroll_area.setWidget(settings_container)
        layout.addWidget(scroll_area)

        # Progress section
        self.create_progress_section(layout)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.calculate_btn = QPushButton("🧮 Calculate Hashes")
        self.calculate_btn.setEnabled(False)
        self.calculate_btn.setMinimumHeight(36)
        self.calculate_btn.setStyleSheet("""
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
        button_layout.addWidget(self.calculate_btn)

        self.cancel_btn = QPushButton("🛑 Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setMinimumHeight(36)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _connect_signals(self):
        """Connect signals"""
        self.calculate_btn.clicked.connect(self._start_calculation)
        self.cancel_btn.clicked.connect(self._cancel_operation)

    def _load_settings(self):
        """Load saved settings"""
        settings = QSettings()
        settings.beginGroup("CopyHashVerify/CalculateHashes")

        # Load algorithm
        algorithm = settings.value("algorithm", "sha256")
        if algorithm == "sha256":
            self.sha256_radio.setChecked(True)
        elif algorithm == "sha1":
            self.sha1_radio.setChecked(True)
        else:
            self.md5_radio.setChecked(True)

        # Load options
        self.generate_csv_check.setChecked(settings.value("generate_csv", True, type=bool))
        self.include_metadata_check.setChecked(settings.value("include_metadata", True, type=bool))

        # NEW: Load parallel processing settings
        self.enable_parallel_check.setChecked(settings.value("enable_parallel", True, type=bool))
        thread_override = settings.value("thread_override", 0, type=int)
        self.workers_spin.setValue(thread_override)

        settings.endGroup()

    def _save_settings(self):
        """Save current settings"""
        settings = QSettings()
        settings.beginGroup("CopyHashVerify/CalculateHashes")

        # Save algorithm
        if self.sha256_radio.isChecked():
            settings.setValue("algorithm", "sha256")
        elif self.sha1_radio.isChecked():
            settings.setValue("algorithm", "sha1")
        else:
            settings.setValue("algorithm", "md5")

        # Save options
        settings.setValue("generate_csv", self.generate_csv_check.isChecked())
        settings.setValue("include_metadata", self.include_metadata_check.isChecked())

        # NEW: Save parallel processing settings
        settings.setValue("enable_parallel", self.enable_parallel_check.isChecked())
        settings.setValue("thread_override", self.workers_spin.value())

        settings.endGroup()

    def _on_algorithm_changed(self, button):
        """Handle algorithm radio button change"""
        algorithm = self._get_selected_algorithm()
        self.info(f"Hash algorithm set to {algorithm.upper()}")

    def _on_parallel_toggled(self, state):
        """Handle parallel processing toggle"""
        enabled = state == Qt.Checked
        if enabled:
            self.info("Parallel processing enabled (storage-aware optimization)")
            # Trigger storage detection if files are selected
            if self.selected_paths:
                self._update_storage_detection()
        else:
            self.info("Parallel processing disabled (sequential mode)")
            self.storage_info_label.setText("Storage: Detection disabled")

    def _add_files(self):
        """Add files to hash"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Hash",
            "",
            "All Files (*.*)"
        )

        if file_paths:
            for file_path in file_paths:
                path = Path(file_path)
                if path not in self.selected_paths:
                    self.selected_paths.append(path)

            self._rebuild_file_tree()
            self._update_ui_state()

    def _add_folder(self):
        """Add folder to hash"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Hash",
            ""
        )

        if folder_path:
            path = Path(folder_path)
            if path not in self.selected_paths:
                self.selected_paths.append(path)

            self._rebuild_file_tree()
            self._update_ui_state()

    def _clear_files(self):
        """Clear all files"""
        self.file_tree.clear()
        self.selected_paths.clear()
        self.last_results = None
        self._update_ui_state()

        if self.stats_group:
            self.stats_group.setVisible(False)

    def _rebuild_file_tree(self):
        """Rebuild file tree from selected paths"""
        self.file_tree.clear()

        if not self.selected_paths:
            return

        for path in sorted(self.selected_paths):
            if path.is_file():
                item = QTreeWidgetItem()
                item.setText(0, f"📄 {path.name}")
                item.setData(0, Qt.UserRole, str(path))
                self.file_tree.addTopLevelItem(item)
            else:
                item = QTreeWidgetItem()
                item.setText(0, f"📁 {path.name}")
                item.setData(0, Qt.UserRole, str(path))
                self.file_tree.addTopLevelItem(item)

        self.file_tree.expandAll()

    def _update_ui_state(self):
        """Update UI state based on selections"""
        has_files = len(self.selected_paths) > 0

        # Update labels
        if has_files:
            self.file_count_label.setText(f"{len(self.selected_paths)} items selected")
        else:
            self.file_count_label.setText("No files selected")

        # Update buttons
        self.clear_btn.setEnabled(has_files)
        self.calculate_btn.setEnabled(has_files and not self.operation_active)

        # Update storage detection info when parallel processing is enabled
        if has_files and self.enable_parallel_check.isChecked():
            self._update_storage_detection()
        elif not self.enable_parallel_check.isChecked():
            self.storage_info_label.setText("Storage: Detection disabled")
        else:
            self.storage_info_label.setText("Storage: Not detected yet")

    def _update_storage_detection(self):
        """Detect and display storage information for selected files"""
        if not self.selected_paths:
            self.storage_info_label.setText("Storage: Not detected yet")
            return

        try:
            from ...core.storage_detector import StorageDetector

            # Use first path for detection (all paths typically on same drive)
            first_path = self.selected_paths[0]

            # Detect storage
            detector = StorageDetector()
            info = detector.analyze_path(first_path)

            # Format display text
            drive_type_display = {
                'nvme': 'NVMe SSD',
                'ssd': 'SATA SSD',
                'external_ssd': 'External SSD',
                'hdd': 'HDD',
                'external_hdd': 'External HDD',
                'unknown': 'Unknown'
            }.get(info.drive_type.value, info.drive_type.value.upper())

            confidence_pct = int(info.confidence * 100)

            # Color based on confidence
            if info.confidence >= 0.8:
                color = "#28a745"  # Green for high confidence
            elif info.confidence >= 0.6:
                color = "#ffc107"  # Yellow for moderate confidence
            else:
                color = "#6c757d"  # Gray for low confidence

            display_text = (
                f'<span style="color: {color};">'
                f'{drive_type_display} on {info.drive_letter} | '
                f'{info.recommended_threads} threads '
                f'({confidence_pct}% confidence)'
                f'</span>'
            )

            self.storage_info_label.setText(display_text)
            self.storage_info_label.setToolTip(
                f"Drive Type: {drive_type_display}\n"
                f"Bus Type: {info.bus_type.name}\n"
                f"Recommended Threads: {info.recommended_threads}\n"
                f"Detection Method: {info.detection_method}\n"
                f"Confidence: {confidence_pct}%"
            )

        except Exception as e:
            logger.debug(f"Failed to detect storage: {e}")
            self.storage_info_label.setText("Storage: Detection failed")

    def _get_selected_algorithm(self) -> str:
        """Get currently selected algorithm"""
        if self.sha256_radio.isChecked():
            return 'sha256'
        elif self.sha1_radio.isChecked():
            return 'sha1'
        else:
            return 'md5'

    def _start_calculation(self):
        """Start hash calculation in background thread"""
        if not self.selected_paths:
            self.error("No files selected")
            return

        # Get algorithm
        algorithm = self._get_selected_algorithm()

        # Get parallel processing settings
        enable_parallel = self.enable_parallel_check.isChecked()
        thread_override = self.workers_spin.value() if self.workers_spin.value() > 0 else None

        # Save settings
        self._save_settings()

        # Log configuration
        if enable_parallel:
            if thread_override:
                self.info(f"Starting hash calculation with {algorithm.upper()} ({thread_override} threads)")
            else:
                self.info(f"Starting hash calculation with {algorithm.upper()} (auto-detect threads)")
        else:
            self.info(f"Starting hash calculation with {algorithm.upper()} (sequential mode)")

        self.set_operation_active(True)

        # Update UI
        self.calculate_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.add_files_btn.setEnabled(False)
        self.add_folder_btn.setEnabled(False)

        # Create and start worker thread with parallel processing config
        self.current_worker = HashWorker(
            paths=self.selected_paths,
            algorithm=algorithm,
            enable_parallel=enable_parallel,
            max_workers_override=thread_override
        )
        self.current_worker.progress_update.connect(self._on_progress)
        self.current_worker.result_ready.connect(self._on_calculation_complete)
        self.current_worker.start()

    def _on_progress(self, percentage: int, message: str):
        """Handle progress update"""
        self.update_progress(percentage, message)

    def _on_calculation_complete(self, result: Result):
        """Handle calculation completion"""
        self.set_operation_active(False)

        # Update UI
        self.calculate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.add_files_btn.setEnabled(True)
        self.add_folder_btn.setEnabled(True)

        if result.success:
            self.last_results = result.value
            hash_count = len(result.value)

            # Update statistics
            total_size = sum(hr.file_size for hr in result.value.values())
            total_duration = sum(hr.duration for hr in result.value.values())
            avg_speed = (total_size / (1024 * 1024)) / total_duration if total_duration > 0 else 0

            self.update_stats(
                total=hash_count,
                success=hash_count,
                failed=0,
                speed=avg_speed
            )

            self.success(f"Hash calculation complete: {hash_count} files processed")

            # Offer to export CSV
            if self.generate_csv_check.isChecked():
                self._export_csv()

        else:
            self.error(f"Hash calculation failed: {result.error.user_message}")

    def _cancel_operation(self):
        """Cancel current operation"""
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.warning("Cancelling hash calculation...")
            self.current_worker.wait(3000)  # Wait up to 3 seconds for clean shutdown

    def _export_csv(self):
        """Export results to CSV using professional HashReportGenerator"""
        if not self.last_results:
            self.error("No results to export")
            return

        algorithm = self._get_selected_algorithm()
        default_filename = f"hash_report_{algorithm}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Hash Report",
            default_filename,
            "CSV Files (*.csv);;All Files (*)"
        )

        if filename:
            try:
                # Convert dict to list of HashResult objects
                hash_results_list = list(self.last_results.values())

                # Use professional report generator
                report_gen = HashReportGenerator()
                include_metadata = self.include_metadata_check.isChecked()

                success = report_gen.generate_single_hash_csv(
                    results=hash_results_list,
                    output_path=Path(filename),
                    algorithm=algorithm,
                    include_metadata=include_metadata
                )

                if success:
                    self.success(f"CSV report exported: {Path(filename).name}")
                    self.info(f"Report location: {filename}")
                else:
                    self.error("Failed to generate CSV report")

            except Exception as e:
                self.error(f"Failed to export CSV: {e}")

    def cleanup(self):
        """Clean up resources"""
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.current_worker.wait(3000)
        self.current_worker = None
        self.last_results = None
