# Refactoring Implementation Plan - Folder Structure Utility
*Created: January 2025*  
*Version: 1.0*

## Overview

This document provides a detailed, phase-by-phase implementation plan to address all issues identified in the comprehensive code review. Each phase includes specific tasks, acceptance criteria, estimated effort, and risk mitigation strategies.

## Implementation Phases

### 🚨 Phase 0: Emergency Hotfix (Day 1)
**Goal:** Fix critical security vulnerability and prevent data loss

#### Tasks
1. **Patch Path Traversal Vulnerability** [2 hours]
   ```python
   # In core/workers/folder_operations.py:43-45
   # Add validation:
   def _validate_destination(self, source_path, dest_path):
       """Ensure destination stays within bounds"""
       try:
           dest_resolved = dest_path.resolve()
           base_resolved = self.destination.resolve()
           if not str(dest_resolved).startswith(str(base_resolved)):
               raise ValueError(f"Path traversal detected: {dest_path}")
           return dest_resolved
       except Exception as e:
           raise ValueError(f"Invalid destination path: {e}")
   ```

2. **Add Emergency Batch Processing Guard** [1 hour]
   ```python
   # In ui/tabs/batch_tab.py - Temporarily disable
   def start_processing(self):
       QMessageBox.warning(self, "Feature Temporarily Disabled",
           "Batch processing is undergoing critical fixes. "
           "Please use single file processing mode.")
       return  # Block execution
   ```

3. **Deploy Hotfix Release v2.0.1** [1 hour]
   - Update version number
   - Add release notes
   - Emergency deployment

#### Acceptance Criteria
- [ ] Path traversal attack vectors blocked
- [ ] Batch processing safely disabled with user notice
- [ ] No regression in single-file mode

---

### 📦 Phase 1: Foundation Layer (Days 2-3)
**Goal:** Create centralized systems for settings and paths

#### Tasks

1. **Create Settings Adapter** [4 hours]
   
   **File:** `core/settings_manager.py`
   ```python
   from PySide6.QtCore import QSettings
   from typing import Any, Optional
   from pathlib import Path
   
   class SettingsManager:
       """Centralized settings management with migration support"""
       
       # Canonical keys
       KEYS = {
           'CALCULATE_HASHES': 'forensic.calculate_hashes',
           'HASH_ALGORITHM': 'forensic.hash_algorithm',
           'COPY_BUFFER_SIZE': 'performance.copy_buffer_size',
           'ZIP_COMPRESSION_LEVEL': 'archive.compression_level',
           'ZIP_AT_ROOT': 'archive.create_at_root',
           'ZIP_AT_LOCATION': 'archive.create_at_location',
           'ZIP_AT_DATETIME': 'archive.create_at_datetime',
           'AUTO_CREATE_ZIP': 'archive.auto_create',
           'PROMPT_FOR_ZIP': 'archive.prompt_user',
           'TECHNICIAN_NAME': 'user.technician_name',
           'BADGE_NUMBER': 'user.badge_number',
           'TIME_OFFSET_PDF': 'reports.generate_time_offset',
           'UPLOAD_LOG_PDF': 'reports.generate_upload_log',
           'HASH_CSV': 'reports.generate_hash_csv',
           'AUTO_SCROLL_LOG': 'ui.auto_scroll_log',
           'CONFIRM_EXIT': 'ui.confirm_exit_with_operations',
           'DEBUG_LOGGING': 'debug.enable_logging',
           'LAST_OUTPUT_DIR': 'paths.last_output_directory',
           'LAST_INPUT_DIR': 'paths.last_input_directory'
       }
       
       # Legacy key mappings
       LEGACY_MAPPINGS = {
           'zip_compression': 'archive.compression_level',
           'generate_hash_csv': 'forensic.calculate_hashes',
           'calculate_hashes': 'forensic.calculate_hashes',
           'enable_hashing': 'forensic.calculate_hashes',
           'buffer_size': 'performance.copy_buffer_size',
           'copy_buffer_size': 'performance.copy_buffer_size'
       }
       
       def __init__(self):
           self._settings = QSettings('FolderStructureUtility', 'Settings')
           self._migrate_legacy_keys()
           self._set_defaults()
       
       def _migrate_legacy_keys(self):
           """Migrate legacy keys to canonical format"""
           for old_key, new_key in self.LEGACY_MAPPINGS.items():
               if self._settings.contains(old_key):
                   value = self._settings.value(old_key)
                   self._settings.setValue(new_key, value)
                   self._settings.remove(old_key)
       
       def _set_defaults(self):
           """Set default values for missing keys"""
           defaults = {
               self.KEYS['CALCULATE_HASHES']: True,
               self.KEYS['HASH_ALGORITHM']: 'sha256',
               self.KEYS['COPY_BUFFER_SIZE']: 1048576,  # 1MB
               self.KEYS['ZIP_COMPRESSION_LEVEL']: 6,
               self.KEYS['DEBUG_LOGGING']: False,
               self.KEYS['AUTO_SCROLL_LOG']: True,
               self.KEYS['CONFIRM_EXIT']: True
           }
           for key, default in defaults.items():
               if not self._settings.contains(key):
                   self._settings.setValue(key, default)
       
       def get(self, key: str, default: Any = None) -> Any:
           """Get setting value with type preservation"""
           canonical_key = self.KEYS.get(key, key)
           return self._settings.value(canonical_key, default)
       
       def set(self, key: str, value: Any):
           """Set setting value"""
           canonical_key = self.KEYS.get(key, key)
           self._settings.setValue(canonical_key, value)
       
       def sync(self):
           """Force settings to disk"""
           self._settings.sync()
       
       # Convenience properties
       @property
       def calculate_hashes(self) -> bool:
           return self.get('CALCULATE_HASHES', True)
       
       @property
       def copy_buffer_size(self) -> int:
           return min(max(self.get('COPY_BUFFER_SIZE', 1048576), 8192), 10485760)
       
       @property
       def technician_name(self) -> str:
           return self.get('TECHNICIAN_NAME', '')
       
       @property
       def badge_number(self) -> str:
           return self.get('BADGE_NUMBER', '')
   ```

