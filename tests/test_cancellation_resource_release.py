#!/usr/bin/env python3
"""
Test script to verify resource release on operation cancellation
Tests that worker resources are properly released when operations are cancelled
"""

import sys
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.services.service_config import configure_services
from core.services.service_registry import get_service
from core.services.interfaces import IResourceManagementService, ResourceType
from ui.tabs.hashing_tab import HashingTab
from ui.tabs.copy_verify_tab import CopyVerifyTab
from ui.tabs.media_analysis_tab import MediaAnalysisTab
from controllers.hash_controller import HashController


def test_hashing_tab_cancellation():
    """Test HashingTab resource release on cancellation"""
    
    print("\n" + "="*60)
    print("Testing HashingTab Cancellation Resource Release")
    print("="*60 + "\n")
    
    # Initialize services
    configure_services()
    
    # Get resource manager
    resource_manager = get_service(IResourceManagementService)
    if not resource_manager:
        print("[ERROR] ResourceManagementService not available")
        return False
    
    # Create HashingTab with controller
    hash_controller = HashController()
    hashing_tab = HashingTab(hash_controller)
    
    print("[TEST] HashingTab created")
    
    # Get initial resource count
    initial_resources = resource_manager.get_resource_count()
    print(f"Initial resources: {initial_resources}")
    
    # Simulate starting a hash operation (without actually processing files)
    print("\n[TEST] Simulating hash operation start...")
    
    # Manually set operation active to simulate
    hashing_tab._set_operation_active(True)
    
    # Check if controller can create a worker (without files)
    from core.workers.hash_worker import SingleHashWorker
    
    # Create a mock worker with empty file list
    mock_worker = SingleHashWorker([], "sha256")
    
    # Track it as HashingTab would
    if hashing_tab._resource_manager:
        hashing_tab._worker_resource_id = hashing_tab._resource_manager.track_resource(
            hashing_tab,
            ResourceType.WORKER,
            mock_worker,
            metadata={
                'type': 'SingleHashWorker',
                'file_count': 0,
                'algorithm': 'sha256',
                'cleanup_func': lambda w: w.cancel() if w and w.isRunning() else None
            }
        )
    
    # Check resources after worker creation
    with_worker_resources = resource_manager.get_resource_count()
    print(f"Resources with worker: {with_worker_resources}")
    
    if with_worker_resources.get('worker', 0) > initial_resources.get('worker', 0):
        print("[OK] Worker resource tracked")
    else:
        print("[ERROR] Worker resource not tracked")
    
    # Now test cancellation
    print("\n[TEST] Cancelling operation...")
    
    # Call the cancel method
    hashing_tab.hash_controller._current_operation = mock_worker
    hashing_tab._cancel_all_operations()
    
    # Check resources after cancellation
    after_cancel_resources = resource_manager.get_resource_count()
    print(f"Resources after cancel: {after_cancel_resources}")
    
    if after_cancel_resources.get('worker', 0) == initial_resources.get('worker', 0):
        print("[OK] Worker resource released on cancellation")
    else:
        print("[ERROR] Worker resource NOT released on cancellation")
    
    # Cleanup
    hashing_tab._cleanup_resources()
    
    print("\n" + "="*60)
    print("HashingTab Cancellation Test Complete")
    print("="*60)
    
    return True


