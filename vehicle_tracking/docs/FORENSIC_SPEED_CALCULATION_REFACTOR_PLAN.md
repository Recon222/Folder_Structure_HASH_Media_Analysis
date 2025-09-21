# Forensic Speed Calculation Refactor Plan
## Critical Issues & Comprehensive Solution Architecture

---

## Executive Summary

The current vehicle tracking interpolation system uses **linear speed interpolation** between GPS points, which creates forensically indefensible assumptions about vehicle behavior. This document outlines a complete refactor to implement **segment-based constant speed calculation** that adheres to forensic video analysis principles.

**Core Principle**: "You don't know what happened off camera - only speak to what is observed."

---

## Part 1: Current Implementation Analysis

### 1.1 Speed Calculation Flow

```
Raw GPS Points → Calculate Speed Between Points → Linear Interpolation → Display
```

#### Current Speed Calculation Locations:

1. **Initial CSV Parsing** (`parse_csv_file` - line 410-430)
   - Reads speed from CSV if available
   - Falls back to calculating from distance/time

2. **Speed Calculation Method** (`_calculate_speed_and_distance` - line 520-550)
   - Uses Haversine formula for distance
   - Calculates: `speed = (distance / time) * 3600`
   - Problem: Returns 0 for duplicate timestamps

3. **Interpolation Speed** (`interpolate_path_global_resampling` - line 783-785)
   ```python
   start_speed = seg_start.calculated_speed_kmh or seg_start.speed_kmh or 0
   end_speed = seg_end.calculated_speed_kmh or seg_end.speed_kmh or 0
   speed = start_speed + (end_speed - start_speed) * time_ratio  # FORENSIC ISSUE!
   ```

4. **JavaScript Visualization** (`mapbox.html` - line 1850-1890)
   - Uses interpolated speeds from Python
   - Displays speed in UI

### 1.2 Critical Forensic Issues

#### Issue 1: Linear Speed Interpolation Creates False Precision
**Current Behavior:**
- Point A: 20 km/h at 10:00:00
- Point B: 40 km/h at 10:00:10
- Interpolated at 10:00:05: 30 km/h (assumes linear acceleration)

**Forensic Reality:**
- Vehicle could have braked to 5 km/h then accelerated
- Could have stopped completely
- Could have maintained 20 km/h for 8 seconds then jumped to 40 km/h
- **We cannot know** - only that it averaged 30 km/h over the segment

#### Issue 2: Speed at Points vs Speed Between Points
**Current:**
- Calculates speed AT each GPS point based on distance from previous point
- Creates misleading precision about instantaneous speed

**Forensically Correct:**
- Speed should represent the SEGMENT between points
- One speed value for entire segment A→B

#### Issue 3: Duplicate Timestamps Create 0 km/h Artifacts
**Current:**
- When time_diff = 0, speed = 0
- Creates false stops in data

**Reality:**
- Duplicate timestamps likely represent sub-second measurements
- Should use surrounding context or minimum time delta

---

## Part 2: Forensic Speed Calculation Design

### 2.1 Core Principles

1. **Segment-Based Speed**: Each segment A→B has ONE constant speed
2. **No Interpolated Speeds**: Interpolated points inherit segment speed
3. **Certainty Thresholds**: Based on time gaps between real points
4. **Clear Data Lineage**: Mark observed vs inferred data

### 2.2 Certainty Framework

```python
class SpeedCertainty(Enum):
    HIGH = "high"        # 0-5 seconds: Vehicle behavior unlikely to change drastically
    MEDIUM = "medium"    # 5-10 seconds: Possible acceleration/deceleration events
    LOW = "low"          # 10-30 seconds: Significant uncertainty
    UNKNOWN = "unknown"  # >30 seconds: Gap too large for meaningful inference
```

### 2.3 Speed Calculation Algorithm

