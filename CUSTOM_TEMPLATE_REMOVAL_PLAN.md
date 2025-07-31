# Custom Template Feature Removal Plan

## Executive Summary

The Custom Template feature is deeply integrated throughout the Folder Structure Utility codebase. This document provides a comprehensive analysis of the integration points and a step-by-step plan for complete removal.

## Integration Depth Analysis

### Severity Levels
- **🔴 HIGH**: Core functionality that requires significant refactoring
- **🟡 MEDIUM**: Features that need careful removal to avoid breaking other parts
- **🟢 LOW**: Simple references that can be removed without major impact

## Complete Integration Map

### 1. Core Files (🔴 HIGH Impact)

#### `/ui/custom_template_widget.py`
- **Size**: 427 lines
- **Purpose**: Complete implementation of custom template builder
- **Dependencies**: 
  - FormData model
  - FolderTemplate class
  - QSettings for persistence
- **Action**: Delete entire file

#### `/ui/main_window.py`
- **Lines**: 28, 94-104, 101-102, 257-369
- **Integration**:
  - Import statement
  - Widget instantiation
  - Signal connections
  - Tab creation
  - Processing methods (3 methods, ~112 lines)
- **Action**: Remove all references and methods

### 2. Controller Integration (🟡 MEDIUM Impact)

#### `/controllers/file_controller.py`
- **Method**: `process_custom_files()` (lines 50-52)
- **Usage**: Creates custom FolderTemplate instances
- **Action**: Remove method

#### `/controllers/folder_controller.py`
- **Method**: `build_custom_structure()` (lines 59-60)
- **Usage**: Builds folder structure from custom template
- **Action**: Remove method

### 3. Data Model Integration (🟡 MEDIUM Impact)

#### `/core/models.py`
- **Fields**:
  - `template_type: str = "forensic"` (line 79)
  - `template_levels: List[str]` (line 80)
- **Impact**: Used in BatchJob model
- **Action**: Remove template_levels field, hardcode template_type to "forensic"

### 4. Batch Processing Integration (🔴 HIGH Impact)

#### `/ui/tabs/batch_tab.py`
- **Lines**: 91, 253, 255
- **Features**:
  - "Custom Mode" option in template dropdown
  - Logic to set template_type = "custom"
  - TODO comment about custom template levels
- **Action**: Remove dropdown option and custom logic

#### `/core/workers/batch_processor.py`
- **Method**: `_process_custom_template()` (lines 159, 207-211)
- **Usage**: Processes custom templates in batch jobs
- **Action**: Remove method and update job processing logic

### 5. Settings & Persistence (🟢 LOW Impact)

#### QSettings Keys
- **Key**: `'custom_templates'`
- **Usage**: Stores user-created templates
- **Action**: Add migration to clean up existing settings

### 6. Documentation (🟢 LOW Impact)

#### Files to Update/Remove
- `/custom_mode_instructions.html` - Delete
- `/CLAUDE.md` - Remove all custom template references
- `/README.md` - Update to remove custom mode mentions

### 7. Test Files (🟢 LOW Impact)

#### `/test_batch_integration.py`
- **Line**: 81
- **Usage**: Tests custom template type
- **Action**: Remove custom template test case

## Step-by-Step Removal Plan

### Phase 1: Preparation (No Code Changes)
1. **Create feature branch**: `feature/remove-custom-templates`
2. **Backup current state**: Tag current version as `v2.0.0-with-custom-templates`
3. **Document all custom template users**: Check settings for saved templates

### Phase 2: UI Layer Removal
1. **Remove tab from main window**:
   ```python
   # In main_window.py, remove:
   - Import of CustomTemplateWidget
   - self.custom_template_widget instantiation
   - Signal connections
   - Tab addition
   ```

2. **Remove processing methods**:
   - `process_custom_structure()`
   - `create_custom_tab()`
   - `_process_custom_tab()`

3. **Delete custom_template_widget.py**

### Phase 3: Controller Layer Cleanup
1. **Remove from file_controller.py**:
   - `process_custom_files()` method

2. **Remove from folder_controller.py**:
   - `build_custom_structure()` method

### Phase 4: Data Model Updates
1. **Update BatchJob in models.py**:
   ```python
   # Change from:
   template_type: str = "forensic"
   template_levels: List[str] = field(default_factory=list)
   
   # To:
   template_type: str = "forensic"  # Always forensic mode
   ```

### Phase 5: Batch Processing Updates
1. **Update batch_tab.py**:
   - Remove "Custom Mode" from template dropdown
   - Remove custom template logic

2. **Update batch_processor.py**:
   - Remove `_process_custom_template()` method
   - Update job processing to only handle forensic mode

### Phase 6: Cleanup & Testing
1. **Settings migration**:
   ```python
   # Add to main.py or settings manager:
   def cleanup_custom_templates():
       settings = QSettings()
       if settings.contains('custom_templates'):
           settings.remove('custom_templates')
   ```

2. **Update tests**:
   - Remove custom template test cases
   - Ensure all tests pass

3. **Documentation updates**:
   - Update README.md
   - Update CLAUDE.md
   - Delete custom_mode_instructions.html

### Phase 7: Final Verification
1. **Search for remaining references**:
   ```bash
   grep -r "custom_template" .
   grep -r "CustomTemplate" .
   grep -r "template_levels" .
   grep -r "create_tab_requested" .
   grep -r "process_requested" .
   ```

2. **Run full application test**:
   - Verify forensic mode works
   - Check batch processing
   - Ensure no UI artifacts remain

## Risk Assessment

### High Risk Areas
1. **Batch Processing**: Custom template removal affects batch job structure
2. **Settings Migration**: Users with saved templates need clean migration
3. **Signal Architecture**: Ensure no orphaned signal connections

### Mitigation Strategies
1. **Incremental Testing**: Test after each phase
2. **User Communication**: Notify users before update
3. **Rollback Plan**: Keep tagged version for emergency rollback

## Estimated Effort

- **Analysis & Planning**: 2 hours ✓ (completed)
- **Implementation**: 4-6 hours
- **Testing**: 2-3 hours
- **Documentation**: 1 hour
- **Total**: 9-12 hours

## Alternative Approach

Instead of complete removal, consider:
1. **Hide the feature**: Remove UI tab but keep backend code
2. **Feature flag**: Add setting to enable/disable custom templates
3. **Deprecation warning**: Show warning for 1-2 versions before removal

## Conclusion

The Custom Template feature is deeply integrated but can be cleanly removed by following this plan. The main challenges are:
1. Batch processing integration
2. User settings migration
3. Ensuring no functionality regression

Recommendation: Use a feature branch and thoroughly test each phase before proceeding to the next.