# Media Analysis Feature - Integration Plan & Architecture

## Executive Summary

Adding a **Media Analysis Tab** to extract and report metadata from video/image files using FFprobe. This feature will seamlessly integrate with the existing refactored architecture, following established patterns while maintaining pragmatic simplicity.

## Feature Overview

### Core Functionality
- **File/Folder Selection**: Point to files/folders containing media
- **Metadata Extraction**: Use FFprobe to extract comprehensive metadata
- **Flexible Reporting**: User-configurable metadata fields and file path formats
- **PDF Generation**: Professional "Media File Analysis" report
- **Error Resilience**: Skip unprocessable files, continue with next

### Key Design Principles
- ✅ **Follow existing patterns** (HashingTab as template)
- ✅ **Leverage existing infrastructure** (FilesPanel, Result objects, PDF generation)
- ✅ **Pragmatic approach** - no overengineering
- ✅ **Modular architecture** - clean separation of concerns
- ✅ **Production-ready** error handling and logging

## Architecture Components

### 1. **UI Layer - MediaAnalysisTab**

```python
ui/tabs/media_analysis_tab.py
```

**Structure Following HashingTab Pattern:**
- Top section: Settings/Options (metadata field selection)
- Middle section: FilesPanel for file/folder selection
- Bottom section: LogConsole for progress/results
- Process button to start analysis

**Key UI Elements:**
```python
class MediaAnalysisTab(QWidget):
    # Signals (following existing pattern)
    log_message = Signal(str)
    status_message = Signal(str)
    
    # Components
    - self.files_panel: FilesPanel (reuse existing)
    - self.settings_panel: MetadataSettingsPanel (new)
    - self.log_console: LogConsole (reuse existing)
    - self.process_btn: QPushButton
    - self.progress_bar: QProgressBar
```

### 2. **Controller Layer - MediaAnalysisController**

```python
controllers/media_analysis_controller.py
```

**Responsibilities:**
- Orchestrate media analysis workflow
- Manage worker thread lifecycle
- Coordinate between UI and services
- Handle cancellation

**Pattern Following HashController:**
```python
class MediaAnalysisController(BaseController):
    def start_media_analysis_workflow(
        self,
        paths: List[Path],
        settings: MediaAnalysisSettings
    ) -> Result[MediaAnalysisWorker]:
        # Validation
        # Create worker
        # Return Result
```

### 3. **Service Layer - MediaAnalysisService**

```python
core/services/media_analysis_service.py
```

**Business Logic:**
- Process file lists
- Coordinate metadata extraction
- Format results for reporting
- Handle file filtering

**Service Interface:**
```python
class MediaAnalysisService(BaseService, IMediaAnalysisService):
    def analyze_media_files(
        self,
        files: List[Path],
        settings: MediaAnalysisSettings
    ) -> Result[MediaAnalysisResult]:
        # Process files
        # Extract metadata
        # Return aggregated results
```

### 4. **Worker Thread - MediaAnalysisWorker**

```python
core/workers/media_analysis_worker.py
```

**Threading Pattern:**
```python
class MediaAnalysisWorker(BaseWorkerThread):
    # Unified signals (following nuclear migration)
    result_ready = Signal(Result)
    progress_update = Signal(int, str)
    
    def execute(self) -> Result[MediaAnalysisResult]:
        # Process files with progress
        # Use FFProbeWrapper for extraction
        # Return Result object
```

### 5. **FFprobe Integration - FFProbeWrapper**

```python
core/media/ffprobe_wrapper.py
```

**Pragmatic Wrapper:**
```python
class FFProbeWrapper:
    def extract_metadata(self, file_path: Path) -> Result[MediaMetadata]:
        # Call ffprobe subprocess
        # Parse JSON output
        # Normalize metadata
        # Return Result with normalized data
        
    def is_media_file(self, file_path: Path) -> bool:
        # Quick check if ffprobe can read file
        # Return True/False without throwing
```

**Metadata Normalization:**
- Raw FFprobe JSON → Human-readable format
- Example: `"codec_name": "h264"` → `"Codec: H.264/AVC"`
- Consistent date formatting: `"2025/08/28"`
- Readable bitrates: `"2000 kb/s"`

### 6. **Settings Management - MediaAnalysisSettings**

```python
core/models/media_analysis_settings.py
```

