# Media Analysis Tab - Comprehensive Implementation Plan

## Executive Summary

This document provides a **phase-by-phase implementation plan** for adding a Media Analysis tab to the Folder Structure Application. The implementation follows the established SOA architecture, leveraging existing patterns from the Copy & Verify refactor while incorporating performance optimizations from FFprobe research.

**Total Estimated Time**: 10-12 hours  
**Architecture Pattern**: Full SOA compliance with Controller → Service → Worker layers  
**Binary Strategy**: Bundle FFprobe like 7zip for reliability

---

## Architecture Overview

```
MediaAnalysisTab → MediaAnalysisController → MediaAnalysisService → MediaAnalysisWorker → FFProbeWrapper
     (UI)            (Orchestration)          (Business Logic)       (Threading)         (Subprocess)
                            ↓
                      ServiceRegistry
                    (Dependency Injection)
```

---

## Phase 1: Core Infrastructure & Binary Management (2 hours)

### 1.1 FFprobe Binary Setup

**Location**: `bin/ffprobe.exe` (Windows), `bin/ffprobe` (Linux/Mac)

```python
# core/media/ffprobe_binary_manager.py
class FFProbeBinaryManager:
    """Manages FFprobe binary detection and validation"""
    
    def __init__(self):
        self.binary_path: Optional[Path] = None
        self.version_info: Optional[str] = None
        self.is_validated: bool = False
        
    def locate_binary(self) -> Optional[Path]:
        """Find FFprobe in bundled location or PATH"""
        # Check bundled locations first
        # Fallback to shutil.which('ffprobe')
        
    def validate_binary(self) -> bool:
        """Validate FFprobe functionality"""
        # Run ffprobe -version
        # Parse version info
        # Set validation flag
```

### 1.2 Service Interface Definition

```python
# core/services/interfaces.py
class IMediaAnalysisService(IService):
    """Interface for media analysis operations"""
    
    @abstractmethod
    def validate_media_files(self, paths: List[Path]) -> Result[List[Path]]:
        """Validate and filter media files"""
        
    @abstractmethod
    def analyze_media_files(
        self, 
        files: List[Path],
        settings: MediaAnalysisSettings
    ) -> Result[MediaAnalysisResult]:
        """Analyze media files and extract metadata"""
        
    @abstractmethod
    def generate_analysis_report(
        self,
        results: MediaAnalysisResult,
        output_path: Path,
        form_data: FormData
    ) -> Result[Path]:
        """Generate PDF report from analysis results"""
```

### 1.3 Data Models

```python
# core/models/media_analysis_models.py
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

class FileReferenceFormat(Enum):
    FULL_PATH = "full_path"
    PARENT_AND_NAME = "parent_name"
    NAME_ONLY = "name_only"

@dataclass
class MetadataFieldGroup:
    """Group of metadata fields with enable state"""
    enabled: bool
    fields: Dict[str, bool]  # field_name -> enabled
    
@dataclass
class MediaAnalysisSettings:
    """Settings for media analysis operation"""
    # Field groups
    general_fields: MetadataFieldGroup
    video_fields: MetadataFieldGroup
    audio_fields: MetadataFieldGroup
    creation_fields: MetadataFieldGroup
    location_fields: MetadataFieldGroup
    device_fields: MetadataFieldGroup
    
    # Display options
    file_reference_format: FileReferenceFormat = FileReferenceFormat.FULL_PATH
    
    # Processing options
    skip_non_media: bool = True
    timeout_seconds: float = 5.0
    max_workers: int = 8

@dataclass
class MediaMetadata:
    """Normalized metadata for a single media file"""
    file_path: Path
    file_size: int
    
    # General
    format: Optional[str] = None
    duration: Optional[float] = None
    bitrate: Optional[int] = None
    creation_date: Optional[datetime] = None
    
    # Video
    video_codec: Optional[str] = None
    resolution: Optional[tuple[int, int]] = None
    frame_rate: Optional[float] = None
    
    # Audio
    audio_codec: Optional[str] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    
    # Location
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    
    # Device
    device_make: Optional[str] = None
    device_model: Optional[str] = None
    
    # Raw data for debugging
    raw_json: Optional[Dict] = None
    error: Optional[str] = None

@dataclass
class MediaAnalysisResult:
    """Results from media analysis operation"""
    total_files: int
    successful: int
    failed: int
    skipped: int
    metadata_list: List[MediaMetadata]
    processing_time: float
    errors: List[str]
```

