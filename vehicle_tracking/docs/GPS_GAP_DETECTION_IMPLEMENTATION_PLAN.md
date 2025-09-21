# GPS Gap Detection & Analysis Implementation Plan

## Executive Summary

This document outlines a comprehensive plan for detecting, analyzing, and handling gaps in vehicle GPS data. Gaps in GPS timestamps can indicate various real-world scenarios (parking, signal loss, device power-off) that have significant forensic implications. This implementation will preserve data integrity while providing intelligent analysis of gap causes.

## Understanding GPS Gaps

### What Are GPS Gaps?
GPS gaps occur when there's an abnormally long time between consecutive GPS readings. Unlike "idling" (where the vehicle is stationary but GPS continues transmitting), gaps indicate the GPS system stopped recording entirely.

### Common Causes of GPS Gaps

1. **Parking Events** (Vehicle Powered Off)
   - Vehicle turned off in parking lot/garage
   - GPS resumes at same location when restarted
   - Typical duration: Minutes to days

2. **Signal Loss** (Environmental)
   - Underground parking
   - Tunnels
   - Dense urban canyons
   - GPS resumes at different location
   - Typical duration: Seconds to minutes

3. **Device Issues**
   - GPS module restart
   - Power interruption
   - System crash/reboot
   - May resume at same or different location
   - Typical duration: Seconds to minutes

4. **Intentional Disabling**
   - Manual GPS disable
   - Device tampering
   - Evidence of evasion
   - Forensically significant

## Current Code Analysis

### Existing Infrastructure

#### 1. GPS Point Model (`vehicle_tracking_models.py`)
```python
@dataclass
class GPSPoint:
    latitude: float
    longitude: float
    timestamp: datetime
    # ... other fields ...
    metadata: Optional[Dict[str, Any]] = None  # ✅ Just added - ready for gap data
```

#### 2. Speed/Distance Calculation (`vehicle_tracking_service.py:517-549`)
- `_calculate_speed_and_distance()` uses Haversine formula
- Returns `(speed_kmh, distance_km)` tuple
- Already handles time difference calculation

#### 3. Interpolation Pipeline (`vehicle_tracking_service.py:691-844`)
- `interpolate_path_global_resampling()` walks through time at exact intervals
- Currently interpolates across ALL segments
- Needs modification to respect gaps

#### 4. Service Logging (`vehicle_tracking_service.py`)
- `_log_operation()` method available for forensic logging
- Consistent logging pattern throughout service

### What's Missing

1. **Gap Detection Logic** - No method to identify gaps
2. **Gap Classification** - No analysis of gap type (parking vs signal loss)
3. **Metadata Structure** - No defined schema for gap metadata
4. **UI Configuration** - No settings for gap thresholds
5. **JavaScript Handling** - Map doesn't handle gap metadata

## Implementation Plan

### Phase 1: Data Structures & Configuration

#### 1.1 Add Gap Detection Settings to `VehicleTrackingSettings`
```python
# In vehicle_tracking_models.py, add to VehicleTrackingSettings:

# Gap detection settings
gap_detection_enabled: bool = True
gap_threshold_seconds: float = 60.0  # Minimum gap to flag
parking_distance_threshold_meters: float = 50.0  # Max distance for parking classification
signal_loss_time_threshold_seconds: float = 120.0  # Max time for signal loss vs parking
```

#### 1.2 Add Gap Analysis Results to `VehicleData`
```python
# In vehicle_tracking_models.py, add to VehicleData:

# Gap analysis results
gaps: List[Dict[str, Any]] = field(default_factory=list)
total_gap_duration: float = 0.0
gap_count: int = 0
```

### Phase 2: Gap Detection & Classification

#### 2.1 Core Gap Detection Method
```python
def _detect_gaps(
    self,
    points: List[GPSPoint],
    threshold_seconds: float = 60.0
) -> List[Dict[str, Any]]:
    """
    Detect gaps in GPS data where timestamps jump unexpectedly.

    Returns list of gap records with analysis.
    """
    gaps = []

    for i in range(len(points) - 1):
        current = points[i]
        next_point = points[i + 1]

        # Calculate time gap
        time_diff = (next_point.timestamp - current.timestamp).total_seconds()

        if time_diff >= threshold_seconds:
            # Calculate distance during gap
            _, distance_km = self._calculate_speed_and_distance(current, next_point)
            distance_m = distance_km * 1000

            # Classify the gap
            gap_type = self._classify_gap(time_diff, distance_m)

            gap_record = {
                'start_idx': i,
                'end_idx': i + 1,
                'start_point': current,
                'end_point': next_point,
                'duration_seconds': time_diff,
                'distance_meters': distance_m,
                'gap_type': gap_type,
                'timestamp_start': current.timestamp,
                'timestamp_end': next_point.timestamp,
                'location_start': (current.latitude, current.longitude),
                'location_end': (next_point.latitude, next_point.longitude)
            }

            gaps.append(gap_record)

            self._log_operation("gap_detection",
                f"Gap detected: {gap_type} for {time_diff:.1f}s, "
                f"distance: {distance_m:.1f}m")

    return gaps
```

