#!/usr/bin/env python3
"""
Media Analysis Tab - UI for media file metadata extraction and analysis
Uses FFprobe to analyze media files and generate reports
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QCheckBox, QFileDialog, QProgressBar, QSplitter,
    QComboBox, QSpinBox, QDoubleSpinBox, QMessageBox, QScrollArea,
    QGridLayout, QTabWidget
)
from PySide6.QtGui import QFont

from ui.components import FilesPanel, LogConsole
from ui.components.elided_label import ElidedLabel
from ui.dialogs.success_dialog import SuccessDialog
from controllers.media_analysis_controller import MediaAnalysisController
from core.media_analysis_models import (
    MediaAnalysisSettings, MediaAnalysisResult, MetadataFieldGroup,
    FileReferenceFormat
)
from core.exiftool.exiftool_models import (
    ExifToolSettings, ExifToolAnalysisResult, GPSPrecisionLevel
)
from core.models import FormData
from ui.components.geo import GeoVisualizationWidget
from core.services.success_message_data import MediaAnalysisOperationData, ExifToolOperationData
from .media_analysis_success import MediaAnalysisSuccessBuilder
from core.settings_manager import settings
from core.logger import logger
from core.exceptions import UIError, ErrorSeverity
from core.error_handler import handle_error


class MediaAnalysisTab(QWidget):
    """Tab for media file analysis operations"""
    
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
        
        # Success message builder for this tab
        self.success_builder = MediaAnalysisSuccessBuilder()
        
        self._create_ui()
        self._connect_signals()
        self._check_ffprobe_status()
    
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
        
        # Left panel - File selection
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
    
    def _create_header(self) -> QGroupBox:
        """Create header with title and status"""
        header = QGroupBox("Media Analysis Operations")
        header_layout = QHBoxLayout(header)
        
        # Title and description
        title_layout = QVBoxLayout()
        title_label = QLabel("🎬 Extract Metadata from Media Files")
        title_label.setFont(self._get_title_font())
        title_layout.addWidget(title_label)
        
        desc_label = QLabel("Analyze media files to extract metadata using FFprobe and ExifTool")
        desc_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        desc_label.setWordWrap(True)
        title_layout.addWidget(desc_label)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        # Status indicator
        self.ffprobe_status_label = QLabel("Checking FFprobe...")
        self.ffprobe_status_label.setStyleSheet("color: #6c757d;")
        header_layout.addWidget(self.ffprobe_status_label)
        
        return header
    
    def _create_file_panel(self) -> QGroupBox:
        """Create left panel for file selection"""
        panel = QGroupBox("Files to Analyze")
        layout = QVBoxLayout(panel)
        
        # File selection buttons
        button_layout = QHBoxLayout()
        
        self.add_files_btn = QPushButton("📁 Add Files")
        self.add_files_btn.clicked.connect(self._add_files)
        button_layout.addWidget(self.add_files_btn)
        
        self.add_folder_btn = QPushButton("📂 Add Folder")
        self.add_folder_btn.clicked.connect(self._add_folder)
        button_layout.addWidget(self.add_folder_btn)
        
        self.clear_btn = QPushButton("🗑️ Clear")
        self.clear_btn.clicked.connect(self._clear_files)
        button_layout.addWidget(self.clear_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Files panel
        self.files_panel = FilesPanel()
        layout.addWidget(self.files_panel)
        
        # File count label
        self.file_count_label = QLabel("No files selected")
        self.file_count_label.setStyleSheet("color: #6c757d;")
        layout.addWidget(self.file_count_label)
        
        return panel
    
    def _create_settings_panel(self) -> QGroupBox:
        """Create right panel for analysis settings"""
        panel = QGroupBox("Analysis Settings")
        main_layout = QVBoxLayout(panel)
        
        # Create tab widget for FFprobe and ExifTool
        self.tool_tabs = QTabWidget()
        
        # FFprobe tab
        ffprobe_tab = self._create_ffprobe_settings_tab()
        self.tool_tabs.addTab(ffprobe_tab, "🎬 FFprobe")
        
        # ExifTool tab
        exiftool_tab = self._create_exiftool_settings_tab()
        self.tool_tabs.addTab(exiftool_tab, "📷 ExifTool")
        
        # Connect tab change signal
        self.tool_tabs.currentChanged.connect(self._on_tool_tab_changed)
        
        main_layout.addWidget(self.tool_tabs)
        
        # Progress bar (shared between tools)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Progress label
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        self.progress_label.setStyleSheet("color: #6c757d; font-size: 10px;")
        main_layout.addWidget(self.progress_label)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.analyze_btn = QPushButton("🔍 Analyze Files")
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.clicked.connect(self._start_analysis)
        button_layout.addWidget(self.analyze_btn)
        
        self.export_btn = QPushButton("📊 Export Results")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_results)
        button_layout.addWidget(self.export_btn)
        
        self.cancel_btn = QPushButton("🛑 Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_operation)
        button_layout.addWidget(self.cancel_btn)
        
        main_layout.addLayout(button_layout)
        
        return panel
    
    def _create_ffprobe_settings_tab(self) -> QWidget:
        """Create FFprobe settings tab"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        
        # Create scrollable area for settings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Container widget for scroll area
        container = QWidget()
        layout = QVBoxLayout(container)
        
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
        
        # Container widget for scroll area
        container = QWidget()
        layout = QVBoxLayout(container)
        
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
    
    def _create_console_section(self) -> QGroupBox:
        """Create console output section"""
        console_group = QGroupBox("Analysis Output")
        console_layout = QVBoxLayout(console_group)
        
        self.console = LogConsole()
        console_layout.addWidget(self.console)
        
        return console_group
    
    def _connect_signals(self):
        """Connect internal signals"""
        # Files panel signals
        self.files_panel.files_changed.connect(self._on_files_changed)
    
    def _check_ffprobe_status(self):
        """Check FFprobe availability and update UI"""
        status = self.controller.get_ffprobe_status()
        
        if status.get('available'):
            version = status.get('version', 'Unknown version')
            # Truncate version string if too long
            if len(version) > 50:
                version = version[:47] + "..."
            self.ffprobe_status_label.setText(f"✓ FFprobe: {version}")
            self.ffprobe_status_label.setStyleSheet("color: #28a745;")
        else:
            self.ffprobe_status_label.setText("⚠ FFprobe not found")
            self.ffprobe_status_label.setStyleSheet("color: #dc3545;")
            self.ffprobe_status_label.setToolTip(
                "FFprobe is required for media analysis.\n"
                "Please download FFmpeg from https://ffmpeg.org/download.html\n"
                "and place ffprobe.exe in the 'bin' folder."
            )
    
    def _get_title_font(self) -> QFont:
        """Get font for title labels"""
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        return font
    
    def _add_files(self):
        """Add files to analyze"""
        # Use FilesPanel's built-in file dialog method
        self.files_panel.add_files()
    
    def _add_folder(self):
        """Add folder to analyze"""
        # Use FilesPanel's built-in folder dialog method
        self.files_panel.add_folder()
    
    def _clear_files(self):
        """Clear all selected files"""
        self.files_panel.clear_all()
        self.last_results = None
        self.export_btn.setEnabled(False)
    
    def _on_files_changed(self):
        """Handle files panel changes"""
        # Get files and folders from FilesPanel
        files, folders = self.files_panel.get_all_items()
        all_paths = files + folders
        file_count = len(all_paths)
        
        if file_count > 0:
            self.file_count_label.setText(f"{file_count} item(s) selected")
            self.analyze_btn.setEnabled(not self.operation_active)
        else:
            self.file_count_label.setText("No files selected")
            self.analyze_btn.setEnabled(False)
        
        self.selected_paths = all_paths
    
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
    
    def _on_tool_tab_changed(self, index: int):
        """Handle tool tab change"""
        self.current_tool = "ffprobe" if index == 0 else "exiftool"
        
        # Update button text based on tool
        if self.current_tool == "ffprobe":
            self.analyze_btn.setText("🔍 Analyze with FFprobe")
        else:
            self.analyze_btn.setText("📷 Analyze with ExifTool")
        
        # Enable export button if we have results for the current tool
        if self.current_tool == "ffprobe" and self.last_results:
            self.export_btn.setEnabled(True)
        elif self.current_tool == "exiftool" and self.last_exiftool_results:
            self.export_btn.setEnabled(True)
        else:
            self.export_btn.setEnabled(False)
    
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
        
        # Debug logging
        logger.info(f"EXIFTOOL SETTINGS: extract_thumbnails={settings.extract_thumbnails}, extract_binary={settings.extract_binary}")
        
        return settings
    
    def _start_analysis(self):
        """Start media analysis operation"""
        if not self.selected_paths:
            return
        
        if self.current_tool == "ffprobe":
            self._start_ffprobe_analysis()
        else:
            self._start_exiftool_analysis()
    
    def _start_ffprobe_analysis(self):
        """Start FFprobe analysis"""
        # Get current settings
        settings = self._get_current_settings()
        
        # Save settings for next time
        self._save_settings(settings)
        
        # Update UI state
        self._set_operation_active(True)
        
        # Log start
        self.log_message.emit(f"Starting analysis of {len(self.selected_paths)} items...")
        
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
            self._set_operation_active(False)
            self.log_message.emit(f"Error: {result.error.user_message}")
            
            QMessageBox.warning(
                self,
                "Analysis Error",
                result.error.user_message
            )
    
    def _start_exiftool_analysis(self):
        """Start ExifTool analysis"""
        # Get ExifTool settings
        settings = self._get_exiftool_settings()
        
        # Update UI state
        self._set_operation_active(True)
        
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
            self._set_operation_active(False)
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
    
    def _on_exiftool_complete(self, result):
        """Handle ExifTool completion"""
        self._set_operation_active(False)
        
        if result.success:
            self.last_exiftool_results = result.value
            self.export_btn.setEnabled(True)
            
            # Log completion
            self.log_message.emit(
                f"ExifTool analysis complete: {self.last_exiftool_results.successful} files processed, "
                f"{self.last_exiftool_results.failed} failed"
            )
            
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
    
    def _show_gps_map(self):
        """Show interactive GPS map"""
        if not self.last_exiftool_results or not self.last_exiftool_results.gps_locations:
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
    
    def _on_analysis_complete(self, result):
        """Handle FFprobe analysis completion"""
        self._set_operation_active(False)
        
        if result.success:
            self.last_results = result.value
            self.export_btn.setEnabled(True)
            
            # Log completion
            self.log_message.emit(
                f"Analysis complete: {self.last_results.successful} media files found, "
                f"{self.last_results.skipped} non-media files skipped"
            )
            
            # Build success message data
            op_data = self._build_operation_data(self.last_results)
            success_message = self.success_builder.build_media_analysis_success_message(op_data)
            
            # Show success dialog
            SuccessDialog.show_success_message(success_message, self)
            
        else:
            # Analysis failed
            self.log_message.emit(f"Analysis failed: {result.error.user_message}")
            
            QMessageBox.warning(
                self,
                "Analysis Failed",
                result.error.user_message
            )
    
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
    
    def _export_results(self):
        """Export analysis results"""
        if self.current_tool == "ffprobe":
            if not self.last_results:
                return
            self._export_ffprobe_results()
        else:
            if not self.last_exiftool_results:
                return
            self._export_exiftool_results()
    
    def _export_ffprobe_results(self):
        """Export FFprobe results"""
        
        # Create export menu
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        
        # PDF report action
        pdf_action = menu.addAction("📄 Generate PDF Report")
        pdf_action.triggered.connect(self._generate_pdf_report)
        
        # CSV export action
        csv_action = menu.addAction("📊 Export to CSV")
        csv_action.triggered.connect(self._export_to_csv)
        
        # Show menu at button
        menu.exec_(self.export_btn.mapToGlobal(self.export_btn.rect().bottomLeft()))
    
    def _export_exiftool_results(self):
        """Export ExifTool results"""
        # Create export menu
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        
        # CSV export action
        csv_action = menu.addAction("📊 Export to CSV")
        csv_action.triggered.connect(self._export_exiftool_csv)
        
        # KML export action (if GPS data exists)
        if self.last_exiftool_results.gps_locations:
            kml_action = menu.addAction("🌍 Export to KML (Google Earth)")
            kml_action.triggered.connect(self._export_to_kml)
        
        # Show menu at button
        menu.exec_(self.export_btn.mapToGlobal(self.export_btn.rect().bottomLeft()))
    
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
                # Show success dialog
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
                # Show success dialog
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
    
    def _generate_pdf_report(self):
        """Generate PDF report from results"""
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
        """Export results to CSV"""
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
                
                # Update operation data with CSV path
                op_data = self._build_operation_data(self.last_results)
                op_data.csv_path = Path(file_path)
                
                # Show success message
                success_message = self.success_builder.build_media_analysis_success_message(op_data)
                SuccessDialog.show_success_message(success_message, self)
            else:
                self.log_message.emit(f"CSV export failed: {result.error.user_message}")
                QMessageBox.warning(
                    self,
                    "Export Error",
                    result.error.user_message
                )
    
    def _cancel_operation(self):
        """Cancel current operation"""
        if self.current_worker and self.current_worker.isRunning():
            self.log_message.emit("Cancelling operation...")
            self.current_worker.cancel()
            
            # Update UI state
            self._set_operation_active(False)
    
    def _set_operation_active(self, active: bool):
        """Update UI state for operation status"""
        self.operation_active = active
        
        # Update buttons
        self.analyze_btn.setEnabled(not active and len(self.selected_paths) > 0)
        self.cancel_btn.setEnabled(active)
        self.add_files_btn.setEnabled(not active)
        self.add_folder_btn.setEnabled(not active)
        self.clear_btn.setEnabled(not active)
        
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