#!/usr/bin/env python3
"""
Vehicle Tracking Tab - UI for GPS vehicle tracking and analysis
Processes CSV files containing vehicle GPS data and provides various analysis modes
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QCheckBox, QFileDialog, QProgressBar, QSplitter,
    QComboBox, QSpinBox, QDoubleSpinBox, QMessageBox, QScrollArea,
    QGridLayout, QTabWidget, QTextEdit, QSlider
)
from PySide6.QtGui import QFont, QTextCharFormat, QColor

# Import vehicle tracking components
from vehicle_tracking.controllers.vehicle_tracking_controller import VehicleTrackingController
from vehicle_tracking.models.vehicle_tracking_models import (
    VehicleTrackingSettings, VehicleTrackingResult, VehicleColor,
    PlaybackSpeed, InterpolationMethod, AnalysisType
)
from vehicle_tracking.ui.components.vehicle_map_widget import VehicleMapWidget

# Core imports
from core.models import FormData
from core.result_types import Result
from core.logger import logger
from core.exceptions import UIError, ErrorSeverity
from core.error_handler import handle_error


class TrackingMode(Enum):
    """Vehicle tracking analysis modes"""
    ANIMATION = "animation"
    COLOCATION = "colocation"
    IDLE = "idle"
    TIMEJUMP = "timejump"
    ROUTE = "route"


class VehicleTrackingTab(QWidget):
    """Tab for vehicle tracking and analysis operations"""

    # Signals
    log_message = Signal(str)
    status_message = Signal(str)

    def __init__(self, form_data: Optional[FormData] = None, parent=None):
        """
        Initialize the Vehicle Tracking tab

        Args:
            form_data: Optional form data for report generation
            parent: Parent widget
        """
        super().__init__(parent)

        # Controller for orchestration
        self.controller = VehicleTrackingController()

        # Form data reference (optional)
        self.form_data = form_data

        # State management
        self.operation_active = False
        self.current_worker = None
        self.last_results: Optional[VehicleTrackingResult] = None
        self.selected_files: List[Path] = []
        self.current_mode = TrackingMode.ANIMATION
        self.map_window: Optional[QWidget] = None

        # Settings
        self.tracking_settings = VehicleTrackingSettings()

        self._create_ui()
        self._connect_signals()

    def _create_ui(self):
        """Create the tab UI with two-column layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Main content splitter (no header banner)
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

    def _create_file_panel(self) -> QGroupBox:
        """Create left panel for CSV file selection"""
        panel = QGroupBox("CSV Files to Track")
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

        # Custom files panel for CSV display
        self.files_panel = VehicleFilesPanel()
        layout.addWidget(self.files_panel)

        # File count label
        self.file_count_label = QLabel("No CSV files selected")
        self.file_count_label.setStyleSheet("color: #6c757d;")
        layout.addWidget(self.file_count_label)

        return panel

    def _create_settings_panel(self) -> QGroupBox:
        """Create right panel for analysis settings"""
        panel = QGroupBox("Tracking Settings")
        main_layout = QVBoxLayout(panel)

        # Create tab widget for different analysis modes
        self.analysis_tabs = QTabWidget()

        # Animation tab (default)
        animation_tab = self._create_animation_settings_tab()
        self.analysis_tabs.addTab(animation_tab, "🚗 Animation")

        # Co-Location Analysis tab
        colocation_tab = self._create_colocation_settings_tab()
        self.analysis_tabs.addTab(colocation_tab, "🎯 Co-Location")

        # Idle Detection tab
        idle_tab = self._create_idle_settings_tab()
        self.analysis_tabs.addTab(idle_tab, "⏸️ Idle Detection")

        # Time Jump Analysis tab
        timejump_tab = self._create_timejump_settings_tab()
        self.analysis_tabs.addTab(timejump_tab, "⏱️ Time Jumps")

        # Route Analysis tab (future)
        route_tab = self._create_route_settings_tab()
        self.analysis_tabs.addTab(route_tab, "🗺️ Route Analysis")
        route_tab.setEnabled(False)  # Disabled for future implementation

        # Connect tab change signal
        self.analysis_tabs.currentChanged.connect(self._on_analysis_tab_changed)

        main_layout.addWidget(self.analysis_tabs)

        # Progress bar (shared between modes)
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

        self.track_btn = QPushButton("🚀 Track Vehicles")
        self.track_btn.setEnabled(False)
        self.track_btn.clicked.connect(self._start_tracking)
        button_layout.addWidget(self.track_btn)

        self.view_map_btn = QPushButton("🗺️ View Map")
        self.view_map_btn.setEnabled(False)
        self.view_map_btn.clicked.connect(self._open_map_window)
        button_layout.addWidget(self.view_map_btn)

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

    def _create_animation_settings_tab(self) -> QWidget:
        """Create animation settings tab"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        # Create scrollable area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Container widget
        container = QWidget()
        layout = QVBoxLayout(container)

        # Display Options group
        display_group = QGroupBox("Display Options")
        display_group.setCheckable(True)
        display_group.setChecked(True)
        display_layout = QVBoxLayout(display_group)

        self.show_trails_check = QCheckBox("Show vehicle trails")
        self.show_trails_check.setChecked(True)
        display_layout.addWidget(self.show_trails_check)

        self.animate_movement_check = QCheckBox("Animate movement")
        self.animate_movement_check.setChecked(True)
        display_layout.addWidget(self.animate_movement_check)

        self.show_timestamps_check = QCheckBox("Show timestamps")
        self.show_timestamps_check.setChecked(False)
        display_layout.addWidget(self.show_timestamps_check)

        self.cluster_markers_check = QCheckBox("Cluster markers")
        self.cluster_markers_check.setChecked(False)
        display_layout.addWidget(self.cluster_markers_check)

        self.auto_center_check = QCheckBox("Auto-center map")
        self.auto_center_check.setChecked(True)
        display_layout.addWidget(self.auto_center_check)

        layout.addWidget(display_group)

        # Animation Controls group
        controls_group = QGroupBox("Animation Controls")
        controls_layout = QGridLayout(controls_group)

        # Speed control
        controls_layout.addWidget(QLabel("Playback Speed:"), 0, 0)
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1x", "2x", "5x", "10x"])
        self.speed_combo.setCurrentIndex(1)  # Default to 1x
        controls_layout.addWidget(self.speed_combo, 0, 1)

        # Trail length
        controls_layout.addWidget(QLabel("Trail Length:"), 1, 0)
        self.trail_combo = QComboBox()
        self.trail_combo.addItems(["5 seconds", "10 seconds", "30 seconds", "1 minute", "Full"])
        self.trail_combo.setCurrentIndex(2)  # Default to 30 seconds
        controls_layout.addWidget(self.trail_combo, 1, 1)

        # Marker size
        controls_layout.addWidget(QLabel("Marker Size:"), 2, 0)
        self.marker_size_combo = QComboBox()
        self.marker_size_combo.addItems(["Small", "Medium", "Large"])
        self.marker_size_combo.setCurrentIndex(1)  # Default to Medium
        controls_layout.addWidget(self.marker_size_combo, 2, 1)

        layout.addWidget(controls_group)

        # Interpolation Settings group
        interp_group = QGroupBox("Path Interpolation")
        interp_layout = QGridLayout(interp_group)

        interp_layout.addWidget(QLabel("Method:"), 0, 0)
        self.interpolation_combo = QComboBox()
        self.interpolation_combo.addItems(["Linear", "Cubic", "Geodesic"])
        self.interpolation_combo.setCurrentIndex(0)  # Default to Linear
        interp_layout.addWidget(self.interpolation_combo, 0, 1)

        interp_layout.addWidget(QLabel("Interval:"), 1, 0)
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["0.5 seconds", "1 second", "2 seconds", "5 seconds"])
        self.interval_combo.setCurrentIndex(1)  # Default to 1 second
        interp_layout.addWidget(self.interval_combo, 1, 1)

        self.smooth_path_check = QCheckBox("Smooth path transitions")
        self.smooth_path_check.setChecked(True)
        interp_layout.addWidget(self.smooth_path_check, 2, 0, 1, 2)

        layout.addWidget(interp_group)

        layout.addStretch()
        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

        return tab

    def _create_colocation_settings_tab(self) -> QWidget:
        """Create co-location analysis settings tab"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)

        # Detection Parameters
        params_group = QGroupBox("Detection Parameters")
        params_layout = QGridLayout(params_group)

        params_layout.addWidget(QLabel("Detection Radius:"), 0, 0)
        self.coloc_radius_combo = QComboBox()
        self.coloc_radius_combo.addItems(["50 meters", "100 meters", "200 meters", "500 meters"])
        self.coloc_radius_combo.setCurrentIndex(0)
        params_layout.addWidget(self.coloc_radius_combo, 0, 1)

        params_layout.addWidget(QLabel("Time Window:"), 1, 0)
        self.coloc_window_combo = QComboBox()
        self.coloc_window_combo.addItems(["1 minute", "5 minutes", "15 minutes", "30 minutes"])
        self.coloc_window_combo.setCurrentIndex(1)
        params_layout.addWidget(self.coloc_window_combo, 1, 1)

        params_layout.addWidget(QLabel("Min Duration:"), 2, 0)
        self.coloc_duration_combo = QComboBox()
        self.coloc_duration_combo.addItems(["10 seconds", "30 seconds", "1 minute", "5 minutes"])
        self.coloc_duration_combo.setCurrentIndex(1)
        params_layout.addWidget(self.coloc_duration_combo, 2, 1)

        layout.addWidget(params_group)

        # Display Options
        display_group = QGroupBox("Display Options")
        display_layout = QVBoxLayout(display_group)

        self.highlight_coloc_check = QCheckBox("Highlight co-locations")
        self.highlight_coloc_check.setChecked(True)
        display_layout.addWidget(self.highlight_coloc_check)

        self.show_duration_check = QCheckBox("Show duration labels")
        self.show_duration_check.setChecked(True)
        display_layout.addWidget(self.show_duration_check)

        self.connect_lines_check = QCheckBox("Connect vehicles with lines")
        self.connect_lines_check.setChecked(False)
        display_layout.addWidget(self.connect_lines_check)

        self.generate_timeline_check = QCheckBox("Generate timeline view")
        self.generate_timeline_check.setChecked(True)
        display_layout.addWidget(self.generate_timeline_check)

        layout.addWidget(display_group)

        layout.addStretch()
        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

        return tab

    def _create_idle_settings_tab(self) -> QWidget:
        """Create idle detection settings tab"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)

        # Idle Parameters
        params_group = QGroupBox("Idle Detection Parameters")
        params_layout = QGridLayout(params_group)

        params_layout.addWidget(QLabel("Speed Threshold:"), 0, 0)
        self.idle_speed_spin = QDoubleSpinBox()
        self.idle_speed_spin.setRange(0.0, 20.0)
        self.idle_speed_spin.setValue(5.0)
        self.idle_speed_spin.setSuffix(" km/h")
        self.idle_speed_spin.setSingleStep(1.0)
        params_layout.addWidget(self.idle_speed_spin, 0, 1)

        params_layout.addWidget(QLabel("Min Duration:"), 1, 0)
        self.idle_duration_combo = QComboBox()
        self.idle_duration_combo.addItems(["30 seconds", "1 minute", "2 minutes", "5 minutes"])
        self.idle_duration_combo.setCurrentIndex(1)
        params_layout.addWidget(self.idle_duration_combo, 1, 1)

        self.include_stops_check = QCheckBox("Include stops at traffic lights")
        self.include_stops_check.setChecked(False)
        params_layout.addWidget(self.include_stops_check, 2, 0, 1, 2)

        self.merge_nearby_check = QCheckBox("Merge nearby idle periods")
        self.merge_nearby_check.setChecked(True)
        params_layout.addWidget(self.merge_nearby_check, 3, 0, 1, 2)

        layout.addWidget(params_group)

        # Visualization Options
        viz_group = QGroupBox("Visualization Options")
        viz_layout = QVBoxLayout(viz_group)

        self.mark_idle_check = QCheckBox("Mark idle locations")
        self.mark_idle_check.setChecked(True)
        viz_layout.addWidget(self.mark_idle_check)

        self.show_bubbles_check = QCheckBox("Show duration bubbles")
        self.show_bubbles_check.setChecked(True)
        viz_layout.addWidget(self.show_bubbles_check)

        self.heatmap_check = QCheckBox("Generate heat map overlay")
        self.heatmap_check.setChecked(False)
        viz_layout.addWidget(self.heatmap_check)

        self.idle_timeline_check = QCheckBox("Generate timeline view")
        self.idle_timeline_check.setChecked(True)
        viz_layout.addWidget(self.idle_timeline_check)

        layout.addWidget(viz_group)

        layout.addStretch()
        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

        return tab

    def _create_timejump_settings_tab(self) -> QWidget:
        """Create time jump analysis settings tab"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)

        # Jump Detection
        detect_group = QGroupBox("Time Jump Detection")
        detect_layout = QGridLayout(detect_group)

        detect_layout.addWidget(QLabel("Gap Threshold:"), 0, 0)
        self.gap_threshold_combo = QComboBox()
        self.gap_threshold_combo.addItems(["5 minutes", "15 minutes", "30 minutes", "1 hour"])
        self.gap_threshold_combo.setCurrentIndex(1)
        detect_layout.addWidget(self.gap_threshold_combo, 0, 1)

        self.highlight_gaps_check = QCheckBox("Highlight time gaps")
        self.highlight_gaps_check.setChecked(True)
        detect_layout.addWidget(self.highlight_gaps_check, 1, 0, 1, 2)

        self.show_gap_duration_check = QCheckBox("Show gap duration labels")
        self.show_gap_duration_check.setChecked(True)
        detect_layout.addWidget(self.show_gap_duration_check, 2, 0, 1, 2)

        self.connect_endpoints_check = QCheckBox("Connect gap endpoints")
        self.connect_endpoints_check.setChecked(True)
        detect_layout.addWidget(self.connect_endpoints_check, 3, 0, 1, 2)

        layout.addWidget(detect_group)

        # Analysis Options
        analysis_group = QGroupBox("Anomaly Analysis")
        analysis_layout = QGridLayout(analysis_group)

        self.calc_implied_speed_check = QCheckBox("Calculate implied speed")
        self.calc_implied_speed_check.setChecked(True)
        analysis_layout.addWidget(self.calc_implied_speed_check, 0, 0, 1, 2)

        self.flag_impossible_check = QCheckBox("Flag impossible speeds")
        self.flag_impossible_check.setChecked(True)
        analysis_layout.addWidget(self.flag_impossible_check, 1, 0, 1, 2)

        analysis_layout.addWidget(QLabel("Max Reasonable Speed:"), 2, 0)
        self.max_speed_spin = QSpinBox()
        self.max_speed_spin.setRange(50, 500)
        self.max_speed_spin.setValue(200)
        self.max_speed_spin.setSuffix(" km/h")
        analysis_layout.addWidget(self.max_speed_spin, 2, 1)

        layout.addWidget(analysis_group)

        layout.addStretch()
        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

        return tab

    def _create_route_settings_tab(self) -> QWidget:
        """Create route analysis settings tab (future implementation)"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        # Placeholder for future implementation
        placeholder_label = QLabel("Route Analysis - Coming Soon")
        placeholder_label.setAlignment(Qt.AlignCenter)
        placeholder_label.setStyleSheet("color: #6c757d; font-size: 14px; padding: 50px;")
        main_layout.addWidget(placeholder_label)

        return tab

    def _create_console_section(self) -> QGroupBox:
        """Create the output console section"""
        console_group = QGroupBox("Analysis Output")
        layout = QVBoxLayout(console_group)

        # Create custom console widget
        self.output_console = VehicleTrackingConsole()
        layout.addWidget(self.output_console)

        return console_group

    def _connect_signals(self):
        """Connect internal signals"""
        # File panel signals
        self.files_panel.files_changed.connect(self._on_files_changed)

        # Controller signals will be connected when operations start
        pass

    def _on_files_changed(self):
        """Handle files changed in panel"""
        self.selected_files = self.files_panel.get_selected_files()
        count = len(self.selected_files)

        if count == 0:
            self.file_count_label.setText("No CSV files selected")
            self.track_btn.setEnabled(False)
        else:
            vehicle_text = "vehicle" if count == 1 else "vehicles"
            self.file_count_label.setText(f"{count} {vehicle_text} ready for tracking")
            self.track_btn.setEnabled(True)

    def _on_analysis_tab_changed(self, index: int):
        """Handle analysis tab change"""
        tab_modes = [
            TrackingMode.ANIMATION,
            TrackingMode.COLOCATION,
            TrackingMode.IDLE,
            TrackingMode.TIMEJUMP,
            TrackingMode.ROUTE
        ]

        if 0 <= index < len(tab_modes):
            self.current_mode = tab_modes[index]
            self._update_ui_for_mode()

    def _update_ui_for_mode(self):
        """Update UI elements based on current mode"""
        # Update button text based on mode
        mode_labels = {
            TrackingMode.ANIMATION: "Track Vehicles",
            TrackingMode.COLOCATION: "Analyze Co-Locations",
            TrackingMode.IDLE: "Detect Idle Periods",
            TrackingMode.TIMEJUMP: "Find Time Jumps",
            TrackingMode.ROUTE: "Analyze Routes"
        }

        if not self.operation_active:
            self.track_btn.setText(f"🚀 {mode_labels.get(self.current_mode, 'Track Vehicles')}")

    def _add_files(self):
        """Add CSV files via file dialog"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select CSV Files",
            "",
            "CSV Files (*.csv);;All Files (*.*)"
        )

        if files:
            csv_files = [Path(f) for f in files if Path(f).suffix.lower() == '.csv']
            self.files_panel.add_files(csv_files)

    def _add_folder(self):
        """Add all CSV files from a folder"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder Containing CSV Files"
        )

        if folder:
            folder_path = Path(folder)
            csv_files = list(folder_path.glob("*.csv"))
            if csv_files:
                self.files_panel.add_files(csv_files)
            else:
                QMessageBox.information(
                    self,
                    "No CSV Files",
                    "No CSV files found in the selected folder."
                )

    def _clear_files(self):
        """Clear all selected files"""
        self.files_panel.clear_files()

    def _start_tracking(self):
        """Start vehicle tracking with selected analysis"""
        # Implementation will connect to controller
        self.output_console.append_message("Starting vehicle tracking...", "info")
        # TODO: Implement actual tracking logic

    def _open_map_window(self):
        """Open the map visualization window"""
        if self.last_results:
            self.map_window = VehicleMapWindow(self.last_results)
            self.map_window.show()

    def _export_results(self):
        """Export analysis results"""
        # TODO: Implement export functionality
        pass

    def _cancel_operation(self):
        """Cancel current operation"""
        if self.current_worker:
            self.current_worker.cancel()


class VehicleFilesPanel(QGroupBox):
    """Custom file panel for CSV vehicle files"""

    files_changed = Signal()

    def __init__(self, parent=None):
        super().__init__("Files & Folders", parent)

        self.files: List[Path] = []
        self.vehicle_colors = {}

        self._create_ui()

    def _create_ui(self):
        """Create the files panel UI"""
        layout = QVBoxLayout(self)

        # File list widget (simplified for now)
        self.file_list = QTextEdit()
        self.file_list.setReadOnly(True)
        self.file_list.setMaximumHeight(300)
        layout.addWidget(self.file_list)

        # Action buttons
        button_layout = QHBoxLayout()

        add_btn = QPushButton("Add Files")
        add_btn.clicked.connect(self._request_add_files)
        button_layout.addWidget(add_btn)

        add_folder_btn = QPushButton("Add Folder")
        add_folder_btn.clicked.connect(self._request_add_folder)
        button_layout.addWidget(add_folder_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        button_layout.addWidget(remove_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_files)
        button_layout.addWidget(clear_btn)

        layout.addLayout(button_layout)

    def add_files(self, files: List[Path]):
        """Add CSV files to the panel"""
        for file in files:
            if file not in self.files and file.suffix.lower() == '.csv':
                self.files.append(file)
                # Assign color
                color_index = len(self.files) - 1
                colors = list(VehicleColor)
                self.vehicle_colors[file] = colors[color_index % len(colors)]

        self._update_display()
        self.files_changed.emit()

    def clear_files(self):
        """Clear all files"""
        self.files.clear()
        self.vehicle_colors.clear()
        self._update_display()
        self.files_changed.emit()

    def get_selected_files(self) -> List[Path]:
        """Get list of selected files"""
        return self.files.copy()

    def _update_display(self):
        """Update the file list display"""
        self.file_list.clear()
        for i, file in enumerate(self.files):
            color = self.vehicle_colors.get(file, VehicleColor.BLUE)
            self.file_list.append(f"Vehicle {i+1} ({color.value}): {file.name}")

    def _request_add_files(self):
        """Request parent to add files"""
        # Parent will handle file dialog
        pass

    def _request_add_folder(self):
        """Request parent to add folder"""
        # Parent will handle folder dialog
        pass

    def _remove_selected(self):
        """Remove selected files"""
        # Simplified - remove last file
        if self.files:
            self.files.pop()
            self._update_display()
            self.files_changed.emit()


class VehicleTrackingConsole(QTextEdit):
    """Custom console for vehicle tracking output"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setReadOnly(True)
        self.setMaximumHeight(200)

        # Set dark background style
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #e8e8e8;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                border: 1px solid #3a3a3a;
            }
        """)

    def append_message(self, message: str, msg_type: str = "info"):
        """Append a message with formatting"""
        # Create format based on message type
        format = QTextCharFormat()

        if msg_type == "info":
            format.setForeground(QColor("#e8e8e8"))
        elif msg_type == "success":
            format.setForeground(QColor("#52c41a"))
        elif msg_type == "warning":
            format.setForeground(QColor("#faad14"))
        elif msg_type == "error":
            format.setForeground(QColor("#ff4d4f"))
        elif msg_type == "progress":
            format.setForeground(QColor("#4B9CD3"))

        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.append(f"[{timestamp}] {message}")


class VehicleMapWindow(QWidget):
    """Separate window for map visualization"""

    def __init__(self, tracking_results: VehicleTrackingResult, parent=None):
        super().__init__(parent)

        self.tracking_results = tracking_results
        self.setWindowTitle("Vehicle Tracking Map")
        self.resize(1200, 800)

        layout = QVBoxLayout(self)

        # Add the existing VehicleMapWidget
        self.map_widget = VehicleMapWidget()
        layout.addWidget(self.map_widget)

        # Load the tracking results
        if tracking_results and tracking_results.animation_data:
            self.map_widget.load_animation_data(tracking_results.animation_data)