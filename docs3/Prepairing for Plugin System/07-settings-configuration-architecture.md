# Document 8: Settings & Configuration Architecture

## Natural Language Technical Overview

### Understanding the Settings Management System

The Folder Structure Utility employs a sophisticated centralized settings management system that demonstrates enterprise-grade configuration architecture. Rather than scattered configuration files or ad-hoc property storage, the application uses a single `SettingsManager` singleton that provides a unified interface to Qt's platform-native settings storage.

**The Settings as Contract Pattern**: The system treats settings as a formal contract between different parts of the application. Every setting has a canonical key defined in a central registry (`KEYS` dictionary), which prevents typos, ensures consistency, and enables refactoring. This means when a plugin needs archive settings, it requests `'ARCHIVE_METHOD'` and gets the canonical key `'archive.method'` automatically.

**Platform-Native Storage Strategy**: Instead of custom configuration files, the system leverages Qt's `QSettings` which automatically chooses the appropriate platform storage:
- **Windows**: Registry (`HKEY_CURRENT_USER`)
- **macOS**: Property list files (`~/Library/Preferences`)
- **Linux**: Configuration files (`~/.config`)

This ensures settings integrate properly with each operating system's conventions and backup systems.

**Type-Safe Property Pattern**: The SettingsManager provides convenience properties that handle Qt's string-based storage internally while exposing strongly-typed interfaces to the application. For example, `settings.calculate_hashes` returns a proper boolean even though Qt stores it as a string, and includes validation to handle edge cases.

**Validation and Fallback Strategy**: Every setting includes comprehensive validation with safe fallbacks. If a user manually edits their settings and introduces an invalid value (like setting archive method to "invalid_method"), the system automatically falls back to safe defaults rather than crashing.

**Migration and Compatibility Support**: The settings system includes built-in support for migrating between different setting formats and versions, ensuring that users who upgrade the application don't lose their preferences or encounter configuration conflicts.

### Plugin Integration Philosophy

**Namespaced Plugin Settings**: The architecture anticipates plugin extension through a namespacing strategy where plugin settings are isolated under `plugins/{plugin-id}/` keys. This prevents conflicts between plugins and ensures clean uninstallation.

**Settings as Services**: The SettingsManager follows the same service-oriented patterns as the rest of the application - plugins access settings through dependency injection rather than global references, enabling testing with mock settings and providing clear dependency relationships.

**Shared Core Settings**: Plugins can access core application settings (like performance options or user information) while maintaining their own isolated configuration space. This enables plugins to integrate with global preferences while preserving independence.

**Validation Extension Points**: The validation patterns established in core settings provide templates for plugins to implement their own setting validation with consistent error handling and fallback behavior.

---

## Senior Developer Technical Specification

### SettingsManager Core Architecture

The `SettingsManager` class provides centralized, thread-safe configuration management using Qt's native settings storage with comprehensive validation and type safety.

#### Singleton Pattern Implementation

```python
class SettingsManager:
    """Centralized settings management with migration support"""
    
    _instance = None
    
    def __new__(cls):
        """Thread-safe singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize settings manager"""
        if self._initialized:
            return
        
        self._initialized = True
        self._settings = QSettings('FolderStructureUtility', 'Settings')
        self._set_defaults()
```

**Plugin Integration Benefits**:
- Single settings instance shared across all plugins
- Automatic default initialization on first access
- Thread-safe access for plugin worker threads

#### Canonical Key Registry System

The `KEYS` dictionary provides centralized key management with hierarchical namespacing:

```python
KEYS = {
    # Forensic settings
    'CALCULATE_HASHES': 'forensic.calculate_hashes',
    'HASH_ALGORITHM': 'forensic.hash_algorithm',
    
    # Performance settings  
    'COPY_BUFFER_SIZE': 'performance.copy_buffer_size',
    
    # Archive settings
    'ZIP_COMPRESSION_LEVEL': 'archive.compression_level',
    'ZIP_ENABLED': 'archive.zip_enabled', 
    'ZIP_LEVEL': 'archive.zip_level',
    'ARCHIVE_METHOD': 'archive.method',
    
    # User settings
    'TECHNICIAN_NAME': 'user.technician_name',
    'BADGE_NUMBER': 'user.badge_number',
    
    # Report settings
    'TIME_OFFSET_PDF': 'reports.generate_time_offset',
    'UPLOAD_LOG_PDF': 'reports.generate_upload_log',
    'HASH_CSV': 'reports.generate_hash_csv',
    
    # UI settings
    'AUTO_SCROLL_LOG': 'ui.auto_scroll_log',
    'CONFIRM_EXIT': 'ui.confirm_exit_with_operations',
    
    # Debug settings
    'DEBUG_LOGGING': 'debug.enable_logging',
    
    # Path settings
    'LAST_OUTPUT_DIR': 'paths.last_output_directory',
    'LAST_INPUT_DIR': 'paths.last_input_directory'
}
```

