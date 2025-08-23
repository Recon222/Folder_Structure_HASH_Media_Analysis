#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI Tabs package
"""

from .forensic_tab import ForensicTab
from .batch_tab import BatchTab  
from .hashing_tab import HashingTab

__all__ = ['ForensicTab', 'BatchTab', 'HashingTab']