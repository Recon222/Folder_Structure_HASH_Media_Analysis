#!/usr/bin/env python3
"""
ResourceManagementService - Centralized resource tracking and lifecycle management for plugin architecture
"""

from typing import Dict, List, Callable, Any, Optional, Set, Tuple
from weakref import WeakKeyDictionary, WeakSet, ref, WeakMethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
import atexit
import sys
import threading
import uuid
import traceback

from PySide6.QtCore import QObject, QTimer, Signal

from core.services.interfaces import (
    IResourceManagementService, ResourceType, ComponentState
)
from core.result_types import Result
from core.exceptions import FSAError

# Initialize logger
import logging
logger = logging.getLogger(__name__)


@dataclass
class TrackedResource:
    """Container for tracked resource information"""
    resource_id: str
    resource_type: ResourceType
    resource_ref: Any  # Can be weak reference
    size_bytes: Optional[int]
    metadata: Dict
    tracked_at: datetime
    component_id: str


@dataclass
class ComponentInfo:
    """Information about a registered component"""
    component_id: str
    component_type: str
    state: ComponentState
    resources: Dict[str, TrackedResource] = field(default_factory=dict)
    cleanup_callbacks: List[Tuple[int, Any]] = field(default_factory=list)  # (priority, callback)
    memory_usage: int = 0
    registered_at: datetime = field(default_factory=datetime.now)


