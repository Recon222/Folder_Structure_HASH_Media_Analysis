# Feature Quality Standards & Architecture Guide

## Purpose
This document defines the quality standards and architectural patterns required for any new feature/tab in the Folder Structure application. It provides a concise, actionable specification without feature-specific details.

---

## Architecture Requirements

### Module Structure
```
feature_name/
├── __init__.py                      # Package initialization
├── controllers/                     # Orchestration layer
│   └── feature_controller.py        # Main controller (thin orchestration)
├── services/                        # Business logic layer
│   ├── core_service.py             # Primary business logic
│   ├── validation_service.py       # Input validation
│   └── supporting_services.py      # Additional services
├── models/                          # Data structures
│   ├── data_models.py              # Dataclasses, type definitions
│   └── interfaces.py               # Service interfaces (Protocol)
├── workers/                         # Background processing
│   └── feature_worker.py           # QThread implementation
└── ui/                              # Presentation layer
    └── feature_tab.py               # Main UI component
```

### Service-Oriented Architecture (SOA)
- **Dependency Injection**: Services injected via constructor, not created internally
- **Interface Segregation**: Define Protocol interfaces for services
- **Single Responsibility**: Each service has ONE clearly defined purpose
- **Testability**: All services mockable through dependency injection

---

## Code Quality Standards

### Type Safety Requirements
```python
# REQUIRED: Full type hints
def process_data(
    input_path: Path,
    options: ProcessingOptions
) -> Result[ProcessedData]:
    ...

# REQUIRED: Result objects for error handling
Result[T] = Union[Success[T], Error]

# FORBIDDEN: Any, dict without TypedDict, untyped returns
```

### Documentation Standards
Every public method MUST have:
```python
def process_file(self, file_path: Path) -> Result[ProcessedData]:
    """
    Process a single file with validation.

    Args:
        file_path: Path to the file to process

    Returns:
        Result containing ProcessedData on success,
        or appropriate error with context

    Raises:
        Never - errors returned via Result objects
    """
```

### Error Handling Pattern
```python
# REQUIRED: Result-based error handling
def operation() -> Result[DataType]:
    try:
        # Validate inputs
        if not self._validate(input_data):
            return Result.error(
                ValidationError(
                    "Technical error message",
                    user_message="User-friendly message"
                )
            )

        # Perform operation
        result = self._process(input_data)
        return Result.success(result)

    except Exception as e:
        return Result.error(
            ProcessingError(
                f"Operation failed: {e}",
                user_message="Unable to complete operation"
            )
        )

# FORBIDDEN: Raising exceptions for control flow
# FORBIDDEN: Boolean returns for operations that can fail
```

---

## Threading Requirements

### Worker Implementation
```python
class FeatureWorker(BaseWorkerThread):
    # REQUIRED: Unified signals
    result_ready = Signal(Result)
    progress_update = Signal(int, str)  # percentage, status

    def __init__(self, services: Dict[str, Any]):
        super().__init__()
        self.services = services
        self._cancelled = False

    def execute(self) -> Result[OutputType]:
        """Main worker logic - NEVER access UI directly."""
        for i, item in enumerate(items):
            # Check cancellation
            if self.check_cancellation():
                return Result.error(CancellationError())

            # Process with progress
            self.progress_update.emit(
                int((i + 1) / total * 100),
                f"Processing {item.name}"
            )

            # Use services for business logic
            result = self.services['processor'].process(item)
            if result.is_error:
                return result

        return Result.success(output)
```

### Thread Safety Rules
- **NO direct UI access** from worker threads
- **NO shared mutable state** between threads
- **Signal marshalling** for all cross-thread communication
- **Cancellation support** with graceful shutdown
- **Resource cleanup** in worker's cleanup() method

---

## UI Integration Pattern

