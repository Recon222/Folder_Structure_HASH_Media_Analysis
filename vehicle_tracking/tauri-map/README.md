# Vehicle Tracking Map - Tauri Application

This is the Tauri-based map visualization component for the Vehicle Tracking System.

## Purpose

Replaces QWebEngineView to avoid CSS conflicts and improve performance while displaying vehicle tracking maps using either Mapbox or Leaflet.

## Architecture

```
Python Qt App → WebSocket → Tauri App (HTML/JS Map)
```

## Setup

### Prerequisites

1. Node.js and npm installed
2. Rust toolchain installed (for Tauri)
3. Python with websocket-server package

### Installation

```bash
# Install Node dependencies
npm install

# Build Tauri application
npm run build
```

## Development

```bash
# Run in development mode
npm run dev
```

## Communication Protocol

The app communicates via WebSocket on a configurable port (default: 8765).

### Message Types

**From Python to Tauri:**
- `load_vehicles`: Load vehicle tracking data
- `control`: Animation control (play/pause/stop)
- `switch_provider`: Switch between Mapbox/Leaflet

**From Tauri to Python:**
- `ready`: Map initialized
- `vehicle_clicked`: User clicked on a vehicle
- `error`: Error occurred

## Map Providers

- **Mapbox**: High-performance WebGL rendering (requires API key)
- **Leaflet**: Open-source alternative

## Files

- `src/index.html`: Router to select map provider
- `src/mapbox.html`: Mapbox GL JS implementation
- `src/leaflet.html`: Leaflet implementation
- `src-tauri/`: Rust/Tauri backend code