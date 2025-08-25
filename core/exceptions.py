#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thread-aware exception hierarchy for Folder Structure Application

This module provides a comprehensive exception system that is fully thread-safe
and designed to work seamlessly with Qt's signal/slot architecture.
"""

from PySide6.QtCore import QThread
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels for categorization and UI display"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class FSAError(Exception):
    """
    Base exception for all Folder Structure Application errors
    
    Thread-aware exception that captures context information and provides
    user-friendly messages for UI display.
    """
    
    def __init__(self, 
                 message: str,
                 error_code: Optional[str] = None,
                 user_message: Optional[str] = None, 
                 recoverable: bool = False,
                 severity: ErrorSeverity = ErrorSeverity.ERROR,
                 context: Optional[Dict[str, Any]] = None):
        """
        Initialize FSA error
        
        Args:
            message: Technical error message for logging
            error_code: Unique error code for categorization
            user_message: User-friendly message for UI display
            recoverable: Whether operation can be retried
            severity: Error severity level
            context: Additional context information
        """
        super().__init__(message)
        
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.user_message = user_message or self._generate_user_message()
        self.recoverable = recoverable
        self.severity = severity
        self.timestamp = datetime.utcnow()
        self.context = context or {}
        
        # Thread context information
        current_thread = QThread.currentThread()
        self.thread_id = current_thread
        self.thread_name = current_thread.objectName() or current_thread.__class__.__name__
        self.is_main_thread = (current_thread == QThread.currentThread().parent())
    
    def _generate_user_message(self) -> str:
        """Generate user-friendly message from technical message"""
        return "An error occurred during the operation. Please check the logs for details."
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging and serialization"""
        return {
            'error_code': self.error_code,
            'message': self.message,
            'user_message': self.user_message,
            'severity': self.severity.value,
            'recoverable': self.recoverable,
            'timestamp': self.timestamp.isoformat(),
            'thread_name': self.thread_name,
            'is_main_thread': self.is_main_thread,
            'context': self.context
        }


class FileOperationError(FSAError):
    """File operation failures (copying, moving, deleting)"""
    
    def __init__(self, message: str, file_path: Optional[str] = None, **kwargs):
        """
        Initialize file operation error
        
        Args:
            message: Technical error message
            file_path: Path to file that caused the error
            **kwargs: Additional FSAError arguments
        """
        context = kwargs.get('context', {})
        if file_path:
            context['file_path'] = file_path
        kwargs['context'] = context
        
        super().__init__(message, **kwargs)
    
    def _generate_user_message(self) -> str:
        return "File operation failed. Please check file permissions and try again."


class ValidationError(FSAError):
    """Form and data validation errors"""
    
    def __init__(self, field_errors: Dict[str, str], **kwargs):
        """
        Initialize validation error
        
        Args:
            field_errors: Dictionary mapping field names to error messages
            **kwargs: Additional FSAError arguments
        """
        self.field_errors = field_errors
        context = kwargs.get('context', {})
        context['field_errors'] = field_errors
        kwargs['context'] = context
        
        message = f"Validation failed: {len(field_errors)} field(s) have errors"
        super().__init__(message, severity=ErrorSeverity.WARNING, **kwargs)
    
    def _generate_user_message(self) -> str:
        error_count = len(self.field_errors)
        if error_count == 1:
            return "Please correct the validation error."
        return f"Please correct {error_count} validation errors."


class ReportGenerationError(FSAError):
    """PDF and report generation failures"""
    
    def __init__(self, message: str, report_type: Optional[str] = None, output_path: Optional[str] = None, **kwargs):
        """
        Initialize report generation error
        
        Args:
            message: Technical error message
            report_type: Type of report being generated
            output_path: Intended output path
            **kwargs: Additional FSAError arguments
        """
        context = kwargs.get('context', {})
        if report_type:
            context['report_type'] = report_type
        if output_path:
            context['output_path'] = output_path
        kwargs['context'] = context
        
        super().__init__(message, **kwargs)
    
    def _generate_user_message(self) -> str:
        return "Report generation failed. Please check output directory permissions."


