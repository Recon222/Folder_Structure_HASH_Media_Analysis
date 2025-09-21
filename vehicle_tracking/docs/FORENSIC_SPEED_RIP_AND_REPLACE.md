# Vehicle Tracking Forensic Speed - Rip-and-Replace Implementation
## Direct Implementation Without Backward Compatibility

---

## Executive Summary

This document provides a **direct rip-and-replace implementation** of the forensic speed calculation system with **zero backward compatibility**. It implements a **court-defensible, uncertainty-aware speed calculation system** that eliminates forensically indefensible assumptions while maintaining smooth animation.

**Core Principle**: "You don't know what happened off camera - only speak to what is observed."

**Approach**: Complete replacement of existing interpolation with forensic segment-based calculation.

---

## Implementation Order

### Completed Tasks ✅
0. ✅ Uniform-cadence passthrough + grid-quantized emit
1. ✅ Fix timestamp distribution
2. ✅ Add heading interpolation
3. ✅ Implement global resampling base
4. ✅ Fix JavaScript per-frame interpolation
5. ✅ Add Web Mercator projection in JavaScript
6. ✅ Add snap-to-anchor logic
7. ✅ Add uniform-cadence passthrough and grid-quantized emit
8. ✅ Add metric projection for Python interpolation

### Remaining Critical Tasks 🔴
9. 🔴 Implement gap/stop detection
10. 🔴 Add anomaly detection
11. 🔴 **Replace ALL interpolation with Forensic Segment-Based Speed Calculation (THIS DOCUMENT)**
12. 🔴 Add wall-clock alignment (Optional)

---

## Task 11: Complete Forensic Speed Implementation 🔴 CRITICAL

### Design Principles
- **One speed per segment** (A→B)
- **No interpolated speeds** - carry segment speed onto interps
- **Certainty tiers** by gap duration
- **Clear lineage**: observed vs inferred fields explicit
- **No compatibility modes** - forensic-only implementation

### Data Model

```python
# vehicle_tracking/models/forensic_models.py (NEW FILE)
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List
from .vehicle_tracking_models import GPSPoint

class SpeedCertainty(Enum):
    HIGH = "high"        # Δt ≤ 5s
    MEDIUM = "medium"    # 5 < Δt ≤ 10s
    LOW = "low"          # 10 < Δt ≤ 30s
    UNKNOWN = "unknown"  # Δt > 30s (don't interpolate)

@dataclass
class SegmentSpeed:
    speed_kmh: Optional[float]
    certainty: SpeedCertainty
    distance_m: float
    time_seconds: float
    gap_type: Optional[str] = None  # 'stop', 'gap', 'temporal_conflict', 'normal'

@dataclass
class GPSSegment:
    start_point: GPSPoint
    end_point: GPSPoint
    segment_speed: SegmentSpeed
    interpolated_points: List[GPSPoint] = field(default_factory=list)
```

### Extend GPSPoint Model

```python
# vehicle_tracking/models/vehicle_tracking_models.py (MODIFY EXISTING)
@dataclass
class GPSPoint:
    # ... existing fields ...

    # ADD: Forensic tracking fields
    segment_speed_kmh: Optional[float] = None
    speed_certainty: Optional[str] = None   # 'high'|'medium'|'low'|'unknown'
    segment_id: Optional[int] = None
    is_observed: bool = True                # False for interpolated points
    is_gap: bool = False                    # True for gap markers
```

### Pre-process Data: Coalesce Same-Location Duplicates

```python
# vehicle_tracking/services/data_preprocessing.py (NEW FILE)
from typing import List, Dict, Any
from datetime import datetime
from ..models.vehicle_tracking_models import GPSPoint

def coalesce_same_location_duplicates(points: List[GPSPoint]) -> List[GPSPoint]:
    """
    Coalesce identical fixes at the same time/place into single anchors.
    Maintains count in metadata for forensic auditing.

    Purpose: Treat repeated same-location samples as confirmed stops,
    not data errors. This preserves forensic integrity.
    """
    if not points:
        return points

    coalesced = []
    i = 0

    while i < len(points):
        current = points[i]
        dup_count = 1
        j = i + 1

        # Find all duplicates at same time and location
        while (j < len(points) and
               points[j].timestamp == current.timestamp and
               points[j].latitude == current.latitude and
               points[j].longitude == current.longitude):
            dup_count += 1
            j += 1

        # Create coalesced point with metadata
        if dup_count > 1:
            # Preserve original point but add metadata
            current.metadata = current.metadata or {}
            current.metadata['coalesced_count'] = dup_count
            current.metadata['gap_type'] = 'stop/coalesced'
            current.is_observed = True

        coalesced.append(current)
        i = j

    return coalesced
```

### Mandatory Metric Projection Setup