2. **Create Path Utilities Module** [3 hours]
   
   **File:** `core/path_utils.py`
   ```python
   from pathlib import Path
   import re
   import unicodedata
   from typing import Optional
   
   class PathSanitizer:
       """Comprehensive path sanitization for cross-platform compatibility"""
       
       # Platform-specific invalid characters
       INVALID_CHARS = {
           'windows': r'<>:"|?*\x00-\x1f',
           'posix': r'\x00',
           'universal': r'\x00'
       }
       
       # Windows reserved names
       RESERVED_NAMES = {
           'CON', 'PRN', 'AUX', 'NUL',
           'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 
           'COM6', 'COM7', 'COM8', 'COM9',
           'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5',
           'LPT6', 'LPT7', 'LPT8', 'LPT9'
       }
       
       @staticmethod
       def sanitize_component(text: str, platform: str = 'universal') -> str:
           """Sanitize a single path component"""
           if not text:
               return '_'
           
           # Unicode normalization
           text = unicodedata.normalize('NFKC', text)
           
           # Remove null bytes
           text = text.replace('\x00', '')
           
           # Platform-specific character removal
           invalid_pattern = PathSanitizer.INVALID_CHARS.get(platform, r'\x00')
           text = re.sub(f'[{invalid_pattern}]', '_', text)
           
           # Remove path separators
           text = text.replace('/', '_').replace('\\', '_')
           
           # Handle Windows reserved names
           if platform == 'windows':
               base_name = text.split('.')[0].upper()
               if base_name in PathSanitizer.RESERVED_NAMES:
                   text = f'_{text}'
           
           # Length limits (255 for most filesystems)
           if len(text) > 255:
               # Preserve extension if present
               if '.' in text:
                   name, ext = text.rsplit('.', 1)
                   max_name_len = 254 - len(ext)
                   text = f"{name[:max_name_len]}.{ext}"
               else:
                   text = text[:255]
           
           # Remove leading/trailing dots and spaces
           text = text.strip('. ')
           
           # Ensure not empty after sanitization
           if not text:
               text = '_'
           
           return text
       
       @staticmethod
       def validate_destination(source: Path, destination: Path, base: Path) -> Path:
           """Validate destination path stays within base directory"""
           try:
               dest_resolved = destination.resolve()
               base_resolved = base.resolve()
               
               # Check if destination is within base
               try:
                   dest_resolved.relative_to(base_resolved)
               except ValueError:
                   raise ValueError(
                       f"Security: Destination {destination} escapes base {base}"
                   )
               
               return dest_resolved
           except Exception as e:
               raise ValueError(f"Invalid destination path: {e}")
   
   
   class ForensicPathBuilder:
       """Build forensic folder structures without side effects"""
       
       @staticmethod
       def build_relative_path(form_data) -> Path:
           """Build relative path without creating directories"""
           from core.models import FormData
           
           # Sanitize components
           sanitizer = PathSanitizer()
           
           occurrence = sanitizer.sanitize_component(
               form_data.occurrence_number or "NO_OCCURRENCE"
           )
           
           # Business @ Location format
           business = sanitizer.sanitize_component(form_data.business_name or "")
           location = sanitizer.sanitize_component(form_data.location_address or "")
           
           if business and location:
               location_part = f"{business} @ {location}"
           elif business:
               location_part = business
           elif location:
               location_part = location
           else:
               location_part = "NO_LOCATION"
           
           location_part = sanitizer.sanitize_component(location_part)
           
           # Date range format
           date_format = "%Y-%m-%d_%H%M"
           start_date = form_data.video_start_datetime.strftime(date_format)
           end_date = form_data.video_end_datetime.strftime(date_format)
           date_part = sanitizer.sanitize_component(f"{start_date}_to_{end_date}")
           
           # Build path
           return Path(occurrence) / location_part / date_part
       
       @staticmethod
       def ensure_directory(base: Path, relative: Path) -> Path:
           """Create directory structure safely"""
           full_path = base / relative
           full_path.mkdir(parents=True, exist_ok=True)
           return full_path
   ```

