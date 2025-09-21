#!/usr/bin/env python3
"""
Vehicle Tracking Data Models

Defines all data structures for the vehicle tracking system.
Follows existing FSA patterns with dataclasses and comprehensive type hints.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum


class InterpolationMethod(Enum):
    """Interpolation methods for GPS path smoothing"""
    LINEAR = "linear"
    CUBIC = "cubic"
    GEODESIC = "geodesic"


class PlaybackSpeed(Enum):
    """Animation playback speed options"""
    SLOW = 0.5
    NORMAL = 1.0
    FAST = 2.0
    VERY_FAST = 5.0
    ULTRA_FAST = 10.0


class VehicleColor(Enum):
    """Predefined vehicle colors for map display"""
    BLUE = "#0066CC"
    RED = "#CC0000"
    GREEN = "#00CC00"
    PURPLE = "#CC00CC"
    ORANGE = "#FF9900"
    CYAN = "#00CCCC"
    MAGENTA = "#CC0066"
    YELLOW = "#FFCC00"
    GRAY = "#808080"
    BLACK = "#000000"


class AnalysisType(Enum):
    """Types of vehicle analysis (future expansion)"""
    CO_LOCATION = "co_location"
    TIMESTAMP_JUMP = "timestamp_jump"
    IDLING = "idling"
    ROUTE_SIMILARITY = "route_similarity"
    SPEED_ANALYSIS = "speed_analysis"


@dataclass
class GPSPoint:
    """
    Individual GPS measurement with timestamp
    
    Core data structure representing a single GPS reading from vehicle infotainment system.
    """
    latitude: float
    longitude: float
    timestamp: datetime
    
    # Optional fields that may be in CSV
    speed_kmh: Optional[float] = None
    altitude: Optional[float] = None
    heading: Optional[float] = None
    accuracy: Optional[float] = None
    
    # Calculated fields
    calculated_speed_kmh: Optional[float] = None
    distance_from_previous: Optional[float] = None
    time_from_previous: Optional[float] = None
    
    # Flags
    is_interpolated: bool = False
    is_anomaly: bool = False

    # Metadata for gaps, stops, anomalies, etc.
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'lat': self.latitude,
            'lon': self.longitude,
            'timestamp': self.timestamp.isoformat(),
            'speed': self.speed_kmh or self.calculated_speed_kmh,
            'altitude': self.altitude,
            'heading': self.heading,
            'interpolated': self.is_interpolated
        }
    
    def to_geojson_coordinates(self) -> List[float]:
        """Convert to GeoJSON coordinate format [lon, lat, alt]"""
        coords = [self.longitude, self.latitude]
        if self.altitude is not None:
            coords.append(self.altitude)
        return coords


@dataclass
class VehicleData:
    """
    Complete GPS track for a single vehicle
    
    Contains all GPS points and metadata for one vehicle's journey.
    """
    vehicle_id: str
    source_file: Path
    gps_points: List[GPSPoint] = field(default_factory=list)
    
    # Metadata
    color: VehicleColor = VehicleColor.BLUE
    label: Optional[str] = None
    description: Optional[str] = None
    
    # Statistics (calculated after loading)
    total_distance_km: Optional[float] = None
    average_speed_kmh: Optional[float] = None
    max_speed_kmh: Optional[float] = None
    duration_seconds: Optional[float] = None
    
    # Time bounds
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Processing flags
    is_processed: bool = False
    has_interpolated_points: bool = False
    
    # Analysis results (future)
    co_locations: List[Dict[str, Any]] = field(default_factory=list)
    timestamp_jumps: List[Dict[str, Any]] = field(default_factory=list)
    idling_periods: List[Dict[str, Any]] = field(default_factory=list)
    
    def get_time_range(self) -> Tuple[datetime, datetime]:
        """Get the time range of this vehicle's data"""
        if not self.gps_points:
            return None, None
        
        if self.start_time and self.end_time:
            return self.start_time, self.end_time
        
        # Calculate from points
        self.start_time = min(p.timestamp for p in self.gps_points)
        self.end_time = max(p.timestamp for p in self.gps_points)
        return self.start_time, self.end_time
    
    def get_bounds(self) -> Tuple[float, float, float, float]:
        """Get geographic bounds [min_lat, min_lon, max_lat, max_lon]"""
        if not self.gps_points:
            return None
        
        lats = [p.latitude for p in self.gps_points]
        lons = [p.longitude for p in self.gps_points]
        
        return min(lats), min(lons), max(lats), max(lons)
    
    @property
    def point_count(self) -> int:
        """Total number of GPS points"""
        return len(self.gps_points)
    
    @property
    def display_name(self) -> str:
        """Get display name for UI"""
        return self.label or self.vehicle_id


