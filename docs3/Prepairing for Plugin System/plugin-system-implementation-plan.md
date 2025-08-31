# Plugin System Implementation Plan

## Overview

This document defines the essential plugin system components we will implement for the Folder Structure Utility. The design leverages the existing sophisticated architecture (ServiceRegistry, Result objects, unified threading, controller patterns) and adds only the necessary components for plugin lifecycle management.

## Core Plugin Components

### 1. Plugin Base Interface (IPlugin)

The foundational contract that all plugins must implement.

```python
from abc import ABC, abstractmethod
from PySide6.QtWidgets import QWidget
from typing import Optional, List
from core.result_types import Result

class IPlugin(ABC):
    """Base interface for all plugins"""
    
    @abstractmethod
    def initialize(self, context: 'PluginContext') -> Result:
        """Initialize plugin with provided context"""
        pass
    
    @abstractmethod
    def activate(self) -> Result:
        """Activate the plugin"""
        pass
    
    @abstractmethod
    def deactivate(self) -> Result:
        """Deactivate the plugin"""
        pass
    
    @abstractmethod
    def create_widget(self) -> Optional[QWidget]:
        """Create the main widget for this plugin"""
        pass
    
    def cleanup(self) -> None:
        """Cleanup resources before unloading"""
        pass
```

### 2. Plugin Metadata Structure

Plugin identification and dependency information.

```python
from dataclasses import dataclass
from typing import List

@dataclass
class PluginMetadata:
    """Plugin identification and requirements"""
    id: str                    # Unique plugin identifier
    name: str                  # Display name
    version: str              # Plugin version
    description: str          # User-friendly description
    author: str               # Plugin author
    category: str             # Plugin category (forensic, analysis, utility)
    min_core_version: str     # Minimum core application version
    dependencies: List[str]   # Other plugin IDs this plugin depends on
```

### 3. Plugin Registry System

Manages plugin discovery, loading, and lifecycle.

```python
from typing import Dict, List, Optional
from pathlib import Path
from enum import Enum
import threading

class PluginState(Enum):
    """Plugin lifecycle states"""
    DISCOVERED = "discovered"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"

class PluginInstance:
    """Wrapper for plugin instance with state management"""
    
    def __init__(self, plugin_id: str, plugin_class: type):
        self.id = plugin_id
        self.plugin_class = plugin_class
        self.instance = None
        self.state = PluginState.LOADED
        self.metadata = None
        
    def initialize(self, context: 'PluginContext') -> Result:
        """Initialize the plugin with context"""
        try:
            self.instance = self.plugin_class()
            result = self.instance.initialize(context)
            if result.success:
                self.state = PluginState.INITIALIZED
            return result
        except Exception as e:
            self.state = PluginState.ERROR
            return Result.error(FSAError(f"Plugin initialization failed: {e}"))
    
    def activate(self) -> Result:
        """Activate the plugin"""
        if self.state != PluginState.INITIALIZED:
            return Result.error(FSAError("Plugin must be initialized before activation"))
        
        try:
            result = self.instance.activate()
            if result.success:
                self.state = PluginState.ACTIVE
            return result
        except Exception as e:
            return Result.error(FSAError(f"Plugin activation failed: {e}"))
    
    def deactivate(self) -> Result:
        """Deactivate the plugin"""
        if self.state != PluginState.ACTIVE:
            return Result.success(None)
        
        try:
            result = self.instance.deactivate()
            if result.success:
                self.state = PluginState.INACTIVE
            return result
        except Exception as e:
            return Result.error(FSAError(f"Plugin deactivation failed: {e}"))

class PluginRegistry:
    """Central registry for plugin discovery and management"""
    
    def __init__(self):
        self._plugins: Dict[str, PluginInstance] = {}
        self._plugin_paths: Dict[str, Path] = {}
        self._lock = threading.RLock()
        
    def discover_plugins(self, plugin_dir: Path) -> List[PluginMetadata]:
        """Scan directory for available plugins"""
        discovered = []
        
        for path in plugin_dir.iterdir():
            if path.is_dir() and (path / "plugin.json").exists():
                metadata = self._load_plugin_metadata(path)
                if metadata:
                    self._plugin_paths[metadata.id] = path
                    discovered.append(metadata)
                    
        return discovered
    
    def register_plugin(self, plugin_id: str, plugin_class: type) -> None:
        """Register a plugin class with the registry"""
        with self._lock:
            if plugin_id in self._plugins:
                raise ValueError(f"Plugin {plugin_id} already registered")
            
            instance = PluginInstance(plugin_id, plugin_class)
            self._plugins[plugin_id] = instance
    
    def get_plugin(self, plugin_id: str) -> Optional[PluginInstance]:
        """Get plugin instance by ID"""
        return self._plugins.get(plugin_id)
    
    def get_all_plugins(self) -> Dict[str, PluginInstance]:
        """Get all registered plugins"""
        return self._plugins.copy()
    
    def check_dependencies(self, plugin_id: str) -> List[str]:
        """Check if plugin dependencies are satisfied"""
        # Implementation for dependency checking
        pass
```

