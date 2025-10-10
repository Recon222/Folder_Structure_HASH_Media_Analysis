#!/usr/bin/env python3
"""
Media Analysis Tab - UI for media file metadata extraction and analysis

Combines professional UI patterns from FilenameParserTab with comprehensive
media analysis functionality for FFprobe and ExifTool operations.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QCheckBox, QFileDialog, QProgressBar, QSplitter,
    QComboBox, QSpinBox, QDoubleSpinBox, QMessageBox, QScrollArea,
    QGridLayout, QTabWidget, QTreeWidget, QTreeWidgetItem, QSizePolicy
)
from PySide6.QtGui import QFont

# Relative imports within media_analysis module
from ..controllers.media_analysis_controller import MediaAnalysisController
from ..core.media_analysis_models import (
    MediaAnalysisSettings, MediaAnalysisResult, MetadataFieldGroup,
    FileReferenceFormat
)
from ..exiftool.exiftool_models import (
    ExifToolSettings, ExifToolAnalysisResult, GPSPrecisionLevel
)

# Core application imports
from core.models import FormData
from core.services.success_message_data import MediaAnalysisOperationData, ExifToolOperationData
from core.services import get_service
from core.services.interfaces import IMediaAnalysisSuccessService
from core.logger import logger
from core.exceptions import UIError, ErrorSeverity
from core.error_handler import handle_error

# UI components
from ui.components import LogConsole
from ui.dialogs.success_dialog import SuccessDialog
from .components.geo import GeoVisualizationWidget


class MediaAnalysisTab(QWidget):
    """Tab for media file analysis operations with professional UI"""

    # Signals
    log_message = Signal(str)
    status_message = Signal(str)

    def __init__(self, form_data: Optional[FormData] = None, parent=None):
        """
        Initialize the Media Analysis tab

        Args:
            form_data: Optional form data for report generation
            parent: Parent widget
        """
        super().__init__(parent)

        # Controller for orchestration
        self.controller = MediaAnalysisController()

        # Form data reference (optional)
        self.form_data = form_data

        # State management
        self.operation_active = False
        self.current_worker = None
        self.last_results: Optional[MediaAnalysisResult] = None
        self.last_exiftool_results: Optional[ExifToolAnalysisResult] = None
        self.selected_paths: List[Path] = []
        self.current_tool = "ffprobe"  # Track which tool is active
        self.geo_widget: Optional[GeoVisualizationWidget] = None

        # Settings
        self.analysis_settings = self._load_settings()

        # Get success builder through dependency injection
        self.success_builder = get_service(IMediaAnalysisSuccessService)

        self._create_ui()
        self._connect_signals()
        self._check_ffprobe_status()

    def _create_ui(self):
        """Create the tab UI with two-column layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # Main content splitter
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)

        # Left panel - File selection with tree view
        left_panel = self._create_file_panel()
        main_splitter.addWidget(left_panel)

        # Right panel - Settings and progress
        right_panel = self._create_settings_panel()
        main_splitter.addWidget(right_panel)

        # Set splitter proportions (45/55)
        main_splitter.setSizes([450, 550])
        layout.addWidget(main_splitter)

        # Console section
        console_group = self._create_console_section()
        layout.addWidget(console_group)

    def _create_file_panel(self) -> QGroupBox:
        """Create left panel for file selection with hierarchical tree view"""
        panel = QGroupBox("📁 Media Files to Analyze")
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
        self.file_tree.setHeaderLabels(["Media Files"])
        self.file_tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.file_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.file_tree.setMinimumHeight(200)
        self.file_tree.setAlternatingRowColors(True)
        layout.addWidget(self.file_tree)

        # File count label
        self.file_count_label = QLabel("No files selected")
        self.file_count_label.setStyleSheet("color: #6c757d;")
        layout.addWidget(self.file_count_label)

        # Statistics section (hidden initially, shown after processing)
        self.stats_group = self._create_stats_section()
        self.stats_group.setVisible(False)
        layout.addWidget(self.stats_group)

        return panel

    def _create_stats_section(self) -> QGroupBox:
        """Create statistics display section with large styled numbers"""
        group = QGroupBox("📊 Processing Statistics")
        layout = QGridLayout(group)

        # Stat labels with Carolina Blue theme
        self.stat_total_label = QLabel("0")
        self.stat_total_label.setStyleSheet("color: #4B9CD3; font-size: 24px; font-weight: bold;")

        self.stat_success_label = QLabel("0")
        self.stat_success_label.setStyleSheet("color: #52c41a; font-size: 24px; font-weight: bold;")

        self.stat_failed_label = QLabel("0")
        self.stat_failed_label.setStyleSheet("color: #ff4d4f; font-size: 24px; font-weight: bold;")

        self.stat_speed_label = QLabel("0.0")
        self.stat_speed_label.setStyleSheet("color: #4B9CD3; font-size: 24px; font-weight: bold;")

        # Layout in grid - 2x2
        layout.addWidget(self.stat_total_label, 0, 0, Qt.AlignCenter)
        layout.addWidget(QLabel("Total Files"), 1, 0, Qt.AlignCenter)

        layout.addWidget(self.stat_success_label, 0, 1, Qt.AlignCenter)
        layout.addWidget(QLabel("Successful"), 1, 1, Qt.AlignCenter)

        layout.addWidget(self.stat_failed_label, 2, 0, Qt.AlignCenter)
        layout.addWidget(QLabel("Failed"), 3, 0, Qt.AlignCenter)

        layout.addWidget(self.stat_speed_label, 2, 1, Qt.AlignCenter)
        layout.addWidget(QLabel("Files/Sec"), 3, 1, Qt.AlignCenter)

        return group

    def _create_settings_panel(self) -> QGroupBox:
        """Create right panel for analysis settings with tab-based layout"""
        panel = QGroupBox("⚙️ Analysis Settings")
        main_layout = QVBoxLayout(panel)
        main_layout.setSpacing(8)

        # Create tab widget for FFprobe and ExifTool
        self.tool_tabs = QTabWidget()

        # Tab 1: FFprobe Analysis
        ffprobe_tab = self._create_ffprobe_settings_tab()
        self.tool_tabs.addTab(ffprobe_tab, "🔍 FFprobe Analysis")

        # Tab 2: ExifTool/GPS
        exiftool_tab = self._create_exiftool_settings_tab()
        self.tool_tabs.addTab(exiftool_tab, "📸 ExifTool/GPS")

        # Connect tab change signal
        self.tool_tabs.currentChanged.connect(self._on_tool_tab_changed)

        main_layout.addWidget(self.tool_tabs)

        # Shared progress bar (below tabs)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMinimumHeight(28)
        main_layout.addWidget(self.progress_bar)

        # Progress label
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setStyleSheet("color: #6c757d; font-size: 10px;")
        main_layout.addWidget(self.progress_label)

        # Action buttons container (changes based on active tab)
        self.action_button_container = QWidget()
        self.action_button_layout = QVBoxLayout(self.action_button_container)
        self.action_button_layout.setContentsMargins(0, 10, 0, 0)
        main_layout.addWidget(self.action_button_container)

        # Create button sets for each tab
        self._create_ffprobe_buttons()
        self._create_exiftool_buttons()

        # Show FFprobe buttons by default
        self._show_ffprobe_buttons()

        return panel

    def _create_ffprobe_settings_tab(self) -> QWidget:
        """Create FFprobe settings tab"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        # Create scrollable area for settings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        # Container widget for scroll area
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)

        # Metadata field groups
        self.field_groups = {}

        # General fields
        general_group = self._create_field_group(
            "General Information",
            ["Format", "Duration", "File Size", "Bitrate", "Creation Date"],
            "general"
        )
        layout.addWidget(general_group)

        # Video fields
        video_group = self._create_field_group(
            "Video Stream",
            ["Video Codec", "Resolution", "Frame Rate", "Aspect Ratio", "Color Space"],
            "video"
        )
        layout.addWidget(video_group)

        # Audio fields
        audio_group = self._create_field_group(
            "Audio Stream",
            ["Audio Codec", "Sample Rate", "Channels", "Bit Depth"],
            "audio"
        )
        layout.addWidget(audio_group)

        # Location fields (disabled by default)
        location_group = self._create_field_group(
            "Location Data",
            ["GPS Coordinates", "Location Name"],
            "location",
            enabled_by_default=False
        )
        layout.addWidget(location_group)

        # Device fields
        device_group = self._create_field_group(
            "Device Information",
            ["Device Make", "Device Model", "Software"],
            "device"
        )
        layout.addWidget(device_group)

        # Advanced Video fields (disabled by default for performance)
        advanced_video_group = self._create_field_group(
            "Advanced Video Properties",
            ["Profile", "Level", "Pixel Format", "Sample Aspect Ratio",
             "Pixel Aspect Ratio", "Color Range", "Color Transfer", "Color Primaries"],
            "advanced_video",
            enabled_by_default=False
        )
        layout.addWidget(advanced_video_group)

        # Frame Analysis fields (disabled by default - expensive operation)
        frame_analysis_group = self._create_field_group(
            "Frame Analysis & GOP Structure",
            ["GOP Structure", "Keyframe Interval", "Frame Type Distribution",
             "I Frame Count", "P Frame Count", "B Frame Count"],
            "frame_analysis",
            enabled_by_default=False
        )
        layout.addWidget(frame_analysis_group)

        # Processing options
        options_group = QGroupBox("Processing Options")
        options_layout = QGridLayout(options_group)

        # File reference format
        options_layout.addWidget(QLabel("File Reference:"), 0, 0)
        self.path_format_combo = QComboBox()
        self.path_format_combo.addItems(["Full Path", "Parent + Name", "Name Only"])
        self.path_format_combo.setCurrentIndex(0)
        options_layout.addWidget(self.path_format_combo, 0, 1)

        # Timeout
        options_layout.addWidget(QLabel("Timeout (seconds):"), 1, 0)
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(1.0, 30.0)
        self.timeout_spin.setValue(5.0)
        self.timeout_spin.setSingleStep(0.5)
        options_layout.addWidget(self.timeout_spin, 1, 1)

        # Max workers
        options_layout.addWidget(QLabel("Parallel Workers:"), 2, 0)
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 32)
        self.workers_spin.setValue(8)
        options_layout.addWidget(self.workers_spin, 2, 1)

        # Skip non-media
        self.skip_non_media_check = QCheckBox("Skip non-media files")
        self.skip_non_media_check.setChecked(True)
        options_layout.addWidget(self.skip_non_media_check, 3, 0, 1, 2)

        layout.addWidget(options_group)
        layout.addStretch()

        # Set scroll area content
        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

        return tab

    def _create_exiftool_settings_tab(self) -> QWidget:
        """Create ExifTool settings tab"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        # Create scrollable area for settings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        # Container widget for scroll area
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)

        # ExifTool field groups
        self.exif_field_groups = {}

        # Geospatial fields
        geo_group = self._create_exif_field_group(
            "Geospatial Data",
            ["GPS Coordinates", "Altitude", "Direction", "Speed", "Satellite Info"],
            "geospatial"
        )
        layout.addWidget(geo_group)

        # Temporal fields
        temporal_group = self._create_exif_field_group(
            "Time & Date",
            ["All Dates", "SubSec Times", "Time Zones", "Clock Skew Detection"],
            "temporal"
        )
        layout.addWidget(temporal_group)

        # Device fields
        device_group = self._create_exif_field_group(
            "Device Information",
            ["Make & Model", "Serial Numbers", "Lens Info", "Firmware"],
            "device"
        )
        layout.addWidget(device_group)

        # Camera Settings
        camera_group = self._create_exif_field_group(
            "Camera Settings",
            ["Exposure", "ISO", "Aperture", "Focal Length", "Flash"],
            "camera_settings"
        )
        layout.addWidget(camera_group)

        # Processing options
        options_group = QGroupBox("ExifTool Options")
        options_layout = QGridLayout(options_group)

        # GPS Privacy
        options_layout.addWidget(QLabel("GPS Privacy:"), 0, 0)
        self.gps_privacy_combo = QComboBox()
        self.gps_privacy_combo.addItems(["Exact", "Building", "Block", "Neighborhood"])
        self.gps_privacy_combo.setCurrentIndex(0)
        options_layout.addWidget(self.gps_privacy_combo, 0, 1)

        # Extract thumbnails
        self.extract_thumbnails_check = QCheckBox("Extract embedded thumbnails")
        self.extract_thumbnails_check.setChecked(False)
        options_layout.addWidget(self.extract_thumbnails_check, 1, 0, 1, 2)

        # Include binary data
        self.include_binary_check = QCheckBox("Include binary data")
        self.include_binary_check.setChecked(False)
        options_layout.addWidget(self.include_binary_check, 2, 0, 1, 2)

        # Batch size
        options_layout.addWidget(QLabel("Batch Size:"), 3, 0)
        self.exif_batch_spin = QSpinBox()
        self.exif_batch_spin.setRange(10, 500)
        self.exif_batch_spin.setValue(100)
        options_layout.addWidget(self.exif_batch_spin, 3, 1)

        layout.addWidget(options_group)

        # Map visualization
        vis_group = QGroupBox("Visualization")
        vis_layout = QVBoxLayout(vis_group)

        self.show_map_check = QCheckBox("Show interactive map for GPS data")
        self.show_map_check.setChecked(True)
        vis_layout.addWidget(self.show_map_check)

        self.cluster_markers_check = QCheckBox("Cluster map markers")
        self.cluster_markers_check.setChecked(True)
        vis_layout.addWidget(self.cluster_markers_check)

        layout.addWidget(vis_group)
        layout.addStretch()

        # Set scroll area content
        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

        return tab

    def _create_field_group(
        self,
        title: str,
        fields: List[str],
        key: str,
        enabled_by_default: bool = True
    ) -> QGroupBox:
        """Create a group of metadata field checkboxes"""
        group = QGroupBox(title)
        group.setCheckable(True)
        group.setChecked(enabled_by_default)

        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        # Store group reference
        self.field_groups[key] = {
            'group': group,
            'fields': {}
        }

        # Create field checkboxes
        for field in fields:
            checkbox = QCheckBox(field)
            checkbox.setChecked(True)
            layout.addWidget(checkbox)

            # Store field reference
            field_key = field.lower().replace(" ", "_")
            self.field_groups[key]['fields'][field_key] = checkbox

        return group

    def _create_exif_field_group(
        self,
        title: str,
        fields: List[str],
        key: str,
        enabled_by_default: bool = True
    ) -> QGroupBox:
        """Create ExifTool field group"""
        group = QGroupBox(title)
        group.setCheckable(True)
        group.setChecked(enabled_by_default)

        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        # Store group reference
        self.exif_field_groups[key] = {
            'group': group,
            'fields': {}
        }

        # Create field checkboxes
        for field in fields:
            checkbox = QCheckBox(field)
            checkbox.setChecked(True)
            layout.addWidget(checkbox)

            # Store field reference
            field_key = field.lower().replace(" ", "_").replace("&", "and")
            self.exif_field_groups[key]['fields'][field_key] = checkbox

        return group

    def _create_ffprobe_buttons(self):
        """Create button set for FFprobe Analysis tab"""
        self.ffprobe_button_widget = QWidget()
        layout = QVBoxLayout(self.ffprobe_button_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Primary action button
        primary_layout = QHBoxLayout()

        self.ffprobe_analyze_btn = QPushButton("🔍 Analyze with FFprobe")
        self.ffprobe_analyze_btn.setEnabled(False)
        self.ffprobe_analyze_btn.clicked.connect(self._start_ffprobe_analysis)
        self.ffprobe_analyze_btn.setMinimumHeight(36)
        primary_layout.addWidget(self.ffprobe_analyze_btn)

        self.ffprobe_cancel_btn = QPushButton("🛑 Cancel")
        self.ffprobe_cancel_btn.setEnabled(False)
        self.ffprobe_cancel_btn.clicked.connect(self._cancel_operation)
        self.ffprobe_cancel_btn.setMinimumHeight(36)
        primary_layout.addWidget(self.ffprobe_cancel_btn)

        layout.addLayout(primary_layout)

        # Export buttons (enabled after analysis)
        export_layout = QHBoxLayout()

        self.ffprobe_export_pdf_btn = QPushButton("📄 PDF Report")
        self.ffprobe_export_pdf_btn.clicked.connect(self._generate_pdf_report)
        self.ffprobe_export_pdf_btn.setEnabled(False)
        self.ffprobe_export_pdf_btn.setMinimumHeight(32)
        export_layout.addWidget(self.ffprobe_export_pdf_btn)

        self.ffprobe_export_csv_btn = QPushButton("📊 Export CSV")
        self.ffprobe_export_csv_btn.clicked.connect(self._export_to_csv)
        self.ffprobe_export_csv_btn.setEnabled(False)
        self.ffprobe_export_csv_btn.setMinimumHeight(32)
        export_layout.addWidget(self.ffprobe_export_csv_btn)

        layout.addLayout(export_layout)

    def _create_exiftool_buttons(self):
        """Create button set for ExifTool/GPS tab"""
        self.exiftool_button_widget = QWidget()
        layout = QVBoxLayout(self.exiftool_button_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Primary action button
        primary_layout = QHBoxLayout()

        self.exiftool_analyze_btn = QPushButton("📷 Analyze with ExifTool")
        self.exiftool_analyze_btn.setEnabled(False)
        self.exiftool_analyze_btn.clicked.connect(self._start_exiftool_analysis)
        self.exiftool_analyze_btn.setMinimumHeight(36)
        primary_layout.addWidget(self.exiftool_analyze_btn)

        self.exiftool_cancel_btn = QPushButton("🛑 Cancel")
        self.exiftool_cancel_btn.setEnabled(False)
        self.exiftool_cancel_btn.clicked.connect(self._cancel_operation)
        self.exiftool_cancel_btn.setMinimumHeight(36)
        primary_layout.addWidget(self.exiftool_cancel_btn)

        layout.addLayout(primary_layout)

        # Export buttons (enabled after analysis)
        export_layout = QHBoxLayout()

        self.exiftool_export_csv_btn = QPushButton("📊 Export CSV")
        self.exiftool_export_csv_btn.clicked.connect(self._export_exiftool_csv)
        self.exiftool_export_csv_btn.setEnabled(False)
        self.exiftool_export_csv_btn.setMinimumHeight(32)
        export_layout.addWidget(self.exiftool_export_csv_btn)

        self.exiftool_export_kml_btn = QPushButton("🌍 Export KML")
        self.exiftool_export_kml_btn.clicked.connect(self._export_to_kml)
        self.exiftool_export_kml_btn.setEnabled(False)
        self.exiftool_export_kml_btn.setMinimumHeight(32)
        export_layout.addWidget(self.exiftool_export_kml_btn)

        self.exiftool_show_map_btn = QPushButton("🗺️ Show Map")
        self.exiftool_show_map_btn.clicked.connect(self._show_gps_map)
        self.exiftool_show_map_btn.setEnabled(False)
        self.exiftool_show_map_btn.setMinimumHeight(32)
        export_layout.addWidget(self.exiftool_show_map_btn)

        layout.addLayout(export_layout)

    def _show_ffprobe_buttons(self):
        """Show FFprobe buttons, hide ExifTool buttons"""
        # Clear layout
        while self.action_button_layout.count():
            child = self.action_button_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)

        # Add FFprobe buttons
        self.action_button_layout.addWidget(self.ffprobe_button_widget)
        self.ffprobe_button_widget.setVisible(True)
        if hasattr(self, 'exiftool_button_widget'):
            self.exiftool_button_widget.setVisible(False)

    def _show_exiftool_buttons(self):
        """Show ExifTool buttons, hide FFprobe buttons"""
        # Clear layout
        while self.action_button_layout.count():
            child = self.action_button_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)

        # Add ExifTool buttons
        self.action_button_layout.addWidget(self.exiftool_button_widget)
        self.exiftool_button_widget.setVisible(True)
        if hasattr(self, 'ffprobe_button_widget'):
            self.ffprobe_button_widget.setVisible(False)

    def _on_tool_tab_changed(self, index: int):
        """Handle tool tab change to swap action buttons"""
        self.current_tool = "ffprobe" if index == 0 else "exiftool"

        if index == 0:  # FFprobe Analysis tab
            self._show_ffprobe_buttons()
        elif index == 1:  # ExifTool/GPS tab
            self._show_exiftool_buttons()

        # Update statistics visibility based on available results
        self._update_stats_display()

    def _create_console_section(self) -> QGroupBox:
        """Create console output section"""
        console_group = QGroupBox("📋 Analysis Output")
        console_layout = QVBoxLayout(console_group)

        self.console = LogConsole()
        console_layout.addWidget(self.console)

        return console_group

    def _connect_signals(self):
        """Connect internal signals"""
        # Log message signal to console
        self.log_message.connect(self.console.append_log)

    def _check_ffprobe_status(self):
        """Check FFprobe availability and log status"""
        status = self.controller.get_ffprobe_status()

        if status.get('available'):
            version = status.get('version', 'Unknown version')
            self.log_message.emit(f"FFprobe ready: {version}")
        else:
            self.log_message.emit(
                "WARNING: FFprobe not found. Please download FFmpeg from "
                "https://ffmpeg.org/download.html and place ffprobe.exe in the 'bin' folder."
            )

    def _add_files(self):
        """Add files to analyze"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Media Files",
            "",
            "Media Files (*.mp4 *.avi *.mov *.mkv *.jpg *.jpeg *.png *.heic *.heif);;All Files (*.*)"
        )

        if file_paths:
            for file_path in file_paths:
                path = Path(file_path)
                if path not in self.selected_paths:
                    self.selected_paths.append(path)
                    self._add_file_to_tree(path)

            self._update_file_count()

    def _add_folder(self):
        """Add folder to analyze"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder",
            ""
        )

        if folder_path:
            path = Path(folder_path)
            if path not in self.selected_paths:
                self.selected_paths.append(path)
                self._add_folder_to_tree(path)

            self._update_file_count()

    def _add_file_to_tree(self, file_path: Path):
        """Add a file to the tree widget"""
        parent_name = file_path.parent.name

        # Find or create parent folder item
        parent_item = self._find_or_create_parent(parent_name)

        # Add file as child
        file_item = QTreeWidgetItem(parent_item)
        file_item.setText(0, f"📄 {file_path.name}")
        file_item.setData(0, Qt.UserRole, str(file_path))

        parent_item.setExpanded(True)

    def _add_folder_to_tree(self, folder_path: Path):
        """Add a folder to the tree widget"""
        folder_item = QTreeWidgetItem(self.file_tree)
        folder_item.setText(0, f"📂 {folder_path.name}")
        folder_item.setData(0, Qt.UserRole, str(folder_path))
        folder_item.setExpanded(True)

    def _find_or_create_parent(self, parent_name: str) -> QTreeWidgetItem:
        """Find or create parent folder item in tree"""
        # Search for existing parent
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            if item.text(0) == f"📂 {parent_name}":
                return item

        # Create new parent
        parent_item = QTreeWidgetItem(self.file_tree)
        parent_item.setText(0, f"📂 {parent_name}")
        return parent_item

    def _clear_files(self):
        """Clear all selected files"""
        self.file_tree.clear()
        self.selected_paths.clear()
        self.last_results = None
        self.last_exiftool_results = None
        self._update_file_count()
        self._update_export_buttons()
        self.stats_group.setVisible(False)

    def _update_file_count(self):
        """Update file count label and enable/disable buttons"""
        file_count = len(self.selected_paths)

        if file_count > 0:
            self.file_count_label.setText(f"{file_count} item(s) selected")
            self.clear_btn.setEnabled(True)

            # Enable analyze button for current tab
            if not self.operation_active:
                if self.current_tool == "ffprobe":
                    self.ffprobe_analyze_btn.setEnabled(True)
                else:
                    self.exiftool_analyze_btn.setEnabled(True)
        else:
            self.file_count_label.setText("No files selected")
            self.clear_btn.setEnabled(False)
            self.ffprobe_analyze_btn.setEnabled(False)
            self.exiftool_analyze_btn.setEnabled(False)

    def _update_export_buttons(self):
        """Update export button states based on available results"""
        # FFprobe export buttons
        has_ffprobe_results = self.last_results is not None
        self.ffprobe_export_pdf_btn.setEnabled(has_ffprobe_results)
        self.ffprobe_export_csv_btn.setEnabled(has_ffprobe_results)

        # ExifTool export buttons
        has_exiftool_results = self.last_exiftool_results is not None
        self.exiftool_export_csv_btn.setEnabled(has_exiftool_results)

        # KML and map buttons only if GPS data exists
        has_gps = (has_exiftool_results and
                   self.last_exiftool_results.gps_locations and
                   len(self.last_exiftool_results.gps_locations) > 0)
        self.exiftool_export_kml_btn.setEnabled(has_gps)
        self.exiftool_show_map_btn.setEnabled(has_gps)

    def _get_current_settings(self) -> MediaAnalysisSettings:
        """Get current analysis settings from UI"""
        settings = MediaAnalysisSettings()

        # General fields
        if 'general' in self.field_groups:
            group_data = self.field_groups['general']
            settings.general_fields = MetadataFieldGroup(
                enabled=group_data['group'].isChecked(),
                fields={
                    key: checkbox.isChecked()
                    for key, checkbox in group_data['fields'].items()
                }
            )

        # Video fields
        if 'video' in self.field_groups:
            group_data = self.field_groups['video']
            settings.video_fields = MetadataFieldGroup(
                enabled=group_data['group'].isChecked(),
                fields={
                    key: checkbox.isChecked()
                    for key, checkbox in group_data['fields'].items()
                }
            )

        # Audio fields
        if 'audio' in self.field_groups:
            group_data = self.field_groups['audio']
            settings.audio_fields = MetadataFieldGroup(
                enabled=group_data['group'].isChecked(),
                fields={
                    key: checkbox.isChecked()
                    for key, checkbox in group_data['fields'].items()
                }
            )

        # Location fields
        if 'location' in self.field_groups:
            group_data = self.field_groups['location']
            settings.location_fields = MetadataFieldGroup(
                enabled=group_data['group'].isChecked(),
                fields={
                    key: checkbox.isChecked()
                    for key, checkbox in group_data['fields'].items()
                }
            )

        # Device fields
        if 'device' in self.field_groups:
            group_data = self.field_groups['device']
            settings.device_fields = MetadataFieldGroup(
                enabled=group_data['group'].isChecked(),
                fields={
                    key: checkbox.isChecked()
                    for key, checkbox in group_data['fields'].items()
                }
            )

        # Advanced Video fields
        if 'advanced_video' in self.field_groups:
            group_data = self.field_groups['advanced_video']
            settings.advanced_video_fields = MetadataFieldGroup(
                enabled=group_data['group'].isChecked(),
                fields={
                    key: checkbox.isChecked()
                    for key, checkbox in group_data['fields'].items()
                }
            )

        # Frame Analysis fields
        if 'frame_analysis' in self.field_groups:
            group_data = self.field_groups['frame_analysis']
            settings.frame_analysis_fields = MetadataFieldGroup(
                enabled=group_data['group'].isChecked(),
                fields={
                    key: checkbox.isChecked()
                    for key, checkbox in group_data['fields'].items()
                }
            )

        # Display options
        format_index = self.path_format_combo.currentIndex()
        settings.file_reference_format = [
            FileReferenceFormat.FULL_PATH,
            FileReferenceFormat.PARENT_AND_NAME,
            FileReferenceFormat.NAME_ONLY
        ][format_index]

        # Processing options
        settings.timeout_seconds = self.timeout_spin.value()
        settings.max_workers = self.workers_spin.value()
        settings.skip_non_media = self.skip_non_media_check.isChecked()

        return settings

    def _get_exiftool_settings(self) -> ExifToolSettings:
        """Get current ExifTool settings from UI"""
        settings = ExifToolSettings()

        # Field groups
        if 'geospatial' in self.exif_field_groups:
            settings.geospatial_enabled = self.exif_field_groups['geospatial']['group'].isChecked()

        if 'temporal' in self.exif_field_groups:
            settings.temporal_enabled = self.exif_field_groups['temporal']['group'].isChecked()

        if 'device' in self.exif_field_groups:
            settings.device_enabled = self.exif_field_groups['device']['group'].isChecked()

        if 'camera_settings' in self.exif_field_groups:
            settings.camera_settings_enabled = self.exif_field_groups['camera_settings']['group'].isChecked()

        # GPS privacy level
        privacy_index = self.gps_privacy_combo.currentIndex()
        settings.gps_precision = [
            GPSPrecisionLevel.EXACT,
            GPSPrecisionLevel.BUILDING,
            GPSPrecisionLevel.BLOCK,
            GPSPrecisionLevel.NEIGHBORHOOD
        ][privacy_index]

        # Other options
        settings.extract_thumbnails = self.extract_thumbnails_check.isChecked()
        settings.extract_binary = self.include_binary_check.isChecked()
        settings.batch_size = self.exif_batch_spin.value()

        return settings

    def _start_ffprobe_analysis(self):
        """Start FFprobe analysis"""
        if not self.selected_paths:
            return

        # Get current settings
        settings = self._get_current_settings()

        # Save settings for next time
        self._save_settings(settings)

        # Update UI state
        self._set_operation_active(True, "ffprobe")

        # Log start
        self.log_message.emit(f"Starting FFprobe analysis of {len(self.selected_paths)} items...")

        # Start workflow through controller
        result = self.controller.start_analysis_workflow(
            self.selected_paths,
            settings,
            self.form_data
        )

        if result.success:
            self.current_worker = result.value

            # Connect worker signals
            self.current_worker.result_ready.connect(self._on_analysis_complete)
            self.current_worker.progress_update.connect(self._on_progress_update)

            # Start worker
            self.current_worker.start()
        else:
            # Failed to start
            self._set_operation_active(False, "ffprobe")
            self.log_message.emit(f"Error: {result.error.user_message}")

            QMessageBox.warning(
                self,
                "Analysis Error",
                result.error.user_message
            )

    def _start_exiftool_analysis(self):
        """Start ExifTool analysis"""
        if not self.selected_paths:
            return

        # Get ExifTool settings
        settings = self._get_exiftool_settings()

        # Update UI state
        self._set_operation_active(True, "exiftool")

        # Log start
        self.log_message.emit(f"Starting ExifTool analysis of {len(self.selected_paths)} items...")

        # Start ExifTool workflow through controller
        result = self.controller.start_exiftool_workflow(
            self.selected_paths,
            settings,
            self.form_data
        )

        if result.success:
            self.current_worker = result.value

            # Connect worker signals
            self.current_worker.result_ready.connect(self._on_exiftool_complete)
            self.current_worker.progress_update.connect(self._on_progress_update)

            # Start worker
            self.current_worker.start()
        else:
            # Failed to start
            self._set_operation_active(False, "exiftool")
            self.log_message.emit(f"Error: {result.error.user_message}")

            QMessageBox.warning(
                self,
                "ExifTool Error",
                result.error.user_message
            )

    def _on_progress_update(self, percentage: int, message: str):
        """Handle progress updates from worker"""
        self.progress_bar.setValue(percentage)
        self.progress_label.setText(message)

        # Log significant progress
        if percentage % 10 == 0 or percentage == 100:
            self.log_message.emit(message)

    def _on_analysis_complete(self, result):
        """Handle FFprobe analysis completion"""
        self._set_operation_active(False, "ffprobe")

        if result.success:
            self.last_results = result.value

            # Update statistics display
            self._update_ffprobe_stats(self.last_results)

            # Log completion
            self.log_message.emit(
                f"FFprobe analysis complete: {self.last_results.successful} media files found, "
                f"{self.last_results.skipped} non-media files skipped"
            )

            # Update export buttons
            self._update_export_buttons()

            # Build success message data
            op_data = self._build_operation_data(self.last_results)
            success_message = self.success_builder.build_media_analysis_success_message(op_data)

            # Show success dialog
            SuccessDialog.show_success_message(success_message, self)

        else:
            # Analysis failed
            self.log_message.emit(f"FFprobe analysis failed: {result.error.user_message}")

            QMessageBox.warning(
                self,
                "Analysis Failed",
                result.error.user_message
            )

    def _on_exiftool_complete(self, result):
        """Handle ExifTool completion"""
        self._set_operation_active(False, "exiftool")

        if result.success:
            self.last_exiftool_results = result.value

            # Update statistics display
            self._update_exiftool_stats(self.last_exiftool_results)

            # Log completion
            self.log_message.emit(
                f"ExifTool analysis complete: {self.last_exiftool_results.successful} files processed, "
                f"{self.last_exiftool_results.failed} failed"
            )

            # Update export buttons
            self._update_export_buttons()

            # Show map if GPS data found and option enabled
            if self.last_exiftool_results.gps_locations and self.show_map_check.isChecked():
                self._show_gps_map()

            # Show success dialog
            op_data = ExifToolOperationData(
                total_files=self.last_exiftool_results.total_files,
                successful=self.last_exiftool_results.successful,
                failed=self.last_exiftool_results.failed,
                gps_count=len(self.last_exiftool_results.gps_locations),
                device_count=len(self.last_exiftool_results.device_map),
                processing_time=self.last_exiftool_results.processing_time
            )

            success_message = self.success_builder.build_exiftool_success_message(op_data)
            SuccessDialog.show_success_message(success_message, self)

        else:
            # Analysis failed
            self.log_message.emit(f"ExifTool analysis failed: {result.error.user_message}")

            QMessageBox.warning(
                self,
                "ExifTool Failed",
                result.error.user_message
            )

    def _update_ffprobe_stats(self, results: MediaAnalysisResult):
        """Update statistics display with FFprobe results"""
        self.stat_total_label.setText(str(results.total_files))
        self.stat_success_label.setText(str(results.successful))
        self.stat_failed_label.setText(str(results.failed + results.skipped))
        self.stat_speed_label.setText(f"{results.files_per_second:.1f}")

        self.stats_group.setVisible(True)

    def _update_exiftool_stats(self, results: ExifToolAnalysisResult):
        """Update statistics display with ExifTool results"""
        self.stat_total_label.setText(str(results.total_files))
        self.stat_success_label.setText(str(results.successful))
        self.stat_failed_label.setText(str(results.failed))

        # Calculate files per second
        files_per_sec = results.total_files / results.processing_time if results.processing_time > 0 else 0
        self.stat_speed_label.setText(f"{files_per_sec:.1f}")

        self.stats_group.setVisible(True)

    def _update_stats_display(self):
        """Update statistics display based on current tab and available results"""
        if self.current_tool == "ffprobe" and self.last_results:
            self._update_ffprobe_stats(self.last_results)
        elif self.current_tool == "exiftool" and self.last_exiftool_results:
            self._update_exiftool_stats(self.last_exiftool_results)
        else:
            self.stats_group.setVisible(False)

    def _build_operation_data(self, results: MediaAnalysisResult) -> MediaAnalysisOperationData:
        """Build operation data for success message"""
        op_data = MediaAnalysisOperationData(
            total_files=results.total_files,
            media_files_found=results.successful,
            non_media_files=results.skipped,
            failed_files=results.failed,
            processing_time_seconds=results.processing_time,
            files_per_second=results.files_per_second
        )

        # Add format statistics
        op_data.format_counts = results.get_format_statistics()

        # Add codec statistics
        codec_stats = results.get_codec_statistics()
        op_data.video_codec_counts = codec_stats.get('video_codecs', {})
        op_data.audio_codec_counts = codec_stats.get('audio_codecs', {})

        # Calculate total duration and size
        for metadata in results.metadata_list:
            if metadata.duration:
                op_data.total_duration_seconds += metadata.duration
            op_data.total_file_size_bytes += metadata.file_size

        return op_data

    def _generate_pdf_report(self):
        """Generate PDF report from FFprobe results"""
        if not self.last_results:
            return

        # Get output path
        default_name = f"media_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF Report",
            default_name,
            "PDF Files (*.pdf)"
        )

        if file_path:
            # Generate report through controller
            result = self.controller.generate_report(
                self.last_results,
                Path(file_path),
                None  # No form data needed for media analysis reports
            )

            if result.success:
                self.log_message.emit(f"Report saved: {file_path}")

                # Update operation data with report path
                op_data = self._build_operation_data(self.last_results)
                op_data.report_path = Path(file_path)

                # Show success message
                success_message = self.success_builder.build_media_analysis_success_message(op_data)
                SuccessDialog.show_success_message(success_message, self)
            else:
                self.log_message.emit(f"Report generation failed: {result.error.user_message}")
                QMessageBox.warning(
                    self,
                    "Report Error",
                    result.error.user_message
                )

    def _export_to_csv(self):
        """Export FFprobe results to CSV"""
        if not self.last_results:
            return

        # Get output path
        default_name = f"media_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export to CSV",
            default_name,
            "CSV Files (*.csv)"
        )

        if file_path:
            # Export through controller
            result = self.controller.export_to_csv(
                self.last_results,
                Path(file_path)
            )

            if result.success:
                self.log_message.emit(f"CSV exported: {file_path}")

                # Show success message
                export_message = self.success_builder.build_csv_export_success(
                    file_path=Path(file_path),
                    record_count=self.last_results.total_files,
                    export_type="FFprobe Media Analysis"
                )
                SuccessDialog.show_success_message(export_message, self)
            else:
                self.log_message.emit(f"CSV export failed: {result.error.user_message}")
                QMessageBox.warning(
                    self,
                    "Export Error",
                    result.error.user_message
                )

    def _export_exiftool_csv(self):
        """Export ExifTool results to CSV"""
        if not self.last_exiftool_results:
            return

        # Get output path
        default_name = f"exiftool_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export to CSV",
            default_name,
            "CSV Files (*.csv)"
        )

        if file_path:
            # Export through controller
            result = self.controller.export_exiftool_to_csv(
                self.last_exiftool_results,
                Path(file_path)
            )

            if result.success:
                self.log_message.emit(f"ExifTool CSV exported: {file_path}")

                # Show success message
                export_message = self.success_builder.build_csv_export_success(
                    file_path=Path(file_path),
                    record_count=self.last_exiftool_results.total_files,
                    export_type="ExifTool"
                )
                SuccessDialog.show_success_message(export_message, self)
            else:
                self.log_message.emit(f"CSV export failed: {result.error.user_message}")
                QMessageBox.warning(
                    self,
                    "Export Error",
                    result.error.user_message
                )

    def _export_to_kml(self):
        """Export GPS data to KML"""
        if not self.last_exiftool_results or not self.last_exiftool_results.gps_locations:
            return

        # Get output path
        default_name = f"gps_locations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.kml"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export to KML",
            default_name,
            "KML Files (*.kml)"
        )

        if file_path:
            # Export through controller
            result = self.controller.export_to_kml(
                self.last_exiftool_results.gps_locations,
                Path(file_path),
                group_by_device=True
            )

            if result.success:
                self.log_message.emit(f"KML exported: {file_path}")

                # Show success message
                device_count = len(self.last_exiftool_results.device_map) if self.last_exiftool_results.device_map else None
                export_message = self.success_builder.build_kml_export_success(
                    file_path=Path(file_path),
                    location_count=len(self.last_exiftool_results.gps_locations),
                    device_count=device_count
                )
                SuccessDialog.show_success_message(export_message, self)
            else:
                self.log_message.emit(f"KML export failed: {result.error.user_message}")
                QMessageBox.warning(
                    self,
                    "Export Error",
                    result.error.user_message
                )

    def _show_gps_map(self):
        """Show interactive GPS map"""
        if not self.last_exiftool_results or not self.last_exiftool_results.gps_locations:
            QMessageBox.information(
                self,
                "No GPS Data",
                "No GPS location data found in the analyzed files."
            )
            return

        # Create map dialog
        from PySide6.QtWidgets import QDialog
        dialog = QDialog(self)
        dialog.setWindowTitle("GPS Location Map")
        dialog.setModal(False)
        dialog.resize(1200, 800)

        layout = QVBoxLayout(dialog)

        # Create and configure map widget
        map_widget = GeoVisualizationWidget()
        self.geo_widget = map_widget

        map_widget.add_media_locations(self.last_exiftool_results.gps_locations)

        # Set clustering option
        if hasattr(map_widget, 'set_clustering'):
            map_widget.set_clustering(self.cluster_markers_check.isChecked())

        # Connect signals for file selection
        map_widget.file_selected.connect(
            lambda path: self.log_message.emit(f"Selected: {path}")
        )

        layout.addWidget(map_widget)

        # Show dialog
        dialog.show()

    def _cancel_operation(self):
        """Cancel current operation"""
        if self.current_worker and self.current_worker.isRunning():
            self.log_message.emit("Cancelling operation...")
            self.current_worker.cancel()

            # Update UI state
            self._set_operation_active(False, self.current_tool)

    def _set_operation_active(self, active: bool, tool: str = None):
        """Update UI state for operation status"""
        self.operation_active = active

        # Update buttons based on tool
        if tool == "ffprobe" or tool is None:
            self.ffprobe_analyze_btn.setEnabled(not active and len(self.selected_paths) > 0)
            self.ffprobe_cancel_btn.setEnabled(active)

        if tool == "exiftool" or tool is None:
            self.exiftool_analyze_btn.setEnabled(not active and len(self.selected_paths) > 0)
            self.exiftool_cancel_btn.setEnabled(active)

        # File selection buttons
        self.add_files_btn.setEnabled(not active)
        self.add_folder_btn.setEnabled(not active)
        self.clear_btn.setEnabled(not active and len(self.selected_paths) > 0)

        # Update progress
        self.progress_bar.setVisible(active)
        self.progress_label.setVisible(active)

        if not active:
            self.progress_bar.setValue(0)
            self.progress_label.setText("")

    def _load_settings(self) -> MediaAnalysisSettings:
        """Load saved settings"""
        qsettings = QSettings()
        qsettings.beginGroup("MediaAnalysis")

        settings = MediaAnalysisSettings()

        # Load saved values if available
        if qsettings.contains("settings_dict"):
            try:
                import json
                settings_str = qsettings.value("settings_dict")
                settings_dict = json.loads(settings_str)
                settings = MediaAnalysisSettings.from_dict(settings_dict)
            except Exception as e:
                logger.warning(f"Failed to load media analysis settings: {e}")

        qsettings.endGroup()
        return settings

    def _save_settings(self, settings: MediaAnalysisSettings):
        """Save current settings"""
        qsettings = QSettings()
        qsettings.beginGroup("MediaAnalysis")

        try:
            import json
            settings_dict = settings.to_dict()
            settings_str = json.dumps(settings_dict)
            qsettings.setValue("settings_dict", settings_str)
        except Exception as e:
            logger.warning(f"Failed to save media analysis settings: {e}")

        qsettings.endGroup()

    def cleanup(self):
        """Simple cleanup that delegates to controller"""
        logger.info("Cleaning up MediaAnalysisTab")

        # Cancel any running operations and clean up controller
        if self.controller:
            self.controller.cancel_current_operation()
            self.controller.cleanup()

        # Clear references
        self.current_worker = None
        self.last_results = None
        self.last_exiftool_results = None
        self.geo_widget = None

        logger.info("MediaAnalysisTab cleanup complete")
