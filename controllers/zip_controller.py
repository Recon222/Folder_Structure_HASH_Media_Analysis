#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZIP Controller - handles all ZIP archive creation logic
"""

import zipfile
from pathlib import Path
from typing import Optional, Dict, Any

from core.settings_manager import SettingsManager
from core.workers.zip_operations import ZipOperationThread
from utils.zip_utils import ZipSettings, ArchiveMethod
from core.logger import logger


class ZipController:
    """Handles all ZIP archive creation logic and session state"""
    
    def __init__(self, settings: SettingsManager):
        """Initialize ZIP controller
        
        Args:
            settings: SettingsManager instance for accessing preferences
        """
        self.settings = settings
        self.session_override = None  # 'enabled'/'disabled'/None for persistent session choices
        self.current_operation_choice = None  # 'enabled'/'disabled'/None for single operations
        self.batch_operation_choice = None  # 'enabled'/'disabled'/None for current batch operation
        
    def should_prompt_user(self) -> bool:
        """Check if we need to show prompt to user
        
        Returns:
            True if user should be prompted for ZIP creation choice
        """
        if self.current_operation_choice is not None:
            return False  # Current operation choice already set
        if self.session_override is not None:
            return False  # Session choice overrides prompting
        return self.settings.zip_enabled == 'prompt'
        
    def should_create_zip(self) -> bool:
        """Determine if ZIP should be created based on settings and session state
        
        Returns:
            True if ZIP archives should be created
            
        Raises:
            ValueError: If prompt is required but not resolved
        """
        # Priority order: current operation > batch operation > session override > settings
        
        # Check current operation choice first (single-use, then cleared)
        if self.current_operation_choice is not None:
            choice = self.current_operation_choice
            self.current_operation_choice = None  # Clear after use
            return choice == 'enabled'
            
        # Check batch operation choice (persistent for current batch)
        if self.batch_operation_choice is not None:
            return self.batch_operation_choice == 'enabled'
            
        # Check session override (persistent for session)
        if self.session_override is not None:
            return self.session_override == 'enabled'
        
        # Finally check settings
        zip_enabled = self.settings.zip_enabled
        if zip_enabled == 'prompt':
            raise ValueError("Must resolve prompt before checking ZIP creation")
        return zip_enabled == 'enabled'
        
    def set_session_choice(self, create_zip: bool, remember_for_session: bool = False):
        """Set user's choice for ZIP creation
        
        Args:
            create_zip: Whether to create ZIP archives
            remember_for_session: If True, remember choice for current session
        """
        if remember_for_session:
            # Persistent choice for entire session
            self.session_override = 'enabled' if create_zip else 'disabled'
            # Clear other choices
            self.current_operation_choice = None
            self.batch_operation_choice = None
        else:
            # Batch operation choice (persists for current batch operation)
            self.batch_operation_choice = 'enabled' if create_zip else 'disabled'
            # Clear single operation choice
            self.current_operation_choice = None
            
    def clear_session_override(self):
        """Clear session override (called when settings change or app restarts)"""
        self.session_override = None
        self.current_operation_choice = None
        
    def clear_batch_operation_choice(self):
        """Clear batch operation choice (called when batch operation completes)"""
        self.batch_operation_choice = None
        self.current_operation_choice = None
        
    def get_archive_settings(self) -> ZipSettings:
        """Build archive settings object from current preferences
        
        Returns:
            ZipSettings configured based on current settings including archive method
        """
        settings = ZipSettings()
        
        # Compression level
        settings.compression_level = self.settings.get('ZIP_COMPRESSION_LEVEL', zipfile.ZIP_STORED)
        
        # Archive method from settings
        archive_method_str = self.settings.archive_method
        if archive_method_str == 'native_7zip':
            settings.archive_method = ArchiveMethod.NATIVE_7ZIP
        elif archive_method_str == 'buffered_python':
            settings.archive_method = ArchiveMethod.BUFFERED_PYTHON
        else:  # 'auto'
            settings.archive_method = ArchiveMethod.AUTO
            
        # Archive creation levels - convert from enum to boolean flags
        zip_level = self.settings.zip_level
        settings.create_at_root = (zip_level == 'root')
        settings.create_at_location = (zip_level == 'location') 
        settings.create_at_datetime = (zip_level == 'datetime')
        
        logger.debug(f"Built archive settings: method={settings.archive_method.value}, level={zip_level}")
        return settings
        
    # Keep backward compatibility
    def get_zip_settings(self) -> ZipSettings:
        """Backward compatibility wrapper for get_archive_settings"""
        return self.get_archive_settings()
        
    def create_zip_thread(self, occurrence_folder: Path, output_dir: Path, form_data=None) -> ZipOperationThread:
        """Factory method for creating ZIP operation threads
        
        Args:
            occurrence_folder: Path to the occurrence folder to zip
            output_dir: Output directory for ZIP files
            form_data: Optional FormData for creating descriptive ZIP names
            
        Returns:
            Configured ZipOperationThread ready to start
        """
        settings = self.get_zip_settings()
        settings.output_path = output_dir
        
        return ZipOperationThread(occurrence_folder, output_dir, settings, form_data)
        
    def get_session_status_text(self) -> str:
        """Get text describing current session state for status display
        
        Returns:
            Human-readable session status
        """
        if self.current_operation_choice is not None:
            status = "Enabled" if self.current_operation_choice == 'enabled' else "Disabled"
            return f"ZIP: Operation Choice - {status}"
        elif self.session_override is not None:
            status = "Enabled" if self.session_override == 'enabled' else "Disabled"
            return f"ZIP: Session Override - {status}"
        else:
            zip_enabled = self.settings.zip_enabled
            if zip_enabled == 'enabled':
                return "ZIP: Always Enabled"
            elif zip_enabled == 'disabled':
                return "ZIP: Always Disabled"
            else:  # 'prompt'
                return "ZIP: Will Prompt"
            
    def on_settings_changed(self):
        """Called when settings are changed - clear session override if needed"""
        if self.settings.zip_enabled != 'prompt':
            # If user changes to enabled/disabled, clear any session override
            self.session_override = None
            
        # Log the new archive method
        method = self.settings.archive_method
        logger.info(f"Archive method changed to: {method}")
        logger.info(f"New method description: {self.settings.get_archive_method_description(method)}")
    
    def get_archive_method_info(self) -> Dict[str, Any]:
        """Get detailed information about the current archive method
        
        Returns:
            Dictionary with method info, availability, and performance estimates
        """
        method = self.settings.archive_method
        return {
            'method': method,
            'display_name': self.settings.get_archive_method_display_name(method),
            'description': self.settings.get_archive_method_description(method),
            'is_native_7zip': method == 'native_7zip',
            'is_buffered_python': method == 'buffered_python',
            'is_auto': method == 'auto'
        }