```python
def calculate_segment_speed(point_a: GPSPoint, point_b: GPSPoint) -> SegmentSpeed:
    """
    Calculate forensically defensible speed for segment A→B
    """
    # Calculate distance using Haversine
    distance_m = haversine_distance(point_a, point_b)

    # Calculate time elapsed
    time_diff = (point_b.timestamp - point_a.timestamp).total_seconds()

    # Handle edge cases
    if time_diff == 0:
        # Duplicate timestamp - use minimum credible time
        time_diff = 0.5  # Assume 0.5 second minimum
        certainty = SpeedCertainty.LOW
    elif time_diff <= 5:
        certainty = SpeedCertainty.HIGH
    elif time_diff <= 10:
        certainty = SpeedCertainty.MEDIUM
    elif time_diff <= 30:
        certainty = SpeedCertainty.LOW
    else:
        # Gap too large
        return SegmentSpeed(
            speed_kmh=None,
            certainty=SpeedCertainty.UNKNOWN,
            gap_seconds=time_diff
        )

    # Calculate average speed for segment
    speed_mps = distance_m / time_diff
    speed_kmh = speed_mps * 3.6

    return SegmentSpeed(
        speed_kmh=speed_kmh,
        certainty=certainty,
        distance_m=distance_m,
        time_seconds=time_diff
    )
```

### 2.4 Data Model Enhancements

```python
@dataclass
class SegmentSpeed:
    """Represents speed calculation for a GPS segment"""
    speed_kmh: Optional[float]
    certainty: SpeedCertainty
    distance_m: float
    time_seconds: float
    gap_type: Optional[str] = None  # 'stop', 'gap', 'normal'

@dataclass
class GPSSegment:
    """Represents a segment between two observed GPS points"""
    start_point: GPSPoint
    end_point: GPSPoint
    segment_speed: SegmentSpeed
    interpolated_points: List[GPSPoint]

@dataclass
class ForensicGPSPoint(GPSPoint):
    """Enhanced GPS point with forensic metadata"""
    is_observed: bool  # True for real GPS data, False for interpolated
    segment_speed_kmh: Optional[float]  # Speed of containing segment
    speed_certainty: Optional[SpeedCertainty]
    segment_id: Optional[int]  # Which segment this point belongs to
```

---

## Part 3: Step-by-Step Refactor Plan

### Phase 1: Data Model Enhancement (2-3 hours)

#### Step 1.1: Create Forensic Data Classes
**File**: `vehicle_tracking/models/forensic_models.py` (NEW)
```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List
from .vehicle_tracking_models import GPSPoint

class SpeedCertainty(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"

@dataclass
class SegmentSpeed:
    speed_kmh: Optional[float]
    certainty: SpeedCertainty
    distance_m: float
    time_seconds: float

@dataclass
class GPSSegment:
    start_point: GPSPoint
    end_point: GPSPoint
    segment_speed: SegmentSpeed
    interpolated_points: List[GPSPoint] = field(default_factory=list)
```

#### Step 1.2: Extend GPSPoint Model
**File**: `vehicle_tracking/models/vehicle_tracking_models.py`
**Changes**: Add forensic fields to GPSPoint
```python
@dataclass
class GPSPoint:
    # ... existing fields ...

    # Forensic tracking fields
    segment_speed_kmh: Optional[float] = None  # Speed of containing segment
    speed_certainty: Optional[str] = None  # 'high', 'medium', 'low', 'unknown'
    segment_id: Optional[int] = None  # Which segment this belongs to
    is_observed: bool = True  # False for interpolated points
```

### Phase 2: Segment-Based Speed Calculation (3-4 hours)

