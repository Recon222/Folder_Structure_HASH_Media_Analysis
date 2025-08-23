#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Centralized settings management with migration support
"""

from typing import Any, Optional
from pathlib import Path
from PySide6.QtCore import QSettings


class SettingsManager:
    """Centralized settings management with migration support"""
    
    # Canonical keys for all settings
    KEYS = {
        # Forensic settings
        'CALCULATE_HASHES': 'forensic.calculate_hashes',
        'HASH_ALGORITHM': 'forensic.hash_algorithm',
        
        # Performance settings
        'COPY_BUFFER_SIZE': 'performance.copy_buffer_size',
        'USE_BUFFERED_OPS': 'performance.use_buffered_operations',
        
        # Archive settings
        'ZIP_COMPRESSION_LEVEL': 'archive.compression_level',
        'ZIP_ENABLED': 'archive.zip_enabled',
        'ZIP_LEVEL': 'archive.zip_level',
        
        # User settings
        'TECHNICIAN_NAME': 'user.technician_name',
        'BADGE_NUMBER': 'user.badge_number',
        
        # Report settings
        'TIME_OFFSET_PDF': 'reports.generate_time_offset',
        'UPLOAD_LOG_PDF': 'reports.generate_upload_log',
        'HASH_CSV': 'reports.generate_hash_csv',
        
        # UI settings
        'AUTO_SCROLL_LOG': 'ui.auto_scroll_log',
        'CONFIRM_EXIT': 'ui.confirm_exit_with_operations',
        
        # Debug settings
        'DEBUG_LOGGING': 'debug.enable_logging',
        
        # Path settings
        'LAST_OUTPUT_DIR': 'paths.last_output_directory',
        'LAST_INPUT_DIR': 'paths.last_input_directory'
    }
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern for settings manager"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize settings manager"""
        if self._initialized:
            return
        
        self._initialized = True
        self._settings = QSettings('FolderStructureUtility', 'Settings')
        
        # Set defaults on initialization
        self._set_defaults()
    
    def _set_defaults(self):
        """Set default values for missing keys"""
        defaults = {
            self.KEYS['CALCULATE_HASHES']: True,
            self.KEYS['HASH_ALGORITHM']: 'sha256',
            self.KEYS['COPY_BUFFER_SIZE']: 1048576,  # 1MB default
            self.KEYS['USE_BUFFERED_OPS']: True,  # Default to new high-performance system
            self.KEYS['ZIP_COMPRESSION_LEVEL']: 6,
            self.KEYS['ZIP_ENABLED']: 'enabled',
            self.KEYS['ZIP_LEVEL']: 'root',
            self.KEYS['TIME_OFFSET_PDF']: True,
            self.KEYS['UPLOAD_LOG_PDF']: True,
            self.KEYS['HASH_CSV']: True,
            self.KEYS['DEBUG_LOGGING']: False,
            self.KEYS['AUTO_SCROLL_LOG']: True,
            self.KEYS['CONFIRM_EXIT']: True,
            self.KEYS['TECHNICIAN_NAME']: '',
            self.KEYS['BADGE_NUMBER']: ''
        }
        
        for key, default in defaults.items():
            if not self._settings.contains(key):
                self._settings.setValue(key, default)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get setting value with type preservation
        
        Args:
            key: Either a KEYS constant or direct key string
            default: Default value if key not found
            
        Returns:
            Setting value or default
        """
        # Convert to canonical key if using constant
        canonical_key = self.KEYS.get(key, key)
        return self._settings.value(canonical_key, default)
    
    def set(self, key: str, value: Any):
        """Set setting value
        
        Args:
            key: Either a KEYS constant or direct key string
            value: Value to set
        """
        canonical_key = self.KEYS.get(key, key)
        self._settings.setValue(canonical_key, value)
    
    def sync(self):
        """Force settings to disk"""
        self._settings.sync()
    
    def contains(self, key: str) -> bool:
        """Check if settings contains key
        
        Args:
            key: Either a KEYS constant or direct key string
            
        Returns:
            True if key exists
        """
        canonical_key = self.KEYS.get(key, key)
        return self._settings.contains(canonical_key)
    
    # Convenience properties for common settings
    @property
    def calculate_hashes(self) -> bool:
        """Whether to calculate file hashes"""
        return bool(self.get('CALCULATE_HASHES', True))
    
    @property
    def hash_algorithm(self) -> str:
        """Hash algorithm to use (sha256 or md5)"""
        algorithm = str(self.get('HASH_ALGORITHM', 'sha256')).lower()
        # Validate algorithm
        if algorithm not in ['sha256', 'md5']:
            return 'sha256'  # Safe fallback
        return algorithm
    
    @hash_algorithm.setter
    def hash_algorithm(self, value: str):
        """Set hash algorithm
        
        Args:
            value: Algorithm name ('sha256' or 'md5')
        """
        algorithm = str(value).lower()
        if algorithm not in ['sha256', 'md5']:
            raise ValueError(f"Unsupported hash algorithm: {value}. Must be 'sha256' or 'md5'")
        self.set('HASH_ALGORITHM', algorithm)
    
    @property
    def copy_buffer_size(self) -> int:
        """Buffer size for file copying (clamped to reasonable range)"""
        raw_value = self.get('COPY_BUFFER_SIZE', 1048576)
        # Handle if it's stored in KB (legacy) vs bytes
        if isinstance(raw_value, str):
            raw_value = int(raw_value)
        elif raw_value < 8192:  # Likely in KB if less than 8KB
            raw_value = raw_value * 1024  # Convert KB to bytes
        size = int(raw_value)
        # Clamp between 8KB and 10MB
        return min(max(size, 8192), 10485760)
    
    @property
    def use_buffered_operations(self) -> bool:
        """Whether to use high-performance buffered file operations"""
        return bool(self.get('USE_BUFFERED_OPS', True))
    
    @property
    def technician_name(self) -> str:
        """Technician name for reports"""
        return str(self.get('TECHNICIAN_NAME', ''))
    
    @property
    def badge_number(self) -> str:
        """Badge number for reports"""
        return str(self.get('BADGE_NUMBER', ''))
    
    @property
    def zip_compression_level(self) -> int:
        """ZIP compression level (0-9)"""
        level = int(self.get('ZIP_COMPRESSION_LEVEL', 6))
        return min(max(level, 0), 9)
    
    @property
    def zip_enabled(self) -> str:
        """ZIP creation behavior: 'enabled', 'disabled', or 'prompt'"""
        value = str(self.get('ZIP_ENABLED', 'enabled'))
        if value not in ['enabled', 'disabled', 'prompt']:
            return 'enabled'  # Safe fallback
        return value
    
    @property  
    def zip_level(self) -> str:
        """ZIP archive level: 'root', 'location', or 'datetime'"""
        value = str(self.get('ZIP_LEVEL', 'root'))
        if value not in ['root', 'location', 'datetime']:
            return 'root'  # Safe fallback
        return value
    
    @property
    def generate_time_offset_pdf(self) -> bool:
        """Whether to generate time offset PDF"""
        return bool(self.get('TIME_OFFSET_PDF', True))
    
    @property
    def generate_upload_log_pdf(self) -> bool:
        """Whether to generate upload log PDF"""
        return bool(self.get('UPLOAD_LOG_PDF', True))
    
    @property
    def generate_hash_csv(self) -> bool:
        """Whether to generate hash CSV (only if hashes calculated)"""
        return bool(self.get('HASH_CSV', True)) and self.calculate_hashes
    
    @property
    def auto_scroll_log(self) -> bool:
        """Whether to auto-scroll log console"""
        return bool(self.get('AUTO_SCROLL_LOG', True))
    
    @property
    def confirm_exit_with_operations(self) -> bool:
        """Whether to confirm exit when operations are active"""
        return bool(self.get('CONFIRM_EXIT', True))
    
    @property
    def debug_logging(self) -> bool:
        """Whether debug logging is enabled"""
        return bool(self.get('DEBUG_LOGGING', False))
    
    @property
    def last_output_directory(self) -> Optional[Path]:
        """Last used output directory"""
        path_str = self.get('LAST_OUTPUT_DIR', None)
        return Path(path_str) if path_str else None
    
    @property
    def last_input_directory(self) -> Optional[Path]:
        """Last used input directory"""
        path_str = self.get('LAST_INPUT_DIR', None)
        return Path(path_str) if path_str else None
    
    def set_last_output_directory(self, path: Path):
        """Set last output directory"""
        self.set('LAST_OUTPUT_DIR', str(path))
    
    def set_last_input_directory(self, path: Path):
        """Set last input directory"""
        self.set('LAST_INPUT_DIR', str(path))
    
    def reset_all_settings(self):
        """Reset all settings for beta testing
        
        This will clear all stored settings and restore defaults.
        Useful for beta testers who need to start fresh.
        """
        from core.logger import logger
        
        # Clear all settings
        self._settings.clear()
        self._settings.sync()
        
        # Restore defaults
        self._set_defaults()
        
        # Log the reset
        if 'logger' in locals():
            logger.info("All settings reset for beta testing")
        
        print("Settings reset successfully. All preferences have been restored to defaults.")


# Global settings instance
settings = SettingsManager()