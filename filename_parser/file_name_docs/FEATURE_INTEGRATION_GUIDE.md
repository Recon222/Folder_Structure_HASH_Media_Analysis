# Feature Integration Guide

## Quick Start Integration

### Basic Tab Integration (8 Lines)
```python
# In your main window __init__:
from feature_name import FeatureTab

self.feature_tab = FeatureTab()
self.feature_tab.log_message.connect(self.log)           # Connect logging
self.feature_tab.status_message.connect(self.update_status)  # Status updates
self.tabs.addTab(self.feature_tab, "Feature Name")
```

**That's it.** Features should be self-contained modules.

---

## Integration Patterns

### Pattern 1: Standalone Tab (Most Common)
```python
from feature_name import FeatureTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Create tab - zero configuration required
        self.feature_tab = FeatureTab()

        # Connect standard signals
        self.feature_tab.log_message.connect(self.on_log_message)
        self.feature_tab.process_requested.connect(self.on_process_requested)

        # Add to UI
        self.tabs.addTab(self.feature_tab, "Feature Name")

    def on_log_message(self, level: str, message: str):
        self.log_console.append(f"[{level}] {message}")
```

### Pattern 2: Controller Integration (Custom Workflows)
```python
from feature_name.controllers import FeatureController
from feature_name.models import FeatureSettings

class CustomWorkflow:
    def __init__(self):
        self.controller = FeatureController()

    def process_data(self, input_data: List[Path]):
        # Configure settings
        settings = FeatureSettings(
            option1=True,
            option2="value",
            output_directory=Path("output")
        )

        # Start processing
        result = self.controller.start_workflow(input_data, settings)

        if result.is_success:
            worker = result.value
            worker.progress_update.connect(self.on_progress)
            worker.result_ready.connect(self.on_complete)
            # Worker already started by controller
        else:
            self.handle_error(result.error)
```

### Pattern 3: Direct Service Usage (No UI)
```python
from feature_name.services import FeatureService

# Create service
service = FeatureService()

# Process data directly
result = service.process(input_data, options)

if result.is_success:
    output = result.value
    print(f"Success: {output}")
else:
    print(f"Error: {result.error.user_message}")
```

---

## Dependency Management

### Required Dependencies
```python
# Core Qt dependencies
from PySide6.QtCore import QThread, Signal, QObject
from PySide6.QtWidgets import QWidget, QMainWindow

# Python standard library
from pathlib import Path
from typing import List, Optional, Dict
import json, csv, tempfile
```

### Application Infrastructure
```python
# These should be provided by parent application:
from core.result_types import Result           # Result object pattern
from core.exceptions import ValidationError    # Custom exceptions
from core.workers import BaseWorkerThread      # Worker base class
from core.services import BaseService          # Service base class
```

### Providing Missing Infrastructure
If your application doesn't have these, create minimal implementations:

```python
# minimal_infrastructure.py
from dataclasses import dataclass
from typing import Any, Optional
from PySide6.QtCore import QThread, Signal

@dataclass
class Result:
    """Minimal Result implementation."""
    is_success: bool
    value: Any = None
    error: Exception = None

    @classmethod
    def success(cls, value):
        return cls(is_success=True, value=value)

    @classmethod
    def error(cls, error):
        return cls(is_success=False, error=error)

class BaseService:
    """Minimal service base class."""
    def __init__(self, name: str):
        self.name = name

class BaseWorkerThread(QThread):
    """Minimal worker thread base."""
    result_ready = Signal(object)  # Signal(Result)
    progress_update = Signal(int, str)

    def run(self):
        result = self.execute()
        self.result_ready.emit(result)

    def execute(self) -> Result:
        raise NotImplementedError
```

---

## Configuration Management

### Default Configuration
Features should work with zero configuration:

```python
class FeatureSettings:
    """Feature configuration with sensible defaults."""
    def __init__(self,
                 option1: bool = True,          # Sensible default
                 option2: str = "auto",          # Auto-detect mode
                 output_dir: Path = None,        # Default to cwd
                 advanced_option: float = 1.0):  # Advanced users only

        self.option1 = option1
        self.option2 = option2
        self.output_dir = output_dir or Path.cwd()
        self.advanced_option = advanced_option
```

