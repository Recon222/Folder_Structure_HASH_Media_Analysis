#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Form panel component for case information input
"""

from PySide6.QtCore import Qt, QDateTime, Signal
from PySide6.QtWidgets import (
    QGroupBox, QGridLayout, QLabel, QLineEdit,
    QDateTimeEdit, QHBoxLayout, QPushButton
)

from core.models import FormData


class FormPanel(QGroupBox):
    """Panel for entering case/forensic information"""
    
    # Signals
    calculate_offset_requested = Signal()
    form_data_changed = Signal(str, object)  # field_name, new_value
    
    def __init__(self, form_data: FormData, parent=None):
        super().__init__("Case Information", parent)
        self.form_data = form_data
        self._setup_ui()
        
    def _update_field(self, field_name: str, value):
        """Update form data field and emit signal
        
        Args:
            field_name: Name of the field to update
            value: New value for the field
        """
        setattr(self.form_data, field_name, value)
        self.form_data_changed.emit(field_name, value)
        
    def _setup_ui(self):
        """Create the form UI"""
        layout = QGridLayout()
        
        # Row 0: Occurrence Number
        layout.addWidget(QLabel("Occurrence #:"), 0, 0)
        self.occ_number = QLineEdit()
        self.occ_number.textChanged.connect(lambda t: self._update_field('occurrence_number', t))
        layout.addWidget(self.occ_number, 0, 1)
        
        # Row 1: Business Name
        layout.addWidget(QLabel("Business Name:"), 1, 0)
        self.business_name = QLineEdit()
        self.business_name.textChanged.connect(lambda t: self._update_field('business_name', t))
        layout.addWidget(self.business_name, 1, 1)
        
        # Row 2: Location Address
        layout.addWidget(QLabel("Address:"), 2, 0)
        self.location_address = QLineEdit()
        self.location_address.textChanged.connect(lambda t: self._update_field('location_address', t))
        layout.addWidget(self.location_address, 2, 1)
        
        # Row 3: Extraction Times
        layout.addWidget(QLabel("Extraction Start:"), 3, 0)
        self.extraction_start = QDateTimeEdit(QDateTime.currentDateTime())
        self.extraction_start.setCalendarPopup(True)
        self.extraction_start.dateTimeChanged.connect(lambda dt: self._update_field('extraction_start', dt))
        layout.addWidget(self.extraction_start, 3, 1)
        # Initialize form data with current value
        self.form_data.extraction_start = self.extraction_start.dateTime()
        
        layout.addWidget(QLabel("Extraction End:"), 4, 0)
        self.extraction_end = QDateTimeEdit(QDateTime.currentDateTime())
        self.extraction_end.setCalendarPopup(True)
        self.extraction_end.dateTimeChanged.connect(lambda dt: self._update_field('extraction_end', dt))
        layout.addWidget(self.extraction_end, 4, 1)
        # Initialize form data with current value
        self.form_data.extraction_end = self.extraction_end.dateTime()
        
        # Row 5: Time Offset
        layout.addWidget(QLabel("Time Offset:"), 5, 0)
        offset_layout = QHBoxLayout()
        self.time_offset = QLineEdit()
        self.time_offset.setPlaceholderText("e.g., DVR is 1hr 30min AHEAD of realtime")
        self.time_offset.textChanged.connect(lambda t: self._update_field('time_offset', t))
        offset_layout.addWidget(self.time_offset)
        
        self.calc_offset_btn = QPushButton("Calculate")
        self.calc_offset_btn.clicked.connect(self.calculate_time_offset)
        offset_layout.addWidget(self.calc_offset_btn)
        layout.addLayout(offset_layout, 5, 1)
        
        # Row 6: DVR Time
        layout.addWidget(QLabel("DVR Time:"), 6, 0)
        self.dvr_time = QDateTimeEdit()
        self.dvr_time.setCalendarPopup(True)
        self.dvr_time.setDateTime(QDateTime())  # Empty/invalid datetime
        self.dvr_time.setSpecialValueText(" ")  # Show blank when empty
        self.dvr_time.dateTimeChanged.connect(lambda dt: self._update_field('dvr_time', dt if dt.isValid() else None))
        layout.addWidget(self.dvr_time, 6, 1)
        
        # Row 7: Real Time
        layout.addWidget(QLabel("Real Time:"), 7, 0)
        self.real_time = QDateTimeEdit()
        self.real_time.setCalendarPopup(True)
        self.real_time.setDateTime(QDateTime())  # Empty/invalid datetime
        self.real_time.setSpecialValueText(" ")  # Show blank when empty
        self.real_time.dateTimeChanged.connect(lambda dt: self._update_field('real_time', dt if dt.isValid() else None))
        layout.addWidget(self.real_time, 7, 1)
        
        # Row 8: Technician Info
        layout.addWidget(QLabel("Technician:"), 8, 0)
        self.tech_name = QLineEdit()
        self.tech_name.textChanged.connect(lambda t: self._update_field('technician_name', t))
        layout.addWidget(self.tech_name, 8, 1)
        
        layout.addWidget(QLabel("Badge #:"), 9, 0)
        self.badge_number = QLineEdit()
        self.badge_number.textChanged.connect(lambda t: self._update_field('badge_number', t))
        layout.addWidget(self.badge_number, 9, 1)
        
        # Row 10: Upload Timestamp
        layout.addWidget(QLabel("Upload Time:"), 10, 0)
        self.upload_timestamp = QDateTimeEdit(QDateTime.currentDateTime())
        self.upload_timestamp.setCalendarPopup(True)
        self.upload_timestamp.dateTimeChanged.connect(lambda dt: self._update_field('upload_timestamp', dt))
        layout.addWidget(self.upload_timestamp, 10, 1)
        # Initialize form data
        self.form_data.upload_timestamp = self.upload_timestamp.dateTime()
        
        self.setLayout(layout)
        
    def calculate_time_offset(self):
        """Calculate time offset between DVR and real time"""
        if self.form_data.dvr_time and self.form_data.real_time:
            offset_seconds = self.form_data.dvr_time.secsTo(self.form_data.real_time)
            
            # Determine if DVR is ahead or behind
            if offset_seconds < 0:
                direction = "AHEAD"
                offset_seconds = abs(offset_seconds)
            else:
                direction = "BEHIND"
            
            # Convert to hours, minutes, seconds
            hours = offset_seconds // 3600
            minutes = (offset_seconds % 3600) // 60
            seconds = offset_seconds % 60
            
            # Format the string
            parts = []
            if hours > 0:
                parts.append(f"{hours}hr")
            if minutes > 0:
                parts.append(f"{minutes}min")
            if seconds > 0 or (hours == 0 and minutes == 0):
                parts.append(f"{seconds}sec")
            
            offset_text = f"DVR is {' '.join(parts)} {direction} of realtime"
            self.time_offset.setText(offset_text)
            self.calculate_offset_requested.emit()
            
    def load_from_data(self, form_data: FormData):
        """Load form fields from FormData object"""
        self.occ_number.setText(form_data.occurrence_number)
        self.business_name.setText(form_data.business_name)
        self.location_address.setText(form_data.location_address)
        self.tech_name.setText(form_data.technician_name)
        self.badge_number.setText(form_data.badge_number)
        if form_data.extraction_start:
            self.extraction_start.setDateTime(form_data.extraction_start)
        if form_data.extraction_end:
            self.extraction_end.setDateTime(form_data.extraction_end)
        if form_data.dvr_time:
            self.dvr_time.setDateTime(form_data.dvr_time)
        if form_data.real_time:
            self.real_time.setDateTime(form_data.real_time)
        if form_data.upload_timestamp:
            self.upload_timestamp.setDateTime(form_data.upload_timestamp)
        # Handle both string and legacy integer formats
        if isinstance(form_data.time_offset, int):
            # Convert legacy integer minutes to text format
            if form_data.time_offset != 0:
                minutes = abs(form_data.time_offset)
                direction = "BEHIND" if form_data.time_offset > 0 else "AHEAD"
                self.time_offset.setText(f"DVR is {minutes}min {direction} of realtime")
            else:
                self.time_offset.setText("")
        else:
            self.time_offset.setText(form_data.time_offset)