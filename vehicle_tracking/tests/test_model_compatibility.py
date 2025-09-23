#!/usr/bin/env python3
"""
Test that Phase 2 model updates don't break existing code.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def test_model_imports():
    """Test that all models import correctly with new fields."""
    try:
        from vehicle_tracking.models.vehicle_tracking_models import (
            GPSPoint, VehicleData, VehicleTrackingSettings, InterpolationMethod
        )
        print("[PASS] Model imports successful")
        return True
    except ImportError as e:
        print(f"[FAIL] Model import failed: {e}")
        return False

def test_gps_point_creation():
    """Test GPSPoint with new forensic fields."""
    try:
        from vehicle_tracking.models.vehicle_tracking_models import GPSPoint

        # Create with minimal fields
        point1 = GPSPoint(
            latitude=45.4215,
            longitude=-75.6972,
            timestamp=datetime.now()
        )
        assert point1.is_observed == True  # Default value
        assert point1.is_gap == False  # Default value
        assert point1.segment_speed_kmh is None

        # Create with forensic fields
        point2 = GPSPoint(
            latitude=45.4220,
            longitude=-75.6970,
            timestamp=datetime.now(),
            segment_speed_kmh=50.5,
            speed_certainty="high",
            segment_id=0,
            is_observed=False,
            is_gap=False
        )
        assert point2.segment_speed_kmh == 50.5
        assert point2.speed_certainty == "high"

        print("[PASS] GPSPoint creation with forensic fields works")
        return True
    except Exception as e:
        print(f"[FAIL] GPSPoint creation failed: {e}")
        return False

def test_vehicle_data_creation():
    """Test VehicleData with new forensic fields."""
    try:
        from vehicle_tracking.models.vehicle_tracking_models import VehicleData

        vehicle = VehicleData(
            vehicle_id="test_vehicle",
            source_file=Path("test.csv")
        )

        # Check new fields
        assert vehicle.has_segment_speeds == False
        assert vehicle.segments is None
        assert vehicle.speed_anomalies is None

        print("[PASS] VehicleData creation with forensic fields works")
        return True
    except Exception as e:
        print(f"[FAIL] VehicleData creation failed: {e}")
        return False

def test_settings_creation():
    """Test VehicleTrackingSettings with forensic thresholds."""
    try:
        from vehicle_tracking.models.vehicle_tracking_models import VehicleTrackingSettings

        settings = VehicleTrackingSettings()

        # Check new forensic thresholds
        assert settings.high_certainty_threshold_s == 5.0
        assert settings.medium_certainty_threshold_s == 10.0
        assert settings.max_gap_threshold_s == 30.0
        assert settings.duplicate_timestamp_min_delta == 0.5
        assert settings.show_certainty_indicators == True
        assert settings.highlight_low_certainty == True
        assert settings.show_gap_markers == True

        print("[PASS] VehicleTrackingSettings with forensic thresholds works")
        return True
    except Exception as e:
        print(f"[FAIL] VehicleTrackingSettings creation failed: {e}")
        return False

def test_forensic_models():
    """Test that forensic models import correctly."""
    try:
        from vehicle_tracking.models.forensic_models import (
            SpeedCertainty, SegmentSpeed, GPSSegment
        )

        # Test enum
        assert SpeedCertainty.HIGH.value == "high"
        assert SpeedCertainty.UNKNOWN.value == "unknown"

        print("[PASS] Forensic models import successful")
        return True
    except Exception as e:
        print(f"[FAIL] Forensic models import failed: {e}")
        return False

def main():
    """Run all compatibility tests."""
    print("=" * 60)
    print("Phase 2 Model Compatibility Tests")
    print("=" * 60)

    tests = [
        test_model_imports,
        test_gps_point_creation,
        test_vehicle_data_creation,
        test_settings_creation,
        test_forensic_models
    ]

    results = []
    for test in tests:
        results.append(test())
        print()

    # Summary
    passed = sum(results)
    total = len(results)

    print("=" * 60)
    if passed == total:
        print(f"SUCCESS: ALL TESTS PASSED ({passed}/{total})")
        print("Model updates are backward compatible!")
    else:
        print(f"FAILURE: SOME TESTS FAILED ({passed}/{total} passed)")
        print("Please fix compatibility issues before proceeding.")
    print("=" * 60)

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)