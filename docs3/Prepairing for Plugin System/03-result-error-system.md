# Document 3: Result Objects & Error System Specification

## Natural Language Technical Overview

### Understanding the Result-Based Communication System

The Folder Structure Utility has implemented a sophisticated communication protocol that fundamentally changes how operations report success, failure, and complex states. Instead of using traditional boolean returns or exception throwing, every operation in the system returns a "Result object" that carries rich information about what happened.

**The Problem with Traditional Error Handling**: In typical applications, functions either return `True`/`False` or throw exceptions when things go wrong. This creates several problems: you lose context about what partially succeeded, you can't easily pass warnings along with success, and exceptions can crash threads or interrupt processing chains unexpectedly.

**The Result Object Solution**: The application uses a generic `Result[T]` class that acts like a "smart envelope" for operation outcomes. Every Result object contains:
- A success indicator (did it work?)
- The actual return value (if successful)
- A rich error object (if failed)
- A list of warnings (non-fatal issues)
- A metadata dictionary (extra context information)

This means a file copy operation can return not just "it worked" but "it worked, processed 150 files, took 2.3 seconds, averaged 45 MB/s, but had 3 warnings about file permissions, and here's the hash of each file copied."

**Thread-Safe Error Communication**: The error handling system is designed around Qt's signal/slot architecture, which means errors that happen in background threads are automatically and safely routed to the main UI thread for display. This prevents the common Qt problem where worker thread errors crash the application or get lost.

**Specialized Result Types**: Different operations return specialized Result objects tailored to their needs. File operations return `FileOperationResult` with performance metrics, validation returns `ValidationResult` with field-specific errors, and report generation returns `ReportGenerationResult` with output paths and statistics.

### Plugin Integration Benefits

**Standardized Communication**: All plugins communicate with the core and with each other using the same Result object protocols. This means a plugin can call a core service and immediately understand the response format, or chain multiple operations together cleanly.

**Rich Error Context**: When plugin operations fail, they can provide both technical details for logging and user-friendly messages for display, along with specific context about what went wrong and whether the operation can be retried.

**Functional Programming Patterns**: Result objects support chaining operations with `.map()` and `.and_then()` methods, allowing plugins to build complex processing pipelines that automatically handle error propagation.

**Thread Safety**: The error handling system ensures that plugin operations running in background threads can safely report errors and status updates to the main UI without thread synchronization issues.

---

## Senior Developer Technical Specification

### Result[T] Base Class Architecture

The `Result[T]` class is the foundation of the entire plugin communication system, providing type-safe operation results with comprehensive context.

#### Core Structure

