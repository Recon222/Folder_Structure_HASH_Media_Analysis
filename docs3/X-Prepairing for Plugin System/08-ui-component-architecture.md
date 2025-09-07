# Document 8: UI Component Architecture & Plugin Integration

## Natural Language Technical Overview

### Understanding the UI Component Responsibility Split

The Folder Structure Utility's transition to a plugin architecture requires a careful separation of UI responsibilities that balances consistency with plugin flexibility. After analyzing the current architecture, it's clear that plugins need complete control over their user interfaces while the core provides foundational elements for consistency.

**The Core Provides UI Foundations**: The core application should provide the essential infrastructure for consistent user experience: the theme system for visual coherence, basic styled widgets following Carolina Blue patterns, system-wide error and success handling, and shared utilities like logging display. These are the foundational elements that ensure all plugins feel like part of the same application.

**Plugins Create Complete User Experiences**: Each plugin must have complete freedom to create forms, file selection interfaces, and workflows that match their specific use cases. A forensic plugin needs case information forms with evidence metadata, while a hash verification plugin might need simple file lists with algorithm selection. A batch processing plugin requires queue management interfaces entirely different from single-operation forms.

**The Critical Insight**: The current FormPanel and FilesPanel components are too opinionated and specific to forensic workflows. They embed assumptions about data models (FormData with occurrence numbers and business names) and interaction patterns (evidence file selection) that don't apply to all plugin types. These should be examples of what plugins can build, not constraints they must accept.

**System-Level vs Plugin-Level Components**: Some components truly are system-level (error notifications, success celebrations, logging display) because they maintain architectural consistency and integrate with core services. Others are plugin-level (forms, file selection, custom controls) because they vary dramatically based on plugin functionality.

**Theme-Based Consistency**: Visual consistency comes not from sharing complete components, but from sharing the theme system, styling patterns, and basic widget implementations. This allows plugins to create unique interfaces that still feel cohesive within the application ecosystem.

### Benefits of This Architecture

**Plugin Flexibility**: Plugins can create forms and interfaces perfectly suited to their specific use cases without being constrained by generic components designed for different workflows.

**Visual Consistency**: All plugins inherit the same theme system, color palette, and styling patterns, ensuring a coherent look and feel across the entire application.

**System Integration**: Core system-level components (error handling, success notifications, logging) maintain architectural consistency while plugins control their own business logic UI.

**Development Efficiency**: Plugin developers get theme-consistent basic widgets and system integration without having to reimplement foundational elements, but aren't forced into inappropriate UI patterns.

**Maintainable Architecture**: Clear separation between system-level concerns (handled by core) and plugin-specific concerns (handled by plugins) creates a maintainable, extensible architecture.

---

## Senior Developer Technical Specification

### Core UI Foundation System (Provided by Core)

The core application provides foundational UI elements that enable plugins to create consistent, integrated user interfaces while maintaining complete control over their specific functionality.

#### Carolina Blue Theme System

**Location**: `ui/styles/carolina_blue.py`  
**Purpose**: Consistent visual styling foundation for all UI components

```python
class CarolinaBlueTheme:
    """Carolina Blue theme constants and styling patterns"""
    
    # Color palette
    PRIMARY_BLUE = "#4B9CD3"      # Carolina Blue primary
    SECONDARY_BLUE = "#6BA6CD"    # Lighter blue for hover states
    SUCCESS_GREEN = "#2E8B57"     # Success operations and confirmations
    WARNING_ORANGE = "#FF8C00"    # Warning states and cautions
    ERROR_RED = "#DC143C"         # Error conditions and failures
    
    # UI element styles
    BUTTON_STYLE = """
        QPushButton {
            background-color: %s;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: %s;
        }
        QPushButton:pressed {
            background-color: %s;
        }
        QPushButton:disabled {
            background-color: #cccccc;
            color: #666666;
        }
    """ % (PRIMARY_BLUE, SECONDARY_BLUE, PRIMARY_BLUE + "aa")
```

**Plugin Integration**:
```python
class PluginWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._apply_carolina_blue_theme()
    
    def _apply_carolina_blue_theme(self):
        """Apply consistent Carolina Blue theme to plugin UI"""
        theme = CarolinaBlueTheme()
        self.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {theme.PRIMARY_BLUE};
                border-radius: 5px;
                margin: 3px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                color: {theme.PRIMARY_BLUE};
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
            {theme.BUTTON_STYLE}
        """)
```

