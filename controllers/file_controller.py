#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File controller - handles all file processing operations
"""

from pathlib import Path
from typing import List, Dict, Tuple, Optional

from core.models import FormData
from core.templates import FolderTemplate, FolderBuilder
from core.workers import FileOperationThread, FolderStructureThread
from core.path_utils import ForensicPathBuilder


class FileController:
    """Handles all file processing operations"""
    
    def __init__(self):
        self.current_operation: Optional[FolderStructureThread] = None
        
    def process_forensic_files(
        self,
        form_data: FormData,
        files: List[Path],
        folders: List[Path],
        output_directory: Path,
        calculate_hash: bool = True,
        performance_monitor = None
    ) -> FolderStructureThread:
        """Process files using forensic folder structure"""
        # Build forensic structure
        folder_path = self._build_forensic_structure(form_data, output_directory)
        
        # Prepare all items
        all_items = self._prepare_items(files, folders)
        
        # Create and return thread with performance monitor
        thread = FolderStructureThread(all_items, folder_path, calculate_hash, performance_monitor)
        self.current_operation = thread
        return thread
        
    def _build_forensic_structure(self, form_data: FormData, base_path: Path) -> Path:
        """Build the forensic folder structure using ForensicPathBuilder"""
        # Use the centralized path builder to create forensic structure
        return ForensicPathBuilder.create_forensic_structure(base_path, form_data)
        
    def _prepare_items(
        self,
        files: List[Path],
        folders: List[Path]
    ) -> List[Tuple[str, Path, Optional[str]]]:
        """Prepare all items for copying"""
        all_items = []
        
        # Add individual files
        for file in files:
            all_items.append(('file', file, file.name))
            
        # Add folders with their complete structure
        for folder in folders:
            all_items.append(('folder', folder, None))
            
        return all_items
        
    def cancel_operation(self):
        """Cancel the current operation if running"""
        if self.current_operation and self.current_operation.isRunning():
            self.current_operation.cancel()
            return True
        return False