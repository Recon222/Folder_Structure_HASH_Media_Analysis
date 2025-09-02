#!/usr/bin/env python3
"""
JSON schema definitions for template validation
"""

from typing import Dict, Any

# Template JSON Schema Definition
TEMPLATE_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Folder Structure Template Schema",
    "description": "Schema for validating folder structure templates",
    "type": "object",
    "required": ["version", "templates"],
    "properties": {
        "version": {
            "type": "string",
            "pattern": r"^\d+\.\d+\.\d+$",
            "description": "Template schema version (semantic versioning)"
        },
        "templates": {
            "type": "object",
            "description": "Collection of templates indexed by template ID",
            "patternProperties": {
                r"^[a-zA-Z0-9_-]{1,50}$": {
                    "$ref": "#/definitions/template"
                }
            },
            "additionalProperties": False,
            "minProperties": 1,
            "maxProperties": 100
        }
    },
    "additionalProperties": False,
    "definitions": {
        "template": {
            "type": "object",
            "description": "Individual template definition",
            "required": ["templateName", "structure"],
            "properties": {
                "templateName": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 100,
                    "description": "Human-readable template name"
                },
                "templateDescription": {
                    "type": "string",
                    "maxLength": 500,
                    "description": "Optional template description"
                },
                "structure": {
                    "$ref": "#/definitions/structure"
                },
                "documentsPlacement": {
                    "oneOf": [
                        {"type": "integer", "minimum": 0, "maximum": 9},
                        {"type": "string", "enum": ["occurrence", "location", "datetime"]}
                    ],
                    "default": 1,
                    "description": "Level index (0-based) for documents placement, or legacy string for backward compatibility"
                },
                "archiveNaming": {
                    "$ref": "#/definitions/archiveNaming"
                },
                "metadata": {
                    "$ref": "#/definitions/metadata"
                }
            },
            "additionalProperties": False
        },
        "structure": {
            "type": "object",
            "description": "Folder structure definition",
            "required": ["levels"],
            "properties": {
                "levels": {
                    "type": "array",
                    "description": "Hierarchical levels of the folder structure",
                    "items": {
                        "$ref": "#/definitions/level"
                    },
                    "minItems": 1,
                    "maxItems": 10
                }
            },
            "additionalProperties": False
        },
        "level": {
            "type": "object",
            "description": "Single folder level definition",
            "required": ["pattern"],
            "properties": {
                "name": {
                    "type": "string",
                    "maxLength": 50,
                    "description": "Optional display name for this level (e.g., 'Case', 'Location', 'Timeline')"
                },
                "pattern": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 200,
                    "description": "Folder name pattern with field placeholders"
                },
                "fallback": {
                    "type": "string",
                    "maxLength": 100,
                    "description": "Fallback pattern when main pattern fails"
                },
                "conditionals": {
                    "$ref": "#/definitions/conditionals"
                },
                "dateFormat": {
                    "type": "string",
                    "enum": ["military", "iso"],
                    "description": "Date formatting style for datetime fields"
                },
                "prefix": {
                    "type": "string",
                    "maxLength": 50,
                    "description": "Prefix to add before pattern"
                },
                "suffix": {
                    "type": "string",
                    "maxLength": 50,
                    "description": "Suffix to add after pattern"
                }
            },
            "additionalProperties": False
        },
        "conditionals": {
            "type": "object",
            "description": "Conditional patterns for missing data scenarios",
            "properties": {
                "business_only": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Pattern when only business name is available"
                },
                "location_only": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Pattern when only location is available"
                },
                "neither": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Pattern when neither business nor location is available"
                }
            },
            "additionalProperties": False
        },
        "archiveNaming": {
            "type": "object",
            "description": "ZIP archive naming configuration",
            "required": ["pattern"],
            "properties": {
                "pattern": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 200,
                    "description": "Primary archive naming pattern"
                },
                "fallbackPattern": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Fallback archive naming pattern"
                }
            },
            "additionalProperties": False
        },
        "metadata": {
            "type": "object",
            "description": "Template metadata for management",
            "properties": {
                "author": {
                    "type": "string",
                    "maxLength": 100,
                    "description": "Template author"
                },
                "agency": {
                    "type": "string",
                    "maxLength": 100,
                    "description": "Agency this template is designed for"
                },
                "version": {
                    "type": "string",
                    "pattern": r"^\d+\.\d+\.\d+$",
                    "description": "Template version"
                },
                "created": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Template creation timestamp"
                },
                "modified": {
                    "type": "string", 
                    "format": "date-time",
                    "description": "Template last modified timestamp"
                },
                "tags": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "maxLength": 50
                    },
                    "maxItems": 20,
                    "description": "Template tags for organization"
                },
                "exported_date": {
                    "type": "string",
                    "format": "date-time",
                    "description": "When the template was exported"
                },
                "exported_by": {
                    "type": "string",
                    "maxLength": 100,
                    "description": "Application that exported the template"
                },
                "original_source": {
                    "type": "string",
                    "maxLength": 50,
                    "description": "Original source of the template (system/user/imported)"
                },
                "imported_from": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Path or source where template was imported from"
                },
                "imported_date": {
                    "type": "string",
                    "format": "date-time",
                    "description": "When the template was imported"
                },
                "notes": {
                    "type": "string",
                    "maxLength": 1000,
                    "description": "Additional notes or usage instructions for the template"
                }
            },
            "additionalProperties": False
        }
    }
}

