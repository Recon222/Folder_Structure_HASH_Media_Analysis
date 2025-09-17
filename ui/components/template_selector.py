#!/usr/bin/env python3
"""
Template selector widget - simple dropdown for choosing folder structure templates
"""

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QLabel, 
    QToolButton, QMenu, QSizePolicy, QMessageBox, QFileDialog
)

from core.services import get_service, IPathService
from core.exceptions import FSAError
from core.logger import logger

class TemplateSelector(QWidget):
    """Simple template selection dropdown with management options"""
    
    template_changed = Signal(str)  # template_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.path_service = None
        self._setup_ui()
        self._initialize_service()
    
    def _setup_ui(self):
        """Create the selector UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        
        # Label
        label = QLabel("Template:")
        label.setToolTip("Folder structure template for organizing files")
        layout.addWidget(label)
        
        # Template dropdown
        self.template_combo = QComboBox()
        self.template_combo.setMinimumWidth(250)
        self.template_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.template_combo.setToolTip("Select folder structure template for current agency")
        # Force non-native rendering to prevent white border issue
        self.template_combo.setFrame(False)  # Disable native frame
        layout.addWidget(self.template_combo, 1)
        
        # Settings button with menu
        self.settings_btn = QToolButton()
        self.settings_btn.setText("⚙")
        self.settings_btn.setToolTip("Template management options")
        self.settings_btn.setFixedSize(24, 24)
        
        # Create settings menu
        menu = QMenu(self)
        menu.addAction("Import Template...", self._import_template)
        menu.addAction("Export Current Template...", self._export_current_template)
        menu.addSeparator()
        menu.addAction("Manage Templates...", self._manage_templates)
        menu.addSeparator()
        menu.addAction("Refresh Templates", self._refresh_templates)
        menu.addSeparator()
        menu.addAction("About Templates", self._show_template_info)
        
        self.settings_btn.setMenu(menu)
        self.settings_btn.setPopupMode(QToolButton.InstantPopup)
        layout.addWidget(self.settings_btn)
        
        # Connect signals
        self.template_combo.currentIndexChanged.connect(self._on_template_selected)
    
    def _initialize_service(self):
        """Initialize path service and load templates"""
        try:
            self.path_service = get_service(IPathService)
            self._load_templates()
        except Exception as e:
            logger.error(f"Failed to initialize template selector: {e}")
            self.setEnabled(False)  # Disable if service unavailable
    
    def _load_templates(self):
        """Load available templates into dropdown"""
        if not self.path_service:
            return
            
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        
        try:
            templates = self.path_service.get_available_templates()
            current_template_id = self.path_service.get_current_template_id()
            current_index = 0
            
            for i, template in enumerate(templates):
                self.template_combo.addItem(template["name"], template["id"])
                if template["id"] == current_template_id:
                    current_index = i
            
            self.template_combo.setCurrentIndex(current_index)
            logger.info(f"Loaded {len(templates)} templates, current: {current_template_id}")
            
        except Exception as e:
            logger.error(f"Failed to load templates: {e}")
            # Add fallback option
            self.template_combo.addItem("Default Forensic", "default_forensic")
            
        finally:
            self.template_combo.blockSignals(False)
    
    def _on_template_selected(self, index):
        """Handle template selection"""
        if index < 0 or not self.path_service:
            return
            
        template_id = self.template_combo.itemData(index)
        if not template_id:
            return
            
        try:
            result = self.path_service.set_current_template(template_id)
            if result.success:
                logger.info(f"Template changed to: {template_id}")
                self.template_changed.emit(template_id)
            else:
                logger.error(f"Failed to set template {template_id}: {result.error}")
                # Revert selection
                self._load_templates()
                
        except Exception as e:
            logger.error(f"Error setting template {template_id}: {e}")
    
    def _refresh_templates(self):
        """Refresh template list from storage"""
        if not self.path_service:
            return
            
        try:
            result = self.path_service.reload_templates()
            if result.success:
                self._load_templates()
                logger.info("Templates refreshed successfully")
            else:
                logger.error(f"Failed to refresh templates: {result.error}")
        except Exception as e:
            logger.error(f"Error refreshing templates: {e}")
    
    def _show_template_info(self):
        """Show information about templates"""
        from PySide6.QtWidgets import QMessageBox
        
        info_text = """