#### Core Widget Factory System

**Location**: `ui/core_widgets/widget_factory.py`  
**Purpose**: Factory methods for creating consistently themed basic widgets

```python
class CoreWidgetFactory:
    """Factory for creating themed basic widgets"""
    
    @staticmethod
    def create_primary_button(text: str, icon: str = None) -> QPushButton:
        """Create primary action button with Carolina Blue styling"""
        button = QPushButton(text)
        if icon:
            button.setIcon(QIcon(icon))
        
        theme = CarolinaBlueTheme()
        button.setStyleSheet(theme.BUTTON_STYLE)
        return button
    
    @staticmethod
    def create_input_field(label: str = None, placeholder: str = None, 
                          validator: QValidator = None) -> Union[QLineEdit, QWidget]:
        """Create themed input field with optional label"""
        if label:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)
            
            label_widget = QLabel(label)
            label_widget.setStyleSheet("font-weight: bold; color: #333333;")
            layout.addWidget(label_widget)
            
            input_field = QLineEdit()
            if placeholder:
                input_field.setPlaceholderText(placeholder)
            if validator:
                input_field.setValidator(validator)
            
            input_field.setStyleSheet("""
                QLineEdit {
                    padding: 6px 8px;
                    border: 2px solid #ddd;
                    border-radius: 4px;
                    font-size: 14px;
                }
                QLineEdit:focus {
                    border-color: #4B9CD3;
                }
            """)
            layout.addWidget(input_field)
            
            return widget
        else:
            input_field = QLineEdit()
            if placeholder:
                input_field.setPlaceholderText(placeholder)
            if validator:
                input_field.setValidator(validator)
            return input_field
    
    @staticmethod
    def create_group_box(title: str) -> QGroupBox:
        """Create themed group box container"""
        group_box = QGroupBox(title)
        theme = CarolinaBlueTheme()
        group_box.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {theme.PRIMARY_BLUE};
                border-radius: 5px;
                margin: 3px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                color: {theme.PRIMARY_BLUE};
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
        """)
        return group_box
    
    @staticmethod
    def create_file_dialog_button(text: str, dialog_type: str = 'file') -> QPushButton:
        """Create button that opens file dialog"""
        button = CoreWidgetFactory.create_primary_button(text)
        
        def open_dialog():
            if dialog_type == 'file':
                path, _ = QFileDialog.getOpenFileName()
            elif dialog_type == 'files':
                paths, _ = QFileDialog.getOpenFileNames()
                return paths
            elif dialog_type == 'folder':
                path = QFileDialog.getExistingDirectory()
            else:
                raise ValueError(f"Unknown dialog type: {dialog_type}")
            return path
        
        button.clicked.connect(open_dialog)
        return button
```

#### LogConsole - System-Wide Logging Display

**Location**: `ui/components/log_console.py`  
**Purpose**: Shared logging display component (system-level requirement)

```python
class LogConsole(QTextEdit):
    """System-wide console widget for displaying operation messages"""
    
    # Signals for integration
    message_logged = Signal(str, str)  # timestamp, message
    log_cleared = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumHeight(150)  # Consistent sizing across all plugins
        self.settings = settings  # Core settings integration
```

**Why This Component is Shared**:
- **System Integration**: Integrates with core settings for auto-scroll behavior
- **Consistency**: Provides uniform logging experience across all plugins
- **Thread Safety**: Handles messages from worker threads safely
- **Standard Formatting**: Ensures consistent timestamp and message formatting

**Plugin Integration Pattern**:
```python
class PluginWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        # LogConsole is provided as a system component
        self.log_console = LogConsole()
        
        # Connect plugin operations to shared logging
        self.worker_thread.progress_update.connect(
            lambda progress, msg: self.log_console.log(f"Progress {progress}%: {msg}")
        )
```

**Justification for Sharing**: Unlike forms or file selection (which vary by plugin), logging should be consistent across the entire application. Users expect the same timestamp format, auto-scroll behavior, and visual appearance regardless of which plugin is running.

#### ErrorNotificationManager - Non-Modal Error Display

