#!/usr/bin/env python3
"""
Test success message integration with service architecture

Tests that the WorkflowController properly integrates with the success message
service and that the service layer provides proper dependency injection.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from controllers.workflow_controller import WorkflowController
from core.services.success_message_builder import SuccessMessageBuilder
from core.services.success_message_data import SuccessMessageData
from core.result_types import FileOperationResult, ReportGenerationResult, ArchiveOperationResult
from core.services import get_service, ISuccessMessageService, configure_services
from core.services.service_registry import ServiceRegistry


class TestSuccessMessageIntegration:
    """Test success message integration with service architecture"""
    
    @pytest.fixture
    def workflow_controller(self):
        """Create workflow controller for testing"""
        # Configure services for testing
        configure_services()
        return WorkflowController()
    
    @pytest.fixture
    def mock_file_result(self):
        """Create mock file operation result"""
        return FileOperationResult(
            success=True,
            files_processed=5,
            bytes_processed=1024 * 1024,  # 1MB
            duration_seconds=10.5,
            average_speed_mbps=1.2,
            value={
                'files_copied': 5,
                'folders_copied': 2,
                'performance_stats': {'total_time': 10.5, 'copy_speed': 1.2}
            }
        )
    
    @pytest.fixture
    def mock_report_results(self):
        """Create mock report generation results"""
        return {
            'time_offset': ReportGenerationResult(
                success=True,
                value=Path('/test/Time_Offset_Report.pdf')
            ),
            'upload_log': ReportGenerationResult(
                success=True,
                value=Path('/test/Upload_Log.pdf')
            ),
            'hash_csv': ReportGenerationResult(
                success=True,
                value=Path('/test/Hash_Verification.csv')
            )
        }
    
    @pytest.fixture
    def mock_zip_result(self):
        """Create mock ZIP operation result"""
        return ArchiveOperationResult(
            success=True,
            archives_created=[
                Path('/test/occurrence_123.zip'),
                Path('/test/occurrence_123_files.zip')
            ],
            value={'compression_ratio': 0.75, 'total_compressed_size': 768 * 1024}
        )
    
    def test_workflow_controller_has_success_message_integration(self, workflow_controller):
        """Test that WorkflowController has success message integration methods"""
        # Verify integration methods exist
        assert hasattr(workflow_controller, 'store_operation_results')
        assert hasattr(workflow_controller, 'build_success_message')
        assert hasattr(workflow_controller, 'clear_stored_results')
        
        # Verify service dependency
        assert hasattr(workflow_controller, 'success_message_service')
    
    def test_success_message_service_registration(self):
        """Test that success message service is properly registered"""
        # Configure services
        configure_services()
        
        # Should be able to retrieve success message service
        service = get_service(ISuccessMessageService)
        assert service is not None
        assert isinstance(service, SuccessMessageBuilder)
        assert hasattr(service, 'build_forensic_success_message')
    
    def test_workflow_controller_success_message_integration(self, workflow_controller, mock_file_result, mock_report_results, mock_zip_result):
        """Test WorkflowController integrates with success message service"""
        
        # Mock the success message service
        mock_service = Mock(spec=SuccessMessageBuilder)
        mock_service.build_forensic_success_message.return_value = SuccessMessageData(
            title="Test Success! 🎉",
            summary_lines=["✅ 5 files processed successfully", "📁 2 folders copied"],
            celebration_emoji="🎉"
        )
        
        with patch.object(workflow_controller, '_success_message_service', mock_service):
            # Store mock results
            workflow_controller.store_operation_results(
                file_result=mock_file_result,
                report_results=mock_report_results,
                zip_result=mock_zip_result
            )
            
            # Build success message
            success_data = workflow_controller.build_success_message()
            
            # Verify service was called correctly
            mock_service.build_forensic_success_message.assert_called_once_with(
                mock_file_result, mock_report_results, mock_zip_result
            )
            
            # Verify returned data
            assert success_data.title == "Test Success! 🎉"
            assert "✅ 5 files processed successfully" in success_data.summary_lines
            assert "📁 2 folders copied" in success_data.summary_lines
            assert success_data.celebration_emoji == "🎉"
    
    def test_workflow_controller_result_storage(self, workflow_controller, mock_file_result, mock_report_results, mock_zip_result):
        """Test that WorkflowController properly stores operation results"""
        
        # Initially no stored results
        assert workflow_controller._last_file_result is None
        assert workflow_controller._last_report_results is None
        assert workflow_controller._last_zip_result is None
        
        # Store results individually
        workflow_controller.store_operation_results(file_result=mock_file_result)
        assert workflow_controller._last_file_result is mock_file_result
        assert workflow_controller._last_report_results is None
        
        workflow_controller.store_operation_results(report_results=mock_report_results)
        assert workflow_controller._last_report_results is mock_report_results
        
        workflow_controller.store_operation_results(zip_result=mock_zip_result)
        assert workflow_controller._last_zip_result is mock_zip_result
        
        # Store all at once
        workflow_controller.store_operation_results(
            file_result=None,  # Should not overwrite existing
            report_results=mock_report_results,
            zip_result=mock_zip_result
        )
        assert workflow_controller._last_file_result is mock_file_result  # Unchanged
        assert workflow_controller._last_report_results is mock_report_results
        assert workflow_controller._last_zip_result is mock_zip_result
    
    def test_workflow_controller_success_message_fallback(self, workflow_controller, mock_file_result):
        """Test WorkflowController success message building with stored results fallback"""
        
        # Mock the success message service
        mock_service = Mock(spec=SuccessMessageBuilder)
        mock_service.build_forensic_success_message.return_value = SuccessMessageData(
            title="Fallback Success!",
            summary_lines=["Used stored results"],
            celebration_emoji="✨"
        )
        
        with patch.object(workflow_controller, '_success_message_service', mock_service):
            # Store results
            workflow_controller.store_operation_results(file_result=mock_file_result)
            
            # Build success message without providing parameters (uses stored results)
            success_data = workflow_controller.build_success_message()
            
            # Verify service was called with stored results
            mock_service.build_forensic_success_message.assert_called_once_with(
                mock_file_result, None, None
            )
            
            # Verify returned data
            assert success_data.title == "Fallback Success!"
            assert "Used stored results" in success_data.summary_lines
    
    def test_workflow_controller_success_message_parameter_priority(self, workflow_controller, mock_file_result, mock_report_results):
        """Test that provided parameters take priority over stored results"""
        
        # Mock the success message service
        mock_service = Mock(spec=SuccessMessageBuilder)
        mock_service.build_forensic_success_message.return_value = SuccessMessageData(
            title="Parameter Priority Test",
            summary_lines=["Parameters used"],
            celebration_emoji="🔧"
        )
        
        # Create different results for stored vs parameters
        stored_file_result = FileOperationResult(success=True, files_processed=10, value={})
        parameter_file_result = FileOperationResult(success=True, files_processed=20, value={})
        
        with patch.object(workflow_controller, '_success_message_service', mock_service):
            # Store one result
            workflow_controller.store_operation_results(file_result=stored_file_result)
            
            # Build success message with different parameter
            success_data = workflow_controller.build_success_message(
                file_result=parameter_file_result,
                report_results=mock_report_results
            )
            
            # Verify service was called with parameters, not stored results
            mock_service.build_forensic_success_message.assert_called_once_with(
                parameter_file_result, mock_report_results, None  # zip_result from stored (None)
            )
    
    def test_workflow_controller_clear_stored_results(self, workflow_controller, mock_file_result, mock_report_results, mock_zip_result):
        """Test that clear_stored_results properly cleans up"""
        
        # Store some results
        workflow_controller.store_operation_results(
            file_result=mock_file_result,
            report_results=mock_report_results,
            zip_result=mock_zip_result
        )
        
        # Verify stored
        assert workflow_controller._last_file_result is not None
        assert workflow_controller._last_report_results is not None
        assert workflow_controller._last_zip_result is not None
        
        # Clear
        workflow_controller.clear_stored_results()
        
        # Verify cleared
        assert workflow_controller._last_file_result is None
        assert workflow_controller._last_report_results is None
        assert workflow_controller._last_zip_result is None
    
    def test_success_message_service_lazy_loading(self, workflow_controller):
        """Test that success message service is lazy loaded"""
        
        # Initially should be None
        assert workflow_controller._success_message_service is None
        
        # First access should load service
        service = workflow_controller.success_message_service
        assert service is not None
        assert isinstance(service, SuccessMessageBuilder)
        
        # Second access should return same instance
        service2 = workflow_controller.success_message_service
        assert service is service2
        assert workflow_controller._success_message_service is service
    
    def test_success_message_integration_error_handling(self, workflow_controller, mock_file_result):
        """Test error handling in success message integration"""
        
        # Mock service to raise an exception
        mock_service = Mock(spec=SuccessMessageBuilder)
        mock_service.build_forensic_success_message.side_effect = Exception("Service error")
        
        with patch.object(workflow_controller, '_success_message_service', mock_service):
            workflow_controller.store_operation_results(file_result=mock_file_result)
            
            # Should handle exception gracefully
            with pytest.raises(Exception, match="Service error"):
                workflow_controller.build_success_message()
    
    def test_service_registry_integration_with_success_messages(self):
        """Test that service registry properly manages success message service lifecycle"""
        
        # Clear any existing service registrations
        from core.services.service_registry import _service_registry
        _service_registry.clear()
        
        # Configure services fresh
        configure_services()
        
        # Should be able to get service multiple times with same instance
        service1 = get_service(ISuccessMessageService)
        service2 = get_service(ISuccessMessageService)
        
        # Should be same instance (singleton behavior)
        assert service1 is service2
        assert isinstance(service1, SuccessMessageBuilder)
    
    def test_workflow_controller_integrates_with_main_window_pattern(self, workflow_controller, mock_file_result):
        """Test integration pattern that MainWindow will use"""
        
        # Mock the success message service to return realistic data
        mock_service = Mock(spec=SuccessMessageBuilder)
        mock_service.build_forensic_success_message.return_value = SuccessMessageData(
            title="Processing Complete! 🎉",
            summary_lines=[
                "✅ 5 files copied successfully",
                "📊 Processing completed in 10.5 seconds",
                "🔍 SHA-256 hashes calculated for all files"
            ],
            celebration_emoji="🎉"
        )
        
        with patch.object(workflow_controller, '_success_message_service', mock_service):
            # Simulate MainWindow pattern:
            # 1. Store results when operations complete
            workflow_controller.store_operation_results(file_result=mock_file_result)
            
            # 2. Build success message for display
            success_data = workflow_controller.build_success_message()
            
            # 3. Clear results to prevent memory leaks
            workflow_controller.clear_stored_results()
            
            # Verify the pattern worked
            assert success_data.title == "Processing Complete! 🎉"
            assert len(success_data.summary_lines) == 3
            assert "✅ 5 files copied successfully" in success_data.summary_lines
            
            # Verify cleanup
            assert workflow_controller._last_file_result is None


class TestServiceRegistryConfiguration:
    """Test service registry configuration for success message integration"""
    
    def test_configure_services_registers_success_message_service(self):
        """Test that configure_services properly registers success message service"""
        
        # Clear existing registrations
        from core.services.service_registry import _service_registry
        _service_registry.clear()
        
        # Configure services
        configure_services()
        
        # Verify success message service is registered
        service = get_service(ISuccessMessageService)
        assert service is not None
        assert isinstance(service, SuccessMessageBuilder)
        
        # Verify it has required methods
        assert hasattr(service, 'build_forensic_success_message')
        assert hasattr(service, 'build_queue_save_success_message')
        assert hasattr(service, 'build_queue_load_success_message')
        assert hasattr(service, 'build_batch_success_message')
    
    def test_service_verification_includes_success_message_service(self):
        """Test that service verification includes success message service"""
        from core.services import verify_service_configuration
        
        # Configure services
        configure_services()
        
        # Verify configuration
        results = verify_service_configuration()
        
        # Success message service should be included and configured
        assert 'ISuccessMessageService' in results
        success_service_info = results['ISuccessMessageService']
        assert success_service_info['configured'] is True
        assert success_service_info['instance'] == 'SuccessMessageBuilder'
        assert success_service_info['error'] is None


if __name__ == '__main__':
    # Allow running tests directly
    pytest.main([__file__, '-v'])