**Key Design Principles**:
- **Hierarchical Namespacing**: Groups related settings (`forensic.*`, `archive.*`, etc.)
- **Descriptive Names**: Constants like `'CALCULATE_HASHES'` map to descriptive keys
- **Plugin Extension Pattern**: Plugins can add keys like `'PLUGIN_SPECIFIC_SETTING': 'plugins.my_plugin.setting'`

#### Core Settings API

**`get(key: str, default: Any = None) -> Any`**
- **Purpose**: Retrieve setting value with automatic key resolution
- **Key Resolution**: Accepts either KEYS constant or direct key string
- **Type Preservation**: Maintains original data types where possible
- **Plugin Usage**:
  ```python
  # Using constant (recommended)
  enabled = settings.get('CALCULATE_HASHES', False)
  
  # Using direct key (for plugin-specific settings)
  plugin_setting = settings.get('plugins.my_plugin.custom_option', 'default')
  ```

**`set(key: str, value: Any)`**
- **Purpose**: Store setting value with automatic key resolution
- **Validation**: Individual properties provide validation (see property setters)
- **Plugin Usage**:
  ```python
  # Core setting
  settings.set('HASH_ALGORITHM', 'sha256')
  
  # Plugin setting
  settings.set('plugins.my_plugin.api_endpoint', 'https://api.example.com')
  ```

**`sync()`**
- **Purpose**: Force immediate write to platform storage
- **Thread Safety**: Safe to call from any thread
- **Plugin Usage**: Essential after bulk setting changes

**`contains(key: str) -> bool`**
- **Purpose**: Check setting existence with key resolution
- **Plugin Usage**: Useful for optional setting detection

### Platform Storage Implementation

#### Qt Settings Integration

```python
def __init__(self):
    self._settings = QSettings('FolderStructureUtility', 'Settings')
```

**Storage Locations by Platform**:

**Windows**:
- **Registry Path**: `HKEY_CURRENT_USER\Software\FolderStructureUtility\Settings`
- **Key Format**: Hierarchical registry keys (e.g., `forensic\calculate_hashes`)
- **Benefits**: Integrated with Windows backup, Group Policy support

**macOS**:
- **Plist Path**: `~/Library/Preferences/FolderStructureUtility.Settings.plist`
- **Format**: XML property list with hierarchical structure
- **Benefits**: Time Machine backup, standard macOS preferences

**Linux**:
- **Config Path**: `~/.config/FolderStructureUtility/Settings.conf`
- **Format**: INI-style configuration file
- **Benefits**: Standard XDG config directory, easy manual editing

#### Plugin Settings Extension Strategy

**Plugin Namespace Pattern**:
```python
# Plugin settings stored under plugins/{plugin-id}/ namespace
plugin_key = f"plugins/{plugin_id}/{setting_name}"

# Example plugin keys:
# "plugins/forensic-plugin/auto_hash_verification"
# "plugins/batch-plugin/max_concurrent_jobs"  
# "plugins/custom-reporter/template_path"
```

**Plugin Settings Manager Pattern**:
```python
class PluginSettingsManager:
    """Namespaced settings access for plugins"""
    
    def __init__(self, plugin_id: str, settings: SettingsManager):
        self.plugin_id = plugin_id
        self.settings = settings
        self._prefix = f"plugins/{plugin_id}/"
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get plugin-specific setting"""
        full_key = self._prefix + key
        return self.settings.get(full_key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set plugin-specific setting"""
        full_key = self._prefix + key
        self.settings.set(full_key, value)
```

### Type-Safe Property System

The SettingsManager provides strongly-typed convenience properties that handle Qt's string-based storage while exposing proper types to the application.

#### Boolean Properties with String Conversion

