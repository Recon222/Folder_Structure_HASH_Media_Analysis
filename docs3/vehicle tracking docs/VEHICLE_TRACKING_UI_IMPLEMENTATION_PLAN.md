# Vehicle Tracking UI Implementation Plan

## Executive Summary

Based on the Media Analysis Tab's successful design pattern, we will create a Vehicle Tracking Tab with multiple analysis modes accessed through tabs. The implementation will be completely independent (no shared widgets) but follow the same visual design and interaction patterns.

## UI Architecture Overview

### Layout Structure (Following Media Analysis Pattern)
```
┌─────────────────────────────────────────────────────────────┐
│ Vehicle Tracking Operations                         [Status] │
├─────────────────────────────────────┴───────────────────────┤
│ ┌─────────────────────┐ ┌─────────────────────────────────┐│
│ │ CSV Files to Track  │ │ Tracking Settings               ││
│ │ ┌─────────────────┐ │ │ ┌───────────────────────────┐   ││
│ │ │ [Add Files]      │ │ │ │🚗 Animation  │🔍 Analysis │   ││
│ │ │ [Add Folder]     │ │ │ ├───────────────────────────┤   ││
│ │ │ [Clear]          │ │ │ │ □ Show Vehicle Trails     │   ││
│ │ ├─────────────────┤ │ │ │ □ Animate Movement        │   ││
│ │ │                 │ │ │ │ □ Cluster Markers         │   ││
│ │ │ File List       │ │ │ │ Speed: [Normal ▼]        │   ││
│ │ │                 │ │ │ │ Interpolation: [Linear ▼] │   ││
│ │ │                 │ │ │ └───────────────────────────┘   ││
│ │ └─────────────────┘ │ │                                 ││
│ │ [2 vehicles ready]  │ │ [Track Vehicles] [Export] [Stop]││
│ └─────────────────────┘ └─────────────────────────────────┘│
├───────────────────────────────────────────────────────────┤
│ Map Display / Analysis Output                               │
│ ┌───────────────────────────────────────────────────────┐ │
│ │                                                         │ │
│ │                    [Interactive Map]                    │ │
│ │                                                         │ │
│ └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Component Hierarchy

### 1. Main Tab Class: `VehicleTrackingTab`
```python
class VehicleTrackingTab(QWidget):
    """Main tab for vehicle tracking and analysis"""

    # Signals matching other tabs
    log_message = Signal(str)
    status_message = Signal(str)

    def __init__(self, form_data: Optional[FormData] = None)
```

### 2. Custom Vehicle Files Panel: `VehicleFilesPanel`
```python
class VehicleFilesPanel(QGroupBox):
    """Independent file selection panel for CSV files"""

    # Own implementation, not shared FilesPanel
    files_changed = Signal()

    Features:
    - CSV file filtering
    - Vehicle count display
    - Color assignment preview
    - File validation indicators
```

### 3. Settings Tabs Structure

#### Tab 1: Animation Settings (Default)
```python
def _create_animation_settings_tab():
    """Settings for basic vehicle animation"""

    Groups:
    - Display Options
      □ Show vehicle trails
      □ Animate movement
      □ Show timestamps
      □ Cluster markers
      □ Auto-center map

    - Animation Controls
      Speed: [0.5x, 1x, 2x, 5x, 10x]
      Trail Length: [5s, 10s, 30s, Full]
      Marker Size: [Small, Medium, Large]

    - Interpolation Settings
      Method: [Linear, Cubic, Geodesic]
      Interval: [0.5s, 1s, 2s, 5s]
      □ Smooth path
```

#### Tab 2: Co-Location Analysis
```python
def _create_colocation_settings_tab():
    """Settings for vehicle co-location detection"""

    Groups:
    - Detection Parameters
      Radius: [50m, 100m, 200m, 500m]
      Time Window: [1min, 5min, 15min, 30min]
      Min Duration: [10s, 30s, 1min, 5min]

    - Display Options
      □ Highlight co-locations
      □ Show duration labels
      □ Connect with lines
      □ Generate timeline
