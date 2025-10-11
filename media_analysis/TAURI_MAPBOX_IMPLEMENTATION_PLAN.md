# Tauri/Mapbox Implementation Plan for Media Analysis Module

## Executive Summary

### Purpose
Replace the current Leaflet/QWebEngineView implementation with a Tauri/Mapbox architecture to achieve:

1. **Performance Isolation** - Eliminate CSS conflicts with the main PySide6 application
2. **Enhanced Performance** - Leverage Mapbox GL JS's WebGL rendering for smooth interactions
3. **Advanced Features** - Enable clustering, heatmaps, and timeline animations
4. **Scalability** - Handle thousands of photo markers efficiently
5. **Consistency** - Align with Vehicle Tracking module's proven architecture

### Benefits
- ✅ **No CSS Conflicts** - Tauri app runs in separate process with independent styling
- ✅ **Superior Performance** - WebGL-accelerated rendering vs. DOM-based Leaflet
- ✅ **Better Clustering** - Mapbox Supercluster for thousands of photos
- ✅ **Timeline Features** - Temporal playback of photo capture sequences
- ✅ **Code Reuse** - Leverage existing Vehicle Tracking infrastructure

### Tradeoffs
- ⚠️ **Complexity** - Requires Rust toolchain and npm build process
- ⚠️ **Distribution** - Must bundle Tauri executable with plugin
- ⚠️ **API Key** - Mapbox requires token (free tier: 50k loads/month)
- ⚠️ **Build Time** - Initial Tauri compilation ~5-10 minutes

### Estimated Implementation Time
- **Phase 1-3 (Basic Scaffold)**: 4-6 hours
- **Phase 4-7 (Core Features)**: 8-12 hours
- **Phase 8-10 (Integration & Polish)**: 6-8 hours
- **Total**: 18-26 hours over 3-5 days

---

## Architecture Overview

### Current State (Leaflet)
```
Python Qt App
    └── QWebEngineView
        └── Leaflet Map (HTML/JS)
            └── Qt WebChannel (bidirectional)
```

**Issues**:
- CSS conflicts with Carolina Blue theme
- DOM performance limits with many markers
- Limited WebGL capabilities

### Target State (Tauri/Mapbox)
```
Python Qt App
    └── WebSocket Server (port 8765+)
        └── JSON Messages
            └── Tauri App (separate process)
                └── Mapbox GL JS (HTML/JS)
                    └── WebGL Rendering
```

**Advantages**:
- Process isolation prevents CSS conflicts
- WebSocket IPC is simple and debuggable
- Mapbox GL uses GPU acceleration
- Same architecture as proven Vehicle Tracking

---

## Data Model Comparison

### Vehicle Tracking Data (Time-Series)
```python
VehicleData {
    vehicle_id: str
    gps_points: List[GPSPoint] {
        latitude, longitude, timestamp,
        speed_kmh, heading, altitude,
        is_interpolated, metadata
    }
    # Continuous path with temporal interpolation
}
```

### Media Analysis Data (Discrete Points)
```python
MediaPhotoData {
    file_path: Path
    gps_data: GPSData {
        latitude, longitude,
        altitude, speed, direction
    }
    temporal_data: TemporalData {
        date_time_original,
        create_date, modify_date
    }
    device_info: DeviceInfo {
        make, model, serial_number
    }
    thumbnail_base64: str  # CRITICAL DIFFERENCE
    thumbnail_type: str    # 'exif' | 'generated'
}
```

### Wire Format for Media Analysis
```json
{
  "photos": [
    {
      "id": "unique_file_id",
      "lat": 51.5074,
      "lon": -0.1278,
      "timestamp_ms": 1234567890000,
      "filename": "IMG_1234.HEIC",
      "device_id": "iPhone_12_Pro_Serial123",
      "device_name": "iPhone 12 Pro",
      "thumbnail": "base64_image_data_or_null",
      "thumbnail_type": "exif",
      "altitude_m": 45.2,
      "speed_kmh": 0,
      "direction_deg": 90,
      "file_path": "/absolute/path/to/file.heic"
    }
  ],
  "meta": {
    "total_photos": 150,
    "devices": ["iPhone_12_Pro_Serial123", "Canon_EOS_R5_456"],
    "time_range": {
      "start_ms": 1234567890000,
      "end_ms": 1234999999000
    },
    "unit_timestamp": "epoch_ms",
    "unit_altitude": "meters",
    "unit_speed": "km/h"
  },
  "settings": {
    "clustering": true,
    "cluster_radius": 50,
    "show_thumbnails": true,
    "group_by_device": true,
    "timeline_enabled": false
  }
}
```

**Key Differences from Vehicle Tracking**:
- ✅ **No interpolation** - Photos are discrete points, not continuous paths
- ✅ **Thumbnails required** - Base64 image data for popups
- ✅ **Device clustering** - Group by camera/phone serial number
- ✅ **Static display** - No timeline animation (optional future feature)
- ✅ **Clustering mandatory** - Hundreds of photos at same location

---

## Phase-by-Phase Implementation

### Phase 1: Tauri App Scaffold (2-3 hours)

**Objective**: Create minimal Tauri app structure in `media_analysis/tauri-map/`

#### Files to Create

**1. `media_analysis/tauri-map/package.json`**
```json
{
  "name": "media-analysis-map",
  "version": "0.1.0",
  "description": "Media Analysis Map Viewer",
  "scripts": {
    "tauri": "tauri",
    "dev": "tauri dev",
    "build": "tauri build",
    "build:win": "npx @tauri-apps/cli build"
  },
  "dependencies": {
    "@tauri-apps/api": "^1.5.6"
  },
  "devDependencies": {
    "@tauri-apps/cli": "^1.5.14"
  }
}
```

**2. `media_analysis/tauri-map/src-tauri/Cargo.toml`**
```toml
[package]
name = "media-analysis-map"
version = "0.1.0"
description = "Media Analysis Map Viewer"
authors = ["CFSA"]
license = ""
repository = ""
edition = "2021"

[build-dependencies]
tauri-build = { version = "1.5", features = [] }

[dependencies]
tauri = { version = "1.5", features = ["shell-open"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"

[features]
default = ["custom-protocol", "devtools"]
custom-protocol = ["tauri/custom-protocol"]
devtools = ["tauri/devtools"]
```

**3. `media_analysis/tauri-map/src-tauri/tauri.conf.json`**
```json
{
  "$schema": "../node_modules/@tauri-apps/cli/schema.json",
  "build": {
    "beforeBuildCommand": "",
    "beforeDevCommand": "",
    "devPath": "http://localhost:8080",
    "distDir": "../src",
    "withGlobalTauri": true
  },
  "package": {
    "productName": "Media Analysis Map",
    "version": "0.1.0"
  },
  "tauri": {
    "allowlist": {
      "all": false,
      "shell": {
        "all": false,
        "open": true
      }
    },
    "bundle": {
      "active": true,
      "targets": "all",
      "identifier": "com.cfsa.mediaanalysis",
      "icon": ["icons/icon.ico"]
    },
    "security": {
      "csp": null
    },
    "windows": [
      {
        "fullscreen": false,
        "resizable": true,
        "title": "Media Analysis Map",
        "width": 1400,
        "height": 900
      }
    ]
  }
}
```