**Settings Structure:**
```python
@dataclass
class MediaAnalysisSettings:
    # Metadata field groups
    general_fields: MetadataFieldGroup
    video_fields: MetadataFieldGroup
    audio_fields: MetadataFieldGroup
    creation_fields: MetadataFieldGroup
    location_fields: MetadataFieldGroup
    device_fields: MetadataFieldGroup
    
    # File reference format
    file_reference_format: FileReferenceFormat
    
    # Processing options
    skip_non_media: bool = True
    max_errors_before_abort: int = 100

@dataclass
class MetadataFieldGroup:
    enabled: bool
    fields: Dict[str, bool]  # field_name -> enabled
    
class FileReferenceFormat(Enum):
    FULL_PATH = "full_path"           # path/to/file.mp4
    PARENT_AND_NAME = "parent_name"   # parent_dir/file.mp4
    NAME_ONLY = "name_only"           # file.mp4
```

### 7. **Report Generation - MediaReportGenerator**

```python
core/media/media_report_generator.py
```

**PDF Report Generation:**
```python
class MediaReportGenerator:
    def generate_report(
        self,
        results: MediaAnalysisResult,
        output_path: Path,
        form_data: FormData
    ) -> ReportGenerationResult:
        # Use existing PDFGenerator patterns
        # Create professional layout
        # Include case information
        # Format metadata tables
        # Return Result object
```

## Integration Points

### 1. **MainWindow Integration**

```python
# In ui/main_window.py _setup_ui():

# Media Analysis tab
self.media_analysis_tab = MediaAnalysisTab(
    self.media_analysis_controller,
    self
)
self.media_analysis_tab.log_message.connect(self.log)
self.tabs.addTab(self.media_analysis_tab, "Media Analysis")
```

### 2. **Controller Registration**

```python
# In main_window.__init__():
self.media_analysis_controller = MediaAnalysisController()
```

### 3. **Service Configuration**

```python
# In core/services/service_config.py:
register_service(IMediaAnalysisService, MediaAnalysisService)
```

## Metadata Field Groups

### General Information
- Format/Container
- Duration
- File Size
- Overall Bitrate
- Creation Date

### Video Stream
- Codec (H.264, H.265, etc.)
- Resolution (1920x1080)
- Frame Rate (30fps)
- Bit Rate
- Profile/Level
- Pixel Format

### Audio Stream
- Codec (AAC, MP3, etc.)
- Sample Rate (48000 Hz)
- Channels (Stereo/5.1)
- Bit Rate

### Creation/Modification
- Creation Time
- Modification Time
- Encoding Date
- Tagged Date

### Location (if present)
- GPS Latitude
- GPS Longitude
- GPS Altitude
- Location String

### Device Information
- Make (Canon, Sony, etc.)
- Model
- Software/Firmware
- Lens Information

## File Processing Strategy

### Smart Processing Approach
Instead of maintaining a massive exclusion list:

1. **Try Everything**: Attempt FFprobe on all files
2. **Fast Fail**: FFprobe fails quickly on non-media
3. **Log and Continue**: Record attempt, move to next
4. **No Extension Discrimination**: Let FFprobe decide

```python
def process_file(file_path: Path) -> Result[MediaMetadata]:
    try:
        # Quick timeout on FFprobe (1 second)
        result = ffprobe_wrapper.extract_metadata(
            file_path, 
            timeout=1.0
        )
        if result.success:
            return result
        else:
            logger.debug(f"Not a media file: {file_path}")
            return Result.error(...)
    except TimeoutError:
        logger.debug(f"Timeout on: {file_path}")
        return Result.error(...)
```

## UI Mockup

