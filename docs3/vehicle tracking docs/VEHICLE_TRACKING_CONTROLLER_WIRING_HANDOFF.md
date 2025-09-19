# Vehicle Tracking Controller Wiring - Implementation Handoff Document

## Executive Summary

This document provides a complete handoff for wiring the Vehicle Tracking UI to its controller and backend services. The UI is **100% complete** and follows established patterns from the Media Analysis tab. The controller and services already exist and are functional. Only the connection layer remains.

## Current Implementation Status

### ✅ COMPLETED Components

1. **UI Layer** (`vehicle_tracking/ui/vehicle_tracking_tab.py`)
   - Main tab with 3-section layout (files panel, settings tabs, console)
   - Custom `VehicleFilesPanel` for CSV file management
   - `VehicleTrackingConsole` for text output
   - 5 analysis mode tabs (Animation, Co-Location, Idle, Time Jump, Route)
   - `VehicleMapWindow` wrapper for separate map visualization
   - All UI elements have proper widget references for data collection

2. **Controller** (`vehicle_tracking/controllers/vehicle_tracking_controller.py`)
   - Fully implemented with `start_vehicle_tracking_workflow()` method
   - Returns `Result` objects following app patterns
   - Resource management via `WorkerResourceCoordinator`
   - Service injection ready

3. **Worker Thread** (`vehicle_tracking/workers/vehicle_tracking_worker.py`)
   - Extends `BaseWorkerThread`
   - Emits standard signals: `result_ready`, `progress_update`
   - Processes CSV files asynchronously
   - Returns `VehicleTrackingResult`

4. **Services** (`vehicle_tracking/services/`)
   - `VehicleTrackingService` with CSV parsing, speed calculation, interpolation
   - `MapTemplateService` for map HTML generation
   - All registered in service registry

5. **Map Widget** (`vehicle_tracking/ui/components/vehicle_map_widget.py`)
   - Complete WebEngine-based map with Leaflet
   - JavaScript bridge for bidirectional communication
   - Animation support via TimeDimension plugin

### ❌ PENDING: Controller Wiring

The **ONLY** remaining work is connecting the UI to the controller. All business logic exists and works - it just needs to be wired together.

## Critical Architecture Patterns (FROM EXISTING APP)

### 1. Controller Workflow Pattern (Media Analysis Example)

```python
# From media_analysis_tab.py:735-784
def _start_analysis(self):
    # 1. Collect settings from UI
    settings = self._get_current_settings()

    # 2. Update UI state
    self._set_operation_active(True)

    # 3. Start workflow through controller
    result = self.controller.start_analysis_workflow(
        self.selected_paths,
        settings,
        self.form_data  # Optional
    )

    if result.success:
        self.current_worker = result.value

        # 4. Connect worker signals
        self.current_worker.result_ready.connect(self._on_analysis_complete)
        self.current_worker.progress_update.connect(self._on_progress_update)

        # 5. Start worker
        self.current_worker.start()
    else:
        # Handle startup failure
        self._set_operation_active(False)
        QMessageBox.warning(self, "Error", result.error.user_message)
```

### 2. Progress Handling Pattern

```python
# From media_analysis_tab.py:824-831
def _on_progress_update(self, percentage: int, message: str):
    self.progress_bar.setValue(percentage)
    self.progress_label.setText(message)

    # Log significant progress
    if percentage % 10 == 0 or percentage == 100:
        self.log_message.emit(message)  # Goes to main window's log
```

### 3. Completion Handling Pattern

```python
# From media_analysis_tab.py:833-872
def _on_tracking_complete(self, result):
    self._set_operation_active(False)

    if result.success:
        self.last_results = result.value
        self.export_btn.setEnabled(True)

        # Log completion
        self.log_message.emit(f"Analysis complete: {result.value.successful} processed")

        # Enable map viewing if applicable
        if result.value.animation_data:
            self.view_map_btn.setEnabled(True)

        # Show success dialog (future implementation)
        # ...
    else:
        # Handle failure
        self.log_message.emit(f"Analysis failed: {result.error.user_message}")
        QMessageBox.warning(self, "Failed", result.error.user_message)
```