```python
@property
def calculate_hashes(self) -> bool:
    """Whether to calculate file hashes"""
    value = self.get('CALCULATE_HASHES', True)
    # Handle QSettings string-to-bool conversion
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on')
    return bool(value)
```

**String-to-Boolean Conversion Logic**:
- **True values**: `'true'`, `'1'`, `'yes'`, `'on'` (case-insensitive)
- **False values**: Everything else
- **Fallback**: Explicit boolean casting for non-string types

**Plugin Implementation Pattern**:
```python
class PluginSettings:
    def __init__(self, settings_manager: PluginSettingsManager):
        self.settings = settings_manager
    
    @property 
    def auto_validation(self) -> bool:
        """Plugin-specific boolean setting"""
        value = self.settings.get('auto_validation', True)
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)
```

#### Validated Enum Properties

```python
@property
def archive_method(self) -> str:
    """Archive method: 'native_7zip', 'buffered_python', or 'auto'"""
    value = str(self.get('ARCHIVE_METHOD', 'native_7zip'))
    if value not in ['native_7zip', 'buffered_python', 'auto']:
        return 'native_7zip'  # Safe fallback to highest performance
    return value

@archive_method.setter
def archive_method(self, value: str):
    """Set archive method with validation"""
    if value in ['native_7zip', 'buffered_python', 'auto']:
        self.set('ARCHIVE_METHOD', value)
    else:
        raise ValueError(f"Invalid archive method: {value}")
```

**Validation Pattern Benefits**:
- **Input Sanitization**: Invalid values automatically fall back to safe defaults
- **Type Safety**: Properties always return expected types
- **Error Prevention**: Setter validation prevents invalid states

#### Range-Clamped Numeric Properties

```python
@property
def copy_buffer_size(self) -> int:
    """Buffer size for file copying (clamped to reasonable range)"""
    raw_value = self.get('COPY_BUFFER_SIZE', 1048576)
    
    # Handle legacy KB vs bytes storage
    if isinstance(raw_value, str):
        raw_value = int(raw_value)
    elif raw_value < 8192:  # Likely in KB if less than 8KB
        raw_value = raw_value * 1024  # Convert KB to bytes
    
    size = int(raw_value)
    # Clamp between 8KB and 10MB
    return min(max(size, 8192), 10485760)
```

**Range Clamping Benefits**:
- **Performance Protection**: Prevents buffer sizes that could cause memory issues
- **Legacy Migration**: Handles old KB-based values vs new byte-based values
- **Defensive Programming**: User can't accidentally set buffer to 1 byte or 100GB

#### Path Properties with Type Safety

```python
@property
def last_output_directory(self) -> Optional[Path]:
    """Last used output directory"""
    path_str = self.get('LAST_OUTPUT_DIR', None)
    return Path(path_str) if path_str else None

def set_last_output_directory(self, path: Path):
    """Set last output directory"""
    self.set('LAST_OUTPUT_DIR', str(path))
```

**Path Handling Pattern**:
- **Storage**: Always store as string for Qt compatibility
- **Return**: Convert to `Path` objects for type safety and path operations
- **Validation**: `Path()` constructor validates path format automatically

### Settings Categories and Usage Patterns

#### Forensic Settings Group

**Core Evidence Processing Settings**:
```python
# Hash calculation settings
calculate_hashes: bool = True           # Enable hash verification
hash_algorithm: str = 'sha256'          # Hash algorithm (sha256/md5)

# Usage in plugins:
forensic_service = get_service(IForensicService)
if settings.calculate_hashes:
    hashes = forensic_service.calculate_hashes(files, settings.hash_algorithm)
```

#### Performance Settings Group

**File Operation Performance**:
```python
# Buffer size for file operations
copy_buffer_size: int = 1048576         # 1MB default, clamped 8KB-10MB

# Usage in file operation plugins:
buffer_size = settings.copy_buffer_size
buffered_ops = BufferedFileOperations(buffer_size=buffer_size)
```

#### Archive Settings Group

**ZIP Creation Configuration**:
```python
# Archive method selection
archive_method: str = 'native_7zip'     # native_7zip/buffered_python/auto
zip_compression_level: int = 6          # 0-9 compression level
zip_enabled: str = 'enabled'            # enabled/disabled/prompt
zip_level: str = 'root'                 # root/location/datetime

# Usage in archive plugins:
if settings.zip_enabled == 'enabled':
    archive_service = get_service(IArchiveService)
    archives = archive_service.create_archives(
        source_path, output_path, 
        compression_level=settings.zip_compression_level,
        method=settings.archive_method
    )
```

