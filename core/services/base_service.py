#!/usr/bin/env python3
"""
Base service class with common functionality
"""
from abc import ABC
from typing import Optional, Dict, Any
import logging

from .interfaces import IService
from ..error_handler import handle_error
from ..exceptions import FSAError, ErrorSeverity

class BaseService(IService, ABC):
    """Base class for all services with common functionality"""
    
    def __init__(self, logger_name: Optional[str] = None):
        self.logger = logging.getLogger(logger_name or self.__class__.__name__)
        
    def _handle_error(self, error: FSAError, context: Optional[Dict[str, Any]] = None):
        """Handle error with consistent logging and reporting"""
        if context is None:
            context = {}
        
        context.update({
            'service': self.__class__.__name__,
            'service_method': context.get('method', 'unknown')
        })
        
        handle_error(error, context)
        
    def _log_operation(self, operation: str, details: str = "", level: str = "info"):
        """Log service operation with consistent format"""
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