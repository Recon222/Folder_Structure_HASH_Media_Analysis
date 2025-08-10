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
        
        # Archive settings
        'ZIP_COMPRESSION_LEVEL': 'archive.compression_level',
        'ZIP_AT_ROOT': 'archive.create_at_root',
        'ZIP_AT_LOCATION': 'archive.create_at_location',
        'ZIP_AT_DATETIME': 'archive.create_at_datetime',
        'AUTO_CREATE_ZIP': 'archive.auto_create',
        'PROMPT_FOR_ZIP': 'archive.prompt_user',
        
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
    
    # Legacy key mappings for migration
    LEGACY_MAPPINGS = {
        # Multiple variants of compression settings
        'zip_compression': 'archive.compression_level',
        'zip_compression_level': 'archive.compression_level',
        
        # Hash settings variants
        'generate_hash_csv': 'forensic.calculate_hashes',
        'calculate_hashes': 'forensic.calculate_hashes',
        'enable_hashing': 'forensic.calculate_hashes',
        
        # Buffer size variants
        'buffer_size': 'performance.copy_buffer_size',
        'copy_buffer_size': 'performance.copy_buffer_size',
        
        # ZIP settings variants
        'create_zip_at_root': 'archive.create_at_root',
        'create_zip_at_location': 'archive.create_at_location',
        'create_zip_at_datetime': 'archive.create_at_datetime',
        'auto_create_zip': 'archive.auto_create',
        'prompt_for_zip': 'archive.prompt_user',
        
        # Report settings variants
        'generate_time_offset': 'reports.generate_time_offset',
        'generate_upload_log': 'reports.generate_upload_log',
        'generate_csv': 'reports.generate_hash_csv',
        'generate_time_offset_pdf': 'reports.generate_time_offset',
        'generate_upload_log_pdf': 'reports.generate_upload_log',
        
        # Additional ZIP variants
        'zip_at_root': 'archive.create_at_root',
        'zip_at_location': 'archive.create_at_location', 
        'zip_at_datetime': 'archive.create_at_datetime',
        
        # UI settings variants
        'auto_scroll_log': 'ui.auto_scroll_log',
        'confirm_exit_with_operations': 'ui.confirm_exit_with_operations',
        
        # User settings variants
        'technician_name': 'user.technician_name',
        'badge_number': 'user.badge_number'
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
        
        # Perform migration on initialization
        self._migrate_legacy_keys()
        self._set_defaults()
    
    def _migrate_legacy_keys(self):
        """Migrate legacy keys to canonical format"""
        migrated_count = 0
        
        for old_key, new_key in self.LEGACY_MAPPINGS.items():
            if self._settings.contains(old_key):
                value = self._settings.value(old_key)
                self._settings.setValue(new_key, value)
                self._settings.remove(old_key)
                migrated_count += 1
        
        if migrated_count > 0:
            self._settings.sync()
            # Note: Can't use logger here due to circular dependency at initialization
            # This migration only happens once, so using print is acceptable
            import sys
            print(f"[SettingsManager] Migrated {migrated_count} legacy settings keys", file=sys.stderr)
    
    def _set_defaults(self):
        """Set default values for missing keys"""
        defaults = {
            self.KEYS['CALCULATE_HASHES']: True,
            self.KEYS['HASH_ALGORITHM']: 'sha256',
            self.KEYS['COPY_BUFFER_SIZE']: 1048576,  # 1MB default
            self.KEYS['ZIP_COMPRESSION_LEVEL']: 6,
            self.KEYS['ZIP_AT_ROOT']: False,
            self.KEYS['ZIP_AT_LOCATION']: False,
            self.KEYS['ZIP_AT_DATETIME']: False,
            self.KEYS['AUTO_CREATE_ZIP']: False,
            self.KEYS['PROMPT_FOR_ZIP']: True,
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
    
    def value(self, key: str, default: Any = None, type=None) -> Any:
        """Compatibility method for QSettings API
        
        Args:
            key: Settings key
            default: Default value if key not found
            type: Type hint for conversion (mimics QSettings API)
            
        Returns:
            Setting value or default
        """
        # Use the get method which handles canonical keys
        result = self.get(key, default)
        
        # Handle type conversion if specified (QSettings compatibility)
        if type is not None and result is not None:
            try:
                if type == bool:
                    # Handle string representations of booleans
                    if isinstance(result, str):
                        return result.lower() in ('true', '1', 'yes', 'on')
                    return bool(result)
                elif type == int:
                    return int(result)
                elif type == float:
                    return float(result)
                elif type == str:
                    return str(result)
                else:
                    return type(result)
            except (ValueError, TypeError):
                return default
        
        return result
    
    def setValue(self, key: str, value: Any):
        """Compatibility method for QSettings API
        
        Args:
            key: Settings key
            value: Value to set
        """
        self.set(key, value)
    
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
        """Hash algorithm to use"""
        return str(self.get('HASH_ALGORITHM', 'sha256'))
    
    @property
    def copy_buffer_size(self) -> int:
        """Buffer size for file copying (clamped to reasonable range)"""
        size = int(self.get('COPY_BUFFER_SIZE', 1048576))
        # Clamp between 8KB and 10MB
        return min(max(size, 8192), 10485760)
    
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
    def auto_create_zip(self) -> bool:
        """Whether to automatically create ZIP archives"""
        return bool(self.get('AUTO_CREATE_ZIP', False))
    
    @property
    def prompt_for_zip(self) -> bool:
        """Whether to prompt user for ZIP creation"""
        return bool(self.get('PROMPT_FOR_ZIP', True))
    
    @property
    def zip_at_root(self) -> bool:
        """Create ZIP at root level"""
        return bool(self.get('ZIP_AT_ROOT', False))
    
    @property
    def zip_at_location(self) -> bool:
        """Create ZIP at location level"""
        return bool(self.get('ZIP_AT_LOCATION', False))
    
    @property
    def zip_at_datetime(self) -> bool:
        """Create ZIP at datetime level"""
        return bool(self.get('ZIP_AT_DATETIME', False))
    
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


# Global settings instance
settings = SettingsManager()