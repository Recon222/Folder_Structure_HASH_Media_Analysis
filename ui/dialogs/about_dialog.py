#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
About Dialog for displaying application information
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout
)


class AboutDialog(QDialog):
    """About dialog for application information"""
    
    VERSION = "2.0"
    
    def __init__(self, parent=None):
        """Initialize about dialog
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.setWindowTitle("About Folder Structure Utility")
        self.setModal(True)
        self.setFixedSize(400, 250)
        
        self._create_ui()
        
    def _create_ui(self):
        """Create the dialog UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Folder Structure Utility")
        title_font = title.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Version
        version = QLabel(f"Version {self.VERSION}")
        version.setAlignment(Qt.AlignCenter)
        layout.addWidget(version)
        
        layout.addSpacing(20)
        
        # Description
        description = QLabel(
            "A professional file organization tool for\n"
            "evidence management and custom file structures.\n\n"
            "Features forensic mode for law enforcement\n"
            "and custom mode for flexible organization."
        )
        description.setAlignment(Qt.AlignCenter)
        description.setWordWrap(True)
        layout.addWidget(description)
        
        layout.addSpacing(20)
        
        # Tagline
        tagline = QLabel("A clean, simple approach to organized file management.")
        tagline.setAlignment(Qt.AlignCenter)
        tagline.setStyleSheet("font-style: italic;")
        layout.addWidget(tagline)
        
        layout.addStretch()
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)