#!/usr/bin/env python3
"""
Map HTML Template - Leaflet-based interactive map for GPS visualization
Self-contained HTML with JavaScript for forensic media location analysis
"""

MAP_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>Media Location Map</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <!-- Leaflet CSS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" 
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" 
          crossorigin=""/>
    
    <!-- Leaflet MarkerCluster CSS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
    
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }
        
        #map { 
            height: 100vh; 
            width: 100%; 
        }
        
        .timeline-control {
            position: absolute;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            width: 80%;
            max-width: 600px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 1000;
        }
        
        .timeline-control h4 {
            margin: 0 0 10px 0;
            font-size: 14px;
            color: #333;
        }
        
        #timeSlider {
            width: 100%;
            margin: 10px 0;
        }
        
        #timeDisplay {
            text-align: center;
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        
        .device-legend {
            position: absolute;
            top: 10px;
            right: 10px;
            background: white;
            padding: 12px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 1000;
            max-width: 250px;
            max-height: 300px;
            overflow-y: auto;
        }
        
        .device-legend h4 {
            margin: 0 0 10px 0;
            font-size: 14px;
            color: #333;
            border-bottom: 1px solid #e0e0e0;
            padding-bottom: 5px;
        }
        
        .device-item {
            display: flex;
            align-items: center;
            margin: 5px 0;
            font-size: 12px;
            cursor: pointer;
            padding: 3px;
            border-radius: 3px;
            transition: background-color 0.2s;
        }
        
        .device-item:hover {
            background-color: #f0f0f0;
        }
        
        .device-color {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            border: 1px solid rgba(0,0,0,0.2);
        }
        
        .stats-panel {
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            z-index: 1000;
            font-size: 12px;
        }
        
        .custom-marker {
            background: none;
            border: none;
        }
        
        .marker-cluster-small {
            background-color: rgba(110, 204, 57, 0.6);
        }
        
        .marker-cluster-medium {
            background-color: rgba(240, 194, 12, 0.6);
        }
        
        .marker-cluster-large {
            background-color: rgba(241, 128, 23, 0.6);
        }
        
        .leaflet-popup-content {
            font-size: 13px;
            line-height: 1.5;
        }
        
        .popup-title {
            font-weight: bold;
            margin-bottom: 5px;
            color: #2c3e50;
        }
        
        .popup-row {
            margin: 3px 0;
        }
        
        .popup-label {
            color: #7f8c8d;
            font-size: 11px;
        }
    </style>
