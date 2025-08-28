#!/usr/bin/env python3
"""
Template import dialog with validation and preview functionality
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QFileDialog, QTextEdit, QGroupBox, QTabWidget, QWidget,
    QTreeWidget, QTreeWidgetItem, QProgressBar, QCheckBox,
    QDialogButtonBox, QSplitter, QFrame, QScrollArea,
    QMessageBox, QLineEdit, QFormLayout
)

from core.services import get_service, IPathService
from core.template_validator import ValidationLevel
from core.exceptions import FSAError
from core.logger import logger


class ValidationIssueWidget(QFrame):
    """Widget to display a single validation issue"""
    
    def __init__(self, issue: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.issue = issue
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the issue display UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        
        # Issue level indicator
        level = self.issue.get("level", "info")
        level_label = QLabel(self._get_level_icon(level))
        level_label.setFixedWidth(20)
        layout.addWidget(level_label)
        
        # Issue content
        content_layout = QVBoxLayout()
        
        # Main message
        message = QLabel(self.issue.get("message", ""))
        message.setWordWrap(True)
        message.setStyleSheet(f"color: {self._get_level_color(level)}; font-weight: bold;")
        content_layout.addWidget(message)
        
        # Path information
        path = self.issue.get("path", "")
        if path:
            path_label = QLabel(f"Path: {path}")
            path_label.setStyleSheet("color: #666; font-size: 10px;")
            content_layout.addWidget(path_label)
        
        # Suggestion
        suggestion = self.issue.get("suggestion", "")
        if suggestion:
            suggestion_label = QLabel(f"💡 {suggestion}")
            suggestion_label.setWordWrap(True)
            suggestion_label.setStyleSheet("color: #0066cc; font-style: italic; margin-top: 2px;")
            content_layout.addWidget(suggestion_label)
        
        layout.addLayout(content_layout, 1)
        
        # Set background color based on level
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {self._get_background_color(level)};
                border: 1px solid {self._get_border_color(level)};
                border-radius: 4px;
                margin: 2px;
            }}
        """)
    
    def _get_level_icon(self, level: str) -> str:
        """Get icon for validation level"""
        icons = {
            "error": "❌",
            "warning": "⚠️", 
            "info": "ℹ️",
            "success": "✅"
        }
        return icons.get(level, "ℹ️")
    
    def _get_level_color(self, level: str) -> str:
        """Get text color for validation level"""
        colors = {
            "error": "#cc0000",
            "warning": "#ff6600",
            "info": "#0066cc",
            "success": "#00cc00"
        }
        return colors.get(level, "#000000")
    
    def _get_background_color(self, level: str) -> str:
        """Get background color for validation level"""
        colors = {
            "error": "#ffe6e6",
            "warning": "#fff3e6",
            "info": "#e6f3ff",
            "success": "#e6ffe6"
        }
        return colors.get(level, "#f5f5f5")
    
    def _get_border_color(self, level: str) -> str:
        """Get border color for validation level"""
        colors = {
            "error": "#ff9999",
            "warning": "#ffcc99",
            "info": "#99ccff",
            "success": "#99ff99"
        }
        return colors.get(level, "#cccccc")


