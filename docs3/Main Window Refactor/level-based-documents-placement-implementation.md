# Level-Based Documents Placement Implementation Guide

## Executive Summary

This document outlines the implementation of a **level-based documents placement system** that completely replaces the current named placement approach ("occurrence", "location", "datetime"). The new system uses numeric levels (0, 1, 2, etc.) to specify where the Documents folder should be placed, making it work with any template structure regardless of what each level represents. No backward compatibility is maintained - the old system will be completely removed.

## Current System Problems

### 1. Hardcoded Assumptions
The current system assumes:
- Level 0 (first) = occurrence number
- Level 1 (second) = business/location
- Level 2 (third) = datetime

But templates can have ANY structure:
```json
// A valid template that breaks current assumptions:
"levels": [
  { "pattern": "{business_name}" },        // Level 0: Business
  { "pattern": "{year}_{month}" },         // Level 1: Date  
  { "pattern": "{occurrence_number}" },    // Level 2: Occurrence
  { "pattern": "Evidence_{technician}" }   // Level 3: Technician
]
```

### 2. Limited Flexibility
- Can't handle templates with more or fewer than 3 levels
- Can't handle reordered levels
- Can't place documents at arbitrary levels (e.g., level 4 in a 5-level structure)

### 3. Confusing Semantics
- "location" doesn't mean anything if template doesn't have a location level
- Users must understand the template structure to know what "occurrence" means

## New Level-Based System

### Schema Change

**Remove Old Schema (template_schema.py):**
```python
# DELETE THIS:
"documentsPlacement": {
    "type": "string",
    "enum": ["occurrence", "location", "datetime"],
    "default": "location",
    "description": "Where to place PDF documents"
}
```

**New Schema:**
```python
"documentsPlacement": {
    "type": "integer",
    "minimum": 0,
    "maximum": 9,
    "default": 1,
    "description": "Zero-based level index for documents placement (0=first level, 1=second level, etc.)"
}
```

Clean and simple - only accepts integers.

### How Level-Based Placement Works

Given a template with N levels and `documentsPlacement = X`:
1. Build the full path to the deepest level (base_forensic_path)
2. Count total levels in the template
3. Navigate from deepest level up to level X
4. Place Documents folder at that level

**Example:**
```python
# Template has 3 levels, documentsPlacement = 1
# base_forensic_path = /output/Level0/Level1/Level2
# 
# Level 0: /output/Level0
# Level 1: /output/Level0/Level1           <- Documents here
# Level 2: /output/Level0/Level1/Level2

# Calculate steps up from deepest:
steps_up = (total_levels - 1) - documentsPlacement
# steps_up = (3 - 1) - 1 = 1

# Navigate up 1 level from base_forensic_path
target = base_forensic_path.parent  # Goes from Level2 to Level1
```

## Implementation Details

### 1. Update PathService (`core/services/path_service.py`)

