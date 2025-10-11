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
"""

from .ui.copy_hash_verify_master_tab import CopyHashVerifyMasterTab

__all__ = ['CopyHashVerifyMasterTab']