```python
@dataclass
class Result(Generic[T]):
    """Universal result object that replaces boolean returns"""
    success: bool
    value: Optional[T] = None
    error: Optional[FSAError] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

#### Factory Methods

**`Result.success(value: T, warnings: Optional[List[str]] = None, **metadata) -> Result[T]`**
- **Purpose**: Create successful result with optional warnings and metadata
- **Parameters**:
  - `value`: The successful operation result
  - `warnings`: Non-fatal issues that occurred during operation
  - `**metadata`: Additional context information
- **Plugin Usage**: 
  ```python
  # Simple success
  return Result.success(file_path)
  
  # Success with warnings and metadata
  return Result.success(
      processed_files,
      warnings=["3 files skipped due to permissions"],
      operation_time=2.5,
      files_processed=147
  )
  ```

**`Result.error(error: FSAError, warnings: Optional[List[str]] = None) -> Result[T]`**
- **Purpose**: Create error result with context preservation
- **Parameters**:
  - `error`: FSAError instance with detailed error information
  - `warnings`: Warnings that occurred before the error
- **Plugin Usage**:
  ```python
  from core.exceptions import FileOperationError
  
  error = FileOperationError(
      "Cannot access file",
      file_path=str(path),
      user_message="File is locked or in use"
  )
  return Result.error(error)
  ```

**`Result.from_bool(success: bool, value: Optional[T] = None, error_message: str = "Operation failed") -> Result[T]`**
- **Purpose**: Migration helper for converting legacy boolean returns
- **Use Cases**: Wrapping legacy APIs during plugin development
- **Plugin Usage**:
  ```python
  # Converting legacy operation
  legacy_success = some_legacy_function()
  return Result.from_bool(legacy_success, result_data, "Legacy operation failed")
  ```

#### Operation Methods

**`unwrap() -> T`**
- **Purpose**: Extract value or raise error (for situations requiring exceptions)
- **Behavior**: Returns value if successful, raises FSAError if failed
- **Thread Safety**: Safe to use in worker threads
- **Plugin Usage**:
  ```python
  result = file_service.copy_files(files, destination)
  try:
      copied_files = result.unwrap()  # Will raise if operation failed
  except FSAError as e:
      handle_error(e)
  ```

**`unwrap_or(default: T) -> T`**
- **Purpose**: Extract value or return default (safe extraction)
- **Plugin Usage**:
  ```python
  file_count = result.unwrap_or(0)  # Default to 0 if operation failed
  ```

**`unwrap_or_else(func) -> T`**
- **Purpose**: Extract value or compute default from error context
- **Plugin Usage**:
  ```python
  processed_files = result.unwrap_or_else(
      lambda error: log_error_and_return_empty_list(error)
  )
  ```

#### Functional Programming Support

**`map(func) -> Result`**
- **Purpose**: Transform successful values while preserving errors
- **Error Handling**: Catches exceptions in transformation function and converts to FSAError
- **Plugin Usage**:
  ```python
  result = file_service.copy_files(files, destination)
  file_paths = result.map(lambda files_dict: [f['path'] for f in files_dict.values()])
  ```

**`and_then(func) -> Result`**
- **Purpose**: Chain operations that return Result objects
- **Error Propagation**: Short-circuits on first error
- **Plugin Usage**:
  ```python
  def plugin_workflow(input_data):
      return (validate_input(input_data)
              .and_then(lambda data: process_files(data))
              .and_then(lambda processed: generate_report(processed))
              .and_then(lambda report: create_archive(report)))
  ```

#### Context Methods

**`has_warnings() -> bool`**
- **Purpose**: Check if operation has non-fatal issues
- **Plugin Usage**: Display warning indicators in UI

**`add_warning(warning: str) -> Result[T]`**
- **Purpose**: Add warning to existing result
- **Fluent Interface**: Returns self for chaining
- **Plugin Usage**:
  ```python
  result = Result.success(data)
  if some_minor_issue:
      result.add_warning("Non-critical issue occurred")
  return result
  ```

**`add_metadata(key: str, value: Any) -> Result[T]`**
- **Purpose**: Add contextual information to result
- **Plugin Usage**:
  ```python
  return (Result.success(output_file)
          .add_metadata("processing_time", elapsed_seconds)
          .add_metadata("algorithm_used", "SHA-256"))
  ```

---

### Specialized Result Types

#### FileOperationResult

**Purpose**: File and folder operations with performance metrics
**Base Type**: `Result[Dict[str, Any]]`

```python
@dataclass 
class FileOperationResult(Result[Dict[str, Any]]):
    """File operation results with performance and processing data"""
    files_processed: int = 0
    bytes_processed: int = 0
    duration_seconds: float = 0.0
    average_speed_mbps: float = 0.0
    performance_metrics: Optional[PerformanceMetrics] = None
```

**Factory Method**:
```python
@classmethod
def create(cls, results_dict: Dict[str, Any], files_processed: int = 0, 
           bytes_processed: int = 0, **kwargs) -> FileOperationResult:
    """Create FileOperationResult from operation results"""
    performance_stats = results_dict.get('_performance_stats', {})
    
    return cls(
        success=True,
        value=results_dict,
        files_processed=files_processed,
        bytes_processed=bytes_processed,
        duration_seconds=performance_stats.get('total_time', 0.0),
        average_speed_mbps=performance_stats.get('average_speed_mbps', 0.0),
        performance_metrics=performance_stats.get('metrics'),
        **kwargs
    )