---

## Phase 2: FFprobe Wrapper & Metadata Extraction (3 hours)

### 2.1 FFprobe Subprocess Wrapper

```python
# core/media/ffprobe_wrapper.py
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

class FFProbeWrapper:
    """Wrapper for FFprobe subprocess operations"""
    
    def __init__(self, binary_path: Path, timeout: float = 5.0):
        self.binary_path = binary_path
        self.timeout = timeout
        
    def extract_metadata(self, file_path: Path) -> Result[Dict[str, Any]]:
        """Extract raw metadata from single file"""
        try:
            # Build command with selective field extraction
            cmd = [
                str(self.binary_path),
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                '-show_entries', 'format=duration,size,bit_rate,tags',
                '-show_entries', 'stream=codec_name,codec_type,width,height,avg_frame_rate,sample_rate,channels',
                str(file_path)
            ]
            
            # Run with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=True
            )
            
            # Parse JSON
            metadata = json.loads(result.stdout)
            return Result.success(metadata)
            
        except subprocess.TimeoutExpired:
            return Result.error(MediaExtractionError(
                f"Timeout extracting metadata from {file_path.name}",
                user_message="File took too long to process"
            ))
        except subprocess.CalledProcessError as e:
            # Not a media file or corrupted
            return Result.error(MediaExtractionError(
                f"FFprobe failed on {file_path.name}: {e}",
                user_message="Not a valid media file"
            ))
        except json.JSONDecodeError:
            return Result.error(MediaExtractionError(
                "Invalid JSON from FFprobe",
                user_message="Failed to parse metadata"
            ))
            
    def extract_batch(
        self, 
        file_paths: List[Path],
        max_workers: int = 8,
        progress_callback: Optional[callable] = None
    ) -> Dict[Path, Result[Dict]]:
        """Extract metadata from multiple files in parallel"""
        results = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_path = {
                executor.submit(self.extract_metadata, path): path
                for path in file_paths
            }
            
            # Process as completed
            completed = 0
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                results[path] = future.result()
                completed += 1
                
                if progress_callback:
                    progress_callback(completed, len(file_paths))
                    
        return results
```

### 2.2 Metadata Normalization

```python
# core/media/metadata_normalizer.py
class MetadataNormalizer:
    """Normalizes raw FFprobe output to MediaMetadata"""
    
    def normalize(self, raw_metadata: Dict, file_path: Path) -> MediaMetadata:
        """Convert raw FFprobe JSON to normalized MediaMetadata"""
        metadata = MediaMetadata(file_path=file_path, file_size=0)
        
        # Extract format info
        if 'format' in raw_metadata:
            fmt = raw_metadata['format']
            metadata.format = fmt.get('format_name', '').split(',')[0]
            metadata.duration = float(fmt.get('duration', 0))
            metadata.bitrate = int(fmt.get('bit_rate', 0))
            metadata.file_size = int(fmt.get('size', 0))
            
            # Extract dates from tags
            tags = fmt.get('tags', {})
            metadata.creation_date = self._parse_date(
                tags.get('creation_time') or tags.get('date')
            )
            
        # Extract stream info
        for stream in raw_metadata.get('streams', []):
            if stream.get('codec_type') == 'video':
                metadata.video_codec = self._normalize_codec(stream.get('codec_name'))
                metadata.resolution = (stream.get('width'), stream.get('height'))
                metadata.frame_rate = self._parse_framerate(stream.get('avg_frame_rate'))
                
            elif stream.get('codec_type') == 'audio':
                metadata.audio_codec = self._normalize_codec(stream.get('codec_name'))
                metadata.sample_rate = int(stream.get('sample_rate', 0))
                metadata.channels = int(stream.get('channels', 0))
                
        # Extract GPS and device info from tags
        self._extract_exif_data(raw_metadata, metadata)
        
        metadata.raw_json = raw_metadata
        return metadata
        
    def _normalize_codec(self, codec: str) -> str:
        """Convert codec names to readable format"""
        codec_map = {
            'h264': 'H.264/AVC',
            'hevc': 'H.265/HEVC',
            'aac': 'AAC',
            'mp3': 'MP3',
            # Add more mappings
        }
        return codec_map.get(codec, codec.upper() if codec else 'Unknown')
```