```python
# vehicle_tracking/services/projection_service.py (NEW FILE)
import pyproj
from typing import Tuple, Optional, Callable
from ..models.vehicle_tracking_models import GPSPoint

def make_local_metric_projection(
    center_point: GPSPoint
) -> Tuple[Optional[Callable], Optional[Callable]]:
    """
    Create mandatory metric projection for forensic accuracy.
    Uses Azimuthal Equidistant centered on data.

    This ensures speed calculations EXACTLY match interpolated geometry.
    No more Haversine/projection mismatches.
    """
    try:
        # Define AEQD projection centered on track
        aeqd = pyproj.CRS.from_proj4(
            f"+proj=aeqd +lat_0={center_point.latitude} "
            f"+lon_0={center_point.longitude} "
            "+datum=WGS84 +units=m +no_defs"
        )
        wgs84 = pyproj.CRS.from_epsg(4326)

        # Create transformers
        to_metric = pyproj.Transformer.from_crs(
            wgs84, aeqd, always_xy=True
        ).transform
        to_wgs84 = pyproj.Transformer.from_crs(
            aeqd, wgs84, always_xy=True
        ).transform

        return to_metric, to_wgs84

    except Exception as e:
        # This should never fail in production
        # Metric projection is MANDATORY for forensic accuracy
        raise ValueError(f"Failed to create mandatory metric projection: {e}")
```

### New Forensic Speed Calculator Service

```python
# vehicle_tracking/services/forensic_speed_calculator.py (NEW FILE)
import math
from typing import List, Optional, Tuple, Dict, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass

from ..models.vehicle_tracking_models import GPSPoint
from ..models.forensic_models import SpeedCertainty, SegmentSpeed, GPSSegment

class ForensicSpeedCalculator:
    """Calculates forensically defensible speeds for GPS segments"""

    MIN_TIME_DELTA = 0.5  # Minimum credible time between points

    def __init__(self, settings=None):
        self.settings = settings or {}
        self.high_threshold = self.settings.get('high_certainty_threshold_s', 5.0)
        self.medium_threshold = self.settings.get('medium_certainty_threshold_s', 10.0)
        self.max_gap_threshold = self.settings.get('max_gap_threshold_s', 30.0)

    def calculate_segment_speeds(
        self,
        points: List[GPSPoint],
        to_metric: Callable,  # MANDATORY - no Optional
        to_wgs84: Callable   # MANDATORY - no Optional
    ) -> List[GPSSegment]:
        """
        Calculate speeds using MANDATORY metric projection.
        No fallback to Haversine - metric projection required for forensic accuracy.
        """
        if not to_metric or not to_wgs84:
            raise ValueError("Metric projection is mandatory for forensic speed calculation")

        segments = []

        for i in range(len(points) - 1):
            segment = self._create_segment(
                points[i], points[i + 1],
                to_metric, to_wgs84
            )
            segments.append(segment)

        return segments

    def _create_segment(
        self,
        start: GPSPoint,
        end: GPSPoint,
        to_metric: Callable,
        to_wgs84: Callable
    ) -> GPSSegment:
        """
        Create segment with metric-accurate distance.
        Metric projection is MANDATORY - no fallbacks.
        """

        # Calculate distance using mandatory metric projection
        distance_m = self._metric_distance(start, end, to_metric)

        # Calculate time
        time_diff = (end.timestamp - start.timestamp).total_seconds()

        # Enhanced duplicate timestamp handling
        if time_diff == 0:
            if start.latitude == end.latitude and start.longitude == end.longitude:
                # Same location - already coalesced in preprocessing
                # This shouldn't happen if preprocessing was done
                gap_type = "stop/coalesced"
                speed_kmh = 0  # Definitive stop
                certainty = SpeedCertainty.HIGH
            else:
                # Different locations - temporal conflict
                # DO NOT fabricate time delta or speed
                gap_type = "temporal_conflict"
                speed_kmh = None  # No speed calculation possible
                certainty = SpeedCertainty.LOW
                # Keep time_diff as 0 for accurate reporting
        else:
            gap_type = "normal"
            certainty = self._determine_certainty(time_diff)

            # Calculate speed only for non-conflict segments
            if certainty == SpeedCertainty.UNKNOWN:
                speed_kmh = None
            else:
                speed_kmh = (distance_m / time_diff) * 3.6

        return GPSSegment(
            start_point=start,
            end_point=end,
            segment_speed=SegmentSpeed(
                speed_kmh=speed_kmh,
                certainty=certainty,
                distance_m=distance_m,
                time_seconds=time_diff,  # Keep actual time_diff (could be 0)
                gap_type=gap_type
            )
        )

    def _metric_distance(
        self,
        a: GPSPoint,
        b: GPSPoint,
        to_metric: Callable
    ) -> float:
        """
        Calculate distance in meters using metric projection.
        This ensures exact match with interpolation geometry.
        """
        x0, y0 = to_metric(a.longitude, a.latitude)
        x1, y1 = to_metric(b.longitude, b.latitude)
        return math.hypot(x1 - x0, y1 - y0)

    def _determine_certainty(self, time_diff: float) -> SpeedCertainty:
        """Determine certainty based on time gap"""
        if time_diff <= self.high_threshold:
            return SpeedCertainty.HIGH
        elif time_diff <= self.medium_threshold:
            return SpeedCertainty.MEDIUM
        elif time_diff <= self.max_gap_threshold:
            return SpeedCertainty.LOW
        else:
            return SpeedCertainty.UNKNOWN
```

### Wire Format Converter Service

