"""
Base resource coordinator for managing resource lifecycles.

Provides a simplified interface for tracking and managing resources
through the ResourceManagementService.
"""

import logging
import weakref
from typing import Any, Dict, Optional, Callable
from PySide6.QtCore import QObject, QThread

from core.services.interfaces import IResourceManagementService
from core.services.service_registry import get_service
from core.services.resource_management_service import ResourceType

logger = logging.getLogger(__name__)


class BaseResourceCoordinator:
    """
    Base coordinator for resource management.
    
    This class provides a simplified interface for controllers to manage
    resources through the ResourceManagementService without embedding
    resource management logic in UI components.
    """
    
    def __init__(self, component_id: str, service: Optional[IResourceManagementService] = None):
        """
        Initialize the resource coordinator.
        
        Args:
            component_id: Unique identifier for the component
            service: Optional service instance (defaults to getting from registry)
        """
        self._component_id = component_id
        self._service = service or get_service(IResourceManagementService)
        self._resources: Dict[str, weakref.ref] = {}
        self._component_ref: Optional[weakref.ref] = None
        self._cleanup_priority = 10
        self.debug_mode = False  # Can be enabled for debugging
        
    def bind_to_component(self, component: Any) -> 'BaseResourceCoordinator':
        """
        Bind the coordinator to a component with automatic registration.
        
        Args:
            component: The component to bind to (usually a controller)
            
        Returns:
            Self for fluent interface
        """
        self._component_ref = weakref.ref(component)
        
        if self._service:
            # Register with service
            self._service.register_component(
                component, 
                self._component_id,
                self._get_component_type(component)
            )
            
            # Register cleanup callback
            self._service.register_cleanup(
                component,
                self.cleanup_all,
                priority=self._cleanup_priority
            )
        
        return self
        
    def track_resource(self,
                      resource: Any,
                      resource_type: ResourceType = ResourceType.CUSTOM,
                      name: Optional[str] = None,
                      cleanup_handler: Optional[Callable] = None,
                      **metadata) -> str:
        """
        Track a resource with the coordinator.
        
        Args:
            resource: The resource to track
            resource_type: Type of the resource
            name: Optional name for the resource
            cleanup_handler: Optional cleanup handler
            **metadata: Additional metadata
            
        Returns:
            Resource ID for tracking
        """
        component = self._get_component()
        if not component:
            raise RuntimeError(f"Component {self._component_id} no longer exists")
        
        if not self._service:
            logger.warning(f"No ResourceManagementService available for {self._component_id}")
            return f"untracked_{id(resource)}"
            
        # Track with service
        resource_id = self._service.track_resource(
            component,
            resource_type,
            resource,
            size_bytes=metadata.get('size_bytes'),
            metadata={
                'name': name or resource.__class__.__name__,
                'cleanup_func': cleanup_handler,
                **metadata
            }
        )
        
        # Store weak reference
        self._resources[resource_id] = weakref.ref(resource)
        
        # Setup auto-cleanup for QObjects
        if isinstance(resource, QObject):
            resource.destroyed.connect(
                lambda: self.release(resource_id)
            )
            
        return resource_id
        
    def track_worker(self, worker: QThread, name: Optional[str] = None) -> str:
        """
        Track a worker thread with automatic cleanup on finish.
        
        Args:
            worker: The worker thread to track
            name: Optional name for the worker
            
        Returns:
            Resource ID for tracking
        """
        def cleanup_worker(w):
            """Cleanup handler for worker threads."""
            if w and w.isRunning():
                if hasattr(w, 'cancel'):
                    w.cancel()
                w.quit()
                if not w.wait(2000):
                    logger.warning(f"Force terminating worker: {name}")
                    w.terminate()
        
        resource_id = self.track_resource(
            worker,
            ResourceType.WORKER,
            name=name or worker.__class__.__name__,
            cleanup_handler=cleanup_worker
        )
        
        # Auto-cleanup on worker finish
        worker.finished.connect(lambda: self.release(resource_id))
        
        return resource_id
        
    def release(self, resource_id: str):
        """
        Release a specific resource.
        
        Args:
            resource_id: The resource ID to release
        """
        if resource_id in self._resources:
            # Hook for debugging
            if self.debug_mode:
                logger.debug(f"Releasing resource {resource_id} from {self._component_id}")
            
            # Call the release hook
            self.on_resource_released(resource_id)
            
            # Remove from tracking
            del self._resources[resource_id]
            
            # Release from service
            if self._service:
                component = self._get_component()
                if component:
                    self._service.release_resource(component, resource_id)
                    
    def on_resource_released(self, resource_id: str):
        """
        Hook called when a resource is released.
        Can be overridden by subclasses for custom behavior.
        
        Args:
            resource_id: The resource being released
        """
        pass  # Override in subclasses if needed
        
    def cleanup_all(self):
        """
        Clean up all tracked resources.
        """
        resource_ids = list(self._resources.keys())
        for resource_id in resource_ids:
            try:
                self.release(resource_id)
            except Exception as e:
                logger.error(f"Error releasing resource {resource_id}: {e}")
                
        self._resources.clear()
        
    def get_resource_count(self) -> int:
        """
        Get the count of actively tracked resources.
        
        Returns:
            Number of tracked resources
        """
        # Clean up dead references
        dead_refs = [rid for rid, ref in self._resources.items() if ref() is None]
        for rid in dead_refs:
            del self._resources[rid]
            
        return len(self._resources)
        
    def _get_component(self) -> Optional[Any]:
        """
        Get the component this coordinator is bound to.
        
        Returns:
            The component or None if no longer exists
        """
        if self._component_ref:
            return self._component_ref()
        return None
        
    def _get_component_type(self, component: Any) -> str:
        """
        Determine the component type for registration.
        
        Args:
            component: The component to check
            
        Returns:
            Component type string
        """
        if hasattr(component, '__class__'):
            class_name = component.__class__.__name__
            if 'Controller' in class_name:
                return 'controller'
            elif 'Tab' in class_name:
                return 'tab'
            elif 'Widget' in class_name:
                return 'widget'
        return 'component'
        
    def __del__(self):
        """
        Safety check on destruction to warn about unreleased resources.
        """
        if hasattr(self, '_resources') and self._resources:
            logger.warning(
                f"Coordinator {self._component_id} destroyed with "
                f"{len(self._resources)} active resources"
            )
            # Try to clean up
            try:
                self.cleanup_all()
            except Exception as e:
                logger.error(f"Error during coordinator cleanup: {e}")