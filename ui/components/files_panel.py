#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Files panel component for file and folder selection
"""

from pathlib import Path
from typing import List, Tuple

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QFileDialog
)


class FilesPanel(QGroupBox):
    """Panel for selecting files and folders to process"""
    
    # Signal emitted when files are added/removed
    files_changed = Signal()
    
    # Signal for logging
    log_message = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__("Files to Process", parent)
        self.selected_files: List[Path] = []
        self.selected_folders: List[Path] = []
        self._setup_ui()
        
    def _setup_ui(self):
        """Create the files panel UI"""
        layout = QVBoxLayout()
        
        # File list
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.file_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.add_files_btn = QPushButton("Add Files")
        self.add_files_btn.clicked.connect(self.add_files)
        btn_layout.addWidget(self.add_files_btn)
        
        self.add_folder_btn = QPushButton("Add Folder")
        print(f"DEBUG: Connecting add_folder button in FilesPanel {id(self)}")
        self.add_folder_btn.clicked.connect(self.add_folder)
        btn_layout.addWidget(self.add_folder_btn)
        
        self.remove_files_btn = QPushButton("Remove")
        self.remove_files_btn.clicked.connect(self.remove_files)
        btn_layout.addWidget(self.remove_files_btn)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
    def add_files(self):
        """Add files to process"""
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "All Files (*.*)")
        for file in files:
            path = Path(file)
            if path not in self.selected_files:
                self.selected_files.append(path)
                self.file_list.addItem(f"📄 {path.name}")
        self.log_message.emit(f"Added {len(files)} files")
        self.files_changed.emit()
        
    def add_folder(self):
        """Add entire folder structure with all subdirectories and files"""
        print("DEBUG: add_folder called")
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            folder_path = Path(folder)
            print(f"DEBUG: Selected folder: {folder_path}")
            
            # Add the folder itself to track
            if folder_path not in self.selected_folders:
                print(f"DEBUG: Folder not in list, adding it")
                self.selected_folders.append(folder_path)
                print(f"DEBUG: Current folders list: {self.selected_folders}")
                self.file_list.addItem(f"📁 {folder_path.name}/ (entire folder structure)")
                print(f"DEBUG: Added to UI list")
                
                # Count total files for logging
                file_count = sum(1 for _ in folder_path.rglob('*') if _.is_file())
                self.log_message.emit(f"Added folder '{folder_path.name}' with {file_count} files")
                self.files_changed.emit()
            else:
                print(f"DEBUG: Folder already in list, skipping")
            
    def remove_files(self):
        """Remove selected files or folders"""
        for item in self.file_list.selectedItems():
            row = self.file_list.row(item)
            item_text = item.text()
            self.file_list.takeItem(row)
            
            # Determine if it's a file or folder and remove from appropriate list
            if item_text.startswith("📄"):
                # It's a file - remove from selected_files
                if row < len(self.selected_files):
                    self.selected_files.pop(row)
            elif item_text.startswith("📁"):
                # It's a folder - find and remove from selected_folders
                for i, folder in enumerate(self.selected_folders):
                    if folder.name in item_text:
                        self.selected_folders.pop(i)
                        break
                        
        self.log_message.emit("Removed selected items")
        self.files_changed.emit()
        
    def get_all_items(self) -> Tuple[List[Path], List[Path]]:
        """Return all selected files and folders"""
        print(f"DEBUG: get_all_items called on FilesPanel {id(self)}")
        print(f"DEBUG: selected_files: {self.selected_files}")
        print(f"DEBUG: selected_folders: {self.selected_folders}")
        print(f"DEBUG: UI list count: {self.file_list.count()}")
        for i in range(self.file_list.count()):
            print(f"DEBUG: UI item {i}: {self.file_list.item(i).text()}")
        return self.selected_files.copy(), self.selected_folders.copy()
        
    def has_items(self) -> bool:
        """Check if any files or folders are selected"""
        return bool(self.selected_files or self.selected_folders)
        
    def clear(self):
        """Clear all selected files and folders"""
        self.selected_files.clear()
        self.selected_folders.clear()
        self.file_list.clear()
        self.files_changed.emit()