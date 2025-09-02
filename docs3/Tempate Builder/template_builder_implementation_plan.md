# Template Builder Implementation Plan

## Memory Graph Analysis Summary

**Searched Components:**
- Template Management System Architecture: Complete enterprise-grade system with TemplateSchema, TemplateValidator, TemplatePathBuilder, TemplateManagementService
- Existing UI Dialogs: TemplateManagementDialog, TemplateImportDialog, TemplateInfoWidget, TemplatePreviewWidget
- Service Layer: PathService, IPathService, ValidationService with Result object patterns
- Template Infrastructure: Template Storage System, Template Security Framework, Template Field System
- Dialog Architecture: UI Dialog Architecture with validation patterns and Carolina Blue theming

**Critical UI Analysis:**
- **TemplateManagementDialog (653 lines)**: Comprehensive split-pane interface with hierarchical tree, filtering, import/export/delete operations, service integration via IPathService
- **TemplateImportDialog (558 lines)**: Three-tab validation wizard with ValidationIssueWidget, TemplatePreviewWidget, real-time validation, and Result object patterns
- **Established UI Patterns**: Color-coded validation, debounced updates (500ms), permission-based button states, context menus, Carolina Blue theming

**Key Discovery:** The application already has a **comprehensive template management system** AND **established UI patterns** for template operations. The Template Builder should **extend the existing dialogs** rather than create separate interfaces.

## Implementation Overview

### What We're Building
A visual template builder dialog that creates the same JSON templates that the existing system already supports. This is purely a UI enhancement - no changes to the underlying template architecture are needed.

### Philosophy
Following the design document's pragmatic approach: **simple forms that create exactly what users need** without complex visual programming. The builder will generate standard JSON templates that integrate seamlessly with the existing template system.

## Existing Infrastructure We'll Leverage

### Template Management System (Already Built)
- **TemplateSchema**: JSON schema validation for template structure
- **TemplateValidator**: 6-phase validation pipeline with security and business logic checks
- **TemplateManagementService**: Import/export, storage, conflict resolution
- **Template Storage System**: Platform-specific user data directories with backup rotation
- **Template Security Framework**: Path traversal prevention, filename validation, pattern sanitization

### Service Layer Integration Points
- **IPathService**: Template operations interface (get_available_templates, import_template, etc.)
- **PathService**: Service implementation with TemplateManagementService integration
- **Result Object Pattern**: All operations return Result[T] for type-safe error handling
- **BaseService**: Logging and error handling foundation for services

### UI Foundation (Ready to Use)
- **Dialog Architecture**: Modal patterns, validation frameworks, Carolina Blue theming
- **Template Management Dialogs**: Existing dialogs for template selection and import
- **FormData Model**: Available fields for template building ({occurrence_number}, {business_name}, etc.)
- **ValidationIssueWidget**: Color-coded validation display with severity levels and suggestions (from TemplateImportDialog)
- **TemplatePreviewWidget**: Live preview with sample data and debounced updates (from TemplateImportDialog)
- **Service Integration Patterns**: IPathService usage, Result object handling, error display patterns

## Implementation Plan

### Phase 1: Core Builder Dialog (Week 1)

#### 1.1 Create TemplateBuilderDialog Class
**File:** `ui/dialogs/template_builder_dialog.py`

```python
class TemplateBuilderDialog(QDialog):
    """Visual template builder - creates JSON templates for existing system"""
    
    # Core UI components
    def __init__(self, parent=None, edit_template=None):
        # Modal dialog, 900x700 pixels
        # Two-panel layout: Properties (left) + Structure Builder (right)
        
    def _setup_ui(self):
        # Left panel: Template properties
        # Right panel: Level builder + preview
        
    def _setup_validation(self):
        # Real-time validation using existing TemplateValidator
        # Error display with suggestions
```

**Integration Points:**
- Uses existing `IPathService` for template operations
- Leverages `TemplateValidator` for real-time validation
- Returns standard JSON template format
- Integrates with existing `Result[TemplateInfo]` pattern
- **Reuses ValidationIssueWidget** from TemplateImportDialog for validation display
- **Follows TemplateManagementDialog styling patterns** (900x700 size, split-pane, Carolina Blue theme)