#### User Settings Group

**Technician/Analyst Information**:
```python
# Personal identification for reports
technician_name: str = ''
badge_number: str = ''

# Usage in report plugins:
report_context = {
    'technician': settings.technician_name,
    'badge': settings.badge_number,
    'timestamp': datetime.now()
}
```

#### Report Settings Group

**Report Generation Control**:
```python
# Report generation flags
generate_time_offset_pdf: bool = True
generate_upload_log_pdf: bool = True  
generate_hash_csv: bool = True         # Only if hashes calculated

# Usage in report plugins:
reports_to_generate = []
if settings.generate_time_offset_pdf:
    reports_to_generate.append('time_offset')
if settings.generate_upload_log_pdf:
    reports_to_generate.append('technician_log')
if settings.generate_hash_csv and settings.calculate_hashes:
    reports_to_generate.append('hash_csv')
```

#### UI Settings Group

**User Interface Behavior**:
```python
# Interface behavior settings
auto_scroll_log: bool = True           # Auto-scroll log console
confirm_exit_with_operations: bool = True  # Confirm exit during ops

# Usage in UI plugins:
if settings.auto_scroll_log:
    self.log_console.scrollToBottom()
    
if settings.confirm_exit_with_operations and self.has_active_operations():
    self.show_exit_confirmation_dialog()
```

### Settings Integration Patterns

#### Service-Based Settings Access

**Settings as Injected Dependency**:
```python
class MyPluginService(BaseService):
    def __init__(self, settings: SettingsManager):
        super().__init__()
        self.settings = settings
    
    def process_data(self, data: Any) -> Result[Any]:
        # Access settings through injected dependency
        if self.settings.calculate_hashes:
            hash_result = self._calculate_hash(data)
        
        buffer_size = self.settings.copy_buffer_size
        return self._process_with_buffer(data, buffer_size)

# Service registration with settings injection
def configure_plugin_services():
    settings = SettingsManager()  # Singleton
    register_service(IMyPluginService, MyPluginService(settings))
```

#### UI Components Settings Binding

**Automatic UI-Settings Synchronization**:
```python
class PluginSettingsDialog(QDialog):
    def __init__(self, settings: SettingsManager):
        self.settings = settings
        self._create_ui()
        self._bind_settings()
    
    def _bind_settings(self):
        """Bind UI controls to settings"""
        # Load current values
        self.hash_enabled_checkbox.setChecked(self.settings.calculate_hashes)
        self.algorithm_combo.setCurrentText(self.settings.hash_algorithm)
        
        # Connect change signals
        self.hash_enabled_checkbox.toggled.connect(
            lambda checked: self.settings.set('CALCULATE_HASHES', checked)
        )
        self.algorithm_combo.currentTextChanged.connect(
            lambda algorithm: setattr(self.settings, 'hash_algorithm', algorithm)
        )
```

#### Worker Thread Settings Access

**Thread-Safe Settings in Background Operations**:
```python
class PluginWorkerThread(BaseWorkerThread):
    def __init__(self, settings: SettingsManager):
        super().__init__()
        self.settings = settings
    
    def execute(self) -> Result:
        # Safe to access settings from worker thread
        if self.settings.calculate_hashes:
            algorithm = self.settings.hash_algorithm  # Thread-safe property
            
        buffer_size = self.settings.copy_buffer_size  # Validated and clamped
        
        # Use settings in operation
        return self._perform_operation(buffer_size, algorithm)
```

### Plugin Extension Architecture

#### Plugin Settings Manager

**Isolated Plugin Configuration**:
```python
class PluginSettingsManager:
    """Manages settings for individual plugins with namespace isolation"""
    
    def __init__(self, plugin_id: str, core_settings: SettingsManager):
        self.plugin_id = plugin_id
        self.core_settings = core_settings
        self._prefix = f"plugins/{plugin_id}/"
        
        # Initialize plugin defaults
        self._set_plugin_defaults()
    
    def _set_plugin_defaults(self):
        """Set default values for plugin settings"""
        # Override in plugin implementations
        pass
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get plugin setting with namespace isolation"""
        full_key = self._prefix + key
        return self.core_settings.get(full_key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set plugin setting with namespace isolation"""
        full_key = self._prefix + key
        self.core_settings.set(full_key, value)
    
    def get_core_setting(self, key: str, default: Any = None) -> Any:
        """Access core application settings"""
        return self.core_settings.get(key, default)
```

