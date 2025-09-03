#!/usr/bin/env python3
"""
ExifTool Normalizer - Transform raw ExifTool output to structured data
Handles various metadata formats and edge cases for forensic analysis
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from collections import defaultdict

from .exiftool_models import (
    ExifToolMetadata, GPSData, DeviceInfo, TemporalData,
    DocumentIntegrity, CameraSettings, GPSPrecisionLevel
)
from ..logger import logger


class ExifToolNormalizer:
    """
    Normalize ExifTool output to structured data
    Follows MetadataNormalizer patterns for consistency
    """
    
    # GPS coordinate regex patterns
    GPS_DMS_PATTERN = re.compile(
        r"(\d+)\s*(?:deg|°)\s*(\d+)['\u2032\u2019]\s*([\d.]+)[\"\u2033\u201D]?\s*([NSEW])?"
    )
    GPS_DECIMAL_PATTERN = re.compile(
        r'^([+-]?\d+\.?\d*)'
    )
    ISO6709_PATTERN = re.compile(
        r'^([+-]\d+\.?\d*)([+-]\d+\.?\d*)'
    )
    
    # Date/time parsing formats
    DATE_FORMATS = [
        '%Y-%m-%d %H:%M:%S',      # Standard format
        '%Y:%m:%d %H:%M:%S',      # EXIF format
        '%Y-%m-%dT%H:%M:%S',      # ISO format without timezone
        '%Y-%m-%dT%H:%M:%SZ',     # ISO format with Z
        '%Y-%m-%dT%H:%M:%S%z',    # ISO format with timezone
        '%Y:%m:%d %H:%M:%S%z',    # EXIF with timezone
    ]
    
    def normalize(
        self,
        raw_metadata: Dict[str, Any],
        file_path: Path,
        settings: Optional['ExifToolSettings'] = None
    ) -> ExifToolMetadata:
        """
        Normalize raw ExifTool output to structured metadata
        
        Args:
            raw_metadata: Raw JSON from ExifTool
            file_path: Path to source file
            settings: Optional settings for privacy controls
            
        Returns:
            Normalized ExifToolMetadata object
        """
        # Create base metadata object
        metadata = ExifToolMetadata(
            file_path=file_path,
            raw_json=raw_metadata,
            extraction_time=raw_metadata.get('_extraction_time')
        )
        
        try:
            # Extract GPS data
            gps_data = self._extract_gps_data(raw_metadata)
            if gps_data and settings and settings.obfuscate_gps:
                gps_data = gps_data.obfuscate(settings.gps_precision)
            metadata.gps_data = gps_data
            
            # Extract device information
            metadata.device_info = self._extract_device_info(raw_metadata)
            
            # Extract temporal data
            metadata.temporal_data = self._extract_temporal_data(raw_metadata)
            
            # Extract document integrity
            metadata.document_integrity = self._extract_document_integrity(raw_metadata)
            
            # Extract camera settings
            metadata.camera_settings = self._extract_camera_settings(raw_metadata)
            
            # Extract file properties
            self._extract_file_properties(metadata, raw_metadata)
            
            # Extract additional location info
            metadata.location_name = self._extract_location_name(raw_metadata)
            
            # Extract thumbnail if present
            self._extract_thumbnail(metadata, raw_metadata)
            
        except Exception as e:
            logger.error(f"Error normalizing metadata for {file_path}: {e}")
            metadata.error = str(e)
        
        return metadata
    
    def _extract_gps_data(self, raw: Dict[str, Any]) -> Optional[GPSData]:
        """
        Extract and normalize GPS coordinates
        
        Args:
            raw: Raw metadata dictionary
            
        Returns:
            GPSData object or None
        """
        # Try different GPS field patterns
        lat = self._extract_coordinate(raw, ['GPSLatitude', 'GPS:Latitude', 'Latitude'])
        lon = self._extract_coordinate(raw, ['GPSLongitude', 'GPS:Longitude', 'Longitude'])
        
        # Debug: Log raw GPS values
        logger.debug(f"Raw GPS extraction - Lat: {lat}, Lon: {lon}")
        logger.debug(f"Raw GPS data: GPSLatitude={raw.get('GPSLatitude')}, GPSLongitude={raw.get('GPSLongitude')}")
        logger.debug(f"GPS Refs: LatRef={raw.get('GPSLatitudeRef')}, LonRef={raw.get('GPSLongitudeRef')}")
        
        
        # Check for combined location field
        if not (lat and lon):
            location = raw.get('Location') or raw.get('GPS:Location')
            if location:
                coords = self._parse_location_string(location)
                if coords:
                    lat, lon = coords
        
        # Check QuickTime atoms
        if not (lat and lon):
            qt_location = raw.get('com.apple.quicktime.location.ISO6709')
            if qt_location:
                coords = self._parse_iso6709(qt_location)
                if coords:
                    lat, lon = coords
        
        if not (lat and lon):
            return None
        
        # Apply hemisphere corrections
        lat_ref = raw.get('GPSLatitudeRef') or raw.get('GPS:LatitudeRef')
        if lat_ref and ('S' in lat_ref or 'South' in lat_ref) and lat > 0:
            lat = -lat
        
        lon_ref = raw.get('GPSLongitudeRef') or raw.get('GPS:LongitudeRef')
        
        # Apply West hemisphere correction if needed
        if lon_ref and ('W' in lon_ref or 'West' in lon_ref) and lon > 0:
            logger.debug(f"Applying West correction: {lon} -> {-lon}")
            lon = -lon
        
        logger.debug(f"Final GPS coordinates - Lat: {lat}, Lon: {lon}")
        
        # Extract additional GPS fields
        gps_data = GPSData(
            latitude=lat,
            longitude=lon,
            altitude=self._extract_altitude(raw),
            accuracy=self._extract_float(raw, ['GPSHPositioningError', 'GPS:HPositioningError']),
            speed=self._extract_float(raw, ['GPSSpeed', 'GPS:Speed']),
            direction=self._extract_float(raw, ['GPSImgDirection', 'GPS:ImgDirection']),
            track=self._extract_float(raw, ['GPSTrack', 'GPS:Track']),
            img_direction=self._extract_float(raw, ['GPSImgDirection', 'GPS:ImgDirection']),
            dest_latitude=self._extract_coordinate(raw, ['GPSDestLatitude', 'GPS:DestLatitude']),
            dest_longitude=self._extract_coordinate(raw, ['GPSDestLongitude', 'GPS:DestLongitude']),
            processing_method=raw.get('GPSProcessingMethod') or raw.get('GPS:ProcessingMethod'),
            area_information=raw.get('GPSAreaInformation') or raw.get('GPS:AreaInformation'),
            map_datum=raw.get('GPSMapDatum') or raw.get('GPS:MapDatum'),
            timestamp=self._extract_gps_timestamp(raw)
        )
        
        return gps_data
    
    def _extract_coordinate(
        self,
        raw: Dict[str, Any],
        field_names: List[str]
    ) -> Optional[float]:
        """
        Extract coordinate from various field formats
        
        Args:
            raw: Raw metadata
            field_names: List of possible field names
            
        Returns:
            Decimal coordinate or None
        """
        for field in field_names:
            value = raw.get(field)
            if value is not None:
                # Already a float
                if isinstance(value, (int, float)):
                    return float(value)
                
                # String format
                if isinstance(value, str):
                    # Try DMS format
                    dms_match = self.GPS_DMS_PATTERN.match(value)
                    if dms_match:
                        deg, min, sec, ref = dms_match.groups()
                        decimal = float(deg) + float(min)/60 + float(sec)/3600
                        # Only apply hemisphere if it's in the string
                        # Otherwise it will be handled by GPSLatitudeRef/GPSLongitudeRef
                        if ref and ref in ['S', 'W']:
                            decimal = -decimal
                        return decimal
                    
                    # Try decimal format
                    try:
                        return float(value)
                    except ValueError:
                        continue
        
        return None
    
    def _parse_location_string(self, location: str) -> Optional[Tuple[float, float]]:
        """
        Parse various location string formats
        
        Args:
            location: Location string
            
        Returns:
            Tuple of (lat, lon) or None
        """
        # ISO 6709 format: +40.7128-074.0060/
        iso_match = self.ISO6709_PATTERN.match(location)
        if iso_match:
            lat_str, lon_str = iso_match.groups()
            try:
                return float(lat_str), float(lon_str)
            except ValueError:
                pass
        
        # Comma-separated: 40.7128, -74.0060
        if ',' in location:
            parts = location.split(',')
            if len(parts) == 2:
                try:
                    return float(parts[0].strip()), float(parts[1].strip())
                except ValueError:
                    pass
        
        return None
    
    def _parse_iso6709(self, iso_str: str) -> Optional[Tuple[float, float]]:
        """
        Parse ISO 6709 coordinate string
        
        Args:
            iso_str: ISO 6709 formatted string
            
        Returns:
            Tuple of (lat, lon) or None
        """
        # Format: +40.7128-074.0060+012.345/
        match = re.match(r'([+-]\d+\.?\d*)([+-]\d+\.?\d*)', iso_str)
        if match:
            try:
                lat = float(match.group(1))
                lon = float(match.group(2))
                return lat, lon
            except ValueError:
                pass
        return None
    
    def _extract_altitude(self, raw: Dict[str, Any]) -> Optional[float]:
        """Extract altitude from various fields"""
        alt_fields = ['GPSAltitude', 'GPS:Altitude', 'Altitude']
        for field in alt_fields:
            value = raw.get(field)
            if value is not None:
                try:
                    # Handle string format like "100 m"
                    if isinstance(value, str):
                        value = value.replace('m', '').strip()
                    altitude = float(value)
                    
                    # Check altitude reference (above/below sea level)
                    alt_ref = raw.get('GPSAltitudeRef') or raw.get('GPS:AltitudeRef')
                    if alt_ref == 1 or alt_ref == '1':  # Below sea level
                        altitude = -altitude
                    
                    return altitude
                except (ValueError, TypeError):
                    continue
        return None
    
    def _extract_device_info(self, raw: Dict[str, Any]) -> Optional[DeviceInfo]:
        """Extract device identification information"""
        device = DeviceInfo(
            make=raw.get('Make') or raw.get('EXIF:Make'),
            model=raw.get('Model') or raw.get('EXIF:Model'),
            serial_number=raw.get('SerialNumber') or raw.get('EXIF:SerialNumber'),
            internal_serial=raw.get('InternalSerialNumber'),
            lens_serial=raw.get('LensSerialNumber') or raw.get('EXIF:LensSerialNumber'),
            body_serial=raw.get('BodySerialNumber') or raw.get('EXIF:BodySerialNumber'),
            camera_serial=raw.get('CameraSerialNumber'),
            device_id=raw.get('DeviceID'),
            unique_device_id=raw.get('UniqueDeviceID'),
            software=raw.get('Software') or raw.get('EXIF:Software'),
            firmware=raw.get('Firmware'),
            host_computer=raw.get('HostComputer')
        )
        
        # Return None if no device info found
        if not any(vars(device).values()):
            return None
        
        return device
    
    def _extract_temporal_data(self, raw: Dict[str, Any]) -> Optional[TemporalData]:
        """Extract temporal/time-related metadata"""
        temporal = TemporalData(
            capture_time=self._parse_datetime(raw.get('DateTimeOriginal')),
            create_time=self._parse_datetime(raw.get('CreateDate')),
            modify_time=self._parse_datetime(raw.get('ModifyDate')),
            digitized_time=self._parse_datetime(raw.get('DateTimeDigitized')),
            file_modify_time=self._parse_datetime(raw.get('FileModifyDate')),
            file_create_time=self._parse_datetime(raw.get('FileCreateDate')),
            media_create_time=self._parse_datetime(raw.get('MediaCreateDate')),
            media_modify_time=self._parse_datetime(raw.get('MediaModifyDate')),
            timezone_offset=raw.get('TimeZoneOffset') or raw.get('OffsetTime'),
            subsec_time=raw.get('SubSecTime'),
            subsec_time_original=raw.get('SubSecTimeOriginal'),
            subsec_time_digitized=raw.get('SubSecTimeDigitized')
        )
        
        # Return None if no temporal data found
        if not temporal.get_primary_timestamp():
            return None
        
        return temporal
    
    def _extract_document_integrity(self, raw: Dict[str, Any]) -> Optional[DocumentIntegrity]:
        """Extract document integrity and edit history"""
        integrity = DocumentIntegrity(
            document_id=raw.get('DocumentID'),
            instance_id=raw.get('InstanceID'),
            original_document_id=raw.get('OriginalDocumentID'),
            derived_from=raw.get('DerivedFrom'),
            preserved_filename=raw.get('PreservedFileName'),
            original_filename=raw.get('OriginalFileName')
        )
        
        # Extract history
        history = raw.get('History')
        if history:
            if isinstance(history, list):
                integrity.history = history
            elif isinstance(history, str):
                integrity.history = [history]
        
        # Extract document ancestors
        ancestors = raw.get('DocumentAncestors')
        if ancestors:
            if isinstance(ancestors, list):
                integrity.document_ancestors = ancestors
            elif isinstance(ancestors, str):
                integrity.document_ancestors = [ancestors]
        
        # Extract ingredients
        ingredients = raw.get('Ingredients')
        if ingredients:
            if isinstance(ingredients, list):
                integrity.ingredients = ingredients
            elif isinstance(ingredients, str):
                integrity.ingredients = [ingredients]
        
        # Return None if no integrity data found
        if not any(vars(integrity).values()):
            return None
        
        return integrity
    
    def _extract_camera_settings(self, raw: Dict[str, Any]) -> Optional[CameraSettings]:
        """Extract camera settings at capture time"""
        settings = CameraSettings(
            iso=self._extract_int(raw, ['ISO', 'EXIF:ISO', 'ISOSpeedRatings']),
            exposure_time=raw.get('ExposureTime') or raw.get('EXIF:ExposureTime'),
            f_number=self._extract_float(raw, ['FNumber', 'EXIF:FNumber', 'ApertureValue']),
            focal_length=self._extract_float(raw, ['FocalLength', 'EXIF:FocalLength']),
            white_balance=raw.get('WhiteBalance') or raw.get('EXIF:WhiteBalance'),
            flash=raw.get('Flash') or raw.get('EXIF:Flash'),
            exposure_mode=raw.get('ExposureMode') or raw.get('EXIF:ExposureMode'),
            exposure_program=raw.get('ExposureProgram') or raw.get('EXIF:ExposureProgram'),
            metering_mode=raw.get('MeteringMode') or raw.get('EXIF:MeteringMode'),
            light_source=raw.get('LightSource') or raw.get('EXIF:LightSource'),
            scene_capture_type=raw.get('SceneCaptureType') or raw.get('EXIF:SceneCaptureType'),
            subject_distance=self._extract_float(raw, ['SubjectDistance', 'EXIF:SubjectDistance']),
            digital_zoom_ratio=self._extract_float(raw, ['DigitalZoomRatio', 'EXIF:DigitalZoomRatio'])
        )
        
        # Return None if no camera settings found
        if not any(vars(settings).values()):
            return None
        
        return settings
    
    def _extract_file_properties(self, metadata: ExifToolMetadata, raw: Dict[str, Any]):
        """Extract file properties into metadata object"""
        metadata.file_size = self._extract_int(raw, ['FileSize'])
        metadata.file_type = raw.get('FileType') or raw.get('FileTypeExtension')
        metadata.file_extension = raw.get('FileTypeExtension')
        metadata.mime_type = raw.get('MIMEType')
        metadata.image_width = self._extract_int(raw, ['ImageWidth', 'EXIF:ImageWidth', 'Width'])
        metadata.image_height = self._extract_int(raw, ['ImageHeight', 'EXIF:ImageHeight', 'Height'])
        metadata.megapixels = self._extract_float(raw, ['Megapixels'])
        metadata.bit_depth = self._extract_int(raw, ['BitDepth', 'BitsPerSample'])
        metadata.color_type = raw.get('ColorType') or raw.get('ColorSpace')
        metadata.compression = raw.get('Compression') or raw.get('CompressionType')
    
    def _extract_location_name(self, raw: Dict[str, Any]) -> Optional[str]:
        """Extract location name from various fields"""
        location_fields = [
            'LocationShownCity',
            'LocationShownCountry',
            'LocationShownLocationName',
            'LocationCreatedCity',
            'LocationCreatedCountry',
            'LocationCreatedLocationName',
            'Location',
            'LocationInformation'
        ]
        
        for field in location_fields:
            value = raw.get(field) or raw.get(f'XMP:{field}')
            if value:
                return value
        
        return None
    
    def _extract_gps_timestamp(self, raw: Dict[str, Any]) -> Optional[datetime]:
        """Extract GPS timestamp"""
        gps_date = raw.get('GPSDateStamp') or raw.get('GPS:DateStamp')
        gps_time = raw.get('GPSTimeStamp') or raw.get('GPS:TimeStamp')
        
        if gps_date and gps_time:
            try:
                # Combine date and time
                datetime_str = f"{gps_date} {gps_time}"
                return self._parse_datetime(datetime_str)
            except:
                pass
        
        # Try combined field
        gps_datetime = raw.get('GPSDateTime') or raw.get('GPS:DateTime')
        if gps_datetime:
            return self._parse_datetime(gps_datetime)
        
        return None
    
    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Parse datetime from various formats"""
        if value is None:
            return None
        
        if isinstance(value, datetime):
            return value
        
        if not isinstance(value, str):
            value = str(value)
        
        # Clean up the string
        value = value.strip()
        
        # Try each format
        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        
        # Try without subseconds
        if '.' in value:
            base_value = value.split('.')[0]
            for fmt in self.DATE_FORMATS:
                try:
                    return datetime.strptime(base_value, fmt)
                except ValueError:
                    continue
        
        logger.debug(f"Could not parse datetime: {value}")
        return None
    
    def _extract_float(self, raw: Dict[str, Any], field_names: List[str]) -> Optional[float]:
        """Extract float value from multiple possible fields"""
        for field in field_names:
            value = raw.get(field)
            if value is not None:
                try:
                    if isinstance(value, str):
                        # Handle formats like "100 km/h"
                        value = re.match(r'([\d.]+)', value)
                        if value:
                            return float(value.group(1))
                    return float(value)
                except (ValueError, TypeError):
                    continue
        return None
    
    def _extract_int(self, raw: Dict[str, Any], field_names: List[str]) -> Optional[int]:
        """Extract integer value from multiple possible fields"""
        for field in field_names:
            value = raw.get(field)
            if value is not None:
                try:
                    if isinstance(value, str):
                        # Handle formats like "100 pixels"
                        value = re.match(r'(\d+)', value)
                        if value:
                            return int(value.group(1))
                    return int(value)
                except (ValueError, TypeError):
                    continue
        return None
    
    def _extract_thumbnail(self, metadata: ExifToolMetadata, raw: Dict[str, Any]) -> None:
        """
        Extract and encode thumbnail data from raw metadata
        
        Args:
            metadata: ExifToolMetadata object to update
            raw: Raw metadata dictionary from ExifTool
        """
        logger.info(f"THUMBNAIL CHECK for {metadata.file_path.name}")
        
        # Check for thumbnail fields in order of preference
        thumbnail_fields = [
            ('ThumbnailImage', 'ThumbnailImage'),      # Most common JPEG thumbnail
            ('PreviewImage', 'PreviewImage'),          # Larger preview image
            ('JpgFromRaw', 'JpgFromRaw'),             # JPEG extracted from RAW
        ]
        
        for field_name, field_type in thumbnail_fields:
            thumbnail_data = raw.get(field_name)
            if thumbnail_data:
                logger.info(f"THUMBNAIL FOUND: {field_type} for {metadata.file_path.name}, data type: {type(thumbnail_data)}")
                # ExifTool with -b flag in JSON mode returns base64 strings
                if isinstance(thumbnail_data, str):
                    # Log first 100 chars to check format
                    logger.debug(f"Thumbnail data preview (first 100 chars): {thumbnail_data[:100]}")
                    
                    # Remove 'base64:' prefix if present (ExifTool adds this)
                    if thumbnail_data.startswith('base64:'):
                        thumbnail_data = thumbnail_data[7:]  # Remove 'base64:' prefix
                        logger.debug("Removed 'base64:' prefix from thumbnail data")
                    
                    # Clean up any whitespace or newlines
                    thumbnail_data = thumbnail_data.strip().replace('\n', '').replace('\r', '')
                    
                    # It's already base64 encoded from ExifTool
                    metadata.thumbnail_base64 = thumbnail_data
                    metadata.thumbnail_type = field_type
                    logger.info(f"THUMBNAIL EXTRACTED: {field_type} thumbnail for {metadata.file_path.name}, base64 length: {len(metadata.thumbnail_base64)}")
                    return
                elif isinstance(thumbnail_data, bytes):
                    # If it's raw bytes, encode to base64
                    import base64
                    metadata.thumbnail_base64 = base64.b64encode(thumbnail_data).decode('utf-8')
                    metadata.thumbnail_type = field_type
                    logger.debug(f"Encoded {field_type} thumbnail for {metadata.file_path.name}")
                    return
        
        logger.debug(f"No thumbnail found for {metadata.file_path.name}")