#!/usr/bin/env python3
"""
Template management dialog for advanced template operations
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QTreeWidget, QTreeWidgetItem, QGroupBox, QTabWidget, QWidget,
    QTextEdit, QDialogButtonBox, QSplitter, QFrame, QScrollArea,
    QMessageBox, QLineEdit, QFormLayout, QComboBox, QCheckBox,
    QHeaderView, QMenu, QFileDialog
)
from PySide6.QtGui import QAction, QFont

from core.services import get_service, IPathService
from core.services.template_management_service import TemplateSource
from core.exceptions import FSAError
from core.logger import logger


class TemplateInfoWidget(QFrame):
    """Widget to display detailed template information"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.template_info = None
        
    def _setup_ui(self):
        """Setup the template info UI"""
        layout = QVBoxLayout(self)
        
        # Title
        self.title_label = QLabel("Template Information")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 8px;")
        layout.addWidget(self.title_label)
        
        # Template details form
        form_layout = QFormLayout()
        
        # Basic info
        self.name_label = QLabel("-")
        self.id_label = QLabel("-")
        self.description_label = QLabel("-")
        self.source_label = QLabel("-")
        
        form_layout.addRow("Name:", self.name_label)
        form_layout.addRow("ID:", self.id_label)
        form_layout.addRow("Description:", self.description_label)
        form_layout.addRow("Source:", self.source_label)
        
        # Metadata info
        self.author_label = QLabel("-")
        self.agency_label = QLabel("-")
        self.version_label = QLabel("-")
        
        form_layout.addRow("Author:", self.author_label)
        form_layout.addRow("Agency:", self.agency_label)
        form_layout.addRow("Version:", self.version_label)
        
        layout.addLayout(form_layout)
        
        # Structure preview
        structure_group = QGroupBox("Folder Structure")
        structure_layout = QVBoxLayout(structure_group)
        
        self.structure_text = QTextEdit()
        self.structure_text.setMaximumHeight(150)
        self.structure_text.setFont(self._get_monospace_font())
        self.structure_text.setReadOnly(True)
        structure_layout.addWidget(self.structure_text)
        
        layout.addWidget(structure_group)
        
        layout.addStretch()
    
    def _get_monospace_font(self):
        """Get monospace font"""
        font = QFont("Consolas, Monaco, monospace")
        font.setPointSize(9)
        return font
    
    def set_template_info(self, template_info: Optional[Dict[str, Any]]):
        """Set template information to display"""
        self.template_info = template_info
        
        if not template_info:
            self._clear_info()
            return
        
        # Basic info
        self.name_label.setText(template_info.get("name", "-"))
        self.id_label.setText(template_info.get("template_id", "-"))
        self.description_label.setText(template_info.get("description", "-") or "No description")
        
        # Source with styling
        source = template_info.get("source", "-")
        source_color = self._get_source_color(source)
        self.source_label.setText(f'<span style="color: {source_color};">{source.title()}</span>')
        
        # Metadata
        metadata = template_info.get("metadata", {})
        self.author_label.setText(metadata.get("author", "-"))
        self.agency_label.setText(metadata.get("agency", "-"))
        self.version_label.setText(metadata.get("version", "-"))
        
        # Structure preview
        self._update_structure_preview(template_info.get("template_data", {}))
    
    def _clear_info(self):
        """Clear all information"""
        for label in [self.name_label, self.id_label, self.description_label, 
                     self.source_label, self.author_label, self.agency_label, self.version_label]:
            label.setText("-")
        self.structure_text.clear()
    
    def _get_source_color(self, source: str) -> str:
        """Get color for template source"""
        colors = {
            TemplateSource.SYSTEM: "#0066cc",
            TemplateSource.USER: "#00cc66",
            TemplateSource.IMPORTED: "#ff6600",
            TemplateSource.CUSTOM: "#cc00cc"
        }
        return colors.get(source, "#666666")
    
    def _update_structure_preview(self, template_data: Dict[str, Any]):
        """Update structure preview"""
        try:
            structure = template_data.get("structure", {})
            levels = structure.get("levels", [])
            
            preview_lines = []
            for i, level in enumerate(levels):
                indent = "  " * i
                pattern = level.get("pattern", "")
                preview_lines.append(f"{indent}📁 {pattern}")
                
                # Show conditionals if present
                conditionals = level.get("conditionals", {})
                if conditionals:
                    for cond_name, cond_pattern in conditionals.items():
                        preview_lines.append(f"{indent}   ↳ {cond_name}: {cond_pattern}")
            
            # Add archive naming
            archive_config = template_data.get("archiveNaming", {})
            if archive_config:
                preview_lines.append("")
                preview_lines.append("📦 Archive Naming:")
                pattern = archive_config.get("pattern", "")
                if pattern:
                    preview_lines.append(f"  {pattern}")
            
            self.structure_text.setText("\n".join(preview_lines))
            
        except Exception as e:
            self.structure_text.setText(f"Error displaying structure: {e}")