class ResourceManagementService(QObject):
    """
    Centralized resource management for plugin architecture.
    Implements IResourceManagementService interface.
    
    Features:
    - Weak reference tracking to prevent memory leaks
    - Automatic cleanup on component destruction
    - Memory usage monitoring
    - Thread-safe operations
    - Crash recovery support
    """
    
    # Qt Signals for monitoring
    resource_tracked = Signal(str, str, str)  # component_id, resource_id, type
    resource_released = Signal(str, str)      # component_id, resource_id
    component_registered = Signal(str)        # component_id
    component_cleanup = Signal(str)           # component_id
    memory_threshold_exceeded = Signal(str, int)  # component_id, bytes
    
    def __init__(self):
        super().__init__()
        
        # Use weak references to avoid preventing garbage collection
        self._component_registry: WeakKeyDictionary = WeakKeyDictionary()
        self._resource_ids: Set[str] = set()  # Track all resource IDs
        self._lock = threading.RLock()  # Thread safety
        self._cleanup_in_progress = False
        
        # Memory monitoring
        self._memory_limits: Dict[str, int] = {}  # Per-component limits
        self._global_memory_limit: Optional[int] = None
        
        # Statistics
        self._total_resources_tracked = 0
        self._total_resources_released = 0
        
        # Crash recovery - register for app shutdown
        atexit.register(self._emergency_cleanup)
        
        # Periodic cleanup timer (every 60 seconds)
        self._cleanup_timer = QTimer()
        self._cleanup_timer.timeout.connect(self._periodic_cleanup)
        self._cleanup_timer.start(60000)
        
        logger.info("ResourceManagementService initialized")
    
    def register_component(self, component: Any, component_id: str, 
                         component_type: str = "plugin") -> None:
        """Register a component for resource tracking"""
        with self._lock:
            if component in self._component_registry:
                logger.warning(f"Component {component_id} already registered")
                return
                
            info = ComponentInfo(
                component_id=component_id,
                component_type=component_type,
                state=ComponentState.LOADED
            )
            
            self._component_registry[component] = info
            
            # Set up automatic cleanup on component destruction if possible
            if isinstance(component, QObject):
                try:
                    # For QObjects, connect to destroyed signal
                    component.destroyed.connect(lambda: self._on_component_destroyed(component))
                except:
                    pass  # Not all QObjects have accessible destroyed signal
            
            logger.info(f"Registered component: {component_id} (type: {component_type})")
            self.component_registered.emit(component_id)
    
    def unregister_component(self, component: Any) -> None:
        """Unregister component and cleanup resources"""
        self.cleanup_component(component, force=True)
        
        with self._lock:
            if component in self._component_registry:
                del self._component_registry[component]
    
    def track_resource(self, component: Any, resource_type: ResourceType,
                      resource: Any, size_bytes: Optional[int] = None,
                      metadata: Optional[Dict] = None) -> str:
        """Track a resource with optional size and metadata"""
        with self._lock:
            if component not in self._component_registry:
                raise FSAError(
                    f"Component not registered for resource tracking",
                    user_message="Component must be registered before tracking resources"
                )
            
            info = self._component_registry[component]
            resource_id = str(uuid.uuid4())
            
            # Use weak reference for QObjects to prevent circular references
            if isinstance(resource, QObject):
                resource_ref = ref(resource, self._make_cleanup_callback(component, resource_id))
            else:
                resource_ref = resource
            
            tracked = TrackedResource(
                resource_id=resource_id,
                resource_type=resource_type,
                resource_ref=resource_ref,
                size_bytes=size_bytes,
                metadata=metadata or {},
                tracked_at=datetime.now(),
                component_id=info.component_id
            )
            
            info.resources[resource_id] = tracked
            self._resource_ids.add(resource_id)
            
            # Update memory tracking
            if size_bytes:
                info.memory_usage += size_bytes
                self._check_memory_limits(component, info)
            
            self._total_resources_tracked += 1
            
            logger.debug(f"Tracked resource {resource_id} for {info.component_id}")
            self.resource_tracked.emit(info.component_id, resource_id, resource_type.value)
            
            return resource_id
    
    def release_resource(self, component: Any, resource_id: str) -> bool:
        """Release a specific tracked resource"""
        with self._lock:
            if component not in self._component_registry:
                return False
                
            info = self._component_registry[component]
            
            if resource_id not in info.resources:
                return False
            
            tracked = info.resources[resource_id]
            
            # Update memory tracking
            if tracked.size_bytes:
                info.memory_usage -= tracked.size_bytes
            
            # Cleanup based on resource type
            self._cleanup_resource(tracked)
            
            # Remove from tracking
            del info.resources[resource_id]
            self._resource_ids.discard(resource_id)
            
            self._total_resources_released += 1
            
            logger.debug(f"Released resource {resource_id} for {info.component_id}")
            self.resource_released.emit(info.component_id, resource_id)
            
            return True
    
    def register_cleanup(self, component: Any, callback: Callable,
                        priority: int = 0) -> None:
        """Register cleanup callback with priority"""
        with self._lock:
            if component not in self._component_registry:
                raise FSAError(
                    "Component not registered",
                    user_message="Component must be registered before adding cleanup callbacks"
                )
            
            info = self._component_registry[component]
            
            # Use WeakMethod for bound methods to prevent circular references
            if hasattr(callback, '__self__'):
                callback_ref = WeakMethod(callback)
            else:
                callback_ref = callback
                
            info.cleanup_callbacks.append((priority, callback_ref))
            # Sort by priority (higher priority first)
            info.cleanup_callbacks.sort(key=lambda x: x[0], reverse=True)
    
    @contextmanager
    def managed_resource(self, component: Any, resource_type: ResourceType):
        """Context manager for automatic resource cleanup"""
        resource_id = None
        resource = None
        
        try:
            # Resource will be set by the caller
            yield resource
            
            # Track the resource if it was created
            if resource is not None:
                resource_id = self.track_resource(component, resource_type, resource)
                
        finally:
            # Cleanup on exit
            if resource_id:
                self.release_resource(component, resource_id)
    
    def cleanup_component(self, component: Any, force: bool = False) -> None:
        """Clean up all resources for a component"""
        with self._lock:
            if component not in self._component_registry:
                return
            
            info = self._component_registry[component]
            
            if self._cleanup_in_progress and not force:
                return
                
            self._cleanup_in_progress = True
            
            try:
                logger.info(f"Cleaning up component: {info.component_id}")
                self.component_cleanup.emit(info.component_id)
                
                # Update state
                info.state = ComponentState.CLEANING
                
                # Run cleanup callbacks in priority order
                for priority, callback_ref in info.cleanup_callbacks:
                    try:
                        # Resolve weak reference
                        if isinstance(callback_ref, (ref, WeakMethod)):
                            callback = callback_ref()
                        else:
                            callback = callback_ref
                            
                        if callback:
                            callback()
                    except Exception as e:
                        logger.error(f"Cleanup callback failed for {info.component_id}: {e}")
                        if not force:
                            raise
                
                # Release all tracked resources
                resource_ids = list(info.resources.keys())
                for resource_id in resource_ids:
                    try:
                        self.release_resource(component, resource_id)
                    except Exception as e:
                        logger.error(f"Failed to release resource {resource_id}: {e}")
                        if not force:
                            raise
                
                # Clear remaining data
                info.resources.clear()
                info.cleanup_callbacks.clear()
                info.memory_usage = 0
                info.state = ComponentState.DESTROYED
                
                logger.info(f"Component cleanup complete: {info.component_id}")
                
            finally:
                self._cleanup_in_progress = False
    
    def get_memory_usage(self) -> Dict[str, int]:
        """Get memory usage by component"""
        with self._lock:
            return {
                info.component_id: info.memory_usage 
                for info in self._component_registry.values()
            }
    
    def get_resource_count(self, component: Any = None) -> Dict[str, int]:
        """Get resource count by type"""
        with self._lock:
            if component:
                if component not in self._component_registry:
                    return {}
                info = self._component_registry[component]
                counts = {}
                for resource in info.resources.values():
                    type_name = resource.resource_type.value
                    counts[type_name] = counts.get(type_name, 0) + 1
                return counts
            else:
                # Global resource count
                counts = {}
                for info in self._component_registry.values():
                    for resource in info.resources.values():
                        type_name = resource.resource_type.value
                        counts[type_name] = counts.get(type_name, 0) + 1
                return counts
    
    def set_component_state(self, component: Any, state: ComponentState) -> None:
        """Update component lifecycle state"""
        with self._lock:
            if component in self._component_registry:
                self._component_registry[component].state = state
                comp_id = self._component_registry[component].component_id
                logger.debug(f"Component state changed: {comp_id} -> {state.value}")
    
    def get_component_state(self, component: Any) -> Optional[ComponentState]:
        """Get current component state"""
        with self._lock:
            if component in self._component_registry:
                return self._component_registry[component].state
            return None
    
    def set_memory_limit(self, component_id: str, limit_bytes: int) -> None:
        """Set memory limit for a component"""
        self._memory_limits[component_id] = limit_bytes
        logger.info(f"Set memory limit for {component_id}: {limit_bytes:,} bytes")
    
    def set_global_memory_limit(self, limit_bytes: int) -> None:
        """Set global memory limit"""
        self._global_memory_limit = limit_bytes
        logger.info(f"Set global memory limit: {limit_bytes:,} bytes")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get resource management statistics"""
        with self._lock:
            return {
                "components_registered": len(self._component_registry),
                "total_resources_tracked": self._total_resources_tracked,
                "total_resources_released": self._total_resources_released,
                "active_resources": len(self._resource_ids),
                "memory_usage": self.get_memory_usage(),
                "resource_counts": self.get_resource_count()
            }
    
    # Private methods
    
    def _cleanup_resource(self, tracked: TrackedResource) -> None:
        """Cleanup specific resource based on type"""
        try:
            # Resolve weak reference if needed
            if isinstance(tracked.resource_ref, ref):
                resource = tracked.resource_ref()
            else:
                resource = tracked.resource_ref
            
            if resource is None:
                return
                
            # Type-specific cleanup
            if tracked.resource_type == ResourceType.QOBJECT:
                if isinstance(resource, QObject):
                    # Check if object still exists and has no parent
                    try:
                        if not resource.parent():
                            resource.deleteLater()
                    except RuntimeError:
                        # Object already deleted
                        pass
                    
            elif tracked.resource_type == ResourceType.THREAD:
                if hasattr(resource, 'quit'):
                    resource.quit()
                if hasattr(resource, 'wait'):
                    resource.wait(1000)  # Wait up to 1 second
                    
            elif tracked.resource_type == ResourceType.FILE_HANDLE:
                if hasattr(resource, 'close'):
                    resource.close()
                    
            elif tracked.resource_type == ResourceType.WORKER:
                if hasattr(resource, 'cancel'):
                    resource.cancel()
                    
            # Custom cleanup via metadata
            if 'cleanup_func' in tracked.metadata:
                cleanup_func = tracked.metadata['cleanup_func']
                if cleanup_func:
                    cleanup_func(resource)
                
        except Exception as e:
            logger.error(f"Error cleaning up resource {tracked.resource_id}: {e}")
    
    def _make_cleanup_callback(self, component: Any, resource_id: str):
        """Create a cleanup callback for weak references"""
        def cleanup(ref):
            try:
                # Component might already be gone
                if component in self._component_registry:
                    self.release_resource(component, resource_id)
            except:
                pass  # Ignore errors in weak reference cleanup
        return cleanup
    
    def _check_memory_limits(self, component: Any, info: ComponentInfo) -> None:
        """Check and enforce memory limits"""
        # Check component-specific limit
        if info.component_id in self._memory_limits:
            limit = self._memory_limits[info.component_id]
            if info.memory_usage > limit:
                logger.warning(
                    f"Component {info.component_id} exceeded memory limit: "
                    f"{info.memory_usage:,} > {limit:,}"
                )
                self.memory_threshold_exceeded.emit(info.component_id, info.memory_usage)
        
        # Check global limit
        if self._global_memory_limit:
            total_usage = sum(i.memory_usage for i in self._component_registry.values())
            if total_usage > self._global_memory_limit:
                logger.warning(
                    f"Global memory limit exceeded: "
                    f"{total_usage:,} > {self._global_memory_limit:,}"
                )
    
    def _on_component_destroyed(self, component: Any) -> None:
        """Handle QObject component destruction"""
        try:
            self.cleanup_component(component, force=True)
        except:
            pass  # Ignore errors during destruction
    
    def _periodic_cleanup(self) -> None:
        """Periodic cleanup of orphaned resources"""
        with self._lock:
            try:
                for info in list(self._component_registry.values()):
                    # Clean up resources with dead weak references
                    dead_resources = []
                    for resource_id, tracked in info.resources.items():
                        if isinstance(tracked.resource_ref, ref):
                            if tracked.resource_ref() is None:
                                dead_resources.append(resource_id)
                    
                    for resource_id in dead_resources:
                        del info.resources[resource_id]
                        self._resource_ids.discard(resource_id)
                        
                    if dead_resources:
                        logger.debug(
                            f"Cleaned up {len(dead_resources)} orphaned resources "
                            f"for {info.component_id}"
                        )
            except Exception as e:
                logger.error(f"Error during periodic cleanup: {e}")
    
    def _emergency_cleanup(self) -> None:
        """Emergency cleanup on application shutdown"""
        logger.info("ResourceManagementService: Emergency cleanup initiated")
        
        try:
            # Stop the cleanup timer
            if hasattr(self, '_cleanup_timer'):
                self._cleanup_timer.stop()
            
            # Force cleanup all components
            components = list(self._component_registry.keys())
            for component in components:
                try:
                    self.cleanup_component(component, force=True)
                except:
                    pass  # Best effort in emergency
                    
            logger.info("ResourceManagementService: Emergency cleanup complete")
            
        except Exception as e:
            logger.critical(f"Emergency cleanup failed: {e}")