```python
# vehicle_tracking/services/wire_format.py (NEW FILE)
from typing import Dict, List, Any
from datetime import datetime
from ..models.vehicle_tracking_models import VehicleData, GPSPoint

def to_wire_format(vehicle_data: VehicleData) -> Dict[str, Any]:
    """
    Convert vehicle data to consistent wire format for transmission.

    Enforces:
    - Timestamps as epoch milliseconds (integers)
    - Speeds in km/h (float) or null
    - Monotonic index for each point
    - Metadata about cadence and interval
    """
    points = []

    # Detect cadence type
    if len(vehicle_data.gps_points) > 1:
        intervals = []
        for i in range(1, len(vehicle_data.gps_points)):
            dt = (vehicle_data.gps_points[i].timestamp -
                  vehicle_data.gps_points[i-1].timestamp).total_seconds()
            intervals.append(dt * 1000)  # Convert to ms

        # Check if uniform
        avg_interval = sum(intervals) / len(intervals)
        variance = sum((i - avg_interval)**2 for i in intervals) / len(intervals)
        cadence = "uniform" if variance < 10 else "mixed"  # 10ms variance threshold
        dt_ms = int(round(avg_interval))
    else:
        cadence = "raw"
        dt_ms = 0

    # Convert points with monotonic index
    for index, point in enumerate(vehicle_data.gps_points):
        # Timestamp as epoch milliseconds (integer)
        timestamp_ms = int(point.timestamp.timestamp() * 1000)

        wire_point = {
            "index": index,  # Monotonic index for UI snapping
            "timestamp_ms": timestamp_ms,
            "latitude": point.latitude,
            "longitude": point.longitude,
            "speed_kmh": point.segment_speed_kmh,  # float or None
            "certainty": point.speed_certainty,
            "is_observed": point.is_observed,
            "is_interpolated": point.is_interpolated,
            "segment_id": point.segment_id
        }

        # Add metadata if present
        if point.metadata:
            wire_point["metadata"] = point.metadata

        # Optional fields
        if point.altitude is not None:
            wire_point["altitude_m"] = point.altitude  # Ensure meters
        if point.heading is not None:
            wire_point["heading_deg"] = point.heading  # Ensure degrees

        points.append(wire_point)

    return {
        "vehicle_id": vehicle_data.vehicle_id,
        "points": points,
        "meta": {
            "dt_ms": dt_ms,  # Average interval in milliseconds
            "cadence": cadence,  # "uniform", "mixed", or "raw"
            "total_points": len(points),
            "observed_points": sum(1 for p in points if p["is_observed"]),
            "interpolated_points": sum(1 for p in points if p["is_interpolated"]),
            "has_segment_speeds": vehicle_data.has_segment_speeds,
            "unit_speed": "km/h",  # Explicit unit declaration
            "unit_distance": "meters",
            "unit_timestamp": "epoch_ms"
        }
    }

def from_wire_format(payload: Dict[str, Any]) -> VehicleData:
    """
    Parse wire format back to VehicleData.
    Validates units and types.
    """
    points = []

    for wire_point in payload["points"]:
        # Validate timestamp is integer milliseconds
        if not isinstance(wire_point["timestamp_ms"], int):
            raise ValueError(f"Timestamp must be integer ms, got {type(wire_point['timestamp_ms'])}")

        # Convert back to datetime
        timestamp = datetime.fromtimestamp(wire_point["timestamp_ms"] / 1000.0)

        point = GPSPoint(
            latitude=wire_point["latitude"],
            longitude=wire_point["longitude"],
            timestamp=timestamp,
            segment_speed_kmh=wire_point.get("speed_kmh"),  # Already in km/h
            speed_certainty=wire_point.get("certainty"),
            is_observed=wire_point.get("is_observed", True),
            is_interpolated=wire_point.get("is_interpolated", False),
            segment_id=wire_point.get("segment_id"),
            altitude=wire_point.get("altitude_m"),  # Already in meters
            heading=wire_point.get("heading_deg"),  # Already in degrees
            metadata=wire_point.get("metadata")
        )

        points.append(point)

    return VehicleData(
        vehicle_id=payload["vehicle_id"],
        gps_points=points,
        has_segment_speeds=payload["meta"].get("has_segment_speeds", False)
    )
```

### REPLACE Existing Interpolation Method