3. **Create Centralized Logger** [2 hours]
   
   **File:** `core/logger.py`
   ```python
   import logging
   import sys
   from pathlib import Path
   from PySide6.QtCore import QObject, Signal
   
   class AppLogger(QObject):
       """Centralized logging with Qt signal support"""
       
       log_message = Signal(str, str)  # level, message
       
       _instance = None
       
       def __new__(cls):
           if cls._instance is None:
               cls._instance = super().__new__(cls)
               cls._instance._initialized = False
           return cls._instance
       
       def __init__(self):
           if self._initialized:
               return
           super().__init__()
           self._initialized = True
           
           # Configure Python logger
           self.logger = logging.getLogger('FolderStructureUtility')
           self.logger.setLevel(logging.DEBUG)
           
           # Console handler
           console_handler = logging.StreamHandler(sys.stdout)
           console_handler.setLevel(logging.INFO)
           
           # File handler
           log_dir = Path.home() / '.folder_structure_utility' / 'logs'
           log_dir.mkdir(parents=True, exist_ok=True)
           log_file = log_dir / 'app.log'
           
           file_handler = logging.FileHandler(log_file)
           file_handler.setLevel(logging.DEBUG)
           
           # Formatter
           formatter = logging.Formatter(
               '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
           )
           console_handler.setFormatter(formatter)
           file_handler.setFormatter(formatter)
           
           self.logger.addHandler(console_handler)
           self.logger.addHandler(file_handler)
       
       def debug(self, message: str):
           """Log debug message"""
           self.logger.debug(message)
           self.log_message.emit('DEBUG', message)
       
       def info(self, message: str):
           """Log info message"""
           self.logger.info(message)
           self.log_message.emit('INFO', message)
       
       def warning(self, message: str):
           """Log warning message"""
           self.logger.warning(message)
           self.log_message.emit('WARNING', message)
       
       def error(self, message: str, exc_info=False):
           """Log error message"""
           self.logger.error(message, exc_info=exc_info)
           self.log_message.emit('ERROR', message)
       
       def critical(self, message: str, exc_info=True):
           """Log critical message"""
           self.logger.critical(message, exc_info=exc_info)
           self.log_message.emit('CRITICAL', message)
   
   # Global logger instance
   logger = AppLogger()
   ```

#### Acceptance Criteria
- [ ] All settings access uses SettingsManager
- [ ] Legacy settings keys successfully migrated
- [ ] Path sanitization passes security tests
- [ ] Logger replaces all print statements
- [ ] No regressions in existing functionality

---

### 🔧 Phase 2: Fix Batch Processing (Days 4-5)
**Goal:** Restore batch processing functionality with proper architecture

#### Tasks

1. **Rewrite Batch Processor Core** [6 hours]
   
   **File:** `core/workers/batch_processor.py` (Key sections)
   ```python
   def _copy_items_sync(self, job, items):
       """Synchronously copy items for a batch job"""
       from core.file_ops import FileOperations
       from core.path_utils import ForensicPathBuilder, PathSanitizer
       
       try:
           # Build destination path properly
           relative_path = ForensicPathBuilder.build_relative_path(job.form_data)
           dest_base = Path(job.output_directory) / relative_path
           dest_base.mkdir(parents=True, exist_ok=True)
           
           # Use FileOperations directly
           file_ops = FileOperations()
           settings = SettingsManager()
           
           # Prepare file list
           all_files = []
           for item in items:
               if item.is_file():
                   all_files.append((item, item.name))
               elif item.is_dir():
                   # Preserve folder structure
                   for file_path in item.rglob('*'):
                       if file_path.is_file():
                           rel_path = file_path.relative_to(item.parent)
                           all_files.append((file_path, rel_path))
           
           # Copy with proper progress
           total_files = len(all_files)
           results = {}
           
           for idx, (src_file, rel_path) in enumerate(all_files):
               # Validate and create destination
               dest_file = dest_base / rel_path
               dest_file.parent.mkdir(parents=True, exist_ok=True)
               
               # Copy single file
               try:
                   # Copy with hash if enabled
                   if settings.calculate_hashes:
                       src_hash = file_ops._calculate_hash(src_file)
                       shutil.copy2(src_file, dest_file)
                       dest_hash = file_ops._calculate_hash(dest_file)
                       verified = src_hash == dest_hash
                   else:
                       shutil.copy2(src_file, dest_file)
                       verified = None
                   
                   results[str(dest_file)] = {
                       'source': str(src_file),
                       'destination': str(dest_file),
                       'size': src_file.stat().st_size,
                       'hash': src_hash if settings.calculate_hashes else None,
                       'verified': verified
                   }
                   
                   # Emit progress
                   progress = int((idx + 1) / total_files * 100)
                   self.job_progress.emit(
                       self.current_index,
                       progress,
                       f"Copying {src_file.name}"
                   )
                   
               except Exception as e:
                   logger.error(f"Failed to copy {src_file}: {e}")
                   results[str(src_file)] = {
                       'error': str(e)
                   }
               
               # Check cancellation
               if self.cancelled:
                   return False, "Cancelled by user", results
           
           return True, "Files copied successfully", results
           
       except Exception as e:
           logger.error(f"Batch copy failed: {e}", exc_info=True)
           return False, str(e), {}
   ```

2. **Fix PDF Generation Calls** [2 hours]
   
   ```python
   def _generate_reports(self, job, results, reports_dir):
       """Generate reports with correct API calls"""
       from core.pdf_gen import PDFGenerator
       from controllers.report_controller import ReportController
       
       settings = SettingsManager()
       
       try:
           # Use ReportController for consistency
           controller = ReportController()
           
           # Generate reports based on settings
           generated = controller.generate_reports(
               form_data=job.form_data,
               file_results=results,
               output_dir=reports_dir,
               generate_time_offset=settings.get('TIME_OFFSET_PDF', True),
               generate_upload_log=settings.get('UPLOAD_LOG_PDF', True),
               generate_hash_csv=settings.calculate_hashes and bool(results)
           )
           
           return True, generated
           
       except Exception as e:
           logger.error(f"Report generation failed: {e}", exc_info=True)
           return False, []
   ```

