# Document 2: Service Layer API Reference

## Natural Language Technical Overview

### Understanding the Service Layer Architecture

The Folder Structure Utility employs a sophisticated service-oriented architecture that acts as the backbone for plugin communication. Think of the service layer as a "universal translator" that allows different parts of the application to communicate through well-defined contracts, without needing to know implementation details.

**The Service Registry Pattern**: At the heart of this system is a thread-safe service registry that acts like a "phone book" for the entire application. When a plugin needs to perform path building, file operations, or report generation, it doesn't directly access implementation classes. Instead, it requests services through interfaces, and the registry provides the appropriate implementation.

**The Interface-Implementation Contract**: Every service is defined by an interface (IPathService, IFileOperationService, etc.) that specifies what operations are available and what parameters they expect. The actual implementation can change without breaking plugins, as long as it honors the interface contract. This enables seamless upgrades and testing with mock services.

**Result-Based Communication**: All service operations return Result objects instead of throwing exceptions or returning simple boolean values. This creates a standardized "language" for success, failure, warnings, and metadata that plugins can reliably interpret.

**Dependency Injection Foundation**: Services can depend on other services, and the registry handles the complexity of providing dependencies in the right order. This eliminates circular dependency issues and makes testing much simpler.

### Plugin Integration Strategy

**Service Discovery**: Plugins discover available services through the global registry using `get_service(IPathService)` calls. This means plugins never need to know about specific implementation classes.

**Service Extension**: Plugins can register their own services, extending the application's capabilities. For example, a hashing plugin would register `IHashingService` with methods for different hash algorithms.

**Shared Services**: Core services like path building and file operations are shared across all plugins, ensuring consistent behavior and avoiding code duplication.

**Configuration Management**: The service configuration system handles the complex orchestration of service registration, including dependency resolution and proper initialization order.

---

## Senior Developer API Reference

### ServiceRegistry Core API

The ServiceRegistry provides the foundation for the entire plugin system through dependency injection and service discovery.

#### ServiceRegistry Class

```python
class ServiceRegistry:
    """Thread-safe service registry with dependency injection"""
    
    def __init__(self):
        self._services: Dict[Type, Any] = {}
        self._factories: Dict[Type, callable] = {}
        self._singletons: Dict[Type, Any] = {}
        self._lock = threading.RLock()
```

#### Core Methods

**`register_singleton(interface: Type[T], implementation: T)`**
- **Purpose**: Register a singleton service instance that will be reused across all requests
- **Thread Safety**: Uses RLock for concurrent access protection
- **Plugin Usage**: `register_service(IMyPluginService, MyPluginService())`

**`register_factory(interface: Type[T], factory: callable)`**
- **Purpose**: Register a factory function that creates new service instances on demand
- **Use Cases**: Services that need per-request state or expensive initialization
- **Plugin Usage**: `register_factory(IMyService, lambda: MyService(config))`

**`get_service(interface: Type[T]) -> T`**
- **Purpose**: Retrieve service instance with automatic dependency resolution
- **Lookup Order**: Singletons first, then factories
- **Error Handling**: Raises `ValueError` if service not found
- **Plugin Usage**: `path_service = get_service(IPathService)`

#### Global Registry Functions

```python
# Global registry instance (singleton)
_service_registry = ServiceRegistry()

def get_service(interface: Type[T]) -> T:
    """Convenience function for plugin service access"""
    return _service_registry.get_service(interface)

def register_service(interface: Type[T], implementation: T):
    """Convenience function for plugin service registration"""
    _service_registry.register_singleton(interface, implementation)

def register_factory(interface: Type[T], factory: callable):
    """Convenience function for plugin factory registration"""
    _service_registry.register_factory(interface, factory)
```

**Plugin Integration Example**:
```python
# Plugin initialization
def initialize_plugin(services: ServiceRegistry, settings: SettingsManager) -> Result[None]:
    # Register plugin services
    register_service(IMyPluginService, MyPluginService(settings))
    
    # Access core services
    path_service = get_service(IPathService) 
    file_service = get_service(IFileOperationService)
    
    return Result.success(None)
```