---

## Phase 3: Service Layer Implementation (2 hours)

### 3.1 Media Analysis Service

```python
# core/services/media_analysis_service.py
class MediaAnalysisService(BaseService, IMediaAnalysisService):
    """Service for media analysis operations"""
    
    def __init__(self):
        super().__init__("MediaAnalysisService")
        self.ffprobe_manager = FFProbeBinaryManager()
        self.ffprobe_wrapper = None
        self.normalizer = MetadataNormalizer()
        
        # Initialize FFprobe
        if self.ffprobe_manager.is_validated:
            self.ffprobe_wrapper = FFProbeWrapper(
                self.ffprobe_manager.binary_path
            )
    
    def validate_media_files(self, paths: List[Path]) -> Result[List[Path]]:
        """Validate and filter media files"""
        if not self.ffprobe_wrapper:
            return Result.error(
                MediaAnalysisError(
                    "FFprobe not available",
                    user_message="FFprobe is required but not found. Please install FFmpeg."
                )
            )
            
        valid_files = []
        for path in paths:
            if path.is_file():
                valid_files.append(path)
            elif path.is_dir():
                # Recursively find all files
                valid_files.extend(path.rglob('*'))
                
        # Filter to actual files only
        valid_files = [f for f in valid_files if f.is_file()]
        
        if not valid_files:
            return Result.error(
                ValidationError(
                    {"paths": "No valid files found"},
                    user_message="No files found in the selected items."
                )
            )
            
        return Result.success(valid_files)
    
    def analyze_media_files(
        self,
        files: List[Path],
        settings: MediaAnalysisSettings,
        progress_callback: Optional[callable] = None
    ) -> Result[MediaAnalysisResult]:
        """Analyze media files with parallel processing"""
        start_time = time.time()
        
        # Extract metadata in parallel
        raw_results = self.ffprobe_wrapper.extract_batch(
            files,
            max_workers=settings.max_workers,
            progress_callback=progress_callback
        )
        
        # Normalize results
        metadata_list = []
        errors = []
        successful = 0
        failed = 0
        skipped = 0
        
        for file_path, extraction_result in raw_results.items():
            if extraction_result.success:
                try:
                    normalized = self.normalizer.normalize(
                        extraction_result.value,
                        file_path
                    )
                    
                    # Apply field filtering based on settings
                    filtered = self._apply_field_filter(normalized, settings)
                    metadata_list.append(filtered)
                    successful += 1
                    
                except Exception as e:
                    errors.append(f"{file_path.name}: {str(e)}")
                    failed += 1
            else:
                # Check if it's a non-media file (expected) or actual error
                if "Not a valid media file" in str(extraction_result.error):
                    skipped += 1
                    logger.debug(f"Skipped non-media: {file_path.name}")
                else:
                    errors.append(f"{file_path.name}: {extraction_result.error}")
                    failed += 1
        
        processing_time = time.time() - start_time
        
        result = MediaAnalysisResult(
            total_files=len(files),
            successful=successful,
            failed=failed,
            skipped=skipped,
            metadata_list=metadata_list,
            processing_time=processing_time,
            errors=errors[:100]  # Limit error list
        )
        
        return Result.success(result)
```

### 3.2 Service Registration

```python
# core/services/service_config.py
# Add to initialize_services():
register_service(IMediaAnalysisService, MediaAnalysisService())
```

---

## Phase 4: Controller Layer (1.5 hours)

### 4.1 Media Analysis Controller