3. **Add Batch Processing Tests** [3 hours]
   
   **File:** `tests/test_batch_processing.py`
   ```python
   import pytest
   import tempfile
   from pathlib import Path
   from core.batch_queue import BatchQueue, BatchJob
   from core.models import FormData
   from core.workers.batch_processor import BatchProcessorThread
   
   class TestBatchProcessing:
       
       @pytest.fixture
       def temp_dirs(self):
           """Create temporary directories for testing"""
           with tempfile.TemporaryDirectory() as src_dir:
               with tempfile.TemporaryDirectory() as dst_dir:
                   # Create test files
                   src_path = Path(src_dir)
                   (src_path / "file1.txt").write_text("content1")
                   (src_path / "file2.txt").write_text("content2")
                   
                   yield src_path, Path(dst_dir)
       
       @pytest.fixture
       def sample_job(self, temp_dirs):
           """Create a sample batch job"""
           src_dir, dst_dir = temp_dirs
           
           form_data = FormData()
           form_data.occurrence_number = "TEST001"
           form_data.business_name = "Test Business"
           form_data.location_address = "123 Test St"
           
           job = BatchJob(
               form_data=form_data,
               files=[src_dir / "file1.txt"],
               folders=[],
               output_directory=str(dst_dir)
           )
           return job
       
       def test_batch_copy_creates_structure(self, sample_job, temp_dirs):
           """Test that batch processing creates correct structure"""
           src_dir, dst_dir = temp_dirs
           
           # Create processor
           queue = BatchQueue()
           queue.add_job(sample_job)
           
           processor = BatchProcessorThread(queue)
           
           # Process synchronously for testing
           success, message, results = processor._copy_items_sync(
               sample_job,
               sample_job.files
           )
           
           # Verify
           assert success is True
           assert len(results) == 1
           
           # Check structure
           expected_path = dst_dir / "TEST001" / "Test Business @ 123 Test St"
           assert expected_path.exists()
       
       def test_batch_handles_errors_gracefully(self, sample_job):
           """Test error handling in batch processing"""
           # Add non-existent file
           sample_job.files.append(Path("/nonexistent/file.txt"))
           
           queue = BatchQueue()
           queue.add_job(sample_job)
           processor = BatchProcessorThread(queue)
           
           success, message, results = processor._copy_items_sync(
               sample_job,
               sample_job.files
           )
           
           # Should still succeed but with errors logged
           assert success is True
           assert any('error' in r for r in results.values())
   ```

#### Acceptance Criteria
- [ ] Batch processing successfully copies files
- [ ] Correct folder structure created
- [ ] PDF generation works without errors
- [ ] Hash verification functional
- [ ] Progress reporting accurate
- [ ] All tests pass

---

### 🎯 Phase 3: Fix UI State Management (Days 6-7)
**Goal:** Correct FilesPanel state corruption and improve UX

#### Tasks

1. **Rewrite FilesPanel State Management** [4 hours]
   
   **File:** `ui/components/files_panel.py` (Key sections)
   ```python
   class FilesPanel(QWidget):
       def __init__(self):
           super().__init__()
           self.selected_files = []
           self.selected_folders = []
           self.entries = []  # New: unified entry list
           self._entry_map = {}  # Map QListWidgetItem to entry
           self.init_ui()
       
       def add_files(self):
           """Add files with proper tracking"""
           file_paths, _ = QFileDialog.getOpenFileNames(
               self, "Select Files", "", "All Files (*.*)"
           )
           
           for file_path in file_paths:
               path = Path(file_path)
               
               # Check for duplicates
               if any(e['path'] == path for e in self.entries if e['type'] == 'file'):
                   continue
               
               # Create entry
               entry = {
                   'type': 'file',
                   'path': path,
                   'id': len(self.entries)
               }
               self.entries.append(entry)
               self.selected_files.append(path)
               
               # Create list item
               item = QListWidgetItem(f"📄 {path.name}")
               item.setData(Qt.UserRole, entry['id'])
               self.files_list.addItem(item)
               self._entry_map[item] = entry
           
           self.files_changed.emit()
           self._update_ui_state()
       
       def add_folders(self):
           """Add folders with proper tracking"""
           folder_path = QFileDialog.getExistingDirectory(
               self, "Select Folder"
           )
           
           if folder_path:
               path = Path(folder_path)
               
               # Check for duplicates
               if any(e['path'] == path for e in self.entries if e['type'] == 'folder'):
                   return
               
               # Create entry
               entry = {
                   'type': 'folder',
                   'path': path,
                   'id': len(self.entries),
                   'file_count': len(list(path.rglob('*')))
               }
               self.entries.append(entry)
               self.selected_folders.append(path)
               
               # Create list item
               item = QListWidgetItem(f"📁 {path.name} ({entry['file_count']} files)")
               item.setData(Qt.UserRole, entry['id'])
               self.files_list.addItem(item)
               self._entry_map[item] = entry
           
           self.files_changed.emit()
           self._update_ui_state()
       
       def remove_selected(self):
           """Remove selected items correctly"""
           selected_items = self.files_list.selectedItems()
           
           if not selected_items:
               return
           
           # Collect entries to remove
           entries_to_remove = []
           for item in selected_items:
               entry_id = item.data(Qt.UserRole)
               entry = next((e for e in self.entries if e['id'] == entry_id), None)
               if entry:
                   entries_to_remove.append(entry)
           
           # Remove from data structures
           for entry in entries_to_remove:
               self.entries.remove(entry)
               
               if entry['type'] == 'file':
                   if entry['path'] in self.selected_files:
                       self.selected_files.remove(entry['path'])
               else:  # folder
                   if entry['path'] in self.selected_folders:
                       self.selected_folders.remove(entry['path'])
           
           # Remove from UI
           for item in selected_items:
               self.files_list.takeItem(self.files_list.row(item))
               if item in self._entry_map:
                   del self._entry_map[item]
           
           self.files_changed.emit()
           self._update_ui_state()
       
       def clear_all(self):
           """Clear all selections"""
           self.entries.clear()
           self.selected_files.clear()
           self.selected_folders.clear()
           self._entry_map.clear()
           self.files_list.clear()
           
           self.files_changed.emit()
           self._update_ui_state()
       
       def _update_ui_state(self):
           """Update UI elements based on state"""
           has_items = bool(self.entries)
           self.remove_btn.setEnabled(has_items)
           self.clear_btn.setEnabled(has_items)
           
           # Update count label
           file_count = len(self.selected_files)
           folder_count = len(self.selected_folders)
           
           if file_count and folder_count:
               count_text = f"{file_count} files, {folder_count} folders"
           elif file_count:
               count_text = f"{file_count} file{'s' if file_count != 1 else ''}"
           elif folder_count:
               count_text = f"{folder_count} folder{'s' if folder_count != 1 else ''}"
           else:
               count_text = "No items selected"
           
           self.count_label.setText(count_text)
   ```

