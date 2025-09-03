#!/usr/bin/env python3
"""
ExifTool data models for forensic metadata
Comprehensive models for GPS, device, temporal, and analysis data
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum


class GPSPrecisionLevel(Enum):
    """GPS coordinate precision levels for privacy"""
    EXACT = 6        # ~0.1m accuracy
    BUILDING = 4     # ~10m accuracy
    BLOCK = 3        # ~100m accuracy
    NEIGHBORHOOD = 2  # ~1km accuracy


@dataclass
class GPSData:
    """GPS location data from ExifTool"""
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    accuracy: Optional[float] = None  # meters
    speed: Optional[float] = None     # km/h
    direction: Optional[float] = None  # degrees
    track: Optional[float] = None      # movement direction
    img_direction: Optional[float] = None  # camera direction
    dest_latitude: Optional[float] = None
    dest_longitude: Optional[float] = None
    processing_method: Optional[str] = None
    area_information: Optional[str] = None
    map_datum: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    def obfuscate(self, level: GPSPrecisionLevel = GPSPrecisionLevel.BLOCK) -> 'GPSData':
        """
        Return obfuscated GPS data for privacy
        
        Args:
            level: Precision level for obfuscation
            
        Returns:
            New GPSData with reduced precision
        """
        precision = level.value
        return GPSData(
            latitude=round(self.latitude, precision),
            longitude=round(self.longitude, precision),
            altitude=round(self.altitude, -1) if self.altitude else None,  # Round to 10m
            accuracy=None,  # Remove accuracy for privacy
            speed=self.speed,
            direction=self.direction,
            track=self.track,
            img_direction=self.img_direction,
            dest_latitude=round(self.dest_latitude, precision) if self.dest_latitude else None,
            dest_longitude=round(self.dest_longitude, precision) if self.dest_longitude else None,
            processing_method=self.processing_method,
            area_information=self.area_information,
            map_datum=self.map_datum,
            timestamp=self.timestamp
        )
    
    def to_decimal_degrees(self) -> Tuple[float, float]:
        """Get coordinates as decimal degrees"""
        return (self.latitude, self.longitude)
    
    def to_dms(self) -> Tuple[str, str]:
        """
        Convert to degrees, minutes, seconds format
        
        Returns:
            Tuple of (latitude_dms, longitude_dms)
        """
        def decimal_to_dms(decimal: float, is_longitude: bool = False) -> str:
            direction = ''
            if is_longitude:
                direction = 'E' if decimal >= 0 else 'W'
            else:
                direction = 'N' if decimal >= 0 else 'S'
            
            decimal = abs(decimal)
            degrees = int(decimal)
            minutes_decimal = (decimal - degrees) * 60
            minutes = int(minutes_decimal)
            seconds = (minutes_decimal - minutes) * 60
            
            return f"{degrees}°{minutes}'{seconds:.2f}\"{direction}"
        
        return (
            decimal_to_dms(self.latitude, False),
            decimal_to_dms(self.longitude, True)
        )


@dataclass
class DeviceInfo:
    """Device identification information"""
    make: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    internal_serial: Optional[str] = None
    lens_serial: Optional[str] = None
    body_serial: Optional[str] = None
    camera_serial: Optional[str] = None
    device_id: Optional[str] = None
    unique_device_id: Optional[str] = None
    software: Optional[str] = None
    firmware: Optional[str] = None
    host_computer: Optional[str] = None
    
    def get_primary_id(self) -> Optional[str]:
        """Get the most specific device identifier available"""
        return (
            self.serial_number or
            self.camera_serial or
            self.unique_device_id or
            self.device_id or
            self.internal_serial or
            self.body_serial
        )
    
    def get_display_name(self) -> str:
        """Get a display-friendly device name"""
        if self.make and self.model:
            return f"{self.make} {self.model}"
        return self.model or self.make or self.get_primary_id() or "Unknown Device"


@dataclass
class TemporalData:
    """Temporal/time-related metadata"""
    capture_time: Optional[datetime] = None
    create_time: Optional[datetime] = None
    modify_time: Optional[datetime] = None
    digitized_time: Optional[datetime] = None
    file_modify_time: Optional[datetime] = None
    file_create_time: Optional[datetime] = None
    media_create_time: Optional[datetime] = None
    media_modify_time: Optional[datetime] = None
    timezone_offset: Optional[str] = None
    subsec_time: Optional[str] = None
    subsec_time_original: Optional[str] = None
    subsec_time_digitized: Optional[str] = None
    
    def get_primary_timestamp(self) -> Optional[datetime]:
        """Get the most relevant timestamp"""
        return (
            self.capture_time or
            self.create_time or
            self.media_create_time or
            self.digitized_time or
            self.file_create_time
        )
    
    def get_time_discrepancies(self) -> List[str]:
        """Identify temporal inconsistencies for forensic analysis"""
        discrepancies = []
        primary = self.get_primary_timestamp()
        
        if not primary:
            return discrepancies
        
        # Check for significant time differences (> 1 day)
        time_fields = [
            ('Create Time', self.create_time),
            ('Modify Time', self.modify_time),
            ('File Create', self.file_create_time),
            ('File Modify', self.file_modify_time)
        ]
        
        for name, timestamp in time_fields:
            if timestamp and abs((timestamp - primary).days) > 1:
                discrepancies.append(
                    f"{name} differs by {abs((timestamp - primary).days)} days"
                )
        
        return discrepancies


@dataclass
class DocumentIntegrity:
    """Document integrity and edit history information"""
    document_id: Optional[str] = None
    instance_id: Optional[str] = None
    original_document_id: Optional[str] = None
    derived_from: Optional[str] = None
    history: List[str] = field(default_factory=list)
    preserved_filename: Optional[str] = None
    original_filename: Optional[str] = None
    document_ancestors: List[str] = field(default_factory=list)
    ingredients: List[str] = field(default_factory=list)
    
    def has_edit_history(self) -> bool:
        """Check if document has been edited"""
        return bool(self.history or self.derived_from or self.document_ancestors)
    
    def get_edit_count(self) -> int:
        """Get number of recorded edits"""
        return len(self.history)


@dataclass
class CameraSettings:
    """Camera settings at capture time"""
    iso: Optional[int] = None
    exposure_time: Optional[str] = None  # e.g., "1/125"
    f_number: Optional[float] = None
    focal_length: Optional[float] = None
    white_balance: Optional[str] = None
    flash: Optional[str] = None
    exposure_mode: Optional[str] = None
    exposure_program: Optional[str] = None
    metering_mode: Optional[str] = None
    light_source: Optional[str] = None
    scene_capture_type: Optional[str] = None
    subject_distance: Optional[float] = None
    digital_zoom_ratio: Optional[float] = None


@dataclass
class ExifToolMetadata:
    """Complete forensic metadata from ExifTool"""
    file_path: Path
    
    # Core data components
    gps_data: Optional[GPSData] = None
    device_info: Optional[DeviceInfo] = None
    temporal_data: Optional[TemporalData] = None
    document_integrity: Optional[DocumentIntegrity] = None
    camera_settings: Optional[CameraSettings] = None
    
    # File properties
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    file_extension: Optional[str] = None
    mime_type: Optional[str] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    megapixels: Optional[float] = None
    bit_depth: Optional[int] = None
    color_type: Optional[str] = None
    compression: Optional[str] = None
    
    # Additional location info
    location_name: Optional[str] = None
    
    # Raw data
    raw_json: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    extraction_time: Optional[float] = None  # seconds
    
    @property
    def has_gps(self) -> bool:
        """Check if file has GPS data"""
        return self.gps_data is not None
    
    @property
    def has_device_id(self) -> bool:
        """Check if device can be identified"""
        return self.device_info is not None and self.device_info.get_primary_id() is not None
    
    @property
    def has_edit_history(self) -> bool:
        """Check if file has edit history"""
        return (
            self.document_integrity is not None and
            self.document_integrity.has_edit_history()
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of metadata for display"""
        summary = {
            'file': self.file_path.name,
            'type': self.file_type,
            'has_gps': self.has_gps,
            'has_device_id': self.has_device_id,
            'has_edits': self.has_edit_history
        }
        
        if self.has_gps:
            summary['coordinates'] = self.gps_data.to_decimal_degrees()
        
        if self.has_device_id:
            summary['device'] = self.device_info.get_display_name()
        
        if self.temporal_data:
            summary['timestamp'] = self.temporal_data.get_primary_timestamp()
        
        return summary