### 4. UI State Management Pattern

```python
def _set_operation_active(self, active: bool):
    """Toggle UI state during operations"""
    self.operation_active = active

    # Disable input controls
    self.add_files_btn.setEnabled(not active)
    self.add_folder_btn.setEnabled(not active)
    self.clear_btn.setEnabled(not active)

    # Toggle action buttons
    self.track_btn.setEnabled(not active and len(self.selected_files) > 0)
    self.cancel_btn.setEnabled(active)

    # Show/hide progress
    self.progress_bar.setVisible(active)
    self.progress_label.setVisible(active)

    if not active:
        self.progress_bar.setValue(0)
        self.progress_label.setText("")
```

## Detailed Wiring Implementation Guide

### Step 1: Import Required Components

```python
# Add to vehicle_tracking_tab.py imports
from vehicle_tracking.controllers.vehicle_tracking_controller import VehicleTrackingController
from vehicle_tracking.models.vehicle_tracking_models import (
    VehicleTrackingSettings, VehicleTrackingResult, VehicleColor,
    PlaybackSpeed, InterpolationMethod, AnalysisType
)
from PySide6.QtWidgets import QMessageBox
```

### Step 2: Implement Settings Collection

```python
def _collect_settings_from_ui(self) -> VehicleTrackingSettings:
    """Collect all settings from UI widgets"""
    settings = VehicleTrackingSettings()

    # Get active tab index to determine mode
    tab_index = self.analysis_tabs.currentIndex()

    if tab_index == 0:  # Animation tab
        settings.animation_enabled = self.animate_movement_check.isChecked()
        settings.show_trails = self.show_trails_check.isChecked()
        settings.show_timestamps = self.show_timestamps_check.isChecked()
        settings.cluster_markers = self.cluster_markers_check.isChecked()
        settings.auto_center = self.auto_center_check.isChecked()

        # Playback speed mapping
        speed_map = {"0.5x": 0.5, "1x": 1.0, "2x": 2.0, "5x": 5.0, "10x": 10.0}
        settings.playback_speed = speed_map.get(self.speed_combo.currentText(), 1.0)

        # Trail length (convert text to seconds)
        trail_text = self.trail_combo.currentText()
        if "5 seconds" in trail_text:
            settings.trail_length_seconds = 5.0
        elif "10 seconds" in trail_text:
            settings.trail_length_seconds = 10.0
        elif "30 seconds" in trail_text:
            settings.trail_length_seconds = 30.0
        elif "1 minute" in trail_text:
            settings.trail_length_seconds = 60.0
        else:  # Full
            settings.trail_length_seconds = -1.0

        # Interpolation settings
        settings.interpolation_enabled = True
        settings.interpolation_method = self.interpolation_combo.currentText().lower()

        # Parse interval
        interval_text = self.interval_combo.currentText()
        settings.interpolation_interval = float(interval_text.split()[0])

    elif tab_index == 1:  # Co-Location tab
        settings.analysis_type = AnalysisType.COLOCATION

        # Parse radius
        radius_text = self.coloc_radius_combo.currentText()
        settings.colocation_radius_meters = float(radius_text.split()[0])

        # Parse time window
        window_text = self.coloc_window_combo.currentText()
        if "minute" in window_text:
            minutes = float(window_text.split()[0])
            settings.colocation_time_window = minutes * 60

        # Parse min duration
        duration_text = self.coloc_duration_combo.currentText()
        if "second" in duration_text:
            settings.colocation_min_duration = float(duration_text.split()[0])
        elif "minute" in duration_text:
            minutes = float(duration_text.split()[0])
            settings.colocation_min_duration = minutes * 60

    elif tab_index == 2:  # Idle Detection tab
        settings.analysis_type = AnalysisType.IDLE
        settings.idle_speed_threshold_kmh = self.idle_speed_spin.value()

        # Parse duration
        duration_text = self.idle_duration_combo.currentText()
        if "second" in duration_text:
            settings.idle_min_duration = float(duration_text.split()[0])
        elif "minute" in duration_text:
            minutes = float(duration_text.split()[0])
            settings.idle_min_duration = minutes * 60

        settings.include_traffic_stops = self.include_stops_check.isChecked()
        settings.merge_nearby_idle = self.merge_nearby_check.isChecked()

    elif tab_index == 3:  # Time Jump tab
        settings.analysis_type = AnalysisType.TIMEJUMP

        # Parse gap threshold
        gap_text = self.gap_threshold_combo.currentText()
        if "minute" in gap_text:
            minutes = float(gap_text.split()[0])
            settings.timejump_gap_threshold = minutes * 60
        elif "hour" in gap_text:
            hours = float(gap_text.split()[0])
            settings.timejump_gap_threshold = hours * 3600

        settings.max_reasonable_speed_kmh = self.max_speed_spin.value()
        settings.flag_impossible_speeds = self.flag_impossible_check.isChecked()

    return settings
```

