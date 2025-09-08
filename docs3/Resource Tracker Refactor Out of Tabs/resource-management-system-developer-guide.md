# Resource Management System - Complete Developer Guide

**Version**: 1.0.0  
**Date**: 2025-09-08  
**Architecture**: Service-Oriented with Coordinator Pattern

---

## Section 1: Natural Language Technical Walkthrough

### The Journey of Resource Management

Imagine you're building a complex desktop application where multiple components spawn worker threads, load images, create map widgets, and manage various resources. Without proper management, these resources can leak memory, leave threads running, or cause crashes when components are destroyed while resources are still active.

Our resource management system solves this elegantly through a **four-layer architecture** that separates concerns and automates lifecycle management.

### How It Works - A Story

#### Act 1: Component Registration

When a controller is born (let's say `MediaAnalysisController`), it immediately creates its own personal assistant - a `WorkerResourceCoordinator`. This coordinator is like a dedicated secretary that keeps track of everything the controller owns.

```
Controller: "I need someone to track my resources"
System: "Here's your coordinator with ID MediaAnalysisController_12345"
Coordinator: "I'll register you with the central service and watch your resources"
```

The coordinator binds itself to the controller using **weak references** - this is crucial. It's like having a business card rather than handcuffs. The coordinator can reference the controller without preventing it from being garbage collected.

#### Act 2: Resource Tracking

When the controller needs to analyze media files, it creates a worker thread:

```
Controller: "I'm creating a MediaAnalysisWorker"
Coordinator: "I'll track that for you with ID uuid-abc-123"
Service: "Registered! I'm watching it now"
Worker: "I'll notify when I'm done"
```

The beautiful part? The coordinator automatically connects to the worker's `finished` signal. When the worker completes:

```
Worker: "I'm finished!"
Coordinator: "Great, releasing resource uuid-abc-123"
Service: "Resource cleaned up, memory freed"
Terminal: "Worker media_analysis_090600 finished after 0.95s"
```

#### Act 3: The Safety Net

What if something goes wrong? What if the application crashes or the user forces a shutdown?

The system has **multiple safety nets**:

1. **Weak References**: Components can be garbage collected naturally
2. **Auto-cleanup on Finish**: Workers clean themselves up when done
3. **Emergency Cleanup**: On app shutdown, all components get cleaned
4. **Periodic Cleanup**: Every 60 seconds, dead references are cleared
5. **Destructor Safety**: Controllers check for active resources in `__del__`

#### Act 4: The UI's Freedom

The UI tabs know nothing about this complex dance. They simply say:

```python
def cleanup(self):
    """I just tell my controller to cleanup"""
    if self.controller:
        self.controller.cleanup()
```

The tab doesn't track resources, doesn't manage workers, doesn't worry about memory. It just displays data and handles user interaction. **Pure presentation logic**.

### The Flow - End to End

Let's trace a complete ExifTool analysis operation:

1. **User clicks "Analyze"** in MediaAnalysisTab
2. **Tab calls** `controller.start_exiftool_workflow()`
3. **Controller creates** ExifToolWorker
4. **Controller tracks** via `self.resources.track_worker(worker, name="exiftool_084001")`
5. **Coordinator registers** with ResourceManagementService
6. **Service tracks** with weak reference and metadata
7. **Worker runs** - analyzes 39 files
8. **Worker finishes** - emits `finished` signal
9. **Coordinator catches** signal, releases resource
10. **Service logs** "Released resource uuid-xyz for MediaAnalysisController_12345"
11. **App closes** - emergency cleanup verifies all clean
12. **Terminal shows** "Component cleanup complete: MediaAnalysisController_12345"

### The Magic of Weak References

The system uses `WeakKeyDictionary` and `weakref.ref` extensively. Why?

**Strong Reference Problem:**
```
Service → Component → Resource → Component (circular!)
```
This creates a reference cycle that prevents garbage collection.

**Weak Reference Solution:**
```
Service ⇀ Component → Resource
         ↘️ Coordinator ⇀ Component
```
The weak references (⇀) allow the component to be collected when no strong references remain.

### Resource Types and Their Behaviors

The system tracks different resource types with specific behaviors:

- **WORKER**: Threads that need cancellation and termination
- **THUMBNAIL**: Image data that needs memory tracking
- **MAP**: Map widgets that need cleanup methods called
- **MEMORY**: Large data structures needing monitoring
- **FILE_HANDLE**: Open files needing closure
- **CUSTOM**: Anything else with custom cleanup

Each type can have custom cleanup handlers:

```python
cleanup_handler = lambda w: w.cancel() if w and w.isRunning() else None
```

### The Coordinator Pattern

Why coordinators? They're the **adapters** between business logic and infrastructure:

```
Business Logic Layer:    Controller (knows what to do)
           ↓
Coordination Layer:      Coordinator (knows how to track)
           ↓
Infrastructure Layer:    Service (knows how to manage)
```

This separation means:
- Controllers don't depend on resource management details
- Testing can mock coordinators easily
- Different controllers can use different coordinator types
- The pattern is reusable across the application

---

## Section 2: Senior Developer Technical Documentation

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    UI Layer (Tabs)                       │
│  - Zero resource management code                         │
│  - Simple cleanup() delegates to controller              │
└─────────────────────┬───────────────────────────────────┘
                      │ owns
┌─────────────────────▼───────────────────────────────────┐
│               Controller Layer                           │
│  - Business logic orchestration                          │
│  - Creates workers/resources                             │
│  - Uses resource coordinator for tracking                │
└─────────────────────┬───────────────────────────────────┘
                      │ uses
┌─────────────────────▼───────────────────────────────────┐
│           Resource Coordinator Layer                     │
│  - BaseResourceCoordinator (general resources)           │
│  - WorkerResourceCoordinator (thread management)         │
│  - Automatic lifecycle management                        │
└─────────────────────┬───────────────────────────────────┘
                      │ delegates to
┌─────────────────────▼───────────────────────────────────┐
│        ResourceManagementService (Core)                  │
│  - Weak reference tracking                               │
│  - Memory monitoring                                     │
│  - Emergency cleanup                                     │
│  - Thread-safe operations                                │
└──────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. ResourceManagementService

**Location**: `core/services/resource_management_service.py`

**Purpose**: Central registry for all resource tracking with weak references

**Key Features**:
- Thread-safe with `threading.RLock()`
- Weak reference storage via `WeakKeyDictionary`
- Qt signal emissions for monitoring
- Emergency cleanup on app shutdown
- Periodic cleanup timer (60 seconds)

**Critical Data Structures**:
```python
@dataclass
class TrackedResource:
    resource_id: str              # UUID for tracking
    resource_type: ResourceType   # Enum for resource category
    resource_ref: Any            # Weak reference to resource
    size_bytes: Optional[int]   # Memory size if applicable
    metadata: Dict              # Custom metadata
    tracked_at: datetime       # Tracking timestamp
    component_id: str         # Owner component ID

@dataclass  
class ComponentInfo:
    component_id: str                    # Unique identifier
    component_type: str                  # controller/tab/widget
    state: ComponentState                # Lifecycle state
    resources: Dict[str, TrackedResource]  # Owned resources
    cleanup_callbacks: List[Tuple[int, Any]]  # Priority-ordered
    memory_usage: int                    # Total memory tracked
    registered_at: datetime              # Registration time
```

**Thread Safety Implementation**:
```python
def track_resource(self, component, resource_type, resource, **kwargs):
    with self._lock:  # RLock for reentrancy
        # Thread-safe tracking logic
        resource_id = str(uuid.uuid4())
        # ... tracking implementation
    return resource_id
```

**Weak Reference Management**:
```python
# Component registry using weak keys
self._component_registry: WeakKeyDictionary = WeakKeyDictionary()

# When component is garbage collected, it's automatically removed
# No manual cleanup needed for component registration
```

#### 2. BaseResourceCoordinator

**Location**: `core/resource_coordinators/base_coordinator.py`

**Purpose**: Simplified interface for resource tracking

**Key Methods**:
```python
def bind_to_component(self, component: Any) -> 'BaseResourceCoordinator':
    """Fluent interface for component binding"""
    self._component_ref = weakref.ref(component)
    # Auto-registers with service
    # Sets up cleanup callbacks
    return self

def track_resource(self, resource: Any, 
                   resource_type: ResourceType = ResourceType.CUSTOM,
                   name: Optional[str] = None,
                   cleanup_handler: Optional[Callable] = None,
                   **metadata) -> str:
    """Generic resource tracking with metadata"""
    # Returns UUID for tracking
    
def track_worker(self, worker: QThread, 
                 name: Optional[str] = None) -> str:
    """Specialized worker tracking with auto-cleanup"""
    # Connects to finished signal
    # Sets up termination handler
    # Returns UUID
```

**Lifecycle Hooks**:
```python
def on_resource_released(self, resource_id: str):
    """Override in subclasses for custom behavior"""
    pass

def cleanup_all(self):
    """Clean up all tracked resources"""
    # Iterates through resources
    # Calls individual cleanup handlers
    # Clears tracking
```

**Safety Mechanisms**:
```python
def __del__(self):
    """Destructor safety check"""
    if hasattr(self, '_resources') and self._resources:
        logger.warning(f"Coordinator {self._component_id} destroyed "
                      f"with {len(self._resources)} active resources")
        self.cleanup_all()  # Best effort cleanup
```

#### 3. WorkerResourceCoordinator

**Location**: `core/resource_coordinators/worker_coordinator.py`

**Purpose**: Enhanced coordinator for QThread worker management

**Specialized Features**:
```python
class WorkerResourceCoordinator(BaseResourceCoordinator):
    def __init__(self, component_id: str):
        super().__init__(component_id)
        self._active_workers: Set[str] = set()
        self._worker_metadata: Dict[str, Dict[str, Any]] = {}
```

**Worker Lifecycle Management**:
```python
def track_worker(self, worker: QThread,
                name: Optional[str] = None,
                cancel_on_cleanup: bool = True,
                auto_release: bool = True) -> str:
    """Enhanced worker tracking"""
    
    # Custom cleanup handler with graceful shutdown
    def cleanup_worker(w):
        if w and w.isRunning():
            if cancel_on_cleanup and hasattr(w, 'cancel'):
                w.cancel()  # Graceful cancellation
            w.quit()        # Request thread quit
            if not w.wait(2000):
                w.terminate()  # Force if needed
    
    # Track with metadata
    resource_id = self.track_resource(
        worker, ResourceType.WORKER,
        name=worker_name,
        cleanup_handler=cleanup_worker
    )
    
    # Auto-release on completion
    if auto_release:
        worker.finished.connect(
            lambda: self._on_worker_finished(resource_id)
        )
```

**Batch Operations**:
```python
def cancel_all_workers(self, timeout_ms: int = 5000) -> bool:
    """Cancel all active workers with timeout"""
    # Send cancel to all workers
    # Wait for graceful shutdown
    # Force terminate if needed
    # Return success status

def get_active_workers(self) -> Dict[str, Dict[str, Any]]:
    """Get runtime statistics for active workers"""
    # Returns metadata with runtime calculations
```

#### 4. BaseController Integration

**Location**: `controllers/base_controller.py`

**Purpose**: Base class providing resource coordination to all controllers

**Initialization Pattern**:
```python
class BaseController(ABC):
    def __init__(self, logger_name: Optional[str] = None):
        self.logger = logging.getLogger(logger_name or self.__class__.__name__)
        
        # Create resource coordinator
        try:
            controller_id = f"{self.__class__.__name__}_{id(self)}"
            self._resources = self._create_resource_coordinator(controller_id)
            
            if self._resources:
                self._resources.bind_to_component(self)
        except (ValueError, ImportError):
            # Service not available (tests)
            self._resources = None
```

**Factory Method Pattern**:
```python
def _create_resource_coordinator(self, component_id: str) -> BaseResourceCoordinator:
    """Override in subclasses for specialized coordinators"""
    return BaseResourceCoordinator(component_id)

# Example override in worker-managing controller:
class MediaAnalysisController(BaseController):
    def _create_resource_coordinator(self, component_id: str):
        return WorkerResourceCoordinator(component_id)  # Specialized
```

### Implementation Patterns

#### Pattern 1: Worker Creation and Tracking

```python
class MediaAnalysisController(BaseController):
    def start_analysis_workflow(self, files: List[Path]) -> Result[Worker]:
        # Create worker
        worker = MediaAnalysisWorker(files)
        self.current_worker = worker
        
        # Track with coordinator
        if self.resources:  # Always check availability
            self._current_worker_id = self.resources.track_worker(
                worker,
                name=f"analysis_{datetime.now():%H%M%S}"
            )
        
        return Result.success(worker)
```

#### Pattern 2: Cleanup Implementation

```python
def cleanup(self) -> None:
    """Controller cleanup pattern"""
    # Cancel active operations
    if self.current_worker and self.current_worker.isRunning():
        self.cancel_current_operation()
    
    # Delegate to coordinator
    if self.resources:
        self.resources.cleanup_all()
    
    # Clear references
    self.current_worker = None
    self._current_worker_id = None
```

#### Pattern 3: UI Tab Simplification

```python
class MediaAnalysisTab(QWidget):
    def cleanup(self):
        """Simple cleanup delegating to controller"""
        if self.controller:
            self.controller.cancel_current_operation()
            self.controller.cleanup()
        
        # Clear UI references only
        self.current_worker = None
        self.last_results = None
```

### Memory Management Strategy

#### Weak Reference Architecture

```python
# Service → Component (weak)
self._component_registry: WeakKeyDictionary = WeakKeyDictionary()

# Coordinator → Component (weak)  
self._component_ref: Optional[weakref.ref] = None

# Coordinator → Resources (weak)
self._resources: Dict[str, weakref.ref] = {}
```

#### Memory Monitoring

```python
@dataclass
class TrackedResource:
    size_bytes: Optional[int]  # Track memory size
    
# Service aggregates memory per component
def get_component_memory_usage(self, component) -> int:
    """Calculate total memory for component"""
    total = sum(r.size_bytes or 0 
                for r in component_info.resources.values())
    return total
```

#### Memory Limits and Thresholds

```python
# Per-component limits
self._memory_limits: Dict[str, int] = {}

# Global limit
self._global_memory_limit: Optional[int] = None

# Threshold monitoring
if memory_usage > limit:
    self.memory_threshold_exceeded.emit(component_id, memory_usage)
```

### Thread Safety Considerations

#### Locking Strategy

```python
class ResourceManagementService:
    def __init__(self):
        self._lock = threading.RLock()  # Reentrant lock
        
    def track_resource(self, ...):
        with self._lock:
            # All modifications protected
            self._component_registry[component] = info
            self._resource_ids.add(resource_id)
```

#### Qt Signal Thread Safety

```python
# Signals are thread-safe for emission
resource_tracked = Signal(str, str, str)

# Can emit from any thread
self.resource_tracked.emit(component_id, resource_id, type_str)

# Slots execute in receiver's thread
```

#### Worker Thread Patterns

```python
class Worker(QThread):
    # Signals for thread-safe communication
    result_ready = Signal(Result)
    progress_update = Signal(int, str)
    
    def run(self):
        # Runs in worker thread
        result = self.process()
        self.result_ready.emit(result)  # Thread-safe
```

### Error Handling and Recovery

#### Graceful Degradation

```python
try:
    self._resources = self._create_resource_coordinator(controller_id)
except (ValueError, ImportError):
    # Service not available (e.g., tests)
    self._resources = None
    
# Later usage always checks
if self.resources:
    self.resources.track_worker(worker)
```

#### Emergency Cleanup

```python
def _emergency_cleanup(self):
    """Called on app shutdown via atexit"""
    logger.info("ResourceManagementService: Emergency cleanup initiated")
    
    with self._lock:
        components = list(self._component_registry.keys())
        
    for component in components:
        try:
            self._cleanup_component(component)
        except Exception as e:
            logger.error(f"Emergency cleanup error: {e}")
```

#### Worker Termination Strategy

```python
def cleanup_worker(w):
    """Three-stage termination"""
    if w and w.isRunning():
        # Stage 1: Graceful cancellation
        if hasattr(w, 'cancel'):
            w.cancel()
            
        # Stage 2: Qt quit request
        w.quit()
        
        # Stage 3: Force termination
        if not w.wait(2000):
            logger.warning(f"Force terminating worker")
            w.terminate()
            w.wait(1000)
```

### Testing Considerations

#### Mock Coordinators for Testing

```python
class MockResourceCoordinator(BaseResourceCoordinator):
    """Test double for resource coordination"""
    def __init__(self):
        # No service dependency
        self._resources = {}
        self.tracked_resources = []
        
    def track_worker(self, worker, name=None):
        resource_id = f"mock_{id(worker)}"
        self.tracked_resources.append((worker, name))
        return resource_id
```

#### Testing Without Service

```python
class TestController:
    def test_controller_without_service(self):
        # Service not registered
        controller = MediaAnalysisController()
        
        # Should work without coordinator
        assert controller.resources is None
        
        # Operations should still work
        result = controller.start_analysis_workflow(files)
        assert result.success
```

### Performance Optimizations

#### Lazy Initialization

```python
@property
def media_service(self) -> IMediaAnalysisService:
    """Lazy load service only when needed"""
    if self._media_service is None:
        self._media_service = self._get_service(IMediaAnalysisService)
    return self._media_service
```

#### Weak Reference Cleanup

```python
def _periodic_cleanup(self):
    """Timer-based cleanup every 60 seconds"""
    # Remove dead weak references
    dead_refs = [rid for rid, ref in self._resources.items() 
                 if ref() is None]
    for rid in dead_refs:
        del self._resources[rid]
```

#### Batch Operations

```python
def cleanup_all(self):
    """Efficient batch cleanup"""
    # Collect all IDs first
    resource_ids = list(self._resources.keys())
    
    # Then release in batch
    for resource_id in resource_ids:
        try:
            self.release(resource_id)
        except Exception:
            pass  # Continue cleanup
```

### Configuration and Customization

#### Resource Type Extension

```python
class ResourceType(Enum):
    """Extensible resource categories"""
    MEMORY = "memory"
    FILE_HANDLE = "file_handle"
    THREAD = "thread"
    QOBJECT = "qobject"
    THUMBNAIL = "thumbnail"
    MAP = "map"
    WORKER = "worker"
    CUSTOM = "custom"  # For extensions
```

#### Custom Cleanup Handlers

```python
# Define custom cleanup
def cleanup_map_widget(widget):
    if widget:
        widget.clear_markers()
        widget.close()

# Track with custom handler
self.resources.track_resource(
    map_widget,
    ResourceType.MAP,
    cleanup_handler=cleanup_map_widget
)
```

#### Priority-Based Cleanup

```python
# Register cleanup with priority
self._service.register_cleanup(
    component,
    self.cleanup_all,
    priority=10  # Lower = earlier
)

# Callbacks executed in priority order
cleanup_callbacks.sort(key=lambda x: x[0])
```

### Debugging and Monitoring

#### Debug Mode

```python
# Enable debug mode on coordinator
coordinator.debug_mode = True

# Logs all resource operations
def release(self, resource_id: str):
    if self.debug_mode:
        logger.debug(f"Releasing {resource_id} from {self._component_id}")
```

#### Statistics and Metrics

```python
# Service statistics
self._total_resources_tracked = 0
self._total_resources_released = 0

# Coordinator statistics
def get_statistics(self) -> Dict[str, Any]:
    return {
        'total_tracked': self.get_resource_count(),
        'active_workers': len(self._active_workers),
        'workers': self.get_active_workers()
    }
```

#### Qt Signal Monitoring

```python
# Connect to monitoring signals
service.resource_tracked.connect(self.on_resource_tracked)
service.memory_threshold_exceeded.connect(self.on_memory_warning)

def on_resource_tracked(self, component_id, resource_id, res_type):
    logger.info(f"Resource tracked: {resource_id} ({res_type})")
```

### Best Practices

#### 1. Always Check Coordinator Availability

```python
if self.resources:  # Might be None in tests
    self.resources.track_worker(worker)
```

#### 2. Clear References After Cleanup

```python
def cancel_operation(self):
    if self.current_worker:
        self.current_worker.cancel()
    
    # Clear references
    self.current_worker = None
    self._current_worker_id = None
```

#### 3. Use Appropriate Coordinator Type

```python
# For worker-heavy controllers
def _create_resource_coordinator(self, component_id: str):
    return WorkerResourceCoordinator(component_id)

# For simple resource tracking
def _create_resource_coordinator(self, component_id: str):
    return BaseResourceCoordinator(component_id)
```

#### 4. Implement Cleanup in Controllers

```python
def cleanup(self):
    """Always implement cleanup"""
    # Cancel operations
    # Delegate to coordinator
    # Clear references
```

#### 5. Keep UI Simple

```python
class Tab(QWidget):
    def cleanup(self):
        """Just delegate"""
        if self.controller:
            self.controller.cleanup()
```

### Migration Guide

#### From UI Resource Management to Controller Pattern

**Before (UI Tab)**:
```python
class MediaAnalysisTab(QWidget):
    def __init__(self):
        self._resource_manager = get_service(IResourceManagementService)
        self._resource_manager.register_component(self, "MediaAnalysisTab", "tab")
        self._worker_resource_id = None
        
    def start_analysis(self):
        worker = MediaAnalysisWorker()
        self._worker_resource_id = self._resource_manager.track_resource(
            self, ResourceType.WORKER, worker
        )
        
    def _cleanup_resources(self):
        if self._worker_resource_id:
            self._resource_manager.release_resource(self, self._worker_resource_id)
```

**After (Controller Pattern)**:
```python
class MediaAnalysisTab(QWidget):
    def __init__(self):
        self.controller = MediaAnalysisController()
        
    def start_analysis(self):
        result = self.controller.start_analysis_workflow()
        if result.success:
            self.current_worker = result.value
            
    def cleanup(self):
        if self.controller:
            self.controller.cleanup()

class MediaAnalysisController(BaseController):
    def _create_resource_coordinator(self, component_id: str):
        return WorkerResourceCoordinator(component_id)
        
    def start_analysis_workflow(self):
        worker = MediaAnalysisWorker()
        if self.resources:
            self.resources.track_worker(worker)
        return Result.success(worker)
```

### Troubleshooting

#### Common Issues and Solutions

**Issue**: "Controller being deleted with X active resources"
```python
# Solution: Ensure cleanup is called
def closeEvent(self, event):
    self.cleanup()  # Clean up before close
    super().closeEvent(event)
```

**Issue**: Worker not releasing after completion
```python
# Solution: Ensure auto_release=True (default)
self.resources.track_worker(worker, auto_release=True)
```

**Issue**: Resource coordinator not available in tests
```python
# Solution: Check for availability
if self.resources:
    self.resources.track_worker(worker)
# Or use mock coordinator in tests
```

**Issue**: Memory growing over time
```python
# Solution: Enable periodic cleanup
self._cleanup_timer.start(60000)  # Every 60 seconds
```

### Future Enhancements

#### Planned Features

1. **Resource Pooling**: Reuse expensive resources
2. **Resource Limits**: Per-component resource limits
3. **Priority Resources**: Critical resources with protection
4. **Resource Migration**: Move resources between components
5. **Distributed Tracking**: Cross-process resource management

#### Extension Points

```python
# Custom resource types
class CustomResourceType(ResourceType):
    DATABASE = "database"
    NETWORK = "network"
    
# Custom coordinators
class DatabaseCoordinator(BaseResourceCoordinator):
    def track_connection(self, conn):
        # Specialized tracking
        
# Plugin integration
class PluginResourceAdapter:
    def adapt_plugin_resources(self, plugin):
        # Bridge plugin resources
```

---

## Appendix: Quick Reference

### Terminal Log Signatures

**Successful Resource Lifecycle**:
```
09:06:00,890 - Registered component: MediaAnalysisController_2115453003344
09:06:00,890 - Tracked resource 2da40b88-6e3a-4cb7-aef9-ae5757351a1b
09:06:00,890 - Tracking worker media_analysis_090600
09:06:01,845 - Worker media_analysis_090600 finished after 0.95s
09:06:01,846 - Released resource 2da40b88-6e3a-4cb7-aef9-ae5757351a1b
09:06:14,731 - Component cleanup complete: MediaAnalysisController_2115453003344
```

### Key Classes and Interfaces

| Class | Location | Purpose |
|-------|----------|---------|
| `ResourceManagementService` | `core/services/resource_management_service.py` | Central registry |
| `BaseResourceCoordinator` | `core/resource_coordinators/base_coordinator.py` | Basic coordination |
| `WorkerResourceCoordinator` | `core/resource_coordinators/worker_coordinator.py` | Worker management |
| `BaseController` | `controllers/base_controller.py` | Controller foundation |
| `IResourceManagementService` | `core/services/interfaces.py` | Service interface |

### Resource Types

| Type | Usage | Cleanup Behavior |
|------|-------|-----------------|
| `WORKER` | QThread workers | Cancel → Quit → Terminate |
| `THUMBNAIL` | Image data | Memory release |
| `MAP` | Map widgets | Widget cleanup methods |
| `MEMORY` | Large data | Garbage collection |
| `FILE_HANDLE` | Open files | File closure |
| `CUSTOM` | Anything else | Custom handlers |

### Coordinator Methods

| Method | Purpose | Returns |
|--------|---------|---------|
| `bind_to_component(component)` | Bind to controller | Self (fluent) |
| `track_resource(resource, type, **kwargs)` | Track any resource | UUID string |
| `track_worker(worker, name)` | Track QThread | UUID string |
| `release(resource_id)` | Release specific resource | None |
| `cleanup_all()` | Release all resources | None |
| `get_resource_count()` | Count active resources | Integer |

---

**END OF DOCUMENT**

Version 1.0.0 - Complete Resource Management System Documentation