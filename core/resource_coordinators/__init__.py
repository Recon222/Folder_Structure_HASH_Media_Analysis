"""
Resource coordinator infrastructure for managing resource lifecycles.

This module provides coordinators that bridge between controllers and the
ResourceManagementService, ensuring proper resource tracking and cleanup.
"""

from .base_coordinator import BaseResourceCoordinator
from .worker_coordinator import WorkerResourceCoordinator

__all__ = [
    'BaseResourceCoordinator',
    'WorkerResourceCoordinator',
]