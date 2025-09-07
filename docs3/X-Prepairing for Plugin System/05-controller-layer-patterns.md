# Document 5: Controller Layer Patterns

## Natural Language Technical Overview

### Understanding the Controller Orchestration Layer

The controller layer in the Folder Structure Utility serves as the **orchestration engine** that coordinates services to accomplish complete workflows. Think of controllers as "conductors" that know which services to call, in what order, and how to handle the results. This is critically important for plugin architecture because plugins will need to follow these same orchestration patterns.

**The Service Coordination Challenge**: Services handle individual responsibilities (path building, file operations, report generation), but complex operations like "process forensic workflow" require multiple services working together in a specific sequence. Controllers solve this coordination problem without duplicating business logic.

**Dependency Injection in Action**: Controllers demonstrate the practical application of the service registry system. Instead of creating service instances directly, controllers request them through interfaces (`IPathService`, `IFileOperationService`) using lazy loading patterns. This creates loose coupling that plugins can leverage.

**Unified Error Handling**: Controllers show how errors from multiple services are consistently handled and routed through the centralized error handler. They also demonstrate context building - adding controller-specific information to errors before routing them.

**Result Aggregation Patterns**: Complex workflows like forensic processing involve multiple Result objects (file operations, report generation, archive creation). Controllers show how to store, combine, and present these results as cohesive success messages.

**Thread Management**: Controllers demonstrate the proper patterns for creating and managing worker threads. They show how to bridge the gap between UI requirements and background processing without tight coupling.

### Plugin Integration Implications

**Service Access Patterns**: Plugins will use the same lazy-loading service access patterns that controllers demonstrate. This ensures plugins get services through dependency injection rather than direct instantiation.

**Workflow Orchestration**: Plugin controllers will follow the same patterns - validate inputs, coordinate multiple services, manage results, handle errors consistently, and create appropriate worker threads.

**State Management**: Controllers show how to maintain operation state (current workers, result storage) without complex state machines. Plugins can follow these same simple patterns.

**Backward Compatibility**: Controllers demonstrate how to provide legacy compatibility methods while moving to new Result-based patterns, which will be important as plugins replace existing tabs.

---

## Senior Developer Technical Specification

### BaseController Foundation

The `BaseController` class provides the foundational patterns that all controllers (including future plugin controllers) inherit.

#### Core Architecture

```python
class BaseController(ABC):
    """Base class for all controllers with service injection"""
    
    def __init__(self, logger_name: Optional[str] = None):
        self.logger = logging.getLogger(logger_name or self.__class__.__name__)
```

#### Service Injection Pattern

**`_get_service(service_interface) -> Service`**
- **Purpose**: Uniform service access through dependency injection
- **Thread Safety**: Safe to call from any thread
- **Error Handling**: Raises ValueError with clear message if service not registered
- **Plugin Usage**: Plugins use identical pattern for service access

```python
def _get_service(self, service_interface):
    """Get service instance through dependency injection"""
    try:
        return get_service(service_interface)
    except ValueError as e:
        self.logger.error(f"Service {service_interface.__name__} not available: {e}")
        raise
```

**Plugin Implementation Pattern**:
```python
class MyPluginController(BaseController):
    def __init__(self):
        super().__init__("MyPluginController")
        self._path_service = None
        
    @property
    def path_service(self) -> IPathService:
        """Lazy load path service"""
        if self._path_service is None:
            self._path_service = self._get_service(IPathService)
        return self._path_service
```

#### Error Handling Integration

**`_handle_error(error: FSAError, context: dict) -> None`**
- **Purpose**: Consistent error routing with controller context
- **Context Enhancement**: Automatically adds controller class and layer information
- **Thread Safety**: Routes through centralized error handler with thread-safe signals

```python
def _handle_error(self, error: FSAError, context: Optional[Dict[str, Any]] = None):
    """Handle controller error with consistent logging"""
    if context is None:
        context = {}
    
    context.update({
        'controller': self.__class__.__name__,
        'layer': 'controller'
    })
    
    handle_error(error, context)
```

**Plugin Error Context Pattern**:
```python
# In plugin controller method
try:
    result = self.risky_operation()
except Exception as e:
    error = FSAError(f"Plugin operation failed: {e}")
    self._handle_error(error, {
        'method': 'risky_operation',
        'plugin_id': self.plugin_id,
        'operation_type': 'file_processing'
    })
    return Result.error(error)
```

#### Structured Logging

**`_log_operation(operation: str, details: str, level: str) -> None`**
- **Purpose**: Consistent operation logging across all controllers
- **Format**: `[ControllerName] operation - details`
- **Level Support**: debug, info, warning, error