```python
# controllers/media_analysis_controller.py
class MediaAnalysisController(BaseController):
    """Controller for media analysis operations"""
    
    def __init__(self):
        super().__init__("MediaAnalysisController")
        self.current_worker: Optional[MediaAnalysisWorker] = None
        
        # Service dependencies
        self._media_service = None
        self._report_service = None
        
    @property
    def media_service(self) -> IMediaAnalysisService:
        if self._media_service is None:
            self._media_service = self._get_service(IMediaAnalysisService)
        return self._media_service
    
    def start_analysis_workflow(
        self,
        paths: List[Path],
        settings: MediaAnalysisSettings,
        form_data: Optional[FormData] = None
    ) -> Result[MediaAnalysisWorker]:
        """Start media analysis workflow"""
        try:
            # Validate and prepare files
            validation_result = self.media_service.validate_media_files(paths)
            if not validation_result.success:
                return Result.error(validation_result.error)
            
            valid_files = validation_result.value
            
            # Create worker thread
            worker = MediaAnalysisWorker(
                files=valid_files,
                settings=settings,
                service=self.media_service,
                form_data=form_data
            )
            
            self.current_worker = worker
            return Result.success(worker)
            
        except Exception as e:
            error = MediaAnalysisError(
                f"Failed to start analysis: {e}",
                user_message="Failed to start media analysis."
            )
            self._handle_error(error)
            return Result.error(error)
    
    def generate_report(
        self,
        results: MediaAnalysisResult,
        output_path: Path,
        form_data: FormData
    ) -> Result[Path]:
        """Generate PDF report from results"""
        return self.media_service.generate_analysis_report(
            results, output_path, form_data
        )
```

---

## Phase 5: Worker Thread Implementation (1.5 hours)

### 5.1 Media Analysis Worker

```python
# core/workers/media_analysis_worker.py
class MediaAnalysisWorker(BaseWorkerThread):
    """Worker thread for media analysis operations"""
    
    def __init__(
        self,
        files: List[Path],
        settings: MediaAnalysisSettings,
        service: IMediaAnalysisService,
        form_data: Optional[FormData] = None
    ):
        super().__init__()
        self.files = files
        self.settings = settings
        self.service = service
        self.form_data = form_data
        
        self.set_operation_name(f"Media Analysis ({len(files)} files)")
        
    def execute(self) -> Result[MediaAnalysisResult]:
        """Execute media analysis"""
        try:
            # Check for cancellation
            self.check_cancellation()
            
            # Progress callback for service
            def progress_callback(completed: int, total: int):
                percentage = int((completed / total) * 100)
                self.emit_progress(
                    percentage,
                    f"Analyzed {completed}/{total} files"
                )
                # Check for pause/cancel
                self.check_pause()
                if self.is_cancelled():
                    raise InterruptedError("Operation cancelled")
            
            # Perform analysis
            self.emit_progress(5, "Starting media analysis...")
            
            result = self.service.analyze_media_files(
                self.files,
                self.settings,
                progress_callback=progress_callback
            )
            
            if result.success:
                self.emit_progress(100, "Analysis complete")
                
            return result
            
        except InterruptedError:
            error = MediaAnalysisError(
                "Operation cancelled by user",
                user_message="Media analysis was cancelled."
            )
            return Result.error(error)
            
        except Exception as e:
            error = MediaAnalysisError(
                f"Analysis failed: {e}",
                user_message="An error occurred during media analysis."
            )
            self.handle_error(error)
            return Result.error(error)
```

---

## Phase 6: UI Implementation (2 hours)

### 6.1 Media Analysis Tab