**4. `media_analysis/tauri-map/src-tauri/src/main.rs`**
```rust
// Prevents console window on Windows
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;

#[tauri::command]
fn get_ws_port() -> u16 {
    // Get port from command line or environment
    let port = std::env::args().nth(1)
        .and_then(|arg| {
            if arg.starts_with("--ws-port=") {
                arg.strip_prefix("--ws-port=").unwrap().parse().ok()
            } else {
                arg.parse().ok()
            }
        })
        .or_else(|| {
            std::env::var("TAURI_WS_PORT")
                .ok()
                .and_then(|s| s.parse().ok())
        })
        .unwrap_or(8765);

    println!("WebSocket port: {}", port);
    port
}

#[tauri::command]
fn get_map_config() -> serde_json::Value {
    serde_json::json!({
        "mapboxToken": std::env::var("MAPBOX_TOKEN").ok(),
        "wsPort": get_ws_port()
    })
}

fn main() {
    let ws_port = get_ws_port();

    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![get_ws_port, get_map_config])
        .setup(move |app| {
            if let Some(window) = app.get_window("main") {
                let window_nav = window.clone();
                std::thread::spawn(move || {
                    std::thread::sleep(std::time::Duration::from_millis(100));
                    let script = format!("window.location.href = 'mapbox.html?port={}'", ws_port);
                    window_nav.eval(&script).ok();
                });

                #[cfg(feature = "devtools")]
                {
                    let window_devtools = window.clone();
                    std::thread::spawn(move || {
                        std::thread::sleep(std::time::Duration::from_millis(1500));
                        window_devtools.open_devtools();
                    });
                }
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

**5. `media_analysis/tauri-map/src-tauri/build.rs`**
```rust
fn main() {
    tauri_build::build()
}
```

**6. `media_analysis/tauri-map/src/index.html`**
```html
<!DOCTYPE html>
<html>
<head>
    <title>Media Analysis Map</title>
    <script>
        const params = new URLSearchParams(window.location.search);
        const provider = params.get('provider') || 'mapbox';
        window.location.href = `${provider}.html${window.location.search}`;
    </script>
</head>
<body>Loading map...</body>
</html>
```

**7. `media_analysis/tauri-map/dev_server.py`**
```python
#!/usr/bin/env python3
"""Development server for testing map without building Tauri"""
import http.server
import socketserver
import os
from pathlib import Path

os.chdir(Path(__file__).parent / "src")
PORT = 8080

class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

print(f"Server: http://localhost:{PORT}")
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    httpd.serve_forever()
```

#### Testing Phase 1
```bash
cd media_analysis/tauri-map
npm install
# Should complete without errors
```

**Rollback**: Delete `media_analysis/tauri-map/` directory

---

### Phase 2: Mapbox Integration (3-4 hours)

**Objective**: Add Mapbox GL JS with basic map display and token management

#### Files to Create

**8. `media_analysis/tauri-map/src/mapbox.html`** (Simplified from Vehicle Tracking)

Key sections needed:
1. **Mapbox GL CSS/JS includes**
2. **Token modal** (for API key entry)
3. **Map container** with basic controls
4. **Photo marker layers** (not vehicle trails)
5. **Cluster layer** (essential for photos)
6. **WebSocket connection** code
7. **Photo popup** template with thumbnail support

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Media Analysis - Mapbox</title>
    <link href="https://api.mapbox.com/mapbox-gl-js/v3.0.1/mapbox-gl.css" rel="stylesheet">
    <style>
        /* Map container */
        #map { height: 100%; width: 100%; }

        /* Token modal (copy from vehicle_tracking) */
        .token-modal { /* ... */ }

        /* Photo info panel */
        .photo-panel {
            position: absolute;
            top: 20px;
            right: 20px;
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        /* Cluster styles */
        .cluster-marker {
            background: #3b82f6;
            border-radius: 50%;
            color: white;
            font-weight: bold;
            text-align: center;
            display: flex;
            align-items: center;
            justify-content: center;
        }
    </style>
</head>
<body>
    <!-- Token Modal (copy from vehicle_tracking/tauri-map/src/mapbox.html) -->
    <div id="tokenModal" class="token-modal">
        <!-- Modal content -->
    </div>

    <!-- Map Container -->
    <div id="map"></div>

    <!-- Photo Info Panel -->
    <div id="photo-panel" class="photo-panel">
        <h3>📸 Photos</h3>
        <div class="stat-grid">
            <div class="stat">
                <div class="stat-label">Total</div>
                <div class="stat-value" id="photo-count">0</div>
            </div>
            <div class="stat">
                <div class="stat-label">Devices</div>
                <div class="stat-value" id="device-count">0</div>
            </div>
        </div>
        <div id="device-list"></div>
    </div>

    <script src="https://api.mapbox.com/mapbox-gl-js/v3.0.1/mapbox-gl.js"></script>
    <script>
        // Configuration (similar to vehicle tracking)
        const CONFIG = {
            mapboxToken: null,
            defaultCenter: [-96, 37.8],
            defaultZoom: 4,
            clusterRadius: 50,
            clusterMaxZoom: 14
        };

        // Token modal manager (copy from vehicle tracking)
        const tokenModalManager = { /* ... */ };

        // Media Analysis Map Class
        class MediaAnalysisMap {
            constructor() {
                this.state = {
                    isInitialized: false,
                    hasData: false
                };
                this.photos = new Map();
                this.devices = new Map();
                this.map = null;

                this.initialize();
            }

            async initialize() {
                await this.waitForConfig();
                this.initializeMap();
            }

            async waitForConfig() {
                // Same logic as vehicle tracking for token retrieval
            }

            initializeMap() {
                mapboxgl.accessToken = CONFIG.mapboxToken;

                this.map = new mapboxgl.Map({
                    container: 'map',
                    style: 'mapbox://styles/mapbox/satellite-streets-v12',
                    center: CONFIG.defaultCenter,
                    zoom: CONFIG.defaultZoom
                });

                this.map.on('load', () => {
                    this.setupMapLayers();
                    this.dispatchReadyEvent();
                });
            }

            setupMapLayers() {
                // Add source for photos
                this.map.addSource('photos', {
                    type: 'geojson',
                    data: {
                        type: 'FeatureCollection',
                        features: []
                    },
                    cluster: true,
                    clusterRadius: CONFIG.clusterRadius,
                    clusterMaxZoom: CONFIG.clusterMaxZoom
                });

                // Cluster circles
                this.map.addLayer({
                    id: 'clusters',
                    type: 'circle',
                    source: 'photos',
                    filter: ['has', 'point_count'],
                    paint: {
                        'circle-color': [
                            'step',
                            ['get', 'point_count'],
                            '#51bbd6', 10,
                            '#f1f075', 50,
                            '#f28cb1'
                        ],
                        'circle-radius': [
                            'step',
                            ['get', 'point_count'],
                            20, 10,
                            30, 50,
                            40
                        ]
                    }
                });

                // Cluster count labels
                this.map.addLayer({
                    id: 'cluster-count',
                    type: 'symbol',
                    source: 'photos',
                    filter: ['has', 'point_count'],
                    layout: {
                        'text-field': '{point_count_abbreviated}',
                        'text-font': ['DIN Offc Pro Medium', 'Arial Unicode MS Bold'],
                        'text-size': 12
                    }
                });

                // Individual photo markers
                this.map.addLayer({
                    id: 'photo-points',
                    type: 'circle',
                    source: 'photos',
                    filter: ['!', ['has', 'point_count']],
                    paint: {
                        'circle-color': '#11b4da',
                        'circle-radius': 8,
                        'circle-stroke-width': 2,
                        'circle-stroke-color': '#fff'
                    }
                });

                // Click handlers
                this.setupInteractions();
            }

            setupInteractions() {
                // Cluster click - zoom in
                this.map.on('click', 'clusters', (e) => {
                    const features = this.map.queryRenderedFeatures(e.point, {
                        layers: ['clusters']
                    });
                    const clusterId = features[0].properties.cluster_id;
                    this.map.getSource('photos').getClusterExpansionZoom(
                        clusterId,
                        (err, zoom) => {
                            if (err) return;
                            this.map.easeTo({
                                center: features[0].geometry.coordinates,
                                zoom: zoom
                            });
                        }
                    );
                });

                // Photo click - show popup with thumbnail
                this.map.on('click', 'photo-points', (e) => {
                    const photo = e.features[0].properties;
                    this.showPhotoPopup(photo, e.lngLat);
                });

                // Cursor changes
                this.map.on('mouseenter', 'clusters', () => {
                    this.map.getCanvas().style.cursor = 'pointer';
                });
                this.map.on('mouseleave', 'clusters', () => {
                    this.map.getCanvas().style.cursor = '';
                });
            }

            showPhotoPopup(photo, lngLat) {
                // Parse photo data (stringified by GeoJSON)
                const data = typeof photo === 'string' ? JSON.parse(photo) : photo;

                let html = `
                    <div class="photo-popup">
                        <h4>${data.filename}</h4>
                `;

                // Add thumbnail if available
                if (data.thumbnail && data.thumbnail !== 'null') {
                    html += `
                        <img src="data:image/jpeg;base64,${data.thumbnail}"
                             style="max-width: 200px; max-height: 200px; border-radius: 4px;"
                             alt="Photo thumbnail">
                    `;
                }

                html += `
                        <div class="photo-info">
                            <p><strong>Device:</strong> ${data.device_name || 'Unknown'}</p>
                            <p><strong>Time:</strong> ${data.time_display || 'N/A'}</p>
                            ${data.altitude_m ? `<p><strong>Altitude:</strong> ${data.altitude_m}m</p>` : ''}
                        </div>
                    </div>
                `;

                new mapboxgl.Popup()
                    .setLngLat(lngLat)
                    .setHTML(html)
                    .addTo(this.map);

                // Notify Python
                if (window.pythonBridge) {
                    window.pythonBridge.send({
                        type: 'photo_clicked',
                        file_path: data.file_path
                    });
                }
            }

            loadPhotos(photoData) {
                console.log('[MediaAnalysisMap] Loading photos:', photoData);

                // Validate
                if (!photoData.photos || !Array.isArray(photoData.photos)) {
                    console.error('Invalid photo data format');
                    return;
                }

                // Convert to GeoJSON features
                const features = photoData.photos.map(photo => ({
                    type: 'Feature',
                    geometry: {
                        type: 'Point',
                        coordinates: [photo.lon, photo.lat]
                    },
                    properties: {
                        id: photo.id,
                        filename: photo.filename,
                        device_name: photo.device_name,
                        device_id: photo.device_id,
                        time_display: photo.time_display,
                        altitude_m: photo.altitude_m,
                        thumbnail: photo.thumbnail,
                        thumbnail_type: photo.thumbnail_type,
                        file_path: photo.file_path
                    }
                }));

                // Update source
                this.map.getSource('photos').setData({
                    type: 'FeatureCollection',
                    features: features
                });

                // Update stats
                this.updateStats(photoData);

                // Fit bounds
                if (features.length > 0) {
                    const bounds = new mapboxgl.LngLatBounds();
                    features.forEach(f => bounds.extend(f.geometry.coordinates));
                    this.map.fitBounds(bounds, { padding: 50 });
                }

                this.state.hasData = true;
            }

            updateStats(photoData) {
                document.getElementById('photo-count').textContent = photoData.photos.length;
                document.getElementById('device-count').textContent =
                    new Set(photoData.photos.map(p => p.device_id)).size;
            }

            dispatchReadyEvent() {
                if (window.pythonBridge) {
                    window.pythonBridge.send({ type: 'ready' });
                }
            }
        }

        // Python WebSocket Bridge (copy from vehicle tracking)
        class PythonBridge {
            constructor() {
                const urlParams = new URLSearchParams(window.location.search);
                this.port = parseInt(urlParams.get('port') || '8765', 10);
                this.connect();
            }

            connect() {
                console.log(`[PythonBridge] Connecting to ws://localhost:${this.port}/`);
                this.ws = new WebSocket(`ws://localhost:${this.port}/`);

                this.ws.onopen = () => {
                    console.log('[PythonBridge] Connected');
                    this.send({ type: 'ready' });
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
                    case 'load_photos':
                        if (window.mediaMap) {
                            window.mediaMap.loadPhotos(msg.data);
                        }
                        break;
                    case 'clear_photos':
                        if (window.mediaMap) {
                            window.mediaMap.clearPhotos();
                        }
                        break;
                }
            }

            send(data) {
                if (this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify(data));
                }
            }
        }

        // Initialize
        window.mediaMap = new MediaAnalysisMap();
        setTimeout(() => {
            window.pythonBridge = new PythonBridge();
        }, 1000);
    </script>
