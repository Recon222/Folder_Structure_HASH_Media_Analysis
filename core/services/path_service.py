#!/usr/bin/env python3
"""
Path service - centralized path building and validation
"""
from pathlib import Path
from typing import Optional

from .interfaces import IPathService
from .base_service import BaseService
from ..models import FormData
from ..result_types import Result
from ..exceptions import FileOperationError, ErrorSeverity
from ..path_utils import ForensicPathBuilder, PathSanitizer

class PathService(BaseService, IPathService):
    """Service for path building and validation operations"""
    
    def __init__(self):
        super().__init__("PathService")
        self._path_sanitizer = PathSanitizer()
    
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
            
            # Build forensic structure using existing builder
            try:
                forensic_path = ForensicPathBuilder.create_forensic_structure(base_path, form_data)
                self._log_operation("forensic_path_built", str(forensic_path))
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