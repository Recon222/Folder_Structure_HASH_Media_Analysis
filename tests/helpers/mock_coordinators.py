"""
Mock resource coordinators for testing.

Provides simplified test doubles for resource coordinators that
track operations without requiring the full ResourceManagementService.
"""

from typing import List, Tuple, Any, Optional, Dict


class MockResourceCoordinator:
    """
    Simple test double for BaseResourceCoordinator.
    
    Tracks all operations for verification in tests without
    requiring actual resource management infrastructure.
    """
    
    def __init__(self):
        """Initialize the mock coordinator."""
        self.tracked: List[Tuple[str, Any, Optional[str]]] = []
        self.released: List[str] = []
        self.bound_component = None
        self.cleanup_called = False
        self._next_id = 0
        
    def bind_to_component(self, component: Any) -> 'MockResourceCoordinator':
        """
        Mock binding to component.
        
        Args:
            component: The component to bind to
            
        Returns:
            Self for fluent interface
        """
        self.bound_component = component
        return self
        
    def track_resource(self,
                       resource: Any,
                       resource_type: Any = None,
                       name: Optional[str] = None,
                       **kwargs) -> str:
        """
        Mock resource tracking.
        
        Args:
            resource: The resource to track
            resource_type: Type of the resource
            name: Optional name
            **kwargs: Additional arguments
            
        Returns:
            Mock resource ID
        """
        resource_id = f"mock_id_{self._next_id}"
        self._next_id += 1
        
        self.tracked.append((
            resource_type or 'CUSTOM',
            resource,
            name,
            kwargs
        ))
        
        return resource_id
        
    def track_worker(self, worker: Any, name: Optional[str] = None) -> str:
        """
        Mock worker tracking.
        
        Args:
            worker: The worker to track
            name: Optional name
            
        Returns:
            Mock resource ID
        """
        return self.track_resource(worker, 'WORKER', name)
        
    def release(self, resource_id: str):
        """
        Mock resource release.
        
        Args:
            resource_id: The resource ID to release
        """
        self.released.append(resource_id)
        
    def cleanup_all(self):
        """Mock cleanup all resources."""
        self.cleanup_called = True
        self.tracked.clear()
        
    def get_resource_count(self) -> int:
        """
        Get count of tracked resources.
        
        Returns:
            Number of tracked resources
        """
        return len(self.tracked) - len(self.released)
        
    def on_resource_released(self, resource_id: str):
        """Mock release hook."""
        pass  # Can be overridden in tests
        
    def get_tracked_resources(self) -> List[Tuple[str, Any, Optional[str]]]:
        """
        Get list of tracked resources for verification.
        
        Returns:
            List of (type, resource, name) tuples
        """
        return [(t[0], t[1], t[2]) for t in self.tracked]
        
    def was_resource_tracked(self, resource: Any) -> bool:
        """
        Check if a specific resource was tracked.
        
        Args:
            resource: The resource to check
            
        Returns:
            True if resource was tracked
        """
        return any(t[1] == resource for t in self.tracked)


class MockWorkerResourceCoordinator(MockResourceCoordinator):
    """
    Mock specialized coordinator for worker threads.
    
    Adds worker-specific tracking capabilities for testing.
    """
    
    def __init__(self):
        """Initialize the mock worker coordinator."""
        super().__init__()
        self.active_workers: Dict[str, Dict[str, Any]] = {}
        self.cancelled_workers: List[str] = []
        self.waited_workers: List[Tuple[str, int]] = []
        
    def track_worker(self,
                    worker: Any,
                    name: Optional[str] = None,
                    cancel_on_cleanup: bool = True,
                    auto_release: bool = True) -> str:
        """
        Mock enhanced worker tracking.
        
        Args:
            worker: The worker to track
            name: Optional name
            cancel_on_cleanup: Whether to cancel on cleanup
            auto_release: Whether to auto-release
            
        Returns:
            Mock resource ID
        """
        resource_id = super().track_worker(worker, name)
        
        self.active_workers[resource_id] = {
            'worker': worker,
            'name': name or worker.__class__.__name__,
            'cancel_on_cleanup': cancel_on_cleanup,
            'auto_release': auto_release
        }
        
        return resource_id
        
    def cancel_all_workers(self, timeout_ms: int = 5000) -> bool:
        """
        Mock cancel all workers.
        
        Args:
            timeout_ms: Timeout in milliseconds
            
        Returns:
            Always returns True for testing
        """
        self.cancelled_workers.extend(self.active_workers.keys())
        self.active_workers.clear()
        return True
        
    def is_worker_active(self, resource_id: str) -> bool:
        """
        Check if worker is active.
        
        Args:
            resource_id: The resource ID to check
            
        Returns:
            True if worker is in active list
        """
        return resource_id in self.active_workers
        
    def wait_for_worker(self, resource_id: str, timeout_ms: int = 30000) -> bool:
        """
        Mock wait for worker.
        
        Args:
            resource_id: The resource ID to wait for
            timeout_ms: Timeout in milliseconds
            
        Returns:
            Always returns True for testing
        """
        self.waited_workers.append((resource_id, timeout_ms))
        return True
        
    def get_active_workers(self) -> Dict[str, Dict[str, Any]]:
        """
        Get active workers.
        
        Returns:
            Dictionary of active workers
        """
        return self.active_workers.copy()
        
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get mock statistics.
        
        Returns:
            Mock statistics dictionary
        """
        return {
            'total_tracked': self.get_resource_count(),
            'active_workers': len(self.active_workers),
            'workers': self.get_active_workers()
        }