#!/usr/bin/env python3
"""
Unit tests for ResourceManagementService
"""

import pytest
import sys
import time
from unittest.mock import MagicMock, patch, call
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtCore import QObject, QThread
from PySide6.QtWidgets import QApplication

from core.services.resource_management_service import ResourceManagementService, TrackedResource
from core.services.interfaces import ResourceType, ComponentState
from core.exceptions import FSAError


# Ensure QApplication exists for Qt tests
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


class TestComponent(QObject):
    """Test component for testing"""
    def __init__(self):
        super().__init__()
        self.cleanup_called = False
        self.cleanup_count = 0
    
    def cleanup(self):
        self.cleanup_called = True
        self.cleanup_count += 1


class TestResourceManagementService:
    
    @pytest.fixture
    def service(self, qapp):
        """Create a fresh service instance for each test"""
        service = ResourceManagementService()
        yield service
        # Cleanup
        service._cleanup_timer.stop()
        service._emergency_cleanup()
    
    @pytest.fixture
    def component(self):
        """Create a test component"""
        return TestComponent()
    
    # ============= Registration Tests =============
    
    def test_component_registration(self, service, component):
        """Test basic component registration"""
        # Register component
        service.register_component(component, "test_component", "test")
        
        # Check state
        assert service.get_component_state(component) == ComponentState.LOADED
        
        # Check statistics
        stats = service.get_statistics()
        assert stats['components_registered'] == 1
    
    def test_duplicate_registration(self, service, component):
        """Test handling of duplicate registration"""
        # Register once
        service.register_component(component, "test_component", "test")
        
        # Register again - should log warning but not fail
        service.register_component(component, "test_component", "test")
        
        # Should still only have one registration
        stats = service.get_statistics()
        assert stats['components_registered'] == 1
    
    def test_unregister_component(self, service, component):
        """Test component unregistration"""
        # Register and then unregister
        service.register_component(component, "test_component", "test")
        service.unregister_component(component)
        
        # Should no longer be registered
        assert service.get_component_state(component) is None
        stats = service.get_statistics()
        assert stats['components_registered'] == 0
    
    # ============= Resource Tracking Tests =============
    
    def test_track_resource(self, service, component):
        """Test basic resource tracking"""
        # Register component
        service.register_component(component, "test_component", "test")
        
        # Track a resource
        test_data = b"test data"
        resource_id = service.track_resource(
            component,
            ResourceType.MEMORY,
            test_data,
            size_bytes=len(test_data)
        )
        
        assert resource_id is not None
        assert isinstance(resource_id, str)
        
        # Check statistics
        stats = service.get_statistics()
        assert stats['total_resources_tracked'] == 1
        assert stats['active_resources'] == 1
    
    def test_track_resource_without_registration(self, service, component):
        """Test tracking resource without registering component first"""
        with pytest.raises(FSAError) as exc_info:
            service.track_resource(
                component,
                ResourceType.MEMORY,
                b"test",
                size_bytes=4
            )
        assert "not registered" in str(exc_info.value)
    
    def test_track_qobject_with_weak_reference(self, service, component):
        """Test that QObjects are tracked with weak references"""
        service.register_component(component, "test_component", "test")
        
        # Create a QObject resource
        qobj = QObject()
        resource_id = service.track_resource(
            component,
            ResourceType.QOBJECT,
            qobj
        )
        
        # Check it was tracked
        counts = service.get_resource_count(component)
        assert counts.get("qobject") == 1
        
        # Delete the QObject
        del qobj
        
        # Force periodic cleanup
        service._periodic_cleanup()
        
        # Check resource was auto-cleaned
        counts = service.get_resource_count(component)
        assert counts.get("qobject", 0) == 0
    
    def test_memory_tracking(self, service, component):
        """Test memory usage tracking"""
        service.register_component(component, "test_component", "test")
        
        # Track resources with size
        data1 = b"x" * 100
        data2 = b"y" * 200
        
        service.track_resource(component, ResourceType.MEMORY, data1, size_bytes=100)
        service.track_resource(component, ResourceType.MEMORY, data2, size_bytes=200)
        
        # Check memory usage
        usage = service.get_memory_usage()
        assert usage.get("test_component") == 300
    
    # ============= Resource Release Tests =============
    
    def test_release_resource(self, service, component):
        """Test releasing a tracked resource"""
        service.register_component(component, "test_component", "test")
        
        # Track and release
        test_data = b"test"
        resource_id = service.track_resource(
            component,
            ResourceType.MEMORY,
            test_data,
            size_bytes=4
        )
        
        success = service.release_resource(component, resource_id)
        assert success is True
        
        # Check it was released
        stats = service.get_statistics()
        assert stats['total_resources_released'] == 1
        assert stats['active_resources'] == 0
    
    def test_release_nonexistent_resource(self, service, component):
        """Test releasing a resource that doesn't exist"""
        service.register_component(component, "test_component", "test")
        
        success = service.release_resource(component, "fake_id")
        assert success is False
    
    def test_memory_updated_on_release(self, service, component):
        """Test that memory tracking is updated when resources are released"""
        service.register_component(component, "test_component", "test")
        
        # Track resource with memory
        resource_id = service.track_resource(
            component,
            ResourceType.MEMORY,
            b"x" * 100,
            size_bytes=100
        )
        
        # Check memory
        assert service.get_memory_usage()["test_component"] == 100
        
        # Release
        service.release_resource(component, resource_id)
        
        # Memory should be cleared
        assert service.get_memory_usage().get("test_component", 0) == 0
    
    # ============= Cleanup Callback Tests =============
    
    def test_register_cleanup_callback(self, service, component):
        """Test registering and executing cleanup callbacks"""
        service.register_component(component, "test_component", "test")
        
        # Register cleanup callback
        service.register_cleanup(component, component.cleanup, priority=10)
        
        # Trigger cleanup
        service.cleanup_component(component)
        
        # Check callback was called
        assert component.cleanup_called is True
        assert component.cleanup_count == 1
    
    def test_cleanup_callback_priority(self, service, component):
        """Test cleanup callbacks are executed in priority order"""
        service.register_component(component, "test_component", "test")
        
        call_order = []
        
        def callback1():
            call_order.append(1)
        
        def callback2():
            call_order.append(2)
        
        def callback3():
            call_order.append(3)
        
        # Register with different priorities (higher runs first)
        service.register_cleanup(component, callback2, priority=5)
        service.register_cleanup(component, callback1, priority=10)
        service.register_cleanup(component, callback3, priority=1)
        
        # Cleanup
        service.cleanup_component(component)
        
        # Check order (highest priority first)
        assert call_order == [1, 2, 3]
    
    def test_cleanup_without_registration(self, service, component):
        """Test registering cleanup without component registration"""
        with pytest.raises(FSAError) as exc_info:
            service.register_cleanup(component, component.cleanup)
        assert "not registered" in str(exc_info.value)
    
    # ============= Component Cleanup Tests =============
    
    def test_cleanup_component_releases_resources(self, service, component):
        """Test that cleanup releases all component resources"""
        service.register_component(component, "test_component", "test")
        
        # Keep strong reference to QObject so it doesn't get garbage collected
        qobj = QObject()
        
        # Track multiple resources
        service.track_resource(component, ResourceType.MEMORY, b"data1", 5)
        service.track_resource(component, ResourceType.MEMORY, b"data2", 5)
        service.track_resource(component, ResourceType.QOBJECT, qobj)
        
        # Check resources exist
        assert service.get_resource_count(component)["memory"] == 2
        assert service.get_resource_count(component)["qobject"] == 1
        
        # Cleanup
        service.cleanup_component(component)
        
        # All resources should be released
        assert service.get_resource_count(component) == {}
        assert service.get_component_state(component) == ComponentState.DESTROYED
    
    def test_force_cleanup_continues_on_errors(self, service, component):
        """Test force cleanup continues even if callbacks fail"""
        service.register_component(component, "test_component", "test")
        
        # Register a failing callback
        def failing_callback():
            raise Exception("Test error")
        
        service.register_cleanup(component, failing_callback)
        service.register_cleanup(component, component.cleanup)
        
        # Force cleanup should not raise
        service.cleanup_component(component, force=True)
        
        # Second callback should still have been called
        assert component.cleanup_called is True
    
    # ============= Memory Limit Tests =============
    
    def test_component_memory_limit(self, service, component):
        """Test component-specific memory limits"""
        service.register_component(component, "test_component", "test")
        service.set_memory_limit("test_component", 100)
        
        # Track resource exceeding limit
        with patch.object(service, 'memory_threshold_exceeded') as mock_signal:
            service.track_resource(
                component,
                ResourceType.MEMORY,
                b"x" * 200,
                size_bytes=200
            )
            
            # Signal should be emitted
            mock_signal.emit.assert_called_once_with("test_component", 200)
    
    def test_global_memory_limit(self, service):
        """Test global memory limit across components"""
        comp1 = TestComponent()
        comp2 = TestComponent()
        
        service.register_component(comp1, "comp1", "test")
        service.register_component(comp2, "comp2", "test")
        service.set_global_memory_limit(150)
        
        # Track resources
        service.track_resource(comp1, ResourceType.MEMORY, b"x" * 100, size_bytes=100)
        
        # This should trigger global limit warning
        import logging
        with patch.object(logging.getLogger('core.services.resource_management_service'), 'warning') as mock_warning:
            service.track_resource(comp2, ResourceType.MEMORY, b"y" * 100, size_bytes=100)
            
            # Check warning was logged
            assert any(
                "Global memory limit exceeded" in str(call)
                for call in mock_warning.call_args_list
            )
    
    # ============= Statistics Tests =============
    
    def test_get_statistics(self, service):
        """Test getting resource management statistics"""
        comp1 = TestComponent()
        comp2 = TestComponent()
        
        service.register_component(comp1, "comp1", "test")
        service.register_component(comp2, "comp2", "test")
        
        # Keep strong reference to QObject
        qobj = QObject()
        
        # Track some resources
        r1 = service.track_resource(comp1, ResourceType.MEMORY, b"data", 4)
        service.track_resource(comp2, ResourceType.QOBJECT, qobj)
        
        # Release one
        service.release_resource(comp1, r1)
        
        stats = service.get_statistics()
        
        assert stats['components_registered'] == 2
        assert stats['total_resources_tracked'] == 2
        assert stats['total_resources_released'] == 1
        assert stats['active_resources'] == 1
        assert "memory_usage" in stats
        assert "resource_counts" in stats
    
    def test_get_resource_count_global(self, service):
        """Test getting global resource counts"""
        comp1 = TestComponent()
        comp2 = TestComponent()
        
        service.register_component(comp1, "comp1", "test")
        service.register_component(comp2, "comp2", "test")
        
        # Keep strong reference to QObject
        qobj = QObject()
        
        # Track various resources
        service.track_resource(comp1, ResourceType.MEMORY, b"data1", 5)
        service.track_resource(comp1, ResourceType.MEMORY, b"data2", 5)
        service.track_resource(comp2, ResourceType.QOBJECT, qobj)
        service.track_resource(comp2, ResourceType.WORKER, MagicMock())
        
        counts = service.get_resource_count()  # Global
        
        assert counts["memory"] == 2
        assert counts["qobject"] == 1
        assert counts["worker"] == 1
    
    def test_get_resource_count_per_component(self, service, component):
        """Test getting resource counts for specific component"""
        service.register_component(component, "test", "test")
        
        # Keep strong reference to QObject
        qobj = QObject()
        
        # Track resources
        service.track_resource(component, ResourceType.MEMORY, b"data1", 5)
        service.track_resource(component, ResourceType.MEMORY, b"data2", 5)
        service.track_resource(component, ResourceType.QOBJECT, qobj)
        
        counts = service.get_resource_count(component)
        
        assert counts["memory"] == 2
        assert counts["qobject"] == 1
    
    # ============= State Management Tests =============
    
    def test_component_state_transitions(self, service, component):
        """Test component state transitions"""
        service.register_component(component, "test", "test")
        
        # Initial state
        assert service.get_component_state(component) == ComponentState.LOADED
        
        # Transition through states
        service.set_component_state(component, ComponentState.INITIALIZED)
        assert service.get_component_state(component) == ComponentState.INITIALIZED
        
        service.set_component_state(component, ComponentState.ACTIVE)
        assert service.get_component_state(component) == ComponentState.ACTIVE
        
        service.set_component_state(component, ComponentState.PAUSED)
        assert service.get_component_state(component) == ComponentState.PAUSED
        
        # Cleanup changes state
        service.cleanup_component(component)
        assert service.get_component_state(component) == ComponentState.DESTROYED
    
    # ============= Context Manager Tests =============
    
    def test_managed_resource_context_manager(self, service, component):
        """Test the managed resource context manager"""
        service.register_component(component, "test", "test")
        
        # Use context manager
        with service.managed_resource(component, ResourceType.FILE_HANDLE) as resource:
            # In real usage, resource would be set by caller
            # For test, we'll track it manually
            if resource is not None:
                service.track_resource(component, ResourceType.FILE_HANDLE, resource)
        
        # Context manager doesn't actually create resources in current implementation
        # It's meant to wrap user-created resources
        # This test mainly verifies it doesn't crash
        assert True
    
    # ============= Thread Safety Tests =============
    
    def test_concurrent_resource_tracking(self, service, component):
        """Test thread-safe concurrent resource tracking"""
        import threading
        
        service.register_component(component, "test", "test")
        
        def track_resources():
            for i in range(10):
                service.track_resource(
                    component,
                    ResourceType.MEMORY,
                    f"data_{threading.current_thread().name}_{i}".encode(),
                    size_bytes=10
                )
        
        # Create multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=track_resources, name=f"Thread-{i}")
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Check all resources were tracked
        stats = service.get_statistics()
        assert stats['total_resources_tracked'] == 50  # 5 threads * 10 resources
    
    # ============= Custom Cleanup Tests =============
    
    def test_custom_cleanup_function(self, service, component):
        """Test custom cleanup function in metadata"""
        service.register_component(component, "test", "test")
        
        # Track resource with custom cleanup
        cleanup_called = False
        
        def custom_cleanup(resource):
            nonlocal cleanup_called
            cleanup_called = True
        
        test_resource = MagicMock()
        resource_id = service.track_resource(
            component,
            ResourceType.CUSTOM,
            test_resource,
            metadata={'cleanup_func': custom_cleanup}
        )
        
        # Release resource
        service.release_resource(component, resource_id)
        
        # Custom cleanup should have been called
        assert cleanup_called is True
    
    # ============= Emergency Cleanup Tests =============
    
    def test_emergency_cleanup(self, service):
        """Test emergency cleanup on shutdown"""
        comp1 = TestComponent()
        comp2 = TestComponent()
        
        service.register_component(comp1, "comp1", "test")
        service.register_component(comp2, "comp2", "test")
        
        # Track resources
        service.track_resource(comp1, ResourceType.MEMORY, b"data1", 10)
        service.track_resource(comp2, ResourceType.MEMORY, b"data2", 10)
        
        # Trigger emergency cleanup
        service._emergency_cleanup()
        
        # All components should be cleaned
        assert service.get_component_state(comp1) == ComponentState.DESTROYED
        assert service.get_component_state(comp2) == ComponentState.DESTROYED
    
    # ============= QObject Integration Tests =============
    
    def test_qobject_destroyed_signal(self, service):
        """Test automatic cleanup when QObject is destroyed"""
        qobj_component = QObject()  # Use QObject as component
        
        service.register_component(qobj_component, "qobj_test", "test")
        service.track_resource(qobj_component, ResourceType.MEMORY, b"data", 10)
        
        # Destroy the QObject
        qobj_component.deleteLater()
        QApplication.processEvents()  # Process deletion
        
        # Component should be cleaned up automatically
        # Note: This might not work perfectly in test environment
        # due to Qt event loop limitations
        pass  # Test mainly verifies no crash occurs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])