```

**Plugin Integration**:
```python
# Using in plugin service
def my_plugin_copy_operation(self, files: List[Path]) -> FileOperationResult:
    file_service = get_service(IFileOperationService)
    result = file_service.copy_files(files, self.destination)
    
    # Result already includes performance metrics
    if result.success:
        self.log_performance(f"Processed {result.files_processed} files at {result.average_speed_mbps:.2f} MB/s")
    
    return result
```

#### ValidationResult

**Purpose**: Form and data validation with field-specific errors
**Base Type**: `Result[None]`

```python
@dataclass
class ValidationResult(Result[None]):
    """Validation results with field-specific errors"""
    field_errors: Dict[str, str] = field(default_factory=dict)
    
    @property
    def has_errors(self) -> bool:
        """Check if validation has errors"""
        return bool(self.field_errors) or not self.success
```

**Factory Methods**:
```python
@classmethod
def create_valid(cls, warnings: Optional[List[str]] = None) -> ValidationResult:
    """Create a valid validation result"""
    return cls(success=True, warnings=warnings or [])

@classmethod  
def create_invalid(cls, field_errors: Dict[str, str], 
                  warnings: Optional[List[str]] = None) -> ValidationResult:
    """Create an invalid validation result"""
    error = ValidationError(field_errors)
    return cls(
        success=False,
        error=error,
        field_errors=field_errors,
        warnings=warnings or []
    )
```

**Plugin Usage**:
```python
def validate_plugin_config(self, config: Dict[str, Any]) -> ValidationResult:
    """Validate plugin configuration"""
    result = ValidationResult.create_valid()
    
    if not config.get('api_key'):
        result.add_field_error('api_key', 'API key is required')
    
    if not config.get('endpoint', '').startswith('https://'):
        result.add_field_error('endpoint', 'Endpoint must use HTTPS')
    
    return result
```

#### ReportGenerationResult

**Purpose**: PDF and report generation with output metadata
**Base Type**: `Result[Path]`

```python
@dataclass
class ReportGenerationResult(Result[Path]):
    """Report generation results with output information"""
    output_path: Optional[Path] = None
    report_type: Optional[str] = None
    page_count: int = 0
    file_size_bytes: int = 0
```

**Factory Method**:
```python
@classmethod
def create_successful(cls, output_path: Path, report_type: str = None, 
                     **kwargs) -> ReportGenerationResult:
    """Create successful report generation result"""
    file_size = 0
    try:
        if output_path.exists():
            file_size = output_path.stat().st_size
    except:
        pass  # File size is optional information
    
    return cls(
        success=True,
        value=output_path,
        output_path=output_path,
        report_type=report_type,
        file_size_bytes=file_size,
        **kwargs
    )
```

**Plugin Extension Example**:
```python
class MyPluginReportService(BaseService):
    def generate_custom_report(self, data: Any, output_path: Path) -> ReportGenerationResult:
        try:
            # Generate custom report
            pages_created = self._generate_pdf(data, output_path)
            
            return ReportGenerationResult.create_successful(
                output_path,
                report_type="custom_analysis",
                page_count=pages_created
            ).add_metadata("generator", "MyPlugin v1.0")
            
        except Exception as e:
            error = ReportGenerationError(
                f"Custom report generation failed: {e}",
                report_type="custom_analysis"
            )
            return ReportGenerationResult(success=False, error=error)
```

#### BatchOperationResult

**Purpose**: Multi-item operations with success rate tracking
**Base Type**: `Result[List[Dict[str, Any]]]`

```python
@dataclass
class BatchOperationResult(Result[List[Dict[str, Any]]]):
    """Batch operation results with success/failure tracking"""
    total_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    item_results: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if self.total_items == 0:
            return 100.0
        return (self.successful_items / self.total_items) * 100
