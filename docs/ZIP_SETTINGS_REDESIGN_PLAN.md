# ZIP_SETTINGS_REDESIGN_PLAN.md

## Overview

This document outlines the complete plan to fix the ZIP settings dialog issues where:
1. All three ZIP level options are always selected regardless of user choice
2. Settings don't persist between dialog sessions
3. Multiple ZIP files are created instead of one at the selected level
4. The interface uses checkboxes instead of mutually exclusive radio buttons
5. No option to completely disable ZIP creation

## Current Issues Analysis

### Problem 1: Settings Not Persisting
- **Root Cause**: Dialog's `accept()` method doesn't call `save_settings()`
- **Evidence**: Settings revert to defaults every time dialog reopens
- **Impact**: User selections are lost, causing all three ZIP levels to activate

### Problem 2: Multiple ZIP Creation
- **Root Cause**: All three ZIP level flags (`ZIP_AT_ROOT`, `ZIP_AT_LOCATION`, `ZIP_AT_DATETIME`) remain active
- **Evidence**: 4 ZIP files created instead of 1 (including Documents_Location.zip)
- **Impact**: Unnecessary processing time and storage usage

### Problem 3: Wrong UI Pattern
- **Root Cause**: Using checkboxes for mutually exclusive options
- **Evidence**: All three options can be checked simultaneously in current UI
- **Impact**: Confusing user experience, logical inconsistency

### Problem 4: Missing Disable Option
- **Root Cause**: No way to completely disable ZIP creation
- **Evidence**: User must uncheck all boxes to disable (unintuitive)
- **Impact**: No clear way to skip ZIP creation entirely

### Problem 5: SettingsManager Error
- **Root Cause**: `remove()` method doesn't exist in SettingsManager
- **Evidence**: `AttributeError: 'SettingsManager' object has no attribute 'remove'`
- **Impact**: Reset ZIP prompt button crashes

## New Design Specification

### UI Layout Structure

```
┌─── ZIP Settings Dialog ────────────────────────────┐
│                                                    │
│ ┌─ Compression Level ──────────────────────────┐   │
│ │ [Dropdown: No Compression / Compressed]     │   │
│ └──────────────────────────────────────────────┘   │
│                                                    │
│ ┌─ ZIP Creation Behavior ──────────────────────┐   │
│ │ ⚪ Enable ZIP Creation                       │   │
│ │ ⚪ Disable ZIP Creation                      │   │
│ │ ⚪ Prompt Each Time                          │   │
│ └──────────────────────────────────────────────┘   │
│                                                    │
│ ┌─ ZIP Archive Level ──────────────────────────┐   │
│ │ ⚪ Root Level (entire structure)             │   │
│ │ ⚪ Location Level (per location folder)      │   │
│ │ ⚪ DateTime Level (per time range folder)    │   │
│ └──────────────────────────────────────────────┘   │
│                                                    │
│               [OK]    [Cancel]                     │
└────────────────────────────────────────────────────┘
```

### Behavior Logic

1. **ZIP Creation Behavior Controls:**
   - **Enable ZIP Creation**: ZIP level options enabled, creates ZIP at selected level
   - **Disable ZIP Creation**: ZIP level options grayed out, no ZIP creation
   - **Prompt Each Time**: ZIP level options enabled, user prompted during each operation

2. **ZIP Archive Level (mutually exclusive):**
   - **Root Level**: Creates single ZIP of entire occurrence folder
   - **Location Level**: Creates ZIP of each location folder
   - **DateTime Level**: Creates ZIP of each datetime folder

3. **Default Values:**
   - ZIP Creation Behavior: "Enable ZIP Creation"
   - ZIP Archive Level: "Root Level"
   - Compression: "No Compression (Fastest)"

## Implementation Plan

### Phase 1: Settings Model Updates

#### 1.1 Update SettingsManager
**File**: `core/settings_manager.py`

**Changes**:
- Add new settings keys:
  ```python
  'ZIP_ENABLED': 'enabled',  # 'enabled', 'disabled', 'prompt'
  'ZIP_LEVEL': 'root',       # 'root', 'location', 'datetime'
  ```
- Add `remove()` method or use `set()` with default values
- Add new properties:
  ```python
  @property
  def zip_enabled(self) -> str:
      return self.get('ZIP_ENABLED', 'enabled')
  
  @property 
  def zip_level(self) -> str:
      return self.get('ZIP_LEVEL', 'root')
  ```

#### 1.2 Update Default Values
**File**: `core/settings_manager.py`

**Changes**:
```python
self.KEYS['ZIP_ENABLED']: 'enabled',
self.KEYS['ZIP_LEVEL']: 'root',
# Remove old keys:
# self.KEYS['ZIP_AT_ROOT']: True,
# self.KEYS['ZIP_AT_LOCATION']: False, 
# self.KEYS['ZIP_AT_DATETIME']: False,
```

### Phase 2: Dialog UI Redesign

#### 2.1 Replace Checkboxes with Radio Buttons
**File**: `ui/dialogs/zip_settings.py`

**Changes**:
- Import `QRadioButton`, `QButtonGroup`
- Replace checkbox creation with radio button groups:
  ```python
  # ZIP Behavior Group
  self.zip_behavior_group = QButtonGroup()
  self.zip_enabled_radio = QRadioButton("Enable ZIP Creation")
  self.zip_disabled_radio = QRadioButton("Disable ZIP Creation") 
  self.zip_prompt_radio = QRadioButton("Prompt Each Time")
  
  # ZIP Level Group
  self.zip_level_group = QButtonGroup()
  self.root_level_radio = QRadioButton("Root Level (entire structure)")
  self.location_level_radio = QRadioButton("Location Level (per location)")
  self.datetime_level_radio = QRadioButton("DateTime Level (per time range)")
  ```

