# Vehicle Tracking Animation Feature - Complete Development Documentation

## Section 1: Natural Language Technical Walkthrough

### Overview
The Vehicle Tracking Animation feature transforms CSV files containing GPS coordinates into an interactive, animated map visualization showing vehicle movements over time. Think of it as converting a spreadsheet of location data into a movie showing where vehicles traveled.

### The Journey of Data

#### 1. CSV Input & Column Detection
When a user selects CSV files through the UI, the system intelligently detects the format. It handles both comma and tab-delimited files, automatically identifying columns for latitude, longitude, timestamp, speed, and bearing/heading. The parser is forgiving - it's case-insensitive and recognizes many column name variations (lat/latitude/LAT, lon/longitude/long, etc.).

#### 2. Timestamp Parsing & Normalization
The system handles various timestamp formats including "YYYY-MM-DD HH:MM", ISO formats, and US/European date formats. Each timestamp gets converted to a Python datetime object, establishing a timeline for the vehicle's journey.

#### 3. GPS Point Validation
Not all GPS data is valid. The system filters out:
- Rows with missing coordinates
- Invalid latitude/longitude values
- Points without timestamps
- Duplicate or corrupted entries

#### 4. Speed Calculation
If speed data isn't provided, the system calculates it using the Haversine formula - measuring the distance between consecutive GPS points and dividing by time elapsed. This gives us speed in km/h for each segment of the journey.

#### 5. Path Interpolation
GPS data often has gaps - maybe the device only recorded every 30 seconds. The interpolation engine fills these gaps:
- **Linear**: Straight lines between points
- **Cubic**: Smooth curves following the path
- **Geodesic**: Great circle paths on Earth's surface

The system generates intermediate points at configurable intervals (0.5s, 1s, 2s, 5s) creating smooth animation.

#### 6. Color Assignment
Each vehicle gets a unique color from a predefined palette (blue, red, green, yellow, purple, orange, cyan, magenta). This helps distinguish multiple vehicles on the same map.

#### 7. Animation Data Preparation
The system calculates:
- Timeline start: earliest timestamp across all vehicles
- Timeline end: latest timestamp across all vehicles
- Total duration in seconds
- Frame rate for smooth playback

#### 8. Tauri Bridge Activation
When ready to visualize, the system:
1. Starts a WebSocket server on a dynamic port
2. Launches the Tauri application (native window with web renderer)
3. Passes the port number via command-line argument
4. Writes a config file with the port for backup

#### 9. Data Transformation & Transmission
Python data structures get converted to JavaScript-friendly JSON:
```
VehicleData → {id, label, color, gps_points[{latitude, longitude, timestamp, speed}]}
AnimationData → {startTime, endTime, vehicles[]}
```

This data streams over WebSocket to the Tauri app.

#### 10. Map Initialization
The Tauri app:
1. Loads Mapbox GL JS
2. Validates/requests Mapbox API token
3. Creates the map centered on vehicle data
4. Sets up layers for markers and trails

#### 11. Animation Engine
The JavaScript animation loop:
1. Uses `requestAnimationFrame` for 60 FPS rendering
2. Calculates current time based on playback speed (0.5x to 10x)
3. For each frame:
   - Finds each vehicle's position at current time
   - Uses binary search for efficiency
   - Interpolates between GPS points
   - Updates marker positions
   - Draws trail lines
   - Updates UI (timeline, speed display)

#### 12. User Interactions
Users can:
- Play/pause/stop animation
- Scrub timeline to any point
- Change playback speed
- Toggle trails on/off
- Click vehicles for details
- Switch map styles

### Error Handling & Recovery
The system gracefully handles:
- Malformed CSV files
- Network issues with map tiles
- Missing GPS data
- WebSocket disconnections
- Invalid timestamps
- Resource limitations

## Section 2: Senior Developer Documentation

### Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   UI Layer  │────▶│  Controller  │────▶│   Service   │
│  (PySide6)  │     │   (Python)   │     │   (Python)  │
└─────────────┘     └──────────────┘     └─────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │    Worker    │
                    │   (QThread)  │
                    └──────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │ Tauri Bridge │
                    │  (WebSocket) │
                    └──────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │  Tauri App   │
                    │ (Rust + JS)  │
                    └──────────────┘