```python
def _log_operation(self, operation: str, details: str = "", level: str = "info"):
    """Log controller operation with consistent format"""
    message = f"[{self.__class__.__name__}] {operation}"
    if details:
        message += f" - {details}"
        
    if level == "debug":
        self.logger.debug(message)
    elif level == "warning":
        self.logger.warning(message)
    elif level == "error":
        self.logger.error(message)
    else:
        self.logger.info(message)
```

---

### WorkflowController - The Master Orchestrator

The `WorkflowController` demonstrates the most complex orchestration patterns that plugins will need to understand.

#### Service Composition Architecture

**Lazy Loading Property Pattern**:
```python
@property
def path_service(self) -> IPathService:
    """Lazy load path service"""
    if self._path_service is None:
        self._path_service = self._get_service(IPathService)
    return self._path_service

@property
def file_service(self) -> IFileOperationService:
    """Lazy load file operation service"""
    if self._file_service is None:
        self._file_service = self._get_service(IFileOperationService)
    return self._file_service
```

**Plugin Benefits**:
- Services loaded only when needed
- Service failures isolated to specific operations
- Easy testing with mock services
- Consistent interface access patterns

#### Unified Workflow System

**`process_forensic_workflow()` Method Pattern**:
```python
def process_forensic_workflow(
    self,
    form_data: FormData,
    files: List[Path],
    folders: List[Path],
    output_directory: Path,
    calculate_hash: bool = True,
    performance_monitor = None
) -> Result[FolderStructureThread]:
```

**Key Orchestration Steps**:

1. **Input Validation**:
```python
# Step 1: Validate form data
validation_result = self.validation_service.validate_form_data(form_data)
if not validation_result.success:
    return Result.error(validation_result.error)

# Step 2: Validate file paths
path_validation_result = self.validation_service.validate_file_paths(all_paths)
if not path_validation_result.success:
    return Result.error(path_validation_result.error)
```

2. **Service Coordination**:
```python
# Step 3: Build forensic structure
path_result = self.path_service.build_forensic_path(form_data, output_directory)
if not path_result.success:
    return Result.error(path_result.error)
```

3. **Worker Thread Creation**:
```python
# Step 5: Create worker thread
thread = FolderStructureThread(
    all_items, 
    forensic_path, 
    calculate_hash, 
    performance_monitor
)
```

**Plugin Orchestration Pattern**:
```python
class MyPluginController(BaseController):
    def process_plugin_workflow(self, plugin_data: Any) -> Result[BaseWorkerThread]:
        try:
            self._log_operation("process_plugin_workflow", f"data: {plugin_data}")
            
            # Step 1: Validate input
            validation = self.validation_service.validate_plugin_data(plugin_data)
            if not validation.success:
                return Result.error(validation.error)
            
            # Step 2: Process with services
            processed_data = self.plugin_service.process_data(validation.value)
            if not processed_data.success:
                return Result.error(processed_data.error)
            
            # Step 3: Create worker
            worker = MyPluginWorker(processed_data.value)
            self.current_operation = worker
            
            return Result.success(worker)
            
        except Exception as e:
            error = FSAError(f"Plugin workflow failed: {e}")
            self._handle_error(error, {'method': 'process_plugin_workflow'})
            return Result.error(error)
```

#### Result Storage and Success Message Integration

**Result Storage Pattern**:
```python
def store_operation_results(
    self,
    file_result: Optional[FileOperationResult] = None,
    report_results: Optional[Dict] = None,
    zip_result: Optional[ArchiveOperationResult] = None
):
    """Store operation results for success message building"""
    if file_result is not None:
        self._last_file_result = file_result
    if report_results is not None:
        self._last_report_results = report_results
    if zip_result is not None:
        self._last_zip_result = zip_result
```

**Success Message Building**:
```python
def build_success_message(
    self,
    file_result: Optional[FileOperationResult] = None,
    report_results: Optional[Dict] = None,
    zip_result: Optional[ArchiveOperationResult] = None
) -> SuccessMessageData:
    """Build success message using service layer"""
    # Use provided results or fall back to stored results
    file_result = file_result or self._last_file_result
    report_results = report_results or self._last_report_results
    zip_result = zip_result or self._last_zip_result
    
    return self.success_message_service.build_forensic_success_message(
        file_result, report_results, zip_result
    )
```

**Plugin Success Pattern**:
```python
class MyPluginController(BaseController):
    def __init__(self):
        super().__init__()
        self._last_plugin_result = None
    
    def handle_plugin_completion(self, result: PluginOperationResult):
        """Handle plugin operation completion"""
        self._last_plugin_result = result
        
        # Build success message
        success_data = self.success_message_service.build_plugin_success_message(result)
        
        # Emit to UI
        self.success_message_ready.emit(success_data)
```

