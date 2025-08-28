# Template Examples

This directory contains sample templates demonstrating various features of the Folder Structure Template System.

## Available Examples

### 1. RCMP Complete Example (`rcmp_complete_example.json`)
- **Template ID**: `rcmp_advanced`
- **Description**: Complete RCMP folder structure with metadata tracking
- **Features**: 
  - ISO date formatting
  - Complex conditional patterns
  - Evidence-focused archive naming
  - Comprehensive metadata
- **Use Case**: Royal Canadian Mounted Police digital forensics operations

**Example Output Structure:**
```
FILE_2024-001_2025/
├── 123_Main_Street_Corner_Store/
│   └── 2025-07-30_16:30:00_to_2025-07-30_18:00:00_UTC/
│       ├── [files here]
│       └── Documents/
└── Documents/  ← Reports placed here (documentsPlacement: "occurrence")
```

### 2. Simple Agency Example (`simple_agency_example.json`)
- **Template ID**: `simple_agency`
- **Description**: Straightforward three-level structure for small agencies
- **Features**:
  - Military date formatting
  - Simple conditional patterns
  - Clean archive naming
- **Use Case**: Small to medium law enforcement agencies

**Example Output Structure:**
```
CASE_2024-001/
├── Corner_Store_123_Main_Street/
│   ├── 30JUL25_1630/
│   │   ├── [files here]
│   │   └── Documents/  ← Reports placed here (documentsPlacement: "location")
│   └── Documents/
└── Documents/
```

### 3. Advanced Features Example (`advanced_features_example.json`)
- **Template ID**: `advanced_features_demo` and `minimal_example`
- **Description**: Demonstrates all available template features
- **Features**:
  - Prefixes and suffixes
  - Four-level folder structure
  - Complex archive naming patterns
  - Multiple templates in one file
  - Technician information fields
- **Use Case**: Reference for creating sophisticated templates

**Example Output Structure (advanced_features_demo):**
```
CASE_2024-001_EVIDENCE/
├── BUSINESS_Corner_Store@123_Main_Street/
│   ├── VIDEO_30JUL25_1630_TO_30JUL25_1800/
│   │   ├── TECH_John_Smith_BADGE_12345/
│   │   │   ├── [files here]
│   │   │   └── Documents/  ← Reports placed here (documentsPlacement: "datetime")
│   │   └── Documents/
│   └── Documents/
└── Documents/
```

## Available Template Fields

Templates can use the following form fields in their patterns:

### Core Fields
- `{occurrence_number}` - Case/occurrence number
- `{business_name}` - Business/establishment name
- `{location_address}` - Address/location
- `{technician_name}` - Technician name (from settings)
- `{badge_number}` - Badge number (from settings)

### Date/Time Fields
- `{video_start_datetime}` - Video start time
- `{video_end_datetime}` - Video end time
- `{current_datetime}` - Current processing time
- `{current_date}` - Current date only
- `{year}` - Current year
- `{extraction_start}` - Extraction start time
- `{extraction_end}` - Extraction end time

### Date Formatting Options
- `"dateFormat": "military"` - Format: 30JUL25_1630
- `"dateFormat": "iso"` - Format: 2025-07-30_16:30

## Template Structure Reference

### Basic Template Structure
```json
{
  "version": "1.0.0",
  "templates": {
    "template_id": {
      "templateName": "Human Readable Name",
      "templateDescription": "Optional description",
      "structure": {
        "levels": [
          {
            "pattern": "{occurrence_number}",
            "fallback": "FALLBACK_VALUE",
            "dateFormat": "military|iso",
            "prefix": "PREFIX_",
            "suffix": "_SUFFIX",
            "conditionals": {
              "business_only": "Pattern when only business available",
              "location_only": "Pattern when only location available", 
              "neither": "Pattern when neither available"
            }
          }
        ]
      },
      "documentsPlacement": "occurrence|location|datetime",
      "archiveNaming": {
        "pattern": "{occurrence_number}_Archive.zip",
        "fallbackPattern": "Archive.zip"
      },
      "metadata": {
        "author": "Template Author",
        "agency": "Agency Name",
        "version": "1.0.0",
        "tags": ["tag1", "tag2"]
      }
    }
  }
}
```

### Conditional Patterns

Templates support conditional patterns for handling missing data:

- `business_only`: Used when business name is available but location is not
- `location_only`: Used when location address is available but business name is not
- `neither`: Used when neither business name nor location address is available

### Documents Placement Options

- `"occurrence"`: Place documents in the first level (occurrence) folder
- `"location"`: Place documents in the second level (location) folder
- `"datetime"`: Place documents in the deepest (datetime) folder

## Usage Instructions

### Importing Templates

1. **Via Forensic Tab Template Selector:**
   - Click the ⚙ (settings) button next to template dropdown
   - Select "Import Template..."
   - Choose a sample JSON file
   - Follow validation and preview steps

2. **Via Main Menu:**
   - Go to Templates → Import Template... (Ctrl+Shift+I)
   - Select sample file and import

### Testing Templates

1. Load any sample file using import dialog
2. Use the Preview tab to see folder structure with sample data
3. Modify sample data to test different scenarios
4. Check Validation tab for any issues

### Creating Custom Templates

1. Start with `simple_agency_example.json` as a base
2. Modify template ID, name, and patterns
3. Test with sample data in import dialog
4. Save and import your custom template

## Validation Notes

All sample templates have been designed to pass validation:
- ✅ Security validation (no unsafe patterns)
- ✅ Business logic validation (proper structure)
- ✅ Performance validation (reasonable complexity)
- ✅ Field reference validation (all fields exist)
- ✅ Pattern validation (proper syntax)

## Support

For questions about template creation or usage, see:
- Template Documentation in main menu (Templates → Template Documentation)
- Template selector "About Templates" option
- Application logs for troubleshooting import issues