def test_copy_verify_tab_cancellation():
    """Test CopyVerifyTab resource release on cancellation"""
    
    print("\n" + "="*60)
    print("Testing CopyVerifyTab Cancellation Resource Release")
    print("="*60 + "\n")
    
    # Get resource manager
    resource_manager = get_service(IResourceManagementService)
    
    # Create CopyVerifyTab
    copy_tab = CopyVerifyTab()
    
    print("[TEST] CopyVerifyTab created")
    
    # Get initial resource count
    initial_resources = resource_manager.get_resource_count()
    print(f"Initial resources: {initial_resources}")
    
    # Create a mock worker
    from core.workers.copy_verify_worker import CopyVerifyWorker
    mock_worker = CopyVerifyWorker([], Path("/tmp"))
    
    # Set it as current worker and track it
    copy_tab.current_worker = mock_worker
    copy_tab.operation_active = True
    
    if copy_tab._resource_manager:
        copy_tab._worker_resource_id = copy_tab._resource_manager.track_resource(
            copy_tab,
            ResourceType.WORKER,
            mock_worker,
            metadata={
                'type': 'CopyVerifyWorker',
                'destination': '/tmp',
                'cleanup_func': lambda w: w.cancel() if w and w.isRunning() else None
            }
        )
    
    # Check resources after worker creation
    with_worker_resources = resource_manager.get_resource_count()
    print(f"Resources with worker: {with_worker_resources}")
    
    if with_worker_resources.get('worker', 0) > initial_resources.get('worker', 0):
        print("[OK] Worker resource tracked")
    else:
        print("[ERROR] Worker resource not tracked")
    
    # Test cancellation
    print("\n[TEST] Cancelling operation...")
    copy_tab._cancel_operation()
    
    # Check resources after cancellation
    after_cancel_resources = resource_manager.get_resource_count()
    print(f"Resources after cancel: {after_cancel_resources}")
    
    if after_cancel_resources.get('worker', 0) == initial_resources.get('worker', 0):
        print("[OK] Worker resource released on cancellation")
    else:
        print("[ERROR] Worker resource NOT released on cancellation")
    
    # Cleanup
    copy_tab._cleanup_resources()
    
    print("\n" + "="*60)
    print("CopyVerifyTab Cancellation Test Complete")
    print("="*60)
    
    return True


def test_media_analysis_tab_cancellation():
    """Test MediaAnalysisTab resource release on cancellation"""
    
    print("\n" + "="*60)
    print("Testing MediaAnalysisTab Cancellation Resource Release")
    print("="*60 + "\n")
    
    # Get resource manager
    resource_manager = get_service(IResourceManagementService)
    
    # Create MediaAnalysisTab
    media_tab = MediaAnalysisTab()
    
    print("[TEST] MediaAnalysisTab created")
    
    # Get initial resource count
    initial_resources = resource_manager.get_resource_count()
    print(f"Initial resources: {initial_resources}")
    
    # Create a mock worker
    from core.workers.media_analysis_worker import MediaAnalysisWorker
    mock_worker = MediaAnalysisWorker([])
    
    # Set it as current worker and track it
    media_tab.current_worker = mock_worker
    media_tab.operation_active = True
    
    if media_tab._resource_manager:
        media_tab._worker_resource_id = media_tab._resource_manager.track_resource(
            media_tab,
            ResourceType.WORKER,
            mock_worker,
            metadata={
                'type': 'MediaScannerWorker',
                'cleanup_func': lambda w: w.cancel() if w and w.isRunning() else None
            }
        )
    
    # Check resources after worker creation
    with_worker_resources = resource_manager.get_resource_count()
    print(f"Resources with worker: {with_worker_resources}")
    
    if with_worker_resources.get('worker', 0) > initial_resources.get('worker', 0):
        print("[OK] Worker resource tracked")
    else:
        print("[ERROR] Worker resource not tracked")
    
    # Test cancellation
    print("\n[TEST] Cancelling operation...")
    media_tab._cancel_operation()
    
    # Check resources after cancellation
    after_cancel_resources = resource_manager.get_resource_count()
    print(f"Resources after cancel: {after_cancel_resources}")
    
    if after_cancel_resources.get('worker', 0) == initial_resources.get('worker', 0):
        print("[OK] Worker resource released on cancellation")
    else:
        print("[ERROR] Worker resource NOT released on cancellation")
    
    # Cleanup
    media_tab._cleanup_resources()
    
    print("\n" + "="*60)
    print("MediaAnalysisTab Cancellation Test Complete")
    print("="*60)
    
    return True


def main():
    """Main test runner"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        # Run all cancellation tests
        test_hashing_tab_cancellation()
        test_copy_verify_tab_cancellation()
        test_media_analysis_tab_cancellation()
        
        print("\n" + "="*60)
        print("All Cancellation Tests Complete")
        print("="*60)
        
        # Use timer to quit after tests
        QTimer.singleShot(100, app.quit)
        
        # Run event loop briefly
        app.exec()
        
        return 0
        
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())