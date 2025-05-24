#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Folder controller - handles folder structure operations
"""

from pathlib import Path
from typing import List, Optional

from core.models import FormData
from core.templates import FolderTemplate, FolderBuilder


class FolderController:
    """Handles folder structure creation and management"""
    
    @staticmethod
    def build_forensic_structure(form_data: FormData, base_path: Optional[Path] = None) -> Path:
        """Build the standard forensic folder structure"""
        if base_path:
            # Create the structure in the specified base path
            occurrence_path = base_path / form_data.occurrence_number
            
            # Level 2: Business @ Address or just Address
            if form_data.business_name:
                level2 = f"{form_data.business_name} @ {form_data.location_address}"
            else:
                level2 = form_data.location_address
                
            # Level 3: Date range
            if form_data.extraction_start and form_data.extraction_end:
                start = form_data.extraction_start.toString("yyyy-MM-dd_HHmm")
                end = form_data.extraction_end.toString("yyyy-MM-dd_HHmm")
                level3 = f"{start} - {end}"
            else:
                from datetime import datetime
                now = datetime.now().strftime("%Y-%m-%d_%H%M")
                level3 = f"{now} - {now}"
                
            # Clean path parts
            level2 = FolderTemplate._sanitize_path_part(None, level2)
            level3 = FolderTemplate._sanitize_path_part(None, level3)
            
            # Combine
            full_path = occurrence_path / level2 / level3
            full_path.mkdir(parents=True, exist_ok=True)
            
            return full_path
        else:
            # Use the core function
            return FolderBuilder.build_forensic_structure(form_data)
            
    @staticmethod
    def build_custom_structure(
        form_data: FormData,
        template_levels: List[str],
        base_path: Path
    ) -> Path:
        """Build a custom folder structure from template"""
        template = FolderTemplate("Custom", "Custom Structure", template_levels)
        folder_path = base_path / template.build_path(form_data)
        folder_path.mkdir(parents=True, exist_ok=True)
        return folder_path
        
    @staticmethod
    def get_preset_templates() -> List[FolderTemplate]:
        """Get available preset templates"""
        return FolderBuilder.get_preset_templates()