```

**Plugin Integration**:
```python
def process_batch_items(self, items: List[Any]) -> BatchOperationResult:
    """Process multiple items with detailed results"""
    item_results = []
    
    for item in items:
        try:
            result = self._process_single_item(item)
            item_results.append({
                'item_id': item.id,
                'success': True,
                'result': result
            })
        except Exception as e:
            item_results.append({
                'item_id': item.id,
                'success': False,
                'error': str(e)
            })
    
    return BatchOperationResult.create(item_results)
```

#### HashOperationResult

**Purpose**: Hash calculation and verification operations
**Base Type**: `Result[Dict[str, Dict[str, Any]]]`

```python
@dataclass
class HashOperationResult(Result[Dict[str, Dict[str, Any]]]):
    """Hash operation results with verification information"""
    files_hashed: int = 0
    verification_failures: int = 0
    hash_algorithm: str = "SHA-256"
    processing_time: float = 0.0
```

#### ArchiveOperationResult

**Purpose**: ZIP and archive creation operations
**Base Type**: `Result[List[Path]]`

```python
@dataclass
class ArchiveOperationResult(Result[List[Path]]):
    """Archive operation results with compression information"""
    archives_created: int = 0
    total_compressed_size: int = 0
    original_size: int = 0
    compression_level: int = 0
    processing_time: float = 0.0
    
    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio as percentage"""
        if self.original_size == 0:
            return 0.0
        return (self.total_compressed_size / self.original_size) * 100
```

---

### FSAError Exception Hierarchy

The exception system provides thread-aware, context-rich error information that integrates seamlessly with the Result object system.

#### FSAError Base Class

```python
class FSAError(Exception):
    """Base exception for all Folder Structure Application errors"""
    
    def __init__(self, 
                 message: str,
                 error_code: Optional[str] = None,
                 user_message: Optional[str] = None, 
                 recoverable: bool = False,
                 severity: ErrorSeverity = ErrorSeverity.ERROR,
                 context: Optional[Dict[str, Any]] = None):
```

#### Core Attributes

**`message: str`** - Technical error message for logging and debugging
**`error_code: str`** - Unique identifier for error categorization
**`user_message: str`** - User-friendly message for UI display
**`recoverable: bool`** - Whether operation can be retried
**`severity: ErrorSeverity`** - Error severity level (INFO, WARNING, ERROR, CRITICAL)
**`context: Dict[str, Any]`** - Additional context information
**`timestamp: datetime`** - When error occurred (UTC)
**`thread_id: QThread`** - Qt thread where error occurred
**`thread_name: str`** - Human-readable thread name
**`is_main_thread: bool`** - Whether error occurred in main thread

#### Thread Context Capture

The FSAError automatically captures Qt thread context during initialization:

```python
def __init__(self, ...):
    # ... other initialization ...
    
    # Thread context information
    current_thread = QThread.currentThread()
    self.thread_id = current_thread
    self.thread_name = current_thread.objectName() or current_thread.__class__.__name__
    self.is_main_thread = (current_thread == QThread.currentThread().parent())
```

**Plugin Benefit**: Plugins can safely create errors in worker threads, and the error handler will automatically route them to the main thread for UI display.

#### Specialized Exception Types

**`FileOperationError`** - File operation failures
```python
def __init__(self, message: str, file_path: Optional[str] = None, **kwargs):
    context = kwargs.get('context', {})
    if file_path:
        context['file_path'] = file_path
    kwargs['context'] = context
    super().__init__(message, **kwargs)
```

**`ValidationError`** - Form and data validation errors
```python
def __init__(self, field_errors: Dict[str, str], **kwargs):
    self.field_errors = field_errors
    context = kwargs.get('context', {})
    context['field_errors'] = field_errors
    kwargs['context'] = context
    
    message = f"Validation failed: {len(field_errors)} field(s) have errors"
    super().__init__(message, severity=ErrorSeverity.WARNING, **kwargs)
```

**`ReportGenerationError`** - PDF and report generation failures
```python
def __init__(self, message: str, report_type: Optional[str] = None, 
             output_path: Optional[str] = None, **kwargs):
```

**`BatchProcessingError`** - Batch job processing failures with statistics
```python
def __init__(self, job_id: str, successes: int, failures: int, 
             error_details: Optional[list] = None, **kwargs):
    # Automatic severity determination based on failure rate
    total = successes + failures
    success_rate = (successes / total * 100) if total > 0 else 0
    
    if failures == 0:
        severity = ErrorSeverity.INFO
    elif successes == 0:
        severity = ErrorSeverity.CRITICAL
    elif failures > successes:
        severity = ErrorSeverity.ERROR
    else:
        severity = ErrorSeverity.WARNING
```

**`HashVerificationError`** - Hash calculation and verification errors
```python
def __init__(self, message: str, file_path: Optional[str] = None, 
             expected_hash: Optional[str] = None, actual_hash: Optional[str] = None, **kwargs):
    # Always CRITICAL severity for hash verification failures
    super().__init__(message, severity=ErrorSeverity.CRITICAL, **kwargs)
```

**`ThreadError`** - Thread management and synchronization errors
**`ConfigurationError`** - Configuration and settings errors
**`UIError`** - User interface and interaction errors
**`TemplateValidationError`** - Template validation and import errors

---

### Error Handler System

The `ErrorHandler` class provides thread-safe centralized error handling with Qt signal routing.

#### Core Architecture

```python
class ErrorHandler(QObject):
    """Thread-safe centralized error handling system"""
    
    # Qt signals for thread-safe error reporting
    error_occurred = Signal(FSAError, dict)  # error, context
```

#### Key Features

**Thread-Safe Routing**: Errors from worker threads are automatically routed to main thread via Qt signals:

```python
def handle_error(self, error: FSAError, context: Optional[dict] = None):
    """Handle error from any thread"""
    # Always log immediately (thread-safe)
    self._log_error(error, context)
    
    # Route to main thread for UI updates  
    if not QThread.currentThread().isMainThread():
        # Use queued connection for thread safety
        self.error_occurred.emit(error, context)
    else:
        # Already in main thread - handle directly
        self._handle_error_main_thread(error, context)
```

**UI Callback Registration**: UI components register for error notifications:

```python
def register_ui_callback(self, callback: Callable[[FSAError, dict], None]):
    """Register UI callback for error notifications"""
    self._ui_callbacks.append(callback)

# Plugin UI registration example
error_handler = get_error_handler()
error_handler.register_ui_callback(self.show_error_notification)
```

**Error Statistics and Debugging**:

```python
def get_error_statistics(self) -> Dict[str, int]:
    """Get error count statistics by severity"""

def get_recent_errors(self, count: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get recent errors for debugging"""

