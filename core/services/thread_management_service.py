#!/usr/bin/env python3
"""
Thread management service - centralized thread lifecycle management
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import gc

from PySide6.QtCore import QThread

from .base_service import BaseService
from ..result_types import Result
from ..exceptions import ThreadManagementError, ErrorSeverity


class ThreadState(Enum):
    """Thread state enumeration"""
    RUNNING = "running"
    STOPPING = "stopping"
    TERMINATED = "terminated"
    UNKNOWN = "unknown"


@dataclass
class ThreadInfo:
    """Information about a managed thread"""
    name: str
    thread: QThread
    state: ThreadState
    can_cancel: bool = False
    description: str = ""


class IThreadManagementService:
    """Interface for thread management operations"""
    
    def discover_active_threads(self, app_components: Dict[str, Any]) -> Result[List[ThreadInfo]]:
        """Discover all active threads in the application"""
        raise NotImplementedError
    
    def request_graceful_shutdown(self, threads: List[ThreadInfo]) -> Result[None]:
        """Request graceful shutdown of threads"""
        raise NotImplementedError
    
    def force_terminate(self, thread: ThreadInfo) -> Result[None]:
        """Force terminate a thread"""
        raise NotImplementedError
    
    def wait_for_completion(self, threads: List[ThreadInfo], timeout_ms: int = 5000) -> Result[List[ThreadInfo]]:
        """Wait for threads to complete with timeout"""
        raise NotImplementedError
    
    def cleanup_thread_resources(self, thread: ThreadInfo) -> Result[None]:
        """Clean up resources associated with a thread"""
        raise NotImplementedError


class ThreadManagementService(BaseService, IThreadManagementService):
    """Service for managing thread lifecycle and cleanup"""
    
    def __init__(self):
        super().__init__("ThreadManagementService")
        self._managed_threads: Dict[str, ThreadInfo] = {}
    
    def discover_active_threads(self, app_components: Dict[str, Any]) -> Result[List[ThreadInfo]]:
        """
        Discover all active threads in the application
        
        This extracts the thread discovery logic from MainWindow.closeEvent()
        
        Args:
            app_components: Dictionary of application components to check
                Expected keys: 'main_window', 'batch_tab', 'hashing_tab'
        
        Returns:
            Result containing list of active ThreadInfo objects
        """
        try:
            self._log_operation("discover_active_threads", "Starting thread discovery")
            threads = []
            
            # Check main window threads
            main_window = app_components.get('main_window')
            if main_window:
                # File operation thread
                if hasattr(main_window, 'file_thread') and main_window.file_thread:
                    if main_window.file_thread.isRunning():
                        threads.append(ThreadInfo(
                            name="File operations",
                            thread=main_window.file_thread,
                            state=ThreadState.RUNNING,
                            can_cancel=hasattr(main_window.file_thread, 'cancel'),
                            description="File copying and verification operations"
                        ))
                
                # Folder operation thread
                if hasattr(main_window, 'folder_thread') and main_window.folder_thread:
                    if main_window.folder_thread.isRunning():
                        threads.append(ThreadInfo(
                            name="Folder operations",
                            thread=main_window.folder_thread,
                            state=ThreadState.RUNNING,
                            can_cancel=hasattr(main_window.folder_thread, 'cancel'),
                            description="Folder structure creation operations"
                        ))
                
                # ZIP operation thread
                if hasattr(main_window, 'zip_thread') and main_window.zip_thread:
                    if main_window.zip_thread.isRunning():
                        threads.append(ThreadInfo(
                            name="ZIP operations",
                            thread=main_window.zip_thread,
                            state=ThreadState.RUNNING,
                            can_cancel=hasattr(main_window.zip_thread, 'cancel'),
                            description="Archive creation operations"
                        ))
            
            # Check batch tab
            batch_tab = app_components.get('batch_tab')
            if batch_tab and hasattr(batch_tab, 'queue_widget'):
                batch_widget = batch_tab.queue_widget
                if hasattr(batch_widget, 'processor_thread') and batch_widget.processor_thread:
                    if batch_widget.processor_thread.isRunning():
                        threads.append(ThreadInfo(
                            name="Batch processing",
                            thread=batch_widget.processor_thread,
                            state=ThreadState.RUNNING,
                            can_cancel=hasattr(batch_widget.processor_thread, 'cancel'),
                            description="Batch job processing operations"
                        ))
            
            # Check hashing tab
            hashing_tab = app_components.get('hashing_tab')
            if hashing_tab and hasattr(hashing_tab, 'hash_controller'):
                if hashing_tab.hash_controller.is_operation_running():
                    current_op = hashing_tab.hash_controller.get_current_operation()
                    if current_op:
                        threads.append(ThreadInfo(
                            name="Hash operations",
                            thread=current_op,
                            state=ThreadState.RUNNING,
                            can_cancel=hasattr(current_op, 'cancel'),
                            description="File hash calculation and verification"
                        ))
            
            # Store discovered threads
            for thread_info in threads:
                self._managed_threads[thread_info.name] = thread_info
            
            self._log_operation("threads_discovered", f"Found {len(threads)} active threads")
            return Result.success(threads)
            
        except Exception as e:
            error = ThreadManagementError(
                f"Failed to discover active threads: {e}",
                user_message="Failed to check for active operations.",
                severity=ErrorSeverity.WARNING
            )
            self._handle_error(error, {'method': 'discover_active_threads'})
            return Result.error(error)
    
    def request_graceful_shutdown(self, threads: List[ThreadInfo]) -> Result[None]:
        """
        Request graceful shutdown of threads
        
        Args:
            threads: List of ThreadInfo objects to shutdown
            
        Returns:
            Result indicating success or failure
        """
        try:
            self._log_operation("request_graceful_shutdown", f"Requesting shutdown for {len(threads)} threads")
            
            shutdown_errors = []
            
            for thread_info in threads:
                try:
                    self._log_operation("shutting_down_thread", thread_info.name)
                    
                    # Try to cancel if method available
                    if thread_info.can_cancel and hasattr(thread_info.thread, 'cancel'):
                        thread_info.thread.cancel()
                        thread_info.state = ThreadState.STOPPING
                    elif hasattr(thread_info.thread, 'cancelled'):
                        # Some threads use a flag instead of method
                        thread_info.thread.cancelled = True
                        thread_info.state = ThreadState.STOPPING
                    else:
                        self._log_operation("no_cancel_method", thread_info.name, "warning")
                        
                except Exception as e:
                    error_msg = f"Error cancelling {thread_info.name}: {e}"
                    self._log_operation("cancel_error", error_msg, "error")
                    shutdown_errors.append(error_msg)
            
            if shutdown_errors:
                error = ThreadManagementError(
                    f"Some threads failed to shutdown gracefully: {'; '.join(shutdown_errors)}",
                    user_message="Some operations could not be cancelled gracefully.",
                    severity=ErrorSeverity.WARNING
                )
                self._handle_error(error, {'method': 'request_graceful_shutdown', 'errors': shutdown_errors})
                return Result.error(error)
            
            return Result.success(None)
            
        except Exception as e:
            error = ThreadManagementError(
                f"Failed to request graceful shutdown: {e}",
                user_message="Failed to stop operations gracefully.",
                severity=ErrorSeverity.ERROR
            )
            self._handle_error(error, {'method': 'request_graceful_shutdown'})
            return Result.error(error)
    
    def wait_for_completion(self, threads: List[ThreadInfo], timeout_ms: int = 5000) -> Result[List[ThreadInfo]]:
        """
        Wait for threads to complete with timeout
        
        Args:
            threads: List of ThreadInfo objects to wait for
            timeout_ms: Maximum time to wait in milliseconds
            
        Returns:
            Result containing list of threads that didn't stop in time
        """
        try:
            self._log_operation("wait_for_completion", f"Waiting for {len(threads)} threads (timeout: {timeout_ms}ms)")
            
            stuck_threads = []
            
            for thread_info in threads:
                try:
                    self._log_operation("waiting_for_thread", f"{thread_info.name}")
                    
                    if thread_info.thread.wait(timeout_ms):
                        thread_info.state = ThreadState.TERMINATED
                        self._log_operation("thread_stopped", f"{thread_info.name} stopped successfully")
                    else:
                        stuck_threads.append(thread_info)
                        self._log_operation("thread_timeout", f"{thread_info.name} did not stop in time", "warning")
                        
                except Exception as e:
                    self._log_operation("wait_error", f"Error waiting for {thread_info.name}: {e}", "error")
                    stuck_threads.append(thread_info)
            
            if stuck_threads:
                self._log_operation("threads_stuck", f"{len(stuck_threads)} threads did not stop gracefully", "warning")
            
            return Result.success(stuck_threads)
            
        except Exception as e:
            error = ThreadManagementError(
                f"Failed to wait for thread completion: {e}",
                user_message="Error while waiting for operations to complete.",
                severity=ErrorSeverity.WARNING
            )
            self._handle_error(error, {'method': 'wait_for_completion'})
            return Result.error(error)
    
    def force_terminate(self, thread: ThreadInfo) -> Result[None]:
        """
        Force terminate a thread
        
        Args:
            thread: ThreadInfo object to terminate
            
        Returns:
            Result indicating success or failure
        """
        try:
            self._log_operation("force_terminate", f"Force terminating {thread.name}", "warning")
            
            thread.thread.terminate()
            
            # Give it a moment to terminate
            if not thread.thread.wait(1000):  # 1 second
                error = ThreadManagementError(
                    f"{thread.name} failed to terminate properly",
                    user_message=f"Could not stop {thread.name} operation.",
                    severity=ErrorSeverity.CRITICAL
                )
                self._handle_error(error, {'method': 'force_terminate', 'thread': thread.name})
                return Result.error(error)
            
            thread.state = ThreadState.TERMINATED
            self._log_operation("thread_terminated", f"{thread.name} terminated")
            return Result.success(None)
            
        except Exception as e:
            error = ThreadManagementError(
                f"Failed to force terminate {thread.name}: {e}",
                user_message=f"Could not force stop {thread.name}.",
                severity=ErrorSeverity.CRITICAL
            )
            self._handle_error(error, {'method': 'force_terminate', 'thread': thread.name})
            return Result.error(error)
    
    def cleanup_thread_resources(self, thread: ThreadInfo) -> Result[None]:
        """
        Clean up resources associated with a thread
        
        Args:
            thread: ThreadInfo object to clean up
            
        Returns:
            Result indicating success or failure
        """
        try:
            self._log_operation("cleanup_thread_resources", f"Cleaning up {thread.name}")
            
            # Disconnect signals if possible
            if hasattr(thread.thread, 'progress_update'):
                try:
                    thread.thread.progress_update.disconnect()
                except:
                    pass  # Already disconnected
            
            if hasattr(thread.thread, 'result_ready'):
                try:
                    thread.thread.result_ready.disconnect()
                except:
                    pass  # Already disconnected
            
            # Remove from managed threads
            if thread.name in self._managed_threads:
                del self._managed_threads[thread.name]
            
            self._log_operation("thread_cleaned", f"{thread.name} resources cleaned")
            return Result.success(None)
            
        except Exception as e:
            error = ThreadManagementError(
                f"Failed to clean up thread resources: {e}",
                user_message="Warning: Some resources may not have been cleaned up properly.",
                severity=ErrorSeverity.WARNING
            )
            self._handle_error(error, {'method': 'cleanup_thread_resources', 'thread': thread.name})
            return Result.error(error)
    
    def shutdown_all_threads(
        self, 
        app_components: Dict[str, Any],
        graceful_timeout_ms: int = 5000,
        force_terminate_stuck: bool = True
    ) -> Result[None]:
        """
        Complete thread shutdown orchestration
        
        This is the main method that orchestrates the entire shutdown process,
        replacing the complex logic in MainWindow.closeEvent()
        
        Args:
            app_components: Dictionary of application components
            graceful_timeout_ms: Time to wait for graceful shutdown
            force_terminate_stuck: Whether to force terminate stuck threads
            
        Returns:
            Result indicating success or failure
        """
        try:
            self._log_operation("shutdown_all_threads", "Starting complete shutdown sequence")
            
            # Step 1: Discover active threads
            discovery_result = self.discover_active_threads(app_components)
            if not discovery_result.success:
                return discovery_result
            
            active_threads = discovery_result.value
            if not active_threads:
                self._log_operation("no_active_threads", "No active threads to shutdown")
                return Result.success(None)
            
            # Step 2: Request graceful shutdown
            self._log_operation("graceful_shutdown_phase", f"Requesting shutdown for {len(active_threads)} threads")
            shutdown_result = self.request_graceful_shutdown(active_threads)
            # Continue even if some threads couldn't be cancelled gracefully
            
            # Step 3: Wait for threads to stop
            wait_result = self.wait_for_completion(active_threads, graceful_timeout_ms)
            if not wait_result.success:
                return wait_result
            
            stuck_threads = wait_result.value
            
            # Step 4: Force terminate stuck threads if requested
            if stuck_threads and force_terminate_stuck:
                self._log_operation("force_terminate_phase", f"Force terminating {len(stuck_threads)} stuck threads")
                for thread_info in stuck_threads:
                    terminate_result = self.force_terminate(thread_info)
                    if not terminate_result.success:
                        self._log_operation("terminate_failed", f"Failed to terminate {thread_info.name}", "error")
            
            # Step 5: Clean up resources
            for thread_info in active_threads:
                self.cleanup_thread_resources(thread_info)
            
            # Force garbage collection
            gc.collect()
            
            self._log_operation("shutdown_complete", "All threads shutdown successfully")
            return Result.success(None)
            
        except Exception as e:
            error = ThreadManagementError(
                f"Failed to complete thread shutdown: {e}",
                user_message="Error during application shutdown.",
                severity=ErrorSeverity.CRITICAL
            )
            self._handle_error(error, {'method': 'shutdown_all_threads'})
            return Result.error(error)
    
    def get_thread_names(self, threads: List[ThreadInfo]) -> List[str]:
        """
        Get list of thread names for display
        
        Args:
            threads: List of ThreadInfo objects
            
        Returns:
            List of thread names
        """
        return [thread.name for thread in threads]
    
    def clear_managed_threads(self):
        """Clear the managed threads registry"""
        self._managed_threads.clear()
        self._log_operation("threads_cleared", "Managed threads registry cleared")