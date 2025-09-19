# Tauri Integration Debugging Session - AI Handoff Document

## Current Status
**Date**: 2025-01-19
**Session Duration**: ~2 hours
**Primary Issues**:
1. ✅ Tauri app builds and launches successfully
2. ❌ Mapbox token modal not visible (DOM present but not displayed)
3. ❌ WebSocket connection failing (port mismatch)

## System Architecture Overview

### Components
1. **Python Test Script** (`test_tauri_integration.py`)
   - Creates mock vehicle tracking data
   - Starts WebSocket server on dynamic port (e.g., 53719)
   - Launches Tauri executable with `--ws-port=PORT` argument

2. **Tauri Application** (`vehicle_tracking/tauri-map/`)
   - Rust backend that creates a native window with web view
   - Should receive WebSocket port via command line args
   - Hosts HTML/JS map visualization

3. **Map Visualization** (`src/mapbox.html`)
   - Mapbox GL JS implementation
   - Should show token input modal if no token saved
   - WebSocket client to receive vehicle data from Python

### Data Flow
```
Python Script → WebSocket Server (port 53719)
      ↓
Launches Tauri with --ws-port=53719
      ↓
Tauri Window loads index.html → redirects to mapbox.html
      ↓
JavaScript should:
  1. Check localStorage for saved Mapbox token
  2. If no token, show modal
  3. Connect to Python WebSocket on correct port
  4. Receive and display vehicle tracking data
```

## Current Issues in Detail

### Issue 1: Token Modal Not Visible
**Symptoms:**
- Console shows modal element is found: `[showTokenModal] Modal element: <div id="tokenModal" class="token-modal show">`
- "show" class is being added
- But modal is not visible to user

**What We've Tried:**
1. Added `!important` to CSS visibility rules
2. Added inline styles via JavaScript to force visibility
3. Set z-index to 9999
4. Verified DOM is ready before showing modal
5. Added retry logic if DOM elements not found

**Console Output:**
```javascript
[waitForConfig] Showing token modal...
[showTokenModal] Modal element: <div id="tokenModal" class="token-modal show">
[showTokenModal] Input element: <input type="text" id="tokenInput"...>
[showTokenModal] Adding show class to modal
[showTokenModal] Forced styles applied
```

**Hypothesis:**
- Something else might be covering the modal (loading screen?)
- CSS might be overridden by another rule
- Tauri webview might have rendering issues

### Issue 2: WebSocket Port Mismatch
**Symptoms:**
- Python starts WebSocket on dynamic port (e.g., 53719)
- JavaScript tries to connect to default port 8765
- Connection refused errors in console

**What We've Tried:**
1. Pass port via command line: `--ws-port=53719`
2. Pass port via environment variable: `TAURI_WS_PORT`
3. Modified Rust to pass port in URL parameters
4. Added Tauri IPC command `get_ws_port()`
5. Delayed PythonBridge initialization to wait for Tauri APIs

**Current Code State:**
- Rust backend has debug logging to show received args
- JavaScript tries multiple methods to get port
- But `window.__TAURI__.invoke` is not functioning properly

**Console Errors:**
```
[PythonBridge] Connecting to ws://localhost:8765/
WebSocket connection to 'ws://localhost:8765/' failed: Error in connection establishment: net::ERR_CONNECTION_REFUSED
```

### Issue 3: Tauri API Not Ready
**Symptoms:**
- `window.__TAURI__.invoke is not a function` errors
- `window.__TAURI__.event` is undefined
- Tauri APIs not available when JavaScript runs

**What We've Tried:**
1. Added delays before using Tauri APIs
2. Check for API availability before use
3. Simplified index.html to avoid early API calls

## File Locations & Key Code

### Modified Files in This Session
1. `/vehicle_tracking/tauri-map/src/mapbox.html`
   - Added token modal HTML (lines 642-665)
   - Added modal CSS styles (lines 30-153)
   - Added tokenModalManager object (lines 770-850)
   - Modified waitForConfig() to show modal (lines 939-972)
   - Modified showTokenModal() with retry logic (lines 974-1028)
   - Modified PythonBridge to get port from Tauri (lines 2358-2385)

2. `/vehicle_tracking/tauri-map/src-tauri/src/main.rs`
   - Added debug logging for port detection (lines 6-36)
   - Modified main() to pass port via URL (lines 46-64)

3. `/vehicle_tracking/tauri-map/src-tauri/tauri.conf.json`
   - Configuration for Tauri v1.5
   - Window settings, bundle configuration

