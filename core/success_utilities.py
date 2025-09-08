#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Success Utilities - Generic helper functions for success message formatting.

This module contains ONLY truly generic utilities that multiple tabs might use.
It does NOT contain any operation-specific logic - that belongs in each tab's
success module.

These utilities are pure functions with no side effects or dependencies.
"""

from typing import Optional, Union
from pathlib import Path


class SuccessFormatters:
    """Generic formatting utilities for success messages."""
    
    @staticmethod
    def format_file_size(bytes_size: int) -> str:
        """
        Format bytes into human-readable size string.
        
        Args:
            bytes_size: Size in bytes
            
        Returns:
            Formatted string like "1.5 GB", "256 KB", etc.
        """
        if bytes_size == 0:
            return "0 bytes"
        
        # Calculate size in different units
        size_kb = bytes_size / 1024
        size_mb = size_kb / 1024
        size_gb = size_mb / 1024
        
        # Choose appropriate unit
        if size_gb >= 1:
            # Show GB with 2 decimal places
            return f"{size_gb:.2f} GB"
        elif size_mb >= 1:
            # Show MB with 1 decimal place
            return f"{size_mb:.1f} MB"
        elif size_kb >= 1:
            # Show KB with 1 decimal place
            return f"{size_kb:.1f} KB"
        else:
            # Show bytes for very small files
            return f"{bytes_size} bytes"
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """
        Format duration in seconds to human-readable string.
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Formatted string like "2.5 minutes", "45 seconds", "1.2 hours"
        """
        if seconds < 0.001:
            return "< 0.001 seconds"
        elif seconds < 1:
            return f"{seconds:.3f} seconds"
        elif seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} minutes"
        else:
            hours = seconds / 3600
            return f"{hours:.1f} hours"
    
    @staticmethod
    def format_speed(bytes_per_second: float) -> str:
        """
        Format transfer speed to human-readable string.
        
        Args:
            bytes_per_second: Speed in bytes per second
            
        Returns:
            Formatted string like "150.5 MB/s"
        """
        mb_per_second = bytes_per_second / (1024 * 1024)
        
        if mb_per_second >= 1000:
            gb_per_second = mb_per_second / 1024
            return f"{gb_per_second:.1f} GB/s"
        elif mb_per_second >= 1:
            return f"{mb_per_second:.1f} MB/s"
        else:
            kb_per_second = bytes_per_second / 1024
            return f"{kb_per_second:.1f} KB/s"
    
    @staticmethod
    def format_percentage(value: float, total: float) -> str:
        """
        Format a percentage with appropriate precision.
        
        Args:
            value: The numerator
            total: The denominator
            
        Returns:
            Formatted percentage string like "95.5%"
        """
        if total == 0:
            return "0%"
        
        percentage = (value / total) * 100
        
        # Use appropriate precision
        if percentage == 100:
            return "100%"
        elif percentage >= 10:
            return f"{percentage:.1f}%"
        else:
            return f"{percentage:.2f}%"
    
    @staticmethod
    def format_path(path: Union[str, Path], max_length: int = 60) -> str:
        """
        Format a file path for display, truncating if needed.
        
        Args:
            path: The path to format
            max_length: Maximum length before truncation
            
        Returns:
            Formatted path string, possibly truncated with ellipsis
        """
        path_str = str(path)
        
        if len(path_str) <= max_length:
            return path_str
        
        # Try to keep the filename visible
        path_obj = Path(path_str)
        filename = path_obj.name
        
        if len(filename) >= max_length - 3:
            # Even filename is too long
            return "..." + path_str[-(max_length - 3):]
        
        # Keep start of path and filename
        available = max_length - len(filename) - 3  # 3 for "..."
        if available > 10:
            return path_str[:available] + "..." + filename
        else:
            return "..." + path_str[-(max_length - 3):]
    
    @staticmethod
    def pluralize(count: int, singular: str, plural: Optional[str] = None) -> str:
        """
        Helper to pluralize words based on count.
        
        Args:
            count: The number of items
            singular: Singular form of the word
            plural: Optional plural form (if not regular)
            
        Returns:
            Properly pluralized string like "1 file" or "5 files"
        """
        if count == 1:
            return f"{count} {singular}"
        else:
            if plural:
                return f"{count} {plural}"
            else:
                # Simple pluralization
                return f"{count} {singular}s"
    
    @staticmethod
    def format_time_range(start_seconds: float, end_seconds: float) -> str:
        """
        Format a time range for display.
        
        Args:
            start_seconds: Start time in seconds
            end_seconds: End time in seconds
            
        Returns:
            Formatted range like "0.5s - 2.3s"
        """
        start_str = SuccessFormatters.format_duration(start_seconds)
        end_str = SuccessFormatters.format_duration(end_seconds)
        
        # Simplify if units are the same
        if "seconds" in start_str and "seconds" in end_str:
            start_val = start_str.replace(" seconds", "")
            end_val = end_str.replace(" seconds", "")
            return f"{start_val}s - {end_val}s"
        elif "minutes" in start_str and "minutes" in end_str:
            start_val = start_str.replace(" minutes", "")
            end_val = end_str.replace(" minutes", "")
            return f"{start_val}m - {end_val}m"
        else:
            return f"{start_str} - {end_str}"


class PerformanceFormatter:
    """Specialized formatter for performance metrics."""
    
    @staticmethod
    def format_throughput_summary(
        files: int,
        bytes_size: int,
        duration: float,
        peak_speed: Optional[float] = None
    ) -> list[str]:
        """
        Format a complete throughput summary.
        
        Args:
            files: Number of files processed
            bytes_size: Total bytes processed
            duration: Total duration in seconds
            peak_speed: Optional peak speed in bytes/second
            
        Returns:
            List of formatted summary lines
        """
        lines = []
        
        # File count
        lines.append(SuccessFormatters.pluralize(files, "file"))
        
        # Size
        if bytes_size > 0:
            lines.append(f"Size: {SuccessFormatters.format_file_size(bytes_size)}")
        
        # Duration
        if duration > 0:
            lines.append(f"Time: {SuccessFormatters.format_duration(duration)}")
            
            # Average speed
            if bytes_size > 0:
                avg_speed = bytes_size / duration
                lines.append(f"Average: {SuccessFormatters.format_speed(avg_speed)}")
            
            # Peak speed if different from average
            if peak_speed and peak_speed > 0:
                peak_str = SuccessFormatters.format_speed(peak_speed)
                if peak_str not in lines[-1]:  # Don't show if same as average
                    lines.append(f"Peak: {peak_str}")
        
        return lines
    
    @staticmethod
    def format_success_rate(successful: int, total: int) -> str:
        """
        Format a success rate message.
        
        Args:
            successful: Number of successful operations
            total: Total number of operations
            
        Returns:
            Formatted string like "Success rate: 95.5% (191/200)"
        """
        if total == 0:
            return "No operations performed"
        
        percentage = SuccessFormatters.format_percentage(successful, total)
        return f"Success rate: {percentage} ({successful}/{total})"


class MessageLineBuilder:
    """Helper for building consistent message lines."""
    
    @staticmethod
    def success_line(text: str) -> str:
        """Format a success line with checkmark."""
        return f"✓ {text}"
    
    @staticmethod
    def warning_line(text: str) -> str:
        """Format a warning line with warning symbol."""
        return f"⚠️ {text}"
    
    @staticmethod
    def error_line(text: str) -> str:
        """Format an error line with X symbol."""
        return f"✗ {text}"
    
    @staticmethod
    def info_line(text: str) -> str:
        """Format an info line with info symbol."""
        return f"ℹ️ {text}"
    
    @staticmethod
    def metric_line(label: str, value: str) -> str:
        """Format a metric line with consistent spacing."""
        return f"📊 {label}: {value}"
    
    @staticmethod
    def file_line(text: str) -> str:
        """Format a file-related line."""
        return f"📄 {text}"
    
    @staticmethod
    def folder_line(text: str) -> str:
        """Format a folder-related line."""
        return f"📁 {text}"
    
    @staticmethod
    def time_line(text: str) -> str:
        """Format a time-related line."""
        return f"⏱️ {text}"