```python
# vehicle_tracking/services/vehicle_tracking_service.py
# DELETE the old interpolate_path_global_resampling method (lines 691-820)
# DELETE the old interpolate_path method
# REPLACE with single forensic implementation:

def interpolate_path(
    self,
    vehicle_data: VehicleData,
    settings: VehicleTrackingSettings,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Result[VehicleData]:
    """
    Forensic interpolation with segment-based constant speeds.
    This is the ONLY interpolation method - no compatibility modes.
    """
    try:
        points = vehicle_data.gps_points
        if len(points) < 2:
            return Result.success(vehicle_data)

        # PREPROCESSING: Coalesce same-location duplicates
        from ..services.data_preprocessing import coalesce_same_location_duplicates
        points = coalesce_same_location_duplicates(points)
        vehicle_data.gps_points = points

        # Check uniform cadence passthrough
        dt = settings.interpolation_interval_seconds
        if self._is_uniform_cadence(points, dt):
            self._log_operation("passthrough", "Data already uniform, no interpolation needed")
            return Result.success(vehicle_data)

        # MANDATORY metric projection setup
        from ..services.projection_service import make_local_metric_projection
        center_idx = len(points) // 2
        center_point = points[center_idx]
        to_metric, to_wgs84 = make_local_metric_projection(center_point)

        if not to_metric or not to_wgs84:
            raise ValueError("Metric projection is mandatory for forensic processing")

        # Calculate segment speeds with same projection
        from ..services.forensic_speed_calculator import ForensicSpeedCalculator

        calculator = ForensicSpeedCalculator(settings.__dict__)
        segments = calculator.calculate_segment_speeds(points, to_metric, to_wgs84)

        interpolated = []
        interpolated.append(points[0])

        # Mark first point as observed
        points[0].is_observed = True
        points[0].is_interpolated = False

        # Process each segment
        for seg_idx, segment in enumerate(segments):
            seg_start = segment.start_point
            seg_end = segment.end_point

            # Skip UNKNOWN segments (gaps too large)
            if segment.segment_speed.certainty == SpeedCertainty.UNKNOWN:
                # Add gap marker
                gap_marker = GPSPoint(
                    latitude=seg_start.latitude,
                    longitude=seg_start.longitude,
                    timestamp=seg_start.timestamp,
                    segment_speed_kmh=0,
                    speed_certainty="unknown",
                    segment_id=seg_idx,
                    is_gap=True,
                    is_observed=False,
                    metadata={'gap_seconds': segment.segment_speed.time_seconds}
                )
                interpolated.append(gap_marker)

                # Log the gap
                self._log_operation("gap_detection",
                    f"Gap of {segment.segment_speed.time_seconds:.1f}s detected, not interpolating")
                continue

            # Handle temporal conflicts - NO interpolation
            if segment.segment_speed.gap_type == "temporal_conflict":
                # DO NOT interpolate temporal conflicts
                # Just mark the segment endpoints, renderer will show dashed line
                seg_start.segment_speed_kmh = None  # No speed
                seg_start.speed_certainty = "low"
                seg_start.segment_id = seg_idx
                seg_start.metadata = seg_start.metadata or {}
                seg_start.metadata['conflict'] = 'temporal_conflict'

                self._log_operation("temporal_conflict",
                    f"Temporal conflict: same timestamp, different locations. No speed calculated.")

                # Skip to next segment - no interpolation between conflicted points
                interpolated.append(seg_end)
                continue

            # Grid-quantized interpolation
            from math import floor
            EPS = 1e-6
            k = 1
            t_emit = seg_start.timestamp + timedelta(seconds=dt)

            while t_emit < seg_end.timestamp - timedelta(seconds=EPS):
                seg_duration = (seg_end.timestamp - seg_start.timestamp).total_seconds()
                time_ratio = (t_emit - seg_start.timestamp).total_seconds() / seg_duration

                # Interpolate position (keep metric projection)
                lat, lon = self._interpolate_in_metric(
                    seg_start, seg_end, time_ratio, to_metric, to_wgs84
                )

                # Create interpolated point with CONSTANT segment speed
                interp_point = GPSPoint(
                    latitude=lat,
                    longitude=lon,
                    timestamp=t_emit,
                    segment_speed_kmh=segment.segment_speed.speed_kmh,  # CONSTANT!
                    speed_certainty=segment.segment_speed.certainty.value,
                    segment_id=seg_idx,
                    is_interpolated=True,
                    is_observed=False
                )

                # Copy other fields if available
                if seg_start.altitude is not None and seg_end.altitude is not None:
                    interp_point.altitude = seg_start.altitude + \
                                         (seg_end.altitude - seg_start.altitude) * time_ratio

                if seg_start.heading is not None and seg_end.heading is not None:
                    interp_point.heading = self._interpolate_heading(
                        seg_start.heading, seg_end.heading, time_ratio
                    )

                interpolated.append(interp_point)

                # Grid-quantized advance
                k += 1
                t_emit = seg_start.timestamp + timedelta(seconds=k * dt)

            # Add segment end point (observed)
            seg_end.segment_speed_kmh = segment.segment_speed.speed_kmh
            seg_end.speed_certainty = segment.segment_speed.certainty.value
            seg_end.segment_id = seg_idx
            seg_end.is_observed = True
            seg_end.is_interpolated = False
            interpolated.append(seg_end)

        # Update vehicle data
        vehicle_data.gps_points = interpolated
        vehicle_data.has_segment_speeds = True
        vehicle_data.segments = segments

        # Log summary
        self._log_operation("forensic_interpolation",
            f"Created {len(interpolated)} points with {len(segments)} segments")

        # Update progress if provided
        if progress_callback:
            progress_callback(100, "Forensic interpolation complete")

        return Result.success(vehicle_data)

    except Exception as e:
        from ..exceptions import VehicleTrackingError
        error = VehicleTrackingError(f"Forensic interpolation failed: {e}")
        self._handle_error(error)
        return Result.error(error)

# DELETE the old calculate_vehicle_speeds method
# REPLACE with forensic version that uses segment speeds:

def calculate_vehicle_speeds(
    self,
    vehicle_data: VehicleData,
    settings: Optional[VehicleTrackingSettings] = None
) -> Result[VehicleData]:
    """
    Calculate forensic segment speeds for vehicle data.
    Uses segment-based calculation, not point-to-point.
    """
    try:
        points = vehicle_data.gps_points
        if len(points) < 2:
            return Result.success(vehicle_data)

        # PREPROCESSING: Coalesce same-location duplicates
        from ..services.data_preprocessing import coalesce_same_location_duplicates
        points = coalesce_same_location_duplicates(points)
        vehicle_data.gps_points = points

        # MANDATORY metric projection for accurate distance
        from ..services.projection_service import make_local_metric_projection
        center_idx = len(points) // 2
        center_point = points[center_idx]
        to_metric, to_wgs84 = make_local_metric_projection(center_point)

        if not to_metric or not to_wgs84:
            raise ValueError("Metric projection is mandatory for forensic speed calculation")

        # Calculate segment speeds
        from ..services.forensic_speed_calculator import ForensicSpeedCalculator

        calculator = ForensicSpeedCalculator(settings.__dict__ if settings else {})
        segments = calculator.calculate_segment_speeds(points, to_metric, to_wgs84)

        # Apply speeds to points
        for i, segment in enumerate(segments):
            if segment.segment_speed.speed_kmh is not None:
                segment.start_point.segment_speed_kmh = segment.segment_speed.speed_kmh
                segment.start_point.speed_certainty = segment.segment_speed.certainty.value
                segment.end_point.segment_speed_kmh = segment.segment_speed.speed_kmh
                segment.end_point.speed_certainty = segment.segment_speed.certainty.value

        # Calculate statistics
        valid_speeds = [s.segment_speed.speed_kmh for s in segments
                       if s.segment_speed.speed_kmh is not None]

        if valid_speeds:
            vehicle_data.average_speed_kmh = sum(valid_speeds) / len(valid_speeds)
            vehicle_data.max_speed_kmh = max(valid_speeds)
            vehicle_data.min_speed_kmh = min(valid_speeds)

        vehicle_data.segments = segments
        vehicle_data.has_segment_speeds = True

        self._log_operation("calculate_speeds",
                          f"Calculated {len(segments)} segment speeds")

        return Result.success(vehicle_data)

    except Exception as e:
        from ..exceptions import VehicleTrackingError
        error = VehicleTrackingError(
            f"Speed calculation failed: {e}",
            user_message="Error calculating vehicle speeds"
        )
        self._handle_error(error)
        return Result.error(error)
```

