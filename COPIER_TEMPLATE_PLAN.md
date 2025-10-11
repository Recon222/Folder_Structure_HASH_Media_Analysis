# Copier Template Implementation Plan: Tauri-Mapbox-Python Bridge Plugin Generator

**Version**: 1.0
**Date**: 2025-10-10
**Purpose**: Educational guide for creating reusable plugin templates
**Target Audience**: Developers who want to UNDERSTAND the process, not just copy-paste

---

## Table of Contents

1. [Introduction: The Template Revolution](#1-introduction-the-template-revolution)
2. [Understanding Copier](#2-understanding-copier)
3. [Pattern Analysis Workshop](#3-pattern-analysis-workshop)
4. [Template Design Session](#4-template-design-session)
5. [Implementation Phases](#5-implementation-phases)
6. [Testing & Validation](#6-testing--validation)
7. [Advanced Techniques](#7-advanced-techniques)
8. [Troubleshooting Guide](#8-troubleshooting-guide)
9. [Future Enhancements](#9-future-enhancements)
10. [Appendix: Quick Reference](#10-appendix-quick-reference)

---

## 1. Introduction: The Template Revolution

### Why This Matters

You've built an incredible vehicle tracking plugin with Tauri + Mapbox + Python integration. Now you need a media analysis plugin with similar architecture. You could:

1. **Copy-paste and rename** (high error rate, difficult to maintain)
2. **Fork the repo** (creates divergence, hard to update)
3. **Create a template** (reusable, maintainable, professional)

This guide teaches you **option 3** - the professional approach.

### What You'll Learn

By the end of this document, you'll understand:

- **Why templates matter** - Reduce duplication, increase consistency
- **How Copier works** - The mechanics of code generation
- **Pattern extraction** - Identifying what varies vs. what stays the same
- **Template design** - Making reusable, flexible templates
- **Jinja2 templating** - Dynamic code generation
- **Testing strategies** - Validating your template works

### The Vision

**The "Kitchen Sink" Philosophy:**

Instead of building a complex template with conditional variants, we're taking a practical approach: **Include everything, let users delete what they don't need.** The vehicle tracking implementation is complete and working - we'll templatize it as-is, giving users a full-featured starting point.

**Before Template:**
```
vehicle_tracking/          (3 weeks to build - COMPLETE!)
├── tauri-map/             ✅ Full WebSocket communication
│   ├── JavaScript/        ✅ Modular architecture (pubsub, animation, timeline)
│   └── Rust backend       ✅ Multi-layer port discovery
├── services/              ✅ Complete bridge service
├── models/                ✅ Data models
└── ui/                    ✅ Qt wrapper

media_analysis/            (Fork & customize - 2-3 hours!)
├── tauri-map/             ← Copy verbatim from vehicle_tracking
├── services/              ← Rename classes/variables
├── models/                ← Adapt data models
└── ui/                    ← Delete animation controls
```

**After Template:**
```bash
# 30 minutes to generate fully-featured plugin
copier copy gh:your-org/tauri-plugin-template media_analysis

? Project name: Media Analysis
? Data type: photos
? Description: Photo GPS visualization

✓ Generated complete plugin in media_analysis/
✓ Includes: Timeline, WebSocket, Animation, Clustering, PubSub
✓ Delete features you don't need (faster than adding them!)
✓ Ready to customize
```

**Key Insight:** Deletion is faster than addition. Users can remove unwanted features in minutes, while building them from scratch would take hours or days.

### Educational Philosophy

This document follows the **70-20-10 learning model**:
- **70% Hands-on** - You'll build the template step-by-step
- **20% Social** - We explain WHY decisions are made
- **10% Formal** - Core concepts and theory

**You will not just copy code. You will understand every line.**

---

## 2. Understanding Copier

### What is Copier?

**Copier** is like a "smart cookie cutter" for code projects.

```
┌─────────────────┐
│   Template      │  ← Defines the shape
│   Directory     │
│  (with {{vars}})│
└────────┬────────┘
         │
         │ copier copy
         ▼
┌─────────────────┐
│   Generated     │  ← Filled in with your answers
│   Project       │
│ (with real code)│
└─────────────────┘
```

**Key Concept**: Copier reads a template directory, asks you questions, and generates a new project by replacing `{{variables}}` with your answers.

### How It Works (Step by Step)

#### Step 1: Questions
Copier reads `copier.yml` and asks questions:
```yaml
# copier.yml
_subdirectory: template

questions:
  plugin_name:
    type: str
    help: "What's your plugin name?"

  data_type:
    type: str
    help: "What data does it display?"
    default: "GPS points"
```

#### Step 2: Templating
Your template files use **Jinja2** syntax to reference answers:
```python
# template/{{plugin_slug}}/models.py
class {{plugin_name}}Data:
    """Data model for {{data_type}}"""
    pass
```

#### Step 3: Generation
Copier replaces variables and creates real files:
```python
# media_analysis/models.py
class MediaAnalysisData:
    """Data model for Photo GPS points"""
    pass
```

### Why Copier vs. Other Options?

| Tool | Pros | Cons | Best For |
|------|------|------|----------|
| **Copier** | Simple, updateable, Python-native | Learning curve | Reusable templates |
| **Cookiecutter** | Popular, mature | No updates after generation | One-time generation |
| **Yeoman** | JS ecosystem | Requires Node.js | Frontend projects |
| **Manual** | Full control | Error-prone, time-consuming | One-off projects |

**We chose Copier because**:
1. Can **update** generated projects when template changes
2. **Python-native** (matches our stack)
3. **Jinja2** templating (familiar from Flask/Django)
4. **Simple** but powerful

### Core Concepts

#### Variables
Things that change between plugins:
```jinja2
plugin_name: "Vehicle Tracking"
data_type: "GPS tracks"
rendering_style: "animated lines"
```

#### Templates
Files with placeholders:
```jinja2
# {{plugin_slug}}/services/{{plugin_slug}}_service.py

class {{plugin_name}}Service:
    """Process {{data_type}}"""
```

#### Answers
Your specific values:
```python
plugin_name = "Media Analysis"
data_type = "Photo GPS points"
```

#### Generated Code
Final output:
```python
# media_analysis/services/media_analysis_service.py

class MediaAnalysisService:
    """Process Photo GPS points"""
```

### Analogy: Mad Libs for Code

Remember **Mad Libs**? You fill in blanks:
```
Once upon a time, there was a [adjective] [noun] who lived in a [place].
                                ↓           ↓              ↓
Once upon a time, there was a  happy      dragon  who lived in a  castle.
```

Copier does the same for code:
```python
class {{plugin_name}}Service:     ← Mad Lib template
      ↓
class MediaAnalysisService:       ← Filled in
```

**But it's smarter** - it also:
- Renames files and directories
- Handles conditionals (if/else)
- Supports loops (for generating multiple files)
- Validates your inputs

### Installation

```bash
# Install Copier
pip install copier

# Verify installation
copier --version
# Expected: copier 9.2.0 (or similar)
```

### Your First Template (5-Minute Exercise)

Let's create a trivial template to understand the basics:

```bash
# Create template structure
mkdir my_first_template
cd my_first_template

# Create copier.yml
cat > copier.yml << 'EOF'
project_name:
  type: str
  help: "What's your project name?"

author:
  type: str
  help: "Your name?"
  default: "Anonymous"
EOF

# Create template file
mkdir -p template
cat > template/README.md << 'EOF'
# {{project_name}}

Created by: {{author}}
EOF

# Generate from template
cd ..
copier copy my_first_template my_project

# It will ask:
# ? What's your project name? My Cool Project
# ? Your name? (Anonymous) Alice

# Check output
cat my_project/README.md
# Output:
# # My Cool Project
#
# Created by: Alice
```

**Checkpoint Questions:**
1. What file defines the questions? (`copier.yml`)
2. What syntax is used for variables? (`{{variable_name}}`)
3. Where does Copier put generated files? (In the directory you specify)

---

## 3. Pattern Analysis Workshop

### The Goal

Before building a template, we need to **understand the pattern**. We'll analyze the existing `vehicle_tracking` plugin to identify:

1. **What changes** between plugins (variables)
2. **What stays the same** (boilerplate)
3. **What needs to be configurable** (options)

### Deep Dive: Vehicle Tracking Structure (Our Complete Reference Implementation)

**IMPORTANT REALIZATION:** The vehicle tracking plugin is MORE complete than initially expected. It's not a prototype - it's a production-ready reference implementation with enterprise-grade architecture.

```
vehicle_tracking/
├── tauri-map/              ← Tauri desktop app (PRODUCTION-READY)
│   ├── src/
│   │   ├── mapbox.html     ← Map UI (2700+ lines) ✅ COMPLETE
│   │   │   ├── WebSocket communication ✅
│   │   │   ├── PubSub event system ✅
│   │   │   ├── Animation engine ✅
│   │   │   ├── Timeline controls ✅
│   │   │   ├── Speed controls ✅
│   │   │   ├── World clock display ✅
│   │   │   └── Modular JavaScript architecture ✅
│   │   ├── js/             ← Modular JavaScript files
│   │   │   ├── mapbox-core.js
│   │   │   ├── timeline-controls.js
│   │   │   ├── animation-engine.js
│   │   │   ├── pubsub.js
│   │   │   └── utils.js
│   │   ├── leaflet.html    ← Alternative provider
│   │   └── index.html      ← Entry point
│   └── src-tauri/
│       ├── src/
│       │   └── main.rs     ← Rust backend (Multi-layer port discovery) ✅
│       └── Cargo.toml      ← Rust dependencies
├── services/
│   ├── tauri_bridge_service.py      ← Python ↔ Tauri bridge ✅
│   ├── vehicle_tracking_service.py  ← Business logic
│   ├── wire_format.py               ← Data serialization
│   └── map_template_service.py      ← HTML template loading
├── models/
│   └── vehicle_tracking_models.py   ← Data structures
├── ui/
│   └── components/
│       └── vehicle_map_widget.py    ← Qt wrapper
└── tests/

**Architecture Highlights:**
- Full bidirectional WebSocket communication (Python ↔ Rust ↔ JavaScript)
- Event-driven PubSub system for decoupled components
- Frame-accurate animation with interpolation
- Complete timeline controls (play/pause/stop/scrubbing)
- World clock for temporal analysis
- Multi-layer port discovery (fallback strategies)
- Modular JavaScript (ready for reuse)
```

**Key Insight:** This isn't a template to BUILD - it's a template to COPY. We're wrapping a complete, working system.

### Critical Insight: Timeline Features Serve Two Purposes

**IMPORTANT DISCOVERY:** The timeline UI controls (scrubber, play/pause, world clock) can drive TWO different behaviors:

#### Use Case 1: Vehicle Tracking (Interpolated Movement)
```javascript
// Timeline drives POSITION INTERPOLATION
function updateFrame(timestamp) {
    vehicles.forEach(vehicle => {
        // Find points before/after current timestamp
        const currentPosition = interpolate(vehicle.path, timestamp);

        // Update marker position (smooth animation)
        marker.setPosition(currentPosition);
    });
}
```
**Result:** Vehicles move smoothly along their paths as timeline progresses.

#### Use Case 2: Media Analysis (Timestamp Filtering)
```javascript
// Timeline drives VISIBILITY FILTERING
function updateFrame(timestamp) {
    photos.forEach(photo => {
        // Photos appear/disappear based on timestamp
        if (photo.timestamp <= timestamp) {
            marker.setVisible(true);   // Show photo
        } else {
            marker.setVisible(false);  // Hide photo (not taken yet)
        }
    });
}
```
**Result:** Photos appear on the map as their capture time is reached in timeline.

#### The Template Implication

**Same UI controls, different update logic!** This means:

1. **Media Analysis DOES need timeline features** (for temporal filtering)
2. **But NOT interpolation logic** (photos don't move)
3. **The template includes BOTH** - users delete what they don't need
4. **Timeline is reusable** - just change the `updateFrame()` implementation

**This validates the "kitchen sink" approach:** Include everything, let users customize the behavior.

### Variance Analysis Table

This is the **key exercise** - what changes vs. what stays the same?

| Component | Vehicle Tracking | Media Analysis | Abstraction | Template Variable |
|-----------|-----------------|----------------|-------------|-------------------|
| **Plugin Name** | "vehicle_tracking" | "media_analysis" | plugin_slug | `{{plugin_slug}}` |
| **Display Name** | "Vehicle Tracking" | "Media Analysis" | plugin_name | `{{plugin_name}}` |
| **Data Type** | GPS tracks with timestamps | Photo GPS points | data_structure | `{{data_structure}}` |
| **Primary Data Class** | `VehicleData` | `MediaData` | DataModel | `{{data_model_name}}` |
| **Point Type** | `GPSPoint` | `GPSPoint` (same) | PointType | Reusable |
| **Service Class** | `VehicleTrackingService` | `MediaAnalysisService` | ServiceClass | `{{plugin_name}}Service` |
| **Map Rendering** | Animated lines + trails | Static markers + clusters | render_mode | `{{render_mode}}` |
| **Animation** | Time-based playback | No animation | has_animation | `{{has_animation}}` |
| **Popup Content** | Speed, time, heading | Thumbnail, EXIF data | popup_fields | `{{popup_fields}}` (list) |
| **Tauri Product Name** | "Vehicle Tracking Map" | "Media Analysis Map" | tauri_name | `{{plugin_name}} Map` |
| **WebSocket Port** | Dynamic (find_free_port) | Dynamic | port_strategy | Reusable |
| **Rust Crate Name** | "tauri-map" | "tauri-map" (same) | crate_name | Fixed |
| **HTML Template** | mapbox.html (animation) | mapbox.html (static) | html_variant | Conditional |

### What We Learned

**High Variance** (needs templating):
- Plugin names (slug, display name, class names)
- Data models and field names
- UI text and labels
- Map rendering logic

**Low Variance** (reusable):
- Tauri ↔ Python bridge architecture
- WebSocket communication pattern
- Qt widget wrapper pattern
- Error handling and logging

**Conditional Logic** (needs if/else):
- Animation controls (only if animated)
- Timeline slider (only if animated)
- Speed controls (only if animated)
- Trail rendering (only if animated)

### Data Flow Mapping

Understanding the **data flow** is crucial:

```
┌──────────────────────────────────────────────────────────────┐
│                    Python Application                        │
│                                                              │
│  ┌────────────────┐    ┌─────────────────┐                │
│  │ Service Layer  │───▶│  Wire Format    │                │
│  │ (Process data) │    │  Converter      │                │
│  └────────────────┘    └────────┬────────┘                │
│                                  │                          │
│                         JSON over WebSocket                │
└─────────────────────────────────┼──────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────┐
│                     Tauri Application                        │
│                                                              │
│  ┌────────────────┐    ┌─────────────────┐                │
│  │ Rust Backend   │───▶│  JavaScript      │                │
│  │ (WebSocket)    │    │  (Map rendering) │                │
│  └────────────────┘    └────────┬────────┘                │
│                                  │                          │
│                         Mapbox GL JS / Leaflet              │
└─────────────────────────────────┼──────────────────────────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │ User Browser │
                            │   (in Tauri) │
                            └──────────────┘
```

**Template Variables Needed**:
- `{{data_model}}` - Python dataclass for your data
- `{{wire_format}}` - Serialization logic
- `{{map_logic}}` - JavaScript rendering
- `{{ui_widget}}` - Qt wrapper class

### Pattern Extraction: Wire Format

Let's examine the **wire format pattern** in detail:

**vehicle_tracking/services/wire_format.py** (excerpts):
```python
def to_wire_format(vehicle_data: VehicleData) -> Dict[str, Any]:
    """Convert vehicle data to wire format."""

    points = []
    for index, point in enumerate(vehicle_data.gps_points):
        wire_point = {
            "index": index,
            "timestamp_ms": int(point.timestamp.timestamp() * 1000),
            "latitude": point.latitude,
            "longitude": point.longitude,
            "speed_kmh": getattr(point, 'segment_speed_kmh', None),
            # Vehicle-specific fields:
            "is_interpolated": point.is_interpolated,
            "is_gap": point.is_gap,
        }
        points.append(wire_point)

    return {
        "vehicle_id": vehicle_data.vehicle_id,  # ← Variable
        "points": points,
        "meta": { ... }
    }
```

**For media_analysis**, this becomes:
```python
def to_wire_format(media_data: MediaData) -> Dict[str, Any]:
    """Convert media data to wire format."""

    items = []  # ← Changed from "points"
    for index, item in enumerate(media_data.media_items):  # ← Changed
        wire_item = {
            "index": index,
            "timestamp_ms": int(item.timestamp.timestamp() * 1000),
            "latitude": item.latitude,
            "longitude": item.longitude,
            # Media-specific fields:
            "thumbnail": item.thumbnail_b64,  # ← New field
            "filename": item.filename,         # ← New field
        }
        items.append(wire_item)

    return {
        "media_id": media_data.media_id,  # ← Changed from vehicle_id
        "items": items,                   # ← Changed from points
        "meta": { ... }
    }
```

**Template Pattern**:
```jinja2
def to_wire_format({{data_var}}: {{DataModel}}) -> Dict[str, Any]:
    """Convert {{data_type}} to wire format."""

    items = []
    for index, item in enumerate({{data_var}}.{{items_field}}):
        wire_item = {
            "index": index,
            "timestamp_ms": int(item.timestamp.timestamp() * 1000),
            "latitude": item.latitude,
            "longitude": item.longitude,
            {% for field in custom_fields %}
            "{{field.name}}": item.{{field.attr}},
            {% endfor %}
        }
        items.append(wire_item)

    return {
        "{{id_field}}": {{data_var}}.{{id_field}},
        "items": items,
        "meta": { ... }
    }
```

**Variables Identified**:
- `data_var`: `vehicle_data` → `media_data`
- `DataModel`: `VehicleData` → `MediaData`
- `data_type`: `"vehicle data"` → `"media data"`
- `items_field`: `gps_points` → `media_items`
- `id_field`: `vehicle_id` → `media_id`
- `custom_fields`: List of plugin-specific fields

### Pattern Extraction: Tauri Main.rs

**vehicle_tracking/tauri-map/src-tauri/src/main.rs** (excerpts):
```rust
fn main() {
    let ws_port = get_ws_port();

    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![get_ws_port, get_map_config])
        .setup(move |app| {
            if let Some(window) = app.get_window("main") {
                // Navigate to mapbox.html
                let script = format!("window.location.href = 'mapbox.html?port={}'", ws_port);
                window.eval(&script).ok();
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

**Template Pattern**:
```rust
// Template: {{plugin_slug}}/tauri-map/src-tauri/src/main.rs

fn main() {
    let ws_port = get_ws_port();

    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![get_ws_port, get_map_config])
        .setup(move |app| {
            if let Some(window) = app.get_window("main") {
                {% if has_animation %}
                // Navigate to mapbox.html with animation support
                {% else %}
                // Navigate to mapbox.html (static mode)
                {% endif %}
                let script = format!("window.location.href = 'mapbox.html?port={}'", ws_port);
                window.eval(&script).ok();
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

**Variables Identified**:
- `plugin_slug`: For file paths
- `has_animation`: Conditional logic
- Most code is **reusable as-is**

### Exercise: Extract Your Own Pattern

Pick a file from `vehicle_tracking` and do this analysis:

1. **Read the file** - Understand what it does
2. **Highlight variables** - What would change for a different plugin?
3. **Identify boilerplate** - What stays the same?
4. **Design template** - How would you make it generic?

**Example**:
```python
# File: vehicle_tracking/ui/components/vehicle_map_widget.py
# Lines 111-120 (excerpt)

class VehicleMapWidget(QWidget):
    """Vehicle map visualization widget"""

    vehicleSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_vehicles: List[VehicleData] = []
        self.template_service = MapTemplateService()
```

**Your Analysis**:
1. **Variables**: `Vehicle`, `VehicleData`, `vehicleSelected`
2. **Boilerplate**: QWidget inheritance, Signal pattern, template service
3. **Template**:
```python
class {{plugin_name}}MapWidget(QWidget):
    """{{plugin_name}} map visualization widget"""

    {{item_name}}Selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_{{items}}: List[{{DataModel}}] = []
        self.template_service = MapTemplateService()
```

---

## 4. Template Design Session

### The Big Picture: Simplified Strategy

**OLD APPROACH (Complex):**
- Design elaborate conditional logic
- Create variants for every feature combination
- Complex copier.yml with many questions
- Estimated time: 18-26 hours

**NEW APPROACH (Kitchen Sink):**
- Copy vehicle_tracking verbatim
- Template ONLY the naming (project_name, data_type, etc.)
- Include ALL features by default
- Users delete what they don't need
- Estimated time: 3-4 hours

Before writing any template code, we need to **design** it. But our design is now dramatically simpler - we're wrapping an existing, complete implementation rather than building variants from scratch.

### Template Directory Structure

```
tauri-mapbox-python-template/
├── copier.yml                    ← Questions and configuration
├── README.md                     ← Template documentation
├── .copier-answers.yml.jinja     ← Store user answers for updates
└── template/                     ← Actual template files
    └── {{plugin_slug}}/          ← Generated plugin directory
        ├── __init__.py.jinja
        ├── {{plugin_slug}}_interfaces.py.jinja
        ├── tauri-map/
        │   ├── src/
        │   │   ├── mapbox.html.jinja
        │   │   └── leaflet.html.jinja
        │   └── src-tauri/
        │       ├── src/
        │       │   └── main.rs.jinja
        │       ├── Cargo.toml.jinja
        │       └── tauri.conf.json.jinja
        ├── services/
        │   ├── tauri_bridge_service.py.jinja
        │   ├── {{plugin_slug}}_service.py.jinja
        │   ├── wire_format.py.jinja
        │   └── map_template_service.py.jinja
        ├── models/
        │   └── {{plugin_slug}}_models.py.jinja
        ├── ui/
        │   └── components/
        │       └── {{plugin_slug}}_map_widget.py.jinja
        └── tests/
            └── test_{{plugin_slug}}.py.jinja
```

**Key Points**:
1. **`.jinja` extension** - Tells Copier this file is a template
2. **`{{plugin_slug}}/`** - Directory name is templated too!
3. **Nested `{{variables}}`** - File names can use variables
4. **Structure mirrors output** - What you see is what you get

### Designing copier.yml: Radically Simplified

**Philosophy Change:** We're not building conditional variants - we're just renaming a complete implementation.

This is the **brain** of your template, but it's now MUCH simpler than originally planned.

#### Basic Structure (Minimalist Approach)

```yaml
# Metadata
_subdirectory: template  # Where to find template files

# Minimum Copier version
_min_copier_version: "9.0.0"

# SIMPLIFIED: Only ask essential questions
# Everything else is included by default
```

#### Question Types

Copier supports various question types:

```yaml
# String input
plugin_name:
  type: str
  help: "Human-readable name (e.g., 'Vehicle Tracking')"
  validator: "{% if not plugin_name %}Required{% endif %}"

# Choice (dropdown)
render_mode:
  type: str
  help: "How should data be displayed?"
  choices:
    - "animated_lines"
    - "static_markers"
    - "clustered_markers"
  default: "static_markers"

# Boolean (yes/no)
has_animation:
  type: bool
  help: "Does this plugin need animation controls?"
  default: false

# Multi-choice
popup_fields:
  type: json
  help: "What fields to show in popups? (JSON array)"
  default: '["timestamp", "speed"]'
```

#### Derived Variables

Some variables can be **computed** from others:

```yaml
plugin_slug:
  type: str
  help: "Plugin module name (snake_case)"
  default: "{{ plugin_name.lower().replace(' ', '_') }}"
  # Example: "Vehicle Tracking" → "vehicle_tracking"

DataModelName:
  type: str
  help: "Main data class name (PascalCase)"
  default: "{{ plugin_name.replace(' ', '') }}Data"
  # Example: "Vehicle Tracking" → "VehicleTrackingData"

tauri_product_name:
  type: str
  help: "Tauri application name"
  default: "{{ plugin_name }} Map"
  # Example: "Vehicle Tracking Map"
```

**Why this matters**: Users only type `plugin_name` once, and all naming conventions are handled automatically!

#### Conditional Questions

Ask follow-up questions based on previous answers:

```yaml
has_animation:
  type: bool
  help: "Enable animation controls?"
  default: false

animation_fps:
  type: int
  help: "Animation frame rate (fps)"
  default: 60
  when: "{{ has_animation }}"  # Only ask if has_animation is true

trail_length:
  type: int
  help: "Trail length in seconds (0 = no trail, -1 = persistent)"
  default: 0
  when: "{{ has_animation }}"
```

#### Validation

Ensure user input is valid:

```yaml
plugin_name:
  type: str
  help: "Plugin name"
  validator: >-
    {% if not plugin_name %}
    Plugin name is required
    {% elif plugin_name|length < 3 %}
    Plugin name must be at least 3 characters
    {% endif %}

websocket_port_strategy:
  type: str
  help: "WebSocket port selection strategy"
  choices:
    - "dynamic"  # Find free port automatically
    - "fixed"    # Use fixed port
  default: "dynamic"

websocket_port:
  type: int
  help: "Fixed WebSocket port (if using 'fixed' strategy)"
  default: 8765
  when: "{{ websocket_port_strategy == 'fixed' }}"
  validator: >-
    {% if websocket_port < 1024 or websocket_port > 65535 %}
    Port must be between 1024 and 65535
    {% endif %}
```

### Designing Templates with Jinja2

#### Jinja2 Basics

Jinja2 uses three types of delimiters:

```jinja2
{{ variable }}         ← Output a variable
{% if condition %}     ← Control structure (if/for/etc)
{# comment #}          ← Comment (not in output)
```

**Example**:
```jinja2
{# This is a comment - won't appear in generated file #}

class {{ DataModelName }}:
    """
    Data model for {{ plugin_name }}.

    {% if has_animation -%}
    Includes animation data.
    {% else -%}
    Static data only.
    {% endif -%}
    """
    pass
```

**Generates** (if `has_animation=True`):
```python
class VehicleTrackingData:
    """
    Data model for Vehicle Tracking.

    Includes animation data.
    """
    pass
```

#### Whitespace Control

**Important**: Jinja2 can create awkward whitespace. Use `-` to strip it:

```jinja2
{# BAD - creates blank lines #}
{% if condition %}
some code
{% endif %}

{# GOOD - strips whitespace #}
{% if condition -%}
some code
{% endif -%}
```

#### Conditional Blocks

Generate entire sections conditionally:

```jinja2
{# Template: services/tauri_bridge_service.py.jinja #}

class TauriBridgeService(BaseService):
    """Bridge between Python and Tauri"""

    {% if has_animation -%}
    def send_animation_command(self, command: str) -> Result[None]:
        """Send animation control command"""
        message = {"type": "animation_control", "command": command}
        return self._send_message(message)
    {% endif -%}

    def send_data(self, data: Dict[str, Any]) -> Result[None]:
        """Send data to Tauri"""
        message = {"type": "load_data", "data": data}
        return self._send_message(message)
```

#### Loops

Generate repetitive code:

```jinja2
{# Generate import statements for custom fields #}
{% for field in custom_fields -%}
from ..models import {{ field.type }}
{% endfor %}

{# Generate property definitions #}
class {{ DataModelName }}:
    {% for field in custom_fields -%}
    {{ field.name }}: {{ field.type }}
    {% endfor %}
```

**If `custom_fields = [{"name": "thumbnail", "type": "str"}, {"name": "altitude", "type": "float"}]`**:

Generates:
```python
from ..models import str
from ..models import float

class MediaAnalysisData:
    thumbnail: str
    altitude: float
```

#### Filters

Transform variables with **filters**:

```jinja2
{# Convert to uppercase #}
{{ plugin_name | upper }}

{# Convert to title case #}
{{ plugin_slug | replace('_', ' ') | title }}

{# Custom logic #}
{% if render_mode == 'animated_lines' -%}
const ANIMATION_ENABLED = true;
{% else -%}
const ANIMATION_ENABLED = false;
{% endif -%}
```

**Common filters**:
- `upper` / `lower` / `title`
- `replace(old, new)`
- `trim` / `strip`
- `default(fallback)` - Use fallback if variable is empty

### Designing for Updates

**Critical Feature**: Copier can **update** generated projects when the template changes!

#### How Updates Work

```bash
# Initial generation
copier copy gh:org/template my-plugin

# Later, template improves
# You can update your plugin:
cd my-plugin
copier update

# Copier will:
# 1. Re-ask questions (showing previous answers)
# 2. Re-generate files
# 3. Smart merge (if you've customized files)
```

#### Storing Answers

Copier stores user answers in `.copier-answers.yml`:

```yaml
# .copier-answers.yml (auto-generated)
_src_path: gh:org/tauri-plugin-template
_commit: abc123def
plugin_name: Vehicle Tracking
plugin_slug: vehicle_tracking
has_animation: true
render_mode: animated_lines
```

**Template for this file**:
```jinja2
{# .copier-answers.yml.jinja #}
_src_path: {{ _copier_conf.src_path }}
_commit: {{ _copier_conf.vcs_ref_hash }}
plugin_name: {{ plugin_name }}
plugin_slug: {{ plugin_slug }}
has_animation: {{ has_animation }}
render_mode: {{ render_mode }}
{# ... more answers #}
```

#### Update Strategies

When you run `copier update`, Copier handles conflicts:

**Strategy 1: Skip Files** (if user heavily customized):
```yaml
# copier.yml
_skip_if_exists:
  - "{{plugin_slug}}/services/custom_logic.py"  # User's custom code
```

**Strategy 2: Inline Markers** (for partial updates):
```jinja2
{# Template file with markers #}
class {{ DataModelName }}:
    # <copier:start> - Don't edit this section
    id: str
    created_at: datetime
    # <copier:end>

    # User can add custom fields here
```

---

## 5. Implementation Phases: DRASTICALLY SIMPLIFIED

**MAJOR CHANGE:** We're no longer "building from scratch" - we're "wrapping a complete implementation."

**OLD PLAN:** 10 phases, 18-26 hours
**NEW PLAN:** 4 phases, 3-4 hours

Now we **wrap** the existing vehicle_tracking implementation! We'll go phase-by-phase, but the work is MUCH simpler.

### Phase 1: Setup Copier Project (30 minutes)

**UNCHANGED** - This phase stays the same.

#### Step 1.1: Create Directory Structure

```bash
# Create template repository
mkdir tauri-mapbox-python-template
cd tauri-mapbox-python-template

# Initialize git
git init
echo "# Tauri-Mapbox-Python Plugin Template" > README.md
git add README.md
git commit -m "Initial commit"

# Create template structure
mkdir -p template/{{plugin_slug}}
```

**Why git?** Copier works best with version-controlled templates. It tracks changes and enables updates.

#### Step 1.2: Write copier.yml (SIMPLIFIED!)

**OLD APPROACH:** 100+ lines with complex conditionals
**NEW APPROACH:** ~30 lines - just rename things

Create `copier.yml` with minimal questions:

```yaml
# copier.yml - Minimalist "Kitchen Sink" Configuration

_subdirectory: template
_min_copier_version: "9.0.0"

# ============================================================================
# ESSENTIAL QUESTIONS ONLY (3 questions, everything else included)
# ============================================================================

project_name:
  type: str
  help: "What's your plugin called? (e.g., 'Media Analysis', 'Drone Tracker')"
  validator: >-
    {% if not project_name -%}
    Project name is required
    {% elif project_name | length < 3 -%}
    Project name must be at least 3 characters
    {% endif %}

data_type:
  type: str
  help: "What data are you visualizing? (e.g., 'photos', 'vehicles', 'drones')"
  default: "items"

description:
  type: str
  help: "Brief description of this plugin"
  default: "Tauri-Mapbox visualization for {{ data_type }}"

# ============================================================================
# OPTIONAL (but recommended)
# ============================================================================

author_name:
  type: str
  help: "Your name or organization"
  default: "CFSA Development Team"

mapbox_token:
  type: str
  help: "Your Mapbox access token (optional - can add later)"
  default: ""
  secret: true

# ============================================================================
# AUTO-GENERATED (don't ask user, compute from above)
# ============================================================================

project_slug:
  type: str
  default: "{{ project_name.lower().replace(' ', '_').replace('-', '_') }}"

data_model_name:
  type: str
  default: "{{ project_name.replace(' ', '').replace('-', '') }}Data"

tauri_product_name:
  type: str
  default: "{{ project_name }} Map"

# ============================================================================
# ANSWER STORAGE
# ============================================================================

_answers_file: .copier-answers.yml
```

**What changed from the complex version:**
1. **3 essential questions** instead of 15+ (project_name, data_type, description)
2. **NO conditional logic** - everything is included
3. **NO feature flags** - users delete unwanted features manually
4. **Auto-generated variables** - computed from user inputs
5. **Time saved:** 15-20 minutes of question design → 5 minutes

**Philosophy:** The template includes EVERYTHING (timeline, animation, clustering, WebSocket, PubSub). Users customize by DELETING, not by answering questions.

#### Step 1.3: Test the Questions

Before writing any template code, test the questions:

```bash
# Test in dry-run mode
copier copy . test-output --defaults

# This will:
# - Ask all questions (using defaults if you press Enter)
# - Show what would be generated
# - NOT actually create files yet
```

**Checkpoint**: Run this and verify:
1. Questions appear in correct order
2. Conditional questions only show when appropriate
3. Defaults make sense
4. Validation catches bad inputs

---

### Phase 2: Copy Vehicle Tracking Implementation (1 hour)

**NEW STRATEGY:** Don't write templates from scratch - copy the complete vehicle_tracking implementation!

#### Step 2.1: Copy the entire vehicle_tracking directory

```bash
# Navigate to template directory
cd tauri-mapbox-python-template/template

# Copy the COMPLETE vehicle_tracking implementation
cp -r ../../vehicle_tracking ./{{project_slug}}

# That's it! You now have a complete, working implementation to templatize
```

**What you just copied:**
- ✅ Complete Tauri app with mapbox.html (2700+ lines)
- ✅ Full JavaScript modules (PubSub, Animation, Timeline, Utils)
- ✅ Rust backend with multi-layer port discovery
- ✅ Python bridge service (WebSocket communication)
- ✅ Qt widget wrapper
- ✅ All data models and wire format serialization

**Time saved:** Instead of writing 2700+ lines of template code, you copied it in 10 seconds.

#### Step 2.2: Rename files to use template variables

Now add `.jinja` extensions and rename using template variables:

```bash
cd template/{{project_slug}}

# Rename Python files to use project_slug
mv vehicle_tracking_interfaces.py {{project_slug}}_interfaces.py.jinja
mv models/vehicle_tracking_models.py models/{{project_slug}}_models.py.jinja
mv services/vehicle_tracking_service.py services/{{project_slug}}_service.py.jinja
mv services/wire_format.py services/wire_format.py.jinja
mv services/tauri_bridge_service.py services/tauri_bridge_service.py.jinja
mv services/map_template_service.py services/map_template_service.py.jinja
mv ui/components/vehicle_map_widget.py ui/components/{{project_slug}}_map_widget.py.jinja

# Rename Rust/Tauri files
mv tauri-map/src-tauri/src/main.rs tauri-map/src-tauri/src/main.rs.jinja
mv tauri-map/src-tauri/Cargo.toml tauri-map/src-tauri/Cargo.toml.jinja
mv tauri-map/src-tauri/tauri.conf.json tauri-map/src-tauri/tauri.conf.json.jinja

# Rename HTML/JS files
mv tauri-map/src/mapbox.html tauri-map/src/mapbox.html.jinja
mv tauri-map/src/leaflet.html tauri-map/src/leaflet.html.jinja

# JavaScript modules can stay as-is (mostly reusable!)
# Only need to template if they contain hardcoded names
```

**Time:** 5-10 minutes to rename files

#### Step 2.3: Template the variable names (Find & Replace)

**OLD APPROACH:** Manually design templates for each file
**NEW APPROACH:** Bulk find-and-replace across all files

```bash
# Use your favorite editor's find-and-replace (VS Code, Sublime, etc.)
# Or use sed for bulk replacement:

cd template/{{project_slug}}

# Replace class names
find . -name "*.jinja" -type f -exec sed -i 's/VehicleData/{{ data_model_name }}/g' {} +
find . -name "*.jinja" -type f -exec sed -i 's/VehicleTrackingService/{{ project_name | replace(" ", "") }}Service/g' {} +
find . -name "*.jinja" -type f -exec sed -i 's/VehicleMapWidget/{{ project_name | replace(" ", "") }}MapWidget/g' {} +

# Replace module names
find . -name "*.jinja" -type f -exec sed -i 's/vehicle_tracking/{{ project_slug }}/g' {} +

# Replace display names
find . -name "*.jinja" -type f -exec sed -i 's/Vehicle Tracking/{{ project_name }}/g' {} +

# Replace product names
find . -name "*.jinja" -type f -exec sed -i 's/Vehicle Tracking Map/{{ tauri_product_name }}/g' {} +

# Data type references
find . -name "*.jinja" -type f -exec sed -i 's/GPS tracks/{{ data_type }}/g' {} +
find . -name "*.jinja" -type f -exec sed -i 's/vehicles/{{ data_type }}/g' {} +
```

**Time:** 15-20 minutes for bulk replacements

#### Step 2.4: Add template-specific comments

Add helpful comments for users who will customize:

```jinja2
{#
  TEMPLATE INCLUDES EVERYTHING - DELETE WHAT YOU DON'T NEED:

  Don't need animation? Delete:
    - js/animation-engine.js
    - js/timeline-controls.js
    - Timeline HTML controls in mapbox.html

  Don't need clustering? Remove clustering config in mapbox-core.js

  Don't need WebSocket? You probably need it (core architecture)
#}
```

**Time:** 10 minutes to add documentation comments

---

### OLD Phase 2 (DELETED): Complex Template Writing

**What we REMOVED** (no longer needed):
- ~~Step-by-step template writing for main.rs~~
- ~~Conditional logic for WebSocket strategies~~
- ~~Complex Jinja2 control structures~~
- ~~1-2 hours of careful template coding~~

**Why we removed it:** The vehicle_tracking implementation is COMPLETE. We copy it verbatim and just rename variables. The complex conditional logic wasn't needed - users can delete features they don't want.

---

### Phase 3: Add Deletion Guide (30 minutes)

Create a `CUSTOMIZATION_GUIDE.md.jinja` to help users trim features:

```markdown
# Customization Guide for {{ project_name }}

This plugin was generated with ALL features included (kitchen sink approach).
**Delete what you don't need** - it's faster than adding features later!

## Feature Deletion Guide

### Removing Animation Features

**If your data doesn't need animated playback** (e.g., static photos):

1. **Delete JavaScript files:**
   ```
   rm tauri-map/src/js/animation-engine.js
   rm tauri-map/src/js/timeline-controls.js
   ```

2. **Edit `mapbox.html`:** Remove timeline controls HTML (lines ~450-520)

3. **Edit `mapbox-core.js`:** Remove animation loop and interpolation logic

**Time saved by deleting:** 5-10 minutes
**Time to build from scratch:** 3-4 hours

### Removing Clustering

**If you don't have dense data** (e.g., sparse vehicle tracks):

1. **Edit `mapbox-core.js`:** Set `cluster: false` in source config

2. **Remove cluster layers:** Delete cluster circle and count layers

**Time:** 2 minutes

### Removing Timeline (Keep Map Only)

**If you don't need temporal features at all:**

1. Delete all animation features (above)
2. Remove world clock display
3. Simplify data loading (no timestamp sorting needed)

**Time:** 10-15 minutes

### Adapting Timeline for Photos (No Interpolation)

**If you want timeline but NOT animated movement:**

1. Keep timeline controls (play/pause/stop)
2. **Replace** `updateFrame()` logic:
   ```javascript
   // OLD (vehicle tracking): Interpolate position
   const position = interpolate(track, timestamp);
   marker.setPosition(position);

   // NEW (photo filtering): Show/hide based on timestamp
   const visible = photo.timestamp <= currentTime;
   marker.setVisible(visible);
   ```

3. Keep everything else (scrubber, world clock, speed controls)

**Time:** 20-30 minutes to adapt

## Common Customizations

### Change Map Style

Edit `mapbox.html`, line ~850:
```javascript
style: 'mapbox://styles/mapbox/satellite-streets-v12'  // Change this
```

### Add Custom Popup Fields

Edit `wire_format.py` to include your custom fields in serialization.

### Change Marker Colors

Edit color assignment logic in JavaScript or Python data models.

## Architecture Notes

**What you SHOULD keep:**
- WebSocket communication (core architecture)
- PubSub system (enables modularity)
- Multi-layer port discovery (robustness)

**What you CAN delete:**
- Animation features (if data is static)
- Clustering (if data is sparse)
- Timeline (if no temporal analysis needed)
```

**Time:** 30 minutes to write comprehensive guide

---

### Phase 4: Test Generation (1 hour)

Test the simplified template:

```bash
# Generate test plugin
copier copy tauri-mapbox-python-template test_media_analysis

# Answer questions:
# ? Project name: Test Media Analysis
# ? Data type: photos
# ? Description: Test photo visualization

# Verify generation
cd test_media_analysis
grep -r "{{" .  # Should return NOTHING (all variables replaced)

# Test build
cd tauri-map
npm install
npm run build

# Success!
```

**Checkpoint:** If all variables are replaced and build succeeds, your template works!

---

## Phase Summary: Comparison

| Phase | OLD Approach (Complex) | NEW Approach (Kitchen Sink) |
|-------|----------------------|---------------------------|
| **1. Setup** | 30 min | 30 min (same) |
| **2. Template Tauri** | 1-2 hours (write from scratch) | 1 hour (copy + rename) |
| **3. Template Python** | 1 hour (write from scratch) | INCLUDED in Phase 2 |
| **4. Template JavaScript** | 2-3 hours (complex logic) | INCLUDED in Phase 2 |
| **5. Conditional Features** | 1-2 hours (if/else logic) | DELETED (not needed) |
| **6-10. Other Phases** | 4-6 hours | DELETED (not needed) |
| **Deletion Guide** | N/A | 30 min (new) |
| **Testing** | 1-2 hours | 1 hour |
| **TOTAL** | **18-26 hours** | **3-4 hours** |

**Time Savings:** 14-22 hours (83-85% reduction!)

---

### Deleted Legacy Phase 2 Content

The following OLD content has been replaced by the simplified approach above. Keeping as reference:

#### OLD Step 2.1: Template main.rs (DELETED - now just copied verbatim)

~~Create `template/{{plugin_slug}}/tauri-map/src-tauri/src/main.rs.jinja`:~~

```rust
// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;
use std::fs;
use std::path::Path;

/// Get WebSocket port from command line or environment
#[tauri::command]
fn get_ws_port() -> u16 {
    let args: Vec<String> = std::env::args().collect();
    println!("Command line args: {:?}", args);

    {% if websocket_strategy == 'fixed' -%}
    // Fixed port strategy
    let port = {{ websocket_port }};
    println!("Using fixed WebSocket port: {}", port);
    {% else -%}
    // Dynamic port strategy
    let port = std::env::args().nth(1)
        .and_then(|arg| {
            if arg.starts_with("--ws-port=") {
                arg.strip_prefix("--ws-port=").unwrap().parse().ok()
            } else {
                arg.parse().ok()
            }
        })
        .or_else(|| {
            std::env::var("TAURI_WS_PORT").ok()?.parse().ok()
        })
        .unwrap_or(8765);
    println!("Using dynamic WebSocket port: {}", port);
    {% endif %}

    // Write port config for JavaScript
    write_ws_config(port);
    port
}

/// Write WebSocket configuration to js file
fn write_ws_config(port: u16) {
    let exe_path = std::env::current_exe().unwrap();
    let exe_dir = exe_path.parent().unwrap();

    let src_path = exe_dir
        .parent()
        .and_then(|p| p.parent())
        .and_then(|p| p.parent())
        .map(|p| p.join("src").join("ws-config.js"));

    if let Some(config_path) = src_path {
        let config_content = format!(
            "window.WS_CONFIG = {{ port: {}, timestamp: '{}' }};\n",
            port,
            chrono::Local::now().format("%Y-%m-%d %H:%M:%S")
        );

        if let Err(e) = fs::write(&config_path, config_content) {
            eprintln!("Failed to write ws-config.js: {}", e);
        }
    }
}

/// Get map configuration (including Mapbox token if available)
#[tauri::command]
fn get_map_config() -> serde_json::Value {
    serde_json::json!({
        "mapboxToken": std::env::var("MAPBOX_TOKEN").ok(),
        "wsPort": get_ws_port()
    })
}

fn main() {
    let ws_port = get_ws_port();
    println!("Starting {{ tauri_product_name }} with WebSocket port: {}", ws_port);

    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![get_ws_port, get_map_config])
        .setup(move |app| {
            if let Some(window) = app.get_window("main") {
                // Navigate to mapbox.html
                let port_for_nav = ws_port;
                std::thread::spawn(move || {
                    std::thread::sleep(std::time::Duration::from_millis(100));
                    let script = format!("window.location.href = 'mapbox.html?port={}'", port_for_nav);
                    window.eval(&script).ok();
                });

                {% if _copier_conf.debug | default(false) -%}
                // Open DevTools in debug mode
                #[cfg(feature = "devtools")]
                {
                    let window_devtools = window.clone();
                    std::thread::spawn(move || {
                        std::thread::sleep(std::time::Duration::from_millis(1500));
                        window_devtools.open_devtools();
                    });
                }
                {% endif %}
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

**What we templated**:
1. **WebSocket strategy** - Fixed vs. dynamic port
2. **Product name** - In println! statements
3. **Debug features** - Optional DevTools
4. **Most code unchanged** - Architecture is reusable!

#### Step 2.2: Template Cargo.toml

Create `template/{{plugin_slug}}/tauri-map/src-tauri/Cargo.toml.jinja`:

```toml
[package]
name = "{{ plugin_slug }}-map"
version = "0.1.0"
description = "{{ plugin_description }} - Map Viewer"
authors = ["{{ author_name }}"]
license = ""
repository = ""
edition = "2021"

[build-dependencies]
tauri-build = { version = "1.5", features = [] }

[dependencies]
tauri = { version = "1.5", features = ["shell-open"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
chrono = "0.4"

[features]
default = ["custom-protocol"{% if _copier_conf.debug | default(false) %}, "devtools"{% endif %}]
custom-protocol = ["tauri/custom-protocol"]
devtools = ["tauri/devtools"]
```

**What changed**:
1. **Package name** - Uses `plugin_slug`
2. **Description** - Uses `plugin_description`
3. **Author** - Uses `author_name`
4. **Features** - DevTools only in debug mode

#### Step 2.3: Template tauri.conf.json

Create `template/{{plugin_slug}}/tauri-map/src-tauri/tauri.conf.json.jinja`:

```json
{
  "build": {
    "beforeDevCommand": "",
    "beforeBuildCommand": "",
    "devPath": "../src",
    "distDir": "../src"
  },
  "package": {
    "productName": "{{ tauri_product_name }}",
    "version": "0.1.0"
  },
  "tauri": {
    "allowlist": {
      "all": false,
      "shell": {
        "all": false,
        "open": true
      },
      "window": {
        "all": true
      }
    },
    "bundle": {
      "active": true,
      "identifier": "com.{{ author_name.lower().replace(' ', '') }}.{{ plugin_slug }}",
      "targets": "all",
      "icon": [
        "icons/32x32.png",
        "icons/128x128.png",
        "icons/icon.icns",
        "icons/icon.ico"
      ]
    },
    "security": {
      "csp": "default-src 'self' https://api.mapbox.com https://*.tiles.mapbox.com; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://api.mapbox.com; style-src 'self' 'unsafe-inline' https://api.mapbox.com; img-src 'self' data: https: blob:; connect-src 'self' https://api.mapbox.com https://*.tiles.mapbox.com ws://localhost:*;"
    },
    "windows": [
      {
        "fullscreen": false,
        "resizable": true,
        "title": "{{ tauri_product_name }}",
        "width": 1400,
        "height": 900
      }
    ]
  }
}
```

**What changed**:
1. **Product name** - Uses `tauri_product_name`
2. **Bundle identifier** - Generated from author and plugin
3. **Window title** - Uses product name

#### Step 2.4: Template mapbox.html (Complex!)

This is the **most complex** template file. We'll show excerpts with explanations.

Create `template/{{plugin_slug}}/tauri-map/src/mapbox.html.jinja`:

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ tauri_product_name }} - Mapbox GL JS</title>

    <!-- Mapbox GL JS CSS -->
    <link href="https://api.mapbox.com/mapbox-gl-js/v3.0.1/mapbox-gl.css" rel="stylesheet">

    <style>
        /* ... CSS styles (mostly unchanged) ... */

        {% if not has_animation -%}
        /* Hide animation controls for static maps */
        .timeline-control {
            display: none !important;
        }
        {% endif %}
    </style>
</head>
<body>
    <div id="map"></div>

    <!-- Info Panel -->
    <div class="info-panel" id="info-panel">
        <h3>{{ plugin_name }}</h3>
        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">Active Items</div>
                <div class="stat-value" id="active-count">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Points</div>
                <div class="stat-value" id="point-count">0</div>
            </div>
        </div>
        <div class="item-list" id="item-list"></div>
    </div>

    {% if has_animation -%}
    <!-- Timeline Control (only if animated) -->
    <div class="timeline-control" id="timeline-control">
        <button class="control-btn" id="play-btn">▶</button>
        <button class="control-btn" id="pause-btn" style="display:none">⏸</button>
        <button class="control-btn" id="stop-btn">⏹</button>

        <div class="timeline-slider">
            <div class="timeline-track" id="timeline-track">
                <div class="timeline-progress" id="timeline-progress"></div>
            </div>
        </div>

        <div class="time-display" id="time-display">--:--:--</div>

        <div class="speed-selector">
            <button class="speed-option" data-speed="0.5">0.5x</button>
            <button class="speed-option active" data-speed="1">1x</button>
            <button class="speed-option" data-speed="2">2x</button>
            <button class="speed-option" data-speed="4">4x</button>
        </div>
    </div>
    {% endif %}

    <!-- Mapbox GL JS -->
    <script src="https://api.mapbox.com/mapbox-gl-js/v3.0.1/mapbox-gl.js"></script>
    <script src="ws-config.js"></script>

    <script>
        'use strict';

        // Configuration
        const CONFIG = {
            mapboxToken: null,
            defaultCenter: [-75.6972, 45.4215],
            defaultZoom: 11,
            {% if has_animation -%}
            animationFPS: {{ animation_fps }},
            showTrails: {{ show_trails | lower }},
            trailLength: {{ trail_length }},
            {% endif %}
            renderMode: '{{ render_mode }}',
            enableClustering: {{ enable_clustering | lower }}
        };

        // Main map class
        class {{ plugin_name | replace(' ', '') }}Map {
            constructor() {
                this.state = {
                    isInitialized: false,
                    {% if has_animation -%}
                    isPlaying: false,
                    currentTime: null,
                    {% endif %}
                    hasData: false
                };

                this.items = new Map();
                this.map = null;

                {% if has_animation -%}
                this.animationFrame = null;
                this.rollingIndex = 0;
                {% endif %}

                this.initialize();
            }

            async initialize() {
                await this.waitForConfig();
                this.initializeMap();
            }

            // ... [Token handling code - unchanged] ...

            initializeMap() {
                mapboxgl.accessToken = CONFIG.mapboxToken;

                this.map = new mapboxgl.Map({
                    container: 'map',
                    style: 'mapbox://styles/mapbox/dark-v11',
                    center: CONFIG.defaultCenter,
                    zoom: CONFIG.defaultZoom
                });

                this.map.once('load', () => {
                    this.setupMapLayers();
                    {% if has_animation -%}
                    this.setupAnimationControls();
                    {% endif %}
                });
            }

            setupMapLayers() {
                {% if render_mode == 'animated_lines' -%}
                // Line rendering for animated paths
                this.map.addSource('item-paths', {
                    type: 'geojson',
                    data: { type: 'FeatureCollection', features: [] }
                });

                this.map.addLayer({
                    id: 'item-paths-layer',
                    type: 'line',
                    source: 'item-paths',
                    paint: {
                        'line-color': ['get', 'color'],
                        'line-width': 3,
                        'line-opacity': 0.8
                    }
                });
                {% elif render_mode == 'static_markers' or render_mode == 'clustered_markers' -%}
                // Marker rendering
                this.map.addSource('item-markers', {
                    type: 'geojson',
                    {% if enable_clustering -%}
                    cluster: true,
                    clusterMaxZoom: 14,
                    clusterRadius: 50,
                    {% endif %}
                    data: { type: 'FeatureCollection', features: [] }
                });

                {% if enable_clustering -%}
                // Cluster circles
                this.map.addLayer({
                    id: 'clusters',
                    type: 'circle',
                    source: 'item-markers',
                    filter: ['has', 'point_count'],
                    paint: {
                        'circle-color': '#3b82f6',
                        'circle-radius': [
                            'step',
                            ['get', 'point_count'],
                            20, 10,
                            30, 50,
                            40
                        ]
                    }
                });

                // Cluster count labels
                this.map.addLayer({
                    id: 'cluster-count',
                    type: 'symbol',
                    source: 'item-markers',
                    filter: ['has', 'point_count'],
                    layout: {
                        'text-field': '{point_count_abbreviated}',
                        'text-font': ['DIN Pro Medium'],
                        'text-size': 12
                    }
                });
                {% endif %}

                // Individual markers
                this.map.addLayer({
                    id: 'item-markers-layer',
                    type: 'circle',
                    source: 'item-markers',
                    {% if enable_clustering -%}
                    filter: ['!', ['has', 'point_count']],
                    {% endif %}
                    paint: {
                        'circle-color': ['get', 'color'],
                        'circle-radius': 8,
                        'circle-stroke-color': '#ffffff',
                        'circle-stroke-width': 2
                    }
                });
                {% endif %}

                // Click handlers
                this.setupMapInteractions();
            }

            setupMapInteractions() {
                this.map.on('click', 'item-markers-layer', (e) => {
                    const feature = e.features[0];
                    this.showPopup(feature);
                });

                this.map.on('mouseenter', 'item-markers-layer', () => {
                    this.map.getCanvas().style.cursor = 'pointer';
                });

                this.map.on('mouseleave', 'item-markers-layer', () => {
                    this.map.getCanvas().style.cursor = '';
                });
            }

            showPopup(feature) {
                const props = feature.properties;

                let popupHTML = `<div class="popup-header">${props.{{ popup_title_field }} || 'Item'}</div>`;
                popupHTML += '<div class="popup-info">';

                {% for field in popup_fields | from_json -%}
                popupHTML += `<strong>{{ field.label }}:</strong> ${props.{{ field.name }}}{% if field.unit %} {{ field.unit }}{% endif %}<br>`;
                {% endfor %}

                {% if enable_thumbnails -%}
                if (props.thumbnail) {
                    popupHTML += `<img src="${props.thumbnail}" style="max-width: 200px; margin-top: 8px;">`;
                }
                {% endif %}

                popupHTML += '</div>';

                new mapboxgl.Popup()
                    .setLngLat(feature.geometry.coordinates)
                    .setHTML(popupHTML)
                    .addTo(this.map);
            }

            {% if has_animation -%}
            setupAnimationControls() {
                document.getElementById('play-btn').addEventListener('click', () => this.play());
                document.getElementById('pause-btn').addEventListener('click', () => this.pause());
                document.getElementById('stop-btn').addEventListener('click', () => this.stop());
            }

            play() {
                if (!this.state.isPlaying && this.state.hasData) {
                    this.state.isPlaying = true;
                    document.getElementById('play-btn').style.display = 'none';
                    document.getElementById('pause-btn').style.display = 'block';
                    this.animate();
                }
            }

            pause() {
                this.state.isPlaying = false;
                if (this.animationFrame) {
                    cancelAnimationFrame(this.animationFrame);
                }
                document.getElementById('play-btn').style.display = 'block';
                document.getElementById('pause-btn').style.display = 'none';
            }

            stop() {
                this.pause();
                this.state.currentTime = this.state.startTime;
                this.renderFrame();
            }

            animate() {
                if (!this.state.isPlaying) return;

                // Animation logic...
                this.renderFrame();

                this.animationFrame = requestAnimationFrame(() => this.animate());
            }

            renderFrame() {
                // Render current frame based on this.state.currentTime
                // ... complex animation logic ...
            }
            {% endif %}

            loadData(data) {
                console.log('Loading data:', data);
                this.items.clear();

                // Process data items
                data.items.forEach(item => {
                    this.items.set(item.id, item);
                });

                {% if has_animation -%}
                this.state.startTime = data.startTime;
                this.state.endTime = data.endTime;
                this.state.currentTime = data.startTime;
                {% endif %}

                this.state.hasData = true;
                this.renderMap();
                this.fitMapToBounds();
            }

            renderMap() {
                const features = [];

                this.items.forEach((item, id) => {
                    features.push({
                        type: 'Feature',
                        properties: {
                            id: id,
                            {{ popup_title_field }}: item.{{ popup_title_field }},
                            {% for field in popup_fields | from_json -%}
                            {{ field.name }}: item.{{ field.name }},
                            {% endfor %}
                            color: item.color || '#3b82f6'
                        },
                        geometry: {
                            type: 'Point',
                            coordinates: [item.longitude, item.latitude]
                        }
                    });
                });

                {% if render_mode == 'animated_lines' -%}
                this.map.getSource('item-paths').setData({
                    type: 'FeatureCollection',
                    features: features
                });
                {% else -%}
                this.map.getSource('item-markers').setData({
                    type: 'FeatureCollection',
                    features: features
                });
                {% endif %}
            }

            fitMapToBounds() {
                if (this.items.size === 0) return;

                const bounds = new mapboxgl.LngLatBounds();
                this.items.forEach(item => {
                    bounds.extend([item.longitude, item.latitude]);
                });

                this.map.fitBounds(bounds, { padding: 50, duration: 1000 });
            }
        }

        // Initialize map
        let mapInstance = null;

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                mapInstance = new {{ plugin_name | replace(' ', '') }}Map();
                window.{{ plugin_slug }}Map = mapInstance;
            });
        } else {
            mapInstance = new {{ plugin_name | replace(' ', '') }}Map();
            window.{{ plugin_slug }}Map = mapInstance;
        }

        // WebSocket bridge
        class PythonBridge {
            constructor() {
                const urlParams = new URLSearchParams(window.location.search);
                this.port = urlParams.get('port') || window.WS_CONFIG?.port || 8765;
                this.connect();
            }

            connect() {
                this.ws = new WebSocket(`ws://localhost:${this.port}/`);

                this.ws.onopen = () => {
                    console.log('[PythonBridge] Connected');
                    this.ws.send(JSON.stringify({ type: 'ready' }));
                };

                this.ws.onmessage = (event) => {
                    const msg = JSON.parse(event.data);
                    this.handleMessage(msg);
                };

                this.ws.onerror = (error) => {
                    console.error('[PythonBridge] Error:', error);
                };

                this.ws.onclose = () => {
                    setTimeout(() => this.connect(), 2000);
                };
            }

            handleMessage(msg) {
                switch(msg.type) {
                    case 'load_data':
                        if (window.{{ plugin_slug }}Map) {
                            window.{{ plugin_slug }}Map.loadData(msg.data);
                        }
                        break;
                    {% if has_animation -%}
                    case 'animation_control':
                        if (window.{{ plugin_slug }}Map) {
                            const cmd = msg.command;
                            if (cmd === 'play') window.{{ plugin_slug }}Map.play();
                            else if (cmd === 'pause') window.{{ plugin_slug }}Map.pause();
                            else if (cmd === 'stop') window.{{ plugin_slug }}Map.stop();
                        }
                        break;
                    {% endif %}
                }
            }

            send(data) {
                if (this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify(data));
                }
            }
        }

        // Initialize bridge
        setTimeout(() => {
            window.pythonBridge = new PythonBridge();
        }, 1000);
    </script>
</body>
</html>
```

**What we templated** (this is complex!):
1. **Title/headers** - Use `plugin_name` / `tauri_product_name`
2. **Animation controls** - Conditional blocks with `{% if has_animation %}`
3. **Map layers** - Different rendering based on `render_mode`
4. **Clustering** - Conditional with `enable_clustering`
5. **Popup fields** - Loop through `popup_fields` list
6. **Thumbnails** - Conditional with `enable_thumbnails`
7. **Class names** - Use `plugin_slug` and `plugin_name`
8. **JavaScript object names** - e.g., `window.{{plugin_slug}}Map`

**Checkpoint**: This is the most complex file. Take a break, re-read it, and identify:
1. Where are the `{{ variables }}`?
2. Where are the `{% if ... %}` blocks?
3. Where are the `{% for ... %}` loops?
4. What stays the same across all plugins?

---

### Phase 3: Template the Python Bridge (1 hour)

Now we template the Python side of the bridge.

#### Step 3.1: Template tauri_bridge_service.py

Create `template/{{plugin_slug}}/services/tauri_bridge_service.py.jinja`:

```python
#!/usr/bin/env python3
"""
Tauri Bridge Service for {{ plugin_name }}

Handles WebSocket communication between Python and Tauri desktop app.
"""

import json
import subprocess
import threading
import socket
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from websocket_server import WebsocketServer

from core.services.base_service import BaseService
from core.result_types import Result
from core.logger import logger


class TauriBridgeService(BaseService):
    """
    Bridge service using WebSocket for Python ↔ Tauri communication.

    Architecture:
    - Python backend runs WebSocket server
    - Tauri app connects as client
    - Bidirectional JSON messaging
    """

    def __init__(self):
        super().__init__("TauriBridgeService")

        # WebSocket server
        self.ws_server: Optional[WebsocketServer] = None
        {% if websocket_strategy == 'fixed' -%}
        self.ws_port: int = {{ websocket_port }}  # Fixed port
        {% else -%}
        self.ws_port: Optional[int] = None  # Dynamic port (found at runtime)
        {% endif %}
        self.ws_thread: Optional[threading.Thread] = None

        # Tauri process
        self.tauri_process: Optional[subprocess.Popen] = None
        self.tauri_path = Path(__file__).parent.parent / "tauri-map"

        # State
        self.is_running = False
        self.connected_clients = []
        self.pending_messages = []

    {% if websocket_strategy == 'dynamic' -%}
    def find_free_port(self) -> int:
        """Find an available port for WebSocket server."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port
    {% endif %}

    def start(self) -> Result[int]:
        """
        Start WebSocket server and launch Tauri application.

        Returns:
            Result containing WebSocket port if successful
        """
        try:
            {% if websocket_strategy == 'dynamic' -%}
            # Find available port
            self.ws_port = self.find_free_port()
            logger.info(f"Using WebSocket port: {self.ws_port}")
            {% else -%}
            logger.info(f"Using fixed WebSocket port: {self.ws_port}")
            {% endif %}

            # Start WebSocket server
            self._start_websocket_server()

            # Launch Tauri application
            self._launch_tauri()

            self.is_running = True
            return Result.success(self.ws_port)

        except Exception as e:
            logger.error(f"Failed to start bridge: {e}")
            return Result.error(str(e))

    def _start_websocket_server(self):
        """Start WebSocket server in background thread."""
        self.ws_server = WebsocketServer(port=self.ws_port, host='localhost')

        # Set up callbacks
        self.ws_server.set_fn_new_client(self._on_client_connected)
        self.ws_server.set_fn_client_left(self._on_client_disconnected)
        self.ws_server.set_fn_message_received(self._on_message_received)

        # Start in daemon thread
        self.ws_thread = threading.Thread(target=self.ws_server.serve_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()

        logger.info(f"WebSocket server started on port {self.ws_port}")

    def _launch_tauri(self):
        """Launch Tauri desktop application."""
        try:
            # Build path to executable
            if sys.platform == "win32":
                exe_name = "{{ tauri_product_name }}.exe"
            elif sys.platform == "darwin":
                exe_name = "{{ tauri_product_name }}"
            else:
                exe_name = "{{ tauri_product_name | lower | replace(' ', '-') }}"

            exe_path = self.tauri_path / "src-tauri" / "target" / "release" / exe_name

            logger.info(f"Looking for Tauri executable at: {exe_path}")

            if not exe_path.exists():
                raise FileNotFoundError(
                    f"Tauri executable not found: {exe_path}\n"
                    f"Please build the Tauri app first:\n"
                    f"  cd {self.tauri_path}\n"
                    f"  npm run build"
                )

            # Launch with WebSocket port parameter
            cmd = [str(exe_path), f"--ws-port={self.ws_port}"]

            # Also pass as environment variable
            env = os.environ.copy()
            env['TAURI_WS_PORT'] = str(self.ws_port)

            self.tauri_process = subprocess.Popen(
                cmd,
                cwd=self.tauri_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            logger.info("Tauri application launched")

        except Exception as e:
            logger.error(f"Failed to launch Tauri: {e}")
            raise

    def _on_client_connected(self, client, server):
        """Handle new WebSocket client connection."""
        logger.info(f"Tauri client connected: {client['id']}")
        self.connected_clients.append(client)

        # Send any pending messages
        for msg in self.pending_messages:
            server.send_message(client, json.dumps(msg))
        self.pending_messages.clear()

    def _on_client_disconnected(self, client, server):
        """Handle client disconnection."""
        logger.info(f"Tauri client disconnected: {client['id']}")
        if client in self.connected_clients:
            self.connected_clients.remove(client)

    def _on_message_received(self, client, server, message):
        """Handle message from Tauri application."""
        try:
            data = json.loads(message)
            msg_type = data.get('type')

            if msg_type == 'ready':
                logger.info("Tauri map ready")
            elif msg_type == 'item_clicked':
                logger.info(f"Item clicked: {data.get('item_id')}")
            elif msg_type == 'error':
                logger.error(f"Tauri error: {data.get('message')}")

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def send_data(self, data: Dict[str, Any]) -> Result[None]:
        """
        Send data to Tauri for visualization.

        Args:
            data: Dictionary containing {{ data_type }} to display

        Returns:
            Result indicating success or failure
        """
        try:
            message = {
                "type": "load_data",
                "data": data
            }

            if self.connected_clients and self.ws_server:
                # Send to all connected clients
                self.ws_server.send_message_to_all(json.dumps(message))
                logger.info(f"Sent data to {len(self.connected_clients)} clients")
            else:
                # Queue for when client connects
                self.pending_messages.append(message)
                logger.info("Queued data for when client connects")

            return Result.success(None)

        except Exception as e:
            logger.error(f"Failed to send data: {e}")
            return Result.error(str(e))

    {% if has_animation -%}
    def send_animation_command(self, command: str) -> Result[None]:
        """
        Send animation control command to Tauri.

        Args:
            command: One of 'play', 'pause', 'stop'

        Returns:
            Result indicating success or failure
        """
        try:
            message = {
                "type": "animation_control",
                "command": command
            }

            if self.connected_clients and self.ws_server:
                self.ws_server.send_message_to_all(json.dumps(message))
                return Result.success(None)
            else:
                logger.warning("No connected clients to send command to")
                return Result.error("No connected clients")

        except Exception as e:
            logger.error(f"Failed to send animation command: {e}")
            return Result.error(str(e))
    {% endif %}

    def shutdown(self):
        """Clean shutdown of bridge service."""
        logger.info("Shutting down Tauri bridge...")

        # Stop WebSocket server
        if self.ws_server:
            try:
                self.ws_server.shutdown()
            except:
                pass

        # Terminate Tauri process
        if self.tauri_process:
            self.tauri_process.terminate()
            try:
                self.tauri_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.tauri_process.kill()

        self.is_running = False
        logger.info("Tauri bridge shutdown complete")
```

**What we templated**:
1. **Docstrings** - Reference `plugin_name` and `data_type`
2. **Port strategy** - Fixed vs. dynamic (big conditional block)
3. **Executable name** - Uses `tauri_product_name`
4. **Animation method** - Conditional with `{% if has_animation %}`
5. **Log messages** - Use appropriate terminology

#### Step 3.2: Template wire_format.py

Create `template/{{plugin_slug}}/services/wire_format.py.jinja`:

```python
"""
Wire format converter for {{ plugin_name }}.

Ensures consistent data serialization between Python and JavaScript.
"""

from typing import Dict, List, Any
from datetime import datetime

from ..models.{{plugin_slug}}_models import {{ DataModelName }}


def to_wire_format(data: {{ DataModelName }}) -> Dict[str, Any]:
    """
    Convert {{ DataModelName }} to wire format for transmission.

    Enforces:
    - Timestamps as epoch milliseconds (integers)
    - Consistent units (km/h for speed, meters for distance)
    - Monotonic indexing for each point

    Args:
        data: {{ plugin_name }} data to convert

    Returns:
        Dictionary ready for JSON serialization
    """
    items = []

    for index, item in enumerate(data.{{ primary_data_field }}):
        # Convert timestamp to milliseconds
        timestamp_ms = int(item.timestamp.timestamp() * 1000)

        wire_item = {
            "index": index,
            "timestamp_ms": timestamp_ms,
            "latitude": item.latitude,
            "longitude": item.longitude,
            {% for field in popup_fields | from_json -%}
            "{{ field.name }}": getattr(item, '{{ field.name }}', None),
            {% endfor %}
        }

        {% if enable_thumbnails -%}
        # Add thumbnail if available
        if hasattr(item, 'thumbnail_b64') and item.thumbnail_b64:
            wire_item["thumbnail"] = item.thumbnail_b64
        {% endif %}

        items.append(wire_item)

    return {
        "{{ id_field }}": data.{{ id_field }},
        "items": items,
        {% if has_animation -%}
        "startTime": int(data.start_time.timestamp() * 1000) if data.start_time else None,
        "endTime": int(data.end_time.timestamp() * 1000) if data.end_time else None,
        {% endif %}
        "meta": {
            "total_items": len(items),
            "data_type": "{{ data_type }}"
        }
    }


def from_wire_format(payload: Dict[str, Any]) -> {{ DataModelName }}:
    """
    Parse wire format back to {{ DataModelName }}.

    Args:
        payload: Wire format dictionary

    Returns:
        {{ DataModelName }} object

    Raises:
        ValueError: If wire format validation fails
    """
    # Validate required fields
    if "{{ id_field }}" not in payload:
        raise ValueError("Missing required field: {{ id_field }}")
    if "items" not in payload:
        raise ValueError("Missing required field: items")

    # Parse items
    items = []
    for wire_item in payload["items"]:
        timestamp = datetime.fromtimestamp(wire_item["timestamp_ms"] / 1000.0)

        # Create item (simplified - you'll need to adapt this to your actual model)
        item = {
            "timestamp": timestamp,
            "latitude": wire_item["latitude"],
            "longitude": wire_item["longitude"],
            {% for field in popup_fields | from_json -%}
            "{{ field.name }}": wire_item.get("{{ field.name }}"),
            {% endfor %}
        }

        {% if enable_thumbnails -%}
        if "thumbnail" in wire_item:
            item["thumbnail_b64"] = wire_item["thumbnail"]
        {% endif %}

        items.append(item)

    # Create data object
    data = {{ DataModelName }}(
        {{ id_field }}=payload["{{ id_field }}"],
        {{ primary_data_field }}=items
    )

    return data
```

**What we templated**:
1. **Class names** - `{{DataModelName}}`
2. **Field names** - `{{id_field}}`, `{{primary_data_field}}`
3. **Popup fields** - Loop through `{{popup_fields}}`
4. **Animation fields** - Conditional with `{% if has_animation %}`
5. **Thumbnails** - Conditional with `{% if enable_thumbnails %}`

#### Step 3.3: Template the Data Model

Create `template/{{plugin_slug}}/models/{{plugin_slug}}_models.py.jinja`:

```python
"""
Data models for {{ plugin_name }}.

Defines data structures for {{ data_type }}.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from enum import Enum


@dataclass
class GPSPoint:
    """
    Individual GPS measurement.

    Reusable across different plugins - represents a single coordinate.
    """
    latitude: float
    longitude: float
    timestamp: datetime

    # Optional fields
    altitude: Optional[float] = None
    accuracy: Optional[float] = None

    {% if enable_thumbnails -%}
    # Thumbnail data (base64 encoded)
    thumbnail_b64: Optional[str] = None
    {% endif %}

    # Generic metadata
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class {{ DataModelName }}:
    """
    Complete dataset for {{ plugin_name }}.

    Contains all {{ data_type }} for visualization.
    """
    {{ id_field }}: str
    source_file: Optional[Path] = None
    {{ primary_data_field }}: List[GPSPoint] = field(default_factory=list)

    # Metadata
    label: Optional[str] = None
    description: Optional[str] = None

    {% if has_animation -%}
    # Time bounds for animation
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_duration_seconds: Optional[float] = None
    {% endif %}

    # Statistics
    total_distance_km: Optional[float] = None
    point_count: int = 0

    def get_bounds(self) -> tuple[float, float, float, float]:
        """
        Get geographic bounds [min_lat, min_lon, max_lat, max_lon].

        Returns:
            Tuple of (min_lat, min_lon, max_lat, max_lon)
        """
        if not self.{{ primary_data_field }}:
            return (0.0, 0.0, 0.0, 0.0)

        lats = [p.latitude for p in self.{{ primary_data_field }}]
        lons = [p.longitude for p in self.{{ primary_data_field }}]

        return (min(lats), min(lons), max(lats), max(lons))

    {% if has_animation -%}
    def get_time_range(self) -> tuple[datetime, datetime]:
        """Get time range of data."""
        if self.start_time and self.end_time:
            return (self.start_time, self.end_time)

        if not self.{{ primary_data_field }}:
            return (datetime.now(), datetime.now())

        self.start_time = min(p.timestamp for p in self.{{ primary_data_field }})
        self.end_time = max(p.timestamp for p in self.{{ primary_data_field }})
        return (self.start_time, self.end_time)
    {% endif %}


@dataclass
class {{ plugin_name.replace(' ', '') }}Result:
    """
    Result of {{ plugin_name }} operation.

    Used with Result[T] pattern for error handling.
    """
    items_processed: int = 0
    processing_time_seconds: float = 0.0

    # Processed data
    data: Optional[{{ DataModelName }}] = None

    # Errors/warnings
    skipped_files: List[tuple[Path, str]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def get_summary(self) -> str:
        """Get human-readable summary."""
        return (
            f"Processed {self.items_processed} items in "
            f"{self.processing_time_seconds:.1f} seconds"
        )
```

**What we templated**:
1. **Class names** - `{{DataModelName}}`, `{{plugin_name}}Result`
2. **Field names** - `{{id_field}}`, `{{primary_data_field}}`
3. **Docstrings** - Reference `{{data_type}}` and `{{plugin_name}}`
4. **Animation fields** - Conditional blocks
5. **Thumbnail support** - Conditional with `{% if enable_thumbnails %}`

---

### Phase 4: Template the UI Integration (1 hour)

Final phase - integrate with the Qt application.

#### Step 4.1: Template the Map Widget

Create `template/{{plugin_slug}}/ui/components/{{plugin_slug}}_map_widget.py.jinja`:

```python
#!/usr/bin/env python3
"""
{{ plugin_name }} Map Widget

Qt wrapper for {{ plugin_name }} map visualization.
"""

from typing import List, Optional
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from ...models.{{plugin_slug}}_models import {{ DataModelName }}
from ...services.tauri_bridge_service import TauriBridgeService
from ...services.wire_format import to_wire_format

from core.logger import logger
from core.result_types import Result


class {{ plugin_name.replace(' ', '') }}MapWidget(QWidget):
    """
    {{ plugin_name }} map visualization widget.

    Provides Qt interface for Tauri-based map display.
    """

    # Signals
    itemSelected = Signal(str)  # Emitted when item clicked
    {% if has_animation -%}
    animationFinished = Signal()  # Emitted when animation completes
    {% endif %}

    def __init__(self, parent=None):
        """
        Initialize {{ plugin_name }} map widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Services
        self.bridge_service = TauriBridgeService()

        # State
        self.current_data: Optional[{{ DataModelName }}] = None
        self._map_loaded: bool = False

        # Create UI
        self._create_ui()

    def _create_ui(self):
        """Create the widget UI."""
        layout = QVBoxLayout(self)

        # Info label
        info_label = QLabel("{{ plugin_name }} Visualization")
        info_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(info_label)

        # Control buttons
        control_layout = QHBoxLayout()

        self.launch_btn = QPushButton("Launch Map")
        self.launch_btn.clicked.connect(self._launch_map)
        control_layout.addWidget(self.launch_btn)

        self.load_btn = QPushButton("Load Data")
        self.load_btn.clicked.connect(self._load_data)
        self.load_btn.setEnabled(False)
        control_layout.addWidget(self.load_btn)

        {% if has_animation -%}
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self._play_animation)
        self.play_btn.setEnabled(False)
        control_layout.addWidget(self.play_btn)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self._pause_animation)
        self.pause_btn.setEnabled(False)
        control_layout.addWidget(self.pause_btn)
        {% endif %}

        layout.addLayout(control_layout)

        # Status label
        self.status_label = QLabel("Not connected")
        self.status_label.setStyleSheet("padding: 5px; background: #f0f0f0;")
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _launch_map(self):
        """Launch Tauri map application."""
        self.status_label.setText("Launching map...")
        self.launch_btn.setEnabled(False)

        result = self.bridge_service.start()

        if result.success:
            self.status_label.setText(f"Map launched on port {result.value}")
            self._map_loaded = True
            self.load_btn.setEnabled(True)
            logger.info("Map launched successfully")
        else:
            self.status_label.setText(f"Failed to launch: {result.error}")
            self.launch_btn.setEnabled(True)
            logger.error(f"Failed to launch map: {result.error}")

    def load_data(self, data: {{ DataModelName }}):
        """
        Load {{ data_type }} into the map.

        Args:
            data: {{ DataModelName }} to visualize
        """
        try:
            self.current_data = data

            if not self._map_loaded:
                logger.warning("Map not loaded yet")
                self.status_label.setText("Please launch map first")
                return

            # Convert to wire format
            wire_data = to_wire_format(data)

            # Send to Tauri
            result = self.bridge_service.send_data(wire_data)

            if result.success:
                self.status_label.setText(f"Loaded {len(data.{{ primary_data_field }})} items")
                {% if has_animation -%}
                self.play_btn.setEnabled(True)
                {% endif %}
                logger.info(f"Data loaded: {len(data.{{ primary_data_field }})} items")
            else:
                self.status_label.setText(f"Failed to load data: {result.error}")
                logger.error(f"Failed to load data: {result.error}")

        except Exception as e:
            logger.error(f"Error loading data: {e}")
            self.status_label.setText(f"Error: {str(e)}")

    def _load_data(self):
        """Load current data (for manual trigger)."""
        if self.current_data:
            self.load_data(self.current_data)
        else:
            self.status_label.setText("No data to load")

    {% if has_animation -%}
    def _play_animation(self):
        """Start animation playback."""
        result = self.bridge_service.send_animation_command("play")
        if result.success:
            self.play_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.status_label.setText("Playing animation...")

    def _pause_animation(self):
        """Pause animation playback."""
        result = self.bridge_service.send_animation_command("pause")
        if result.success:
            self.play_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.status_label.setText("Animation paused")
    {% endif %}

    def cleanup(self):
        """Clean up resources."""
        if self.bridge_service:
            self.bridge_service.shutdown()
        logger.info("{{ plugin_name }} map widget cleaned up")
```

**What we templated**:
1. **Class name** - `{{plugin_name}}MapWidget`
2. **Docstrings** - Reference `{{plugin_name}}` and `{{data_type}}`
3. **Data model** - Uses `{{DataModelName}}`
4. **Field names** - `{{primary_data_field}}`
5. **Animation controls** - Conditional with `{% if has_animation %}`
6. **UI labels** - Use `{{plugin_name}}`

---

### Phase 5: Template Enhancements (30 minutes)

#### Step 5.1: Add Template Configuration

Create `template/{{plugin_slug}}/.copier-answers.yml.jinja`:

```yaml
# Copier answers for {{ plugin_name }}
# This file allows updating the plugin when the template changes

_src_path: {{ _copier_conf.src_path }}
_commit: {{ _copier_conf.vcs_ref_hash }}

# User answers
plugin_name: {{ plugin_name }}
plugin_slug: {{ plugin_slug }}
plugin_description: {{ plugin_description }}
author_name: {{ author_name }}

data_type: {{ data_type }}
primary_data_field: {{ primary_data_field }}
id_field: {{ id_field }}

render_mode: {{ render_mode }}
has_animation: {{ has_animation }}
{% if has_animation -%}
animation_fps: {{ animation_fps }}
show_trails: {{ show_trails }}
trail_length: {{ trail_length }}
{% endif %}

popup_title_field: {{ popup_title_field }}
popup_fields: {{ popup_fields }}

websocket_strategy: {{ websocket_strategy }}
{% if websocket_strategy == 'fixed' -%}
websocket_port: {{ websocket_port }}
{% endif %}

enable_thumbnails: {{ enable_thumbnails }}
enable_clustering: {{ enable_clustering }}
enable_search: {{ enable_search }}
```

#### Step 5.2: Add README Template

Create `template/{{plugin_slug}}/README.md.jinja`:

```markdown
# {{ plugin_name }}

{{ plugin_description }}

## Overview

This plugin visualizes {{ data_type }} on interactive maps using:
- **Tauri**: Desktop application framework
- **Mapbox GL JS**: Map rendering
- **Python**: Data processing backend
- **Qt (PySide6)**: UI integration

## Generated with Copier

This plugin was generated from the Tauri-Mapbox-Python template.

**Configuration:**
- **Render Mode**: {{ render_mode }}
{% if has_animation -%}
- **Animation**: Enabled ({{ animation_fps }} FPS)
{% else -%}
- **Animation**: Disabled (static visualization)
{% endif %}
{% if enable_clustering -%}
- **Clustering**: Enabled
{% endif %}
{% if enable_thumbnails -%}
- **Thumbnails**: Enabled
{% endif %}

## Building the Tauri App

```bash
cd tauri-map
npm install
npm run build
```

This creates an executable at:
```
tauri-map/src-tauri/target/release/{{ tauri_product_name }}{% if _copier_conf.os == 'Windows' %}.exe{% endif %}
```

## Usage

```python
from {{ plugin_slug }}.models.{{plugin_slug}}_models import {{ DataModelName }}
from {{ plugin_slug }}.ui.components.{{plugin_slug}}_map_widget import {{ plugin_name.replace(' ', '') }}MapWidget

# Create widget
map_widget = {{ plugin_name.replace(' ', '') }}MapWidget()

# Load data
data = {{ DataModelName }}(
    {{ id_field }}="sample_001",
    {{ primary_data_field }}=[...]  # Your GPS points
)

map_widget.load_data(data)
```

## Architecture

```
Python Backend                Tauri Frontend
┌─────────────────┐          ┌──────────────────┐
│  Qt UI Widget   │          │  Rust WebSocket  │
│                 │          │     Handler      │
└────────┬────────┘          └────────┬─────────┘
         │                            │
         │ WebSocket (JSON)           │
         └────────────────────────────┘
                     │
         ┌───────────▼──────────┐
         │   Mapbox GL JS Map   │
         │  ({{ render_mode }})  │
         └──────────────────────┘
```

## Customization

### Adding Custom Fields

Edit `models/{{plugin_slug}}_models.py`:
```python
@dataclass
class GPSPoint:
    # Add custom fields here
    custom_field: Optional[str] = None
```

### Changing Map Style

Edit `tauri-map/src/mapbox.html`, line ~1065:
```javascript
style: 'mapbox://styles/mapbox/dark-v11',  // Change this
```

Available styles:
- `dark-v11`
- `light-v11`
- `streets-v12`
- `satellite-streets-v12`
- `navigation-night-v1`

## Updating from Template

If the template is updated, you can update this plugin:

```bash
cd {{ plugin_slug }}/
copier update
```

Copier will:
1. Show your previous answers
2. Re-generate files
3. Smart-merge your customizations

## License

{{ _copier_conf.license | default('Proprietary') }}

## Generated

- **Template**: {{ _copier_conf.src_path }}
- **Commit**: {{ _copier_conf.vcs_ref_hash }}
- **Date**: {{ _copier_conf.timestamp }}
```

---

## 5.5. Architecture Variants in Practice

This new section demonstrates how the SAME "kitchen sink" template supports different use cases through selective feature deletion.

### The Power of the Kitchen Sink Approach

**Key Insight:** One template, multiple use cases. Users customize by deleting, not by configuring.

### Variant 1: Vehicle Tracking (Keep Everything)

**Generated with:**
```bash
copier copy template vehicle_tracking_v2
? Project name: Vehicle Tracking V2
? Data type: vehicles
```

**Features kept:**
- ✅ Timeline controls (for animation playback)
- ✅ Interpolation logic (smooth movement between GPS points)
- ✅ Animation engine (frame-accurate playback)
- ✅ Speed controls (0.5x, 1x, 2x, 4x)
- ✅ World clock (temporal context)
- ❌ Clustering (deleted - vehicles don't cluster)
- ✅ Popups (speed, heading, timestamp)

**Deletion time:** 5 minutes (remove clustering config)

---

### Variant 2: Media Analysis (Selective Features)

**Generated with:**
```bash
copier copy template media_analysis
? Project name: Media Analysis
? Data type: photos
```

**Features kept:**
- ✅ Timeline controls (for temporal filtering)
- ❌ Interpolation logic (deleted - photos don't move)
- ⚠️ Animation engine (modified - controls visibility, not position)
- ✅ Speed controls (still useful for scrubbing through time)
- ✅ World clock (show when photos were taken)
- ✅ Clustering (many photos at same GPS location)
- ✅ Popups (modified for thumbnails + EXIF data)

**Customization time:** 30 minutes (delete interpolation, modify updateFrame() logic)

**Key code change:**
```javascript
// BEFORE (vehicle tracking):
function updateFrame(timestamp) {
    const position = interpolatePath(vehicle.track, timestamp);
    marker.setLngLat(position);
}

// AFTER (media analysis):
function updateFrame(timestamp) {
    const visible = photo.timestamp <= timestamp;
    marker.setVisibility(visible);
}
```

---

### Variant 3: Simple Map Viewer (Minimal)

**Generated with:**
```bash
copier copy template simple_location_viewer
? Project name: Location Viewer
? Data type: locations
```

**Features kept:**
- ❌ Timeline controls (deleted - no temporal analysis)
- ❌ Interpolation logic (deleted)
- ❌ Animation engine (deleted)
- ❌ Speed controls (deleted)
- ❌ World clock (deleted)
- ⚠️ Clustering (optional - user decides)
- ✅ Popups (basic info only)

**Deletion time:** 15 minutes (delete entire timeline system)

**Result:** Simple, static map with markers. Perfect for non-temporal data.

---

### Variant 4: Drone Tracker (Keep Everything + Add Custom)

**Generated with:**
```bash
copier copy template drone_tracker
? Project name: Drone Flight Tracker
? Data type: drones
```

**Features kept:**
- ✅ Everything from vehicle tracking
- ➕ ADDED: Altitude visualization (custom)
- ➕ ADDED: 3D flight path rendering (custom)
- ➕ ADDED: Battery level indicators (custom)

**Customization:** 2 hours (add new features, keep all existing)

**Insight:** Starting with "everything" doesn't prevent adding more - it gives you a solid foundation.

---

### Comparison Table: Template Variants

| Feature | Vehicle Tracking | Media Analysis | Simple Viewer | Drone Tracker |
|---------|------------------|----------------|---------------|---------------|
| **Timeline Controls** | ✅ Keep | ✅ Keep | ❌ Delete | ✅ Keep |
| **Interpolation** | ✅ Keep | ❌ Delete | ❌ Delete | ✅ Keep |
| **Animation Engine** | ✅ Keep | ⚠️ Modify | ❌ Delete | ✅ Keep |
| **Clustering** | ❌ Delete | ✅ Keep | ⚠️ Optional | ❌ Delete |
| **World Clock** | ✅ Keep | ✅ Keep | ❌ Delete | ✅ Keep |
| **Custom Features** | None | Thumbnails | None | Altitude, 3D paths |
| **Setup Time** | 5 min | 30 min | 15 min | 2 hours |
| **vs. Building from Scratch** | 3-4 hours saved | 4-5 hours saved | 2 hours saved | 6-8 hours saved |

---

### Key Takeaways

1. **Same template, different results** - The "kitchen sink" approach is flexible
2. **Deletion is predictable** - You know what you're removing
3. **Addition is unpredictable** - Building features from scratch is time-consuming
4. **Foundation is solid** - Even minimal variants benefit from robust WebSocket, PubSub, etc.
5. **Documentation guides deletion** - CUSTOMIZATION_GUIDE.md makes it easy

**Philosophy validated:** Include everything, let users trim. Much faster than conditional generation.

---

## 6. Testing & Validation

**UPDATED:** Testing exercises now reflect the simplified "kitchen sink" approach.

### Exercise 1: Generate Media Analysis Plugin (Trim Features)

Now let's test our simplified template by generating the media_analysis plugin!

**UPDATED:** Only 3 questions instead of 12+

```bash
# Navigate to your project root
cd "d:\Active Working Coding Projects\Folder Structure Multiple Versions\Folder_Structure_HASH_Media_Analysis"

# Generate plugin from template (SIMPLIFIED!)
copier copy tauri-mapbox-python-template media_analysis_generated

# Answer questions (ONLY 3!):
# ? Project name: Media Analysis
# ? Data type: photos
# ? Description: Visualize photo GPS locations with temporal filtering

# That's it! Template includes EVERYTHING by default
```

**Expected output:**
```
Copying from template tauri-mapbox-python-template
 identical  .
    create  media_analysis_generated
    create  media_analysis_generated/__init__.py
    create  media_analysis_generated/media_analysis_interfaces.py
    create  media_analysis_generated/tauri-map
    create  media_analysis_generated/tauri-map/src
    create  media_analysis_generated/tauri-map/src/mapbox.html
    create  media_analysis_generated/tauri-map/src-tauri
    ... (47 files created)
```

### Exercise 2: Validate Generated Code

#### Test 2.1: Check Variable Substitution

```bash
# Check that variables were replaced correctly
grep -r "{{" media_analysis_generated/

# Should return NOTHING (all {{variables}} replaced)
# If you see {{ ... }}, something went wrong!
```

#### Test 2.2: Check Conditional Logic

```bash
# Animation controls should NOT exist (has_animation=False)
grep -n "animation" media_analysis_generated/tauri-map/src/mapbox.html

# Clustering should exist (enable_clustering=True)
grep -n "cluster" media_analysis_generated/tauri-map/src/mapbox.html
```

#### Test 2.3: Syntax Check

```bash
# Python syntax
python -m py_compile media_analysis_generated/services/*.py
python -m py_compile media_analysis_generated/models/*.py

# Rust syntax (if you have rust installed)
cd media_analysis_generated/tauri-map/src-tauri
cargo check
```

### Exercise 3: Build and Run

```bash
# Build Tauri app
cd media_analysis_generated/tauri-map
npm install
npm run build

# Check executable created
ls -lh src-tauri/target/release/
# Should see "Media Analysis Map.exe" (or similar)
```

### Validation Checklist

- [ ] All `{{variables}}` replaced
- [ ] No syntax errors in Python files
- [ ] No syntax errors in Rust files
- [ ] Tauri build succeeds
- [ ] Animation controls absent (if has_animation=False)
- [ ] Clustering code present (if enable_clustering=True)
- [ ] Popup fields match configuration
- [ ] README generated with correct info
- [ ] .copier-answers.yml contains all answers

---

## 7. Advanced Techniques

### Technique 1: Multi-File Generation

Generate multiple files from a list:

```yaml
# copier.yml
custom_services:
  type: json
  help: "List of custom service names to generate"
  default: '[]'
```

```jinja2
{# Template: generate multiple service files #}
{% for service in custom_services | from_json -%}
{# This would create services/{{service}}_service.py for each #}
{% endfor %}
```

### Technique 2: Conditional File Creation

Only create files if needed:

```yaml
# copier.yml
_exclude:
  {% if not has_animation -%}
  - "{{plugin_slug}}/services/animation_controller.py.jinja"
  - "{{plugin_slug}}/ui/components/timeline_widget.py.jinja"
  {% endif %}
  {% if not enable_search -%}
  - "{{plugin_slug}}/services/search_service.py.jinja"
  {% endif %}
```

### Technique 3: Post-Generation Hooks

Run commands after generation:

```yaml
# copier.yml
_tasks:
  - "cd {{_copier_conf.dst_path}}/{{plugin_slug}}/tauri-map && npm install"
  - "python -m black {{_copier_conf.dst_path}}/{{plugin_slug}}/"
```

### Technique 4: Template Inheritance

Share common code across templates:

```jinja2
{# _base_service.py.jinja #}
from core.services.base_service import BaseService

class {{ ServiceName }}(BaseService):
    def __init__(self):
        super().__init__("{{ ServiceName }}")

    {% block methods %}
    {# Subclasses override this #}
    {% endblock %}
```

```jinja2
{# my_service.py.jinja #}
{% extends "_base_service.py.jinja" %}

{% block methods %}
def custom_method(self):
    pass
{% endblock %}
```

### Technique 5: Jinja2 Macros

Reusable code snippets:

```jinja2
{# _macros.jinja #}
{% macro generate_dataclass(name, fields) -%}
@dataclass
class {{ name }}:
    {% for field in fields -%}
    {{ field.name }}: {{ field.type }}
    {% endfor %}
{%- endmacro %}
```

```jinja2
{# models.py.jinja #}
{% import "_macros.jinja" as macros %}

{{ macros.generate_dataclass("GPSPoint", [
    {"name": "latitude", "type": "float"},
    {"name": "longitude", "type": "float"}
]) }}
```

---

## 8. Troubleshooting Guide

### Problem: Variables Not Replaced

**Symptom**: Generated files contain `{{variable_name}}` literally.

**Causes**:
1. Forgot `.jinja` extension on template file
2. Used wrong delimiter syntax
3. Variable not defined in `copier.yml`

**Solutions**:
```bash
# Check file extensions
find template/ -type f ! -name "*.jinja"

# Check for undefined variables
copier copy . test --data-file test-answers.yml --vcs-ref HEAD
```

### Problem: Conditional Blocks Not Working

**Symptom**: Code appears regardless of condition.

**Causes**:
1. Wrong boolean syntax (use `{{ var | lower }}` for `true`/`false`)
2. String comparison instead of boolean
3. Whitespace issues

**Solutions**:
```jinja2
{# WRONG #}
{% if has_animation == "true" %}  ← String comparison

{# RIGHT #}
{% if has_animation %}  ← Boolean
```

### Problem: Syntax Errors in Generated Code

**Symptom**: Python/Rust/HTML syntax errors after generation.

**Causes**:
1. Whitespace stripped incorrectly
2. Indentation broken by Jinja2
3. Quote escaping issues

**Solutions**:
```jinja2
{# Use - to control whitespace #}
{% if condition -%}
code here
{% endif -%}

{# Preserve indentation with proper spacing #}
class Foo:
    {% if bar -%}
    def method(self):  ← Maintain 4-space indent
        pass
    {% endif -%}
```

### Problem: Copier Update Conflicts

**Symptom**: `copier update` overwrites custom changes.

**Causes**:
1. Template changed significantly
2. User edited generated boilerplate
3. No merge strategy configured

**Solutions**:
```yaml
# copier.yml - Skip user-modified files
_skip_if_exists:
  - "{{plugin_slug}}/custom_*.py"
  - "{{plugin_slug}}/services/user_logic.py"
```

---

## 9. Future Enhancements

### Enhancement 1: Multiple Map Providers

Add support for Leaflet, Google Maps, etc:

```yaml
# copier.yml
map_provider:
  type: str
  choices:
    - mapbox
    - leaflet
    - google_maps
  default: mapbox
```

```jinja2
{# Conditional HTML generation #}
{% if map_provider == 'mapbox' -%}
{% include 'mapbox.html.jinja' %}
{% elif map_provider == 'leaflet' -%}
{% include 'leaflet.html.jinja' %}
{% endif %}
```

### Enhancement 2: Plugin Marketplace

Host templates in a registry:

```bash
# Install from marketplace
copier copy gh:tauri-plugins/mapbox-python my-plugin

# Or from URL
copier copy https://example.com/templates/mapbox.git my-plugin
```

### Enhancement 3: AI-Assisted Generation

Use LLMs to generate custom logic:

```python
# Generate custom fields with AI
custom_fields = ai_generate_fields(
    "Generate EXIF fields for camera metadata"
)

# Pass to Copier
copier copy template/ output/ --data custom_fields=custom_fields
```

---

## 10. Appendix: Quick Reference

### Copier Commands

```bash
# Copy template
copier copy <template> <output>

# Copy with defaults
copier copy <template> <output> --defaults

# Copy with data file
copier copy <template> <output> --data-file answers.yml

# Update existing project
cd <project>
copier update

# Recopy (force regeneration)
copier copy <template> <output> --force
```

### Jinja2 Cheat Sheet

```jinja2
{# Variables #}
{{ variable }}

{# Conditionals #}
{% if condition %}...{% endif %}
{% if cond1 %}...{% elif cond2 %}...{% else %}...{% endif %}

{# Loops #}
{% for item in items %}{{ item }}{% endfor %}

{# Filters #}
{{ text | upper }}
{{ text | lower }}
{{ text | title }}
{{ text | replace('old', 'new') }}
{{ list | join(', ') }}
{{ json_str | from_json }}
{{ bool | lower }}  {# true/false #}

{# Whitespace control #}
{% if cond -%}  ← Strip whitespace after
{% endif %}

{%- if cond %}  ← Strip whitespace before
{% endif %}

{# Comments (not in output) #}
{# This is a comment #}

{# Include other templates #}
{% include 'other_template.jinja' %}

{# Macros (reusable snippets) #}
{% macro my_macro(arg) -%}
  {{ arg }}
{%- endmacro %}
{{ my_macro('value') }}
```

### Variable Naming Conventions

```python
# Snake_case for files/modules
plugin_slug = "vehicle_tracking"

# PascalCase for classes
DataModelName = "VehicleTrackingData"
ServiceName = "VehicleTrackingService"

# camelCase for JavaScript
jsObjectName = "vehicleTrackingMap"

# kebab-case for URLs/IDs
html_id = "vehicle-tracking-map"
```

### Common Filters

```jinja2
{# String manipulation #}
{{ "hello world" | title }}        → "Hello World"
{{ "HELLO" | lower }}              → "hello"
{{ "hello" | upper }}              → "HELLO"
{{ "  text  " | trim }}            → "text"
{{ "hello_world" | replace('_', ' ') }}  → "hello world"

{# Lists #}
{{ [1, 2, 3] | join(', ') }}       → "1, 2, 3"
{{ [1, 2, 3] | length }}           → 3
{{ [1, 2, 3] | first }}            → 1
{{ [1, 2, 3] | last }}             → 3

{# JSON #}
{{ '{"a": 1}' | from_json }}       → Python dict

{# Defaults #}
{{ undefined_var | default('fallback') }}  → "fallback"
```

---

## Summary: What You've Learned

Congratulations! You now understand:

1. **Why templates matter** - Reduce duplication, increase consistency
2. **How Copier works** - Questions → Variables → Generation
3. **Pattern extraction** - Identifying variance in existing code
4. **Template design** - Planning before implementing
5. **Jinja2 templating** - Dynamic code generation with control flow
6. **Testing strategies** - Validating generated code
7. **Advanced techniques** - Hooks, macros, inheritance
8. **Troubleshooting** - Common issues and solutions

**Key Pedagogical Approaches Used:**
- **Learn by doing** - Hands-on exercises throughout
- **Explain before coding** - Concepts introduced before implementation
- **Visual aids** - Diagrams and tables for complex concepts
- **Real examples** - Based on actual vehicle_tracking plugin
- **Progressive complexity** - Simple to advanced techniques
- **Checkpoints** - Verify understanding at each phase
- **Troubleshooting** - Real problems and solutions

**Next Steps:**
1. Generate your first plugin with this template
2. Customize the generated code
3. Iterate on the template based on your needs
4. Share your template with your team
5. Build a template library for common patterns

**Estimated Time Investment (UPDATED):**

**OLD ESTIMATE (Complex Template Approach):**
- Understanding concepts: 2 hours
- Building template: 18-26 hours
- Testing and refinement: 2-3 hours
- **Total**: ~22-31 hours for first template

**NEW ESTIMATE (Kitchen Sink Approach):**
- Understanding concepts: 2 hours
- Copy + Templatize vehicle_tracking: 2-3 hours
- Create deletion guide: 30 minutes
- Testing and refinement: 1 hour
- **Total**: ~5-6 hours for first template

**Time saved:** 17-25 hours (76-81% reduction)

---

**ROI (Return on Investment) - UPDATED:**

| Metric | Without Template | With Complex Template | With Kitchen Sink Template |
|--------|------------------|----------------------|---------------------------|
| **Template creation time** | N/A | 22-31 hours | 5-6 hours |
| **New plugin from scratch** | 2-3 weeks (80-120h) | Same | Same |
| **New plugin with template** | N/A | 30-60 min | 30-60 min |
| **Customization time** | Included above | 2-4 hours (adding features) | 1-2 hours (deleting features) |
| **Total for first plugin** | 80-120h | 26-35h + template | 7-9h + template |
| **Break-even point** | N/A | After 2-3 plugins | After 1-2 plugins |
| **Long-term productivity** | 1x baseline | 8-10x improvement | 10-15x improvement |

**Key Insights:**
1. **Kitchen sink breaks even FASTER** (1-2 plugins vs. 2-3 plugins)
2. **Deletion is faster than addition** (1-2h trim vs. 2-4h build)
3. **Template creation is 5x faster** (5-6h vs. 22-31h)
4. **Lower risk** (copying working code vs. designing abstractions)

---

**When to Use Kitchen Sink Approach:**
- ✅ You have a complete, working reference implementation
- ✅ Features are modular and can be independently deleted
- ✅ Users prefer "delete what you don't need" over "answer 20 questions"
- ✅ Time-to-first-plugin is critical
- ✅ Maintenance is low (one source of truth: the reference implementation)

**When to Use Complex Template Approach:**
- ⚠️ Reference implementation is incomplete or has many bugs
- ⚠️ Features are tightly coupled (hard to delete independently)
- ⚠️ Users need precise control over every aspect
- ⚠️ Template size is a constraint (bandwidth, storage)
- ⚠️ You have unlimited time for template development

**Our Verdict:** Kitchen sink wins for this use case. Vehicle tracking is production-ready, modular, and well-documented.

---

**Document Status**: Complete ✅
**Last Updated**: 2025-10-10
**Template Version**: 1.0
**Maintainer**: CFSA Development Team