---

### Service Interfaces Documentation

#### IPathService Interface

**Purpose**: Path building, validation, and template management operations
**Implementation**: `PathService` (core/services/path_service.py)

##### Core Path Operations

**`build_forensic_path(form_data: FormData, base_path: Path) -> Result[Path]`**
- **Function**: Creates forensic folder structure from form data and template
- **Parameters**: 
  - `form_data`: FormData instance with case information
  - `base_path`: Root directory for folder structure
- **Returns**: `Result[Path]` with created folder path or error
- **Error Handling**: FileOperationError for validation failures, path creation issues
- **Template Support**: Uses active template or falls back to legacy ForensicPathBuilder

**`validate_output_path(path: Path, base: Path) -> Result[Path]`**
- **Function**: Security validation to prevent directory traversal attacks
- **Parameters**:
  - `path`: Path to validate
  - `base`: Allowed base directory
- **Returns**: `Result[Path]` with validated path or security error
- **Security**: Prevents paths outside base directory, handles symbolic links

**`sanitize_path_component(component: str) -> str`**
- **Function**: Remove invalid characters from path components for cross-platform compatibility
- **Parameters**: `component`: Path component string to sanitize
- **Returns**: Sanitized string safe for file system use
- **Character Handling**: Removes/replaces invalid characters, handles Unicode

##### Template Management Operations

**`get_available_templates() -> List[Dict[str, str]]`**
- **Function**: List all available templates for UI selection
- **Returns**: List of dicts with 'id' and 'name' keys
- **Template Sources**: Includes built-in, imported, and user-created templates

**`set_current_template(template_id: str) -> Result[None]`**
- **Function**: Set active template for path building operations
- **Parameters**: `template_id`: Template identifier
- **Returns**: `Result[None]` with success or error if template not found

**`get_current_template_id() -> str`**
- **Function**: Get currently active template identifier
- **Returns**: Template ID string (defaults to "default_forensic")

**`reload_templates() -> Result[None]`**
- **Function**: Refresh template cache from storage
- **Returns**: `Result[None]` with operation status
- **Use Cases**: After template import/export, configuration changes

##### Template Import/Export Operations

**`import_template(file_path: Path) -> Result[Dict[str, Any]]`**
- **Function**: Import template from JSON file with validation
- **Parameters**: `file_path`: Path to template JSON file
- **Returns**: `Result[Dict]` with template data or validation errors
- **Validation**: Schema validation, format checking, name conflicts

**`export_template(template_id: str, file_path: Path) -> Result[None]`**
- **Function**: Export template to JSON file
- **Parameters**: 
  - `template_id`: Template to export
  - `file_path`: Destination file path
- **Returns**: `Result[None]` with operation status
- **File Handling**: Overwrites existing files, creates directories as needed

**`validate_template_file(file_path: Path) -> Result[List[Dict[str, Any]]]`**
- **Function**: Validate template file without importing
- **Parameters**: `file_path`: Template file to validate
- **Returns**: `Result[List]` with validation issues or empty list if valid
- **Validation Rules**: Schema compliance, required fields, format consistency

**`get_template_info(template_id: str) -> Result[Dict[str, Any]]`**
- **Function**: Get detailed template metadata
- **Parameters**: `template_id`: Template identifier
- **Returns**: `Result[Dict]` with complete template information
- **Metadata**: Name, description, structure, source, version info

**`delete_user_template(template_id: str) -> Result[None]`**
- **Function**: Delete user-imported template (built-in templates protected)
- **Parameters**: `template_id`: Template to delete
- **Returns**: `Result[None]` with operation status
- **Safety**: Only deletes user templates, updates active template if needed

**`get_template_sources() -> List[Dict[str, str]]`**
- **Function**: Get templates grouped by source (built-in, imported, etc.)
- **Returns**: List of source groups with template lists
- **Organization**: Enables UI grouping and source identification

**`build_archive_name(form_data: FormData) -> Result[str]`**
- **Function**: Generate archive filename using template pattern
- **Parameters**: `form_data`: Case information for name building
- **Returns**: `Result[str]` with sanitized archive name
- **Template Integration**: Uses current template or fallback pattern