@dataclass
class ExifToolSettings:
    """Settings for ExifTool extraction"""
    # Field groups
    geospatial_enabled: bool = True
    temporal_enabled: bool = True
    device_enabled: bool = True
    document_integrity_enabled: bool = False
    camera_settings_enabled: bool = False
    file_properties_enabled: bool = True
    
    # Advanced options
    use_mwg: bool = False           # Use Metadata Working Group mappings
    extract_binary: bool = False     # Extract binary data
    extract_unknown: bool = False    # Extract unknown tags
    
    # Privacy settings
    gps_precision: GPSPrecisionLevel = GPSPrecisionLevel.EXACT
    obfuscate_gps: bool = False
    
    # Performance settings
    batch_size: int = 50
    max_workers: int = 4
    timeout_per_file: float = 10.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'geospatial_enabled': self.geospatial_enabled,
            'temporal_enabled': self.temporal_enabled,
            'device_enabled': self.device_enabled,
            'document_integrity_enabled': self.document_integrity_enabled,
            'camera_settings_enabled': self.camera_settings_enabled,
            'file_properties_enabled': self.file_properties_enabled,
            'use_mwg': self.use_mwg,
            'extract_binary': self.extract_binary,
            'extract_unknown': self.extract_unknown,
            'gps_precision': self.gps_precision.name,
            'obfuscate_gps': self.obfuscate_gps,
            'batch_size': self.batch_size,
            'max_workers': self.max_workers,
            'timeout_per_file': self.timeout_per_file
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExifToolSettings':
        """Create from dictionary"""
        settings = cls()
        for key, value in data.items():
            if key == 'gps_precision':
                value = GPSPrecisionLevel[value]
            if hasattr(settings, key):
                setattr(settings, key, value)
        return settings


