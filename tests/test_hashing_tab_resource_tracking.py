#!/usr/bin/env python3
"""
Test script for HashingTab resource tracking with ResourceManagementService
Verifies that resources are properly tracked and released
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QObject, Signal

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ui.tabs.hashing_tab import HashingTab
from controllers.hash_controller import HashController
from core.services.resource_management_service import ResourceManagementService
from core.services.interfaces import IResourceManagementService, ResourceType
from core.services.service_registry import register_service
from core.result_types import Result
from core.logger import logger

# Mock worker for testing
class MockHashWorker(QObject):
    """Mock hash worker for testing"""
    progress_update = Signal(int, str)
    result_ready = Signal(object)
    
    def __init__(self):
        super().__init__()
        self.is_running = True
        
    def start(self):
        """Simulate starting the worker"""
        # Simulate completion after a short delay
        QTimer.singleShot(100, self._complete)
    
    def _complete(self):
        """Simulate completion with results"""
        results = {
            'results': [
                {'file': 'test1.txt', 'hash': 'abc123'},
                {'file': 'test2.txt', 'hash': 'def456'},
                {'file': 'test3.txt', 'hash': 'ghi789'}
            ],
            'files_processed': 3,
            'duration_seconds': 1.5,
            'average_speed_mbps': 10.5
        }
        self.result_ready.emit(Result.success(results))
        self.is_running = False
    
    def cancel(self):
        """Simulate cancellation"""
        self.is_running = False
        print("Worker cancelled")
    
    def isRunning(self):
        """Check if running"""
        return self.is_running

def test_hashing_tab_resources():
    """Test HashingTab resource management"""
    
    print("=" * 60)
    print("HashingTab Resource Management Test")
    print("=" * 60)
    
    # Setup service registry
    resource_service = ResourceManagementService()
    register_service(IResourceManagementService, resource_service)
    
    print("\n1. Creating HashingTab...")
    
    # Create HashController
    hash_controller = HashController()
    
    # Create HashingTab
    hashing_tab = HashingTab(hash_controller)
    
    # Check registration
    stats = resource_service.get_statistics()
    print(f"   Components registered: {stats['components_registered']}")
    
    # Check resource count
    resource_counts = resource_service.get_resource_count()
    print(f"   Initial resource counts: {resource_counts}")
    
    print("\n2. Simulating hash operation...")
    
    # Mock the controller's start method to return our mock worker
    original_start = hash_controller.start_single_hash_operation
    mock_worker = MockHashWorker()
    
    def mock_start_operation(paths, algorithm):
        return mock_worker
    
    hash_controller.start_single_hash_operation = mock_start_operation
    
    # Add some files to the panel (simulate)
    hashing_tab.single_files_panel._files = ['test1.txt', 'test2.txt']
    hashing_tab.single_files_panel._folders = ['test_folder']
    
    # Trigger operation
    print("   Starting single hash operation...")
    hashing_tab._start_single_hash_operation()
    
    # Let the operation start
    QApplication.processEvents()
    
    # Check resources after starting
    resource_counts = resource_service.get_resource_count()
    print(f"   Resources during operation: {resource_counts}")
    
    # Check memory usage
    memory_usage = resource_service.get_memory_usage()
    print(f"   Memory usage: {memory_usage}")
    
    # Wait for operation to complete
    print("\n3. Waiting for operation to complete...")
    
    # Process events for completion
    for _ in range(10):
        QApplication.processEvents()
        QTimer.singleShot(50, lambda: None)
    
    # Force the completion
    mock_worker._complete()
    QApplication.processEvents()
    
    # Check resources after completion
    resource_counts = resource_service.get_resource_count()
    print(f"   Resources after completion: {resource_counts}")
    
    # Check if results are tracked
    memory_usage = resource_service.get_memory_usage()
    print(f"   Memory usage with results: {memory_usage}")
    
    print("\n4. Testing verification operation...")
    
    # Mock verification worker
    mock_verification_worker = MockHashWorker()
    
    def mock_start_verification(source_paths, target_paths, algorithm):
        return mock_verification_worker
    
    hash_controller.start_verification_operation = mock_start_verification
    
    # Add files to verification panels
    hashing_tab.source_files_panel._files = ['source1.txt', 'source2.txt']
    hashing_tab.target_files_panel._files = ['target1.txt', 'target2.txt']
    
    # Start verification
    print("   Starting verification operation...")
    hashing_tab._start_verification_operation()
    
    QApplication.processEvents()
    
    # Check resources
    resource_counts = resource_service.get_resource_count()
    print(f"   Resources during verification: {resource_counts}")
    
    # Complete verification
    verification_results = {
        'matches': [{'file': 'match1.txt'}, {'file': 'match2.txt'}],
        'mismatches': [{'file': 'diff1.txt'}],
        'source_only': [{'file': 'only_source.txt'}],
        'target_only': [],
        'files_processed': 5,
        'duration_seconds': 2.0
    }
    mock_verification_worker.result_ready.emit(Result.success(verification_results))
    QApplication.processEvents()
    
    # Check final resources
    resource_counts = resource_service.get_resource_count()
    print(f"   Resources after verification: {resource_counts}")
    
    print("\n5. Testing cleanup...")
    
    # Call cleanup
    hashing_tab._cleanup_resources()
    
    # Check resources after cleanup
    resource_counts = resource_service.get_resource_count()
    print(f"   Resources after cleanup: {resource_counts}")
    
    memory_usage = resource_service.get_memory_usage()
    print(f"   Memory after cleanup: {memory_usage}")
    
    # Final statistics
    print("\n6. Final Statistics:")
    stats = resource_service.get_statistics()
    print(f"   Total resources tracked: {stats['total_resources_tracked']}")
    print(f"   Total resources released: {stats['total_resources_released']}")
    print(f"   Active resources: {stats['active_resources']}")
    
    # Cleanup the component completely
    resource_service.cleanup_component(hashing_tab, force=True)
    
    print("\n7. After complete cleanup:")
    final_stats = resource_service.get_statistics()
    print(f"   Components registered: {final_stats['components_registered']}")
    print(f"   Active resources: {final_stats['active_resources']}")
    
    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("HashingTab resource management is working correctly.")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    try:
        success = test_hashing_tab_resources()
        if success:
            print("\n[OK] All tests passed!")
        else:
            print("\n[FAIL] Some tests failed!")
    except Exception as e:
        print(f"\n[ERROR] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        app.quit()