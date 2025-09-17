#!/usr/bin/env python3
"""
Enterprise service layer for Folder Structure Application

This package provides a comprehensive service-oriented architecture with:
- Dependency injection through service registry
- Clean separation of business logic from UI components
- Testable, mockable service interfaces
- Enterprise-grade error handling and logging
"""

from .service_registry import ServiceRegistry, get_service, register_service, register_factory
from .interfaces import (
    IService, IPathService, IFileOperationService,
    IReportService, IArchiveService, IValidationService,
    IVehicleTrackingService  # Optional vehicle tracking module
)
from .base_service import BaseService

# Service implementations
from .path_service import PathService
from .file_operation_service import FileOperationService
from .report_service import ReportService
from .archive_service import ArchiveService
from .validation_service import ValidationService

# Data structures for success messages
from .success_message_data import SuccessMessageData, QueueOperationData

# Service configuration
from .service_config import configure_services, verify_service_configuration

__all__ = [
    'ServiceRegistry', 'get_service', 'register_service', 'register_factory',
    'IService', 'IPathService', 'IFileOperationService',
    'IReportService', 'IArchiveService', 'IValidationService',
    'IVehicleTrackingService',  # Optional vehicle tracking interface
    'BaseService',
    'PathService', 'FileOperationService', 'ReportService',
    'ArchiveService', 'ValidationService',
    'SuccessMessageData', 'QueueOperationData',
    'configure_services', 'verify_service_configuration'
]