**Replace the entire determine_documents_location method:**
```python
def determine_documents_location(self, base_forensic_path: Path, output_directory: Path) -> Result[Path]:
    """
    Determine where to place the Documents folder based on template level settings
    
    Args:
        base_forensic_path: The deepest level path (e.g., datetime folder)
        output_directory: Base output directory
        
    Returns:
        Result containing the Documents folder path
    """
    try:
        self._log_operation("determine_documents_location", f"base_path: {base_forensic_path}")
        
        # Get the template and its documentsPlacement setting
        template = self._templates.get(self._current_template_id)
        if not template:
            documents_placement = 1  # Default to level 1
        else:
            documents_placement = template.get('documentsPlacement', 1)
        
        # Validate it's an integer
        if not isinstance(documents_placement, int):
            self._log_operation(
                "documents_placement_error",
                f"Invalid documentsPlacement type: {type(documents_placement)}, using default level 1",
                "warning"
            )
            documents_placement = 1
        
        # Calculate level-based placement
        documents_dir = self._calculate_level_based_placement(
            base_forensic_path, 
            output_directory, 
            documents_placement,
            template
        )
        
        # Create the Documents directory
        documents_dir.mkdir(parents=True, exist_ok=True)
        self._log_operation("documents_location", f"Created at: {documents_dir}")
        return Result.success(documents_dir)
        
    except Exception as e:
        error = FileOperationError(
            f"Failed to determine documents location: {e}",
            user_message="Failed to determine where to place documents."
        )
        self._handle_error(error, {'method': 'determine_documents_location'})
        return Result.error(error)

def _calculate_level_based_placement(
    self, 
    base_forensic_path: Path, 
    output_directory: Path,
    level_index: int,
    template: dict
) -> Path:
    """
    Calculate documents placement using level index
    
    Args:
        base_forensic_path: Deepest level path
        output_directory: Root output directory
        level_index: Zero-based index of desired level
        template: Template configuration
        
    Returns:
        Path where Documents folder should be placed
    """
    # Get the number of levels in the template
    levels = template.get('structure', {}).get('levels', [])
    total_levels = len(levels)
    
    if total_levels == 0:
        # No levels defined, use output directory
        self._log_operation("level_placement", "No levels in template, using output directory")
        return output_directory / "Documents"
    
    # Validate level index
    if level_index >= total_levels:
        self._log_operation(
            "level_placement_warning", 
            f"Level {level_index} exceeds template levels ({total_levels}), using deepest level",
            "warning"
        )
        return base_forensic_path / "Documents"
    
    if level_index < 0:
        self._log_operation(
            "level_placement_warning",
            f"Invalid level {level_index}, using default level 1",
            "warning"
        )
        level_index = min(1, total_levels - 1)
    
    # Calculate how many levels up from the base path
    # base_forensic_path is at level (total_levels - 1)
    current_level = total_levels - 1
    steps_up = current_level - level_index
    
    self._log_operation(
        "level_calculation",
        f"Total levels: {total_levels}, Target level: {level_index}, Steps up: {steps_up}"
    )
    
    # Navigate up from base path
    target_path = base_forensic_path
    for _ in range(steps_up):
        if target_path.parent == target_path:
            # Reached root, can't go higher
            break
        target_path = target_path.parent
    
    return target_path / "Documents"

# DELETE the _calculate_named_placement method entirely - no longer needed
```

### 2. Update Batch Processor (`core/workers/batch_processor.py`)

**Replace hardcoded placement at line 627:**
```python
def _generate_reports(self, job: BatchJob, output_path: Path, file_results: Dict) -> Dict:
    """Generate reports for the job with template-aware placement"""
    try:
        from ..pdf_gen import PDFGenerator
        from core.services.service_registry import get_service
        from core.services.interfaces import IPathService
        
        # Get PathService for documents placement
        path_service = get_service(IPathService)
        
        # output_path is the datetime folder (deepest level)
        # Use PathService to determine correct documents location
        documents_result = path_service.determine_documents_location(
            output_path,  # This is already the base forensic path
            Path(job.output_directory)
        )
        
        if documents_result.success:
            reports_dir = documents_result.value
            logger.info(f"Documents will be placed at: {reports_dir}")
        else:
            # Fallback to legacy behavior
            logger.warning("Failed to determine documents location, using legacy placement")
            reports_dir = output_path.parent / "Documents"
            reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Continue with report generation...
        pdf_gen = PDFGenerator()
        generated_reports = {}
        
        # ... rest of the method remains the same
```

### 3. Update ALL Template Files

**Convert all existing templates to use numeric levels:**

```json
// OLD:
"documentsPlacement": "location"

// NEW:
"documentsPlacement": 1
```

**Conversion mapping:**
- `"occurrence"` → `0`
- `"location"` → `1`
- `"datetime"` → `2`

**Example updated template:**
```json
{
  "version": "1.0.0",
  "templates": {
    "default_forensic": {
      "templateName": "Default Forensic Structure",
      "templateDescription": "Standard forensic folder structure",
      "structure": {
        "levels": [
          {
            "pattern": "{occurrence_number}",
            "fallback": "NO_OCCURRENCE"
          },
          {
            "pattern": "{business_name} @ {location_address}",
            "conditionals": {
              "business_only": "{business_name}",
              "location_only": "{location_address}",
              "neither": "NO_LOCATION"
            }
          },
          {
            "pattern": "{video_start_datetime}_to_{video_end_datetime}_DVR_Time",
            "dateFormat": "military",
            "fallback": "{current_datetime}"
          }
        ]
      },
      "documentsPlacement": 1,  // Level 1 (second level, 0-indexed)
      "archiveNaming": {
        "pattern": "{occurrence_number}_Recovery.zip",
        "fallbackPattern": "Evidence.zip"
      }
    }
  }
}
```

### 4. Update ForensicPathBuilder Fallback

**The Issue:** ForensicPathBuilder is used as a fallback when template building fails. It creates a hardcoded 3-level structure that assumes:
- Level 0 = occurrence number
- Level 1 = business @ location  
- Level 2 = datetime

