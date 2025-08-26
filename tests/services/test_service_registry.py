#!/usr/bin/env python3
"""
Tests for service registry functionality
"""
import pytest
import threading
import time
from core.services import ServiceRegistry, IService

class MockService(IService):
    def __init__(self, value: str = "test"):
        self.value = value

class MockDependentService(IService):
    def __init__(self, dep: MockService):
        self.dependency = dep

def test_singleton_registration():
    """Test singleton service registration"""
    registry = ServiceRegistry()
    service = MockService("singleton")
    
    registry.register_singleton(MockService, service)
    retrieved = registry.get_service(MockService)
    
    assert retrieved is service
    assert retrieved.value == "singleton"

def test_factory_registration():
    """Test factory service registration"""
    registry = ServiceRegistry()
    
    def factory():
        return MockService("factory")
    
    registry.register_factory(MockService, factory)
    retrieved = registry.get_service(MockService)
    
    assert isinstance(retrieved, MockService)
    assert retrieved.value == "factory"

def test_factory_creates_new_instances():
    """Test that factory creates new instances each time"""
    registry = ServiceRegistry()
    
    def factory():
        return MockService("factory")
    
    registry.register_factory(MockService, factory)
    instance1 = registry.get_service(MockService)
    instance2 = registry.get_service(MockService)
    
    # Should be different instances
    assert instance1 is not instance2
    assert instance1.value == instance2.value == "factory"

def test_singleton_returns_same_instance():
    """Test that singleton returns the same instance every time"""
    registry = ServiceRegistry()
    service = MockService("singleton")
    
    registry.register_singleton(MockService, service)
    instance1 = registry.get_service(MockService)
    instance2 = registry.get_service(MockService)
    
    # Should be the same instance
    assert instance1 is instance2 is service

def test_service_not_found():
    """Test error when service not registered"""
    registry = ServiceRegistry()
    
    with pytest.raises(ValueError, match="Service MockService not registered"):
        registry.get_service(MockService)

def test_singleton_priority_over_factory():
    """Test that singleton takes priority over factory when both are registered"""
    registry = ServiceRegistry()
    singleton = MockService("singleton")
    
    registry.register_factory(MockService, lambda: MockService("factory"))
    registry.register_singleton(MockService, singleton)
    
    retrieved = registry.get_service(MockService)
    assert retrieved is singleton
    assert retrieved.value == "singleton"

def test_clear_registry():
    """Test clearing all registrations"""
    registry = ServiceRegistry()
    service = MockService("test")
    
    registry.register_singleton(MockService, service)
    assert registry.get_service(MockService) is service
    
    registry.clear()
    
    with pytest.raises(ValueError):
        registry.get_service(MockService)

def test_thread_safety():
    """Test thread safety of service registry"""
    registry = ServiceRegistry()
    results = []
    errors = []
    
    def register_and_get_service():
        try:
            registry.register_singleton(MockService, MockService("thread"))
            time.sleep(0.01)  # Small delay to test race conditions
            result = registry.get_service(MockService)
            results.append(result)
        except Exception as e:
            errors.append(e)
    
    # Create multiple threads that try to register and get the service
    threads = [threading.Thread(target=register_and_get_service) for _ in range(10)]
    
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    
    # Should not have any errors
    assert len(errors) == 0
    
    # All results should be the same instance (last registration wins)
    assert len(results) == 10
    unique_instances = set(id(result) for result in results)
    assert len(unique_instances) == 1, f"Expected 1 unique instance, got {len(unique_instances)}"

def test_multiple_service_types():
    """Test registry with multiple different service types"""
    registry = ServiceRegistry()
    
    test_service = MockService("test")
    another_service = MockDependentService(test_service)
    
    registry.register_singleton(MockService, test_service)
    registry.register_singleton(MockDependentService, another_service)
    
    retrieved_test = registry.get_service(MockService)
    retrieved_another = registry.get_service(MockDependentService)
    
    assert retrieved_test is test_service
    assert retrieved_another is another_service
    assert retrieved_another.dependency is test_service

def test_convenience_functions():
    """Test global convenience functions"""
    from core.services import get_service, register_service, register_factory
    
    # Clear any existing registrations
    from core.services.service_registry import _service_registry
    _service_registry.clear()
    
    # Test register_service convenience function
    service = MockService("convenience")
    register_service(MockService, service)
    
    retrieved = get_service(MockService)
    assert retrieved is service
    
    # Test register_factory convenience function  
    _service_registry.clear()
    register_factory(MockService, lambda: MockService("factory_convenience"))
    
    retrieved = get_service(MockService)
    assert retrieved.value == "factory_convenience"

def test_error_messages():
    """Test that error messages are informative"""
    registry = ServiceRegistry()
    
    try:
        registry.get_service(MockService)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "MockService" in str(e)
        assert "not registered" in str(e)