#!/usr/bin/env python3
"""
Test ExifTool thumbnail extraction functionality
"""

import sys
import json
import subprocess
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from core.exiftool.exiftool_models import ExifToolSettings
from core.exiftool.exiftool_command_builder import ExifToolForensicCommandBuilder
from core.exiftool.exiftool_normalizer import ExifToolNormalizer
from core.logger import logger

def test_thumbnail_command_generation():
    """Test that thumbnail extraction commands are generated correctly"""
    print("\n" + "="*60)
    print("THUMBNAIL COMMAND GENERATION TEST")
    print("="*60 + "\n")
    
    builder = ExifToolForensicCommandBuilder()
    
    # Test with thumbnails disabled
    settings_no_thumb = ExifToolSettings()
    settings_no_thumb.extract_thumbnails = False
    
    cmd_no_thumb = builder._build_base_command(Path("exiftool"), settings_no_thumb)
    has_thumbnail_tags = any('-ThumbnailImage' in cmd_no_thumb or 
                            '-PreviewImage' in cmd_no_thumb or 
                            '-JpgFromRaw' in cmd_no_thumb 
                            for tag in cmd_no_thumb)
    
    print(f"Thumbnails disabled - Has thumbnail tags: {has_thumbnail_tags}")
    assert not has_thumbnail_tags, "Should not have thumbnail tags when disabled"
    print("  PASS PASSED: No thumbnail tags when disabled\n")
    
    # Test with thumbnails enabled
    settings_with_thumb = ExifToolSettings()
    settings_with_thumb.extract_thumbnails = True
    
    cmd_with_thumb = builder._build_base_command(Path("exiftool"), settings_with_thumb)
    
    print(f"Thumbnails enabled - Command includes:")
    print(f"  -ThumbnailImage: {'-ThumbnailImage' in cmd_with_thumb}")
    print(f"  -PreviewImage: {'-PreviewImage' in cmd_with_thumb}")
    print(f"  -JpgFromRaw: {'-JpgFromRaw' in cmd_with_thumb}")
    print(f"  -b flag: {'-b' in cmd_with_thumb}")
    
    assert '-ThumbnailImage' in cmd_with_thumb, "Should have -ThumbnailImage"
    assert '-PreviewImage' in cmd_with_thumb, "Should have -PreviewImage"
    assert '-JpgFromRaw' in cmd_with_thumb, "Should have -JpgFromRaw"
    assert '-b' in cmd_with_thumb, "Should have -b flag for binary data"
    
    print("  PASS PASSED: All thumbnail tags present when enabled\n")
    
    return True

def test_thumbnail_extraction_simulation():
    """Test thumbnail extraction from simulated ExifTool output"""
    print("\n" + "="*60)
    print("THUMBNAIL EXTRACTION SIMULATION TEST")
    print("="*60 + "\n")
    
    normalizer = ExifToolNormalizer()
    
    # Simulate ExifTool output with base64 thumbnail
    test_cases = [
        {
            "name": "With ThumbnailImage",
            "raw_data": {
                "SourceFile": "/path/to/image.jpg",
                "FileType": "JPEG",
                "ThumbnailImage": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg==",  # 1x1 transparent PNG
                "GPSLatitude": "43.786011",
                "GPSLongitude": "-79.731689"
            },
            "expected_type": "ThumbnailImage"
        },
        {
            "name": "With PreviewImage only",
            "raw_data": {
                "SourceFile": "/path/to/raw.cr2",
                "FileType": "CR2",
                "PreviewImage": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg==",
                "GPSLatitude": "43.786011",
                "GPSLongitude": "-79.731689"
            },
            "expected_type": "PreviewImage"
        },
        {
            "name": "Without thumbnail",
            "raw_data": {
                "SourceFile": "/path/to/video.mp4",
                "FileType": "MP4",
                "GPSLatitude": "43.786011",
                "GPSLongitude": "-79.731689"
            },
            "expected_type": None
        }
    ]
    
    all_passed = True
    
    for test in test_cases:
        print(f"Test: {test['name']}")
        print("-" * 40)
        
        # Normalize the data
        metadata = normalizer.normalize(
            test['raw_data'],
            Path(test['raw_data']['SourceFile'])
        )
        
        # Check thumbnail extraction
        if test['expected_type']:
            if metadata.thumbnail_base64:
                print(f"  PASS Thumbnail extracted")
                print(f"  Type: {metadata.thumbnail_type}")
                print(f"  Base64 length: {len(metadata.thumbnail_base64)}")
                
                if metadata.thumbnail_type != test['expected_type']:
                    print(f"  FAIL Expected type {test['expected_type']}, got {metadata.thumbnail_type}")
                    all_passed = False
                else:
                    print(f"  PASS Correct thumbnail type")
            else:
                print(f"  FAIL No thumbnail extracted (expected {test['expected_type']})")
                all_passed = False
        else:
            if metadata.thumbnail_base64:
                print(f"  FAIL Unexpected thumbnail extracted: {metadata.thumbnail_type}")
                all_passed = False
            else:
                print(f"  PASS No thumbnail (as expected)")
        
        print()
    
    return all_passed

def test_settings_mapping():
    """Test that UI settings are properly mapped"""
    print("\n" + "="*60)
    print("SETTINGS MAPPING TEST")
    print("="*60 + "\n")
    
    settings = ExifToolSettings()
    
    # Test default value
    print(f"Default extract_thumbnails: {settings.extract_thumbnails}")
    assert settings.extract_thumbnails == False, "Default should be False"
    print("  PASS PASSED: Default is False\n")
    
    # Test setting to True
    settings.extract_thumbnails = True
    print(f"After setting to True: {settings.extract_thumbnails}")
    assert settings.extract_thumbnails == True, "Should be True after setting"
    print("  PASS PASSED: Can be set to True\n")
    
    # Test serialization
    settings_dict = settings.to_dict()
    print(f"Serialized extract_thumbnails: {settings_dict.get('extract_thumbnails')}")
    assert 'extract_thumbnails' in settings_dict, "Should be in serialized dict"
    assert settings_dict['extract_thumbnails'] == True, "Should serialize correctly"
    print("  PASS PASSED: Serializes correctly\n")
    
    # Test deserialization
    new_settings = ExifToolSettings.from_dict(settings_dict)
    print(f"Deserialized extract_thumbnails: {new_settings.extract_thumbnails}")
    assert new_settings.extract_thumbnails == True, "Should deserialize correctly"
    print("  PASS PASSED: Deserializes correctly\n")
    
    return True

def main():
    """Run all thumbnail tests"""
    print("\n" + "="*60)
    print("EXIFTOOL THUMBNAIL EXTRACTION TESTS")
    print("="*60)
    
    tests = [
        ("Command Generation", test_thumbnail_command_generation),
        ("Extraction Simulation", test_thumbnail_extraction_simulation),
        ("Settings Mapping", test_settings_mapping)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\nFAIL {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for test_name, passed in results:
        status = "PASS PASSED" if passed else "FAIL FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "="*60)
    if all_passed:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED!")
    print("="*60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())