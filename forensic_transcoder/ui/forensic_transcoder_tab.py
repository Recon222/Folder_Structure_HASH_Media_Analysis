"""
Forensic Transcoder Tab - Main UI Component

Main tab widget for the forensic video transcoder feature.
Coordinates between UI panels, controllers, and user interactions.
"""

from pathlib import Path
from typing import Optional, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget,
    QLabel, QProgressBar, QTextEdit, QSplitter, QFileDialog,
    QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..models.transcode_settings import TranscodeSettings, QualityPreset
from ..models.concatenate_settings import ConcatenateSettings
from ..models.processing_result import ProcessingResult, BatchProcessingStatistics
from ..controllers.transcoder_controller import TranscoderController
from ..controllers.concatenate_controller import ConcatenateController


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
    log_message = pyqtSignal(str)  # For error/info logging to main window
    
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
        
        # State
        self.selected_files: List[Path] = []
        self.current_command: Optional[str] = None
        self.is_processing = False
        
        # Build UI
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        
        # === Top Section: File Selection ===
        file_section = self._create_file_section()
        layout.addLayout(file_section)
        
        # === Middle Section: Tabbed Settings ===
        self.settings_tabs = QTabWidget()
        
        # Transcode settings tab (placeholder for now)
        transcode_widget = QWidget()
        transcode_layout = QVBoxLayout(transcode_widget)
        transcode_layout.addWidget(QLabel("Transcode Settings (To be implemented)"))
        self.settings_tabs.addTab(transcode_widget, "Transcode")
        
        # Concatenate settings tab (placeholder for now)
        concat_widget = QWidget()
        concat_layout = QVBoxLayout(concat_widget)
        concat_layout.addWidget(QLabel("Concatenate Settings (To be implemented)"))
        self.settings_tabs.addTab(concat_widget, "Concatenate")
        
        layout.addWidget(self.settings_tabs)
        
        # === Command Terminal Section ===
        command_section = self._create_command_section()
        layout.addWidget(command_section)
        
        # === Progress Section ===
        progress_section = self._create_progress_section()
        layout.addWidget(progress_section)
        
        # === Action Buttons ===
        button_section = self._create_button_section()
        layout.addLayout(button_section)
    
    def _create_file_section(self) -> QHBoxLayout:
        """Create file selection section."""
        layout = QHBoxLayout()
        
        self.file_count_label = QLabel("No files selected")
        layout.addWidget(self.file_count_label)
        
        layout.addStretch()
        
        self.select_files_btn = QPushButton("Select Files")
        self.select_files_btn.clicked.connect(self._on_select_files)
        layout.addWidget(self.select_files_btn)
        
        self.clear_files_btn = QPushButton("Clear")
        self.clear_files_btn.clicked.connect(self._on_clear_files)
        self.clear_files_btn.setEnabled(False)
        layout.addWidget(self.clear_files_btn)
        
        return layout
    
    def _create_command_section(self) -> QWidget:
        """Create FFmpeg command preview/edit section."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(QLabel("FFmpeg Command:"))
        
        self.command_display = QTextEdit()
        self.command_display.setMaximumHeight(150)
        self.command_display.setReadOnly(False)  # Editable
        self.command_display.setPlaceholderText(
            "FFmpeg command will appear here after you configure settings.\n"
            "You can edit the command before executing."
        )
        layout.addWidget(self.command_display)
        
        # Command validation status
        self.command_status_label = QLabel("")
        layout.addWidget(self.command_status_label)
        
        return widget
    
    def _create_progress_section(self) -> QWidget:
        """Create progress tracking section."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.progress_label = QLabel("Ready")
        layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        return widget
    
    def _create_button_section(self) -> QHBoxLayout:
        """Create action buttons section."""
        layout = QHBoxLayout()
        
        layout.addStretch()
        
        self.build_command_btn = QPushButton("Build Command")
        self.build_command_btn.clicked.connect(self._on_build_command)
        self.build_command_btn.setEnabled(False)
        layout.addWidget(self.build_command_btn)
        
        self.start_btn = QPushButton("Start Processing")
        self.start_btn.clicked.connect(self._on_start_processing)
        self.start_btn.setEnabled(False)
        layout.addWidget(self.start_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.cancel_btn.setEnabled(False)
        layout.addWidget(self.cancel_btn)
        
        return layout
    
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
        # TODO: Build FFmpeg command from current settings
        # This will be implemented when settings widgets are added
        self.log_message.emit("Build command functionality to be implemented")
    
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
    
    # === Processing Methods (Delegate to controllers) ===
    
    def _start_transcode(self):
        """Start transcode operation via controller."""
        try:
            # Create default settings (will be replaced with actual settings from UI)
            settings = TranscodeSettings(
                output_format='mp4',
                video_codec='libx264',
                quality_preset=QualityPreset.HIGH_FORENSIC
            )
            
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
            
            # Create default settings (will be replaced with actual settings from UI)
            settings = ConcatenateSettings(
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
        
        if count == 0:
            self.file_count_label.setText("No files selected")
            self.clear_files_btn.setEnabled(False)
            self.build_command_btn.setEnabled(False)
        else:
            self.file_count_label.setText(f"{count} file(s) selected")
            self.clear_files_btn.setEnabled(True)
            self.build_command_btn.setEnabled(True)
    
    def _set_processing_state(self, is_processing: bool):
        """Update UI for processing state."""
        self.is_processing = is_processing
        
        # Disable inputs during processing
        self.select_files_btn.setEnabled(not is_processing)
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