#### 2.2 Add Enable/Disable Logic
**File**: `ui/dialogs/zip_settings.py`

**Changes**:
- Connect radio button signals to enable/disable methods:
  ```python
  self.zip_disabled_radio.toggled.connect(self._on_zip_behavior_changed)
  ```
- Implement disable logic:
  ```python
  def _on_zip_behavior_changed(self):
      disabled = self.zip_disabled_radio.isChecked()
      self.root_level_radio.setEnabled(not disabled)
      self.location_level_radio.setEnabled(not disabled)
      self.datetime_level_radio.setEnabled(not disabled)
  ```

#### 2.3 Fix Settings Save/Load
**File**: `ui/dialogs/zip_settings.py`

**Changes**:
- Fix `accept()` method to call `save_settings()`:
  ```python
  def accept(self):
      self.save_settings()
      super().accept()
  ```
- Update `_load_settings()` and `save_settings()` for new radio buttons
- Remove broken `reset_zip_prompt()` method

### Phase 3: Business Logic Updates

#### 3.1 Update ZIP Creation Logic
**File**: `ui/main_window.py`

**Changes**:
- Update `create_zip_archives()` to use new settings model:
  ```python
  zip_enabled = self.settings.zip_enabled
  if zip_enabled == 'disabled':
      return  # Skip ZIP creation
  elif zip_enabled == 'prompt':
      # Show prompt dialog
      pass
  
  zip_level = self.settings.zip_level
  settings.create_at_root = (zip_level == 'root')
  settings.create_at_location = (zip_level == 'location') 
  settings.create_at_datetime = (zip_level == 'datetime')
  ```

#### 3.2 Update Report Controller
**File**: `controllers/report_controller.py`

**Changes**:
- Update `should_create_zip()`:
  ```python
  def should_create_zip(self) -> bool:
      return self.settings.get('ZIP_ENABLED', 'enabled') != 'disabled'
  ```
- Update `get_zip_settings()` to use new model

#### 3.3 Add Prompt Dialog (if needed)
**File**: `ui/dialogs/` (new file if needed)

**Changes**:
- Create simple prompt dialog for "Prompt Each Time" option
- Return user's choice for that specific operation

### Phase 4: Cleanup and Migration

#### 4.1 Settings Migration
**File**: `core/settings_manager.py`

**Changes**:
- Add migration logic for existing users:
  ```python
  def _migrate_old_zip_settings(self):
      # Convert old checkbox settings to new radio button model
      if self.get('ZIP_AT_ROOT', None) is not None:
          # Migrate old settings
          pass
  ```

#### 4.2 Remove Old Code
**Files**: Multiple

**Changes**:
- Remove references to old `ZIP_AT_*` keys
- Remove unused import statements
- Clean up dead code paths

### Phase 5: Testing Strategy

#### 5.1 Unit Testing Scenarios
1. **Settings Persistence**: Verify settings save and load correctly
2. **Radio Button Logic**: Verify mutual exclusivity works
3. **Enable/Disable Logic**: Verify ZIP level options get disabled properly
4. **ZIP Creation**: Verify only one ZIP created at selected level

#### 5.2 Integration Testing Scenarios  
1. **Dialog→Settings→ZipCreation**: Full workflow test
2. **Multiple Dialog Opens**: Verify settings persist between sessions
3. **Different ZIP Levels**: Test each level creates correct ZIP
4. **Disable Option**: Verify no ZIP created when disabled

#### 5.3 User Acceptance Testing
1. **Intuitive Interface**: Verify radio buttons are clearer than checkboxes
2. **Expected Behavior**: Verify one ZIP created at selected level
3. **Disable Functionality**: Verify disable option works as expected

## Risk Assessment

### Low Risk
- UI changes (radio buttons vs checkboxes) - easy to revert
- Settings key changes - can maintain backward compatibility

### Medium Risk  
- Business logic changes in ZIP creation - thorough testing needed
- Settings migration - need to handle edge cases

### High Risk
- None identified - changes are incremental and reversible

## Success Criteria

### Primary Goals
✅ **Single ZIP Creation**: Only one ZIP file created at user's selected level  
✅ **Settings Persistence**: User selections survive dialog close/reopen  
✅ **Intuitive Interface**: Radio buttons provide clear mutually exclusive choices  
✅ **Disable Option**: Clean way to completely disable ZIP creation  

### Secondary Goals  
✅ **Error-Free Operation**: No more SettingsManager.remove() crashes  
✅ **Performance**: No unnecessary ZIP creation processing  
✅ **User Experience**: Clearer, more professional dialog interface  

## Implementation Timeline

1. **Phase 1** (Settings Model): 30 minutes
2. **Phase 2** (UI Redesign): 45 minutes  
3. **Phase 3** (Business Logic): 30 minutes
4. **Phase 4** (Cleanup): 15 minutes
5. **Phase 5** (Testing): 30 minutes

**Total Estimated Time**: 2.5 hours

## Rollback Plan

If issues arise during implementation:
1. **Revert settings keys** to old `ZIP_AT_*` format
2. **Restore checkbox UI** in dialog  
3. **Git revert** to last known good state
4. **Re-analyze** root causes before retry

---

## Conclusion

This plan addresses all identified issues with the ZIP settings system through a systematic redesign that improves user experience while fixing the underlying technical problems. The phased approach ensures each component can be tested independently and rolled back if necessary.