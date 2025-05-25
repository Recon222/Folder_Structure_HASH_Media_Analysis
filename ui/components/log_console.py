#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Log console component for displaying status messages
"""

from datetime import datetime

from PySide6.QtCore import Signal, QSettings
from PySide6.QtWidgets import QTextEdit


class LogConsole(QTextEdit):
    """Console widget for displaying log messages"""
    
    # Signals
    message_logged = Signal(str, str)  # timestamp, message
    log_cleared = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumHeight(150)
        
        # Check settings for auto-scroll preference
        self.settings = QSettings('FolderStructureUtility', 'Settings')
        
    def log(self, message: str):
        """Add a timestamped message to the log
        
        Args:
            message: Message to log
            
        Emits:
            message_logged: Signal with timestamp and message
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.append(formatted_message)
        
        # Auto-scroll if enabled
        if self.settings.value('auto_scroll_log', True, type=bool):
            cursor = self.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.setTextCursor(cursor)
            self.ensureCursorVisible()
        
        # Emit signal
        self.message_logged.emit(timestamp, message)
        
    def clear_log(self):
        """Clear all log messages
        
        Emits:
            log_cleared: Signal when log is cleared
        """
        self.clear()
        self.log_cleared.emit()