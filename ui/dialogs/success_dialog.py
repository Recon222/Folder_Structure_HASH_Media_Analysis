#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Success Dialog - Modal dialog for displaying operation success messages
with rich formatting and Carolina Blue theme integration.
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QTextEdit, QApplication)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon, QPalette
from ui.styles.carolina_blue import CarolinaBlueTheme


class SuccessDialog(QDialog):
    """
    Modal success dialog for displaying rich operation completion messages.
    
    Features:
    - Modal blocking behavior (user must acknowledge)
    - Carolina Blue theme integration
    - Rich text formatting with performance stats
    - Automatic center screen positioning
    - Large, readable success display
    - Clean interface without technical clutter
    """
    
    def __init__(self, title: str = "Operation Complete!", 
                 message: str = "", 
                 details: str = "",
                 parent=None):
        """
        Initialize success dialog.
        
        Args:
            title: Dialog title (e.g., "Forensic Processing Complete!")
            message: Main success message with rich formatting
            details: Additional details like output location
            parent: Parent widget for centering
        """
        super().__init__(parent)
        
        self.title = title
        self.message = message  
        self.details = details
        
        self._setup_dialog()
        self._setup_ui()
        self._apply_theme()
        self._center_on_screen()
        
    def _setup_dialog(self):
        """Configure dialog window properties"""
        self.setWindowTitle(self.title)
        self.setModal(True)  # Block interaction with parent
        self.setWindowFlags(
            Qt.Dialog | 
            Qt.WindowTitleHint | 
            Qt.WindowCloseButtonHint |
            Qt.WindowSystemMenuHint
        )
        
        # Set larger size to accommodate more content without scrolling
        self.setMinimumSize(650, 450)
        self.resize(750, 550)
        
    def _setup_ui(self):
        """Create and arrange UI components"""
        # Main layout with optimized spacing for larger content area
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(25, 25, 25, 25)
        
        # Success header with icon
        header_layout = QHBoxLayout()
        
        # Success icon (using Unicode checkmark)
        icon_label = QLabel("✅")
        icon_font = QFont()
        icon_font.setPointSize(32)
        icon_label.setFont(icon_font)
        icon_label.setAlignment(Qt.AlignCenter)
        
        # Title label
        title_label = QLabel(self.title)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label, 1)
        header_layout.addStretch()
        
        # Main message display (rich text)
        self.message_display = QTextEdit()
        self.message_display.setReadOnly(True)
        self.message_display.setPlainText(self.message)
        
        # Configure message display
        message_font = QFont()
        message_font.setPointSize(11)
        self.message_display.setFont(message_font)
        
        # Remove height restriction to allow full content display
        # Set minimum height to ensure adequate space
        self.message_display.setMinimumHeight(250)
        self.message_display.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Details section (if provided)
        details_layout = QVBoxLayout()
        if self.details:
            details_label = QLabel("Output Location:")
            details_font = QFont()
            details_font.setBold(True)
            details_label.setFont(details_font)
            
            details_text = QLabel(self.details)
            details_text.setWordWrap(True)
            details_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
            
            details_layout.addWidget(details_label)
            details_layout.addWidget(details_text)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # OK button
        ok_button = QPushButton("OK")
        ok_button.setMinimumSize(100, 35)
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        
        button_layout.addWidget(ok_button)
        
        # Add all layouts to main layout - give message area maximum space
        main_layout.addLayout(header_layout)
        main_layout.addWidget(self.message_display, 3)  # Give message area most of the space
        if self.details:
            main_layout.addLayout(details_layout)
        main_layout.addLayout(button_layout)
        
    def _apply_theme(self):
        """Apply Carolina Blue theme styling"""
        colors = CarolinaBlueTheme.COLORS
        
        # Custom stylesheet for success dialog
        stylesheet = f"""
        QDialog {{
            background-color: {colors['background']};
            color: {colors['text']};
        }}
        
        QLabel {{
            background-color: transparent;
            color: {colors['text']};
        }}
        
        QTextEdit {{
            background-color: {colors['surface']};
            color: {colors['text']};
            border: 2px solid {colors['primary']};
            border-radius: 8px;
            padding: 15px;
            font-family: 'Consolas', 'Courier New', monospace;
        }}
        
        QPushButton {{
            background-color: {colors['primary']};
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 12px;
        }}
        
        QPushButton:hover {{
            background-color: {colors['hover']};
        }}
        
        QPushButton:pressed {{
            background-color: {colors['pressed']};
        }}
        
        QPushButton:default {{
            border: 2px solid {colors['hover']};
        }}
        """
        
        self.setStyleSheet(stylesheet)
        
    def _center_on_screen(self):
        """Always center dialog on primary screen for consistent positioning"""
        # Always center on primary screen regardless of parent
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        screen_center = screen_geometry.center()
        
        # Calculate position to center this dialog  
        dialog_rect = self.geometry()
        new_x = screen_center.x() - dialog_rect.width() // 2
        new_y = screen_center.y() - dialog_rect.height() // 2
        
        self.move(new_x, new_y)
            
    def show_success(self):
        """Show the success dialog modally and return when user closes it"""
        return self.exec()
        
    @staticmethod
    def show_success_message(message_data, parent=None):
        """
        Display success message using SuccessMessageData object.
        
        This is the PRIMARY method for showing success messages in the new architecture.
        Each tab creates its own SuccessMessageData and passes it here for display.
        
        Args:
            message_data: SuccessMessageData object with all message information
            parent: Parent widget
            
        Returns:
            QDialog result (accepted/rejected)
        """
        from core.services.success_message_data import SuccessMessageData
        
        if not isinstance(message_data, SuccessMessageData):
            raise ValueError("message_data must be a SuccessMessageData object")
        
        dialog = SuccessDialog(
            title=message_data.title,
            message=message_data.to_display_message(),
            details=message_data.output_location or "",
            parent=parent
        )
        
        # Update dialog icon with custom emoji if provided
        if message_data.celebration_emoji != "✅":
            # Find and update the icon label
            for widget in dialog.findChildren(QLabel):
                if widget.text() == "✅":
                    widget.setText(message_data.celebration_emoji)
                    break
        
        return dialog.show_success()
        
    @staticmethod 
    def show_batch_success(title: str, message: str, details: str = "", parent=None):
        """
        LEGACY: Static method to show batch processing success dialog (string-based).
        
        DEPRECATED: Use show_success() with SuccessMessageData instead.
        
        Args:
            title: Dialog title  
            message: Rich success message with batch stats
            details: Output location or additional details
            parent: Parent widget
            
        Returns:
            QDialog result (accepted/rejected)
        """
        dialog = SuccessDialog(title, message, details, parent)
        return dialog.show_success()


# Example usage and testing
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Test message
    test_message = """Operation Complete!

✓ Copied 4 files
✓ Generated 3 reports  
✓ Created 1 ZIP archive(s)

📊 Performance Summary:
Files: 4
Size: 125.3 MB
Time: 2.4 seconds
Average Speed: 52.2 MB/s
Peak Speed: 67.8 MB/s
Mode: Balanced"""
    
    test_details = r"D:\New Folder Structure Testing\Timeline from Neil - Folder Structure App Test\Images 2"
    
    # Show test dialog
    SuccessDialog.show_forensic_success(
        "Forensic Processing Complete!",
        test_message, 
        test_details
    )
    
    sys.exit(0)