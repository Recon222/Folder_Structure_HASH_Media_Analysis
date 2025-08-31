# Custom Template Builder Design - Pragmatic UI/UX Approach

## Overview Philosophy

The Custom Template Builder follows the same pragmatic approach as the existing template manager: powerful enough to be useful, simple enough that anyone can use it without training. No complex visual designers or drag-and-drop builders - just straightforward forms that create exactly what users need.

## Main Interface Design

### Window Layout

The builder opens as a modal dialog, similar size to the template manager (900x700 pixels). It uses a simple two-panel design:

**Left Panel - Template Properties**
- Template name text field
- Description text area (3 lines)
- Agency/organization text field
- Save button
- Cancel button

**Right Panel - Folder Structure Builder**
- Visual preview of the folder structure being built
- Controls to add and modify folder levels
- Real-time preview updates as you type

## Core Interface Components

### The Folder Level Builder

Each folder level appears as a horizontal card with these elements:

**Level Card Design**
- Gray background card with rounded corners
- Number badge on the left (Level 1, Level 2, etc.)
- Main content area in the middle
- Delete button (red X) on the right
- Up/Down arrows to reorder levels

**Inside Each Level Card**

The card contains a row of components that build the folder name:

1. **Component Type Dropdown** (first element)
   - Static Text
   - Form Field
   - Current Date
   - Current Year
   - Counter

2. **Configuration Area** (changes based on type selected)

### Component Type Configurations

**When "Static Text" is selected:**
- Single text field appears
- User types exactly what they want (like "Documents" or "Evidence")
- This text appears the same in every folder structure

**When "Form Field" is selected:**
- Dropdown appears with available fields:
  - Occurrence Number
  - Business Name  
  - Location Address
  - Video Start Date/Time
  - Video End Date/Time
  - Technician Name
  - Any other form fields

**When "Current Date" is selected:**
- Format dropdown appears:
  - Military (30JUL25)
  - ISO (2025-07-30)
  - US Format (07-30-2025)
  - Custom (with format builder)

### Adding Prefixes and Suffixes

Each form field component has three text fields in a row:
- **Prefix field** (optional) - like "CASE-" or "FILE_"
- **Form field dropdown** (middle) - shows selected field name
- **Suffix field** (optional) - like "_EVIDENCE" or "-FINAL"

Example visual:
```
[CASE-] [Occurrence Number▼] [_2025]
```
Would produce: CASE-PR123456_2025

### Building Complex Folder Names

Users can add multiple components to a single level using the "+" button:

**Level 2 folder name builder:**
```
[Form Field▼: Business Name] [+]
[@] [+]  
[Form Field▼: Location Address] [+]
```
Result: "Shoppers Drug Mart @ 123 Main Street"

### Conditional Logic (Simple Version)

For fields that might be empty, a checkbox appears:
- ☑ "Skip this component if field is empty"
- ☑ "Use fallback text if empty" [text field for fallback]

This handles the business/location scenario without complex programming.

## Adding Folder Levels

### The "Add Level" Button

Large blue button at the bottom of the structure list:
**"+ Add Folder Level"**

Clicking it adds a new level card with:
- Default configuration set to "Static Text" 
- Empty text field ready for input
- Automatically numbered (Level 3, Level 4, etc.)

### Quick Templates

Dropdown button next to "Add Folder Level":
**"Add Common Structure ▼"**
- Add Date/Time Level
- Add Location Level  
- Add Documents Folder
- Add Evidence Type Folders

These insert pre-configured level cards that users can modify.

## Live Preview Panel

### Preview Section (Bottom of Right Panel)

Shows the folder structure as it will appear:

**Preview with Sample Data:**
```
📁 PR2025-12345
  └── 📁 Shoppers Drug Mart @ 405 Belsize Dr
       └── 📁 30JUL25_1430_to_30JUL25_1630_DVR_Time
            └── 📁 Documents
            └── 📁 Evidence
```

**Toggle for Preview Mode:**
- "Show with sample data" (default)
- "Show with field names"

When showing field names:
```
📁 {Occurrence Number}
  └── 📁 {Business Name} @ {Location Address}
       └── 📁 {Start Date}_to_{End Date}_DVR_Time
```

## Special Folders Configuration

### Documents Folder Placement