#### Step 2.1: Create Forensic Speed Calculator
**File**: `vehicle_tracking/services/forensic_speed_calculator.py` (NEW)
```python
class ForensicSpeedCalculator:
    """Calculates forensically defensible speeds for GPS segments"""

    MIN_TIME_DELTA = 0.5  # Minimum credible time between points

    def calculate_segment_speeds(
        self,
        points: List[GPSPoint]
    ) -> List[GPSSegment]:
        """Calculate speeds for all segments in GPS data"""
        segments = []

        for i in range(len(points) - 1):
            segment = self._create_segment(points[i], points[i + 1])
            segments.append(segment)

        return segments

    def _create_segment(
        self,
        start: GPSPoint,
        end: GPSPoint
    ) -> GPSSegment:
        """Create a GPS segment with calculated speed"""
        # Calculate distance
        distance_m = self._haversine_distance(start, end)

        # Calculate time
        time_diff = (end.timestamp - start.timestamp).total_seconds()

        # Determine certainty
        certainty = self._determine_certainty(time_diff)

        # Handle duplicate timestamps
        if time_diff == 0:
            time_diff = self.MIN_TIME_DELTA

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
                time_seconds=time_diff
            )
        )
```

#### Step 2.2: Refactor VehicleTrackingService Speed Calculation
**File**: `vehicle_tracking/services/vehicle_tracking_service.py`
**Location**: Lines 520-550 (_calculate_speed_and_distance method)

**Replace with**:
```python
def _calculate_segment_speeds(
    self,
    vehicle_data: VehicleData
) -> Result[List[GPSSegment]]:
    """Calculate forensically sound speeds for all segments"""
    try:
        calculator = ForensicSpeedCalculator()
        segments = calculator.calculate_segment_speeds(vehicle_data.gps_points)

        # Store segment speeds in GPS points
        for seg_idx, segment in enumerate(segments):
            # Mark segment speed in both endpoints
            segment.start_point.segment_speed_kmh = segment.segment_speed.speed_kmh
            segment.start_point.speed_certainty = segment.segment_speed.certainty.value
            segment.start_point.segment_id = seg_idx

            segment.end_point.segment_speed_kmh = segment.segment_speed.speed_kmh
            segment.end_point.speed_certainty = segment.segment_speed.certainty.value
            segment.end_point.segment_id = seg_idx

        return Result.success(segments)
    except Exception as e:
        return Result.error(VehicleTrackingError(str(e)))
```

### Phase 3: Refactor Interpolation (4-5 hours)

#### Step 3.1: Modify Global Resampling Method
**File**: `vehicle_tracking/services/vehicle_tracking_service.py`
**Location**: Lines 691-844 (interpolate_path_global_resampling)

**Key Changes**:
```python
def interpolate_path_global_resampling(
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

        # STEP 1: Calculate segment speeds
        segments_result = self._calculate_segment_speeds(vehicle_data)
        if not segments_result.success:
            return segments_result
        segments = segments_result.value

        dt = settings.interpolation_interval_seconds
        interpolated = []

        # Always include first point
        interpolated.append(points[0])

        # Walk through each segment
        for seg_idx, segment in enumerate(segments):
            seg_start = segment.start_point
            seg_end = segment.end_point

            # Skip if gap is too large
            if segment.segment_speed.certainty == SpeedCertainty.UNKNOWN:
                # Add gap marker
                gap_marker = GPSPoint(
                    latitude=seg_start.latitude,
                    longitude=seg_start.longitude,
                    timestamp=seg_start.timestamp,
                    segment_speed_kmh=0,
                    speed_certainty="unknown",
                    is_gap=True,
                    metadata={'gap_seconds': segment.segment_speed.time_seconds}
                )
                interpolated.append(gap_marker)
                continue

            # Generate interpolated points at dt intervals
            current_t = seg_start.timestamp + timedelta(seconds=dt)

            while current_t < seg_end.timestamp:
                # Calculate position ratio
                seg_duration = (seg_end.timestamp - seg_start.timestamp).total_seconds()
                time_ratio = (current_t - seg_start.timestamp).total_seconds() / seg_duration

                # Interpolate position (keep existing metric projection)
                lat, lon = self._interpolate_in_metric(
                    seg_start, seg_end, time_ratio, to_metric, to_wgs84
                )

                # Create interpolated point with SEGMENT speed (not interpolated!)
                interp_point = GPSPoint(
                    latitude=lat,
                    longitude=lon,
                    timestamp=current_t,
                    segment_speed_kmh=segment.segment_speed.speed_kmh,  # CONSTANT!
                    speed_certainty=segment.segment_speed.certainty.value,
                    segment_id=seg_idx,
                    is_interpolated=True,
                    is_observed=False
                )

                interpolated.append(interp_point)
                current_t += timedelta(seconds=dt)

        # Add final point
        interpolated.append(points[-1])

        # Update vehicle data
        vehicle_data.gps_points = interpolated
        vehicle_data.has_segment_speeds = True
        vehicle_data.segments = segments

        return Result.success(vehicle_data)
```

