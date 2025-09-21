# Vehicle Tracking Forensic Speed - Unified Implementation Plan
## Complete Architecture with GPT-5 Enhancements

---

## Executive Summary

This document unifies the forensic speed calculation refactor with advanced optimizations from GPT-5's analysis. It provides a **court-defensible, uncertainty-aware speed calculation system** that eliminates forensically indefensible assumptions while maintaining smooth animation.

**Core Principle**: "You don't know what happened off camera - only speak to what is observed."

**Integration Note:** This refactor coordinates with the main interpolation plan as **Task 11** and includes UI wiring for constant segment speeds and certainty indicators. See *Vehicle Tracking Interpolation – Complete Implementation Plan* for rollout checkpoints.

---

## Implementation Order

### Completed Tasks ✅
0. ✅ Uniform-cadence passthrough + grid-quantized emit (NEW)
1. ✅ Fix timestamp distribution (DONE - Python)
2. ✅ Add heading interpolation (DONE - Python)
3. ✅ Implement global resampling (DONE - Python)
4. ✅ Fix JavaScript per-frame interpolation (DONE - JavaScript)
5. ✅ Add Web Mercator projection in JavaScript (DONE - JavaScript)
6. ✅ Add snap-to-anchor logic (DONE - JavaScript)
7. ✅ Add uniform-cadence passthrough and grid-quantized emit (DONE - Python)
8. ✅ Add metric projection for Python interpolation (DONE - Python)

### Remaining Critical Tasks 🔴
9. 🔴 Implement gap/stop detection in Python
10. 🔴 Add anomaly detection in Python
11. 🔴 **Forensic Segment-Based Speed Calculation (CRITICAL NEW)**
12. 🔴 Add wall-clock alignment (Optional)

---

## Task 0: Uniform-Cadence Passthrough & Grid-Quantized Emit ✅

### Problem
When CSV already has perfect 1-second cadence, interpolator wastes CPU and may create redundant points.

### Implementation

```python
def is_uniform_cadence(ts, dt=1.0, tol=1e-3):
    if len(ts) < 2: return True
    base = ts[0]
    return all(abs((base + i*dt) - t) <= tol for i, t in enumerate(ts))

# At top of interpolate_path_global_resampling:
timestamps = [p.timestamp for p in vehicle_data.gps_points]
if is_uniform_cadence(timestamps, settings.interpolation_interval_seconds):
    return Result.success(vehicle_data)  # passthrough; no interps
```

### Grid-Quantize Emit Times
```python
EPS = 1e-6
# Quantize t_emit to exact grid relative to segment start
k = math.floor((t_emit - seg_start.timestamp)/dt + EPS)
t_emit = seg_start.timestamp + k*dt

# Emit strictly before next real point
while t_emit < seg_end.timestamp - EPS:
    # ... interpolate & append interp point ...
    k += 1
    t_emit = seg_start.timestamp + k*dt
```

---

## Task 11: Forensic Segment-Based Speed Calculation 🔴 CRITICAL

### Design Principles
- **One speed per segment** (A→B)
- **No interpolated speeds** - carry segment speed onto interps
- **Certainty tiers** by gap duration
- **Clear lineage**: observed vs inferred fields explicit

### Data Model

```python
# vehicle_tracking/models/forensic_models.py (NEW)
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
# vehicle_tracking/models/vehicle_tracking_models.py
@dataclass
class GPSPoint:
    # ... existing fields ...

    # Forensic tracking fields
    segment_speed_kmh: Optional[float] = None
    speed_certainty: Optional[str] = None   # 'high'|'medium'|'low'|'unknown'
    segment_id: Optional[int] = None
    is_observed: bool = True                # False for interpolated points
```

### Segment Speed Calculator