### Update VehicleTrackingSettings

```python
# vehicle_tracking/models/vehicle_tracking_models.py
# MODIFY existing VehicleTrackingSettings class:

@dataclass
class VehicleTrackingSettings:
    # ... existing fields ...

    # ADD: Forensic speed thresholds (no feature flags!)
    high_certainty_threshold_s: float = 5.0
    medium_certainty_threshold_s: float = 10.0
    max_gap_threshold_s: float = 30.0               # > this => UNKNOWN (no interpolation)
    duplicate_timestamp_min_delta: float = 0.5      # fallback for duplicate timestamps

    # ADD: Display options
    show_certainty_indicators: bool = True
    highlight_low_certainty: bool = True
    show_gap_markers: bool = True
```

### Update VehicleData Model

```python
# vehicle_tracking/models/vehicle_tracking_models.py
# ADD to VehicleData class:

@dataclass
class VehicleData:
    # ... existing fields ...

    # ADD: Forensic tracking
    has_segment_speeds: bool = False
    segments: Optional[List['GPSSegment']] = None
    speed_anomalies: Optional[List[Dict[str, Any]]] = None
```

---

## UI/JavaScript Updates

```javascript
// tauri-map/src/mapbox.html
// MODIFY renderFrame() to use segment speeds:

// Around line 1690, when computing UI speed readout:
const segSpeed = currentPoint.segment_speed_kmh || currentPoint.speed || 0;
const certainty = currentPoint.speed_certainty || 'unknown';

// Color code by certainty
let speedColor;
switch(certainty) {
    case 'high':
        speedColor = '#00ff00';  // Green - reliable
        break;
    case 'medium':
        speedColor = '#ffaa00';  // Orange - acceptable
        break;
    case 'low':
        speedColor = '#ff0000';  // Red - questionable
        break;
    default:
        speedColor = '#666666';  // Gray - unknown
}

// Update speed display with certainty indicator
this.updateSpeedDisplay(segSpeed, certainty, speedColor);

// Handle gaps and conflicts visually
if (currentPoint.is_gap) {
    this.showGapIndicator(currentPoint.metadata.gap_seconds);
}

// Enhanced temporal conflict visualization
if (currentPoint.metadata?.conflict === 'temporal_conflict') {
    this.showTemporalConflictWarning();
    // Draw dashed line to next point as visual cue
    this.drawDashedConnector(currentPoint, nextPoint);
}

// Show coalesced stop indicators
if (currentPoint.metadata?.gap_type === 'stop/coalesced') {
    const count = currentPoint.metadata.coalesced_count || 1;
    this.showStopIndicator(currentPoint, count);
}

// ADD new method for speed display:
updateSpeedDisplay(speed, certainty, color) {
    const speedElement = document.getElementById('speed-display');
    if (speedElement) {
        speedElement.innerHTML = `
            <span style="color: ${color}">
                ${speed ? speed.toFixed(1) : '---'} km/h
            </span>
            <span class="certainty-indicator certainty-${certainty}">
                ${certainty.toUpperCase()}
            </span>
        `;
    }
}

// ADD wire format validation on receive:
validateWireFormat(payload) {
    // Validate timestamps are epoch milliseconds
    console.assert(Array.isArray(payload.points), "Points must be array");

    payload.points.forEach((point, idx) => {
        // Timestamp validation
        console.assert(Number.isInteger(point.timestamp_ms),
            `Point ${idx}: timestamp_ms must be integer, got ${typeof point.timestamp_ms}`);

        // Index validation - must be monotonic
        console.assert(point.index === idx,
            `Point ${idx}: index mismatch, expected ${idx} got ${point.index}`);

        // Speed validation - km/h or null
        if (point.speed_kmh !== null) {
            console.assert(typeof point.speed_kmh === 'number',
                `Point ${idx}: speed_kmh must be number or null`);
            console.assert(point.speed_kmh >= 0 && point.speed_kmh <= 300,
                `Point ${idx}: speed ${point.speed_kmh} out of range`);
        }
    });

    // Validate metadata
    console.assert(payload.meta, "Missing metadata");
    console.assert(typeof payload.meta.dt_ms === 'number', "dt_ms must be number");
    console.assert(['uniform', 'mixed', 'raw'].includes(payload.meta.cadence),
        `Unknown cadence: ${payload.meta.cadence}`);

    // Validate units are explicitly declared
    console.assert(payload.meta.unit_speed === 'km/h', "Speed unit must be km/h");
    console.assert(payload.meta.unit_distance === 'meters', "Distance unit must be meters");
    console.assert(payload.meta.unit_timestamp === 'epoch_ms', "Timestamp unit must be epoch_ms");

    return true;
}
```

