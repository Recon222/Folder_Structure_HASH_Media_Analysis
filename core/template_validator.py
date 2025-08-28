#!/usr/bin/env python3
"""
Comprehensive template validation engine with multi-level validation
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

from .template_schema import (
    TEMPLATE_SCHEMA, AVAILABLE_FIELDS, UNSAFE_PATTERNS, COMPLEXITY_LIMITS
)
from .result_types import Result
from .exceptions import TemplateValidationError, ErrorSeverity
from .path_utils import PathSanitizer

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


class ValidationLevel:
    """Validation severity levels"""
    ERROR = "error"      # Blocks import
    WARNING = "warning"  # Allows import with user confirmation
    INFO = "info"        # Informational only
    SUCCESS = "success"  # Validation passed


class ValidationIssue:
    """Represents a validation issue"""
    
    def __init__(self, level: str, message: str, path: str = "", 
                 suggestion: str = "", field: str = ""):
        self.level = level
        self.message = message
        self.path = path  # JSON path to the issue
        self.suggestion = suggestion
        self.field = field
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "level": self.level,
            "message": self.message,
            "path": self.path,
            "suggestion": self.suggestion,
            "field": self.field
        }
        
    def __str__(self) -> str:
        """String representation"""
        return f"[{self.level.upper()}] {self.message}"


class TemplateValidator:
    """Comprehensive template validation engine"""
    
    def __init__(self):
        self.path_sanitizer = PathSanitizer()
        
    def validate_template_file(self, file_path: Path) -> Result[List[ValidationIssue]]:
        """Validate template file from disk"""
        try:
            # File existence and accessibility
            if not file_path.exists():
                error = TemplateValidationError(
                    f"Template file not found: {file_path}",
                    user_message="The selected template file could not be found."
                )
                return Result.error(error)
                
            if not file_path.is_file():
                error = TemplateValidationError(
                    f"Path is not a file: {file_path}",
                    user_message="The selected path is not a file."
                )
                return Result.error(error)
                
            # File size check
            file_size = file_path.stat().st_size
            if file_size > COMPLEXITY_LIMITS["max_template_size"]:
                error = TemplateValidationError(
                    f"Template file too large: {file_size} bytes (max: {COMPLEXITY_LIMITS['max_template_size']})",
                    user_message="Template file is too large. Maximum size is 1MB."
                )
                return Result.error(error)
                
            # Load and parse JSON
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    template_data = json.load(f)
            except json.JSONDecodeError as e:
                error = TemplateValidationError(
                    f"Invalid JSON in template file: {e}",
                    user_message=f"Template file contains invalid JSON: {e.msg} at line {e.lineno}"
                )
                return Result.error(error)
            except UnicodeDecodeError as e:
                error = TemplateValidationError(
                    f"Template file encoding error: {e}",
                    user_message="Template file must be saved as UTF-8 text."
                )
                return Result.error(error)
                
            # Validate template data
            return self.validate_template_data(template_data)
            
        except Exception as e:
            error = TemplateValidationError(
                f"Unexpected error validating template file: {e}",
                user_message="An unexpected error occurred while validating the template file."
            )
            return Result.error(error)
    
    def validate_template_data(self, template_data: Dict[str, Any]) -> Result[List[ValidationIssue]]:
        """Validate template data structure"""
        issues = []
        
        try:
            # Level 1: JSON Schema Validation
            schema_issues = self._validate_schema(template_data)
            issues.extend(schema_issues)
            
            # If schema validation fails completely, stop here
            if any(issue.level == ValidationLevel.ERROR for issue in schema_issues):
                return Result.success(issues)
            
            # Level 2: Security Validation
            security_issues = self._validate_security(template_data)
            issues.extend(security_issues)
            
            # Level 3: Business Logic Validation
            business_issues = self._validate_business_logic(template_data)
            issues.extend(business_issues)
            
            # Level 4: Performance Validation
            performance_issues = self._validate_performance(template_data)
            issues.extend(performance_issues)
            
            # Level 5: Field Reference Validation
            field_issues = self._validate_field_references(template_data)
            issues.extend(field_issues)
            
            # Level 6: Pattern Validation
            pattern_issues = self._validate_patterns(template_data)
            issues.extend(pattern_issues)
            
            # Add success message if no blocking issues
            if not any(issue.level == ValidationLevel.ERROR for issue in issues):
                issues.append(ValidationIssue(
                    ValidationLevel.SUCCESS,
                    f"Template validation completed successfully. Found {len(template_data.get('templates', {}))} template(s)."
                ))
            
            return Result.success(issues)
            
        except Exception as e:
            error = TemplateValidationError(
                f"Validation engine error: {e}",
                user_message="Internal validation error occurred."
            )
            return Result.error(error)
    
    def _validate_schema(self, template_data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate against JSON schema"""
        issues = []
        
        if not HAS_JSONSCHEMA:
            issues.append(ValidationIssue(
                ValidationLevel.WARNING,
                "JSON schema validation unavailable (jsonschema package not installed)",
                suggestion="Install jsonschema package for enhanced validation"
            ))
            return issues
            
        try:
            jsonschema.validate(template_data, TEMPLATE_SCHEMA)
            issues.append(ValidationIssue(
                ValidationLevel.SUCCESS,
                "JSON schema validation passed"
            ))
        except jsonschema.ValidationError as e:
            issues.append(ValidationIssue(
                ValidationLevel.ERROR,
                f"Schema validation failed: {e.message}",
                path=".".join(str(p) for p in e.absolute_path),
                suggestion="Check template structure against schema requirements"
            ))
        except jsonschema.SchemaError as e:
            issues.append(ValidationIssue(
                ValidationLevel.ERROR,
                f"Internal schema error: {e.message}",
                suggestion="Report this issue to the developers"
            ))
        
        return issues
    
    def _validate_security(self, template_data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate for security issues"""
        issues = []
        
        templates = template_data.get("templates", {})
        
        for template_id, template in templates.items():
            # Check template ID for safety
            if not re.match(r"^[a-zA-Z0-9_-]+$", template_id):
                issues.append(ValidationIssue(
                    ValidationLevel.ERROR,
                    f"Template ID '{template_id}' contains unsafe characters",
                    path=f"templates.{template_id}",
                    suggestion="Use only letters, numbers, underscores, and hyphens in template IDs"
                ))
            
            # Check patterns for unsafe content
            structure = template.get("structure", {})
            levels = structure.get("levels", [])
            
            for level_idx, level in enumerate(levels):
                pattern = level.get("pattern", "")
                path = f"templates.{template_id}.structure.levels[{level_idx}].pattern"
                
                # Check against unsafe patterns
                for unsafe_pattern in UNSAFE_PATTERNS:
                    if re.search(unsafe_pattern, pattern, re.IGNORECASE):
                        issues.append(ValidationIssue(
                            ValidationLevel.ERROR,
                            f"Pattern contains potentially unsafe content: {pattern}",
                            path=path,
                            suggestion="Remove path traversal sequences, control characters, and reserved names"
                        ))
                        break
                
                # Check fallback pattern if present
                fallback = level.get("fallback", "")
                if fallback:
                    for unsafe_pattern in UNSAFE_PATTERNS:
                        if re.search(unsafe_pattern, fallback, re.IGNORECASE):
                            issues.append(ValidationIssue(
                                ValidationLevel.WARNING,
                                f"Fallback pattern contains potentially unsafe content: {fallback}",
                                path=f"{path}_fallback",
                                suggestion="Use safe fallback patterns"
                            ))
                            break
                
                # Check conditional patterns
                conditionals = level.get("conditionals", {})
                for cond_name, cond_pattern in conditionals.items():
                    for unsafe_pattern in UNSAFE_PATTERNS:
                        if re.search(unsafe_pattern, cond_pattern, re.IGNORECASE):
                            issues.append(ValidationIssue(
                                ValidationLevel.WARNING,
                                f"Conditional pattern '{cond_name}' contains potentially unsafe content: {cond_pattern}",
                                path=f"{path}.conditionals.{cond_name}",
                                suggestion="Use safe conditional patterns"
                            ))
                            break
            
            # Check archive naming patterns
            archive_config = template.get("archiveNaming", {})
            if archive_config:
                for pattern_name, pattern_value in archive_config.items():
                    if pattern_value:
                        for unsafe_pattern in UNSAFE_PATTERNS:
                            if re.search(unsafe_pattern, pattern_value, re.IGNORECASE):
                                issues.append(ValidationIssue(
                                    ValidationLevel.WARNING,
                                    f"Archive {pattern_name} contains potentially unsafe content: {pattern_value}",
                                    path=f"templates.{template_id}.archiveNaming.{pattern_name}",
                                    suggestion="Use safe archive naming patterns"
                                ))
                                break
        
        if not any(issue.level == ValidationLevel.ERROR for issue in issues):
            issues.append(ValidationIssue(
                ValidationLevel.SUCCESS,
                "Security validation passed - no unsafe patterns detected"
            ))
        
        return issues
    
    def _validate_business_logic(self, template_data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate business logic and folder structure validity"""
        issues = []
        
        templates = template_data.get("templates", {})
        
        for template_id, template in templates.items():
            # Check for required template properties
            if not template.get("templateName"):
                issues.append(ValidationIssue(
                    ValidationLevel.ERROR,
                    f"Template '{template_id}' missing required templateName",
                    path=f"templates.{template_id}.templateName",
                    suggestion="Add a descriptive template name"
                ))
            
            structure = template.get("structure", {})
            levels = structure.get("levels", [])
            
            if not levels:
                issues.append(ValidationIssue(
                    ValidationLevel.ERROR,
                    f"Template '{template_id}' has no folder levels defined",
                    path=f"templates.{template_id}.structure.levels",
                    suggestion="Define at least one folder level"
                ))
                continue
            
            # Check level patterns
            for level_idx, level in enumerate(levels):
                pattern = level.get("pattern", "")
                path = f"templates.{template_id}.structure.levels[{level_idx}]"
                
                if not pattern.strip():
                    issues.append(ValidationIssue(
                        ValidationLevel.ERROR,
                        f"Level {level_idx + 1} has empty pattern",
                        path=f"{path}.pattern",
                        suggestion="Provide a valid pattern for each level"
                    ))
                
                # Check for circular references (pattern referencing itself)
                field_refs = re.findall(r'\{(\w+)\}', pattern)
                if template_id in field_refs:
                    issues.append(ValidationIssue(
                        ValidationLevel.ERROR,
                        f"Circular reference detected in pattern: {pattern}",
                        path=f"{path}.pattern",
                        suggestion="Remove self-referencing patterns"
                    ))
                
                # Check date format usage
                date_format = level.get("dateFormat")
                if date_format and date_format not in ["military", "iso"]:
                    issues.append(ValidationIssue(
                        ValidationLevel.ERROR,
                        f"Invalid dateFormat '{date_format}' (must be 'military' or 'iso')",
                        path=f"{path}.dateFormat",
                        suggestion="Use 'military' for DDMMMYY_HHMM or 'iso' for YYYY-MM-DD_HHMM"
                    ))
                
                # Check if date format is used appropriately
                has_datetime_fields = any(field in field_refs for field in 
                                        ["video_start_datetime", "video_end_datetime", "current_datetime"])
                if date_format and not has_datetime_fields:
                    issues.append(ValidationIssue(
                        ValidationLevel.WARNING,
                        f"Level {level_idx + 1} specifies dateFormat but has no datetime fields",
                        path=f"{path}.dateFormat",
                        suggestion="Remove dateFormat or add datetime field references"
                    ))
            
            # Check documents placement
            docs_placement = template.get("documentsPlacement", "location")
            if docs_placement not in ["occurrence", "location", "datetime"]:
                issues.append(ValidationIssue(
                    ValidationLevel.ERROR,
                    f"Invalid documentsPlacement '{docs_placement}'",
                    path=f"templates.{template_id}.documentsPlacement",
                    suggestion="Use 'occurrence', 'location', or 'datetime'"
                ))
            elif docs_placement == "datetime" and len(levels) < 3:
                issues.append(ValidationIssue(
                    ValidationLevel.WARNING,
                    "documentsPlacement is 'datetime' but template has fewer than 3 levels",
                    path=f"templates.{template_id}.documentsPlacement",
                    suggestion="Consider using 'location' or add more levels"
                ))
        
        if not any(issue.level == ValidationLevel.ERROR for issue in issues):
            issues.append(ValidationIssue(
                ValidationLevel.SUCCESS,
                "Business logic validation passed"
            ))
        
        return issues
    
    def _validate_performance(self, template_data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate for performance issues"""
        issues = []
        
        templates = template_data.get("templates", {})
        
        # Check template count
        template_count = len(templates)
        if template_count > COMPLEXITY_LIMITS["max_templates"]:
            issues.append(ValidationIssue(
                ValidationLevel.WARNING,
                f"Large number of templates ({template_count}) may impact performance",
                suggestion=f"Consider splitting into multiple files (max recommended: {COMPLEXITY_LIMITS['max_templates']})"
            ))
        
        for template_id, template in templates.items():
            structure = template.get("structure", {})
            levels = structure.get("levels", [])
            
            # Check level count
            if len(levels) > COMPLEXITY_LIMITS["max_levels"]:
                issues.append(ValidationIssue(
                    ValidationLevel.WARNING,
                    f"Template '{template_id}' has many levels ({len(levels)}) which may create deep folder structures",
                    path=f"templates.{template_id}.structure.levels",
                    suggestion=f"Consider reducing to {COMPLEXITY_LIMITS['max_levels']} levels or fewer"
                ))
            
            # Check pattern complexity
            for level_idx, level in enumerate(levels):
                pattern = level.get("pattern", "")
                
                # Check pattern length
                if len(pattern) > COMPLEXITY_LIMITS["max_pattern_length"]:
                    issues.append(ValidationIssue(
                        ValidationLevel.WARNING,
                        f"Very long pattern in level {level_idx + 1} may cause filesystem issues",
                        path=f"templates.{template_id}.structure.levels[{level_idx}].pattern",
                        suggestion="Consider shortening the pattern"
                    ))
                
                # Check field reference count
                field_refs = re.findall(r'\{(\w+)\}', pattern)
                if len(field_refs) > COMPLEXITY_LIMITS["max_field_references"]:
                    issues.append(ValidationIssue(
                        ValidationLevel.WARNING,
                        f"Level {level_idx + 1} has many field references ({len(field_refs)}) which may impact performance",
                        path=f"templates.{template_id}.structure.levels[{level_idx}].pattern",
                        suggestion="Consider simplifying the pattern"
                    ))
        
        issues.append(ValidationIssue(
            ValidationLevel.SUCCESS,
            "Performance validation completed"
        ))
        
        return issues
    
    def _validate_field_references(self, template_data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate field references in patterns"""
        issues = []
        
        templates = template_data.get("templates", {})
        available_field_names = set(AVAILABLE_FIELDS.keys())
        
        for template_id, template in templates.items():
            structure = template.get("structure", {})
            levels = structure.get("levels", [])
            
            for level_idx, level in enumerate(levels):
                patterns_to_check = [
                    ("pattern", level.get("pattern", "")),
                    ("fallback", level.get("fallback", ""))
                ]
                
                # Add conditional patterns
                conditionals = level.get("conditionals", {})
                for cond_name, cond_pattern in conditionals.items():
                    patterns_to_check.append((f"conditionals.{cond_name}", cond_pattern))
                
                for pattern_type, pattern in patterns_to_check:
                    if not pattern:
                        continue
                        
                    field_refs = re.findall(r'\{(\w+)\}', pattern)
                    path = f"templates.{template_id}.structure.levels[{level_idx}].{pattern_type}"
                    
                    for field_ref in field_refs:
                        if field_ref not in available_field_names:
                            issues.append(ValidationIssue(
                                ValidationLevel.ERROR,
                                f"Unknown field reference '{{{field_ref}}}' in {pattern_type}",
                                path=path,
                                field=field_ref,
                                suggestion=f"Available fields: {', '.join(sorted(available_field_names))}"
                            ))
                        
                        # Check for datetime field usage with appropriate format
                        if field_ref in ["video_start_datetime", "video_end_datetime", "current_datetime"]:
                            date_format = level.get("dateFormat")
                            if not date_format:
                                issues.append(ValidationIssue(
                                    ValidationLevel.WARNING,
                                    f"Datetime field '{field_ref}' used without dateFormat specification",
                                    path=path,
                                    field=field_ref,
                                    suggestion="Add dateFormat: 'military' or 'iso' to this level"
                                ))
            
            # Check archive naming patterns
            archive_config = template.get("archiveNaming", {})
            for pattern_name, pattern_value in archive_config.items():
                if not pattern_value:
                    continue
                    
                field_refs = re.findall(r'\{(\w+)\}', pattern_value)
                path = f"templates.{template_id}.archiveNaming.{pattern_name}"
                
                for field_ref in field_refs:
                    if field_ref not in available_field_names:
                        issues.append(ValidationIssue(
                            ValidationLevel.ERROR,
                            f"Unknown field reference '{{{field_ref}}}' in archive {pattern_name}",
                            path=path,
                            field=field_ref,
                            suggestion=f"Available fields: {', '.join(sorted(available_field_names))}"
                        ))
        
        if not any(issue.level == ValidationLevel.ERROR for issue in issues):
            issues.append(ValidationIssue(
                ValidationLevel.SUCCESS,
                "Field reference validation passed"
            ))
        
        return issues
    
    def _validate_patterns(self, template_data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate pattern syntax and semantics"""
        issues = []
        
        templates = template_data.get("templates", {})
        
        for template_id, template in templates.items():
            structure = template.get("structure", {})
            levels = structure.get("levels", [])
            
            for level_idx, level in enumerate(levels):
                pattern = level.get("pattern", "")
                path = f"templates.{template_id}.structure.levels[{level_idx}].pattern"
                
                # Check for balanced braces
                open_braces = pattern.count("{")
                close_braces = pattern.count("}")
                if open_braces != close_braces:
                    issues.append(ValidationIssue(
                        ValidationLevel.ERROR,
                        f"Unbalanced braces in pattern: {pattern}",
                        path=path,
                        suggestion="Ensure each {{ has a matching }}"
                    ))
                
                # Check for empty field references
                empty_refs = re.findall(r'\{\s*\}', pattern)
                if empty_refs:
                    issues.append(ValidationIssue(
                        ValidationLevel.ERROR,
                        f"Empty field references found in pattern: {pattern}",
                        path=path,
                        suggestion="Provide field names inside braces, e.g., {occurrence_number}"
                    ))
                
                # Check for nested braces
                if re.search(r'\{[^}]*\{', pattern):
                    issues.append(ValidationIssue(
                        ValidationLevel.ERROR,
                        f"Nested braces not allowed in pattern: {pattern}",
                        path=path,
                        suggestion="Use flat field references, e.g., {field_name}"
                    ))
                
                # Check for potential infinite loops in fallback
                fallback = level.get("fallback", "")
                if fallback and fallback == pattern:
                    issues.append(ValidationIssue(
                        ValidationLevel.ERROR,
                        f"Fallback pattern identical to main pattern (infinite loop risk): {pattern}",
                        path=f"{path}_fallback", 
                        suggestion="Use a different fallback pattern or remove fallback"
                    ))
        
        if not any(issue.level == ValidationLevel.ERROR for issue in issues):
            issues.append(ValidationIssue(
                ValidationLevel.SUCCESS,
                "Pattern validation passed"
            ))
        
        return issues
    
    def test_template_with_sample_data(self, template_data: Dict[str, Any], 
                                     sample_form_data: Optional[Dict[str, Any]] = None) -> Result[Dict[str, Any]]:
        """Test template with sample data to preview results"""
        try:
            from .models import FormData
            from .template_path_builder import TemplatePathBuilder
            from PySide6.QtCore import QDateTime
            
            # Create sample form data if not provided
            if sample_form_data is None:
                sample_form_data = {
                    "occurrence_number": "2024-TEST-001",
                    "business_name": "Sample Business",
                    "location_address": "123 Test Street",
                    "video_start_datetime": QDateTime(2025, 8, 28, 16, 30, 0),
                    "video_end_datetime": QDateTime(2025, 8, 28, 18, 15, 0),
                    "technician_name": "Test Technician",
                    "badge_number": "12345"
                }
            
            # Create FormData instance
            form_data = FormData()
            for field, value in sample_form_data.items():
                if hasattr(form_data, field):
                    setattr(form_data, field, value)
            
            results = {}
            templates = template_data.get("templates", {})
            
            for template_id, template in templates.items():
                try:
                    builder = TemplatePathBuilder(template, self.path_sanitizer)
                    
                    # Test path building
                    relative_path = builder.build_relative_path(form_data)
                    
                    # Test archive naming
                    archive_name = builder.build_archive_name(form_data)
                    
                    results[template_id] = {
                        "template_name": template.get("templateName", template_id),
                        "folder_path": str(relative_path),
                        "path_parts": relative_path.parts,
                        "archive_name": archive_name,
                        "documents_placement": template.get("documentsPlacement", "location"),
                        "success": True
                    }
                    
                except Exception as e:
                    results[template_id] = {
                        "template_name": template.get("templateName", template_id),
                        "error": str(e),
                        "success": False
                    }
            
            return Result.success(results)
            
        except Exception as e:
            error = TemplateValidationError(
                f"Template testing failed: {e}",
                user_message="Failed to test template with sample data."
            )
            return Result.error(error)
    
    def get_field_documentation(self) -> Dict[str, Any]:
        """Get documentation for available template fields"""
        return {
            "available_fields": AVAILABLE_FIELDS.copy(),
            "date_formats": {
                "military": {
                    "description": "Military date format",
                    "pattern": "DDMMMYY_HHMM",
                    "example": "28AUG25_1630"
                },
                "iso": {
                    "description": "ISO date format", 
                    "pattern": "YYYY-MM-DD_HHMM",
                    "example": "2025-08-28_1630"
                }
            },
            "conditional_patterns": {
                "business_only": "Used when only business name is available",
                "location_only": "Used when only location address is available",
                "neither": "Used when neither business nor location is available"
            },
            "documents_placement": {
                "occurrence": "Place documents in the first level (occurrence) folder",
                "location": "Place documents in the second level (location) folder", 
                "datetime": "Place documents in the deepest (datetime) folder"
            }
        }