</head>
<body>
    <div id="map"></div>
    
    <!-- Timeline Control -->
    <div class="timeline-control" id="timeline" style="display: none;">
        <h4>Timeline Filter</h4>
        <input type="range" id="timeSlider" min="0" max="100" value="100" />
        <div id="timeDisplay">All Times</div>
    </div>
    
    <!-- Device Legend -->
    <div class="device-legend" id="legend">
        <h4>Devices</h4>
        <div id="deviceList"></div>
    </div>
    
    <!-- Stats Panel -->
    <div class="stats-panel" id="stats" style="display: none;">
        <div id="statsContent"></div>
    </div>
    
    <!-- QWebChannel -->
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    
    <!-- Leaflet JS -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" 
            integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" 
            crossorigin=""></script>
    
    <!-- Leaflet MarkerCluster -->
    <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
    
    <script>
        class MapController {
            constructor() {
                this.map = null;
                this.markers = [];
                this.markerLayer = null;
                this.devices = new Map();
                this.markerCluster = null;
                this.bridge = null;
                this.timeline = null;
                this.deviceColors = [
                    '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
                    '#DDA0DD', '#98D8C8', '#F7DC6F', '#85C1E2', '#F8B739'
                ];
                
                this.initMap();
                this.initQWebChannel();
            }
            
            initMap() {
                // Initialize Leaflet map
                this.map = L.map('map', {
                    center: [40.7128, -74.0060], // Default to NYC
                    zoom: 13,
                    zoomControl: true,
                    attributionControl: true
                });
                
                // Add OpenStreetMap tiles
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenStreetMap contributors',
                    maxZoom: 19
                }).addTo(this.map);
                
                // Initialize marker cluster group
                this.markerCluster = L.markerClusterGroup({
                    chunkedLoading: true,
                    spiderfyOnMaxZoom: true,
                    showCoverageOnHover: false,
                    zoomToBoundsOnClick: true,
                    maxClusterRadius: 60,
                    iconCreateFunction: function(cluster) {
                        const count = cluster.getChildCount();
                        let size = 'small';
                        let dimension = 40;
                        
                        if (count > 10) {
                            size = 'medium';
                            dimension = 50;
                        }
                        if (count > 50) {
                            size = 'large';
                            dimension = 60;
                        }
                        
                        return new L.DivIcon({
                            html: '<div><span>' + count + '</span></div>',
                            className: 'marker-cluster marker-cluster-' + size,
                            iconSize: new L.Point(dimension, dimension)
                        });
                    }
                });
                
                this.map.addLayer(this.markerCluster);
                
                // Track map bounds changes
                this.map.on('moveend', () => this.onBoundsChange());
                
                console.log('Map initialized');
            }
            
            initQWebChannel() {
                // Connect to Python backend via Qt WebChannel
                if (typeof QWebChannel !== 'undefined' && typeof qt !== 'undefined') {
                    new QWebChannel(qt.webChannelTransport, (channel) => {
                        this.bridge = channel.objects.geoBridge;
                        
                        // Notify Python that map is ready
                        if (this.bridge) {
                            this.bridge.on_map_ready();
                            
                            // Load initial markers
                            this.loadMarkersFromBridge();
                        }
                    });
                } else {
                    console.log('Running in standalone mode (no Qt bridge)');
                    // Load test data if available
                    if (typeof MARKERS_DATA !== 'undefined') {
                        this.updateMarkers(MARKERS_DATA);
                    }
                }
            }
            
            loadMarkersFromBridge() {
                if (!this.bridge) return;
                
                // Get markers from Python
                this.bridge.get_markers_json((markersJson) => {
                    if (markersJson) {
                        const markers = JSON.parse(markersJson);
                        this.updateMarkers(markers);
                    }
                });
            }
            
            updateMarkers(markerData) {
                // Clear existing markers
                this.clearMarkers();
                
                // Reset device tracking
                this.devices.clear();
                let colorIndex = 0;
                
                // Process each marker
                markerData.forEach(data => {
                    // Track devices
                    if (data.device_id && !this.devices.has(data.device_id)) {
                        this.devices.set(data.device_id, {
                            name: data.device || 'Unknown',
                            color: this.deviceColors[colorIndex % this.deviceColors.length],
                            count: 0,
                            markers: []
                        });
                        colorIndex++;
                    }
                    
                    // Create marker
                    const marker = this.createMarker(data);
                    if (marker) {
                        this.markers.push(marker);
                        this.markerCluster.addLayer(marker);
                        
                        // Update device count
                        if (data.device_id) {
                            const deviceInfo = this.devices.get(data.device_id);
                            deviceInfo.count++;
                            deviceInfo.markers.push(marker);
                        }
                    }
                });
                
                // Update UI elements
                this.updateDeviceLegend();
                this.updateTimeline();
                this.updateStats();
                
                // Fit map to markers
                if (this.markers.length > 0) {
                    this.fitAllMarkers();
                }
                
                console.log(`Updated ${this.markers.length} markers`);
            }
            
            createMarker(data) {
                if (!data.lat || !data.lon) return null;
                
                // Get device info for styling
                const deviceInfo = data.device_id ? this.devices.get(data.device_id) : null;
                const color = deviceInfo ? deviceInfo.color : '#3388ff';
                
                // Choose icon based on type
                let iconSymbol = '📍';
                if (data.type === 'video') iconSymbol = '🎥';
                else if (data.type === 'photo') iconSymbol = '📷';
                
                // Create custom icon
                const icon = L.divIcon({
                    html: `<div style="color: ${color}; font-size: 24px; text-shadow: 1px 1px 2px rgba(0,0,0,0.3);">${iconSymbol}</div>`,
                    iconSize: [30, 30],
                    iconAnchor: [15, 30],
                    popupAnchor: [0, -30],
                    className: 'custom-marker'
                });
                
                // Create marker
                const marker = L.marker([data.lat, data.lon], { icon: icon });
                
                // Create popup content
                let popupHtml = `<div class="popup-content">`;
                popupHtml += `<div class="popup-title">${data.filename || 'Unknown'}</div>`;
                
                if (data.time_display) {
                    popupHtml += `<div class="popup-row"><span class="popup-label">Time:</span> ${data.time_display}</div>`;
                }
                
                if (data.device) {
                    popupHtml += `<div class="popup-row"><span class="popup-label">Device:</span> ${data.device}</div>`;
                }
                
                popupHtml += `<div class="popup-row"><span class="popup-label">Coordinates:</span> ${data.lat.toFixed(6)}, ${data.lon.toFixed(6)}</div>`;
                
                if (data.altitude) {
                    popupHtml += `<div class="popup-row"><span class="popup-label">Altitude:</span> ${data.altitude.toFixed(1)}m</div>`;
                }
                
                if (data.speed) {
                    popupHtml += `<div class="popup-row"><span class="popup-label">Speed:</span> ${data.speed.toFixed(1)} km/h</div>`;
                }
                
                if (data.direction) {
                    popupHtml += `<div class="popup-row"><span class="popup-label">Direction:</span> ${data.direction.toFixed(0)}°</div>`;
                }
                
                popupHtml += '</div>';
                
                marker.bindPopup(popupHtml);
                
                // Add click handler
                marker.on('click', () => {
                    if (this.bridge) {
                        this.bridge.on_marker_click(data.path);
                    }
                });
                
                // Store data on marker
                marker.data = data;
                
                return marker;
            }
            
            updateDeviceLegend() {
                const legendDiv = document.getElementById('deviceList');
                legendDiv.innerHTML = '';
                
                this.devices.forEach((info, deviceId) => {
                    const item = document.createElement('div');
                    item.className = 'device-item';
                    item.innerHTML = `
                        <span class="device-color" style="background-color: ${info.color}"></span>
                        <span>${info.name} (${info.count})</span>
                    `;
                    
                    // Add click handler to focus on device
                    item.onclick = () => this.focusOnDevice(deviceId);
                    
                    legendDiv.appendChild(item);
                });
                
                // Add unknown device entry if needed
                const unknownCount = this.markers.filter(m => !m.data.device_id).length;
                if (unknownCount > 0) {
                    const item = document.createElement('div');
                    item.className = 'device-item';
                    item.innerHTML = `
                        <span class="device-color" style="background-color: #999"></span>
                        <span>Unknown (${unknownCount})</span>
                    `;
                    legendDiv.appendChild(item);
                }
            }
            
            updateTimeline() {
                // Get time range from markers
                const times = this.markers
                    .map(m => m.data.time)
                    .filter(t => t)
                    .map(t => new Date(t).getTime());
                
                if (times.length === 0) {
                    document.getElementById('timeline').style.display = 'none';
                    return;
                }
                
                document.getElementById('timeline').style.display = 'block';
                
                const minTime = Math.min(...times);
                const maxTime = Math.max(...times);
                
                const slider = document.getElementById('timeSlider');
                const display = document.getElementById('timeDisplay');
                
                // Reset slider
                slider.value = 100;
                display.textContent = 'All Times';
                
                slider.oninput = (e) => {
                    const percent = e.target.value / 100;
                    
                    if (percent === 1) {
                        display.textContent = 'All Times';
                        this.showAllMarkers();
                    } else {
                        const currentTime = minTime + (maxTime - minTime) * percent;
                        display.textContent = new Date(currentTime).toLocaleString();
                        this.filterMarkersByTime(currentTime);
                    }
                };
            }
            
            updateStats() {
                const statsContent = document.getElementById('statsContent');
                const totalMarkers = this.markers.length;
                const devicesCount = this.devices.size;
                
                if (totalMarkers > 0) {
                    statsContent.innerHTML = `
                        <strong>Statistics</strong><br>
                        Locations: ${totalMarkers}<br>
                        Devices: ${devicesCount}
                    `;
                    document.getElementById('stats').style.display = 'block';
                } else {
                    document.getElementById('stats').style.display = 'none';
                }
            }
            
            filterMarkersByTime(maxTime) {
                this.markerCluster.clearLayers();
                
                this.markers.forEach(marker => {
                    if (!marker.data.time || new Date(marker.data.time).getTime() <= maxTime) {
                        this.markerCluster.addLayer(marker);
                    }
                });
            }
            
            focusOnDevice(deviceId) {
                const deviceInfo = this.devices.get(deviceId);
                if (!deviceInfo || deviceInfo.markers.length === 0) return;
                
                // Create feature group from device markers
                const group = new L.featureGroup(deviceInfo.markers);
                
                // Fit map to device markers
                this.map.fitBounds(group.getBounds().pad(0.1));
            }
            
            clearMarkers() {
                this.markerCluster.clearLayers();
                this.markers = [];
                this.devices.clear();
            }
            
            showAllMarkers() {
                this.markerCluster.clearLayers();
                this.markers.forEach(marker => {
                    this.markerCluster.addLayer(marker);
                });
            }
            
            fitAllMarkers() {
                if (this.markers.length > 0) {
                    const group = new L.featureGroup(this.markers);
                    this.map.fitBounds(group.getBounds().pad(0.1));
                }
            }
            
            setMapType(type) {
                // Would need additional tile layers for satellite/terrain
                console.log('Map type change not implemented in basic version');
            }
            
            zoomIn() {
                this.map.zoomIn();
            }
            
            zoomOut() {
                this.map.zoomOut();
            }
            
            onBoundsChange() {
                if (this.bridge) {
                    const bounds = this.map.getBounds();
                    this.bridge.on_bounds_change(
                        bounds.getSouth(),
                        bounds.getWest(),
                        bounds.getNorth(),
                        bounds.getEast()
                    );
                }
            }
        }
        
        // Initialize controller
        window.mapController = new MapController();
        
        // For standalone HTML exports, markers can be embedded
        const MARKERS_DATA = {{MARKERS_DATA}};
    </script>
</body>
</html>"""