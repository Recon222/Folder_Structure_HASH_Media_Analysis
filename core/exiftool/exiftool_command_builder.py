#!/usr/bin/env python3
"""
ExifTool Command Builder for forensic metadata extraction
Dynamically builds optimized commands based on user settings
Following successful FFProbeCommandBuilder pattern
"""

from pathlib import Path
from typing import List, Dict, Any, Set, Optional, Tuple
from dataclasses import dataclass
from ..logger import logger


class ExifToolForensicCommandBuilder:
    """
    Build optimized ExifTool commands for batch processing
    Pattern follows FFProbeCommandBuilder for consistency
    """
    
    # Forensic field mappings organized by category
    FORENSIC_FIELDS = {
        'geospatial': [
            '-GPS:all',                    # All GPS tags
            '-XMP:LocationShown*',         # XMP location data
            '-EXIF:GPSSpeed',              # Speed information
            '-EXIF:GPSImgDirection',       # Direction/bearing
            '-EXIF:GPSDestLatitude',       # Destination coordinates
            '-EXIF:GPSDestLongitude',
            '-EXIF:GPSTrack',              # Movement track
            '-EXIF:GPSProcessingMethod',   # How GPS was obtained
            '-EXIF:GPSAreaInformation',    # Area name
            '-EXIF:GPSMapDatum',           # Map datum used
            '-Location',                    # QuickTime location
            '-LocationInformation',         # Additional location
        ],
        'temporal': [
            '-AllDates',                    # All date/time fields
            '-SubSecTime*',                 # Sub-second precision
            '-TimeZone*',                   # Timezone information
            '-OffsetTime*',                 # UTC offset
            '-CreateDate',                  # File creation
            '-ModifyDate',                  # Last modified
            '-DateTimeOriginal',            # Original capture time
            '-DateTimeDigitized',           # Digitization time
            '-FileModifyDate',              # Filesystem date
            '-FileCreateDate',
            '-MediaCreateDate',             # Media creation
            '-MediaModifyDate',
            '-TrackCreateDate',             # Track dates
            '-TrackModifyDate',
        ],
        'device': [
            '-Make',                        # Device manufacturer
            '-Model',                       # Device model
            '-SerialNumber',                # Device serial
            '-InternalSerialNumber',        # Internal serial
            '-LensSerialNumber',            # Lens serial
            '-BodySerialNumber',            # Camera body serial
            '-CameraSerialNumber',          # Camera serial
            '-DeviceID',                    # Generic device ID
            '-UniqueDeviceID',              # Unique identifier
            '-DeviceManufacturer',
            '-DeviceModel',
            '-Software',                    # Software used
            '-Firmware',                    # Firmware version
            '-HostComputer',                # Computer name
            '-DeviceSettingDescription',   # Device settings
        ],
        'document_integrity': [
            '-DocumentID',                  # Document identifier
            '-InstanceID',                  # Instance identifier
            '-OriginalDocumentID',          # Original document
            '-DerivedFrom*',                # Derivation info
            '-History*',                    # Edit history
            '-PreservedFileName',           # Original filename
            '-OriginalFileName',
            '-DocumentAncestors',           # Document lineage
            '-Ingredients*',                # Component files
            '-PantryItem*',                 # Adobe pantry
        ],
        'camera_settings': [
            '-ISO',                         # ISO speed
            '-ExposureTime',                # Shutter speed
            '-FNumber',                     # Aperture
            '-FocalLength',                 # Focal length
            '-WhiteBalance',                # White balance
            '-Flash',                       # Flash status
            '-ExposureMode',
            '-ExposureProgram',
            '-MeteringMode',
            '-LightSource',
            '-SceneCaptureType',
            '-SubjectDistance',
            '-DigitalZoomRatio',
        ],
        'file_properties': [
            '-FileSize',                    # File size
            '-FileType',                    # File type
            '-FileTypeExtension',           # Extension
            '-MIMEType',                    # MIME type
            '-ImageWidth',                  # Dimensions
            '-ImageHeight',
            '-Megapixels',
            '-BitDepth',
            '-ColorType',
            '-Compression',
            '-EncodingProcess',
        ]
    }
    
    # Command optimization cache
    def __init__(self):
        """Initialize command builder with caching"""
        self._command_cache: Dict[str, List[str]] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("ExifToolForensicCommandBuilder initialized")
    
    def build_batch_command(
        self,
        binary_path: Path,
        files: List[Path],
        settings: 'ExifToolSettings',
        max_batch: int = 50
    ) -> List[List[str]]:
        """
        Build commands for batch processing
        
        Args:
            binary_path: Path to ExifTool binary
            files: List of files to process
            settings: ExifTool settings with field selections
            max_batch: Maximum files per command (default 50)
            
        Returns:
            List of command lists for batch execution
        """
        # Build base command with selected fields
        base_cmd = self._build_base_command(binary_path, settings)
        
        # Split files into batches
        commands = []
        for i in range(0, len(files), max_batch):
            batch = files[i:i + max_batch]
            cmd = base_cmd.copy()
            cmd.extend([str(f) for f in batch])
            commands.append(cmd)
        
        return commands
    
    def build_single_command(
        self,
        binary_path: Path,
        file_path: Path,
        settings: 'ExifToolSettings'
    ) -> List[str]:
        """
        Build command for single file extraction
        
        Args:
            binary_path: Path to ExifTool binary
            file_path: File to analyze
            settings: ExifTool settings
            
        Returns:
            Command list for execution
        """
        cmd = self._build_base_command(binary_path, settings)
        cmd.append(str(file_path))
        return cmd
    
    def build_simple_command(
        self,
        binary_path: Path,
        file_path: Path
    ) -> List[str]:
        """
        Build minimal command for quick checks
        
        Args:
            binary_path: Path to ExifTool binary
            file_path: File to check
            
        Returns:
            Minimal command list
        """
        return [
            str(binary_path),
            '-json',
            '-fast2',
            '-FileType',
            '-MIMEType',
            '-GPS:all',
            str(file_path)
        ]
    
    def _build_base_command(
        self,
        binary_path: Path,
        settings: 'ExifToolSettings'
    ) -> List[str]:
        """
        Build base command with selected fields
        
        Args:
            binary_path: Path to ExifTool binary
            settings: Settings with field selections
            
        Returns:
            Base command list
        """
        # Check cache first
        settings_hash = self._get_settings_hash(settings)
        if settings_hash in self._command_cache:
            self._cache_hits += 1
            return self._command_cache[settings_hash].copy()
        
        self._cache_misses += 1
        
        # Build new command
        cmd = [
            str(binary_path),
            '-json',            # JSON output format
            '-fast2',           # Fast mode (skip MakerNotes)
            '-struct',          # Output structured data
            '-coordFormat',     # Decimal GPS coordinates
            '%.8f',            # 8 decimal places precision
            '-dateFormat',      # ISO date format
            '%Y-%m-%d %H:%M:%S',
        ]
        
        # Add field groups based on settings
        if getattr(settings, 'geospatial_enabled', True):
            cmd.extend(self.FORENSIC_FIELDS['geospatial'])
        
        if getattr(settings, 'temporal_enabled', True):
            cmd.extend(self.FORENSIC_FIELDS['temporal'])
        
        if getattr(settings, 'device_enabled', True):
            cmd.extend(self.FORENSIC_FIELDS['device'])
        
        if getattr(settings, 'document_integrity_enabled', False):
            cmd.extend(self.FORENSIC_FIELDS['document_integrity'])
        
        if getattr(settings, 'camera_settings_enabled', False):
            cmd.extend(self.FORENSIC_FIELDS['camera_settings'])
        
        if getattr(settings, 'file_properties_enabled', True):
            cmd.extend(self.FORENSIC_FIELDS['file_properties'])
        
        # Add performance options
        if getattr(settings, 'use_mwg', False):
            cmd.append('-use')
            cmd.append('MWG')  # Use Metadata Working Group mappings
        
        # Handle thumbnail extraction specifically
        extract_thumbnails = getattr(settings, 'extract_thumbnails', False)
        logger.info(f"COMMAND BUILDER - extract_thumbnails={extract_thumbnails}")
        
        if extract_thumbnails:
            logger.info("THUMBNAIL EXTRACTION ENABLED - Adding thumbnail tags to command")
            # Extract specific thumbnail fields as base64
            cmd.extend([
                '-ThumbnailImage',     # JPEG thumbnail (most common)
                '-PreviewImage',       # Larger preview image
                '-JpgFromRaw',        # JPEG extracted from RAW
                '-b'                  # Binary output as base64 in JSON
            ])
        elif getattr(settings, 'extract_binary', False):
            # Extract ALL binary data
            cmd.append('-b')
        
        if getattr(settings, 'extract_unknown', False):
            cmd.append('-U')  # Extract unknown tags
        
        # Cache the command
        self._command_cache[settings_hash] = cmd.copy()
        
        return cmd
    
    def _get_settings_hash(self, settings: 'ExifToolSettings') -> str:
        """
        Generate hash for settings to use as cache key
        
        Args:
            settings: ExifTool settings object
            
        Returns:
            Hash string for caching
        """
        # Create a tuple of settings for hashing
        settings_tuple = (
            getattr(settings, 'geospatial_enabled', True),
            getattr(settings, 'temporal_enabled', True),
            getattr(settings, 'device_enabled', True),
            getattr(settings, 'document_integrity_enabled', False),
            getattr(settings, 'camera_settings_enabled', False),
            getattr(settings, 'file_properties_enabled', True),
            getattr(settings, 'use_mwg', False),
            getattr(settings, 'extract_binary', False),
            getattr(settings, 'extract_unknown', False),
            getattr(settings, 'extract_thumbnails', False),
        )
        return str(hash(settings_tuple))
    
    def get_optimization_info(self) -> Dict[str, Any]:
        """
        Get cache statistics and optimization info
        
        Returns:
            Dictionary with cache performance metrics
        """
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'cached_commands': len(self._command_cache),
            'total_requests': total_requests
        }
    
    def estimate_performance_improvement(
        self,
        fields_requested: int,
        total_possible_fields: int = 300
    ) -> float:
        """
        Estimate performance improvement from selective extraction
        
        Args:
            fields_requested: Number of fields being extracted
            total_possible_fields: Total possible fields (default 300)
            
        Returns:
            Estimated speedup factor
        """
        # Based on empirical testing with FFprobe pattern
        if fields_requested < 10:
            return 2.5  # 60-70% improvement
        elif fields_requested < 30:
            return 1.8  # 40-50% improvement
        elif fields_requested < 60:
            return 1.4  # 20-30% improvement
        else:
            return 1.1  # Minimal improvement
    
    def get_field_count(self, settings: 'ExifToolSettings') -> int:
        """
        Count number of fields that will be extracted
        
        Args:
            settings: ExifTool settings
            
        Returns:
            Approximate number of fields
        """
        count = 0
        
        if getattr(settings, 'geospatial_enabled', True):
            count += len(self.FORENSIC_FIELDS['geospatial'])
        
        if getattr(settings, 'temporal_enabled', True):
            count += len(self.FORENSIC_FIELDS['temporal'])
        
        if getattr(settings, 'device_enabled', True):
            count += len(self.FORENSIC_FIELDS['device'])
        
        if getattr(settings, 'document_integrity_enabled', False):
            count += len(self.FORENSIC_FIELDS['document_integrity'])
        
        if getattr(settings, 'camera_settings_enabled', False):
            count += len(self.FORENSIC_FIELDS['camera_settings'])
        
        if getattr(settings, 'file_properties_enabled', True):
            count += len(self.FORENSIC_FIELDS['file_properties'])
        
        return count
    
    def clear_cache(self):
        """Clear command cache"""
        self._command_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.debug("Command cache cleared")