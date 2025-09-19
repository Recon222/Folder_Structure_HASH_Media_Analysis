# Tauri Integration - Simplified Implementation Roadmap
## Vehicle Tracking System - 4-6 Hour Sprint

### 🎯 Goal
Replace QWebEngineView with Tauri to fix CSS conflicts while keeping existing architecture intact.

---

## Phase 1: Tauri App Setup (1 hour)

### Step 1.1: Create Tauri Application
```bash
cd vehicle_tracking
npx create-tauri-app tauri-map --template vanilla
cd tauri-map

# Install dependencies
npm install
```

### Step 1.2: Copy Templates
```bash
# Copy the production-ready Mapbox template
cp ../templates/maps/mapbox_tauri_template_production.html src/mapbox.html

# Copy and modify Leaflet template (remove QWebChannel)
cp ../templates/maps/leaflet_vehicle_template.html src/leaflet.html
```

### Step 1.3: Minimal Rust Setup
```rust
// src-tauri/src/main.rs
use tauri::Manager;

#[tauri::command]
fn get_ws_port(window: tauri::Window) -> u16 {
    // Get port from command line args or environment
    std::env::args().nth(1)
        .and_then(|arg| arg.parse().ok())
        .unwrap_or(8765)
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![get_ws_port])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

### Step 1.4: Simple HTML Router
```html
<!-- src/index.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Vehicle Tracking Map</title>
    <script>
        // Get provider from URL params or default
        const params = new URLSearchParams(window.location.search);
        const provider = params.get('provider') || 'mapbox';

        // Redirect to appropriate template
        window.location.href = `${provider}.html${window.location.search}`;
    </script>
</head>
<body>Loading...</body>
</html>
```

---

## Phase 2: Simple Bridge Service (1 hour)

### Step 2.1: Install WebSocket Server
```bash
pip install websocket-server
```

### Step 2.2: Create Bridge Service
```python
# vehicle_tracking/services/tauri_bridge_service.py
#!/usr/bin/env python3
"""
Simplified Tauri Bridge Service - No async complexity
"""

import json
import subprocess
import threading
import socket
from pathlib import Path
from typing import Optional, Dict, Any
from websocket_server import WebsocketServer

from core.services.base_service import BaseService
from core.result_types import Result
from core.logger import logger