#### Batch Processing Architecture

**Unified System Insight**:
```python
def process_batch_workflow(
    self,
    batch_jobs: List['BatchJob'],
    base_output_directory: Path,
    calculate_hash: bool = True
) -> Result[List[Dict]]:
    """Process batch workflow - unified system for both forensic and batch"""
    
    for job in batch_jobs:
        # Each batch job uses the same forensic workflow
        job_result = self.process_forensic_workflow(
            form_data=job.form_data,
            files=job.files,
            folders=job.folders,
            output_directory=base_output_directory,
            calculate_hash=calculate_hash
        )
```

**Key Plugin Insight**: The batch system demonstrates that different processing modes can share the same underlying workflow. Plugins can implement multiple "modes" that all use the same core processing logic.

---

### ReportController - Service Aggregation Patterns

The `ReportController` demonstrates how to coordinate multiple related services and handle partial failures gracefully.

#### Multi-Service Orchestration

**`generate_all_reports()` Method Pattern**:
```python
def generate_all_reports(
    self,
    form_data: FormData,
    file_results: Dict[str, Dict[str, str]],
    output_dir: Path,
    generate_time_offset: bool = True,
    generate_upload_log: bool = True,
    generate_hash_csv: bool = True
) -> Dict[str, ReportGenerationResult]:
```

**Key Patterns**:

1. **Independent Service Calls**:
```python
# Time offset report
if generate_time_offset and self._should_generate_time_offset_report(form_data):
    time_report_path = output_dir / "Time_Offset_Report.pdf"
    result = self.report_service.generate_time_offset_report(form_data, time_report_path)
    generated_reports['time_offset'] = result
```

2. **Partial Failure Handling**:
```python
if result.success:
    self._log_operation("time_offset_report_generated", str(time_report_path))
else:
    self._log_operation("time_offset_report_failed", str(result.error), "warning")
```

3. **Result Aggregation**:
```python
# Returns Dict[str, ReportGenerationResult] with all attempted operations
return generated_reports
```

**Plugin Multi-Service Pattern**:
```python
class MyPluginController(BaseController):
    def process_multi_step_operation(self, data: Any) -> Dict[str, Result]:
        """Process multiple independent operations"""
        results = {}
        
        # Step 1: Data processing (continue even if this fails)
        try:
            process_result = self.data_service.process(data)
            results['processing'] = process_result
        except Exception as e:
            results['processing'] = Result.error(FSAError(f"Processing failed: {e}"))
        
        # Step 2: Report generation (independent of step 1)
        try:
            report_result = self.report_service.generate_plugin_report(data)
            results['reporting'] = report_result
        except Exception as e:
            results['reporting'] = Result.error(FSAError(f"Reporting failed: {e}"))
        
        return results
```

#### Archive Integration Patterns

**Service Composition**:
```python
def create_workflow_archives(
    self,
    base_path: Path,
    output_directory: Path,
    form_data: FormData = None
) -> Result[List[Path]]:
    """Create archives as part of complete workflow"""
    try:
        self._log_operation("create_workflow_archives", f"base: {base_path}")
        return self.archive_service.create_archives(base_path, output_directory, form_data)
        
    except Exception as e:
        error = ReportGenerationError(f"Archive creation workflow failed: {e}")
        self._handle_error(error, {'method': 'create_workflow_archives'})
        return Result.error(error)
```

**Backward Compatibility Pattern**:
```python
def create_zip_archives(self, base_path: Path, output_directory: Path, progress_callback=None) -> List[Path]:
    """Legacy method for backward compatibility"""
    try:
        result = self.create_workflow_archives(base_path, output_directory)
        if result.success:
            return result.value or []
        else:
            self._log_operation("legacy_zip_creation_failed", str(result.error), "error")
            return []
    except Exception as e:
        self._log_operation("legacy_zip_creation_error", str(e), "error")
        return []
```

---

### HashController - Enhanced Validation and Lifecycle Management

The `HashController` demonstrates advanced validation patterns and operation lifecycle management that plugins will need.

#### Enhanced Validation Patterns

