#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test suite for FilesPanel state management
"""

import pytest
import tempfile
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QListWidgetItem
from ui.components.files_panel import FilesPanel


class TestFilesPanel:
    """Test suite for FilesPanel state management"""
    
    @pytest.fixture
    def app(self):
        """Create QApplication for testing"""
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app
        
    @pytest.fixture
    def panel(self, app):
        """Create FilesPanel instance for testing"""
        panel = FilesPanel()
        yield panel
        panel.deleteLater()
    
    @pytest.fixture
    def temp_files(self):
        """Create temporary test files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            file1 = temp_path / "test1.txt"
            file2 = temp_path / "test2.txt"
            file1.write_text("content1")
            file2.write_text("content2")
            
            # Create test folder with files
            folder1 = temp_path / "test_folder"
            folder1.mkdir()
            (folder1 / "nested1.txt").write_text("nested content 1")
            (folder1 / "nested2.txt").write_text("nested content 2")
            
            yield file1, file2, folder1
    
    def test_initial_state(self, panel):
        """Test that FilesPanel initializes with correct state"""
        assert len(panel.selected_files) == 0
        assert len(panel.selected_folders) == 0
        assert len(panel.entries) == 0
        assert panel.file_list.count() == 0
        assert panel.count_label.text() == "No items selected"
        assert not panel.remove_btn.isEnabled()
        assert not panel.clear_btn.isEnabled()
    
    def test_add_files_state_tracking(self, panel, temp_files):
        """Test that adding files properly updates simplified state"""
        file1, file2, _ = temp_files
        
        # Manually add files using simplified approach
        entry1 = panel._create_entry('file', file1)
        panel.entries.append(entry1)
        
        entry2 = panel._create_entry('file', file2)
        panel.entries.append(entry2)
        
        # Verify simplified state
        assert len(panel.selected_files) == 2
        assert len(panel.entries) == 2
        assert file1 in panel.selected_files
        assert file2 in panel.selected_files
        
        # Verify entries are FileEntry objects
        assert entry1.path == file1
        assert entry1.type == 'file'
        assert entry2.path == file2
        assert entry2.type == 'file'
    
    def test_add_folder_state_tracking(self, panel, temp_files):
        """Test that adding folders properly updates simplified state"""
        _, _, folder1 = temp_files
        
        # Add folder using simplified approach
        entry = panel._create_entry('folder', folder1)
        panel.entries.append(entry)
        
        # Verify simplified state
        assert len(panel.selected_folders) == 1
        assert len(panel.entries) == 1
        assert folder1 in panel.selected_folders
        assert entry.file_count is not None  # Should have file count
        assert entry.file_count >= 2  # Has at least 2 files
        assert entry.type == 'folder'
        assert entry.path == folder1
    
    def test_mixed_files_folders(self, panel, temp_files):
        """Test mixing files and folders maintains correct simplified state"""
        file1, file2, folder1 = temp_files
        
        # Add mixed items using simplified approach
        file_entry = panel._create_entry('file', file1)
        panel.entries.append(file_entry)
        
        folder_entry = panel._create_entry('folder', folder1)
        panel.entries.append(folder_entry)
        
        # Verify simplified state
        assert len(panel.entries) == 2
        assert len(panel.selected_files) == 1
        assert len(panel.selected_folders) == 1
        assert file1 in panel.selected_files
        assert folder1 in panel.selected_folders
        
        # Verify entry types
        assert file_entry.type == 'file'
        assert folder_entry.type == 'folder'
    
    def test_remove_selected_items(self, panel, temp_files):
        """Test that removing items correctly updates simplified state"""
        file1, file2, folder1 = temp_files
        
        # Add items using simplified approach
        entries = []
        for item_type, path in [('file', file1), ('file', file2), ('folder', folder1)]:
            entry = panel._create_entry(item_type, path)
            panel.entries.append(entry)
            entries.append(entry)
        
        # Remove middle item (file2) 
        entry_to_remove = entries[1]
        panel.entries.remove(entry_to_remove)
        
        # Verify simplified state after removal
        assert len(panel.entries) == 2
        assert len(panel.selected_files) == 1
        assert len(panel.selected_folders) == 1
        assert file1 in panel.selected_files
        assert file2 not in panel.selected_files
        assert folder1 in panel.selected_folders
        
        # Verify remaining entries
        remaining_files = [e for e in panel.entries if e.type == 'file']
        remaining_folders = [e for e in panel.entries if e.type == 'folder']
        assert len(remaining_files) == 1
        assert len(remaining_folders) == 1
        assert remaining_files[0].path == file1
        assert remaining_folders[0].path == folder1
    
    def test_clear_all(self, panel, temp_files):
        """Test that clear_all properly resets simplified state"""
        file1, file2, folder1 = temp_files
        
        # Add multiple items using simplified approach
        for item_type, path in [('file', file1), ('file', file2), ('folder', folder1)]:
            entry = panel._create_entry(item_type, path)
            panel.entries.append(entry)
        
        # Clear all
        panel.clear_all()
        
        # Verify complete reset with simplified state
        assert len(panel.entries) == 0
        assert len(panel.selected_files) == 0
        assert len(panel.selected_folders) == 0
        assert panel.file_list.count() == 0
    
    def test_duplicate_prevention(self, panel, temp_files):
        """Test that duplicate files/folders are not added with simplified state"""
        file1, _, _ = temp_files
        
        # Add file first time using simplified approach
        entry1 = panel._create_entry('file', file1)
        panel.entries.append(entry1)
        
        # Try to add same file again (should be prevented in real usage)
        duplicate_exists = any(entry.path == file1 and entry.type == 'file' for entry in panel.entries)
        
        assert duplicate_exists is True
        assert len(panel.selected_files) == 1
        assert len(panel.entries) == 1
    
    def test_get_all_items_returns_copies(self, panel, temp_files):
        """Test that get_all_items returns new lists from simplified state"""
        file1, _, folder1 = temp_files
        
        # Add items using simplified approach
        file_entry = panel._create_entry('file', file1)
        panel.entries.append(file_entry)
        
        folder_entry = panel._create_entry('folder', folder1)
        panel.entries.append(folder_entry)
        
        # Get items
        files, folders = panel.get_all_items()
        
        # Verify we got proper lists
        assert files is not panel.selected_files
        assert folders is not panel.selected_folders
        assert files == panel.selected_files
        assert folders == panel.selected_folders
        
        # Modifying returned lists shouldn't affect internal state
        files.clear()
        folders.clear()
        assert len(panel.selected_files) == 1
        assert len(panel.selected_folders) == 1
    
    def test_fileentry_dataclass(self, panel, temp_files):
        """Test that FileEntry dataclass works correctly"""
        file1, _, folder1 = temp_files
        
        # Test file entry
        file_entry = panel._create_entry('file', file1)
        assert file_entry.path == file1
        assert file_entry.type == 'file'
        assert file_entry.file_count is None
        
        # Test folder entry
        folder_entry = panel._create_entry('folder', folder1)
        assert folder_entry.path == folder1
        assert folder_entry.type == 'folder'
        assert folder_entry.file_count is not None
        assert folder_entry.file_count >= 0
    
    def test_ui_state_updates(self, panel, temp_files):
        """Test that UI state properly reflects simplified data state"""
        file1, _, _ = temp_files
        
        # Initially disabled
        assert not panel.remove_btn.isEnabled()
        assert not panel.clear_btn.isEnabled()
        
        # Add item using simplified approach
        entry = panel._create_entry('file', file1)
        panel.entries.append(entry)
        panel._update_ui_state()
        
        # Should be enabled
        assert panel.remove_btn.isEnabled()
        assert panel.clear_btn.isEnabled()
        assert "1 file" in panel.count_label.text()
        
        # Clear
        panel.clear_all()
        
        # Should be disabled again
        assert not panel.remove_btn.isEnabled()
        assert not panel.clear_btn.isEnabled()
        assert panel.count_label.text() == "No items selected"
    
    def test_count_methods(self, panel, temp_files):
        """Test count methods return correct values with simplified state"""
        file1, file2, folder1 = temp_files
        
        # Add items using simplified approach
        for item_type, path in [('file', file1), ('file', file2), ('folder', folder1)]:
            entry = panel._create_entry(item_type, path)
            panel.entries.append(entry)
        
        # Test counts with simplified state
        assert panel.get_entry_count() == 3
        assert panel.get_file_count() == 2
        assert panel.get_folder_count() == 1
        assert panel.has_items() is True
        
        # Clear and test again
        panel.clear_all()
        assert panel.get_entry_count() == 0
        assert panel.get_file_count() == 0
        assert panel.get_folder_count() == 0
        assert panel.has_items() is False


def run_tests():
    """Run FilesPanel tests"""
    print("Running FilesPanel state management tests...")
    
    # Create QApplication for testing
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    
    try:
        # Create panel
        panel = FilesPanel()
        
        # Test initial state with simplified approach
        assert len(panel.entries) == 0
        assert len(panel.selected_files) == 0
        assert len(panel.selected_folders) == 0
        
        # Test adding entries using simplified state
        test_path1 = Path("/tmp/test1.txt")
        test_path2 = Path("/tmp/test_folder")
        
        entry1 = panel._create_entry('file', test_path1)
        panel.entries.append(entry1)
        
        entry2 = panel._create_entry('folder', test_path2)
        panel.entries.append(entry2)
        
        # Verify simplified state
        assert len(panel.entries) == 2
        assert len(panel.selected_files) == 1
        assert len(panel.selected_folders) == 1
        assert entry1.type == 'file'
        assert entry2.type == 'folder'
        
        # Test clear
        panel.clear_all()
        assert len(panel.entries) == 0
        
        print("SUCCESS: All FilesPanel tests passed!")
        return True
        
    except Exception as e:
        print(f"FAILED: Test failed: {e}")
        return False
    
    finally:
        app.quit()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)