### Custom Configuration
Allow override for advanced users:

```python
# User-provided configuration
settings = FeatureSettings(
    option1=False,                    # Override default
    option2="manual",                 # Specific mode
    output_dir=Path("/custom/path"), # Custom output
    advanced_option=2.5               # Fine-tuning
)

# Pass to controller/service
result = controller.process(data, settings)
```

---

## External Dependencies

### Binary Dependencies
If your feature needs external binaries (FFmpeg, ImageMagick, etc.):

```python
class BinaryManager:
    """Manage external binary dependencies."""

    def __init__(self):
        self._ffmpeg_path = None
        self._detect_binaries()

    def _detect_binaries(self):
        """Auto-detect binaries in common locations."""
        # Check PATH
        if shutil.which("ffmpeg"):
            self._ffmpeg_path = Path(shutil.which("ffmpeg"))

        # Check common locations
        common_paths = [
            Path("bin/ffmpeg"),
            Path("/usr/bin/ffmpeg"),
            Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe")
        ]

        for path in common_paths:
            if path.exists():
                self._ffmpeg_path = path
                break

    def get_ffmpeg_path(self) -> Optional[Path]:
        """Get FFmpeg path or None if not found."""
        return self._ffmpeg_path

    def set_custom_path(self, binary: str, path: Path):
        """Allow manual override."""
        if binary == "ffmpeg":
            self._ffmpeg_path = path

# Usage
binary_manager = BinaryManager()
if not binary_manager.get_ffmpeg_path():
    show_error("FFmpeg not found. Please install FFmpeg.")
```

---

## Signal Interface

### Standard Signals
Every feature tab should emit these standard signals:

```python
class FeatureTab(QWidget):
    # Required signals for integration
    log_message = Signal(str, str)        # level, message
    status_message = Signal(str)          # Status bar update
    process_requested = Signal()          # Processing started
    process_completed = Signal(bool)      # Success/failure

    # Optional signals
    progress_update = Signal(int, str)    # percentage, message
    error_occurred = Signal(str)          # Error message
```

### Worker Signals
Workers must follow this pattern:

```python
class FeatureWorker(BaseWorkerThread):
    # Required unified signals
    result_ready = Signal(object)         # Signal(Result)
    progress_update = Signal(int, str)    # percentage, status

    # Optional signals
    log_message = Signal(str, str)        # level, message
    intermediate_result = Signal(object)  # Partial results
```

---

## Testing Integration

### Unit Test Pattern
```python
import pytest
from feature_name.services import FeatureService

def test_feature_service():
    """Test service in isolation."""
    service = FeatureService()
    result = service.process(test_data, test_options)

    assert result.is_success
    assert result.value.output_count == expected_count
```

### Integration Test Pattern
```python
from unittest.mock import Mock, patch
from feature_name.controllers import FeatureController

def test_controller_workflow():
    """Test controller with mocked services."""
    controller = FeatureController()

    # Mock service responses
    with patch.object(controller.service, 'process') as mock_process:
        mock_process.return_value = Result.success(test_output)

        result = controller.start_workflow(test_input, settings)

        assert result.is_success
        assert mock_process.called
```

### UI Integration Test
```python
from PySide6.QtTest import QTest
from feature_name import FeatureTab

def test_tab_integration(qtbot):
    """Test tab UI integration."""
    tab = FeatureTab()
    qtbot.addWidget(tab)

    # Simulate button click
    qtbot.mouseClick(tab.process_button, Qt.LeftButton)

    # Verify signal emitted
    with qtbot.waitSignal(tab.process_requested):
        tab.start_processing()
```

---

## Performance Considerations

### Threading Strategy
```python
# GOOD: Long operations in worker thread
class FeatureWorker(QThread):
    def execute(self):
        # Heavy processing here
        for item in large_dataset:
            process(item)
            self.progress_update.emit(progress, status)

# BAD: Blocking UI thread
def on_button_click(self):
    # DON'T DO THIS - blocks UI
    for item in large_dataset:
        process(item)
```

