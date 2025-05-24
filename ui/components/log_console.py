#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Log console component for displaying status messages
"""

from datetime import datetime

from PySide6.QtWidgets import QTextEdit


class LogConsole(QTextEdit):
    """Console widget for displaying log messages"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumHeight(150)
        
    def log(self, message: str):
        """Add a timestamped message to the log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.append(f"[{timestamp}] {message}")
        
    def clear_log(self):
        """Clear all log messages"""
        self.clear()