#### 1.2 Template Properties Panel
**Components:**
- Template name (required, validated)
- Description text area (optional)
- Agency/organization field (optional)
- Documents folder placement (radio buttons)
- Archive naming section

**Validation:**
- Real-time name validation (no duplicates, safe characters)
- Integration with existing `TemplateValidator` security checks

#### 1.3 Folder Level Builder System
**Core Component:** `FolderLevelCard` widget

```python
class FolderLevelCard(QWidget):
    """Single folder level configuration card"""
    
    def __init__(self, level_number: int):
        # Gray background card with rounded corners
        # Level badge, component builder, delete/reorder buttons
        
    def add_component(self, component_type: str):
        # Adds: Static Text, Form Field, Current Date, etc.
        # Each component has prefix/suffix options
```

**Component Types:**
- **Static Text**: Simple text input (e.g., "Documents", "Evidence")
- **Form Field**: Dropdown with FormData fields (occurrence_number, business_name, etc.)
- **Current Date**: Format options (military, ISO, custom)
- **Counter**: Sequential numbering (future enhancement)

### Phase 2: Component System (Week 1)

#### 2.1 Component Builder Infrastructure
**File:** `ui/dialogs/template_builder_components.py`

```python
class ComponentWidget(QWidget):
    """Base class for folder name components"""
    component_changed = Signal()  # Triggers preview update
    
class StaticTextComponent(ComponentWidget):
    """Simple text input component"""
    
class FormFieldComponent(ComponentWidget):
    """Form field selector with prefix/suffix"""
    # Uses FormData field names from existing model
    
class DateComponent(ComponentWidget):
    """Date formatting component"""
    # Military: 30JUL25_1630
    # ISO: 2025-07-30_1630
```

**Available Form Fields (from existing FormData model):**
- occurrence_number
- business_name  
- location_address
- video_start_datetime / video_end_datetime
- technician_name
- badge_number

#### 2.2 Live Preview System
**Reuse Existing TemplatePreviewWidget** from TemplateImportDialog:

```python
# Import and extend existing preview widget
from ui.dialogs.template_import_dialog import TemplatePreviewWidget

class TemplateBuilderPreviewWidget(TemplatePreviewWidget):
    """Extended preview widget for template builder"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # Inherits: sample data form, tree display, auto-update timer
        # Inherits: 500ms debounced updates
        
    def update_from_builder_config(self, builder_config: dict):
        # Convert builder UI config to template format
        # Use inherited update_preview() method
```

**Inherited Features:**
- Sample data form with occurrence/business/location fields
- Tree display with Template/Preview Path/Archive Name columns  
- Auto-update with 500ms debounced timer
- Error handling for preview generation

### Phase 3: Template Generation (Week 2)

#### 3.1 JSON Template Builder
```python
class TemplateJsonBuilder:
    """Converts UI configuration to JSON template format"""
    
    def build_template(self, config: dict) -> dict:
        # Creates standard template JSON matching existing schema
        # Handles conditionals, date formats, archive naming
        # Returns format compatible with TemplateValidator
```

**Output Format (matches existing schema):**
```json
{
    "version": "1.0.0",
    "templates": {
        "custom_template_id": {
            "templateName": "User Template Name",
            "structure": [
                {
                    "pattern": "{occurrence_number}",
                    "conditionals": {...},
                    "prefix": "CASE-",
                    "suffix": "_2025"
                }
            ],
            "documentsPlacement": "location",
            "archiveNaming": {
                "pattern": "{occurrence_number}_{business_name}.zip"
            }
        }
    }
}
```

#### 3.2 Template Validation Integration
**Reuse TemplateImportDialog Validation Patterns:**

```python
# Import existing validation UI components
from ui.dialogs.template_import_dialog import ValidationIssueWidget

class TemplateBuilderValidation:
    """Validation system using existing components"""
    
    def display_validation_results(self, issues: List[dict]):
        # Reuse ValidationIssueWidget for each issue
        # Same color coding: error/warning/info/success
        # Same styling and layout patterns
```

