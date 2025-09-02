# Copy & Verify Tab - Implementation Plan

## Executive Summary

A new standalone tab for direct file/folder copying with hash verification, bypassing all form validation and template schemas. This tab provides a streamlined interface for users who simply need to copy files/folders from source to destination while maintaining exact folder structure and generating hash verification reports.

## Core Requirements

### What Users Need
1. **Simple copy operation**: "Move these files/folders from here to here"
2. **Structure preservation**: Maintain exact source folder hierarchy
3. **Hash verification**: Generate CSV with source and destination hashes
4. **No form constraints**: No occurrence number, no location address, no templates
5. **Direct operation**: No time offset sheets, no technician logs - just copy and verify

### What Users Don't Need
- Form validation requirements
- Template-based folder structures
- Time offset documentation
- Technician/uploader logs
- Business name or location fields
- Any mandatory metadata

## Technical Architecture

### UI Components

#### CopyVerifyTab (Main Tab Widget)
```python
class CopyVerifyTab(QWidget):
    """Standalone tab for direct copy and verify operations"""
    
    # Signals
    copy_requested = Signal(list, Path, Path, bool)  # files, source, dest, preserve_structure
    log_message = Signal(str, str)  # message, level
    
    # Components:
    - Source panel (FilesPanel for source selection)
    - Destination panel (Path selector with browse button)
    - CSV output selector (Optional path for hash report)
    - Options panel (checkboxes for preserve structure, generate hashes)
    - Action buttons (Copy, Copy & Verify, Cancel)
    - Progress panel (dual progress bars for copy and verify)
    - Results display (summary of operation)
```

#### Key UI Features
1. **Three-column layout**:
   - Left: Source file/folder selection
   - Center: Operation controls and options
   - Right: Progress and results

2. **Simplified controls**:
   - Browse button for destination
   - Optional CSV path selector
   - Checkbox: "Preserve folder structure"
   - Checkbox: "Generate hash verification"
   - Radio buttons: SHA-256 (default), MD5, SHA-1

3. **Real-time feedback**:
   - Progress bars showing copy progress
   - Speed indicators using buffer reuse metrics
   - Live file count and size updates

### Backend Components

#### CopyVerifyController
```python
class CopyVerifyController(BaseController):
    """Controller for copy and verify operations without form dependencies"""
    
    def execute_copy_verify(
        self,
        source_items: List[Path],
        destination: Path,
        csv_path: Optional[Path] = None,
        preserve_structure: bool = True,
        calculate_hashes: bool = True,
        algorithm: str = "sha256"
    ) -> Result[CopyVerifyResult]:
        """
        Execute copy operation with optional verification
        
        No form validation, no templates, just direct operation
        """
```

#### CopyVerifyWorkerThread
```python
class CopyVerifyWorkerThread(BaseWorkerThread):
    """Worker thread for copy/verify operations"""
    
    def execute(self) -> Result:
        # 1. Copy files using BufferedFileOperations with buffer reuse
        # 2. If hashes enabled, collect source and dest hashes
        # 3. Generate CSV report if path provided
        # 4. Return comprehensive results
```

#### CopyVerifyResult (Data Structure)
```python
@dataclass
class CopyVerifyResult:
    """Results from copy and verify operation"""
    files_copied: int
    total_size: int
    source_hashes: Dict[Path, str]
    destination_hashes: Dict[Path, str]
    verification_status: Dict[Path, bool]  # True if hashes match
    csv_generated: Optional[Path]
    performance_metrics: PerformanceMetrics
    errors: List[str]
```

### Integration with Buffer Reuse Optimization

The Copy & Verify tab will leverage the buffer reuse optimization for maximum performance:

1. **Direct BufferedFileOperations usage**:
   ```python
   ops = BufferedFileOperations(
       progress_callback=self.update_progress,
       cancel_event=self.cancel_event
   )
   ```

2. **Automatic optimization selection**:
   - Small files (<1MB): Single read with in-memory hashing
   - Large files (≥1MB): Stream copy with integrated source hashing
   - Destination always verified from disk for forensic integrity

3. **Performance metrics exposure**:
   - Show "disk reads saved" counter
   - Display real-time MB/s throughput
   - Track CPU vs I/O bottleneck indicators

### CSV Report Format