2. **Add FilesPanel Tests** [2 hours]
   
   **File:** `tests/test_files_panel.py`
   ```python
   import pytest
   from pathlib import Path
   from PySide6.QtCore import Qt
   from ui.components.files_panel import FilesPanel
   
   class TestFilesPanel:
       
       @pytest.fixture
       def panel(self, qtbot):
           """Create FilesPanel instance"""
           widget = FilesPanel()
           qtbot.addWidget(widget)
           return widget
       
       def test_add_remove_files(self, panel):
           """Test adding and removing files"""
           # Add files
           file1 = Path("/test/file1.txt")
           file2 = Path("/test/file2.txt")
           
           panel.selected_files = [file1, file2]
           panel.entries = [
               {'type': 'file', 'path': file1, 'id': 0},
               {'type': 'file', 'path': file2, 'id': 1}
           ]
           
           # Test removal
           assert len(panel.selected_files) == 2
           
           # Simulate removing first file
           panel.entries.remove(panel.entries[0])
           panel.selected_files.remove(file1)
           
           assert len(panel.selected_files) == 1
           assert panel.selected_files[0] == file2
       
       def test_mixed_files_folders(self, panel):
           """Test mixed file and folder handling"""
           file1 = Path("/test/file.txt")
           folder1 = Path("/test/folder")
           
           panel.selected_files = [file1]
           panel.selected_folders = [folder1]
           panel.entries = [
               {'type': 'folder', 'path': folder1, 'id': 0},
               {'type': 'file', 'path': file1, 'id': 1}
           ]
           
           # Remove folder (first item)
           panel.entries.remove(panel.entries[0])
           panel.selected_folders.remove(folder1)
           
           # File should remain
           assert len(panel.selected_files) == 1
           assert len(panel.selected_folders) == 0
       
       def test_clear_all(self, panel):
           """Test clear all functionality"""
           panel.selected_files = [Path("/test/file.txt")]
           panel.selected_folders = [Path("/test/folder")]
           panel.entries = [
               {'type': 'file', 'path': Path("/test/file.txt"), 'id': 0},
               {'type': 'folder', 'path': Path("/test/folder"), 'id': 1}
           ]
           
           panel.clear_all()
           
           assert len(panel.selected_files) == 0
           assert len(panel.selected_folders) == 0
           assert len(panel.entries) == 0
   ```

3. **Remove Debug Prints** [1 hour]
   
   Replace all debug prints with proper logging:
   ```python
   # Before:
   print(f"DEBUG-ID-1001: Adding file {file_path}")
   
   # After:
   logger.debug(f"Adding file {file_path}")
   ```

#### Acceptance Criteria
- [ ] FilesPanel correctly manages mixed files/folders
- [ ] No IndexError on removal operations
- [ ] Proper state synchronization
- [ ] All debug prints removed
- [ ] Tests pass for all edge cases

---

### 🏗️ Phase 4: Architecture Cleanup (Days 8-9)
**Goal:** Fix architectural issues and remove side effects

#### Tasks

1. **Fix Static Method Issues** [2 hours]
   
   **File:** `core/templates.py`
   ```python
   class FolderTemplate:
       # Change from instance to static method
       @staticmethod
       def sanitize_path_part(text):
           """Static method for path sanitization"""
           from core.path_utils import PathSanitizer
           return PathSanitizer.sanitize_component(text)
   ```
   
   Update all call sites:
   ```python
   # Before:
   FolderTemplate._sanitize_path_part(None, text)
   
   # After:
   FolderTemplate.sanitize_path_part(text)
   ```