**Location**: `ui/components/error_notification_system.py`  
**Purpose**: Thread-safe, non-modal error notifications with severity-based styling

```python
class ErrorNotificationManager(QWidget):
    """Manages non-modal error notifications for thread-safe error display"""
    
    def show_error(self, error: FSAError, context: dict = None, parent: QWidget = None):
        """Display error notification with appropriate severity styling"""
        notification = ErrorNotification(error, context or {}, str(uuid.uuid4()))
        self._manage_notification_display(notification, parent)
```

**Key Features**:
- **Thread-Safe**: Can be called from worker threads via Qt signals
- **Severity Styling**: Visual indicators for INFO, WARNING, ERROR, CRITICAL
- **Auto-Dismiss**: Non-critical errors auto-dismiss after timeout
- **Detail Expansion**: Click for full error details and context
- **Queue Management**: Multiple errors displayed gracefully

**Plugin Integration Pattern**:
```python
class PluginService(BaseService):
    def risky_operation(self) -> Result:
        try:
            result = self._perform_operation()
            return Result.success(result)
        except Exception as e:
            error = FSAError(
                f"Plugin operation failed: {e}",
                user_message="Plugin operation failed. Please try again."
            )
            # Error automatically routed to notification system
            handle_error(error, {'plugin': self.__class__.__name__})
            return Result.error(error)
```

**Shared Functionality**:
- Consistent error styling across all plugins
- Thread-safe error display from worker operations
- Severity-appropriate auto-dismiss behavior
- Detailed error information on demand

### Core Dialog Library (Provided by Core)

#### SuccessDialog - Operation Completion Celebration

**Location**: `ui/dialogs/success_dialog.py`  
**Purpose**: Modal success dialog with Carolina Blue theme and rich content display

```python
class SuccessDialog(QDialog):
    """Modal success dialog with rich formatting and theme integration"""
    
    def __init__(self, title: str = "Operation Complete!", 
                 message: str = "", 
                 details: str = "",
                 parent=None):
        super().__init__(parent)
        self.setModal(True)  # Block interaction until acknowledged
        self._apply_theme()  # Carolina Blue integration
```

**Key Features**:
- **Modal Behavior**: User must acknowledge success before continuing
- **Rich Content**: Formatted messages with performance statistics
- **Theme Integration**: Consistent Carolina Blue styling
- **Large Display**: 750x550 size for comprehensive success information
- **Auto-Centering**: Automatically centers on parent or screen

**Plugin Integration Pattern**:
```python
class PluginController(BaseController):
    def handle_operation_success(self, result: FileOperationResult):
        """Display plugin success using shared dialog"""
        success_message = self.success_message_builder.build_plugin_success_message(
            result,
            plugin_name=self.plugin_name
        )
        SuccessDialog.show_success_message(success_message, parent=self.main_widget)
```

#### Settings Dialogs - Configuration Interfaces

**Locations**: 
- `ui/dialogs/user_settings.py` - User preferences
- `ui/dialogs/zip_settings.py` - Archive configuration  

**Purpose**: Consistent settings interfaces with automatic persistence

**Key Features**:
- **Tabbed Organization**: Logical grouping of related settings
- **Automatic Binding**: UI controls automatically sync with SettingsManager
- **Validation Feedback**: Real-time validation with visual indicators
- **Help Text**: Tooltips and descriptions for all options

**Plugin Integration Pattern**:
```python
class PluginSettingsDialog(QDialog):
    """Plugin-specific settings dialog following core patterns"""
    
    def __init__(self, plugin_settings: PluginSettingsManager, parent=None):
        super().__init__(parent)
        self.settings = plugin_settings
        
        # Follow core dialog patterns
        self.setWindowTitle("Plugin Settings")
        self.setModal(True)
        self._create_tabbed_interface()
        self._bind_settings_to_controls()
```

### Theme System Integration

#### Carolina Blue Theme Consistency

**Location**: `ui/styles/carolina_blue.py`  
**Purpose**: Consistent visual styling across core and plugin components

```python
class CarolinaBlueTheme:
    """Carolina Blue theme constants and styling"""
    
    PRIMARY_BLUE = "#4B9CD3"      # Carolina Blue
    SUCCESS_GREEN = "#2E8B57"     # Success operations
    WARNING_ORANGE = "#FF8C00"    # Warning states
    ERROR_RED = "#DC143C"         # Error conditions
```