@dataclass
class ExifToolAnalysisResult:
    """Results from ExifTool analysis"""
    total_files: int
    successful: int
    failed: int
    skipped: int
    metadata_list: List[ExifToolMetadata]
    gps_locations: List[ExifToolMetadata]  # Files with GPS
    device_map: Dict[str, List[ExifToolMetadata]]  # By device ID
    temporal_path: List[Tuple[datetime, ExifToolMetadata]]  # Time-ordered
    processing_time: float
    errors: List[str]
    privacy_warnings: List[str] = field(default_factory=list)
    
    def get_device_statistics(self) -> Dict[str, int]:
        """Get count of files per device"""
        return {device: len(files) for device, files in self.device_map.items()}
    
    def get_gps_bounds(self) -> Optional[Tuple[float, float, float, float]]:
        """
        Get bounding box of all GPS coordinates
        
        Returns:
            Tuple of (min_lat, min_lon, max_lat, max_lon) or None
        """
        if not self.gps_locations:
            return None
        
        lats = [m.gps_data.latitude for m in self.gps_locations if m.gps_data]
        lons = [m.gps_data.longitude for m in self.gps_locations if m.gps_data]
        
        if not lats or not lons:
            return None
        
        return (min(lats), min(lons), max(lats), max(lons))
    
    def get_temporal_range(self) -> Optional[Tuple[datetime, datetime]]:
        """Get time range of all files"""
        if not self.temporal_path:
            return None
        
        times = [t for t, _ in self.temporal_path]
        return (min(times), max(times)) if times else None