#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Files panel component for file and folder selection with proper state management
"""

from pathlib import Path
from typing import List, Tuple, Dict, Optional

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, 
    QFileDialog, QLabel
)
from core.logger import logger


class FilesPanel(QGroupBox):
    """Panel for selecting files and folders to process with robust state management"""
    
    # Signal emitted when files are added/removed
    files_changed = Signal()
    
    # Signal for logging
    log_message = Signal(str)
    
    def __init__(self, parent=None, show_remove_selected=True, compact_buttons=False):
        """Initialize FilesPanel
        
        Args:
            parent: Parent widget
            show_remove_selected: Whether to show the "Remove Selected" button
            compact_buttons: Whether to use compact button styling
        """
        super().__init__("Files to Process", parent)
        
        # Configuration options
        self.show_remove_selected = show_remove_selected
        self.compact_buttons = compact_buttons
        
        # Primary data structures
        self.selected_files: List[Path] = []
        self.selected_folders: List[Path] = []
        
        # NEW: Unified entry tracking system
        self.entries: List[Dict] = []  # List of {'type': 'file'|'folder', 'path': Path, 'id': int}
        self._entry_counter = 0  # Unique ID generator
        self._entry_map: Dict[int, Dict] = {}  # ID -> entry mapping for fast lookup
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Create the files panel UI"""
        layout = QVBoxLayout()
        
        # File list
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.file_list)
        
        # Count label
        self.count_label = QLabel("No items selected")
        layout.addWidget(self.count_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        # Button styling based on compact_buttons option
        button_style = "QPushButton { padding: 4px 8px; }" if self.compact_buttons else ""
        
        self.add_files_btn = QPushButton("Add Files")
        if button_style:
            self.add_files_btn.setStyleSheet(button_style)
        self.add_files_btn.clicked.connect(self.add_files)
        btn_layout.addWidget(self.add_files_btn)
        
        self.add_folder_btn = QPushButton("Add Folder")
        if button_style:
            self.add_folder_btn.setStyleSheet(button_style)
        self.add_folder_btn.clicked.connect(self.add_folder)
        btn_layout.addWidget(self.add_folder_btn)
        
        # Conditionally add Remove Selected button
        if self.show_remove_selected:
            self.remove_btn = QPushButton("Remove Selected")
            if button_style:
                self.remove_btn.setStyleSheet(button_style)
            self.remove_btn.clicked.connect(self.remove_selected)
            self.remove_btn.setEnabled(False)
            btn_layout.addWidget(self.remove_btn)
        else:
            self.remove_btn = None
        
        # Clear button text depends on compact_buttons option
        clear_text = "Clear" if self.compact_buttons else "Clear All"
        self.clear_btn = QPushButton(clear_text)
        if button_style:
            self.clear_btn.setStyleSheet(button_style)
        self.clear_btn.clicked.connect(self.clear_all)
        self.clear_btn.setEnabled(False)
        btn_layout.addWidget(self.clear_btn)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
    def _generate_entry_id(self) -> int:
        """Generate unique entry ID"""
        self._entry_counter += 1
        return self._entry_counter
        
    def _create_entry(self, entry_type: str, path: Path) -> Dict:
        """Create a new entry with unique ID"""
        entry = {
            'type': entry_type,
            'path': path,
            'id': self._generate_entry_id()
        }
        
        # Add file count for folders
        if entry_type == 'folder':
            try:
                file_count = len(list(path.rglob('*')))
                entry['file_count'] = file_count
            except:
                entry['file_count'] = 0
                
        return entry
        
    def add_files(self):
        """Add files to selection with proper tracking"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Files", "", "All Files (*.*)"
        )
        
        if not file_paths:
            return
            
        added = 0
        for file_path in file_paths:
            path = Path(file_path)
            
            # Check for duplicates
            if any(e['path'] == path for e in self.entries if e['type'] == 'file'):
                logger.debug(f"File already in list: {path}")
                continue
                
            # Create entry
            entry = self._create_entry('file', path)
            self.entries.append(entry)
            self._entry_map[entry['id']] = entry
            self.selected_files.append(path)
            
            # Create list item
            item = QListWidgetItem(f"📄 {path.name}")
            item.setData(Qt.UserRole, entry['id'])
            item.setToolTip(str(path))
            self.file_list.addItem(item)
            
            added += 1
            
        if added > 0:
            logger.info(f"Added {added} files")
            self.log_message.emit(f"Added {added} files")
            self.files_changed.emit()
            self._update_ui_state()
            
    def add_folder(self):
        """Add folder to selection with proper tracking"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Folder"
        )
        
        if not folder_path:
            return
            
        path = Path(folder_path)
        
        # Check for duplicates
        if any(e['path'] == path for e in self.entries if e['type'] == 'folder'):
            logger.debug(f"Folder already in list: {path}")
            return
            
        # Create entry
        entry = self._create_entry('folder', path)
        self.entries.append(entry)
        self._entry_map[entry['id']] = entry
        self.selected_folders.append(path)
        
        # Create list item
        file_count = entry.get('file_count', 0)
        item = QListWidgetItem(f"📁 {path.name} ({file_count} files)")
        item.setData(Qt.UserRole, entry['id'])
        item.setToolTip(str(path))
        self.file_list.addItem(item)
        
        logger.info(f"Added folder with {file_count} files: {path.name}")
        self.log_message.emit(f"Added folder: {path.name}")
        self.files_changed.emit()
        self._update_ui_state()
        
    def remove_selected(self):
        """Remove selected items with proper state management"""
        selected_items = self.file_list.selectedItems()
        
        if not selected_items:
            return
            
        # Collect entries to remove
        entries_to_remove = []
        for item in selected_items:
            entry_id = item.data(Qt.UserRole)
            if entry_id in self._entry_map:
                entries_to_remove.append(self._entry_map[entry_id])
                
        # Remove from data structures
        for entry in entries_to_remove:
            # Remove from entries list
            if entry in self.entries:
                self.entries.remove(entry)
                
            # Remove from type-specific lists
            if entry['type'] == 'file':
                if entry['path'] in self.selected_files:
                    self.selected_files.remove(entry['path'])
            else:  # folder
                if entry['path'] in self.selected_folders:
                    self.selected_folders.remove(entry['path'])
                    
            # Remove from entry map
            if entry['id'] in self._entry_map:
                del self._entry_map[entry['id']]
                
        # Remove from UI
        for item in selected_items:
            row = self.file_list.row(item)
            self.file_list.takeItem(row)
            
        logger.info(f"Removed {len(entries_to_remove)} items")
        self.log_message.emit(f"Removed {len(entries_to_remove)} items")
        self.files_changed.emit()
        self._update_ui_state()
        
    def remove_files(self):
        """Legacy method for compatibility - redirects to remove_selected"""
        self.remove_selected()
        
    def clear_all(self):
        """Clear all selections"""
        self.entries.clear()
        self.selected_files.clear()
        self.selected_folders.clear()
        self._entry_map.clear()
        self.file_list.clear()
        
        logger.info("Cleared all items")
        self.log_message.emit("Cleared all items")
        self.files_changed.emit()
        self._update_ui_state()
        
    def _update_ui_state(self):
        """Update UI elements based on current state"""
        has_items = bool(self.entries)
        
        # Update button states
        if self.remove_btn:
            self.remove_btn.setEnabled(has_items)
        self.clear_btn.setEnabled(has_items)
        
        # Update count label
        file_count = len(self.selected_files)
        folder_count = len(self.selected_folders)
        
        if file_count and folder_count:
            count_text = f"{file_count} files, {folder_count} folders"
        elif file_count:
            count_text = f"{file_count} file{'s' if file_count != 1 else ''}"
        elif folder_count:
            count_text = f"{folder_count} folder{'s' if folder_count != 1 else ''}"
        else:
            count_text = "No items selected"
            
        self.count_label.setText(count_text)
        
    def get_all_items(self) -> Tuple[List[Path], List[Path]]:
        """Get all selected files and folders
        
        Returns:
            Tuple of (files list, folders list)
        """
        logger.debug(f"get_all_items called on FilesPanel {id(self)}")
        logger.debug(f"selected_files: {self.selected_files}")
        logger.debug(f"selected_folders: {self.selected_folders}")
        logger.debug(f"entries count: {len(self.entries)}")
        
        # Return copies to prevent external modification
        return self.selected_files.copy(), self.selected_folders.copy()
        
    def has_items(self) -> bool:
        """Check if any items are selected"""
        return bool(self.entries)
        
    def get_entry_count(self) -> int:
        """Get total number of entries"""
        return len(self.entries)
        
    def get_file_count(self) -> int:
        """Get number of selected files"""
        return len(self.selected_files)
        
    def get_folder_count(self) -> int:
        """Get number of selected folders"""
        return len(self.selected_folders)
        
    def clear(self):
        """Clear all selections (alias for clear_all)"""
        self.clear_all()