#### Step 3.2: Remove Linear Speed Interpolation
**File**: `vehicle_tracking/services/vehicle_tracking_service.py`
**Location**: Lines 783-785

**DELETE these lines**:
```python
# DELETE THIS BLOCK
start_speed = seg_start.calculated_speed_kmh or seg_start.speed_kmh or 0
end_speed = seg_end.calculated_speed_kmh or seg_end.speed_kmh or 0
speed = start_speed + (end_speed - start_speed) * time_ratio
```

**REPLACE with**:
```python
# Use constant segment speed
speed = segment.segment_speed.speed_kmh
certainty = segment.segment_speed.certainty.value
```

### Phase 4: UI/Display Updates (2-3 hours)

#### Step 4.1: Update JavaScript Speed Display
**File**: `vehicle_tracking/tauri-map/src/mapbox.html`
**Location**: Lines 1850-1890

**Add certainty visualization**:
```javascript
// Get speed and certainty
const speed = currentPoint.segment_speed_kmh || 0;
const certainty = currentPoint.speed_certainty || 'unknown';

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

// Update speed display with certainty indicator
document.getElementById('speed-display').innerHTML =
    `<span style="color: ${speedColor}">${speed.toFixed(1)} km/h (${certainty})</span>`;
```

#### Step 4.2: Add Gap Visualization
```javascript
// Check for gaps
if (currentPoint.is_gap) {
    // Show gap indicator
    document.getElementById('gap-indicator').style.display = 'block';
    document.getElementById('gap-duration').innerText =
        `Data gap: ${currentPoint.metadata.gap_seconds}s`;
}
```

### Phase 5: Testing & Validation (3-4 hours)

#### Step 5.1: Create Forensic Speed Tests
**File**: `vehicle_tracking/tests/test_forensic_speed.py` (NEW)
```python
def test_segment_speed_calculation():
    """Test that segment speeds are constant"""
    # Create test points
    points = [
        GPSPoint(43.0, -79.0, datetime(2024, 1, 1, 10, 0, 0)),
        GPSPoint(43.001, -79.001, datetime(2024, 1, 1, 10, 0, 10))
    ]

    # Calculate segment speed
    calculator = ForensicSpeedCalculator()
    segments = calculator.calculate_segment_speeds(points)

    # Verify one speed for entire segment
    assert len(segments) == 1
    assert segments[0].segment_speed.speed_kmh is not None
    assert segments[0].segment_speed.certainty == SpeedCertainty.HIGH

def test_interpolated_points_inherit_segment_speed():
    """Test that all interpolated points have same speed"""
    # Interpolate at 2-second intervals
    result = service.interpolate_path(vehicle_data, settings)

    # Check all points in segment have same speed
    for point in result.value.gps_points[1:-1]:
        if point.segment_id == 0:
            assert point.segment_speed_kmh == segments[0].segment_speed.speed_kmh
```

#### Step 5.2: Validation Against Ground Truth
```python
def test_against_ground_truth():
    """Compare forensic speeds with known ground truth"""
    # Load ground truth data
    ground_truth = load_csv("belsize_to_bayview_interpolated_2sec.csv")

    # Calculate forensic speeds
    forensic_result = calculate_forensic_speeds(ground_truth)

    # Compare segment by segment
    for segment in forensic_result.segments:
        # Forensic speed should be average over segment
        assert_close(segment.speed_kmh, segment.ground_truth_average)
```