<h3>Folder Structure Templates</h3>
<p>Templates define how your folder structures are organized:</p>
<ul>
<li><b>Default Forensic:</b> Standard law enforcement structure</li>
<li><b>RCMP Basic:</b> Royal Canadian Mounted Police format</li>
<li><b>Generic Agency:</b> Simple three-level structure</li>
</ul>
<p>Templates are loaded from <code>templates/folder_templates.json</code></p>
<p>Each agency can have their own customized folder organization while using the same application.</p>
        """
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Template Information")
        msg.setTextFormat(Qt.RichText)
        msg.setText(info_text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()
    
    def get_current_template_id(self) -> str:
        """Get currently selected template ID"""
        if self.path_service:
            return self.path_service.get_current_template_id()
        return "default_forensic"
    
    def set_enabled_state(self, enabled: bool):
        """Enable or disable the template selector"""
        self.setEnabled(enabled)
        if enabled and not self.path_service:
            self._initialize_service()
    
    def _import_template(self):
        """Import template from JSON file"""
        if not self.path_service:
            QMessageBox.warning(self, "Service Unavailable", "Template service is not available.")
            return
            
        try:
            # Use the import dialog
            from ui.dialogs.template_import_dialog import TemplateImportDialog
            
            dialog = TemplateImportDialog(self)
            dialog.template_imported.connect(self._on_template_imported)
            dialog.show_import_dialog(self)
            
        except ImportError:
            # Fallback to simple file dialog if import dialog not available
            self._import_template_fallback()
        except Exception as e:
            logger.error(f"Template import error: {e}")
            QMessageBox.critical(self, "Import Error", f"Failed to open template import dialog:\n\n{e}")
    
    def _import_template_fallback(self):
        """Fallback import method using simple file dialog"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Import Template",
                "",
                "JSON Files (*.json);;All Files (*)"
            )
            
            if not file_path:
                return
                
            from pathlib import Path
            result = self.path_service.import_template(Path(file_path))
            
            if result.success:
                imported_info = result.value
                imported_templates = imported_info.get("imported_templates", [])
                
                if len(imported_templates) == 1:
                    message = f"Successfully imported template: {imported_templates[0]}"
                else:
                    message = f"Successfully imported {len(imported_templates)} templates"
                    
                QMessageBox.information(self, "Import Successful", message)
                
                # Refresh templates
                self._load_templates()
                
            else:
                error_message = "Template import failed."
                if hasattr(result.error, 'user_message'):
                    error_message = result.error.user_message
                    
                QMessageBox.critical(self, "Import Failed", error_message)
                
        except Exception as e:
            logger.error(f"Template import fallback error: {e}")
            QMessageBox.critical(self, "Import Error", f"Template import failed:\n\n{e}")
    
    def _export_current_template(self):
        """Export currently selected template"""
        if not self.path_service:
            QMessageBox.warning(self, "Service Unavailable", "Template service is not available.")
            return
            
        current_template_id = self.get_current_template_id()
        if not current_template_id:
            QMessageBox.information(self, "No Template", "No template is currently selected.")
            return
            
        try:
            # Get template info for better filename
            template_info_result = self.path_service.get_template_info(current_template_id)
            if template_info_result.success:
                template_info = template_info_result.value
                template_name = template_info.get("name", current_template_id)
                suggested_filename = f"{template_name.replace(' ', '_')}.json"
            else:
                suggested_filename = f"{current_template_id}.json"
            
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Template",
                suggested_filename,
                "JSON Files (*.json);;All Files (*)"
            )
            
            if not file_path:
                return
                
            from pathlib import Path
            result = self.path_service.export_template(current_template_id, Path(file_path))
            
            if result.success:
                QMessageBox.information(
                    self, 
                    "Export Successful", 
                    f"Template '{current_template_id}' exported successfully to:\n{file_path}"
                )
            else:
                error_message = "Template export failed."
                if hasattr(result.error, 'user_message'):
                    error_message = result.error.user_message
                    
                QMessageBox.critical(self, "Export Failed", error_message)
                
        except Exception as e:
            logger.error(f"Template export error: {e}")
            QMessageBox.critical(self, "Export Error", f"Template export failed:\n\n{e}")
    
    def _manage_templates(self):
        """Open template management dialog"""
        try:
            from ui.dialogs.template_management_dialog import TemplateManagementDialog
            
            dialog = TemplateManagementDialog(self)
            dialog.templates_changed.connect(self._on_templates_changed)
            dialog.exec()
            
        except ImportError:
            # Template management dialog not yet implemented
            QMessageBox.information(
                self, 
                "Coming Soon", 
                "Advanced template management features are coming in a future update.\n\n"
                "Current available options:\n"
                "• Import Template (📥)\n"
                "• Export Template (📤)\n"
                "• Refresh Templates (🔄)"
            )
        except Exception as e:
            logger.error(f"Template management error: {e}")
            QMessageBox.critical(self, "Management Error", f"Failed to open template management:\n\n{e}")
    
    def _on_template_imported(self, import_info: dict):
        """Handle template imported signal"""
        try:
            # Refresh templates to include newly imported ones
            self._load_templates()
            
            # Try to select one of the imported templates
            imported_templates = import_info.get("imported_templates", [])
            if imported_templates and self.path_service:
                first_imported = imported_templates[0]
                
                # Find the template in the dropdown
                for i in range(self.template_combo.count()):
                    template_id = self.template_combo.itemData(i)
                    if template_id == first_imported:
                        self.template_combo.setCurrentIndex(i)
                        break
                        
            logger.info(f"Template import completed: {imported_templates}")
            
        except Exception as e:
            logger.error(f"Error handling template import: {e}")
    
    def _on_templates_changed(self):
        """Handle templates changed signal from management dialog"""
        try:
            self._load_templates()
            logger.info("Templates refreshed after management changes")
        except Exception as e:
            logger.error(f"Error refreshing templates: {e}")