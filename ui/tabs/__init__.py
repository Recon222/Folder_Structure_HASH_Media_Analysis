#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI Tabs package
"""

from .forensic_tab import ForensicTab
from .batch_tab import BatchTab  
from .hashing_tab import HashingTab
from .copy_verify_tab import CopyVerifyTab

__all__ = ['ForensicTab', 'BatchTab', 'HashingTab', 'CopyVerifyTab']