```python
# vehicle_tracking/services/forensic_speed_calculator.py (NEW)
class ForensicSpeedCalculator:
    """Calculates forensically defensible speeds for GPS segments"""

    MIN_TIME_DELTA = 0.5  # Minimum credible time between points

    def calculate_segment_speeds(
        self,
        points: List[GPSPoint],
        to_metric: Optional[Transformer] = None,
        to_wgs84: Optional[Transformer] = None
    ) -> List[GPSSegment]:
        """Calculate speeds using same metric projection as interpolation"""
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
        to_metric: Optional[Transformer],
        to_wgs84: Optional[Transformer]
    ) -> GPSSegment:
        """Create segment with metric-accurate distance"""

        # Calculate distance in same projection as interpolation
        if to_metric:
            x1, y1 = to_metric.transform(start.longitude, start.latitude)
            x2, y2 = to_metric.transform(end.longitude, end.latitude)
            distance_m = math.hypot(x2 - x1, y2 - y1)
        else:
            distance_m = self._haversine_distance(start, end) * 1000

        # Calculate time
        time_diff = (end.timestamp - start.timestamp).total_seconds()

        # Duplicate timestamp handling
        if time_diff == 0:
            if start.latitude == end.latitude and start.longitude == end.longitude:
                # Same location - coalesce
                gap_type = "coalesced"
                time_diff = self.MIN_TIME_DELTA
                certainty = SpeedCertainty.HIGH
            else:
                # Different locations - temporal conflict
                gap_type = "temporal_conflict"
                certainty = SpeedCertainty.LOW
                time_diff = self.MIN_TIME_DELTA
        else:
            gap_type = "normal"
            certainty = self._determine_certainty(time_diff)

        # Calculate speed
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
                time_seconds=time_diff,
                gap_type=gap_type
            )
        )

    def _determine_certainty(self, time_diff: float) -> SpeedCertainty:
        """Determine certainty based on time gap"""
        if time_diff <= 5:
            return SpeedCertainty.HIGH
        elif time_diff <= 10:
            return SpeedCertainty.MEDIUM
        elif time_diff <= 30:
            return SpeedCertainty.LOW
        else:
            return SpeedCertainty.UNKNOWN
```

### Modified Interpolation

```python
def interpolate_path_global_resampling_forensic(
    self,
    vehicle_data: VehicleData,
    settings: VehicleTrackingSettings,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Result[VehicleData]:
    """Global resampling with forensic segment speeds"""
    try:
        points = vehicle_data.gps_points
        if len(points) < 2:
            return Result.success(vehicle_data)

        # Check uniform cadence passthrough
        timestamps = [p.timestamp for p in points]
        dt = settings.interpolation_interval_seconds
        if is_uniform_cadence(timestamps, dt):
            self._log_operation("passthrough", "Data already uniform, no interpolation needed")
            return Result.success(vehicle_data)

        # Get metric projection (same as interpolation uses)
        center_idx = len(points) // 2
        center_lat = points[center_idx].latitude
        center_lon = points[center_idx].longitude
        to_metric, to_wgs84 = self._get_metric_transformer(center_lat, center_lon)

        # Calculate segment speeds with same projection
        calculator = ForensicSpeedCalculator()
        segments = calculator.calculate_segment_speeds(points, to_metric, to_wgs84)

        interpolated = []
        interpolated.append(points[0])

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
                    metadata={'gap_seconds': segment.segment_speed.time_seconds}
                )
                interpolated.append(gap_marker)
                continue

            # Skip temporal conflicts
            if segment.segment_speed.gap_type == "temporal_conflict":
                conflict_marker = GPSPoint(
                    latitude=seg_start.latitude,
                    longitude=seg_start.longitude,
                    timestamp=seg_start.timestamp,
                    segment_speed_kmh=segment.segment_speed.speed_kmh,
                    speed_certainty="low",
                    segment_id=seg_idx,
                    metadata={'conflict': 'temporal_conflict'}
                )
                interpolated.append(conflict_marker)
                continue

            # Grid-quantized interpolation
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

                interpolated.append(interp_point)

                # Grid-quantized advance
                k += 1
                t_emit = seg_start.timestamp + timedelta(seconds=k * dt)

            # Add segment end point
            seg_end.segment_speed_kmh = segment.segment_speed.speed_kmh
            seg_end.speed_certainty = segment.segment_speed.certainty.value
            seg_end.segment_id = seg_idx
            interpolated.append(seg_end)

        # Update vehicle data
        vehicle_data.gps_points = interpolated
        vehicle_data.has_segment_speeds = True
        vehicle_data.segments = segments

        return Result.success(vehicle_data)

    except Exception as e:
        error = VehicleTrackingError(f"Forensic interpolation failed: {e}")
        return Result.error(error)
```

