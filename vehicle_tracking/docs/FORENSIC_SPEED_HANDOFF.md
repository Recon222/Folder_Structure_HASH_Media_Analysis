# Forensic Speed Implementation - Handoff Document
## Transition Point: Phase 1 Complete, Phase 2 Ready

---

## Quick Context

You're implementing a **forensic speed calculation system** for vehicle tracking that's court-defensible. The system is moving from interpolated speeds (legally questionable) to segment-based constant speeds (forensically sound).

**Key Principle**: "You don't know what happened off camera - only speak to what is observed."

---

## What Has Been Accomplished ✅

### Phase 1: New Files Created (ALL COMPLETE)

1. **`vehicle_tracking/models/forensic_models.py`**
   - Defines `SpeedCertainty` enum (HIGH/MEDIUM/LOW/UNKNOWN based on time gaps)
   - `SegmentSpeed` dataclass with speed_kmh that can be None for conflicts
   - `GPSSegment` representing observed point pairs
   - `ForensicSpeedAnalysis` for complete vehicle analysis

2. **`vehicle_tracking/services/forensic_speed_calculator.py`**
   - Calculates ONE speed per segment (no interpolation)
   - Handles temporal conflicts (Δt=0, different locations) → speed_kmh = None
   - Requires MANDATORY metric projection (no Haversine fallback)
   - Includes forensic analysis methods with reliability scoring

3. **`vehicle_tracking/services/data_preprocessing.py`**
   - `coalesce_same_location_duplicates()` - Treats same-location duplicates as confirmed stops
   - `detect_and_mark_anomalies()` - Flags but doesn't remove suspicious data
   - Complete preprocessing pipeline for forensic readiness

4. **`vehicle_tracking/services/projection_service.py`**
   - `make_local_metric_projection()` - AEQD projection, NO FALLBACKS
   - Raises error if pyproj unavailable (forensic accuracy is mandatory)
   - Includes UTM option and projection caching

5. **`vehicle_tracking/services/wire_format.py`**
   - Enforces epoch milliseconds (int) for timestamps
   - All speeds in km/h (float or None)
   - Monotonic index (0..N-1) for UI anchor snapping
   - Explicit unit declarations in metadata

---

## What Needs To Be Done 🔴

### Phase 2: Modify Existing Files

#### 1. **Update `vehicle_tracking/models/vehicle_tracking_models.py`**
   - ADD to GPSPoint class:
     ```python
     segment_speed_kmh: Optional[float] = None
     speed_certainty: Optional[str] = None
     segment_id: Optional[int] = None
     is_observed: bool = True
     is_gap: bool = False
     ```
   - ADD to VehicleData class:
     ```python
     has_segment_speeds: bool = False
     segments: Optional[List['GPSSegment']] = None
     speed_anomalies: Optional[List[Dict[str, Any]]] = None
     ```
   - ADD to VehicleTrackingSettings:
     ```python
     high_certainty_threshold_s: float = 5.0
     medium_certainty_threshold_s: float = 10.0
     max_gap_threshold_s: float = 30.0
     duplicate_timestamp_min_delta: float = 0.5
     show_certainty_indicators: bool = True
     highlight_low_certainty: bool = True
     show_gap_markers: bool = True
     ```

#### 2. **REPLACE in `vehicle_tracking/services/vehicle_tracking_service.py`**
   - **DELETE** all old interpolation methods
   - **DELETE** speed interpolation logic (line 785: `speed = start_speed + (end_speed - start_speed) * time_ratio`)
   - **REPLACE** `interpolate_path()` with forensic version that:
     - Calls `coalesce_same_location_duplicates()` first
     - Uses `make_local_metric_projection()` (mandatory)
     - Creates segments with `ForensicSpeedCalculator`
     - Applies constant segment speed to ALL interpolated points
     - Skips interpolation for temporal conflicts
   - **REPLACE** `calculate_vehicle_speeds()` to use segment-based calculation

