#!/usr/bin/env python3
"""
Template selector widget - simple dropdown for choosing folder structure templates
"""

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QLabel, 
    QToolButton, QMenu, QSizePolicy
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
        layout.addWidget(self.template_combo, 1)
        
        # Settings button with menu
        self.settings_btn = QToolButton()
        self.settings_btn.setText("⚙")
        self.settings_btn.setToolTip("Template management options")
        self.settings_btn.setFixedSize(24, 24)
        
        # Create settings menu
        menu = QMenu(self)
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