---

## UI/JavaScript Updates

```javascript
// In renderFrame(), when computing UI speed readout:
const segSpeed = currentPoint.segment_speed_kmh;       // constant per segment
const certainty = currentPoint.speed_certainty;        // 'high'|'medium'|'low'|'unknown'

// Color code by certainty
let speedColor;
switch(certainty) {
    case 'high':
        speedColor = '#00ff00';  // Green
        break;
    case 'medium':
        speedColor = '#ffaa00';  // Orange
        break;
    case 'low':
        speedColor = '#ff0000';  // Red
        break;
    default:
        speedColor = '#666666';  // Gray
}

ui.updateSpeed(segSpeed, certainty, speedColor);

// Optional: visual instantaneous speed (for UI only, not persisted)
if (prevFrame && currentFrame) {
    const dx = currentFrame.x - prevFrame.x;
    const dy = currentFrame.y - prevFrame.y;
    const m = Math.hypot(dx, dy);
    const dt = (currentFrame.t - prevFrame.t) / 1000;
    const visualKph = dt > 0 ? (m / dt) * 3.6 : 0;
    ui.updateVisualSpeed(visualKph); // label as "visual"
}

// Handle gaps and conflicts
if (currentPoint.is_gap) {
    ui.showGapIndicator(currentPoint.metadata.gap_seconds);
}
if (currentPoint.metadata?.conflict === 'temporal_conflict') {
    ui.showConflictWarning();
}
```

---

## Configuration

```yaml
# Feature-flagged forensic speed calculation
use_forensic_speed_calculation: false   # default off; enable after validation
high_certainty_threshold_s: 5.0
medium_certainty_threshold_s: 10.0
max_gap_threshold_s: 30.0               # > this => UNKNOWN (no interpolation)
duplicate_timestamp_min_delta: 0.5      # fallback for duplicate timestamps

# Display options
show_certainty_indicators: true
highlight_low_certainty: true
show_gap_markers: true
show_visual_speed: false                # optional instantaneous speed
```

---

## Testing Procedures

### Test 0: 1 Hz Passthrough
```python
def test_uniform_cadence_passthrough():
    """1 Hz CSV should pass through unchanged"""
    # Load known 1 Hz CSV
    result = service.interpolate_path(uniform_1hz_data, settings)

    # Assert no interpolation occurred
    assert len(result.value.gps_points) == len(uniform_1hz_data.gps_points)
    assert all(not p.is_interpolated for p in result.value.gps_points)
```

### Test 11.1: Constant Segment Speed
```python
def test_constant_segment_speed():
    """All points in segment have same speed"""
    # For segment with Δt=3s
    segment = segments[0]

    # Every interpolated point inherits segment speed
    for point in interpolated_points:
        if point.segment_id == 0:
            assert point.segment_speed_kmh == segment.segment_speed.speed_kmh
```

### Test 11.2: Unknown Gap Handling
```python
def test_unknown_gap():
    """Large gaps should not be interpolated"""
    # Points 45s apart
    points = [
        GPSPoint(43.0, -79.0, datetime(2024, 1, 1, 10, 0, 0)),
        GPSPoint(43.001, -79.001, datetime(2024, 1, 1, 10, 0, 45))
    ]

    result = calculate_segments(points)
    assert result[0].segment_speed.certainty == SpeedCertainty.UNKNOWN

    # No interpolated points should exist
    interpolated = interpolate_forensic(points)
    assert len(interpolated) == 3  # start, gap_marker, end
```

