#!/usr/bin/env python3
"""
Vehicle Tracking Controller - Orchestration layer

Coordinates between UI, services, and worker threads for vehicle tracking operations.
Follows FSA controller patterns with resource management.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from controllers.base_controller import BaseController
from core.result_types import Result
from core.exceptions import ValidationError, FileOperationError, ErrorSeverity
from core.resource_coordinators import WorkerResourceCoordinator
from core.services.interfaces import IService

# Import models
from vehicle_tracking.models.vehicle_tracking_models import (
    VehicleData, VehicleTrackingSettings, AnimationData,
    VehicleTrackingResult, VehicleColor
)

# Import service interface (will be properly registered via DI)
from vehicle_tracking.services.vehicle_tracking_service import IVehicleTrackingService

# Import worker (to be created)
# from vehicle_tracking.workers.vehicle_tracking_worker import VehicleTrackingWorker


class VehicleTrackingController(BaseController):
    """
    Controller for vehicle tracking operations
    
    Orchestrates the workflow of loading CSV files, processing GPS data,
    generating animations, and managing map display.
    """
    
    def __init__(self):
        """Initialize vehicle tracking controller"""
        super().__init__("VehicleTrackingController")
        
        # Service dependencies (injected via DI)
        self._vehicle_service: Optional[IVehicleTrackingService] = None
        self._map_template_service = None  # Future: IMapTemplateService
        self._analysis_service = None  # Future: IVehicleAnalysisService
        
        # Current operation state
        self.current_worker = None
        self.current_vehicles: List[VehicleData] = []
        self.current_animation: Optional[AnimationData] = None
        self.current_settings: VehicleTrackingSettings = VehicleTrackingSettings()
        
        # Resource tracking
        self._operation_id: Optional[str] = None
        self._resource_coordinator: Optional[WorkerResourceCoordinator] = None
    
    def _create_resource_coordinator(self, component_id: str) -> WorkerResourceCoordinator:
        """
        Create resource coordinator for worker management
        
        Args:
            component_id: Unique component identifier
            
        Returns:
            WorkerResourceCoordinator instance
        """
        return WorkerResourceCoordinator(component_id)
    
    @property
    def vehicle_service(self) -> IVehicleTrackingService:
        """Lazy load vehicle tracking service"""
        if self._vehicle_service is None:
            self._vehicle_service = self._get_service(IVehicleTrackingService)
        return self._vehicle_service
    
    def load_csv_files(
        self,
        file_paths: List[Path],
        settings: Optional[VehicleTrackingSettings] = None
    ) -> Result[List[VehicleData]]:
        """
        Load and process CSV files containing vehicle GPS data
        
        Args:
            file_paths: List of CSV file paths
            settings: Optional processing settings
            
        Returns:
            Result containing list of VehicleData or error
        """
        try:
            self._log_operation("load_csv_files", f"Loading {len(file_paths)} files")
            
            # Validate inputs
            if not file_paths:
                error = ValidationError(
                    {'files': 'No files selected'},
                    user_message="Please select CSV files to load"
                )
                self._handle_error(error, {'method': 'load_csv_files'})
                return Result.error(error)
            
            # Use provided settings or defaults
            if settings:
                self.current_settings = settings
            
            # Initialize resource coordinator
            self._operation_id = f"vehicle_load_{datetime.now().timestamp()}"
            self._resource_coordinator = self._create_resource_coordinator(self._operation_id)
            
            # Process each CSV file
            vehicles = []
            errors = []
            
            for idx, file_path in enumerate(file_paths):
                self._log_operation("load_csv_file", f"Processing {file_path.name}")
                
                # Parse CSV
                result = self.vehicle_service.parse_csv_file(
                    file_path, 
                    self.current_settings,
                    progress_callback=lambda p, m: self._handle_progress(p, m, idx, len(file_paths))
                )
                
                if result.success:
                    vehicle_data = result.value
                    
                    # Calculate speeds if not present
                    if self.current_settings.calculate_speeds:
                        speed_result = self.vehicle_service.calculate_speeds(vehicle_data)
                        if speed_result.success:
                            vehicle_data = speed_result.value
                    
                    # Apply interpolation if enabled
                    if self.current_settings.interpolation_enabled:
                        interp_result = self.vehicle_service.interpolate_path(
                            vehicle_data,
                            self.current_settings
                        )
                        if interp_result.success:
                            vehicle_data = interp_result.value
                    
                    # Assign color based on index
                    colors = list(VehicleColor)
                    vehicle_data.color = colors[idx % len(colors)]
                    
                    vehicles.append(vehicle_data)
                    
                    # Track as resource
                    if self._resource_coordinator:
                        self._resource_coordinator.track_resource(
                            f"vehicle_{vehicle_data.vehicle_id}",
                            vehicle_data,
                            cleanup_func=lambda: None  # Cleanup handled by service cache
                        )
                else:
                    errors.append(f"{file_path.name}: {result.error.user_message}")
            
            # Store loaded vehicles
            self.current_vehicles = vehicles
            
            # Handle results
            if vehicles and not errors:
                self._log_operation("load_csv_files", f"Successfully loaded {len(vehicles)} vehicles")
                return Result.success(vehicles)
            elif vehicles and errors:
                # Partial success
                result = Result.success(vehicles)
                for error in errors:
                    result.add_warning(error)
                return result
            else:
                # Complete failure
                error = FileOperationError(
                    f"Failed to load any CSV files: {'; '.join(errors)}",
                    user_message="No valid vehicle data could be loaded"
                )
                self._handle_error(error, {'method': 'load_csv_files', 'errors': errors})
                return Result.error(error)
                
        except Exception as e:
            error = FileOperationError(
                f"Unexpected error loading CSV files: {e}",
                user_message="An unexpected error occurred while loading vehicle data"
            )
            self._handle_error(error, {'method': 'load_csv_files', 'exception': str(e)})
            return Result.error(error)
    
    def prepare_animation(
        self,
        vehicles: Optional[List[VehicleData]] = None,
        settings: Optional[VehicleTrackingSettings] = None
    ) -> Result[AnimationData]:
        """
        Prepare animation data for map display
        
        Args:
            vehicles: Optional list of vehicles (uses current if not provided)
            settings: Optional settings (uses current if not provided)
            
        Returns:
            Result containing AnimationData or error
        """
        try:
            self._log_operation("prepare_animation", "Preparing animation data")
            
            # Use provided or current vehicles
            vehicles_to_animate = vehicles or self.current_vehicles
            animation_settings = settings or self.current_settings
            
            if not vehicles_to_animate:
                error = ValidationError(
                    {'vehicles': 'No vehicles to animate'},
                    user_message="Please load vehicle data before creating animation"
                )
                self._handle_error(error, {'method': 'prepare_animation'})
                return Result.error(error)
            
            # Prepare animation through service
            result = self.vehicle_service.prepare_animation_data(
                vehicles_to_animate,
                animation_settings
            )
            
            if result.success:
                self.current_animation = result.value
                self._log_operation("prepare_animation", 
                                  f"Animation ready: {result.value.total_duration_seconds:.1f}s")
                
                # Track animation as resource
                if self._resource_coordinator:
                    self._resource_coordinator.track_resource(
                        "animation_data",
                        self.current_animation,
                        cleanup_func=lambda: setattr(self, 'current_animation', None)
                    )
            
            return result
            
        except Exception as e:
            error = FileOperationError(
                f"Animation preparation failed: {e}",
                user_message="Failed to prepare animation data"
            )
            self._handle_error(error, {'method': 'prepare_animation', 'exception': str(e)})
            return Result.error(error)
    
    def start_vehicle_tracking_workflow(
        self,
        file_paths: List[Path],
        settings: Optional[VehicleTrackingSettings] = None,
        use_worker: bool = True
    ) -> Result:
        """
        Start complete vehicle tracking workflow
        
        This is the main entry point for processing vehicle data.
        Can run in main thread or spawn worker thread.
        
        Args:
            file_paths: List of CSV files to process
            settings: Processing settings
            use_worker: Whether to use worker thread
            
        Returns:
            Result containing worker thread or processed data
        """
        try:
            self._log_operation("start_workflow", f"Starting workflow for {len(file_paths)} files")
            
            # Check for existing operation
            if self.current_worker and self.current_worker.isRunning():
                error = FileOperationError(
                    "Another vehicle tracking operation is in progress",
                    user_message="Please wait for the current operation to complete"
                )
                self._handle_error(error, {'method': 'start_workflow'})
                return Result.error(error)
            
            # Store settings
            if settings:
                self.current_settings = settings
            
            if use_worker:
                # Import worker here to avoid circular dependency
                try:
                    from vehicle_tracking.workers.vehicle_tracking_worker import VehicleTrackingWorker
                    
                    # Create and configure worker
                    self.current_worker = VehicleTrackingWorker(
                        file_paths=file_paths,
                        settings=self.current_settings,
                        controller=self
                    )
                    
                    # Track worker as resource
                    if self._resource_coordinator:
                        self._resource_coordinator.track_worker(
                            "vehicle_tracking_worker",
                            self.current_worker
                        )
                    
                    # Start worker
                    self.current_worker.start()
                    
                    self._log_operation("start_workflow", "Worker thread started")
                    return Result.success(self.current_worker)
                    
                except ImportError:
                    # Worker not implemented yet, fall back to synchronous
                    self._log_operation("start_workflow", 
                                      "Worker not available, running synchronously")
                    use_worker = False
            
            if not use_worker:
                # Run synchronously in main thread
                load_result = self.load_csv_files(file_paths, settings)
                if not load_result.success:
                    return load_result
                
                animation_result = self.prepare_animation()
                if not animation_result.success:
                    return animation_result
                
                # Create tracking result
                tracking_result = VehicleTrackingResult(
                    vehicles_processed=len(self.current_vehicles),
                    total_points_processed=sum(v.point_count for v in self.current_vehicles),
                    vehicle_data=self.current_vehicles,
                    animation_data=self.current_animation
                )
                
                return Result.success(tracking_result)
                
        except Exception as e:
            error = FileOperationError(
                f"Workflow failed: {e}",
                user_message="Vehicle tracking workflow failed"
            )
            self._handle_error(error, {'method': 'start_workflow', 'exception': str(e)})
            return Result.error(error)
    
    def update_vehicle_settings(
        self,
        vehicle_id: str,
        color: Optional[VehicleColor] = None,
        label: Optional[str] = None,
        visible: Optional[bool] = None
    ) -> Result[VehicleData]:
        """
        Update settings for a specific vehicle
        
        Args:
            vehicle_id: Vehicle identifier
            color: Optional new color
            label: Optional new label
            visible: Optional visibility flag
            
        Returns:
            Result containing updated VehicleData
        """
        try:
            # Find vehicle
            vehicle = next((v for v in self.current_vehicles if v.vehicle_id == vehicle_id), None)
            
            if not vehicle:
                error = ValidationError(
                    {'vehicle_id': f'Vehicle not found: {vehicle_id}'},
                    user_message=f"Vehicle {vehicle_id} not found"
                )
                return Result.error(error)
            
            # Update settings
            if color is not None:
                vehicle.color = color
            if label is not None:
                vehicle.label = label
            # Note: visible flag would be used by the map display
            
            self._log_operation("update_vehicle", f"Updated {vehicle_id}")
            return Result.success(vehicle)
            
        except Exception as e:
            error = FileOperationError(
                f"Failed to update vehicle: {e}",
                user_message=f"Failed to update vehicle {vehicle_id}"
            )
            self._handle_error(error, {'method': 'update_vehicle', 'vehicle_id': vehicle_id})
            return Result.error(error)
    
    def cleanup_resources(self):
        """Clean up all resources and cancel operations"""
        try:
            self._log_operation("cleanup", "Starting resource cleanup")
            
            # Cancel worker if running
            if self.current_worker and self.current_worker.isRunning():
                self.current_worker.cancel()
                self.current_worker.wait(5000)  # Wait up to 5 seconds
                
            # Clean up through resource coordinator
            if self._resource_coordinator:
                self._resource_coordinator.cleanup_all()
                
            # Clear service cache
            if self._vehicle_service:
                self._vehicle_service.clear_cache()
            
            # Clear local state
            self.current_vehicles.clear()
            self.current_animation = None
            self.current_worker = None
            
            self._log_operation("cleanup", "Resource cleanup complete")
            
        except Exception as e:
            self._log_operation("cleanup", f"Cleanup error: {e}", "error")
    
    def _handle_progress(self, progress: float, message: str, current_file: int, total_files: int):
        """
        Handle progress updates from service operations
        
        Args:
            progress: Progress percentage for current file
            message: Progress message
            current_file: Current file index
            total_files: Total number of files
        """
        # Calculate overall progress
        file_weight = 100.0 / total_files
        overall_progress = (current_file * file_weight) + (progress * file_weight / 100)
        
        # Log progress
        self._log_operation("progress", f"[{overall_progress:.1f}%] {message}")