```

#### Tab 3: Idle Detection
```python
def _create_idle_settings_tab():
    """Settings for vehicle idle period detection"""

    Groups:
    - Idle Parameters
      Speed Threshold: [5 km/h ▼]
      Min Duration: [30s, 1min, 2min, 5min]
      □ Include stops at lights
      □ Merge nearby idle periods

    - Visualization
      □ Mark idle locations
      □ Show duration bubbles
      □ Heat map overlay
      □ Timeline view
```

#### Tab 4: Time Jump Analysis
```python
def _create_timejump_settings_tab():
    """Settings for GPS timestamp anomaly detection"""

    Groups:
    - Jump Detection
      Gap Threshold: [5min, 15min, 30min, 1hr]
      □ Highlight gaps
      □ Show gap duration
      □ Connect endpoints

    - Analysis Options
      □ Calculate implied speed
      □ Flag impossible speeds
      Max Speed: [200 km/h ▼]
```

#### Tab 5: Route Analysis (Future)
```python
def _create_route_settings_tab():
    """Settings for route similarity and pattern detection"""

    Groups:
    - Similarity Detection
      Threshold: [70%, 80%, 90%]
      Buffer Distance: [50m, 100m, 200m]

    - Pattern Analysis
      □ Detect repeated routes
      □ Find common waypoints
      □ Identify meeting points
```

### 4. Map Display Widget Integration
```python
def _create_map_section():
    """Create map display area"""

    # Use existing VehicleMapWidget
    self.map_widget = VehicleMapWidget()

    # Add analysis overlay controls
    self.overlay_controls = AnalysisOverlayControls()
```

### 5. Analysis Output Console
```python
def _create_output_section():
    """Create analysis output console"""

    # Custom console for vehicle tracking
    self.output_console = VehicleTrackingConsole()

    Features:
    - Vehicle loading progress
    - Analysis results summary
    - Co-location events list
    - Idle period reports
    - Time jump warnings
```

## Implementation Details

### Settings Management
```python
class VehicleTrackingSettings:
    """Comprehensive settings for all analysis modes"""

    # Animation settings
    animation_enabled: bool = True
    playback_speed: PlaybackSpeed = PlaybackSpeed.NORMAL
    show_trails: bool = True
    trail_length_seconds: float = 30.0

    # Co-location settings
    colocation_enabled: bool = False
    colocation_radius_meters: float = 50.0
    colocation_time_window: float = 300.0

    # Idle detection settings
    idle_detection_enabled: bool = False
    idle_speed_threshold_kmh: float = 5.0
    idle_minimum_duration: float = 60.0

    # Time jump settings
    timejump_detection_enabled: bool = False
    timejump_gap_threshold: float = 900.0  # 15 minutes

    def get_active_analyses(self) -> List[AnalysisType]:
        """Return list of enabled analysis types"""
```

### Worker Integration
```python
def _start_tracking(self):
    """Start vehicle tracking with selected analyses"""

    # Gather settings from all tabs
    settings = self._collect_all_settings()

    # Determine which analyses to run
    analyses = settings.get_active_analyses()

    # Create appropriate worker
    if analyses:
        worker = VehicleAnalysisWorker(
            files=self.selected_files,
            settings=settings,
            analyses=analyses
        )
    else:
        worker = VehicleTrackingWorker(
            files=self.selected_files,
            settings=settings
        )

    # Connect signals and start
    worker.result_ready.connect(self._on_tracking_complete)
    worker.progress_update.connect(self._update_progress)
    worker.start()