---

#### IFileOperationService Interface

**Purpose**: File and folder copy operations with performance optimization
**Implementation**: `FileOperationService` (core/services/file_operation_service.py)

##### File Operations

**`copy_files(files: List[Path], destination: Path, calculate_hash: bool = True) -> FileOperationResult`**
- **Function**: Copy multiple files to destination with optional hash verification
- **Parameters**:
  - `files`: List of file paths to copy
  - `destination`: Destination directory
  - `calculate_hash`: Whether to calculate SHA-256 hashes during copy
- **Returns**: `FileOperationResult` with operation statistics and performance metrics
- **Features**: 
  - Automatic destination directory creation
  - File path validation and filtering
  - Progress reporting via callbacks
  - Buffered I/O for performance
  - Hash calculation during copy (no double-read)

**`copy_folders(folders: List[Path], destination: Path, calculate_hash: bool = True) -> FileOperationResult`**
- **Function**: Copy folder hierarchies preserving structure
- **Parameters**:
  - `folders`: List of folder paths to copy
  - `destination`: Destination directory
  - `calculate_hash`: Whether to calculate hashes for all files
- **Returns**: `FileOperationResult` with detailed operation results
- **Hierarchy Preservation**: Maintains complete folder structure and metadata
- **Recursive Processing**: Handles nested folders with progress reporting

##### FileOperationResult Structure

```python
@dataclass
class FileOperationResult(Result[Dict[str, Any]]):
    """Specialized result for file operations"""
    files_processed: int = 0
    bytes_processed: int = 0
    performance_metrics: Optional[PerformanceMetrics] = None
    hash_results: Dict[str, str] = field(default_factory=dict)  # filepath -> hash
    skipped_files: List[str] = field(default_factory=list)
    operation_duration: float = 0.0
```

**Plugin Usage Examples**:
```python
# Basic file copying
file_service = get_service(IFileOperationService)
result = file_service.copy_files([Path("source.txt")], Path("destination/"))

if result.success:
    print(f"Copied {result.files_processed} files, {result.bytes_processed} bytes")
    print(f"Speed: {result.performance_metrics.average_speed_mbps:.2f} MB/s")
else:
    handle_error(result.error)
```

---

#### IReportService Interface

**Purpose**: PDF report generation for forensic documentation
**Implementation**: `ReportService` (core/services/report_service.py)

##### Report Generation Methods

**`generate_time_offset_report(form_data: FormData, output_path: Path) -> ReportGenerationResult`**
- **Function**: Generate time offset analysis report for DVR discrepancies
- **Parameters**:
  - `form_data`: Case data including time offset information
  - `output_path`: Output directory for PDF file
- **Returns**: `ReportGenerationResult` with file path and metadata
- **Content**: Time offset calculations, DVR vs real-time comparisons
- **Format**: Professional PDF with headers, tables, and analysis

**`generate_technician_log(form_data: FormData, output_path: Path) -> ReportGenerationResult`**
- **Function**: Generate technician processing log with file inventory
- **Parameters**:
  - `form_data`: Complete case information
  - `output_path`: Output directory for PDF file
- **Returns**: `ReportGenerationResult` with generation details
- **Content**: Technician info, processing steps, file inventory, timestamps
- **Compliance**: Meets law enforcement documentation requirements

**`generate_hash_csv(file_results: Dict[str, Any], output_path: Path) -> ReportGenerationResult`**
- **Function**: Generate CSV file with hash verification data
- **Parameters**:
  - `file_results`: Dictionary with file paths and hash values
  - `output_path`: Output directory for CSV file
- **Returns**: `ReportGenerationResult` with file details
- **Format**: CSV with columns: filename, size, sha256_hash, verification_status
- **Integrity**: Provides forensic chain of custody documentation

##### ReportGenerationResult Structure

```python
@dataclass
class ReportGenerationResult(Result[Dict[str, Any]]):
    """Specialized result for report generation"""
    output_path: Optional[Path] = None
    report_type: str = ""
    page_count: int = 0
    file_size: int = 0
    generation_time: float = 0.0
```

