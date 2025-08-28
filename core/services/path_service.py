#!/usr/bin/env python3
"""
Path service - centralized path building and validation with template support
"""
from pathlib import Path
from typing import Optional, Dict, Any, List
import json

from .interfaces import IPathService
from .base_service import BaseService
from ..models import FormData
from ..result_types import Result
from ..exceptions import FileOperationError, ErrorSeverity
from ..path_utils import ForensicPathBuilder, PathSanitizer
from ..template_path_builder import TemplatePathBuilder

class PathService(BaseService, IPathService):
    """Service for path building and validation operations with template support"""
    
    def __init__(self):
        super().__init__("PathService")
        self._path_sanitizer = PathSanitizer()
        self._templates: Dict[str, Dict] = {}
        self._current_template_id: str = "default_forensic"
        self._load_templates()
    
    def build_forensic_path(self, form_data: FormData, base_path: Path) -> Result[Path]:
        """Build forensic folder structure path with validation"""
        try:
            self._log_operation("build_forensic_path", f"base: {base_path}")
            
            # Input validation
            if not form_data:
                error = FileOperationError(
                    "Form data is required for forensic path building",
                    user_message="Form data is missing. Please fill out the required fields."
                )
                self._handle_error(error, {'method': 'build_forensic_path'})
                return Result.error(error)
            
            if not base_path:
                error = FileOperationError(
                    "Base path is required for forensic path building",
                    user_message="Output directory is required."
                )
                self._handle_error(error, {'method': 'build_forensic_path'})
                return Result.error(error)
            
            # Ensure base path exists
            if not base_path.exists():
                try:
                    base_path.mkdir(parents=True, exist_ok=True)
                    self._log_operation("base_path_created", str(base_path))
                except Exception as e:
                    error = FileOperationError(
                        f"Cannot create base directory {base_path}: {e}",
                        user_message="Cannot create output directory. Please check permissions."
                    )
                    self._handle_error(error, {'method': 'build_forensic_path'})
                    return Result.error(error)
            
            # Try template-based path building first
            try:
                # Get current template
                template = self._templates.get(self._current_template_id)
                if template:
                    # Build path using template
                    builder = TemplatePathBuilder(template, self._path_sanitizer)
                    relative_path = builder.build_relative_path(form_data)
                    
                    # Create full path
                    full_path = base_path / relative_path
                    full_path.mkdir(parents=True, exist_ok=True)
                    
                    self._log_operation("template_path_built", str(full_path))
                    return Result.success(full_path)
                else:
                    self._log_operation("template_not_found", f"Template {self._current_template_id} not found, using legacy builder", "warning")
            
            except Exception as e:
                self._log_operation("template_build_failed", str(e), "warning")
            
            # Fallback to existing ForensicPathBuilder for backward compatibility
            try:
                forensic_path = ForensicPathBuilder.create_forensic_structure(base_path, form_data)
                self._log_operation("legacy_path_built", str(forensic_path))
                return Result.success(forensic_path)
                
            except Exception as e:
                error = FileOperationError(
                    f"Failed to build forensic path: {e}",
                    user_message="Failed to create folder structure. Please check form data."
                )
                self._handle_error(error, {'method': 'build_forensic_path'})
                return Result.error(error)
                
        except Exception as e:
            error = FileOperationError(
                f"Unexpected error in build_forensic_path: {e}",
                user_message="An unexpected error occurred while building the folder structure."
            )
            self._handle_error(error, {'method': 'build_forensic_path'})
            return Result.error(error)
    
    def _load_templates(self):
        """Load templates from simple JSON file"""
        template_file = Path("templates/folder_templates.json")
        if template_file.exists():
            try:
                with open(template_file) as f:
                    templates_data = json.load(f)
                    self._templates = templates_data.get("templates", {})
                    self._log_operation("templates_loaded", f"Loaded {len(self._templates)} templates")
            except Exception as e:
                self._log_operation("template_load_failed", str(e), "error")
        
        # Ensure default template exists
        if "default_forensic" not in self._templates:
            self._templates["default_forensic"] = self._get_default_template()
            self._log_operation("default_template_created", "Using built-in default template")
    
    def _get_default_template(self) -> Dict[str, Any]:
        """Default template matching current ForensicPathBuilder behavior"""
        return {
            "templateName": "Default Forensic Structure",
            "structure": {
                "levels": [
                    {"pattern": "{occurrence_number}", "fallback": "NO_OCCURRENCE"},
                    {
                        "pattern": "{business_name} @ {location_address}",
                        "conditionals": {
                            "business_only": "{business_name}",
                            "location_only": "{location_address}",
                            "neither": "NO_LOCATION"
                        }
                    },
                    {
                        "pattern": "{video_start_datetime}_to_{video_end_datetime}_DVR_Time",
                        "dateFormat": "military",
                        "fallback": "{current_datetime}"
                    }
                ]
            },
            "documentsPlacement": "location"
        }
    
    def validate_output_path(self, path: Path, base: Path) -> Result[Path]:
        """Validate output path for security"""
        try:
            self._log_operation("validate_output_path", f"path: {path}, base: {base}")
            
            # Use existing path sanitizer validation
            validated_path = PathSanitizer.validate_destination(path, base)
            self._log_operation("path_validated", str(validated_path))
            return Result.success(validated_path)
            
        except ValueError as e:
            error = FileOperationError(
                f"Path validation failed: {e}",
                user_message="Invalid output path. Path may be outside allowed directory."
            )
            self._handle_error(error, {'method': 'validate_output_path'})
            return Result.error(error)
            
        except Exception as e:
            error = FileOperationError(
                f"Unexpected error in validate_output_path: {e}",
                user_message="An unexpected error occurred during path validation."
            )
            self._handle_error(error, {'method': 'validate_output_path'})
            return Result.error(error)
    
    def sanitize_path_component(self, component: str) -> str:
        """Sanitize individual path component"""
        try:
            self._log_operation("sanitize_component", f"component: {component[:50]}..." if len(component) > 50 else f"component: {component}")
            return self._path_sanitizer.sanitize_component(component)
        except Exception as e:
            self.logger.warning(f"Component sanitization failed for '{component}': {e}")
            return "_"  # Safe fallback
    
    def get_available_templates(self) -> List[Dict[str, str]]:
        """Get list of available templates for UI dropdown"""
        return [
            {
                "id": template_id,
                "name": template.get("templateName", template_id)
            }
            for template_id, template in self._templates.items()
        ]
    
    def set_current_template(self, template_id: str) -> Result[None]:
        """Set active template"""
        if template_id not in self._templates:
            error = FileOperationError(
                f"Template {template_id} not found",
                user_message="Selected template is not available."
            )
            self._handle_error(error, {'method': 'set_current_template'})
            return Result.error(error)
        
        self._current_template_id = template_id
        self._log_operation("template_changed", f"Active template: {template_id}")
        return Result.success(None)
    
    def get_current_template_id(self) -> str:
        """Get current template ID"""
        return self._current_template_id
    
    def reload_templates(self) -> Result[None]:
        """Reload templates from file"""
        try:
            old_count = len(self._templates)
            self._load_templates()
            new_count = len(self._templates)
            self._log_operation("templates_reloaded", f"Templates: {old_count} -> {new_count}")
            return Result.success(None)
        except Exception as e:
            error = FileOperationError(
                f"Failed to reload templates: {e}",
                user_message="Failed to reload template configuration."
            )
            self._handle_error(error, {'method': 'reload_templates'})
            return Result.error(error)
    
    def build_archive_name(self, form_data: FormData) -> Result[str]:
        """Build archive name using current template"""
        try:
            # Get current template
            template = self._templates.get(self._current_template_id)
            if template:
                # Build archive name using template
                builder = TemplatePathBuilder(template, self._path_sanitizer)
                archive_name = builder.build_archive_name(form_data)
                
                self._log_operation("template_archive_name_built", archive_name)
                return Result.success(archive_name)
            else:
                # Fallback to basic naming if no template
                fallback_name = f"{form_data.occurrence_number or 'Archive'}_Video_Recovery.zip"
                fallback_name = self._path_sanitizer.sanitize_component(fallback_name)
                
                self._log_operation("fallback_archive_name_used", fallback_name)
                return Result.success(fallback_name)
                
        except Exception as e:
            error = FileOperationError(
                f"Failed to build archive name: {e}",
                user_message="Failed to generate archive name."
            )
            self._handle_error(error, {'method': 'build_archive_name'})
            return Result.error(error)