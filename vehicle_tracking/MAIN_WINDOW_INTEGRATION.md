# Vehicle Tracking Tab - Main Window Integration Guide

## Overview
This document provides instructions for integrating the Vehicle Tracking tab into the main application window when the UI is ready.

## Integration Steps

### Step 1: Import the Tab
Add to the imports section of `ui/main_window.py` (around line 35 with other tab imports):

```python
from vehicle_tracking.ui.vehicle_tracking_tab import VehicleTrackingTab
```

### Step 2: Create Tab Instance
In the `_setup_tabs()` method (around line 123), add after media_analysis_tab:

```python
# Vehicle Tracking Tab (optional module)
try:
    self.vehicle_tracking_tab = VehicleTrackingTab(self.form_data)
    self.tab_widget.addTab(self.vehicle_tracking_tab, "Vehicle Tracking")

    # Connect signals
    self.vehicle_tracking_tab.log_message.connect(self._handle_log_message)
    self.vehicle_tracking_tab.status_message.connect(self.status_bar.showMessage)
except ImportError:
    # Vehicle tracking module not available
    self.vehicle_tracking_tab = None
```

### Step 3: Optional - Add Menu Action (if menu bar exists)
If there's a menu bar, add an action to show/hide the tab:

```python
# In menu setup
vehicle_tracking_action = QAction("Vehicle Tracking", self)
vehicle_tracking_action.setCheckable(True)
vehicle_tracking_action.setChecked(True)
vehicle_tracking_action.triggered.connect(self._toggle_vehicle_tracking_tab)
```

## Minimal Integration (4 Lines Only)

If you prefer the absolute minimum integration without error handling:

```python
# Line 1: Import
from vehicle_tracking.ui.vehicle_tracking_tab import VehicleTrackingTab

# Line 2: Create instance
self.vehicle_tracking_tab = VehicleTrackingTab(self.form_data)

# Line 3: Add to tab widget
self.tab_widget.addTab(self.vehicle_tracking_tab, "Vehicle Tracking")

# Line 4: Connect log signal (optional but recommended)
self.vehicle_tracking_tab.log_message.connect(self._handle_log_message)
```

## Testing the Integration

1. **Check Service Registration**:
   ```python
   from core.services import get_service, IVehicleTrackingService
   service = get_service(IVehicleTrackingService)
   print(f"Vehicle tracking service: {service}")
   ```

2. **Verify Tab Appears**:
   - Run the application
   - Look for "Vehicle Tracking" tab
   - Tab should be visible even if UI components are incomplete

3. **Check Log Output**:
   - Click on Vehicle Tracking tab
   - Check console for any initialization messages

## Dependencies

The Vehicle Tracking tab requires:
- PySide6 (already installed)
- No additional Python packages needed for basic functionality

Optional dependencies for full features:
- Leaflet.js (loaded from CDN in HTML template)
- QWebEngineView (part of PySide6)

## Graceful Degradation

The integration is designed to fail gracefully:
- If the module isn't found, the tab won't appear
- If the service isn't registered, operations will return error Results
- If UI components are incomplete, partial functionality remains

## Current Status

As of this documentation:
- ✅ Service interface added to core
- ✅ Service registration with fallback
- ✅ Module structure complete
- ⏳ UI components need completion
- ⏳ Main window integration pending

## Notes

- The tab will use the existing FormData instance from MainWindow
- Log messages will appear in the application's log console
- Status messages will show in the status bar
- The tab follows the same patterns as MediaAnalysisTab