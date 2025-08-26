#!/usr/bin/env python3
"""
Service configuration and registration - streamlined
"""
from .service_registry import register_service
from .interfaces import (
    IPathService, IFileOperationService, IReportService,
    IArchiveService, IValidationService, ISuccessMessageService
)
from .path_service import PathService
from .file_operation_service import FileOperationService
from .report_service import ReportService
from .archive_service import ArchiveService
from .validation_service import ValidationService
from .success_message_builder import SuccessMessageBuilder

def configure_services(zip_controller=None):
    """Configure and register all application services"""
    try:
        # Core business logic services
        register_service(IPathService, PathService())
        register_service(IFileOperationService, FileOperationService())
        register_service(IReportService, ReportService())
        register_service(IValidationService, ValidationService())
        
        # Archive service requires zip controller dependency
        register_service(IArchiveService, ArchiveService(zip_controller))
        
        # ✅ SUCCESS MESSAGE SERVICE: Integrates existing SuccessMessageBuilder
        register_service(ISuccessMessageService, SuccessMessageBuilder())
        
        # Optional: Log successful configuration
        import logging
        logger = logging.getLogger("ServiceConfiguration")
        logger.info("All services configured successfully")
        
    except Exception as e:
        # Log configuration errors but don't crash the application
        import logging
        logger = logging.getLogger("ServiceConfiguration")
        logger.error(f"Service configuration failed: {e}")
        raise

def get_configured_services():
    """Get list of all configured service interfaces for debugging"""
    return [
        IPathService,
        IFileOperationService,
        IReportService,
        IArchiveService,
        IValidationService,
        ISuccessMessageService
    ]

def verify_service_configuration():
    """Verify all services are properly configured (for testing/debugging)"""
    from .service_registry import get_service
    
    results = {}
    services = get_configured_services()
    
    for service_interface in services:
        try:
            service = get_service(service_interface)
            results[service_interface.__name__] = {
                'configured': True,
                'instance': service.__class__.__name__,
                'error': None
            }
        except Exception as e:
            results[service_interface.__name__] = {
                'configured': False,
                'instance': None,
                'error': str(e)
            }
    
    return results