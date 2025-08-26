#!/usr/bin/env python3
"""
Enterprise service registry with dependency injection
"""
from typing import Dict, Type, TypeVar, Optional, Any
from abc import ABC, abstractmethod
import threading

T = TypeVar('T')

class IService(ABC):
    """Base interface for all services"""
    pass

class ServiceRegistry:
    """Thread-safe service registry with dependency injection"""
    
    def __init__(self):
        self._services: Dict[Type, Any] = {}
        self._factories: Dict[Type, callable] = {}
        self._singletons: Dict[Type, Any] = {}
        self._lock = threading.RLock()
    
    def register_singleton(self, interface: Type[T], implementation: T):
        """Register singleton service instance"""
        with self._lock:
            self._singletons[interface] = implementation
    
    def register_factory(self, interface: Type[T], factory: callable):
        """Register service factory"""
        with self._lock:
            self._factories[interface] = factory
    
    def get_service(self, interface: Type[T]) -> T:
        """Get service instance with dependency injection"""
        with self._lock:
            # Check singleton first
            if interface in self._singletons:
                return self._singletons[interface]
            
            # Check factory
            if interface in self._factories:
                return self._factories[interface]()
            
            raise ValueError(f"Service {interface.__name__} not registered")
    
    def clear(self):
        """Clear all registrations (for testing)"""
        with self._lock:
            self._services.clear()
            self._factories.clear()
            self._singletons.clear()

# Global service registry
_service_registry = ServiceRegistry()

def get_service(interface: Type[T]) -> T:
    """Convenience function to get service"""
    return _service_registry.get_service(interface)

def register_service(interface: Type[T], implementation: T):
    """Convenience function to register singleton service"""
    _service_registry.register_singleton(interface, implementation)

def register_factory(interface: Type[T], factory: callable):
    """Convenience function to register service factory"""
    _service_registry.register_factory(interface, factory)