2. **Remove Side Effects from Path Builders** [2 hours]
   
   ```python
   class FolderBuilder:
       @staticmethod
       def build_forensic_structure(form_data):
           """Build path without creating directories"""
           from core.path_utils import ForensicPathBuilder
           return ForensicPathBuilder.build_relative_path(form_data)
       
       @staticmethod
       def create_forensic_structure(base_path, form_data):
           """Build and create directories"""
           relative = FolderBuilder.build_forensic_structure(form_data)
           full_path = base_path / relative
           full_path.mkdir(parents=True, exist_ok=True)
           return full_path
   ```

3. **Fix Thread Cleanup** [2 hours]
   
   **File:** `ui/main_window.py`
   ```python
   def closeEvent(self, event):
       """Properly clean up all threads"""
       # Cancel any active operations
       threads_to_stop = []
       
       # File operation threads
       if hasattr(self, 'file_thread') and self.file_thread:
           if self.file_thread.isRunning():
               threads_to_stop.append(('file_thread', self.file_thread))
       
       # Folder operation threads
       if hasattr(self, 'folder_thread') and self.folder_thread:
           if self.folder_thread.isRunning():
               threads_to_stop.append(('folder_thread', self.folder_thread))
       
       # Batch processing threads
       if hasattr(self, 'batch_tab') and self.batch_tab:
           batch_widget = self.batch_tab.queue_widget
           if batch_widget.processor_thread and batch_widget.processor_thread.isRunning():
               threads_to_stop.append(('batch_processor', batch_widget.processor_thread))
       
       # ZIP operation threads
       if hasattr(self, 'zip_thread') and self.zip_thread:
           if self.zip_thread.isRunning():
               threads_to_stop.append(('zip_thread', self.zip_thread))
       
       if threads_to_stop:
           # Ask user
           if self.settings.get('CONFIRM_EXIT', True):
               reply = QMessageBox.question(
                   self, 
                   "Active Operations",
                   f"There are {len(threads_to_stop)} active operations. "
                   "Do you want to cancel them and exit?",
                   QMessageBox.Yes | QMessageBox.No
               )
               
               if reply == QMessageBox.No:
                   event.ignore()
                   return
           
           # Cancel and wait for threads
           for name, thread in threads_to_stop:
               logger.info(f"Stopping {name}")
               thread.cancel()
           
           # Wait with timeout
           for name, thread in threads_to_stop:
               if not thread.wait(5000):  # 5 second timeout
                   logger.warning(f"Thread {name} did not stop gracefully")
                   thread.terminate()
       
       # Save settings
       self.settings.sync()
       
       # Proceed with close
       event.accept()
   ```

#### Acceptance Criteria
- [ ] All static methods properly declared
- [ ] Path builders have no side effects
- [ ] Thread cleanup works for all thread types
- [ ] No orphaned threads on exit
- [ ] Clean shutdown in all scenarios

---

### 🚀 Phase 5: Performance Optimization (Days 10-11)
**Goal:** Implement performance improvements

#### Tasks

1. **Implement Buffered File Operations** [3 hours]
   
   **File:** `core/file_ops.py`
   ```python
   def copy_file_buffered(self, source: Path, dest: Path, 
                          buffer_size: int = None,
                          progress_callback = None) -> dict:
       """Copy file with configurable buffer and progress"""
       settings = SettingsManager()
       buffer_size = buffer_size or settings.copy_buffer_size
       
       # Ensure buffer size is reasonable
       buffer_size = min(max(buffer_size, 8192), 10485760)  # 8KB to 10MB
       
       result = {
           'source': str(source),
           'destination': str(dest),
           'size': source.stat().st_size,
           'start_time': time.time()
       }
       
       try:
           # Create destination directory
           dest.parent.mkdir(parents=True, exist_ok=True)
           
           bytes_copied = 0
           total_size = result['size']
           
           # Stream copy for large files
           if total_size > 104857600:  # 100MB
               with open(source, 'rb') as src:
                   with open(dest, 'wb') as dst:
                       while True:
                           chunk = src.read(buffer_size)
                           if not chunk:
                               break
                           
                           dst.write(chunk)
                           bytes_copied += len(chunk)
                           
                           # Report progress
                           if progress_callback:
                               progress = int(bytes_copied / total_size * 100)
                               progress_callback(progress, f"Copying {source.name}")
                           
                           # Check cancellation
                           if hasattr(self, 'cancelled') and self.cancelled:
                               raise InterruptedError("Operation cancelled")
           else:
               # Small files - copy at once
               shutil.copy2(source, dest)
               bytes_copied = total_size
           
           # Preserve metadata
           shutil.copystat(source, dest)
           
           # Calculate hash if enabled
           if settings.calculate_hashes:
               result['hash'] = self._calculate_hash_buffered(dest, buffer_size)
               result['verified'] = True
           
           result['end_time'] = time.time()
           result['duration'] = result['end_time'] - result['start_time']
           result['success'] = True
           
           return result
           
       except Exception as e:
           result['error'] = str(e)
           result['success'] = False
           logger.error(f"Failed to copy {source}: {e}")
           return result
   
   def _calculate_hash_buffered(self, file_path: Path, 
                                buffer_size: int = 1048576) -> str:
       """Calculate file hash with buffered reading"""
       hash_obj = hashlib.sha256()
       
       with open(file_path, 'rb') as f:
           while True:
               chunk = f.read(buffer_size)
               if not chunk:
                   break
               hash_obj.update(chunk)
       
       return hash_obj.hexdigest()
   ```

