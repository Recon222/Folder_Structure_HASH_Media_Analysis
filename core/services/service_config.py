#!/usr/bin/env python3
"""
Service configuration and registration - streamlined
"""
from .service_registry import register_service
from .interfaces import (
    IPathService, IFileOperationService, IReportService,
    IArchiveService, IValidationService,
    ICopyVerifyService, IMediaAnalysisService, IResourceManagementService,
    # Success Builder Interfaces
    IForensicSuccessService, IHashingSuccessService,
    ICopyVerifySuccessService, IMediaAnalysisSuccessService,
    IBatchSuccessService,
    # Vehicle Tracking Interface (optional module)
    IVehicleTrackingService
)
from .path_service import PathService
from .file_operation_service import FileOperationService
from .report_service import ReportService
from .archive_service import ArchiveService
from .validation_service import ValidationService
from .copy_verify_service import CopyVerifyService
from .media_analysis_service import MediaAnalysisService
from .thread_management_service import ThreadManagementService, IThreadManagementService
from .performance_formatter_service import PerformanceFormatterService, IPerformanceFormatterService
from .resource_management_service import ResourceManagementService
# Success Builder Implementations
from .success_builders.forensic_success import ForensicSuccessBuilder
from .success_builders.hashing_success import HashingSuccessBuilder
from .success_builders.copy_verify_success import CopyVerifySuccessBuilder
from .success_builders.media_analysis_success import MediaAnalysisSuccessBuilder
from .success_builders.batch_success import BatchSuccessBuilder

def configure_services(zip_controller=None):
    """Configure and register all application services"""
    try:
        # ✅ RESOURCE MANAGEMENT SERVICE: Foundational service for plugin architecture
        # Register first as other services and components will depend on it
        register_service(IResourceManagementService, ResourceManagementService())
        
        # Core business logic services
        register_service(IPathService, PathService())
        register_service(IFileOperationService, FileOperationService())
        register_service(IReportService, ReportService())
        register_service(IValidationService, ValidationService())
        
        # Archive service requires zip controller dependency
        register_service(IArchiveService, ArchiveService(zip_controller))
        
        # ✅ COPY VERIFY SERVICE: SOA-compliant copy and verify operations
        register_service(ICopyVerifyService, CopyVerifyService())
        
        # ✅ MEDIA ANALYSIS SERVICE: FFprobe-based media metadata extraction
        register_service(IMediaAnalysisService, MediaAnalysisService())
        
        # ✅ THREAD MANAGEMENT SERVICE: Centralized thread lifecycle management
        register_service(IThreadManagementService, ThreadManagementService())
        
        # ✅ PERFORMANCE FORMATTER SERVICE: Performance data formatting and extraction
        register_service(IPerformanceFormatterService, PerformanceFormatterService())
        
        # ✅ SUCCESS BUILDER SERVICES: Tab-specific success message builders (SOA-compliant)
        register_service(IForensicSuccessService, ForensicSuccessBuilder())
        register_service(IHashingSuccessService, HashingSuccessBuilder())
        register_service(ICopyVerifySuccessService, CopyVerifySuccessBuilder())
        register_service(IMediaAnalysisSuccessService, MediaAnalysisSuccessBuilder())
        register_service(IBatchSuccessService, BatchSuccessBuilder())

        # ✅ VEHICLE TRACKING SERVICE: Optional module with graceful fallback
        # Only register if the module is available (plugin architecture)
        try:
            from vehicle_tracking.services.vehicle_tracking_service import VehicleTrackingService
            register_service(IVehicleTrackingService, VehicleTrackingService())
            import logging
            logger = logging.getLogger("ServiceConfiguration")
            logger.info("Vehicle tracking module registered successfully")
        except ImportError:
            # Vehicle tracking module not available - graceful degradation
            import logging
            logger = logging.getLogger("ServiceConfiguration")
            logger.debug("Vehicle tracking module not available - skipping registration")

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
    services = [
        IResourceManagementService,  # Foundational service
        IPathService,
        IFileOperationService,
        IReportService,
        IArchiveService,
        IValidationService,
        ICopyVerifyService,
        IMediaAnalysisService,
        IThreadManagementService,
        IPerformanceFormatterService,
        # Success Builder Services
        IForensicSuccessService,
        IHashingSuccessService,
        ICopyVerifySuccessService,
        IMediaAnalysisSuccessService,
        IBatchSuccessService
    ]

    # Include vehicle tracking if available
    try:
        import vehicle_tracking
        services.append(IVehicleTrackingService)
    except ImportError:
        pass

    return services

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