#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base worker thread class with unified error handling for Folder Structure Application

This module provides the foundation for all worker threads in the application,
implementing the new unified signal system and thread-safe error handling.
"""

from PySide6.QtCore import QThread, Signal
from typing import Optional, Any, Dict
from datetime import datetime

from ..result_types import Result
from ..exceptions import FSAError, ThreadError
from ..error_handler import handle_error


class BaseWorkerThread(QThread):
    """
    Base class for all worker threads with unified error handling
    
    Provides standardized signals, error handling, and cancellation support
    for all background operations in the application.
    """
    
    # NEW: Unified signal system
    result_ready = Signal(Result)          # Single result signal replaces finished(bool, str, dict)
    progress_update = Signal(int, str)     # Replaces separate progress(int) + status(str)
    
    # OLD signals are DELETED - no longer used:
    # finished = Signal(bool, str, dict)   # ❌ REMOVED
    # status = Signal(str)                 # ❌ REMOVED  
    # progress = Signal(int)               # ❌ REMOVED
    
    def __init__(self, parent=None):
        """
        Initialize base worker thread
        
        Args:
            parent: Parent QObject for proper Qt lifecycle management
        """
        super().__init__(parent)
        
        # Cancellation support
        self.cancelled = False
        self._cancel_requested = False
        
        # Pause support
        self.pause_requested = False
        
        # Operation context
        self.operation_start_time = None
        self.operation_name = self.__class__.__name__
        
        # Thread identification
        self.setObjectName(f"{self.__class__.__name__}_{id(self)}")
    
    def run(self):
        """
        Main thread execution method
        
        Subclasses should override this method and implement their logic
        within try/catch blocks, using emit_result() to report outcomes.
        """
        try:
            self.operation_start_time = datetime.utcnow()
            self.emit_progress(0, f"Starting {self.operation_name}...")
            
            # Subclasses implement their logic here
            result = self.execute()
            
            if result is not None:
                self.emit_result(result)
            else:
                # Default success for operations that don't return explicit results
                from ..result_types import Result
                self.emit_result(Result.success(None))
                
        except Exception as e:
            self.handle_unexpected_error(e)
    
    def execute(self) -> Optional[Result]:
        """
        Execute the worker operation
        
        Subclasses should override this method to implement their specific logic.
        Should return a Result object or None (None triggers default success result).
        
        Returns:
            Result object indicating operation outcome, or None for default success
        """
        raise NotImplementedError("Subclasses must implement execute() method")
    
    def emit_progress(self, percentage: int, message: str):
        """
        Thread-safe progress emission
        
        Args:
            percentage: Progress percentage (0-100)
            message: Status message describing current operation
        """
        # Validate percentage
        percentage = max(0, min(100, percentage))
        
        # Check for cancellation before emitting
        if not self.cancelled:
            self.progress_update.emit(percentage, message)
    
    def emit_result(self, result: Result):
        """
        Thread-safe result emission
        
        Args:
            result: Result object containing operation outcome
        """
        # Add timing information if available
        if self.operation_start_time:
            duration = (datetime.utcnow() - self.operation_start_time).total_seconds()
            result.add_metadata('duration_seconds', duration)
            result.add_metadata('operation_name', self.operation_name)
        
        # Add thread information
        result.add_metadata('worker_thread', self.objectName())
        result.add_metadata('thread_id', str(id(QThread.currentThread())))
        
        self.result_ready.emit(result)
    
    def handle_error(self, error: FSAError, context: Optional[dict] = None):
        """
        Handle error with centralized error handling system
        
        Args:
            error: The FSA error that occurred
            context: Additional context information
        """
        context = context or {}
        context.update({
            'worker_class': self.__class__.__name__,
            'worker_object_name': self.objectName(),
            'thread_id': str(id(QThread.currentThread())),
            'operation_name': self.operation_name,
            'cancelled': self.cancelled
        })
        
        if self.operation_start_time:
            context['operation_duration'] = (datetime.utcnow() - self.operation_start_time).total_seconds()
        
        # Use centralized error handler
        handle_error(error, context)
        
        # Emit error result
        from ..result_types import Result
        self.emit_result(Result.error(error))
    
    def handle_unexpected_error(self, exception: Exception):
        """
        Handle unexpected exceptions that weren't converted to FSAError
        
        Args:
            exception: The unexpected exception
        """
        # Convert to appropriate FSAError
        if isinstance(exception, FSAError):
            self.handle_error(exception)
        else:
            # Create ThreadError for unexpected exceptions
            error = ThreadError(
                f"Unexpected error in {self.operation_name}: {str(exception)}",
                thread_name=self.objectName(),
                user_message="An unexpected error occurred. Please try the operation again."
            )
            
            # Add exception details to context
            context = {
                'exception_type': exception.__class__.__name__,
                'exception_str': str(exception),
                'severity': 'critical'
            }
            
            self.handle_error(error, context)
    
    def cancel(self):
        """
        Request cancellation of the operation
        
        Sets the cancelled flag and internal cancel request flag.
        Worker implementations should check cancelled flag regularly
        and exit gracefully when it becomes True.
        """
        self._cancel_requested = True
        self.cancelled = True
        
        self.emit_progress(100, f"{self.operation_name} cancelled by user")
    
    def is_cancelled(self) -> bool:
        """
        Check if cancellation has been requested
        
        Worker operations should call this method periodically and
        exit gracefully if it returns True.
        
        Returns:
            True if cancellation has been requested
        """
        return self.cancelled
    
    def check_cancellation(self):
        """
        Check for cancellation and raise appropriate error if cancelled
        
        Convenience method for worker operations to check cancellation
        and automatically handle the cancellation flow.
        
        Raises:
            ThreadError: If cancellation has been requested
        """
        if self.cancelled:
            error = ThreadError(
                f"{self.operation_name} was cancelled",
                thread_name=self.objectName(),
                user_message="Operation was cancelled by user request.",
                recoverable=True
            )
            raise error
    
    def pause(self):
        """Request pause of the worker operation"""
        self.pause_requested = True
    
    def resume(self):
        """Resume the worker operation"""
        self.pause_requested = False
    
    def is_paused(self) -> bool:
        """Check if the worker is paused"""
        return self.pause_requested
    
    def check_pause(self):
        """
        Check for pause and wait until resumed or cancelled
        
        Worker operations should call this method periodically in loops
        to allow responsive pausing during long operations.
        """
        while self.pause_requested and not self.cancelled:
            self.msleep(100)  # Wait 100ms before checking again
    
    def set_operation_name(self, name: str):
        """
        Set a descriptive name for this operation
        
        Args:
            name: Human-readable operation name for progress messages
        """
        self.operation_name = name


class FileWorkerThread(BaseWorkerThread):
    """
    Specialized base class for file operation workers
    
    Provides additional context and error handling specific to file operations.
    """
    
    def __init__(self, files=None, destination=None, **kwargs):
        """
        Initialize file worker thread
        
        Args:
            files: List of files to operate on
            destination: Destination path for operations
            **kwargs: Additional arguments passed to BaseWorkerThread
        """
        super().__init__(**kwargs)
        
        self.files = files or []
        self.destination = destination
        
        # File operation context
        self.files_processed = 0
        self.total_files = len(self.files) if files else 0
        
        self.set_operation_name("File Operation")
    
    def handle_file_error(self, error: Exception, file_path: str, context: Optional[dict] = None):
        """
        Handle file-specific errors with additional context
        
        Args:
            error: The error that occurred
            file_path: Path to the file that caused the error
            context: Additional context information
        """
        from ..exceptions import FileOperationError
        
        context = context or {}
        context.update({
            'file_path': str(file_path),
            'files_processed': self.files_processed,
            'total_files': self.total_files,
            'destination': str(self.destination) if self.destination else None
        })
        
        if isinstance(error, FSAError):
            self.handle_error(error, context)
        else:
            # Convert to FileOperationError
            fsa_error = FileOperationError(
                f"File operation failed on {file_path}: {str(error)}",
                file_path=str(file_path),
                user_message="File operation failed. Please check file permissions and try again."
            )
            self.handle_error(fsa_error, context)
    
    def update_file_progress(self, files_completed: int, current_file: str = ""):
        """
        Update progress based on file completion
        
        Args:
            files_completed: Number of files completed
            current_file: Name of current file being processed
        """
        self.files_processed = files_completed
        
        if self.total_files > 0:
            percentage = int((files_completed / self.total_files) * 100)
        else:
            percentage = 0
        
        if current_file:
            message = f"{current_file} ({files_completed}/{self.total_files})"
        else:
            message = f"Processed {files_completed}/{self.total_files} files"
        
        self.emit_progress(percentage, message)