class TemplatePreviewWidget(QFrame):
    """Widget to show template preview with sample data"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the preview UI"""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("📁 Template Preview")
        title.setStyleSheet("font-weight: bold; font-size: 12px; margin-bottom: 8px;")
        layout.addWidget(title)
        
        # Preview tree
        self.preview_tree = QTreeWidget()
        self.preview_tree.setHeaderLabels(["Template", "Preview Path", "Archive Name"])
        self.preview_tree.setAlternatingRowColors(True)
        layout.addWidget(self.preview_tree)
        
        # Sample data controls
        sample_group = QGroupBox("Sample Data")
        sample_layout = QFormLayout(sample_group)
        
        self.sample_occurrence = QLineEdit("2024-TEST-001")
        self.sample_business = QLineEdit("Sample Business")
        self.sample_location = QLineEdit("123 Test Street")
        
        sample_layout.addRow("Occurrence Number:", self.sample_occurrence)
        sample_layout.addRow("Business Name:", self.sample_business)
        sample_layout.addRow("Location Address:", self.sample_location)
        
        # Update button
        update_btn = QPushButton("Update Preview")
        update_btn.clicked.connect(self.update_preview)
        sample_layout.addRow(update_btn)
        
        layout.addWidget(sample_group)
        
        # Connect sample data changes to auto-update (with delay)
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.update_preview)
        
        self.sample_occurrence.textChanged.connect(self._schedule_update)
        self.sample_business.textChanged.connect(self._schedule_update)
        self.sample_location.textChanged.connect(self._schedule_update)
    
    def _schedule_update(self):
        """Schedule preview update with delay"""
        self.update_timer.stop()
        self.update_timer.start(500)  # 500ms delay
    
    def update_preview(self):
        """Update preview with current sample data"""
        if hasattr(self, 'template_data') and self.template_data:
            try:
                path_service = get_service(IPathService)
                
                # Get sample data
                sample_data = {
                    "occurrence_number": self.sample_occurrence.text(),
                    "business_name": self.sample_business.text(),
                    "location_address": self.sample_location.text()
                }
                
                # Test templates with sample data
                self.preview_tree.clear()
                templates = self.template_data.get("templates", {})
                
                for template_id, template_info in templates.items():
                    template_name = template_info.get("templateName", template_id)
                    
                    # Create preview by testing with validator
                    try:
                        # This would need to be implemented in the validator
                        preview_path = "preview/path/here"  # Placeholder
                        archive_name = "preview_archive.zip"  # Placeholder
                        
                        item = QTreeWidgetItem([template_name, preview_path, archive_name])
                        item.setToolTip(0, f"Template ID: {template_id}")
                        self.preview_tree.addTopLevelItem(item)
                        
                    except Exception as e:
                        item = QTreeWidgetItem([template_name, f"Error: {e}", ""])
                        item.setForeground(1, Qt.red)
                        self.preview_tree.addTopLevelItem(item)
                
                self.preview_tree.expandAll()
                self.preview_tree.resizeColumnToContents(0)
                self.preview_tree.resizeColumnToContents(1)
                
            except Exception as e:
                logger.error(f"Preview update failed: {e}")
    
    def set_template_data(self, template_data: Dict[str, Any]):
        """Set template data for preview"""
        self.template_data = template_data
        self.update_preview()


