# Python-Tauri WebSocket Bridge - Complete Architecture Documentation

## Section 1: Natural Language Technical Walkthrough

### Overview
The Python-Tauri Bridge is a WebSocket-based communication system that enables real-time bidirectional data flow between a Python backend (PySide6/Qt application) and a Tauri frontend (Rust-wrapped web application with Mapbox visualization). This bridge solves the fundamental challenge of connecting Python's data processing capabilities with modern web-based visualization technologies.

### The Architecture Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     PYTHON APPLICATION (PySide6)                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   Vehicle Tracking Tab                    │   │
│  │  ┌──────────┐  ┌──────────┐  ┌─────────────────────┐   │   │
│  │  │   UI     │──▶│Controller│──▶│  TauriBridgeService │   │   │
│  │  └──────────┘  └──────────┘  └──────────┬──────────┘   │   │
│  └───────────────────────────────────────────┼──────────────┘   │
│                                              │                   │
│                                              ▼                   │
│                                   ┌──────────────────┐          │
│                                   │  WebSocket Server │          │
│                                   │   (Port: Dynamic) │          │
│                                   └────────┬─────────┘          │
└────────────────────────────────────────────┼───────────────────┘
                                             │
                                             │ WebSocket
                                             │ ws://localhost:PORT
                                             │
┌────────────────────────────────────────────┼───────────────────┐
│                        TAURI APPLICATION    │                    │
│                                             ▼                    │
│  ┌────────────────────────────────────────────────────────┐    │
│  │                    WebSocket Client                      │    │
│  │                    (PythonBridge)                        │    │
│  └──────────────────────────┬───────────────────────────────┘   │
│                              │                                    │
│  ┌───────────────────────────▼────────────────────────────────┐ │
│  │                     mapbox.html                             │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │ │
│  │  │ VehicleMap   │◀─│ PythonBridge │─▶│   Mapbox GL  │    │ │
│  │  │  Template    │  │    Class     │  │      Map      │    │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘    │ │
│  └──────────────────────────────────────────────────────────┘ │
│                         (Rust Process)                          │
└──────────────────────────────────────────────────────────────┘
```

### Port Discovery Mechanism

The system uses a sophisticated multi-layered port discovery mechanism to ensure reliable connection:

#### 1. **Dynamic Port Allocation (Python Side)**
```python
# Python allocates a free port dynamically
def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('localhost', 0))  # OS assigns free port
        s.listen(1)
        port = s.getsockname()[1]
    return port  # e.g., 49843
```

#### 2. **Port Communication Chain**
The port number travels through FOUR different channels to ensure reliability:

```
Python finds port (49843)
    │
    ├──▶ Command Line Argument: --ws-port=49843
    │    (Passed to Tauri executable)
    │
    ├──▶ Configuration File: ws-config.js
    │    (Written to disk with timestamp)
    │
    ├──▶ URL Parameter: ?port=49843
    │    (Embedded in navigation URL)
    │
    └──▶ Environment Variable: TAURI_WS_PORT=49843
         (Fallback mechanism)
```

#### 3. **JavaScript Port Discovery Priority**
The JavaScript client attempts to discover the port in this order:

1. **ws-config.js file** (if recent, <5 seconds old)
2. **URL parameter** (?port=XXXXX)
3. **Environment variable** (window.TAURI_WS_PORT)
4. **Default fallback** (8765 - usually fails)

### Message Protocol

The WebSocket uses JSON messages with a type-based routing system:

#### Python → JavaScript Messages
```javascript
{
    "type": "load_vehicles",
    "data": {
        "vehicles": [...],
        "settings": {
            "showTrails": true,
            "trailLength": 30,
            "playbackSpeed": 1.0
        },
        "startTime": "2024-01-01T10:00:00",
        "endTime": "2024-01-01T10:30:00"
    }
}
```

#### JavaScript → Python Messages
```javascript
{
    "type": "ready" | "vehicle_clicked" | "animation_complete" | "map_error",
    "vehicleId": "vehicle_1",  // optional
    "message": "error details", // optional
    "critical": false           // optional
}
```

### Connection Lifecycle

```
1. Python starts WebSocket server on free port
2. Python launches Tauri with port argument
3. Tauri (Rust) reads port from command line
4. Tauri writes ws-config.js file
5. Tauri navigates to mapbox.html?port=XXXXX
6. JavaScript loads and reads port from URL
7. JavaScript connects WebSocket to Python
8. Python sends queued messages on connection
9. Bidirectional communication established
```

### Data Flow Example: Loading Vehicle Data

```
User clicks "Open Map" in Python UI
    │
    ▼