### Tab Implementation
```python
class FeatureTab(QWidget):
    # REQUIRED: Standard signals
    process_requested = Signal()
    log_message = Signal(str, str)  # level, message

    def __init__(self, form_data: FormData):
        super().__init__()
        self.form_data = form_data
        self.controller = None  # Lazy initialization
        self._setup_ui()
        self._connect_signals()

    def _process(self):
        """Handle process button click."""
        # Get controller (lazy init)
        if not self.controller:
            self.controller = self._create_controller()

        # Validate inputs
        validation = self.controller.validate_inputs(...)
        if validation.is_error:
            self._show_error(validation.error)
            return

        # Create and start worker
        self.worker = FeatureWorker(self.controller.get_services())
        self.worker.result_ready.connect(self._on_complete)
        self.worker.progress_update.connect(self._on_progress)
        self.worker.start()
```

---

## Service Layer Standards

### Service Implementation
```python
class FeatureService:
    """Core business logic service."""

    def __init__(self,
                 validator: ValidationService,
                 processor: ProcessingService):
        """Inject dependencies."""
        self.validator = validator
        self.processor = processor

    def process_batch(
        self,
        items: List[Item],
        options: ProcessingOptions,
        progress_callback: Optional[Callable] = None
    ) -> Result[BatchResult]:
        """
        Process multiple items with validation.

        NO UI code, NO Qt dependencies, pure business logic.
        """
        # Validate first
        validation = self.validator.validate_batch(items, options)
        if validation.is_error:
            return validation

        results = []
        for i, item in enumerate(items):
            if progress_callback:
                progress_callback(i, len(items))

            result = self.processor.process_item(item, options)
            results.append(result)

        return Result.success(BatchResult(results))
```

### Service Rules
- **Pure business logic** - no UI, no Qt dependencies
- **Testable in isolation** - all dependencies injected
- **Result objects** for all operations that can fail
- **Progress callbacks** optional, never required
- **Stateless when possible** - avoid mutable service state

---

## Testing Requirements

### Minimum Test Coverage
```python
# REQUIRED: Integration test
def test_end_to_end_workflow():
    """Test complete feature workflow."""
    controller = FeatureController()
    result = controller.process(test_data)
    assert result.is_success
    assert result.value.processed_count == expected

# REQUIRED: Service unit tests
def test_service_validation():
    """Test service validates inputs correctly."""
    service = FeatureService(mock_validator, mock_processor)
    result = service.process(invalid_data)
    assert result.is_error
    assert isinstance(result.error, ValidationError)

# REQUIRED: Error handling tests
def test_worker_handles_errors():
    """Test worker propagates errors correctly."""
    worker = FeatureWorker(failing_service)
    result = worker.execute()
    assert result.is_error
    assert result.error.user_message  # Has user-friendly message
```

### Testing Standards
- **Test real functionality**, not just code coverage
- **Mock external dependencies** (file system, network, etc.)
- **Test error paths** as thoroughly as success paths
- **Verify thread safety** for worker implementations
- **No test manipulation** - fix bugs, don't hack tests

---

## SOLID Principles Checklist

### ✅ Single Responsibility
- Each class/service has ONE reason to change
- Services < 400 lines
- Methods < 50 lines

### ✅ Open/Closed
- Extensible through dependency injection
- New features don't modify existing code
- Use composition over inheritance

### ✅ Liskov Substitution
- Implement defined interfaces completely
- Workers follow BaseWorkerThread contract
- Services honor Protocol definitions

### ✅ Interface Segregation
- Small, focused interfaces
- Clients depend only on methods they use
- No "god interfaces" with 50+ methods

### ✅ Dependency Inversion
- Depend on abstractions (Protocol/ABC)
- Inject concrete implementations
- UI → Controller → Service → Worker flow

---

## Security Requirements