### 4. Plugin Context System

Provides plugins with access to core services and settings.

```python
from dataclasses import dataclass
import logging

@dataclass
class PluginContext:
    """Context provided to plugins during initialization"""
    plugin_id: str
    service_registry: 'ServiceRegistry'
    settings_manager: 'PluginSettingsManager'
    logger: logging.Logger
```

### 5. Plugin Settings Manager

Namespaced settings management for plugins.

```python
from PySide6.QtCore import QSettings
from typing import Any

class PluginSettingsManager:
    """Manages settings for individual plugins"""
    
    def __init__(self, plugin_id: str, settings: QSettings):
        self.plugin_id = plugin_id
        self.settings = settings
        self._prefix = f"plugins/{plugin_id}/"
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get plugin setting"""
        full_key = self._prefix + key
        return self.settings.value(full_key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set plugin setting"""
        full_key = self._prefix + key
        self.settings.setValue(full_key, value)
    
    def remove(self, key: str):
        """Remove a setting"""
        full_key = self._prefix + key
        self.settings.remove(full_key)
    
    def clear_all(self):
        """Clear all settings for this plugin"""
        self.settings.remove(self._prefix)
```

### 6. Plugin Manager

High-level plugin orchestration and lifecycle management.

```python
from typing import Set

class PluginManager:
    """High-level plugin orchestration"""
    
    def __init__(self, registry: PluginRegistry, service_registry: 'ServiceRegistry'):
        self.registry = registry
        self.service_registry = service_registry
        self._active_plugins: Set[str] = set()
        
    def load_plugin(self, plugin_id: str, activate: bool = True) -> Result[PluginInstance]:
        """Load and optionally activate a plugin"""
        # Check if already loaded
        if plugin_id in self.registry.get_all_plugins():
            return Result.success(self.registry.get_plugin(plugin_id))
        
        # Load plugin module
        if not self.registry.load_plugin(plugin_id):
            return Result.error(FSAError(f"Failed to load plugin {plugin_id}"))
        
        # Check dependencies
        missing = self.registry.check_dependencies(plugin_id)
        if missing:
            return Result.error(FSAError(f"Missing dependencies: {missing}"))
        
        # Get plugin instance
        plugin = self.registry.get_plugin(plugin_id)
        
        # Create plugin context
        context = self._create_plugin_context(plugin_id)
        
        # Initialize plugin
        init_result = plugin.initialize(context)
        if not init_result.success:
            return Result.error(init_result.error)
        
        # Activate if requested
        if activate:
            activate_result = plugin.activate()
            if not activate_result.success:
                return Result.error(activate_result.error)
            self._active_plugins.add(plugin_id)
        
        return Result.success(plugin)
    
    def unload_plugin(self, plugin_id: str) -> Result:
        """Deactivate and unload a plugin"""
        plugin = self.registry.get_plugin(plugin_id)
        if not plugin:
            return Result.error(FSAError(f"Plugin {plugin_id} not found"))
        
        # Deactivate first
        if plugin_id in self._active_plugins:
            deactivate_result = plugin.deactivate()
            if not deactivate_result.success:
                return deactivate_result
            self._active_plugins.remove(plugin_id)
        
        # Cleanup
        if hasattr(plugin.instance, 'cleanup'):
            plugin.instance.cleanup()
        
        # Remove from registry
        del self.registry._plugins[plugin_id]
        
        return Result.success(None)
    
    def _create_plugin_context(self, plugin_id: str) -> PluginContext:
        """Create context object for plugin initialization"""
        return PluginContext(
            plugin_id=plugin_id,
            service_registry=self.service_registry,
            settings_manager=self._get_plugin_settings(plugin_id),
            logger=self._get_plugin_logger(plugin_id)
        )
    
    def get_active_plugins(self) -> List[str]:
        """Get list of currently active plugins"""
        return list(self._active_plugins)
    
    def is_plugin_active(self, plugin_id: str) -> bool:
        """Check if a plugin is currently active"""
        return plugin_id in self._active_plugins
```

## Plugin Controller Pattern

Plugins will follow established controller patterns from the existing architecture.