---

#### IArchiveService Interface

**Purpose**: ZIP archive creation for evidence packaging
**Implementation**: `ArchiveService` (core/services/archive_service.py)

##### Archive Operations

**`create_archives(source_path: Path, output_path: Path, form_data: FormData = None) -> Result[List[Path]]`**
- **Function**: Create multi-level ZIP archives from folder structure
- **Parameters**:
  - `source_path`: Source folder to archive
  - `output_path`: Base output directory
  - `form_data`: Optional case data for naming
- **Returns**: `Result[List[Path]]` with created archive paths
- **Multi-Level Strategy**: Creates archives at occurrence, location, and datetime levels
- **Compression**: Configurable compression levels and methods

**`should_create_archives() -> bool`**
- **Function**: Check if archives should be created based on user settings
- **Returns**: Boolean indicating archive creation preference
- **Settings Integration**: Reads from user preferences and configuration

---

#### IValidationService Interface

**Purpose**: Form data and input validation
**Implementation**: `ValidationService` (core/services/validation_service.py)

##### Validation Methods

**`validate_form_data(form_data: FormData) -> ValidationResult`**
- **Function**: Comprehensive validation of form data
- **Parameters**: `form_data`: FormData instance to validate
- **Returns**: `ValidationResult` with field-specific error details
- **Validation Rules**: Required fields, format validation, business logic constraints

**`validate_file_paths(paths: List[Path]) -> Result[List[Path]]`**
- **Function**: Validate file paths for existence and accessibility
- **Parameters**: `paths`: List of file/folder paths to validate
- **Returns**: `Result[List[Path]]` with valid paths or validation errors
- **Checks**: File existence, read permissions, path security

##### ValidationResult Structure

```python
@dataclass
class ValidationResult(Result[Dict[str, Any]]):
    """Specialized result for validation operations"""
    field_errors: Dict[str, List[str]] = field(default_factory=dict)
    
    def has_errors(self) -> bool:
        """Check if any validation errors exist"""
        return bool(self.field_errors)
    
    def add_field_error(self, field: str, error: str):
        """Add field-specific validation error"""
        if field not in self.field_errors:
            self.field_errors[field] = []
        self.field_errors[field].append(error)
```

---

#### ISuccessMessageService Interface

**Purpose**: Success message construction for user feedback
**Implementation**: `SuccessMessageBuilder` (core/services/success_message_builder.py)

##### Message Building Methods

**`build_forensic_success_message(file_result: FileOperationResult, report_results: Optional[Dict[str, ReportGenerationResult]] = None, zip_result: Optional[ArchiveOperationResult] = None) -> SuccessMessageData`**
- **Function**: Build comprehensive success message for forensic operations
- **Parameters**:
  - `file_result`: File operation results with metrics
  - `report_results`: Optional report generation results
  - `zip_result`: Optional archive creation results
- **Returns**: `SuccessMessageData` with formatted message content
- **Content**: Performance metrics, file counts, operation summaries

**`build_queue_save_success_message(queue_data: QueueOperationData) -> SuccessMessageData`**
- **Function**: Build success message for batch queue save operations
- **Parameters**: `queue_data`: Queue operation metadata
- **Returns**: `SuccessMessageData` with queue-specific content

**`build_batch_success_message(batch_data: Any) -> SuccessMessageData`**
- **Function**: Build success message for batch processing completion
- **Parameters**: `batch_data`: Batch operation results and statistics
- **Returns**: `SuccessMessageData` with batch-specific metrics

---

### Service Configuration System

#### Service Registration Order

The `configure_services()` function handles service registration with proper dependency resolution:

```python
def configure_services(zip_controller=None):
    """Configure and register all application services"""
    # 1. Core business logic services (no dependencies)
    register_service(IPathService, PathService())
    register_service(IFileOperationService, FileOperationService())
    register_service(IReportService, ReportService())
    register_service(IValidationService, ValidationService())
    
    # 2. Services with dependencies
    register_service(IArchiveService, ArchiveService(zip_controller))  # Requires ZipController
    
    # 3. UI/presentation services
    register_service(ISuccessMessageService, SuccessMessageBuilder())
```