2. **Add Performance Benchmarks** [2 hours]
   
   **File:** `tests/test_performance.py`
   ```python
   import pytest
   import tempfile
   import time
   from pathlib import Path
   from core.file_ops import FileOperations
   
   class TestPerformance:
       
       @pytest.fixture
       def large_file(self):
           """Create a large test file"""
           with tempfile.NamedTemporaryFile(delete=False) as tmp:
               # Write 100MB of data
               data = b'x' * 1048576  # 1MB
               for _ in range(100):
                   tmp.write(data)
               return Path(tmp.name)
       
       def test_buffered_copy_performance(self, large_file, tmp_path):
           """Test that buffered copy is faster than unbuffered"""
           file_ops = FileOperations()
           
           # Test different buffer sizes
           buffer_sizes = [8192, 65536, 1048576, 5242880]
           results = {}
           
           for buffer_size in buffer_sizes:
               dest = tmp_path / f"copy_{buffer_size}.dat"
               
               start = time.time()
               file_ops.copy_file_buffered(
                   large_file, dest, 
                   buffer_size=buffer_size
               )
               duration = time.time() - start
               
               results[buffer_size] = duration
               dest.unlink()  # Clean up
           
           # Larger buffers should be faster (to a point)
           assert results[1048576] < results[8192]
       
       def test_hash_performance(self, large_file):
           """Test hash calculation performance"""
           file_ops = FileOperations()
           
           # Time hash calculation
           start = time.time()
           hash_value = file_ops._calculate_hash_buffered(large_file)
           duration = time.time() - start
           
           # Should complete in reasonable time
           assert duration < 5.0  # 100MB in under 5 seconds
           assert len(hash_value) == 64  # SHA-256 hex length
   ```

3. **Optimize UI Responsiveness** [2 hours]
   
   Add chunked progress reporting:
   ```python
   class FileOperationThread(QThread):
       chunk_progress = Signal(int, int)  # bytes_done, bytes_total
       
       def run(self):
           """Run with byte-level progress"""
           # ... existing code ...
           
           def progress_callback(percent, message):
               self.progress.emit(percent)
               self.status.emit(message)
           
           # Use buffered operations
           for file in self.files:
               result = self.file_ops.copy_file_buffered(
                   file, dest, 
                   progress_callback=progress_callback
               )
   ```

#### Acceptance Criteria
- [ ] Buffered copy faster than unbuffered
- [ ] Large files don't exhaust memory
- [ ] Progress updates at byte level
- [ ] Hash calculation optimized
- [ ] Performance tests pass

---

### 🧪 Phase 6: Testing & Quality (Days 12-13)
**Goal:** Achieve comprehensive test coverage and quality metrics

#### Tasks

1. **Create Test Suite** [4 hours]
   
   **File:** `tests/test_suite.py`
   ```python
   """Comprehensive test suite for critical paths"""
   
   # Test categories:
   # 1. Unit tests for core modules
   # 2. Integration tests for workflows
   # 3. UI tests for components
   # 4. Security tests for vulnerabilities
   # 5. Performance tests for bottlenecks
   
   def run_all_tests():
       """Run complete test suite"""
       import pytest
       
       # Run with coverage
       pytest.main([
           '--cov=core',
           '--cov=controllers',
           '--cov=ui',
           '--cov-report=html',
           '--cov-report=term-missing',
           'tests/'
       ])
   ```

2. **Add Security Tests** [3 hours]
   
   **File:** `tests/test_security.py`
   ```python
   class TestSecurity:
       
       def test_path_traversal_blocked(self):
           """Test that path traversal attacks are blocked"""
           sanitizer = PathSanitizer()
           
           # Test various attack vectors
           attacks = [
               "../../../etc/passwd",
               "..\\..\\..\\windows\\system32",
               "test/../../outside",
               "symlink_to_root",
           ]
           
           for attack in attacks:
               sanitized = sanitizer.sanitize_component(attack)
               assert ".." not in sanitized
               assert "/" not in sanitized
               assert "\\" not in sanitized
       
       def test_null_byte_injection(self):
           """Test null byte injection prevention"""
           sanitizer = PathSanitizer()
           
           malicious = "file.txt\x00.exe"
           sanitized = sanitizer.sanitize_component(malicious)
           
           assert "\x00" not in sanitized
           assert sanitized == "file.txt.exe"
       
       def test_unicode_attacks(self):
           """Test Unicode normalization attacks"""
           sanitizer = PathSanitizer()
           
           # Unicode look-alike characters
           malicious = "fıle.txt"  # Turkish dotless i
           sanitized = sanitizer.sanitize_component(malicious)
           
           # Should normalize to standard characters
           assert sanitized == "file.txt"
   ```

3. **Add Integration Tests** [3 hours]
   
   **File:** `tests/test_integration.py`
   ```python
   class TestIntegration:
       
       def test_full_forensic_workflow(self, tmp_path):
           """Test complete forensic processing workflow"""
           # Create test data
           src_dir = tmp_path / "source"
           src_dir.mkdir()
           (src_dir / "evidence.txt").write_text("test evidence")
           
           dst_dir = tmp_path / "output"
           
           # Create form data
           form_data = FormData()
           form_data.occurrence_number = "2024-001"
           form_data.business_name = "Test Corp"
           
           # Process files
           controller = FileController()
           thread = controller.process_forensic_files(
               form_data=form_data,
               files=[src_dir / "evidence.txt"],
               folders=[],
               output_directory=str(dst_dir)
           )
           
           # Run synchronously for testing
           thread.run()
           
           # Verify structure
           expected = dst_dir / "2024-001" / "Test Corp" / "*"
           assert len(list(expected.parent.glob("*"))) > 0
       
       def test_batch_recovery(self, tmp_path):
           """Test batch processing recovery after crash"""
           # Create recovery file
           recovery_mgr = BatchRecoveryManager()
           
           # Simulate interrupted batch
           queue = BatchQueue()
           job = BatchJob(...)
           job.status = 'processing'
           queue.add_job(job)
           
           # Save state
           recovery_mgr.save_recovery_state(queue)
           
           # Simulate restart
           recovered = recovery_mgr.check_recovery()
           assert recovered is not None
           
           # Verify job resumed
           assert recovered.jobs[0].status == 'pending'
   ```