def export_error_log(self, output_path: Path) -> bool:
    """Export recent errors to JSON file"""
```

#### Global Error Handling Functions

**Initialization**:
```python
def initialize_error_handling(parent=None) -> ErrorHandler:
    """Initialize global error handling system"""

def get_error_handler() -> ErrorHandler:
    """Get global error handler instance"""

def handle_error(error: FSAError, context: Optional[dict] = None):
    """Convenience function using global handler"""
```

**Plugin Usage Pattern**:
```python
class MyPluginService(BaseService):
    def plugin_operation(self, data: Any) -> Result[Any]:
        try:
            result = self._process_data(data)
            return Result.success(result)
        except Exception as e:
            error = FSAError(
                f"Plugin operation failed: {e}",
                error_code="PLUGIN_001",
                user_message="Data processing failed. Please check your input."
            )
            handle_error(error, {'plugin': self.__class__.__name__, 'data': str(data)})
            return Result.error(error)
```

---

### Result Utility Functions

#### Combining Multiple Results

```python
def combine_results(results: List[Result[T]]) -> Result[List[T]]:
    """Combine multiple results into single result"""
    successful_values = []
    all_warnings = []
    
    for result in results:
        if result.success:
            successful_values.append(result.value)
        else:
            # Return first error encountered
            return Result.error(result.error, all_warnings + result.warnings)
        all_warnings.extend(result.warnings)
    
    return Result.success(successful_values, all_warnings)