#### Plugin Service Extension

Plugins extend the service configuration by registering additional services:

```python
# Plugin service registration example
def configure_plugin_services():
    """Register plugin-specific services"""
    register_service(IHashingService, HashingService())
    register_service(IBatchService, BatchService())
    register_service(ITemplateService, TemplateService())
    
    # Register plugin factories for expensive services
    register_factory(IPluginWorkerService, lambda: PluginWorkerService(get_service(IFileOperationService)))
```

#### Service Verification

The system provides debugging and verification tools:

```python
def verify_service_configuration():
    """Verify all services are properly configured"""
    services_to_check = [
        IPathService, IFileOperationService, IReportService,
        IArchiveService, IValidationService, ISuccessMessageService
    ]
    
    for service_interface in services_to_check:
        try:
            service = get_service(service_interface)
            print(f"✓ {service_interface.__name__}: {service.__class__.__name__}")
        except Exception as e:
            print(f"✗ {service_interface.__name__}: {e}")
```

---

### BaseService Foundation

All service implementations inherit from `BaseService`, providing consistent patterns:

```python
class BaseService(IService, ABC):
    """Base class for all services with common functionality"""
    
    def __init__(self, logger_name: Optional[str] = None):
        self.logger = logging.getLogger(logger_name or self.__class__.__name__)
        
    def _handle_error(self, error: FSAError, context: Optional[Dict[str, Any]] = None):
        """Handle error with consistent logging and reporting"""
        # Adds service context information
        # Routes to centralized error handler
        
    def _log_operation(self, operation: str, details: str = "", level: str = "info"):
        """Log service operation with consistent format"""
        # Standardized logging format
        # Service identification
        # Operation tracking
```

**Plugin Service Implementation Pattern**:
```python
class MyPluginService(BaseService, IMyPluginService):
    """Example plugin service implementation"""
    
    def __init__(self):
        super().__init__("MyPluginService")
        # Plugin-specific initialization
    
    def my_operation(self, data: Any) -> Result[Any]:
        try:
            self._log_operation("my_operation", f"processing {data}")
            # Implementation logic
            result = process_data(data)
            self._log_operation("my_operation_completed", f"result: {result}")
            return Result.success(result)
        except Exception as e:
            error = FSAError(f"Operation failed: {e}")
            self._handle_error(error, {'method': 'my_operation', 'data': str(data)})
            return Result.error(error)
```

---

### Thread Safety and Concurrency

#### Service Registry Thread Safety
- Uses `threading.RLock()` for concurrent access protection
- All registration and retrieval operations are atomic
- Safe for multi-threaded plugin environments

#### Service Implementation Guidelines
- Services should be stateless where possible
- Use instance variables carefully in multi-threaded contexts
- Leverage BaseService logging for thread identification
- Return Result objects rather than raising exceptions

#### Plugin Threading Considerations
```python
# Thread-safe service access in plugin workers
class MyPluginWorker(BaseWorkerThread):
    def run(self):
        # Safe to access services from worker threads
        path_service = get_service(IPathService)
        file_service = get_service(IFileOperationService)
        
        # Service operations are thread-safe
        result = file_service.copy_files(self.files, self.destination)
        self.result_ready.emit(result)
```

This comprehensive service layer API provides the complete foundation for plugin development, ensuring consistent patterns, robust error handling, and clear separation of concerns throughout the application architecture.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content": "Complete Document 1: Core Architecture Extraction", "status": "completed", "activeForm": "Completing Document 1: Core Architecture Extraction"}, {"content": "Create Document 2: Service Layer API Reference", "status": "completed", "activeForm": "Creating Document 2: Service Layer API Reference"}, {"content": "Build memory graph of service interfaces and implementations", "status": "completed", "activeForm": "Building memory graph of service interfaces and implementations"}, {"content": "Document all service methods and signatures comprehensively", "status": "completed", "activeForm": "Documenting all service methods and signatures comprehensively"}]