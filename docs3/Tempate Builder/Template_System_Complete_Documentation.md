# Template System Complete Documentation

## Table of Contents
1. [System Overview](#section-1-system-overview)
2. [User Guide - Creating and Managing Templates](#section-2-user-guide)
3. [Developer Documentation](#section-3-developer-documentation)

---

## Section 1: System Overview

### What is the Template System?

The Template System is a powerful, flexible framework for defining custom folder structures in the Folder Structure Application. It replaces hardcoded path building with dynamic, configurable templates that can adapt to any organizational need.

### Core Concepts

#### Templates
A template is a JSON-based configuration that defines:
- **Folder hierarchy levels** - The nested folder structure (up to 10 levels deep)
- **Naming patterns** - How folders are named using field placeholders
- **Documents placement** - Where reports and CSVs are saved (level-based)
- **Archive naming** - Fully customizable ZIP file names with placeholders and fallback patterns
- **Metadata** - Author, agency, version information

#### Level-Based Architecture
The system uses a **zero-indexed level system**:
- Level 0: First/topmost folder
- Level 1: Second folder (child of Level 0)
- Level 2: Third folder (child of Level 1)
- And so on...

Each level can have an optional display name (e.g., "Case", "Location", "Timeline") making it intuitive for users.

#### Dynamic Field Replacement
Templates use placeholder fields wrapped in curly braces that get replaced with actual data:
- `{occurrence_number}` - Case or incident number
- `{business_name}` - Business/organization name
- `{location_address}` - Physical address
- `{video_start_datetime}` - Start time of evidence
- `{technician_name}` - Person processing evidence
- And many more...

#### Documents Placement
The revolutionary **level-based documents placement** system allows you to specify exactly which level in your folder hierarchy should contain the Documents folder (where PDFs and CSVs are saved). No more hardcoded assumptions - you decide where reports go.

### How It Works

1. **Template Selection**: User selects or imports a template
2. **Data Entry**: User fills out the form with case information
3. **Path Building**: System builds folder structure based on template patterns
4. **Smart Placement**: Documents folder created at specified level
5. **File Operations**: Files copied to deepest level, reports to Documents folder
6. **Archive Creation**: Optional ZIP files named according to template

---

## Section 2: User Guide - Creating and Managing Templates

### Understanding Template Structure

A template consists of:

#### 1. Levels (Folder Hierarchy)
Each level defines one folder in your structure:
```json
"levels": [
  {
    "name": "Case",  // Optional display name
    "pattern": "{occurrence_number}",
    "fallback": "NO_CASE"
  },
  {
    "name": "Location",
    "pattern": "{business_name} @ {location_address}",
    "conditionals": {
      "business_only": "{business_name}",
      "location_only": "{location_address}",
      "neither": "NO_LOCATION"
    }
  }
]
```

#### 2. Documents Placement
Specify where reports go using a level index:
```json
"documentsPlacement": 1  // Places Documents at Level 1 (second folder)
```

#### 3. Archive Naming (Customizable ZIP File Names)

The archive naming system provides full control over how ZIP files are named, using the same placeholder system as folder structures.

**Configuration Structure:**
```json
"archiveNaming": {
  "pattern": "{occurrence_number}_{business_name}_Evidence.zip",
  "fallbackPattern": "{occurrence_number}_Evidence.zip"
}
```

**How It Works:**
- **Primary Pattern**: Used when all referenced fields have data
- **Fallback Pattern**: Automatically used when primary pattern has missing fields
- **Smart Cleanup**: Empty placeholders and extra spaces are removed automatically
- **Extension Handling**: `.zip` extension is ensured even if omitted in pattern

**Example Archive Naming Patterns:**

*Law Enforcement Style:*
```json
"pattern": "CASE_{occurrence_number}_{badge_number}_{year}_Evidence.zip"
// Result: "CASE_2024-001_12345_2024_Evidence.zip"
```

*Business-Focused:*
```json
"pattern": "{business_name}_Security_Footage_{video_start_datetime}.zip"
// Result: "Corner_Store_Security_Footage_30JUL24_1630.zip"
```

*Date-Based Organization:*
```json
"pattern": "Backup_{year}_{month}_{day}_{occurrence_number}.zip"
// Result: "Backup_2024_12_02_2024-001.zip"
```

*Simple Sequential:*
```json
"pattern": "{occurrence_number}_DVR_Export.zip",
"fallbackPattern": "Export_{current_datetime}.zip"
```

**Available Placeholders:**
All field placeholders listed below in "Available Field Placeholders" section can be used in archive naming patterns. The system will replace them with actual form data at archive creation time.

**Fallback Behavior:**
1. System attempts to use the primary `pattern`
2. If fields are missing, switches to `fallbackPattern`
3. If both fail, generates `Archive_[timestamp].zip` as ultimate fallback
4. Invalid filesystem characters are automatically sanitized

### Creating a Template

1. **Export an existing template** as a starting point
2. **Edit the JSON file** in a text editor
3. **Modify the structure**:
   - Add/remove levels
   - Change patterns
   - Set documents placement
   - Customize archive naming patterns
4. **Import the template** back into the application
5. **Test with sample data**

### Template Management Features

- **Import**: Load templates from JSON files
- **Export**: Save templates for sharing/backup
- **Delete**: Remove user-imported templates (system templates protected)
- **Preview**: Visual hierarchy with [← 📄 Documents] indicator
- **Validation**: Automatic checking for errors

### Available Field Placeholders

**Case Information:**
- `{occurrence_number}` - Case/incident number
- `{officer_name}` - Officer handling case
- `{badge_number}` - Officer badge number

**Location Details:**
- `{business_name}` - Business/organization
- `{location_address}` - Street address
- `{phone_number}` - Contact phone

**Time Information:**
- `{video_start_datetime}` - Evidence start time
- `{video_end_datetime}` - Evidence end time
- `{current_datetime}` - Current system time
- `{year}`, `{month}`, `{day}` - Date components

**Technical Details:**
- `{technician_name}` - Person processing
- `{extraction_start}` - Processing start
- `{extraction_end}` - Processing end
- `{time_offset}` - DVR time offset

### Best Practices

1. **Use descriptive level names** - Helps users understand the structure
2. **Provide fallbacks** - Handle missing data gracefully
3. **Test thoroughly** - Verify with various data combinations
4. **Document templates** - Include description and metadata
5. **Version control** - Track template changes

---

## Section 3: Developer Documentation

### Architecture Overview

The template system consists of several interconnected components:

```
TemplateManagementService (Orchestrator)
    ├── TemplateValidator (Validation)
    ├── TemplatePathBuilder (Path Construction)
    ├── PathService (Integration Point)
    └── Template Storage (JSON Files)
```

### Core Components

#### 1. TemplateManagementService
**Location**: `core/services/template_management_service.py`

Central service managing all template operations:
- Loading from multiple sources (system, user, imported)
- Import/export functionality
- Validation coordination
- Storage management

#### 2. TemplateValidator
**Location**: `core/template_validator.py`

Comprehensive validation system:
- JSON schema validation
- Security checks (path traversal prevention)
- Business logic validation
- Performance validation
- Field reference validation

#### 3. TemplatePathBuilder
**Location**: `core/template_path_builder.py`

Constructs paths from templates:
- Pattern replacement
- Conditional handling
- Date formatting (military, ISO)
- Fallback application
- Archive name building with smart cleanup

#### 4. PathService
**Location**: `core/services/path_service.py`

Integration point for path operations:
- Template selection
- Path building orchestration
- Documents placement calculation
- Archive naming

### Level-Based Documents Placement Implementation

#### The Algorithm
```python
def _calculate_level_placement(base_path, output_dir, level_index, template):
    levels = template['structure']['levels']
    total_levels = len(levels)
    
    # Calculate steps up from deepest level
    current_level = total_levels - 1
    steps_up = current_level - level_index
    
    # Navigate up from base path
    target_path = base_path
    for _ in range(steps_up):
        if target_path.parent == target_path:
            break  # Reached root
        target_path = target_path.parent
    
    return target_path / "Documents"
```

#### Key Features
- **Zero-indexed levels** - Consistent with programming conventions
- **Automatic clamping** - Invalid levels handled gracefully
- **Legacy conversion** - Strings auto-convert to integers
- **Template-aware** - Works with any template depth

### Archive Naming Implementation

#### The build_archive_name Method
**Location**: `core/template_path_builder.py` (lines 149-193)

```python
def build_archive_name(self, form_data: FormData) -> str:
    """Build archive name from template configuration"""
    archive_config = self.template.get('archiveNaming', {})
    pattern = archive_config.get('pattern', '{occurrence_number}_Video_Recovery.zip')
    fallback_pattern = archive_config.get('fallbackPattern', '{occurrence_number}_Recovery.zip')
    
    # Try main pattern, fallback if needed
    # Smart cleanup of empty @ symbols and spaces
    # Ensure .zip extension
    # Ultimate fallback: Archive_[timestamp].zip
```

#### Key Features
- **Dual Pattern System** - Primary and fallback patterns for robustness
- **Smart Cleanup** - Removes empty @ symbols when adjacent fields are missing
- **Placeholder Resolution** - Uses same system as folder naming
- **Sanitization** - Ensures filesystem-safe names
- **Extension Guarantee** - Always adds .zip if missing

### Template Schema

**Location**: `core/template_schema.py`

JSON Schema validation ensures templates are well-formed:

```python
"documentsPlacement": {
    "oneOf": [
        {"type": "integer", "minimum": 0, "maximum": 9},
        {"type": "string", "enum": ["occurrence", "location", "datetime"]}
    ]
}
```

### Storage Locations

Templates are stored in three locations:

1. **System Templates**: `templates/folder_templates.json`
   - Built-in, read-only
   - Ship with application

2. **User Templates**: `%APPDATA%/Local/FolderStructureApp/templates/`
   - User-imported templates
   - Persist across sessions

3. **Sample Templates**: `docs3/Template Builder/Templates/`
   - Examples and documentation
   - Available for import

### Integration Points

#### WorkflowController
Uses PathService to build paths:
```python
path_result = self.path_service.build_forensic_path(form_data, output_dir)
```

#### BatchProcessor
Determines documents location per job:
```python
documents_result = path_service.determine_documents_location(
    output_path,  # Base forensic path
    Path(job.output_directory)
)
```

#### UI Components
- **Template Management Dialog** - Visual template browser
- **Template Import Dialog** - Validation and preview
- **Main Window** - Template selection dropdown

### Performance Considerations

- **Lazy Loading** - Templates loaded on demand
- **Caching** - Templates cached in memory
- **Validation** - One-time validation on import
- **Path Building** - Efficient string operations

### Error Handling

All operations return `Result` objects:
```python
Result.success(value)  # Success case
Result.error(FSAError)  # Error case
```

Errors include:
- `TemplateValidationError` - Invalid template structure
- `FileOperationError` - Path building failures
- `ImportError` - Template import issues

### Testing

Key test areas:
- Template validation rules
- Path building with various data
- Documents placement calculation
- Legacy string conversion
- Edge cases (missing data, invalid levels)

### Future Enhancements

Potential improvements:
- Template editor UI (drag-drop builder)
- Template marketplace/sharing
- Dynamic field discovery
- Conditional documents placement
- Template inheritance/composition

### Migration Path

From hardcoded to template-based:
1. ForensicPathBuilder remains as fallback
2. Default template mimics legacy behavior
3. Gradual migration to full template usage
4. Eventually deprecate ForensicPathBuilder

---

## Conclusion

The Template System transforms the Folder Structure Application from a rigid, hardcoded tool into a flexible, enterprise-grade solution. With level-based documents placement, optional level names, and comprehensive validation, it provides professional forensic teams with the customization they need while maintaining consistency and reliability.

The system's elegant design - using simple integers for levels while supporting legacy strings - ensures smooth adoption and future extensibility. Whether you're a user creating templates or a developer maintaining the system, the architecture provides clear patterns and robust error handling for all scenarios.