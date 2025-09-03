#!/usr/bin/env python3
"""
Test GPS hemisphere handling in ExifToolNormalizer
Ensures proper longitude/latitude negation for West/South coordinates
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from core.exiftool.exiftool_normalizer import ExifToolNormalizer
from core.logger import logger

def test_hemisphere_handling():
    """Test various GPS hemisphere reference formats"""
    normalizer = ExifToolNormalizer()
    
    test_cases = [
        # Test case 1: Toronto coordinates with 'West' string
        {
            "name": "Toronto with 'West' string",
            "raw": {
                "GPSLatitude": "43 deg 47' 9.64\" N",
                "GPSLongitude": "79 deg 43' 54.08\" W",
                "GPSLatitudeRef": "North",
                "GPSLongitudeRef": "West"
            },
            "expected_lat": 43.786011,
            "expected_lon": -79.731689
        },
        # Test case 2: Sydney coordinates with 'S' and 'E'
        {
            "name": "Sydney with single letters",
            "raw": {
                "GPSLatitude": "33 deg 51' 35.9\" S",
                "GPSLongitude": "151 deg 12' 40.5\" E",
                "GPSLatitudeRef": "S",
                "GPSLongitudeRef": "E"
            },
            "expected_lat": -33.859972,
            "expected_lon": 151.211250
        },
        # Test case 3: Already negative values
        {
            "name": "Pre-negated values",
            "raw": {
                "GPSLatitude": -43.786011,
                "GPSLongitude": -79.731689,
                "GPSLatitudeRef": None,
                "GPSLongitudeRef": None
            },
            "expected_lat": -43.786011,
            "expected_lon": -79.731689
        },
        # Test case 4: Decimal with refs
        {
            "name": "Decimal with West ref",
            "raw": {
                "GPSLatitude": 43.786011,
                "GPSLongitude": 79.731689,
                "GPSLatitudeRef": "North",
                "GPSLongitudeRef": "W"
            },
            "expected_lat": 43.786011,
            "expected_lon": -79.731689
        },
        # Test case 5: Mixed format
        {
            "name": "Mixed South/West format",
            "raw": {
                "GPSLatitude": "33.859972",
                "GPSLongitude": "151.211250",
                "GPSLatitudeRef": "South",
                "GPSLongitudeRef": "West"
            },
            "expected_lat": -33.859972,
            "expected_lon": -151.211250
        }
    ]
    
    print("\n" + "="*60)
    print("GPS HEMISPHERE HANDLING TESTS")
    print("="*60 + "\n")
    
    all_passed = True
    
    for test in test_cases:
        print(f"Test: {test['name']}")
        print("-" * 40)
        
        # Extract GPS data
        gps_data = normalizer._extract_gps_data(test['raw'])
        
        if gps_data:
            lat, lon = gps_data.to_decimal_degrees()
            
            # Check results
            lat_passed = abs(lat - test['expected_lat']) < 0.000001
            lon_passed = abs(lon - test['expected_lon']) < 0.000001
            
            print(f"  Input GPS Lat: {test['raw'].get('GPSLatitude')}")
            print(f"  Input GPS Lon: {test['raw'].get('GPSLongitude')}")
            print(f"  Input Lat Ref: {test['raw'].get('GPSLatitudeRef')}")
            print(f"  Input Lon Ref: {test['raw'].get('GPSLongitudeRef')}")
            print(f"  Output Lat: {lat:.6f} (expected: {test['expected_lat']:.6f}) {'PASS' if lat_passed else 'FAIL'}")
            print(f"  Output Lon: {lon:.6f} (expected: {test['expected_lon']:.6f}) {'PASS' if lon_passed else 'FAIL'}")
            
            if not (lat_passed and lon_passed):
                all_passed = False
                print(f"  FAILED!")
            else:
                print(f"  PASSED!")
        else:
            print(f"  ERROR: No GPS data extracted!")
            all_passed = False
        
        print()
    
    print("="*60)
    if all_passed:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED!")
    print("="*60)
    
    return all_passed

if __name__ == "__main__":
    success = test_hemisphere_handling()
    sys.exit(0 if success else 1)