#### 2.2 Gap Classification Logic
```python
def _classify_gap(
    self,
    duration_seconds: float,
    distance_meters: float,
    settings: Optional[VehicleTrackingSettings] = None
) -> str:
    """
    Classify gap based on duration and distance traveled.

    Returns: 'parking', 'signal_loss', 'device_restart', or 'unknown'
    """
    settings = settings or VehicleTrackingSettings()

    # Quick restart (< 2 minutes, close proximity)
    if duration_seconds < 120 and distance_meters < 100:
        return 'device_restart'

    # Parking (any duration, minimal movement)
    if distance_meters < settings.parking_distance_threshold_meters:
        return 'parking'

    # Signal loss (moderate time, significant movement)
    if duration_seconds < settings.signal_loss_time_threshold_seconds:
        # Calculate implied speed
        implied_speed_kmh = (distance_meters / 1000) / (duration_seconds / 3600)

        # Reasonable speed = likely signal loss (tunnel, parking garage)
        if implied_speed_kmh < 150:  # Below highway speeds
            return 'signal_loss'

    # Long duration + large distance = suspicious
    return 'unknown'  # Possible tampering or data issue
```

#### 2.3 Gap Metadata Injection
```python
def _inject_gap_metadata(
    self,
    points: List[GPSPoint],
    gaps: List[Dict[str, Any]]
) -> None:
    """
    Add gap metadata to affected GPS points for JavaScript consumption.
    """
    for gap in gaps:
        start_point = points[gap['start_idx']]
        end_point = points[gap['end_idx']]

        # Mark the last point before gap
        if start_point.metadata is None:
            start_point.metadata = {}
        start_point.metadata['gap_after'] = {
            'type': gap['gap_type'],
            'duration': gap['duration_seconds'],
            'distance': gap['distance_meters'],
            'next_location': gap['location_end']
        }

        # Mark the first point after gap
        if end_point.metadata is None:
            end_point.metadata = {}
        end_point.metadata['gap_before'] = {
            'type': gap['gap_type'],
            'duration': gap['duration_seconds'],
            'distance': gap['distance_meters'],
            'previous_location': gap['location_start']
        }
```

### Phase 3: Integration with Interpolation

#### 3.1 Modified Interpolation to Respect Gaps
```python
def interpolate_path_global_resampling(self, vehicle_data, settings, progress_callback=None):
    # ... existing setup code ...

    # Detect gaps first
    if settings.gap_detection_enabled:
        gaps = self._detect_gaps(points, settings.gap_threshold_seconds)
        vehicle_data.gaps = gaps
        vehicle_data.gap_count = len(gaps)
        vehicle_data.total_gap_duration = sum(g['duration_seconds'] for g in gaps)

        # Inject metadata for JavaScript
        self._inject_gap_metadata(points, gaps)

        # Build gap index for fast lookup
        gap_segments = {(g['start_idx'], g['end_idx']): g for g in gaps}

    # ... existing interpolation setup ...

    # Modified interpolation loop
    while seg_idx < len(points) - 1 and t_emit <= points[-1].timestamp:
        seg_start = points[seg_idx]
        seg_end = points[seg_idx + 1]

        # Check if this segment is a gap
        if settings.gap_detection_enabled and (seg_idx, seg_idx + 1) in gap_segments:
            gap = gap_segments[(seg_idx, seg_idx + 1)]

            # Don't interpolate across gaps - add marker point
            gap_marker = self._create_gap_marker(gap, t_emit)
            if gap_marker:
                interpolated.append(gap_marker)

            # Jump to after the gap
            seg_idx += 1
            t_emit = seg_end.timestamp + timedelta(seconds=dt)
            continue

        # ... existing interpolation logic for normal segments ...
```

#### 3.2 Gap Marker Creation
```python
def _create_gap_marker(self, gap: Dict[str, Any], t_emit: datetime) -> Optional[GPSPoint]:
    """
    Create a special marker point to indicate gap in data.
    """
    # Only create marker if we're within the gap time range
    if t_emit < gap['timestamp_start'] or t_emit > gap['timestamp_end']:
        return None

    # Create marker at last known position
    marker = GPSPoint(
        latitude=gap['location_start'][0],
        longitude=gap['location_start'][1],
        timestamp=t_emit,
        calculated_speed_kmh=0,
        is_interpolated=False,  # Not interpolated - it's a marker
        metadata={
            'gap_marker': True,
            'gap_type': gap['gap_type'],
            'gap_duration': gap['duration_seconds'],
            'gap_distance': gap['distance_meters'],
            'message': self._get_gap_message(gap)
        }
    )

    return marker
```