```

### Core Components

#### VehicleTrackingTab (`ui/vehicle_tracking_tab.py`)
```python
class VehicleTrackingTab(QWidget):
    # Entry point - manages UI state
    def _start_tracking(self):
        settings = self._gather_current_settings()
        result = self.controller.start_vehicle_tracking_workflow(
            file_paths=self.selected_files,
            settings=settings,
            use_worker=True
        )

    def _on_tracking_complete(self, result: Result):
        if result.success:
            self._open_map_with_tauri()

    def _convert_to_js_format(self, tracking_result):
        # Transform Python models to JS-compatible dict
        return {
            "vehicles": [...],
            "startTime": ISO_string,
            "endTime": ISO_string
        }
```

#### VehicleTrackingService (`services/vehicle_tracking_service.py`)
```python
class VehicleTrackingService(BaseService, IVehicleTrackingService):

    def parse_csv_file(self, file_path, settings):
        # 1. Detect delimiter (tab/comma)
        # 2. Map columns (case-insensitive)
        # 3. Parse rows with validation
        # 4. Return Result[VehicleData]

    def interpolate_path(self, vehicle_data, settings):
        # Generate intermediate points
        # Methods: LINEAR, CUBIC, GEODESIC
        # Interval: 0.5-5 seconds

    def prepare_animation_data(self, vehicles, settings):
        # Calculate timeline bounds
        # Return AnimationData with all vehicles
```

#### CSV Parsing Pipeline
```python
DEFAULT_COLUMN_MAPPINGS = {
    'latitude': ['latitude', 'lat', 'Latitude', 'LAT', 'GPS_Latitude'],
    'longitude': ['longitude', 'lon', 'lng', 'Longitude', 'LON', 'LNG'],
    'timestamp': ['timestamp', 'time', 'datetime', 'Timestamp', 'TIME'],
    'speed': ['speed', 'speed_kmh', 'Speed', 'SPEED'],
    'heading': ['heading', 'bearing', 'direction', 'Heading', 'BEARING']
}

def _parse_timestamp(self, timestamp_str):
    formats = [
        '%Y-%m-%d %H:%M',      # 2024-11-09 15:26
        '%Y-%m-%d %H:%M:%S',   # With seconds
        '%Y-%m-%dT%H:%M:%S',   # ISO format
        # ... 10+ more formats
    ]
    for fmt in formats:
        try: return datetime.strptime(timestamp_str, fmt)
```

#### TauriBridgeService (`services/tauri_bridge_service.py`)
```python
class TauriBridgeService(BaseService):

    def start(self) -> Result[int]:
        # 1. Find free port
        # 2. Start WebSocket server
        # 3. Launch Tauri with --ws-port=XXXX
        # 4. Return port number

    def send_vehicle_data(self, data: Dict):
        # Send JSON over WebSocket
        # Message format: {"type": "vehicle_data", ...}
```

#### Tauri Backend (`tauri-map/src-tauri/src/main.rs`)
```rust
#[tauri::command]
fn get_ws_port() -> u16 {
    // Parse --ws-port from args
    // Write ws-config.js for backup
    // Return port
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            // Navigate to mapbox.html?port=XXXX
            window.eval(&format!("window.location.href = 'mapbox.html?port={}'", port));
        })
        .run()
}
```

#### JavaScript Animation Engine (`mapbox_tauri_template_production.html`)
```javascript
class VehicleMapTemplate {
    constructor() {
        this.vehicles = new Map();
        this.state = {
            isPlaying: false,
            currentTime: null,
            startTime: null,
            endTime: null,
            playbackSpeed: 1
        };
    }

    loadVehicles(vehicleData) {
        // Process each vehicle
        // Normalize GPS points
        // Set timeline bounds
    }

    animate() {
        if (!this.state.isPlaying) return;

        const deltaTime = performance.now() - this.state.lastFrameTime;
        this.state.currentTime += deltaTime * this.state.playbackSpeed;

        this.renderFrame();
        this.animationFrame = requestAnimationFrame(() => this.animate());
    }

