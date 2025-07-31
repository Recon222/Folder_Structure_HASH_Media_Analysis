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
        calculate_hash: bool = True
    ) -> FolderStructureThread:
        """Process files using forensic folder structure"""
        # Build forensic structure
        folder_path = self._build_forensic_structure(form_data, output_directory)
        
        # Prepare all items
        all_items = self._prepare_items(files, folders)
        
        # Create and return thread
        thread = FolderStructureThread(all_items, folder_path, calculate_hash)
        self.current_operation = thread
        return thread
        
    def _build_forensic_structure(self, form_data: FormData, base_path: Path) -> Path:
        """Build the forensic folder structure"""
        # Create the structure in the specified base path
        occurrence_path = base_path / form_data.occurrence_number
        
        # Level 2: Business @ Address or just Address
        if form_data.business_name:
            level2 = f"{form_data.business_name} @ {form_data.location_address}"
        else:
            level2 = form_data.location_address
            
        # Level 3: Date range
        if form_data.extraction_start and form_data.extraction_end:
            start = form_data.extraction_start.toString("yyyy-MM-dd_HHmm")
            end = form_data.extraction_end.toString("yyyy-MM-dd_HHmm")
            level3 = f"{start} - {end}"
        else:
            from datetime import datetime
            now = datetime.now().strftime("%Y-%m-%d_%H%M")
            level3 = f"{now} - {now}"
            
        # Clean path parts
        level2 = FolderTemplate._sanitize_path_part(None, level2)
        level3 = FolderTemplate._sanitize_path_part(None, level3)
        
        # Combine
        full_path = occurrence_path / level2 / level3
        full_path.mkdir(parents=True, exist_ok=True)
        
        return full_path
        
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