</body>
</html>
```

#### Testing Phase 2
```bash
# 1. Get Mapbox token from https://account.mapbox.com/
# 2. Test with dev server:
python dev_server.py
# Open browser to http://localhost:8080/mapbox.html?port=8765
# Should show token modal, then map after entering token
```

**Rollback**: Revert `src/mapbox.html` to empty file

---

### Phase 3: Python Bridge Service (2-3 hours)

**Objective**: Create WebSocket service in Python to communicate with Tauri

#### Files to Create

**9. `media_analysis/services/tauri_bridge_service.py`**

Copy from `vehicle_tracking/services/tauri_bridge_service.py` with modifications:

```python
#!/usr/bin/env python3
"""
Tauri Bridge Service for Media Analysis
WebSocket-based communication with Tauri map application
"""

import json
import subprocess
import threading
import socket
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from websocket_server import WebsocketServer

from core.services.base_service import BaseService
from core.result_types import Result
from core.logger import logger


class MediaAnalysisTauriBridgeService(BaseService):
    """Bridge service for Media Analysis Tauri map"""

    def __init__(self):
        super().__init__("MediaAnalysisTauriBridgeService")

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
            self.ws_port = self.find_free_port()
            logger.info(f"Media Analysis WebSocket port: {self.ws_port}")

            self._start_websocket_server()
            self._launch_tauri()

            self.is_running = True
            return Result.success(self.ws_port)

        except Exception as e:
            logger.error(f"Failed to start Media Analysis bridge: {e}")
            return Result.error(str(e))

    def _start_websocket_server(self):
        """Start WebSocket server in a thread"""
        self.ws_server = WebsocketServer(port=self.ws_port, host='localhost')

        self.ws_server.set_fn_new_client(self._on_client_connected)
        self.ws_server.set_fn_client_left(self._on_client_disconnected)
        self.ws_server.set_fn_message_received(self._on_message_received)

        self.ws_thread = threading.Thread(target=self.ws_server.serve_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()

        logger.info(f"Media Analysis WebSocket server started on port {self.ws_port}")

    def _launch_tauri(self):
        """Launch Tauri application"""
        try:
            if sys.platform == "win32":
                exe_name = "Media Analysis Map.exe"
            else:
                exe_name = "Media Analysis Map"

            exe_path = self.tauri_path / "src-tauri" / "target" / "release" / exe_name

            if not exe_path.exists():
                logger.error(f"Tauri executable not found: {exe_path}")
                logger.error("Run 'npm run build' in media_analysis/tauri-map/")
                raise FileNotFoundError(f"Tauri executable not found: {exe_path}")

            cmd = [str(exe_path), f"--ws-port={self.ws_port}"]
            env = os.environ.copy()
            env['TAURI_WS_PORT'] = str(self.ws_port)

            self.tauri_process = subprocess.Popen(
                cmd,
                cwd=self.tauri_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            logger.info("Media Analysis Tauri application launched")

        except Exception as e:
            logger.error(f"Failed to launch Tauri: {e}")
            raise

    def _on_client_connected(self, client, server):
        """Handle new WebSocket client"""
        logger.info(f"Media Analysis Tauri client connected: {client['id']}")
        self.connected_clients.append(client)

        # Send pending messages
        for msg in self.pending_messages:
            server.send_message(client, json.dumps(msg))
        self.pending_messages.clear()

    def _on_client_disconnected(self, client, server):
        """Handle client disconnect"""
        logger.info(f"Media Analysis Tauri client disconnected: {client['id']}")
        if client in self.connected_clients:
            self.connected_clients.remove(client)

    def _on_message_received(self, client, server, message):
        """Handle message from Tauri"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')

            if msg_type == 'ready':
                logger.info("Media Analysis map ready")
            elif msg_type == 'photo_clicked':
                logger.info(f"Photo clicked: {data.get('file_path')}")
                # Could emit signal here for parent to handle
            elif msg_type == 'error':
                logger.error(f"Tauri error: {data.get('message')}")

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def send_photo_data(self, photo_data: Dict[str, Any]) -> Result[None]:
        """
        Send photo location data to Tauri

        Args:
            photo_data: Dictionary with 'photos' list and 'meta' dict
        """
        try:
            message = {
                "type": "load_photos",
                "data": photo_data
            }

            if self.connected_clients and self.ws_server:
                self.ws_server.send_message_to_all(json.dumps(message))
                logger.info(f"Sent photo data: {len(photo_data.get('photos', []))} photos")
            else:
                self.pending_messages.append(message)
                logger.info("Queued photo data for when client connects")

            return Result.success(None)

        except Exception as e:
            logger.error(f"Failed to send photo data: {e}")
            return Result.error(str(e))

    def clear_photos(self) -> Result[None]:
        """Clear all photos from map"""
        try:
            message = {"type": "clear_photos"}

            if self.connected_clients and self.ws_server:
                self.ws_server.send_message_to_all(json.dumps(message))

            return Result.success(None)

        except Exception as e:
            logger.error(f"Failed to clear photos: {e}")
            return Result.error(str(e))

    def shutdown(self):
        """Clean shutdown"""
        logger.info("Shutting down Media Analysis Tauri bridge...")

        if self.ws_server:
            try:
                self.ws_server.shutdown()
            except:
                pass

        if self.tauri_process:
            self.tauri_process.terminate()
            try:
                self.tauri_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.tauri_process.kill()

        self.is_running = False
        logger.info("Media Analysis Tauri bridge shutdown complete")
```

#### Testing Phase 3
```python
# Test script: test_bridge.py
from media_analysis.services.tauri_bridge_service import MediaAnalysisTauriBridgeService
import time

bridge = MediaAnalysisTauriBridgeService()
result = bridge.start()

if result.is_success:
    print(f"Bridge started on port {result.data}")
    time.sleep(60)  # Keep alive for testing
    bridge.shutdown()
```

**Rollback**: Delete `media_analysis/services/tauri_bridge_service.py`

---

### Phase 4: Data Models & Wire Format (2-3 hours)

**Objective**: Define data structures for photo locations

#### Files to Create

**10. `media_analysis/services/wire_format.py`**

```python
"""
Wire format converter for Media Analysis GPS data
Ensures consistent data transmission between Python and Tauri
"""

from typing import Dict, List, Any
from pathlib import Path
import logging

from media_analysis.exiftool.exiftool_models import ExifToolMetadata


def to_wire_format(metadata_list: List[ExifToolMetadata]) -> Dict[str, Any]:
    """
    Convert ExifToolMetadata list to wire format for Tauri

    Args:
        metadata_list: List of media metadata objects

    Returns:
        Dictionary ready for JSON serialization
    """
    photos = []
    devices = set()
    timestamps = []

    for metadata in metadata_list:
        if not metadata.has_gps or not metadata.gps_data:
            continue

        lat, lon = metadata.gps_data.to_decimal_degrees()

        # Get device ID
        device_id = None
        device_name = "Unknown"
        if metadata.device_info:
            device_id = metadata.device_info.get_primary_id()
            device_name = metadata.device_info.get_display_name()
            if device_id:
                devices.add(device_id)

        # Get timestamp
        timestamp_ms = None
        time_display = None
        if metadata.temporal_data:
            timestamp = metadata.temporal_data.get_primary_timestamp()
            if timestamp:
                timestamp_ms = int(timestamp.timestamp() * 1000)
                time_display = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                timestamps.append(timestamp_ms)

        photo = {
            "id": str(metadata.file_path),  # Unique ID
            "lat": lat,
            "lon": lon,
            "filename": metadata.file_path.name,
            "file_path": str(metadata.file_path.absolute()),
            "device_id": device_id,
            "device_name": device_name,
            "timestamp_ms": timestamp_ms,
            "time_display": time_display,
            "altitude_m": metadata.gps_data.altitude,
            "speed_kmh": metadata.gps_data.speed,
            "direction_deg": metadata.gps_data.direction,
            "thumbnail": metadata.thumbnail_base64,
            "thumbnail_type": metadata.thumbnail_type
        }

        photos.append(photo)

    # Build metadata
    meta = {
        "total_photos": len(photos),
        "devices": list(devices),
        "unit_timestamp": "epoch_ms",
        "unit_altitude": "meters",
        "unit_speed": "km/h",
        "unit_direction": "degrees"
    }

    # Add time range if we have timestamps
    if timestamps:
        meta["time_range"] = {
            "start_ms": min(timestamps),
            "end_ms": max(timestamps)
        }

    return {
        "photos": photos,
        "meta": meta,
        "settings": {
            "clustering": True,
            "cluster_radius": 50,
            "show_thumbnails": True,
            "group_by_device": True
        }
    }


def validate_wire_format(payload: Dict[str, Any]) -> List[str]:
    """
    Validate wire format for consistency

    Args:
        payload: Wire format dictionary

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if "photos" not in payload:
        errors.append("Missing required field: photos")
    if "meta" not in payload:
        errors.append("Missing required field: meta")

    if not errors:
        photos = payload["photos"]
        if not isinstance(photos, list):
            errors.append("Photos must be a list")
        else:
            for i, photo in enumerate(photos):
                if "lat" not in photo:
                    errors.append(f"Photo {i}: missing lat")
                if "lon" not in photo:
                    errors.append(f"Photo {i}: missing lon")
                if "file_path" not in photo:
                    errors.append(f"Photo {i}: missing file_path")

                # Validate coordinates
                if "lat" in photo:
                    lat = photo["lat"]
                    if not (-90 <= lat <= 90):
                        errors.append(f"Photo {i}: invalid latitude {lat}")

                if "lon" in photo:
                    lon = photo["lon"]
                    if not (-180 <= lon <= 180):
                        errors.append(f"Photo {i}: invalid longitude {lon}")

    return errors
```

#### Testing Phase 4
```python
# Test wire format conversion
from media_analysis.services.wire_format import to_wire_format
from media_analysis.exiftool.exiftool_models import ExifToolMetadata, GPSData

# Create test metadata
metadata = ExifToolMetadata(file_path=Path("test.jpg"))
metadata.gps_data = GPSData(
    latitude=51.5074,
    longitude=-0.1278,
    latitude_ref='N',
    longitude_ref='W'
)

wire_data = to_wire_format([metadata])
print(json.dumps(wire_data, indent=2))
```

**Rollback**: Delete `media_analysis/services/wire_format.py`

---

### Phase 5: Photo Markers & Thumbnails (3-4 hours)

**Objective**: Implement photo marker rendering with thumbnail popups

**Key Implementation Points**:

1. **Thumbnail Handling** - Base64 data must be properly formatted
2. **Clustering** - Use Mapbox Supercluster for performance
3. **Device Grouping** - Color-code markers by device
4. **Popup Templates** - Show thumbnail + metadata

**Modifications to `mapbox.html`** (already included in Phase 2):
- ✅ Cluster layer configuration
- ✅ Thumbnail popup rendering
- ✅ Device color mapping

**Additional CSS for Popups**:
```css
.photo-popup {
    font-family: -apple-system, sans-serif;
    max-width: 250px;
}

.photo-popup h4 {
    margin: 0 0 10px 0;
    font-size: 14px;
    font-weight: 600;
}

.photo-popup img {
    display: block;
    margin: 10px 0;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.photo-info p {
    margin: 5px 0;
    font-size: 12px;
    color: #666;
}
```

#### Testing Phase 5
1. Load photos with thumbnails
2. Verify clustering works
3. Click cluster - should zoom in
4. Click individual photo - should show popup with thumbnail
5. Test with HEIC-generated thumbnails

**Rollback**: Revert `mapbox.html` to Phase 2 version

---

### Phase 6: Clustering & Performance (2-3 hours)

**Objective**: Optimize for hundreds/thousands of photos

**Clustering Configuration** (in `setupMapLayers()`):
```javascript
this.map.addSource('photos', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
    cluster: true,
    clusterRadius: 50,        // Pixels
    clusterMaxZoom: 14,       // Max zoom to cluster
    clusterProperties: {
        // Count by device
        'device_count': ['+', ['case', ['has', 'device_id'], 1, 0]]
    }
});
```

**Performance Optimizations**:
1. **Lazy Loading** - Only send visible photos to map
2. **Thumbnail Optimization** - Limit base64 size (200x200 max)
3. **Layer Simplification** - Remove unnecessary map layers
4. **Bounds-based Loading** - Only load photos in viewport

**Performance Monitoring**:
```javascript
this.performanceMetrics = {
    photoCount: 0,
    renderTime: 0,
    clusterCount: 0
};
```

#### Testing Phase 6
- Load 1000+ photos
- Verify smooth panning/zooming
- Measure FPS (should be 60fps)
- Test cluster expansion

**Rollback**: Revert clustering config to default

---

### Phase 7: Interactive Features (2-3 hours)

**Objective**: Add device filtering, search, and export

**Device Filter Panel**:
```javascript
updateDeviceList(devices) {
    const container = document.getElementById('device-list');
    container.innerHTML = '';

    devices.forEach(deviceId => {
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = true;
        checkbox.dataset.deviceId = deviceId;
        checkbox.addEventListener('change', () => this.filterByDevice());

        const label = document.createElement('label');
        label.textContent = deviceId;

        container.appendChild(checkbox);
        container.appendChild(label);
    });
}

filterByDevice() {
    const selectedDevices = Array.from(
        document.querySelectorAll('#device-list input:checked')
    ).map(cb => cb.dataset.deviceId);

    // Filter photos
    this.map.setFilter('photo-points', [
        'in',
        ['get', 'device_id'],
        ['literal', selectedDevices]
    ]);
    this.map.setFilter('clusters', [
        'in',
        ['get', 'device_id'],
        ['literal', selectedDevices]
    ]);
}
```

**Export Features**:
- HTML export (standalone map)
- GeoJSON export (for GIS tools)
- KML export (for Google Earth)

#### Testing Phase 7
- Filter by device
- Export HTML and verify standalone
- Export KML and open in Google Earth

**Rollback**: Remove filter panel HTML

---

### Phase 8: UI Integration (3-4 hours)

**Objective**: Replace GeoVisualizationWidget with Tauri-based version

**11. `media_analysis/ui/components/geo/geo_visualization_widget_tauri.py`**

```python
#!/usr/bin/env python3
"""
Tauri-based Geo Visualization Widget
Replaces QWebEngineView with external Tauri process
"""

from pathlib import Path
from typing import List, Dict, Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton,
    QLabel, QToolBar, QMessageBox
)

from media_analysis.exiftool.exiftool_models import ExifToolMetadata
from media_analysis.services.tauri_bridge_service import MediaAnalysisTauriBridgeService
from media_analysis.services.wire_format import to_wire_format, validate_wire_format
from core.logger import logger


class GeoVisualizationWidgetTauri(QWidget):
    """
    Tauri-based map visualization for GPS data
    Uses external Tauri process instead of QWebEngineView
    """

    file_selected = Signal(str)
    export_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Bridge service
        self.bridge_service = MediaAnalysisTauriBridgeService()

        # State
        self.current_metadata: List[ExifToolMetadata] = []
        self._map_ready = False

        self._create_ui()
        self._start_bridge()

    def _create_ui(self):
        """Create widget UI"""
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # Status/Info area
        self.info_label = QLabel("🗺️ Map window will open in separate window")
        self.info_label.setStyleSheet("""
            QLabel {
                background: #e3f2fd;
                padding: 12px;
                border-radius: 4px;
                color: #1565c0;
            }
        """)
        layout.addWidget(self.info_label)

        # Stats panel
        self.stats_label = QLabel("No photos loaded")
        layout.addWidget(self.stats_label)

        # Controls
        controls_layout = QVBoxLayout()

        self.refresh_btn = QPushButton("🔄 Refresh Map")
        self.refresh_btn.clicked.connect(self._refresh_map)
        controls_layout.addWidget(self.refresh_btn)

        self.clear_btn = QPushButton("🗑️ Clear Map")
        self.clear_btn.clicked.connect(self.clear_map)
        controls_layout.addWidget(self.clear_btn)

        layout.addLayout(controls_layout)
        layout.addStretch()

    def _create_toolbar(self) -> QToolBar:
        """Create toolbar"""
        toolbar = QToolBar()
        toolbar.addAction("💾 Export HTML", lambda: self._export('html'))
        toolbar.addAction("🌍 Export KML", lambda: self._export('kml'))
        toolbar.addAction("📊 Statistics", self._show_statistics)
        return toolbar

    def _start_bridge(self):
        """Start Tauri bridge service"""
        result = self.bridge_service.start()

        if result.is_success:
            port = result.data
            self.info_label.setText(
                f"✅ Map service running (WebSocket port {port})\n"
                "A map window should have opened. If not, check if the Tauri app is built."
            )
            logger.info(f"Tauri bridge started on port {port}")
        else:
            self.info_label.setText(
                f"❌ Failed to start map service: {result.error}\n"
                "Make sure to build the Tauri app first: cd media_analysis/tauri-map && npm run build"
            )
            logger.error(f"Failed to start bridge: {result.error}")

    def add_media_locations(self, metadata_list: List[ExifToolMetadata]):
        """
        Add media locations to map

        Args:
            metadata_list: List of ExifToolMetadata with GPS data
        """
        self.current_metadata = metadata_list

        # Convert to wire format
        wire_data = to_wire_format(metadata_list)

        # Validate
        errors = validate_wire_format(wire_data)
        if errors:
            logger.warning(f"Wire format validation warnings: {errors}")

        # Send to Tauri
        result = self.bridge_service.send_photo_data(wire_data)

        if result.is_success:
            photo_count = len(wire_data['photos'])
            device_count = len(wire_data['meta']['devices'])
            self.stats_label.setText(
                f"📸 {photo_count} photos from {device_count} devices"
            )
            logger.info(f"Sent {photo_count} photos to map")
        else:
            logger.error(f"Failed to send photo data: {result.error}")

    def _refresh_map(self):
        """Refresh map with current data"""
        if self.current_metadata:
            self.add_media_locations(self.current_metadata)

    def clear_map(self):
        """Clear all markers from map"""
        self.current_metadata.clear()
        self.bridge_service.clear_photos()
        self.stats_label.setText("No photos loaded")

    def _show_statistics(self):
        """Show GPS statistics"""
        if not self.current_metadata:
            QMessageBox.information(self, "Statistics", "No data loaded")
            return

        gps_count = sum(1 for m in self.current_metadata if m.has_gps)
        devices = set(
            m.device_info.get_primary_id()
            for m in self.current_metadata
            if m.device_info and m.device_info.get_primary_id()
        )

        stats = f"""GPS Statistics:

Files with GPS: {gps_count}
Unique devices: {len(devices)}
Total files: {len(self.current_metadata)}

Devices:
{chr(10).join('  - ' + d for d in sorted(devices))}
        """

        QMessageBox.information(self, "GPS Statistics", stats)

    def _export(self, format_type: str):
        """Export map data"""
        self.export_requested.emit(format_type, '')

    def export_html(self, output_path: Path) -> bool:
        """
        Export standalone HTML map

        Args:
            output_path: Path to save HTML

        Returns:
            True if successful
        """
        try:
            wire_data = to_wire_format(self.current_metadata)

            # Read template from Tauri src
            template_path = (
                Path(__file__).parent.parent.parent /
                "tauri-map" / "src" / "mapbox.html"
            )

            if not template_path.exists():
                logger.error(f"Template not found: {template_path}")
                return False

            html_content = template_path.read_text(encoding='utf-8')

            # Inject data
            html_content = html_content.replace(
                'const PHOTOS_DATA = undefined;',
                f'const PHOTOS_DATA = {json.dumps(wire_data)};'
            )

            # Write output
            output_path.write_text(html_content, encoding='utf-8')

            logger.info(f"Exported HTML map: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export HTML: {e}")
            return False

    def closeEvent(self, event):
        """Handle widget close"""
        self.bridge_service.shutdown()
        super().closeEvent(event)
```

**12. Update `media_analysis/ui/media_analysis_tab.py`**

Replace import:
```python
# OLD:
# from .components.geo.geo_visualization_widget import GeoVisualizationWidget

# NEW:
from .components.geo.geo_visualization_widget_tauri import GeoVisualizationWidgetTauri as GeoVisualizationWidget
```

#### Testing Phase 8
1. Open Media Analysis tab
2. Load photos with GPS
3. Verify Tauri window opens
4. Verify photos appear on map
5. Test all toolbar functions

**Rollback**: Revert import to use original `GeoVisualizationWidget`

---

### Phase 9: Build & Distribution (2-3 hours)

**Objective**: Package Tauri executable for distribution

**13. `media_analysis/tauri-map/build.py`** (Build automation)

```python
#!/usr/bin/env python3
"""
Build script for Media Analysis Tauri map
Automates the build process and validates output
"""

import subprocess
import sys
from pathlib import Path
import shutil

def main():
    # Change to tauri-map directory
    tauri_dir = Path(__file__).parent
    print(f"Building Tauri app in: {tauri_dir}")

    # Check npm is installed
    try:
        subprocess.run(['npm', '--version'], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: npm not found. Install Node.js first.")
        sys.exit(1)

    # Check Rust is installed
    try:
        subprocess.run(['cargo', '--version'], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: cargo not found. Install Rust first.")
        sys.exit(1)

    # Install dependencies
    print("\n1. Installing npm dependencies...")
    result = subprocess.run(['npm', 'install'], cwd=tauri_dir)
    if result.returncode != 0:
        print("ERROR: npm install failed")
        sys.exit(1)

    # Build Tauri
    print("\n2. Building Tauri application...")
    result = subprocess.run(['npm', 'run', 'build'], cwd=tauri_dir)
    if result.returncode != 0:
        print("ERROR: Tauri build failed")
        sys.exit(1)

    # Verify output
    if sys.platform == "win32":
        exe_name = "Media Analysis Map.exe"
    else:
        exe_name = "Media Analysis Map"

    exe_path = tauri_dir / "src-tauri" / "target" / "release" / exe_name

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n✅ Build successful!")
        print(f"   Executable: {exe_path}")
        print(f"   Size: {size_mb:.1f} MB")
    else:
        print(f"\n❌ Build failed - executable not found: {exe_path}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

**Usage**:
```bash
cd media_analysis/tauri-map
python build.py
```

**Distribution Checklist**:
- [ ] Build on Windows
- [ ] Test executable runs standalone
- [ ] Verify WebSocket communication works
- [ ] Package in `bin/` directory for distribution
- [ ] Add to `.gitignore`: `media_analysis/tauri-map/src-tauri/target/`

**14. `.gitignore` additions**:
```gitignore
# Tauri build artifacts
media_analysis/tauri-map/src-tauri/target/
media_analysis/tauri-map/node_modules/

# Tauri executable in bin
bin/Media Analysis Map.exe
bin/media-analysis-map
```

#### Testing Phase 9
1. Build on clean machine
2. Copy executable to different location
3. Run and verify map loads
4. Test WebSocket connection

**Rollback**: Delete build artifacts

---

### Phase 10: Testing & Polish (3-4 hours)

**Objective**: Comprehensive testing and bug fixes

#### Test Suite

**15. `media_analysis/tests/test_tauri_map_integration.py`**

```python
#!/usr/bin/env python3
"""
Integration tests for Tauri map system
"""

import pytest
import time
from pathlib import Path
from media_analysis.services.tauri_bridge_service import MediaAnalysisTauriBridgeService
from media_analysis.services.wire_format import to_wire_format, validate_wire_format
from media_analysis.exiftool.exiftool_models import ExifToolMetadata, GPSData


class TestTauriIntegration:
    """Test Tauri map integration"""

    def test_bridge_start_stop(self):
        """Test bridge service lifecycle"""
        bridge = MediaAnalysisTauriBridgeService()

        # Start
        result = bridge.start()
        assert result.is_success
        assert bridge.is_running
        assert bridge.ws_port is not None

        # Allow time for Tauri to launch
        time.sleep(2)

        # Shutdown
        bridge.shutdown()
        assert not bridge.is_running

    def test_wire_format_conversion(self):
        """Test metadata to wire format conversion"""
        # Create test metadata
        metadata = ExifToolMetadata(file_path=Path("test.jpg"))
        metadata.gps_data = GPSData(
            latitude=51.5074,
            longitude=-0.1278,
            latitude_ref='N',
            longitude_ref='W',
            altitude=45.2
        )

        # Convert
        wire_data = to_wire_format([metadata])

        # Validate structure
        assert 'photos' in wire_data
        assert 'meta' in wire_data
        assert len(wire_data['photos']) == 1

        photo = wire_data['photos'][0]
        assert photo['lat'] == 51.5074
        assert photo['lon'] == -0.1278
        assert photo['altitude_m'] == 45.2

    def test_wire_format_validation(self):
        """Test wire format validation"""
        # Valid data
        valid_data = {
            "photos": [
                {"lat": 51.5, "lon": -0.1, "file_path": "/test.jpg"}
            ],
            "meta": {"total_photos": 1}
        }
        errors = validate_wire_format(valid_data)
        assert len(errors) == 0

        # Invalid data - missing fields
        invalid_data = {"photos": [{"lat": 51.5}]}
        errors = validate_wire_format(invalid_data)
        assert len(errors) > 0

        # Invalid coordinates
        invalid_coords = {
            "photos": [{"lat": 91.0, "lon": -0.1, "file_path": "/test.jpg"}],
            "meta": {}
        }
        errors = validate_wire_format(invalid_coords)
        assert any("invalid latitude" in e for e in errors)

    def test_send_photo_data(self):
        """Test sending photo data through bridge"""
        bridge = MediaAnalysisTauriBridgeService()
        result = bridge.start()
        assert result.is_success

        # Create test data
        photo_data = {
            "photos": [
                {
                    "id": "test1",
                    "lat": 51.5074,
                    "lon": -0.1278,
                    "filename": "test.jpg",
                    "file_path": "/path/to/test.jpg",
                    "device_id": "iPhone_12_Pro",
                    "device_name": "iPhone 12 Pro"
                }
            ],
            "meta": {
                "total_photos": 1,
                "devices": ["iPhone_12_Pro"]
            },
            "settings": {
                "clustering": True
            }
        }

        # Send data
        result = bridge.send_photo_data(photo_data)
        assert result.is_success

        # Cleanup
        bridge.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

#### Manual Test Checklist

- [ ] **Basic Functionality**
  - [ ] Map opens in Tauri window
  - [ ] Photos appear on map
  - [ ] Clustering works
  - [ ] Popups show thumbnails
  - [ ] Device filtering works

- [ ] **Performance**
  - [ ] Load 100 photos - smooth
  - [ ] Load 500 photos - acceptable
  - [ ] Load 1000+ photos - should still work with clustering
  - [ ] Map panning/zooming is 60fps

- [ ] **Edge Cases**
  - [ ] No GPS data - graceful message
  - [ ] Missing thumbnails - placeholder shown
  - [ ] Invalid coordinates - filtered out
  - [ ] Tauri not built - clear error message

- [ ] **Integration**
  - [ ] Works with HEIC photos
  - [ ] Works with JPEG photos
  - [ ] Device grouping correct
  - [ ] Export functions work

- [ ] **Shutdown**
  - [ ] Closing tab closes Tauri
  - [ ] No orphaned processes
  - [ ] Clean restart works

#### Polish Items

**Error Messages**:
- Improve error when Tauri not built
- Better WebSocket connection feedback
- Loading indicators

**UI Enhancements**:
- Progress bar for photo loading
- Device legend with colors
- Search/filter controls
- Timeline scrubber (optional)

**Documentation**:
- Add README.md to `tauri-map/`
- User guide for API key setup
- Troubleshooting guide

**Rollback**: Full rollback to Leaflet implementation

---

## Technical Specifications

### File Structure
```
media_analysis/
├── tauri-map/                      # Tauri application
│   ├── src/
│   │   ├── index.html             # Router
│   │   └── mapbox.html            # Main map interface
│   ├── src-tauri/
│   │   ├── src/
│   │   │   └── main.rs            # Rust backend
│   │   ├── Cargo.toml             # Rust dependencies
│   │   ├── tauri.conf.json        # Tauri config
│   │   └── build.rs               # Build script
│   ├── package.json               # npm config
│   ├── dev_server.py              # Development server
│   └── build.py                   # Build automation
├── services/
│   ├── tauri_bridge_service.py    # WebSocket bridge
│   └── wire_format.py             # Data conversion
├── ui/
│   └── components/
│       └── geo/
│           └── geo_visualization_widget_tauri.py
└── tests/
    └── test_tauri_map_integration.py
```

### API Contracts

#### Python → JavaScript (WebSocket Messages)

**Load Photos**:
```json
{
  "type": "load_photos",
  "data": {
    "photos": [...],
    "meta": {...},
    "settings": {...}
  }
}
```

**Clear Photos**:
```json
{
  "type": "clear_photos"
}
```

#### JavaScript → Python (WebSocket Messages)

**Map Ready**:
```json
{
  "type": "ready"
}
```

**Photo Clicked**:
```json
{
  "type": "photo_clicked",
  "file_path": "/absolute/path/to/photo.jpg"
}
```

**Error**:
```json
{
  "type": "error",
  "message": "Error description"
}
```

### Configuration

**Environment Variables**:
```bash
# Mapbox API token (get from https://account.mapbox.com/)
MAPBOX_TOKEN=pk.eyJ1...

# WebSocket port (auto-assigned if not set)
TAURI_WS_PORT=8765
```

**Settings** (in `core/settings_manager.py`):
```python
{
    'map_provider': 'mapbox',          # or 'leaflet' for fallback
    'map_clustering': True,             # Enable marker clustering
    'cluster_radius': 50,               # Clustering radius in pixels
    'show_map_thumbnails': True,        # Show thumbnails in popups
    'mapbox_token': 'pk.eyJ...'        # Stored securely
}
```

### Dependencies

**npm Packages** (`package.json`):
```json
{
  "dependencies": {
    "@tauri-apps/api": "^1.5.6"
  },
  "devDependencies": {
    "@tauri-apps/cli": "^1.5.14"
  }
}
```

**Rust Crates** (`Cargo.toml`):
```toml
[dependencies]
tauri = { version = "1.5", features = ["shell-open"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
```

**Python Packages** (add to `requirements.txt`):
```
websocket-server>=0.6.0
```

### Build Process

**1. Install Prerequisites**:
```bash
# Node.js & npm
# Download from https://nodejs.org/

# Rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Python dependencies
pip install websocket-server
```

**2. Build Tauri App**:
```bash
cd media_analysis/tauri-map
npm install
npm run build
```

**3. Verify Build**:
```bash
# Windows
dir src-tauri\target\release\*.exe

# Linux/Mac
ls -lh src-tauri/target/release/
```

**Build Output**:
- **Windows**: `Media Analysis Map.exe` (~8-15 MB)
- **Linux**: `media-analysis-map` (~10-20 MB)
- **macOS**: `Media Analysis Map.app` (bundle)

---

## Migration Strategy

### Backward Compatibility During Transition

**Feature Flag Approach**:

```python
# media_analysis/ui/media_analysis_tab.py

USE_TAURI_MAP = True  # Feature flag

if USE_TAURI_MAP:
    from .components.geo.geo_visualization_widget_tauri import (
        GeoVisualizationWidgetTauri as GeoVisualizationWidget
    )
else:
    from .components.geo.geo_visualization_widget import GeoVisualizationWidget
```

### Gradual Rollout

**Week 1**: Phases 1-3 (infrastructure)
- Tauri scaffold
- Mapbox integration
- Bridge service
- Test with developers only

**Week 2**: Phases 4-7 (features)
- Data models
- Photo markers
- Clustering
- Interactive features
- Beta testing with power users

**Week 3**: Phases 8-10 (integration)
- UI integration
- Build process
- Full testing
- Documentation

**Week 4**: Release
- Enable by default
- Monitor for issues
- Keep Leaflet as fallback

### Rollback Plan

**Immediate Rollback** (if critical issues):
```python
USE_TAURI_MAP = False  # Single line change
```

**Gradual Rollback** (if performance issues):
1. Identify specific issue
2. Fix in Tauri implementation
3. Re-enable gradually

---

## Appendices

### Appendix A: Leaflet vs. Tauri/Mapbox Comparison

| Feature | Leaflet (Current) | Tauri/Mapbox (Proposed) |
|---------|-------------------|-------------------------|
| **Performance** | DOM-based, ~30fps with 100+ markers | WebGL, 60fps with 1000+ markers |
| **Clustering** | Leaflet.markercluster (good) | Mapbox Supercluster (excellent) |
| **CSS Conflicts** | ❌ Conflicts with Qt styles | ✅ Isolated process |
| **Thumbnails** | ✅ Base64 in popups | ✅ Base64 in popups |
| **Timeline** | ❌ Not available | ✅ Temporal playback |
| **Heatmaps** | ⚠️ Plugin required | ✅ Built-in |
| **3D Support** | ❌ No | ✅ Terrain, buildings |
| **Offline** | ✅ Full offline | ⚠️ Requires API key |
| **Setup Complexity** | Low (pure JS) | High (Rust + npm build) |
| **Distribution** | ✅ Simple | ⚠️ Bundle executable |
| **API Costs** | Free | Free tier: 50k loads/month |

### Appendix B: Code Templates

**Template 1: Adding a New Message Type**

```python
# Python side (tauri_bridge_service.py)
def send_custom_command(self, command_data: Dict[str, Any]) -> Result[None]:
    try:
        message = {
            "type": "custom_command",
            "data": command_data
        }
        if self.connected_clients and self.ws_server:
            self.ws_server.send_message_to_all(json.dumps(message))
        return Result.success(None)
    except Exception as e:
        return Result.error(str(e))
```

```javascript
// JavaScript side (mapbox.html)
handleMessage(msg) {
    switch(msg.type) {
        case 'custom_command':
            this.handleCustomCommand(msg.data);
            break;
        // ... other cases
    }
}

handleCustomCommand(data) {
    console.log('Custom command:', data);
    // Implementation
}
```

**Template 2: Adding a Map Control**

```javascript
// In setupControls()
this.map.addControl(new mapboxgl.NavigationControl(), 'top-left');
this.map.addControl(new mapboxgl.ScaleControl(), 'bottom-right');
this.map.addControl(new mapboxgl.FullscreenControl(), 'top-right');

// Custom control
class CustomControl {
    onAdd(map) {
        this.map = map;
        this.container = document.createElement('div');
        this.container.className = 'mapboxgl-ctrl mapboxgl-ctrl-group';
        this.container.innerHTML = '<button>Custom</button>';
        this.container.onclick = () => {
            // Handle click
        };
        return this.container;
    }

    onRemove() {
        this.container.parentNode.removeChild(this.container);
        this.map = undefined;
    }
}

this.map.addControl(new CustomControl(), 'top-left');
```

### Appendix C: Troubleshooting Guide

**Issue**: Tauri executable not found
```bash
# Solution
cd media_analysis/tauri-map
npm install
npm run build
# Verify: ls src-tauri/target/release/
```

**Issue**: WebSocket connection refused
```bash
# Check if WebSocket server is running
# Check firewall isn't blocking localhost:8765
# Check Tauri app logs in DevTools
```

**Issue**: Map not loading / blank screen
```
1. Open Tauri DevTools (F12)
2. Check console for errors
3. Verify MAPBOX_TOKEN is set
4. Check network tab for failed API calls
```

**Issue**: Thumbnails not showing
```
1. Verify base64 data is present in wire format
2. Check console for image decode errors
3. Verify base64 prefix is correct (data:image/jpeg;base64,)
4. Test with small thumbnail first
```

**Issue**: Build fails on Rust compile
```bash
# Update Rust toolchain
rustup update

# Clear build cache
cd media_analysis/tauri-map/src-tauri
cargo clean
cargo build --release
```

**Issue**: Performance issues with many photos
```javascript
// Reduce cluster radius
CONFIG.clusterRadius = 30;

// Increase cluster max zoom
CONFIG.clusterMaxZoom = 16;

// Disable thumbnails temporarily
CONFIG.showThumbnails = false;
```

### Appendix D: Future Enhancements

**Phase 2 Features** (Post-Initial Release):

1. **Timeline Animation**
   - Playback photos chronologically
   - Speed controls (1x, 2x, 5x)
   - Date range slider
   - Auto-play mode

2. **Heatmap Mode**
   - Photo density heatmap
   - Device activity heatmap
   - Time-based heatmap (morning/afternoon/evening)

3. **Advanced Filtering**
   - Date range picker
   - Device multi-select
   - File type filter
   - Has-thumbnail filter

4. **Measurement Tools**
   - Distance measurement
   - Area calculation
   - Elevation profile

5. **3D Visualization**
   - Terrain mode
   - Building extrusion
   - Altitude-based markers
   - Camera path visualization

6. **Collaboration**
   - Share map view (URL)
   - Export with comments
   - Annotation tools
   - Print-optimized export

7. **Advanced Analysis**
   - Co-location detection
   - Route reconstruction
   - Speed analysis
   - Stop detection

### Appendix E: Performance Benchmarks

Target performance metrics:

| Metric | Target | Acceptable | Poor |
|--------|--------|------------|------|
| Initial load time | <1s | <3s | >5s |
| 100 photos render | <200ms | <500ms | >1s |
| 1000 photos render | <500ms | <2s | >5s |
| FPS (panning) | 60fps | 45fps | <30fps |
| Memory usage | <200MB | <500MB | >1GB |
| WebSocket latency | <50ms | <200ms | >500ms |

---

## Summary

This implementation plan provides a complete roadmap for replacing the Leaflet-based map with a Tauri/Mapbox architecture. The key advantages are:

1. **Process Isolation** - Eliminates CSS conflicts
2. **Performance** - WebGL rendering for thousands of photos
3. **Feature Richness** - Clustering, heatmaps, 3D terrain
4. **Proven Architecture** - Based on working Vehicle Tracking implementation

The phased approach allows for incremental development and testing, with clear rollback points at each phase. The total estimated time is 18-26 hours over 3-5 days, with the ability to ship a working MVP after Phase 8.

The feature flag approach ensures backward compatibility during migration, and the comprehensive test suite validates functionality at each stage.

**Key Success Factors**:
- Follow Vehicle Tracking patterns closely
- Test thoroughly at each phase
- Maintain clear separation between Python and JavaScript
- Use wire format validation to catch issues early
- Keep Leaflet implementation as fallback during transition

**Next Steps**:
1. Review and approve plan
2. Set up development environment (Node.js, Rust)
3. Begin Phase 1 (Tauri scaffold)
4. Iterate through phases with testing
5. Deploy and monitor

---

*Document Version: 1.0*
*Created: 2025-10-10*
*Author: Claude (Anthropic)*
*Project: Folder Structure Utility - Media Analysis Module*
