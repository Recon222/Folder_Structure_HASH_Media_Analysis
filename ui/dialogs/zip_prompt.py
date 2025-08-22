#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZIP Prompt Dialog - prompts user for ZIP creation choice during operations
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, 
    QPushButton, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class ZipPromptDialog(QDialog):
    """Modal dialog that prompts user for ZIP creation choice"""
    
    def __init__(self, parent=None):
        """Initialize ZIP prompt dialog
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("ZIP Archive Creation")
        self.setModal(True)
        self.setFixedSize(400, 200)
        
        # Remove close button - force user to choose Yes/No
        self.setWindowFlags(
            Qt.Dialog | 
            Qt.WindowTitleHint |
            Qt.CustomizeWindowHint
        )
        
        # Result values
        self.create_zip = False
        self.remember_for_session = False
        
        self._create_ui()
        
    def _create_ui(self):
        """Create the dialog UI"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Main question
        question_label = QLabel("Create ZIP archive for this operation?")
        question_font = QFont()
        question_font.setPointSize(12)
        question_font.setBold(True)
        question_label.setFont(question_font)
        question_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(question_label)
        
        # Session choice checkbox
        self.remember_checkbox = QCheckBox("Remember this choice for current session")
        self.remember_checkbox.setToolTip(
            "If checked, you won't be prompted again until the application is restarted"
        )
        layout.addWidget(self.remember_checkbox)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        # Settings hint
        hint_label = QLabel("Note: You can change the default behavior in Settings → ZIP Settings")
        hint_label.setStyleSheet("color: #666666; font-size: 10px;")
        hint_label.setAlignment(Qt.AlignCenter)
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.yes_button = QPushButton("Yes")
        self.yes_button.setMinimumWidth(80)
        self.yes_button.setDefault(True)  # Default choice
        self.yes_button.clicked.connect(self._on_yes_clicked)
        button_layout.addWidget(self.yes_button)
        
        self.no_button = QPushButton("No")
        self.no_button.setMinimumWidth(80)
        self.no_button.clicked.connect(self._on_no_clicked)
        button_layout.addWidget(self.no_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Focus on Yes button by default
        self.yes_button.setFocus()
        
    def _on_yes_clicked(self):
        """Handle Yes button click"""
        self.create_zip = True
        self.remember_for_session = self.remember_checkbox.isChecked()
        self.accept()
        
    def _on_no_clicked(self):
        """Handle No button click"""
        self.create_zip = False
        self.remember_for_session = self.remember_checkbox.isChecked()
        self.accept()
        
    def closeEvent(self, event):
        """Prevent closing without making a choice"""
        event.ignore()  # Force user to click Yes/No
        
    def keyPressEvent(self, event):
        """Handle key presses"""
        # Allow Escape to close with No choice (fallback)
        if event.key() == Qt.Key_Escape:
            self._on_no_clicked()
        else:
            super().keyPressEvent(event)
            
    @staticmethod
    def prompt_user(parent=None) -> dict:
        """Static method to show prompt and return user choice
        
        Args:
            parent: Parent widget for the dialog
            
        Returns:
            Dictionary with keys:
            - 'create_zip': bool - whether to create ZIP
            - 'remember_for_session': bool - whether to remember choice
        """
        dialog = ZipPromptDialog(parent)
        dialog.exec()
        
        return {
            'create_zip': dialog.create_zip,
            'remember_for_session': dialog.remember_for_session
        }