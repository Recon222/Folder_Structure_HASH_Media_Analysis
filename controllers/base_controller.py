#!/usr/bin/env python3
"""
Base controller class with dependency injection, error handling, and resource coordination
"""
from abc import ABC
from typing import Optional, Dict, Any
import logging

from core.services import get_service
from core.error_handler import handle_error
from core.exceptions import FSAError
from core.resource_coordinators import BaseResourceCoordinator

class BaseController(ABC):
    """Base class for all controllers with service injection and resource management"""
    
    def __init__(self, logger_name: Optional[str] = None):
        self.logger = logging.getLogger(logger_name or self.__class__.__name__)
        
        # Initialize resource coordinator if service is available
        try:
            controller_id = f"{self.__class__.__name__}_{id(self)}"
            self._resources = self._create_resource_coordinator(controller_id)
            
            # Bind coordinator to this controller
            if self._resources:
                self._resources.bind_to_component(self)
        except (ValueError, ImportError) as e:
            # ResourceManagementService not available (e.g., in tests)
            self.logger.debug(f"Resource coordination not available: {e}")
            self._resources = None
        
    def _create_resource_coordinator(self, component_id: str) -> BaseResourceCoordinator:
        """
        Factory method for creating resource coordinator.
        Override in subclasses to use specialized coordinators.
        
        Args:
            component_id: Unique identifier for the component
            
        Returns:
            Resource coordinator instance
        """
        return BaseResourceCoordinator(component_id)
        
    @property
    def resources(self) -> Optional[BaseResourceCoordinator]:
        """
        Public API for resource management.
        
        Returns:
            The resource coordinator for this controller, or None if not available
        """
        return self._resources
        
    def cleanup(self) -> None:
        """
        Explicit cleanup method for controller resources.
        Should be called when controller is no longer needed.
        """
        try:
            if self._resources:
                self._resources.cleanup_all()
                self._log_operation("Cleanup completed", level="debug")
        except Exception as e:
            self.logger.error(f"Error during controller cleanup: {e}")
        
    def _get_service(self, service_interface):
        """Get service instance through dependency injection"""
        try:
            return get_service(service_interface)
        except ValueError as e:
            self.logger.error(f"Service {service_interface.__name__} not available: {e}")
            raise
    
    def _handle_error(self, error: FSAError, context: Optional[Dict[str, Any]] = None):
        """Handle controller error with consistent logging"""
        if context is None:
            context = {}
        
        context.update({
            'controller': self.__class__.__name__,
            'layer': 'controller'
        })
        
        handle_error(error, context)
        
    def _log_operation(self, operation: str, details: str = "", level: str = "info"):
        """Log controller operation with consistent format"""
        message = f"[{self.__class__.__name__}] {operation}"
        if details:
            message += f" - {details}"
            
        if level == "debug":
            self.logger.debug(message)
        elif level == "warning":
            self.logger.warning(message)
        elif level == "error":
            self.logger.error(message)
        else:
            self.logger.info(message)
            
    def __del__(self):
        """Ensure cleanup on deletion"""
        # Try to clean up resources if not already done
        if hasattr(self, '_resources') and self._resources:
            try:
                if self._resources.get_resource_count() > 0:
                    self.logger.warning(
                        f"Controller {self.__class__.__name__} being deleted with "
                        f"{self._resources.get_resource_count()} active resources"
                    )
                    self.cleanup()
            except Exception:
                pass  # Best effort cleanup