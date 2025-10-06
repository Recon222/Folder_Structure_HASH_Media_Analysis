#!/usr/bin/env python3
"""
Path service - centralized path building and validation with template support
"""
from pathlib import Path
from typing import Optional, Dict, Any, List
import json

from .interfaces import IPathService
from .base_service import BaseService
from .template_management_service import TemplateManagementService, TemplateSource
from ..models import FormData
from ..result_types import Result
from ..exceptions import FileOperationError, TemplateValidationError, ErrorSeverity
from ..path_utils import ForensicPathBuilder, PathSanitizer
from ..template_path_builder import TemplatePathBuilder

class PathService(BaseService, IPathService):
    """Service for path building and validation operations with template support"""
    
    def __init__(self):
        super().__init__("PathService")
        self._path_sanitizer = PathSanitizer()
        self._templates: Dict[str, Dict] = {}
        self._current_template_id: str = "default_forensic"
        
        # Initialize template management service
        self._template_manager = TemplateManagementService()
        
        self._load_templates()
    
    def build_forensic_path(self, form_data: FormData, base_path: Path) -> Result[Path]:
        """Build forensic folder structure path with validation

        NOTE: This method creates only the PARENT directories, NOT the final destination folder.
        This allows os.rename() to work for instant same-drive moves.

        For a "Create Structure Only" feature, use:
            full_path.mkdir(parents=True, exist_ok=True) instead of full_path.parent.mkdir()
        """
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

                    # Create full path (but don't create final folder yet for same-drive move optimization)
                    full_path = base_path / relative_path

                    # Create only the parent directories, NOT the final destination folder
                    # This allows os.rename() to work for instant same-drive moves
                    full_path.parent.mkdir(parents=True, exist_ok=True)

                    self._log_operation("template_path_built", str(full_path))
                    return Result.success(full_path)
                else:
                    self._log_operation("template_not_found", f"Template {self._current_template_id} not found, using legacy builder", "warning")
            
            except Exception as e:
                self._log_operation("template_build_failed", str(e), "warning")
            
            # Fallback to existing ForensicPathBuilder for backward compatibility
            try:
                # Build path but only create parent directories, not final folder
                # This allows os.rename() to work for instant same-drive moves
                relative_path = ForensicPathBuilder.build_relative_path(form_data)
                forensic_path = base_path / relative_path

                # Create only parent directories, NOT the final destination folder
                forensic_path.parent.mkdir(parents=True, exist_ok=True)

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
        """Load templates from all sources using template management service"""
        try:
            # Load all templates through template management service
            all_templates_result = self._template_manager.get_all_templates()
            if all_templates_result.success:
                self._templates = {}
                for template_info in all_templates_result.value:
                    self._templates[template_info.template_id] = template_info.template_data
                
                self._log_operation("templates_loaded", 
                                  f"Loaded {len(self._templates)} templates from all sources")
            else:
                self._log_operation("template_load_failed", str(all_templates_result.error), "error")
                self._templates = {}
                
        except Exception as e:
            self._log_operation("template_load_failed", str(e), "error")
            self._templates = {}
        
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
            "documentsPlacement": 1
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
    
    def import_template(self, file_path: Path) -> Result[Dict[str, Any]]:
        """Import template from JSON file"""
        try:
            import_result = self._template_manager.import_template(file_path)
            if import_result.success:
                # Reload templates to include newly imported ones
                self._load_templates()
                self._log_operation("template_imported", f"Template imported from {file_path}")
            
            return import_result
            
        except Exception as e:
            error = TemplateValidationError(
                f"Template import failed: {e}",
                user_message="Failed to import template file."
            )
            self._handle_error(error, {'method': 'import_template', 'file_path': str(file_path)})
            return Result.error(error)
    
    def export_template(self, template_id: str, file_path: Path) -> Result[None]:
        """Export template to JSON file"""
        try:
            export_result = self._template_manager.export_template(template_id, file_path)
            if export_result.success:
                self._log_operation("template_exported", f"Template {template_id} exported to {file_path}")
            
            return export_result
            
        except Exception as e:
            error = TemplateValidationError(
                f"Template export failed: {e}",
                template_id=template_id,
                user_message=f"Failed to export template '{template_id}'."
            )
            self._handle_error(error, {'method': 'export_template', 'template_id': template_id})
            return Result.error(error)
    
    def get_template_info(self, template_id: str) -> Result[Dict[str, Any]]:
        """Get detailed template information"""
        try:
            all_templates_result = self._template_manager.get_all_templates()
            if not all_templates_result.success:
                return Result.error(all_templates_result.error)
            
            for template_info in all_templates_result.value:
                if template_info.template_id == template_id:
                    return Result.success(template_info.to_dict())
            
            error = TemplateValidationError(
                f"Template {template_id} not found",
                template_id=template_id,
                user_message=f"Template '{template_id}' could not be found."
            )
            return Result.error(error)
            
        except Exception as e:
            error = TemplateValidationError(
                f"Failed to get template info: {e}",
                template_id=template_id,
                user_message=f"Failed to retrieve information for template '{template_id}'."
            )
            self._handle_error(error, {'method': 'get_template_info', 'template_id': template_id})
            return Result.error(error)
    
    def validate_template_file(self, file_path: Path) -> Result[List[Dict[str, Any]]]:
        """Validate template file and return validation issues"""
        try:
            validation_result = self._template_manager.validator.validate_template_file(file_path)
            if validation_result.success:
                issues = [issue.to_dict() for issue in validation_result.value]
                return Result.success(issues)
            else:
                return Result.error(validation_result.error)
                
        except Exception as e:
            error = TemplateValidationError(
                f"Template file validation failed: {e}",
                user_message="Failed to validate template file."
            )
            self._handle_error(error, {'method': 'validate_template_file', 'file_path': str(file_path)})
            return Result.error(error)
    
    def delete_user_template(self, template_id: str) -> Result[None]:
        """Delete user-imported template"""
        try:
            delete_result = self._template_manager.delete_user_template(template_id)
            if delete_result.success:
                # Reload templates to reflect deletion
                self._load_templates()
                # Update current template if deleted template was active
                if self._current_template_id == template_id:
                    self._current_template_id = "default_forensic"
                self._log_operation("template_deleted", f"Template {template_id} deleted")
            
            return delete_result
            
        except Exception as e:
            error = TemplateValidationError(
                f"Template deletion failed: {e}",
                template_id=template_id,
                user_message=f"Failed to delete template '{template_id}'."
            )
            self._handle_error(error, {'method': 'delete_user_template', 'template_id': template_id})
            return Result.error(error)
    
    def get_template_sources(self) -> List[Dict[str, str]]:
        """Get available templates grouped by source"""
        try:
            all_templates_result = self._template_manager.get_all_templates()
            if not all_templates_result.success:
                return []
            
            sources = {}
            for template_info in all_templates_result.value:
                source = template_info.source
                if source not in sources:
                    sources[source] = []
                
                sources[source].append({
                    "id": template_info.template_id,
                    "name": template_info.name,
                    "description": template_info.description
                })
            
            # Convert to list format
            result = []
            for source_name, templates in sources.items():
                result.append({
                    "source": source_name,
                    "templates": templates
                })
            
            return result
            
        except Exception as e:
            self._log_operation("get_template_sources_failed", str(e), "warning")
            return []
    
    def determine_documents_location(
        self, 
        base_forensic_path: Path,
        output_directory: Path
    ) -> Result[Path]:
        """
        Determine where to place the Documents folder based on template settings
        
        This encapsulates the business logic for document folder placement that was
        previously in MainWindow.generate_reports()
        
        Args:
            base_forensic_path: The base forensic structure path (datetime folder level)
                               NOT a file path with preserved folder structure
            output_directory: Base output directory
            
        Returns:
            Result containing the Documents folder path
        """
        try:
            self._log_operation("determine_documents_location", f"base_path: {base_forensic_path}")
            
            # Get the template and its documentsPlacement setting
            template = self._templates.get(self._current_template_id)
            if not template:
                documents_placement = 1  # Default to level 1
            else:
                documents_placement = template.get('documentsPlacement', 1)
                
                # Auto-convert legacy string values to integers
                if isinstance(documents_placement, str):
                    conversion_map = {
                        "occurrence": 0,  # Level 0
                        "location": 1,    # Level 1
                        "datetime": 2     # Level 2
                    }
                    original_value = documents_placement
                    documents_placement = conversion_map.get(documents_placement, 1)
                    self._log_operation(
                        "legacy_conversion",
                        f"Converted '{original_value}' to level {documents_placement}",
                        "info"
                    )
            
            # Validate it's an integer
            if not isinstance(documents_placement, int):
                self._log_operation(
                    "documents_placement_error",
                    f"Invalid documentsPlacement type: {type(documents_placement)}, using default level 1",
                    "warning"
                )
                documents_placement = 1
            
            # Calculate level-based placement
            documents_dir = self._calculate_level_placement(
                base_forensic_path,
                output_directory,
                documents_placement,
                template
            )
            
            # Create the Documents directory
            try:
                documents_dir.mkdir(parents=True, exist_ok=True)
                self._log_operation("documents_location", f"Created at: {documents_dir}")
                return Result.success(documents_dir)
            except Exception as e:
                error = FileOperationError(
                    f"Failed to create Documents folder: {e}",
                    user_message="Failed to create Documents folder. Please check permissions."
                )
                self._handle_error(error, {'method': 'determine_documents_location'})
                return Result.error(error)
                
        except Exception as e:
            error = FileOperationError(
                f"Failed to determine documents location: {e}",
                user_message="Failed to determine where to place documents."
            )
            self._handle_error(error, {'method': 'determine_documents_location'})
            return Result.error(error)
    
    def _calculate_level_placement(
        self,
        base_forensic_path: Path,
        output_directory: Path,
        level_index: int,
        template: dict
    ) -> Path:
        """
        Calculate documents placement using level index
        
        Args:
            base_forensic_path: Deepest level path (e.g., datetime folder)
            output_directory: Root output directory
            level_index: Zero-based index of desired level
            template: Template configuration (may be None)
            
        Returns:
            Path where Documents folder should be placed
        """
        # Get the number of levels in the template
        if not template:
            # No template, use default 3-level structure
            total_levels = 3
        else:
            levels = template.get('structure', {}).get('levels', [])
            total_levels = len(levels)
        
        if total_levels == 0:
            # No levels defined, use output directory
            self._log_operation("level_placement", "No levels in template, using output directory")
            return output_directory / "Documents"
        
        # Clamp level index to valid range
        if level_index >= total_levels:
            self._log_operation(
                "level_placement_warning",
                f"Level {level_index} exceeds template levels ({total_levels}), using deepest level",
                "warning"
            )
            return base_forensic_path / "Documents"
        
        if level_index < 0:
            self._log_operation(
                "level_placement_warning",
                f"Invalid level {level_index}, using default level 1",
                "warning"
            )
            level_index = min(1, total_levels - 1)
        
        # Calculate how many levels up from the base path
        # base_forensic_path is at level (total_levels - 1)
        current_level = total_levels - 1
        steps_up = current_level - level_index
        
        self._log_operation(
            "level_calculation",
            f"Total levels: {total_levels}, Target level: {level_index}, Steps up: {steps_up}"
        )
        
        # Navigate up from base path
        target_path = base_forensic_path
        for _ in range(steps_up):
            if target_path.parent == target_path:
                # Reached root, can't go higher
                self._log_operation("level_placement", f"Reached root at {target_path}")
                break
            target_path = target_path.parent
        
        return target_path / "Documents"
    
    def find_occurrence_folder(
        self,
        path: Path,
        output_directory: Path
    ) -> Result[Path]:
        """
        Find the occurrence number folder by navigating up the directory tree
        
        This encapsulates the path navigation logic that was previously in MainWindow
        
        Args:
            path: Current path to start from
            output_directory: Base output directory to stop at
            
        Returns:
            Result containing the occurrence folder path
        """
        try:
            self._log_operation("find_occurrence_folder", f"path: {path}, root: {output_directory}")
            
            # Navigate to root folder (occurrence number level)
            current_path = path if path.is_dir() else path.parent
            
            # Check if we're at or above the output directory (invalid structure)
            if current_path == output_directory:
                error = FileOperationError(
                    f"Path {path} is at the output directory level - no occurrence folder found",
                    user_message="Invalid folder structure - no occurrence folder found."
                )
                self._handle_error(error, {'method': 'find_occurrence_folder'})
                return Result.error(error)
            
            # Keep going up until we find the occurrence folder
            # (direct child of output_directory)
            while current_path != output_directory and current_path.parent != output_directory:
                if current_path.parent == current_path:
                    # Reached filesystem root without finding occurrence folder
                    error = FileOperationError(
                        f"Could not find occurrence folder from {path}",
                        user_message="Could not locate the occurrence folder in the directory structure."
                    )
                    self._handle_error(error, {'method': 'find_occurrence_folder'})
                    return Result.error(error)
                current_path = current_path.parent
            
            # current_path should now be the occurrence number folder
            self._log_operation("occurrence_folder_found", str(current_path))
            return Result.success(current_path)
            
        except Exception as e:
            error = FileOperationError(
                f"Failed to find occurrence folder: {e}",
                user_message="Failed to navigate to occurrence folder."
            )
            self._handle_error(error, {'method': 'find_occurrence_folder'})
            return Result.error(error)
    
    def navigate_to_occurrence_folder(
        self,
        current_path: Path,
        root_directory: Path
    ) -> Result[Path]:
        """
        Navigate to the occurrence folder from any path in the structure
        
        This is an alias for find_occurrence_folder for clearer API
        
        Args:
            current_path: Current path to navigate from
            root_directory: Root output directory
            
        Returns:
            Result containing the occurrence folder path
        """
        return self.find_occurrence_folder(current_path, root_directory)