@dataclass
class VehicleTrackingSettings:
    """Configuration for vehicle tracking processing"""
    
    # Interpolation settings
    interpolation_enabled: bool = True
    interpolation_method: InterpolationMethod = InterpolationMethod.LINEAR
    interpolation_interval_seconds: float = 1.0
    
    # Speed calculation
    calculate_speeds: bool = True
    speed_unit: str = "kmh"  # or "mph"
    max_reasonable_speed: float = 200.0  # km/h, for anomaly detection
    
    # Animation settings
    playback_speed: PlaybackSpeed = PlaybackSpeed.NORMAL
    show_trails: bool = True
    trail_length_seconds: float = 30.0
    marker_size: int = 10
    
    # Performance settings
    chunk_size: int = 10000  # For processing large CSV files
    max_points_per_vehicle: int = 100000  # Limit for browser performance
    decimation_threshold: int = 50000  # Simplify path if over this
    
    # Analysis settings (future)
    co_location_radius_meters: float = 50.0
    co_location_time_window_seconds: float = 300.0
    idling_speed_threshold_kmh: float = 5.0
    idling_minimum_duration_seconds: float = 60.0
    timestamp_jump_threshold_seconds: float = 3600.0
    
    # Map settings
    default_zoom_level: int = 13
    cluster_markers: bool = True
    auto_center: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'interpolation_enabled': self.interpolation_enabled,
            'interpolation_method': self.interpolation_method.value,
            'interpolation_interval': self.interpolation_interval_seconds,
            'calculate_speeds': self.calculate_speeds,
            'playback_speed': self.playback_speed.value,
            'show_trails': self.show_trails,
            'chunk_size': self.chunk_size
        }


@dataclass
class AnimationData:
    """
    Prepared data structure for map animation
    
    Contains processed and optimized data ready for JavaScript animation.
    """
    vehicles: List[VehicleData]
    
    # GeoJSON features for TimestampedGeoJson
    feature_collection: Dict[str, Any] = field(default_factory=dict)
    
    # Timeline data
    timeline_start: datetime = None
    timeline_end: datetime = None
    total_duration_seconds: float = 0.0
    
    # Frame data (if pre-calculated)
    frames: List[Dict[str, Any]] = field(default_factory=list)
    frame_interval_ms: int = 100  # milliseconds between frames
    
    # Map bounds for initial view
    bounds: Tuple[float, float, float, float] = None
    center: Tuple[float, float] = None
    zoom_level: int = 13
    
    def to_geojson(self) -> Dict[str, Any]:
        """Convert to GeoJSON FeatureCollection for map display with TimestampedGeoJson support"""
        if self.feature_collection:
            return self.feature_collection

        features = []
        for vehicle in self.vehicles:
            # Create individual point features with time property for TimestampedGeoJson
            for point in vehicle.gps_points:
                feature = {
                    'type': 'Feature',
                    'properties': {
                        'vehicle_id': vehicle.vehicle_id,
                        'vehicle_label': vehicle.label or vehicle.vehicle_id,  # Add label for display
                        'time': point.timestamp.isoformat(),  # ISO 8601 format for TimestampedGeoJson
                        'speed': point.speed_kmh or point.calculated_speed_kmh,
                        'color': vehicle.color.value,
                        'interpolated': point.is_interpolated,
                        'altitude': point.altitude,
                        'heading': point.heading
                    },
                    'geometry': {
                        'type': 'Point',
                        'coordinates': point.to_geojson_coordinates()
                    }
                }
                features.append(feature)

            # Add LineString trail with times array for progressive trail rendering
            if len(vehicle.gps_points) > 1:
                trail_feature = {
                    'type': 'Feature',
                    'properties': {
                        'vehicle_id': vehicle.vehicle_id,
                        'vehicle_label': vehicle.label or vehicle.vehicle_id,
                        'color': vehicle.color.value,
                        'type': 'trail',  # Identify as trail feature
                        'times': [p.timestamp.isoformat() for p in vehicle.gps_points]  # Array of times for TimestampedGeoJson
                    },
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': [p.to_geojson_coordinates() for p in vehicle.gps_points]
                    }
                }
                features.append(trail_feature)

        self.feature_collection = {
            'type': 'FeatureCollection',
            'features': features
        }
        return self.feature_collection


