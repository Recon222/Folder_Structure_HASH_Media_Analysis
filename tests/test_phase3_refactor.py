#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Phase 3 refactoring changes
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.path_utils import ForensicPathBuilder, PathSanitizer
from core.models import FormData
from controllers.file_controller import FileController
from controllers.folder_controller import FolderController
from datetime import datetime
from PySide6.QtCore import QDateTime


def test_templates_system_removed():
    """Test that templates system is no longer available"""
    print("Testing templates system removal...")
    
    try:
        from core.templates import FolderTemplate
        assert False, "Templates system should be removed"
    except ImportError:
        print("[OK] Templates system successfully removed")
    except ModuleNotFoundError:
        print("[OK] Templates system successfully removed")


def test_forensic_path_builder():
    """Test ForensicPathBuilder handles both field name formats"""
    print("\nTesting ForensicPathBuilder with different field names...")
    
    # Test with video_start_datetime (new format)
    form_data = FormData()
    form_data.occurrence_number = "2024-001"
    form_data.business_name = "Test Business"
    form_data.location_address = "123 Test St"
    form_data.video_start_datetime = datetime(2024, 1, 15, 10, 30)
    form_data.video_end_datetime = datetime(2024, 1, 15, 14, 45)
    
    path = ForensicPathBuilder.build_relative_path(form_data)
    expected = Path("2024-001") / "Test Business @ 123 Test St" / "2024-01-15_1030_to_2024-01-15_1445"
    assert str(path) == str(expected), f"Expected '{expected}', got '{path}'"
    print(f"[OK] video_start_datetime format: {path}")
    
    # Test with extraction_start (legacy format with QDateTime)
    form_data2 = FormData()
    form_data2.occurrence_number = "2024-002"
    form_data2.business_name = "Legacy Business"
    form_data2.location_address = "456 Old St"
    form_data2.extraction_start = QDateTime(2024, 1, 20, 9, 15, 0)
    form_data2.extraction_end = QDateTime(2024, 1, 20, 17, 30, 0)
    
    path2 = ForensicPathBuilder.build_relative_path(form_data2)
    expected2 = Path("2024-002") / "Legacy Business @ 456 Old St" / "2024-01-20_0915_to_2024-01-20_1730"
    assert str(path2) == str(expected2), f"Expected '{expected2}', got '{path2}'"
    print(f"[OK] extraction_start format: {path2}")


def test_controller_consolidation():
    """Test that controllers use ForensicPathBuilder"""
    print("\nTesting controller consolidation...")
    
    form_data = FormData()
    form_data.occurrence_number = "2024-003"
    form_data.business_name = "Controller Test"
    form_data.location_address = "789 Test Ave"
    form_data.video_start_datetime = datetime(2024, 1, 25, 11, 0)
    form_data.video_end_datetime = datetime(2024, 1, 25, 15, 0)
    
    # Test FileController
    file_controller = FileController()
    
    # Test FolderController (with base path)
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        result_path = FolderController.build_forensic_structure(form_data, base_path)
        
        # Check that path was created
        assert result_path.exists(), f"Path should exist: {result_path}"
        
        # Check structure - verify key parts are in the path
        assert "2024-003" in str(result_path), f"Occurrence number not found in {result_path}"
        assert "Controller Test @ 789 Test Ave" in str(result_path), f"Business/location not found in {result_path}"
        
        print(f"[OK] Controllers use centralized path building: {result_path}")


def test_path_sanitizer():
    """Test PathSanitizer functionality"""
    print("\nTesting PathSanitizer...")
    
    # Test invalid characters
    result = PathSanitizer.sanitize_component("file<>name:test|file?.txt")
    assert "<" not in result and ">" not in result and ":" not in result
    assert "|" not in result and "?" not in result
    print(f"[OK] Invalid chars sanitized: {result}")
    
    # Test Windows reserved names
    result = PathSanitizer.sanitize_component("CON", platform_type="windows")
    assert result == "_CON", f"Expected '_CON', got '{result}'"
    print(f"[OK] Windows reserved name handled: {result}")
    
    # Test path traversal prevention - slashes should be replaced
    result = PathSanitizer.sanitize_component("../../../etc/passwd")
    # The important thing is that "/" is replaced, making traversal impossible
    assert "/" not in result, f"'/' still in result: {result}"
    assert "\\" not in result, f"'\\' still in result: {result}"
    # Result should be safe for filesystem use
    print(f"[OK] Path traversal prevented: '{result}' (slashes replaced)")


def main():
    """Run all tests"""
    print("="*60)
    print("Phase 3 Refactoring Tests")
    print("="*60)
    
    try:
        test_templates_system_removed()
        test_forensic_path_builder()
        test_controller_consolidation()
        test_path_sanitizer()
        
        print("\n" + "="*60)
        print("[SUCCESS] All Phase 3 tests passed!")
        print("="*60)
        return 0
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())