---

## Part 4: Migration Strategy

### 4.1 Feature Flags for Gradual Rollout
```python
class VehicleTrackingSettings:
    # Add feature flag
    use_forensic_speed_calculation: bool = False  # Default to old behavior

    # Certainty thresholds (configurable)
    high_certainty_threshold_s: float = 5.0
    medium_certainty_threshold_s: float = 10.0
    max_gap_threshold_s: float = 30.0
```

### 4.2 Backward Compatibility
- Keep old speed fields for compatibility
- Add new `segment_speed_kmh` field alongside
- UI can switch between display modes

### 4.3 Rollout Phases
1. **Phase 1**: Implement new calculation, disabled by default
2. **Phase 2**: Enable for testing/validation
3. **Phase 3**: A/B testing with select users
4. **Phase 4**: Make default, keep old as fallback
5. **Phase 5**: Remove old implementation

---

## Part 5: Expected Outcomes

### 5.1 Forensic Benefits
- **Defensible in court**: No false assumptions about vehicle behavior
- **Clear uncertainty boundaries**: Explicit about what we know vs infer
- **Accurate representation**: Segment averages instead of false precision

### 5.2 Technical Benefits
- **Simpler logic**: One speed per segment
- **Better performance**: Less calculation during interpolation
- **Clearer data model**: Explicit segment structure

### 5.3 User Benefits
- **Transparency**: Users see certainty levels
- **Trust**: No mysterious speed variations
- **Understanding**: Clear when data is missing/uncertain

---

## Part 6: Implementation Timeline

### Week 1
- Days 1-2: Data model enhancement (Phase 1)
- Days 3-4: Segment speed calculation (Phase 2)
- Day 5: Initial testing

### Week 2
- Days 1-3: Interpolation refactor (Phase 3)
- Day 4: UI updates (Phase 4)
- Day 5: Integration testing

### Week 3
- Days 1-2: Comprehensive testing (Phase 5)
- Days 3-4: Documentation and training
- Day 5: Staged rollout begins

---

## Appendix A: Code Examples

### Example 1: Segment with High Certainty
```python
# Points 3 seconds apart
point_a = GPSPoint(43.0, -79.0, datetime(2024, 1, 1, 10, 0, 0))
point_b = GPSPoint(43.0001, -79.0001, datetime(2024, 1, 1, 10, 0, 3))

# Result
segment_speed = 4.2 km/h (HIGH certainty)
# All interpolated points get 4.2 km/h
```

### Example 2: Segment with Gap
```python
# Points 45 seconds apart
point_a = GPSPoint(43.0, -79.0, datetime(2024, 1, 1, 10, 0, 0))
point_b = GPSPoint(43.001, -79.001, datetime(2024, 1, 1, 10, 0, 45))

# Result
segment_speed = None (UNKNOWN)
# No interpolation performed - gap marked in data
```

---

## Appendix B: Configuration Options

```yaml
forensic_speed_config:
  # Certainty thresholds
  high_certainty_max_seconds: 5
  medium_certainty_max_seconds: 10
  low_certainty_max_seconds: 30

  # Duplicate timestamp handling
  duplicate_timestamp_min_delta: 0.5

  # Gap handling
  mark_gaps_over_seconds: 30
  interpolate_gaps_under_seconds: 10

  # Display options
  show_certainty_indicators: true
  highlight_low_certainty: true
  show_gap_markers: true
```

---

## Conclusion

This refactor transforms the vehicle tracking system from making **forensically indefensible assumptions** to providing **court-ready, uncertainty-aware speed calculations**. The implementation preserves smooth animation while ensuring every speed claim is defensible based on observed data.

**Total Estimated Time**: 15-20 hours of development + 5 hours testing

**Risk Level**: Medium (significant refactor but well-isolated)

**Forensic Improvement**: HIGH - Transforms from assumptions to evidence-based calculations