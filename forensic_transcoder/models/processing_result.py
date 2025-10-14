"""
Processing result data model.

Tracks the outcome, timing, and statistics of video processing operations.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ProcessingStatus(Enum):
    """Processing operation status."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    IN_PROGRESS = "in_progress"


class ProcessingType(Enum):
    """Type of processing operation."""
    TRANSCODE = "transcode"
    CONCATENATE = "concatenate"
    ANALYSIS = "analysis"


@dataclass
class ProcessingResult:
    """
    Result of a video processing operation.
    
    Contains outcome status, timing information, file details, performance metrics,
    and any errors or warnings generated during processing.
    """
    
    # === Operation Info ===
    processing_type: ProcessingType
    input_file: Path
    output_file: Optional[Path] = None
    
    # === Status ===
    status: ProcessingStatus = ProcessingStatus.IN_PROGRESS
    
    # === Timing ===
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # === File Information ===
    input_size_bytes: Optional[int] = None
    output_size_bytes: Optional[int] = None
    compression_ratio: Optional[float] = None  # output_size / input_size
    
    # === Performance Metrics ===
    encoding_speed: Optional[float] = None  # Multiplier (e.g., 2.3x means 2.3x realtime)
    average_fps: Optional[float] = None  # Frames processed per second
    frames_processed: Optional[int] = None
    
    # === Error Handling ===
    error_message: Optional[str] = None
    error_code: Optional[int] = None
    error_details: Optional[str] = None  # Stack trace or detailed error info
    
    # === Warnings ===
    warnings: List[str] = field(default_factory=list)
    
    # === FFmpeg Command ===
    ffmpeg_command: Optional[str] = None  # The actual command that was executed
    ffmpeg_output: Optional[str] = None  # FFmpeg console output (for debugging)
    
    def __post_init__(self):
        """Ensure paths are Path objects."""
        if not isinstance(self.input_file, Path):
            self.input_file = Path(self.input_file)
        
        if self.output_file and not isinstance(self.output_file, Path):
            self.output_file = Path(self.output_file)
    
    def mark_complete(self, status: ProcessingStatus = ProcessingStatus.SUCCESS):
        """
        Mark the processing operation as complete.
        
        Args:
            status: Final status of the operation
        """
        self.status = status
        self.end_time = datetime.now()
        
        if self.start_time and self.end_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        
        # Calculate compression ratio if both sizes are available
        if (self.input_size_bytes and self.output_size_bytes and 
            self.input_size_bytes > 0):
            self.compression_ratio = self.output_size_bytes / self.input_size_bytes
    
    def mark_failed(self, error_message: str, error_code: Optional[int] = None):
        """
        Mark the operation as failed with error details.
        
        Args:
            error_message: Human-readable error description
            error_code: Optional numeric error code
        """
        self.status = ProcessingStatus.FAILED
        self.error_message = error_message
        self.error_code = error_code
        self.mark_complete(ProcessingStatus.FAILED)
    
    def mark_cancelled(self):
        """Mark the operation as cancelled by user."""
        self.status = ProcessingStatus.CANCELLED
        self.mark_complete(ProcessingStatus.CANCELLED)
    
    def add_warning(self, warning: str):
        """
        Add a warning message to the result.
        
        Args:
            warning: Warning message
        """
        self.warnings.append(warning)
    
    @property
    def is_success(self) -> bool:
        """Check if processing succeeded."""
        return self.status == ProcessingStatus.SUCCESS
    
    @property
    def is_failed(self) -> bool:
        """Check if processing failed."""
        return self.status == ProcessingStatus.FAILED
    
    @property
    def is_complete(self) -> bool:
        """Check if processing is complete (success, failed, or cancelled)."""
        return self.status in [
            ProcessingStatus.SUCCESS,
            ProcessingStatus.FAILED,
            ProcessingStatus.CANCELLED,
            ProcessingStatus.SKIPPED
        ]
    
    @property
    def duration_formatted(self) -> str:
        """Get formatted duration string (e.g., '00:02:34')."""
        if not self.duration_seconds:
            return "00:00:00"
        
        hours = int(self.duration_seconds // 3600)
        minutes = int((self.duration_seconds % 3600) // 60)
        seconds = int(self.duration_seconds % 60)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    @property
    def compression_percent(self) -> Optional[float]:
        """Get compression as percentage (e.g., 65.5 means output is 65.5% of input size)."""
        if self.compression_ratio is None:
            return None
        return self.compression_ratio * 100.0
    
    @property
    def size_saved_bytes(self) -> Optional[int]:
        """Get bytes saved by compression (negative if file grew)."""
        if self.input_size_bytes is None or self.output_size_bytes is None:
            return None
        return self.input_size_bytes - self.output_size_bytes
    
    def to_dict(self) -> dict:
        """Convert result to dictionary for serialization."""
        return {
            'processing_type': self.processing_type.value,
            'input_file': str(self.input_file),
            'output_file': str(self.output_file) if self.output_file else None,
            'status': self.status.value,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration_seconds,
            'input_size_bytes': self.input_size_bytes,
            'output_size_bytes': self.output_size_bytes,
            'compression_ratio': self.compression_ratio,
            'encoding_speed': self.encoding_speed,
            'average_fps': self.average_fps,
            'frames_processed': self.frames_processed,
            'error_message': self.error_message,
            'error_code': self.error_code,
            'error_details': self.error_details,
            'warnings': self.warnings,
            'ffmpeg_command': self.ffmpeg_command,
            'ffmpeg_output': self.ffmpeg_output,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ProcessingResult':
        """Create result from dictionary."""
        # Convert enum strings back to enums
        if 'processing_type' in data:
            data['processing_type'] = ProcessingType(data['processing_type'])
        if 'status' in data:
            data['status'] = ProcessingStatus(data['status'])
        
        # Convert datetime strings back to datetime objects
        if 'start_time' in data and data['start_time']:
            data['start_time'] = datetime.fromisoformat(data['start_time'])
        if 'end_time' in data and data['end_time']:
            data['end_time'] = datetime.fromisoformat(data['end_time'])
        
        # Convert path strings back to Path objects
        if 'input_file' in data:
            data['input_file'] = Path(data['input_file'])
        if 'output_file' in data and data['output_file']:
            data['output_file'] = Path(data['output_file'])
        
        return cls(**data)


@dataclass
class BatchProcessingStatistics:
    """
    Statistics for batch processing operations.
    
    Aggregates results from multiple processing operations to provide
    overall success rates, timing, and performance metrics.
    """
    
    total_files: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    cancelled: int = 0
    
    total_duration_seconds: float = 0.0
    total_input_size_bytes: int = 0
    total_output_size_bytes: int = 0
    
    results: List[ProcessingResult] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_files == 0:
            return 0.0
        return (self.successful / self.total_files) * 100.0
    
    @property
    def average_compression_ratio(self) -> Optional[float]:
        """Calculate average compression ratio across all files."""
        if self.total_input_size_bytes == 0:
            return None
        return self.total_output_size_bytes / self.total_input_size_bytes
    
    @property
    def average_duration_seconds(self) -> float:
        """Calculate average processing time per file."""
        if self.successful == 0:
            return 0.0
        return self.total_duration_seconds / self.successful
    
    @property
    def total_size_saved_bytes(self) -> int:
        """Calculate total bytes saved across all files."""
        return self.total_input_size_bytes - self.total_output_size_bytes
    
    def add_result(self, result: ProcessingResult):
        """
        Add a processing result to the statistics.
        
        Args:
            result: ProcessingResult to add
        """
        self.results.append(result)
        self.total_files += 1
        
        if result.status == ProcessingStatus.SUCCESS:
            self.successful += 1
        elif result.status == ProcessingStatus.FAILED:
            self.failed += 1
        elif result.status == ProcessingStatus.SKIPPED:
            self.skipped += 1
        elif result.status == ProcessingStatus.CANCELLED:
            self.cancelled += 1
        
        if result.duration_seconds:
            self.total_duration_seconds += result.duration_seconds
        
        if result.input_size_bytes:
            self.total_input_size_bytes += result.input_size_bytes
        
        if result.output_size_bytes:
            self.total_output_size_bytes += result.output_size_bytes
    
    def to_dict(self) -> dict:
        """Convert statistics to dictionary."""
        return {
            'total_files': self.total_files,
            'successful': self.successful,
            'failed': self.failed,
            'skipped': self.skipped,
            'cancelled': self.cancelled,
            'success_rate': self.success_rate,
            'total_duration_seconds': self.total_duration_seconds,
            'average_duration_seconds': self.average_duration_seconds,
            'total_input_size_bytes': self.total_input_size_bytes,
            'total_output_size_bytes': self.total_output_size_bytes,
            'average_compression_ratio': self.average_compression_ratio,
            'total_size_saved_bytes': self.total_size_saved_bytes,
            'results': [r.to_dict() for r in self.results],
        }
