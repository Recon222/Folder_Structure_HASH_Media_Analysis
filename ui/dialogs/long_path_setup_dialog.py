"""
Long Path Setup Dialog

User-friendly dialog to help users enable Windows long path support.
Shows status, offers automatic enablement (if admin), or provides clear
manual instructions.

Author: Claude Code
Created: 2025-10-05
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.windows_long_path_manager import WindowsLongPathManager
from core.settings_manager import SettingsManager
from core.logger import logger


class LongPathSetupDialog(QDialog):
    """
    Dialog to guide users through enabling Windows long path support.

    Provides:
    - Status detection
    - Automatic enablement (if admin rights available)
    - Clear manual instructions
    - "Don't show again" option
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = WindowsLongPathManager()
        self.settings = SettingsManager()
        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("Windows Long Path Support")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        layout = QVBoxLayout(self)

        # Title and explanation
        title = QLabel("Windows Long Path Support Setup")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        explanation = QLabel(
            "Windows has a 260-character path limit by default. This can cause issues\n"
            "when processing forensic evidence with deep folder structures.\n\n"
            "Enabling long path support removes this limitation."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        # Status group
        status_group = self._create_status_group()
        layout.addWidget(status_group)

        # Instructions group
        instructions_group = self._create_instructions_group()
        layout.addWidget(instructions_group)

        # Action buttons
        button_layout = self._create_button_layout()
        layout.addLayout(button_layout)

        # Don't show again checkbox
        self.dont_show_checkbox = QCheckBox("Don't show this message again")
        self.dont_show_checkbox.setToolTip(
            "You can re-enable this check in Settings → Performance"
        )
        layout.addWidget(self.dont_show_checkbox)

    def _create_status_group(self) -> QGroupBox:
        """Create status information group."""
        group = QGroupBox("Current Status")
        layout = QVBoxLayout(group)

        status = self.manager.get_status_summary()

        # Status message with icon
        status_label = QLabel()
        if status['is_enabled']:
            status_label.setText("✓ Long path support is ENABLED")
            status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            status_label.setText("✗ Long path support is DISABLED")
            status_label.setStyleSheet("color: red; font-weight: bold;")

        layout.addWidget(status_label)

        # Additional info
        info_text = []
        if status['is_admin']:
            info_text.append("• Running with administrator privileges")
        else:
            info_text.append("• Running without administrator privileges")

        if not status['is_enabled']:
            info_text.append("• Some operations may fail with long file paths")
            info_text.append("• Maximum path length limited to 260 characters")

        info_label = QLabel("\n".join(info_text))
        layout.addWidget(info_label)

        return group

    def _create_instructions_group(self) -> QGroupBox:
        """Create manual instructions group."""
        group = QGroupBox("Setup Instructions")
        layout = QVBoxLayout(group)

        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setPlainText(self.manager.get_manual_enable_instructions())
        instructions.setMinimumHeight(200)

        layout.addWidget(instructions)

        return group

    def _create_button_layout(self) -> QHBoxLayout:
        """Create action button layout."""
        layout = QHBoxLayout()

        status = self.manager.get_status_summary()

        # Auto-enable button (only if admin and not already enabled)
        if status['can_auto_enable']:
            auto_btn = QPushButton("Enable Automatically")
            auto_btn.setToolTip("Requires administrator privileges")
            auto_btn.clicked.connect(self._auto_enable)
            layout.addWidget(auto_btn)

        # Test button
        test_btn = QPushButton("Recheck Status")
        test_btn.clicked.connect(self._recheck_status)
        layout.addWidget(test_btn)

        layout.addStretch()

        # Close button
        close_btn = QPushButton("Close" if status['is_enabled'] else "Skip for Now")
        close_btn.clicked.connect(self._close_dialog)
        layout.addWidget(close_btn)

        return layout

    def _auto_enable(self):
        """Attempt to automatically enable long path support."""
        reply = QMessageBox.question(
            self,
            "Enable Long Path Support?",
            "This will modify the Windows registry to enable long path support.\n\n"
            "Administrator privileges are required.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success, message = self.manager.enable_long_paths()

            if success:
                QMessageBox.information(
                    self,
                    "Success",
                    "Long path support has been enabled successfully!\n\n"
                    "You may need to restart the application for changes to take effect."
                )
                self._recheck_status()
            else:
                QMessageBox.warning(
                    self,
                    "Failed",
                    f"Could not enable long path support:\n\n{message}\n\n"
                    "Please follow the manual instructions below."
                )

    def _recheck_status(self):
        """Recheck the long path status and update UI."""
        # Recreate the dialog to refresh all status displays
        self.close()
        new_dialog = LongPathSetupDialog(self.parent())
        new_dialog.exec()

    def _close_dialog(self):
        """Close dialog and save preference if requested."""
        if self.dont_show_checkbox.isChecked():
            self.settings.set("performance/suppress_long_path_warning", True)
            logger.info("Long path warning suppressed by user")

        self.accept()

    @staticmethod
    def should_show_dialog() -> bool:
        """
        Determine if the dialog should be shown.

        Returns:
            True if dialog should be shown, False otherwise
        """
        settings = SettingsManager()

        # Check if user has suppressed this warning
        if settings.get("performance/suppress_long_path_warning", False):
            return False

        # Check if long paths are already enabled
        if WindowsLongPathManager.is_long_paths_enabled():
            return False

        # Check if running on Windows
        if not WindowsLongPathManager.is_windows():
            return False

        # Show dialog
        return True

    @staticmethod
    def show_if_needed(parent=None) -> bool:
        """
        Show dialog only if needed (paths disabled and not suppressed).

        Args:
            parent: Parent widget

        Returns:
            True if long paths are enabled (or not Windows), False otherwise
        """
        if not LongPathSetupDialog.should_show_dialog():
            # Either already enabled or user suppressed warning
            return WindowsLongPathManager.is_long_paths_enabled()

        # Show the dialog
        dialog = LongPathSetupDialog(parent)
        dialog.exec()

        # Return current status after dialog closes
        return WindowsLongPathManager.is_long_paths_enabled()