```python
class PluginControllerBase(BaseController):
    """Base class for plugin controllers"""
    
    def __init__(self, plugin_id: str, plugin_name: str):
        super().__init__(f"{plugin_id}Controller")
        self.plugin_id = plugin_id
        self.plugin_name = plugin_name
        self.current_operation: Optional[BaseWorkerThread] = None
        
        # Lazy-loaded services (following established patterns)
        self._validation_service = None
        self._file_service = None
        
    @property
    def validation_service(self) -> 'IValidationService':
        """Lazy load validation service"""
        if self._validation_service is None:
            self._validation_service = self._get_service(IValidationService)
        return self._validation_service
    
    @property
    def file_service(self) -> 'IFileOperationService':
        """Lazy load file operation service"""
        if self._file_service is None:
            self._file_service = self._get_service(IFileOperationService)
        return self._file_service
    
    def cancel_plugin_operation(self) -> bool:
        """Cancel current plugin operation"""
        if self.current_operation and self.current_operation.isRunning():
            self._log_operation("cancel_plugin_operation", self.plugin_name)
            self.current_operation.cancel()
            return True
        return False
    
    def get_plugin_status(self) -> Dict[str, Any]:
        """Get plugin operation status"""
        if not self.current_operation:
            return {"status": "idle", "operation": None, "can_cancel": False}
        
        return {
            "status": "running" if self.current_operation.isRunning() else "completed",
            "operation": self.current_operation.__class__.__name__,
            "can_cancel": self.current_operation.isRunning()
        }
```

## Plugin Implementation Example

Example of how ForensicTab would be converted to a plugin:

```python
class ForensicPlugin(IPlugin):
    """Forensic processing plugin"""
    
    def __init__(self):
        self.context = None
        self.widget = None
        self.controller = None
        
    def initialize(self, context: PluginContext) -> Result:
        """Initialize with context"""
        self.context = context
        
        # Create plugin-specific controller
        self.controller = ForensicPluginController("forensic-plugin", "Forensic Processing")
        
        # Register any plugin-specific services if needed
        # (Most plugins will use existing core services)
        
        return Result.success(None)
    
    def activate(self) -> Result:
        """Activate the plugin"""
        return Result.success(None)
    
    def deactivate(self) -> Result:
        """Deactivate the plugin"""
        return Result.success(None)
    
    def create_widget(self) -> QWidget:
        """Create the forensic tab widget"""
        if not self.widget:
            # Reuse existing ForensicTab but with plugin context
            self.widget = ForensicTab(self.context.service_registry)
        return self.widget
    
    def cleanup(self) -> None:
        """Cleanup resources"""
        if self.controller:
            self.controller.cancel_plugin_operation()

class ForensicPluginController(PluginControllerBase):
    """Controller for forensic plugin operations"""
    
    def process_forensic_workflow(self, form_data, files, folders, output_dir) -> Result:
        """Process forensic workflow using existing patterns"""
        try:
            # Follow established WorkflowController patterns
            workflow_controller = self._get_service(IWorkflowController)
            return workflow_controller.process_forensic_workflow(
                form_data, files, folders, output_dir
            )
        except Exception as e:
            error = FSAError(f"Forensic workflow failed: {e}")
            self._handle_error(error, {'plugin': 'forensic-plugin'})
            return Result.error(error)
```

## Service Registry Integration

Plugins integrate seamlessly with the existing service registry:

```python
# In service_config.py - extend existing configuration
def configure_plugin_services():
    """Configure plugin-related services"""
    
    # Plugin system services
    plugin_registry = PluginRegistry()
    register_service(IPluginRegistry, plugin_registry)
    
    plugin_manager = PluginManager(plugin_registry, get_service(ServiceRegistry))
    register_service(IPluginManager, plugin_manager)
    
    # Plugin services use same patterns as core services
    # register_service(IPluginSpecificService, PluginSpecificService())
```

## Implementation Phases

### Phase 1: Core Plugin Infrastructure
1. Implement IPlugin interface and PluginMetadata
2. Create PluginRegistry for lifecycle management
3. Build PluginSettingsManager for namespaced settings
4. Develop PluginManager for orchestration

### Phase 2: Plugin Integration Framework
1. Extend service configuration for plugin services
2. Create plugin discovery and loading mechanisms
3. Implement plugin directory structure conventions
4. Build plugin validation and error handling

### Phase 3: First Plugin Conversion
1. Convert ForensicTab to ForensicPlugin
2. Test plugin loading, activation, and operation
3. Validate service integration and error handling
4. Ensure UI integration works properly

### Phase 4: Additional Plugin Conversions
1. Convert HashingTab to HashingPlugin
2. Convert BatchTab to BatchPlugin (most complex)
3. Test multi-plugin scenarios
4. Implement plugin management UI

## Key Benefits

1. **Minimal Architecture Changes**: Leverages existing sophisticated systems
2. **Service Integration**: Plugins use established service injection patterns
3. **Error Handling**: Inherits existing thread-safe error management
4. **Threading**: Uses proven unified worker thread architecture
5. **Result Communication**: Maintains consistent Result-based protocols
6. **Settings Isolation**: Plugin-specific settings without conflicts
7. **Lifecycle Management**: Clean plugin loading, activation, and cleanup

## Architecture Preservation

This plugin system design preserves all existing architectural strengths:

- **ServiceRegistry remains the core dependency injection system**
- **Result objects maintain type-safe communication**
- **ErrorHandler provides thread-safe error routing**
- **BaseWorkerThread ensures unified threading patterns**
- **Controller patterns provide orchestration examples**

Plugins extend the architecture without replacing or duplicating existing sophisticated systems.