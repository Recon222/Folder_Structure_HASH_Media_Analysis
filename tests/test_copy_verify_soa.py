#!/usr/bin/env python3
"""
Test suite for Copy & Verify SOA refactor
Validates proper architecture compliance and functionality
"""

import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
import tempfile
import shutil

from core.services.copy_verify_service import CopyVerifyService
from core.services.interfaces import ICopyVerifyService
from controllers.copy_verify_controller import CopyVerifyController
from core.result_types import Result
from core.exceptions import ValidationError, FileOperationError


class TestCopyVerifyService(unittest.TestCase):
    """Test the CopyVerifyService business logic"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.service = CopyVerifyService()
        self.temp_dir = tempfile.mkdtemp()
        self.test_source = Path(self.temp_dir) / "source"
        self.test_dest = Path(self.temp_dir) / "dest"
        self.test_source.mkdir()
        
        # Create test files
        (self.test_source / "test.txt").write_text("test content")
        (self.test_source / "subdir").mkdir()
        (self.test_source / "subdir" / "nested.txt").write_text("nested content")
        
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_validate_copy_operation_success(self):
        """Test successful validation of copy operation"""
        source_items = [self.test_source / "test.txt"]
        result = self.service.validate_copy_operation(source_items, self.test_dest)
        
        self.assertTrue(result.success)
        self.assertIsNone(result.error)
        
    def test_validate_copy_operation_no_sources(self):
        """Test validation fails with no source items"""
        result = self.service.validate_copy_operation([], self.test_dest)
        
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ValidationError)
        self.assertIn("No source files", result.error.user_message)
        
    def test_validate_copy_operation_no_destination(self):
        """Test validation fails with no destination"""
        source_items = [self.test_source / "test.txt"]
        result = self.service.validate_copy_operation(source_items, None)
        
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ValidationError)
        self.assertIn("No destination", result.error.user_message)
        
    def test_validate_destination_security_valid(self):
        """Test destination security validation passes for valid path"""
        result = self.service.validate_destination_security(
            self.test_dest,
            [self.test_source / "test.txt"]
        )
        
        self.assertTrue(result.success)
        
    def test_validate_destination_security_prevents_source_child(self):
        """Test destination cannot be child of source"""
        source_dir = self.test_source / "subdir"
        dest_in_source = source_dir / "dest"
        
        result = self.service.validate_copy_operation(
            [source_dir],
            dest_in_source
        )
        
        self.assertFalse(result.success)
        self.assertIn("cannot be inside source", result.error.user_message)
        
    def test_prepare_copy_operation_single_file(self):
        """Test preparing single file for copy"""
        source_items = [self.test_source / "test.txt"]
        result = self.service.prepare_copy_operation(
            source_items,
            self.test_dest,
            preserve_structure=False
        )
        
        self.assertTrue(result.success)
        files = result.value
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0][0], self.test_source / "test.txt")
        self.assertIsNone(files[0][1])  # No relative path
        
    def test_prepare_copy_operation_directory_with_structure(self):
        """Test preparing directory with structure preservation"""
        source_items = [self.test_source / "subdir"]
        result = self.service.prepare_copy_operation(
            source_items,
            self.test_dest,
            preserve_structure=True
        )
        
        self.assertTrue(result.success)
        files = result.value
        self.assertEqual(len(files), 1)  # One file in subdir
        # Should preserve the subdir structure
        self.assertEqual(files[0][1], Path("subdir/nested.txt"))
        
    def test_process_operation_results(self):
        """Test processing operation results into success message"""
        results = {
            "file1": {
                "success": True,
                "size": 1024,
                "verified": True
            },
            "file2": {
                "success": True,
                "size": 2048,
                "verified": False  # Hash mismatch
            },
            "file3": {
                "success": False,
                "error": "Permission denied"
            }
        }
        
        result = self.service.process_operation_results(results, calculate_hash=True)
        
        self.assertTrue(result.success)
        message_data = result.value
        self.assertIsNotNone(message_data)
        # Should have proper counts in the message data


class TestCopyVerifyController(unittest.TestCase):
    """Test the CopyVerifyController orchestration"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.controller = CopyVerifyController()
        self.mock_service = Mock(spec=ICopyVerifyService)
        self.controller._copy_service = self.mock_service
        
        self.temp_dir = tempfile.mkdtemp()
        self.test_source = Path(self.temp_dir) / "source"
        self.test_dest = Path(self.temp_dir) / "dest"
        self.test_source.mkdir()
        (self.test_source / "test.txt").write_text("test")
        
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_execute_copy_operation_success(self):
        """Test successful copy operation execution"""
        # Mock service responses
        self.mock_service.validate_copy_operation.return_value = Result.success(None)
        self.mock_service.validate_destination_security.return_value = Result.success(None)
        
        with patch('controllers.copy_verify_controller.CopyVerifyWorker') as MockWorker:
            mock_worker = Mock()
            MockWorker.return_value = mock_worker
            
            result = self.controller.execute_copy_operation(
                source_items=[self.test_source / "test.txt"],
                destination=self.test_dest,
                preserve_structure=True,
                calculate_hash=True,
                csv_path=None
            )
            
            self.assertTrue(result.success)
            self.assertEqual(result.value, mock_worker)
            
            # Verify service calls
            self.mock_service.validate_copy_operation.assert_called_once()
            self.mock_service.validate_destination_security.assert_called_once()
            
            # Verify worker created with service
            MockWorker.assert_called_once()
            call_kwargs = MockWorker.call_args.kwargs
            self.assertEqual(call_kwargs['service'], self.mock_service)
            
    def test_execute_copy_operation_validation_failure(self):
        """Test copy operation fails on validation"""
        error = ValidationError(
            {"source": "Invalid"},
            user_message="Invalid source"
        )
        self.mock_service.validate_copy_operation.return_value = Result.error(error)
        
        result = self.controller.execute_copy_operation(
            source_items=[],
            destination=self.test_dest
        )
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, error)
        
    def test_process_operation_results(self):
        """Test processing results delegates to service"""
        mock_results = {"file1": {"success": True}}
        mock_message = Mock()
        self.mock_service.process_operation_results.return_value = Result.success(mock_message)
        
        result = self.controller.process_operation_results(mock_results, calculate_hash=True)
        
        self.assertTrue(result.success)
        self.assertEqual(result.value, mock_message)
        self.mock_service.process_operation_results.assert_called_once_with(
            mock_results, True
        )
        
    def test_cancel_operation(self):
        """Test cancel operation"""
        mock_worker = Mock()
        mock_worker.isRunning.return_value = True
        self.controller.current_worker = mock_worker
        
        result = self.controller.cancel_operation()
        
        self.assertTrue(result.success)
        mock_worker.cancel.assert_called_once()


