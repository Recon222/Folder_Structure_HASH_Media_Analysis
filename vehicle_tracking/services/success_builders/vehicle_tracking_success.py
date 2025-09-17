#!/usr/bin/env python3
"""
Vehicle Tracking Success Builder

Creates rich success messages for vehicle tracking operations.
Follows FSA success builder patterns.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from core.services.base_service import BaseService
from core.services.interfaces import IService
from core.services.success_message_data import SuccessMessageData

# Import vehicle tracking models
from vehicle_tracking.models.vehicle_tracking_models import (
    VehicleTrackingResult, VehicleAnalysisResult, AnalysisType
)


class IVehicleTrackingSuccessService(IService):
    """Interface for vehicle tracking success builder (defined in interfaces.py)"""
    pass


class VehicleTrackingSuccessBuilder(BaseService, IVehicleTrackingSuccessService):
    """
    Success message builder for vehicle tracking operations
    
    Creates detailed, celebratory success messages for tracking and analysis operations.
    """
    
    def __init__(self):
        """Initialize vehicle tracking success builder"""
        super().__init__("VehicleTrackingSuccessBuilder")
    
    def build_tracking_success(
        self,
        vehicles_processed: int,
        total_points: int,
        processing_time: float,
        has_animation: bool = False,
        skipped_files: int = 0
    ) -> SuccessMessageData:
        """
        Build success message for vehicle tracking operation
        
        Args:
            vehicles_processed: Number of vehicles successfully processed
            total_points: Total GPS points processed
            processing_time: Processing duration in seconds
            has_animation: Whether animation data was created
            skipped_files: Number of files that were skipped
            
        Returns:
            SuccessMessageData for display
        """
        try:
            # Choose emoji and title based on scale
            if vehicles_processed >= 10:
                emoji = "🚗🚙🚕"
                title = "Fleet Tracking Complete!"
            elif vehicles_processed >= 5:
                emoji = "🚗🚗"
                title = "Multi-Vehicle Tracking Complete!"
            elif vehicles_processed > 1:
                emoji = "🚗"
                title = "Vehicle Tracking Complete!"
            else:
                emoji = "📍"
                title = "GPS Track Processed!"
            
            # Build summary lines
            summary_lines = []
            
            # Main success line
            if vehicles_processed == 1:
                summary_lines.append(f"{emoji} Successfully processed 1 vehicle track")
            else:
                summary_lines.append(f"{emoji} Successfully processed {vehicles_processed} vehicle tracks")
            
            # Points processed
            if total_points >= 1000000:
                summary_lines.append(f"📊 {total_points:,} GPS points ({total_points/1000000:.1f}M points)")
            elif total_points >= 1000:
                summary_lines.append(f"📊 {total_points:,} GPS points ({total_points/1000:.1f}K points)")
            else:
                summary_lines.append(f"📊 {total_points:,} GPS points")
            
            # Processing time
            if processing_time < 1:
                summary_lines.append(f"⚡ Processed in {processing_time*1000:.0f} milliseconds")
            elif processing_time < 60:
                summary_lines.append(f"⏱️ Processed in {processing_time:.1f} seconds")
            else:
                minutes = int(processing_time / 60)
                seconds = int(processing_time % 60)
                summary_lines.append(f"⏱️ Processed in {minutes}m {seconds}s")
            
            # Processing speed
            if processing_time > 0:
                points_per_sec = total_points / processing_time
                if points_per_sec > 10000:
                    summary_lines.append(f"🚀 {points_per_sec/1000:.1f}K points/second")
                else:
                    summary_lines.append(f"📈 {points_per_sec:.0f} points/second")
            
            # Animation status
            if has_animation:
                summary_lines.append("🗺️ Animation data ready for playback")
            
            # Warnings for skipped files
            if skipped_files > 0:
                summary_lines.append(f"⚠️ {skipped_files} file(s) skipped due to errors")
            
            # Add details section
            details_lines = []
            
            # Per-vehicle statistics
            if vehicles_processed > 0 and total_points > 0:
                avg_points = total_points / vehicles_processed
                details_lines.append(f"Average points per vehicle: {avg_points:.0f}")
            
            # Data density
            if processing_time > 0 and vehicles_processed > 0:
                # Estimate based on typical GPS data
                estimated_duration_hours = (total_points / vehicles_processed) / 60  # Assume 1 point/minute
                if estimated_duration_hours >= 24:
                    days = int(estimated_duration_hours / 24)
                    details_lines.append(f"Estimated tracking duration: {days} days")
                elif estimated_duration_hours >= 1:
                    details_lines.append(f"Estimated tracking duration: {estimated_duration_hours:.1f} hours")
            
            # Create performance data
            performance_data = {
                'vehicles_processed': vehicles_processed,
                'total_points': total_points,
                'processing_time_seconds': processing_time,
                'points_per_second': total_points / processing_time if processing_time > 0 else 0,
                'has_animation': has_animation
            }
            
            # Create SuccessMessageData
            success_message = SuccessMessageData(
                title=title,
                emoji=emoji,
                summary_lines=summary_lines,
                details_lines=details_lines,
                performance_data=performance_data,
                timestamp=datetime.now()
            )
            
            self._log_operation("build_tracking_success", 
                              f"Created success message for {vehicles_processed} vehicles")
            
            return success_message
            
        except Exception as e:
            # Fallback message
            self._log_operation("build_tracking_success", f"Error building message: {e}", "error")
            
            return SuccessMessageData(
                title="Vehicle Tracking Complete",
                emoji="✅",
                summary_lines=[
                    f"Processed {vehicles_processed} vehicles",
                    f"Total: {total_points:,} GPS points"
                ],
                timestamp=datetime.now()
            )
    
    def build_analysis_success(
        self,
        analysis_type: AnalysisType,
        events_found: int,
        vehicles_analyzed: int,
        processing_time: float
    ) -> SuccessMessageData:
        """
        Build success message for analysis operations
        
        Args:
            analysis_type: Type of analysis performed
            events_found: Number of events/findings discovered
            vehicles_analyzed: Number of vehicles analyzed
            processing_time: Analysis duration in seconds
            
        Returns:
            SuccessMessageData for display
        """
        try:
            # Choose title and emoji based on analysis type
            if analysis_type == AnalysisType.CO_LOCATION:
                emoji = "🎯"
                title = "Co-Location Analysis Complete!"
                event_name = "co-location event"
            elif analysis_type == AnalysisType.TIMESTAMP_JUMP:
                emoji = "⏰"
                title = "Timestamp Analysis Complete!"
                event_name = "timestamp gap"
            elif analysis_type == AnalysisType.IDLING:
                emoji = "⏸️"
                title = "Idling Analysis Complete!"
                event_name = "idling period"
            elif analysis_type == AnalysisType.ROUTE_SIMILARITY:
                emoji = "🔄"
                title = "Route Similarity Analysis Complete!"
                event_name = "similar route"
            elif analysis_type == AnalysisType.SPEED_ANALYSIS:
                emoji = "🏁"
                title = "Speed Analysis Complete!"
                event_name = "speed event"
            else:
                emoji = "🔍"
                title = "Analysis Complete!"
                event_name = "event"
            
            # Build summary lines
            summary_lines = []
            
            # Main result line
            if events_found == 0:
                summary_lines.append(f"{emoji} No {event_name}s detected")
            elif events_found == 1:
                summary_lines.append(f"{emoji} Found 1 {event_name}")
            else:
                summary_lines.append(f"{emoji} Found {events_found} {event_name}s")
            
            # Vehicles analyzed
            if vehicles_analyzed == 1:
                summary_lines.append(f"🚗 Analyzed 1 vehicle")
            else:
                summary_lines.append(f"🚗 Analyzed {vehicles_analyzed} vehicles")
            
            # Processing time
            if processing_time < 1:
                summary_lines.append(f"⚡ Completed in {processing_time*1000:.0f}ms")
            elif processing_time < 60:
                summary_lines.append(f"⏱️ Completed in {processing_time:.1f} seconds")
            else:
                minutes = int(processing_time / 60)
                seconds = int(processing_time % 60)
                summary_lines.append(f"⏱️ Completed in {minutes}m {seconds}s")
            
            # Add context based on findings
            details_lines = []
            
            if events_found > 0:
                if analysis_type == AnalysisType.CO_LOCATION:
                    details_lines.append("Vehicles were at the same location within the specified radius")
                    details_lines.append("Check the analysis panel for detailed timestamps and locations")
                elif analysis_type == AnalysisType.TIMESTAMP_JUMP:
                    details_lines.append("GPS data contains temporal discontinuities")
                    details_lines.append("This may indicate device power cycles or data gaps")
                elif analysis_type == AnalysisType.IDLING:
                    details_lines.append("Detected periods of minimal movement")
                    details_lines.append("Review locations and durations in the analysis panel")
                elif analysis_type == AnalysisType.ROUTE_SIMILARITY:
                    details_lines.append("Multiple vehicles followed similar paths")
                    details_lines.append("This may indicate convoy or following behavior")
            else:
                details_lines.append(f"No {event_name}s found matching the analysis criteria")
                details_lines.append("Try adjusting the analysis parameters")
            
            # Create performance data
            performance_data = {
                'analysis_type': analysis_type.value,
                'events_found': events_found,
                'vehicles_analyzed': vehicles_analyzed,
                'processing_time_seconds': processing_time
            }
            
            # Create SuccessMessageData
            success_message = SuccessMessageData(
                title=title,
                emoji=emoji,
                summary_lines=summary_lines,
                details_lines=details_lines,
                performance_data=performance_data,
                timestamp=datetime.now()
            )
            
            self._log_operation("build_analysis_success", 
                              f"Created success message for {analysis_type.value} analysis")
            
            return success_message
            
        except Exception as e:
            # Fallback message
            self._log_operation("build_analysis_success", f"Error building message: {e}", "error")
            
            return SuccessMessageData(
                title="Analysis Complete",
                emoji="✅",
                summary_lines=[
                    f"Analysis completed",
                    f"Found {events_found} events",
                    f"Analyzed {vehicles_analyzed} vehicles"
                ],
                timestamp=datetime.now()
            )
    
    def build_from_result(
        self,
        result: VehicleTrackingResult
    ) -> SuccessMessageData:
        """
        Build success message from tracking result object
        
        Args:
            result: VehicleTrackingResult from worker
            
        Returns:
            SuccessMessageData for display
        """
        has_animation = result.animation_data is not None
        skipped_files = len(result.skipped_files) if result.skipped_files else 0
        
        success_message = self.build_tracking_success(
            vehicles_processed=result.vehicles_processed,
            total_points=result.total_points_processed,
            processing_time=result.processing_time_seconds,
            has_animation=has_animation,
            skipped_files=skipped_files
        )
        
        # Add any warnings from result
        if result.warnings:
            for warning in result.warnings:
                success_message.details_lines.append(f"⚠️ {warning}")
        
        # Add memory usage if significant
        if result.memory_usage_mb > 100:
            success_message.details_lines.append(
                f"Memory used: {result.memory_usage_mb:.1f} MB"
            )
        
        return success_message
    
    def build_export_success(
        self,
        export_format: str,
        file_path: str,
        vehicles_exported: int
    ) -> SuccessMessageData:
        """
        Build success message for export operations
        
        Args:
            export_format: Format exported to (KML, GeoJSON, CSV)
            file_path: Path where file was saved
            vehicles_exported: Number of vehicles exported
            
        Returns:
            SuccessMessageData for display
        """
        emoji = "💾"
        title = f"{export_format} Export Complete!"
        
        summary_lines = [
            f"{emoji} Successfully exported to {export_format}",
            f"📁 Saved to: {file_path}",
            f"🚗 Exported {vehicles_exported} vehicle track(s)"
        ]
        
        details_lines = []
        
        if export_format == "KML":
            details_lines.append("File can be opened in Google Earth")
        elif export_format == "GeoJSON":
            details_lines.append("File can be used in GIS applications")
        elif export_format == "CSV":
            details_lines.append("File can be opened in Excel or other spreadsheet software")
        
        return SuccessMessageData(
            title=title,
            emoji=emoji,
            summary_lines=summary_lines,
            details_lines=details_lines,
            timestamp=datetime.now()
        )