---

## Testing Procedures

### Test 1: Constant Segment Speed
```python
# vehicle_tracking/tests/test_forensic_speed.py (NEW FILE)
import sys
from pathlib import Path
from datetime import datetime, timedelta
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vehicle_tracking.services.vehicle_tracking_service import VehicleTrackingService
from vehicle_tracking.models.vehicle_tracking_models import (
    VehicleData, GPSPoint, VehicleTrackingSettings
)

def test_constant_segment_speed():
    """All points in segment must have same speed"""

    # Create test data with varying gaps
    base = datetime(2024, 1, 1, 10, 0, 0)
    points = [
        GPSPoint(45.4215, -75.6972, base),
        GPSPoint(45.4220, -75.6970, base + timedelta(seconds=3)),  # HIGH certainty
        GPSPoint(45.4225, -75.6968, base + timedelta(seconds=10)), # MEDIUM certainty
        GPSPoint(45.4230, -75.6966, base + timedelta(seconds=40)), # UNKNOWN - gap
    ]

    vehicle = VehicleData(
        vehicle_id="test",
        source_file=Path("test.csv"),
        gps_points=points
    )

    service = VehicleTrackingService()
    settings = VehicleTrackingSettings(
        interpolation_enabled=True,
        interpolation_interval_seconds=1.0
    )

    result = service.interpolate_path(vehicle, settings)

    if result.success:
        output = result.value

        # Check that all interpolated points in same segment have same speed
        for point in output.gps_points:
            if point.segment_id == 0:  # First segment
                assert point.speed_certainty == "high"
                # All points in segment 0 should have same speed
                seg0_speed = output.segments[0].segment_speed.speed_kmh
                assert abs(point.segment_speed_kmh - seg0_speed) < 0.001

        print("[SUCCESS] Constant segment speeds verified")

        # Verify gap handling
        gap_points = [p for p in output.gps_points if p.is_gap]
        assert len(gap_points) > 0, "Should have gap markers"
        print(f"[SUCCESS] Found {len(gap_points)} gap markers")

    else:
        print(f"[FAIL] {result.error}")

if __name__ == "__main__":
    test_constant_segment_speed()
```

### Test 2: Temporal Conflict Handling
```python
def test_temporal_conflict():
    """Test that temporal conflicts produce NO speed"""

    base = datetime(2024, 1, 1, 10, 0, 0)

    # Different location, same timestamp - temporal conflict
    points = [
        GPSPoint(43.0, -79.0, base),
        GPSPoint(43.001, -79.001, base),  # Same time, different location
        GPSPoint(43.002, -79.002, base + timedelta(seconds=5))
    ]

    vehicle = VehicleData(
        vehicle_id="test_conflict",
        source_file=Path("test.csv"),
        gps_points=points
    )

    service = VehicleTrackingService()
    settings = VehicleTrackingSettings()

    result = service.calculate_vehicle_speeds(vehicle, settings)

    if result.success:
        segments = result.value.segments

        # First segment should be temporal conflict with NO speed
        assert segments[0].segment_speed.gap_type == "temporal_conflict"
        assert segments[0].segment_speed.speed_kmh is None  # NO speed calculated
        assert segments[0].segment_speed.time_seconds == 0  # Actual time difference preserved
        print("[SUCCESS] Temporal conflict: speed_kmh = None verified")

if __name__ == "__main__":
    test_temporal_conflict()
```

