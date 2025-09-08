"""
Unit tests for resource coordinators.

Tests the BaseResourceCoordinator and WorkerResourceCoordinator
implementations with mock services.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import weakref
from PySide6.QtCore import QThread, QObject

# Import the coordinators
from core.resource_coordinators.base_coordinator import BaseResourceCoordinator
from core.resource_coordinators.worker_coordinator import WorkerResourceCoordinator
from core.services.resource_management_service import ResourceType
from tests.helpers.mock_coordinators import MockResourceCoordinator, MockWorkerResourceCoordinator


class TestBaseResourceCoordinator(unittest.TestCase):
    """Test BaseResourceCoordinator functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_service = Mock()
        self.mock_service.register_component = Mock(return_value=True)
        self.mock_service.register_cleanup = Mock(return_value=True)
        self.mock_service.track_resource = Mock(return_value="resource_123")
        self.mock_service.release_resource = Mock(return_value=True)
        
        # Patch get_service to return our mock
        patcher = patch('core.resource_coordinators.base_coordinator.get_service')
        self.mock_get_service = patcher.start()
        self.mock_get_service.return_value = self.mock_service
        self.addCleanup(patcher.stop)
        
    def test_initialization(self):
        """Test coordinator initialization."""
        coordinator = BaseResourceCoordinator("test_component")
        
        self.assertEqual(coordinator._component_id, "test_component")
        self.assertIsNotNone(coordinator._service)
        self.assertEqual(coordinator._cleanup_priority, 10)
        self.assertFalse(coordinator.debug_mode)
        
    def test_bind_to_component(self):
        """Test binding coordinator to component."""
        coordinator = BaseResourceCoordinator("test_component")
        mock_component = Mock()
        
        result = coordinator.bind_to_component(mock_component)
        
        # Should return self for fluent interface
        self.assertEqual(result, coordinator)
        
        # Should register with service
        self.mock_service.register_component.assert_called_once()
        self.mock_service.register_cleanup.assert_called_once()
        
        # Should store weak reference
        self.assertIsNotNone(coordinator._component_ref)
        
    def test_track_resource(self):
        """Test resource tracking."""
        coordinator = BaseResourceCoordinator("test_component")
        mock_component = Mock()
        coordinator.bind_to_component(mock_component)
        
        mock_resource = Mock()
        resource_id = coordinator.track_resource(
            mock_resource,
            ResourceType.CUSTOM,
            name="test_resource"
        )
        
        self.assertEqual(resource_id, "resource_123")
        self.mock_service.track_resource.assert_called_once()
        self.assertIn(resource_id, coordinator._resources)
        
    def test_track_worker(self):
        """Test worker tracking with auto-cleanup."""
        coordinator = BaseResourceCoordinator("test_component")
        mock_component = Mock()
        coordinator.bind_to_component(mock_component)
        
        # Create a mock worker
        mock_worker = Mock(spec=QThread)
        mock_worker.finished = Mock()
        mock_worker.finished.connect = Mock()
        
        resource_id = coordinator.track_worker(mock_worker, name="test_worker")
        
        self.assertEqual(resource_id, "resource_123")
        self.mock_service.track_resource.assert_called_once()
        
        # Should connect to finished signal for auto-cleanup
        mock_worker.finished.connect.assert_called_once()
        
    def test_release_resource(self):
        """Test resource release."""
        coordinator = BaseResourceCoordinator("test_component")
        mock_component = Mock()
        coordinator.bind_to_component(mock_component)
        
        # Track a resource first
        mock_resource = Mock()
        resource_id = coordinator.track_resource(mock_resource)
        
        # Release it
        coordinator.release(resource_id)
        
        self.assertNotIn(resource_id, coordinator._resources)
        self.mock_service.release_resource.assert_called_once()
        
    def test_cleanup_all(self):
        """Test cleanup of all resources."""
        coordinator = BaseResourceCoordinator("test_component")
        mock_component = Mock()
        coordinator.bind_to_component(mock_component)
        
        # Track multiple resources
        resources = [Mock() for _ in range(3)]
        resource_ids = []
        for resource in resources:
            rid = coordinator.track_resource(resource)
            resource_ids.append(rid)
            
        # Cleanup all
        coordinator.cleanup_all()
        
        self.assertEqual(len(coordinator._resources), 0)
        self.assertEqual(coordinator.get_resource_count(), 0)
        
    def test_del_warning(self):
        """Test that __del__ warns about unreleased resources."""
        with patch('core.resource_coordinators.base_coordinator.logger') as mock_logger:
            coordinator = BaseResourceCoordinator("test_component")
            mock_component = Mock()
            coordinator.bind_to_component(mock_component)
            
            # Track a resource
            coordinator.track_resource(Mock())
            
            # Simulate deletion
            coordinator.__del__()
            
            # Should log warning
            mock_logger.warning.assert_called()
            

