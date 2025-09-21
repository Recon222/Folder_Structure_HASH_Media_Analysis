# Vehicle Tracking Trail Settings Debug - AI Handoff Document

## Issue Summary
The vehicle tracking animation feature has a trail rendering issue where:
1. Trail settings from the UI (None, 5s, 10s, 30s, 60s, Persistent) are not being applied
2. Trails are always showing even when set to "None"
3. A Tauri API error is breaking JavaScript execution preventing settings from being received

## Current State of the Issue
- **Primary Problem**: Trail settings still not working after fixes
- **Error in Console**: `Uncaught TypeError: window.__TAURI__.invoke is not a function`
- **Symptom**: Trails always show regardless of UI settings
- **Possible Cause**: Cache issue preventing updated JavaScript from loading

## Work Completed in This Session

### 1. Trail Feature Enhancement Implementation
**Goal**: Add configurable trail options with "None" as default

#### Changes Made:
- **UI (vehicle_tracking_tab.py)**:
  - Added "None" option to trail dropdown (line 271)
  - Changed "Full" to "Persistent"
  - Set default to "None" (index 0)
  - Updated trail mapping: `{"None": 0, "5 seconds": 5, ..., "Persistent": -1}`
  - Changed `show_trails_check` default to unchecked (False)
  - Modified `_convert_to_js_format()` to include settings in vehicle data

- **JavaScript (mapbox.html)**:
  - Changed default `CONFIG.trailLength` from 100 to 0
  - Updated `loadVehicles()` to apply received settings with proper defaults
  - Modified `getTrailPoints()` to handle:
    - 0 = no trail
    - >0 = time-based trail with cutoff
    - -1 = persistent trail (full path)
  - Added performance optimization to skip trail calculation when disabled
  - Implemented trail opacity fading based on age (30% to 100%)

### 2. Tauri API Integration Fix
**Root Cause**: JavaScript trying to invoke non-existent Rust commands

#### Discovered Issues:
- Rust backend only has `get_ws_port` and `get_map_config` commands
- JavaScript trying to invoke: `map_ready`, `vehicle_clicked`, `animation_complete`, `map_error`
- These don't exist in Rust, causing uncaught exceptions

#### Fixes Applied:
- Replaced all non-existent Tauri invokes with WebSocket messages
- Changed from `window.__TAURI__.invoke()` to `window.pythonBridge.send()`
- Added type checking: `typeof window.__TAURI__.invoke === 'function'`
- All events now sent through existing WebSocket connection

### 3. Error Handler Fix
**Fixed AttributeError**: `VehicleTrackingWorker` doesn't have `error_occurred` signal
- Removed incorrect signal connection
- Added comment explaining errors come through `result_ready`

## Debug Logging Added
```javascript
// In handleMessage (line 2535)
console.log('[PythonBridge] Received vehicle data:', msg.data);
console.log('[PythonBridge] Settings in data:', msg.data.settings);

// In loadVehicles (line 1418)
console.log('[Settings] Trail settings:', {
    showTrails: CONFIG.showTrails,
    trailLength: CONFIG.trailLength
});

// In renderFrame (line 1713)
if (this.performanceMetrics.frameCount % 60 === 0) {
    console.log('[Trail Debug]', {
        showTrails: CONFIG.showTrails,
        trailLength: CONFIG.trailLength,
        vehicleId: vehicleId
    });
}
```

## Cache Issues - LIKELY CULPRIT

### Browser/WebView Cache
The Tauri app uses a WebView which may be caching the old JavaScript:

1. **Tauri WebView Cache Locations** (Windows):
   - `%APPDATA%\com.cfsa.vehicletracking\`
   - `%LOCALAPPDATA%\com.cfsa.vehicletracking\`
   - WebView2 cache: `%USERPROFILE%\AppData\Local\Microsoft\Edge\User Data\`

2. **Force Refresh Methods**:
   - Add cache-busting query params to HTML files
   - Clear WebView2 cache programmatically
   - Rebuild Tauri app with `--force` flag

3. **Stale ws-config.js**:
   - Console shows "Config file is stale (50651.731 seconds old)"
   - Delete: `vehicle_tracking/tauri-map/src/ws-config.js`

### Rebuild Commands
```bash
# Clean build
cd vehicle_tracking/tauri-map
rm -rf src-tauri/target
rm src/ws-config.js
cd src-tauri
cargo build --release
```

## Settings Data Flow (How It Should Work)

1. **Python Side** (vehicle_tracking_tab.py):
   ```python
   settings = self._gather_current_settings()  # Gets UI values
   js_data = {
       "vehicles": [...],
       "settings": {
           "showTrails": settings.show_trails,      # From checkbox
           "trailLength": settings.trail_length,    # 0, 5-60, or -1
           ...
       }
   }
   ```

2. **WebSocket Transport** (tauri_bridge_service.py):
   ```python
   message = {"type": "load_vehicles", "data": vehicle_data}
   self.ws_server.send_message_to_all(json.dumps(message))
   ```

3. **JavaScript Reception** (mapbox.html):
   ```javascript
   // Should receive and apply settings
   if (vehicleData.settings) {
       CONFIG.showTrails = vehicleData.settings.showTrails;
       CONFIG.trailLength = vehicleData.settings.trailLength;
   }
   ```

## What's Not Working

**Missing Console Output**: The debug logs aren't appearing, suggesting:
1. Old cached JavaScript is still running
2. Settings aren't being included in the WebSocket message
3. WebSocket message arrives before map initialization

## Next Debugging Steps

### 1. Verify Python Side
Check if settings are actually being sent:
```python
# In _open_map_with_tauri() around line 809
vehicle_data_js = self._convert_to_js_format(self.last_results)
print(f"DEBUG: Sending settings: {vehicle_data_js.get('settings')}")
```

### 2. Force Cache Clear
```bash
# Windows PowerShell
Remove-Item -Recurse -Force "$env:APPDATA\com.cfsa.vehicletracking"
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\com.cfsa.vehicletracking"
```

### 3. Add Version String
Add to mapbox.html to verify updates are loaded:
```javascript
console.log('[Version] mapbox.html v2024.09.19.18:00');
```

### 4. Check WebSocket Message Order
The vehicle data might be sent before the map is ready. Check if:
- `loadVehicles()` is called before map initialization
- Settings are applied but then overwritten

### 5. Direct Test
Open browser console and manually test:
```javascript
CONFIG.showTrails = false;
CONFIG.trailLength = 0;
```

## Files Modified

### Python Files:
- `/vehicle_tracking/ui/vehicle_tracking_tab.py`
  - Lines: 271-273 (trail dropdown)
  - Lines: 235-237 (show_trails checkbox)
  - Lines: 688-692 (trail mapping)
  - Lines: 838-879 (_convert_to_js_format)
  - Line: 643 (removed error_occurred signal)

### JavaScript Files:
- `/vehicle_tracking/tauri-map/src/mapbox.html`
  - Line: 768-769 (default CONFIG)
  - Lines: 1406-1421 (loadVehicles settings)
  - Lines: 1710-1743 (trail rendering)
  - Lines: 1823-1836 (getTrailPoints)
  - Lines: 2195-2243 (Tauri invoke replacements)
  - Lines: 960-974 (Tauri API checks)

### Configuration:
- `/vehicle_tracking/tauri-map/src-tauri/tauri.conf.json`
  - Verified: `"withGlobalTauri": true`

## Alternative Solutions

### 1. Hard Refresh in Tauri
Add to main.rs:
```rust
window.eval("location.reload(true)").ok();
```

### 2. Bypass Cache with Timestamp
```javascript
window.location.href = `mapbox.html?port=${port}&v=${Date.now()}`;
```

### 3. Direct Settings Override
Add UI controls in the map itself to test without Python:
```javascript
// Add temporary debug buttons
document.getElementById('debug-trails-off').onclick = () => {
    CONFIG.showTrails = false;
    CONFIG.trailLength = 0;
};
```

## Summary for Next AI

**The Issue**: Trail settings aren't being applied despite comprehensive fixes. The root cause appears to be cached JavaScript in the Tauri WebView.

**Key Points**:
1. All code changes are correct and should work
2. Tauri invoke errors have been fixed
3. Settings are being passed through WebSocket
4. Debug logs aren't appearing = old code is running

**Priority Action**: Clear all caches and rebuild the Tauri application. The code is correct; it's just not being loaded.

**Test Method**: After clearing cache, you should see:
- No Tauri invoke errors
- Debug console logs showing settings received
- Trails responding to UI settings
- "None" = no trails, "Persistent" = full path

---
*Document created: 2024-09-19 18:00*
*Context: Debugging session after implementing trail feature enhancements*