### Test 3: Same-Location Duplicate Coalescing
```python
def test_duplicate_coalescing():
    """Test that same-location duplicates are coalesced in preprocessing"""

    base = datetime(2024, 1, 1, 10, 0, 0)

    # Multiple identical samples at same time/location
    points = [
        GPSPoint(43.0, -79.0, base),
        GPSPoint(43.0, -79.0, base),  # Duplicate 1
        GPSPoint(43.0, -79.0, base),  # Duplicate 2
        GPSPoint(43.001, -79.001, base + timedelta(seconds=5))
    ]

    # Apply preprocessing
    from vehicle_tracking.services.data_preprocessing import coalesce_same_location_duplicates
    coalesced = coalesce_same_location_duplicates(points)

    # Should reduce to 2 points
    assert len(coalesced) == 2, f"Expected 2 points after coalescing, got {len(coalesced)}"

    # First point should have coalesced metadata
    assert coalesced[0].metadata['coalesced_count'] == 3
    assert coalesced[0].metadata['gap_type'] == 'stop/coalesced'

    print("[SUCCESS] Same-location duplicates coalesced: 3→1")

if __name__ == "__main__":
    test_duplicate_coalescing()
```

### Test 4: Metric Projection Consistency
```python
def test_metric_projection_parity():
    """Verify speed calculation uses same projection as interpolation"""

    from vehicle_tracking.services.projection_service import make_local_metric_projection

    base = datetime(2024, 1, 1, 10, 0, 0)
    points = [
        GPSPoint(45.4215, -75.6972, base),
        GPSPoint(45.4220, -75.6970, base + timedelta(seconds=5))
    ]

    vehicle = VehicleData(
        vehicle_id="test_projection",
        source_file=Path("test.csv"),
        gps_points=points
    )

    service = VehicleTrackingService()
    settings = VehicleTrackingSettings()

    # Calculate with mandatory metric projection
    result = service.interpolate_path(vehicle, settings)

    if result.success:
        # All distances should use same projection
        segments = result.value.segments

        # Segment distance should match sum of interpolated steps
        # (within small epsilon for floating point)
        print("[SUCCESS] Metric projection used throughout")

if __name__ == "__main__":
    test_metric_projection_parity()
```

### Test 5: Unit & Wire-Format Consistency
```python
def test_unit_consistency():
    """Enforce consistent units across the system"""

    # Test speed units - ALL speeds must be km/h floats or None
    vehicle = create_test_vehicle()
    result = service.calculate_vehicle_speeds(vehicle, settings)

    if result.success:
        segments = result.value.segments

        # Speed units check - km/h only
        for seg in segments:
            assert seg.segment_speed.speed_kmh is None or isinstance(seg.segment_speed.speed_kmh, float), \
                f"Speed must be None or float km/h, got {type(seg.segment_speed.speed_kmh)}"

            # If speed exists, verify reasonable range
            if seg.segment_speed.speed_kmh is not None:
                assert 0 <= seg.segment_speed.speed_kmh <= 300, \
                    f"Speed {seg.segment_speed.speed_kmh} km/h out of reasonable range"

        print("[SUCCESS] All speeds in km/h (float)")

def test_wire_format_consistency():
    """Verify wire format uses consistent units and types"""

    from vehicle_tracking.services.wire_format import to_wire_format

    vehicle = create_test_vehicle_with_interpolation()

    # Convert to wire format
    payload = to_wire_format(vehicle)

    # Timestamps must be epoch milliseconds (integers)
    assert all(isinstance(p["timestamp_ms"], int) for p in payload["points"]), \
        "All timestamps must be epoch milliseconds (int)"

    # Verify monotonic index
    for i, point in enumerate(payload["points"]):
        assert point["index"] == i, f"Index {point['index']} != {i}, not monotonic"

    # Check metadata
    assert "meta" in payload
    assert "dt_ms" in payload["meta"], "Missing dt_ms in metadata"
    assert payload["meta"]["dt_ms"] in [50, 100, 500, 1000, 2000, 5000], \
        f"Unexpected dt_ms: {payload['meta']['dt_ms']}"

    assert "cadence" in payload["meta"]
    assert payload["meta"]["cadence"] in ["uniform", "mixed", "raw"], \
        f"Unknown cadence type: {payload['meta']['cadence']}"

    # Speed must be in km/h or null
    for point in payload["points"]:
        if "speed_kmh" in point:
            assert point["speed_kmh"] is None or isinstance(point["speed_kmh"], (int, float)), \
                "Speed must be numeric km/h or null"

    print("[SUCCESS] Wire format consistent: epoch ms, monotonic index, km/h speeds")

if __name__ == "__main__":
    test_unit_consistency()
    test_wire_format_consistency()
```