**Plugin Theme Integration**:
```python
class PluginWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply Carolina Blue theme to plugin components"""
        theme = CarolinaBlueTheme()
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.PRIMARY_BLUE};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {theme.PRIMARY_BLUE}cc;
            }}
        """)
```

### Plugin-Created UI Components (Plugin Responsibility)

Plugins have complete control over their user interfaces, creating custom forms, file selection, and business logic controls tailored to their specific needs.

#### Custom Form Creation Patterns

Plugins create their own forms using core widget factory for consistent styling:

```python
class ForensicPlugin(IPlugin):
    def create_widget(self) -> QWidget:
        """Create complete forensic processing interface"""
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # Plugin creates its own forensic case form
        self.case_form = self._create_forensic_case_form()
        main_layout.addWidget(self.case_form)
        
        # Plugin creates its own evidence file selection
        self.evidence_selector = self._create_evidence_file_selector()
        main_layout.addWidget(self.evidence_selector)
        
        # Use shared log console
        self.log_console = LogConsole()
        main_layout.addWidget(self.log_console)
        
        # Plugin-specific process button using core styling
        self.process_button = CoreWidgetFactory.create_primary_button(
            "Start Forensic Processing"
        )
        self.process_button.clicked.connect(self.start_forensic_processing)
        main_layout.addWidget(self.process_button)
        
        return main_widget
    
    def _create_forensic_case_form(self) -> QWidget:
        """Create forensic-specific case information form"""
        form_group = CoreWidgetFactory.create_group_box("Case Information")
        layout = QGridLayout(form_group)
        
        # Forensic-specific fields using core widget factory
        self.occurrence_field = CoreWidgetFactory.create_input_field(
            "Occurrence Number", "Enter case occurrence number"
        )
        layout.addWidget(self.occurrence_field, 0, 0, 1, 2)
        
        self.business_field = CoreWidgetFactory.create_input_field(
            "Business Name", "Enter business or location name"
        )
        layout.addWidget(self.business_field, 1, 0, 1, 2)
        
        self.address_field = CoreWidgetFactory.create_input_field(
            "Location Address", "Enter address of incident"
        )
        layout.addWidget(self.address_field, 2, 0, 1, 2)
        
        # Forensic-specific date/time controls
        self.datetime_group = QWidget()
        datetime_layout = QHBoxLayout(self.datetime_group)
        datetime_layout.addWidget(QLabel("Incident Date/Time:"))
        
        self.incident_datetime = QDateTimeEdit()
        self.incident_datetime.setDateTime(QDateTime.currentDateTime())
        datetime_layout.addWidget(self.incident_datetime)
        
        layout.addWidget(self.datetime_group, 3, 0, 1, 2)
        
        return form_group
    
    def _create_evidence_file_selector(self) -> QWidget:
        """Create forensic-specific evidence file selection"""
        selector_group = CoreWidgetFactory.create_group_box("Evidence Files")
        layout = QVBoxLayout(selector_group)
        
        # Evidence file list
        self.evidence_list = QListWidget()
        layout.addWidget(self.evidence_list)
        
        # Forensic-specific buttons
        button_layout = QHBoxLayout()
        
        add_files_btn = CoreWidgetFactory.create_primary_button("Add Evidence Files")
        add_files_btn.clicked.connect(self._add_evidence_files)
        button_layout.addWidget(add_files_btn)
        
        add_folder_btn = CoreWidgetFactory.create_primary_button("Add Evidence Folder")
        add_folder_btn.clicked.connect(self._add_evidence_folder)
        button_layout.addWidget(add_folder_btn)
        
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected_evidence)
        button_layout.addWidget(remove_btn)
        
        layout.addWidget(QWidget())  # Spacer
        layout.addLayout(button_layout)
        
        return selector_group
```

#### Different Plugin Types, Different Forms

Each plugin type creates forms optimized for its specific use case:

```python
class HashVerificationPlugin(IPlugin):
    def create_widget(self) -> QWidget:
        """Hash plugin needs minimal form - just files and algorithm selection"""
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        
        # Simple file selection for hashing
        self.hash_files_selector = self._create_hash_file_selector()
        layout.addWidget(self.hash_files_selector)
        
        # Hash algorithm selection (plugin-specific)
        self.algorithm_selector = self._create_algorithm_selector()
        layout.addWidget(self.algorithm_selector)
        
        # Shared log console
        self.log_console = LogConsole()
        layout.addWidget(self.log_console)
        
        return main_widget
    
    def _create_algorithm_selector(self) -> QWidget:
        """Hash-specific algorithm selection"""
        group = CoreWidgetFactory.create_group_box("Hash Algorithm")
        layout = QVBoxLayout(group)
        
        self.sha256_radio = QRadioButton("SHA-256 (Recommended)")
        self.md5_radio = QRadioButton("MD5 (Legacy)")
        self.sha256_radio.setChecked(True)
        
        layout.addWidget(self.sha256_radio)
        layout.addWidget(self.md5_radio)
        
        return group

class BatchProcessingPlugin(IPlugin):
    def create_widget(self) -> QWidget:
        """Batch plugin needs queue management, no case forms"""
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        
        # Batch queue management (completely different from forensic forms)
        self.batch_queue = self._create_batch_queue_widget()
        layout.addWidget(self.batch_queue)
        
        # Queue controls
        self.queue_controls = self._create_queue_controls()
        layout.addWidget(self.queue_controls)
        
        # Shared log console
        self.log_console = LogConsole()
        layout.addWidget(self.log_console)
        
        return main_widget
    
    def _create_batch_queue_widget(self) -> QWidget:
        """Batch-specific queue management interface"""
        group = CoreWidgetFactory.create_group_box("Batch Processing Queue")
        layout = QVBoxLayout(group)
        
        # Queue list
        self.queue_list = QListWidget()
        layout.addWidget(self.queue_list)
        
        # Queue statistics
        self.stats_label = QLabel("Queue: 0 jobs, 0 pending")
        layout.addWidget(self.stats_label)
        
        return group
```

**Key Point**: Each plugin creates forms that match its workflow - forensic plugins need case information, hash plugins need algorithm selection, batch plugins need queue management. No single shared form could serve all these different needs.

#### Plugin-Specific Custom Controls

Plugins create specialized controls for their unique functionality while following established patterns.

**Custom Control Creation Pattern**:
```python
class ForensicOptionsWidget(QGroupBox):
    """Plugin-specific options for forensic processing"""
    
    options_changed = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__("Forensic Options", parent)
        self._setup_ui()
        
    def _setup_ui(self):
        """Create forensic-specific controls"""
        layout = QVBoxLayout(self)
        
        # Plugin-specific options
        self.hash_verification = QCheckBox("Verify file integrity with hashes")
        self.evidence_sealing = QCheckBox("Generate evidence sealing report")
        self.chain_of_custody = QCheckBox("Create chain of custody documentation")
        
        layout.addWidget(self.hash_verification)
        layout.addWidget(self.evidence_sealing) 
        layout.addWidget(self.chain_of_custody)
        
        # Follow theme patterns
        self._apply_plugin_theme()
    
    def get_options(self) -> dict:
        """Return current plugin option values"""
        return {
            'hash_verification': self.hash_verification.isChecked(),
            'evidence_sealing': self.evidence_sealing.isChecked(),
            'chain_of_custody': self.chain_of_custody.isChecked()
        }
```

#### Plugin Settings Interfaces

Plugins create their own settings dialogs following core patterns for consistency.

**Plugin Settings Dialog Pattern**:
```python
class PluginSettingsDialog(QDialog):
    """Settings dialog for plugin-specific configuration"""
    
    def __init__(self, plugin_settings: PluginSettingsManager, parent=None):
        super().__init__(parent)
        self.settings = plugin_settings
        
        # Follow core dialog conventions
        self.setWindowTitle(f"{self.settings.plugin_id} Settings")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        self._create_tabbed_interface()
        self._bind_settings_to_controls()
        self._apply_theme()
    
    def _create_tabbed_interface(self):
        """Create tabbed settings interface like core dialogs"""
        layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Plugin-specific tabs
        self._create_general_tab()
        self._create_advanced_tab()
        
        # Standard dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
```

### Signal Integration Patterns

#### Component Communication

Plugins orchestrate communication between shared components and plugin-specific elements through Qt signals.