#### Simple Copy & Verify Report
```csv
# Copy & Verify Report
# Generated: 2024-12-02 14:30:00
# Operation: Direct Copy with Verification
# Algorithm: SHA-256

Source Path,Destination Path,Source Hash,Destination Hash,Match,Size (bytes),Status
/source/file1.mp4,/dest/file1.mp4,abc123...,abc123...,TRUE,1048576,SUCCESS
/source/dir/file2.jpg,/dest/dir/file2.jpg,def456...,def456...,TRUE,524288,SUCCESS
/source/file3.doc,/dest/file3.doc,ghi789...,xyz000...,FALSE,262144,MISMATCH
```

### Implementation Steps

#### Phase 1: UI Creation (2 hours)
1. Create `ui/tabs/copy_verify_tab.py`
2. Implement three-column layout
3. Add source/destination selectors
4. Create options panel with checkboxes
5. Add progress indicators

#### Phase 2: Controller Implementation (2 hours)
1. Create `controllers/copy_verify_controller.py`
2. Implement `execute_copy_verify()` method
3. Add path validation (minimal, just existence checks)
4. Wire up to BufferedFileOperations

#### Phase 3: Worker Thread (1 hour)
1. Create `core/workers/copy_verify_worker.py`
2. Implement threaded copy with progress
3. Add hash collection during copy
4. Handle cancellation gracefully

#### Phase 4: CSV Generation (1 hour)
1. Create simplified CSV generator in controller
2. Format with source/dest paths and hashes
3. Include verification status
4. Add performance metrics summary

#### Phase 5: Integration (1 hour)
1. Add tab to MainWindow
2. Connect signals and slots
3. Test with various file sizes
4. Verify buffer reuse optimization active

#### Phase 6: Testing & Polish (1 hour)
1. Test with large file sets
2. Verify hash accuracy
3. Test cancellation at various points
4. Add success/error dialogs

## Key Differentiators from Existing Tabs

### What Makes This Different
1. **No form validation**: No required fields at all
2. **No templates**: Direct copy without folder structure manipulation
3. **No metadata**: No technician info, no time offsets
4. **Simplified reporting**: Just hashes, no PDFs or logs
5. **Direct operation**: Source → Destination, nothing else

### What Stays the Same
1. **Buffer reuse optimization**: Full performance benefits
2. **Progress reporting**: Real-time feedback
3. **Error handling**: Result objects and proper error messages
4. **Thread safety**: Proper Qt threading model
5. **Cancellation support**: Clean interruption

## Benefits

### For Users
- **Simplicity**: No forms to fill out
- **Speed**: Direct operation without overhead
- **Flexibility**: Use for any copy/verify need
- **Transparency**: See exactly what's being copied where

### For Forensics
- **Hash verification**: Cryptographic proof of accurate copy
- **Structure preservation**: Exact source hierarchy maintained
- **CSV documentation**: Audit trail of all operations
- **No contamination**: No metadata added to copied files

## Risk Mitigation

### Potential Issues and Solutions

1. **Accidental overwrites**:
   - Solution: Prompt before overwriting existing files
   - Add "Skip existing" checkbox option

2. **Large file sets**:
   - Solution: Use buffered operations with progress
   - Allow cancellation at any point

3. **Hash mismatches**:
   - Solution: Clearly report in CSV and UI
   - Offer retry option for failed files

4. **Path confusion**:
   - Solution: Show full paths in UI
   - Preview of operation before starting

## Success Metrics

### Performance Targets
- Copy speed: Match or exceed OS native copy
- Hash calculation: 500+ MB/s (SHA-256)
- Memory usage: <100MB regardless of file size
- UI responsiveness: Progress updates every 100ms

### User Experience Targets
- Time to start operation: <5 seconds from tab selection
- Clarity: User understands exactly what will happen
- Feedback: Never more than 1 second without progress update
- Recovery: Clear options when errors occur

## Conclusion

The Copy & Verify tab provides a streamlined, schema-free alternative for users who need simple file copying with hash verification. By leveraging the buffer reuse optimization and removing all form validation overhead, this tab offers maximum performance with minimal complexity.

Total estimated implementation time: **8 hours**

### Next Steps
1. Review and approve this plan
2. Create UI mockup for user feedback
3. Implement Phase 1 (UI Creation)
4. Iterate based on initial testing