Python: _open_map_with_tauri()
    │
    ├─▶ Start WebSocket server
    ├─▶ Launch Tauri process
    ├─▶ Convert vehicle data to JS format
    └─▶ Queue data for sending

Tauri launches
    │
    ▼
JavaScript: PythonBridge connects
    │
    ├─▶ Send "ready" message
    └─▶ Receive queued vehicle data

JavaScript: loadVehicles(data)
    │
    ├─▶ Apply settings
    ├─▶ Process GPS points
    └─▶ Render on map
```

## Section 2: Senior Developer Documentation

### TauriBridgeService Implementation

```python
class TauriBridgeService(BaseService):
    """
    Manages WebSocket server and Tauri process lifecycle.
    Thread-safe singleton pattern with automatic cleanup.
    """

    def __init__(self):
        self.ws_server: Optional[WebsocketServer] = None
        self.ws_port: Optional[int] = None
        self.ws_thread: Optional[threading.Thread] = None
        self.tauri_process: Optional[subprocess.Popen] = None
        self.connected_clients: List[Dict] = []
        self.pending_messages: List[Dict] = []  # Queue for offline clients

    def start(self) -> Result[int]:
        """
        Initialize bridge infrastructure:
        1. Find free port using socket.bind(0)
        2. Start WebSocket server in daemon thread
        3. Launch Tauri with --ws-port argument
        4. Return port for status display
        """

    def _start_websocket_server(self):
        """
        WebSocket server with callbacks:
        - set_fn_new_client: Handle connections
        - set_fn_client_left: Handle disconnections
        - set_fn_message_received: Route messages
        """

    def _on_client_connected(self, client, server):
        """
        Critical: Send pending_messages immediately on connect
        This ensures data sent before connection is not lost
        """
        for msg in self.pending_messages:
            server.send_message(client, json.dumps(msg))
        self.pending_messages.clear()
```

### JavaScript PythonBridge Implementation

```javascript
class PythonBridge {
    constructor() {
        this.port = null;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
    }

    async init() {
        // Port discovery cascade with validation
        // Priority: config file → URL params → env → default

        if (window.WS_CONFIG?.port) {
            // Validate timestamp to avoid stale configs
            const configAge = (Date.now() - Date.parse(window.WS_CONFIG.timestamp)) / 1000;
            if (configAge < 5) {  // Less than 5 seconds old
                this.port = window.WS_CONFIG.port;
                return this.connect();
            }
        }

        // URL parameter is most reliable
        const urlParams = new URLSearchParams(window.location.search);
        const urlPort = urlParams.get('port');
        if (urlPort) {
            this.port = parseInt(urlPort, 10);
            return this.connect();
        }
    }

    connect() {
        this.ws = new WebSocket(`ws://localhost:${this.port}/`);

        this.ws.onopen = () => {
            this.reconnectAttempts = 0;
            this.ws.send(JSON.stringify({ type: 'ready' }));
        };

        this.ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            this.handleMessage(msg);
        };

        this.ws.onclose = () => {
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                setTimeout(() => this.connect(), 2000);
                this.reconnectAttempts++;
            }
        };
    }
}
```

### Rust Integration (main.rs)

```rust
#[tauri::command]
fn get_ws_port() -> u16 {
    // Parse command line: --ws-port=XXXXX
    std::env::args().nth(1)
        .and_then(|arg| {
            if arg.starts_with("--ws-port=") {
                arg.strip_prefix("--ws-port=")?.parse().ok()
            } else {
                arg.parse().ok()
            }
        })
        .or_else(|| std::env::var("TAURI_WS_PORT").ok()?.parse().ok())
        .unwrap_or(8765)
}