class TemplateManagementDialog(QDialog):
    """Advanced template management dialog"""
    
    templates_changed = Signal()  # Emitted when templates are modified
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.path_service = None
        self.templates = []
        
        self._setup_ui()
        self._initialize_service()
        self._load_templates()
        
    def _setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle("Template Management")
        self.setModal(True)
        self.resize(1000, 700)
        
        layout = QVBoxLayout(self)
        
        # Main content with splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - template list
        left_panel = self._create_template_list_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - template details
        right_panel = self._create_template_details_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([400, 600])
        layout.addWidget(splitter)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Action buttons
        self.import_btn = QPushButton("📥 Import Template...")
        self.import_btn.clicked.connect(self._import_template)
        button_layout.addWidget(self.import_btn)
        
        self.export_btn = QPushButton("📤 Export Template...")
        self.export_btn.clicked.connect(self._export_template)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)
        
        self.delete_btn = QPushButton("🗑️ Delete Template")
        self.delete_btn.clicked.connect(self._delete_template)
        self.delete_btn.setEnabled(False)
        button_layout.addWidget(self.delete_btn)
        
        button_layout.addStretch()
        
        # Dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Close)
        self.button_box.rejected.connect(self.accept)
        button_layout.addWidget(self.button_box)
        
        layout.addLayout(button_layout)
    
    def _create_template_list_panel(self) -> QWidget:
        """Create template list panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Filter controls
        filter_group = QGroupBox("Filter Templates")
        filter_layout = QVBoxLayout(filter_group)
        
        # Source filter
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("Source:"))
        
        self.source_filter = QComboBox()
        self.source_filter.addItem("All Sources", "")
        self.source_filter.addItem("🔧 System", TemplateSource.SYSTEM)
        self.source_filter.addItem("📥 Imported", TemplateSource.IMPORTED)
        self.source_filter.addItem("✏️ Custom", TemplateSource.CUSTOM)
        self.source_filter.currentTextChanged.connect(self._filter_templates)
        source_layout.addWidget(self.source_filter)
        source_layout.addStretch()
        
        filter_layout.addLayout(source_layout)
        
        # Search box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search templates...")
        self.search_box.textChanged.connect(self._filter_templates)
        search_layout.addWidget(self.search_box)
        
        filter_layout.addLayout(search_layout)
        layout.addWidget(filter_group)
        
        # Template tree
        self.template_tree = QTreeWidget()
        self.template_tree.setHeaderLabels(["Template", "Source", "Description"])
        self.template_tree.setAlternatingRowColors(True)
        self.template_tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.template_tree.itemSelectionChanged.connect(self._on_template_selected)
        
        # Setup context menu
        self.template_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.template_tree.customContextMenuRequested.connect(self._show_context_menu)
        
        # Configure columns
        header = self.template_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) 
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        
        layout.addWidget(self.template_tree)
        
        # Template count
        self.count_label = QLabel("0 templates")
        self.count_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.count_label)
        
        return panel
    
    def _create_template_details_panel(self) -> QWidget:
        """Create template details panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Template info widget
        self.template_info_widget = TemplateInfoWidget()
        layout.addWidget(self.template_info_widget)
        
        return panel
    
    def _initialize_service(self):
        """Initialize path service"""
        try:
            self.path_service = get_service(IPathService)
        except Exception as e:
            logger.error(f"Failed to initialize path service: {e}")
            QMessageBox.critical(
                self,
                "Service Error",
                "Failed to initialize template service. Template management functionality may not work properly."
            )
    
    def _load_templates(self):
        """Load all templates"""
        if not self.path_service:
            return
            
        try:
            # Get template sources (which includes all templates grouped by source)
            template_sources = self.path_service.get_template_sources()
            
            # Flatten to single list
            self.templates = []
            for source_info in template_sources:
                source = source_info.get("source", "")
                templates = source_info.get("templates", [])
                
                for template in templates:
                    template["source"] = source
                    self.templates.append(template)
            
            self._populate_template_tree()
            
        except Exception as e:
            logger.error(f"Failed to load templates: {e}")
            QMessageBox.warning(self, "Load Error", f"Failed to load templates: {e}")
    
    def _populate_template_tree(self):
        """Populate template tree with filtered templates"""
        self.template_tree.clear()
        
        # Get filter values
        source_filter = self.source_filter.currentData()
        search_text = self.search_box.text().lower()
        
        # Filter templates
        filtered_templates = []
        for template in self.templates:
            # Source filter
            if source_filter and template.get("source", "") != source_filter:
                continue
                
            # Search filter
            if search_text:
                searchable_text = " ".join([
                    template.get("name", "").lower(),
                    template.get("id", "").lower(),
                    template.get("description", "").lower()
                ])
                if search_text not in searchable_text:
                    continue
            
            filtered_templates.append(template)
        
        # Group by source for tree display
        sources = {}
        for template in filtered_templates:
            source = template.get("source", "unknown")
            if source not in sources:
                sources[source] = []
            sources[source].append(template)
        
        # Create tree items
        for source, source_templates in sources.items():
            # Create source group item
            source_item = QTreeWidgetItem([self._get_source_display_name(source), "", ""])
            source_item.setExpanded(True)
            source_item.setFont(0, self._get_bold_font())
            source_item.setForeground(0, self._get_source_brush(source))
            self.template_tree.addTopLevelItem(source_item)
            
            # Add templates under source
            for template in source_templates:
                template_item = QTreeWidgetItem([
                    template.get("name", template.get("id", "")),
                    "",  # Source column empty for individual templates
                    template.get("description", "")[:60] + ("..." if len(template.get("description", "")) > 60 else "")
                ])
                
                # Store template data
                template_item.setData(0, Qt.UserRole, template)
                
                # Styling based on source
                if source == TemplateSource.SYSTEM:
                    template_item.setToolTip(0, "System template (read-only)")
                elif source == TemplateSource.IMPORTED:
                    template_item.setToolTip(0, "Imported template (can be deleted)")
                elif source == TemplateSource.CUSTOM:
                    template_item.setToolTip(0, "Custom template (can be modified)")
                
                source_item.addChild(template_item)
        
        # Update count
        self.count_label.setText(f"{len(filtered_templates)} template(s)")
        
        # Expand all
        self.template_tree.expandAll()
    
    def _get_source_display_name(self, source: str) -> str:
        """Get display name for template source"""
        names = {
            TemplateSource.SYSTEM: "🔧 System Templates",
            TemplateSource.IMPORTED: "📥 Imported Templates", 
            TemplateSource.CUSTOM: "✏️ Custom Templates",
            TemplateSource.USER: "👤 User Templates"
        }
        return names.get(source, f"📁 {source.title()} Templates")
    
    def _get_source_brush(self, source: str):
        """Get color brush for template source"""
        from PySide6.QtGui import QColor
        colors = {
            TemplateSource.SYSTEM: QColor("#0066cc"),
            TemplateSource.IMPORTED: QColor("#ff6600"),
            TemplateSource.CUSTOM: QColor("#cc00cc"),
            TemplateSource.USER: QColor("#00cc66")
        }
        return colors.get(source, QColor("#666666"))
    
    def _get_bold_font(self):
        """Get bold font for group headers"""
        font = QFont()
        font.setBold(True)
        return font
    
    def _filter_templates(self):
        """Filter templates based on current filter criteria"""
        self._populate_template_tree()
    
    def _on_template_selected(self):
        """Handle template selection"""
        selected_items = self.template_tree.selectedItems()
        
        if not selected_items:
            self._clear_selection()
            return
            
        item = selected_items[0]
        template_data = item.data(0, Qt.UserRole)
        
        if not template_data:
            # This is a group item
            self._clear_selection()
            return
        
        # Get full template info
        template_id = template_data.get("id", "")
        if template_id and self.path_service:
            try:
                result = self.path_service.get_template_info(template_id)
                if result.success:
                    full_info = result.value
                    self.template_info_widget.set_template_info(full_info)
                    self._update_buttons(full_info)
                    return
            except Exception as e:
                logger.error(f"Error getting template info: {e}")
        
        # Fallback to basic info
        self.template_info_widget.set_template_info(template_data)
        self._update_buttons(template_data)
    
    def _clear_selection(self):
        """Clear template selection"""
        self.template_info_widget.set_template_info(None)
        self.export_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
    
    def _update_buttons(self, template_info: Dict[str, Any]):
        """Update button states based on selected template"""
        source = template_info.get("source", "")
        template_id = template_info.get("template_id", "")
        
        # Export button - always enabled if template is selected
        self.export_btn.setEnabled(bool(template_id))
        
        # Delete button - only enabled for user templates
        can_delete = source in [TemplateSource.IMPORTED, TemplateSource.CUSTOM]
        self.delete_btn.setEnabled(can_delete)
    
    def _show_context_menu(self, position):
        """Show context menu for template tree"""
        item = self.template_tree.itemAt(position)
        if not item:
            return
            
        template_data = item.data(0, Qt.UserRole)
        if not template_data:
            return  # Group item
        
        menu = QMenu(self)
        
        # Export action
        export_action = menu.addAction("📤 Export Template...")
        export_action.triggered.connect(self._export_template)
        
        # Delete action (only for user templates)
        source = template_data.get("source", "")
        if source in [TemplateSource.IMPORTED, TemplateSource.CUSTOM]:
            delete_action = menu.addAction("🗑️ Delete Template")
            delete_action.triggered.connect(self._delete_template)
        
        menu.exec(self.template_tree.mapToGlobal(position))
    
    def _import_template(self):
        """Import new template"""
        try:
            from ui.dialogs.template_import_dialog import TemplateImportDialog
            
            dialog = TemplateImportDialog(self)
            dialog.template_imported.connect(self._on_template_imported)
            dialog.show_import_dialog(self)
            
        except ImportError:
            # Fallback to simple file dialog
            self._import_template_fallback()
        except Exception as e:
            logger.error(f"Template import error: {e}")
            QMessageBox.critical(self, "Import Error", f"Failed to open import dialog:\n\n{e}")
    
    def _import_template_fallback(self):
        """Fallback import using simple file dialog"""
        if not self.path_service:
            return
            
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Import Template",
                "",
                "JSON Files (*.json);;All Files (*)"
            )
            
            if file_path:
                result = self.path_service.import_template(Path(file_path))
                if result.success:
                    QMessageBox.information(self, "Import Successful", "Template imported successfully.")
                    self._on_template_imported(result.value)
                else:
                    QMessageBox.critical(self, "Import Failed", f"Failed to import template:\n{result.error}")
                    
        except Exception as e:
            logger.error(f"Template import fallback error: {e}")
            QMessageBox.critical(self, "Import Error", f"Template import failed:\n\n{e}")
    
    def _export_template(self):
        """Export selected template"""
        if not self.path_service:
            return
            
        selected_items = self.template_tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select a template to export.")
            return
            
        template_data = selected_items[0].data(0, Qt.UserRole)
        if not template_data:
            return
            
        template_id = template_data.get("id", "")
        template_name = template_data.get("name", template_id)
        
        try:
            suggested_filename = f"{template_name.replace(' ', '_')}.json"
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Template", 
                suggested_filename,
                "JSON Files (*.json);;All Files (*)"
            )
            
            if file_path:
                result = self.path_service.export_template(template_id, Path(file_path))
                if result.success:
                    QMessageBox.information(
                        self,
                        "Export Successful",
                        f"Template exported successfully to:\n{file_path}"
                    )
                else:
                    QMessageBox.critical(self, "Export Failed", f"Failed to export template:\n{result.error}")
                    
        except Exception as e:
            logger.error(f"Template export error: {e}")
            QMessageBox.critical(self, "Export Error", f"Template export failed:\n\n{e}")
    
    def _delete_template(self):
        """Delete selected template"""
        if not self.path_service:
            return
            
        selected_items = self.template_tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select a template to delete.")
            return
            
        template_data = selected_items[0].data(0, Qt.UserRole)
        if not template_data:
            return
            
        template_id = template_data.get("id", "")
        template_name = template_data.get("name", template_id)
        source = template_data.get("source", "")
        
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete the template '{template_name}'?\n\n"
            f"This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            result = self.path_service.delete_user_template(template_id)
            if result.success:
                QMessageBox.information(self, "Deletion Successful", f"Template '{template_name}' deleted successfully.")
                self._load_templates()
                self.templates_changed.emit()
            else:
                QMessageBox.critical(self, "Deletion Failed", f"Failed to delete template:\n{result.error}")
                
        except Exception as e:
            logger.error(f"Template deletion error: {e}")
            QMessageBox.critical(self, "Deletion Error", f"Template deletion failed:\n\n{e}")
    
    def _on_template_imported(self, import_info: dict):
        """Handle template import completion"""
        self._load_templates()
        self.templates_changed.emit()
        logger.info(f"Template management: templates imported {import_info.get('imported_templates', [])}")


# Convenience function
def show_template_management_dialog(parent=None) -> None:
    """Show template management dialog"""
    dialog = TemplateManagementDialog(parent)
    dialog.exec()