**Pre-Operation Validation**:
```python
def start_single_hash_workflow(
    self,
    paths: List[Path],
    algorithm: str = None
) -> Result[SingleHashWorker]:
    """Start a single hash workflow with enhanced validation and error handling"""
    
    # Check if another operation is running
    if self.current_operation and self.current_operation.isRunning():
        error = FileOperationError(
            "Another hash operation is already running",
            user_message="Please wait for the current hash operation to complete."
        )
        self._handle_error(error, {'method': 'start_single_hash_workflow'})
        return Result.error(error)
    
    # Validate algorithm
    if algorithm is None:
        algorithm = settings.hash_algorithm
        
    if algorithm.lower() not in ['sha256', 'md5']:
        error = ValidationError(
            {"algorithm": f"Unsupported algorithm: {algorithm}"},
            user_message=f"Hash algorithm '{algorithm}' is not supported."
        )
        self._handle_error(error, {'method': 'start_single_hash_workflow'})
        return Result.error(error)
```

**Service Integration Validation**:
```python
# Use validation service for consistent path validation
path_validation_result = self.validation_service.validate_file_paths(paths)
if not path_validation_result.success:
    return Result.error(path_validation_result.error)

valid_paths = path_validation_result.value
```

#### Operation Lifecycle Management

**Thread Management Pattern**:
```python
def cancel_current_operation(self):
    """Cancel the current operation with proper cleanup and logging"""
    if self.current_operation and self.current_operation.isRunning():
        self._log_operation("cancel_hash_operation", 
                          f"{self.current_operation.__class__.__name__}")
        self.current_operation.cancel()
        self.current_operation.wait(timeout=5000)  # Wait up to 5 seconds for cancellation
        self._log_operation("hash_operation_cancelled")
    else:
        self._log_operation("no_operation_to_cancel", level="debug")
```

**Status Reporting**:
```python
def get_current_operation_status(self) -> Dict[str, Any]:
    """Get detailed status of current operation"""
    if not self.current_operation:
        return {"status": "idle", "operation": None, "can_cancel": False}
    
    return {
        "status": "running" if self.current_operation.isRunning() else "completed",
        "operation": self.current_operation.__class__.__name__,
        "can_cancel": self.current_operation.isRunning()
    }
```

#### Backward Compatibility Patterns

**Legacy Method Wrappers**:
```python
def start_single_hash_operation(
    self,
    paths: List[Path],
    algorithm: str = None
) -> SingleHashWorker:
    """Legacy method - calls new workflow method and extracts result
    
    DEPRECATED: Use start_single_hash_workflow() for better error handling
    """
    result = self.start_single_hash_workflow(paths, algorithm)
    if result.success:
        return result.value
    else:
        # Convert back to exception for backward compatibility
        if isinstance(result.error, ValidationError):
            raise ValueError(result.error.user_message)
        else:
            raise RuntimeError(result.error.user_message)
```

**Plugin Migration Pattern**: Plugins can provide both new Result-based methods and legacy compatibility methods during transition periods.

---

### ZipController - Session State Management

The `ZipController` demonstrates sophisticated state management patterns that plugins may need for persistent settings and session overrides.

#### Hierarchical State Management

**Priority-Based Decision Making**:
```python
def should_create_zip(self) -> bool:
    """Determine if ZIP should be created based on settings and session state
    
    Priority order: current operation > batch operation > session override > settings
    """
    
    # Check current operation choice first (single-use, then cleared)
    if self.current_operation_choice is not None:
        choice = self.current_operation_choice
        self.current_operation_choice = None  # Clear after use
        return choice == 'enabled'
        
    # Check batch operation choice (persistent for current batch)
    if self.batch_operation_choice is not None:
        return self.batch_operation_choice == 'enabled'
        
    # Check session override (persistent for session)
    if self.session_override is not None:
        return self.session_override == 'enabled'
    
    # Finally check settings
    zip_enabled = self.settings.zip_enabled
    if zip_enabled == 'prompt':
        raise ValueError("Must resolve prompt before checking ZIP creation")
    return zip_enabled == 'enabled'
```

#### Settings Integration Patterns

**Settings Object Building**:
```python
def get_archive_settings(self) -> ZipSettings:
    """Build archive settings object from current preferences"""
    settings = ZipSettings()
    
    # Compression level
    settings.compression_level = self.settings.get('ZIP_COMPRESSION_LEVEL', zipfile.ZIP_STORED)
    
    # Archive method from settings
    archive_method_str = self.settings.archive_method
    if archive_method_str == 'native_7zip':
        settings.archive_method = ArchiveMethod.NATIVE_7ZIP
    elif archive_method_str == 'buffered_python':
        settings.archive_method = ArchiveMethod.BUFFERED_PYTHON
    else:  # 'auto'
        settings.archive_method = ArchiveMethod.AUTO
    
    return settings
```

#### Thread Factory Patterns

