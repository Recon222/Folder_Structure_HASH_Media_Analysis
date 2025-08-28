#!/usr/bin/env python3
"""
Lightweight template-based path builder
"""

from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import re

from .path_utils import PathSanitizer
from .models import FormData

class TemplatePathBuilder:
    """Lightweight template-based path builder integrating with existing sanitization"""
    
    def __init__(self, template: Dict[str, Any], sanitizer: PathSanitizer):
        self.template = template
        self.sanitizer = sanitizer
    
    def build_relative_path(self, form_data: FormData) -> Path:
        """Build relative path from template and form data"""
        components = []
        
        for level in self.template["structure"]["levels"]:
            component = self._build_level_component(level, form_data)
            if component:
                # Use existing sanitization
                clean_component = self.sanitizer.sanitize_component(component)
                components.append(clean_component)
        
        return Path(*components) if components else Path('.')
    
    def _build_level_component(self, level: Dict[str, Any], form_data: FormData) -> str:
        """Build single level component"""
        pattern = level.get("pattern", "")
        
        # Handle conditionals (for business/location level)
        if "conditionals" in level:
            pattern = self._resolve_conditional(level, form_data, pattern)
        
        # Replace placeholders
        component = self._replace_placeholders(pattern, form_data, level)
        
        # Use fallback if empty
        if not component.strip():
            fallback = level.get("fallback", "UNKNOWN")
            component = self._replace_placeholders(fallback, form_data, level)
        
        return component
    
    def _resolve_conditional(self, level: Dict[str, Any], form_data: FormData, pattern: str) -> str:
        """Handle conditional patterns for business/location"""
        business = getattr(form_data, 'business_name', None) or ""
        location = getattr(form_data, 'location_address', None) or ""
        
        conditionals = level.get("conditionals", {})
        
        if business and location:
            return pattern  # Use full pattern
        elif business:
            return conditionals.get("business_only", pattern)
        elif location:
            return conditionals.get("location_only", pattern)
        else:
            return conditionals.get("neither", pattern)
    
    def _replace_placeholders(self, pattern: str, form_data: FormData, level: Dict[str, Any]) -> str:
        """Replace {field} placeholders with actual values"""
        # Handle date formatting
        if level.get("dateFormat") == "military":
            pattern = self._format_military_dates(pattern, form_data)
        elif level.get("dateFormat") == "iso":
            pattern = self._format_iso_dates(pattern, form_data)
        
        # Standard field replacement
        placeholders = re.findall(r'\{(\w+)\}', pattern)
        for placeholder in placeholders:
            value = self._get_field_value(placeholder, form_data)
            pattern = pattern.replace(f'{{{placeholder}}}', str(value))
        
        return pattern
    
    def _format_military_dates(self, pattern: str, form_data: FormData) -> str:
        """Convert datetime fields to military format"""
        months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
        
        # Handle start datetime
        if '{video_start_datetime}' in pattern:
            start_dt = getattr(form_data, 'video_start_datetime', None)
            if start_dt:
                formatted = self._format_datetime_military(start_dt, months)
                pattern = pattern.replace('{video_start_datetime}', formatted)
        
        # Handle end datetime  
        if '{video_end_datetime}' in pattern:
            end_dt = getattr(form_data, 'video_end_datetime', None)
            if end_dt:
                formatted = self._format_datetime_military(end_dt, months)
                pattern = pattern.replace('{video_end_datetime}', formatted)
        
        return pattern
    
    def _format_iso_dates(self, pattern: str, form_data: FormData) -> str:
        """Convert datetime fields to ISO format"""
        # Handle start datetime
        if '{video_start_datetime}' in pattern:
            start_dt = getattr(form_data, 'video_start_datetime', None)
            if start_dt:
                formatted = self._format_datetime_iso(start_dt)
                pattern = pattern.replace('{video_start_datetime}', formatted)
        
        # Handle end datetime  
        if '{video_end_datetime}' in pattern:
            end_dt = getattr(form_data, 'video_end_datetime', None)
            if end_dt:
                formatted = self._format_datetime_iso(end_dt)
                pattern = pattern.replace('{video_end_datetime}', formatted)
        
        return pattern
    
    def _format_datetime_military(self, dt, months) -> str:
        """Format single datetime to military format"""
        if hasattr(dt, 'toString'):  # QDateTime
            month_idx = dt.date().month() - 1
            return f"{dt.date().day()}{months[month_idx]}{dt.toString('yy')}_{dt.toString('HHmm')}"
        else:  # Standard datetime
            month_idx = dt.month - 1
            return f"{dt.day}{months[month_idx]}{dt.strftime('%y')}_{dt.strftime('%H%M')}"
    
    def _format_datetime_iso(self, dt) -> str:
        """Format single datetime to ISO format"""
        if hasattr(dt, 'toString'):  # QDateTime
            return dt.toString('yyyy-MM-dd_HHmm')
        else:  # Standard datetime
            return dt.strftime('%Y-%m-%d_%H%M')
    
    def _get_field_value(self, field: str, form_data: FormData) -> str:
        """Get field value from form data"""
        if field == 'current_datetime':
            return datetime.now().strftime('%Y-%m-%d_%H%M%S')
        elif field == 'year':
            return str(datetime.now().year)
        
        value = getattr(form_data, field, None)
        return str(value) if value else ""
    
    def build_archive_name(self, form_data: FormData) -> str:
        """Build archive name from template"""
        archive_config = self.template.get('archiveNaming', {})
        pattern = archive_config.get('pattern', '{occurrence_number}_Video_Recovery.zip')
        fallback_pattern = archive_config.get('fallbackPattern', '{occurrence_number}_Recovery.zip')
        
        try:
            # Try main pattern first
            archive_name = self._replace_placeholders(pattern, form_data, {})
            
            # Check if all placeholders were replaced (no remaining {})
            if '{' not in archive_name or '}' not in archive_name:
                # Clean up any empty parts from missing data
                archive_name = re.sub(r'\s+@\s*', ' ', archive_name)  # Remove empty @ parts
                archive_name = re.sub(r'\s{2,}', ' ', archive_name)   # Remove multiple spaces
                archive_name = archive_name.strip()
                
                # Sanitize the filename
                archive_name = self.sanitizer.sanitize_component(archive_name)
                
                # Ensure .zip extension
                if not archive_name.lower().endswith('.zip'):
                    archive_name += '.zip'
                    
                return archive_name
            
        except Exception:
            # If main pattern fails, ignore and try fallback
            pass
        
        # Use fallback pattern
        try:
            archive_name = self._replace_placeholders(fallback_pattern, form_data, {})
            archive_name = self.sanitizer.sanitize_component(archive_name)
            
            if not archive_name.lower().endswith('.zip'):
                archive_name += '.zip'
                
            return archive_name
            
        except Exception:
            # Ultimate fallback - basic name with timestamp
            fallback_name = f"Archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            return self.sanitizer.sanitize_component(fallback_name)