```python
# ui/tabs/media_analysis_tab.py
class MediaAnalysisTab(QWidget):
    """Tab for media file analysis operations"""
    
    # Signals
    log_message = Signal(str)
    status_message = Signal(str)
    
    def __init__(self, controller: MediaAnalysisController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.current_worker = None
        self.last_results = None
        
        self._create_ui()
        self._connect_signals()
        
    def _create_ui(self):
        """Create two-column layout like Copy & Verify"""
        layout = QVBoxLayout(self)
        
        # Header
        header = self._create_header()
        layout.addWidget(header)
        
        # Main content splitter
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - File selection
        left_panel = self._create_file_panel()
        main_splitter.addWidget(left_panel)
        
        # Right panel - Settings and progress
        right_panel = self._create_settings_panel()
        main_splitter.addWidget(right_panel)
        
        main_splitter.setSizes([450, 550])
        layout.addWidget(main_splitter)
        
        # Console
        console = self._create_console()
        layout.addWidget(console)
        
    def _create_settings_panel(self) -> QGroupBox:
        """Create metadata settings panel"""
        panel = QGroupBox("Metadata Settings")
        layout = QVBoxLayout(panel)
        
        # Field groups with checkboxes
        self.field_groups = {}
        
        # General fields
        general_group = QGroupBox("General Information")
        general_layout = QVBoxLayout(general_group)
        self.field_groups['general'] = {
            'group_check': QCheckBox("Enable All"),
            'fields': {
                'format': QCheckBox("Format/Container"),
                'duration': QCheckBox("Duration"),
                'size': QCheckBox("File Size"),
                'bitrate': QCheckBox("Bitrate")
            }
        }
        # Add checkboxes to layout...
        
        # Video fields
        video_group = QGroupBox("Video Stream")
        # Similar setup...
        
        # File reference format
        format_group = QGroupBox("Display Options")
        format_layout = QVBoxLayout(format_group)
        
        self.path_format = QComboBox()
        self.path_format.addItems([
            "Full Path",
            "Parent Folder + Name",
            "Filename Only"
        ])
        format_layout.addWidget(QLabel("File Reference:"))
        format_layout.addWidget(self.path_format)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.analyze_btn = QPushButton("🔍 Analyze Files")
        self.analyze_btn.setEnabled(False)
        button_layout.addWidget(self.analyze_btn)
        
        self.export_btn = QPushButton("📄 Export Report")
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)
        
        self.cancel_btn = QPushButton("🛑 Cancel")
        self.cancel_btn.setEnabled(False)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
        return panel
```

### 6.2 Settings Panel Component

```python
# ui/components/metadata_settings_panel.py
class MetadataSettingsPanel(QWidget):
    """Reusable panel for metadata field selection"""
    
    settings_changed = Signal(MediaAnalysisSettings)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._create_ui()
        self._load_settings()
        
    def get_settings(self) -> MediaAnalysisSettings:
        """Get current settings configuration"""
        # Build MediaAnalysisSettings from UI state
        
    def _save_settings(self):
        """Persist settings to QSettings"""
        settings = QSettings()
        settings.beginGroup("MediaAnalysis")
        # Save field states...
```

---

## Phase 7: Report Generation (1 hour)

### 7.1 PDF Report Generator

```python
# core/media/media_report_generator.py
class MediaReportGenerator:
    """Generates PDF reports for media analysis"""
    
    def generate_report(
        self,
        results: MediaAnalysisResult,
        output_path: Path,
        form_data: Optional[FormData] = None
    ) -> Result[Path]:
        """Generate professional PDF report"""
        try:
            from core.pdf_gen import PDFGenerator
            
            pdf = PDFGenerator()
            
            # Add header with case info
            if form_data:
                pdf.add_case_header(form_data)
            
            # Summary section
            pdf.add_summary({
                'Total Files': results.total_files,
                'Media Files': results.successful,
                'Non-Media': results.skipped,
                'Failed': results.failed,
                'Processing Time': f"{results.processing_time:.1f} seconds"
            })
            
            # Metadata table for each file
            for metadata in results.metadata_list:
                pdf.add_media_entry(metadata)
            
            # Save PDF
            pdf.save(output_path)
            
            return Result.success(output_path)
            
        except Exception as e:
            return Result.error(
                ReportGenerationError(f"Failed to generate report: {e}")
            )
```

---

## Phase 8: Integration & Testing (1 hour)

### 8.1 MainWindow Integration

```python
# ui/main_window.py
# In __init__():
self.media_analysis_controller = MediaAnalysisController()

# In _setup_ui():
self.media_analysis_tab = MediaAnalysisTab(
    self.media_analysis_controller,
    self
)
self.media_analysis_tab.log_message.connect(self.log)
self.tabs.addTab(self.media_analysis_tab, "Media Analysis")
```

### 8.2 Unit Tests

