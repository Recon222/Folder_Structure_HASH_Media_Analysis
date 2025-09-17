#!/usr/bin/env python3
"""
Vehicle Tracking Worker - Thread for async GPS processing

Processes vehicle GPS data in background thread with progress reporting.
Follows FSA worker patterns with Result-based error handling.
"""

from pathlib import Path
from typing import List, Optional, Any
from datetime import datetime

from core.workers.base_worker import BaseWorkerThread
from core.result_types import Result
from core.exceptions import ValidationError, FileOperationError, ErrorSeverity

# Import models
from vehicle_tracking.models.vehicle_tracking_models import (
    VehicleData, VehicleTrackingSettings, AnimationData,
    VehicleTrackingResult, VehicleColor
)


class VehicleTrackingWorker(BaseWorkerThread):
    """
    Worker thread for vehicle tracking operations
    
    Processes CSV files, calculates speeds, interpolates paths,
    and prepares animation data without blocking the UI.
    """
    
    def __init__(
        self,
        file_paths: List[Path],
        settings: VehicleTrackingSettings,
        controller: Any = None,  # VehicleTrackingController
        parent=None
    ):
        """
        Initialize vehicle tracking worker
        
        Args:
            file_paths: List of CSV files to process
            settings: Processing settings
            controller: Optional controller reference for service access
            parent: Parent QObject for Qt lifecycle
        """
        super().__init__(parent)
        
        self.file_paths = file_paths
        self.settings = settings
        self.controller = controller
        
        # Results storage
        self.vehicles: List[VehicleData] = []
        self.animation_data: Optional[AnimationData] = None
        self.skipped_files: List[tuple] = []
        
        # Set descriptive operation name
        file_count = len(file_paths) if file_paths else 0
        self.set_operation_name(f"Vehicle Tracking ({file_count} files)")
    
    def execute(self) -> Result[VehicleTrackingResult]:
        """
        Execute vehicle tracking workflow in thread
        
        Returns:
            Result containing VehicleTrackingResult or error
        """
        try:
            start_time = datetime.now()
            
            # Validate inputs
            validation_result = self._validate_inputs()
            if not validation_result.success:
                return validation_result
            
            # Check for cancellation
            self.check_cancellation()
            
            # Get service from controller or fail
            if not self.controller or not hasattr(self.controller, 'vehicle_service'):
                error = ValidationError(
                    {'controller': 'Controller or service not available'},
                    user_message="System error: Vehicle service not available"
                )
                self.handle_error(error)
                return Result.error(error)
            
            vehicle_service = self.controller.vehicle_service
            
            # Process each CSV file
            total_points = 0
            self.emit_progress(0, f"Processing {len(self.file_paths)} vehicle files...")
            
            for idx, file_path in enumerate(self.file_paths):
                # Check cancellation between files
                if self.is_cancelled():
                    self.emit_progress(100, "Operation cancelled")
                    return self._create_partial_result(start_time, total_points)
                
                # Update progress
                file_progress = (idx / len(self.file_paths)) * 70  # Reserve 30% for animation prep
                self.emit_progress(
                    int(file_progress),
                    f"Loading {file_path.name} ({idx + 1}/{len(self.file_paths)})"
                )
                
                # Parse CSV
                parse_result = vehicle_service.parse_csv_file(
                    file_path,
                    self.settings,
                    progress_callback=lambda p, m: self._handle_file_progress(p, m, idx)
                )
                
                if not parse_result.success:
                    self.skipped_files.append((file_path, parse_result.error.user_message))
                    continue
                
                vehicle_data = parse_result.value
                
                # Calculate speeds if enabled
                if self.settings.calculate_speeds:
                    self.emit_progress(
                        int(file_progress + 10),
                        f"Calculating speeds for {vehicle_data.vehicle_id}"
                    )
                    
                    speed_result = vehicle_service.calculate_speeds(
                        vehicle_data,
                        progress_callback=lambda p, m: self._handle_file_progress(p, m, idx, 10)
                    )
                    
                    if speed_result.success:
                        vehicle_data = speed_result.value
                
                # Interpolate if enabled
                if self.settings.interpolation_enabled:
                    self.emit_progress(
                        int(file_progress + 20),
                        f"Interpolating path for {vehicle_data.vehicle_id}"
                    )
                    
                    interp_result = vehicle_service.interpolate_path(
                        vehicle_data,
                        self.settings,
                        progress_callback=lambda p, m: self._handle_file_progress(p, m, idx, 20)
                    )
                    
                    if interp_result.success:
                        vehicle_data = interp_result.value
                
                # Assign color based on index
                colors = list(VehicleColor)
                vehicle_data.color = colors[idx % len(colors)]
                
                # Add label if not present
                if not vehicle_data.label:
                    vehicle_data.label = f"Vehicle {idx + 1}"
                
                # Add to results
                self.vehicles.append(vehicle_data)
                total_points += vehicle_data.point_count
                
                self.emit_progress(
                    int((idx + 1) / len(self.file_paths) * 70),
                    f"Completed {vehicle_data.vehicle_id}: {vehicle_data.point_count:,} points"
                )
            
            # Check if we have any vehicles
            if not self.vehicles:
                if self.skipped_files:
                    errors = [f"{f.name}: {reason}" for f, reason in self.skipped_files]
                    error = FileOperationError(
                        f"No valid vehicle data found: {'; '.join(errors[:3])}",
                        user_message="No valid GPS data could be extracted from the selected files"
                    )
                else:
                    error = FileOperationError(
                        "No vehicles processed",
                        user_message="No vehicle data was processed"
                    )
                self.handle_error(error)
                return Result.error(error)
            
            # Check cancellation before animation
            self.check_cancellation()
            
            # Prepare animation data
            self.emit_progress(75, "Preparing animation data...")
            
            animation_result = vehicle_service.prepare_animation_data(
                self.vehicles,
                self.settings
            )
            
            if animation_result.success:
                self.animation_data = animation_result.value
                self.emit_progress(90, "Animation data ready")
            else:
                # Non-fatal - we still have vehicle data
                self.animation_data = None
            
            # Create final result
            processing_time = (datetime.now() - start_time).total_seconds()
            
            tracking_result = VehicleTrackingResult(
                vehicles_processed=len(self.vehicles),
                total_points_processed=total_points,
                processing_time_seconds=processing_time,
                vehicle_data=self.vehicles,
                animation_data=self.animation_data,
                skipped_files=self.skipped_files,
                average_points_per_second=total_points / processing_time if processing_time > 0 else 0
            )
            
            # Add warnings for skipped files
            result = Result.success(tracking_result)
            for file_path, reason in self.skipped_files:
                result.add_warning(f"Skipped {file_path.name}: {reason}")
            
            # Final progress
            self.emit_progress(100, tracking_result.get_summary())
            
            return result
            
        except Exception as e:
            # Handle unexpected errors
            error = FileOperationError(
                f"Vehicle tracking failed: {str(e)}",
                user_message="An error occurred during vehicle tracking"
            )
            self.handle_error(error, {
                'stage': 'vehicle_tracking',
                'files_count': len(self.file_paths),
                'exception': str(e)
            })
            return Result.error(error)
    
    def _validate_inputs(self) -> Result:
        """
        Validate worker inputs
        
        Returns:
            Result indicating validation success or failure
        """
        if not self.file_paths:
            error = ValidationError(
                {'files': 'No files provided'},
                user_message="No CSV files selected for processing"
            )
            self.handle_error(error)
            return Result.error(error)
        
        # Check all files exist
        missing_files = [f for f in self.file_paths if not f.exists()]
        if missing_files:
            error = ValidationError(
                {'files': f"Files not found: {[f.name for f in missing_files]}"},
                user_message=f"Some files could not be found: {', '.join(f.name for f in missing_files[:3])}"
            )
            self.handle_error(error)
            return Result.error(error)
        
        # Check all are CSV
        non_csv = [f for f in self.file_paths if f.suffix.lower() != '.csv']
        if non_csv:
            error = ValidationError(
                {'files': f"Non-CSV files: {[f.name for f in non_csv]}"},
                user_message=f"Only CSV files are supported: {', '.join(f.name for f in non_csv[:3])}"
            )
            self.handle_error(error)
            return Result.error(error)
        
        return Result.success(None)
    
    def _handle_file_progress(
        self, 
        progress: float, 
        message: str, 
        file_index: int, 
        stage_offset: int = 0
    ):
        """
        Handle progress updates from service operations
        
        Args:
            progress: Progress percentage for current operation
            message: Progress message
            file_index: Index of current file
            stage_offset: Additional offset within file processing
        """
        # Calculate weighted progress
        file_weight = 70.0 / len(self.file_paths)  # 70% for file processing
        base_progress = file_index * file_weight
        stage_progress = (progress / 100) * (file_weight / 3)  # Divide file weight by stages
        
        overall_progress = base_progress + stage_offset + stage_progress
        
        # Don't emit micro-updates
        if int(overall_progress) % 5 == 0:
            self.emit_progress(int(overall_progress), message)
    
    def _create_partial_result(
        self, 
        start_time: datetime, 
        total_points: int
    ) -> Result[VehicleTrackingResult]:
        """
        Create result for partial/cancelled operation
        
        Args:
            start_time: Operation start time
            total_points: Total points processed
            
        Returns:
            Result with partial data
        """
        processing_time = (datetime.now() - start_time).total_seconds()
        
        tracking_result = VehicleTrackingResult(
            vehicles_processed=len(self.vehicles),
            total_points_processed=total_points,
            processing_time_seconds=processing_time,
            vehicle_data=self.vehicles,
            animation_data=self.animation_data,
            skipped_files=self.skipped_files,
            warnings=["Operation cancelled by user"]
        )
        
        result = Result.success(tracking_result)
        result.add_warning("Operation was cancelled - results may be incomplete")
        
        return result
    
    def cancel(self):
        """Request cancellation of the operation"""
        super().cancel()
        self.emit_progress(100, "Cancelling vehicle tracking...")
    
    def cleanup(self):
        """Clean up worker resources"""
        # Clear large data structures
        self.vehicles.clear()
        self.animation_data = None
        self.skipped_files.clear()
        
        # Let controller handle service cleanup
        if self.controller and hasattr(self.controller, 'cleanup_resources'):
            self.controller.cleanup_resources()