**Inherited Validation Features:**
- Uses existing `TemplateValidator.validate_template()` with 6-phase validation
- Real-time validation with debounced updates (500ms) 
- **ValidationIssueWidget**: Color-coded error display with suggestions
- Error/warning/info level handling with import controls
- Progress indication during validation

### Phase 4: Dialog Integration (Week 2)

#### 4.1 Template Manager Integration
**Modify:** `ui/dialogs/template_management_dialog.py`

**Exact Integration Point (around line 220):**
```python
# Add "Create Template" button near existing action buttons
def _setup_action_buttons(self, button_layout):
    """Add template builder to existing button layout"""
    
    # Existing buttons: Import, Export, Delete
    # ... existing button code ...
    
    # NEW: Add Template Builder button
    self.create_template_btn = QPushButton("✏️ Create Custom Template")
    self.create_template_btn.clicked.connect(self._open_template_builder)
    self.create_template_btn.setToolTip("Create a new custom template using the visual builder")
    button_layout.addWidget(self.create_template_btn)
    
def _open_template_builder(self):
    """Open template builder dialog"""
    from ui.dialogs.template_builder_dialog import TemplateBuilderDialog
    
    builder = TemplateBuilderDialog(self)
    if builder.exec() == QDialog.Accepted:
        self._load_templates()  # Existing refresh method
        self.templates_changed.emit()  # Existing signal
```

**Button Placement:** After Import/Export/Delete buttons, before the stretch spacer (maintains existing layout)

#### 4.2 Template Selector Integration  
**Modify:** `ui/components/template_selector.py`

```python
# Add "Create Template" to settings menu
def _setup_settings_menu(self):
    # ... existing menu items ...
    self.settings_menu.addAction("Create Template...", self._open_builder)
```

#### 4.3 Menu Integration
**Modify:** `ui/main_window.py`

```python
# Add to Tools menu
def _setup_menus(self):
    tools_menu = self.menuBar().addMenu("Tools")
    tools_menu.addAction("Template Builder", self._open_template_builder)
```

### Phase 5: Advanced Features (Week 3)

#### 5.1 Quick Templates System
**Dropdown button:** "Add Common Structure ▼"

Pre-configured level templates:
- **Add Date/Time Level**: `{video_start_datetime}` with military format
- **Add Location Level**: `{business_name} @ {location_address}` with conditionals
- **Add Documents Folder**: Static text "Documents"
- **Add Evidence Type Folders**: Multiple static text levels

#### 5.2 Test & Validation Dialog
```python
class TemplateTestDialog(QDialog):
    """Test template with sample data"""
    
    def __init__(self, template_config: dict):
        # Form fields for test data entry
        # Generate button with live preview
        # Integration with TemplatePathBuilder
```

#### 5.3 Import/Export Integration
- **Import**: Existing templates can be loaded for editing
- **Export**: Templates can be shared as JSON files
- Uses existing `TemplateManagementService` methods

## Technical Implementation Details

### Service Layer (No Changes Needed)
The existing service architecture is complete:
- `IPathService.import_template()` - saves generated JSON
- `TemplateValidator.validate_template()` - validates configuration  
- `TemplateManagementService` - handles storage and conflicts
- `Result[TemplateInfo]` - type-safe error handling

### Data Flow
1. User configures template in builder UI
2. `TemplateJsonBuilder` converts to JSON format
3. `TemplateValidator` validates the JSON
4. `IPathService.import_template()` saves to user templates
5. Template immediately available in dropdown selectors

### Error Handling Pattern
```python
def save_template(self) -> Result[TemplateInfo]:
    """Save template using existing infrastructure"""
    try:
        template_json = self.json_builder.build_template(self.get_config())
        validation_result = self.validator.validate_template(template_json)
        
        if validation_result.has_errors():
            return Result.error("Template validation failed")
            
        return self.path_service.import_template(template_json)
    except Exception as e:
        return Result.error(f"Failed to save template: {e}")
```

