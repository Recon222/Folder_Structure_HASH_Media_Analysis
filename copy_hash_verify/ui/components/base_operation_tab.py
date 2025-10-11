#!/usr/bin/env python3
"""
Base Operation Tab - Shared layout and functionality for operation tabs

Provides consistent splitter-based layout following media_analysis patterns:
- Left panel (45%): File selection
- Right panel (55%): Settings and controls
- Shared logger console at bottom
- Progress indicators
- Statistics display
"""

from typing import Optional, Tuple
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox,
    QLabel, QProgressBar, QGridLayout, QPushButton, QSizePolicy
)
from PySide6.QtGui import QFont

from .operation_log_console import OperationLogConsole


class BaseOperationTab(QWidget):
    """
    Base class for operation sub-tabs

    Provides:
    - Splitter-based layout (45/55 split)
    - Shared logger instance
    - Progress bar component
    - Statistics display component
    - Consistent styling
    """

    # Signals
    log_message = Signal(str)  # For external logging (main window)
    status_message = Signal(str)  # For status bar updates

    def __init__(
        self,
        tab_name: str,
        shared_logger: Optional[OperationLogConsole] = None,
        parent=None
    ):
        """
        Initialize base operation tab

        Args:
            tab_name: Name of this tab (for log prefixes)
            shared_logger: Shared logger instance (optional)
            parent: Parent widget
        """
        super().__init__(parent)

        self.tab_name = tab_name
        self.shared_logger = shared_logger
        self.operation_active = False

        # Will be set by subclasses
        self.left_panel = None
        self.right_panel = None
        self.main_splitter = None
        self.progress_bar = None
        self.progress_label = None
        self.stats_group = None

    def create_base_layout(self) -> Tuple[QWidget, QWidget]:
        """
        Create the base splitter layout

        Returns:
            Tuple of (left_panel_container, right_panel_container)
        """
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # Main content splitter (horizontal)
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)

        # Create panel containers
        left_container = QWidget()
        right_container = QWidget()

        self.main_splitter.addWidget(left_container)
        self.main_splitter.addWidget(right_container)

        # Set splitter proportions (45/55)
        self.main_splitter.setSizes([450, 550])

        layout.addWidget(self.main_splitter)

        return left_container, right_container

    def create_progress_section(self, parent_layout: QVBoxLayout):
        """
        Create progress bar section

        Args:
            parent_layout: Layout to add progress section to
        """
        progress_label = QLabel("📊 Operation Progress:")
        progress_label.setObjectName("sectionHeader")
        parent_layout.addWidget(progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMinimumHeight(28)
        parent_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setObjectName("mutedText")
        parent_layout.addWidget(self.progress_label)

    def create_stats_section(self) -> QGroupBox:
        """
        Create statistics display section (hidden by default)

        Returns:
            QGroupBox containing statistics
        """
        self.stats_group = QGroupBox("📊 Processing Statistics")
        layout = QGridLayout(self.stats_group)

        # Stat labels with Carolina Blue theme
        self.stat_total_label = QLabel("0")
        self.stat_total_label.setStyleSheet(
            "color: #4B9CD3; font-size: 24px; font-weight: bold;"
        )

        self.stat_success_label = QLabel("0")
        self.stat_success_label.setStyleSheet(
            "color: #52c41a; font-size: 24px; font-weight: bold;"
        )

        self.stat_failed_label = QLabel("0")
        self.stat_failed_label.setStyleSheet(
            "color: #ff4d4f; font-size: 24px; font-weight: bold;"
        )

        self.stat_speed_label = QLabel("0.0")
        self.stat_speed_label.setStyleSheet(
            "color: #4B9CD3; font-size: 24px; font-weight: bold;"
        )

        # Layout in grid - 2x2
        layout.addWidget(self.stat_total_label, 0, 0, Qt.AlignCenter)
        layout.addWidget(QLabel("Total Files"), 1, 0, Qt.AlignCenter)

        layout.addWidget(self.stat_success_label, 0, 1, Qt.AlignCenter)
        layout.addWidget(QLabel("Successful"), 1, 1, Qt.AlignCenter)

        layout.addWidget(self.stat_failed_label, 2, 0, Qt.AlignCenter)
        layout.addWidget(QLabel("Failed"), 3, 0, Qt.AlignCenter)

        layout.addWidget(self.stat_speed_label, 2, 1, Qt.AlignCenter)
        layout.addWidget(QLabel("MB/s"), 3, 1, Qt.AlignCenter)

        self.stats_group.setVisible(False)
        return self.stats_group

    def update_stats(
        self,
        total: int = 0,
        success: int = 0,
        failed: int = 0,
        speed: float = 0.0
    ):
        """
        Update statistics display

        Args:
            total: Total files processed
            success: Successful operations
            failed: Failed operations
            speed: Processing speed (MB/s)
        """
        if hasattr(self, 'stat_total_label'):
            self.stat_total_label.setText(str(total))
        if hasattr(self, 'stat_success_label'):
            self.stat_success_label.setText(str(success))
        if hasattr(self, 'stat_failed_label'):
            self.stat_failed_label.setText(str(failed))
        if hasattr(self, 'stat_speed_label'):
            self.stat_speed_label.setText(f"{speed:.1f}")

        if hasattr(self, 'stats_group'):
            self.stats_group.setVisible(True)

    def _log(self, level: str, message: str):
        """
        Log a message with color-coded formatting

        Args:
            level: Log level (INFO, SUCCESS, WARNING, ERROR)
            message: Message text
        """
        # Log to shared console if available
        if self.shared_logger:
            prefixed_message = f"[{self.tab_name}] {message}"
            self.shared_logger.log(level, prefixed_message)

        # Emit signal for main window logging
        self.log_message.emit(f"[{self.tab_name}] {message}")

    def info(self, message: str):
        """Log an INFO message"""
        self._log("INFO", message)

    def success(self, message: str):
        """Log a SUCCESS message"""
        self._log("SUCCESS", message)

    def warning(self, message: str):
        """Log a WARNING message"""
        self._log("WARNING", message)

    def error(self, message: str):
        """Log an ERROR message"""
        self._log("ERROR", message)

    def update_progress(self, percentage: int, message: str):
        """
        Update progress bar and label

        Args:
            percentage: Progress percentage (0-100)
            message: Status message
        """
        if self.progress_bar:
            self.progress_bar.setValue(percentage)
            self.progress_bar.setVisible(True)

        if self.progress_label:
            self.progress_label.setText(message)
            self.progress_label.setVisible(True)

        # Log significant progress milestones
        if percentage % 20 == 0 or percentage == 100:
            self.info(message)

    def set_operation_active(self, active: bool):
        """
        Set operation active state

        Args:
            active: Whether operation is active
        """
        self.operation_active = active

        # Update progress visibility
        if not active:
            if self.progress_bar:
                self.progress_bar.setVisible(False)
                self.progress_bar.setValue(0)
            if self.progress_label:
                self.progress_label.setVisible(False)
                self.progress_label.setText("")

        # Emit status
        if active:
            self.status_message.emit(f"{self.tab_name} operation in progress...")
        else:
            self.status_message.emit("Ready")

    def get_title_font(self) -> QFont:
        """Get title font"""
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        return font

    def get_section_font(self) -> QFont:
        """Get section header font"""
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        return font

    def cleanup(self):
        """Clean up resources (override in subclasses)"""
        pass
