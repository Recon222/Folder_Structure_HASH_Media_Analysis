#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Custom Template Builder Widget - Interactive folder structure builder
"""

import json
from pathlib import Path
from typing import List, Dict, Optional

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QPushButton, QLabel, QLineEdit, QComboBox,
    QListWidget, QListWidgetItem, QTextEdit, QSplitter,
    QMessageBox, QTabWidget
)

from core.models import FormData
from core.templates import FolderTemplate


class CustomTemplateWidget(QWidget):
    """Widget for building custom folder structure templates"""
    
    # Signal emitted when user wants to save template as a new tab
    create_tab_requested = Signal(str, list)  # name, template_levels
    
    # Signal emitted when template is selected for processing
    process_requested = Signal(list)  # template_levels
    
    def __init__(self, settings, form_data: FormData, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.form_data = form_data
        self.saved_templates = {}
        
        self._setup_ui()
        self._load_saved_templates()
        
        # Update preview after UI is ready
        QTimer.singleShot(100, self.update_preview)
        
    def _setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout(self)
        
        # Main splitter for side-by-side layout
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side: Template management and fields
        left_widget = self._create_left_panel()
        
        # Right side: Template editor and preview
        right_widget = self._create_right_panel()
        
        # Add to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)  # Left side smaller
        splitter.setStretchFactor(1, 3)  # Right side larger
        
        layout.addWidget(splitter)
        
    def _create_left_panel(self):
        """Create the left panel with template management and fields"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Template management
        template_control = QGroupBox("Template Management")
        control_layout = QVBoxLayout()
        
        # Template dropdown
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("Load Template:"))
        self.template_combo = QComboBox()
        select_layout.addWidget(self.template_combo)
        
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self.load_selected_template)
        select_layout.addWidget(load_btn)
        control_layout.addLayout(select_layout)
        
        # Template name for saving
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Template Name:"))
        self.template_name_input = QLineEdit()
        self.template_name_input.setPlaceholderText("My Custom Template")
        name_layout.addWidget(self.template_name_input)
        control_layout.addLayout(name_layout)
        
        # Save buttons
        save_layout = QHBoxLayout()
        save_btn = QPushButton("💾 Save Template")
        save_btn.clicked.connect(self.save_custom_template)
        save_layout.addWidget(save_btn)
        
        save_as_tab_btn = QPushButton("📌 Save as New Tab")
        save_as_tab_btn.clicked.connect(self.save_template_as_tab)
        save_layout.addWidget(save_as_tab_btn)
        control_layout.addLayout(save_layout)
        
        template_control.setLayout(control_layout)
        layout.addWidget(template_control)
        
        # Available fields
        fields_group = self._create_fields_panel()
        layout.addWidget(fields_group)
        
        layout.addStretch()
        return widget
        
    def _create_fields_panel(self):
        """Create the available fields panel"""
        fields_group = QGroupBox("Available Fields (Click to Insert)")
        fields_layout = QVBoxLayout()
        
        # Form fields
        form_fields_label = QLabel("📋 Form Fields:")
        fields_layout.addWidget(form_fields_label)
        
        form_fields_grid = QGridLayout()
        field_buttons = [
            ("{occurrence_number}", "Occurrence #"),
            ("{business_name}", "Business"),
            ("{location_address}", "Address"),
            ("{technician_name}", "Technician"),
            ("{badge_number}", "Badge #"),
        ]
        
        for i, (field, label) in enumerate(field_buttons):
            btn = QPushButton(f"{label}\n{field}")
            btn.clicked.connect(lambda checked, f=field: self.insert_field(f))
            form_fields_grid.addWidget(btn, i // 2, i % 2)
        fields_layout.addLayout(form_fields_grid)
        
        # Date/Time fields
        datetime_label = QLabel("\n📅 Date/Time Fields:")
        fields_layout.addWidget(datetime_label)
        
        datetime_grid = QGridLayout()
        datetime_buttons = [
            ("{date}", "Current Date"),
            ("{time}", "Current Time"),
            ("{year}", "Year"),
            ("{month}", "Month"),
            ("{day}", "Day"),
            ("{extraction_start}", "Start Time"),
            ("{extraction_end}", "End Time"),
        ]
        
        for i, (field, label) in enumerate(datetime_buttons):
            btn = QPushButton(f"{label}\n{field}")
            btn.clicked.connect(lambda checked, f=field: self.insert_field(f))
            datetime_grid.addWidget(btn, i // 2, i % 2)
        fields_layout.addLayout(datetime_grid)
        
        fields_group.setLayout(fields_layout)
        return fields_group
        
    def _create_right_panel(self):
        """Create the right panel with template editor and preview"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Template builder
        builder_group = QGroupBox("Folder Structure Builder")
        builder_layout = QVBoxLayout()
        
        # Instructions
        instructions = QLabel("Build your folder structure (one level per line):\n"
                            "• Use spaces at the start to indent sub-folders\n"
                            "• Click field buttons or type {field_name} manually")
        builder_layout.addWidget(instructions)
        
        # Template editor
        self.template_editor = QListWidget()
        self.template_editor.setDragDropMode(QListWidget.InternalMove)
        
        # Add default structure
        default_items = [
            "{occurrence_number}",
            "  {business_name} @ {location_address}",
            "    {extraction_start} - {extraction_end}"
        ]
        
        for item_text in default_items:
            item = QListWidgetItem(item_text)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.template_editor.addItem(item)
            
        self.template_editor.itemChanged.connect(self.update_preview)
        builder_layout.addWidget(self.template_editor)
        
        # Level controls
        level_controls = self._create_level_controls()
        builder_layout.addLayout(level_controls)
        
        builder_group.setLayout(builder_layout)
        layout.addWidget(builder_group)
        
        # Preview
        preview_group = QGroupBox("Live Preview")
        preview_layout = QVBoxLayout()
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(150)
        preview_layout.addWidget(self.preview_text)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # Process button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.process_btn = QPushButton("Process with This Structure")
        self.process_btn.clicked.connect(self.process_with_template)
        btn_layout.addWidget(self.process_btn)
        layout.addLayout(btn_layout)
        
        return widget
        
    def _create_level_controls(self):
        """Create the controls for managing template levels"""
        layout = QHBoxLayout()
        
        add_btn = QPushButton("➕ Add Level")
        add_btn.clicked.connect(self.add_template_level)
        layout.addWidget(add_btn)
        
        remove_btn = QPushButton("➖ Remove Level")
        remove_btn.clicked.connect(self.remove_template_level)
        layout.addWidget(remove_btn)
        
        indent_btn = QPushButton("➡️ Indent")
        indent_btn.clicked.connect(lambda: self.adjust_indent(2))
        layout.addWidget(indent_btn)
        
        outdent_btn = QPushButton("⬅️ Outdent")
        outdent_btn.clicked.connect(lambda: self.adjust_indent(-2))
        layout.addWidget(outdent_btn)
        
        layout.addStretch()
        return layout
        
    def insert_field(self, field_text: str):
        """Insert a field into the current template editor item"""
        current_item = self.template_editor.currentItem()
        if current_item:
            current_text = current_item.text()
            current_item.setText(current_text + field_text)
        else:
            # Add new item with the field
            item = QListWidgetItem(field_text)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.template_editor.addItem(item)
        
        self.update_preview()
        
    def add_template_level(self):
        """Add a new level to the template"""
        item = QListWidgetItem("  New Folder Level")
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.template_editor.addItem(item)
        self.template_editor.setCurrentItem(item)
        self.template_editor.editItem(item)
        
    def remove_template_level(self):
        """Remove the selected level from the template"""
        current_row = self.template_editor.currentRow()
        if current_row >= 0:
            self.template_editor.takeItem(current_row)
            self.update_preview()
            
    def adjust_indent(self, spaces: int):
        """Adjust indentation of the selected level"""
        current_item = self.template_editor.currentItem()
        if current_item:
            text = current_item.text()
            current_indent = len(text) - len(text.lstrip())
            new_indent = max(0, current_indent + spaces)
            current_item.setText(" " * new_indent + text.lstrip())
            self.update_preview()
            
    def update_preview(self):
        """Update the preview based on current template"""
        try:
            # Get template levels
            levels = self.get_template_levels()
            
            # Create a temporary template
            template = FolderTemplate("Preview", "Preview", levels)
            
            # Build path with current form data
            path = template.build_path(self.form_data)
            
            # Create visual representation
            preview_lines = []
            parts = path.parts
            for i, part in enumerate(parts):
                indent = "  " * i
                preview_lines.append(f"{indent}📁 {part}")
            
            if preview_lines:
                preview_lines.append(f"{'  ' * len(parts)}📄 (your files will go here)")
                
            self.preview_text.setPlainText("\n".join(preview_lines))
            
        except Exception as e:
            self.preview_text.setPlainText(f"Preview error: {str(e)}")
            
    def get_template_levels(self) -> List[str]:
        """Get the current template levels from the editor"""
        levels = []
        for i in range(self.template_editor.count()):
            item = self.template_editor.item(i)
            text = item.text()
            # Remove leading spaces to get the actual template
            levels.append(text.strip())
        return levels
        
    def save_custom_template(self):
        """Save the current template"""
        name = self.template_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Save Template", 
                              "Please enter a template name")
            return
            
        # Get template levels
        levels = self.get_template_levels()
        
        # Save to settings
        templates = self.settings.value('custom_templates', {})
        if not isinstance(templates, dict):
            templates = {}
            
        templates[name] = {
            'name': name,
            'levels': levels
        }
        
        self.settings.setValue('custom_templates', templates)
        
        # Update combo box
        self._load_saved_templates()
        
        QMessageBox.information(self, "Template Saved", 
                              f"Template '{name}' saved successfully!")
        
    def save_template_as_tab(self):
        """Save the template and request creation of a new tab"""
        name = self.template_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Save as Tab", 
                              "Please enter a template name")
            return
            
        # First save the template
        self.save_custom_template()
        
        # Get template levels
        levels = self.get_template_levels()
        
        # Emit signal to create tab
        self.create_tab_requested.emit(name, levels)
        
    def load_selected_template(self):
        """Load the selected template into the editor"""
        template_name = self.template_combo.currentText()
        if template_name and template_name in self.saved_templates:
            template_data = self.saved_templates[template_name]
            
            # Clear current editor
            self.template_editor.clear()
            
            # Load template levels
            for level in template_data.get('levels', []):
                item = QListWidgetItem(level)
                item.setFlags(item.flags() | Qt.ItemIsEditable)
                self.template_editor.addItem(item)
                
            # Update template name
            self.template_name_input.setText(template_name)
            
            # Update preview
            self.update_preview()
            
    def _load_saved_templates(self):
        """Load saved templates from settings"""
        # Get custom templates
        templates = self.settings.value('custom_templates', {})
        if isinstance(templates, dict):
            self.saved_templates = templates
        else:
            self.saved_templates = {}
            
        # Update combo box
        self.template_combo.clear()
        
        # Add preset templates
        presets = [
            "Law Enforcement (Default)",
            "Medical Records",
            "Legal Documents", 
            "Media Production"
        ]
        self.template_combo.addItems(presets)
        
        # Add custom templates
        if self.saved_templates:
            self.template_combo.addItem("--- Custom Templates ---")
            self.template_combo.addItems(list(self.saved_templates.keys()))
            
    def load_saved_templates(self):
        """Public method to load templates - called from __init__"""
        self._load_saved_templates()
            
    def process_with_template(self):
        """Process files with the current template"""
        levels = self.get_template_levels()
        if not levels:
            QMessageBox.warning(self, "No Template", 
                              "Please create a folder structure first")
            return
            
        self.process_requested.emit(levels)