```python
# tests/test_media_analysis.py
class TestMediaAnalysisService(unittest.TestCase):
    def setUp(self):
        self.service = MediaAnalysisService()
        
    def test_ffprobe_detection(self):
        """Test FFprobe binary is found"""
        
    def test_metadata_extraction(self):
        """Test metadata extraction from sample file"""
        
    def test_parallel_processing(self):
        """Test batch processing performance"""
        
    def test_non_media_handling(self):
        """Test graceful handling of non-media files"""
```

---

## Performance Optimizations

### Threading Strategy
Based on research, optimal configuration:
```python
max_workers = min(32, (os.cpu_count() or 1) + 4)
```

### Selective Field Extraction
Only request needed fields from FFprobe:
```python
'-show_entries', 'format=duration,size,bit_rate',
'-show_entries', 'stream=codec_name,width,height'
```

### Progress Optimization
- Update progress every 5-10 files, not every file
- Use throttled updates to prevent UI flooding

---

## Error Handling Strategy

### Exception Hierarchy
```python
class MediaAnalysisError(FSAError):
    """Base for media analysis errors"""
    
class FFProbeNotFoundError(MediaAnalysisError):
    """FFprobe binary not available"""
    
class MediaExtractionError(MediaAnalysisError):
    """Failed to extract metadata"""
    
class MediaReportError(MediaAnalysisError):
    """Failed to generate report"""
```

### Graceful Degradation
1. If FFprobe not found → Show clear message with installation instructions
2. If file times out → Skip and continue with next
3. If JSON parse fails → Log and skip file
4. If report fails → Still provide CSV export option

---

## Binary Distribution

### Windows
- Bundle `ffprobe.exe` in `bin/` directory
- ~50MB file size
- Download from: https://ffmpeg.org/download.html

### Linux/Mac
- Check system installation first
- Fallback to bundled if needed
- Provide installation command in error message

---

## Success Criteria

✅ **Phase 1 Complete When**:
- FFprobe binary detected and validated
- Service interfaces defined
- Data models created

✅ **Phase 2 Complete When**:
- FFprobe wrapper extracts metadata
- Parallel processing works
- Metadata normalized correctly

✅ **Phase 3 Complete When**:
- Service validates files
- Analysis completes successfully
- Results properly structured

✅ **Phase 4 Complete When**:
- Controller orchestrates workflow
- Proper error handling
- Service integration works

✅ **Phase 5 Complete When**:
- Worker thread processes files
- Progress updates work
- Cancellation supported

✅ **Phase 6 Complete When**:
- UI displays properly
- Settings persist
- User can select files and options

✅ **Phase 7 Complete When**:
- PDF reports generate
- Format is professional
- All metadata displayed correctly

✅ **Phase 8 Complete When**:
- Tab appears in MainWindow
- All signals connected
- Tests pass

---

## Implementation Checklist

- [ ] Download and place ffprobe.exe in bin/
- [ ] Create FFProbeBinaryManager
- [ ] Define IMediaAnalysisService interface
- [ ] Create data models
- [ ] Implement FFProbeWrapper
- [ ] Create MetadataNormalizer
- [ ] Implement MediaAnalysisService
- [ ] Register service in ServiceRegistry
- [ ] Create MediaAnalysisController
- [ ] Implement MediaAnalysisWorker
- [ ] Build MediaAnalysisTab UI
- [ ] Create MetadataSettingsPanel
- [ ] Implement MediaReportGenerator
- [ ] Integrate with MainWindow
- [ ] Write unit tests
- [ ] Test with various media formats
- [ ] Performance testing with 100+ files
- [ ] Error handling verification
- [ ] Documentation update

---

## Conclusion

This implementation plan provides a complete roadmap for adding Media Analysis functionality while maintaining full SOA compliance. The architecture leverages proven patterns from the existing codebase, incorporates performance optimizations from research, and ensures professional-grade error handling and reporting.

The modular design allows for incremental implementation and testing, with clear success criteria for each phase. Following this plan will result in a robust, maintainable feature that enhances the application's forensic capabilities.

---

*Implementation Plan Version: 2.0*  
*Architecture Pattern: Full SOA Compliance*  
*Estimated Time: 10-12 hours*  
*Risk Level: Low (follows established patterns)*