```

**Plugin Usage**:
```python
def process_multiple_files(self, files: List[Path]) -> Result[List[Dict]]:
    """Process multiple files and combine results"""
    results = [self._process_single_file(f) for f in files]
    return combine_results(results)
```

#### First Success Pattern

```python
def first_success(results: List[Result[T]]) -> Result[T]:
    """Return first successful result, or last error if all fail"""
```

**Plugin Usage - Fallback Strategies**:
```python
def try_multiple_processors(self, data: Any) -> Result[Any]:
    """Try multiple processing strategies"""
    strategies = [
        lambda: self._fast_processor(data),
        lambda: self._reliable_processor(data),
        lambda: self._fallback_processor(data)
    ]
    
    results = [strategy() for strategy in strategies]
    return first_success(results)
```

---

### Plugin Integration Patterns

#### Service Method Implementation

```python
class MyPluginService(BaseService, IMyPluginService):
    def my_operation(self, input_data: Any) -> Result[OutputType]:
        """Standard plugin operation pattern"""
        try:
            # Input validation
            validation = self._validate_input(input_data)
            if not validation.success:
                return Result.error(validation.error)
            
            # Main operation
            result = self._perform_operation(validation.value)
            
            # Add plugin context to result
            result.add_metadata("plugin", self.__class__.__name__)
            result.add_metadata("version", "1.0.0")
            
            return result
            
        except Exception as e:
            error = FSAError(
                f"Plugin operation failed: {e}",
                error_code=f"{self.__class__.__name__}_ERROR",
                user_message="Plugin operation failed. Please try again."
            )
            handle_error(error, {'method': 'my_operation', 'input': str(input_data)})
            return Result.error(error)
```

#### Worker Thread Error Handling

```python
class MyPluginWorker(BaseWorkerThread):
    def execute(self) -> Result[Any]:
        """Worker thread with Result-based error handling"""
        try:
            # Check for cancellation
            if self.is_cancelled():
                error = FSAError("Operation was cancelled", severity=ErrorSeverity.INFO)
                return Result.error(error)
            
            # Perform work with progress updates
            for i, item in enumerate(self.work_items):
                if self.is_cancelled():
                    break
                
                # Update progress (thread-safe)
                progress = int((i / len(self.work_items)) * 100)
                self.progress_update.emit(progress, f"Processing item {i+1}")
                
                # Process item
                item_result = self._process_item(item)
                if not item_result.success:
                    return item_result  # Propagate error
            
            return Result.success(self.results)
            
        except Exception as e:
            error = ThreadError(
                f"Worker thread failed: {e}",
                thread_name=self.objectName()
            )
            return Result.error(error)
    
    def run(self):
        """Qt thread run method"""
        result = self.execute()
        self.result_ready.emit(result)  # Unified signal emission
```

This comprehensive Result object and error handling system provides the foundation for robust, maintainable plugin architecture with consistent communication patterns, rich error context, and thread-safe operation throughout the application.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content": "Complete Document 1: Core Architecture Extraction", "status": "completed", "activeForm": "Completing Document 1: Core Architecture Extraction"}, {"content": "Complete Document 2: Service Layer API Reference", "status": "completed", "activeForm": "Completing Document 2: Service Layer API Reference"}, {"content": "Create Document 3: Result Objects & Error System Specification", "status": "completed", "activeForm": "Creating Document 3: Result Objects & Error System Specification"}, {"content": "Analyze complete Result objects hierarchy and error handling system", "status": "completed", "activeForm": "Analyzing complete Result objects hierarchy and error handling system"}, {"content": "Document FSAError exception system and thread context handling", "status": "completed", "activeForm": "Documenting FSAError exception system and thread context handling"}]