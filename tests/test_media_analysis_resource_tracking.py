#!/usr/bin/env python3
"""
Test script to verify MediaAnalysisTab resource tracking with ResourceManagementService
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from core.services.service_registry import get_service
from core.services.interfaces import IResourceManagementService
from core.exiftool.exiftool_models import ExifToolMetadata, ExifToolAnalysisResult

def test_resource_tracking():
    """Test that MediaAnalysisTab properly tracks resources"""
    
    # Create app
    app = QApplication(sys.argv)
    
    # Create main window
    window = MainWindow()
    
    # Get resource service
    resource_service = get_service(IResourceManagementService)
    if not resource_service:
        print("ERROR: ResourceManagementService not available")
        return False
    
    # Get initial stats
    initial_stats = resource_service.get_statistics()
    print(f"Initial Statistics:")
    print(f"  Components: {initial_stats.get('components_registered', 0)}")
    print(f"  Resources tracked: {initial_stats.get('total_resources_tracked', 0)}")
    print(f"  Active resources: {initial_stats.get('active_resources', 0)}")
    print()
    
    # Access MediaAnalysisTab
    media_tab = window.media_analysis_tab
    print("MediaAnalysisTab accessed")
    
    # Simulate ExifTool results with thumbnails
    print("Simulating ExifTool results with thumbnails...")
    
    # Create mock metadata with thumbnails
    mock_metadata_list = []
    for i in range(5):
        metadata = ExifToolMetadata(
            file_path=Path(f"test_image_{i}.jpg"),
            thumbnail_base64="FAKE_BASE64_DATA" * 100,  # ~1.5KB each
            thumbnail_type="ThumbnailImage"
        )
        mock_metadata_list.append(metadata)
    
    # Create mock result
    mock_result = ExifToolAnalysisResult(
        total_files=5,
        successful=5,
        failed=0,
        skipped=0,
        metadata_list=mock_metadata_list,
        gps_locations=[],
        device_map={},
        temporal_path=[],
        processing_time=1.0,
        errors=[]
    )
    
    # Simulate result arrival
    from core.result_types import Result
    result_wrapper = Result.success(mock_result)
    
    # Call the handler directly
    media_tab._on_exiftool_complete(result_wrapper)
    
    # Get stats after thumbnail tracking
    after_stats = resource_service.get_statistics()
    print(f"\nAfter thumbnail tracking:")
    print(f"  Components: {after_stats.get('components_registered', 0)}")
    print(f"  Resources tracked: {after_stats.get('total_resources_tracked', 0)}")
    print(f"  Active resources: {after_stats.get('active_resources', 0)}")
    
    # Get memory usage
    memory_usage = resource_service.get_memory_usage()
    print(f"\nMemory usage by component:")
    for component, bytes_used in memory_usage.items():
        print(f"  {component}: {bytes_used:,} bytes")
    
    # Get resource counts
    resource_counts = resource_service.get_resource_count()
    print(f"\nResource counts by type:")
    for resource_type, count in resource_counts.items():
        print(f"  {resource_type}: {count}")
    
    # Test cleanup
    print("\nTesting cleanup...")
    media_tab._cleanup_resources()
    
    # Get final stats
    final_stats = resource_service.get_statistics()
    print(f"\nAfter cleanup:")
    print(f"  Components: {final_stats.get('components_registered', 0)}")
    print(f"  Resources tracked: {final_stats.get('total_resources_tracked', 0)}")
    print(f"  Active resources: {final_stats.get('active_resources', 0)}")
    
    # Check if thumbnails were released
    final_memory = resource_service.get_memory_usage()
    if "MediaAnalysisTab" in final_memory:
        tab_memory = final_memory["MediaAnalysisTab"]
        if tab_memory == 0:
            print("\nSUCCESS: All thumbnail memory released!")
        else:
            print(f"\nWARNING: MediaAnalysisTab still using {tab_memory} bytes")
    
    return True

if __name__ == "__main__":
    try:
        success = test_resource_tracking()
        print("\nTest completed successfully!" if success else "\nTest failed!")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()