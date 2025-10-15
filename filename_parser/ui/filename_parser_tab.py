#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename Parser Tab - UI for SMPTE timecode extraction from video filenames

Processes video files to extract timestamps and write SMPTE metadata using FFmpeg.
Standalone, modular design following VehicleTrackingTab architecture.
"""

from pathlib import Path
from typing import List, Optional, Dict
from enum import Enum

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QCheckBox, QFileDialog, QProgressBar, QSplitter,
    QComboBox, QSpinBox, QRadioButton, QGridLayout, QTreeWidget,
    QTreeWidgetItem, QScrollArea, QTextEdit, QButtonGroup, QSizePolicy,
    QLineEdit, QDoubleSpinBox, QMessageBox, QTabWidget
)
from PySide6.QtGui import QFont

# Filename parser imports
from filename_parser.controllers.filename_parser_controller import FilenameParserController
from filename_parser.controllers.timeline_controller import TimelineController
from filename_parser.models.filename_parser_models import FilenameParserSettings
from filename_parser.models.processing_result import ProcessingStatistics
from filename_parser.models.timeline_models import RenderSettings, VideoMetadata
from filename_parser.services.json_timeline_export_service import JSONTimelineExportService

# Core imports
from core.models import FormData
from core.result_types import Result
from core.logger import logger
from core.exceptions import UIError, ErrorSeverity


class FilenameParserTab(QWidget):
    """Tab for filename parsing and SMPTE timecode extraction"""

    # Signals
    log_message = Signal(str)
    status_message = Signal(str)

    def __init__(self, form_data: Optional[FormData] = None, parent=None):
        """
        Initialize the Filename Parser tab

        Args:
            form_data: Optional form data for report generation
            parent: Parent widget
        """
        super().__init__(parent)

        # Controllers and services for orchestration
        self.controller = FilenameParserController()
        self.timeline_controller = TimelineController()
        self.json_export_service = JSONTimelineExportService()

        # Form data reference (optional)
        self.form_data = form_data

        # State management
        self.operation_active = False
        self.current_worker = None
        self.timeline_worker = None
        self.last_stats: Optional[ProcessingStatistics] = None
        self.video_metadata_list: List[VideoMetadata] = []  # Store complete metadata for timeline
        self.selected_files: List[Path] = []

        # Settings
        self.settings = FilenameParserSettings()
        self.timeline_settings = RenderSettings()

        self._create_ui()
        self._connect_signals()

    def _create_ui(self):
        """Create the tab UI with two-column layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # Main content splitter
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)

        # Left panel - File selection
        left_panel = self._create_file_panel()
        main_splitter.addWidget(left_panel)

        # Right panel - Settings and controls
        right_panel = self._create_settings_panel()
        main_splitter.addWidget(right_panel)

        # Set splitter proportions (45/55)
        main_splitter.setSizes([450, 550])
        layout.addWidget(main_splitter)

        # Console section
        console_group = self._create_console_section()
        layout.addWidget(console_group)

    def _create_file_panel(self) -> QGroupBox:
        """Create left panel for video file selection"""
        panel = QGroupBox("📁 Video Files to Process")
        layout = QVBoxLayout(panel)

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

        # File tree widget (hierarchical directory structure)
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["Video Files"])
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
        self.stats_group = self._create_stats_section()
        self.stats_group.setVisible(False)
        layout.addWidget(self.stats_group)

        return panel

    def _create_stats_section(self) -> QGroupBox:
        """Create statistics display section"""
        group = QGroupBox("📊 Processing Statistics")
        layout = QGridLayout(group)

        # Stat labels
        self.stat_total_label = QLabel("0")
        self.stat_total_label.setStyleSheet("color: #4B9CD3; font-size: 24px; font-weight: bold;")
        self.stat_success_label = QLabel("0")
        self.stat_success_label.setStyleSheet("color: #52c41a; font-size: 24px; font-weight: bold;")
        self.stat_failed_label = QLabel("0")
        self.stat_failed_label.setStyleSheet("color: #ff4d4f; font-size: 24px; font-weight: bold;")
        self.stat_speed_label = QLabel("0.0")
        self.stat_speed_label.setStyleSheet("color: #4B9CD3; font-size: 24px; font-weight: bold;")

        # Layout in grid
        layout.addWidget(self.stat_total_label, 0, 0, Qt.AlignCenter)
        layout.addWidget(QLabel("Total"), 1, 0, Qt.AlignCenter)

        layout.addWidget(self.stat_success_label, 0, 1, Qt.AlignCenter)
        layout.addWidget(QLabel("Success"), 1, 1, Qt.AlignCenter)

        layout.addWidget(self.stat_failed_label, 0, 2, Qt.AlignCenter)
        layout.addWidget(QLabel("Failed"), 1, 2, Qt.AlignCenter)

        layout.addWidget(self.stat_speed_label, 0, 3, Qt.AlignCenter)
        layout.addWidget(QLabel("Files/Sec"), 1, 3, Qt.AlignCenter)

        return group

    def _create_settings_panel(self) -> QGroupBox:
        """Create right panel for processing settings with tab-based layout"""
        panel = QGroupBox("Processing Settings")
        main_layout = QVBoxLayout(panel)
        main_layout.setSpacing(8)

        # Create tab widget for different features
        self.settings_tabs = QTabWidget()

        # Tab 1: Filename Parsing
        parse_tab = self._create_parse_settings_tab()
        self.settings_tabs.addTab(parse_tab, "🔍 Parse Filenames")

        # Tab 2: Timeline Video Generation
        timeline_tab = self._create_timeline_settings_tab()
        self.settings_tabs.addTab(timeline_tab, "🎬 Timeline Video")

        # Connect tab change signal
        self.settings_tabs.currentChanged.connect(self._on_settings_tab_changed)

        main_layout.addWidget(self.settings_tabs)

        # Shared progress bar (below tabs)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMinimumHeight(28)
        main_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setObjectName("mutedText")
        main_layout.addWidget(self.progress_label)

        # Dynamic action buttons (change based on active tab)
        self.action_button_container = QWidget()
        self.action_button_layout = QVBoxLayout(self.action_button_container)
        self.action_button_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.action_button_container)

        # Create button sets for each tab
        self._create_parse_buttons()
        self._create_timeline_buttons()

        # Show parse buttons by default
        self._show_parse_buttons()

        return panel

    def _create_parse_settings_tab(self) -> QWidget:
        """Create filename parsing settings tab"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setSpacing(8)

        # Create scroll area for settings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setSpacing(12)

        # Pattern Selection section
        pattern_group = self._create_pattern_section()
        settings_layout.addWidget(pattern_group)

        # Frame Rate section
        fps_group = self._create_fps_section()
        settings_layout.addWidget(fps_group)

        # Time Offset section
        offset_group = self._create_time_offset_section()
        settings_layout.addWidget(offset_group)

        # Output Settings section
        output_group = self._create_output_section()
        settings_layout.addWidget(output_group)

        settings_layout.addStretch()
        scroll_area.setWidget(settings_widget)
        main_layout.addWidget(scroll_area)

        return tab

    def _create_pattern_section(self) -> QGroupBox:
        """Create pattern selection section with preview"""
        group = QGroupBox("🔍 Pattern Selection")
        layout = QVBoxLayout(group)

        # Pattern selector with generator button
        selector_layout = QHBoxLayout()

        # ComboBox with AGGRESSIVE border fix
        self.pattern_combo = QComboBox()
        self.pattern_combo.setObjectName("patternCombo")  # For specific styling

        # Add patterns organized by category
        self.pattern_combo.addItem("Auto-detect (Recommended)", "auto")

        # DVR - Dahua Systems
        self.pattern_combo.insertSeparator(self.pattern_combo.count())
        self.pattern_combo.addItem("— DVR - Dahua Systems —", None)
        self.pattern_combo.addItem("  Dahua NVR Standard", "dahua_nvr_standard")
        self.pattern_combo.addItem("  Dahua Web Export", "dahua_web_export")

        # Compact Timestamps
        self.pattern_combo.insertSeparator(self.pattern_combo.count())
        self.pattern_combo.addItem("— Compact Timestamps —", None)
        self.pattern_combo.addItem("  HHMMSS Compact (161048)", "hhmmss_compact")
        self.pattern_combo.addItem("  HH_MM_SS Underscore (16_10_48)", "hh_mm_ss_underscore")
        self.pattern_combo.addItem("  HHMMSSmmm with Milliseconds", "hhmmssmmm_compact")

        # Embedded Date/Time
        self.pattern_combo.insertSeparator(self.pattern_combo.count())
        self.pattern_combo.addItem("— Embedded Date/Time —", None)
        self.pattern_combo.addItem("  Embedded Time (_20240115_143025_)", "embedded_time")
        self.pattern_combo.addItem("  ISO 8601 Basic (20240115T143025)", "iso8601_basic")
        self.pattern_combo.addItem("  ISO 8601 Extended (2024-01-15T14:30:25)", "iso8601_extended")

        # Alternative Formats
        self.pattern_combo.insertSeparator(self.pattern_combo.count())
        self.pattern_combo.addItem("— Alternative Formats —", None)
        self.pattern_combo.addItem("  Screenshot Style (2024-01-15 14-30-25)", "screenshot_style")
        self.pattern_combo.addItem("  Military Date (30JAN24_161325)", "military_date_compact")

        self.pattern_combo.currentIndexChanged.connect(self._update_pattern_preview)
        selector_layout.addWidget(self.pattern_combo)

        self.generator_btn = QPushButton("⚙️ Generator")
        self.generator_btn.clicked.connect(self._open_pattern_generator)
        selector_layout.addWidget(self.generator_btn)

        layout.addLayout(selector_layout)

        # Pattern preview area
        preview_widget = QWidget()
        preview_widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        preview_layout = QVBoxLayout(preview_widget)

        self.pattern_example_label = QLabel("Example: _20240115_143025_")
        self.pattern_example_label.setFont(QFont("Consolas", 10))
        preview_layout.addWidget(self.pattern_example_label)

        self.pattern_regex_label = QLabel("Regex: _(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_")
        self.pattern_regex_label.setFont(QFont("Consolas", 9))
        self.pattern_regex_label.setObjectName("mutedText")
        preview_layout.addWidget(self.pattern_regex_label)

        self.pattern_match_label = QLabel("✓ Match: 14:30:25 (2024-01-15)")
        self.pattern_match_label.setStyleSheet("color: #52c41a; font-weight: bold;")
        preview_layout.addWidget(self.pattern_match_label)

        layout.addWidget(preview_widget)

        return group

    def _create_fps_section(self) -> QGroupBox:
        """Create frame rate detection section"""
        group = QGroupBox("🎞️ Frame Rate Settings")
        layout = QVBoxLayout(group)

        # Auto-detect checkbox
        self.auto_detect_fps = QCheckBox("Auto-detect frame rate from video files (recommended)")
        self.auto_detect_fps.setChecked(True)
        self.auto_detect_fps.toggled.connect(self._toggle_fps_settings)
        layout.addWidget(self.auto_detect_fps)

        # Detection method dropdown (NEW)
        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("Detection Method:"))

        self.fps_method_combo = QComboBox()
        self.fps_method_combo.setObjectName("fpsMethodCombo")
        self.fps_method_combo.addItem("📊 Container Metadata (Fast)", "metadata")
        self.fps_method_combo.addItem("⏱️ PTS Timing (Accurate)", "pts_timing")
        self.fps_method_combo.setCurrentIndex(0)  # Default to metadata
        self.fps_method_combo.setEnabled(True)  # Always enabled when detect_fps is checked

        # Tooltip explaining the difference
        self.fps_method_combo.setToolTip(
            "<b>Frame Rate Detection Method:</b><br><br>"
            "<b>Container Metadata (Fast):</b><br>"
            "• Reads r_frame_rate/avg_frame_rate from file<br>"
            "• Instant detection, no processing<br>"
            "• May be INCORRECT for CCTV/DVR files<br>"
            "• DVRs often stamp wrong FPS (e.g., 25fps when actual is 12.5fps)<br><br>"
            "<b>PTS Timing (Accurate):</b><br>"
            "• Calculates FPS from frame timestamps (PTS deltas)<br>"
            "• Measures ACTUAL playback rate<br>"
            "• Slower (~1-2s per file)<br>"
            "• Recommended for forensic/CCTV workflows<br>"
            "• Matches VLC/MPV playback behavior"
        )

        method_layout.addWidget(self.fps_method_combo)
        method_layout.addStretch()
        layout.addLayout(method_layout)

        # Manual FPS selection
        manual_layout = QHBoxLayout()
        manual_layout.addWidget(QLabel("Manual FPS:"))

        self.manual_fps_combo = QComboBox()
        self.manual_fps_combo.addItems([
            "23.976 fps (Film)",
            "24 fps",
            "25 fps (PAL)",
            "29.97 fps (NTSC)",
            "30 fps",
            "50 fps",
            "59.94 fps",
            "60 fps"
        ])
        self.manual_fps_combo.setCurrentIndex(3)  # Default 29.97
        self.manual_fps_combo.setEnabled(False)
        self.manual_fps_combo.setToolTip(
            "Manually specify frame rate (disables auto-detection).<br>"
            "Use this when both metadata and PTS detection fail."
        )
        manual_layout.addWidget(self.manual_fps_combo)
        layout.addLayout(manual_layout)

        # Detect button
        self.detect_fps_btn = QPushButton("🔍 Detect Frame Rates Now")
        self.detect_fps_btn.clicked.connect(self._detect_frame_rates)
        self.detect_fps_btn.setEnabled(False)
        layout.addWidget(self.detect_fps_btn)

        return group

    def _create_time_offset_section(self) -> QGroupBox:
        """Create time offset configuration section"""
        group = QGroupBox("⏰ Time Offset (Optional)")
        layout = QVBoxLayout(group)

        # Enable checkbox
        self.enable_offset = QCheckBox("Enable time offset correction")
        self.enable_offset.setChecked(False)
        self.enable_offset.toggled.connect(self._toggle_offset_settings)
        layout.addWidget(self.enable_offset)

        # Offset settings container
        self.offset_container = QWidget()
        offset_layout = QVBoxLayout(self.offset_container)
        offset_layout.setContentsMargins(20, 0, 0, 0)

        # Direction radio buttons
        direction_layout = QHBoxLayout()
        direction_layout.addWidget(QLabel("Direction:"))

        self.offset_behind = QRadioButton("Camera Behind")
        self.offset_ahead = QRadioButton("Camera Ahead")
        self.offset_behind.setChecked(True)
        self.offset_behind.setEnabled(False)
        self.offset_ahead.setEnabled(False)

        self.offset_direction_group = QButtonGroup()
        self.offset_direction_group.addButton(self.offset_behind)
        self.offset_direction_group.addButton(self.offset_ahead)

        direction_layout.addWidget(self.offset_behind)
        direction_layout.addWidget(self.offset_ahead)
        direction_layout.addStretch()
        offset_layout.addLayout(direction_layout)

        # Time spinboxes
        time_layout = QHBoxLayout()

        time_layout.addWidget(QLabel("Hours:"))
        self.offset_hours = QSpinBox()
        self.offset_hours.setRange(0, 23)
        self.offset_hours.setEnabled(False)
        time_layout.addWidget(self.offset_hours)

        time_layout.addWidget(QLabel("Minutes:"))
        self.offset_minutes = QSpinBox()
        self.offset_minutes.setRange(0, 59)
        self.offset_minutes.setEnabled(False)
        time_layout.addWidget(self.offset_minutes)

        time_layout.addWidget(QLabel("Seconds:"))
        self.offset_seconds = QSpinBox()
        self.offset_seconds.setRange(0, 59)
        self.offset_seconds.setEnabled(False)
        time_layout.addWidget(self.offset_seconds)

        time_layout.addStretch()
        offset_layout.addLayout(time_layout)

        layout.addWidget(self.offset_container)

        return group

    def _create_output_section(self) -> QGroupBox:
        """Create output structure settings section"""
        group = QGroupBox("💾 Output Settings")
        layout = QVBoxLayout(group)

        # Output structure radio buttons
        self.output_local = QRadioButton("Save to local subdirectory (next to source files)")
        self.output_mirrored = QRadioButton("Mirrored directory structure")
        self.output_local.setChecked(True)

        self.output_structure_group = QButtonGroup()
        self.output_structure_group.addButton(self.output_local)
        self.output_structure_group.addButton(self.output_mirrored)

        layout.addWidget(self.output_local)
        layout.addWidget(self.output_mirrored)

        # Base directory selection (for mirrored)
        self.base_dir_container = QWidget()
        base_dir_layout = QHBoxLayout(self.base_dir_container)
        base_dir_layout.setContentsMargins(20, 0, 0, 0)

        base_dir_layout.addWidget(QLabel("Base Directory:"))

        self.base_dir_input = QLabel("(Select directory...)")
        self.base_dir_input.setObjectName("mutedText")
        self.base_dir_input.setEnabled(False)
        base_dir_layout.addWidget(self.base_dir_input, 1)

        self.browse_btn = QPushButton("📂 Browse")
        self.browse_btn.clicked.connect(self._browse_base_directory)
        self.browse_btn.setEnabled(False)
        base_dir_layout.addWidget(self.browse_btn)

        layout.addWidget(self.base_dir_container)

        # Connect output structure toggle
        self.output_mirrored.toggled.connect(self._toggle_output_structure)

        return group

    def _create_parse_buttons(self):
        """Create button set for Parse Filenames tab"""
        self.parse_button_widget = QWidget()
        layout = QVBoxLayout(self.parse_button_widget)
        layout.setContentsMargins(0, 10, 0, 0)

        # Primary action buttons
        primary_layout = QHBoxLayout()

        self.process_btn = QPushButton("🔍 Parse Filenames")
        self.process_btn.setObjectName("primaryAction")
        self.process_btn.clicked.connect(self._start_processing)
        self.process_btn.setEnabled(False)
        self.process_btn.setMinimumHeight(36)
        primary_layout.addWidget(self.process_btn)

        self.cancel_btn = QPushButton("⏹️ Cancel")
        self.cancel_btn.clicked.connect(self._cancel_processing)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setMinimumHeight(36)
        primary_layout.addWidget(self.cancel_btn)

        layout.addLayout(primary_layout)

        # Export action buttons (enabled after parsing)
        export_layout = QHBoxLayout()

        self.export_csv_btn = QPushButton("📊 Export CSV")
        self.export_csv_btn.clicked.connect(self._export_csv)
        self.export_csv_btn.setEnabled(False)
        self.export_csv_btn.setMinimumHeight(32)
        export_layout.addWidget(self.export_csv_btn)

        self.export_json_btn = QPushButton("📄 Export JSON Timeline")
        self.export_json_btn.clicked.connect(self._export_json_timeline)
        self.export_json_btn.setEnabled(False)
        self.export_json_btn.setMinimumHeight(32)
        export_layout.addWidget(self.export_json_btn)

        self.copy_with_smpte_btn = QPushButton("📹 Copy with SMPTE")
        self.copy_with_smpte_btn.clicked.connect(self._copy_with_smpte)
        self.copy_with_smpte_btn.setEnabled(False)
        self.copy_with_smpte_btn.setMinimumHeight(32)
        export_layout.addWidget(self.copy_with_smpte_btn)

        layout.addLayout(export_layout)

    def _create_timeline_buttons(self):
        """Create button set for Timeline Video tab"""
        self.timeline_button_widget = QWidget()
        layout = QHBoxLayout(self.timeline_button_widget)
        layout.setContentsMargins(0, 10, 0, 0)

        self.timeline_render_btn = QPushButton("🎬 Generate Timeline Video")
        self.timeline_render_btn.setObjectName("primaryAction")
        self.timeline_render_btn.clicked.connect(self._start_timeline_rendering)
        self.timeline_render_btn.setEnabled(False)
        self.timeline_render_btn.setMinimumHeight(36)
        layout.addWidget(self.timeline_render_btn)

        self.timeline_cancel_btn = QPushButton("⏹️ Cancel Render")
        self.timeline_cancel_btn.clicked.connect(self._cancel_timeline_rendering)
        self.timeline_cancel_btn.setEnabled(False)
        self.timeline_cancel_btn.setMinimumHeight(36)
        layout.addWidget(self.timeline_cancel_btn)

    def _show_parse_buttons(self):
        """Show parse buttons, hide timeline buttons"""
        # Clear layout
        while self.action_button_layout.count():
            child = self.action_button_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)

        # Add parse buttons
        self.action_button_layout.addWidget(self.parse_button_widget)
        self.parse_button_widget.setVisible(True)
        if hasattr(self, 'timeline_button_widget'):
            self.timeline_button_widget.setVisible(False)

    def _show_timeline_buttons(self):
        """Show timeline buttons, hide parse buttons"""
        # Clear layout
        while self.action_button_layout.count():
            child = self.action_button_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)

        # Add timeline buttons
        self.action_button_layout.addWidget(self.timeline_button_widget)
        self.timeline_button_widget.setVisible(True)
        if hasattr(self, 'parse_button_widget'):
            self.parse_button_widget.setVisible(False)

    def _on_settings_tab_changed(self, index: int):
        """Handle settings tab change to swap action buttons"""
        if index == 0:  # Parse Filenames tab
            self._show_parse_buttons()
        elif index == 1:  # Timeline Video tab
            self._show_timeline_buttons()

    def _create_timeline_settings_tab(self) -> QWidget:
        """Create timeline video generation settings tab - clean and focused"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setSpacing(8)

        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        settings_widget = QWidget()
        layout = QVBoxLayout(settings_widget)
        layout.setSpacing(12)

        # Info banner
        info_label = QLabel(
            "ℹ️  Parse filenames first to extract SMPTE timecodes, "
            "then generate seamless timeline videos with automatic gap detection."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #6c757d; font-size: 11px; padding: 8px;")
        layout.addWidget(info_label)

        # Output Settings Group
        output_group = QGroupBox("Output Settings")
        output_layout = QVBoxLayout(output_group)

        # Output directory
        dir_layout = QHBoxLayout()
        dir_label = QLabel("Output Directory:")
        dir_layout.addWidget(dir_label)

        self.timeline_output_dir_input = QLabel("(Not selected)")
        self.timeline_output_dir_input.setStyleSheet("color: #6c757d;")
        dir_layout.addWidget(self.timeline_output_dir_input, 1)

        self.timeline_browse_btn = QPushButton("📂 Browse")
        self.timeline_browse_btn.clicked.connect(self._browse_timeline_output)
        dir_layout.addWidget(self.timeline_browse_btn)
        output_layout.addLayout(dir_layout)

        # Output filename
        filename_layout = QHBoxLayout()
        filename_label = QLabel("Output Filename:")
        filename_layout.addWidget(filename_label)

        self.timeline_filename_input = QLineEdit("timeline.mp4")
        filename_layout.addWidget(self.timeline_filename_input, 1)
        output_layout.addLayout(filename_layout)

        layout.addWidget(output_group)

        # Timeline Parameters Group
        params_group = QGroupBox("Timeline Parameters")
        params_layout = QGridLayout(params_group)

        # Timeline FPS
        params_layout.addWidget(QLabel("Timeline FPS:"), 0, 0)
        self.timeline_fps_spin = QDoubleSpinBox()
        self.timeline_fps_spin.setRange(1.0, 120.0)
        self.timeline_fps_spin.setValue(30.0)
        self.timeline_fps_spin.setDecimals(2)
        self.timeline_fps_spin.setSuffix(" fps")
        params_layout.addWidget(self.timeline_fps_spin, 0, 1)

        # Min gap duration
        params_layout.addWidget(QLabel("Min Gap Duration:"), 1, 0)
        self.timeline_min_gap_spin = QDoubleSpinBox()
        self.timeline_min_gap_spin.setRange(0.1, 3600.0)
        self.timeline_min_gap_spin.setValue(5.0)
        self.timeline_min_gap_spin.setDecimals(1)
        self.timeline_min_gap_spin.setSuffix(" seconds")
        params_layout.addWidget(self.timeline_min_gap_spin, 1, 1)

        # Output resolution
        params_layout.addWidget(QLabel("Output Resolution:"), 2, 0)
        self.timeline_resolution_combo = QComboBox()
        self.timeline_resolution_combo.addItems([
            "1920x1080 (1080p)",
            "1280x720 (720p)",
            "3840x2160 (4K)",
            "2560x1440 (1440p)"
        ])
        params_layout.addWidget(self.timeline_resolution_combo, 2, 1)

        layout.addWidget(params_group)

        # Slate Appearance Group
        slate_group = QGroupBox("🎨 Slate Appearance")
        slate_layout = QGridLayout(slate_group)
        slate_layout.setColumnStretch(1, 1)  # Make second column expandable

        # Row 0: Slate Label Preset
        slate_layout.addWidget(QLabel("Slate Label:"), 0, 0)
        self.slate_label_combo = QComboBox()
        self.slate_label_combo.addItem("GAP", "gap")
        self.slate_label_combo.addItem("Nothing of Interest", "nothing_of_interest")
        self.slate_label_combo.addItem("Motion Gap", "motion_gap")
        self.slate_label_combo.addItem("Gap in Chronology", "chronology_gap")
        self.slate_label_combo.addItem("Custom...", "custom")
        self.slate_label_combo.setToolTip(
            "<b>Choose the text label displayed on gap slates.</b><br><br>"
            "Select 'Custom...' to enter your own text."
        )
        self.slate_label_combo.currentIndexChanged.connect(self._toggle_custom_slate_label)
        slate_layout.addWidget(self.slate_label_combo, 0, 1)

        # Row 1: Custom Slate Label Input (hidden by default)
        slate_layout.addWidget(QLabel("Custom Label:"), 1, 0)
        self.slate_label_custom_input = QLineEdit()
        self.slate_label_custom_input.setPlaceholderText("Enter custom label text...")
        self.slate_label_custom_input.setEnabled(False)
        self.slate_label_custom_input.setMaxLength(50)
        self.slate_label_custom_input.setToolTip(
            "Enter your custom slate label text.<br>"
            "Example: 'No Activity', 'Coverage Gap', etc.<br>"
            "Maximum 50 characters."
        )
        slate_layout.addWidget(self.slate_label_custom_input, 1, 1)

        # Row 2: Time Format
        slate_layout.addWidget(QLabel("Time Format:"), 2, 0)
        self.slate_time_format_combo = QComboBox()
        self.slate_time_format_combo.addItem("HH:MM:SS only", "time_only")
        self.slate_time_format_combo.addItem("Full Date & Time", "date_time")
        self.slate_time_format_combo.addItem("Multiline Duration", "duration_multiline")
        self.slate_time_format_combo.setToolTip(
            "<b>Choose how times are displayed on gap slates.</b><br><br>"
            "<b>HH:MM:SS only:</b><br>"
            "19:35:00 to 19:40:15<br>"
            "Duration: 5m 15s<br><br>"
            "<b>Full Date & Time:</b><br>"
            "Tue 21 May 19:35:00 → Tue 21 May 19:40:15  (Δ 5m 15s)<br><br>"
            "<b>Multiline Duration:</b><br>"
            "19:35:00 to 19:40:15<br>"
            "Total Duration = 5 min 15 sec"
        )
        slate_layout.addWidget(self.slate_time_format_combo, 2, 1)

        # Row 3: Preview info
        slate_preview_label = QLabel(
            "ℹ️  Preview updates when rendering starts"
        )
        slate_preview_label.setWordWrap(True)
        slate_preview_label.setStyleSheet(
            "color: #6c757d; font-size: 10px; padding: 4px 8px; "
            "background-color: #f8f9fa; border-radius: 3px; margin-top: 4px;"
        )
        slate_layout.addWidget(slate_preview_label, 3, 0, 1, 2)

        layout.addWidget(slate_group)

        # Performance Settings Group (Three-Tier System)
        perf_group = QGroupBox("⚡ Performance Settings")
        perf_layout = QVBoxLayout(perf_group)

        # Hardware Decode checkbox
        self.timeline_hwdecode_check = QCheckBox("Use GPU Hardware Decode (NVDEC)")
        self.timeline_hwdecode_check.setToolTip(
            "<b>Speeds up rendering by using GPU to decode video instead of CPU.</b><br><br>"
            "<b style='color: #ff9800;'>⚠️ Warning:</b> Increases command length. May cause errors with:<br>"
            "• More than ~200 files<br>"
            "• Long file paths (deep folder structures)<br><br>"
            "If rendering fails, disable this option."
        )
        perf_layout.addWidget(self.timeline_hwdecode_check)

        # Batch Rendering checkbox
        self.timeline_batch_check = QCheckBox("Use Batch Rendering for Large Datasets")
        self.timeline_batch_check.setToolTip(
            "<b>Automatically splits rendering into multiple passes when file count<br>"
            "or command length exceeds Windows limits.</b><br><br>"
            "Prevents '[WinError 206]' failures with large datasets.<br>"
            "Slightly slower (multiple passes) but handles unlimited files.<br><br>"
            "<b style='color: #52c41a;'>✓ Recommended:</b> Enable for investigations with 250+ files."
        )
        perf_layout.addWidget(self.timeline_batch_check)

        # Keep temp files checkbox (debugging)
        self.timeline_keep_temp_check = QCheckBox("Keep Temp Files (Debugging)")
        self.timeline_keep_temp_check.setToolTip(
            "<b>Preserve temporary batch files for manual inspection.</b><br><br>"
            "When enabled, intermediate batch files are NOT deleted after rendering.<br>"
            "Useful for debugging batch rendering issues.<br><br>"
            "<b style='color: #ff9800;'>⚠️ Warning:</b> Temp files can be large (GBs).<br>"
            "Remember to manually delete them when done!"
        )
        perf_layout.addWidget(self.timeline_keep_temp_check)

        # Auto-fallback info label
        auto_fallback_info = QLabel(
            "ℹ️  Auto-fallback: Batch mode activates automatically if command exceeds Windows limits"
        )
        auto_fallback_info.setWordWrap(True)
        auto_fallback_info.setStyleSheet(
            "color: #6c757d; font-size: 10px; padding: 4px 8px; "
            "background-color: #f8f9fa; border-radius: 3px; margin-top: 4px;"
        )
        perf_layout.addWidget(auto_fallback_info)

        layout.addWidget(perf_group)

        layout.addStretch()
        scroll_area.setWidget(settings_widget)
        main_layout.addWidget(scroll_area)

        return tab

    def _create_console_section(self) -> QGroupBox:
        """Create console log display"""
        group = QGroupBox("📋 Processing Console")
        layout = QVBoxLayout(group)

        # Console controls
        controls_layout = QHBoxLayout()
        controls_layout.addStretch()

        self.clear_console_btn = QPushButton("Clear")
        self.clear_console_btn.clicked.connect(self._clear_console)
        controls_layout.addWidget(self.clear_console_btn)

        self.export_log_btn = QPushButton("Export Log")
        self.export_log_btn.clicked.connect(self._export_log)
        controls_layout.addWidget(self.export_log_btn)

        layout.addLayout(controls_layout)

        # Console text widget
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(150)
        self.console.setMaximumHeight(200)
        self.console.setFont(QFont("Consolas", 9))
        layout.addWidget(self.console)

        # Initial message
        self._log("INFO", "Filename Parser ready. Select video files to begin.")

        return group

    # ========================================
    # EVENT HANDLERS
    # ========================================

    def _add_files(self):
        """Open file dialog to add video files"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Video Files",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.dav *.h264 *.h265 *.m4v);;All Files (*)"
        )

        if files:
            added = 0
            for file_path in files:
                path = Path(file_path)
                if path not in self.selected_files:
                    self.selected_files.append(path)
                    added += 1

            self._rebuild_file_tree()
            self._update_file_list()
            self._log("INFO", f"Added {added} file(s)")

    def _add_folder(self):
        """Open folder dialog and add all video files"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder with Video Files"
        )

        if folder:
            folder_path = Path(folder)
            video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.dav', '.h264', '.h265', '.m4v'}

            added = 0
            for file_path in folder_path.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
                        added += 1

            self._rebuild_file_tree()
            self._update_file_list()
            self._log("INFO", f"Added {added} file(s) from folder")

    def _clear_files(self):
        """Clear all selected files"""
        self.selected_files.clear()
        self.file_tree.clear()
        self._update_file_list()
        self.stats_group.setVisible(False)
        self._log("INFO", "File list cleared")

    def _rebuild_file_tree(self):
        """Rebuild file tree from selected_files with hierarchical folder structure"""
        self.file_tree.clear()

        if not self.selected_files:
            return

        # Find common root path
        if len(self.selected_files) == 1:
            common_root = self.selected_files[0].parent
        else:
            # Find common ancestor
            all_parts = [list(f.parents)[::-1] for f in self.selected_files]
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

        for file_path in sorted(self.selected_files):
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
                        self.file_tree.addTopLevelItem(folder_item)
                    else:
                        current_parent.addChild(folder_item)

                    folder_items[partial_path] = folder_item

                current_parent = folder_items[partial_path]

            # Add file item
            file_item = QTreeWidgetItem()
            file_item.setText(0, f"🎥 {file_path.name}")
            file_item.setData(0, Qt.UserRole, str(file_path))

            if current_parent is None:
                self.file_tree.addTopLevelItem(file_item)
            else:
                current_parent.addChild(file_item)

        # Expand all folders by default
        self.file_tree.expandAll()

    def _update_file_list(self):
        """Update file count label and button states"""
        count = len(self.selected_files)

        if count == 0:
            self.file_count_label.setText("No files selected")
            self.clear_btn.setEnabled(False)
            self.process_btn.setEnabled(False)
            self.detect_fps_btn.setEnabled(False)
        else:
            self.file_count_label.setText(f"{count} file{'s' if count != 1 else ''} selected")
            self.clear_btn.setEnabled(True)
            self.process_btn.setEnabled(not self.operation_active)
            self.detect_fps_btn.setEnabled(not self.operation_active)

    def _update_pattern_preview(self):
        """Update pattern preview when selection changes"""
        current_data = self.pattern_combo.currentData()

        if current_data is None:
            return  # Separator or category header

        # Pattern examples (simplified)
        examples = {
            "auto": ("Auto-detect best pattern", "Multiple patterns tested", "✓ Automatic selection"),
            "embedded_time": ("_20240115_143025_", "_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_", "✓ 14:30:25 (2024-01-15)"),
            "dahua_nvr_standard": ("CH01-20171215143022.DAV", "CH(\d+).*(\d{14})", "✓ 14:30:22 (2017-12-15)"),
            "hhmmss_compact": ("video_161048.mp4", "(\d{2})(\d{2})(\d{2})(?!\d)", "✓ 16:10:48"),
        }

        example, regex, match = examples.get(current_data, ("Example", "Regex", "Match"))

        self.pattern_example_label.setText(f"Example: {example}")
        self.pattern_regex_label.setText(f"Regex: {regex}")
        self.pattern_match_label.setText(match)

    def _toggle_fps_settings(self, checked):
        """Toggle manual FPS controls"""
        self.manual_fps_combo.setEnabled(not checked)
        self.fps_method_combo.setEnabled(checked)  # Enable method selection when detecting

        # If unchecked, we're using override - change combo to "override" mode
        if not checked:
            # Visually indicate override mode (optional - just for UX)
            self.fps_method_combo.setToolTip("Using manual FPS override")

    def _toggle_offset_settings(self, checked):
        """Toggle time offset controls"""
        self.offset_behind.setEnabled(checked)
        self.offset_ahead.setEnabled(checked)
        self.offset_hours.setEnabled(checked)
        self.offset_minutes.setEnabled(checked)
        self.offset_seconds.setEnabled(checked)

    def _toggle_output_structure(self, checked):
        """Toggle base directory controls"""
        self.base_dir_input.setEnabled(checked)
        self.browse_btn.setEnabled(checked)

    def _toggle_custom_slate_label(self, index):
        """Toggle custom slate label input based on dropdown selection"""
        selected_data = self.slate_label_combo.currentData()
        is_custom = (selected_data == "custom")
        self.slate_label_custom_input.setEnabled(is_custom)

        # Auto-focus the input when custom is selected
        if is_custom:
            self.slate_label_custom_input.setFocus()

    def _browse_base_directory(self):
        """Browse for base output directory"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Base Output Directory"
        )

        if folder:
            self.base_dir_input.setText(folder)
            self.settings.base_output_directory = Path(folder)

    def _open_pattern_generator(self):
        """Open pattern generator dialog"""
        self._log("INFO", "Pattern generator dialog (not yet implemented)")
        # TODO: Implement pattern generator dialog

    def _detect_frame_rates(self):
        """Detect frame rates for selected files"""
        if not self.selected_files:
            return

        self._log("INFO", "Starting frame rate detection...")
        self.detect_fps_btn.setEnabled(False)

        # TODO: Implement actual frame rate detection
        QTimer.singleShot(1000, lambda: self._log("INFO", "Frame rate detection complete (placeholder)"))
        QTimer.singleShot(1000, lambda: self.detect_fps_btn.setEnabled(True))

    def _start_processing(self):
        """Start filename parsing workflow"""
        if not self.selected_files:
            return

        # Build settings
        self._build_settings()

        # Validate files
        validation_result = self.controller.validate_files(self.selected_files)
        if not validation_result.success:
            self._log("ERROR", f"Validation failed: {validation_result.error.user_message}")
            return

        # Start workflow
        self.operation_active = True
        self.process_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.stats_group.setVisible(False)

        self._log("INFO", f"Starting batch processing of {len(self.selected_files)} files...")

        result = self.controller.start_processing_workflow(
            self.selected_files,
            self.settings
        )

        if result.success:
            self.current_worker = result.value
            self.current_worker.progress_update.connect(self._on_progress)
            self.current_worker.result_ready.connect(self._on_complete)
            self.status_message.emit("Processing video files...")
        else:
            self._log("ERROR", f"Failed to start: {result.error.user_message}")
            self._reset_ui()

    def _cancel_processing(self):
        """Cancel current processing operation"""
        self._log("WARNING", "Cancelling processing...")
        self.controller.cancel_processing()
        self._reset_ui()
        self.status_message.emit("Processing cancelled")

    def _build_settings(self):
        """Build settings from UI"""
        # Pattern
        pattern_data = self.pattern_combo.currentData()
        self.settings.pattern_id = None if pattern_data == "auto" else pattern_data

        # FPS
        self.settings.detect_fps = self.auto_detect_fps.isChecked()

        if self.settings.detect_fps:
            # Auto-detection enabled - use selected method
            self.settings.fps_detection_method = self.fps_method_combo.currentData()
            self.settings.fps_override = None
        else:
            # Manual override
            self.settings.fps_detection_method = "override"
            fps_text = self.manual_fps_combo.currentText()
            self.settings.fps_override = float(fps_text.split()[0])

        # Time offset
        self.settings.enable_time_offset = self.enable_offset.isChecked()
        if self.settings.enable_time_offset:
            self.settings.time_offset_direction = "behind" if self.offset_behind.isChecked() else "ahead"
            self.settings.time_offset_hours = self.offset_hours.value()
            self.settings.time_offset_minutes = self.offset_minutes.value()
            self.settings.time_offset_seconds = self.offset_seconds.value()

        # Output
        self.settings.use_mirrored_structure = self.output_mirrored.isChecked()
        # Note: write_metadata and export_csv are set explicitly by action buttons

    def _on_progress(self, percentage: int, message: str):
        """Handle progress updates from worker"""
        self.progress_bar.setValue(percentage)
        self.progress_label.setText(message)

    def _on_complete(self, result: Result):
        """Handle completion from worker"""
        self.operation_active = False

        if result.success:
            stats = result.value
            self.last_stats = stats

            # Store complete video metadata for timeline rendering
            if hasattr(stats, 'results'):
                # Build VideoMetadata objects from ProcessingResult objects
                self.video_metadata_list = []
                for item in stats.results:
                    if item.success:  # Only include successful parses
                        metadata = VideoMetadata(
                            file_path=Path(item.source_file),
                            filename=item.filename,
                            smpte_timecode=item.smpte_timecode or '00:00:00:00',
                            start_time=item.start_time_iso,
                            end_time=item.end_time_iso,
                            frame_rate=item.frame_rate or 30.0,
                            duration_seconds=item.duration_seconds,
                            camera_path=item.camera_id or 'Unknown',
                            width=item.width,
                            height=item.height,
                            codec=item.codec or 'h264',
                            pixel_format=item.pixel_format or 'yuv420p',
                            video_bitrate=item.video_bitrate or 0,
                        )
                        self.video_metadata_list.append(metadata)
            else:
                self.video_metadata_list = []

            self._log("SUCCESS", f"Processing complete: {stats.successful} successful, {stats.failed} failed")

            # Update statistics display
            self.stat_total_label.setText(str(stats.total_files))
            self.stat_success_label.setText(str(stats.successful))
            self.stat_failed_label.setText(str(stats.failed))
            self.stat_speed_label.setText(f"{stats.files_per_second:.2f}")
            self.stats_group.setVisible(True)

            # Enable export buttons now that parsing is complete
            self.export_csv_btn.setEnabled(True)
            self.export_json_btn.setEnabled(True)
            self.copy_with_smpte_btn.setEnabled(True)

            # Enable timeline rendering if we have metadata and output directory selected
            if self.video_metadata_list and self.timeline_output_dir_input.text() != "(Not selected)":
                self.timeline_render_btn.setEnabled(True)
                self._log("INFO", f"✓ Timeline rendering now available with {len(self.video_metadata_list)} videos - select output directory and click 'Generate Timeline Video'")

            self.status_message.emit(f"Parsing complete: {stats.successful}/{stats.total_files} successful")
        else:
            self._log("ERROR", f"Parsing failed: {result.error.user_message}")
            self.status_message.emit("Parsing failed")

        self._reset_ui()

    def _reset_ui(self):
        """Reset UI to ready state"""
        self.operation_active = False
        self.current_worker = None
        self.process_btn.setEnabled(len(self.selected_files) > 0)
        self.cancel_btn.setEnabled(False)

        QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))
        QTimer.singleShot(2000, lambda: self.progress_label.setVisible(False))

    def _log(self, level: str, message: str):
        """Log message to console"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")

        colors = {
            "INFO": "#4B9CD3",
            "SUCCESS": "#52c41a",
            "WARNING": "#faad14",
            "ERROR": "#ff4d4f"
        }

        color = colors.get(level, "#e8e8e8")
        formatted = f'<span style="color: #6b6b6b;">{timestamp}</span> <span style="color: {color}; font-weight: bold;">[{level}]</span> {message}'

        self.console.append(formatted)

        # Also emit to main window
        self.log_message.emit(f"[FilenameParser] {message}")

    def _clear_console(self):
        """Clear console log"""
        self.console.clear()
        self._log("INFO", "Console cleared")

    def _export_log(self):
        """Export console log to file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Console Log",
            "filename_parser_log.txt",
            "Text Files (*.txt);;All Files (*)"
        )

        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write(self.console.toPlainText())
                self._log("SUCCESS", f"Log exported to {file_path}")
            except Exception as e:
                self._log("ERROR", f"Failed to export log: {e}")

    def _export_csv(self):
        """Export parsing results to CSV"""
        if not self.last_stats or not self.last_stats.results:
            self._log("WARNING", "No parsing results available to export")
            return

        # Ask user for save location
        from datetime import datetime
        default_filename = f"filename_parser_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Results to CSV",
            default_filename,
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        self._log("INFO", f"Exporting {len(self.last_stats.results)} results to CSV...")

        try:
            # Use CSV export service to export results
            from filename_parser.services.csv_export_service import CSVExportService
            csv_service = CSVExportService()

            # Convert results to dictionaries
            result_dicts = [r.to_dict() for r in self.last_stats.results]

            # Export with metadata
            success, output_path = csv_service.export_results(
                result_dicts,
                file_path,
                include_metadata=True
            )

            if success:
                self._log("SUCCESS", f"CSV exported successfully to: {output_path}")
                self.status_message.emit(f"CSV exported: {len(self.last_stats.results)} files")
            else:
                self._log("ERROR", f"CSV export failed: {output_path}")
                self.status_message.emit("CSV export failed")

        except Exception as e:
            self._log("ERROR", f"Error exporting CSV: {e}")
            self.status_message.emit("CSV export error")

    def _export_json_timeline(self):
        """Export timeline data as GPT-5-compatible JSON"""
        if not self.video_metadata_list:
            self._log("WARNING", "No video metadata available to export")
            QMessageBox.warning(
                self,
                "No Data",
                "Please parse filenames first to generate timeline data."
            )
            return

        # Ask user for save location
        from datetime import datetime
        default_filename = f"timeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Timeline JSON",
            default_filename,
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        self._log("INFO", f"Exporting timeline with {len(self.video_metadata_list)} videos to JSON...")

        try:
            # Export using JSON timeline service
            result = self.json_export_service.export_timeline(
                self.video_metadata_list,
                Path(file_path)
            )

            if result.success:
                self._log("SUCCESS", f"Timeline JSON exported successfully to: {file_path}")
                self.status_message.emit(f"Timeline JSON exported: {len(self.video_metadata_list)} videos")

                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Timeline JSON exported successfully!\n\n"
                    f"Location: {file_path}\n"
                    f"Videos: {len(self.video_metadata_list)}\n\n"
                    f"This JSON can be:\n"
                    f"• Reviewed for timeline accuracy\n"
                    f"• Edited manually if needed\n"
                    f"• Used with GPT-5 timeline builder"
                )
            else:
                self._log("ERROR", f"JSON export failed: {result.error.user_message}")
                self.status_message.emit("JSON export failed")

                QMessageBox.critical(
                    self,
                    "Export Failed",
                    f"Failed to export timeline JSON:\n{result.error.user_message}"
                )

        except Exception as e:
            logger.error(f"Error exporting JSON timeline: {e}", exc_info=True)
            self._log("ERROR", f"Error exporting JSON: {e}")
            self.status_message.emit("JSON export error")

            QMessageBox.critical(
                self,
                "Export Error",
                f"An unexpected error occurred:\n{str(e)}"
            )

    def _copy_with_smpte(self):
        """Copy files with embedded SMPTE metadata"""
        if not self.last_stats or not self.last_stats.results:
            self._log("WARNING", "No parsing results available to process")
            return

        if not self.selected_files:
            self._log("WARNING", "No files selected")
            return

        # Ask user for output directory
        from PySide6.QtWidgets import QFileDialog
        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory for Copied Files",
            "",
            QFileDialog.Option.ShowDirsOnly
        )

        if not output_dir:
            return

        self._log("INFO", f"Starting copy with SMPTE metadata to: {output_dir}")
        self._log("INFO", f"Processing {len(self.selected_files)} files...")

        # Build settings with write_metadata enabled
        self._build_settings()
        self.settings.write_metadata = True
        self.settings.base_output_directory = Path(output_dir)

        # Disable buttons during processing
        self.process_btn.setEnabled(False)
        self.export_csv_btn.setEnabled(False)
        self.copy_with_smpte_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Copying files with SMPTE metadata...")

        # Start workflow using controller (controller creates and manages worker)
        result = self.controller.start_processing_workflow(
            self.selected_files,
            self.settings  # Has write_metadata=True and base_output_directory
        )

        if result.success:
            self.operation_active = True
            self.current_worker = result.value
            self.current_worker.progress_update.connect(self._on_progress)
            self.current_worker.result_ready.connect(self._on_copy_complete)
            self.status_message.emit("Copying files with SMPTE metadata...")
        else:
            self._log("ERROR", f"Failed to start copy operation: {result.error.user_message}")
            self._reset_ui()

    def _on_copy_complete(self, result: Result):
        """Handle completion of copy with SMPTE operation"""
        self.operation_active = False

        if result.success:
            stats = result.value

            self._log("SUCCESS", f"Copy complete: {stats.successful} files processed, {stats.failed} failed")
            self._log("INFO", f"Files written to: {self.settings.base_output_directory}")

            # Update statistics display
            self.stat_total_label.setText(str(stats.total_files))
            self.stat_success_label.setText(str(stats.successful))
            self.stat_failed_label.setText(str(stats.failed))
            self.stat_speed_label.setText(f"{stats.files_per_second:.2f}")

            self.status_message.emit(f"Copy complete: {stats.successful}/{stats.total_files} successful")
        else:
            self._log("ERROR", f"Copy failed: {result.error.user_message}")
            self.status_message.emit("Copy with SMPTE failed")

        # Re-enable buttons
        self._reset_ui()

        # Keep export buttons enabled since we still have results
        if self.last_stats:
            self.export_csv_btn.setEnabled(True)
            self.copy_with_smpte_btn.setEnabled(True)

    # ========================================
    # TIMELINE RENDERING EVENT HANDLERS
    # ========================================

    def _browse_timeline_output(self):
        """Browse for timeline output directory"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory for Timeline Video",
            "",
            QFileDialog.ShowDirsOnly
        )

        if directory:
            self.timeline_output_dir_input.setText(directory)
            self.timeline_output_dir_input.setStyleSheet("""
                QLabel {
                    background-color: #1e1e1e;
                    border: 1px solid #3a3a3a;
                    border-radius: 4px;
                    padding: 8px;
                    color: #e8e8e8;
                }
            """)

            # Enable render button if we have video metadata
            if self.video_metadata_list:
                self.timeline_render_btn.setEnabled(True)

    def _start_timeline_rendering(self):
        """Start timeline video rendering workflow"""
        try:
            # Validate output directory
            output_dir = self.timeline_output_dir_input.text()
            if output_dir == "(Not selected)" or not Path(output_dir).exists():
                QMessageBox.warning(
                    self,
                    "Output Directory Required",
                    "Please select an output directory for the timeline video."
                )
                return

            # Validate we have video metadata
            if not self.video_metadata_list:
                QMessageBox.warning(
                    self,
                    "Parse Files First",
                    "Please parse filenames first to extract SMPTE timecodes and metadata before generating timeline."
                )
                return

            # Extract resolution from combo box
            resolution_text = self.timeline_resolution_combo.currentText()
            if "1920x1080" in resolution_text:
                resolution = (1920, 1080)
            elif "1280x720" in resolution_text:
                resolution = (1280, 720)
            elif "3840x2160" in resolution_text:
                resolution = (3840, 2160)
            elif "2560x1440" in resolution_text:
                resolution = (2560, 1440)
            else:
                resolution = (1920, 1080)

            # Build RenderSettings (including performance settings and slate customization)
            self.timeline_settings = RenderSettings(
                output_resolution=resolution,
                output_fps=self.timeline_fps_spin.value(),
                output_directory=Path(output_dir),
                output_filename=self.timeline_filename_input.text(),
                slate_label_preset=self.slate_label_combo.currentData(),
                slate_label_custom=self.slate_label_custom_input.text(),
                slate_time_format=self.slate_time_format_combo.currentData(),
                use_hardware_decode=self.timeline_hwdecode_check.isChecked(),
                use_batch_rendering=self.timeline_batch_check.isChecked(),
                keep_batch_temp_files=self.timeline_keep_temp_check.isChecked()
            )

            self._log("INFO", "Starting timeline rendering workflow...")
            self._log("INFO", f"Output: {output_dir}/{self.timeline_filename_input.text()}")
            self._log("INFO", f"Resolution: {resolution[0]}x{resolution[1]} @ {self.timeline_fps_spin.value()}fps")
            self._log("INFO", f"Processing {len(self.video_metadata_list)} videos")
            if self.timeline_hwdecode_check.isChecked():
                self._log("INFO", "Hardware decode (NVDEC) enabled")
            if self.timeline_batch_check.isChecked():
                self._log("INFO", "Batch rendering enabled (manual)")

            # NEW: GPT-5 Approach - Pass video metadata directly to renderer
            # No validation, no timeline calculation here - FFmpegTimelineBuilder handles it all!
            self.progress_bar.setVisible(True)
            self.progress_label.setVisible(True)
            self.progress_bar.setValue(10)
            self.progress_label.setText("Starting timeline render...")

            # Start rendering with video metadata list (bypassing old timeline calculation)
            render_result = self.timeline_controller.start_rendering(
                videos=self.video_metadata_list,  # Pass metadata directly
                settings=self.timeline_settings
            )

            if not render_result.success:
                QMessageBox.critical(
                    self,
                    "Render Start Failed",
                    f"Failed to start rendering:\n{render_result.error.user_message}"
                )
                self.progress_bar.setVisible(False)
                self.progress_label.setVisible(False)
                return

            # Connect worker signals
            self.timeline_worker = render_result.value
            self.timeline_worker.progress_update.connect(self._on_timeline_progress)
            self.timeline_worker.result_ready.connect(self._on_timeline_complete)

            # Update UI state
            self.timeline_render_btn.setEnabled(False)
            self.timeline_cancel_btn.setEnabled(True)

            self._log("INFO", "Timeline rendering in progress...")

        except Exception as e:
            logger.error(f"Timeline rendering error: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Unexpected Error",
                f"An unexpected error occurred:\n{str(e)}"
            )
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)

    def _cancel_timeline_rendering(self):
        """Cancel ongoing timeline rendering"""
        if self.timeline_worker and self.timeline_worker.isRunning():
            self._log("WARNING", "Cancelling timeline render...")
            self.timeline_worker.cancel()
            self.timeline_cancel_btn.setEnabled(False)

    def _on_timeline_progress(self, percentage: int, message: str):
        """Handle timeline rendering progress updates"""
        self.progress_bar.setValue(percentage)
        self.progress_label.setText(message)

    def _on_timeline_complete(self, result: Result):
        """Handle timeline rendering completion"""
        # Reset UI state
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.timeline_render_btn.setEnabled(True)
        self.timeline_cancel_btn.setEnabled(False)

        if result.success:
            output_path = result.value
            self._log("SUCCESS", f"✓ Timeline video generated successfully!")
            self._log("SUCCESS", f"  Output: {output_path}")

            QMessageBox.information(
                self,
                "Timeline Complete! 🎉",
                f"Timeline video generated successfully!\n\n"
                f"Location: {output_path}\n\n"
                f"The video includes:\n"
                f"• Chronological video segments\n"
                f"• Gap slates showing missing coverage\n"
                f"• SMPTE timecode information"
            )
        else:
            self._log("ERROR", f"✗ Timeline rendering failed: {result.error.user_message}")

            # Check if this is an audio codec error
            error_context = result.error.context if hasattr(result.error, 'context') else {}
            is_audio_error = error_context.get('is_audio_error', False)

            if is_audio_error:
                # Audio codec incompatibility detected - offer solutions
                self._handle_audio_codec_error(error_context)
            else:
                # Generic error
                QMessageBox.critical(
                    self,
                    "Rendering Failed",
                    f"Timeline rendering failed:\n{result.error.user_message}"
                )

    def _handle_audio_codec_error(self, error_context: dict):
        """Handle audio codec incompatibility with user-friendly dialog"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QRadioButton, QDialogButtonBox, QTextEdit

        # Create custom dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Audio Codec Incompatibility Detected")
        dialog.setMinimumWidth(600)
        layout = QVBoxLayout(dialog)

        # Explanation
        explanation = QLabel(
            "⚠️ The audio codec in your videos (likely pcm_mulaw or pcm_alaw) is not compatible "
            "with MP4 containers.\n\n"
            "This is common with CCTV footage. Choose how to handle the audio:"
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        # Options
        self.audio_option_drop = QRadioButton(
            "🔇 Drop Audio Track (Recommended for silent CCTV footage)\n"
            "   Remove audio entirely - fastest option"
        )
        self.audio_option_drop.setChecked(True)  # Default
        layout.addWidget(self.audio_option_drop)

        self.audio_option_transcode = QRadioButton(
            "🔊 Transcode Audio to AAC (If audio is important)\n"
            "   Convert audio to MP4-compatible format - slower but preserves audio"
        )
        layout.addWidget(self.audio_option_transcode)

        # Error details (collapsible)
        details_label = QLabel("\n<b>Technical Details:</b>")
        layout.addWidget(details_label)

        details_text = QTextEdit()
        details_text.setPlainText(error_context.get('stderr', 'No error details available'))
        details_text.setReadOnly(True)
        details_text.setMaximumHeight(150)
        layout.addWidget(details_text)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        # Show dialog
        if dialog.exec() == QDialog.Accepted:
            # Determine selected option
            if self.audio_option_drop.isChecked():
                audio_mode = "drop"
                self._log("INFO", "User selected: Drop audio track")
            else:
                audio_mode = "transcode"
                self._log("INFO", "User selected: Transcode audio to AAC")

            # Retry rendering with selected audio handling
            self._retry_timeline_with_audio_mode(audio_mode)
        else:
            self._log("INFO", "User cancelled audio handling selection")

    def _retry_timeline_with_audio_mode(self, audio_mode: str):
        """Retry timeline rendering with specified audio handling mode"""
        try:
            # Verify we have a stored timeline
            if not hasattr(self, 'last_timeline') or self.last_timeline is None:
                QMessageBox.warning(
                    self,
                    "Retry Not Possible",
                    "Timeline data not available for retry. Please start rendering again."
                )
                return

            self._log("INFO", f"Retrying timeline render with audio mode: {audio_mode}")

            # Update settings with selected audio mode
            self.timeline_settings.audio_handling = audio_mode

            # Show progress bar again
            self.progress_bar.setVisible(True)
            self.progress_label.setVisible(True)
            self.progress_bar.setValue(50)
            self.progress_label.setText(f"Retrying with audio mode: {audio_mode}...")

            # Start rendering with updated settings
            render_result = self.timeline_controller.start_rendering(
                timeline=self.last_timeline,
                settings=self.timeline_settings
            )

            if not render_result.success:
                QMessageBox.critical(
                    self,
                    "Retry Failed",
                    f"Failed to restart rendering:\n{render_result.error.user_message}"
                )
                self.progress_bar.setVisible(False)
                self.progress_label.setVisible(False)
                return

            # Connect worker signals
            self.timeline_worker = render_result.value
            self.timeline_worker.progress_update.connect(self._on_timeline_progress)
            self.timeline_worker.result_ready.connect(self._on_timeline_complete)

            # Update UI state
            self.timeline_render_btn.setEnabled(False)
            self.timeline_cancel_btn.setEnabled(True)

            self._log("INFO", f"Timeline rendering resumed with {audio_mode} audio handling...")

        except Exception as e:
            logger.error(f"Timeline retry error: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Retry Error",
                f"An error occurred while retrying:\n{str(e)}"
            )
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)

    def _connect_signals(self):
        """Connect internal signals"""
        # Pattern preview updates
        self._update_pattern_preview()

    def cleanup(self):
        """Cleanup resources when tab is closed"""
        if self.controller:
            self.controller.cleanup_resources()
