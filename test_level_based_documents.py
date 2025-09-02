#!/usr/bin/env python3
"""
Test script for level-based documents placement
"""

import sys
from pathlib import Path
from core.services.path_service import PathService
from core.models import FormData

def test_level_based_placement():
    """Test the new level-based documents placement"""
    print("Testing Level-Based Documents Placement\n" + "="*50)
    
    # Initialize PathService
    path_service = PathService()
    
    # Create test form data
    form_data = FormData()
    form_data.occurrence_number = "2024-001"
    form_data.business_name = "Test Store"
    form_data.location_address = "123 Main St"
    
    # Create test paths
    output_dir = Path("/tmp/test_output")
    base_path = output_dir / "2024-001" / "Test Store @ 123 Main St" / "01JAN24_1200"
    
    print(f"Output directory: {output_dir}")
    print(f"Base forensic path (deepest level): {base_path}")
    print()
    
    # Test 1: Check legacy string conversion
    print("Test 1: Legacy String Conversion")
    print("-" * 30)
    
    # Test with string values
    for legacy_value, expected_level in [("occurrence", 0), ("location", 1), ("datetime", 2)]:
        # Simulate template with legacy string
        path_service._templates["test_template"] = {
            "documentsPlacement": legacy_value,
            "structure": {
                "levels": [
                    {"pattern": "{occurrence_number}"},
                    {"pattern": "{business_name} @ {location_address}"},
                    {"pattern": "{video_start_datetime}"}
                ]
            }
        }
        path_service._current_template_id = "test_template"
        
        result = path_service.determine_documents_location(base_path, output_dir)
        if result.success:
            documents_path = result.value
            # Calculate what level this actually is
            relative = documents_path.parent.relative_to(output_dir)
            actual_level = len(relative.parts)
            print(f"  '{legacy_value}' -> Level {expected_level}: {documents_path}")
            print(f"    Actual level: {actual_level}")
        else:
            print(f"  Error: {result.error}")
    
    print()
    
    # Test 2: Test with integer values
    print("Test 2: Integer Level Placement")
    print("-" * 30)
    
    for level in [0, 1, 2]:
        # Simulate template with integer level
        path_service._templates["test_template"] = {
            "documentsPlacement": level,
            "structure": {
                "levels": [
                    {"name": "Case", "pattern": "{occurrence_number}"},
                    {"name": "Location", "pattern": "{business_name} @ {location_address}"},
                    {"name": "Timeline", "pattern": "{video_start_datetime}"}
                ]
            }
        }
        path_service._current_template_id = "test_template"
        
        result = path_service.determine_documents_location(base_path, output_dir)
        if result.success:
            documents_path = result.value
            print(f"  Level {level}: {documents_path}")
        else:
            print(f"  Error: {result.error}")
    
    print()
    
    # Test 3: Test with different template depths
    print("Test 3: Different Template Depths")
    print("-" * 30)
    
    # 2-level template
    path_service._templates["shallow"] = {
        "documentsPlacement": 1,
        "structure": {
            "levels": [
                {"name": "Project", "pattern": "{occurrence_number}"},
                {"name": "Date", "pattern": "{current_datetime}"}
            ]
        }
    }
    
    # 5-level template
    path_service._templates["deep"] = {
        "documentsPlacement": 3,
        "structure": {
            "levels": [
                {"name": "Year", "pattern": "{year}"},
                {"name": "Agency", "pattern": "AGENCY"},
                {"name": "Case", "pattern": "{occurrence_number}"},
                {"name": "Evidence", "pattern": "Evidence"},
                {"name": "Timeline", "pattern": "{video_start_datetime}"}
            ]
        }
    }
    
    # Test shallow template
    path_service._current_template_id = "shallow"
    shallow_base = output_dir / "2024-001" / "2024-01-01"
    result = path_service.determine_documents_location(shallow_base, output_dir)
    if result.success:
        print(f"  2-level template, placement at level 1: {result.value}")
    
    # Test deep template
    path_service._current_template_id = "deep"
    deep_base = output_dir / "2024" / "AGENCY" / "2024-001" / "Evidence" / "01JAN24"
    result = path_service.determine_documents_location(deep_base, output_dir)
    if result.success:
        print(f"  5-level template, placement at level 3: {result.value}")
    
    print()
    
    # Test 4: Test edge cases
    print("Test 4: Edge Cases")
    print("-" * 30)
    
    # Test with invalid level (too high)
    path_service._templates["test_template"]["documentsPlacement"] = 10
    result = path_service.determine_documents_location(base_path, output_dir)
    if result.success:
        print(f"  Level 10 (exceeds template): {result.value}")
    
    # Test with negative level
    path_service._templates["test_template"]["documentsPlacement"] = -1
    result = path_service.determine_documents_location(base_path, output_dir)
    if result.success:
        print(f"  Level -1 (negative): {result.value}")
    
    print("\n" + "="*50)
    print("All tests completed!")

if __name__ == "__main__":
    test_level_based_placement()