class BatchProcessingError(FSAError):
    """Batch job processing failures"""
    
    def __init__(self, job_id: str, successes: int, failures: int, 
                 error_details: Optional[list] = None, **kwargs):
        """
        Initialize batch processing error
        
        Args:
            job_id: Unique identifier for the batch job
            successes: Number of successful operations
            failures: Number of failed operations
            error_details: List of detailed error information
            **kwargs: Additional FSAError arguments
        """
        self.job_id = job_id
        self.successes = successes
        self.failures = failures
        self.error_details = error_details or []
        
        context = kwargs.get('context', {})
        context.update({
            'job_id': job_id,
            'successes': successes,
            'failures': failures,
            'error_details': self.error_details
        })
        kwargs['context'] = context
        
        total = successes + failures
        success_rate = (successes / total * 100) if total > 0 else 0
        message = f"Batch job {job_id}: {success_rate:.1f}% success ({successes}/{total})"
        
        # Determine severity based on failure rate
        if failures == 0:
            severity = ErrorSeverity.INFO
        elif successes == 0:
            severity = ErrorSeverity.CRITICAL
        elif failures > successes:
            severity = ErrorSeverity.ERROR
        else:
            severity = ErrorSeverity.WARNING
            
        super().__init__(message, severity=severity, **kwargs)
    
    def _generate_user_message(self) -> str:
        if self.failures == 0:
            return f"Batch job completed successfully ({self.successes} items processed)"
        elif self.successes == 0:
            return f"Batch job failed completely ({self.failures} errors)"
        else:
            return f"Batch job partially successful: {self.successes} completed, {self.failures} failed"


class ArchiveError(FSAError):
    """ZIP creation and archive errors"""
    
    def __init__(self, message: str, archive_path: Optional[str] = None, **kwargs):
        """
        Initialize archive error
        
        Args:
            message: Technical error message
            archive_path: Path where archive was being created
            **kwargs: Additional FSAError arguments
        """
        context = kwargs.get('context', {})
        if archive_path:
            context['archive_path'] = archive_path
        kwargs['context'] = context
        
        super().__init__(message, **kwargs)
    
    def _generate_user_message(self) -> str:
        return "Archive creation failed. Please check available disk space."


class HashVerificationError(FSAError):
    """Hash calculation and verification errors"""
    
    def __init__(self, message: str, file_path: Optional[str] = None, 
                 expected_hash: Optional[str] = None, actual_hash: Optional[str] = None, **kwargs):
        """
        Initialize hash verification error
        
        Args:
            message: Technical error message
            file_path: Path to file with hash mismatch
            expected_hash: Expected hash value
            actual_hash: Actual calculated hash
            **kwargs: Additional FSAError arguments
        """
        context = kwargs.get('context', {})
        if file_path:
            context['file_path'] = file_path
        if expected_hash:
            context['expected_hash'] = expected_hash
        if actual_hash:
            context['actual_hash'] = actual_hash
        kwargs['context'] = context
        
        super().__init__(message, severity=ErrorSeverity.CRITICAL, **kwargs)
    
    def _generate_user_message(self) -> str:
        return "Hash verification failed. File integrity may be compromised."


class ConfigurationError(FSAError):
    """Configuration and settings errors"""
    
    def __init__(self, message: str, setting_key: Optional[str] = None, **kwargs):
        """
        Initialize configuration error
        
        Args:
            message: Technical error message
            setting_key: Configuration key that caused the error
            **kwargs: Additional FSAError arguments
        """
        context = kwargs.get('context', {})
        if setting_key:
            context['setting_key'] = setting_key
        kwargs['context'] = context
        
        super().__init__(message, severity=ErrorSeverity.WARNING, **kwargs)
    
    def _generate_user_message(self) -> str:
        return "Configuration error. Please check application settings."


class ThreadError(FSAError):
    """Thread management and synchronization errors"""
    
    def __init__(self, message: str, thread_name: Optional[str] = None, **kwargs):
        """
        Initialize thread error
        
        Args:
            message: Technical error message
            thread_name: Name of problematic thread
            **kwargs: Additional FSAError arguments
        """
        context = kwargs.get('context', {})
        if thread_name:
            context['problem_thread'] = thread_name
        kwargs['context'] = context
        
        super().__init__(message, severity=ErrorSeverity.CRITICAL, **kwargs)
    
    def _generate_user_message(self) -> str:
        return "Internal processing error. Please restart the operation."


class UIError(FSAError):
    """User interface and interaction errors"""
    
    def __init__(self, message: str, component: Optional[str] = None, **kwargs):
        """
        Initialize UI error
        
        Args:
            message: Technical error message
            component: UI component that caused the error
            **kwargs: Additional FSAError arguments (including severity)
        """
        context = kwargs.get('context', {})
        if component:
            context['ui_component'] = component
        kwargs['context'] = context
        
        # Default to WARNING severity if not specified
        if 'severity' not in kwargs:
            kwargs['severity'] = ErrorSeverity.WARNING
        
        super().__init__(message, **kwargs)
    
    def _generate_user_message(self) -> str:
        return "Interface error occurred. Please try the operation again."