4. `/vehicle_tracking/services/tauri_bridge_service.py`
   - Fixed executable name: "Vehicle Tracking Map.exe" (line 91)
   - Passes port via --ws-port argument (line 106)
   - Sets TAURI_WS_PORT environment variable (line 110)

### Build & Test Commands
```powershell
# Kill any running processes
Get-Process | Where-Object {$_.Name -like "*Vehicle Tracking*"} | Stop-Process -Force

# Build Tauri app
cd "C:\Users\kriss\Desktop\Working_Apps_for_CFSA\Folder Structure App\folder_structure_application\vehicle_tracking\tauri-map"
npm run build

# Run test
cd ..
python test_tauri_integration.py
```

### DevTools Debugging
To open DevTools in Tauri window:
1. Right-click in the window
2. Select "Inspect" or "Inspect Element"
3. Check Console tab for errors
4. Check Elements tab to verify modal HTML/CSS

## Version Information
- Tauri: v1.5 (Rust crates)
- @tauri-apps/api: v1.5.6
- @tauri-apps/cli: v1.5.14
- PySide6: Used for main application
- Python: 3.x with websocket-server package

## Next Steps to Try

### For Modal Visibility Issue:
1. **Check loading screen z-index**: Look for `.loading-screen` element that might be covering modal
2. **Try removing loading screen**: Add code to hide loading screen when showing modal
3. **Test in browser**: Open `mapbox.html` directly in browser to see if modal works outside Tauri
4. **Check computed styles**: In DevTools, check all computed styles on modal element
5. **Try alert() test**: Replace modal with simple alert() to verify code path works

### For WebSocket Port Issue:
1. **Hardcode port temporarily**: Change Python to use fixed port 8765 to test if connection works
2. **Check Rust console output**: The debug prints should show what args are received
3. **Try URL parameter directly**: Modify index.html redirect to include `?port=53719`
4. **Bypass Tauri IPC**: Don't use `window.__TAURI__.invoke`, just parse URL params

### For Tauri API Issue:
1. **Check Tauri version compatibility**: Ensure HTML is using correct API for Tauri v1.5
2. **Add window load listener**: Wait for window.onload before accessing Tauri APIs
3. **Check CSP settings**: Content Security Policy might block Tauri APIs

## Important Context

### Why Tauri?
The original application used QWebEngineView (Qt's web view) but had severe CSS conflicts between the main app's styling and the map visualization. Tauri provides complete isolation by running the map in a separate process/window.

### Architecture Decision
Instead of complex async solutions, we used:
- Simple WebSocket for Python-JavaScript communication
- Threading instead of asyncio in Python
- Separate control panel window in Qt while map runs in Tauri

### Known Working Parts
- ✅ Tauri builds successfully
- ✅ Executable launches from Python
- ✅ WebSocket server starts in Python
- ✅ Mock vehicle data is created
- ✅ HTML/JavaScript loads in Tauri window
- ✅ Modal DOM elements are created
- ✅ DevTools work in Tauri window (right-click → Inspect)

### Known Broken Parts
- ❌ Modal not visible despite being in DOM
- ❌ WebSocket connects to wrong port
- ❌ Tauri IPC commands not working
- ❌ No visual indication of what's blocking modal

## Testing Data
The test creates 2 mock vehicles with 10 GPS points each:
- Vehicle 1: Blue color, 10 points with increasing speed
- Vehicle 2: Red color, 10 points with movement
- Animation timeline: 2024-01-01 10:00:00 to 10:00:09

## Success Criteria
1. User sees token input modal on first launch
2. User can enter and save Mapbox token
3. Token persists in localStorage for future sessions
4. WebSocket connects to Python on correct port
5. Vehicle data displays on map
6. Animation controls work (play/pause/stop)

## Additional Resources
- Original roadmap: `/vehicle_tracking/TAURI_SIMPLIFIED_ROADMAP.md`
- Mapbox template: `/vehicle_tracking/templates/maps/mapbox_tauri_template_production.html`
- Test script: `/vehicle_tracking/test_tauri_integration.py`

## Questions for Next Session
1. Should we simplify by using a fixed WebSocket port?
2. Should we try Tauri v2 instead of v1.5?
3. Could we show the token input differently (not as modal)?
4. Is the loading screen interfering with modal display?
5. Should we add more aggressive debugging (visual borders, console.log every line)?

## Session Summary
Made significant progress on Tauri integration but stuck on two interconnected issues: modal visibility and WebSocket port communication. The architecture is sound but implementation details around Tauri's API availability and CSS rendering are causing problems. The next debugging session should focus on simplifying the approach - perhaps hardcoding the port and using a simpler token input method to get a working baseline before adding complexity back.