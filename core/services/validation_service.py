#!/usr/bin/env python3
"""
Validation service - handles form and data validation
"""
from pathlib import Path
from typing import List, Dict, Any

from .interfaces import IValidationService
from .base_service import BaseService
from ..models import FormData
from ..result_types import Result
from ..exceptions import ValidationError

class ValidationService(BaseService, IValidationService):
    """Service for validation operations"""
    
    def __init__(self):
        super().__init__("ValidationService")
    
    def validate_form_data(self, form_data: FormData) -> Result[None]:
        """Validate form data completeness"""
        try:
            self._log_operation("validate_form_data")
            
            if not form_data:
                error = ValidationError(
                    {"form_data": "Form data object is required"},
                    user_message="Form data is missing."
                )
                self._handle_error(error, {'method': 'validate_form_data'})
                return Result.error(error)
            
            field_errors = {}
            
            # Required field validation
            if not form_data.occurrence_number or not form_data.occurrence_number.strip():
                field_errors['occurrence_number'] = 'Occurrence number is required'
            
            # Business name OR location address is required
            has_business = form_data.business_name and form_data.business_name.strip()
            has_location = form_data.location_address and form_data.location_address.strip()
            
            if not has_business and not has_location:
                field_errors['location'] = 'Either business name or location address is required'
            
            # Date validation
            if hasattr(form_data, 'video_start_datetime') and form_data.video_start_datetime:
                if hasattr(form_data, 'video_end_datetime') and form_data.video_end_datetime:
                    try:
                        if form_data.video_end_datetime < form_data.video_start_datetime:
                            field_errors['video_dates'] = 'Video end date must be after start date'
                    except (TypeError, AttributeError) as e:
                        self.logger.warning(f"Date comparison failed: {e}")
                        # Don't fail validation for date comparison issues
            
            # Occurrence number format validation (basic)
            if form_data.occurrence_number and form_data.occurrence_number.strip():
                occ_num = form_data.occurrence_number.strip()
                if len(occ_num) < 2:
                    field_errors['occurrence_number'] = 'Occurrence number must be at least 2 characters'
                elif any(char in occ_num for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']):
                    field_errors['occurrence_number'] = 'Occurrence number contains invalid characters'
            
            # Time offset validation
            if hasattr(form_data, 'time_offset') and form_data.time_offset is not None:
                try:
                    # Handle both string and numeric time offsets
                    if isinstance(form_data.time_offset, str):
                        # String format is allowed (e.g., "DVR is 2 hr 0 min 0 sec AHEAD of realtime")
                        pass
                    elif isinstance(form_data.time_offset, (int, float)):
                        # Numeric format should be reasonable (within 24 hours = 1440 minutes)
                        if abs(form_data.time_offset) > 1440:
                            field_errors['time_offset'] = 'Time offset seems unreasonably large (>24 hours)'
                    else:
                        field_errors['time_offset'] = 'Time offset must be a number or descriptive text'
                except (ValueError, TypeError):
                    field_errors['time_offset'] = 'Invalid time offset format'
            
            if field_errors:
                error = ValidationError(
                    field_errors,
                    user_message="Please correct the following form validation errors."
                )
                self._handle_error(error, {'method': 'validate_form_data', 'errors': field_errors})
                return Result.error(error)
            
            self._log_operation("form_data_valid")
            return Result.success(None)
            
        except Exception as e:
            error = ValidationError(
                {"general": f"Validation process failed: {e}"},
                user_message="Form validation encountered an error."
            )
            self._handle_error(error, {'method': 'validate_form_data'})
            return Result.error(error)
    
    def validate_file_paths(self, paths: List[Path]) -> Result[List[Path]]:
        """Validate file paths exist and are accessible"""
        try:
            self._log_operation("validate_file_paths", f"{len(paths)} paths")
            
            if not paths:
                error = ValidationError(
                    {"paths": "No file paths provided for validation"},
                    user_message="No files or folders selected."
                )
                self._handle_error(error, {'method': 'validate_file_paths'})
                return Result.error(error)
            
            valid_paths = []
            invalid_paths = []
            
            for path in paths:
                try:
                    if not isinstance(path, Path):
                        path = Path(path)
                    
                    if path.exists():
                        # Check if readable
                        try:
                            if path.is_file():
                                # Try to read file info
                                path.stat()
                            elif path.is_dir():
                                # Try to list directory
                                list(path.iterdir())
                            valid_paths.append(path)
                        except (PermissionError, OSError) as e:
                            self.logger.warning(f"Path exists but not accessible: {path} - {e}")
                            invalid_paths.append(str(path))
                    else:
                        self.logger.warning(f"Path does not exist: {path}")
                        invalid_paths.append(str(path))
                        
                except Exception as e:
                    self.logger.warning(f"Error validating path {path}: {e}")
                    invalid_paths.append(str(path))
            
            if not valid_paths:
                error = ValidationError(
                    {"files": "No valid files or folders found"},
                    user_message="No valid files or folders found. Please check file paths and permissions."
                )
                self._handle_error(error, {'method': 'validate_file_paths', 'invalid_paths': invalid_paths})
                return Result.error(error)
            
            if invalid_paths:
                self._log_operation("some_paths_invalid", 
                                  f"valid: {len(valid_paths)}, invalid: {len(invalid_paths)}", 
                                  "warning")
            
            self._log_operation("file_paths_validated", f"{len(valid_paths)} valid paths")
            return Result.success(valid_paths)
            
        except Exception as e:
            error = ValidationError(
                {"files": f"File validation failed: {e}"},
                user_message="File validation encountered an error."
            )
            self._handle_error(error, {'method': 'validate_file_paths'})
            return Result.error(error)
    
    def validate_output_directory(self, output_path: Path) -> Result[Path]:
        """Validate output directory is writable"""
        try:
            self._log_operation("validate_output_directory", str(output_path))
            
            if not output_path:
                error = ValidationError(
                    {"output_path": "Output directory is required"},
                    user_message="Output directory is required."
                )
                self._handle_error(error, {'method': 'validate_output_directory'})
                return Result.error(error)
            
            if not isinstance(output_path, Path):
                output_path = Path(output_path)
            
            # Try to create directory if it doesn't exist
            if not output_path.exists():
                try:
                    output_path.mkdir(parents=True, exist_ok=True)
                    self._log_operation("output_directory_created", str(output_path))
                except Exception as e:
                    error = ValidationError(
                        {"output_path": f"Cannot create output directory: {e}"},
                        user_message="Cannot create output directory. Please check permissions."
                    )
                    self._handle_error(error, {'method': 'validate_output_directory'})
                    return Result.error(error)
            
            # Test if directory is writable
            test_file = output_path / '.write_test'
            try:
                test_file.write_text("test")
                test_file.unlink()  # Clean up test file
                self._log_operation("output_directory_writable", str(output_path))
            except Exception as e:
                error = ValidationError(
                    {"output_path": f"Output directory is not writable: {e}"},
                    user_message="Output directory is not writable. Please check permissions."
                )
                self._handle_error(error, {'method': 'validate_output_directory'})
                return Result.error(error)
            
            return Result.success(output_path)
            
        except Exception as e:
            error = ValidationError(
                {"output_path": f"Output directory validation failed: {e}"},
                user_message="Output directory validation encountered an error."
            )
            self._handle_error(error, {'method': 'validate_output_directory'})
            return Result.error(error)