    findPointAtTime(points, timestamp) {
        // Binary search for efficiency
        // Interpolate between points
        // Return {latitude, longitude, speed}
    }

    renderFrame() {
        const positions = [];
        this.vehicles.forEach((vehicle, id) => {
            const point = this.findPointAtTime(vehicle.gps_points, this.state.currentTime);
            positions.push({
                type: 'Feature',
                properties: {vehicle_id: id, speed: point.speed},
                geometry: {type: 'Point', coordinates: [point.longitude, point.latitude]}
            });
        });

        this.map.getSource('vehicle-positions').setData({
            type: 'FeatureCollection',
            features: positions
        });
    }
}
```

### Critical Data Structures

#### Python Models
```python
@dataclass
class GPSPoint:
    latitude: float
    longitude: float
    timestamp: datetime
    speed_kmh: Optional[float] = None
    heading: Optional[float] = None
    altitude: Optional[float] = None

@dataclass
class VehicleData:
    vehicle_id: str
    source_file: Path
    gps_points: List[GPSPoint] = field(default_factory=list)
    color: Optional[VehicleColor] = None
    label: Optional[str] = None

@dataclass
class AnimationData:
    vehicles: List[VehicleData]
    timeline_start: datetime
    timeline_end: datetime
    total_duration_seconds: float = 0.0
```

#### JavaScript Format
```javascript
{
    "vehicles": [{
        "id": "vehicle_1",
        "label": "Test Vehicle 1",
        "color": "#0099ff",
        "gps_points": [{
            "latitude": 45.4215,
            "longitude": -75.6972,
            "timestamp": "2024-01-01T10:00:00",
            "speed": 30.0,
            "altitude": 0,
            "heading": 315
        }]
    }],
    "startTime": "2024-01-01T10:00:00",
    "endTime": "2024-01-01T10:04:30"
}
```

### Performance Optimizations

1. **Binary Search**: O(log n) position lookup in `findPointAtTime()`
2. **Chunked CSV Reading**: Process large files without memory overflow
3. **WebSocket Streaming**: Send data progressively, not all at once
4. **RequestAnimationFrame**: Smooth 60 FPS rendering
5. **Mapbox Layer Updates**: Update data sources, not recreate layers
6. **Point Limiting**: Cap at configurable max (default 10000/vehicle)

### Configuration Points

```python
class VehicleTrackingSettings:
    # Processing
    max_points_per_vehicle: int = 10000
    chunk_size: int = 5000

    # Interpolation
    interpolation_enabled: bool = True
    interpolation_method: InterpolationMethod = LINEAR
    interpolation_interval: float = 1.0

    # Animation
    playback_speed: float = 1.0
    show_trails: bool = True
    trail_length: int = 30  # seconds

    # Display
    auto_center: bool = True
    cluster_markers: bool = False
```

### Error Recovery

```python
# Result-based error handling throughout
Result.success(data) / Result.error(FSAError)

# Worker thread cancellation
if self.is_cancelled():
    return Result.error(CancellationError())

# WebSocket reconnection
if connection lost:
    retry with exponential backoff

# Tauri crash recovery
if process.poll() is not None:
    restart Tauri application
```

### Testing Entry Points

```python
# Direct service test
service = VehicleTrackingService()
result = service.parse_csv_file(Path("test.csv"), settings)

# Full pipeline test
.venv/Scripts/python.exe vehicle_tracking/test_tauri_integration.py

# Quick animation test
.venv/Scripts/python.exe vehicle_tracking/test_tauri_quick.py
```

### Deployment Checklist

- [ ] Build Tauri: `cd tauri-map && cargo build --release`
- [ ] Verify ws-config.js in .gitignore
- [ ] Check Mapbox token handling
- [ ] Test with various CSV formats
- [ ] Validate memory usage with large files
- [ ] Confirm WebSocket port allocation
- [ ] Test animation performance

### Known Limitations

1. Max 25 vehicles simultaneously (Mapbox layer limit)
2. Max 10000 points per vehicle (configurable)
3. Requires Mapbox API token
4. Windows-only Tauri build currently
5. No offline map support