class TauriBridgeService(BaseService):
    """Simple bridge service using threading instead of asyncio"""

    def __init__(self):
        super().__init__("TauriBridgeService")

        # WebSocket server
        self.ws_server: Optional[WebsocketServer] = None
        self.ws_port: Optional[int] = None
        self.ws_thread: Optional[threading.Thread] = None

        # Tauri process
        self.tauri_process: Optional[subprocess.Popen] = None
        self.tauri_path = Path(__file__).parent.parent / "tauri-map"

        # State
        self.is_running = False
        self.connected_clients = []
        self.pending_messages = []

    def find_free_port(self) -> int:
        """Find an available port"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    def start(self) -> Result[int]:
        """Start WebSocket server and launch Tauri"""
        try:
            # Find available port
            self.ws_port = self.find_free_port()
            logger.info(f"Using WebSocket port: {self.ws_port}")

            # Start WebSocket server in thread
            self._start_websocket_server()

            # Launch Tauri application
            self._launch_tauri()

            self.is_running = True
            return Result.success(self.ws_port)

        except Exception as e:
            logger.error(f"Failed to start bridge: {e}")
            return Result.error(str(e))

    def _start_websocket_server(self):
        """Start WebSocket server in a thread"""
        self.ws_server = WebsocketServer(port=self.ws_port, host='localhost')

        # Set up callbacks
        self.ws_server.set_fn_new_client(self._on_client_connected)
        self.ws_server.set_fn_client_left(self._on_client_disconnected)
        self.ws_server.set_fn_message_received(self._on_message_received)

        # Start in daemon thread
        self.ws_thread = threading.Thread(target=self.ws_server.serve_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()

        logger.info(f"WebSocket server started on port {self.ws_port}")

    def _launch_tauri(self):
        """Launch Tauri application"""
        try:
            # Build path to Tauri executable
            if sys.platform == "win32":
                exe_name = "tauri-map.exe"
            else:
                exe_name = "tauri-map"

            exe_path = self.tauri_path / "src-tauri" / "target" / "release" / exe_name

            # Check if built, if not try to build
            if not exe_path.exists():
                logger.info("Building Tauri application...")
                build_cmd = ["npm", "run", "tauri", "build"]
                subprocess.run(build_cmd, cwd=self.tauri_path, check=True)

            # Launch with WebSocket port parameter
            cmd = [str(exe_path), f"--ws-port={self.ws_port}"]

            # Also pass as URL parameter
            env = os.environ.copy()
            env['TAURI_WS_PORT'] = str(self.ws_port)

            self.tauri_process = subprocess.Popen(
                cmd,
                cwd=self.tauri_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            logger.info("Tauri application launched")

        except Exception as e:
            logger.error(f"Failed to launch Tauri: {e}")
            raise

    def _on_client_connected(self, client, server):
        """Handle new WebSocket client"""
        logger.info(f"Tauri client connected: {client['id']}")
        self.connected_clients.append(client)

        # Send any pending messages
        for msg in self.pending_messages:
            server.send_message(client, json.dumps(msg))
        self.pending_messages.clear()

    def _on_client_disconnected(self, client, server):
        """Handle client disconnect"""
        logger.info(f"Tauri client disconnected: {client['id']}")
        if client in self.connected_clients:
            self.connected_clients.remove(client)

    def _on_message_received(self, client, server, message):
        """Handle message from Tauri"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')

            if msg_type == 'ready':
                logger.info("Tauri map ready")
            elif msg_type == 'vehicle_clicked':
                logger.info(f"Vehicle clicked: {data.get('vehicle_id')}")
            elif msg_type == 'error':
                logger.error(f"Tauri error: {data.get('message')}")

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def send_vehicle_data(self, vehicle_data: Dict[str, Any]) -> Result[None]:
        """Send vehicle data to Tauri"""
        try:
            message = {
                "type": "load_vehicles",
                "data": vehicle_data
            }

            if self.connected_clients and self.ws_server:
                # Send to all connected clients
                self.ws_server.send_message_to_all(json.dumps(message))
                logger.info(f"Sent vehicle data to {len(self.connected_clients)} clients")
            else:
                # Queue for when client connects
                self.pending_messages.append(message)
                logger.info("Queued vehicle data for when client connects")

            return Result.success(None)

        except Exception as e:
            logger.error(f"Failed to send vehicle data: {e}")
            return Result.error(str(e))

    def shutdown(self):
        """Clean shutdown"""
        logger.info("Shutting down Tauri bridge...")

        # Stop WebSocket server
        if self.ws_server:
            self.ws_server.shutdown()

        # Terminate Tauri process
        if self.tauri_process:
            self.tauri_process.terminate()
            try:
                self.tauri_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.tauri_process.kill()

        self.is_running = False
        logger.info("Tauri bridge shutdown complete")
```

---

## Phase 3: Modify VehicleMapWindow (1 hour)

### Step 3.1: Update the Window Class
```python
# vehicle_tracking/ui/vehicle_tracking_tab.py (modify existing class)

