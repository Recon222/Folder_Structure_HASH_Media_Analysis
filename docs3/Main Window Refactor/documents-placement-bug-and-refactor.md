# Documents Folder Placement Bug & MainWindow Business Logic Refactor

## Executive Summary

There are two interconnected issues that need to be addressed:
1. **BUG**: Documents folder is being placed incorrectly when copying folders with preserved structure in the Forensics tab
2. **ARCHITECTURAL VIOLATION**: MainWindow contains business logic for path determination that should be in the controller/service layer

Fixing the architectural issue will also fix the bug, making this a double win.

## Table of Contents
1. [The Bug: Documents Folder Misplacement](#the-bug-documents-folder-misplacement)
2. [The Architectural Issue](#the-architectural-issue)
3. [Root Cause Analysis](#root-cause-analysis)
4. [The Solution](#the-solution)
5. [Implementation Guide](#implementation-guide)
6. [Testing Checklist](#testing-checklist)

---

## The Bug: Documents Folder Misplacement

### Current Behavior (WRONG)
When using the Forensics tab to copy folders with preserved structure, the Documents folder ends up inside the copied folder structure instead of at the correct template-specified location.

```
PR123456/
└── Hooked @ 12345 Danforth Ave. Toronto/
    └── 31AUG25_2049_to_1SEP25_2049_DVR_Time/
        └── Original Video - 19.7/              ← Copied folder (preserved structure)
            ├── 136 Lockwood/                    ← Preserved subfolders
            │   └── 136_Lockwood_Rd.mov
            └── Documents/                       ← ❌ WRONG! Inside copied folder
                ├── Time_Offset_Report.pdf
                ├── Upload_Log.pdf
                └── Hash_Verification.csv
```

### Expected Behavior (CORRECT)
According to the template setting `"documentsPlacement": "location"`, Documents should be at Level 2 (the business/location folder):

```
PR123456/
└── Hooked @ 12345 Danforth Ave. Toronto/
    ├── Documents/                               ← ✅ CORRECT! At location level
    │   ├── Time_Offset_Report.pdf
    │   ├── Upload_Log.pdf
    │   └── Hash_Verification.csv
    └── 31AUG25_2049_to_1SEP25_2049_DVR_Time/
        └── Original Video - 19.7/
            └── 136 Lockwood/
                └── 136_Lockwood_Rd.mov
```

### Template Structure Levels
The forensic folder structure has three levels:
1. **Level 1 (occurrence)**: `{occurrence_number}` → "PR123456"
2. **Level 2 (location)**: `{business_name} @ {location_address}` → "Hooked @ 12345 Danforth Ave. Toronto"
3. **Level 3 (datetime)**: `{video_start_datetime}_to_{video_end_datetime}_DVR_Time` → "31AUG25_2049_to_1SEP25_2049_DVR_Time"

The template at `docs3/Tempate Builder/Templates/Default_Forensic_Structure.json` specifies:
```json
"documentsPlacement": "location"
```

### Why Batch Processing Works
Batch processing correctly places Documents because it uses a different code path that doesn't have this bug:
- File: `core/workers/batch_processor.py`, line 627
- It correctly calculates: `reports_dir = output_path.parent / "Documents"`
- Where `output_path` is the datetime folder, so `parent` is the location folder

---

## The Architectural Issue

### Business Logic in MainWindow
During the refactor to move business logic out of MainWindow into the service layer, report generation logic was partially moved but **path determination logic was missed**.

**Current problematic code in `ui/main_window.py` (lines 495-511):**
```python
# Find a result entry with dest_path
file_dest_path = None
for result_value in self.file_operation_results.values():
    if isinstance(result_value, dict) and 'dest_path' in result_value:
        file_dest_path = Path(result_value['dest_path'])
        break
        
if not file_dest_path:
    self.log("Cannot generate reports - no destination path found in results")
    self.show_final_completion_message()
    return

# Use PathService to determine documents location
documents_location_result = self.workflow_controller.path_service.determine_documents_location(
    file_dest_path,
    self.output_directory
)
```

### Why This Is Wrong
1. **Business Logic in UI**: MainWindow is making decisions about which path to use from results
2. **Incorrect Path Selection**: It grabs the first file's destination path, which includes preserved folder structure
3. **Lost Context**: MainWindow doesn't know the difference between the forensic structure and preserved folders

### What Should Happen
MainWindow should simply call:
```python
report_result = self.workflow_controller.generate_reports(
    self.form_data,
    self.file_operation_results,
    self.output_directory
)
```

The WorkflowController should handle ALL the business logic.

---

## Root Cause Analysis

### The Path Calculation Problem

When files are copied with preserved folder structure:
1. **File destination path**: `.../31AUG25.../Original Video - 19.7/136 Lockwood/136_Lockwood_Rd.mov`
2. **PathService tries to calculate** (in `core/services/path_service.py`, lines 452-454):
   ```python
   # These comments show what it EXPECTS:
   # file_dest_path.parent is the datetime folder
   # file_dest_path.parent.parent is the business/location folder
   business_dir = file_dest_path.parent.parent
   ```
3. **But actually gets**:
   - `file_dest_path.parent` = `.../Original Video - 19.7/136 Lockwood` (NOT datetime folder!)
   - `file_dest_path.parent.parent` = `.../Original Video - 19.7` (NOT location folder!)

### Why The Bug Exists
The code assumes file paths have exactly 3 levels below the output directory, but with preserved folder structure, there can be any number of additional levels.

---

## The Solution

### Step 1: Move Business Logic to WorkflowController

Add a new method to `controllers/workflow_controller.py`:

```python
def generate_reports(
    self,
    form_data: FormData,
    file_operation_results: Dict,
    output_directory: Path
) -> Result[Dict]:
    """
    Generate all reports with proper path determination
    
    This method encapsulates the business logic for:
    1. Determining the correct base path for documents
    2. Handling different scenarios (files vs folders)
    3. Calling ReportController with correct paths
    """
    try:
        # Validate inputs
        validation_result = self.validation_service.validate_report_requirements(
            form_data, file_operation_results
        )
        if not validation_result.success:
            return validation_result
        
        # Determine the base forensic structure path
        # This is the KEY FIX - we need to find the datetime folder path,
        # not use a file's destination path
        base_path_result = self._determine_base_forensic_path(
            file_operation_results,
            output_directory,
            form_data
        )
        if not base_path_result.success:
            return base_path_result
        
        base_forensic_path = base_path_result.value
        
        # Determine documents location based on template
        documents_location_result = self.path_service.determine_documents_location(
            base_forensic_path,  # Pass the base path, not a file path!
            output_directory
        )
        if not documents_location_result.success:
            return documents_location_result
        
        # Generate reports
        report_results = self.report_controller.generate_all_reports(
            form_data=form_data,
            file_results=file_operation_results,
            output_dir=documents_location_result.value,
            generate_time_offset=True,
            generate_upload_log=True,
            generate_hash_csv=bool(file_operation_results)
        )
        
        return Result.success({
            'reports': report_results,
            'documents_dir': documents_location_result.value
        })
        
    except Exception as e:
        error = WorkflowError(
            f"Report generation failed: {str(e)}",
            user_message="Failed to generate reports. Please check the logs."
        )
        return Result.error(error)

def _determine_base_forensic_path(
    self,
    file_operation_results: Dict,
    output_directory: Path,
    form_data: FormData
) -> Result[Path]:
    """
    Determine the base forensic structure path (datetime folder)
    This is the critical fix - we need the forensic structure path,
    not a path that includes preserved folder structure
    """
    try:
        # Build the expected forensic path using the same logic that created it
        path_result = self.path_service.build_full_output_path(
            occurrence_number=form_data.occurrence_number,
            business_name=form_data.business_name,
            location_address=form_data.location_address,
            video_start=form_data.video_start_datetime,
            video_end=form_data.video_end_datetime,
            output_directory=output_directory
        )
        
        if not path_result.success:
            # Fallback: try to extract from results
            # But be smart about it - look for the datetime folder pattern
            for result in file_operation_results.values():
                if isinstance(result, dict) and 'dest_path' in result:
                    dest_path = Path(result['dest_path'])
                    # Walk up the path looking for the datetime folder
                    for parent in dest_path.parents:
                        if self._is_datetime_folder(parent.name):
                            return Result.success(parent)
            
            return Result.error(
                WorkflowError("Could not determine base forensic path")
            )
        
        return path_result
    
    except Exception as e:
        return Result.error(
            WorkflowError(f"Failed to determine base path: {str(e)}")
        )

def _is_datetime_folder(self, folder_name: str) -> bool:
    """Check if folder name matches datetime pattern"""
    # Pattern: XXX##_####_to_XXX##_####_DVR_Time
    import re
    pattern = r'^\w{3}\d{2}_\d{4}_to_\w{3}\d{2}_\d{4}_DVR_Time$'
    return bool(re.match(pattern, folder_name))
```

### Step 2: Fix PathService.determine_documents_location()

Update `core/services/path_service.py` to handle the base path correctly:

```python
def determine_documents_location(
    self, 
    base_forensic_path: Path,  # Renamed from file_dest_path for clarity
    output_directory: Path
) -> Result[Path]:
    """
    Determine where to place the Documents folder based on template settings
    
    Args:
        base_forensic_path: The base forensic structure path (datetime folder level)
                           NOT a file path with preserved folder structure
        output_directory: Base output directory
        
    Returns:
        Result containing the Documents folder path
    """
    try:
        self._log_operation("determine_documents_location", f"base_path: {base_forensic_path}")
        
        # Find the occurrence folder first
        occurrence_result = self.find_occurrence_folder(base_forensic_path, output_directory)
        if not occurrence_result.success:
            return occurrence_result
        
        occurrence_dir = occurrence_result.value
        
        # Get the template's documentsPlacement setting
        documents_placement = "location"  # Default fallback
        
        try:
            template = self._templates.get(self._current_template_id)
            if template:
                documents_placement = template.get('documentsPlacement', 'location')
                self._log_operation("documents_placement", f"Using template setting: {documents_placement}")
        except Exception as e:
            self._log_operation("documents_placement_error", str(e), "warning")
        
        # Determine Documents folder location based on template setting
        if documents_placement == "occurrence":
            # Level 1: Occurrence number folder
            documents_dir = occurrence_dir / "Documents"
            self._log_operation("documents_location", f"Occurrence level: {documents_dir}")
            
        elif documents_placement == "location":
            # Level 2: Business/location folder
            # Since base_forensic_path is the datetime folder,
            # its parent is the location folder
            location_dir = base_forensic_path.parent
            documents_dir = location_dir / "Documents"
            self._log_operation("documents_location", f"Location level: {documents_dir}")
            
        elif documents_placement == "datetime":
            # Level 3: DateTime folder
            documents_dir = base_forensic_path / "Documents"
            self._log_operation("documents_location", f"DateTime level: {documents_dir}")
        
        else:
            # Default to location level
            location_dir = base_forensic_path.parent
            documents_dir = location_dir / "Documents"
            self._log_operation("documents_location", f"Default to location level: {documents_dir}")
        
        return Result.success(documents_dir)
        
    except Exception as e:
        error = PathError(
            f"Failed to determine documents location: {str(e)}",
            user_message="Could not determine where to place reports."
        )
        return Result.error(error)
```

### Step 3: Update MainWindow

Simplify `ui/main_window.py` (starting around line 489):

```python
def generate_reports(self):
    """Generate reports after file operations complete"""
    try:
        if not self.forensic_tab.generate_time_offset.isChecked() and \
           not self.forensic_tab.generate_upload_log.isChecked() and \
           not self.forensic_tab.calculate_hash.isChecked():
            self.log("No reports selected for generation")
            self.show_final_completion_message()
            return
        
        # Call WorkflowController to handle all business logic
        report_result = self.workflow_controller.generate_reports(
            form_data=self.form_data,
            file_operation_results=self.file_operation_results,
            output_directory=self.output_directory
        )
        
        if not report_result.success:
            error = UIError(
                f"Report generation failed: {report_result.error.message}",
                user_message=report_result.error.user_message,
                component="MainWindow"
            )
            handle_error(error, {'operation': 'report_generation'})
            self.show_final_completion_message()
            return
        
        # Log success
        report_data = report_result.value
        documents_dir = report_data.get('documents_dir')
        self.log(f"Reports generated in: {documents_dir}")
        
        # Handle ZIP if needed
        if self.forensic_tab.create_zip.isChecked():
            self.create_zip_archive()
        else:
            self.show_final_completion_message()
            
    except Exception as e:
        self.log(f"Error generating reports: {e}")
        self.show_final_completion_message()
```

---

## Implementation Guide

### Files to Modify

1. **controllers/workflow_controller.py**
   - Add `generate_reports()` method
   - Add `_determine_base_forensic_path()` helper
   - Add `_is_datetime_folder()` helper

2. **core/services/path_service.py**
   - Update `determine_documents_location()` parameter name and logic
   - Fix the path calculation to work with base forensic path

3. **ui/main_window.py**
   - Remove business logic from `generate_reports()` method (lines 495-511)
   - Replace with single call to WorkflowController

### Order of Implementation

1. **First**: Implement the WorkflowController changes
2. **Second**: Update PathService to work with base paths
3. **Third**: Simplify MainWindow to use the new controller method
4. **Test**: Verify both Forensics tab and Batch processing work correctly

---

## Testing Checklist

### Test Scenarios

#### 1. Forensics Tab - Single File
- [ ] Copy a single file
- [ ] Verify Documents folder at correct level
- [ ] Verify all reports generated

#### 2. Forensics Tab - Folder with Structure
- [ ] Copy a folder with subfolders
- [ ] Verify Documents folder at location level (NOT inside copied folder)
- [ ] Verify folder structure preserved
- [ ] Verify reports reference correct files

#### 3. Batch Processing
- [ ] Process multiple jobs
- [ ] Verify Documents folder placement for each job
- [ ] Ensure no regression in batch processing

#### 4. Template Settings
- [ ] Test with `"documentsPlacement": "occurrence"`
- [ ] Test with `"documentsPlacement": "location"`
- [ ] Test with `"documentsPlacement": "datetime"` (if supported)

#### 5. Edge Cases
- [ ] Empty folder structure
- [ ] Very deep folder nesting
- [ ] Special characters in folder names
- [ ] Missing template (should use default)

### Expected Results

For all tests with `"documentsPlacement": "location"`:
```
OccurrenceNumber/
└── Business @ Location/
    ├── Documents/              ← Documents here (Level 2)
    │   ├── Time_Offset_Report.pdf
    │   ├── Upload_Log.pdf
    │   └── Hash_Verification.csv
    └── DateTime_Folder/
        └── [Copied files/folders with preserved structure]
```

---

## Benefits of This Fix

### 1. Fixes the Bug
- Documents folder will be placed correctly regardless of preserved folder structure
- Consistent behavior between Forensics tab and Batch processing

### 2. Improves Architecture
- Removes business logic from MainWindow (UI layer)
- Consolidates path logic in WorkflowController
- Makes the code more maintainable and testable

### 3. Future-Proofs the Code
- Easier to add new document placement options
- Cleaner separation of concerns
- Single source of truth for path determination

---

## Additional Notes

### Why This Bug Happened
The original code assumed file paths would always have a predictable structure, but when folder preservation was added, this assumption broke. The refactor to move business logic out of MainWindow was incomplete, leaving path determination logic in the UI layer where it couldn't properly handle the complexity.

### Alternative Solutions Considered
1. **Quick fix in PathService only**: Would work but leaves business logic in MainWindow
2. **Store base path separately**: Adds complexity and state management
3. **Complete refactor** (chosen): Fixes both the bug and the architecture

### Related Files for Reference
- Template file: `docs3/Tempate Builder/Templates/Default_Forensic_Structure.json`
- Batch processor (working correctly): `core/workers/batch_processor.py`
- Current PathService: `core/services/path_service.py`
- Current MainWindow: `ui/main_window.py`

---

## Contact & Questions

This document was prepared as a comprehensive handoff for fixing the Documents folder placement bug and completing the MainWindow refactor. The solution addresses both the immediate bug and the underlying architectural issue.

Key principle: **UI should orchestrate, Controllers should coordinate, Services should implement.**