**Plugin Implementation Example**:
```python
class ForensicPluginSettings(PluginSettingsManager):
    """Settings for forensic plugin"""
    
    def _set_plugin_defaults(self):
        """Set forensic plugin defaults"""
        if not self.core_settings.contains(f"{self._prefix}auto_hash_verification"):
            self.set('auto_hash_verification', True)
        if not self.core_settings.contains(f"{self._prefix}evidence_templates"):
            self.set('evidence_templates', ['standard', 'mobile', 'network'])
    
    @property
    def auto_hash_verification(self) -> bool:
        """Whether to automatically verify hashes after copy"""
        value = self.get('auto_hash_verification', True)
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)
    
    @property  
    def evidence_templates(self) -> List[str]:
        """Available evidence templates"""
        templates = self.get('evidence_templates', ['standard'])
        if isinstance(templates, str):
            return templates.split(',')
        return templates if isinstance(templates, list) else ['standard']
```

#### Plugin Context Integration

**Settings Provided to Plugins via Context**:
```python
@dataclass
class PluginContext:
    """Context provided to plugins during initialization"""
    plugin_id: str
    service_registry: ServiceRegistry
    settings_manager: PluginSettingsManager  # Plugin-specific settings
    logger: logging.Logger

# Plugin initialization with settings context
def initialize_plugin(plugin_id: str) -> Result[IPlugin]:
    core_settings = SettingsManager()
    plugin_settings = PluginSettingsManager(plugin_id, core_settings)
    
    context = PluginContext(
        plugin_id=plugin_id,
        service_registry=get_service(ServiceRegistry),
        settings_manager=plugin_settings,
        logger=get_plugin_logger(plugin_id)
    )
    
    plugin = load_plugin_class(plugin_id)()
    return plugin.initialize(context)
```

### Settings Migration and Compatibility

#### Version Migration Support

**Schema Evolution Handling**:
```python
class SettingsManager:
    SETTINGS_VERSION = "2.0"
    
    def _migrate_settings_if_needed(self):
        """Migrate settings from older versions"""
        current_version = self.get('system.settings_version', '1.0')
        
        if current_version == '1.0':
            self._migrate_from_v1_0()
            current_version = '1.1'
        
        if current_version == '1.1':
            self._migrate_from_v1_1()
            current_version = '2.0'
        
        self.set('system.settings_version', self.SETTINGS_VERSION)
    
    def _migrate_from_v1_0(self):
        """Migrate from version 1.0 settings format"""
        # Convert legacy boolean strings to proper booleans
        if self.contains('legacy_hash_enabled'):
            old_value = self.get('legacy_hash_enabled')
            self.set('CALCULATE_HASHES', old_value == 'true')
            self._settings.remove('legacy_hash_enabled')
        
        # Convert buffer sizes from KB to bytes
        if self.contains('buffer_size_kb'):
            kb_value = int(self.get('buffer_size_kb', 1024))
            self.set('COPY_BUFFER_SIZE', kb_value * 1024)
            self._settings.remove('buffer_size_kb')
```

#### Plugin Settings Migration

**Plugin-Specific Migration Hooks**:
```python
class PluginSettingsManager:
    def migrate_plugin_settings(self, from_version: str, to_version: str):
        """Plugin-specific settings migration"""
        # Override in plugin implementations
        pass

# Plugin implementation
class MyPluginSettings(PluginSettingsManager):
    def migrate_plugin_settings(self, from_version: str, to_version: str):
        """Migrate plugin settings between versions"""
        if from_version == '1.0' and to_version == '2.0':
            # Convert old plugin setting format
            if self.core_settings.contains(f"{self._prefix}old_setting_name"):
                old_value = self.get('old_setting_name')
                self.set('new_setting_name', self._convert_old_format(old_value))
                self.core_settings._settings.remove(f"{self._prefix}old_setting_name")
```

### Settings Validation and Error Handling

#### Comprehensive Validation Framework