class TestArchitecturalCompliance(unittest.TestCase):
    """Test architectural compliance of the refactor"""
    
    def test_service_implements_interface(self):
        """Test CopyVerifyService implements ICopyVerifyService"""
        service = CopyVerifyService()
        self.assertIsInstance(service, ICopyVerifyService)
        
        # Check all interface methods are implemented
        interface_methods = [
            'validate_copy_operation',
            'validate_destination_security',
            'prepare_copy_operation',
            'process_operation_results',
            'generate_csv_report',
            'export_results_to_csv'
        ]
        
        for method in interface_methods:
            self.assertTrue(hasattr(service, method))
            self.assertTrue(callable(getattr(service, method)))
            
    def test_controller_uses_dependency_injection(self):
        """Test controller uses proper dependency injection"""
        controller = CopyVerifyController()
        
        # Should lazy-load service
        self.assertIsNone(controller._copy_service)
        
        # Mock the service registry
        with patch('controllers.copy_verify_controller.CopyVerifyController._get_service') as mock_get:
            mock_service = Mock(spec=ICopyVerifyService)
            mock_get.return_value = mock_service
            
            # Access service property
            service = controller.copy_service
            
            # Should have called _get_service
            mock_get.assert_called_once_with(ICopyVerifyService)
            self.assertEqual(service, mock_service)
            self.assertEqual(controller._copy_service, mock_service)
            
    def test_no_business_logic_in_worker(self):
        """Test worker contains no business logic"""
        # Check that CSV generation method was removed
        from core.workers.copy_verify_worker import CopyVerifyWorker
        
        # Should not have the old CSV generation method
        self.assertFalse(hasattr(CopyVerifyWorker, '_generate_csv_report'))
        
        # Worker should delegate CSV generation to service
        worker = CopyVerifyWorker(
            source_items=[],
            destination=Path('/tmp'),
            service=Mock()
        )
        self.assertIsNotNone(worker.service)
        
    def test_service_registration(self):
        """Test service is properly registered"""
        from core.services.service_config import get_configured_services
        from core.services.interfaces import ICopyVerifyService
        
        configured = get_configured_services()
        self.assertIn(ICopyVerifyService, configured)


if __name__ == '__main__':
    unittest.main()