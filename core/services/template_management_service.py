#!/usr/bin/env python3
"""
Template management service for import/export operations and user template handling
"""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from .base_service import BaseService
from ..result_types import Result
from ..exceptions import TemplateValidationError, FileOperationError, ErrorSeverity
from ..template_validator import TemplateValidator, ValidationLevel
from ..models import FormData


class TemplateSource:
    """Represents different template sources"""
    SYSTEM = "system"        # Built-in templates
    USER = "user"           # User-imported templates
    IMPORTED = "imported"   # Recently imported templates
    CUSTOM = "custom"       # User-created templates


class TemplateInfo:
    """Information about a template"""
    
    def __init__(self, template_id: str, template_data: Dict[str, Any], 
                 source: str, file_path: Optional[Path] = None):
        self.template_id = template_id
        self.template_data = template_data
        self.source = source
        self.file_path = file_path
        
        # Extract metadata
        self.name = template_data.get("templateName", template_id)
        self.description = template_data.get("templateDescription", "")
        self.metadata = template_data.get("metadata", {})
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "file_path": str(self.file_path) if self.file_path else None,
            "metadata": self.metadata,
            "template_data": self.template_data
        }


class TemplateManagementService(BaseService):
    """Service for managing template import, export, and storage operations"""
    
    def __init__(self):
        super().__init__("TemplateManagementService")
        self.validator = TemplateValidator()
        self._setup_directories()
        
    def _setup_directories(self):
        """Setup user template directories"""
        try:
            # Get user data directory (platform-specific)
            self.user_templates_dir = self._get_user_data_directory()
            self.imported_dir = self.user_templates_dir / "imported"
            self.custom_dir = self.user_templates_dir / "custom"
            self.backups_dir = self.user_templates_dir / "backups"
            self.exported_dir = self.user_templates_dir / "exported"
            
            # Create directories if they don't exist
            for directory in [self.imported_dir, self.custom_dir, 
                            self.backups_dir, self.exported_dir]:
                directory.mkdir(parents=True, exist_ok=True)
                
            self._log_operation("directories_setup", 
                              f"User template directories created at {self.user_templates_dir}")
                              
            # Check for first-time initialization
            self._check_first_time_setup()
                              
        except Exception as e:
            self._log_operation("directory_setup_failed", str(e), "error")
            # Fallback to templates directory if user data directory creation fails
            self.user_templates_dir = Path("templates/user_templates")
            self.user_templates_dir.mkdir(parents=True, exist_ok=True)
            
            self.imported_dir = self.user_templates_dir / "imported"
            self.custom_dir = self.user_templates_dir / "custom"
            self.backups_dir = self.user_templates_dir / "backups"
            self.exported_dir = self.user_templates_dir / "exported"
            
            for directory in [self.imported_dir, self.custom_dir, 
                            self.backups_dir, self.exported_dir]:
                directory.mkdir(parents=True, exist_ok=True)
    
    def _get_user_data_directory(self) -> Path:
        """Get platform-specific user data directory"""
        import platform
        import os
        
        system = platform.system()
        
        if system == "Windows":
            # Use AppData/Local for Windows
            appdata = os.getenv("LOCALAPPDATA")
            if appdata:
                return Path(appdata) / "FolderStructureApp" / "templates"
        elif system == "Darwin":  # macOS
            # Use ~/Library/Application Support
            home = Path.home()
            return home / "Library" / "Application Support" / "FolderStructureApp" / "templates"
        else:  # Linux and others
            # Use ~/.local/share
            home = Path.home()
            return home / ".local" / "share" / "FolderStructureApp" / "templates"
        
        # Fallback to current directory
        return Path("templates/user_templates")
    
    def _check_first_time_setup(self):
        """Check if this is first time setup and log sample template availability"""
        try:
            # Check if any user templates exist
            has_user_templates = False
            for directory in [self.imported_dir, self.custom_dir]:
                if directory.exists() and list(directory.glob("*.json")):
                    has_user_templates = True
                    break
            
            if not has_user_templates:
                # First time setup - log information about sample templates
                samples_dir = Path("templates/samples")
                if samples_dir.exists():
                    sample_files = list(samples_dir.glob("*.json"))
                    if sample_files:
                        self._log_operation("first_time_setup", 
                                          f"First-time initialization: {len(sample_files)} sample templates available for import")
                    else:
                        self._log_operation("first_time_setup", "First-time initialization: No sample templates found")
                else:
                    self._log_operation("first_time_setup", "First-time initialization: Sample templates directory not found")
            
        except Exception as e:
            self._log_operation("first_time_setup_check_failed", str(e), "warning")
    
    def import_template(self, file_path: Path, target_source: str = TemplateSource.IMPORTED) -> Result[Dict[str, Any]]:
        """Import template from JSON file with comprehensive validation"""
        try:
            self._log_operation("import_template_start", f"Importing from {file_path}")
            
            # Validate file path
            if not file_path.exists():
                error = TemplateValidationError(
                    f"Template file not found: {file_path}",
                    user_message="The selected template file could not be found."
                )
                return Result.error(error)
            
            # Step 1: Validate template file
            validation_result = self.validator.validate_template_file(file_path)
            if not validation_result.success:
                return Result.error(validation_result.error)
            
            validation_issues = validation_result.value
            
            # Check for blocking errors
            blocking_errors = [issue for issue in validation_issues 
                             if issue.level == ValidationLevel.ERROR]
            if blocking_errors:
                error = TemplateValidationError(
                    f"Template validation failed with {len(blocking_errors)} error(s)",
                    validation_issues=validation_issues,
                    user_message="Template contains validation errors and cannot be imported."
                )
                return Result.error(error)
            
            # Load template data
            with open(file_path, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
            
            # Step 2: Handle template conflicts and installation
            installation_result = self._install_templates(template_data, target_source, file_path.name)
            if not installation_result.success:
                return installation_result
            
            installed_templates = installation_result.value
            
            # Step 3: Create backup before installation
            backup_result = self._create_backup()
            if not backup_result.success:
                self._log_operation("backup_failed", str(backup_result.error), "warning")
                # Continue with import even if backup fails
            
            result = {
                "imported_templates": installed_templates,
                "validation_issues": [issue.to_dict() for issue in validation_issues],
                "source_file": str(file_path),
                "target_source": target_source,
                "backup_created": backup_result.success,
                "import_timestamp": datetime.now().isoformat()
            }
            
            self._log_operation("import_template_success", 
                              f"Imported {len(installed_templates)} templates from {file_path}")
            
            return Result.success(result)
            
        except Exception as e:
            error = TemplateValidationError(
                f"Template import failed: {e}",
                user_message="An unexpected error occurred during template import."
            )
            self._handle_error(error, {'method': 'import_template', 'file_path': str(file_path)})
            return Result.error(error)
    
    def _install_templates(self, template_data: Dict[str, Any], target_source: str, 
                          source_filename: str) -> Result[List[str]]:
        """Install templates to target location with conflict resolution"""
        try:
            templates = template_data.get("templates", {})
            installed_template_ids = []
            
            # Determine target directory
            if target_source == TemplateSource.IMPORTED:
                target_dir = self.imported_dir
            elif target_source == TemplateSource.CUSTOM:
                target_dir = self.custom_dir
            else:
                error = TemplateValidationError(
                    f"Invalid target source: {target_source}",
                    user_message="Invalid installation target specified."
                )
                return Result.error(error)
            
            # Check for conflicts
            conflicts = self._check_template_conflicts(list(templates.keys()))
            if conflicts:
                # For now, we'll rename conflicting templates by adding a suffix
                # In the UI, we could prompt the user for resolution
                templates = self._resolve_template_conflicts(templates, conflicts)
            
            # Create individual template files
            for template_id, template_info in templates.items():
                try:
                    # Create individual template file
                    template_file_data = {
                        "version": template_data.get("version", "1.0.0"),
                        "templates": {
                            template_id: template_info
                        }
                    }
                    
                    # Add metadata
                    if "metadata" not in template_info:
                        template_info["metadata"] = {}
                    
                    template_info["metadata"].update({
                        "imported_from": source_filename,
                        "imported_date": datetime.now().isoformat(),
                        "source": target_source
                    })
                    
                    # Write template file
                    template_file = target_dir / f"{template_id}.json"
                    with open(template_file, 'w', encoding='utf-8') as f:
                        json.dump(template_file_data, f, indent=2, ensure_ascii=False)
                    
                    installed_template_ids.append(template_id)
                    self._log_operation("template_installed", f"Template {template_id} installed to {template_file}")
                    
                except Exception as e:
                    self._log_operation("template_install_failed", 
                                      f"Failed to install template {template_id}: {e}", "warning")
                    continue
            
            if not installed_template_ids:
                error = TemplateValidationError(
                    "No templates were successfully installed",
                    user_message="Template import failed - no templates could be installed."
                )
                return Result.error(error)
            
            return Result.success(installed_template_ids)
            
        except Exception as e:
            error = TemplateValidationError(
                f"Template installation failed: {e}",
                user_message="Failed to install templates to the system."
            )
            return Result.error(error)
    
    def _check_template_conflicts(self, template_ids: List[str]) -> Dict[str, str]:
        """Check for existing templates with the same IDs"""
        conflicts = {}
        
        # Check system templates
        system_templates_file = Path("templates/folder_templates.json")
        if system_templates_file.exists():
            try:
                with open(system_templates_file, 'r') as f:
                    system_data = json.load(f)
                    system_template_ids = set(system_data.get("templates", {}).keys())
                    
                for template_id in template_ids:
                    if template_id in system_template_ids:
                        conflicts[template_id] = TemplateSource.SYSTEM
            except Exception:
                pass  # Ignore errors reading system templates
        
        # Check user templates
        for directory in [self.imported_dir, self.custom_dir]:
            if directory.exists():
                for template_file in directory.glob("*.json"):
                    template_id = template_file.stem
                    if template_id in template_ids:
                        conflicts[template_id] = TemplateSource.USER
        
        return conflicts
    
    def _resolve_template_conflicts(self, templates: Dict[str, Any], 
                                  conflicts: Dict[str, str]) -> Dict[str, Any]:
        """Resolve template ID conflicts by renaming"""
        resolved_templates = {}
        
        for template_id, template_info in templates.items():
            if template_id in conflicts:
                # Create new ID with timestamp suffix
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_id = f"{template_id}_imported_{timestamp}"
                
                # Update template name to reflect the change
                if "templateName" in template_info:
                    template_info["templateName"] += f" (Imported {timestamp})"
                
                resolved_templates[new_id] = template_info
                self._log_operation("template_renamed", 
                                  f"Renamed conflicting template {template_id} to {new_id}")
            else:
                resolved_templates[template_id] = template_info
        
        return resolved_templates
    
    def export_template(self, template_id: str, output_path: Path, 
                       include_metadata: bool = True) -> Result[None]:
        """Export template to JSON file"""
        try:
            self._log_operation("export_template_start", f"Exporting {template_id} to {output_path}")
            
            # Find template
            template_info = self._find_template(template_id)
            if not template_info:
                error = TemplateValidationError(
                    f"Template {template_id} not found",
                    template_id=template_id,
                    user_message=f"Template '{template_id}' could not be found for export."
                )
                return Result.error(error)
            
            # Prepare export data
            export_data = {
                "version": "1.0.0",
                "templates": {
                    template_id: template_info.template_data.copy()
                }
            }
            
            # Add export metadata
            if include_metadata:
                if "metadata" not in export_data["templates"][template_id]:
                    export_data["templates"][template_id]["metadata"] = {}
                
                export_data["templates"][template_id]["metadata"].update({
                    "exported_date": datetime.now().isoformat(),
                    "exported_by": "FolderStructureApp",
                    "original_source": template_info.source
                })
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write export file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self._log_operation("export_template_success", f"Exported {template_id} to {output_path}")
            return Result.success(None)
            
        except Exception as e:
            error = TemplateValidationError(
                f"Template export failed: {e}",
                template_id=template_id,
                user_message=f"Failed to export template '{template_id}'."
            )
            self._handle_error(error, {'method': 'export_template', 'template_id': template_id})
            return Result.error(error)
    
    def export_all_user_templates(self, output_path: Path) -> Result[Dict[str, Any]]:
        """Export all user templates to a single JSON file"""
        try:
            self._log_operation("export_all_start", f"Exporting all user templates to {output_path}")
            
            all_templates = {}
            exported_count = 0
            
            # Collect templates from user directories
            for directory in [self.imported_dir, self.custom_dir]:
                if directory.exists():
                    for template_file in directory.glob("*.json"):
                        try:
                            with open(template_file, 'r', encoding='utf-8') as f:
                                template_data = json.load(f)
                                
                            templates = template_data.get("templates", {})
                            for template_id, template_info in templates.items():
                                all_templates[template_id] = template_info
                                exported_count += 1
                                
                        except Exception as e:
                            self._log_operation("export_template_skipped", 
                                              f"Skipped {template_file}: {e}", "warning")
            
            if not all_templates:
                error = TemplateValidationError(
                    "No user templates found to export",
                    user_message="No user templates available for export."
                )
                return Result.error(error)
            
            # Create export data
            export_data = {
                "version": "1.0.0",
                "templates": all_templates,
                "export_metadata": {
                    "export_date": datetime.now().isoformat(),
                    "exported_by": "FolderStructureApp",
                    "template_count": exported_count,
                    "export_type": "user_templates_backup"
                }
            }
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write export file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            result = {
                "exported_count": exported_count,
                "export_file": str(output_path),
                "export_timestamp": datetime.now().isoformat()
            }
            
            self._log_operation("export_all_success", 
                              f"Exported {exported_count} templates to {output_path}")
            return Result.success(result)
            
        except Exception as e:
            error = TemplateValidationError(
                f"Bulk template export failed: {e}",
                user_message="Failed to export user templates."
            )
            self._handle_error(error, {'method': 'export_all_user_templates'})
            return Result.error(error)
    
    def delete_user_template(self, template_id: str) -> Result[None]:
        """Delete a user template"""
        try:
            self._log_operation("delete_template_start", f"Deleting template {template_id}")
            
            # Find template file
            template_file = None
            for directory in [self.imported_dir, self.custom_dir]:
                potential_file = directory / f"{template_id}.json"
                if potential_file.exists():
                    template_file = potential_file
                    break
            
            if not template_file:
                error = TemplateValidationError(
                    f"User template {template_id} not found",
                    template_id=template_id,
                    user_message=f"Template '{template_id}' could not be found for deletion."
                )
                return Result.error(error)
            
            # Create backup before deletion
            backup_result = self._create_backup()
            if not backup_result.success:
                self._log_operation("delete_backup_failed", str(backup_result.error), "warning")
            
            # Delete template file
            template_file.unlink()
            
            self._log_operation("delete_template_success", f"Deleted template {template_id}")
            return Result.success(None)
            
        except Exception as e:
            error = TemplateValidationError(
                f"Template deletion failed: {e}",
                template_id=template_id,
                user_message=f"Failed to delete template '{template_id}'."
            )
            self._handle_error(error, {'method': 'delete_user_template', 'template_id': template_id})
            return Result.error(error)
    
    def get_all_templates(self) -> Result[List[TemplateInfo]]:
        """Get all templates from all sources"""
        try:
            all_templates = []
            
            # Load system templates
            system_templates = self._load_system_templates()
            all_templates.extend(system_templates)
            
            # Load user templates
            user_templates = self._load_user_templates()
            all_templates.extend(user_templates)
            
            return Result.success(all_templates)
            
        except Exception as e:
            error = TemplateValidationError(
                f"Failed to load templates: {e}",
                user_message="Failed to load template library."
            )
            return Result.error(error)
    
    def _load_system_templates(self) -> List[TemplateInfo]:
        """Load system templates from folder_templates.json"""
        templates = []
        system_file = Path("templates/folder_templates.json")
        
        if system_file.exists():
            try:
                with open(system_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for template_id, template_data in data.get("templates", {}).items():
                    templates.append(TemplateInfo(
                        template_id=template_id,
                        template_data=template_data,
                        source=TemplateSource.SYSTEM,
                        file_path=system_file
                    ))
            except Exception as e:
                self._log_operation("system_templates_load_failed", str(e), "warning")
        
        return templates
    
    def _load_user_templates(self) -> List[TemplateInfo]:
        """Load user templates from user directories"""
        templates = []
        
        for directory in [self.imported_dir, self.custom_dir]:
            if not directory.exists():
                continue
                
            source = (TemplateSource.IMPORTED if directory == self.imported_dir 
                     else TemplateSource.CUSTOM)
            
            for template_file in directory.glob("*.json"):
                try:
                    with open(template_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    for template_id, template_data in data.get("templates", {}).items():
                        templates.append(TemplateInfo(
                            template_id=template_id,
                            template_data=template_data,
                            source=source,
                            file_path=template_file
                        ))
                except Exception as e:
                    self._log_operation("user_template_load_failed", 
                                      f"Failed to load {template_file}: {e}", "warning")
        
        return templates
    
    def _find_template(self, template_id: str) -> Optional[TemplateInfo]:
        """Find template by ID"""
        templates_result = self.get_all_templates()
        if not templates_result.success:
            return None
        
        for template_info in templates_result.value:
            if template_info.template_id == template_id:
                return template_info
        
        return None
    
    def _create_backup(self) -> Result[Path]:
        """Create backup of current user templates"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backups_dir / f"templates_backup_{timestamp}.json"
            
            # Export all user templates to backup
            export_result = self.export_all_user_templates(backup_file)
            if export_result.success:
                # Keep only last 10 backups
                self._cleanup_old_backups()
                return Result.success(backup_file)
            else:
                return Result.error(export_result.error)
                
        except Exception as e:
            error = FileOperationError(
                f"Backup creation failed: {e}",
                user_message="Failed to create backup of templates."
            )
            return Result.error(error)
    
    def _cleanup_old_backups(self):
        """Keep only the 10 most recent backups"""
        try:
            if not self.backups_dir.exists():
                return
            
            backup_files = list(self.backups_dir.glob("templates_backup_*.json"))
            backup_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            # Remove old backups (keep 10 most recent)
            for old_backup in backup_files[10:]:
                try:
                    old_backup.unlink()
                    self._log_operation("old_backup_deleted", f"Deleted old backup {old_backup}")
                except Exception as e:
                    self._log_operation("backup_cleanup_failed", f"Failed to delete {old_backup}: {e}", "warning")
                    
        except Exception as e:
            self._log_operation("backup_cleanup_error", str(e), "warning")
    
    def validate_template_preview(self, template_data: Dict[str, Any], 
                                sample_data: Optional[Dict[str, Any]] = None) -> Result[Dict[str, Any]]:
        """Validate template and generate preview"""
        try:
            # Validate template structure
            validation_result = self.validator.validate_template_data(template_data)
            if not validation_result.success:
                return Result.error(validation_result.error)
            
            validation_issues = validation_result.value
            
            # Generate preview with sample data
            preview_result = self.validator.test_template_with_sample_data(template_data, sample_data)
            if not preview_result.success:
                return Result.error(preview_result.error)
            
            preview_data = preview_result.value
            
            result = {
                "validation_issues": [issue.to_dict() for issue in validation_issues],
                "preview_data": preview_data,
                "has_errors": any(issue.level == ValidationLevel.ERROR for issue in validation_issues),
                "has_warnings": any(issue.level == ValidationLevel.WARNING for issue in validation_issues)
            }
            
            return Result.success(result)
            
        except Exception as e:
            error = TemplateValidationError(
                f"Template preview generation failed: {e}",
                user_message="Failed to generate template preview."
            )
            return Result.error(error)