# Template Import System - Complete Documentation

## Table of Contents
1. [Executive Overview](#executive-overview)
2. [Technical Architecture](#technical-architecture)
3. [Senior Developer Guide](#senior-developer-guide)
4. [User Guide](#user-guide)
5. [Troubleshooting](#troubleshooting)

---

## Executive Overview

The Template Import System transforms the Folder Structure Utility from a single-template application into a flexible, multi-agency platform capable of supporting unlimited organizational structures. This enterprise-grade system enables law enforcement agencies, forensic departments, and evidence management organizations to create, share, and deploy custom folder organization templates while maintaining the highest standards of security and validation.

### Business Impact

**Problem Solved**: Different agencies require different folder structures for evidence management, but the application was limited to a single hardcoded template. This created deployment barriers and forced agencies to either modify source code or accept suboptimal folder organization.

**Solution Delivered**: A comprehensive template import/export system that allows agencies to:
- Create custom JSON-based folder structure templates
- Share templates between agencies and departments
- Validate templates for security vulnerabilities and business logic errors
- Preview templates before deployment
- Maintain backward compatibility with existing installations

**Key Benefits**:
- **Scalability**: Unlimited template variations without code changes
- **Security**: Six-level validation prevents malicious template injection
- **User Experience**: Professional UI with real-time validation feedback
- **Interoperability**: JSON-based templates enable easy sharing and version control
- **Deployment**: Zero-risk deployment with 100% backward compatibility

### Core Capabilities

1. **Template Import Engine**: Sophisticated validation system with security, business logic, and performance checks
2. **Professional UI**: Tabbed import dialog with validation results, template preview, and raw JSON inspection
3. **Template Management**: Complete CRUD operations for template lifecycle management
4. **Multi-Agency Support**: Platform-specific storage and conflict resolution for organizational templates
5. **Integration Layer**: Seamless integration with existing path building and archive naming systems

---

## Technical Architecture

### System Design Philosophy

The Template Import System follows enterprise architecture patterns established in the existing codebase, emphasizing service-oriented design, result-based error handling, and separation of concerns. The system is designed as a non-breaking enhancement that gracefully degrades when unavailable.

### Core Components Overview

**Validation Engine**: A six-tier validation system that ensures template security, correctness, and performance. Each validation level serves a specific purpose: JSON schema validation ensures structural integrity, security validation prevents malicious patterns, business logic validation ensures operational viability, performance validation prevents resource exhaustion, field reference validation ensures template compatibility, and pattern validation ensures syntactic correctness.

**Template Management Service**: Handles all template lifecycle operations including import, export, storage, and conflict resolution. The service provides platform-specific storage locations while maintaining a unified API for all operations. It includes automatic backup creation, cleanup processes, and metadata management.

**User Interface Layer**: Professional dialog-based interface providing real-time validation feedback, template preview capabilities, and comprehensive error reporting. The UI is designed to guide users through the import process while providing technical details for troubleshooting.

**Integration Points**: The system integrates with existing PathService, WorkflowController, and MainWindow components through dependency injection and service registration. Integration is designed to be optional, allowing the application to function normally when the template system is unavailable.

### Data Flow Architecture

Template processing follows a structured pipeline: File selection triggers validation through the six-tier validation engine, successful validation leads to conflict detection and resolution, templates are then installed to platform-specific storage locations with metadata enhancement, and finally the template becomes available through the existing template selection system.

The validation pipeline is designed to fail fast while providing comprehensive feedback. Early validation failures prevent resource-intensive operations, while detailed error reporting enables users to correct issues efficiently.

### Security Model

The security model operates on defense-in-depth principles with multiple validation layers. Path traversal prevention blocks directory escape attempts, character validation prevents filesystem attacks, pattern complexity limits prevent resource exhaustion attacks, field reference validation prevents injection through unknown fields, and template ID validation prevents namespace pollution.

All user input undergoes sanitization before processing, and templates are stored in controlled locations with appropriate access restrictions. The system maintains audit logs of all template operations for security monitoring.

### Performance Characteristics

The system is designed for responsive operation with templates cached in memory for instant switching. Template loading occurs asynchronously with progress feedback, validation operations complete in under one second for typical templates, and the UI remains responsive during all operations through proper threading.

Storage operations use efficient JSON serialization with automatic compression for backup files. The system includes cleanup processes to prevent storage bloat while maintaining operational history.

### Scalability and Extensibility

The architecture supports unlimited templates through efficient storage and indexing. Template schema versioning enables backward compatibility as the system evolves. The validation engine is extensible with additional validation levels, and the storage system supports multiple template sources.

Integration points use interface-based design enabling future enhancements without breaking existing functionality. The system's modular design allows individual components to be enhanced or replaced independently.

---

## Senior Developer Guide

### Core Architecture Implementation

The Template Import System is built on a foundation of three primary service classes that integrate seamlessly with the existing service-oriented architecture:

```python
# Core validation engine with comprehensive error handling
class TemplateValidator:
    def __init__(self):
        self.path_sanitizer = PathSanitizer()
    
    def validate_template_data(self, template_data: Dict[str, Any]) -> Result[List[ValidationIssue]]:
        """Six-level validation pipeline"""
        issues = []
        
        # Level 1: JSON Schema Validation
        schema_issues = self._validate_schema(template_data)
        issues.extend(schema_issues)
        
        # Early termination on schema failures
        if any(issue.level == ValidationLevel.ERROR for issue in schema_issues):
            return Result.success(issues)
        
        # Levels 2-6: Security, Business Logic, Performance, Field Reference, Pattern
        for validator_method in [
            self._validate_security,
            self._validate_business_logic, 
            self._validate_performance,
            self._validate_field_references,
            self._validate_patterns
        ]:
            issues.extend(validator_method(template_data))
        
        return Result.success(issues)
```

The validation system uses a structured approach where each level serves a specific purpose and can terminate early on critical errors while still providing comprehensive feedback.

### Service Integration Pattern

```python
class TemplateManagementService(BaseService):
    def __init__(self):
        super().__init__("TemplateManagementService")
        self.validator = TemplateValidator()
        self._setup_directories()
    
    def import_template(self, file_path: Path) -> Result[Dict[str, Any]]:
        """Complete import workflow with validation and conflict resolution"""
        # Validation phase
        validation_result = self.validator.validate_template_file(file_path)
        if not validation_result.success:
            return Result.error(validation_result.error)
        
        # Conflict detection and resolution
        template_data = self._load_template_data(file_path)
        resolved_templates = self._resolve_conflicts(template_data)
        
        # Installation with metadata enhancement
        return self._install_templates(resolved_templates, TemplateSource.IMPORTED)
```

The service layer handles all business logic while maintaining clean separation between validation, conflict resolution, and storage operations.

### Advanced UI Implementation

The import dialog uses a sophisticated tabbed interface with real-time validation feedback:

```python
class TemplateImportDialog(QDialog):
    template_imported = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.path_service = get_service(IPathService)
        self.template_data = None
        self.validation_issues = []
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Creates tabbed interface with validation, preview, and JSON tabs"""
        self.tab_widget = QTabWidget()
        
        # Validation tab with real-time issue display
        self.validation_tab = self._create_validation_tab()
        self.tab_widget.addTab(self.validation_tab, "Validation")
        
        # Preview tab with sample data testing
        self.preview_tab = TemplatePreviewWidget()
        self.tab_widget.addTab(self.preview_tab, "Preview")
        
        # Raw JSON inspection tab
        self.json_tab = self._create_json_tab()
        self.tab_widget.addTab(self.json_tab, "JSON Content")
    
    def _load_template_file(self, file_path: Path):
        """Comprehensive file loading with validation integration"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.template_data = json.load(f)
            
            # Trigger validation pipeline
            if self.path_service:
                self._validate_template(file_path)
            
        except json.JSONDecodeError as e:
            self._show_validation_error(f"Invalid JSON: {e}")
```

The UI implements progressive disclosure, showing basic information first and providing detailed technical information on demand.

### PathService Integration

```python
class PathService(BaseService):
    def __init__(self):
        super().__init__("PathService")
        try:
            self._template_management_service = TemplateManagementService()
        except Exception:
            self._template_management_service = None
    
    def import_template(self, file_path: Path) -> Result[Dict[str, Any]]:
        """Import template with service integration"""
        if not self._template_management_service:
            return Result.error(ServiceError("Template management service unavailable"))
        
        return self._template_management_service.import_template(file_path)
    
    def get_available_templates(self) -> List[Dict[str, str]]:
        """Multi-source template loading with fallback"""
        templates = []
        
        # Load system templates
        templates.extend(self._load_system_templates())
        
        # Load user templates if service available
        if self._template_management_service:
            user_templates_result = self._template_management_service.get_all_templates()
            if user_templates_result.success:
                for template_info in user_templates_result.value:
                    templates.append({
                        "id": template_info.template_id,
                        "name": template_info.name,
                        "source": template_info.source
                    })
        
        return templates
```

The integration maintains backward compatibility while providing enhanced functionality when the template system is available.

### Data Persistence Architecture

```python
class TemplateInfo:
    """Rich template metadata container"""
    def __init__(self, template_id: str, template_data: Dict[str, Any], 
                 source: str, file_path: Optional[Path] = None):
        self.template_id = template_id
        self.template_data = template_data
        self.source = source
        self.file_path = file_path
        
        # Extract and enhance metadata
        self.name = template_data.get("templateName", template_id)
        self.description = template_data.get("templateDescription", "")
        self.metadata = self._enhance_metadata(template_data.get("metadata", {}))
    
    def _enhance_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Add system-generated metadata"""
        enhanced = metadata.copy()
        enhanced.update({
            "last_accessed": datetime.now().isoformat(),
            "access_count": enhanced.get("access_count", 0) + 1,
            "system_version": "1.0.0"
        })
        return enhanced
```

The data model supports rich metadata while maintaining JSON serialization compatibility.

### Error Handling Strategy

```python
class TemplateValidationError(FSAError):
    """Specialized error for template validation failures"""
    def __init__(self, message: str, template_id: str = None, 
                 validation_issues: List[ValidationIssue] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.template_id = template_id
        self.validation_issues = validation_issues or []
        
        # Generate user-friendly message
        if not self.user_message:
            self.user_message = self._generate_user_message()
    
    def _generate_user_message(self) -> str:
        """Convert technical errors to user-friendly messages"""
        if self.validation_issues:
            error_count = len([i for i in self.validation_issues if i.level == ValidationLevel.ERROR])
            if error_count > 0:
                return f"Template contains {error_count} validation error(s) that must be fixed before import."
        
        return "Template validation failed. Please check the template format and try again."
```

Error handling provides both technical details for developers and user-friendly messages for end users.

### Testing Architecture

```python
class TestTemplateImportIntegration:
    """Comprehensive integration testing"""
    
    def setup_method(self):
        """Test environment setup with service mocking"""
        self.test_data_dir = Path("test_integration_data")
        self.template_service = TemplateManagementService()
        
        # Override directories for testing isolation
        self.template_service.user_templates_dir = self.test_data_dir
        
        # Register services for dependency injection testing
        register_service(IPathService, self.path_service)
    
    def test_end_to_end_template_workflow(self):
        """Complete workflow testing from import to usage"""
        # Step 1: Import template
        template_file = self.create_test_template_file(self.sample_template_data)
        import_result = self.path_service.import_template(template_file)
        assert import_result.success
        
        # Step 2: Verify availability
        templates = self.path_service.get_available_templates()
        assert "integration_test" in [t["id"] for t in templates]
        
        # Step 3: Use for path building
        form_data = self.create_test_form_data()
        path_result = self.path_service.build_forensic_path(form_data, Path("/test/base"))
        assert path_result.success
        
        # Step 4: Verify path structure
        built_path = path_result.value
        assert self.validate_expected_structure(built_path)
```

The testing strategy covers unit tests, integration tests, and end-to-end workflow validation.

### Performance Optimization

```python
class TemplateCache:
    """High-performance template caching system"""
    def __init__(self):
        self._cache: Dict[str, TemplateInfo] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._max_cache_size = 100
    
    def get_template(self, template_id: str) -> Optional[TemplateInfo]:
        """O(1) template lookup with LRU eviction"""
        if template_id in self._cache:
            self._cache_timestamps[template_id] = time.time()
            return self._cache[template_id]
        return None
    
    def cache_template(self, template_info: TemplateInfo):
        """Cache with automatic eviction"""
        if len(self._cache) >= self._max_cache_size:
            self._evict_lru()
        
        self._cache[template_info.template_id] = template_info
        self._cache_timestamps[template_info.template_id] = time.time()
```

Caching ensures responsive template switching while managing memory usage.

### Extension Points

```python
class TemplateValidator:
    """Extensible validation system"""
    
    def register_custom_validator(self, name: str, validator_func: Callable):
        """Allow plugins to add custom validation rules"""
        self._custom_validators[name] = validator_func
    
    def _validate_custom_rules(self, template_data: Dict[str, Any]) -> List[ValidationIssue]:
        """Execute custom validation rules"""
        issues = []
        for name, validator in self._custom_validators.items():
            try:
                custom_issues = validator(template_data)
                issues.extend(custom_issues)
            except Exception as e:
                issues.append(ValidationIssue(
                    ValidationLevel.WARNING,
                    f"Custom validator {name} failed: {e}",
                    suggestion="Contact system administrator"
                ))
        return issues
```

The architecture supports extensibility through well-defined interfaces and plugin mechanisms.

---

## User Guide

### Getting Started with Template Import

The Template Import System allows you to customize how your folders are organized when processing evidence and files. Different agencies can have different folder naming conventions, date formats, and organizational structures - the template system makes this completely configurable.

### Understanding Templates

**What are Templates?**
Templates are configuration files that define how your folder structures should be organized. Think of them as blueprints that tell the application how to name folders, where to place files, and how to handle different scenarios like missing information.

**Why Use Custom Templates?**
- **Agency Compliance**: Match your agency's specific folder naming requirements
- **Standardization**: Ensure consistent folder structures across your organization
- **Flexibility**: Handle different case types with appropriate organization
- **Sharing**: Use templates created by other agencies or share your templates with colleagues

### Accessing Template Features

**Method 1: Main Menu (Recommended)**
1. Click **Templates** in the main menu bar
2. Choose from:
   - **Import Template...** (Ctrl+Shift+I) - Add new templates from files
   - **Export Current Template...** - Save your current template to share
   - **Manage Templates...** (Ctrl+Shift+M) - Advanced template management
   - **Template Documentation** - Help and field reference

**Method 2: Forensic Tab Template Selector**
1. Go to the **Forensic** tab
2. Find the template dropdown (shows current template like "Default Forensic Structure")
3. Click the **⚙** (gear) button next to it
4. Select your desired action from the menu

### Importing Templates

#### Basic Import Process

1. **Start Import**:
   - Use Templates → Import Template... or Forensic tab ⚙ → Import Template...
   - The Template Import Dialog will open

2. **Select Template File**:
   - Click **Browse...** to select your JSON template file
   - The file will be automatically loaded and validated

3. **Review Validation Results**:
   - The **Validation** tab shows any issues found
   - ✅ Green checkmarks indicate passed validation
   - ⚠️ Yellow warnings can usually be imported (your choice)
   - ❌ Red errors must be fixed before import

4. **Preview Template Structure**:
   - Click the **Preview** tab to see how folders will be organized
   - Modify the sample data to test different scenarios
   - This helps ensure the template works as expected

5. **Inspect JSON Content**:
   - The **JSON Content** tab shows the raw template file
   - Useful for reviewing exact template definitions

6. **Complete Import**:
   - Click **Import Template** if validation passes
   - The template will be added to your available templates
   - It automatically becomes available in the template selector

#### Understanding Validation Results

**Success Messages** ✅
- "Template validation completed successfully"
- "Security validation passed - no unsafe patterns detected"
- "JSON schema validation passed"

**Warning Messages** ⚠️ (can usually proceed)
- "Template has many levels which may create deep folder structures"
- "Very long pattern may cause filesystem issues"
- "DateTime field used without dateFormat specification"

**Error Messages** ❌ (must fix before import)
- "Template contains validation errors and cannot be imported"
- "Unknown field reference found"
- "Pattern contains potentially unsafe content"
- "Template missing required templateName"

#### Sample Data Testing

In the Preview tab, you can test your template with different data scenarios:

1. **Modify Sample Data**:
   - Change Occurrence Number (e.g., "2024-CASE-001")
   - Update Business Name (e.g., "Sample Store")
   - Change Location Address (e.g., "123 Main Street")

2. **Review Preview**:
   - See exactly how folders will be named
   - Verify archive (ZIP) naming
   - Check document placement

3. **Test Edge Cases**:
   - Try empty fields to see fallback behavior
   - Test with special characters
   - Verify different date scenarios

### Using Sample Templates

The application includes several sample templates to get you started:

#### Available Samples (in `templates/samples/` directory):

**1. RCMP Complete Example** (`rcmp_complete_example.json`)
- Advanced structure for Royal Canadian Mounted Police
- Uses ISO date formatting (2025-08-28_1630)
- Complex conditional patterns for business/location handling
- Example output: `FILE_2024-001_2025/123_Main_Street_Corner_Store/2025-07-30_16:30:00_to_2025-07-30_18:00:00_UTC/`

**2. Simple Agency Example** (`simple_agency_example.json`)
- Straightforward three-level structure
- Uses military date formatting (30JUL25_1630)
- Good starting point for most agencies
- Example output: `CASE_2024-001/Corner_Store_123_Main_Street/30JUL25_1630/`

**3. Advanced Features Example** (`advanced_features_example.json`)
- Demonstrates all available template features
- Shows prefixes, suffixes, four-level structures
- Includes both advanced and minimal template examples
- Use as reference for creating sophisticated templates

#### Importing Sample Templates:

1. Use Templates → Import Template...
2. Navigate to your application's `templates/samples/` folder
3. Choose a sample template file
4. Follow the normal import process
5. The template becomes immediately available for use

### Exporting and Sharing Templates

#### Exporting Your Current Template

1. **Select Method**:
   - Templates → Export Current Template... (main menu)
   - Forensic tab ⚙ → Export Current Template...

2. **Choose Export Location**:
   - Pick a filename (e.g., "MyAgency_Template.json")
   - Choose a folder (Desktop, shared drive, etc.)
   - Click **Save**

3. **Share the File**:
   - Email the JSON file to colleagues
   - Store in shared network location
   - Include in agency documentation

#### Export Benefits
- **Standardization**: Ensure all staff use the same folder structure
- **Backup**: Save your template configurations
- **Collaboration**: Share effective templates with other agencies
- **Version Control**: Track template changes over time

### Managing Templates

#### Switching Between Templates

1. **Via Forensic Tab**:
   - Go to Forensic tab
   - Use the template dropdown to select different templates
   - Changes take effect immediately for new operations

2. **Current Template Display**:
   - The dropdown shows your current template (e.g., "RCMP Basic Structure")
   - Template changes apply to all new folder creation operations
   - Existing folders are not affected

#### Template Organization

Templates are organized by source:
- **System Templates**: Built into the application (Default Forensic, RCMP Basic, etc.)
- **Imported Templates**: Templates you've imported from files
- **Custom Templates**: Templates you've created or modified

#### Refreshing Templates

If templates seem out of sync:
1. Use the template selector ⚙ → Refresh Templates
2. Or restart the application
3. New templates should appear in the dropdown

### Advanced Features

#### Template Validation Levels

The system checks templates at six different levels:

1. **JSON Schema**: Ensures proper file format and required fields
2. **Security**: Prevents malicious patterns and path traversal attacks
3. **Business Logic**: Validates folder structure makes operational sense
4. **Performance**: Prevents templates that could cause performance issues
5. **Field References**: Ensures all referenced form fields exist
6. **Pattern Syntax**: Validates pattern syntax and prevents infinite loops

#### Available Form Fields

Your templates can use these fields from your forms:

**Core Fields:**
- `{occurrence_number}` - Case/occurrence number
- `{business_name}` - Business or establishment name
- `{location_address}` - Address or location
- `{technician_name}` - Technician name (from settings)
- `{badge_number}` - Badge number (from settings)

**Date/Time Fields:**
- `{video_start_datetime}` - Video start time
- `{video_end_datetime}` - Video end time
- `{current_datetime}` - Current processing time
- `{current_date}` - Current date only
- `{year}` - Current year

#### Date Formatting Options

Templates support two date formats:
- **Military Format**: `"dateFormat": "military"` → 30JUL25_1630
- **ISO Format**: `"dateFormat": "iso"` → 2025-07-30_16:30

#### Conditional Patterns

Templates can handle missing information gracefully:
- **business_only**: Used when only business name is available
- **location_only**: Used when only location address is available
- **neither**: Used when neither business nor location is available

### Troubleshooting

#### Common Import Issues

**"Template file contains invalid JSON"**
- Solution: Use a JSON validator to check your file format
- Common causes: Missing commas, extra commas, unmatched brackets

**"Template contains validation errors"**
- Solution: Review the Validation tab for specific errors
- Common causes: Unknown field references, unsafe patterns, missing required fields

**"Template import failed - no templates could be installed"**
- Solution: Check that your JSON file contains valid template definitions
- Verify the file has the proper structure with "version" and "templates" sections

#### Template Not Appearing in Dropdown

1. Check the import was successful (you should see a success message)
2. Try refreshing templates: template selector ⚙ → Refresh Templates
3. Restart the application if templates still don't appear
4. Check that the template has a valid templateName field

#### Validation Warnings vs. Errors

- **Warnings** (⚠️): You can choose to import anyway, but consider the implications
- **Errors** (❌): Must be fixed before import - the template could cause problems

#### Getting Help

1. **Template Documentation**: Templates → Template Documentation (comprehensive field reference)
2. **About Templates**: Template selector ⚙ → About Templates (basic information)
3. **Sample Templates**: Use provided examples as starting points
4. **Application Logs**: Check console output for technical details

#### Performance Considerations

- **Large Templates**: Templates with many levels may create deep folder structures
- **Complex Patterns**: Very long pattern names may cause filesystem issues
- **Template Count**: The system handles hundreds of templates efficiently

### Best Practices

#### Template Creation
1. **Start Simple**: Begin with sample templates and modify them
2. **Test Thoroughly**: Use the preview feature with various data scenarios
3. **Document Changes**: Include meaningful descriptions in your templates
4. **Version Control**: Use version numbers in your template metadata

#### Template Management
1. **Backup Templates**: Export important templates to safe locations
2. **Standardize Naming**: Use consistent naming conventions for template files
3. **Share Effectively**: Include documentation when sharing templates with others
4. **Review Regularly**: Periodically review templates for optimization opportunities

#### Organizational Deployment
1. **Pilot Testing**: Test new templates with small groups first
2. **Training**: Ensure staff understand how to use new templates
3. **Documentation**: Maintain agency-specific template documentation
4. **Version Management**: Track template versions across your organization

### Template File Format Reference

For users who want to create templates manually, here's the basic structure:

```json
{
  "version": "1.0.0",
  "templates": {
    "your_template_id": {
      "templateName": "Your Template Name",
      "templateDescription": "Description of what this template does",
      "structure": {
        "levels": [
          {
            "pattern": "{occurrence_number}",
            "fallback": "NO_OCCURRENCE"
          },
          {
            "pattern": "{business_name}_{location_address}",
            "conditionals": {
              "business_only": "{business_name}",
              "location_only": "{location_address}",
              "neither": "NO_BUSINESS_LOCATION"
            }
          }
        ]
      },
      "documentsPlacement": "location",
      "archiveNaming": {
        "pattern": "{occurrence_number}_{business_name}.zip",
        "fallbackPattern": "{occurrence_number}.zip"
      }
    }
  }
}
```

This creates a two-level folder structure with document placement and custom archive naming.

---

## Troubleshooting

### System Requirements

- **Operating System**: Windows 10+, macOS 10.14+, or Linux (Ubuntu 18.04+)
- **Python**: 3.7 or higher with PySide6 support
- **Dependencies**: All required packages installed via requirements.txt
- **Optional**: jsonschema package for enhanced validation (automatically detected)

### Installation Issues

**Template Features Not Available**
- Symptom: No Templates menu or import options
- Cause: Template system initialization failed
- Solution: Check application logs for initialization errors, verify all dependencies installed

**Import Dialog Won't Open**
- Symptom: Import menu item exists but dialog doesn't appear
- Cause: Missing UI dependencies or initialization failure
- Solution: Check console for Qt/PySide6 errors, restart application

### Validation Issues

**All Templates Fail Validation**
- Symptom: Even sample templates show validation errors
- Cause: System clock issues, missing dependencies, or corrupted installation
- Solution: Verify system time is correct, reinstall dependencies, check file permissions

**Inconsistent Validation Results**
- Symptom: Same template validates differently at different times
- Cause: Template file modified between validations
- Solution: Verify template file integrity, check for file locking issues

### Performance Issues

**Slow Template Loading**
- Cause: Large number of templates, slow disk access, or antivirus scanning
- Solution: Reduce template count, check disk performance, exclude template directories from antivirus scanning

**UI Freezing During Import**
- Cause: Very large template files or complex validation
- Solution: Break large templates into smaller files, check available memory

### Storage Issues

**Templates Not Persisting**
- Symptom: Imported templates disappear after restart
- Cause: Insufficient permissions, disk full, or storage location issues
- Solution: Check disk space, verify write permissions to user data directory

**Backup Creation Failures**
- Symptom: Import succeeds but no backup created
- Cause: Insufficient disk space or permissions
- Solution: Free disk space, check backup directory permissions

### Integration Issues

**Templates Don't Affect Folder Creation**
- Symptom: Template imported successfully but folder structures unchanged
- Cause: Template not properly selected or PathService integration issue
- Solution: Verify current template selection, restart application, check service initialization

**Archive Naming Not Working**
- Symptom: Templates import but ZIP files use default naming
- Cause: Archive naming service integration issue
- Solution: Check template archiveNaming section, verify service dependencies

### Error Code Reference

**TMPL001**: Template file not found or inaccessible
**TMPL002**: Invalid JSON format in template file
**TMPL003**: Template validation failed (security)
**TMPL004**: Template validation failed (business logic)
**TMPL005**: Template ID conflict detected
**TMPL006**: Storage operation failed
**TMPL007**: Service integration error
**TMPL008**: Template file too large
**TMPL009**: Unknown field reference
**TMPL010**: Pattern syntax error

### Diagnostic Commands

For troubleshooting, these operations can help identify issues:

1. **Template System Status**: Check Templates → Template Documentation for system status
2. **Validation Test**: Try importing a sample template to test validation system
3. **Storage Test**: Export any template to test storage system
4. **Service Test**: Switch between templates to test integration
5. **Log Review**: Check application console output for detailed error messages

### Recovery Procedures

**Reset Template System**
1. Close application
2. Navigate to user template directory (shown in error messages)
3. Create backup of existing templates
4. Clear imported and custom template directories
5. Restart application
6. Re-import templates one by one

**Template Corruption Recovery**
1. Export all working templates before making changes
2. Use sample templates to verify system functionality
3. Import templates individually to identify problematic files
4. Use JSON validators to check template file integrity

**Complete System Reset**
1. Uninstall and reinstall application
2. Restore templates from backup exports
3. Reconfigure template preferences
4. Test with sample templates first

This completes the comprehensive documentation for the Template Import System. The system is designed to be user-friendly while providing enterprise-grade functionality and reliability.