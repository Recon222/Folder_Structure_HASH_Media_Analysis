# ExifTool Integration with Interactive Geolocation Visualization
## Implementation Plan for Enhanced Media Analysis

## Executive Summary

This plan details the integration of ExifTool alongside FFprobe with interactive geolocation visualization using QWebEngineView and mapping libraries (Leaflet, Mapbox, Google Maps). The two-tab approach separates FFprobe's media analysis from ExifTool's forensic metadata extraction while adding powerful GPS visualization capabilities for investigation workflows.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [UI Design Specification](#ui-design-specification)
3. [Technology Stack](#technology-stack)
4. [Implementation Phases](#implementation-phases)
5. [Component Specifications](#component-specifications)
6. [Security & Privacy](#security-privacy)
7. [Performance Optimization](#performance-optimization)
8. [Testing Strategy](#testing-strategy)

---

## Architecture Overview

### High-Level Design

```
┌─────────────────────────────────────────────────────────┐
│                    MediaAnalysisTab                      │
│  ┌──────────────────────────────────────────────────┐  │
│  │            Tab Widget Container                   │  │
│  │  ┌──────────────┐  ┌──────────────────────┐    │  │
│  │  │ FFprobe Tab  │  │   ExifTool Tab       │    │  │
│  │  └──────────────┘  └──────────────────────┘    │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │     MediaAnalysisController             │
        └─────────────────────────────────────────┘
                              │
                 ┌────────────┴────────────┐
                 ▼                         ▼
    ┌─────────────────────┐   ┌─────────────────────┐
    │  FFProbeWrapper      │   │  ExifToolWrapper    │
    └─────────────────────┘   └─────────────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │  GeoVisualizationEngine │
                 │    (QWebEngineView)     │
                 └─────────────────────────┘
```

### Component Interaction Flow

1. **User selects files** → ExifTool Tab
2. **Clicks Analyze** → ExifToolWrapper extracts metadata
3. **GPS data found** → Passed to GeoVisualizationEngine
4. **JavaScript bridge** → Markers plotted on interactive map
5. **User interaction** → Click markers, view clusters, export data

---

## UI Design Specification

### ExifTool Tab Layout

```
┌─ Media Analysis ─────────────────────────────────────────────────────┐
│  [FFprobe] [ExifTool]  <── Tab Selection                             │
│                                                                       │
│  ==================== ExifTool Tab ====================              │
│                                                                       │
│  ┌─ Files to Analyze ─────────────────────────────────────────────┐ │
│  │ [📁 Add Files] [📂 Add Folder] [🗑️ Clear]  47 files selected   │ │
│  │ ┌──────────────────────────────────────────────────────────┐   │ │
│  │ │ ✓ DSC_0001.jpg    📍 40.7128, -74.0060   2024-01-15 10:30 │   │ │
│  │ │ ✓ DSC_0002.jpg    📍 40.7580, -73.9855   2024-01-15 11:45 │   │ │
│  │ │ ✗ Document.pdf    No GPS data                             │   │ │
│  │ │ ✓ VID_0001.mp4    📍 40.7489, -73.9680   2024-01-15 14:20 │   │ │
│  │ └──────────────────────────────────────────────────────────┘   │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│ ┌─ ExifTool Settings ──────────┐ ┌─ GPS Visualization ─────────────┐ │
│ │ ┌─ SCROLLABLE ────────────┐  │ │                                 │ │
│ │ │                         │  │ │    [🗺️ Map View] [🛰️ Satellite] │ │
│ │ │ ☐ Geospatial Data      │  │ │    [+] [-] ⟲  [Export KML]      │ │
│ │ │   ☑ GPS Coordinates    │  │ │                                 │ │
│ │ │   ☑ GPS Accuracy       │  │ │   ┌─────────────────────────┐   │ │
│ │ │   ☑ Altitude           │  │ │   │                         │   │ │
│ │ │   ☑ Speed/Direction    │  │ │   │     🗺️ LEAFLET MAP      │   │ │
│ │ │                         │  │ │   │                         │   │ │
│ │ │ ☐ Temporal Forensics   │  │ │   │    📍 📍    📍           │   │ │
│ │ │   ☑ Original DateTime  │  │ │   │      📍  📍              │   │ │
│ │ │   ☑ All Timestamps     │  │ │   │         📍 📍 📍         │   │ │
│ │ │   ☑ Timezone Info      │  │ │   │                         │   │ │
│ │ │                         │  │ │   │   [Timeline Scrubber]   │   │ │
│ │ │ ☐ Device ID            │  │ │   │   ├──●──────────────┤   │   │ │
│ │ │   ☑ Serial Numbers     │  │ │   └─────────────────────────┘   │ │
│ │ │   ☑ Make/Model        │  │ │                                 │ │
│ │ └─────────────────────▼──┘  │ │ Legend:                         │ │
│ │                              │ │ 📍 Photo  🎥 Video  ● Selected │ │
│ │ [🔍 Analyze with ExifTool]   │ │ Device A: 🔵  Device B: 🔴      │ │
│ └──────────────────────────────┘ └─────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────┘
```

### Map Interaction Features

- **Click on marker** → Highlight corresponding file in list
- **Click on file** → Center map on location, show popup
- **Cluster markers** → Auto-group nearby locations
- **Timeline scrubber** → Show temporal progression
- **Device filtering** → Show/hide by device serial
- **Export options** → HTML, KML, CSV with coordinates

---

## Technology Stack

### Core Technologies

#### Mapping Libraries Comparison

| Feature | Leaflet | Mapbox GL JS | Google Maps |
|---------|---------|--------------|-------------|
| **License** | Open Source (BSD-2) | Proprietary | Proprietary |
| **Cost** | Free | Free tier + paid | $200 credit/month |
| **Performance** | Good (DOM-based) | Excellent (WebGL) | Excellent |
| **File Size** | 42KB | ~200KB | ~50KB (loader) |
| **Offline Maps** | Yes (with tiles) | Yes | Limited |
| **3D Support** | Plugin | Native | Native |
| **Clustering** | Plugin | Native | Native |
| **Best For** | Open source, flexibility | Beautiful visuals | Familiar UX |

### Recommended Stack

```python
# Primary: Leaflet (open source, forensic-friendly)
# Secondary: Mapbox (for advanced visualizations)
# Tertiary: Google Maps (if customer requires)

TECHNOLOGY_STACK = {
    "web_engine": "PySide6.QtWebEngineView",
    "bridge": "PySide6.QtWebChannel",
    "primary_map": "Leaflet 1.9.4",
    "tile_provider": "OpenStreetMap / Custom",
    "clustering": "Leaflet.markercluster",
    "export": "tokml (Python) / Leaflet.Export (JS)"
}
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)

#### 1.1 ExifTool Infrastructure

```python
# core/exiftool/exiftool_binary_manager.py
class ExifToolBinaryManager:
    """Manages ExifTool binary detection and validation"""
    
    def locate_binary(self) -> Optional[Path]:
        """Find exiftool in system"""
        locations = [
            Path("bin/exiftool.exe"),  # Windows bundled
            Path("/usr/bin/exiftool"),  # Linux system
            Path("/usr/local/bin/exiftool"),  # macOS homebrew
        ]
        # Check PATH environment variable
        return self._validate_locations(locations)
    
    def validate_binary(self, path: Path) -> bool:
        """Validate ExifTool functionality"""
        try:
            result = subprocess.run(
                [str(path), "-ver"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
```

#### 1.2 ExifTool Command Builder

```python
# core/exiftool/exiftool_command_builder.py
class ExifToolForensicCommandBuilder:
    """Build optimized ExifTool commands for batch processing"""
    
    FORENSIC_FIELDS = {
        'geospatial': [
            '-GPS:all',
            '-XMP:LocationShown*',
            '-EXIF:GPSSpeed',
            '-EXIF:GPSImgDirection'
        ],
        'temporal': [
            '-AllDates',
            '-SubSecTime*',
            '-TimeZone*',
            '-OffsetTime*'
        ],
        'device': [
            '-Make', '-Model',
            '-SerialNumber',
            '-InternalSerialNumber',
            '-LensSerialNumber',
            '-BodySerialNumber'
        ]
    }
    
    def build_batch_command(
        self, 
        files: List[Path], 
        settings: ExifToolSettings
    ) -> List[str]:
        """Build single command for batch processing"""
        cmd = ['exiftool', '-json', '-fast2', '-struct']
        
        # Add field groups based on settings
        if settings.geospatial_enabled:
            cmd.extend(self.FORENSIC_FIELDS['geospatial'])
        if settings.temporal_enabled:
            cmd.extend(self.FORENSIC_FIELDS['temporal'])
        if settings.device_enabled:
            cmd.extend(self.FORENSIC_FIELDS['device'])
        
        # Add file paths
        cmd.extend([str(f) for f in files])
        return cmd
```

### Phase 2: Batch Processing & Normalization (Week 2)

#### 2.1 ExifTool Wrapper

```python
# core/exiftool/exiftool_wrapper.py
class ExifToolWrapper:
    """Batch processing wrapper for ExifTool"""
    
    def __init__(self, binary_path: Path):
        self.binary_path = binary_path
        self.command_builder = ExifToolForensicCommandBuilder()
        
    def extract_batch(
        self,
        files: List[Path],
        settings: ExifToolSettings,
        max_batch: int = 50,
        progress_callback: Optional[Callable] = None
    ) -> List[ExifToolMetadata]:
        """Process files in optimized batches"""
        
        results = []
        total_batches = (len(files) + max_batch - 1) // max_batch
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            
            for i in range(0, len(files), max_batch):
                batch = files[i:i+max_batch]
                future = executor.submit(
                    self._process_batch,
                    batch,
                    settings
                )
                futures.append((i // max_batch, future))
            
            for batch_num, future in futures:
                try:
                    batch_results = future.result(timeout=30)
                    results.extend(batch_results)
                    
                    if progress_callback:
                        progress = (batch_num + 1) / total_batches * 100
                        progress_callback(progress, f"Batch {batch_num+1}/{total_batches}")
                        
                except TimeoutError:
                    logger.error(f"Batch {batch_num} timed out")
                    
        return results
```

#### 2.2 ExifTool Normalizer

```python
# core/exiftool/exiftool_normalizer.py
class ExifToolNormalizer:
    """Normalize ExifTool output to structured data"""
    
    def normalize_gps(self, raw_data: Dict) -> Optional[GPSData]:
        """Extract and normalize GPS coordinates"""
        
        # Handle different GPS formats
        lat = raw_data.get('GPSLatitude')
        lon = raw_data.get('GPSLongitude')
        
        if not lat or not lon:
            # Try alternate fields
            location = raw_data.get('Location')
            if location:
                # Parse ISO 6709 format
                lat, lon = self._parse_iso6709(location)
        
        if lat and lon:
            return GPSData(
                latitude=self._dms_to_decimal(lat),
                longitude=self._dms_to_decimal(lon),
                altitude=raw_data.get('GPSAltitude'),
                accuracy=raw_data.get('GPSHPositioningError'),
                speed=raw_data.get('GPSSpeed'),
                direction=raw_data.get('GPSImgDirection')
            )
        return None
```

### Phase 3: QWebEngineView Integration (Week 3)

#### 3.1 Map Widget Implementation

```python
# ui/components/geo_visualization_widget.py
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QObject, Slot, Signal

class GeoBridge(QObject):
    """Bridge between Python and JavaScript map"""
    
    marker_clicked = Signal(str)  # file_path
    map_clicked = Signal(float, float)  # lat, lon
    export_requested = Signal(str)  # format
    
    def __init__(self):
        super().__init__()
        self._markers = []
        
    @Slot(list)
    def add_markers(self, markers: List[Dict]):
        """Add markers to map from Python"""
        self._markers.extend(markers)
        # JavaScript will be notified via signal
        
    @Slot(str)
    def on_marker_click(self, file_path: str):
        """Handle marker click from JavaScript"""
        self.marker_clicked.emit(file_path)
        
    @Slot(str, result=str)
    def get_api_key(self, provider: str) -> str:
        """Securely provide API key to JavaScript"""
        return settings.get_map_api_key(provider)

class GeoVisualizationWidget(QWidget):
    """Interactive map visualization for GPS data"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Web view setup
        self.web_view = QWebEngineView()
        self.web_channel = QWebChannel()
        self.geo_bridge = GeoBridge()
        
        # Register bridge
        self.web_channel.registerObject("geoBridge", self.geo_bridge)
        self.web_view.page().setWebChannel(self.web_channel)
        
        # Load HTML
        self._load_map_html()
        
        # Connect signals
        self.geo_bridge.marker_clicked.connect(self._on_marker_clicked)
        
    def _load_map_html(self):
        """Load the map HTML with selected provider"""
        html_path = Path(__file__).parent / "map_template.html"
        self.web_view.load(QUrl.fromLocalFile(str(html_path)))
        
    def add_media_locations(self, media_list: List[ExifToolMetadata]):
        """Add media file locations to map"""
        markers = []
        for media in media_list:
            if media.gps_latitude and media.gps_longitude:
                markers.append({
                    'lat': media.gps_latitude,
                    'lon': media.gps_longitude,
                    'path': str(media.file_path),
                    'time': media.capture_time.isoformat() if media.capture_time else None,
                    'device': media.device_id,
                    'type': 'photo' if media.file_path.suffix.lower() in ['.jpg', '.heic'] else 'video'
                })
        
        # Send to JavaScript
        self.web_view.page().runJavaScript(
            f"window.mapController.addMarkers({json.dumps(markers)})"
        )
```

#### 3.2 HTML/JavaScript Map Template

```html
<!-- ui/components/map_template.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Media Location Map</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <!-- Leaflet CSS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    
    <!-- Leaflet MarkerCluster CSS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
    
    <style>
        #map { height: 100vh; width: 100%; }
        .timeline-control {
            position: absolute;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            width: 80%;
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            z-index: 1000;
        }
        .device-legend {
            position: absolute;
            top: 10px;
            right: 10px;
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            z-index: 1000;
        }
    </style>
</head>
<body>
    <div id="map"></div>
    
    <!-- Timeline Control -->
    <div class="timeline-control" id="timeline">
        <input type="range" id="timeSlider" min="0" max="100" value="100" style="width:100%">
        <div id="timeDisplay">All Times</div>
    </div>
    
    <!-- Device Legend -->
    <div class="device-legend" id="legend">
        <h4>Devices</h4>
        <div id="deviceList"></div>
    </div>
    
    <!-- QWebChannel -->
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    
    <!-- Leaflet JS -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    
    <!-- Leaflet MarkerCluster -->
    <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
    
    <script>
        class MapController {
            constructor() {
                this.map = null;
                this.markers = [];
                this.devices = new Map();
                this.markerCluster = null;
                this.bridge = null;
                
                this.initMap();
                this.initQWebChannel();
            }
            
            initMap() {
                // Initialize Leaflet map
                this.map = L.map('map').setView([40.7128, -74.0060], 13);
                
                // Add OpenStreetMap tiles
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenStreetMap contributors',
                    maxZoom: 19
                }).addTo(this.map);
                
                // Initialize marker cluster group
                this.markerCluster = L.markerClusterGroup({
                    chunkedLoading: true,
                    spiderfyOnMaxZoom: true,
                    showCoverageOnHover: true,
                    zoomToBoundsOnClick: true
                });
                this.map.addLayer(this.markerCluster);
            }
            
            initQWebChannel() {
                // Connect to Python backend
                new QWebChannel(qt.webChannelTransport, (channel) => {
                    this.bridge = channel.objects.geoBridge;
                    
                    // Listen for Python commands
                    this.bridge.markersUpdated.connect(() => {
                        this.refreshMarkers();
                    });
                });
            }
            
            addMarkers(markerData) {
                // Clear existing markers
                this.markerCluster.clearLayers();
                this.markers = [];
                this.devices.clear();
                
                // Process each marker
                markerData.forEach(data => {
                    // Track devices
                    if (data.device && !this.devices.has(data.device)) {
                        this.devices.set(data.device, {
                            color: this.getDeviceColor(this.devices.size),
                            count: 0
                        });
                    }
                    
                    // Create marker
                    const icon = this.createIcon(data.type, data.device);
                    const marker = L.marker([data.lat, data.lon], { icon: icon });
                    
                    // Add popup
                    marker.bindPopup(`
                        <strong>${data.path.split('/').pop()}</strong><br>
                        ${data.time ? `Time: ${new Date(data.time).toLocaleString()}<br>` : ''}
                        ${data.device ? `Device: ${data.device}<br>` : ''}
                        Coordinates: ${data.lat.toFixed(6)}, ${data.lon.toFixed(6)}
                    `);
                    
                    // Add click handler
                    marker.on('click', () => {
                        if (this.bridge) {
                            this.bridge.on_marker_click(data.path);
                        }
                    });
                    
                    // Store marker data
                    marker.data = data;
                    this.markers.push(marker);
                    
                    // Add to cluster
                    this.markerCluster.addLayer(marker);
                    
                    // Update device count
                    if (data.device) {
                        this.devices.get(data.device).count++;
                    }
                });
                
                // Update legend
                this.updateDeviceLegend();
                
                // Fit map to markers
                if (this.markers.length > 0) {
                    const group = new L.featureGroup(this.markers);
                    this.map.fitBounds(group.getBounds().pad(0.1));
                }
                
                // Initialize timeline
                this.initTimeline();
            }
            
            createIcon(type, device) {
                const deviceInfo = device ? this.devices.get(device) : null;
                const color = deviceInfo ? deviceInfo.color : '#3388ff';
                const iconSymbol = type === 'video' ? '🎥' : '📍';
                
                return L.divIcon({
                    html: `<div style="color: ${color}; font-size: 24px;">${iconSymbol}</div>`,
                    iconSize: [30, 30],
                    iconAnchor: [15, 30],
                    popupAnchor: [0, -30],
                    className: 'custom-marker'
                });
            }
            
            getDeviceColor(index) {
                const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96E6A1', '#FFEAA7'];
                return colors[index % colors.length];
            }
            
            updateDeviceLegend() {
                const legendDiv = document.getElementById('deviceList');
                legendDiv.innerHTML = '';
                
                this.devices.forEach((info, deviceId) => {
                    const item = document.createElement('div');
                    item.innerHTML = `
                        <span style="color: ${info.color}">●</span>
                        ${deviceId} (${info.count} files)
                    `;
                    legendDiv.appendChild(item);
                });
            }
            
            initTimeline() {
                // Get time range
                const times = this.markers
                    .map(m => m.data.time)
                    .filter(t => t)
                    .map(t => new Date(t).getTime());
                
                if (times.length === 0) {
                    document.getElementById('timeline').style.display = 'none';
                    return;
                }
                
                const minTime = Math.min(...times);
                const maxTime = Math.max(...times);
                
                const slider = document.getElementById('timeSlider');
                const display = document.getElementById('timeDisplay');
                
                slider.addEventListener('input', (e) => {
                    const percent = e.target.value / 100;
                    const currentTime = minTime + (maxTime - minTime) * percent;
                    
                    // Update display
                    if (percent === 1) {
                        display.textContent = 'All Times';
                    } else {
                        display.textContent = new Date(currentTime).toLocaleString();
                    }
                    
                    // Filter markers
                    this.filterMarkersByTime(currentTime);
                });
            }
            
            filterMarkersByTime(maxTime) {
                this.markerCluster.clearLayers();
                
                this.markers.forEach(marker => {
                    if (!marker.data.time || new Date(marker.data.time).getTime() <= maxTime) {
                        this.markerCluster.addLayer(marker);
                    }
                });
            }
            
            exportMap(format) {
                if (format === 'html') {
                    this.exportAsHTML();
                } else if (format === 'kml') {
                    this.exportAsKML();
                }
            }
            
            exportAsHTML() {
                // Create standalone HTML with current markers
                const html = `
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Exported Media Locations</title>
                        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
                        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                    </head>
                    <body>
                        <div id="map" style="height: 100vh;"></div>
                        <script>
                            const map = L.map('map').setView([40.7128, -74.0060], 13);
                            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
                            const markers = ${JSON.stringify(this.markers.map(m => m.data))};
                            markers.forEach(data => {
                                L.marker([data.lat, data.lon])
                                    .bindPopup(data.path)
                                    .addTo(map);
                            });
                        </script>
                    </body>
                    </html>
                `;
                
                // Send to Python for saving
                if (this.bridge) {
                    this.bridge.export_html(html);
                }
            }
            
            popOutToBrowser() {
                // Export current state and open in browser
                this.exportAsHTML();
                if (this.bridge) {
                    this.bridge.open_in_browser();
                }
            }
        }
        
        // Initialize controller
        window.mapController = new MapController();
    </script>
</body>
</html>
```

### Phase 4: Service Integration & UI (Week 4)

#### 4.1 Enhanced MediaAnalysisService

```python
# core/services/media_analysis_service.py (additions)
class MediaAnalysisService(BaseService, IMediaAnalysisService):
    """Extended service with ExifTool support"""
    
    def __init__(self):
        super().__init__()
        self.ffprobe_wrapper = FFProbeWrapper()
        self.exiftool_wrapper = ExifToolWrapper()
        
    def analyze_with_exiftool(
        self,
        files: List[Path],
        settings: ExifToolSettings,
        progress_callback: Optional[Callable] = None
    ) -> Result[ExifToolAnalysisResult]:
        """Analyze files with ExifTool for forensic metadata"""
        
        try:
            # Extract metadata
            metadata_list = self.exiftool_wrapper.extract_batch(
                files,
                settings,
                progress_callback=progress_callback
            )
            
            # Normalize results
            normalized = [
                self.exiftool_normalizer.normalize(m) 
                for m in metadata_list
            ]
            
            # Build result
            result = ExifToolAnalysisResult(
                total_files=len(files),
                successful=len([m for m in normalized if not m.error]),
                metadata_list=normalized,
                gps_locations=[m for m in normalized if m.has_gps],
                device_map=self._build_device_map(normalized)
            )
            
            return Result.success(result)
            
        except Exception as e:
            return Result.error(MediaAnalysisError(str(e)))
```

#### 4.2 ExifTool Tab Implementation

```python
# ui/tabs/exiftool_analysis_tab.py
class ExifToolAnalysisTab(QWidget):
    """Tab for ExifTool analysis with geolocation visualization"""
    
    def __init__(self, form_data: Optional[FormData] = None, parent=None):
        super().__init__(parent)
        self.controller = MediaAnalysisController()
        self.form_data = form_data
        self.last_results = None
        
        self._create_ui()
        
    def _create_ui(self):
        layout = QVBoxLayout(self)
        
        # Top: File selection (compact)
        files_group = self._create_files_section()
        layout.addWidget(files_group, stretch=1)
        
        # Bottom: Settings and Map side by side
        bottom_splitter = QSplitter(Qt.Horizontal)
        
        # Left: Settings
        settings_panel = self._create_settings_panel()
        bottom_splitter.addWidget(settings_panel)
        
        # Right: Map visualization
        self.map_widget = GeoVisualizationWidget()
        bottom_splitter.addWidget(self.map_widget)
        
        # Set proportions (30% settings, 70% map)
        bottom_splitter.setSizes([300, 700])
        
        layout.addWidget(bottom_splitter, stretch=3)
        
    def _on_analysis_complete(self, result: Result):
        """Handle analysis completion"""
        if result.is_success():
            data = result.data
            
            # Update file list with GPS indicators
            self._update_file_list(data.metadata_list)
            
            # Update map with locations
            if data.gps_locations:
                self.map_widget.add_media_locations(data.gps_locations)
                
            # Show success message
            self._show_success_dialog(data)
            
    def _export_map(self):
        """Export map in various formats"""
        menu = QMenu(self)
        
        # Export as HTML
        html_action = menu.addAction("📄 Export as HTML")
        html_action.triggered.connect(lambda: self._export_html())
        
        # Export as KML
        kml_action = menu.addAction("🌍 Export as KML")
        kml_action.triggered.connect(lambda: self._export_kml())
        
        # Open in browser
        browser_action = menu.addAction("🌐 Open in Browser")
        browser_action.triggered.connect(lambda: self._open_in_browser())
        
        menu.exec_(QCursor.pos())
```

---

## Component Specifications

### Data Models

```python
# core/exiftool/exiftool_models.py
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

@dataclass
class GPSData:
    """GPS location data from ExifTool"""
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    accuracy: Optional[float] = None  # meters
    speed: Optional[float] = None  # km/h
    direction: Optional[float] = None  # degrees
    
@dataclass
class ExifToolMetadata:
    """Forensic metadata from ExifTool"""
    file_path: Path
    
    # Geospatial
    gps_data: Optional[GPSData] = None
    location_name: Optional[str] = None
    
    # Temporal (multiple sources for validation)
    capture_time: Optional[datetime] = None
    create_time: Optional[datetime] = None
    modify_time: Optional[datetime] = None
    file_modify_time: Optional[datetime] = None
    timezone_offset: Optional[str] = None
    
    # Device identification
    device_make: Optional[str] = None
    device_model: Optional[str] = None
    device_id: Optional[str] = None  # Serial number
    lens_id: Optional[str] = None
    
    # Document integrity
    document_id: Optional[str] = None
    instance_id: Optional[str] = None
    edit_history: Optional[List[str]] = None
    
    # Raw data
    raw_json: Optional[Dict] = None
    error: Optional[str] = None
    
    @property
    def has_gps(self) -> bool:
        return self.gps_data is not None

@dataclass
class ExifToolAnalysisResult:
    """Results from ExifTool analysis"""
    total_files: int
    successful: int
    failed: int
    metadata_list: List[ExifToolMetadata]
    gps_locations: List[ExifToolMetadata]  # Files with GPS
    device_map: Dict[str, List[ExifToolMetadata]]  # By device ID
    processing_time: float
    errors: List[str]
```

### API Key Management

```python
# ui/dialogs/map_settings_dialog.py
class MapSettingsDialog(QDialog):
    """Settings dialog for map API keys"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Map Settings")
        self._create_ui()
        
    def _create_ui(self):
        layout = QFormLayout(self)
        
        # Map provider selection
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Leaflet (OpenStreetMap)", "Mapbox", "Google Maps"])
        layout.addRow("Map Provider:", self.provider_combo)
        
        # API Key inputs
        self.mapbox_key = QLineEdit()
        self.mapbox_key.setEchoMode(QLineEdit.Password)
        self.mapbox_key.setPlaceholderText("pk.eyJ1I...")
        layout.addRow("Mapbox API Key:", self.mapbox_key)
        
        self.google_key = QLineEdit()
        self.google_key.setEchoMode(QLineEdit.Password)
        self.google_key.setPlaceholderText("AIzaSy...")
        layout.addRow("Google Maps API Key:", self.google_key)
        
        # Tile server for offline
        self.tile_server = QLineEdit()
        self.tile_server.setPlaceholderText("http://localhost:8080/tiles/{z}/{x}/{y}.png")
        layout.addRow("Custom Tile Server:", self.tile_server)
        
        # Save/Cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._save_settings)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
```

---

## Security & Privacy

### API Key Protection

1. **Storage**: Use QSettings with encryption for API keys
2. **Transport**: Pass keys via QWebChannel, never embed in HTML
3. **Validation**: Validate API keys before use
4. **Rotation**: Support key rotation without code changes

### Privacy Considerations

1. **GPS Obfuscation**: Option to round coordinates (reduce precision)
2. **Export Control**: Confirm before exporting location data
3. **Offline Mode**: Support offline tile servers for air-gapped systems
4. **Data Retention**: Clear map data when analysis completes

```python
def obfuscate_gps(lat: float, lon: float, precision: int = 4) -> Tuple[float, float]:
    """Reduce GPS precision for privacy"""
    return (
        round(lat, precision),
        round(lon, precision)
    )
```

---

## Performance Optimization

### Batch Processing Strategy

- **ExifTool**: Process 50 files per command (optimal for command line limits)
- **Threading**: Use 4 workers for parallel batch processing
- **Caching**: Cache device IDs and GPS clusters
- **Lazy Loading**: Load map tiles on demand

### Performance Metrics

| Operation | Target | Method |
|-----------|--------|---------|
| 100 files extraction | < 3 seconds | Batch processing |
| 1000 markers display | < 1 second | Clustering |
| Map interaction | < 100ms | WebGL rendering |
| Export HTML | < 2 seconds | Template generation |

---

## Testing Strategy

### Test Data Requirements

```python
TEST_MEDIA = {
    "iPhone HEIC with GPS": "test_data/iphone_gps.heic",
    "Android video with GPS": "test_data/android_video.mp4",
    "DSLR without GPS": "test_data/canon_no_gps.jpg",
    "Edited with history": "test_data/photoshop_edited.jpg",
    "Multiple devices": "test_data/device_collection/",
}
```

### Unit Tests

```python
def test_batch_processing_performance():
    """Verify batch processing efficiency"""
    files = list(Path("test_media").glob("*"))
    
    start = time.time()
    wrapper = ExifToolWrapper(binary_path)
    results = wrapper.extract_batch(files, settings)
    duration = time.time() - start
    
    # Should process at ~30ms per file
    assert duration / len(files) < 0.03
    
def test_gps_extraction():
    """Verify GPS coordinate extraction"""
    result = wrapper.extract_metadata(
        Path("test_data/iphone_gps.heic"),
        settings
    )
    
    assert result.gps_data is not None
    assert -90 <= result.gps_data.latitude <= 90
    assert -180 <= result.gps_data.longitude <= 180
```

### Integration Tests

1. **End-to-end workflow**: Files → ExifTool → Map → Export
2. **JavaScript bridge**: Python ↔ JavaScript communication
3. **Map interaction**: Click events, clustering, timeline
4. **Export formats**: HTML, KML validation

---

## Implementation Timeline

### Week 1: Foundation
- ✅ ExifTool binary manager
- ✅ Command builder with forensic fields
- ✅ Basic wrapper implementation
- ✅ Unit tests for core components

### Week 2: Processing & Normalization
- ✅ Batch processing optimization
- ✅ GPS normalization (multiple formats)
- ✅ Device ID extraction
- ✅ Temporal data validation

### Week 3: Map Integration
- ✅ QWebEngineView setup
- ✅ QWebChannel bridge
- ✅ Leaflet integration
- ✅ Marker clustering
- ✅ Timeline control

### Week 4: UI & Polish
- ✅ ExifTool tab UI
- ✅ Settings persistence
- ✅ Export functionality
- ✅ API key management
- ✅ Integration testing

---

## Success Metrics

- ✅ Process 100 files in < 3 seconds
- ✅ Display 1000+ GPS markers smoothly
- ✅ Export map as standalone HTML
- ✅ Support offline tile servers
- ✅ Extract GPS from iOS/Android media
- ✅ Identify devices by serial number
- ✅ Timeline-based filtering
- ✅ Cluster nearby locations
- ✅ Export to KML for Google Earth

---

## Conclusion

This implementation plan provides a robust foundation for integrating ExifTool with interactive geolocation visualization. The two-tab approach maintains clean separation between FFprobe and ExifTool while adding significant forensic value through GPS visualization. The use of QWebEngineView with Leaflet provides a professional, interactive mapping experience that enhances investigation workflows.

The architecture supports future enhancements including:
- Heat map visualizations
- Path reconstruction
- Multi-device tracking
- Temporal analysis
- Integration with case management systems

The focus on batch processing, forensic metadata, and privacy considerations ensures this solution meets professional investigation requirements while maintaining excellent performance.