@dataclass
class CoLocationEvent:
    """Co-location analysis result (future implementation)"""
    vehicle_ids: List[str]
    location: Tuple[float, float]  # lat, lon
    timestamp: datetime
    duration_seconds: float
    radius_meters: float
    
    def get_center(self) -> Tuple[float, float]:
        """Get center point of co-location"""
        return self.location


@dataclass
class TimestampJump:
    """Timestamp jump analysis result (future implementation)"""
    vehicle_id: str
    start_time: datetime
    end_time: datetime
    gap_seconds: float
    last_location: Tuple[float, float]
    next_location: Tuple[float, float]
    distance_km: float


@dataclass
class IdlingPeriod:
    """Idling analysis result (future implementation)"""
    vehicle_id: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    location: Tuple[float, float]
    average_speed_kmh: float


@dataclass
class VehicleAnalysisResult:
    """Container for all analysis results (future implementation)"""
    vehicle_id: str
    analysis_type: AnalysisType
    timestamp: datetime
    
    # Analysis-specific results
    co_locations: List[CoLocationEvent] = field(default_factory=list)
    timestamp_jumps: List[TimestampJump] = field(default_factory=list)
    idling_periods: List[IdlingPeriod] = field(default_factory=list)
    
    # Statistics
    total_events: int = 0
    analysis_duration_seconds: float = 0.0
    
    def has_results(self) -> bool:
        """Check if analysis found any results"""
        return (len(self.co_locations) > 0 or 
                len(self.timestamp_jumps) > 0 or 
                len(self.idling_periods) > 0)


@dataclass
class VehicleTrackingResult:
    """
    Result of vehicle tracking operation
    
    Used with Result[T] pattern for error handling.
    """
    vehicles_processed: int = 0
    total_points_processed: int = 0
    processing_time_seconds: float = 0.0
    
    # Processed data
    vehicle_data: List[VehicleData] = field(default_factory=list)
    animation_data: Optional[AnimationData] = None
    
    # Analysis results (if performed)
    analysis_results: List[VehicleAnalysisResult] = field(default_factory=list)
    
    # Errors/warnings
    skipped_files: List[Tuple[Path, str]] = field(default_factory=list)  # (file, reason)
    warnings: List[str] = field(default_factory=list)
    
    # Performance metrics
    average_points_per_second: float = 0.0
    memory_usage_mb: float = 0.0
    
    def get_summary(self) -> str:
        """Get human-readable summary"""
        return (f"Processed {self.vehicles_processed} vehicles with "
                f"{self.total_points_processed:,} GPS points in "
                f"{self.processing_time_seconds:.1f} seconds")