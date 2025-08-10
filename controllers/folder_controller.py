#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Folder controller - handles folder structure operations
"""

from pathlib import Path
from typing import List, Optional

from core.models import FormData
from core.templates import FolderTemplate, FolderBuilder
from core.path_utils import ForensicPathBuilder


class FolderController:
    """Handles folder structure creation and management"""
    
    @staticmethod
    def build_forensic_structure(form_data: FormData, base_path: Optional[Path] = None) -> Path:
        """Build the standard forensic folder structure using ForensicPathBuilder"""
        if base_path:
            # Use the centralized path builder to create forensic structure
            return ForensicPathBuilder.create_forensic_structure(base_path, form_data)
        else:
            # Use the core function (legacy support)
            return FolderBuilder.build_forensic_structure(form_data)
            
    @staticmethod
    def get_preset_templates() -> List[FolderTemplate]:
        """Get available preset templates"""
        return FolderBuilder.get_preset_templates()