#### 3.3 Gap Message Generation
```python
def _get_gap_message(self, gap: Dict[str, Any]) -> str:
    """
    Generate human-readable message about the gap.
    """
    duration = gap['duration_seconds']
    distance = gap['distance_meters']
    gap_type = gap['gap_type']

    # Format duration
    if duration < 120:
        duration_str = f"{duration:.0f} seconds"
    elif duration < 3600:
        duration_str = f"{duration/60:.1f} minutes"
    else:
        duration_str = f"{duration/3600:.1f} hours"

    # Generate message based on type
    if gap_type == 'parking':
        return f"Vehicle parked for {duration_str}"
    elif gap_type == 'signal_loss':
        return f"GPS signal lost for {duration_str} ({distance:.0f}m traveled)"
    elif gap_type == 'device_restart':
        return f"GPS device restarted ({duration_str})"
    else:
        return f"GPS gap: {duration_str}, {distance:.0f}m movement"
```

### Phase 4: JavaScript Integration

#### 4.1 JavaScript Gap Handling (Conceptual)
```javascript
// In the map rendering code
if (point.metadata?.gap_after) {
    // Show gap indicator after this point
    const gap = point.metadata.gap_after;

    // Different visualization based on gap type
    if (gap.type === 'parking') {
        // Show parking icon
        addParkingMarker(point.latitude, point.longitude, gap.duration);
    } else if (gap.type === 'signal_loss') {
        // Show dashed line to next point
        addDashedLine(point, gap.next_location, '#FFA500');
    }

    // Add notification/tooltip
    addGapNotification({
        type: gap.type,
        duration: gap.duration,
        distance: gap.distance,
        position: [point.longitude, point.latitude]
    });
}
```

### Phase 5: Testing Strategy

#### 5.1 Unit Tests
```python
def test_gap_detection():
    """Test gap detection with various scenarios"""
    # Create points with 5-minute gap (parking scenario)
    # Create points with 30-second gap, 2km apart (signal loss)
    # Create points with no gaps (continuous tracking)
    # Verify correct classification
```

#### 5.2 Test Data Generation
```python
def generate_gap_test_data():
    """Generate CSV with known gap patterns"""
    # Normal driving for 10 minutes
    # 2-hour parking gap (same location)
    # 3-minute tunnel (different location, reasonable distance)
    # Device restart (15 seconds, same location)
    # Suspicious gap (1 hour, 200km movement)
```

## Configuration Recommendations

### Default Settings
```python
# Recommended defaults for law enforcement use
gap_threshold_seconds = 60.0  # 1 minute minimum gap
parking_distance_threshold_meters = 50.0  # ~165 feet
signal_loss_time_threshold_seconds = 300.0  # 5 minutes max for signal loss
```

### Adjustable Parameters
- **Urban vs Rural**: Tighter thresholds in urban areas (more signal loss expected)
- **Vehicle Type**: Commercial vehicles may have longer legitimate gaps
- **Investigation Type**: Stricter analysis for criminal investigations

## Forensic Considerations

### Data Integrity
1. **Never interpolate across gaps** - Don't create false movement
2. **Preserve original timestamps** - Critical for court evidence
3. **Log all gap detections** - Audit trail for analysis

### Chain of Evidence
1. **Document gap classification logic** - Explainable in court
2. **Retain all metadata** - Don't discard "insignificant" gaps
3. **Export gap analysis** - Include in forensic reports

### Red Flags for Investigation
- Gaps with impossible implied speeds (>250 km/h)
- Regular pattern gaps (every day at same time)
- Gaps coinciding with crime times
- Inconsistent gap patterns (tampering indicator)

## Implementation Timeline

### Day 1: Foundation (4 hours)
1. Add settings to VehicleTrackingSettings (30 min)
2. Add gap storage to VehicleData (30 min)
3. Implement `_detect_gaps()` method (1 hour)
4. Implement `_classify_gap()` method (1 hour)
5. Implement `_inject_gap_metadata()` (1 hour)

### Day 2: Integration (3 hours)
1. Modify `interpolate_path_global_resampling()` (1.5 hours)
2. Implement gap marker creation (1 hour)
3. Add forensic logging (30 min)

### Day 3: Testing (2 hours)
1. Create test data generator (30 min)
2. Write unit tests (1 hour)
3. Integration testing (30 min)

### Day 4: UI & Refinement (2 hours)
1. Add UI controls for gap settings (1 hour)
2. Test with real GPS data (30 min)
3. Documentation updates (30 min)

## Success Metrics

### Functional Requirements
- [ ] Detect all gaps > threshold
- [ ] Correctly classify parking vs signal loss
- [ ] No interpolation across gaps
- [ ] Metadata attached to points
- [ ] Forensic logging complete

### Performance Requirements
- [ ] Gap detection < 100ms for 10,000 points
- [ ] No memory leaks with metadata
- [ ] Smooth animation despite gaps

### Accuracy Requirements
- [ ] 95% correct parking classification
- [ ] 90% correct signal loss classification
- [ ] Zero false gap creation

## Conclusion

This implementation provides forensically-sound gap detection that preserves data integrity while offering intelligent analysis. The classification system helps investigators understand why gaps occurred, which is often as important as knowing they exist. The modular design allows easy enhancement with additional classification rules as patterns emerge from real-world data.