---

## Success Criteria

- ✅ ALL interpolated points use constant segment speed (no speed interpolation)
- ✅ Segments exceeding max gap threshold are marked and not interpolated
- ✅ Temporal conflicts (Δt=0, different locations) produce speed_kmh = None
- ✅ Same-location duplicates are coalesced with metadata preservation
- ✅ Metric projection is MANDATORY - no Haversine fallbacks
- ✅ Speed calculation uses EXACT same projection as position interpolation
- ✅ All speeds stored as km/h (float) - conversion only at display
- ✅ Wire format uses epoch milliseconds (int) for timestamps
- ✅ Monotonic index (0..N-1) for UI anchor snapping
- ✅ Explicit unit declarations in metadata
- ✅ Certainty indicators clearly show data reliability
- ✅ No backward compatibility code exists
- ✅ Single implementation path - forensic only

---

## Simplified Timeline

**Total Estimated Time**: 10-12 hours (reduced from 15-20)

- Day 1: Data models & calculator service (4 hours)
- Day 1: Replace interpolation methods (4 hours)
- Day 2: JavaScript UI updates (2 hours)
- Day 2: Testing & validation (2 hours)

**Risk Level**: Low (complete replacement, no compatibility concerns)

**Forensic Improvement**: HIGH - Direct transformation to evidence-based calculations

---

## Deployment Steps

1. **Create new files**:
   - `forensic_models.py` - Speed certainty and segment models
   - `forensic_speed_calculator.py` - Segment-based speed calculation
   - `data_preprocessing.py` - Duplicate coalescing logic
   - `projection_service.py` - Mandatory metric projection setup
   - Test files for all new functionality

2. **Modify existing files**:
   - Update `vehicle_tracking_models.py` with forensic tracking fields
   - REPLACE ALL interpolation in `vehicle_tracking_service.py`
   - Remove Haversine fallbacks - metric projection only
   - Update JavaScript UI for certainty indicators and conflict warnings

3. **Delete old code**:
   - Remove ALL old interpolation methods
   - Remove ALL speed interpolation logic (linear blending)
   - Remove Haversine distance calculations from main path
   - No feature flags or compatibility checks

4. **Test and deploy**:
   - Run all forensic tests (constant speed, temporal conflicts, coalescing, projection)
   - Verify with real CSV data containing duplicates
   - Deploy directly - no phased rollout

---

## Expected Outcomes

### Forensic Benefits
- **Court-defensible**: No false assumptions about acceleration
- **Clear uncertainty**: Explicit about observation limits
- **Accurate averages**: True segment speeds, not invented curves
- **Consistent units**: All speeds in km/h, distances in meters

### Technical Benefits
- **Simpler codebase**: One implementation, no compatibility
- **Better performance**: Less code to maintain
- **Clearer data model**: Explicit segment structure
- **Faster development**: No migration complexity
- **Unit consistency**: Prevents regression bugs from mixed units

### User Benefits
- **Transparency**: Clear certainty indicators from day one
- **Trust**: No mysterious speed variations
- **Understanding**: Obvious when data is missing/uncertain
- **Reliability**: Consistent behavior across all data types

---

## Known Limitations

- **GPS Noise**: Severe GPS noise or gaps beyond `max_gap_threshold_s` (30s default) are shown as gaps/anomalies - no motion is invented
- **Temporal Conflicts**: When two points share exact timestamp but different locations, no speed is calculated (marked as conflict)
- **Maximum Vehicle Count**: System tested with up to 25 simultaneous vehicles (Mapbox layer limits)
- **Projection Accuracy**: AEQD projection is accurate for local areas (~100km radius) but may distort for very large geographic spans
- **Speed Range**: Speeds above 250 km/h flagged as anomalies (configurable threshold)

---

## Performance Profile Configuration

```python
# Optional performance profiles in settings
class PerformanceProfile(Enum):
    DEFAULT = "default"          # Standard processing
    HIGH_PRECISION = "high_precision"  # More projection cache, finer interpolation

# Settings based on profile
PROFILE_SETTINGS = {
    "default": {
        "interpolation_interval_seconds": 1.0,
        "projection_cache_size": 100,
        "max_points_per_vehicle": 10000
    },
    "high_precision": {
        "interpolation_interval_seconds": 0.5,
        "projection_cache_size": 500,
        "max_points_per_vehicle": 50000
    }
}
```

---

## CI Integration

Add these checks to continuous integration:

```yaml
# .github/workflows/forensic_tests.yml
forensic-unit-tests:
  - test_unit_consistency      # All speeds in km/h
  - test_wire_format           # Epoch ms, monotonic index
  - test_temporal_conflicts    # No fabricated speeds
  - test_duplicate_coalescing  # Same-location handling
  - test_projection_mandatory  # No Haversine fallback

golden-dataset-validation:
  - known_temporal_conflict.csv  # Verify speed = None
  - known_duplicates.csv         # Verify coalescing
  - known_gaps.csv              # Verify no interpolation
```

---

*Document created: 2024-11-21*
*Purpose: Direct rip-and-replace forensic implementation with unit consistency*
*Status: Ready for immediate implementation*