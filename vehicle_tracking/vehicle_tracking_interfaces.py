#!/usr/bin/env python3
"""
Vehicle Tracking Service Interfaces

These interface definitions should be added to core/services/interfaces.py
for proper dependency injection integration.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from core.result_types import Result

# Import vehicle tracking models
from vehicle_tracking.models.vehicle_tracking_models import (
    VehicleData, VehicleTrackingSettings, AnimationData,
    VehicleAnalysisResult, AnalysisType
)


# ============================================================================
# ADD TO core/services/interfaces.py
# ============================================================================

class IVehicleTrackingService(IService):
    """
    Interface for vehicle tracking service
    
    Handles GPS data processing, speed calculation, and interpolation.
    """
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def calculate_speeds(
        self, 
        vehicle_data: VehicleData,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Result[VehicleData]:
        """
        Calculate speeds between GPS points
        
        Args:
            vehicle_data: Vehicle data with GPS points
            progress_callback: Optional progress callback
            
        Returns:
            Result containing updated VehicleData with calculated speeds
        """
        pass
    
    @abstractmethod
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
            settings: Processing settings with interpolation config
            progress_callback: Optional progress callback
            
        Returns:
            Result containing interpolated VehicleData
        """
        pass
    
    @abstractmethod
    def prepare_animation_data(
        self, 
        vehicles: List[VehicleData], 
        settings: VehicleTrackingSettings
    ) -> Result[AnimationData]:
        """
        Prepare data for map animation
        
        Args:
            vehicles: List of vehicle data
            settings: Processing settings
            
        Returns:
            Result containing AnimationData
        """
        pass
    
    @abstractmethod
    def clear_cache(self):
        """Clear all cached vehicle data"""
        pass
    
    @abstractmethod
    def get_cached_vehicle(self, vehicle_id: str) -> Optional[VehicleData]:
        """
        Get cached vehicle data if available
        
        Args:
            vehicle_id: Vehicle identifier
            
        Returns:
            Cached VehicleData or None
        """
        pass


class IMapTemplateService(IService):
    """
    Interface for map template management service
    
    Handles loading, selection, and configuration of map providers.
    """
    
    @abstractmethod
    def get_available_providers(self) -> List[str]:
        """
        Get list of available map providers
        
        Returns:
            List of provider names (e.g., ['leaflet', 'mapbox', 'google'])
        """
        pass
    
    @abstractmethod
    def load_template(
        self, 
        provider: str, 
        container_id: str = "map"
    ) -> Result[str]:
        """
        Load map template HTML for specified provider
        
        Args:
            provider: Provider name
            container_id: HTML container ID for map
            
        Returns:
            Result containing template HTML or error
        """
        pass
    
    @abstractmethod
    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """
        Get configuration for specific provider
        
        Args:
            provider: Provider name
            
        Returns:
            Provider configuration dictionary
        """
        pass
    
    @abstractmethod
    def set_provider_config(
        self, 
        provider: str, 
        config: Dict[str, Any]
    ) -> Result[None]:
        """
        Update provider configuration
        
        Args:
            provider: Provider name
            config: Configuration dictionary
            
        Returns:
            Result indicating success or error
        """
        pass
    
    @abstractmethod
    def validate_api_key(self, provider: str, api_key: str) -> Result[bool]:
        """
        Validate API key for provider
        
        Args:
            provider: Provider name
            api_key: API key to validate
            
        Returns:
            Result containing validation status
        """
        pass
    
    @abstractmethod
    def get_default_provider(self) -> str:
        """
        Get the default map provider
        
        Returns:
            Default provider name
        """
        pass
    
    @abstractmethod
    def set_default_provider(self, provider: str) -> Result[None]:
        """
        Set the default map provider
        
        Args:
            provider: Provider name
            
        Returns:
            Result indicating success or error
        """
        pass


class IVehicleAnalysisService(IService):
    """
    Interface for vehicle analysis service
    
    Handles co-location detection, timestamp analysis, and other analytics.
    (Future implementation - stubbed for extensibility)
    """
    
    @abstractmethod
    def analyze_co_location(
        self,
        vehicles: List[VehicleData],
        radius_meters: float = 50.0,
        time_window_seconds: float = 300.0,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Result[VehicleAnalysisResult]:
        """
        Detect when vehicles were at the same location
        
        Args:
            vehicles: List of vehicles to analyze
            radius_meters: Co-location radius
            time_window_seconds: Time window for co-location
            progress_callback: Optional progress callback
            
        Returns:
            Result containing co-location analysis
        """
        pass
    
    @abstractmethod
    def detect_timestamp_jumps(
        self,
        vehicle: VehicleData,
        threshold_seconds: float = 3600.0
    ) -> Result[VehicleAnalysisResult]:
        """
        Find gaps in GPS data timestamps
        
        Args:
            vehicle: Vehicle data to analyze
            threshold_seconds: Minimum gap to consider a jump
            
        Returns:
            Result containing timestamp jump analysis
        """
        pass
    
    @abstractmethod
    def detect_idling(
        self,
        vehicle: VehicleData,
        speed_threshold_kmh: float = 5.0,
        minimum_duration_seconds: float = 60.0
    ) -> Result[VehicleAnalysisResult]:
        """
        Detect periods where vehicle was idling
        
        Args:
            vehicle: Vehicle data to analyze
            speed_threshold_kmh: Maximum speed for idling
            minimum_duration_seconds: Minimum idling duration
            
        Returns:
            Result containing idling analysis
        """
        pass
    
    @abstractmethod
    def analyze_route_similarity(
        self,
        vehicles: List[VehicleData],
        similarity_threshold: float = 0.8
    ) -> Result[VehicleAnalysisResult]:
        """
        Compare routes between vehicles for similarity
        
        Args:
            vehicles: Vehicles to compare
            similarity_threshold: Minimum similarity score
            
        Returns:
            Result containing route similarity analysis
        """
        pass
    
    @abstractmethod
    def run_analysis_suite(
        self,
        vehicles: List[VehicleData],
        analysis_types: List[AnalysisType],
        settings: Dict[str, Any]
    ) -> Result[List[VehicleAnalysisResult]]:
        """
        Run multiple analysis types on vehicle data
        
        Args:
            vehicles: Vehicles to analyze
            analysis_types: Types of analysis to perform
            settings: Analysis settings
            
        Returns:
            Result containing all analysis results
        """
        pass


class IVehicleTrackingSuccessService(IService):
    """
    Interface for vehicle tracking success message builder
    
    Creates success messages for vehicle tracking operations.
    """
    
    @abstractmethod
    def build_tracking_success(
        self,
        vehicles_processed: int,
        total_points: int,
        processing_time: float,
        has_animation: bool = False,
        skipped_files: int = 0
    ) -> 'SuccessMessageData':
        """
        Build success message for vehicle tracking
        
        Args:
            vehicles_processed: Number of vehicles processed
            total_points: Total GPS points processed
            processing_time: Processing duration in seconds
            has_animation: Whether animation was created
            skipped_files: Number of files skipped
            
        Returns:
            SuccessMessageData for display
        """
        pass
    
    @abstractmethod
    def build_analysis_success(
        self,
        analysis_type: AnalysisType,
        events_found: int,
        vehicles_analyzed: int,
        processing_time: float
    ) -> 'SuccessMessageData':
        """
        Build success message for analysis operations
        
        Args:
            analysis_type: Type of analysis performed
            events_found: Number of events/findings
            vehicles_analyzed: Number of vehicles analyzed
            processing_time: Analysis duration in seconds
            
        Returns:
            SuccessMessageData for display
        """
        pass