# Copy/Hash/Verify Module

Self-contained module for professional file hashing, verification, and copy operations with integrated UI.

## Architecture

Follows the `media_analysis/` module pattern with complete self-containment and professional UI design.

### Module Structure

```
copy_hash_verify/
├── __init__.py                          # Module exports
├── README.md                            # This file
├── core/                                # Core business logic
│   ├── __init__.py
│   └── unified_hash_calculator.py       # Combined hash engine
├── controllers/                         # (Future) Operation controllers
│   └── __init__.py
├── services/                            # (Future) Service layer
│   └── __init__.py
└── ui/                                  # User interface
    ├── __init__.py
    ├── copy_hash_verify_master_tab.py   # Main tab container
    ├── components/                      # Reusable UI components
    │   ├── __init__.py
    │   ├── operation_log_console.py     # Color-coded logger
    │   └── base_operation_tab.py        # Base class for sub-tabs
    └── tabs/                            # Operation sub-tabs
        ├── __init__.py
        ├── calculate_hashes_tab.py      # Single hash calculation
        ├── verify_hashes_tab.py         # Bidirectional verification
        └── copy_verify_operation_tab.py # Copy with hash verification
```

## Features

### 1. **Calculate Hashes** Sub-Tab
- Hierarchical file tree for selection (files and folders)
- Full viewport scrollable settings panel
- Multiple algorithms: SHA-256, SHA-1, MD5
- CSV report generation with metadata
- Performance tuning (adaptive buffering, parallel workers)
- Large styled statistics display

### 2. **Verify Hashes** Sub-Tab
- Split source/target file panels
- Bidirectional hash verification
- Mismatch detection and reporting
- Stop-on-first-mismatch option
- Comprehensive CSV verification reports

### 3. **Copy & Verify** Sub-Tab
- Integrated copy + hash verification (2-read optimization)
- Source files and destination folder selection
- Preserve folder structure option
- Pause/resume support
- Dual progress indicators (copy + hash)
- Performance optimization settings

## UI Patterns (Following Media Analysis)

### Color-Coded Logger
All operations use a shared console with HTML-formatted, color-coded output:
- **INFO**: Carolina Blue `#4B9CD3`
- **SUCCESS**: Green `#52c41a`
- **WARNING**: Orange `#faad14`
- **ERROR**: Red `#ff4d4f`

### Splitter-Based Layout
Each sub-tab uses consistent 45/55 splitter layout:
- **Left Panel (45%)**: File selection with hierarchical trees
- **Right Panel (55%)**: Full viewport scrollable settings
- **Bottom Section**: Shared color-coded logger console

### Large Statistics Display
After operations complete, large styled numbers show:
- Total files processed (24px, Carolina Blue)
- Successful operations (24px, Green)
- Failed operations (24px, Red)
- Processing speed MB/s (24px, Carolina Blue)

## UnifiedHashCalculator

The core hash engine combining best features from both existing implementations:

### Features
- **Adaptive Buffering**: Automatically selects optimal buffer size based on file size
  - Small files (<1MB): 256KB buffer
  - Medium files (1-100MB): 2MB buffer
  - Large files (>100MB): 10MB buffer
- **Algorithm Flexibility**: SHA-256, SHA-1, MD5
- **2-Read Optimization**: Combines copy and hash operations for efficiency
- **Bidirectional Verification**: Compares source and target hashes
- **Progress Reporting**: Comprehensive callbacks for UI integration
- **Cancellation Support**: Thread-safe operation cancellation
- **Result-Based Architecture**: All operations return Result objects

### Usage

```python
from copy_hash_verify.core.unified_hash_calculator import UnifiedHashCalculator

# Create calculator
calculator = UnifiedHashCalculator(
    algorithm='sha256',
    progress_callback=lambda pct, msg: print(f"{pct}%: {msg}"),
    cancelled_check=lambda: False
)

# Hash files
result = calculator.hash_files([Path('file1.txt'), Path('folder/')])

if result.success:
    for path, hash_result in result.value.items():
        print(f"{path}: {hash_result.hash_value}")
else:
    print(f"Error: {result.error.user_message}")

# Verify hashes
verify_result = calculator.verify_hashes(
    source_paths=[Path('source/')],
    target_paths=[Path('target/')]
)

if verify_result.success:
    for path, ver_result in verify_result.value.items():
        if ver_result.match:
            print(f"✓ {path} verified")
        else:
            print(f"✗ {path} mismatch!")
```

## Integration

### Main Window Integration (4-Line Pattern)

```python
from copy_hash_verify import CopyHashVerifyMasterTab

# In MainWindow._setup_ui()
self.copy_hash_verify_tab = CopyHashVerifyMasterTab()
self.copy_hash_verify_tab.log_message.connect(self.main_console.append_log)
self.copy_hash_verify_tab.status_message.connect(self.statusBar().showMessage)
self.tabs.addTab(self.copy_hash_verify_tab, "🔢 Copy/Hash/Verify")
```

## Design Philosophy

### Media Analysis Patterns
This module follows the successful patterns established by `media_analysis/`:
1. **Self-Contained**: All dependencies within module boundary
2. **Tab-Based Organization**: Multiple operation types in one clean interface
3. **Shared Logger**: Single console for all operations with color coding
4. **Full Viewport Settings**: No cramped checkboxes, all options clearly visible
5. **Professional Statistics**: Large styled numbers for key metrics
6. **Splitter Layouts**: Consistent 45/55 splits for file selection vs settings

### Advantages Over Old Design
**Before** (Separate HashingTab + CopyVerifyTab):
- Cramped three-column layout in HashingTab
- Generic LogConsole with no color coding
- Tiny operation cards with limited info
- Duplicated hash implementations
- Separate tabs competing for space

**After** (Unified Module):
- Full viewport for each operation type
- Color-coded professional logger
- Large statistics displays
- Single unified hash engine
- Tab-based organization keeps UI clean

## Future Enhancements

### Phase 1 (Completed)
- ✅ Module structure
- ✅ Color-coded logger console
- ✅ Base operation tab class
- ✅ UnifiedHashCalculator
- ✅ Calculate Hashes sub-tab
- ✅ Verify Hashes sub-tab
- ✅ Copy & Verify sub-tab
- ✅ Master tab container

### Phase 2 (Pending)
- [ ] Worker threads for background operations
- [ ] Service layer (IHashService, ICopyVerifyService)
- [ ] Success message builders
- [ ] CSV report generation improvements
- [ ] Performance monitoring integration
- [ ] Comprehensive testing

### Phase 3 (Future)
- [ ] Parallel hashing with hashwise
- [ ] Advanced verification modes
- [ ] Progress persistence
- [ ] Operation queue management
- [ ] Export to multiple formats (JSON, XML)

## Testing

```bash
# Run the application with new module
.venv/Scripts/python.exe main.py

# Navigate to Copy/Hash/Verify tab
# Test each sub-tab:
# 1. Calculate Hashes - Add files, select algorithm, calculate
# 2. Verify Hashes - Add source/target, verify
# 3. Copy & Verify - Add source, select destination, copy+verify
```

## Notes

- All sub-tabs share the same logger console at the bottom
- Messages are prefixed with `[Calculate Hashes]`, `[Verify Hashes]`, or `[Copy & Verify]`
- Statistics are tab-specific and hidden until operation completes
- Settings are persisted using QSettings per sub-tab

## Credits

Architecture inspired by the successful `media_analysis/` module design patterns.