### Step 3: Implement Start Tracking Method

```python
def _start_tracking(self):
    """Start vehicle tracking with selected analysis"""
    if not self.selected_files:
        return

    # Collect settings
    settings = self._collect_settings_from_ui()

    # Update UI state
    self._set_operation_active(True)

    # Log to console
    self.output_console.append_message(
        f"Starting vehicle tracking with {len(self.selected_files)} files...",
        "info"
    )

    # Start workflow through controller
    result = self.controller.start_vehicle_tracking_workflow(
        self.selected_files,
        settings,
        use_worker=True  # Always use worker thread
    )

    if result.success:
        self.current_worker = result.value

        # Connect worker signals
        self.current_worker.result_ready.connect(self._on_tracking_complete)
        self.current_worker.progress_update.connect(self._on_progress_update)

        # Start worker
        self.current_worker.start()

        # Log
        self.log_message.emit(f"Vehicle tracking started for {len(self.selected_files)} files")
    else:
        # Failed to start
        self._set_operation_active(False)
        self.output_console.append_message(
            f"Error: {result.error.user_message}",
            "error"
        )

        QMessageBox.warning(
            self,
            "Tracking Error",
            result.error.user_message
        )
```

### Step 4: Implement Progress Handler

```python
def _on_progress_update(self, percentage: int, message: str):
    """Handle progress updates from worker"""
    self.progress_bar.setValue(percentage)
    self.progress_label.setText(message)

    # Update console with progress
    if percentage % 20 == 0 or percentage == 100:
        self.output_console.append_message(message, "progress")
```

### Step 5: Implement Completion Handler

```python
def _on_tracking_complete(self, result):
    """Handle tracking completion"""
    self._set_operation_active(False)

    if result.success:
        self.last_results = result.value

        # Enable relevant buttons
        self.view_map_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

        # Log completion to console
        vehicles_text = "vehicle" if self.last_results.total_vehicles == 1 else "vehicles"
        self.output_console.append_message(
            f"✓ Successfully tracked {self.last_results.successful_vehicles} {vehicles_text}",
            "success"
        )

        # Log GPS points
        if self.last_results.total_gps_points > 0:
            self.output_console.append_message(
                f"✓ Processed {self.last_results.total_gps_points:,} GPS points",
                "success"
            )

        # Log analysis results based on mode
        if self.current_mode == TrackingMode.COLOCATION:
            self.output_console.append_message(
                f"✓ Found {self.last_results.colocation_events} co-location events",
                "success"
            )
        elif self.current_mode == TrackingMode.IDLE:
            self.output_console.append_message(
                f"✓ Detected {self.last_results.idle_periods} idle periods",
                "success"
            )
        elif self.current_mode == TrackingMode.TIMEJUMP:
            self.output_console.append_message(
                f"✓ Identified {self.last_results.time_jumps} time jumps",
                "success"
            )

        # Emit to main window log
        self.log_message.emit(
            f"Vehicle tracking complete: {self.last_results.successful_vehicles} vehicles processed"
        )

        # Success dialog will be implemented separately

    else:
        # Analysis failed
        self.output_console.append_message(
            f"Tracking failed: {result.error.user_message}",
            "error"
        )

        self.log_message.emit(f"Vehicle tracking failed: {result.error.user_message}")

        QMessageBox.warning(
            self,
            "Tracking Failed",
            result.error.user_message
        )

    # Cleanup worker reference
    self.current_worker = None
```