class TemplateImportDialog(QDialog):
    """Comprehensive template import dialog with validation and preview"""
    
    template_imported = Signal(dict)  # Emitted when template is successfully imported
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.path_service = None
        self.template_data = None
        self.validation_issues = []
        
        self._setup_ui()
        self._initialize_service()
        
    def _setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle("Import Template")
        self.setModal(True)
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # File selection
        file_group = self._create_file_selection_group()
        layout.addWidget(file_group)
        
        # Main content with tabs
        self.tab_widget = QTabWidget()
        
        # Validation tab
        self.validation_tab = self._create_validation_tab()
        self.tab_widget.addTab(self.validation_tab, "Validation")
        
        # Preview tab
        self.preview_tab = TemplatePreviewWidget()
        self.tab_widget.addTab(self.preview_tab, "Preview")
        
        # Raw JSON tab
        self.json_tab = self._create_json_tab()
        self.tab_widget.addTab(self.json_tab, "JSON Content")
        
        layout.addWidget(self.tab_widget)
        
        # Options
        options_group = self._create_options_group()
        layout.addWidget(options_group)
        
        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self._import_template)
        self.button_box.rejected.connect(self.reject)
        
        # Initially disable OK button
        self.button_box.button(QDialogButtonBox.Ok).setText("Import Template")
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)
        
        layout.addWidget(self.button_box)
    
    def _create_file_selection_group(self) -> QGroupBox:
        """Create file selection group"""
        group = QGroupBox("Template File")
        layout = QHBoxLayout(group)
        
        self.file_path_label = QLabel("No file selected")
        self.file_path_label.setStyleSheet("color: #666;")
        layout.addWidget(self.file_path_label, 1)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        layout.addWidget(browse_btn)
        
        return group
    
    def _create_validation_tab(self) -> QWidget:
        """Create validation results tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Validation status
        self.validation_status = QLabel("No template loaded")
        self.validation_status.setStyleSheet("font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(self.validation_status)
        
        # Progress bar for validation
        self.validation_progress = QProgressBar()
        self.validation_progress.setVisible(False)
        layout.addWidget(self.validation_progress)
        
        # Validation issues scroll area
        self.issues_scroll = QScrollArea()
        self.issues_scroll.setWidgetResizable(True)
        self.issues_widget = QWidget()
        self.issues_layout = QVBoxLayout(self.issues_widget)
        self.issues_layout.addStretch()
        self.issues_scroll.setWidget(self.issues_widget)
        layout.addWidget(self.issues_scroll)
        
        return widget
    
    def _create_json_tab(self) -> QWidget:
        """Create JSON content tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.json_text = QTextEdit()
        self.json_text.setFont(self._get_monospace_font())
        self.json_text.setReadOnly(True)
        layout.addWidget(self.json_text)
        
        return widget
    
    def _create_options_group(self) -> QGroupBox:
        """Create import options group"""
        group = QGroupBox("Import Options")
        layout = QVBoxLayout(group)
        
        self.create_backup_check = QCheckBox("Create backup before import")
        self.create_backup_check.setChecked(True)
        self.create_backup_check.setToolTip("Automatically backup existing templates before importing")
        layout.addWidget(self.create_backup_check)
        
        self.import_warnings_check = QCheckBox("Import templates with warnings")
        self.import_warnings_check.setChecked(True)
        self.import_warnings_check.setToolTip("Allow import of templates that have validation warnings")
        layout.addWidget(self.import_warnings_check)
        
        return group
    
    def _get_monospace_font(self):
        """Get monospace font for JSON display"""
        from PySide6.QtGui import QFont
        font = QFont("Consolas, Monaco, monospace")
        font.setPointSize(10)
        return font
    
    def _initialize_service(self):
        """Initialize path service"""
        try:
            self.path_service = get_service(IPathService)
        except Exception as e:
            logger.error(f"Failed to initialize path service: {e}")
            QMessageBox.critical(
                self, 
                "Service Error",
                "Failed to initialize template service. Template import functionality may not work properly."
            )
    
    def _browse_file(self):
        """Browse for template file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Template File",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            self._load_template_file(Path(file_path))
    
    def _load_template_file(self, file_path: Path):
        """Load and validate template file"""
        try:
            self.file_path_label.setText(str(file_path))
            self.validation_progress.setVisible(True)
            self.validation_progress.setRange(0, 0)  # Indeterminate
            
            # Load JSON content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.template_data = json.loads(content)
            
            # Display JSON content
            self.json_text.setText(content)
            
            # Validate template
            if self.path_service:
                self._validate_template(file_path)
            else:
                self._show_validation_error("Template service not available")
            
            self.validation_progress.setVisible(False)
            
        except json.JSONDecodeError as e:
            self.validation_progress.setVisible(False)
            self._show_validation_error(f"Invalid JSON: {e}")
        except Exception as e:
            self.validation_progress.setVisible(False)
            self._show_validation_error(f"Failed to load file: {e}")
    
    def _validate_template(self, file_path: Path):
        """Validate template file"""
        try:
            result = self.path_service.validate_template_file(file_path)
            
            if result.success:
                self.validation_issues = result.value
                self._display_validation_results()
                
                # Update preview
                if self.template_data:
                    self.preview_tab.set_template_data(self.template_data)
                
            else:
                self._show_validation_error(f"Validation failed: {result.error}")
                
        except Exception as e:
            self._show_validation_error(f"Validation error: {e}")
    
    def _display_validation_results(self):
        """Display validation results"""
        # Clear previous issues
        for i in reversed(range(self.issues_layout.count() - 1)):  # Keep stretch at end
            child = self.issues_layout.itemAt(i).widget()
            if child:
                child.deleteLater()
        
        if not self.validation_issues:
            no_issues = QLabel("No validation issues found")
            no_issues.setStyleSheet("color: #666; font-style: italic;")
            self.issues_layout.insertWidget(0, no_issues)
            self.validation_status.setText("✅ Template validation passed")
            self.validation_status.setStyleSheet("color: #00cc00; font-weight: bold;")
            self._enable_import(True)
            return
        
        # Count issue levels
        error_count = sum(1 for issue in self.validation_issues if issue.get("level") == "error")
        warning_count = sum(1 for issue in self.validation_issues if issue.get("level") == "warning")
        
        # Update status
        if error_count > 0:
            self.validation_status.setText(f"❌ {error_count} error(s), {warning_count} warning(s)")
            self.validation_status.setStyleSheet("color: #cc0000; font-weight: bold;")
            self._enable_import(False)
        elif warning_count > 0:
            self.validation_status.setText(f"⚠️ {warning_count} warning(s)")
            self.validation_status.setStyleSheet("color: #ff6600; font-weight: bold;")
            self._enable_import(self.import_warnings_check.isChecked())
        else:
            self.validation_status.setText("✅ Template validation passed")
            self.validation_status.setStyleSheet("color: #00cc00; font-weight: bold;")
            self._enable_import(True)
        
        # Display issues
        for issue in self.validation_issues:
            issue_widget = ValidationIssueWidget(issue)
            self.issues_layout.insertWidget(self.issues_layout.count() - 1, issue_widget)
    
    def _show_validation_error(self, error_message: str):
        """Show validation error"""
        self.validation_status.setText(f"❌ Validation Error")
        self.validation_status.setStyleSheet("color: #cc0000; font-weight: bold;")
        
        # Clear previous issues
        for i in reversed(range(self.issues_layout.count() - 1)):
            child = self.issues_layout.itemAt(i).widget()
            if child:
                child.deleteLater()
        
        # Show error
        error_issue = {
            "level": "error",
            "message": error_message,
            "suggestion": "Please check the template file format and try again."
        }
        error_widget = ValidationIssueWidget(error_issue)
        self.issues_layout.insertWidget(0, error_widget)
        
        self._enable_import(False)
    
    def _enable_import(self, enabled: bool):
        """Enable or disable import button"""
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(enabled)
    
    def _import_template(self):
        """Import the template"""
        if not self.path_service or not hasattr(self, 'template_data'):
            QMessageBox.critical(self, "Import Error", "No template data available for import.")
            return
            
        try:
            file_path = Path(self.file_path_label.text())
            result = self.path_service.import_template(file_path)
            
            if result.success:
                import_info = result.value
                
                # Show success message
                imported_templates = import_info.get("imported_templates", [])
                template_count = len(imported_templates)
                
                if template_count == 1:
                    message = f"Successfully imported template: {imported_templates[0]}"
                else:
                    message = f"Successfully imported {template_count} templates"
                
                # Add validation summary
                validation_issues = import_info.get("validation_issues", [])
                warning_count = sum(1 for issue in validation_issues if issue.get("level") == "warning")
                if warning_count > 0:
                    message += f"\n\n{warning_count} validation warnings were noted but did not prevent import."
                
                QMessageBox.information(self, "Import Successful", message)
                
                # Emit signal
                self.template_imported.emit(import_info)
                
                self.accept()
                
            else:
                error_message = "Template import failed."
                if hasattr(result.error, 'user_message'):
                    error_message = result.error.user_message
                
                QMessageBox.critical(self, "Import Failed", error_message)
                
        except Exception as e:
            logger.error(f"Template import error: {e}")
            QMessageBox.critical(self, "Import Error", f"An unexpected error occurred during import:\n\n{e}")
    
    def show_import_dialog(self, parent=None) -> bool:
        """Show import dialog and return True if template was imported"""
        if parent:
            self.setParent(parent)
            
        return self.exec() == QDialog.Accepted


# Convenience function for showing import dialog
def show_template_import_dialog(parent=None) -> bool:
    """Show template import dialog"""
    dialog = TemplateImportDialog(parent)
    return dialog.show_import_dialog(parent)