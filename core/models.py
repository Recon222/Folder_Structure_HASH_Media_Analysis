#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data models for the application - simple and clean
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import uuid
from PySide6.QtCore import QDateTime, Qt


@dataclass
class FormData:
    """Simple container for form data - no complex observers needed"""
    occurrence_number: str = ""
    business_name: str = ""
    location_address: str = ""
    extraction_start: Optional[QDateTime] = None
    extraction_end: Optional[QDateTime] = None
    time_offset: str = ""  # Text format: "DVR is X hr Y min Z sec AHEAD/BEHIND of realtime"
    dvr_time: Optional[QDateTime] = None
    real_time: Optional[QDateTime] = None
    technician_name: str = ""
    badge_number: str = ""
    include_tech_in_offset: bool = False
    upload_timestamp: Optional[QDateTime] = None
    
    def validate(self) -> List[str]:
        """Simple validation - return list of errors"""
        errors = []
        if not self.occurrence_number:
            errors.append("Occurrence number is required")
        if not self.location_address:
            errors.append("Location address is required")
        # Technician info is now stored in settings, not form data
        return errors
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON storage"""
        data = {}
        for key, value in asdict(self).items():
            if isinstance(value, QDateTime):
                data[key] = value.toString(Qt.ISODate) if value else None
            else:
                data[key] = value
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'FormData':
        """Create from dict"""
        form_data = cls()
        for key, value in data.items():
            if hasattr(form_data, key):
                if key.endswith('_time') or key == 'upload_timestamp' or 'extraction' in key:
                    # Convert string dates back to QDateTime
                    if value:
                        setattr(form_data, key, QDateTime.fromString(value, Qt.ISODate))
                else:
                    setattr(form_data, key, value)
        return form_data


@dataclass
class BatchJob:
    """Single job in a batch processing queue"""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_name: str = ""
    form_data: FormData = field(default_factory=FormData)
    files: List[Path] = field(default_factory=list)
    folders: List[Path] = field(default_factory=list)
    output_directory: Optional[Path] = None
    status: str = "pending"  # pending, processing, completed, failed
    error_message: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    template_type: str = "forensic"  # Always forensic mode
    
    def validate(self) -> List[str]:
        """Validate job configuration"""
        errors = []
        
        # Validate form data
        form_errors = self.form_data.validate()
        if form_errors:
            errors.extend([f"Form: {error}" for error in form_errors])
        
        # Validate files/folders
        if not self.files and not self.folders:
            errors.append("At least one file or folder must be selected")
            
        # Validate paths exist
        for file_path in self.files:
            if not file_path.exists():
                errors.append(f"File not found: {file_path}")
                
        for folder_path in self.folders:
            if not folder_path.exists():
                errors.append(f"Folder not found: {folder_path}")
                
        # Validate output directory
        if self.output_directory and not self.output_directory.parent.exists():
            errors.append(f"Output directory parent not found: {self.output_directory.parent}")
            
        return errors
    
    def to_dict(self) -> dict:
        """Serialize for saving"""
        return {
            'job_id': self.job_id,
            'job_name': self.job_name,
            'form_data': self.form_data.to_dict(),
            'files': [str(f) for f in self.files],
            'folders': [str(f) for f in self.folders],
            'output_directory': str(self.output_directory) if self.output_directory else None,
            'status': self.status,
            'error_message': self.error_message,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'template_type': self.template_type
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BatchJob':
        """Create from dict"""
        job = cls()
        job.job_id = data.get('job_id', str(uuid.uuid4()))
        job.job_name = data.get('job_name', '')
        job.form_data = FormData.from_dict(data.get('form_data', {}))
        job.files = [Path(f) for f in data.get('files', [])]
        job.folders = [Path(f) for f in data.get('folders', [])]
        job.output_directory = Path(data['output_directory']) if data.get('output_directory') else None
        job.status = data.get('status', 'pending')
        job.error_message = data.get('error_message', '')
        job.template_type = data.get('template_type', 'forensic')
        
        # Parse datetime fields
        if data.get('start_time'):
            job.start_time = datetime.fromisoformat(data['start_time'])
        if data.get('end_time'):
            job.end_time = datetime.fromisoformat(data['end_time'])
            
        return job
    
    def get_duration(self) -> Optional[float]:
        """Get job duration in seconds"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    def get_file_count(self) -> int:
        """Get total number of files in this job"""
        file_count = len(self.files)
        
        # Count files in folders
        for folder in self.folders:
            if folder.exists():
                file_count += sum(1 for _ in folder.rglob('*') if _.is_file())
                
        return file_count