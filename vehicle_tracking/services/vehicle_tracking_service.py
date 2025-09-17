#!/usr/bin/env python3
"""
Vehicle Tracking Service - Core business logic for GPS processing

Handles CSV parsing, speed calculations, interpolation, and data preparation.
Follows FSA service patterns with Result-based error handling.
"""

import csv
import io
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
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


class IVehicleTrackingService(IService):
    """Interface for vehicle tracking service"""
    
    def parse_csv_file(self, file_path: Path, settings: VehicleTrackingSettings) -> Result[VehicleData]:
        """Parse CSV file and extract GPS data"""
        pass
    
    def calculate_speeds(self, vehicle_data: VehicleData) -> Result[VehicleData]:
        """Calculate speeds between GPS points"""
        pass
    
    def interpolate_path(self, vehicle_data: VehicleData, settings: VehicleTrackingSettings) -> Result[VehicleData]:
        """Interpolate GPS points for smooth animation"""
        pass
    
    def prepare_animation_data(self, vehicles: List[VehicleData], settings: VehicleTrackingSettings) -> Result[AnimationData]:
        """Prepare data for map animation"""
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
        'latitude': ['latitude', 'lat', 'Latitude', 'LAT', 'GPS_Latitude'],
        'longitude': ['longitude', 'lon', 'lng', 'Longitude', 'LON', 'LNG', 'GPS_Longitude'],
        'timestamp': ['timestamp', 'time', 'datetime', 'Timestamp', 'TIME', 'DateTime'],
        'speed': ['speed', 'speed_kmh', 'Speed', 'SPEED', 'Speed_KMH'],
        'altitude': ['altitude', 'alt', 'elevation', 'Altitude', 'ALT'],
        'heading': ['heading', 'bearing', 'direction', 'Heading', 'HEADING']
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
            
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                # Detect delimiter
                sample = csvfile.read(1024)
                csvfile.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                
                # Map columns
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
        """Detect column mappings from CSV headers"""
        mapping = {}
        
        for field, possible_names in self.DEFAULT_COLUMN_MAPPINGS.items():
            for col in columns:
                if col in possible_names:
                    mapping[field] = col
                    break
        
        # Check required fields
        if 'latitude' in mapping and 'longitude' in mapping and 'timestamp' in mapping:
            return mapping
        
        return None
    
    def _create_gps_point(self, row: Dict[str, Any], column_mapping: Dict[str, str]) -> Optional[GPSPoint]:
        """Create GPSPoint from CSV row"""
        try:
            # Required fields
            lat = float(row[column_mapping['latitude']])
            lon = float(row[column_mapping['longitude']])
            
            # Parse timestamp
            timestamp_str = row[column_mapping['timestamp']]
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
                try:
                    point.speed_kmh = float(row[column_mapping['speed']])
                except (ValueError, TypeError):
                    pass
            
            if 'altitude' in column_mapping and column_mapping['altitude'] in row:
                try:
                    point.altitude = float(row[column_mapping['altitude']])
                except (ValueError, TypeError):
                    pass
            
            if 'heading' in column_mapping and column_mapping['heading'] in row:
                try:
                    point.heading = float(row[column_mapping['heading']])
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
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M:%S.%f',
            '%Y/%m/%d %H:%M:%S',
            '%m/%d/%Y %H:%M:%S',
            '%d/%m/%Y %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%fZ',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue
        
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
    
    def interpolate_path(
        self, 
        vehicle_data: VehicleData, 
        settings: VehicleTrackingSettings,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Result[VehicleData]:
        """
        Interpolate GPS points for smooth animation
        
        Args:
            vehicle_data: Vehicle data to interpolate
            settings: Processing settings
            progress_callback: Optional progress callback
            
        Returns:
            Result containing interpolated VehicleData
        """
        try:
            if not settings.interpolation_enabled:
                return Result.success(vehicle_data)
            
            self._log_operation("interpolate_path", 
                              f"Interpolating {vehicle_data.vehicle_id} "
                              f"with {settings.interpolation_interval_seconds}s interval")
            
            # Check cache
            cache_key = f"{vehicle_data.vehicle_id}_{settings.interpolation_interval_seconds}"
            if cache_key in self._interpolation_cache:
                return Result.success(self._interpolation_cache[cache_key])
            
            interpolated_points = []
            original_count = len(vehicle_data.gps_points)
            
            for i in range(len(vehicle_data.gps_points) - 1):
                current = vehicle_data.gps_points[i]
                next_point = vehicle_data.gps_points[i + 1]
                
                # Add original point
                interpolated_points.append(current)
                
                # Calculate time difference
                time_diff = (next_point.timestamp - current.timestamp).total_seconds()
                
                # Create interpolated points
                num_interpolated = max(1, int(time_diff / settings.interpolation_interval_seconds))
                
                if num_interpolated > 1 and settings.interpolation_method != InterpolationMethod.LINEAR:
                    # For non-linear methods, limit interpolation
                    num_interpolated = min(num_interpolated, 10)
                
                for j in range(1, num_interpolated):
                    ratio = j / num_interpolated
                    
                    # Linear interpolation (can be enhanced with other methods)
                    lat = current.latitude + (next_point.latitude - current.latitude) * ratio
                    lon = current.longitude + (next_point.longitude - current.longitude) * ratio
                    
                    # Interpolate timestamp
                    timestamp = current.timestamp + timedelta(seconds=j * settings.interpolation_interval_seconds)
                    
                    # Interpolate speed
                    current_speed = current.calculated_speed_kmh or current.speed_kmh or 0
                    next_speed = next_point.calculated_speed_kmh or next_point.speed_kmh or 0
                    speed = current_speed + (next_speed - current_speed) * ratio
                    
                    # Create interpolated point
                    interp_point = GPSPoint(
                        latitude=lat,
                        longitude=lon,
                        timestamp=timestamp,
                        calculated_speed_kmh=speed,
                        is_interpolated=True
                    )
                    
                    # Interpolate optional fields
                    if current.altitude is not None and next_point.altitude is not None:
                        interp_point.altitude = current.altitude + (next_point.altitude - current.altitude) * ratio
                    
                    if current.heading is not None and next_point.heading is not None:
                        interp_point.heading = current.heading + (next_point.heading - current.heading) * ratio
                    
                    interpolated_points.append(interp_point)
                
                # Progress update
                if progress_callback and i % 100 == 0:
                    progress = (i / len(vehicle_data.gps_points)) * 100
                    progress_callback(progress, f"Interpolating: {len(interpolated_points)} points")
            
            # Add last point
            if vehicle_data.gps_points:
                interpolated_points.append(vehicle_data.gps_points[-1])
            
            # Update vehicle data
            vehicle_data.gps_points = interpolated_points
            vehicle_data.has_interpolated_points = True
            
            # Cache the result
            self._interpolation_cache[cache_key] = vehicle_data
            
            self._log_operation("interpolate_path", 
                              f"Interpolated from {original_count} to {len(interpolated_points)} points")
            
            return Result.success(vehicle_data)
            
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