#### Acceptance Criteria
- [ ] Test coverage >60% for critical modules
- [ ] All security tests pass
- [ ] Integration tests cover main workflows
- [ ] Performance benchmarks established
- [ ] CI/CD pipeline configured

---

### 📋 Phase 7: Documentation & Deployment (Days 14-15)
**Goal:** Update documentation and prepare for release

#### Tasks

1. **Update Documentation** [3 hours]
   - Update README with accurate features
   - Create CHANGELOG with all fixes
   - Update CLAUDE.md with new architecture
   - Add API documentation for core modules

2. **Create Release Package** [2 hours]
   - Version bump to 2.1.0
   - Create release notes
   - Build distribution packages
   - Test installation process

3. **Performance Validation** [2 hours]
   - Run performance benchmarks
   - Compare with baseline
   - Document improvements

#### Acceptance Criteria
- [ ] Documentation accurate and complete
- [ ] Release notes comprehensive
- [ ] Installation tested on target platforms
- [ ] Performance improvements documented

---

## Implementation Timeline

| Phase | Days | Priority | Dependencies |
|-------|------|----------|--------------|
| Phase 0: Emergency Hotfix | 1 | CRITICAL | None |
| Phase 1: Foundation Layer | 2 | HIGH | Phase 0 |
| Phase 2: Fix Batch Processing | 2 | CRITICAL | Phase 1 |
| Phase 3: Fix UI State | 2 | HIGH | Phase 1 |
| Phase 4: Architecture Cleanup | 2 | MEDIUM | Phases 1-3 |
| Phase 5: Performance | 2 | MEDIUM | Phase 4 |
| Phase 6: Testing | 2 | HIGH | Phases 1-5 |
| Phase 7: Documentation | 2 | MEDIUM | All phases |

**Total Duration:** 15 working days (3 weeks)

## Risk Mitigation

### Technical Risks

| Risk | Mitigation |
|------|------------|
| Breaking changes in refactoring | Comprehensive test suite before changes |
| Performance regression | Benchmark before/after each phase |
| Data loss during migration | Backup settings, test migration thoroughly |
| User disruption | Phase rollout, feature flags where needed |

### Process Risks

| Risk | Mitigation |
|------|------------|
| Scope creep | Strict phase boundaries, defer nice-to-haves |
| Integration issues | Test each phase independently |
| Incomplete testing | Minimum coverage requirements per phase |
| Documentation drift | Update docs with each phase |

## Success Metrics

### Functionality Metrics
- ✅ Batch processing success rate: >99%
- ✅ File operation accuracy: 100%
- ✅ PDF generation success: 100%
- ✅ Zero security vulnerabilities

### Performance Metrics
- ✅ Large file copy: >100MB/s on SSD
- ✅ Hash calculation: >200MB/s
- ✅ UI responsiveness: <100ms
- ✅ Memory usage: <500MB for typical operations

### Quality Metrics
- ✅ Test coverage: >60% critical paths
- ✅ Code complexity: <10 cyclomatic
- ✅ Zero critical bugs in production
- ✅ User satisfaction: >90%

## Post-Implementation Review

After completing all phases:

1. **Code Review:** Full review of changes
2. **Security Audit:** Penetration testing of file operations
3. **Performance Analysis:** Benchmark against requirements
4. **User Acceptance:** Beta testing with key users
5. **Lessons Learned:** Document what worked/didn't work

## Appendix: Quick Reference

### File Modifications by Phase

**Phase 0:**
- `core/workers/folder_operations.py`
- `ui/tabs/batch_tab.py`

**Phase 1:**
- NEW: `core/settings_manager.py`
- NEW: `core/path_utils.py`
- NEW: `core/logger.py`

**Phase 2:**
- `core/workers/batch_processor.py`
- NEW: `tests/test_batch_processing.py`

**Phase 3:**
- `ui/components/files_panel.py`
- NEW: `tests/test_files_panel.py`

**Phase 4:**
- `core/templates.py`
- `ui/main_window.py`
- All files with static method calls

**Phase 5:**
- `core/file_ops.py`
- `core/workers/file_operations.py`
- NEW: `tests/test_performance.py`

**Phase 6:**
- NEW: `tests/test_security.py`
- NEW: `tests/test_integration.py`
- NEW: `tests/test_suite.py`

### Command Quick Reference

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest --cov=core --cov=controllers --cov=ui tests/

# Run specific test file
pytest tests/test_batch_processing.py -v

# Format code
black .

# Lint code
flake8 . --max-line-length=100

# Run application
python main.py

# Run in debug mode
python main.py --debug
```

---
*End of Refactoring Implementation Plan*