Radio button group in template properties:
- ⚪ No documents folder
- ⚪ At root level (Level 1)
- ⚫ At location level (Level 2) 
- ⚪ At date/time level (Level 3)
- ⚪ Custom level [dropdown of created levels]

### Archive Naming Pattern

Separate section at bottom of properties panel:

**"ZIP Archive Naming"**
Uses the same component builder as folder levels:
```
[Form Field▼: Occurrence Number] [+]
[Static Text: "_"] [+]
[Form Field▼: Business Name] [+]
[Static Text: "_Recovery.zip"] 
```

## User Workflow

### Creating a Template

1. User clicks "Create Custom Template" from Template Manager
2. Template Builder opens with one default level
3. User enters template name like "Vancouver Police Department"
4. User configures Level 1:
   - Selects "Form Field" from dropdown
   - Chooses "Occurrence Number"
   - Adds prefix "VPD-"
   - Sees preview update: "📁 VPD-PR2025-12345"

5. User clicks "+ Add Folder Level"
6. Configures Level 2 as static text: "Evidence"
7. Adds Level 3 for dates with military format
8. Sets Documents folder to Level 2
9. Clicks Save

### Editing Existing Templates

1. User selects template in manager and clicks "Edit"
2. Template Builder opens with all levels populated
3. User can:
   - Modify any level
   - Reorder levels with arrows
   - Delete levels
   - Add new levels
4. Preview updates in real-time
5. Save overwrites the existing template

## Smart Defaults and Helpers

### Form Field Intelligence

When a date/time field is selected, automatically:
- Suggests date format options
- Offers common patterns like "_to_" for ranges
- Provides DVR_Time suffix as option

### Validation Helpers

Red text appears below fields when:
- Template name is empty
- No levels are defined
- Circular references detected
- Invalid characters used in static text

### Common Patterns Library

Dropdown menu "Insert Common Pattern":
- Case-Date-Location
- Agency-Division-Case
- Date-Time-Duration
- Evidence-Type-Sequential

Selecting one pre-populates the builder with a starting structure.

## Save and Test

### Save Options

Two buttons at bottom:
- **"Save and Close"** - Saves template and returns to manager
- **"Save and Test"** - Saves then shows test dialog

### Test Dialog

Simple modal with:
- Form fields to enter test data
- Generate button
- Result preview showing exact folder structure
- "Looks good!" or "Edit template" buttons

## What This Design Deliberately Omits

### No Complex Features
- No scripting or formulas
- No if/then/else builders
- No regular expressions
- No custom functions
- No variables or calculations

### No Visual Complexity
- No drag and drop
- No connection lines
- No flowcharts
- No node editors
- No timeline views

### Why These Omissions Are Good

Users need to create folder structures, not program computers. Every agency interviewed wants the same thing: their specific folder structure working reliably. This design delivers exactly that without the learning curve of a visual programming environment.

## Responsive Design Elements

### Adaptive Component Width
Components expand to fill available space, text truncates with ellipsis when too long.

### Error Prevention
- Disable save when template invalid
- Prevent deletion of last level
- Warn before closing with unsaved changes
- Auto-save draft every 60 seconds

### Keyboard Shortcuts
- Tab moves between components
- Enter adds new component
- Delete removes selected component
- Ctrl+S saves template
- Escape cancels without saving

## Integration with Existing System

### Where It Appears
- Button in Template Manager: "Create Custom Template"
- Menu item: Tools → Template Builder
- Right-click in template list: "Create New Template"

### What It Produces
Standard JSON template file saved to templates/custom/ directory, immediately available in dropdown.

### No Migration Required
Existing templates continue working, can be edited in builder or JSON editor.

## Success Metrics

A user should be able to:
1. Create a basic 3-level template in under 2 minutes
2. Understand every option without documentation
3. Test their template before saving
4. Modify existing templates without breaking them
5. Share templates with other agencies easily

## Summary

This Template Builder design follows the same philosophy that makes the rest of the application successful: solve the real problem without creating new ones. It's powerful enough to create any folder structure an agency needs, yet simple enough that the receptionist could create a template during a coffee break.

The interface is immediately understandable - dropdowns, text fields, and buttons that do exactly what they say. No abstraction, no complexity, just a straightforward tool that creates folder structures.

This is the difference between enterprise software that requires training and professional software that just works.