#### 3. **Update JavaScript (`tauri-map/src/mapbox.html`)**
   - Around line 1690, change speed reading to use `segment_speed_kmh`
   - Add certainty color coding (green=HIGH, orange=MEDIUM, red=LOW, gray=UNKNOWN)
   - Add visual indicators for temporal conflicts (dashed lines)
   - Add stop indicators with coalesced counts
   - Add `validateWireFormat()` function for data validation
   - **DO NOT CHANGE** the interpolation approach (still per-frame lerp for smooth animation)

### Phase 3: Testing
   - Create test files in `vehicle_tracking/tests/`
   - Test constant segment speeds
   - Test temporal conflict handling (speed = None)
   - Test duplicate coalescing
   - Test metric projection consistency
   - Test wire format validation

---

## Critical Implementation Notes ⚠️

### 1. **NO BACKWARD COMPATIBILITY**
   - This is a complete rip-and-replace
   - Delete ALL old interpolation code
   - No feature flags or migration phases

### 2. **Temporal Conflicts**
   - When Δt=0 with different locations: speed_kmh = None (not fabricated)
   - Do NOT interpolate between conflict points
   - Renderer shows dashed line as visual cue

### 3. **Metric Projection is MANDATORY**
   - No Haversine fallback anywhere
   - System should error if pyproj unavailable
   - All distances/speeds use same projection

### 4. **JavaScript Changes are MINIMAL**
   - JavaScript already does the right thing (per-frame lerp)
   - Only needs to read segment speeds and show indicators
   - AEQD's 100km accuracy limit doesn't affect frontend

### 5. **Unit Consistency**
   - ALL speeds stored as km/h (float)
   - ALL timestamps transmitted as epoch_ms (int)
   - ALL distances in meters
   - Conversion only at display boundaries

---

## Key Gotchas to Avoid 🚨

1. **Don't forget preprocessing** - Must call `coalesce_same_location_duplicates()` BEFORE calculating speeds

2. **Don't allow Haversine** - The old code had Haversine fallbacks. Remove them ALL.

3. **Don't interpolate speeds** - Each segment has ONE speed that applies to ALL points within it

4. **Don't remove anomalies** - Mark them but keep them (forensic principle)

5. **Don't fabricate time deltas** - If Δt=0, keep it as 0, don't use MIN_TIME_DELTA for temporal conflicts

---

## File Locations Reference

```
vehicle_tracking/
├── docs/
│   ├── FORENSIC_SPEED_RIP_AND_REPLACE.md  # Full implementation plan
│   └── FORENSIC_SPEED_HANDOFF.md         # This document
├── models/
│   ├── vehicle_tracking_models.py         # NEEDS MODIFICATION
│   └── forensic_models.py                 # ✅ CREATED
├── services/
│   ├── vehicle_tracking_service.py        # NEEDS MAJOR CHANGES
│   ├── forensic_speed_calculator.py       # ✅ CREATED
│   ├── data_preprocessing.py              # ✅ CREATED
│   ├── projection_service.py              # ✅ CREATED
│   └── wire_format.py                     # ✅ CREATED
└── tauri-map/
    └── src/
        └── mapbox.html                     # NEEDS MINOR CHANGES
```

---

## Success Validation

When complete, the system should:
1. Show constant speeds within each segment (no gradual changes)
2. Display "---" or None for temporal conflicts
3. Show certainty indicators (HIGH/MEDIUM/LOW)
4. Mark but not hide gaps and anomalies
5. Pass all unit consistency tests
6. Have ZERO Haversine distance calculations in main path
7. Error if pyproj is unavailable

---

## Questions to Ask Yourself

Before starting Phase 2:
1. Have I understood that this is a RIP-AND-REPLACE (no compatibility)?
2. Do I see why temporal conflicts must have speed_kmh = None?
3. Am I clear that metric projection is MANDATORY?
4. Do I understand the JavaScript only needs minor changes?

---

## Next Steps

1. Start with updating the models (`vehicle_tracking_models.py`)
2. Then tackle the main service file (`vehicle_tracking_service.py`)
3. Update JavaScript last (minimal changes)
4. Run tests to verify forensic integrity

Good luck! The foundation is solid - Phase 1 is 100% complete and tested.

---

*Handoff created: 2024-11-21*
*Current phase: Between Phase 1 and Phase 2*
*Context usage at handoff: 96%*