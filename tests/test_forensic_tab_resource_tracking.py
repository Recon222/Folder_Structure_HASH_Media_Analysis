#!/usr/bin/env python3
"""
Test ForensicTab resource tracking with ResourceManagementService
"""

from pathlib import Path
from unittest.mock import MagicMock, patch, call
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QThread
import sys

# Setup application
app = QApplication.instance() or QApplication(sys.argv)

# Import first, then we'll patch
from core.models import FormData
from core.services.interfaces import ResourceType

def test_forensic_tab_resource_tracking():
    """Test that ForensicTab properly tracks resources"""
    
    print("Testing ForensicTab resource tracking...")
    print("=" * 60)
    
    # Create comprehensive mocks
    mock_resource_manager = MagicMock()
    mock_resource_manager.register_component = MagicMock()
    mock_resource_manager.register_cleanup = MagicMock()
    mock_resource_manager.track_resource = MagicMock(return_value="worker_resource_123")
    mock_resource_manager.release_resource = MagicMock(return_value=True)
    mock_resource_manager.get_statistics = MagicMock(return_value={
        'components_registered': 1,
        'total_resources_tracked': 0,
        'total_resources_released': 0,
        'active_resources': 0,
        'resource_counts': {}
    })
    
    # Mock path service for TemplateSelector
    mock_path_service = MagicMock()
    
    # Patch both services
    with patch('ui.tabs.forensic_tab.get_service') as mock_get_service, \
         patch('ui.components.template_selector.get_service') as mock_template_get_service:
        
        # Setup service returns
        def get_service_side_effect(interface):
            from core.services.interfaces import IResourceManagementService, IPathService
            if interface == IResourceManagementService:
                return mock_resource_manager
            elif interface == IPathService:
                return mock_path_service
            return None
            
        mock_get_service.side_effect = get_service_side_effect
        mock_template_get_service.side_effect = get_service_side_effect
        
        # Import after patching
        from ui.tabs.forensic_tab import ForensicTab
    
        # Create FormData for the tab
        form_data = FormData()
        form_data.occurrence_number = "2024-TEST-001"
        form_data.technician_name = "Test Tech"
        
        # Create ForensicTab
        print("\n1. Creating ForensicTab...")
        forensic_tab = ForensicTab(form_data)
        
        # Verify registration
        assert mock_resource_manager.register_component.called
        print("[OK] ForensicTab registered with ResourceManagementService")
        
        # Verify cleanup callback registration
        assert mock_resource_manager.register_cleanup.called
        print("[OK] Cleanup callback registered")
        
        # Check initial state
        print("\n2. Initial resource state:")
        stats = mock_resource_manager.get_statistics()
        print(f"   Components registered: {stats['components_registered']}")
        print(f"   Active resources: {stats['active_resources']}")
        
        # Simulate processing start with a mock thread
        print("\n3. Simulating processing start...")
        mock_thread = MagicMock(spec=QThread)
        mock_thread.isRunning = MagicMock(return_value=True)
        mock_thread.cancel = MagicMock()
        
        forensic_tab.set_processing_state(True, mock_thread)
        
        # Verify worker was tracked
        assert mock_resource_manager.track_resource.called
        tracked_call = mock_resource_manager.track_resource.call_args
        assert tracked_call[0][1] == ResourceType.WORKER
        assert tracked_call[0][2] == mock_thread
        assert 'FolderStructureThread' in str(tracked_call[1]['metadata']['type'])
        print("[OK] Worker thread tracked as resource")
        print(f"   Resource ID: {forensic_tab._worker_resource_id}")
        
        # Simulate processing stop
        print("\n4. Simulating processing stop...")
        forensic_tab.set_processing_state(False)
        
        # Verify worker was released
        assert mock_resource_manager.release_resource.called
        print("[OK] Worker resource released when processing stopped")
        
        # Test cleanup
        print("\n5. Testing cleanup...")
        # Reset mock to track new calls
        mock_resource_manager.release_resource.reset_mock()
        mock_thread.cancel.reset_mock()
        
        # Start another operation
        forensic_tab.set_processing_state(True, mock_thread)
        
        # Call cleanup while operation is running
        forensic_tab._cleanup_resources()
        
        # Verify thread was cancelled
        assert mock_thread.cancel.called
        print("[OK] Thread cancelled during cleanup")
        
        # Verify resource was released
        assert mock_resource_manager.release_resource.called
        print("[OK] Worker resource released during cleanup")
        
        # Verify state was reset
        assert forensic_tab.processing_active == False
        assert forensic_tab.is_paused == False
        assert forensic_tab.current_thread == None
        print("[OK] Tab state properly reset")
        
        print("\n" + "=" * 60)
        print("SUCCESS: ForensicTab resource tracking working correctly!")
        print("\nSummary:")
        print("- Tab registers with ResourceManagementService")
        print("- Worker threads tracked when processing starts")
        print("- Resources released when processing stops")
        print("- Cleanup cancels operations and releases resources")
        print("- No memory leaks from orphaned threads")

if __name__ == "__main__":
    test_forensic_tab_resource_tracking()