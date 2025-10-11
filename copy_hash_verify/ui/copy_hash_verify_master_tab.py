#!/usr/bin/env python3
"""
Copy/Hash/Verify Master Tab - Container for all operation sub-tabs

This is the top-level tab that gets integrated into main window.

Features:
- Three operation sub-tabs (Calculate, Verify, Copy & Verify)
- Shared color-coded logger console
- Tab-based organization (like media analysis FFprobe/ExifTool pattern)
- Professional UI with consistent styling
"""

from typing import Optional

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QGroupBox, QSizePolicy
)

from .components.operation_log_console import OperationLogConsole
from .tabs.calculate_hashes_tab import CalculateHashesTab
from .tabs.verify_hashes_tab import VerifyHashesTab
from .tabs.copy_verify_operation_tab import CopyVerifyOperationTab
from core.logger import logger


class CopyHashVerifyMasterTab(QWidget):
    """
    Master tab container for Copy/Hash/Verify operations

    Integrates three operation types:
    1. Calculate Hashes - Single hash calculation with full settings
    2. Verify Hashes - Bidirectional verification
    3. Copy & Verify - Integrated copy with hash verification

    All sub-tabs share a common logger console at the bottom.
    """

    # Signals for main window integration
    log_message = Signal(str)
    status_message = Signal(str)

    def __init__(self, parent=None):
        """
        Initialize the master tab

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Create shared logger console
        self.shared_logger = OperationLogConsole(show_controls=True)

        # Sub-tab instances
        self.calculate_tab = None
        self.verify_tab = None
        self.copy_verify_tab = None

        # Tab widget
        self.tab_widget = None

        self._create_ui()
        self._connect_signals()

        # Log initial message
        self.shared_logger.info("Copy/Hash/Verify module ready. Select an operation to begin.")

    def _create_ui(self):
        """Create the master tab UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Create tab widget for sub-tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)

        # Create sub-tabs with shared logger
        self.calculate_tab = CalculateHashesTab(shared_logger=self.shared_logger)
        self.tab_widget.addTab(self.calculate_tab, "🔢 Calculate Hashes")

        self.verify_tab = VerifyHashesTab(shared_logger=self.shared_logger)
        self.tab_widget.addTab(self.verify_tab, "🔍 Verify Hashes")

        self.copy_verify_tab = CopyVerifyOperationTab(shared_logger=self.shared_logger)
        self.tab_widget.addTab(self.copy_verify_tab, "🔄 Copy & Verify")

        # Set size policy for proper expansion
        self.tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout.addWidget(self.tab_widget, stretch=7)  # 70% of height

        # Shared logger console at bottom
        console_group = QGroupBox("📋 Operation Console")
        console_layout = QVBoxLayout(console_group)
        console_layout.setContentsMargins(8, 8, 8, 8)

        self.shared_logger.setMaximumHeight(200)
        self.shared_logger.setMinimumHeight(150)
        console_layout.addWidget(self.shared_logger)

        layout.addWidget(console_group, stretch=3)  # 30% of height

    def _connect_signals(self):
        """Connect signals from sub-tabs to main window"""
        # Connect calculate tab signals
        self.calculate_tab.log_message.connect(self._on_log_message)
        self.calculate_tab.status_message.connect(self._on_status_message)

        # Connect verify tab signals
        self.verify_tab.log_message.connect(self._on_log_message)
        self.verify_tab.status_message.connect(self._on_status_message)

        # Connect copy/verify tab signals
        self.copy_verify_tab.log_message.connect(self._on_log_message)
        self.copy_verify_tab.status_message.connect(self._on_status_message)

        # Connect logger signals to main window
        self.shared_logger.message_logged.connect(self._on_logger_message)

    def _on_log_message(self, message: str):
        """
        Handle log message from sub-tab

        Args:
            message: Log message
        """
        # Emit to main window for global logging
        self.log_message.emit(message)
        logger.info(message)

    def _on_status_message(self, message: str):
        """
        Handle status message from sub-tab

        Args:
            message: Status message
        """
        # Emit to main window status bar
        self.status_message.emit(message)

    def _on_logger_message(self, level: str, message: str):
        """
        Handle message from shared logger

        Args:
            level: Log level
            message: Message text
        """
        # Already logged to console, just emit to main window
        self.log_message.emit(f"[{level}] {message}")

    def get_current_tab_name(self) -> str:
        """
        Get the name of the currently active sub-tab

        Returns:
            Name of active sub-tab
        """
        current_index = self.tab_widget.currentIndex()
        tab_names = ["Calculate Hashes", "Verify Hashes", "Copy & Verify"]
        return tab_names[current_index] if 0 <= current_index < len(tab_names) else "Unknown"

    def cancel_current_operation(self):
        """Cancel any running operation in the current sub-tab"""
        current_index = self.tab_widget.currentIndex()

        if current_index == 0:
            self.calculate_tab._cancel_operation()
        elif current_index == 1:
            self.verify_tab._cancel_operation()
        elif current_index == 2:
            self.copy_verify_tab._cancel_operation()

    def cleanup(self):
        """Clean up all sub-tabs"""
        logger.info("Cleaning up CopyHashVerifyMasterTab")

        # Clean up each sub-tab
        if self.calculate_tab:
            self.calculate_tab.cleanup()

        if self.verify_tab:
            self.verify_tab.cleanup()

        if self.copy_verify_tab:
            self.copy_verify_tab.cleanup()

        # Clear logger
        if self.shared_logger:
            self.shared_logger.clear()

        logger.info("CopyHashVerifyMasterTab cleanup complete")
