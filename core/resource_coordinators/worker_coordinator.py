"""
Specialized resource coordinator for worker thread management.

Provides enhanced functionality for tracking and managing worker threads
with intelligent cleanup and cancellation support.
"""

import logging
import time
from typing import Set, Optional, Dict, Any
from PySide6.QtCore import QThread

from .base_coordinator import BaseResourceCoordinator
from core.services.resource_management_service import ResourceType

logger = logging.getLogger(__name__)


class WorkerResourceCoordinator(BaseResourceCoordinator):
    """
    Specialized coordinator for managing worker threads.
    
    Provides additional functionality for tracking active workers,
    coordinating cancellation, and ensuring proper cleanup.
    """
    
    def __init__(self, component_id: str):
        """
        Initialize the worker resource coordinator.
        
        Args:
            component_id: Unique identifier for the component
        """
        super().__init__(component_id)
        self._active_workers: Set[str] = set()
        self._worker_metadata: Dict[str, Dict[str, Any]] = {}
        
    def track_worker(self, 
                    worker: QThread,
                    name: Optional[str] = None,
                    cancel_on_cleanup: bool = True,
                    auto_release: bool = True) -> str:
        """
        Track a worker thread with enhanced management capabilities.
        
        Args:
            worker: The worker thread to track
            name: Optional name for the worker
            cancel_on_cleanup: Whether to cancel the worker on cleanup
            auto_release: Whether to auto-release when worker finishes
            
        Returns:
            Resource ID for tracking
        """
        worker_name = name or worker.__class__.__name__
        
        # Define cleanup handler
        def cleanup_worker(w):
            """Enhanced cleanup handler for worker threads."""
            if w and w.isRunning():
                # Try graceful shutdown first
                if cancel_on_cleanup and hasattr(w, 'cancel'):
                    logger.debug(f"Cancelling worker: {worker_name}")
                    w.cancel()
                    
                # Request thread quit
                w.quit()
                
                # Wait for graceful shutdown
                if not w.wait(2000):
                    logger.warning(f"Force terminating worker: {worker_name}")
                    w.terminate()
                    w.wait(1000)  # Give it a moment to actually terminate
        
        # Track the worker with base class
        resource_id = self.track_resource(
            worker,
            ResourceType.WORKER,
            name=worker_name,
            cleanup_handler=cleanup_worker if cancel_on_cleanup else None,
            thread_id=id(worker),  # Use object id as unique identifier
            cancel_on_cleanup=cancel_on_cleanup
        )
        
        # Track as active
        self._active_workers.add(resource_id)
        self._worker_metadata[resource_id] = {
            'name': worker_name,
            'start_time': time.time(),
            'cancel_on_cleanup': cancel_on_cleanup
        }
        
        # Monitor worker lifecycle
        if auto_release:
            worker.finished.connect(
                lambda: self._on_worker_finished(resource_id)
            )
        
        logger.debug(f"Tracking worker {worker_name} with ID {resource_id}")
        
        return resource_id
        
    def _on_worker_finished(self, resource_id: str):
        """
        Handle worker completion.
        
        Args:
            resource_id: The resource ID of the finished worker
        """
        if resource_id in self._active_workers:
            self._active_workers.discard(resource_id)
            
            # Log runtime if metadata available
            if resource_id in self._worker_metadata:
                metadata = self._worker_metadata[resource_id]
                runtime = time.time() - metadata['start_time']
                logger.debug(
                    f"Worker {metadata['name']} finished after {runtime:.2f}s"
                )
                del self._worker_metadata[resource_id]
                
            # Release the resource
            self.release(resource_id)
            
    def cancel_all_workers(self, timeout_ms: int = 5000) -> bool:
        """
        Cancel all active workers with timeout.
        
        Args:
            timeout_ms: Maximum time to wait for workers to finish
            
        Returns:
            True if all workers stopped within timeout
        """
        if not self._active_workers:
            return True
            
        logger.info(f"Cancelling {len(self._active_workers)} active workers")
        
        # Send cancel signal to all workers
        for resource_id in list(self._active_workers):
            resource_ref = self._resources.get(resource_id)
            if resource_ref:
                worker = resource_ref()
                if worker and hasattr(worker, 'cancel'):
                    worker.cancel()
                    
        # Wait for workers to finish
        start_time = time.time()
        while self._active_workers and (time.time() - start_time) * 1000 < timeout_ms:
            QThread.msleep(100)
            
        # Check if any workers are still running
        still_running = len(self._active_workers)
        if still_running > 0:
            logger.warning(f"{still_running} workers did not stop within timeout")
            
            # Force terminate remaining workers
            for resource_id in list(self._active_workers):
                resource_ref = self._resources.get(resource_id)
                if resource_ref:
                    worker = resource_ref()
                    if worker and worker.isRunning():
                        logger.warning(f"Force terminating worker {resource_id}")
                        worker.terminate()
                        
        return len(self._active_workers) == 0
        
    def get_active_workers(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about active workers.
        
        Returns:
            Dictionary mapping resource IDs to worker metadata
        """
        active = {}
        for resource_id in self._active_workers:
            if resource_id in self._worker_metadata:
                metadata = self._worker_metadata[resource_id].copy()
                metadata['runtime'] = time.time() - metadata['start_time']
                active[resource_id] = metadata
        return active
        
    def is_worker_active(self, resource_id: str) -> bool:
        """
        Check if a specific worker is still active.
        
        Args:
            resource_id: The resource ID to check
            
        Returns:
            True if the worker is active
        """
        if resource_id not in self._active_workers:
            return False
            
        # Verify the worker actually exists and is running
        resource_ref = self._resources.get(resource_id)
        if resource_ref:
            worker = resource_ref()
            if worker and worker.isRunning():
                return True
                
        # Worker is not actually running, clean up
        self._active_workers.discard(resource_id)
        return False
        
    def wait_for_worker(self, resource_id: str, timeout_ms: int = 30000) -> bool:
        """
        Wait for a specific worker to complete.
        
        Args:
            resource_id: The resource ID to wait for
            timeout_ms: Maximum time to wait
            
        Returns:
            True if worker completed within timeout
        """
        if not self.is_worker_active(resource_id):
            return True
            
        resource_ref = self._resources.get(resource_id)
        if resource_ref:
            worker = resource_ref()
            if worker:
                return worker.wait(timeout_ms)
                
        return False
        
    def on_resource_released(self, resource_id: str):
        """
        Hook called when a resource is released.
        
        Args:
            resource_id: The resource being released
        """
        # Clean up worker tracking
        self._active_workers.discard(resource_id)
        if resource_id in self._worker_metadata:
            del self._worker_metadata[resource_id]
            
    def cleanup_all(self):
        """
        Clean up all resources, ensuring workers are properly stopped.
        """
        # Cancel all workers first
        if self._active_workers:
            self.cancel_all_workers(timeout_ms=5000)
            
        # Then do standard cleanup
        super().cleanup_all()
        
        # Clear tracking
        self._active_workers.clear()
        self._worker_metadata.clear()
        
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about worker management.
        
        Returns:
            Dictionary with worker statistics
        """
        return {
            'total_tracked': self.get_resource_count(),
            'active_workers': len(self._active_workers),
            'workers': self.get_active_workers()
        }