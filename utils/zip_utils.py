#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZIP utility for creating compressed archives with progress reporting
"""

import zipfile
from pathlib import Path
from typing import List, Optional, Callable
from dataclasses import dataclass


@dataclass
class ZipSettings:
    """Settings for ZIP operations"""
    compression_level: int = zipfile.ZIP_STORED  # No compression by default for speed
    create_at_root: bool = True
    create_at_location: bool = False
    create_at_datetime: bool = False
    output_path: Optional[Path] = None
    

class ZipUtility:
    """Handles ZIP file creation with progress reporting"""
    
    def __init__(self, progress_callback: Optional[Callable[[int, str], None]] = None):
        """
        Initialize with optional progress callback
        
        Args:
            progress_callback: Function that receives (progress_pct, status_message)
        """
        self.progress_callback = progress_callback
        self.cancelled = False
        
    def cancel(self):
        """Cancel the current ZIP operation"""
        self.cancelled = True
        
    def create_archive(self, source_path: Path, output_path: Path, 
                      settings: Optional[ZipSettings] = None) -> bool:
        """
        Create a ZIP archive from a directory
        
        Args:
            source_path: Directory to compress
            output_path: Where to save the ZIP file
            settings: ZIP settings (compression level, etc.)
            
        Returns:
            True if successful
        """
        if settings is None:
            settings = ZipSettings()
            
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
                        arcname = file.relative_to(source_path.parent)
                    else:
                        arcname = file.name
                        
                    # Report progress
                    self._report_progress(
                        int((compressed_size / total_size * 100) if total_size > 0 else 0),
                        f"Compressing: {file.name}"
                    )
                    
                    # Add file to archive
                    zf.write(file, arcname)
                    
                    # Update progress
                    compressed_size += file.stat().st_size
                    
            # Final progress
            self._report_progress(100, f"Archive created: {output_path.name}")
            return True
            
        except Exception as e:
            self._report_progress(0, f"Error: {str(e)}")
            return False
            
    def create_multi_level_archives(self, root_path: Path, settings: ZipSettings) -> List[Path]:
        """
        Create archives at multiple folder levels based on settings
        
        Args:
            root_path: Root directory containing the folder structure
            settings: ZIP settings specifying which levels to compress
            
        Returns:
            List of created archive paths
        """
        created_archives = []
        
        try:
            # Helper to create archive name
            def make_archive_name(path: Path, suffix: str = "") -> str:
                name = path.name.replace(' ', '_')
                return f"{name}{suffix}.zip"
                
            # Create at root level
            if settings.create_at_root and root_path.exists():
                output = settings.output_path or root_path.parent
                archive_path = output / make_archive_name(root_path, "_Complete")
                if self.create_archive(root_path, archive_path, settings):
                    created_archives.append(archive_path)
                    
            # Create at location level (second level folders)
            if settings.create_at_location:
                for location_folder in root_path.iterdir():
                    if location_folder.is_dir() and not self.cancelled:
                        output = settings.output_path or location_folder.parent
                        archive_path = output / make_archive_name(location_folder, "_Location")
                        if self.create_archive(location_folder, archive_path, settings):
                            created_archives.append(archive_path)
                            
            # Create at datetime level (third level folders)
            if settings.create_at_datetime:
                for location_folder in root_path.iterdir():
                    if location_folder.is_dir():
                        for datetime_folder in location_folder.iterdir():
                            if datetime_folder.is_dir() and not self.cancelled:
                                output = settings.output_path or datetime_folder.parent
                                archive_path = output / make_archive_name(datetime_folder, "_DateTime")
                                if self.create_archive(datetime_folder, archive_path, settings):
                                    created_archives.append(archive_path)
                                    
        except Exception as e:
            self._report_progress(0, f"Error creating archives: {str(e)}")
            
        return created_archives
        
    def _report_progress(self, percentage: int, message: str):
        """Report progress if callback is available"""
        if self.progress_callback:
            self.progress_callback(percentage, message)
            
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