**Update `core/path_utils.py`:**
Since ForensicPathBuilder creates a fixed 3-level structure, we need to ensure it works with level-based placement. When ForensicPathBuilder is used as fallback, PathService should:
1. Know that it's using the fallback (3-level structure)
2. Map the level index correctly for this structure

**Alternative: Remove ForensicPathBuilder entirely** and always use templates. Create a hardcoded default template that matches ForensicPathBuilder's behavior.

### 5. Clean Up Code

**Remove from PathService:**
- Delete all references to "occurrence", "location", "datetime" string checks
- Delete the `_calculate_named_placement` method
- Delete the `find_occurrence_folder` method if only used for legacy placement
- Consider removing ForensicPathBuilder entirely (replace with default template)

**Update Template Validator:**
- Remove string validation for documentsPlacement
- Only accept integers 0-9

**Update Batch Processor:**
- Line 616: Replace `ForensicPathBuilder.build_relative_path()` with template-based path building
- Use PathService for all path building

## Benefits of Level-Based System

### 1. Universal Compatibility
Works with ANY template structure:
- 2-level templates
- 5-level templates
- Templates with unconventional ordering

### 2. Clear and Intuitive
- "Place at level 1" is unambiguous
- No need to understand template semantics
- Visual correspondence with folder hierarchy

### 3. Future-Proof
- New template structures don't require code changes
- Can handle arbitrary depth
- Simple to explain and document

### 4. Clean Implementation
- No legacy code to maintain
- Simple, straightforward logic
- Easy to understand and debug

## Testing Plan

### Test Cases

1. **3-Level Template, Level 0**
   ```
   Expected: OccurrenceNumber/Documents/
   ```

2. **3-Level Template, Level 1**
   ```
   Expected: OccurrenceNumber/BusinessLocation/Documents/
   ```

3. **3-Level Template, Level 2**
   ```
   Expected: OccurrenceNumber/BusinessLocation/DateTime/Documents/
   ```

4. **5-Level Template, Level 3**
   ```
   Expected: Level0/Level1/Level2/Level3/Documents/
   ```

5. **2-Level Template, Level 1**
   ```
   Expected: Level0/Level1/Documents/
   ```

6. **Invalid Level (too high)**
   ```
   Input: Level 5 for 3-level template
   Expected: Use deepest level (Level 2)
   ```

7. **Non-integer Input (Error Case)**
   ```
   Input: "location" (string)
   Expected: Log warning, default to level 1
   ```

### Validation Tests

Create test templates with various structures:
- Reversed order (datetime first, occurrence last)
- Missing traditional levels (no occurrence number)
- Extra levels (technician, evidence type, etc.)
- Single level templates

## Implementation Checklist

- [ ] Update template_schema.py to ONLY accept integer documentsPlacement
- [ ] Remove string enum from schema definition
- [ ] Replace entire determine_documents_location method in PathService
- [ ] Add _calculate_level_based_placement method
- [ ] Delete _calculate_named_placement method
- [ ] Delete find_occurrence_folder method (if not used elsewhere)
- [ ] Fix batch_processor.py to use PathService
- [ ] Update ALL template files to use integers (0, 1, or 2)
- [ ] Update template validator to reject strings
- [ ] Test with forensic tab
- [ ] Test with batch tab
- [ ] Remove all "occurrence", "location", "datetime" string literals from codebase
- [ ] Update template management UI to use numeric spinner (0-9)
- [ ] Update documentation to explain level-based system

## Files to Modify

### Core Changes
1. `core/template_schema.py` - Change documentsPlacement to integer only
2. `core/services/path_service.py` - Complete rewrite of documents placement logic
3. `core/workers/batch_processor.py` - Use PathService instead of hardcoded placement
4. `core/template_validator.py` - Remove string validation for documentsPlacement
5. `core/path_utils.py` - Either update ForensicPathBuilder or remove it entirely

### Template Updates
1. `templates/folder_templates.json` - Convert all to integers
2. `docs3/Tempate Builder/Templates/*.json` - Convert all to integers
3. Any user templates - Convert to integers

### UI Updates (if applicable)
1. Template management dialog - Use number input (0-9) instead of dropdown
2. Template import - Auto-convert strings to integers during import

## Conclusion

The level-based documents placement system provides a clean, robust solution that works with any template structure. By completely removing the old named system, we eliminate all assumptions and limitations. This approach makes the application truly template-agnostic and ready for any folder structure requirements. The implementation is simpler, more maintainable, and easier to understand without any legacy baggage.