class VehicleMapWindow(QWidget):
    """Modified to be a control panel while Tauri shows the map"""

    def __init__(self, tracking_results: VehicleTrackingResult, parent=None):
        super().__init__(parent)

        self.tracking_results = tracking_results
        self.bridge = None

        # Update window properties - smaller since it's just controls
        self.setWindowTitle("Vehicle Tracking - Control Panel")
        self.setWindowIcon(QIcon("🎮"))  # Control icon
        self.resize(400, 500)  # Smaller window

        # Create UI
        self._create_ui()

        # Launch map after UI is ready
        QTimer.singleShot(100, self._launch_map)

    def _create_ui(self):
        """Create control panel UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title_label = QLabel("🗺️ Vehicle Tracking Map Controls")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        # Status
        self.status_label = QLabel("Initializing map...")
        self.status_label.setStyleSheet("color: #666; padding: 10px;")
        layout.addWidget(self.status_label)

        # Separator
        layout.addWidget(self._create_separator())

        # Map Provider Selection
        provider_group = QGroupBox("Map Provider")
        provider_layout = QVBoxLayout(provider_group)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Mapbox (High Performance)", "Leaflet (Open Source)"])
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_layout.addWidget(self.provider_combo)

        layout.addWidget(provider_group)

        # Controls
        controls_group = QGroupBox("Animation Controls")
        controls_layout = QGridLayout(controls_group)

        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self._play_animation)
        controls_layout.addWidget(self.play_btn, 0, 0)

        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.clicked.connect(self._pause_animation)
        controls_layout.addWidget(self.pause_btn, 0, 1)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.clicked.connect(self._stop_animation)
        controls_layout.addWidget(self.stop_btn, 0, 2)

        layout.addWidget(controls_group)

        # Info
        info_group = QGroupBox("Information")
        info_layout = QVBoxLayout(info_group)

        if self.tracking_results:
            vehicles_count = len(self.tracking_results.vehicles) if self.tracking_results.vehicles else 0
            info_text = f"""
            <b>Vehicles:</b> {vehicles_count}<br>
            <b>Time Range:</b> {self.tracking_results.time_range}<br>
            <b>Analysis Type:</b> {self.tracking_results.analysis_type.value}
            """
            info_label = QLabel(info_text)
            info_layout.addWidget(info_label)

        layout.addWidget(info_group)

        # Spacer
        layout.addStretch()

        # Close button
        close_btn = QPushButton("Close Map")
        close_btn.clicked.connect(self._close_map)
        layout.addWidget(close_btn)

    def _create_separator(self):
        """Create a horizontal separator"""
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def _launch_map(self):
        """Launch Tauri map application"""
        try:
            self.status_label.setText("Starting WebSocket server...")

            # Initialize bridge service
            from vehicle_tracking.services.tauri_bridge_service import TauriBridgeService
            self.bridge = TauriBridgeService()

            # Start bridge (WebSocket + Tauri)
            result = self.bridge.start()

            if result.success:
                self.status_label.setText("Launching map window...")

                # Send vehicle data after a short delay
                QTimer.singleShot(2000, self._send_tracking_data)
            else:
                self.status_label.setText(f"Error: {result.error}")
                QMessageBox.critical(self, "Launch Error", f"Failed to launch map: {result.error}")

        except Exception as e:
            logger.error(f"Failed to launch map: {e}")
            self.status_label.setText(f"Error: {str(e)}")

    def _send_tracking_data(self):
        """Send tracking data to Tauri map"""
        try:
            if self.tracking_results and self.tracking_results.animation_data:
                # Convert to dictionary
                data = self.tracking_results.animation_data.to_dict()

                # Send via bridge
                result = self.bridge.send_vehicle_data(data)

                if result.success:
                    self.status_label.setText("✓ Map loaded with vehicle data")
                else:
                    self.status_label.setText(f"Error sending data: {result.error}")
            else:
                self.status_label.setText("✓ Map ready (no data to display)")

        except Exception as e:
            logger.error(f"Failed to send data: {e}")
            self.status_label.setText(f"Error: {str(e)}")

    def _on_provider_changed(self, text: str):
        """Handle provider change"""
        if self.bridge and self.bridge.is_running:
            provider = "mapbox" if "Mapbox" in text else "leaflet"
            self.bridge.send_vehicle_data({
                "type": "switch_provider",
                "provider": provider
            })

    def _play_animation(self):
        """Send play command"""
        if self.bridge:
            self.bridge.send_vehicle_data({"type": "control", "command": "play"})

    def _pause_animation(self):
        """Send pause command"""
        if self.bridge:
            self.bridge.send_vehicle_data({"type": "control", "command": "pause"})

    def _stop_animation(self):
        """Send stop command"""
        if self.bridge:
            self.bridge.send_vehicle_data({"type": "control", "command": "stop"})

    def _close_map(self):
        """Close map and cleanup"""
        if self.bridge:
            self.bridge.shutdown()
        self.close()

    def closeEvent(self, event):
        """Handle window close"""
        if self.bridge:
            self.bridge.shutdown()
        super().closeEvent(event)
```

---

## Phase 4: Update Templates (30 minutes)

### Step 4.1: Add WebSocket to Mapbox Template
```javascript
// Add to mapbox_tauri_template_production.html (after line 1982)

// WebSocket connection for Python bridge
class PythonBridge {
    constructor() {
        // Get port from URL params or Tauri
        this.port = new URLSearchParams(window.location.search).get('port') || 8765;
        this.connect();
    }

    connect() {
        this.ws = new WebSocket(`ws://localhost:${this.port}/`);

        this.ws.onopen = () => {
            console.log('[PythonBridge] Connected');
            this.ws.send(JSON.stringify({ type: 'ready' }));
        };

        this.ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                this.handleMessage(msg);
            } catch (e) {
                console.error('[PythonBridge] Parse error:', e);
            }
        };

        this.ws.onerror = (error) => {
            console.error('[PythonBridge] Error:', error);
        };

        this.ws.onclose = () => {
            console.log('[PythonBridge] Disconnected, retrying...');
            setTimeout(() => this.connect(), 2000);
        };
    }

    handleMessage(msg) {
        switch(msg.type) {
            case 'load_vehicles':
                if (window.vehicleMap) {
                    window.vehicleMap.loadVehicles(msg.data);
                }
                break;

            case 'control':
                this.handleControl(msg.command);
                break;

            case 'switch_provider':
                window.location.href = `${msg.provider}.html?port=${this.port}`;
                break;
        }
    }

    handleControl(command) {
        if (!window.vehicleMap) return;

        switch(command) {
            case 'play':
                window.vehicleMap.startAnimation();
                break;
            case 'pause':
                window.vehicleMap.pauseAnimation();
                break;
            case 'stop':
                window.vehicleMap.stopAnimation();
                break;
        }
    }

    send(data) {
        if (this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }
}

// Initialize bridge
window.pythonBridge = new PythonBridge();

// Hook into existing vehicle click handler
const originalOnVehicleClick = window.vehicleMapInstance?.onVehicleClick;
if (originalOnVehicleClick) {
    window.vehicleMapInstance.onVehicleClick = function(vehicleId) {
        originalOnVehicleClick.call(this, vehicleId);
        window.pythonBridge.send({ type: 'vehicle_clicked', vehicle_id: vehicleId });
    };
}
```

### Step 4.2: Update Leaflet Template Similarly
Remove QWebChannel code and add the same PythonBridge class.

---

## Phase 5: Testing (1-2 hours)

### Step 5.1: Build Tauri
```bash
cd vehicle_tracking/tauri-map
npm run tauri build
```

### Step 5.2: Test Script
```python
# test_tauri_integration.py
from vehicle_tracking.services.tauri_bridge_service import TauriBridgeService
from vehicle_tracking.models.vehicle_tracking_models import VehicleTrackingResult
import time

# Create mock data
mock_result = VehicleTrackingResult(
    vehicles=[...],  # Add test vehicle data
    animation_data=...
)

# Start bridge
bridge = TauriBridgeService()
result = bridge.start()

if result.success:
    print(f"WebSocket running on port {result.value}")

    # Wait for connection
    time.sleep(3)

    # Send test data
    bridge.send_vehicle_data(mock_result.animation_data.to_dict())

    # Keep running
    input("Press Enter to stop...")

    bridge.shutdown()
```

---

## ✅ Success Criteria

1. **CSS Issues Resolved**: No more Leaflet/Mapbox conflicts
2. **Performance Improved**: 50%+ memory reduction
3. **Existing Code Works**: Minimal changes to existing vehicle tracking
4. **User Experience Same**: Still opens separate map window
5. **Provider Switching Works**: Can switch between Mapbox/Leaflet

---

## 📊 Time Breakdown

| Task | Time | Status |
|------|------|--------|
| Tauri app setup | 1 hour | Ready |
| Bridge service | 1 hour | Ready |
| Modify VehicleMapWindow | 1 hour | Ready |
| Update templates | 30 mins | Ready |
| Testing | 1-2 hours | Ready |
| **Total** | **4.5-5.5 hours** | ✅ |

---

## 🚀 Quick Start Commands

```bash
# 1. Set up Tauri
cd vehicle_tracking
npx create-tauri-app tauri-map --template vanilla

# 2. Copy templates
cp templates/maps/mapbox_tauri_template_production.html tauri-map/src/mapbox.html

# 3. Install Python deps
pip install websocket-server

# 4. Build Tauri
cd tauri-map && npm run tauri build

# 5. Test
cd .. && python test_tauri_integration.py
```

---

## 🎯 Key Insight

**We're not redesigning - we're just swapping the renderer!**

- Keep: Window management, data processing, UI structure
- Replace: Only QWebEngineView → Tauri
- Result: Same UX, no CSS conflicts, better performance