#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Native 7zip integration for high-performance archive operations
Windows-focused implementation using bundled 7za.exe for 7-14x speed improvement
"""

from .binary_manager import Native7ZipBinaryManager
from .command_builder import ForensicCommandBuilder  
from .controller import Native7ZipController

__all__ = ['Native7ZipBinaryManager', 'ForensicCommandBuilder', 'Native7ZipController']

# Version info
__version__ = '1.0.0'
__author__ = 'FSA Development Team'
__description__ = 'High-performance 7zip integration for forensic applications'