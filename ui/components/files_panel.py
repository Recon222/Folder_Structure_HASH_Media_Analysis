#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Files panel component for file and folder selection with proper state management
"""

from pathlib import Path
from typing import List, Tuple, Dict, Optional, Literal
from dataclasses import dataclass

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, 
    QFileDialog, QLabel, QSizePolicy
)
from core.logger import logger


@dataclass
class FileEntry:
    """Represents a file or folder entry with consistent state"""
    path: Path
    type: Literal['file', 'folder']
    file_count: Optional[int] = None  # For folders, tracks number of files inside


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
        
        # Simplified state management - single source of truth
        self.entries: List[FileEntry] = []
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Create the files panel UI"""
        layout = QVBoxLayout()
        
        # File list - CRITICAL FIX: Prevent expansion from long file paths
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        # Prevent list from expanding horizontally due to long file names
        self.file_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.file_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Set reasonable size constraints
        self.file_list.setMinimumHeight(100)
        layout.addWidget(self.file_list)
        
        # Count label - CRITICAL FIX: Prevent expansion from long count text
        self.count_label = QLabel("No items selected")
        self.count_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.count_label.setMaximumHeight(30)
        layout.addWidget(self.count_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        # Button styling based on compact_buttons option
        button_style = "QPushButton { padding: 6px 12px; min-width: 90px; }" if self.compact_buttons else ""
        
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
        
    def _create_entry(self, entry_type: Literal['file', 'folder'], path: Path) -> FileEntry:
        """Create a new FileEntry"""
        file_count = None
        
        # Add file count for folders
        if entry_type == 'folder':
            try:
                file_count = len([f for f in path.rglob('*') if f.is_file()])
            except:
                file_count = 0
                
        return FileEntry(path=path, type=entry_type, file_count=file_count)
        
    def add_files(self):
        """Add files to selection with simplified state management"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Files", "", "All Files (*.*)"
        )
        
        if not file_paths:
            return
            
        added = 0
        for file_path in file_paths:
            path = Path(file_path)
            
            # Check for duplicates
            if any(entry.path == path and entry.type == 'file' for entry in self.entries):
                logger.debug(f"File already in list: {path}")
                continue
                
            # Create entry
            entry = self._create_entry('file', path)
            self.entries.append(entry)
            
            # Create list item - CRITICAL FIX: Truncate long file names
            display_name = path.name
            if len(display_name) > 50:  # Truncate very long names
                display_name = display_name[:47] + "..."
            
            item = QListWidgetItem(f"📄 {display_name}")
            item.setData(Qt.UserRole, len(self.entries) - 1)  # Store index
            item.setToolTip(str(path))  # Full path in tooltip
            self.file_list.addItem(item)
            
            added += 1
            
        if added > 0:
            logger.info(f"Added {added} files")
            self.log_message.emit(f"Added {added} files")
            self.files_changed.emit()
            self._update_ui_state()
            
    def add_folder(self):
        """Add folder to selection with simplified state management"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Folder"
        )
        
        if not folder_path:
            return
            
        path = Path(folder_path)
        
        # Check for duplicates
        if any(entry.path == path and entry.type == 'folder' for entry in self.entries):
            logger.debug(f"Folder already in list: {path}")
            return
            
        # Create entry
        entry = self._create_entry('folder', path)
        self.entries.append(entry)
        
        # Create list item - CRITICAL FIX: Truncate long folder names
        file_count = entry.file_count or 0
        display_name = path.name
        if len(display_name) > 40:  # Truncate long folder names (leave room for file count)
            display_name = display_name[:37] + "..."
        
        item = QListWidgetItem(f"📁 {display_name} ({file_count} files)")
        item.setData(Qt.UserRole, len(self.entries) - 1)  # Store index
        item.setToolTip(str(path))  # Full path in tooltip
        self.file_list.addItem(item)
        
        logger.info(f"Added folder with {file_count} files: {path.name}")
        self.log_message.emit(f"Added folder: {path.name}")
        self.files_changed.emit()
        self._update_ui_state()
        
    def remove_selected(self):
        """Remove selected items with simplified state management"""
        selected_items = self.file_list.selectedItems()
        
        if not selected_items:
            return
            
        # Collect indices to remove (sorted in reverse order to avoid index shifting)
        indices_to_remove = []
        for item in selected_items:
            index = item.data(Qt.UserRole)
            if index is not None and 0 <= index < len(self.entries):
                indices_to_remove.append(index)
                
        indices_to_remove.sort(reverse=True)
        
        # Remove entries from data structure (reverse order to maintain indices)
        removed_count = 0
        for index in indices_to_remove:
            if 0 <= index < len(self.entries):
                self.entries.pop(index)
                removed_count += 1
                
        # Clear and rebuild UI list to maintain correct indices - CRITICAL FIX: Apply truncation
        self.file_list.clear()
        for i, entry in enumerate(self.entries):
            if entry.type == 'file':
                display_name = entry.path.name
                if len(display_name) > 50:
                    display_name = display_name[:47] + "..."
                item = QListWidgetItem(f"📄 {display_name}")
            else:
                file_count = entry.file_count or 0
                display_name = entry.path.name
                if len(display_name) > 40:
                    display_name = display_name[:37] + "..."
                item = QListWidgetItem(f"📁 {display_name} ({file_count} files)")
            
            item.setData(Qt.UserRole, i)
            item.setToolTip(str(entry.path))  # Full path in tooltip
            self.file_list.addItem(item)
            
        logger.info(f"Removed {removed_count} items")
        self.log_message.emit(f"Removed {removed_count} items")
        self.files_changed.emit()
        self._update_ui_state()
        
    def remove_files(self):
        """Legacy method for compatibility - redirects to remove_selected"""
        self.remove_selected()
        
    def clear_all(self):
        """Clear all selections with simplified state"""
        self.entries.clear()
        self.file_list.clear()
        
        logger.info("Cleared all items")
        self.log_message.emit("Cleared all items")
        self.files_changed.emit()
        self._update_ui_state()
        
    def _update_ui_state(self):
        """Update UI elements based on simplified state"""
        has_items = bool(self.entries)
        
        # Update button states
        if self.remove_btn:
            self.remove_btn.setEnabled(has_items)
        self.clear_btn.setEnabled(has_items)
        
        # Update count label
        file_count = len([e for e in self.entries if e.type == 'file'])
        folder_count = len([e for e in self.entries if e.type == 'folder'])
        
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
        """Get all selected files and folders with simplified state
        
        Returns:
            Tuple of (files list, folders list)
        """
        logger.debug(f"get_all_items called on FilesPanel {id(self)}")
        logger.debug(f"entries count: {len(self.entries)}")
        
        files = [entry.path for entry in self.entries if entry.type == 'file']
        folders = [entry.path for entry in self.entries if entry.type == 'folder']
        
        logger.debug(f"files: {files}")
        logger.debug(f"folders: {folders}")
        
        return files, folders
        
    def has_items(self) -> bool:
        """Check if any items are selected"""
        return bool(self.entries)
        
    def get_entry_count(self) -> int:
        """Get total number of entries"""
        return len(self.entries)
        
    def get_file_count(self) -> int:
        """Get number of selected files"""
        return len([entry for entry in self.entries if entry.type == 'file'])
        
    def get_folder_count(self) -> int:
        """Get number of selected folders"""
        return len([entry for entry in self.entries if entry.type == 'folder'])
        
    def clear(self):
        """Clear all selections (alias for clear_all)"""
        self.clear_all()
        
    # Additional interface methods for compatibility
    def get_files(self) -> List[Path]:
        """Get list of selected files"""
        return [entry.path for entry in self.entries if entry.type == 'file']
        
    def get_folders(self) -> List[Path]:
        """Get list of selected folders"""
        return [entry.path for entry in self.entries if entry.type == 'folder']
        
    def has_files(self) -> bool:
        """Check if any files are selected"""
        return any(entry.type == 'file' for entry in self.entries)
        
    # Properties for backward compatibility (BatchTab direct access)
    @property
    def selected_files(self) -> List[Path]:
        """Get selected files as property for backward compatibility"""
        return [entry.path for entry in self.entries if entry.type == 'file']
        
    @property
    def selected_folders(self) -> List[Path]:
        """Get selected folders as property for backward compatibility"""
        return [entry.path for entry in self.entries if entry.type == 'folder']