```
┌─────────────────────────────────────────────────┐
│ Media Analysis                                  │
├─────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────┐ │
│ │ Metadata Settings                           │ │
│ │                                             │ │
│ │ [✓] General Information                     │ │
│ │     [✓] Format  [✓] Duration  [✓] Size     │ │
│ │                                             │ │
│ │ [✓] Video Stream                            │ │
│ │     [✓] Codec  [✓] Resolution  [✓] FPS     │ │
│ │                                             │ │
│ │ [✓] Audio Stream                            │ │
│ │     [✓] Codec  [✓] Sample Rate             │ │
│ │                                             │ │
│ │ File Reference Format:                      │ │
│ │ [•] Full Path                               │ │
│ │ [ ] Parent Dir + Name                       │ │
│ │ [ ] Filename Only                           │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ ┌─────────────────────────────────────────────┐ │
│ │ Files to Process                            │ │
│ │ [Standard FilesPanel Component]             │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ [Process Files] [Export Report]                 │
│                                                 │
│ ┌─────────────────────────────────────────────┐ │
│ │ Log Console                                 │ │
│ │ Processing file 1 of 150...                 │ │
│ │ Extracted metadata from video1.mp4          │ │
│ │ Skipped document.pdf (not media)            │ │
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

## Implementation Phases

### Phase 1: Core Infrastructure (2-3 hours)
1. Create MediaAnalysisTab UI
2. Create MediaAnalysisController
3. Create MediaAnalysisWorker thread
4. Wire up to MainWindow

### Phase 2: FFprobe Integration (2-3 hours)
1. Create FFProbeWrapper
2. Implement metadata extraction
3. Add metadata normalization
4. Test with various media formats

### Phase 3: Settings & Configuration (1-2 hours)
1. Create MetadataSettingsPanel UI
2. Implement settings persistence
3. Add field selection logic

### Phase 4: Report Generation (2-3 hours)
1. Create MediaReportGenerator
2. Design PDF layout
3. Implement normalized formatting
4. Test report generation

### Phase 5: Testing & Polish (1-2 hours)
1. Test with large file sets
2. Verify error handling
3. Performance optimization
4. UI polish

**Total Estimate: 8-13 hours**

## Error Handling Strategy

### Graceful Degradation
```python
class MediaAnalysisError(FSAError):
    """Media analysis specific errors"""
    pass

class FFProbeNotFoundError(MediaAnalysisError):
    """FFprobe binary not available"""
    user_message = "FFprobe is required but not found. Please install FFmpeg."

class MediaExtractionError(MediaAnalysisError):
    """Failed to extract metadata from file"""
    # Log and continue, don't stop processing
```

### Progress Reporting
- Overall progress: X of Y files processed
- Current file being processed
- Running count of successful/skipped files
- Estimated time remaining

## Success Metrics

The feature will be considered successful when:

1. ✅ Can process 1000+ files without crashing
2. ✅ Generates professional PDF reports
3. ✅ Handles non-media files gracefully
4. ✅ Provides useful progress feedback
5. ✅ Integrates seamlessly with existing UI
6. ✅ Follows all existing code patterns
7. ✅ Maintains application stability

## Configuration & Dependencies

### External Dependencies
```python
# requirements.txt addition
# (FFprobe must be installed separately)
```

### FFprobe Detection
```python
def find_ffprobe() -> Optional[Path]:
    # Check PATH
    if shutil.which("ffprobe"):
        return Path(shutil.which("ffprobe"))
    
    # Check common locations
    common_paths = [
        Path("C:/ffmpeg/bin/ffprobe.exe"),
        Path("/usr/bin/ffprobe"),
        Path("/usr/local/bin/ffprobe"),
    ]
    
    for path in common_paths:
        if path.exists():
            return path
    
    return None
```

## Sample Report Output

```
                Media File Analysis Report
                
Case Information:
- Occurrence Number: 2024-12345
- Location: 123 Main St
- Technician: John Doe

Analysis Summary:
- Total Files Analyzed: 150
- Media Files Found: 142
- Non-Media Files Skipped: 8
- Processing Time: 2.5 minutes

File: CCTV_Front_Door/video_001.mp4
- Creation Date: 2025/08/28 14:30:00
- Duration: 00:05:23
- Resolution: 1920x1080
- Frame Rate: 30fps
- Video Codec: H.264/AVC
- Audio Codec: AAC
- Overall Bitrate: 2500 kb/s

File: Evidence_Photos/IMG_2341.jpg
- Creation Date: 2025/08/27 09:15:00
- Resolution: 4032x3024
- Device Make: Apple
- Device Model: iPhone 13 Pro
- GPS Location: 40.7128°N, 74.0060°W
```

## Conclusion

This Media Analysis feature will integrate seamlessly with the existing application architecture while providing powerful metadata extraction capabilities. By following established patterns and maintaining pragmatic simplicity, we can deliver a production-ready feature that enhances the application's forensic capabilities without adding unnecessary complexity.

The modular design ensures easy maintenance and future enhancements while the robust error handling maintains the application's enterprise-grade reliability.

---

*Integration Plan Version: 1.0*  
*Estimated Implementation: 8-13 hours*  
*Complexity: Medium*  
*Risk Level: Low (follows existing patterns)*