### Threading & Performance
- UI operations only (no heavy processing)
- Preview updates debounced at 500ms
- Template validation is lightweight (existing infrastructure)
- No background threads needed

## File Structure

### New Files Required
```
ui/dialogs/
├── template_builder_dialog.py          # Main builder dialog
└── template_builder_components.py      # Component widgets (FolderLevelCard, ComponentWidget)

core/
└── template_json_builder.py           # JSON generation utility (converts UI config to template JSON)
```

**Reused Files (No New Files Needed):**
```
ui/dialogs/template_import_dialog.py    # ValidationIssueWidget, TemplatePreviewWidget
ui/dialogs/template_management_dialog.py # Integration point, styling patterns
```

### Modified Files
```
ui/dialogs/template_management_dialog.py  # Add "Create" button
ui/components/template_selector.py        # Add builder menu item
ui/main_window.py                         # Add Tools menu item
```

## User Experience Flow

### Creating a Template
1. User clicks "Create Custom Template" (Template Manager or Tools menu)
2. Template Builder opens with default single level
3. User configures template name and first level
4. Uses "+" button to add additional levels
5. Live preview shows folder structure in real-time
6. Click "Save and Test" to validate with sample data
7. Template saved to user templates, immediately available

### Editing Existing Templates
1. User selects template in Template Manager
2. Clicks "Edit" button (new button)
3. Template Builder opens with configuration loaded
4. User modifies levels, sees live preview updates
5. Save overwrites existing template

## Risk Mitigation

### Low Implementation Risk
- **No architectural changes**: Uses existing template system
- **Proven UI patterns**: **Reuses existing ValidationIssueWidget, TemplatePreviewWidget**
- **Comprehensive validation**: Leverages existing security framework
- **Type safety**: Result objects prevent runtime errors
- **Minimal new code**: Only 3 new files needed, reuses existing UI components
- **Seamless integration**: Fits naturally into existing TemplateManagementDialog

### Fallback Strategy
If advanced features prove complex:
1. **Phase 1-3**: Core builder functionality (sufficient for MVP)
2. **Phase 4**: Dialog integration (essential for user access)  
3. **Phase 5**: Advanced features (can be deferred)

## Success Metrics

### Technical Success
- Templates created by builder work identically to JSON templates
- No security vulnerabilities introduced
- Performance maintains existing standards
- All existing template operations continue working

### User Success (from design document)
1. Create basic 3-level template in under 2 minutes ✓
2. Understand every option without documentation ✓
3. Test template before saving ✓
4. Modify existing templates without breaking them ✓
5. Share templates with other agencies easily ✓

## Integration Testing Plan

### Template Compatibility Testing
1. Create templates via builder
2. Verify JSON output matches schema
3. Test template usage in forensic workflow
4. Validate folder structure creation
5. Confirm report generation works

### Service Integration Testing
1. Template import via IPathService
2. Validation via TemplateValidator  
3. Storage via TemplateManagementService
4. Error handling with Result objects
5. UI integration with existing dialogs

## Summary

This implementation leverages the existing **comprehensive template management infrastructure** and **proven UI components** to create a seamless visual interface. The risk is minimal because:

- **No changes to core template architecture**
- **Reuses established UI components**: ValidationIssueWidget, TemplatePreviewWidget, existing dialog patterns
- **Minimal new code required**: Only 3 new files vs existing 20+ template system files
- **Proven integration patterns**: Follows TemplateManagementDialog and TemplateImportDialog patterns
- **Generates standard JSON compatible with existing system**
- **Comprehensive validation and security already built-in**

The Template Builder will provide the **user-friendly interface** described in the design document while maintaining the **enterprise-grade architecture** and **consistent user experience** that already exists in the application.

**Revised Timeline Estimate:**
- **Core functionality: 4-5 days** (reduced due to component reuse)
- **Integration and polish: 3-4 days** (minimal changes needed)
- **Total: 1-2 weeks for complete implementation** (reduced from 2-3 weeks)