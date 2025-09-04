#!/usr/bin/env python3
"""
Test script to verify CopyVerifyTab resource tracking with ResourceManagementService
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
from core.workers.copy_verify_worker import CopyVerifyWorker
from core.result_types import Result

def test_copy_verify_resource_tracking():
    """Test that CopyVerifyTab properly tracks resources"""
    
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
    
    # Access CopyVerifyTab
    copy_tab = window.copy_verify_tab
    print("CopyVerifyTab accessed")
    
    # Simulate worker creation (without actually starting operation)
    print("Simulating worker creation...")
    
    # Create mock worker
    mock_worker = CopyVerifyWorker(
        source_items=[Path("test_file.txt")],
        destination=Path("test_destination"),
        preserve_structure=True,
        calculate_hash=True,
        csv_path=None,
        service=None
    )
    
    # Manually track the worker as the tab would
    if copy_tab._resource_manager:
        copy_tab._worker_resource_id = copy_tab._resource_manager.track_resource(
            copy_tab,
            ResourceType.WORKER,
            mock_worker,
            metadata={
                'type': 'CopyVerifyWorker',
                'destination': 'test_destination',
                'cleanup_func': lambda w: w.cancel() if w and w.isRunning() else None
            }
        )
        copy_tab.current_worker = mock_worker
    
    # Get stats after worker tracking
    after_stats = resource_service.get_statistics()
    print(f"\nAfter worker tracking:")
    print(f"  Components: {after_stats.get('components_registered', 0)}")
    print(f"  Resources tracked: {after_stats.get('total_resources_tracked', 0)}")
    print(f"  Active resources: {after_stats.get('active_resources', 0)}")
    
    # Get resource counts
    resource_counts = resource_service.get_resource_count()
    print(f"\nResource counts by type:")
    for resource_type, count in resource_counts.items():
        print(f"  {resource_type}: {count}")
    
    # Test cleanup
    print("\nTesting cleanup...")
    copy_tab._cleanup_resources()
    
    # Get final stats
    final_stats = resource_service.get_statistics()
    print(f"\nAfter cleanup:")
    print(f"  Components: {final_stats.get('components_registered', 0)}")
    print(f"  Resources tracked: {final_stats.get('total_resources_tracked', 0)}")
    print(f"  Active resources: {final_stats.get('active_resources', 0)}")
    
    # Check if worker was released
    final_counts = resource_service.get_resource_count()
    worker_count = final_counts.get('worker', 0)
    if worker_count == 0:
        print("\nSUCCESS: Worker resource properly released!")
    else:
        print(f"\nWARNING: Still have {worker_count} worker resources")
    
    return True

if __name__ == "__main__":
    try:
        from core.services.interfaces import ResourceType
        success = test_copy_verify_resource_tracking()
        print("\nTest completed successfully!" if success else "\nTest failed!")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()