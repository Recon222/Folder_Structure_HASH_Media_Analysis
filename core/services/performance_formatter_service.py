#!/usr/bin/env python3
"""
Performance formatter service - centralized performance data formatting and extraction
"""
from typing import Dict, Any, Optional, Tuple
import re
from datetime import timedelta

from .base_service import BaseService
from ..result_types import Result, FileOperationResult
from ..exceptions import FSAError


class IPerformanceFormatterService:
    """Interface for performance formatting operations"""
    
    def format_statistics(self, stats: Dict[str, Any]) -> str:
        """Format performance statistics for display"""
        raise NotImplementedError
    
    def extract_speed_from_message(self, message: str) -> Optional[float]:
        """Extract speed value from log message"""
        raise NotImplementedError
    
    def build_performance_summary(self, result: FileOperationResult) -> str:
        """Build comprehensive performance summary from result"""
        raise NotImplementedError
    
    def format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        raise NotImplementedError
    
    def format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        raise NotImplementedError
    
    def format_speed(self, speed_mbps: float) -> str:
        """Format transfer speed in human-readable format"""
        raise NotImplementedError


class PerformanceFormatterService(BaseService, IPerformanceFormatterService):
    """Service for formatting and extracting performance data"""
    
    def __init__(self):
        super().__init__("PerformanceFormatterService")
        
        # Regex patterns for speed extraction
        self._speed_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*MB/s')
        self._percentage_pattern = re.compile(r'(\d+)%')
    
    def format_statistics(self, stats: Dict[str, Any]) -> str:
        """
        Format performance statistics for display
        
        This extracts the formatting logic from MainWindow lines 392-414
        
        Args:
            stats: Dictionary containing performance statistics
                Expected keys: files_processed, total_size_mb, duration_seconds,
                             average_speed_mbps, peak_speed_mbps
        
        Returns:
            Formatted string for display
        """
        try:
            self._log_operation("format_statistics", f"Formatting {len(stats)} stats")
            
            if not stats:
                return "No performance statistics available"
            
            # Extract values with defaults
            files_count = stats.get('files_processed', 0)
            total_mb = stats.get('total_size_mb', 0)
            duration = stats.get('duration_seconds', 0)
            avg_speed = stats.get('average_speed_mbps', 0)
            peak_speed = stats.get('peak_speed_mbps', 0)
            
            # Format components
            parts = []
            
            # File count
            if files_count:
                file_text = "file" if files_count == 1 else "files"
                parts.append(f"{files_count} {file_text}")
            
            # Total size
            if total_mb > 0:
                size_str = self.format_size(int(total_mb * 1024 * 1024))
                parts.append(f"{size_str} processed")
            
            # Duration
            if duration > 0:
                duration_str = self.format_duration(duration)
                parts.append(f"in {duration_str}")
            
            # Speed metrics
            if avg_speed > 0:
                avg_str = self.format_speed(avg_speed)
                parts.append(f"at {avg_str} average")
            
            if peak_speed > 0 and peak_speed != avg_speed:
                peak_str = self.format_speed(peak_speed)
                parts.append(f"(peak: {peak_str})")
            
            # Join all parts
            if parts:
                summary = " ".join(parts)
                self._log_operation("statistics_formatted", f"Generated: {summary[:100]}...")
                return summary
            else:
                return "Operation completed"
                
        except Exception as e:
            self._log_operation("format_statistics_error", str(e), "warning")
            return "Performance statistics unavailable"
    
    def extract_speed_from_message(self, message: str) -> Optional[float]:
        """
        Extract speed value from log message
        
        This extracts the parsing logic from MainWindow lines 1017-1026
        
        Args:
            message: Log message potentially containing speed information
        
        Returns:
            Speed in MB/s if found, None otherwise
        """
        try:
            if not message or " @ " not in message:
                return None
            
            # Try to extract speed after @ symbol
            speed_part = message.split(" @ ")[1]
            
            # Look for MB/s pattern
            match = self._speed_pattern.search(speed_part)
            if match:
                speed = float(match.group(1))
                # Changed to debug to reduce terminal spam - speed is already shown in progress
                self._log_operation("speed_extracted", f"{speed} MB/s from message", "debug")
                return speed
            
            return None
            
        except Exception as e:
            self._log_operation("speed_extraction_error", str(e), "debug")
            return None
    
    def build_performance_summary(self, result: FileOperationResult) -> str:
        """
        Build comprehensive performance summary from result
        
        Args:
            result: FileOperationResult containing performance data
        
        Returns:
            Formatted performance summary string
        """
        try:
            self._log_operation("build_performance_summary", "Building summary from result")
            
            if not result or not result.success:
                return "No performance data available"
            
            # Extract performance metrics from result
            if hasattr(result, 'performance_metrics') and result.performance_metrics:
                metrics = result.performance_metrics
                
                # Build statistics dictionary
                stats = {
                    'files_processed': metrics.get('files_processed', 0),
                    'total_size_mb': metrics.get('total_size_mb', 0),
                    'duration_seconds': metrics.get('duration_seconds', 0),
                    'average_speed_mbps': metrics.get('average_speed_mbps', 0),
                    'peak_speed_mbps': metrics.get('peak_speed_mbps', 0)
                }
                
                return self.format_statistics(stats)
            
            # Fallback to basic result info
            if hasattr(result, 'value') and result.value:
                file_count = len(result.value) if isinstance(result.value, (list, dict)) else 1
                return f"{file_count} file(s) processed successfully"
            
            return "Operation completed successfully"
            
        except Exception as e:
            self._log_operation("build_summary_error", str(e), "warning")
            return "Performance summary unavailable"
    
    def format_duration(self, seconds: float) -> str:
        """
        Format duration in human-readable format
        
        Args:
            seconds: Duration in seconds
        
        Returns:
            Formatted duration string
        """
        try:
            if seconds < 1:
                return f"{seconds*1000:.0f}ms"
            elif seconds < 60:
                return f"{seconds:.1f}s"
            elif seconds < 3600:
                minutes = int(seconds // 60)
                secs = int(seconds % 60)
                return f"{minutes}m {secs}s"
            else:
                td = timedelta(seconds=int(seconds))
                hours = td.seconds // 3600
                minutes = (td.seconds % 3600) // 60
                return f"{hours}h {minutes}m"
                
        except Exception as e:
            self._log_operation("format_duration_error", str(e), "warning")
            return f"{seconds:.1f}s"
    
    def format_size(self, size_bytes: int) -> str:
        """
        Format file size in human-readable format
        
        Args:
            size_bytes: Size in bytes
        
        Returns:
            Formatted size string
        """
        try:
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024.0:
                    if unit == 'B':
                        return f"{size_bytes} {unit}"
                    else:
                        return f"{size_bytes:.2f} {unit}"
                size_bytes /= 1024.0
            
            return f"{size_bytes:.2f} PB"
            
        except Exception as e:
            self._log_operation("format_size_error", str(e), "warning")
            return f"{size_bytes} bytes"
    
    def format_speed(self, speed_mbps: float) -> str:
        """
        Format transfer speed in human-readable format
        
        Args:
            speed_mbps: Speed in MB/s
        
        Returns:
            Formatted speed string
        """
        try:
            if speed_mbps < 1:
                return f"{speed_mbps*1024:.0f} KB/s"
            elif speed_mbps < 1000:
                return f"{speed_mbps:.1f} MB/s"
            else:
                return f"{speed_mbps/1024:.2f} GB/s"
                
        except Exception as e:
            self._log_operation("format_speed_error", str(e), "warning")
            return f"{speed_mbps:.1f} MB/s"
    
    def extract_performance_from_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract performance data from operation results
        
        This consolidates performance extraction logic from MainWindow
        
        Args:
            results: Operation results dictionary
        
        Returns:
            Dictionary of performance statistics
        """
        try:
            self._log_operation("extract_performance", "Extracting from results")
            
            stats = {}
            
            # Look for _performance_stats entry
            if '_performance_stats' in results:
                stats.update(results['_performance_stats'])
            
            # Extract from individual file results
            file_count = 0
            total_size = 0
            
            for key, value in results.items():
                if isinstance(value, dict) and 'size' in value:
                    file_count += 1
                    total_size += value.get('size', 0)
            
            if file_count > 0:
                stats['files_processed'] = stats.get('files_processed', file_count)
                stats['total_size_mb'] = stats.get('total_size_mb', total_size / (1024 * 1024))
            
            self._log_operation("performance_extracted", f"Extracted {len(stats)} metrics")
            return stats
            
        except Exception as e:
            self._log_operation("extract_performance_error", str(e), "warning")
            return {}
    
    def parse_progress_message(self, message: str) -> Tuple[Optional[int], Optional[str], Optional[float]]:
        """
        Parse progress message to extract percentage, status, and speed
        
        Args:
            message: Progress message to parse
        
        Returns:
            Tuple of (percentage, status_text, speed_mbps)
        """
        try:
            percentage = None
            status = message
            speed = None
            
            # Extract percentage
            percent_match = self._percentage_pattern.search(message)
            if percent_match:
                percentage = int(percent_match.group(1))
            
            # Extract speed
            speed = self.extract_speed_from_message(message)
            
            # Extract status text (remove percentage and speed)
            status_text = message
            if percent_match:
                status_text = status_text.replace(percent_match.group(0), "").strip()
            if speed and " @ " in status_text:
                status_text = status_text.split(" @ ")[0].strip()
            
            return (percentage, status_text, speed)
            
        except Exception as e:
            self._log_operation("parse_progress_error", str(e), "debug")
            return (None, message, None)