class TestWorkerResourceCoordinator(unittest.TestCase):
    """Test WorkerResourceCoordinator functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_service = Mock()
        self.mock_service.register_component = Mock(return_value=True)
        self.mock_service.register_cleanup = Mock(return_value=True)
        self.mock_service.track_resource = Mock(return_value="worker_123")
        self.mock_service.release_resource = Mock(return_value=True)
        
        # Patch get_service
        patcher = patch('core.resource_coordinators.base_coordinator.get_service')
        self.mock_get_service = patcher.start()
        self.mock_get_service.return_value = self.mock_service
        self.addCleanup(patcher.stop)
        
    def test_track_worker_enhanced(self):
        """Test enhanced worker tracking."""
        coordinator = WorkerResourceCoordinator("test_component")
        mock_component = Mock()
        coordinator.bind_to_component(mock_component)
        
        # Create mock worker
        mock_worker = Mock(spec=QThread)
        mock_worker.__class__.__name__ = "TestWorker"
        mock_worker.isRunning = Mock(return_value=True)
        mock_worker.finished = Mock()
        mock_worker.finished.connect = Mock()
        # No need to mock thread ID anymore
        
        resource_id = coordinator.track_worker(
            mock_worker,
            name="test_worker",
            cancel_on_cleanup=True
        )
        
        self.assertEqual(resource_id, "worker_123")
        self.assertIn(resource_id, coordinator._active_workers)
        self.assertIn(resource_id, coordinator._worker_metadata)
        
        # Should connect to finished signal
        mock_worker.finished.connect.assert_called_once()
        
    def test_cancel_all_workers(self):
        """Test cancelling all active workers."""
        coordinator = WorkerResourceCoordinator("test_component")
        mock_component = Mock()
        coordinator.bind_to_component(mock_component)
        
        # Create mock workers with proper weak refs
        mock_workers = []
        resource_ids = []
        for i in range(3):
            mock_worker = Mock(spec=QThread)
            mock_worker.cancel = Mock()
            mock_worker.isRunning = Mock(return_value=True)
            mock_worker.finished = Mock()
            mock_worker.finished.connect = Mock()
            mock_worker.thread = Mock()
            mock_worker.thread().currentThreadId = Mock(return_value=12345 + i)
            mock_workers.append(mock_worker)
            
            # Track the worker and store resource ID
            self.mock_service.track_resource = Mock(return_value=f"worker_{i}")
            resource_id = coordinator.track_worker(mock_worker, name=f"worker_{i}")
            resource_ids.append(resource_id)
            
        # Verify workers are tracked
        self.assertEqual(len(coordinator._active_workers), 3)
        
        # Cancel all workers
        with patch.object(QThread, 'msleep'):
            result = coordinator.cancel_all_workers(timeout_ms=1000)
            
        # Check that cancel was called on all workers
        for worker in mock_workers:
            worker.cancel.assert_called_once()
            
    def test_get_active_workers(self):
        """Test getting active worker information."""
        coordinator = WorkerResourceCoordinator("test_component")
        mock_component = Mock()
        coordinator.bind_to_component(mock_component)
        
        # Track a worker
        mock_worker = Mock(spec=QThread)
        mock_worker.finished = Mock()
        mock_worker.finished.connect = Mock()
        # No need to mock thread ID anymore
        
        resource_id = coordinator.track_worker(mock_worker, name="test_worker")
        
        active = coordinator.get_active_workers()
        
        self.assertEqual(len(active), 1)
        self.assertIn(resource_id, active)
        self.assertEqual(active[resource_id]['name'], "test_worker")
        self.assertIn('runtime', active[resource_id])
        
    def test_is_worker_active(self):
        """Test checking if worker is active."""
        coordinator = WorkerResourceCoordinator("test_component")
        mock_component = Mock()
        coordinator.bind_to_component(mock_component)
        
        # Track a worker
        mock_worker = Mock(spec=QThread)
        mock_worker.isRunning = Mock(return_value=True)
        mock_worker.finished = Mock()
        mock_worker.finished.connect = Mock()
        # No need to mock thread ID anymore
        
        resource_id = coordinator.track_worker(mock_worker)
        
        self.assertTrue(coordinator.is_worker_active(resource_id))
        self.assertFalse(coordinator.is_worker_active("nonexistent"))
        
    def test_wait_for_worker(self):
        """Test waiting for worker completion."""
        coordinator = WorkerResourceCoordinator("test_component")
        mock_component = Mock()
        coordinator.bind_to_component(mock_component)
        
        # Track a worker
        mock_worker = Mock(spec=QThread)
        mock_worker.wait = Mock(return_value=True)
        mock_worker.isRunning = Mock(return_value=True)
        mock_worker.finished = Mock()
        mock_worker.finished.connect = Mock()
        # No need to mock thread ID anymore
        
        resource_id = coordinator.track_worker(mock_worker)
        
        result = coordinator.wait_for_worker(resource_id, timeout_ms=5000)
        
        self.assertTrue(result)
        mock_worker.wait.assert_called_once_with(5000)
        
    def test_get_statistics(self):
        """Test getting coordinator statistics."""
        coordinator = WorkerResourceCoordinator("test_component")
        mock_component = Mock()
        coordinator.bind_to_component(mock_component)
        
        # Track some workers with unique resource IDs
        for i in range(2):
            mock_worker = Mock(spec=QThread)
            mock_worker.finished = Mock()
            mock_worker.finished.connect = Mock()
            mock_worker.thread = Mock()
            mock_worker.thread().currentThreadId = Mock(return_value=12345 + i)
            
            # Set unique resource ID for each worker
            self.mock_service.track_resource = Mock(return_value=f"worker_{i}")
            coordinator.track_worker(mock_worker, name=f"worker_{i}")
            
        stats = coordinator.get_statistics()
        
        self.assertEqual(stats['active_workers'], 2)
        self.assertEqual(stats['total_tracked'], 2)
        self.assertIn('workers', stats)
        

class TestMockCoordinators(unittest.TestCase):
    """Test mock coordinators for testing support."""
    
    def test_mock_resource_coordinator(self):
        """Test MockResourceCoordinator."""
        mock_coord = MockResourceCoordinator()
        
        # Test binding
        component = Mock()
        result = mock_coord.bind_to_component(component)
        self.assertEqual(result, mock_coord)
        self.assertEqual(mock_coord.bound_component, component)
        
        # Test tracking
        resource = Mock()
        resource_id = mock_coord.track_resource(resource, name="test")
        self.assertEqual(resource_id, "mock_id_0")
        self.assertTrue(mock_coord.was_resource_tracked(resource))
        
        # Test release
        mock_coord.release(resource_id)
        self.assertIn(resource_id, mock_coord.released)
        
        # Test cleanup
        mock_coord.cleanup_all()
        self.assertTrue(mock_coord.cleanup_called)
        
    def test_mock_worker_coordinator(self):
        """Test MockWorkerResourceCoordinator."""
        mock_coord = MockWorkerResourceCoordinator()
        
        # Test worker tracking
        worker = Mock()
        worker.__class__.__name__ = "TestWorker"
        
        resource_id = mock_coord.track_worker(
            worker,
            name="test_worker",
            cancel_on_cleanup=True
        )
        
        self.assertTrue(mock_coord.is_worker_active(resource_id))
        self.assertIn(resource_id, mock_coord.active_workers)
        
        # Test cancel all
        result = mock_coord.cancel_all_workers()
        self.assertTrue(result)
        self.assertIn(resource_id, mock_coord.cancelled_workers)
        
        # Test statistics
        stats = mock_coord.get_statistics()
        self.assertIn('total_tracked', stats)
        self.assertIn('active_workers', stats)


if __name__ == '__main__':
    unittest.main()