#!/usr/bin/env python3
"""
Operation Log Console - Color-coded logging component

Follows the media_analysis MediaAnalysisTab _log() pattern with HTML color coding
for professional operation logging with severity-based styling.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QFileDialog
from PySide6.QtGui import QFont


class OperationLogConsole(QWidget):
    """
    Professional color-coded log console for operations

    Features:
    - Color-coded log levels (INFO, SUCCESS, WARNING, ERROR)
    - Timestamp prefixes
    - HTML formatting for rich display
    - Export to text/HTML
    - Clear functionality
    """

    # Signal emitted when a message is logged
    message_logged = Signal(str, str)  # level, message

    def __init__(self, show_controls: bool = True, parent=None):
        """
        Initialize the operation log console

        Args:
            show_controls: Whether to show clear/export buttons
            parent: Parent widget
        """
        super().__init__(parent)

        self.show_controls = show_controls
        self._setup_ui()

    def _setup_ui(self):
        """Create the console UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Control buttons (optional)
        if self.show_controls:
            controls_layout = QHBoxLayout()
            controls_layout.addStretch()

            self.clear_btn = QPushButton("Clear")
            self.clear_btn.clicked.connect(self.clear)
            controls_layout.addWidget(self.clear_btn)

            self.export_btn = QPushButton("Export Log")
            self.export_btn.clicked.connect(self.export_log)
            controls_layout.addWidget(self.export_btn)

            layout.addLayout(controls_layout)

        # Console text widget with monospace font
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 9))

        # Set minimum height to ensure visibility
        self.console.setMinimumHeight(150)

        layout.addWidget(self.console)

    def log(self, level: str, message: str):
        """
        Log a message with color-coded formatting

        Args:
            level: Log level (INFO, SUCCESS, WARNING, ERROR)
            message: Message text
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Color palette matching media analysis tab
        colors = {
            "INFO": "#4B9CD3",      # Carolina Blue
            "SUCCESS": "#52c41a",   # Green
            "WARNING": "#faad14",   # Orange/Yellow
            "ERROR": "#ff4d4f"      # Red
        }

        color = colors.get(level, "#e8e8e8")

        # HTML formatting with spans for color
        formatted = (
            f'<span style="color: #6b6b6b;">{timestamp}</span> '
            f'<span style="color: {color}; font-weight: bold;">[{level}]</span> '
            f'{message}'
        )

        self.console.append(formatted)

        # Emit signal for external logging
        self.message_logged.emit(level, message)

    def info(self, message: str):
        """Log an INFO message"""
        self.log("INFO", message)

    def success(self, message: str):
        """Log a SUCCESS message"""
        self.log("SUCCESS", message)

    def warning(self, message: str):
        """Log a WARNING message"""
        self.log("WARNING", message)

    def error(self, message: str):
        """Log an ERROR message"""
        self.log("ERROR", message)

    def clear(self):
        """Clear the console"""
        self.console.clear()
        self.info("Console cleared")

    def export_log(self):
        """Export console log to file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Console Log",
            "",
            "Text Files (*.txt);;HTML Files (*.html);;All Files (*.*)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    if file_path.endswith('.html'):
                        f.write(self.console.toHtml())
                    else:
                        f.write(self.console.toPlainText())

                self.success(f"Log exported to: {Path(file_path).name}")
            except Exception as e:
                self.error(f"Failed to export log: {str(e)}")

    def get_text(self) -> str:
        """Get plain text content of console"""
        return self.console.toPlainText()

    def get_html(self) -> str:
        """Get HTML content of console"""
        return self.console.toHtml()

    def set_max_height(self, height: int):
        """Set maximum height for console"""
        self.console.setMaximumHeight(height)

    def set_min_height(self, height: int):
        """Set minimum height for console"""
        self.console.setMinimumHeight(height)
