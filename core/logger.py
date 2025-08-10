#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Centralized logging system with Qt signal support
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from PySide6.QtCore import QObject, Signal


class AppLogger(QObject):
    """Centralized logging with Qt signal support for UI integration"""
    
    # Qt signal for UI components to receive log messages
    log_message = Signal(str, str)  # level, message
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern ensures single logger instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the logger (only once due to singleton)"""
        if self._initialized:
            return
            
        super().__init__()
        self._initialized = True
        
        # Create logger instance
        self.logger = logging.getLogger('FolderStructureUtility')
        self.logger.setLevel(logging.DEBUG)
        
        # Remove any existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Setup handlers
        self._setup_console_handler()
        self._setup_file_handler()
        
        # Track if debug mode is enabled
        self._debug_enabled = False
    
    def _setup_console_handler(self):
        """Setup console (stdout) handler"""
        console_handler = logging.StreamHandler(sys.stdout)
        
        # Default to INFO level (DEBUG messages hidden unless debug mode)
        console_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        # Add to logger
        self.logger.addHandler(console_handler)
        self._console_handler = console_handler
    
    def _setup_file_handler(self):
        """Setup file handler for persistent logs"""
        # Create log directory in user's home
        log_dir = Path.home() / '.folder_structure_utility' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create log file with date in name
        log_filename = f"app_{datetime.now().strftime('%Y%m%d')}.log"
        log_file = log_dir / log_filename
        
        # Create file handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # File always gets all levels
        
        # Detailed formatter for file
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        # Add to logger
        self.logger.addHandler(file_handler)
        self._file_handler = file_handler
    
    def enable_debug(self, enabled: bool = True):
        """Enable or disable debug logging to console
        
        Args:
            enabled: Whether to show debug messages in console
        """
        self._debug_enabled = enabled
        if enabled:
            self._console_handler.setLevel(logging.DEBUG)
            self.info("Debug logging enabled")
        else:
            self._console_handler.setLevel(logging.INFO)
            self.info("Debug logging disabled")
    
    def debug(self, message: str):
        """Log debug message
        
        Args:
            message: Debug message to log
        """
        self.logger.debug(message)
        if self._debug_enabled:
            self.log_message.emit('DEBUG', message)
    
    def info(self, message: str):
        """Log info message
        
        Args:
            message: Info message to log
        """
        self.logger.info(message)
        self.log_message.emit('INFO', message)
    
    def warning(self, message: str):
        """Log warning message
        
        Args:
            message: Warning message to log
        """
        self.logger.warning(message)
        self.log_message.emit('WARNING', message)
    
    def error(self, message: str, exc_info: bool = False):
        """Log error message
        
        Args:
            message: Error message to log
            exc_info: Whether to include exception traceback
        """
        self.logger.error(message, exc_info=exc_info)
        self.log_message.emit('ERROR', message)
    
    def critical(self, message: str, exc_info: bool = True):
        """Log critical message
        
        Args:
            message: Critical message to log
            exc_info: Whether to include exception traceback
        """
        self.logger.critical(message, exc_info=exc_info)
        self.log_message.emit('CRITICAL', message)
    
    def exception(self, message: str):
        """Log exception with automatic traceback
        
        Args:
            message: Exception message to log
        """
        self.logger.exception(message)
        self.log_message.emit('ERROR', f"Exception: {message}")
    
    def get_log_file_path(self) -> Optional[Path]:
        """Get the current log file path
        
        Returns:
            Path to current log file, or None if file handler not setup
        """
        if hasattr(self, '_file_handler'):
            return Path(self._file_handler.baseFilename)
        return None
    
    def get_log_directory(self) -> Path:
        """Get the log directory path
        
        Returns:
            Path to log directory
        """
        return Path.home() / '.folder_structure_utility' / 'logs'
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Clean up log files older than specified days
        
        Args:
            days_to_keep: Number of days of logs to keep
        """
        log_dir = self.get_log_directory()
        if not log_dir.exists():
            return
        
        cutoff_date = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
        
        for log_file in log_dir.glob('app_*.log'):
            try:
                if log_file.stat().st_mtime < cutoff_date:
                    log_file.unlink()
                    self.debug(f"Deleted old log file: {log_file.name}")
            except Exception as e:
                self.warning(f"Failed to delete old log {log_file.name}: {e}")


# Global logger instance
logger = AppLogger()


# Convenience functions for module-level logging
def debug(message: str):
    """Log debug message"""
    logger.debug(message)


def info(message: str):
    """Log info message"""
    logger.info(message)


def warning(message: str):
    """Log warning message"""
    logger.warning(message)


def error(message: str, exc_info: bool = False):
    """Log error message"""
    logger.error(message, exc_info=exc_info)


def critical(message: str, exc_info: bool = True):
    """Log critical message"""
    logger.critical(message, exc_info=exc_info)


def exception(message: str):
    """Log exception with traceback"""
    logger.exception(message)