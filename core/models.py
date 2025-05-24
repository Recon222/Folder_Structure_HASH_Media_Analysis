#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data models for the application - simple and clean
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime
from PySide6.QtCore import QDateTime, Qt


@dataclass
class FormData:
    """Simple container for form data - no complex observers needed"""
    occurrence_number: str = ""
    business_name: str = ""
    location_address: str = ""
    extraction_start: Optional[QDateTime] = None
    extraction_end: Optional[QDateTime] = None
    time_offset: int = 0
    dvr_time: Optional[QDateTime] = None
    real_time: Optional[QDateTime] = None
    technician_name: str = ""
    badge_number: str = ""
    upload_timestamp: Optional[QDateTime] = None
    
    def validate(self) -> List[str]:
        """Simple validation - return list of errors"""
        errors = []
        if not self.occurrence_number:
            errors.append("Occurrence number is required")
        if not self.location_address:
            errors.append("Location address is required")
        if not self.technician_name:
            errors.append("Technician name is required")
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