### Input Validation
```python
# REQUIRED: Validate ALL user inputs
if not path.exists():
    return Result.error(ValidationError("File not found"))

# REQUIRED: Resolve paths to absolute
safe_path = Path(user_input).resolve()

# REQUIRED: Validate path is within expected directory
if not safe_path.is_relative_to(base_dir):
    return Result.error(SecurityError("Path traversal detected"))
```

### Command Execution
```python
# REQUIRED: Use argv list for subprocesses
subprocess.run([exe, arg1, arg2], shell=False)

# FORBIDDEN: shell=True with user input
# FORBIDDEN: String concatenation for commands
# FORBIDDEN: Unescaped user input in commands
```

---

## Performance Guidelines

### Optimization Priorities
1. **Correctness first** - optimize only after it works
2. **Measure before optimizing** - profile actual bottlenecks
3. **User-perceivable improvements** - focus on UI responsiveness

### Resource Management
```python
# REQUIRED: Cleanup resources
def cleanup(self):
    """Clean up temporary files and resources."""
    if self.temp_file and self.temp_file.exists():
        self.temp_file.unlink()

    if self.subprocess:
        self.subprocess.terminate()
        self.subprocess.wait(timeout=3)
```

### Progress Reporting
- Update progress at meaningful intervals (not every iteration)
- Include status messages, not just percentages
- Throttle updates to prevent UI flooding (max 10-20/sec)

---

## Integration Checklist

### Before Starting
- [ ] Review existing patterns in codebase
- [ ] Define clear service boundaries
- [ ] Design data models (dataclasses)
- [ ] Plan worker thread implementation

### Implementation
- [ ] Create module structure following template
- [ ] Implement services with dependency injection
- [ ] Add comprehensive type hints
- [ ] Write docstrings for public methods
- [ ] Implement Result-based error handling
- [ ] Create worker for background processing
- [ ] Build UI with proper signal connections

### Testing & Documentation
- [ ] Write integration tests
- [ ] Add service unit tests
- [ ] Test error paths
- [ ] Verify thread safety
- [ ] Document complex algorithms
- [ ] Add usage examples

### Code Review Checklist
- [ ] No god objects (classes > 1000 lines)
- [ ] No magic numbers (use constants)
- [ ] No copy-paste code (DRY)
- [ ] No global state
- [ ] No tight coupling
- [ ] Result objects used consistently
- [ ] Proper error messages (technical + user)
- [ ] Resources cleaned up properly

---

## Quality Metrics

### Target Metrics
- **Code organization**: Clear separation of concerns
- **Type safety**: 100% type hints on public APIs
- **Documentation**: All public methods documented
- **Error handling**: Result objects throughout
- **Thread safety**: Proper Qt signal usage
- **Testability**: > 80% code coverage
- **Maintainability**: < 20 cyclomatic complexity

### Red Flags
- Methods > 100 lines
- Classes > 1000 lines
- Circular dependencies
- Direct UI access from services
- Exception-based control flow
- Untested error paths
- Missing type hints
- No documentation

---

## Quick Reference

### File Template
```python
"""
Module description.
"""
from typing import Optional, List, Dict
from pathlib import Path
from PySide6.QtCore import QThread, Signal

from core.result_types import Result
from .interfaces import IFeatureService

class FeatureThing:
    """What this class does."""

    def process(self, data: InputType) -> Result[OutputType]:
        """
        Brief description.

        Args:
            data: What this is

        Returns:
            Result containing OutputType or error
        """
        # Implementation
```

### Common Patterns
- **Lazy initialization**: Create services on first use
- **Progress callbacks**: Optional callable for long operations
- **Validation first**: Always validate before processing
- **Early returns**: Return errors immediately
- **Resource cleanup**: Use try/finally or context managers

---

## Conclusion

Follow these standards to ensure your feature:
- Integrates seamlessly with the application
- Maintains code quality standards
- Is testable and maintainable
- Provides excellent user experience
- Can be extended without modification

**Remember**: The goal is clean, professional, maintainable code that other developers (including future you) can understand and modify confidently.