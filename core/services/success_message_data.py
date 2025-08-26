#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Success Message Data - Type-safe data structures for success messages.

This module defines the data structures used to pass success message information
between business logic and UI components, maintaining clean separation of concerns.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime


@dataclass
class SuccessMessageData:
    """
    Type-safe container for success message data.
    
    This dataclass encapsulates all information needed to display a success message,
    separating the business logic of message construction from UI presentation.
    """
    
    title: str = "Operation Complete!"
    """Main dialog title (e.g., 'Forensic Processing Complete!')"""
    
    summary_lines: List[str] = field(default_factory=list)
    """List of summary lines to display (e.g., ['✓ Copied 4 files', '📊 Performance data'])"""
    
    output_location: Optional[str] = None
    """Output directory path for user reference"""
    
    details: Optional[str] = None
    """Additional details to display below main content"""
    
    celebration_emoji: str = "✅"
    """Emoji to display in dialog header"""
    
    performance_data: Optional[Dict[str, Any]] = None
    """Performance metrics for display formatting"""
    
    raw_data: Optional[Dict[str, Any]] = None
    """Raw operation data for advanced formatting"""
    
    def to_display_message(self) -> str:
        """
        Convert the message data to a formatted display string.
        
        Returns:
            Formatted string suitable for display in success dialog
        """
        if not self.summary_lines:
            return "Operation completed successfully!"
            
        return "\n".join(self.summary_lines)
    
    def has_performance_data(self) -> bool:
        """Check if performance data is available for display."""
        return (self.performance_data is not None and 
                len(self.performance_data) > 0)
    
    def get_performance_summary(self) -> str:
        """
        Format performance data into a readable summary.
        
        Returns:
            Formatted performance summary string
        """
        if not self.has_performance_data():
            return ""
            
        perf = self.performance_data
        lines = []
        
        # Add standard performance metrics
        if 'files_processed' in perf:
            lines.append(f"Files: {perf['files_processed']}")
        if 'total_size_mb' in perf:
            lines.append(f"Size: {perf['total_size_mb']:.1f} MB")
        if 'total_time_seconds' in perf:
            lines.append(f"Time: {perf['total_time_seconds']:.1f} seconds")
        if 'average_speed_mbps' in perf:
            lines.append(f"Average Speed: {perf['average_speed_mbps']:.1f} MB/s")
        if 'peak_speed_mbps' in perf:
            lines.append(f"Peak Speed: {perf['peak_speed_mbps']:.1f} MB/s")
        if 'mode' in perf:
            lines.append(f"Mode: {perf['mode']}")
            
        if lines:
            return "📊 Performance Summary:\n" + "\n".join(lines)
        return ""


@dataclass 
class QueueOperationData:
    """Data structure for queue save/load operation results."""
    
    operation_type: str  # 'save' or 'load'
    file_path: Path
    job_count: int
    file_size_bytes: int = 0
    duration_seconds: float = 0
    duplicate_jobs_skipped: int = 0
    
    def get_file_size_display(self) -> str:
        """Get human-readable file size."""
        if self.file_size_bytes == 0:
            return "Unknown size"
        
        size_kb = self.file_size_bytes / 1024
        if size_kb < 1024:
            return f"{size_kb:.1f} KB"
        else:
            size_mb = size_kb / 1024
            return f"{size_mb:.1f} MB"


@dataclass
class HashOperationData:
    """Data structure for hash verification operation results."""
    
    files_verified: int
    verification_time_seconds: float
    hash_algorithm: str = "SHA-256"
    csv_file_path: Optional[Path] = None
    failed_verifications: int = 0
    
    def get_success_rate(self) -> float:
        """Calculate hash verification success rate."""
        if self.files_verified == 0:
            return 0.0
        
        successful = self.files_verified - self.failed_verifications
        return (successful / self.files_verified) * 100


@dataclass
class BatchOperationData:
    """Data structure for batch processing operation results."""
    
    total_jobs: int
    successful_jobs: int
    failed_jobs: int
    processing_time_seconds: float = 0
    
    def get_success_rate(self) -> float:
        """Calculate batch processing success rate."""
        if self.total_jobs == 0:
            return 0.0
        return (self.successful_jobs / self.total_jobs) * 100
    
    @property
    def is_complete_success(self) -> bool:
        """Check if all jobs completed successfully."""
        return self.failed_jobs == 0 and self.successful_jobs == self.total_jobs


@dataclass
class EnhancedBatchOperationData:
    """Enhanced data structure for rich batch processing success messages."""
    
    # Job Summary (inherited from BatchOperationData)
    total_jobs: int
    successful_jobs: int
    failed_jobs: int
    processing_time_seconds: float = 0
    
    # Aggregate File Processing Data
    total_files_processed: int = 0
    total_bytes_processed: int = 0
    aggregate_speed_mbps: float = 0
    peak_speed_mbps: float = 0
    peak_speed_job_name: str = ""
    
    # Aggregate Report Data
    total_reports_generated: int = 0
    report_breakdown: Dict[str, int] = field(default_factory=dict)  # {"time_offset": 4, "technician_log": 3}
    total_report_size_bytes: int = 0
    
    # Aggregate ZIP Data
    total_zip_archives: int = 0
    total_zip_size_bytes: int = 0
    
    # Job-Level Details
    job_results: List[Dict[str, Any]] = field(default_factory=list)
    failed_job_summaries: List[str] = field(default_factory=list)
    
    # Output Information
    batch_output_directories: List[Path] = field(default_factory=list)
    batch_start_time: Optional[datetime] = None
    batch_end_time: Optional[datetime] = None
    
    def get_success_rate(self) -> float:
        """Calculate batch processing success rate."""
        if self.total_jobs == 0:
            return 0.0
        return (self.successful_jobs / self.total_jobs) * 100
    
    @property
    def is_complete_success(self) -> bool:
        """Check if all jobs completed successfully."""
        return self.failed_jobs == 0 and self.successful_jobs == self.total_jobs
    
    def get_total_size_gb(self) -> float:
        """Get total size processed in GB."""
        return self.total_bytes_processed / (1024**3) if self.total_bytes_processed > 0 else 0.0
    
    def get_total_zip_size_gb(self) -> float:
        """Get total ZIP size in GB."""
        return self.total_zip_size_bytes / (1024**3) if self.total_zip_size_bytes > 0 else 0.0
    
    def get_total_report_size_mb(self) -> float:
        """Get total report size in MB."""
        return self.total_report_size_bytes / (1024**2) if self.total_report_size_bytes > 0 else 0.0
    
    def get_processing_time_minutes(self) -> float:
        """Get processing time in minutes."""
        return self.processing_time_seconds / 60 if self.processing_time_seconds > 0 else 0.0