### Memory Management
```python
# Stream large files instead of loading into memory
def process_large_file(file_path: Path):
    with open(file_path, 'r') as f:
        for line in f:  # Stream line by line
            process_line(line)

# Clean up resources
def cleanup(self):
    if hasattr(self, 'temp_files'):
        for temp_file in self.temp_files:
            temp_file.unlink(missing_ok=True)
```

---

## Common Integration Scenarios

### Scenario 1: Adding to Existing Application
```python
# main_window.py
def add_feature_tab(self):
    """Add new feature to existing application."""
    # Import feature
    from feature_name import FeatureTab

    # Create and configure
    feature_tab = FeatureTab()
    feature_tab.log_message.connect(self.logger.log)

    # Add to tab widget
    self.tab_widget.addTab(feature_tab, "New Feature")

    # Register in menu
    self.menu_bar.add_action("New Feature", feature_tab.show)
```

### Scenario 2: CLI Tool Integration
```python
#!/usr/bin/env python
import sys
from pathlib import Path
from feature_name.services import FeatureService

def main(args):
    """CLI wrapper for feature."""
    if len(args) < 2:
        print(f"Usage: {args[0]} <input_file>")
        return 1

    service = FeatureService()
    result = service.process(Path(args[1]))

    if result.is_success:
        print(f"Success: {result.value}")
        return 0
    else:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

### Scenario 3: Web API Integration
```python
from fastapi import FastAPI, File, UploadFile
from feature_name.services import FeatureService

app = FastAPI()
service = FeatureService()

@app.post("/process")
async def process_file(file: UploadFile = File(...)):
    """API endpoint for feature."""
    # Save uploaded file
    temp_path = Path(f"/tmp/{file.filename}")
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    # Process
    result = service.process(temp_path)

    # Cleanup
    temp_path.unlink()

    if result.is_success:
        return {"status": "success", "data": result.value}
    else:
        return {"status": "error", "message": str(result.error)}
```

---

## Troubleshooting Guide

### Common Issues

**Module Import Error**
```python
# Solution: Add feature to Python path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from feature_name import FeatureTab
```

**Missing Dependencies**
```python
# Solution: Check and install requirements
try:
    import required_module
except ImportError:
    print("Please install: pip install required_module")
```

**UI Freezing**
```python
# Solution: Use worker threads for long operations
# Never call service methods directly from UI thread
```

**Signal Connection Issues**
```python
# Solution: Ensure signals connected before use
self.worker.result_ready.connect(self.on_complete)
self.worker.start()  # Start AFTER connecting signals
```

---

## Integration Checklist

### Pre-Integration
- [ ] Review feature documentation
- [ ] Check dependency requirements
- [ ] Install required packages
- [ ] Verify external binaries (if needed)

### Integration Steps
- [ ] Import feature module
- [ ] Create feature instance
- [ ] Connect required signals
- [ ] Add to UI (tab, menu, etc.)
- [ ] Configure settings (if needed)

### Post-Integration
- [ ] Test basic functionality
- [ ] Verify signal connections
- [ ] Check error handling
- [ ] Test with real data
- [ ] Monitor performance

### Deployment
- [ ] Document configuration
- [ ] Add to requirements.txt
- [ ] Update user documentation
- [ ] Create integration tests

---

## Summary

### Integration Complexity: **Minimal**
- **8 lines** for basic integration
- **Zero configuration** required (sensible defaults)
- **Self-contained** modules
- **Standard signals** for loose coupling

### Key Principles
1. **Self-contained**: Minimize external dependencies
2. **Zero-config**: Work with defaults
3. **Signal-based**: Loose coupling via Qt signals
4. **Service-oriented**: Clean separation of concerns
5. **Thread-safe**: Background processing for heavy operations

### Best Practices
- Always use worker threads for long operations
- Provide sensible defaults for all settings
- Emit standard signals for integration
- Include comprehensive error messages
- Clean up resources properly

**Remember**: A well-designed feature should integrate in minutes, not hours.