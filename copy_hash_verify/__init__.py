#!/usr/bin/env python3
"""
Copy/Hash/Verify Module - Self-contained module for file operations

This module provides comprehensive file hashing, verification, and copy operations
with a professional UI following the media_analysis module patterns.

Features:
- Single hash calculation with multiple algorithms
- Bidirectional hash verification
- Copy operations with integrated hash verification
- Color-coded operation logging
- Professional tab-based UI
- SOA/DI architecture with service registration
"""

from .ui.copy_hash_verify_master_tab import CopyHashVerifyMasterTab
from core.logger import logger


def register_services():
    """
    Register copy/hash/verify services with main application

    Services registered:
    - ICopyVerifyService -> CopyVerifyService
    - IHashService -> HashService

    Note: SuccessMessageBuilder is instantiated directly in UI (not via DI)
    """
    from core.services import register_service, get_service

    # Check if already registered (idempotent)
    try:
        from .services.interfaces import ICopyVerifyService
        get_service(ICopyVerifyService)
        logger.debug("Copy/Hash/Verify services already registered")
        return
    except ValueError:
        pass  # Not registered, proceed

    try:
        # Import interfaces
        from .services.interfaces import (
            ICopyVerifyService,
            IHashService,
        )

        # Import implementations
        from .services.copy_verify_service import CopyVerifyService
        from .services.hash_service import HashService

        # Register services
        register_service(ICopyVerifyService, CopyVerifyService())
        register_service(IHashService, HashService())

        logger.info("Copy/Hash/Verify services registered successfully")

    except Exception as e:
        logger.error(f"Failed to register Copy/Hash/Verify services: {e}")
        raise


# Auto-register on module import
try:
    register_services()
except Exception as e:
    logger.error(f"Copy/Hash/Verify module registration failed: {e}")


__all__ = [
    'CopyHashVerifyMasterTab',
    'register_services',
]
