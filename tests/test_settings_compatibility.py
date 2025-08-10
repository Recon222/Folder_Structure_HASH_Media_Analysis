#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test SettingsManager compatibility with QSettings API
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.settings_manager import SettingsManager


def test_qsettings_compatibility():
    """Test that SettingsManager works with QSettings API"""
    print("Testing SettingsManager QSettings API compatibility...")
    
    # Create a test instance
    settings = SettingsManager()
    
    # Test value() method with type parameter
    print("\n1. Testing value() method:")
    
    # Test boolean type conversion
    result = settings.value('calculate_hashes', True, type=bool)
    print(f"   calculate_hashes (bool): {result} - type: {type(result)}")
    assert isinstance(result, bool), f"Expected bool, got {type(result)}"
    
    # Test integer type conversion
    result = settings.value('zip_compression_level', 6, type=int)
    print(f"   zip_compression_level (int): {result} - type: {type(result)}")
    assert isinstance(result, (int, type(None))), f"Expected int or None, got {type(result)}"
    
    # Test string type conversion
    result = settings.value('technician_name', 'Default Tech', type=str)
    print(f"   technician_name (str): {result} - type: {type(result)}")
    assert isinstance(result, str), f"Expected str, got {type(result)}"
    
    # Test without type parameter
    result = settings.value('auto_create_zip', False)
    print(f"   auto_create_zip (no type): {result}")
    
    print("\n2. Testing setValue() method:")
    
    # Test setting a value
    test_key = 'test_key_for_compatibility'
    test_value = 'test_value_123'
    settings.setValue(test_key, test_value)
    
    # Verify it was set
    retrieved = settings.value(test_key)
    print(f"   Set '{test_key}' = '{test_value}'")
    print(f"   Retrieved: '{retrieved}'")
    assert retrieved == test_value, f"Expected '{test_value}', got '{retrieved}'"
    
    print("\n3. Testing legacy key mapping:")
    
    # Test that legacy keys are mapped correctly
    legacy_keys = [
        ('calculate_hashes', 'forensic.calculate_hashes'),
        ('generate_time_offset_pdf', 'reports.generate_time_offset'),
        ('zip_at_root', 'archive.create_at_root'),
        ('prompt_for_zip', 'archive.prompt_user')
    ]
    
    for legacy, canonical in legacy_keys:
        # The get method should handle the mapping
        result = settings.get(legacy)
        print(f"   {legacy} -> {canonical}: {result}")
    
    print("\n4. Testing contains() method:")
    result = settings.contains('calculate_hashes')
    print(f"   contains('calculate_hashes'): {result}")
    
    print("\n5. Testing sync() method:")
    settings.sync()
    print("   sync() called successfully")
    
    print("\n[SUCCESS] All compatibility tests passed!")
    return True


def test_property_access():
    """Test convenience properties"""
    print("\nTesting SettingsManager convenience properties...")
    
    settings = SettingsManager()
    
    properties = [
        'calculate_hashes',
        'technician_name',
        'badge_number',
        'copy_buffer_size',
        'zip_compression_level',
        'auto_create_zip',
        'prompt_for_zip',
        'generate_time_offset_pdf',
        'generate_upload_log_pdf'
    ]
    
    for prop in properties:
        if hasattr(settings, prop):
            value = getattr(settings, prop)
            print(f"   {prop}: {value} (type: {type(value).__name__})")
        else:
            print(f"   [WARNING] Property {prop} not found")
    
    print("\n[SUCCESS] Property access tests completed!")
    return True


def main():
    """Run all tests"""
    print("="*60)
    print("SettingsManager Compatibility Tests")
    print("="*60)
    
    try:
        test_qsettings_compatibility()
        test_property_access()
        
        print("\n" + "="*60)
        print("[SUCCESS] All SettingsManager tests passed!")
        print("="*60)
        return 0
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())