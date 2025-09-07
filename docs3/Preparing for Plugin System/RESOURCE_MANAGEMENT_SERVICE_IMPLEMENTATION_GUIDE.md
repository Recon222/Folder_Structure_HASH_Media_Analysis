# Resource Management Service Implementation Guide
## Comprehensive Strategy for Plugin Architecture Resource Management

### Table of Contents
1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Phase 1: Core Service Implementation](#phase-1-core-service-implementation)
4. [Phase 2: Integration Patterns](#phase-2-integration-patterns)
5. [Phase 3: MediaAnalysisTab Migration](#phase-3-mediaanalysistab-migration)
6. [Phase 4: System-Wide Migration](#phase-4-system-wide-migration)
7. [Phase 5: Plugin System Integration](#phase-5-plugin-system-integration)
8. [Testing Strategy](#testing-strategy)
9. [Performance Monitoring](#performance-monitoring)
10. [Best Practices and Patterns](#best-practices-and-patterns)

---

## Executive Summary

This guide provides a comprehensive, phase-by-phase implementation strategy for transitioning from MainWindow-based resource cleanup to a sophisticated, plugin-ready Resource Management Service. Based on industry best practices from VSCode, IntelliJ, and Qt plugin architectures, this approach will:

- **Decouple resource management** from MainWindow
- **Enable dynamic plugin loading** with automatic resource tracking
- **Prevent memory leaks** through weak references and lifecycle management
- **Provide comprehensive monitoring** of resource usage
- **Ensure graceful cleanup** even on crashes or forced unloads

### Key Benefits

| Current Approach | Resource Management Service |
|------------------|---------------------------|
| ❌ Hard-coded cleanup in MainWindow | ✅ Dynamic registration and tracking |
| ❌ Tight coupling between tabs | ✅ Loose coupling via service interface |
| ❌ Manual resource tracking | ✅ Automatic resource lifecycle management |
| ❌ No memory monitoring | ✅ Real-time memory usage tracking |
| ❌ Plugin-incompatible | ✅ Plugin-ready architecture |

---

## Architecture Overview

### Core Concepts

The Resource Management Service acts as a **centralized broker** for all resource allocation, tracking, and cleanup operations. It follows these principles:

1. **Separation of Concerns**: The service manages resources; plugins/tabs focus on their functionality
2. **Lifecycle Management**: Explicit states (loaded → initialized → active → cleanup → destroyed)
3. **Weak References**: Prevents circular dependencies and memory leaks
4. **Context Managers**: Ensures deterministic resource cleanup
5. **Monitoring & Auditing**: Tracks resource usage per component

### Component Hierarchy

```
ResourceManagementService (Core)
├── Component Registry (WeakKeyDictionary)
├── Resource Tracker
│   ├── Memory Resources (thumbnails, buffers)
│   ├── System Resources (file handles, threads)
│   └── Qt Resources (QObjects, widgets)
├── Cleanup Manager
│   ├── Callback Registry
│   ├── Force Cleanup Handler
│   └── Crash Recovery
├── Memory Monitor
│   └── Usage Statistics
└── Plugin Interface
    ├── Registration API
    ├── Resource Request API
    └── Lifecycle Hooks
```

---

## Phase 1: Core Service Implementation

### Step 1.1: Create Service Interface

```python
# core/services/interfaces.py (add to existing file)

from abc import ABC, abstractmethod
from typing import Dict, List, Callable, Any, Optional, ContextManager
from enum import Enum

class ResourceType(Enum):
    """Types of resources that can be tracked"""
    MEMORY = "memory"
    FILE_HANDLE = "file_handle"
    THREAD = "thread"
    QOBJECT = "qobject"
    THUMBNAIL = "thumbnail"
    MAP = "map"
    WORKER = "worker"
    CUSTOM = "custom"

class ComponentState(Enum):
    """Lifecycle states for components"""
    LOADED = "loaded"
    INITIALIZED = "initialized"
    ACTIVE = "active"
    PAUSED = "paused"
    CLEANING = "cleaning"
    DESTROYED = "destroyed"

class IResourceManagementService(ABC):
    """Interface for centralized resource management"""
    
    @abstractmethod
    def register_component(self, component: Any, component_id: str, 
                         component_type: str = "plugin") -> None:
        """Register a component for resource tracking"""
        pass
    
    @abstractmethod
    def unregister_component(self, component: Any) -> None:
        """Unregister a component and cleanup resources"""
        pass
    
    @abstractmethod
    def track_resource(self, component: Any, resource_type: ResourceType,
                      resource: Any, size_bytes: Optional[int] = None,
                      metadata: Optional[Dict] = None) -> str:
        """Track a resource with optional size and metadata"""
        pass
    
    @abstractmethod
    def release_resource(self, component: Any, resource_id: str) -> bool:
        """Release a specific tracked resource"""
        pass
    
    @abstractmethod
    def register_cleanup(self, component: Any, callback: Callable,
                        priority: int = 0) -> None:
        """Register cleanup callback with priority"""
        pass
    
    @abstractmethod
    def managed_resource(self, component: Any, 
                        resource_type: ResourceType) -> ContextManager:
        """Context manager for automatic resource cleanup"""
        pass
    
    @abstractmethod
    def cleanup_component(self, component: Any, force: bool = False) -> None:
        """Clean up all resources for a component"""
        pass
    
    @abstractmethod
    def get_memory_usage(self) -> Dict[str, int]:
        """Get memory usage by component"""
        pass
    
    @abstractmethod
    def get_resource_count(self, component: Any = None) -> Dict[str, int]:
        """Get resource count by type"""
        pass
    
    @abstractmethod
    def set_component_state(self, component: Any, state: ComponentState) -> None:
        """Update component lifecycle state"""
        pass
    
    @abstractmethod
    def get_component_state(self, component: Any) -> Optional[ComponentState]:
        """Get current component state"""
        pass
```

### Step 1.2: Implement Core Service

```python
# core/services/resource_management_service.py

from typing import Dict, List, Callable, Any, Optional, Set
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
from core.logger import AppLogger
from core.services.interfaces import (
    IResourceManagementService, ResourceType, ComponentState
)
from core.result_types import Result
from core.exceptions import FSAError

logger = AppLogger.get_instance()

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
    cleanup_callbacks: List[Callable] = field(default_factory=list)
    memory_usage: int = 0
    registered_at: datetime = field(default_factory=datetime.now)
    
class ResourceManagementService(QObject, IResourceManagementService):
    """
    Centralized resource management for plugin architecture.
    
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
            
            # Set up automatic cleanup on component destruction
            if hasattr(component, '__del__'):
                original_del = component.__del__
                def wrapped_del():
                    self.cleanup_component(component)
                    original_del()
                component.__del__ = wrapped_del
            
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
                raise FSAError(f"Component not registered for resource tracking")
            
            info = self._component_registry[component]
            resource_id = str(uuid.uuid4())
            
            # Use weak reference for QObjects
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
                raise FSAError("Component not registered")
            
            info = self._component_registry[component]
            
            # Use WeakMethod for bound methods to prevent circular references
            if hasattr(callback, '__self__'):
                callback_ref = WeakMethod(callback)
            else:
                callback_ref = callback
                
            info.cleanup_callbacks.append((priority, callback_ref))
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
                
                # Run cleanup callbacks
                for priority, callback_ref in info.cleanup_callbacks:
                    try:
                        # Resolve weak reference
                        callback = callback_ref() if isinstance(callback_ref, (ref, WeakMethod)) else callback_ref
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
                logger.debug(f"Component state changed: {self._component_registry[component].component_id} -> {state.value}")
    
    def get_component_state(self, component: Any) -> Optional[ComponentState]:
        """Get current component state"""
        with self._lock:
            if component in self._component_registry:
                return self._component_registry[component].state
            return None
    
    def set_memory_limit(self, component_id: str, limit_bytes: int) -> None:
        """Set memory limit for a component"""
        self._memory_limits[component_id] = limit_bytes
    
    def set_global_memory_limit(self, limit_bytes: int) -> None:
        """Set global memory limit"""
        self._global_memory_limit = limit_bytes
    
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
            resource = tracked.resource_ref() if isinstance(tracked.resource_ref, ref) else tracked.resource_ref
            
            if resource is None:
                return
                
            # Type-specific cleanup
            if tracked.resource_type == ResourceType.QOBJECT:
                if isinstance(resource, QObject) and not resource.parent():
                    resource.deleteLater()
                    
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
                cleanup_func(resource)
                
        except Exception as e:
            logger.error(f"Error cleaning up resource {tracked.resource_id}: {e}")
    
    def _make_cleanup_callback(self, component: Any, resource_id: str):
        """Create a cleanup callback for weak references"""
        def cleanup(ref):
            try:
                self.release_resource(component, resource_id)
            except:
                pass  # Component might already be gone
        return cleanup
    
    def _check_memory_limits(self, component: Any, info: ComponentInfo) -> None:
        """Check and enforce memory limits"""
        # Check component-specific limit
        if info.component_id in self._memory_limits:
            limit = self._memory_limits[info.component_id]
            if info.memory_usage > limit:
                logger.warning(f"Component {info.component_id} exceeded memory limit: {info.memory_usage} > {limit}")
                self.memory_threshold_exceeded.emit(info.component_id, info.memory_usage)
        
        # Check global limit
        if self._global_memory_limit:
            total_usage = sum(i.memory_usage for i in self._component_registry.values())
            if total_usage > self._global_memory_limit:
                logger.warning(f"Global memory limit exceeded: {total_usage} > {self._global_memory_limit}")
    
    def _periodic_cleanup(self) -> None:
        """Periodic cleanup of orphaned resources"""
        with self._lock:
            for info in list(self._component_registry.values()):
                # Clean up resources with dead weak references
                dead_resources = []
                for resource_id, tracked in info.resources.items():
                    if isinstance(tracked.resource_ref, ref) and tracked.resource_ref() is None:
                        dead_resources.append(resource_id)
                
                for resource_id in dead_resources:
                    del info.resources[resource_id]
                    self._resource_ids.discard(resource_id)
                    
                if dead_resources:
                    logger.debug(f"Cleaned up {len(dead_resources)} orphaned resources for {info.component_id}")
    
    def _emergency_cleanup(self) -> None:
        """Emergency cleanup on application shutdown"""
        logger.info("ResourceManagementService: Emergency cleanup initiated")
        
        try:
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
```

### Step 1.3: Register Service with ServiceRegistry

```python
# core/services/service_config.py (update existing file)

from core.services.resource_management_service import ResourceManagementService
from core.services.interfaces import IResourceManagementService

def register_services(registry: ServiceRegistry):
    """Register all services with the registry"""
    
    # ... existing service registrations ...
    
    # Register Resource Management Service (singleton)
    resource_service = ResourceManagementService()
    registry.register(IResourceManagementService, resource_service)
    
    logger.info("Resource Management Service registered")
```

---

## Phase 2: Integration Patterns

### Step 2.1: Create Base Plugin Class

```python
# core/plugin_system/plugin_base.py (new file)

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal

from core.services.interfaces import IResourceManagementService, ComponentState
from core.services.service_registry import get_service
from core.logger import AppLogger

logger = AppLogger.get_instance()

class PluginBase(QWidget, ABC):
    """
    Base class for all plugins/tabs with automatic resource management.
    
    Provides:
    - Automatic registration with ResourceManagementService
    - Lifecycle management
    - Resource tracking helpers
    - Cleanup coordination
    """
    
    # Signals
    plugin_activated = Signal()
    plugin_deactivated = Signal()
    resource_tracked = Signal(str)  # resource_id
    
    def __init__(self, plugin_id: str, plugin_type: str = "plugin", parent=None):
        super().__init__(parent)
        
        self.plugin_id = plugin_id
        self.plugin_type = plugin_type
        self._resource_manager: Optional[IResourceManagementService] = None
        self._is_initialized = False
        
        # Auto-register with resource manager
        self._register_with_resource_manager()
    
    def _register_with_resource_manager(self):
        """Register this plugin with the resource management service"""
        try:
            self._resource_manager = get_service(IResourceManagementService)
            if self._resource_manager:
                self._resource_manager.register_component(
                    self, 
                    self.plugin_id, 
                    self.plugin_type
                )
                
                # Register our cleanup method
                self._resource_manager.register_cleanup(
                    self, 
                    self._cleanup_resources,
                    priority=10  # Higher priority for plugin cleanup
                )
                
                logger.info(f"Plugin {self.plugin_id} registered with ResourceManagementService")
                
        except Exception as e:
            logger.warning(f"Could not register {self.plugin_id} with ResourceManagementService: {e}")
            self._resource_manager = None
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the plugin. Override in subclasses.
        Should return True if initialization successful.
        """
        pass
    
    @abstractmethod
    def _cleanup_resources(self):
        """
        Clean up plugin-specific resources. Override in subclasses.
        Called by resource manager during cleanup.
        """
        pass
    
    def activate(self):
        """Activate the plugin"""
        if not self._is_initialized:
            if self.initialize():
                self._is_initialized = True
            else:
                logger.error(f"Failed to initialize plugin {self.plugin_id}")
                return
        
        if self._resource_manager:
            self._resource_manager.set_component_state(self, ComponentState.ACTIVE)
        
        self.plugin_activated.emit()
        logger.info(f"Plugin {self.plugin_id} activated")
    
    def deactivate(self):
        """Deactivate the plugin"""
        if self._resource_manager:
            self._resource_manager.set_component_state(self, ComponentState.PAUSED)
        
        self.plugin_deactivated.emit()
        logger.info(f"Plugin {self.plugin_id} deactivated")
    
    def track_resource(self, resource_type, resource, size_bytes=None, metadata=None):
        """
        Helper method to track a resource.
        Returns resource_id for later release.
        """
        if self._resource_manager:
            resource_id = self._resource_manager.track_resource(
                self, resource_type, resource, size_bytes, metadata
            )
            self.resource_tracked.emit(resource_id)
            return resource_id
        return None
    
    def release_resource(self, resource_id: str):
        """Helper method to release a tracked resource"""
        if self._resource_manager:
            return self._resource_manager.release_resource(self, resource_id)
        return False
    
    def get_memory_usage(self) -> int:
        """Get this plugin's current memory usage"""
        if self._resource_manager:
            usage = self._resource_manager.get_memory_usage()
            return usage.get(self.plugin_id, 0)
        return 0
    
    def closeEvent(self, event):
        """Handle widget close event"""
        self.deactivate()
        if self._resource_manager:
            self._resource_manager.cleanup_component(self)
        super().closeEvent(event)
```

### Step 2.2: Create Resource Tracking Decorators

```python
# core/plugin_system/decorators.py (new file)

from functools import wraps
from typing import Callable, Any
from core.services.interfaces import ResourceType
from core.logger import AppLogger

logger = AppLogger.get_instance()

def track_resource(resource_type: ResourceType, 
                  size_func: Callable[[Any], int] = None,
                  metadata_func: Callable[[Any], dict] = None):
    """
    Decorator to automatically track resources returned by methods.
    
    Args:
        resource_type: Type of resource being created
        size_func: Optional function to calculate resource size
        metadata_func: Optional function to provide metadata
    
    Example:
        @track_resource(ResourceType.THUMBNAIL, 
                       size_func=lambda img: len(img) if isinstance(img, bytes) else 0)
        def load_thumbnail(self, path):
            return load_image_data(path)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Call the original function
            result = func(self, *args, **kwargs)
            
            # Track the resource if we have a resource manager
            if result is not None and hasattr(self, '_resource_manager') and self._resource_manager:
                try:
                    size = size_func(result) if size_func else None
                    metadata = metadata_func(result) if metadata_func else {}
                    
                    resource_id = self._resource_manager.track_resource(
                        self, resource_type, result, size, metadata
                    )
                    
                    # Store resource_id on the object if possible
                    if hasattr(result, '__dict__'):
                        result._resource_id = resource_id
                        
                except Exception as e:
                    logger.warning(f"Failed to track resource from {func.__name__}: {e}")
            
            return result
        return wrapper
    return decorator

def cleanup_on_error(cleanup_func: Callable):
    """
    Decorator to ensure cleanup happens even on exceptions.
    
    Args:
        cleanup_func: Function to call for cleanup (called with self)
        
    Example:
        @cleanup_on_error(lambda self: self.cancel_operation())
        def risky_operation(self):
            # ... code that might fail ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                try:
                    cleanup_func(self)
                except Exception as cleanup_error:
                    logger.error(f"Cleanup failed after error: {cleanup_error}")
                raise e
        return wrapper
    return decorator

def with_managed_resource(resource_type: ResourceType):
    """
    Decorator to use resource manager's context manager.
    
    The decorated function should yield the resource.
    
    Example:
        @with_managed_resource(ResourceType.FILE_HANDLE)
        def process_file(self, path):
            file_handle = open(path, 'rb')
            yield file_handle
            # ... process file ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if hasattr(self, '_resource_manager') and self._resource_manager:
                with self._resource_manager.managed_resource(self, resource_type) as resource:
                    gen = func(self, *args, **kwargs)
                    if gen:
                        # Get the yielded resource
                        resource = next(gen)
                        try:
                            # Continue execution
                            next(gen)
                        except StopIteration as result:
                            return result.value
            else:
                # Fallback if no resource manager
                return func(self, *args, **kwargs)
        return wrapper
    return decorator
```

---

## Phase 3: MediaAnalysisTab Migration

### Step 3.1: Update MediaAnalysisTab to Use PluginBase

```python
# ui/tabs/media_analysis_tab.py (update existing file)

from core.plugin_system.plugin_base import PluginBase
from core.plugin_system.decorators import track_resource, cleanup_on_error
from core.services.interfaces import ResourceType

class MediaAnalysisTab(PluginBase):  # Changed from QWidget
    """Media Analysis tab with automatic resource management"""
    
    def __init__(self, form_data: FormData = None):
        # Initialize plugin base with unique ID
        super().__init__(
            plugin_id="MediaAnalysisTab",
            plugin_type="analysis_tab"
        )
        
        self.form_data = form_data
        self.last_exiftool_results = None
        self.geo_widget = None
        self.current_worker = None
        
        # Track resource IDs for cleanup
        self._thumbnail_resources = []
        self._worker_resource_id = None
        
        # Setup UI (existing code)
        self._setup_ui()
        self._connect_signals()
        
    def initialize(self) -> bool:
        """Initialize the plugin (required by PluginBase)"""
        try:
            # Any initialization that might fail
            self._load_settings()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize MediaAnalysisTab: {e}")
            return False
    
    @track_resource(ResourceType.THUMBNAIL,
                   size_func=lambda data: sum(len(m.thumbnail_base64) 
                                             for m in data if m.thumbnail_base64))
    def _on_exiftool_complete(self, results):
        """Handle ExifTool analysis completion with automatic resource tracking"""
        
        # Clear old thumbnail resources
        self._clear_thumbnail_resources()
        
        # Store results (will be tracked by decorator)
        self.last_exiftool_results = results
        
        # Track individual thumbnails for fine-grained management
        for metadata in results:
            if metadata.thumbnail_base64:
                resource_id = self.track_resource(
                    ResourceType.THUMBNAIL,
                    metadata.thumbnail_base64,
                    size_bytes=len(metadata.thumbnail_base64),
                    metadata={
                        'file': str(metadata.file_path),
                        'type': 'base64_thumbnail'
                    }
                )
                if resource_id:
                    self._thumbnail_resources.append(resource_id)
        
        # Update UI
        self._update_results_display(results)
    
    @cleanup_on_error(lambda self: self._cancel_current_operation())
    def _start_analysis(self):
        """Start media analysis with automatic cleanup on error"""
        
        # Cancel any existing operation
        self._cancel_current_operation()
        
        # ... validation code ...
        
        # Create and track worker
        self.current_worker = MediaAnalysisWorker(
            files, settings, self._get_service(), self.form_data
        )
        
        # Track the worker as a resource
        self._worker_resource_id = self.track_resource(
            ResourceType.WORKER,
            self.current_worker,
            metadata={
                'type': 'MediaAnalysisWorker',
                'file_count': len(files),
                'cleanup_func': lambda w: w.cancel() if w else None
            }
        )
        
        # Connect signals and start
        self.current_worker.result_ready.connect(self._on_analysis_complete)
        self.current_worker.progress_update.connect(self._on_progress_update)
        self.current_worker.start()
    
    def _show_map_view(self):
        """Show geolocation visualization with resource tracking"""
        if not self.geo_widget:
            self.geo_widget = GeoVisualizationWidget()
            
            # Track the map widget
            self.track_resource(
                ResourceType.MAP,
                self.geo_widget,
                metadata={
                    'type': 'GeoVisualizationWidget',
                    'cleanup_func': lambda w: w.clear_map() if w else None
                }
            )
        
        # ... rest of map display code ...
    
    def _cleanup_resources(self):
        """Clean up plugin-specific resources (required by PluginBase)"""
        logger.info("Cleaning up MediaAnalysisTab resources")
        
        # Cancel any running operations
        self._cancel_current_operation()
        
        # Clear map
        if self.geo_widget:
            self.geo_widget.clear_map()
            self.geo_widget = None
        
        # Clear thumbnail data
        self._clear_thumbnail_resources()
        
        # Clear results
        self.last_exiftool_results = None
        
        logger.info("MediaAnalysisTab cleanup complete")
    
    def _clear_thumbnail_resources(self):
        """Helper to clear tracked thumbnail resources"""
        for resource_id in self._thumbnail_resources:
            self.release_resource(resource_id)
        self._thumbnail_resources.clear()
    
    def _cancel_current_operation(self):
        """Cancel current analysis operation"""
        if self.current_worker:
            self.current_worker.cancel()
            
            # Release worker resource
            if self._worker_resource_id:
                self.release_resource(self._worker_resource_id)
                self._worker_resource_id = None
                
            self.current_worker = None
```

### Step 3.2: Remove MediaAnalysisTab Cleanup from MainWindow

```python
# ui/main_window.py (update existing file)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # ... existing init code ...
        
        # Remove media_analysis_tab cleanup from closeEvent
        
    def closeEvent(self, event):
        """Handle application close event"""
        
        # Save window state
        self._save_window_state()
        
        # The ResourceManagementService handles all cleanup now
        # Components registered with it will be cleaned up automatically
        
        # Just handle non-plugin cleanup
        if hasattr(self, 'log_console'):
            self.log_console.cleanup()
        
        event.accept()
```

---

## Phase 4: System-Wide Migration

### Step 4.1: Create Migration Helper

```python
# core/plugin_system/migration_helper.py (new file)

from typing import List, Tuple, Callable
from PySide6.QtWidgets import QWidget
from core.services.interfaces import IResourceManagementService
from core.services.service_registry import get_service
from core.logger import AppLogger

logger = AppLogger.get_instance()

class ResourceMigrationHelper:
    """Helper class to migrate existing tabs to resource management"""
    
    @staticmethod
    def migrate_tab(tab: QWidget, tab_id: str, 
                    cleanup_func: Callable = None) -> bool:
        """
        Migrate an existing tab to use ResourceManagementService.
        
        Args:
            tab: The tab widget to migrate
            tab_id: Unique identifier for the tab
            cleanup_func: Optional cleanup function to register
            
        Returns:
            True if migration successful
        """
        try:
            resource_manager = get_service(IResourceManagementService)
            if not resource_manager:
                logger.warning(f"ResourceManagementService not available for {tab_id}")
                return False
            
            # Register the tab
            resource_manager.register_component(tab, tab_id, "legacy_tab")
            
            # Register cleanup if provided
            if cleanup_func:
                resource_manager.register_cleanup(tab, cleanup_func)
            
            # Add helper methods to the tab
            tab._resource_manager = resource_manager
            tab.track_resource = lambda rt, r, s=None, m=None: \
                resource_manager.track_resource(tab, rt, r, s, m)
            tab.release_resource = lambda rid: \
                resource_manager.release_resource(tab, rid)
            
            logger.info(f"Successfully migrated {tab_id} to resource management")
            return True
            
        except Exception as e:
            logger.error(f"Failed to migrate {tab_id}: {e}")
            return False
    
    @staticmethod
    def migrate_all_tabs(tabs: List[Tuple[QWidget, str, Callable]]) -> dict:
        """
        Batch migrate multiple tabs.
        
        Args:
            tabs: List of (widget, id, cleanup_func) tuples
            
        Returns:
            Dictionary of tab_id -> success status
        """
        results = {}
        for tab, tab_id, cleanup_func in tabs:
            results[tab_id] = ResourceMigrationHelper.migrate_tab(
                tab, tab_id, cleanup_func
            )
        return results
```

### Step 4.2: Migrate Other Tabs

```python
# Example migration for ForensicTab
# ui/tabs/forensic_tab.py (update)

class ForensicTab(QWidget):
    def __init__(self, form_data):
        super().__init__()
        
        # ... existing init ...
        
        # Migrate to resource management
        from core.plugin_system.migration_helper import ResourceMigrationHelper
        ResourceMigrationHelper.migrate_tab(
            self, 
            "ForensicTab",
            self._cleanup_resources
        )
    
    def _cleanup_resources(self):
        """Cleanup callback for resource manager"""
        # Add any specific cleanup needed
        if hasattr(self, 'current_thread') and self.current_thread:
            self.current_thread.cancel()
```

---

## Phase 5: Plugin System Integration

### Step 5.1: Create Plugin Manager

```python
# core/plugin_system/plugin_manager.py (new file)

from typing import Dict, List, Optional, Type
from pathlib import Path
import importlib.util
import sys
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from core.plugin_system.plugin_base import PluginBase
from core.services.interfaces import IResourceManagementService
from core.services.service_registry import get_service
from core.logger import AppLogger
from core.result_types import Result

logger = AppLogger.get_instance()

@dataclass
class PluginInfo:
    """Plugin metadata"""
    plugin_id: str
    name: str
    version: str
    author: str
    description: str
    plugin_class: Type[PluginBase]
    file_path: Path
    is_loaded: bool = False
    instance: Optional[PluginBase] = None

class PluginManager(QObject):
    """
    Manages plugin lifecycle with ResourceManagementService integration.
    
    Features:
    - Dynamic plugin loading/unloading
    - Automatic resource tracking
    - Plugin dependency management
    - Safe plugin isolation
    """
    
    # Signals
    plugin_loaded = Signal(str)    # plugin_id
    plugin_unloaded = Signal(str)  # plugin_id
    plugin_error = Signal(str, str)  # plugin_id, error
    
    def __init__(self):
        super().__init__()
        
        self._plugins: Dict[str, PluginInfo] = {}
        self._plugin_paths: List[Path] = []
        self._resource_manager = get_service(IResourceManagementService)
        
        # Register ourselves with resource manager
        if self._resource_manager:
            self._resource_manager.register_component(
                self, "PluginManager", "system"
            )
        
        # Default plugin directory
        self.add_plugin_path(Path("plugins"))
        
    def add_plugin_path(self, path: Path):
        """Add a directory to search for plugins"""
        if path.exists() and path.is_dir():
            self._plugin_paths.append(path)
            logger.info(f"Added plugin path: {path}")
    
    def discover_plugins(self) -> List[PluginInfo]:
        """Discover available plugins in plugin paths"""
        discovered = []
        
        for plugin_path in self._plugin_paths:
            for file_path in plugin_path.glob("*.py"):
                if file_path.stem.startswith("_"):
                    continue
                    
                try:
                    info = self._load_plugin_info(file_path)
                    if info:
                        discovered.append(info)
                        self._plugins[info.plugin_id] = info
                        
                except Exception as e:
                    logger.error(f"Failed to load plugin info from {file_path}: {e}")
        
        logger.info(f"Discovered {len(discovered)} plugins")
        return discovered
    
    def load_plugin(self, plugin_id: str) -> Result[PluginBase]:
        """Load and initialize a plugin"""
        
        if plugin_id not in self._plugins:
            return Result.error(f"Plugin {plugin_id} not found")
        
        info = self._plugins[plugin_id]
        
        if info.is_loaded:
            return Result.success(info.instance)
        
        try:
            # Create plugin instance
            instance = info.plugin_class()
            
            # Plugin auto-registers with ResourceManagementService
            # via PluginBase.__init__
            
            # Initialize the plugin
            if instance.initialize():
                info.instance = instance
                info.is_loaded = True
                
                logger.info(f"Loaded plugin: {plugin_id}")
                self.plugin_loaded.emit(plugin_id)
                
                return Result.success(instance)
            else:
                return Result.error(f"Plugin {plugin_id} initialization failed")
                
        except Exception as e:
            error_msg = f"Failed to load plugin {plugin_id}: {e}"
            logger.error(error_msg)
            self.plugin_error.emit(plugin_id, str(e))
            return Result.error(error_msg)
    
    def unload_plugin(self, plugin_id: str) -> Result[None]:
        """Unload a plugin and cleanup resources"""
        
        if plugin_id not in self._plugins:
            return Result.error(f"Plugin {plugin_id} not found")
        
        info = self._plugins[plugin_id]
        
        if not info.is_loaded:
            return Result.success(None)
        
        try:
            # Deactivate plugin
            if info.instance:
                info.instance.deactivate()
                
                # ResourceManagementService handles cleanup
                if self._resource_manager:
                    self._resource_manager.cleanup_component(info.instance)
                
                # Clear instance
                info.instance = None
            
            info.is_loaded = False
            
            logger.info(f"Unloaded plugin: {plugin_id}")
            self.plugin_unloaded.emit(plugin_id)
            
            return Result.success(None)
            
        except Exception as e:
            error_msg = f"Failed to unload plugin {plugin_id}: {e}"
            logger.error(error_msg)
            return Result.error(error_msg)
    
    def reload_plugin(self, plugin_id: str) -> Result[PluginBase]:
        """Reload a plugin (unload then load)"""
        
        unload_result = self.unload_plugin(plugin_id)
        if unload_result.is_error:
            return Result.error(f"Failed to unload for reload: {unload_result.error}")
        
        return self.load_plugin(plugin_id)
    
    def get_loaded_plugins(self) -> List[PluginInfo]:
        """Get list of loaded plugins"""
        return [info for info in self._plugins.values() if info.is_loaded]
    
    def get_plugin(self, plugin_id: str) -> Optional[PluginBase]:
        """Get a loaded plugin instance"""
        if plugin_id in self._plugins:
            info = self._plugins[plugin_id]
            if info.is_loaded:
                return info.instance
        return None
    
    def _load_plugin_info(self, file_path: Path) -> Optional[PluginInfo]:
        """Load plugin metadata from file"""
        
        # Load module
        spec = importlib.util.spec_from_file_location(
            file_path.stem, file_path
        )
        if not spec or not spec.loader:
            return None
            
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Find plugin class
        plugin_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and 
                issubclass(attr, PluginBase) and 
                attr is not PluginBase):
                plugin_class = attr
                break
        
        if not plugin_class:
            return None
        
        # Get metadata
        metadata = getattr(module, 'PLUGIN_METADATA', {})
        
        return PluginInfo(
            plugin_id=metadata.get('id', file_path.stem),
            name=metadata.get('name', file_path.stem),
            version=metadata.get('version', '1.0.0'),
            author=metadata.get('author', 'Unknown'),
            description=metadata.get('description', ''),
            plugin_class=plugin_class,
            file_path=file_path
        )
    
    def cleanup(self):
        """Cleanup all plugins"""
        for plugin_id in list(self._plugins.keys()):
            self.unload_plugin(plugin_id)
```

### Step 5.2: Example Plugin Implementation

```python
# plugins/example_plugin.py (new file)

from PySide6.QtWidgets import QVBoxLayout, QLabel, QPushButton
from core.plugin_system.plugin_base import PluginBase
from core.services.interfaces import ResourceType
from core.logger import AppLogger

logger = AppLogger.get_instance()

# Plugin metadata
PLUGIN_METADATA = {
    'id': 'example_plugin',
    'name': 'Example Plugin',
    'version': '1.0.0',
    'author': 'Your Name',
    'description': 'Demonstrates plugin resource management'
}

class ExamplePlugin(PluginBase):
    """Example plugin demonstrating resource management"""
    
    def __init__(self):
        super().__init__(
            plugin_id=PLUGIN_METADATA['id'],
            plugin_type='example'
        )
        
        self.data_buffer = None
        self.data_resource_id = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel(f"<h2>{PLUGIN_METADATA['name']}</h2>")
        layout.addWidget(title)
        
        # Info label
        self.info_label = QLabel("Plugin loaded successfully")
        layout.addWidget(self.info_label)
        
        # Memory usage label
        self.memory_label = QLabel("Memory: 0 bytes")
        layout.addWidget(self.memory_label)
        
        # Test button
        test_btn = QPushButton("Allocate Test Resource")
        test_btn.clicked.connect(self._allocate_test_resource)
        layout.addWidget(test_btn)
        
        # Release button
        release_btn = QPushButton("Release Test Resource")
        release_btn.clicked.connect(self._release_test_resource)
        layout.addWidget(release_btn)
        
        layout.addStretch()
    
    def initialize(self) -> bool:
        """Initialize the plugin"""
        logger.info(f"Initializing {PLUGIN_METADATA['name']}")
        return True
    
    def _allocate_test_resource(self):
        """Allocate a test resource"""
        
        # Release old resource if exists
        self._release_test_resource()
        
        # Create new resource (simulated data buffer)
        self.data_buffer = bytearray(1024 * 1024)  # 1MB
        
        # Track it
        self.data_resource_id = self.track_resource(
            ResourceType.MEMORY,
            self.data_buffer,
            size_bytes=len(self.data_buffer),
            metadata={'type': 'test_buffer'}
        )
        
        # Update UI
        self.info_label.setText("Test resource allocated")
        self._update_memory_display()
    
    def _release_test_resource(self):
        """Release test resource"""
        if self.data_resource_id:
            self.release_resource(self.data_resource_id)
            self.data_resource_id = None
            self.data_buffer = None
            
            self.info_label.setText("Test resource released")
            self._update_memory_display()
    
    def _update_memory_display(self):
        """Update memory usage display"""
        usage = self.get_memory_usage()
        self.memory_label.setText(f"Memory: {usage:,} bytes")
    
    def _cleanup_resources(self):
        """Clean up plugin resources"""
        logger.info(f"Cleaning up {PLUGIN_METADATA['name']}")
        
        # Release any allocated resources
        self._release_test_resource()
```

---

## Phase 6: Testing Strategy

### Step 6.1: Unit Tests for ResourceManagementService

```python
# tests/test_resource_management_service.py (new file)

import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import QObject

from core.services.resource_management_service import ResourceManagementService
from core.services.interfaces import ResourceType, ComponentState

class TestComponent(QObject):
    """Test component for testing"""
    def __init__(self):
        super().__init__()
        self.cleanup_called = False
    
    def cleanup(self):
        self.cleanup_called = True

class TestResourceManagementService:
    
    @pytest.fixture
    def service(self):
        return ResourceManagementService()
    
    @pytest.fixture
    def component(self):
        return TestComponent()
    
    def test_component_registration(self, service, component):
        """Test component registration"""
        
        # Register component
        service.register_component(component, "test_component", "test")
        
        # Check state
        assert service.get_component_state(component) == ComponentState.LOADED
        
        # Check in registry
        stats = service.get_statistics()
        assert stats['components_registered'] == 1
    
    def test_resource_tracking(self, service, component):
        """Test resource tracking"""
        
        # Register component
        service.register_component(component, "test_component", "test")
        
        # Track a resource
        test_data = b"test data"
        resource_id = service.track_resource(
            component,
            ResourceType.MEMORY,
            test_data,
            size_bytes=len(test_data)
        )
        
        assert resource_id is not None
        
        # Check memory usage
        usage = service.get_memory_usage()
        assert usage.get("test_component") == len(test_data)
        
        # Check resource count
        counts = service.get_resource_count(component)
        assert counts.get("memory") == 1
    
    def test_resource_release(self, service, component):
        """Test resource release"""
        
        # Setup
        service.register_component(component, "test_component", "test")
        test_data = b"test data"
        resource_id = service.track_resource(
            component,
            ResourceType.MEMORY,
            test_data,
            len(test_data)
        )
        
        # Release resource
        success = service.release_resource(component, resource_id)
        assert success
        
        # Check memory cleared
        usage = service.get_memory_usage()
        assert usage.get("test_component") == 0
        
        # Check resource count
        counts = service.get_resource_count(component)
        assert counts.get("memory", 0) == 0
    
    def test_cleanup_callbacks(self, service, component):
        """Test cleanup callback execution"""
        
        # Register component
        service.register_component(component, "test_component", "test")
        
        # Register cleanup callback
        service.register_cleanup(component, component.cleanup, priority=10)
        
        # Trigger cleanup
        service.cleanup_component(component)
        
        # Check callback was called
        assert component.cleanup_called
    
    def test_memory_limits(self, service, component):
        """Test memory limit enforcement"""
        
        # Setup
        service.register_component(component, "test_component", "test")
        service.set_memory_limit("test_component", 100)  # 100 bytes limit
        
        # Track resource exceeding limit
        with patch.object(service, 'memory_threshold_exceeded') as mock_signal:
            large_data = b"x" * 200
            service.track_resource(
                component,
                ResourceType.MEMORY,
                large_data,
                len(large_data)
            )
            
            # Check signal emitted
            mock_signal.emit.assert_called_once()
    
    def test_weak_reference_cleanup(self, service):
        """Test weak reference automatic cleanup"""
        
        # Create and register component
        component = TestComponent()
        service.register_component(component, "test_component", "test")
        
        # Track a QObject resource
        qobj = QObject()
        resource_id = service.track_resource(
            component,
            ResourceType.QOBJECT,
            qobj
        )
        
        # Delete the QObject
        del qobj
        
        # Trigger periodic cleanup
        service._periodic_cleanup()
        
        # Check resource was cleaned up
        counts = service.get_resource_count(component)
        assert counts.get("qobject", 0) == 0
    
    def test_context_manager(self, service, component):
        """Test managed resource context manager"""
        
        service.register_component(component, "test_component", "test")
        
        resource_tracked = False
        
        with service.managed_resource(component, ResourceType.FILE_HANDLE) as resource:
            # Simulate resource creation
            resource = "test_file_handle"
            
            # Would normally track here
            resource_tracked = True
        
        # Resource should be auto-cleaned after context
        assert resource_tracked
```

---

## Phase 7: Performance Monitoring

### Step 7.1: Create Resource Monitor UI

```python
# ui/dialogs/resource_monitor_dialog.py (new file)

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QPushButton, QLabel, QTabWidget,
    QTextEdit, QHeaderView
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont

from core.services.interfaces import IResourceManagementService
from core.services.service_registry import get_service

class ResourceMonitorDialog(QDialog):
    """Dialog for monitoring resource usage"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("Resource Monitor")
        self.setModal(False)
        self.resize(800, 600)
        
        self._resource_manager = get_service(IResourceManagementService)
        
        self._setup_ui()
        self._setup_timer()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("<h2>Resource Usage Monitor</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Components tab
        self.components_table = self._create_components_tab()
        tabs.addTab(self.components_table, "Components")
        
        # Resources tab
        self.resources_table = self._create_resources_tab()
        tabs.addTab(self.resources_table, "Resources")
        
        # Statistics tab
        self.stats_text = self._create_stats_tab()
        tabs.addTab(self.stats_text, "Statistics")
        
        # Buttons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._update_display)
        button_layout.addWidget(refresh_btn)
        
        cleanup_btn = QPushButton("Force Cleanup")
        cleanup_btn.clicked.connect(self._force_cleanup)
        button_layout.addWidget(cleanup_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _create_components_tab(self):
        """Create components table"""
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels([
            "Component ID", "Type", "State", "Memory Usage"
        ])
        
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        
        return table
    
    def _create_resources_tab(self):
        """Create resources table"""
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels([
            "Resource Type", "Count", "Total Size"
        ])
        
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        
        return table
    
    def _create_stats_tab(self):
        """Create statistics display"""
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Consolas", 10))
        
        return text_edit
    
    def _setup_timer(self):
        """Setup auto-refresh timer"""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._update_display)
        self.refresh_timer.start(2000)  # Update every 2 seconds
        
        # Initial update
        self._update_display()
    
    def _update_display(self):
        """Update all displays"""
        if not self._resource_manager:
            return
        
        # Get statistics
        stats = self._resource_manager.get_statistics()
        memory_usage = self._resource_manager.get_memory_usage()
        resource_counts = self._resource_manager.get_resource_count()
        
        # Update components table
        self.components_table.setRowCount(len(memory_usage))
        for row, (comp_id, memory) in enumerate(memory_usage.items()):
            self.components_table.setItem(row, 0, QTableWidgetItem(comp_id))
            self.components_table.setItem(row, 1, QTableWidgetItem("-"))  # Type
            self.components_table.setItem(row, 2, QTableWidgetItem("-"))  # State
            self.components_table.setItem(row, 3, QTableWidgetItem(f"{memory:,} bytes"))
        
        # Update resources table
        self.resources_table.setRowCount(len(resource_counts))
        for row, (resource_type, count) in enumerate(resource_counts.items()):
            self.resources_table.setItem(row, 0, QTableWidgetItem(resource_type))
            self.resources_table.setItem(row, 1, QTableWidgetItem(str(count)))
            self.resources_table.setItem(row, 2, QTableWidgetItem("-"))
        
        # Update statistics
        stats_text = f"""
Resource Management Statistics
==============================

Components Registered: {stats.get('components_registered', 0)}
Total Resources Tracked: {stats.get('total_resources_tracked', 0)}
Total Resources Released: {stats.get('total_resources_released', 0)}
Active Resources: {stats.get('active_resources', 0)}

Memory Usage by Component:
{self._format_memory_usage(memory_usage)}

Resource Counts:
{self._format_resource_counts(resource_counts)}
"""
        self.stats_text.setPlainText(stats_text)
    
    def _format_memory_usage(self, memory_usage):
        """Format memory usage for display"""
        if not memory_usage:
            return "  No components with tracked memory"
        
        lines = []
        for comp_id, memory in memory_usage.items():
            lines.append(f"  {comp_id}: {memory:,} bytes")
        
        return "\n".join(lines)
    
    def _format_resource_counts(self, resource_counts):
        """Format resource counts for display"""
        if not resource_counts:
            return "  No resources tracked"
        
        lines = []
        for resource_type, count in resource_counts.items():
            lines.append(f"  {resource_type}: {count}")
        
        return "\n".join(lines)
    
    def _force_cleanup(self):
        """Force cleanup of all components"""
        # This would need proper confirmation dialog
        pass
    
    def closeEvent(self, event):
        """Handle dialog close"""
        self.refresh_timer.stop()
        super().closeEvent(event)
```

---

## Best Practices and Patterns

### Resource Management Best Practices

1. **Always Use Weak References for QObjects**
   - Prevents circular references
   - Allows automatic cleanup on deletion

2. **Track Resource Size**
   - Enables memory limit enforcement
   - Provides usage statistics

3. **Register Cleanup Callbacks**
   - Ensures proper cleanup even on errors
   - Use priority for ordering

4. **Use Context Managers**
   - Guarantees cleanup in all cases
   - Simplifies resource management

5. **Monitor Resource Usage**
   - Set memory limits per component
   - Track resource counts
   - Log cleanup operations

### Plugin Development Best Practices

1. **Inherit from PluginBase**
   - Automatic resource management
   - Lifecycle management
   - Standard interface

2. **Implement Required Methods**
   - `initialize()` for setup
   - `_cleanup_resources()` for cleanup

3. **Track All Resources**
   - Memory allocations
   - File handles
   - Threads and workers
   - UI components

4. **Handle Errors Gracefully**
   - Use cleanup decorators
   - Implement error recovery
   - Log all issues

5. **Test Resource Management**
   - Unit test cleanup
   - Test memory limits
   - Verify no leaks

### Migration Strategy Best Practices

1. **Phase Migration**
   - Start with highest memory users
   - Test thoroughly at each phase
   - Monitor for regressions

2. **Maintain Compatibility**
   - Support both old and new during transition
   - Use migration helpers
   - Document changes

3. **Monitor Performance**
   - Track memory usage
   - Watch for leaks
   - Profile cleanup times

---

## Conclusion

This comprehensive guide provides a complete roadmap for implementing a sophisticated Resource Management Service that will:

- **Enable plugin architecture** with automatic resource tracking
- **Prevent memory leaks** through weak references and lifecycle management
- **Ensure cleanup** even on crashes or forced unloads
- **Provide monitoring** of resource usage across all components
- **Support dynamic loading** of plugins with full resource management

The phased approach ensures smooth migration from the current MainWindow-based cleanup to a fully decoupled, plugin-ready architecture that follows industry best practices from VSCode, IntelliJ, and Qt plugin systems.

Key advantages:
- **Scalability**: Add new plugins without modifying core code
- **Reliability**: Automatic cleanup prevents resource leaks
- **Observability**: Monitor resource usage in real-time
- **Maintainability**: Clear separation of concerns
- **Testability**: Components can be tested in isolation

The implementation is production-ready and follows enterprise patterns for resource management in plugin architectures.