**Signal Connection Pattern**:
```python
class PluginWidget(QWidget):
    def _connect_component_signals(self):
        """Connect shared component signals to plugin logic"""
        
        # Form changes trigger plugin validation
        self.form_panel.form_data_changed.connect(self.validate_form_data)
        
        # File selection changes update plugin state
        self.files_panel.files_changed.connect(self.update_processing_state)
        
        # Template changes affect plugin configuration
        self.template_selector.template_changed.connect(self.on_template_changed)
        
        # Plugin operations log to shared console
        self.worker_thread.progress_update.connect(
            lambda progress, msg: self.log_console.log(f"{msg} ({progress}%)")
        )
        
        # Errors route to shared notification system
        self.plugin_service.error_occurred.connect(
            lambda error, context: self.error_manager.show_error(error, context, self)
        )
```

#### Cross-Component Data Flow

**Data Binding and State Management**:
```python
class PluginController(BaseController):
    def __init__(self, plugin_widget: QWidget):
        super().__init__()
        self.widget = plugin_widget
        
        # Shared FormData instance
        self.form_data = FormData()
        
        # Service dependencies
        self.path_service = self._get_service(IPathService)
        self.file_service = self._get_service(IFileOperationService)
        
    def validate_form_data(self, field_name: str, value: Any):
        """Handle form data changes with validation"""
        validation_service = self._get_service(IValidationService)
        validation_result = validation_service.validate_form_data(self.form_data)
        
        if not validation_result.success:
            # Show validation errors via shared error system
            self.widget.error_manager.show_error(
                validation_result.error,
                {'field': field_name, 'value': str(value)},
                self.widget
            )
    
    def update_processing_state(self):
        """Update plugin state based on file selection"""
        files = self.widget.files_panel.entries
        can_process = len(files) > 0 and self.form_data.is_valid()
        
        self.widget.process_button.setEnabled(can_process)
        
        if can_process:
            file_count = sum(1 for f in files if f.type == 'file')
            folder_count = sum(1 for f in files if f.type == 'folder')
            self.widget.log_console.log(f"Ready to process {file_count} files, {folder_count} folders")
```

### Plugin Development Guidelines

#### UI Consistency Requirements

**Visual Standards**:
1. **Use Core Widget Factory**: Create all basic controls using CoreWidgetFactory for consistent theming
2. **Follow Carolina Blue Theme**: Apply theme system to all custom plugin controls
3. **Use System Components**: Always use LogConsole, ErrorNotificationManager, SuccessDialog for system-level functionality
4. **Create Custom Forms**: Build forms specific to plugin needs using core styling
5. **Signal Integration**: Connect component signals for proper data flow between plugin-created components

**Layout Standards**:
1. **Consistent Spacing**: Use standard margins and padding (8px, 16px) provided by core widgets
2. **Group Organization**: Use CoreWidgetFactory.create_group_box() for logical grouping
3. **Button Styling**: Use CoreWidgetFactory.create_primary_button() for main actions
4. **System Integration**: Use shared LogConsole for progress display
5. **Responsive Design**: Create layouts that work with different window sizes

#### Component Reuse Patterns

**Shared Component Integration**:
```python
# Standard plugin layout template
class StandardPluginLayout:
    """Template for consistent plugin layout"""
    
    @staticmethod
    def create_standard_layout(plugin_widget: QWidget, 
                             custom_controls: QWidget = None) -> QVBoxLayout:
        """Create standard plugin layout with shared components"""
        layout = QVBoxLayout(plugin_widget)
        
        # Template selector (if applicable)
        template_selector = TemplateSelector()
        layout.addWidget(template_selector)
        
        # Main content area
        content_splitter = QSplitter(Qt.Horizontal)
        
        # Left: Form and files
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(FormPanel(plugin_widget.form_data))
        left_layout.addWidget(FilesPanel())
        content_splitter.addWidget(left_panel)
        
        # Right: Custom controls and log
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        if custom_controls:
            right_layout.addWidget(custom_controls)
        right_layout.addWidget(LogConsole())
        content_splitter.addWidget(right_panel)
        
        layout.addWidget(content_splitter)
        
        return layout
```

This comprehensive UI component architecture provides plugins with powerful, consistent building blocks while maintaining complete control over their user experience design and business logic integration.