# Available form fields that can be used in templates
AVAILABLE_FIELDS = {
    # Core form fields
    "occurrence_number": {
        "description": "Case/occurrence number",
        "type": "string",
        "example": "2024-001"
    },
    "business_name": {
        "description": "Business/establishment name", 
        "type": "string",
        "example": "Corner Store"
    },
    "location_address": {
        "description": "Address/location",
        "type": "string", 
        "example": "123 Main Street"
    },
    "video_start_datetime": {
        "description": "Video start time",
        "type": "datetime",
        "example": "2025-07-30 16:30:00"
    },
    "video_end_datetime": {
        "description": "Video end time",
        "type": "datetime",
        "example": "2025-07-30 18:00:00"
    },
    "technician_name": {
        "description": "Technician name (from settings)",
        "type": "string",
        "example": "John Smith"
    },
    "badge_number": {
        "description": "Badge number (from settings)",
        "type": "string", 
        "example": "12345"
    },
    
    # Special computed fields
    "current_datetime": {
        "description": "Current date/time when processing",
        "type": "datetime",
        "example": "2025-08-28 14:30:00"
    },
    "current_date": {
        "description": "Current date only",
        "type": "date",
        "example": "2025-08-28"
    },
    "year": {
        "description": "Current year",
        "type": "number",
        "example": "2025"
    },
    "extraction_start": {
        "description": "Extraction start time",
        "type": "datetime",
        "example": "2025-08-28 10:00:00"
    },
    "extraction_end": {
        "description": "Extraction end time", 
        "type": "datetime",
        "example": "2025-08-28 12:00:00"
    }
}

# Patterns that are considered potentially unsafe
UNSAFE_PATTERNS = [
    r"\.\.",           # Path traversal attempts
    r"[<>:\"|?*]",     # Windows invalid characters
    r"[\x00-\x1f]",    # Control characters
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$",  # Windows reserved names
    r"^\s*$",          # Empty or whitespace-only patterns
    r".{300,}",        # Excessively long patterns
]

# Maximum complexity limits
COMPLEXITY_LIMITS = {
    "max_template_size": 1024 * 1024,  # 1MB max template file size
    "max_pattern_length": 200,         # Max characters in a pattern
    "max_levels": 10,                  # Max folder levels
    "max_templates": 100,              # Max templates per file
    "max_conditionals": 10,            # Max conditional patterns
    "max_field_references": 50,        # Max field references per pattern
}