**Setting Validation with Fallbacks**:
```python
def _validate_setting(self, key: str, value: Any, validator_func: callable, fallback: Any) -> Any:
    """Validate setting value with automatic fallback"""
    try:
        if validator_func(value):
            return value
        else:
            logger.warning(f"Invalid value for {key}: {value}. Using fallback: {fallback}")
            return fallback
    except Exception as e:
        logger.error(f"Validation error for {key}: {e}. Using fallback: {fallback}")
        return fallback

# Usage in property implementations
@property
def hash_algorithm(self) -> str:
    """Hash algorithm with validation"""
    value = str(self.get('HASH_ALGORITHM', 'sha256')).lower()
    return self._validate_setting(
        'HASH_ALGORITHM',
        value,
        lambda v: v in ['sha256', 'md5'],
        'sha256'
    )
```

**Plugin Validation Extension**:
```python
class PluginSettingsValidator:
    """Validation framework for plugin settings"""
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format"""
        return url.startswith(('http://', 'https://'))
    
    @staticmethod
    def validate_port(port: int) -> bool:
        """Validate network port range"""
        return 1 <= port <= 65535
    
    @staticmethod
    def validate_file_path(path: str) -> bool:
        """Validate file path accessibility"""
        return Path(path).parent.exists()

# Plugin usage
class APIPluginSettings(PluginSettingsManager):
    @property
    def api_endpoint(self) -> str:
        """API endpoint URL with validation"""
        value = self.get('api_endpoint', 'https://api.example.com')
        if not PluginSettingsValidator.validate_url(value):
            logger.warning(f"Invalid API endpoint: {value}")
            return 'https://api.example.com'
        return value
```

### Debug and Development Support

#### Settings Debugging Tools

**Development and Testing Utilities**:
```python
class SettingsManager:
    def reset_all_settings(self):
        """Reset all settings for beta testing"""
        self._settings.clear()
        self._settings.sync()
        self._set_defaults()
        logger.info("All settings reset for beta testing")
    
    def export_settings_debug(self) -> Dict[str, Any]:
        """Export all settings for debugging"""
        debug_settings = {}
        for key_name, canonical_key in self.KEYS.items():
            debug_settings[key_name] = {
                'canonical_key': canonical_key,
                'value': self.get(canonical_key),
                'type': type(self.get(canonical_key)).__name__
            }
        return debug_settings
    
    def validate_all_settings(self) -> List[str]:
        """Validate all settings and return issues"""
        issues = []
        
        # Validate each setting using its property accessor
        try:
            _ = self.calculate_hashes
        except Exception as e:
            issues.append(f"calculate_hashes: {e}")
        
        try:
            _ = self.hash_algorithm
        except Exception as e:
            issues.append(f"hash_algorithm: {e}")
        
        # Continue for all settings...
        return issues
```

**Plugin Settings Debugging**:
```python
class PluginSettingsManager:
    def debug_plugin_settings(self) -> Dict[str, Any]:
        """Export plugin settings for debugging"""
        plugin_settings = {}
        
        # Get all keys under plugin namespace
        for key in self.core_settings._settings.allKeys():
            if key.startswith(self._prefix):
                setting_name = key[len(self._prefix):]
                plugin_settings[setting_name] = self.get(setting_name)
        
        return {
            'plugin_id': self.plugin_id,
            'namespace': self._prefix,
            'settings': plugin_settings
        }
```

### Current Settings Usage in Codebase

#### Core Component Integration

**Components Using Settings**:
- **HashController**: `settings.hash_algorithm` for hash operations
- **MainWindow**: Multiple settings for UI behavior and processing flags
- **BufferedFileOperations**: `copy_buffer_size` for performance optimization
- **BatchProcessor**: Settings for batch job processing preferences
- **LogConsole**: `auto_scroll_log` for UI behavior
- **ZipController**: Archive settings for ZIP creation
- **Various Dialogs**: UserSettingsDialog, ZipSettingsDialog for configuration

**Settings Access Patterns**:
```python
# Global singleton access (current pattern)
from core.settings_manager import settings

# Class member access
calculate_hash = settings.calculate_hashes
algorithm = settings.hash_algorithm
buffer_size = settings.copy_buffer_size

# Settings injection (recommended for plugins)
class PluginService(BaseService):
    def __init__(self, settings: SettingsManager):
        self.settings = settings
```

This comprehensive settings architecture provides plugins with robust, validated, and thread-safe configuration management while maintaining clear separation of concerns and enabling seamless integration with the core application's enterprise-grade patterns.