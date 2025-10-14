"""
Forensic Transcoder Tab - Main UI Component

Main tab widget for the forensic video transcoder feature.
Coordinates between UI panels, controllers, and user interactions.
"""

from pathlib import Path
from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget,
    QLabel, QProgressBar, QTextEdit, QSplitter, QFileDialog,
    QMessageBox, QGroupBox, QTreeWidget, QTreeWidgetItem,
    QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from ..models.transcode_settings import TranscodeSettings, QualityPreset
from ..models.concatenate_settings import ConcatenateSettings
from ..models.processing_result import ProcessingResult, BatchProcessingStatistics
from ..controllers.transcoder_controller import TranscoderController
from ..controllers.concatenate_controller import ConcatenateController
from .transcode_settings_widget import TranscodeSettingsWidget
from .concatenate_settings_widget import ConcatenateSettingsWidget
from ..services.ffmpeg_command_builder import FFmpegCommandBuilder
from ..services.video_analyzer_service import VideoAnalyzerService


class ForensicTranscoderTab(QWidget):
    """
    Main tab widget for forensic video transcoding.
    
    Provides UI for:
    - File selection
    - Transcode settings configuration
    - Concatenation settings configuration
    - FFmpeg command preview/editing
    - Progress tracking
    - Result display
    
    This is a pure UI coordinator - contains NO business logic.
    All processing is delegated to controllers.
    """
    
    # Signals for main window integration
    log_message = Signal(str)  # For error/info logging to main window
    
    def __init__(self, parent=None):
        """
        Initialize the Forensic Transcoder tab.
        
        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        
        # Controllers (business logic layer)
        self.transcoder_controller = TranscoderController(self)
        self.concatenate_controller = ConcatenateController(self)

        # Services for command building
        self.command_builder = FFmpegCommandBuilder()
        self.analyzer = VideoAnalyzerService()

        # State
        self.selected_files: List[Path] = []
        self.current_command: Optional[str] = None
        self.is_processing = False
        
        # Build UI
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """Initialize the user interface with clean two-panel layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # Main content splitter (horizontal: left panel | right panel)
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

        # FFmpeg Command section (collapsible)
        command_group = self._create_command_section()
        layout.addWidget(command_group)

        # Console section (collapsible)
        console_group = self._create_console_section()
        layout.addWidget(console_group)
    
    def _create_file_panel(self) -> QGroupBox:
        """Create left panel for video file selection."""
        panel = QGroupBox("📁 Video Files to Process")
        layout = QVBoxLayout(panel)

        # File selection buttons
        button_layout = QHBoxLayout()

        self.add_files_btn = QPushButton("📄 Add Files")
        self.add_files_btn.clicked.connect(self._on_select_files)
        button_layout.addWidget(self.add_files_btn)

        self.clear_files_btn = QPushButton("🗑️ Clear")
        self.clear_files_btn.clicked.connect(self._on_clear_files)
        self.clear_files_btn.setEnabled(False)
        button_layout.addWidget(self.clear_files_btn)

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

        return panel

    def _create_settings_panel(self) -> QGroupBox:
        """Create right panel for processing settings with scrollable tab-based layout."""
        panel = QGroupBox("Processing Settings")
        main_layout = QVBoxLayout(panel)
        main_layout.setSpacing(8)

        # Create tab widget for Transcode vs Concatenate
        self.settings_tabs = QTabWidget()

        # Tab 1: Transcode Settings (with scroll area)
        transcode_tab = self._create_transcode_tab()
        self.settings_tabs.addTab(transcode_tab, "🎬 Transcode")

        # Tab 2: Concatenate Settings (with scroll area)
        concatenate_tab = self._create_concatenate_tab()
        self.settings_tabs.addTab(concatenate_tab, "🔗 Concatenate")

        # Connect tab change signal for dynamic button swapping
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
        self._create_transcode_buttons()
        self._create_concatenate_buttons()

        # Show transcode buttons by default
        self._show_transcode_buttons()

        return panel

    def _create_transcode_tab(self) -> QWidget:
        """Create transcode settings tab with scroll area."""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area for settings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        # Transcode settings widget
        self.transcode_settings = TranscodeSettingsWidget()
        scroll_area.setWidget(self.transcode_settings)
        main_layout.addWidget(scroll_area)

        return tab

    def _create_concatenate_tab(self) -> QWidget:
        """Create concatenate settings tab with scroll area."""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area for settings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        # Concatenate settings widget
        self.concatenate_settings = ConcatenateSettingsWidget()
        scroll_area.setWidget(self.concatenate_settings)
        main_layout.addWidget(scroll_area)

        return tab

    def _create_command_section(self) -> QGroupBox:
        """Create collapsible FFmpeg command preview/edit section."""
        group = QGroupBox("📺 FFmpeg Command")
        layout = QVBoxLayout(group)

        # Command text widget
        self.command_display = QTextEdit()
        self.command_display.setMinimumHeight(80)
        self.command_display.setMaximumHeight(150)
        self.command_display.setFont(QFont("Consolas", 9))
        self.command_display.setReadOnly(False)  # Editable
        self.command_display.setPlaceholderText(
            "FFmpeg command will appear here after you configure settings.\n"
            "You can edit the command before executing."
        )
        layout.addWidget(self.command_display)

        # Command validation status
        self.command_status_label = QLabel("")
        layout.addWidget(self.command_status_label)

        return group

    def _create_console_section(self) -> QGroupBox:
        """Create collapsible console log display."""
        group = QGroupBox("📋 Processing Console")
        layout = QVBoxLayout(group)

        # Console text widget
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(100)
        self.console.setMaximumHeight(200)
        self.console.setFont(QFont("Consolas", 9))
        layout.addWidget(self.console)

        # Initial message
        self._log("INFO", "Forensic Transcoder ready. Select video files to begin.")

        return group

    def _create_transcode_buttons(self):
        """Create button set for Transcode tab."""
        self.transcode_button_widget = QWidget()
        layout = QVBoxLayout(self.transcode_button_widget)
        layout.setContentsMargins(0, 10, 0, 0)

        # Primary action buttons
        primary_layout = QHBoxLayout()

        self.build_command_btn = QPushButton("🔨 Build Command")
        self.build_command_btn.clicked.connect(self._on_build_command)
        self.build_command_btn.setEnabled(False)
        self.build_command_btn.setMinimumHeight(36)
        primary_layout.addWidget(self.build_command_btn)

        self.start_btn = QPushButton("▶️ Start Processing")
        self.start_btn.setObjectName("primaryAction")
        self.start_btn.clicked.connect(self._on_start_processing)
        self.start_btn.setEnabled(False)
        self.start_btn.setMinimumHeight(36)
        primary_layout.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("⏹️ Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setMinimumHeight(36)
        primary_layout.addWidget(self.cancel_btn)

        layout.addLayout(primary_layout)

    def _create_concatenate_buttons(self):
        """Create button set for Concatenate tab."""
        self.concatenate_button_widget = QWidget()
        layout = QHBoxLayout(self.concatenate_button_widget)
        layout.setContentsMargins(0, 10, 0, 0)

        self.concat_build_btn = QPushButton("🔨 Build Concat Command")
        self.concat_build_btn.clicked.connect(self._on_build_command)
        self.concat_build_btn.setEnabled(False)
        self.concat_build_btn.setMinimumHeight(36)
        layout.addWidget(self.concat_build_btn)

        self.concat_start_btn = QPushButton("🔗 Start Concatenation")
        self.concat_start_btn.setObjectName("primaryAction")
        self.concat_start_btn.clicked.connect(self._on_start_processing)
        self.concat_start_btn.setEnabled(False)
        self.concat_start_btn.setMinimumHeight(36)
        layout.addWidget(self.concat_start_btn)

        self.concat_cancel_btn = QPushButton("⏹️ Cancel")
        self.concat_cancel_btn.clicked.connect(self._on_cancel)
        self.concat_cancel_btn.setEnabled(False)
        self.concat_cancel_btn.setMinimumHeight(36)
        layout.addWidget(self.concat_cancel_btn)

    def _show_transcode_buttons(self):
        """Show transcode buttons, hide concatenate buttons."""
        # Clear layout
        while self.action_button_layout.count():
            child = self.action_button_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)

        # Add transcode buttons
        self.action_button_layout.addWidget(self.transcode_button_widget)
        self.transcode_button_widget.setVisible(True)
        if hasattr(self, 'concatenate_button_widget'):
            self.concatenate_button_widget.setVisible(False)

    def _show_concatenate_buttons(self):
        """Show concatenate buttons, hide transcode buttons."""
        # Clear layout
        while self.action_button_layout.count():
            child = self.action_button_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)

        # Add concatenate buttons
        self.action_button_layout.addWidget(self.concatenate_button_widget)
        self.concatenate_button_widget.setVisible(True)
        if hasattr(self, 'transcode_button_widget'):
            self.transcode_button_widget.setVisible(False)

    def _on_settings_tab_changed(self, index: int):
        """Handle settings tab change to swap action buttons."""
        if index == 0:  # Transcode tab
            self._show_transcode_buttons()
        elif index == 1:  # Concatenate tab
            self._show_concatenate_buttons()

    def _rebuild_file_tree(self):
        """Rebuild file tree from selected_files with hierarchical folder structure."""
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

    def _log(self, level: str, message: str):
        """Log message to console."""
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
        self.log_message.emit(f"[Transcoder] {message}")

    def _connect_signals(self):
        """Connect controller signals to UI handlers."""
        # Transcode controller signals
        self.transcoder_controller.progress_update.connect(self._on_progress_update)
        self.transcoder_controller.transcode_complete.connect(self._on_transcode_complete)
        self.transcoder_controller.transcode_error.connect(self._on_error)
        
        # Concatenate controller signals
        self.concatenate_controller.progress_update.connect(self._on_progress_update)
        self.concatenate_controller.concatenate_complete.connect(self._on_concatenate_complete)
        self.concatenate_controller.concatenate_error.connect(self._on_error)
    
    # === UI Event Handlers (No business logic) ===
    
    def _on_select_files(self):
        """Handle file selection button click."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Video Files",
            "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.ts);;All Files (*.*)"
        )
        
        if files:
            self.selected_files = [Path(f) for f in files]
            self._update_file_selection_ui()
    
    def _on_clear_files(self):
        """Handle clear files button click."""
        self.selected_files = []
        self._update_file_selection_ui()
    
    def _on_build_command(self):
        """Handle build command button click."""
        if not self.selected_files:
            QMessageBox.warning(self, "No Files", "Please select files to process.")
            return

        try:
            # Determine which tab is active
            current_tab = self.settings_tabs.currentIndex()

            if current_tab == 0:  # Transcode tab
                self._build_transcode_command()
            elif current_tab == 1:  # Concatenate tab
                self._build_concatenate_command()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to build command: {e}")
            self.log_message.emit(f"Command build error: {e}")
    
    def _on_start_processing(self):
        """Handle start processing button click."""
        if not self.selected_files:
            QMessageBox.warning(self, "No Files", "Please select files to process.")
            return
        
        # Determine which tab is active
        current_tab = self.settings_tabs.currentIndex()
        
        if current_tab == 0:  # Transcode tab
            self._start_transcode()
        elif current_tab == 1:  # Concatenate tab
            self._start_concatenate()
    
    def _on_cancel(self):
        """Handle cancel button click."""
        if self.transcoder_controller.is_running():
            self.transcoder_controller.cancel_transcode()
        elif self.concatenate_controller.is_running():
            self.concatenate_controller.cancel_concatenate()
        
        self.log_message.emit("Cancellation requested...")

    # === Command Building Methods ===

    def _build_transcode_command(self):
        """Build FFmpeg command for transcode operation."""
        # Get settings from widget
        settings = self.transcode_settings.get_settings()

        # Use first file as example (for single file or batch)
        input_file = self.selected_files[0]

        # Generate output path
        if settings.output_directory:
            output_dir = settings.output_directory
        else:
            output_dir = input_file.parent

        output_filename = settings.output_filename_pattern.format(
            original_name=input_file.stem,
            ext=settings.output_format
        )
        output_file = output_dir / output_filename

        # Analyze input (optional but helpful)
        try:
            analysis = self.analyzer.analyze_video(input_file)
        except Exception:
            analysis = None

        # Build command
        cmd_array, cmd_string = self.command_builder.build_transcode_command(
            input_file=input_file,
            output_file=output_file,
            settings=settings,
            input_analysis=analysis
        )

        # Display command
        self.command_display.setPlainText(cmd_string)
        self.current_command = cmd_string
        self.command_status_label.setText("✓ Command built successfully")
        self.command_status_label.setStyleSheet("color: green;")

        # Enable start button
        if not self.is_processing:
            self.start_btn.setEnabled(True)

        self.log_message.emit("Transcode command built successfully")

    def _build_concatenate_command(self):
        """Build FFmpeg command for concatenate operation."""
        if len(self.selected_files) < 2:
            QMessageBox.warning(
                self,
                "Insufficient Files",
                "At least 2 files are required for concatenation."
            )
            return

        # Get output file from user
        output_file, _ = QFileDialog.getSaveFileName(
            self,
            "Save Concatenated Video",
            "",
            "Video Files (*.mp4 *.mkv *.mov);;All Files (*.*)"
        )

        if not output_file:
            return

        # Get settings from widget
        settings = self.concatenate_settings.get_settings(
            input_files=self.selected_files,
            output_file=Path(output_file)
        )

        # Analyze inputs
        try:
            analyses = self.analyzer.analyze_batch(self.selected_files)
        except Exception:
            analyses = []

        if len(analyses) != len(self.selected_files):
            QMessageBox.warning(
                self,
                "Analysis Failed",
                "Failed to analyze one or more input files. Command may be incomplete."
            )

        # Build command
        cmd_array, cmd_string = self.command_builder.build_concatenate_command(
            settings=settings,
            analyses=analyses
        )

        # Display command
        self.command_display.setPlainText(cmd_string)
        self.current_command = cmd_string
        self.command_status_label.setText("✓ Command built successfully")
        self.command_status_label.setStyleSheet("color: green;")

        # Enable start button
        if not self.is_processing:
            self.start_btn.setEnabled(True)

        self.log_message.emit("Concatenate command built successfully")

    # === Processing Methods (Delegate to controllers) ===
    
    def _start_transcode(self):
        """Start transcode operation via controller."""
        try:
            # Get settings from widget
            settings = self.transcode_settings.get_settings()

            # Update UI state
            self._set_processing_state(True)

            # Start transcode via controller
            self.transcoder_controller.start_transcode(
                input_files=self.selected_files,
                settings=settings
            )

            self.log_message.emit(f"Started transcoding {len(self.selected_files)} file(s)")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start transcode: {e}")
            self._set_processing_state(False)
    
    def _start_concatenate(self):
        """Start concatenate operation via controller."""
        try:
            if len(self.selected_files) < 2:
                QMessageBox.warning(
                    self,
                    "Insufficient Files",
                    "At least 2 files are required for concatenation."
                )
                return

            # Get output file
            output_file, _ = QFileDialog.getSaveFileName(
                self,
                "Save Concatenated Video",
                "",
                "Video Files (*.mp4 *.mkv *.mov);;All Files (*.*)"
            )

            if not output_file:
                return

            # Get settings from widget
            settings = self.concatenate_settings.get_settings(
                input_files=self.selected_files,
                output_file=Path(output_file)
            )

            # Update UI state
            self._set_processing_state(True)

            # Start concatenate via controller
            self.concatenate_controller.start_concatenate(settings=settings)

            self.log_message.emit(f"Started concatenating {len(self.selected_files)} file(s)")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start concatenation: {e}")
            self._set_processing_state(False)
    
    # === Controller Signal Handlers (Update UI only) ===
    
    def _on_progress_update(self, percentage: float, message: str):
        """Handle progress update from controller."""
        self.progress_bar.setValue(int(percentage))
        self.progress_label.setText(message)
    
    def _on_transcode_complete(self, result):
        """Handle transcode completion from controller."""
        self._set_processing_state(False)
        
        if isinstance(result, ProcessingResult):
            # Single file result
            if result.is_success:
                QMessageBox.information(
                    self,
                    "Success",
                    f"Transcode completed successfully!\n\n"
                    f"Output: {result.output_file}\n"
                    f"Duration: {result.duration_formatted}\n"
                    f"Speed: {result.encoding_speed:.2f}x" if result.encoding_speed else ""
                )
            else:
                QMessageBox.warning(
                    self,
                    "Failed",
                    f"Transcode failed: {result.error_message}"
                )
        
        elif isinstance(result, BatchProcessingStatistics):
            # Batch results
            QMessageBox.information(
                self,
                "Batch Complete",
                f"Batch processing completed!\n\n"
                f"Total files: {result.total_files}\n"
                f"Successful: {result.successful}\n"
                f"Failed: {result.failed}\n"
                f"Success rate: {result.success_rate:.1f}%"
            )
        
        self.log_message.emit("Transcode operation completed")
    
    def _on_concatenate_complete(self, result: ProcessingResult):
        """Handle concatenation completion from controller."""
        self._set_processing_state(False)
        
        if result.is_success:
            QMessageBox.information(
                self,
                "Success",
                f"Concatenation completed successfully!\n\n"
                f"Output: {result.output_file}\n"
                f"Duration: {result.duration_formatted}"
            )
        else:
            QMessageBox.warning(
                self,
                "Failed",
                f"Concatenation failed: {result.error_message}"
            )
        
        self.log_message.emit("Concatenation operation completed")
    
    def _on_error(self, error_message: str):
        """Handle error from controller."""
        self._set_processing_state(False)
        QMessageBox.critical(self, "Error", error_message)
        self.log_message.emit(f"Error: {error_message}")
    
    # === UI State Management (Pure UI updates) ===
    
    def _update_file_selection_ui(self):
        """Update UI based on selected files."""
        count = len(self.selected_files)

        # Rebuild file tree
        self._rebuild_file_tree()

        if count == 0:
            self.file_count_label.setText("No files selected")
            self.clear_files_btn.setEnabled(False)
            self.build_command_btn.setEnabled(False)
            self.concat_build_btn.setEnabled(False)
        else:
            self.file_count_label.setText(f"{count} file{'s' if count != 1 else ''} selected")
            self.clear_files_btn.setEnabled(True)
            self.build_command_btn.setEnabled(True)
            self.concat_build_btn.setEnabled(True)
    
    def _set_processing_state(self, is_processing: bool):
        """Update UI for processing state."""
        self.is_processing = is_processing

        # Disable inputs during processing
        self.add_files_btn.setEnabled(not is_processing)
        self.clear_files_btn.setEnabled(not is_processing and len(self.selected_files) > 0)
        self.build_command_btn.setEnabled(not is_processing and len(self.selected_files) > 0)
        self.settings_tabs.setEnabled(not is_processing)
        
        # Toggle start/cancel buttons
        self.start_btn.setEnabled(not is_processing and len(self.selected_files) > 0)
        self.cancel_btn.setEnabled(is_processing)
        
        # Reset progress if starting
        if is_processing:
            self.progress_bar.setValue(0)
            self.progress_label.setText("Starting...")
        else:
            self.progress_label.setText("Ready")