### Test 11.3: Duplicate Timestamp Handling
```python
def test_duplicate_timestamps():
    """Duplicate timestamps handled correctly"""

    # Same location - should coalesce
    points_same = [
        GPSPoint(43.0, -79.0, datetime(2024, 1, 1, 10, 0, 0)),
        GPSPoint(43.0, -79.0, datetime(2024, 1, 1, 10, 0, 0))
    ]
    segment = calculate_segment(points_same[0], points_same[1])
    assert segment.gap_type == "coalesced"
    assert segment.speed_kmh != 0  # Uses MIN_TIME_DELTA

    # Different location - temporal conflict
    points_diff = [
        GPSPoint(43.0, -79.0, datetime(2024, 1, 1, 10, 0, 0)),
        GPSPoint(43.001, -79.001, datetime(2024, 1, 1, 10, 0, 0))
    ]
    segment = calculate_segment(points_diff[0], points_diff[1])
    assert segment.gap_type == "temporal_conflict"
    assert segment.certainty == SpeedCertainty.LOW
```

### Test 11.4: Projection Parity
```python
def test_projection_parity():
    """Speed calculation uses same projection as interpolation"""
    # Distance for speed should match interpolated traversal
    segment_distance = segment.segment_speed.distance_m

    # Sum interpolated point-to-point distances
    interp_distance = sum(
        distance(p1, p2) for p1, p2 in zip(interps[:-1], interps[1:])
    )

    # Should match within epsilon (1%)
    assert abs(segment_distance - interp_distance) / segment_distance < 0.01
```

---

## Success Criteria

- ✅ 1 Hz CSV inputs pass through with zero interpolated points (NEW)
- ✅ Within each observed segment A→B, all displayed speeds are the constant segment average
- ✅ No speed interpolation is used (forensically defensible)
- ✅ Segments exceeding max gap threshold are marked and not interpolated
- ✅ Duplicate-timestamp conflicts are flagged appropriately
- ✅ Speed calculation uses same metric projection as position interpolation
- ✅ Certainty indicators clearly show data reliability
- ✅ Visual speed (if shown) is clearly labeled as non-forensic

---

## Migration Strategy

### Phase 1: Feature Flag Implementation
- Add `use_forensic_speed_calculation` flag (default false)
- Implement parallel to existing system

### Phase 2: Validation
- A/B testing with known routes
- Compare forensic vs interpolated speeds
- Verify court defensibility

### Phase 3: Gradual Rollout
- Enable for test users
- Monitor feedback
- Refine thresholds

### Phase 4: Full Deployment
- Make default
- Keep old method as fallback
- Document for legal teams

---

## Expected Outcomes

### Forensic Benefits
- **Court-defensible**: No false assumptions about acceleration
- **Clear uncertainty**: Explicit about observation limits
- **Accurate averages**: True segment speeds, not invented curves

### Technical Benefits
- **Simpler logic**: One speed per segment
- **Better performance**: Less calculation during interpolation
- **Clearer data model**: Explicit segment structure
- **Projection consistency**: Speed matches visual motion

### User Benefits
- **Transparency**: Clear certainty indicators
- **Trust**: No mysterious speed variations
- **Understanding**: Obvious when data is missing/uncertain

---

## Timeline

**Total Estimated Time**: 15-20 hours development + 5 hours testing

- Week 1: Data model & calculator (8 hours)
- Week 2: Interpolation refactor & UI (8 hours)
- Week 3: Testing & validation (5 hours)

**Risk Level**: Medium (significant refactor but well-isolated)

**Forensic Improvement**: HIGH - Transforms assumptions to evidence-based calculations