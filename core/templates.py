#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Folder structure templates - flexible and extensible
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from .models import FormData


@dataclass
class FolderTemplate:
    """Template for custom folder structures"""
    name: str
    description: str
    levels: List[str] = field(default_factory=list)
    
    def build_path(self, form_data: FormData) -> Path:
        """Build actual path from template and form data"""
        path_parts = []
        
        # Create a dict of available values for formatting
        format_dict = self._build_format_dict(form_data)
        
        # Build path from template levels
        for level in self.levels:
            try:
                # Replace template variables
                part = level.format(**format_dict)
                # Clean up the path part
                part = self._sanitize_path_part(part)
                if part:  # Only add non-empty parts
                    path_parts.append(part)
            except KeyError as e:
                # If a variable doesn't exist, use the template as-is
                path_parts.append(self._sanitize_path_part(level))
                
        return Path(*path_parts) if path_parts else Path('.')
    
    def _build_format_dict(self, form_data: FormData) -> Dict[str, str]:
        """Build dictionary of available format values"""
        format_dict = {
            'occurrence_number': form_data.occurrence_number,
            'business_name': form_data.business_name,
            'location_address': form_data.location_address,
            'technician_name': form_data.technician_name,
            'badge_number': form_data.badge_number,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H-%M-%S'),
            'year': datetime.now().strftime('%Y'),
            'month': datetime.now().strftime('%m'),
            'day': datetime.now().strftime('%d'),
        }
        
        # Add datetime fields if they exist
        if form_data.extraction_start:
            format_dict['extraction_start'] = form_data.extraction_start.toString('yyyy-MM-dd_HH-mm')
            format_dict['extraction_start_date'] = form_data.extraction_start.toString('yyyy-MM-dd')
            format_dict['extraction_start_time'] = form_data.extraction_start.toString('HH-mm')
            
        if form_data.extraction_end:
            format_dict['extraction_end'] = form_data.extraction_end.toString('yyyy-MM-dd_HH-mm')
            format_dict['extraction_end_date'] = form_data.extraction_end.toString('yyyy-MM-dd')
            format_dict['extraction_end_time'] = form_data.extraction_end.toString('HH-mm')
            
        return format_dict
    
    def _sanitize_path_part(self, part: str) -> str:
        """Remove invalid characters from path part"""
        # Replace invalid characters with underscores
        invalid_chars = '<>:"|?*'
        for char in invalid_chars:
            part = part.replace(char, '_')
        # Remove leading/trailing whitespace and dots
        part = part.strip(' .')
        return part


class FolderBuilder:
    """Handles folder structure creation"""
    
    @staticmethod
    def build_forensic_structure(form_data: FormData) -> Path:
        """Build the standard forensic folder structure"""
        # Root: Occurrence number
        root = Path(form_data.occurrence_number)
        
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
            # Fallback if dates aren't set
            from datetime import datetime
            now = datetime.now().strftime("%Y-%m-%d_%H%M")
            level3 = f"{now} - {now}"
        
        # Clean path parts
        level2 = FolderTemplate._sanitize_path_part(None, level2)
        level3 = FolderTemplate._sanitize_path_part(None, level3)
        
        # Combine
        full_path = root / level2 / level3
        
        # Create directories
        full_path.mkdir(parents=True, exist_ok=True)
        
        return full_path
    
    @staticmethod
    def get_preset_templates() -> List[FolderTemplate]:
        """Get built-in template presets"""
        return [
            FolderTemplate(
                name="Law Enforcement",
                description="Standard forensic evidence structure",
                levels=[
                    "{occurrence_number}",
                    "{business_name} @ {location_address}",
                    "{extraction_start} - {extraction_end}"
                ]
            ),
            FolderTemplate(
                name="Medical Records",
                description="Patient-based medical file organization",
                levels=[
                    "Patients",
                    "{occurrence_number}_{technician_name}",
                    "{date}_Visit",
                    "Records"
                ]
            ),
            FolderTemplate(
                name="Legal Documents",
                description="Case-based legal document organization",
                levels=[
                    "Cases",
                    "{occurrence_number}",
                    "{business_name}",
                    "{date}_Documents"
                ]
            ),
            FolderTemplate(
                name="Media Production",
                description="Project-based media file organization",
                levels=[
                    "{occurrence_number}_Project",
                    "{date}_Shoot",
                    "{technician_name}",
                    "Raw_Media"
                ]
            )
        ]