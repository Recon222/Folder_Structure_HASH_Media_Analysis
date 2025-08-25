#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Path utilities for sanitization and forensic structure building
"""

import re
import unicodedata
import platform
from pathlib import Path
from typing import Optional


class PathSanitizer:
    """Comprehensive path sanitization for cross-platform compatibility"""
    
    # Platform-specific invalid characters
    INVALID_CHARS = {
        'windows': '<>:"|?*',
        'posix': '',
        'universal': ''
    }
    
    # Control characters (0x00-0x1f) are invalid on all platforms
    CONTROL_CHARS = ''.join(chr(i) for i in range(32))
    
    # Windows reserved names
    RESERVED_NAMES = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 
        'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5',
        'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    @staticmethod
    def get_platform() -> str:
        """Detect current platform for appropriate sanitization
        
        Returns:
            'windows', 'posix', or 'universal'
        """
        system = platform.system().lower()
        if system == 'windows':
            return 'windows'
        elif system in ('linux', 'darwin'):
            return 'posix'
        else:
            return 'universal'
    
    @staticmethod
    def sanitize_component(text: str, platform_type: Optional[str] = None) -> str:
        """Sanitize a single path component for filesystem safety
        
        Args:
            text: Path component to sanitize
            platform_type: Target platform ('windows', 'posix', 'universal')
                         If None, auto-detects current platform
        
        Returns:
            Sanitized path component safe for filesystem use
        """
        if not text:
            return '_'
        
        # Auto-detect platform if not specified
        if platform_type is None:
            platform_type = PathSanitizer.get_platform()
        
        # Unicode normalization (NFKC = compatibility decomposition + canonical composition)
        # This prevents Unicode tricks and ensures consistent representation
        text = unicodedata.normalize('NFKC', text)
        
        # Remove null bytes and control characters (always invalid)
        for char in PathSanitizer.CONTROL_CHARS:
            text = text.replace(char, '')
        
        # Remove platform-specific invalid characters
        invalid_chars = PathSanitizer.INVALID_CHARS.get(platform_type, '')
        for char in invalid_chars:
            text = text.replace(char, '_')
        
        # Remove path separators (prevent directory traversal)
        text = text.replace('/', '_').replace('\\', '_')
        
        # Handle Windows reserved names
        if platform_type == 'windows':
            # Check base name without extension
            parts = text.split('.')
            base_name = parts[0].upper()
            if base_name in PathSanitizer.RESERVED_NAMES:
                # Prefix with underscore to make it safe
                parts[0] = f'_{parts[0]}'
                text = '.'.join(parts)
        
        # Remove leading/trailing dots and spaces (Windows doesn't like these)
        text = text.strip('. ')
        
        # Handle length limits (255 chars for most filesystems)
        if len(text) > 255:
            # Try to preserve file extension if present
            if '.' in text:
                # Find the last dot for extension
                name_part, ext_part = text.rsplit('.', 1)
                # Ensure extension isn't too long either
                if len(ext_part) <= 50:  # Reasonable extension length
                    max_name_len = 254 - len(ext_part)
                    text = f"{name_part[:max_name_len]}.{ext_part}"
                else:
                    text = text[:255]
            else:
                text = text[:255]
        
        # Ensure not empty after sanitization
        if not text or text == '.':
            text = '_'
        
        return text
    
    @staticmethod
    def validate_destination(destination: Path, base: Path) -> Path:
        """Validate that a destination path stays within base directory bounds
        
        Args:
            destination: Proposed destination path
            base: Base directory that should contain destination
        
        Returns:
            Resolved destination path
            
        Raises:
            ValueError: If destination escapes base directory (security risk)
        """
        try:
            # Resolve to absolute paths
            dest_resolved = destination.resolve()
            base_resolved = base.resolve()
            
            # Ensure destination is within base
            try:
                # This will raise ValueError if dest is not relative to base
                dest_resolved.relative_to(base_resolved)
            except ValueError:
                raise ValueError(
                    f"Security violation: Destination '{destination}' "
                    f"escapes base directory '{base}'"
                )
            
            return dest_resolved
            
        except Exception as e:
            raise ValueError(f"Invalid destination path: {e}")
    
    @staticmethod
    def sanitize_path(path: Path, platform_type: Optional[str] = None) -> Path:
        """Sanitize an entire path, component by component
        
        Args:
            path: Path to sanitize
            platform_type: Target platform
        
        Returns:
            Sanitized path
        """
        parts = []
        for part in path.parts:
            # Skip root/drive components
            if part in ('/', '\\') or (len(part) == 2 and part[1] == ':'):
                parts.append(part)
            else:
                parts.append(PathSanitizer.sanitize_component(part, platform_type))
        
        return Path(*parts) if parts else Path('_')


class ForensicPathBuilder:
    """Build forensic folder structures without side effects"""
    
    @staticmethod
    def build_relative_path(form_data) -> Path:
        """Build relative forensic path without creating directories
        
        Args:
            form_data: FormData instance with case information
        
        Returns:
            Relative path for forensic structure
        """
        from core.models import FormData
        
        # Ensure we have valid form data
        if not isinstance(form_data, FormData):
            raise TypeError("form_data must be a FormData instance")
        
        # Get sanitizer for current platform
        sanitizer = PathSanitizer()
        platform_type = sanitizer.get_platform()
        
        # Sanitize occurrence number
        occurrence = sanitizer.sanitize_component(
            form_data.occurrence_number or "NO_OCCURRENCE",
            platform_type
        )
        
        # Build location component (Business @ Location format)
        business = form_data.business_name or ""
        location = form_data.location_address or ""
        
        if business and location:
            location_part = f"{business} @ {location}"
        elif business:
            location_part = business
        elif location:
            location_part = location
        else:
            location_part = "NO_LOCATION"
        
        location_part = sanitizer.sanitize_component(location_part, platform_type)
        
        # Helper function to convert to military date format
        def to_military_format(dt):
            """Convert datetime or QDateTime to military format: DDMMMYY_HHMM"""
            if not dt:
                return ""
            months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                     'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
            
            # Handle both QDateTime and regular datetime objects
            if hasattr(dt, 'toString'):  # QDateTime
                month_idx = dt.date().month() - 1
                return f"{dt.date().day()}{months[month_idx]}{dt.toString('yy')}_{dt.toString('HHmm')}"
            else:  # Regular datetime
                month_idx = dt.month - 1
                return f"{dt.day}{months[month_idx]}{dt.strftime('%y')}_{dt.strftime('%H%M')}"
        
        # Build date range component
        if hasattr(form_data, 'video_start_datetime') and form_data.video_start_datetime:
            # Use military format for law enforcement
            start_date = to_military_format(form_data.video_start_datetime)
            
            if hasattr(form_data, 'video_end_datetime') and form_data.video_end_datetime:
                end_date = to_military_format(form_data.video_end_datetime)
            else:
                end_date = start_date
            
            date_part = f"{start_date}_to_{end_date}_DVR_Time"
        else:
            # Fallback if no dates available
            from datetime import datetime
            now = datetime.now()
            date_part = now.strftime("%Y-%m-%d_%H%M%S")
        
        date_part = sanitizer.sanitize_component(date_part, platform_type)
        
        # Build complete relative path
        return Path(occurrence) / location_part / date_part
    
    @staticmethod
    def build_forensic_path(base: Path, form_data) -> Path:
        """Build complete forensic path (base + relative)
        
        Args:
            base: Base output directory
            form_data: FormData instance
        
        Returns:
            Complete path (not created)
        """
        relative = ForensicPathBuilder.build_relative_path(form_data)
        return base / relative
    
    @staticmethod
    def ensure_directory(base: Path, relative: Path) -> Path:
        """Create directory structure safely
        
        Args:
            base: Base directory
            relative: Relative path to create
        
        Returns:
            Created directory path
            
        Raises:
            ValueError: If path would escape base directory
        """
        # Validate path stays within bounds
        full_path = base / relative
        validated = PathSanitizer.validate_destination(full_path, base)
        
        # Create directory structure
        validated.mkdir(parents=True, exist_ok=True)
        
        return validated
    
    @staticmethod
    def create_forensic_structure(base: Path, form_data) -> Path:
        """Build and create complete forensic directory structure
        
        Args:
            base: Base output directory
            form_data: FormData instance
        
        Returns:
            Created directory path
        """
        relative = ForensicPathBuilder.build_relative_path(form_data)
        return ForensicPathBuilder.ensure_directory(base, relative)