fn write_ws_config(port: u16) {
    // Critical: Write config file for JavaScript fallback
    let config_content = format!(
        "window.WS_CONFIG = {{\n\
         \tport: {},\n\
         \ttimestamp: '{}'\n\
         }};",
        port,
        chrono::Local::now().format("%Y-%m-%d %H:%M:%S")
    );
    // Write to src/ws-config.js for static loading
}

fn main() {
    let ws_port = get_ws_port();

    tauri::Builder::default()
        .setup(move |app| {
            // Navigate with port in URL - most reliable method
            let script = format!("window.location.href = 'mapbox.html?port={}'", ws_port);
            window.eval(&script).ok();
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

### Message Handling Architecture

#### Python Side Message Dispatch
```python
def send_vehicle_data(self, vehicle_data: Dict[str, Any]) -> Result[None]:
    message = {
        "type": "load_vehicles",
        "data": vehicle_data
    }

    if self.connected_clients and self.ws_server:
        # Send immediately if connected
        self.ws_server.send_message_to_all(json.dumps(message))
    else:
        # Queue for when client connects
        self.pending_messages.append(message)

    return Result.success(None)
```

#### JavaScript Message Router
```javascript
handleMessage(msg) {
    switch(msg.type) {
        case 'load_vehicles':
            // Critical: Apply settings BEFORE loading vehicles
            if (msg.data.settings) {
                this.applySettings(msg.data.settings);
            }
            window.vehicleMap?.loadVehicles(msg.data);
            break;

        case 'control':
            this.handleControl(msg.command);
            break;

        case 'switch_provider':
            // Navigate to different map provider
            window.location.href = `${msg.provider}.html?port=${this.port}`;
            break;
    }
}
```

### Critical Implementation Details

#### 1. Thread Safety
- WebSocket server runs in daemon thread
- All client lists protected by GIL
- Message queuing prevents race conditions

#### 2. Process Management
```python
# Tauri process launched with proper cleanup
self.tauri_process = subprocess.Popen(
    [tauri_exe, "--ws-port", str(self.ws_port)],
    cwd=self.tauri_path / "src-tauri",
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

def shutdown(self):
    # Clean shutdown sequence
    if self.tauri_process:
        self.tauri_process.terminate()
        self.tauri_process.wait(timeout=5)
    if self.ws_server:
        self.ws_server.shutdown()
```

#### 3. Settings Propagation
```python
# Settings MUST be included in vehicle data
js_data = {
    "vehicles": [...],
    "settings": {
        "showTrails": settings.show_trails,
        "trailLength": settings.trail_length,  # 0=none, >0=seconds, -1=persistent
        "playbackSpeed": settings.playback_speed,
        "autoCenter": settings.auto_center
    }
}
```

### Performance Considerations

1. **Message Batching**: Queue multiple updates, send as single message
2. **Binary Data**: For large datasets, consider MessagePack over JSON
3. **Compression**: Enable WebSocket compression for large GPS datasets
4. **Throttling**: Limit update frequency to 60 FPS maximum

### Security Considerations

1. **Localhost Only**: WebSocket bound to localhost prevents external access
2. **Port Randomization**: Dynamic ports prevent port scanning
3. **Message Validation**: Always validate message types and data
4. **Process Isolation**: Tauri runs in separate process with limited permissions

## Bug Fixes and Lessons Learned

### Bug 1: Tauri API Invoke Errors
**Problem**: JavaScript calling non-existent Rust commands causing uncaught exceptions
```javascript
// WRONG - These commands don't exist in Rust
window.__TAURI__.invoke('map_ready')  // Uncaught TypeError
```

**Solution**: Use WebSocket for all communication
```javascript
// CORRECT - Send through WebSocket
window.pythonBridge.send({ type: 'map_ready' })
```

**Prevention**:
- Document all Tauri commands in Rust
- Use TypeScript for type-safe invoke calls
- Implement proper error boundaries

### Bug 2: Port Discovery Failures
**Problem**: Multiple port discovery methods failing due to timing issues

**Solution**: Implement cascade with validation
```javascript
// Validate config timestamp
if (configAge < 5) {  // Only use if recent
    this.port = window.WS_CONFIG.port;
}
```

**Prevention**:
- Always pass port in URL parameters (most reliable)
- Implement timestamp validation for config files
- Provide multiple fallback mechanisms

### Bug 3: Settings Not Applied
**Problem**: Vehicle data loaded before settings, causing defaults to be used

**Solution**: Apply settings in loadVehicles BEFORE processing
```javascript
loadVehicles(vehicleData) {
    // Apply settings FIRST
    if (vehicleData.settings) {
        CONFIG.showTrails = vehicleData.settings.showTrails;
        CONFIG.trailLength = vehicleData.settings.trailLength;
    }
    // THEN process vehicles
    this.processVehicles(vehicleData.vehicles);
}
```

**Prevention**:
- Always include settings in data messages
- Apply settings before any processing
- Use explicit defaults matching Python defaults

### Bug 4: Stale Configuration Files
**Problem**: Old ws-config.js files being used hours later

**Solution**: Timestamp validation
```javascript
const configAge = (Date.now() - Date.parse(window.WS_CONFIG.timestamp)) / 1000;
if (configAge > 5) {
    console.warn('[ws-config.js] Config file is stale, ignoring');
}
```

**Prevention**:
- Add ws-config.js to .gitignore
- Clean up config files on shutdown
- Always validate timestamps

### Bug 5: WebSocket Reconnection Storms
**Problem**: Infinite reconnection attempts consuming resources

**Solution**: Implement exponential backoff with limits
```javascript
if (this.reconnectAttempts < this.maxReconnectAttempts) {
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    setTimeout(() => this.connect(), delay);
}
```

### Future Extensibility

#### Adding New Message Types
1. Define message structure in both Python and JavaScript
2. Add handler in PythonBridge.handleMessage()
3. Implement sender in TauriBridgeService
4. Document in message protocol section

#### Supporting Multiple Visualizations
```python
# Each tab gets its own bridge instance
self.bridges = {
    'vehicle_tracking': TauriBridgeService(),
    'cell_towers': TauriBridgeService(),
    'transit_taps': TauriBridgeService()
}
```

#### Database Integration Points
```python
# Future: Stream from database through bridge
async def stream_from_database(self, query):
    async for batch in database.stream(query):
        processed = self.process_batch(batch)
        self.bridge.send_vehicle_data(processed)
        await asyncio.sleep(0.1)  # Throttle
```

## Testing the Bridge

### Manual Testing
```python
# Test port allocation
bridge = TauriBridgeService()
result = bridge.start()
print(f"WebSocket running on port: {result.value}")

# Test message sending
test_data = {"vehicles": [], "settings": {"showTrails": False}}
bridge.send_vehicle_data(test_data)
```

### JavaScript Console Testing
```javascript
// Verify connection
console.log(window.pythonBridge.ws.readyState);  // 1 = OPEN

// Send test message
window.pythonBridge.send({ type: 'test', data: 'hello' });

// Check configuration
console.log(CONFIG);
```

## Conclusion

This Python-Tauri WebSocket bridge provides a robust, extensible foundation for real-time data visualization. The multi-layered port discovery, message queuing, and error handling ensure reliable communication even in complex deployment scenarios. The architecture supports multiple simultaneous visualizations, handles large datasets efficiently, and provides clear extension points for future features like database streaming and additional visualization types.

---
*Document created: 2024-09-19*
*Purpose: Complete technical documentation of Python-Tauri WebSocket Bridge for future development*
*Audience: AI assistants and senior developers extending this system*