# GPS Hemisphere Fix Summary

## Issue
GPS longitude values were not being negated for Western hemisphere coordinates, causing locations like Toronto (79°W) to appear in Kazakhstan (79°E).

## Root Cause
ExifTool returns hemisphere references as full words ('North', 'South', 'East', 'West') rather than single letters ('N', 'S', 'E', 'W'). The code was only checking for single letter 'W' to negate longitude.

## Fix Applied
Updated `/core/exiftool/exiftool_normalizer.py` to check for both formats:

```python
# Before (incorrect):
if lon_ref == 'W' and lon > 0:
    lon = -lon

# After (fixed):
if lon_ref and ('W' in lon_ref or 'West' in lon_ref) and lon > 0:
    lon = -lon
```

Similarly for latitude/South handling:
```python
if lat_ref and ('S' in lat_ref or 'South' in lat_ref) and lat > 0:
    lat = -lat
```

## Test Results
Created comprehensive test suite (`tests/test_gps_hemisphere_handling.py`) that validates:
- Toronto coordinates with 'West' string: ✅ PASS
- Sydney coordinates with single letters: ✅ PASS  
- Pre-negated values preserved: ✅ PASS
- Decimal values with hemisphere refs: ✅ PASS
- Mixed South/West format: ✅ PASS

## Impact
- GPS coordinates now correctly display on map
- Western longitude values properly negated (e.g., Toronto at -79.73° instead of +79.73°)
- Southern latitude values properly negated
- Handles both full word and single letter hemisphere references from ExifTool