**Worker Thread Creation**:
```python
def create_zip_thread(self, occurrence_folder: Path, output_dir: Path, form_data=None) -> ZipOperationThread:
    """Factory method for creating ZIP operation threads"""
    settings = self.get_zip_settings()
    settings.output_path = output_dir
    
    return ZipOperationThread(occurrence_folder, output_dir, settings, form_data)
```

---

### Controller Dependencies Map

#### Service Dependencies by Controller

**WorkflowController**:
- `IPathService` → path building and validation
- `IFileOperationService` → file/folder operations
- `IValidationService` → input validation
- `ISuccessMessageService` → success message construction

**ReportController**:
- `IReportService` → PDF generation
- `IArchiveService` → ZIP creation
- `ZipController` → legacy compatibility (injected dependency)

**HashController**:
- `IValidationService` → path and algorithm validation
- Internal hash workers → SingleHashWorker, VerificationWorker

**ZipController**:
- `SettingsManager` → configuration access
- Direct ZIP utilities → ZipSettings, ArchiveMethod enums

#### Plugin Controller Patterns

**Standard Plugin Controller Dependencies**:
```python
class PluginController(BaseController):
    def __init__(self, plugin_id: str):
        super().__init__(f"{plugin_id}Controller")
        self.plugin_id = plugin_id
        
        # Lazy-loaded services
        self._validation_service = None
        self._file_service = None
        self._plugin_service = None  # Plugin-specific service
        
    @property
    def validation_service(self) -> IValidationService:
        if self._validation_service is None:
            self._validation_service = self._get_service(IValidationService)
        return self._validation_service
```

#### Controller Communication Patterns

**Result Passing**:
- WorkflowController creates workers → results stored for ReportController
- ReportController uses WorkflowController results → generates reports
- Success message building uses aggregated results from multiple controllers

**State Coordination**:
- Controllers maintain independent state
- Results passed explicitly between controllers
- No shared mutable state between controllers

---

### Plugin Integration Patterns

#### Controller Factory Pattern for Plugins

```python
class PluginControllerFactory:
    """Factory for creating plugin controllers"""
    
    @staticmethod
    def create_forensic_controller() -> ForensicPluginController:
        """Create controller for forensic plugin"""
        controller = ForensicPluginController()
        # Register plugin-specific services
        register_service(IForensicService, ForensicService())
        return controller
    
    @staticmethod
    def create_hash_controller() -> HashPluginController:
        """Create controller for hashing plugin"""
        controller = HashPluginController()
        register_service(IHashingService, HashingService())
        return controller
```

#### Plugin Controller Base Class

```python
class PluginControllerBase(BaseController):
    """Base class for plugin controllers"""
    
    def __init__(self, plugin_id: str, plugin_name: str):
        super().__init__(f"{plugin_id}Controller")
        self.plugin_id = plugin_id
        self.plugin_name = plugin_name
        self.current_operation: Optional[BaseWorkerThread] = None
        
    @abstractmethod
    def process_plugin_workflow(self, data: Any) -> Result[BaseWorkerThread]:
        """Process plugin-specific workflow"""
        pass
    
    @abstractmethod
    def get_plugin_status(self) -> Dict[str, Any]:
        """Get plugin operation status"""
        pass
    
    def cancel_plugin_operation(self) -> bool:
        """Cancel current plugin operation"""
        if self.current_operation and self.current_operation.isRunning():
            self._log_operation("cancel_plugin_operation", self.plugin_name)
            self.current_operation.cancel()
            return True
        return False
```

---

### Controller Pattern Summary for Plugins

#### Essential Patterns Plugins Must Follow

1. **Service Injection**: Use lazy-loaded properties with `_get_service()`
2. **Error Handling**: Use `_handle_error()` with plugin context information
3. **Structured Logging**: Use `_log_operation()` for consistent logging
4. **Result-Based Methods**: Return Result objects, not exceptions
5. **Worker Management**: Store current operation reference for cancellation
6. **Status Reporting**: Provide operation status for UI updates

#### Service Coordination Patterns

1. **Input Validation First**: Always validate inputs before service calls
2. **Service Call Chaining**: Chain service calls with Result object error propagation
3. **Result Storage**: Store operation results for success message building
4. **Cleanup**: Clear stored results and operation references after completion

#### Thread Integration Patterns

1. **Worker Factory Methods**: Create configured worker threads
2. **Thread Reference Storage**: Store worker reference for lifecycle management
3. **Cancellation Support**: Implement proper cancellation with cleanup
4. **Status Reporting**: Provide real-time operation status

This controller layer documentation provides the complete foundation that plugins need to understand service orchestration, error handling, result aggregation, and thread management patterns. Plugins that follow these established patterns will integrate seamlessly with the existing architecture.