```

### State Management
```python
class VehicleTrackingTab:
    def __init__(self):
        # Track current state
        self.current_mode = TrackingMode.ANIMATION
        self.selected_files: List[Path] = []
        self.vehicles: List[VehicleData] = []
        self.analysis_results: Dict[AnalysisType, Any] = {}
        self.operation_active = False

    def _on_tab_changed(self, index: int):
        """Handle analysis tab change"""
        # Update current mode
        self.current_mode = self._get_mode_from_tab(index)

        # Update button states
        self._update_ui_for_mode()

        # Clear previous results if switching modes
        if self.current_mode != TrackingMode.ANIMATION:
            self.map_widget.clear_analysis_overlays()
```

## Visual Design Specifications

### Color Scheme (Matching Media Analysis)
- Background: Application theme (Carolina Blue accents)
- Headers: Bold with emoji icons
- Settings groups: Collapsible with checkboxes
- Progress: Matching progress bar style
- Console: Dark background with syntax highlighting

### Button Styling
```python
# Primary action button
"QPushButton { background-color: #4A90E2; color: white; }"

# Secondary buttons
"QPushButton { background-color: #6c757d; color: white; }"

# Cancel/Stop button
"QPushButton { background-color: #dc3545; color: white; }"
```

### Tab Icons
- 🚗 Animation (default)
- 🎯 Co-Location
- ⏸️ Idle Detection
- ⏱️ Time Jumps
- 🗺️ Route Analysis

## File Structure

```
vehicle_tracking/
├── ui/
│   ├── vehicle_tracking_tab.py          # Main tab implementation
│   ├── components/
│   │   ├── vehicle_files_panel.py       # Custom file selection
│   │   ├── vehicle_map_widget.py        # Existing map widget
│   │   ├── vehicle_tracking_console.py  # Output console
│   │   └── analysis_overlay_controls.py # Map overlay controls
│   └── settings/
│       ├── animation_settings.py
│       ├── colocation_settings.py
│       ├── idle_settings.py
│       └── timejump_settings.py
```

## Implementation Priority

### Phase 1: Core UI (Day 1)
1. Create `VehicleTrackingTab` main structure
2. Implement `VehicleFilesPanel`
3. Create tabbed settings panel
4. Wire up basic animation settings

### Phase 2: Animation Tab (Day 1-2)
1. Complete animation settings UI
2. Connect to existing `VehicleMapWidget`
3. Integrate with `VehicleTrackingWorker`
4. Test basic vehicle loading and display

### Phase 3: Analysis Tabs (Day 2)
1. Implement co-location settings tab
2. Implement idle detection settings tab
3. Create basic analysis workers
4. Add results to output console

### Phase 4: Polish (Day 2-3)
1. Add progress reporting
2. Implement export functionality
3. Add success messages
4. Settings persistence

## Key Differences from Media Analysis Tab

1. **No Shared Dependencies**: Custom file panel instead of shared `FilesPanel`
2. **Map-Centric Display**: Map widget is primary display, not console
3. **Multi-Analysis Modes**: Different analysis types in separate tabs
4. **Real-Time Animation**: Live playback controls vs static analysis
5. **Vehicle-Specific Features**: Color coding, trail display, clustering

## Success Criteria

1. ✅ Tab loads without errors
2. ✅ Can select and load CSV files
3. ✅ Settings tabs switch correctly
4. ✅ Animation plays on map
5. ✅ Analysis results display in console
6. ✅ Progress reporting works
7. ✅ Export generates reports
8. ✅ Settings persist between sessions
9. ✅ Cancellation works properly
10. ✅ Success messages show results

## Risk Mitigation

1. **Map Widget Integration**: Already exists, just needs connection
2. **Analysis Features**: Start with stubs, implement incrementally
3. **Performance**: Use existing worker thread patterns
4. **Settings Complexity**: Group logically, provide defaults
5. **Testing**: Create sample CSV files for testing

## Conclusion

This implementation plan provides a clear path to creating a professional, feature-rich Vehicle Tracking UI that matches the quality and design of the Media Analysis tab while being completely independent. The phased approach allows for incremental development and testing, with the core animation functionality available quickly and analysis features added progressively.

**Estimated Total Time**: 2-3 days for complete implementation with all analysis tabs