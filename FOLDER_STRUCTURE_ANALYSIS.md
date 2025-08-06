# Folder Structure Analysis - Complete Breakdown

## Overview
This document provides a comprehensive analysis of how the Folder Structure Application creates both unzipped and zipped folder hierarchies, including the exact source of each folder name from the form fields.

## Form Fields Available
Based on `core/models.py` FormData class:

| Field Name | Type | Description | Example Value |
|------------|------|-------------|---------------|
| `occurrence_number` | string | Case/incident number | "2024-12345" |
| `business_name` | string | Business name (optional) | "ABC Electronics Store" |
| `location_address` | string | Physical address | "123 Main Street, Suite 100" |
| `extraction_start` | QDateTime | Start date/time of extraction | "2024-01-15T10:00:00" |
| `extraction_end` | QDateTime | End date/time of extraction | "2024-01-15T14:30:00" |
| `time_offset` | string | DVR time offset | "DVR is 2 hr 0 min 0 sec AHEAD of realtime" |
| `dvr_time` | QDateTime | DVR timestamp | "2024-01-15T09:15:00" |
| `real_time` | QDateTime | Real world time | "2024-01-15T10:00:00" |
| `technician_name` | string | Technician's name | "John Smith" |
| `badge_number` | string | Badge/ID number | "B1234" |
| `upload_timestamp` | QDateTime | Upload time | "2024-01-15T16:00:00" |

## Unzipped Folder Structure

### Location: `controllers/folder_controller.py` and `core/templates.py`

The unzipped folder structure is created in `FolderController.build_forensic_structure()` and `FolderBuilder.build_forensic_structure()`.

### Current Structure:
```
output/
└── {occurrence_number}/                    # Level 1: Root folder
    └── {business_name} @ {location_address}/   # Level 2: Business @ Location (or just location)
        └── {start_datetime} - {end_datetime}/  # Level 3: Date range
            └── [copied files and folders]
```

### Detailed Folder Name Construction:

#### Level 1: Occurrence Number Folder
- **Source Field**: `form_data.occurrence_number`
- **Code Location**: `folder_controller.py:22` and `templates.py:90`
- **Format**: Direct use of occurrence number
- **Example**: `2024-12345`

#### Level 2: Business @ Location Folder
- **Source Fields**: `form_data.business_name` and `form_data.location_address`
- **Code Location**: `folder_controller.py:24-28` and `templates.py:92-96`
- **Logic**:
  ```python
  if form_data.business_name:
      level2 = f"{form_data.business_name} @ {form_data.location_address}"
  else:
      level2 = form_data.location_address
  ```
- **Example with business**: `ABC Electronics Store @ 123 Main Street, Suite 100`
- **Example without business**: `123 Main Street, Suite 100`
- **Sanitization**: Invalid characters (`<>:"|?*`) replaced with underscores

#### Level 3: DateTime Range Folder
- **Source Fields**: `form_data.extraction_start` and `form_data.extraction_end`
- **Code Location**: `folder_controller.py:30-38` and `templates.py:98-107`
- **Format**: 
  - Start: `yyyy-MM-dd_HHmm` format
  - End: `yyyy-MM-dd_HHmm` format
  - Combined: `{start} - {end}`
- **Example**: `2024-01-15_1000 - 2024-01-15_1430`
- **Fallback**: If dates not set, uses current datetime for both start and end

### Documents Folder (Reports)
- **Location**: Reports are saved separately
- **Path**: `output/{occurrence_number}/Documents/`
- **Contains**: PDF reports (Time Offset, Technician Log, Hash CSV)

## Zipped Folder Structure

### Location: `utils/zip_utils.py`

The ZIP creation happens in `ZipUtility.create_multi_level_archives()` method.

### ZIP File Naming:

#### Root Level ZIP (Primary Archive)
- **Code Location**: `zip_utils.py:126-140`
- **Source Fields**: 
  - `form_data.occurrence_number`
  - `form_data.business_name` (optional)
  - `form_data.location_address` (optional)
- **Format Construction**:
  ```python
  name_parts = [occurrence]
  if business:
      name_parts.append(business)
  if location:
      name_parts.append(f"@ {location}")
  name_parts.append("Video Recovery")
  archive_name = " ".join(name_parts) + ".zip"
  ```
- **Example with all fields**: `2024-12345 ABC Electronics Store @ 123 Main Street, Suite 100 Video Recovery.zip`
- **Example without business**: `2024-12345 @ 123 Main Street, Suite 100 Video Recovery.zip`
- **Fallback Format** (no form_data): `{folder_name}_Complete.zip`

#### Location Level ZIP (Optional)
- **Code Location**: `zip_utils.py:148-155`
- **Format**: `{folder_name}_Location.zip`
- **Example**: `ABC_Electronics_Store_@_123_Main_Street,_Suite_100_Location.zip`

#### DateTime Level ZIP (Optional)
- **Code Location**: `zip_utils.py:158-166`
- **Format**: `{folder_name}_DateTime.zip`
- **Example**: `2024-01-15_1000_-_2024-01-15_1430_DateTime.zip`

## Key Differences Between Zipped and Unzipped

### 1. Root Folder/ZIP Name
- **Unzipped**: Simple occurrence number (e.g., `2024-12345`)
- **Zipped**: Full descriptive name with occurrence, business, location, and "Video Recovery" suffix

### 2. Archive Structure
- **Unzipped**: Direct folder hierarchy on disk
- **Zipped**: Preserves internal folder structure but ZIP file itself has descriptive name

### 3. Path Preservation
- **Code Location**: `zip_utils.py:76-77`
- When zipping, the relative path is calculated from the source's parent:
  ```python
  arcname = file.relative_to(source_path.parent)
  ```
- This means the ZIP contains the full folder hierarchy starting from the occurrence number

## File Operation Flow

1. **Folder Creation**: 
   - `FolderController.build_forensic_structure()` creates the physical folder structure
   - Returns the full path to the created structure

2. **File Copying**:
   - `FolderStructureThread` copies files preserving folder hierarchies
   - Files maintain their relative paths within the structure

3. **ZIP Creation** (if enabled):
   - `ZipOperationThread` creates archives
   - Uses `ZipUtility.create_multi_level_archives()`
   - ZIP name is descriptive, but internal structure matches unzipped

## Settings That Affect Structure

From QSettings:
- `zip_at_root`: Create ZIP at occurrence level (default: True)
- `zip_at_location`: Create ZIP at business/location level (default: False)
- `zip_at_datetime`: Create ZIP at datetime level (default: False)
- `zip_compression_level`: ZIP compression type (default: ZIP_STORED - no compression)

## Path Sanitization

All folder names go through sanitization (`templates.py:72-80`):
- Invalid characters replaced: `<>:"|?*` → `_`
- Leading/trailing spaces removed
- Leading/trailing dots removed

## Summary of Issues

Based on this analysis, the main discrepancy appears to be:

1. **Unzipped root folder**: Uses only `occurrence_number`
2. **ZIP file name**: Uses full descriptive format with occurrence, business, location, and "Video Recovery"

This means when extracting a ZIP, the root folder inside will be just the occurrence number, but the ZIP file itself has the full descriptive name.