### Step 6: Implement Map Window Opening

```python
def _open_map_window(self):
    """Open the map visualization window"""
    if not self.last_results or not self.last_results.animation_data:
        QMessageBox.information(
            self,
            "No Data",
            "Please run vehicle tracking first to generate map data."
        )
        return

    # Create and show map window
    self.map_window = VehicleMapWindow(self.last_results)
    self.map_window.show()

    # Log
    self.output_console.append_message("Map window opened", "info")
```

### Step 7: Implement Cancel Operation

```python
def _cancel_operation(self):
    """Cancel current tracking operation"""
    if self.current_worker and self.current_worker.isRunning():
        self.current_worker.cancel()
        self.output_console.append_message("Cancelling operation...", "warning")

        # Worker will emit result_ready with partial results or error
```

### Step 8: Implement Export (Stub for now)

```python
def _export_results(self):
    """Export analysis results"""
    if not self.last_results:
        return

    # Get export format from dialog
    formats = ["GeoJSON (*.geojson)", "KML (*.kml)", "CSV (*.csv)"]
    file_dialog = QFileDialog.getSaveFileName(
        self,
        "Export Results",
        "",
        ";;".join(formats)
    )

    if file_dialog[0]:
        # TODO: Implement actual export via controller
        self.output_console.append_message(
            f"Export functionality coming soon: {file_dialog[0]}",
            "info"
        )
```

## Critical Implementation Notes

### 1. Signal Connections
- The UI emits `log_message` and `status_message` signals that should be connected by MainWindow
- These signals allow the tab to communicate with the main application log

### 2. Form Data
- The `form_data` parameter is optional but can be passed for report generation
- It contains occurrence number and other case details

### 3. Resource Management
- The controller handles resource cleanup via `WorkerResourceCoordinator`
- Worker threads are automatically tracked and cleaned up

### 4. Error Handling
- All operations return `Result` objects
- Check `result.success` before accessing `result.value`
- Use `result.error.user_message` for user-friendly error messages

### 5. Thread Safety
- All UI updates from worker threads go through Qt signals
- Never directly update UI from worker thread

## Testing the Integration

1. **Basic Flow Test**:
   - Add CSV files
   - Click "Track Vehicles"
   - Verify progress updates in console
   - Verify "View Map" enables on completion
   - Click "View Map" to open visualization

2. **Error Handling Test**:
   - Try loading invalid CSV file
   - Verify error message appears
   - Verify UI returns to ready state

3. **Cancellation Test**:
   - Start tracking large files
   - Click Cancel during processing
   - Verify operation stops cleanly

## File Structure Reference

```
vehicle_tracking/
├── ui/
│   ├── vehicle_tracking_tab.py          # MODIFY THIS - Add wiring
│   └── components/
│       └── vehicle_map_widget.py        # Complete - DO NOT MODIFY
├── controllers/
│   └── vehicle_tracking_controller.py   # Complete - DO NOT MODIFY
├── workers/
│   └── vehicle_tracking_worker.py       # Complete - DO NOT MODIFY
├── services/
│   └── vehicle_tracking_service.py      # Complete - DO NOT MODIFY
└── models/
    └── vehicle_tracking_models.py       # Complete - DO NOT MODIFY
```

## Common Pitfalls to Avoid

1. **Don't forget to set operation_active** - This prevents concurrent operations
2. **Always check Result.success** - Never assume operations succeeded
3. **Connect signals before starting worker** - Otherwise you miss events
4. **Clean up worker reference** - Set to None after completion
5. **Use proper parent for dialogs** - Pass `self` as parent to QMessageBox

## Summary for Next AI

You're implementing the "glue code" between a complete UI and a complete backend. Everything exists and works - it just needs to be connected. Follow the Media Analysis tab patterns exactly - they're proven to work. The controller returns a worker, connect its signals, start it, and handle the results. That's it.

The success message system will be implemented separately, so just put a comment placeholder where it would go. Focus on getting data flowing from UI → Controller → Worker → Results → UI.

Good luck!