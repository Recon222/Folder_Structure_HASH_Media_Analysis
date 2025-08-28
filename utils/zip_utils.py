#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hybrid ZIP utility supporting both native 7zip (7-14x faster) and Python buffered operations
Native 7zip is the default with automatic fallback to buffered operations
"""

import zipfile
from pathlib import Path
from typing import List, Optional, Callable, Union
from dataclasses import dataclass
from enum import Enum

# Import high-performance ZIP operations
from core.buffered_zip_ops import BufferedZipOperations, ZipPerformanceMetrics
from core.native_7zip.controller import Native7ZipController, Native7ZipMetrics
from core.result_types import Result, ArchiveOperationResult
from core.logger import logger

# Import template services
try:
    from core.services import get_service, IPathService
    _TEMPLATE_SERVICE_AVAILABLE = True
except ImportError:
    _TEMPLATE_SERVICE_AVAILABLE = False


class ArchiveMethod(Enum):
    """Archive method options for hybrid mode"""
    NATIVE_7ZIP = "native_7zip"  # High-performance native 7zip (default)
    BUFFERED_PYTHON = "buffered_python"  # Buffered Python ZIP operations
    AUTO = "auto"  # Automatically choose best method


@dataclass
class ZipSettings:
    """Settings for ZIP operations with hybrid mode support"""
    compression_level: int = zipfile.ZIP_STORED  # No compression by default for speed
    create_at_root: bool = True
    create_at_location: bool = False
    create_at_datetime: bool = False
    output_path: Optional[Path] = None
    archive_method: ArchiveMethod = ArchiveMethod.NATIVE_7ZIP  # Default to 7zip
    

class ZipUtility:
    """
    Hybrid ZIP utility supporting both native 7zip (7-14x faster) and Python buffered operations
    
    Performance hierarchy:
    1. Native 7zip (default): 2,000-4,000 MB/s on Windows
    2. Buffered Python: 290 MB/s (current high-performance implementation)
    3. Legacy Python: ~150 MB/s (fallback only)
    
    Automatic fallback ensures compatibility across all environments.
    """
    
    def __init__(self, progress_callback: Optional[Callable[[int, str], None]] = None,
                 archive_method: ArchiveMethod = ArchiveMethod.NATIVE_7ZIP):
        """
        Initialize hybrid ZIP utility
        
        Args:
            progress_callback: Function that receives (progress_pct, status_message)
            archive_method: Preferred archive method (default: NATIVE_7ZIP)
        """
        self.progress_callback = progress_callback
        self.cancelled = False
        self.archive_method = archive_method
        
        # Performance metrics (will be set by active method)
        self.performance_metrics: Optional[Union[ZipPerformanceMetrics, Native7ZipMetrics]] = None
        self.active_method: Optional[str] = None
        
        # Initialize controllers
        self.native_controller: Optional[Native7ZipController] = None
        self.buffered_ops: Optional[BufferedZipOperations] = None
        
        # Initialize based on method preference and availability
        self._initialize_controllers()
    
    def _initialize_controllers(self):
        """Initialize archive controllers based on method preference and availability"""
        try:
            # Try to initialize native 7zip first (highest performance)
            if self.archive_method in (ArchiveMethod.NATIVE_7ZIP, ArchiveMethod.AUTO):
                self.native_controller = Native7ZipController(self.progress_callback)
                if self.native_controller.is_available():
                    self.active_method = "native_7zip"
                    logger.info("Initialized with native 7zip (high-performance mode)")
                    return
                else:
                    logger.warning("Native 7zip not available, falling back to buffered Python")
                    self.native_controller = None
            
            # Initialize buffered Python operations (fallback or explicit choice)
            self.buffered_ops = BufferedZipOperations(
                progress_callback=self.progress_callback,
                metrics_callback=self._handle_buffered_metrics_callback,
                cancelled_check=lambda: self.cancelled
            )
            self.active_method = "buffered_python"
            logger.info("Initialized with buffered Python ZIP operations")
            
        except Exception as e:
            logger.error(f"Error initializing ZIP controllers: {e}")
            # Ultimate fallback - will use legacy method
            self.active_method = "legacy_python"
        
    def _handle_buffered_metrics_callback(self, metrics: ZipPerformanceMetrics):
        """Handle performance metrics from BufferedZipOperations"""
        self.performance_metrics = metrics
        
    def _handle_native_metrics_callback(self, metrics: Native7ZipMetrics):
        """Handle performance metrics from Native7ZipController"""
        self.performance_metrics = metrics
        
    def cancel(self):
        """Cancel the current ZIP operation"""
        self.cancelled = True
        
        # Cancel active controller
        if self.active_method == "native_7zip" and self.native_controller:
            self.native_controller.cancel()
        elif self.active_method == "buffered_python" and self.buffered_ops:
            self.buffered_ops.cancel()
        
    def create_archive(self, source_path: Path, output_path: Path, 
                      settings: Optional[ZipSettings] = None) -> bool:
        """
        Create archive using the best available method with automatic fallback
        
        Args:
            source_path: Directory to compress
            output_path: Where to save the archive file
            settings: Archive settings (compression level, method preference, etc.)
            
        Returns:
            True if successful
        """
        if settings is None:
            settings = ZipSettings()
        
        # Update archive method from settings if provided
        if hasattr(settings, 'archive_method'):
            self.archive_method = settings.archive_method
            # Re-initialize if method changed
            if ((self.archive_method == ArchiveMethod.NATIVE_7ZIP and self.active_method != "native_7zip") or
                (self.archive_method == ArchiveMethod.BUFFERED_PYTHON and self.active_method != "buffered_python")):
                self._initialize_controllers()
        
        # Try native 7zip first (highest performance)
        if self.active_method == "native_7zip" and self.native_controller:
            logger.debug(f"Using native 7zip for {source_path}")
            
            # Native 7zip now creates .zip files (using -tzip flag)
            native_output = output_path.with_suffix('.zip')
            
            result = self.native_controller.create_archive(
                source_path, 
                native_output, 
                "store" if settings.compression_level == zipfile.ZIP_STORED else "fast"
            )
            
            if result.success:
                # Update performance metrics
                self.performance_metrics = self.native_controller.get_metrics()
                
                # Log performance metrics
                if self.performance_metrics:
                    logger.info(
                        f"Native 7zip Performance: {self.performance_metrics.average_speed_mbps:.1f} MB/s avg, "
                        f"{self.performance_metrics.files_processed}/{self.performance_metrics.total_files} files, "
                        f"{self.performance_metrics.execution_time:.2f}s duration"
                    )
                return True
            else:
                logger.warning(f"Native 7zip failed: {result.error}")
                logger.info("Falling back to buffered Python ZIP")
                # Continue to buffered fallback
        
        # Try buffered Python operations (fallback or explicit choice)
        if self.active_method in ("buffered_python", "legacy_python") and self.buffered_ops:
            logger.debug(f"Using buffered Python ZIP operations for {source_path}")
            
            result = self.buffered_ops.create_archive_buffered(
                source_path, 
                output_path, 
                settings.compression_level
            )
            
            if result.success:
                # Log performance metrics
                if self.performance_metrics:
                    logger.info(
                        f"Buffered ZIP Performance: {self.performance_metrics.average_speed_mbps:.1f} MB/s avg, "
                        f"{self.performance_metrics.files_processed}/{self.performance_metrics.total_files} files, "
                        f"{self.performance_metrics.bytes_processed / (1024*1024):.1f} MB processed"
                    )
                return True
            else:
                logger.error(f"Buffered ZIP failed: {result.error}")
                logger.info("Falling back to legacy ZIP method")
        
        # Ultimate fallback: legacy ZIP method
        logger.debug(f"Using legacy ZIP operations for {source_path}")
        return self._create_archive_legacy(source_path, output_path, settings)
    
    def _create_archive_legacy(self, source_path: Path, output_path: Path, 
                              settings: ZipSettings) -> bool:
        """
        Legacy ZIP creation method (original implementation)
        
        Kept for backward compatibility and as fallback
        """
        try:
            # Get all files to compress
            files = list(source_path.rglob('*') if source_path.is_dir() else [source_path])
            files = [f for f in files if f.is_file()]
            
            if not files:
                self._report_progress(100, "No files to compress")
                return False
                
            # Calculate total size
            total_size = sum(f.stat().st_size for f in files)
            compressed_size = 0
            
            # Create ZIP file
            with zipfile.ZipFile(output_path, 'w', settings.compression_level) as zf:
                for i, file in enumerate(files):
                    if self.cancelled:
                        return False
                        
                    # Calculate relative path
                    if source_path.is_dir():
                        arcname = file.relative_to(source_path)
                    else:
                        arcname = file.name
                        
                    # Report progress
                    self._report_progress(
                        int((compressed_size / total_size * 100) if total_size > 0 else 0),
                        f"Compressing: {file.name}"
                    )
                    
                    # Add file to archive (SLOW - loads entire file into memory)
                    zf.write(file, arcname)
                    
                    # Update progress
                    compressed_size += file.stat().st_size
                    
            # Final progress
            self._report_progress(100, f"Archive created: {output_path.name}")
            return True
            
        except Exception as e:
            self._report_progress(0, f"Error: {str(e)}")
            return False
            
    def create_multi_level_archives(self, root_path: Path, settings: ZipSettings, 
                                   form_data=None) -> List[Path]:
        """
        Create archives at multiple folder levels based on settings
        
        Args:
            root_path: Root directory containing the folder structure
            settings: ZIP settings specifying which levels to compress
            form_data: Optional FormData for creating descriptive names
            
        Returns:
            List of created archive paths
        """
        created_archives = []
        
        try:
            # Helper to create consistent descriptive archive name
            def create_descriptive_archive_name() -> str:
                # Try template-based naming first
                if form_data and _TEMPLATE_SERVICE_AVAILABLE:
                    try:
                        path_service = get_service(IPathService)
                        result = path_service.build_archive_name(form_data)
                        if result.success:
                            logger.debug(f"Using template-based archive name: {result.value}")
                            return result.value
                        else:
                            logger.warning(f"Template archive naming failed: {result.error}")
                    except Exception as e:
                        logger.warning(f"Template service unavailable for archive naming: {e}")
                
                # Fallback to legacy naming
                if form_data:
                    occurrence = form_data.occurrence_number or "Unknown"
                    business = form_data.business_name or ""
                    location = form_data.location_address or ""
                    
                    # Build the name: "PR123456 Shoppers Drug Mart @ 405 Belsize Dr. Video Recovery"
                    name_parts = [occurrence]
                    if business:
                        name_parts.append(business)
                    if location:
                        name_parts.append(f"@ {location}")
                    name_parts.append("Video Recovery")
                    
                    # All methods now create .zip files
                    return " ".join(name_parts) + " Video Recovery.zip"
                else:
                    # Fallback naming when no form_data
                    name = root_path.name.replace(' ', '_')
                    # All methods now create .zip files
                    return f"{name}_Complete.zip"
                
            # Create at root level
            if settings.create_at_root and root_path.exists():
                output = settings.output_path or root_path.parent
                archive_name = create_descriptive_archive_name()
                archive_path = output / archive_name
                if self.create_archive(root_path, archive_path, settings):
                    created_archives.append(archive_path)
                    
            # Create at location level (second level folders)
            if settings.create_at_location:
                for location_folder in root_path.iterdir():
                    if location_folder.is_dir() and not self.cancelled:
                        output = settings.output_path or location_folder.parent
                        archive_name = create_descriptive_archive_name()
                        archive_path = output / archive_name
                        if self.create_archive(location_folder, archive_path, settings):
                            created_archives.append(archive_path)
                            
            # Create at datetime level (third level folders)
            if settings.create_at_datetime:
                for location_folder in root_path.iterdir():
                    if location_folder.is_dir():
                        for datetime_folder in location_folder.iterdir():
                            if datetime_folder.is_dir() and not self.cancelled:
                                output = settings.output_path or datetime_folder.parent
                                archive_name = create_descriptive_archive_name()
                                archive_path = output / archive_name
                                if self.create_archive(datetime_folder, archive_path, settings):
                                    created_archives.append(archive_path)
                                    
        except Exception as e:
            self._report_progress(0, f"Error creating archives: {str(e)}")
            
        return created_archives
        
    def _report_progress(self, percentage: int, message: str):
        """Report progress if callback is available"""
        if self.progress_callback:
            self.progress_callback(percentage, message)
            
    def get_performance_metrics(self) -> Optional[Union[ZipPerformanceMetrics, Native7ZipMetrics]]:
        """
        Get performance metrics from the last archive operation
        
        Returns:
            Performance metrics from the active method, None if no operation completed
        """
        return self.performance_metrics
        
    def get_active_method(self) -> str:
        """
        Get the currently active archive method
        
        Returns:
            'native_7zip', 'buffered_python', or 'legacy_python'
        """
        return self.active_method or 'unknown'
        
    def get_method_info(self) -> dict:
        """
        Get detailed information about available and active methods
        
        Returns:
            Dictionary with method availability and performance info
        """
        info = {
            'active_method': self.get_active_method(),
            'preferred_method': self.archive_method.value if self.archive_method else 'unknown',
            'methods': {
                'native_7zip': {
                    'available': self.native_controller is not None and self.native_controller.is_available(),
                    'expected_speed': '2,000-4,000 MB/s',
                    'description': 'Native 7za.exe subprocess (highest performance)'
                },
                'buffered_python': {
                    'available': self.buffered_ops is not None,
                    'expected_speed': '290 MB/s',
                    'description': 'Buffered Python ZIP operations (high performance)'
                },
                'legacy_python': {
                    'available': True,  # Always available
                    'expected_speed': '150 MB/s',
                    'description': 'Standard Python ZIP operations (compatibility fallback)'
                }
            }
        }
        
        # Add diagnostic info if available
        if self.native_controller:
            try:
                info['native_7zip_diagnostics'] = self.native_controller.get_diagnostic_info()
            except Exception as e:
                info['native_7zip_diagnostics'] = f"Error getting diagnostics: {e}"
                
        return info
    
    def is_native_7zip_available(self) -> bool:
        """Check if native 7zip is available for high-performance operations"""
        return (self.native_controller is not None and 
                self.native_controller.is_available())
        
    def switch_method(self, new_method: ArchiveMethod) -> bool:
        """
        Switch to a different archive method
        
        Args:
            new_method: New archive method to use
            
        Returns:
            True if switch was successful
        """
        if new_method == self.archive_method:
            return True  # Already using this method
            
        self.archive_method = new_method
        old_method = self.active_method
        
        try:
            self._initialize_controllers()
            logger.info(f"Switched archive method from {old_method} to {self.active_method}")
            return True
        except Exception as e:
            logger.error(f"Failed to switch archive method: {e}")
            return False
            
    def cancel(self):
        """Cancel the current operation"""
        self.cancelled = True
        
    @staticmethod
    def estimate_compressed_size(source_path: Path, compression_level: int = zipfile.ZIP_STORED) -> int:
        """
        Estimate the compressed size of a directory
        
        Args:
            source_path: Directory to estimate
            compression_level: Compression level to use
            
        Returns:
            Estimated size in bytes
        """
        # For stored (no compression), size is roughly the same
        if compression_level == zipfile.ZIP_STORED:
            total = 0
            for file in source_path.rglob('*'):
                if file.is_file():
                    total += file.stat().st_size
            return total
            
        # For deflated, estimate 50-70% of original size (rough estimate)
        elif compression_level == zipfile.ZIP_DEFLATED:
            total = 0
            for file in source_path.rglob('*'):
                if file.is_file():
                    total += file.stat().st_size
            return int(total * 0.6)  # 60% of original
            
        return 0