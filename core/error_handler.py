#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thread-safe centralized error handling system for Folder Structure Application

This module provides a Qt-compatible error handling system that safely routes
errors from worker threads to the main thread for UI updates and logging.
"""

from PySide6.QtCore import QObject, Signal, QMetaObject, QThread, Qt, QTimer
from typing import Callable, List, Dict, Any, Optional
import logging
import traceback
from datetime import datetime
from pathlib import Path

from .exceptions import FSAError, ErrorSeverity


class ErrorHandler(QObject):
    """
    Thread-safe centralized error handling system
    
    Routes errors from any thread to the main thread for UI updates while
    providing immediate thread-safe logging. Uses Qt's signal system to
    ensure proper thread boundaries.
    """
    
    # Qt signals for thread-safe error reporting
    error_occurred = Signal(FSAError, dict)  # error, context
    
    def __init__(self, parent=None):
        """
        Initialize error handler
        
        Args:
            parent: Parent QObject for proper Qt lifecycle management
        """
        super().__init__(parent)
        
        # Set up logging
        self._setup_logging()
        
        # UI callback registry
        self._ui_callbacks: List[Callable[[FSAError, dict], None]] = []
        
        # Error statistics
        self._error_counts = {
            ErrorSeverity.INFO: 0,
            ErrorSeverity.WARNING: 0,
            ErrorSeverity.ERROR: 0,
            ErrorSeverity.CRITICAL: 0
        }
        
        # Recent errors for debugging
        self._recent_errors: List[Dict[str, Any]] = []
        self._max_recent_errors = 100
        
        # Connect our signal to the main thread handler
        self.error_occurred.connect(
            self._handle_error_main_thread,
            Qt.QueuedConnection  # Ensure main thread execution
        )
        
        self.logger.info("Error handler initialized")
    
    def _setup_logging(self):
        """Set up logging configuration"""
        self.logger = logging.getLogger(__name__)
        
        # Don't add handlers if they already exist
        if not self.logger.handlers:
            # Create formatter
            formatter = logging.Formatter(
                '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            
            # File handler (if logs directory exists)
            try:
                logs_dir = Path("logs")
                logs_dir.mkdir(exist_ok=True)
                
                log_file = logs_dir / f"fsa_errors_{datetime.now().strftime('%Y%m%d')}.log"
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            except Exception:
                # File logging is optional
                pass
            
            self.logger.setLevel(logging.INFO)
    
    def register_ui_callback(self, callback: Callable[[FSAError, dict], None]):
        """
        Register UI callback for error notifications
        
        Must be called from the main thread. Callbacks will be invoked
        in the main thread when errors occur.
        
        Args:
            callback: Function to call with (error, context) parameters
        """
        if not QThread.currentThread().isMainThread():
            self.logger.warning("UI callback registered from non-main thread")
        
        self._ui_callbacks.append(callback)
        self.logger.debug(f"Registered UI callback: {callback.__name__ if hasattr(callback, '__name__') else str(callback)}")
    
    def unregister_ui_callback(self, callback: Callable[[FSAError, dict], None]):
        """
        Unregister UI callback
        
        Args:
            callback: Function to remove from callbacks
        """
        try:
            self._ui_callbacks.remove(callback)
            self.logger.debug("Unregistered UI callback")
        except ValueError:
            self.logger.warning("Attempted to unregister non-existent UI callback")
    
    def handle_error(self, error: FSAError, context: Optional[dict] = None):
        """
        Handle error from any thread
        
        Automatically routes to main thread for UI updates while providing
        immediate thread-safe logging.
        
        Args:
            error: The FSA error that occurred
            context: Additional context information
        """
        context = context or {}
        
        # Add thread information to context
        current_thread = QThread.currentThread()
        context.update({
            'handler_thread': current_thread.objectName() or current_thread.__class__.__name__,
            'handler_thread_id': str(id(QThread.currentThread())),
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Always log immediately (thread-safe)
        self._log_error(error, context)
        
        # Update statistics
        self._error_counts[error.severity] += 1
        
        # Store in recent errors
        self._store_recent_error(error, context)
        
        # Route to main thread for UI updates  
        if not QThread.currentThread().isMainThread():
            # We're in a worker thread - use queued connection
            self.error_occurred.emit(error, context)
        else:
            # We're already in main thread - handle directly
            self._handle_error_main_thread(error, context)
    
    def _handle_error_main_thread(self, error: FSAError, context: dict):
        """
        Handle error in main thread (for UI updates)
        
        This slot is guaranteed to run in the main thread due to Qt's
        signal routing with QueuedConnection.
        
        Args:
            error: The FSA error that occurred
            context: Additional context information
        """
        # Verify we're in the main thread
        if not QThread.currentThread().isMainThread():
            self.logger.error("Main thread handler called from worker thread!")
            return
        
        # Notify all UI callbacks
        for callback in self._ui_callbacks:
            try:
                callback(error, context)
            except Exception as callback_error:
                self.logger.error(f"UI callback failed: {callback_error}")
                self.logger.debug(f"Callback traceback: {traceback.format_exc()}")
    
    def _log_error(self, error: FSAError, context: dict):
        """
        Thread-safe error logging
        
        Args:
            error: The FSA error to log
            context: Context information
        """
        # Build context string
        context_items = []
        for key, value in context.items():
            if key not in ['timestamp', 'handler_thread', 'handler_thread_id']:
                context_items.append(f"{key}={value}")
        context_str = ', '.join(context_items) if context_items else 'None'
        
        # Build log message
        log_msg = f"[{error.error_code}] {error.message}"
        if context_str != 'None':
            log_msg += f" | Context: {context_str}"
        
        # Log based on severity
        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_msg, exc_info=True)
        elif error.severity == ErrorSeverity.ERROR:
            self.logger.error(log_msg, exc_info=True)
        elif error.severity == ErrorSeverity.WARNING:
            self.logger.warning(log_msg)
        else:  # INFO
            self.logger.info(log_msg)
    
    def _store_recent_error(self, error: FSAError, context: dict):
        """
        Store error in recent errors list for debugging
        
        Args:
            error: The FSA error to store
            context: Context information
        """
        error_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'error_code': error.error_code,
            'message': error.message,
            'user_message': error.user_message,
            'severity': error.severity.value,
            'recoverable': error.recoverable,
            'thread_name': error.thread_name,
            'context': context.copy()
        }
        
        self._recent_errors.append(error_record)
        
        # Trim to maximum size
        if len(self._recent_errors) > self._max_recent_errors:
            self._recent_errors = self._recent_errors[-self._max_recent_errors:]
    
    def get_error_statistics(self) -> Dict[str, int]:
        """
        Get error count statistics
        
        Returns:
            Dictionary with error counts by severity
        """
        return {severity.value: count for severity, count in self._error_counts.items()}
    
    def get_recent_errors(self, count: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get recent errors for debugging
        
        Args:
            count: Number of recent errors to return (None for all)
            
        Returns:
            List of recent error records
        """
        if count is None:
            return self._recent_errors.copy()
        else:
            return self._recent_errors[-count:] if self._recent_errors else []
    
    def clear_statistics(self):
        """Clear error statistics and recent errors"""
        self._error_counts = {severity: 0 for severity in ErrorSeverity}
        self._recent_errors.clear()
        self.logger.info("Error statistics cleared")
    
    def export_error_log(self, output_path: Path) -> bool:
        """
        Export recent errors to a JSON file for debugging
        
        Args:
            output_path: Path where to save the error log
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            import json
            
            export_data = {
                'export_timestamp': datetime.utcnow().isoformat(),
                'statistics': self.get_error_statistics(),
                'recent_errors': self._recent_errors
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Error log exported to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export error log: {e}")
            return False


# Global singleton instance
_global_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """
    Get the global error handler instance
    
    Creates the instance if it doesn't exist. Should be called from
    the main thread during application initialization.
    
    Returns:
        Global ErrorHandler instance
    """
    global _global_error_handler
    
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    
    return _global_error_handler


def initialize_error_handling(parent=None) -> ErrorHandler:
    """
    Initialize the global error handling system
    
    Should be called once during application startup from the main thread.
    
    Args:
        parent: Parent QObject for proper Qt lifecycle management
        
    Returns:
        Global ErrorHandler instance
    """
    global _global_error_handler
    
    if _global_error_handler is not None:
        _global_error_handler.logger.warning("Error handler already initialized")
        return _global_error_handler
    
    _global_error_handler = ErrorHandler(parent)
    _global_error_handler.logger.info("Global error handling initialized")
    
    return _global_error_handler


def shutdown_error_handling():
    """
    Shutdown the global error handling system
    
    Should be called during application shutdown.
    """
    global _global_error_handler
    
    if _global_error_handler is not None:
        _global_error_handler.logger.info("Shutting down error handling")
        _global_error_handler.clear_statistics()
        _global_error_handler = None


# Convenience function for common error handling
def handle_error(error: FSAError, context: Optional[dict] = None):
    """
    Handle an error using the global error handler
    
    Convenience function that automatically uses the global error handler.
    Creates the handler if it doesn't exist.
    
    Args:
        error: The FSA error that occurred
        context: Additional context information
    """
    error_handler = get_error_handler()
    error_handler.handle_error(error, context)