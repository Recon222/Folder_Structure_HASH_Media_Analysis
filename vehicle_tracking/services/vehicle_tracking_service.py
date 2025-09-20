#!/usr/bin/env python3
"""
Vehicle Tracking Service - Core business logic for GPS processing

Handles CSV parsing, speed calculations, interpolation, and data preparation.
Follows FSA service patterns with Result-based error handling.
"""

import csv
import io
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2, floor
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable
import logging

from core.services.base_service import BaseService
from core.services.interfaces import IService, IVehicleTrackingService
from core.result_types import Result
from core.exceptions import ValidationError, FileOperationError, FSAError

# Import models from the vehicle_tracking package
from vehicle_tracking.models.vehicle_tracking_models import (
    GPSPoint, VehicleData, VehicleTrackingSettings, 
    AnimationData, VehicleTrackingResult, VehicleColor,
    InterpolationMethod
)

# Try to import pandas for better CSV handling (optional)
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# Try to import numpy for vectorized operations (optional)
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)


class VehicleTrackingError(FSAError):
    """Vehicle tracking specific errors"""
    pass


class VehicleTrackingService(BaseService, IVehicleTrackingService):
    """
    Service for vehicle tracking operations
    
    Handles all GPS processing logic including parsing, speed calculation,
    interpolation, and animation preparation.
    """
    
    # Earth's radius in kilometers
    EARTH_RADIUS_KM = 6371.0
    
    # CSV column mappings (can be configured)
    DEFAULT_COLUMN_MAPPINGS = {
        'latitude': ['latitude', 'lat', 'Latitude', 'LAT', 'GPS_Latitude', 'gps_lat'],
        'longitude': ['longitude', 'lon', 'lng', 'Longitude', 'LON', 'LNG', 'GPS_Longitude', 'long', 'gps_lon'],
        'timestamp': ['timestamp', 'time', 'datetime', 'Timestamp', 'TIME', 'DateTime', 'date_time', 'gps_time'],
        'speed': ['speed', 'speed_kmh', 'Speed', 'SPEED', 'Speed_KMH', 'velocity'],
        'altitude': ['altitude', 'alt', 'elevation', 'Altitude', 'ALT', 'height'],
        'heading': ['heading', 'bearing', 'direction', 'Heading', 'HEADING', 'BEARING', 'course']
    }
    
    def __init__(self):
        """Initialize vehicle tracking service"""
        super().__init__("VehicleTrackingService")
        
        # Cache for processed data
        self._vehicle_cache: Dict[str, VehicleData] = {}
        self._interpolation_cache: Dict[str, VehicleData] = {}
    
    def parse_csv_file(
        self, 
        file_path: Path, 
        settings: VehicleTrackingSettings,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Result[VehicleData]:
        """
        Parse CSV file and extract GPS data
        
        Args:
            file_path: Path to CSV file
            settings: Processing settings
            progress_callback: Optional progress callback
            
        Returns:
            Result containing VehicleData or error
        """
        try:
            self._log_operation("parse_csv_file", f"Parsing {file_path.name}")
            
            # Validate file
            if not file_path.exists():
                return Result.error(
                    ValidationError(
                        {'file': f"File not found: {file_path}"},
                        user_message=f"CSV file not found: {file_path.name}"
                    )
                )
            
            if not file_path.suffix.lower() == '.csv':
                return Result.error(
                    ValidationError(
                        {'file': f"Not a CSV file: {file_path}"},
                        user_message=f"File must be a CSV: {file_path.name}"
                    )
                )
            
            # Generate vehicle ID from filename
            vehicle_id = file_path.stem
            
            # Parse CSV based on available libraries
            if HAS_PANDAS:
                result = self._parse_csv_pandas(file_path, vehicle_id, settings, progress_callback)
            else:
                result = self._parse_csv_native(file_path, vehicle_id, settings, progress_callback)
            
            if result.success and result.value:
                # Cache the parsed data
                self._vehicle_cache[vehicle_id] = result.value
                self._log_operation("parse_csv_file", f"Successfully parsed {result.value.point_count} points")
            
            return result
            
        except Exception as e:
            error = VehicleTrackingError(
                f"Failed to parse CSV file: {e}",
                user_message=f"Error reading CSV file: {file_path.name}"
            )
            self._handle_error(error)
            return Result.error(error)
    
    def _parse_csv_pandas(
        self, 
        file_path: Path, 
        vehicle_id: str,
        settings: VehicleTrackingSettings,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Result[VehicleData]:
        """Parse CSV using pandas (faster for large files)"""
        try:
            # Read CSV in chunks for large files
            chunks = []
            total_rows = 0
            
            for chunk_num, chunk in enumerate(pd.read_csv(file_path, chunksize=settings.chunk_size)):
                chunks.append(chunk)
                total_rows += len(chunk)
                
                if progress_callback:
                    progress_callback(
                        min(90, (chunk_num + 1) * 10),
                        f"Reading chunk {chunk_num + 1}, {total_rows:,} rows"
                    )
                
                # Limit points if configured
                if total_rows >= settings.max_points_per_vehicle:
                    logger.warning(f"Limiting {vehicle_id} to {settings.max_points_per_vehicle} points")
                    break
            
            # Combine chunks
            df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
            
            if df.empty:
                return Result.error(
                    VehicleTrackingError(
                        f"No data in CSV file",
                        user_message="CSV file is empty or has no valid data"
                    )
                )
            
            # Map columns
            column_mapping = self._detect_columns(df.columns)
            if not column_mapping:
                return Result.error(
                    VehicleTrackingError(
                        f"Required columns not found in CSV",
                        user_message="CSV must have latitude, longitude, and timestamp columns"
                    )
                )
            
            # Create VehicleData
            vehicle_data = VehicleData(
                vehicle_id=vehicle_id,
                source_file=file_path
            )
            
            # Parse each row
            for idx, row in df.iterrows():
                gps_point = self._create_gps_point(row, column_mapping)
                if gps_point:
                    vehicle_data.gps_points.append(gps_point)
            
            # Calculate statistics
            vehicle_data.start_time, vehicle_data.end_time = vehicle_data.get_time_range()
            vehicle_data.is_processed = True
            
            return Result.success(vehicle_data)
            
        except Exception as e:
            return Result.error(
                VehicleTrackingError(
                    f"Pandas CSV parsing failed: {e}",
                    user_message=f"Error processing CSV with pandas: {str(e)}"
                )
            )
    
    def _parse_csv_native(
        self, 
        file_path: Path, 
        vehicle_id: str,
        settings: VehicleTrackingSettings,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Result[VehicleData]:
        """Parse CSV using native Python csv module"""
        try:
            vehicle_data = VehicleData(
                vehicle_id=vehicle_id,
                source_file=file_path
            )
            
            with open(file_path, 'r', encoding='utf-8-sig') as csvfile:
                # Detect delimiter (handle both comma and tab)
                sample = csvfile.read(1024)
                csvfile.seek(0)

                # Try tab first since it's common for GPS data
                if '\t' in sample:
                    delimiter = '\t'
                else:
                    try:
                        sniffer = csv.Sniffer()
                        delimiter = sniffer.sniff(sample).delimiter
                    except:
                        delimiter = ','

                reader = csv.DictReader(csvfile, delimiter=delimiter)

                # Clean fieldnames (remove BOM and strip whitespace)
                if reader.fieldnames:
                    reader.fieldnames = [field.strip() for field in reader.fieldnames]

                # Map columns (case-insensitive)
                column_mapping = self._detect_columns(reader.fieldnames)
                if not column_mapping:
                    return Result.error(
                        VehicleTrackingError(
                            f"Required columns not found",
                            user_message="CSV must have latitude, longitude, and timestamp columns"
                        )
                    )
                
                # Parse rows
                for row_num, row in enumerate(reader):
                    if row_num >= settings.max_points_per_vehicle:
                        logger.warning(f"Limiting {vehicle_id} to {settings.max_points_per_vehicle} points")
                        break
                    
                    gps_point = self._create_gps_point(row, column_mapping)
                    if gps_point:
                        vehicle_data.gps_points.append(gps_point)
                    
                    # Progress updates
                    if progress_callback and row_num % 1000 == 0:
                        progress_callback(
                            min(90, row_num / 100),
                            f"Processed {row_num:,} GPS points"
                        )
            
            if not vehicle_data.gps_points:
                return Result.error(
                    VehicleTrackingError(
                        "No valid GPS points found",
                        user_message="No valid GPS data found in CSV"
                    )
                )
            
            # Calculate statistics
            vehicle_data.start_time, vehicle_data.end_time = vehicle_data.get_time_range()
            vehicle_data.is_processed = True
            
            return Result.success(vehicle_data)
            
        except Exception as e:
            return Result.error(
                VehicleTrackingError(
                    f"CSV parsing failed: {e}",
                    user_message=f"Error reading CSV file: {str(e)}"
                )
            )
    
    def _detect_columns(self, columns: List[str]) -> Dict[str, str]:
        """Detect column mappings from CSV headers (case-insensitive)"""
        mapping = {}

        # Make columns lowercase for comparison
        columns_lower = {col.lower(): col for col in columns if col}

        for field, possible_names in self.DEFAULT_COLUMN_MAPPINGS.items():
            for possible_name in possible_names:
                if possible_name.lower() in columns_lower:
                    # Store the actual column name, not the lowercase version
                    mapping[field] = columns_lower[possible_name.lower()]
                    break

        # Check required fields
        if 'latitude' in mapping and 'longitude' in mapping and 'timestamp' in mapping:
            logger.info(f"Column mapping detected: {mapping}")
            return mapping

        # Log what was missing for debugging
        missing = []
        if 'latitude' not in mapping:
            missing.append('latitude')
        if 'longitude' not in mapping:
            missing.append('longitude')
        if 'timestamp' not in mapping:
            missing.append('timestamp')

        logger.warning(f"Missing required columns: {missing}. Available columns: {columns}")
        return None
    
    def _create_gps_point(self, row: Dict[str, Any], column_mapping: Dict[str, str]) -> Optional[GPSPoint]:
        """Create GPSPoint from CSV row"""
        try:
            # Required fields - skip rows with empty lat/lon
            lat_str = row.get(column_mapping['latitude'], '').strip()
            lon_str = row.get(column_mapping['longitude'], '').strip()

            if not lat_str or not lon_str:
                return None

            lat = float(lat_str)
            lon = float(lon_str)

            # Parse timestamp
            timestamp_str = row.get(column_mapping['timestamp'], '').strip()
            if not timestamp_str:
                return None

            timestamp = self._parse_timestamp(timestamp_str)

            if not timestamp:
                return None

            # Create GPS point
            point = GPSPoint(
                latitude=lat,
                longitude=lon,
                timestamp=timestamp
            )

            # Optional fields
            if 'speed' in column_mapping and column_mapping['speed'] in row:
                speed_str = row[column_mapping['speed']].strip()
                if speed_str and speed_str != '':
                    try:
                        point.speed_kmh = float(speed_str)
                    except (ValueError, TypeError):
                        pass

            if 'altitude' in column_mapping and column_mapping['altitude'] in row:
                alt_str = row[column_mapping['altitude']].strip()
                if alt_str and alt_str != '':
                    try:
                        point.altitude = float(alt_str)
                    except (ValueError, TypeError):
                        pass

            if 'heading' in column_mapping and column_mapping['heading'] in row:
                heading_str = row[column_mapping['heading']].strip()
                if heading_str and heading_str != '':
                    try:
                        point.heading = float(heading_str)
                    except (ValueError, TypeError):
                        pass
            
            return point
            
        except (ValueError, KeyError, TypeError) as e:
            logger.debug(f"Invalid GPS point: {e}")
            return None
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse timestamp string to datetime"""
        # Try common formats
        formats = [
            '%Y-%m-%d %H:%M',  # Your format: 2024-11-09 15:26
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M:%S.%f',
            '%Y/%m/%d %H:%M:%S',
            '%Y/%m/%d %H:%M',
            '%m/%d/%Y %H:%M:%S',
            '%m/%d/%Y %H:%M',
            '%d/%m/%Y %H:%M:%S',
            '%d/%m/%Y %H:%M',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%SZ',
        ]

        # Clean up the timestamp string
        timestamp_str = timestamp_str.strip()

        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue

        # Try parsing with dateutil if available
        try:
            from dateutil import parser
            return parser.parse(timestamp_str)
        except:
            pass

        logger.debug(f"Could not parse timestamp: {timestamp_str}")
        return None
    
    def calculate_speeds(
        self, 
        vehicle_data: VehicleData,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Result[VehicleData]:
        """
        Calculate speeds between GPS points using Haversine formula
        
        Args:
            vehicle_data: Vehicle data with GPS points
            progress_callback: Optional progress callback
            
        Returns:
            Result containing updated VehicleData with calculated speeds
        """
        try:
            self._log_operation("calculate_speeds", f"Calculating speeds for {vehicle_data.vehicle_id}")
            
            if len(vehicle_data.gps_points) < 2:
                return Result.success(vehicle_data)
            
            speeds = []
            max_speed = 0
            total_distance = 0
            
            for i in range(len(vehicle_data.gps_points)):
                if i == 0:
                    # First point - use next point for speed
                    if len(vehicle_data.gps_points) > 1:
                        speed, distance = self._calculate_speed_and_distance(
                            vehicle_data.gps_points[0],
                            vehicle_data.gps_points[1]
                        )
                        vehicle_data.gps_points[0].calculated_speed_kmh = speed
                        vehicle_data.gps_points[0].distance_from_previous = 0
                else:
                    # Calculate from previous point
                    speed, distance = self._calculate_speed_and_distance(
                        vehicle_data.gps_points[i-1],
                        vehicle_data.gps_points[i]
                    )
                    
                    vehicle_data.gps_points[i].calculated_speed_kmh = speed
                    vehicle_data.gps_points[i].distance_from_previous = distance
                    
                    speeds.append(speed)
                    max_speed = max(max_speed, speed)
                    total_distance += distance
                
                # Progress update
                if progress_callback and i % 1000 == 0:
                    progress = (i / len(vehicle_data.gps_points)) * 100
                    progress_callback(progress, f"Calculating speeds: {i}/{len(vehicle_data.gps_points)}")
            
            # Update vehicle statistics
            if speeds:
                vehicle_data.average_speed_kmh = sum(speeds) / len(speeds)
                vehicle_data.max_speed_kmh = max_speed
                vehicle_data.total_distance_km = total_distance
                
                if vehicle_data.start_time and vehicle_data.end_time:
                    vehicle_data.duration_seconds = (
                        vehicle_data.end_time - vehicle_data.start_time
                    ).total_seconds()
            
            self._log_operation("calculate_speeds", 
                              f"Completed: avg={vehicle_data.average_speed_kmh:.1f} km/h, "
                              f"max={vehicle_data.max_speed_kmh:.1f} km/h")
            
            return Result.success(vehicle_data)
            
        except Exception as e:
            error = VehicleTrackingError(
                f"Speed calculation failed: {e}",
                user_message="Error calculating vehicle speeds"
            )
            self._handle_error(error)
            return Result.error(error)
    
    def _calculate_speed_and_distance(
        self, 
        point1: GPSPoint, 
        point2: GPSPoint
    ) -> Tuple[float, float]:
        """
        Calculate speed and distance between two GPS points using Haversine formula
        
        Returns:
            Tuple of (speed_kmh, distance_km)
        """
        # Haversine formula
        lat1_rad = radians(point1.latitude)
        lon1_rad = radians(point1.longitude)
        lat2_rad = radians(point2.latitude)
        lon2_rad = radians(point2.longitude)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance_km = self.EARTH_RADIUS_KM * c
        
        # Calculate time difference
        time_diff = (point2.timestamp - point1.timestamp).total_seconds()
        
        # Calculate speed (avoid division by zero)
        if time_diff > 0:
            speed_kmh = (distance_km / time_diff) * 3600  # Convert to km/h
        else:
            speed_kmh = 0
        
        return speed_kmh, distance_km

    def _interpolate_heading(self, heading1: float, heading2: float, ratio: float) -> float:
        """
        Circular interpolation for compass headings (0-360 degrees)
        Handles wraparound at 0/360 boundary by taking shortest angular path

        Args:
            heading1: Starting heading in degrees
            heading2: Ending heading in degrees
            ratio: Interpolation ratio (0.0 to 1.0)

        Returns:
            Interpolated heading in degrees (0-360)
        """
        # Normalize to 0-360 range
        h1 = heading1 % 360
        h2 = heading2 % 360

        # Find shortest angular distance
        diff = h2 - h1
        if diff > 180:
            diff -= 360
        elif diff < -180:
            diff += 360

        # Interpolate
        result = h1 + diff * ratio

        # Normalize result to 0-360
        if result < 0:
            result += 360
        elif result >= 360:
            result -= 360

        return result

    def _is_uniform_cadence(self, points: List[GPSPoint], dt: float = 1.0, tol: float = 1e-3) -> bool:
        """
        Check if GPS points are already at uniform intervals.
        Also validates no missing segments.

        Args:
            points: GPS points to check
            dt: Expected time interval in seconds
            tol: Tolerance for floating-point comparison

        Returns:
            True if points are uniformly spaced at dt intervals
        """
        if len(points) < 2:
            return True

        # Check both time spacing AND continuous sequence
        for i in range(1, len(points)):
            expected = points[0].timestamp + timedelta(seconds=i * dt)
            actual = points[i].timestamp
            if abs((actual - expected).total_seconds()) > tol:
                return False

        # Log when we skip interpolation
        self._log_operation("uniform_cadence_check",
                           f"Data already at {dt}s intervals, skipping interpolation")
        return True

    def interpolate_path_global_resampling(
        self,
        vehicle_data: VehicleData,
        settings: VehicleTrackingSettings,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Result[VehicleData]:
        """
        Global resampling interpolation - samples path at uniform time intervals.
        This eliminates variance and ensures perfectly even time spacing.

        Args:
            vehicle_data: Vehicle data to interpolate
            settings: Processing settings
            progress_callback: Optional progress callback

        Returns:
            Result containing interpolated VehicleData with uniform time spacing
        """
        try:
            points = vehicle_data.gps_points
            if len(points) < 2:
                return Result.success(vehicle_data)

            dt = settings.interpolation_interval_seconds

            # Check if data is already at target cadence
            if self._is_uniform_cadence(points, dt):
                self._log_operation("interpolate_path_global_resampling",
                                  f"Input already at {dt}s cadence, passthrough")
                return Result.success(vehicle_data)  # Return unchanged

            interpolated = []

            # Always include first point
            interpolated.append(points[0])

            # Initialize emission time to first interval after start
            t_emit = points[0].timestamp + timedelta(seconds=dt)
            seg_idx = 0

            # Track progress
            total_duration = (points[-1].timestamp - points[0].timestamp).total_seconds()

            # Walk through time at exact intervals
            while seg_idx < len(points) - 1 and t_emit <= points[-1].timestamp:
                seg_start = points[seg_idx]
                seg_end = points[seg_idx + 1]

                # Find the segment containing t_emit
                while seg_idx < len(points) - 1 and t_emit > seg_end.timestamp:
                    seg_idx += 1
                    if seg_idx < len(points) - 1:
                        seg_start = points[seg_idx]
                        seg_end = points[seg_idx + 1]

                # If t_emit falls within this segment, interpolate
                if seg_idx < len(points) - 1 and t_emit <= seg_end.timestamp:
                    # Calculate position ratio within segment
                    seg_duration = (seg_end.timestamp - seg_start.timestamp).total_seconds()

                    if seg_duration > 0:
                        time_ratio = (t_emit - seg_start.timestamp).total_seconds() / seg_duration

                        # Snap to exact point if very close (within 1ms)
                        if abs((t_emit - seg_start.timestamp).total_seconds()) < 0.001:
                            interpolated.append(seg_start)
                            # Grid-quantized emission to prevent float drift
                            elapsed = (t_emit - points[0].timestamp).total_seconds()
                            k = floor(elapsed / dt + 1e-6) + 1
                            t_emit = points[0].timestamp + timedelta(seconds=k * dt)
                            continue
                        if abs((t_emit - seg_end.timestamp).total_seconds()) < 0.001:
                            interpolated.append(seg_end)
                            # Grid-quantized emission to prevent float drift
                            elapsed = (t_emit - points[0].timestamp).total_seconds()
                            k = floor(elapsed / dt + 1e-6) + 1
                            t_emit = points[0].timestamp + timedelta(seconds=k * dt)
                            continue

                        # Linear interpolation of position
                        lat = seg_start.latitude + (seg_end.latitude - seg_start.latitude) * time_ratio
                        lon = seg_start.longitude + (seg_end.longitude - seg_start.longitude) * time_ratio

                        # Interpolate speed
                        start_speed = seg_start.calculated_speed_kmh or seg_start.speed_kmh or 0
                        end_speed = seg_end.calculated_speed_kmh or seg_end.speed_kmh or 0
                        speed = start_speed + (end_speed - start_speed) * time_ratio

                        # Create interpolated point
                        interp_point = GPSPoint(
                            latitude=lat,
                            longitude=lon,
                            timestamp=t_emit,
                            calculated_speed_kmh=speed,
                            is_interpolated=True
                        )

                        # Interpolate optional fields
                        if seg_start.altitude is not None and seg_end.altitude is not None:
                            interp_point.altitude = seg_start.altitude + \
                                                   (seg_end.altitude - seg_start.altitude) * time_ratio

                        if seg_start.heading is not None and seg_end.heading is not None:
                            interp_point.heading = self._interpolate_heading(
                                seg_start.heading, seg_end.heading, time_ratio
                            )

                        interpolated.append(interp_point)

                    # Grid-quantized emission to prevent float drift
                    elapsed = (t_emit - points[0].timestamp).total_seconds()
                    k = floor(elapsed / dt + 1e-6) + 1
                    t_emit = points[0].timestamp + timedelta(seconds=k * dt)

                    # Update progress
                    if progress_callback:
                        elapsed = (t_emit - points[0].timestamp).total_seconds()
                        progress = min(100, (elapsed / total_duration) * 100)
                        progress_callback(progress, f"Global resampling: {len(interpolated)} points")
                else:
                    # Move to next time if we've gone past the data (grid-quantized)
                    elapsed = (t_emit - points[0].timestamp).total_seconds()
                    k = floor(elapsed / dt + 1e-6) + 1
                    t_emit = points[0].timestamp + timedelta(seconds=k * dt)

            # Always include last point
            if interpolated[-1].timestamp != points[-1].timestamp:
                interpolated.append(points[-1])

            # Update vehicle data
            vehicle_data.gps_points = interpolated
            vehicle_data.has_interpolated_points = True

            self._log_operation("interpolate_path_global_resampling",
                              f"Resampled from {len(points)} to {len(interpolated)} points "
                              f"with perfect {dt}s spacing")

            return Result.success(vehicle_data)

        except Exception as e:
            error = VehicleTrackingError(
                f"Global resampling failed: {e}",
                user_message="Error resampling GPS path"
            )
            self._handle_error(error)
            return Result.error(error)

    def interpolate_path(
        self,
        vehicle_data: VehicleData,
        settings: VehicleTrackingSettings,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Result[VehicleData]:
        """
        Interpolate GPS points for smooth animation using global resampling.
        This ensures perfectly even time spacing with zero variance.

        Args:
            vehicle_data: Vehicle data to interpolate
            settings: Processing settings
            progress_callback: Optional progress callback

        Returns:
            Result containing interpolated VehicleData with uniform time spacing
        """
        try:
            if not settings.interpolation_enabled:
                return Result.success(vehicle_data)

            self._log_operation("interpolate_path",
                              f"Using global resampling for {vehicle_data.vehicle_id} "
                              f"with {settings.interpolation_interval_seconds}s interval")

            # Check cache
            cache_key = f"{vehicle_data.vehicle_id}_{settings.interpolation_interval_seconds}"
            if cache_key in self._interpolation_cache:
                return Result.success(self._interpolation_cache[cache_key])

            # Use the new global resampling method
            result = self.interpolate_path_global_resampling(vehicle_data, settings, progress_callback)

            # Cache the successful result
            if result.success:
                self._interpolation_cache[cache_key] = result.value

            return result
            
        except Exception as e:
            error = VehicleTrackingError(
                f"Interpolation failed: {e}",
                user_message="Error interpolating GPS path"
            )
            self._handle_error(error)
            return Result.error(error)
    
    def prepare_animation_data(
        self,
        vehicles: List[VehicleData],
        settings: VehicleTrackingSettings
    ) -> Result[AnimationData]:
        """
        Prepare data for map animation with TimestampedGeoJson support

        Args:
            vehicles: List of vehicle data
            settings: Processing settings

        Returns:
            Result containing AnimationData with properly formatted GeoJSON
        """
        try:
            self._log_operation("prepare_animation_data", f"Preparing animation for {len(vehicles)} vehicles")

            if not vehicles:
                return Result.error(
                    ValidationError(
                        {'vehicles': 'No vehicles to animate'},
                        user_message="No vehicle data available for animation"
                    )
                )

            # IMPORTANT: Validate and ensure all GPS points have proper datetime objects
            for vehicle in vehicles:
                valid_points = []
                for point in vehicle.gps_points:
                    # Ensure timestamp is a datetime object, not a string
                    if isinstance(point.timestamp, str):
                        try:
                            # Try to parse the timestamp if it's a string
                            point.timestamp = datetime.fromisoformat(point.timestamp.replace('Z', '+00:00'))
                        except (ValueError, AttributeError) as e:
                            self._log_operation("prepare_animation_data",
                                              f"Skipping invalid timestamp: {point.timestamp}")
                            continue  # Skip points with invalid timestamps

                    # Only include points with valid datetime objects
                    if isinstance(point.timestamp, datetime):
                        valid_points.append(point)

                # Update vehicle with only valid points
                vehicle.gps_points = valid_points

            # Remove vehicles with no valid points
            vehicles = [v for v in vehicles if len(v.gps_points) > 0]

            if not vehicles:
                return Result.error(
                    ValidationError(
                        {'vehicles': 'No valid GPS data after timestamp validation'},
                        user_message="No valid GPS timestamps found in the data"
                    )
                )

            animation_data = AnimationData(vehicles=vehicles)

            # Calculate timeline bounds
            all_start_times = []
            all_end_times = []
            all_lats = []
            all_lons = []

            for vehicle in vehicles:
                start, end = vehicle.get_time_range()
                if start and end:
                    all_start_times.append(start)
                    all_end_times.append(end)

                bounds = vehicle.get_bounds()
                if bounds:
                    min_lat, min_lon, max_lat, max_lon = bounds
                    all_lats.extend([min_lat, max_lat])
                    all_lons.extend([min_lon, max_lon])

            if all_start_times and all_end_times:
                animation_data.timeline_start = min(all_start_times)
                animation_data.timeline_end = max(all_end_times)
                animation_data.total_duration_seconds = (
                    animation_data.timeline_end - animation_data.timeline_start
                ).total_seconds()

            # Calculate map bounds
            if all_lats and all_lons:
                animation_data.bounds = (
                    min(all_lats), min(all_lons),
                    max(all_lats), max(all_lons)
                )
                animation_data.center = (
                    sum(all_lats) / len(all_lats),
                    sum(all_lons) / len(all_lons)
                )
                animation_data.zoom_level = settings.default_zoom_level

            # ALWAYS generate GeoJSON for TimestampedGeoJson compatibility
            # This ensures proper time formatting and feature structure
            animation_data.to_geojson()

            self._log_operation("prepare_animation_data",
                              f"Animation ready: {animation_data.total_duration_seconds:.1f}s duration, "
                              f"{sum(len(v.gps_points) for v in vehicles)} total points")

            return Result.success(animation_data)

        except Exception as e:
            error = VehicleTrackingError(
                f"Animation preparation failed: {e}",
                user_message="Error preparing animation data"
            )
            self._handle_error(error)
            return Result.error(error)
    
    def clear_cache(self):
        """Clear all cached data"""
        self._vehicle_cache.clear()
        self._interpolation_cache.clear()
        self._log_operation("clear_cache", "Cache cleared")
    
    def get_cached_vehicle(self, vehicle_id: str) -> Optional[VehicleData]:
        """Get cached vehicle data if available"""
        return self._vehicle_cache.get(vehicle_id)

    def process_vehicle_files(
        self,
        files: List[Path],
        settings: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Result:
        """
        Process vehicle GPS data files - Main interface method

        This is the minimal interface method exposed to the core application.
        It processes multiple CSV files and returns analyzed vehicle data.

        Args:
            files: List of CSV files containing GPS data
            settings: Optional processing settings dictionary
            progress_callback: Optional callback for progress updates

        Returns:
            Result containing VehicleTrackingResult with processed data or error
        """
        try:
            # Convert settings dict to VehicleTrackingSettings if provided
            if settings:
                # Handle dict to VehicleTrackingSettings conversion
                tracking_settings = VehicleTrackingSettings(**settings) if isinstance(settings, dict) else settings
            else:
                tracking_settings = VehicleTrackingSettings()

            processed_vehicles = []
            total_points = 0
            import time
            start_time = time.time()

            # Process each file
            for i, file_path in enumerate(files):
                if progress_callback:
                    progress = (i / len(files)) * 100
                    progress_callback(progress, f"Processing {file_path.name}")

                # Parse CSV file
                result = self.parse_csv_file(file_path, tracking_settings, progress_callback)

                if result.success:
                    vehicle_data = result.value

                    # Calculate speeds if needed
                    if tracking_settings.calculate_speeds:
                        speed_result = self.calculate_speeds(vehicle_data, progress_callback)
                        if speed_result.success:
                            vehicle_data = speed_result.value

                    # Interpolate if enabled
                    if tracking_settings.interpolation_enabled:
                        interp_result = self.interpolate_path(vehicle_data, tracking_settings, progress_callback)
                        if interp_result.success:
                            vehicle_data = interp_result.value

                    processed_vehicles.append(vehicle_data)
                    total_points += vehicle_data.point_count

            # Prepare animation data
            animation_data = None
            if processed_vehicles:
                animation_result = self.prepare_animation_data(processed_vehicles, tracking_settings)
                if animation_result.success:
                    animation_data = animation_result.value

            # Create tracking result
            if processed_vehicles:
                tracking_result = VehicleTrackingResult(
                    vehicles_processed=len(processed_vehicles),
                    total_points_processed=total_points,
                    processing_time_seconds=time.time() - start_time,
                    vehicle_data=processed_vehicles,
                    animation_data=animation_data
                )

                return Result.success(tracking_result)
            else:
                return Result.error(
                    ValidationError(
                        {'files': 'No valid vehicle data processed'},
                        user_message="Could not process any vehicle files"
                    )
                )

        except Exception as e:
            error = VehicleTrackingError(
                f"Vehicle file processing failed: {e}",
                user_message="Error processing vehicle tracking files"
            )
            self._handle_error(error)
            return Result.error(error)