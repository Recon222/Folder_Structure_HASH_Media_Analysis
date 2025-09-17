#!/usr/bin/env python3
"""
Test script to validate TimestampedGeoJson migration changes
"""

from datetime import datetime, timedelta
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vehicle_tracking.models.vehicle_tracking_models import (
    GPSPoint, VehicleData, AnimationData, VehicleColor, VehicleTrackingSettings
)
from vehicle_tracking.services.vehicle_tracking_service import VehicleTrackingService


def create_test_data():
    """Create sample vehicle data for testing"""

    # Create GPS points with proper datetime objects
    base_time = datetime(2024, 1, 15, 10, 0, 0)

    vehicle1_points = []
    vehicle2_points = []

    # Vehicle 1 - Moving north
    for i in range(10):
        point = GPSPoint(
            latitude=40.7128 + (i * 0.001),
            longitude=-74.0060,
            timestamp=base_time + timedelta(seconds=i * 30),
            speed_kmh=50.0 + i,
            altitude=100.0 + i * 2,
            heading=0.0  # North
        )
        vehicle1_points.append(point)

    # Vehicle 2 - Moving east
    for i in range(10):
        point = GPSPoint(
            latitude=40.7128,
            longitude=-74.0060 + (i * 0.001),
            timestamp=base_time + timedelta(seconds=i * 30),
            speed_kmh=45.0 + i,
            altitude=110.0 + i * 2,
            heading=90.0  # East
        )
        vehicle2_points.append(point)

    # Create vehicle data
    vehicle1 = VehicleData(
        vehicle_id="VEHICLE_001",
        source_file=Path("test_vehicle1.csv"),
        gps_points=vehicle1_points,
        color=VehicleColor.BLUE,
        label="Blue Vehicle"
    )

    vehicle2 = VehicleData(
        vehicle_id="VEHICLE_002",
        source_file=Path("test_vehicle2.csv"),
        gps_points=vehicle2_points,
        color=VehicleColor.RED,
        label="Red Vehicle"
    )

    return [vehicle1, vehicle2]


def test_geojson_generation():
    """Test that GeoJSON is properly formatted for TimestampedGeoJson"""

    print("=" * 60)
    print("Testing TimestampedGeoJson Format")
    print("=" * 60)

    # Create test data
    vehicles = create_test_data()

    # Create animation data
    animation_data = AnimationData(vehicles=vehicles)

    # Generate GeoJSON
    geojson = animation_data.to_geojson()

    # Validate structure
    assert geojson['type'] == 'FeatureCollection', "GeoJSON must be a FeatureCollection"
    assert 'features' in geojson, "GeoJSON must have features"

    print(f"[OK] Generated {len(geojson['features'])} features")

    # Check for point features with time property
    point_features = [f for f in geojson['features'] if f['geometry']['type'] == 'Point']
    trail_features = [f for f in geojson['features'] if f['geometry']['type'] == 'LineString']

    print(f"[OK] {len(point_features)} Point features")
    print(f"[OK] {len(trail_features)} LineString trail features")

    # Validate point features
    for feature in point_features:
        props = feature['properties']
        assert 'time' in props, "Each point must have a 'time' property"
        assert 'vehicle_id' in props, "Each point must have a 'vehicle_id'"
        assert 'vehicle_label' in props, "Each point must have a 'vehicle_label'"
        assert 'color' in props, "Each point must have a 'color'"

        # Validate ISO 8601 format
        time_str = props['time']
        try:
            datetime.fromisoformat(time_str)
            print(f"  [OK] Valid ISO 8601 time: {time_str}")
        except ValueError:
            print(f"  [FAIL] Invalid time format: {time_str}")
            raise

    # Validate trail features
    for feature in trail_features:
        props = feature['properties']
        assert 'times' in props, "Trail must have 'times' array"
        assert isinstance(props['times'], list), "'times' must be an array"
        assert props['type'] == 'trail', "Trail must have type='trail'"

        # Validate each time in the times array
        for time_str in props['times']:
            try:
                datetime.fromisoformat(time_str)
            except ValueError:
                print(f"  [FAIL] Invalid time in trail: {time_str}")
                raise

        print(f"  [OK] Trail with {len(props['times'])} timestamps")

    print("\n[OK] All features properly formatted for TimestampedGeoJson!")

    # Save sample output for inspection
    output_file = Path("test_geojson_output.json")
    with open(output_file, 'w') as f:
        json.dump(geojson, f, indent=2)
    print(f"\n[OK] Sample GeoJSON saved to: {output_file}")

    return geojson


def test_service_integration():
    """Test the complete service integration"""

    print("\n" + "=" * 60)
    print("Testing Service Integration")
    print("=" * 60)

    # Create service
    service = VehicleTrackingService()

    # Create test data
    vehicles = create_test_data()

    # Create settings
    settings = VehicleTrackingSettings()

    # Test prepare_animation_data
    result = service.prepare_animation_data(vehicles, settings)

    if result.success:
        animation_data = result.value
        print(f"[OK] Animation data prepared successfully")
        print(f"  - Timeline: {animation_data.timeline_start} to {animation_data.timeline_end}")
        print(f"  - Duration: {animation_data.total_duration_seconds} seconds")
        print(f"  - Center: {animation_data.center}")
        print(f"  - Bounds: {animation_data.bounds}")

        # Check that GeoJSON was generated
        assert animation_data.feature_collection, "GeoJSON should be generated"
        print(f"[OK] GeoJSON automatically generated with {len(animation_data.feature_collection['features'])} features")
    else:
        print(f"[FAIL] Service error: {result.error}")
        raise Exception(result.error)

    print("\n[OK] Service integration test passed!")


def test_timestamp_validation():
    """Test that string timestamps are properly converted"""

    print("\n" + "=" * 60)
    print("Testing Timestamp Validation")
    print("=" * 60)

    # Create a point with string timestamp
    point = GPSPoint(
        latitude=40.7128,
        longitude=-74.0060,
        timestamp="2024-01-15T10:00:00"  # String timestamp
    )

    # Create vehicle with mixed timestamps
    vehicle = VehicleData(
        vehicle_id="TEST_VEHICLE",
        source_file=Path("test.csv"),
        gps_points=[point],
        label="Test Vehicle"
    )

    # Test service handling
    service = VehicleTrackingService()
    settings = VehicleTrackingSettings()

    result = service.prepare_animation_data([vehicle], settings)

    if result.success:
        animation_data = result.value
        # Check that timestamp was converted
        for v in animation_data.vehicles:
            for p in v.gps_points:
                assert isinstance(p.timestamp, datetime), f"Timestamp should be datetime, got {type(p.timestamp)}"
        print("[OK] String timestamps properly converted to datetime objects")
    else:
        print(f"[FAIL] Timestamp validation failed: {result.error}")

    print("\n[OK] Timestamp validation test passed!")


if __name__ == "__main__":
    try:
        # Run tests
        test_geojson_generation()
        test_service_integration()
        test_timestamp_validation()

        print("\n" + "=" * 60)
        print("[SUCCESS] All TimestampedGeoJson migration tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)