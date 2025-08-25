#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Folder controller - handles folder structure operations
"""

from pathlib import Path
from typing import Optional

from core.models import FormData
from core.path_utils import ForensicPathBuilder


class FolderController:
    """Handles folder structure creation and management"""
    
    @staticmethod
    def build_forensic_structure(form_data: FormData, base_path: Optional[Path] = None) -> Path:
        """Build the standard forensic folder structure using ForensicPathBuilder
        
        Args:
            form_data: FormData instance with case information
            base_path: Base directory for structure. If None, uses current directory
            
        Returns:
            Path to created directory structure
        """
        # Always use ForensicPathBuilder for consistent behavior
        if not base_path:
            base_path = Path.cwd()
        return ForensicPathBuilder.create_forensic_structure(base_path, form_data)