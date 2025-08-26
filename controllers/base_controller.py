#!/usr/bin/env python3
"""
Base controller class with dependency injection and error handling
"""
from abc import ABC
from typing import Optional, Dict, Any
import logging

from core.services import get_service
from core.error_handler import handle_error
from core.exceptions import FSAError

class BaseController(ABC):
    """Base class for all controllers with service injection"""
    
    def __init__(self, logger_name: Optional[str] = None):
        self.logger = logging.getLogger(logger_name or self.__class__.__name__)
        
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