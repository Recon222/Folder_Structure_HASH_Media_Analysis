#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF generation for reports - time offset sheets and technician logs
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import csv

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from .models import FormData
from PySide6.QtCore import QSettings


class PDFGenerator:
    """Generates PDF reports for forensic documentation"""
    
    def __init__(self):
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab is required for PDF generation. Install with: pip install reportlab")
            
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
        # Get technician info from settings
        self.settings = QSettings('FolderStructureUtility', 'Settings')
        self.tech_name = self.settings.value('technician_name', '', type=str)
        self.badge_number = self.settings.value('badge_number', '', type=str)
        
    def _setup_custom_styles(self):
        """Set up custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=16,
            textColor=colors.HexColor('#13294B'),  # Carolina Blue dark
            spaceAfter=30
        ))
        
        # Header style
        self.styles.add(ParagraphStyle(
            name='CustomHeader',
            parent=self.styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#13294B'),
            spaceAfter=12
        ))
        
    def generate_time_offset_report(self, form_data: FormData, output_path: Path) -> bool:
        """
        Generate time offset report PDF
        
        Args:
            form_data: Form data containing time information
            output_path: Where to save the PDF
            
        Returns:
            True if successful
        """
        try:
            doc = SimpleDocTemplate(str(output_path), pagesize=letter)
            story = []
            
            # Title
            story.append(Paragraph("DVR Time Offset Report", self.styles['CustomTitle']))
            story.append(Spacer(1, 0.2*inch))
            
            # Case information
            story.append(Paragraph("Case Information", self.styles['CustomHeader']))
            
            case_data = [
                ['Occurrence Number:', form_data.occurrence_number],
                ['Location:', form_data.location_address],
                ['Business:', form_data.business_name or 'N/A']
            ]
            
            # Only include technician info if checkbox is selected
            if hasattr(form_data, 'include_tech_in_offset') and form_data.include_tech_in_offset:
                case_data.append(['Technician:', f"{self.tech_name} (Badge: {self.badge_number})"])
            
            case_table = Table(case_data, colWidths=[2*inch, 4*inch])
            case_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            story.append(case_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Time offset information
            story.append(Paragraph("Time Offset Calculation", self.styles['CustomHeader']))
            
            # Check if we have time offset data
            if form_data.time_offset:
                # If DVR and real times are provided, show them
                if form_data.dvr_time and form_data.real_time:
                    time_data = [
                        ['DVR Time:', form_data.dvr_time.toString('yyyy-MM-dd HH:mm:ss')],
                        ['Real Time:', form_data.real_time.toString('yyyy-MM-dd HH:mm:ss')],
                        ['Time Offset:', form_data.time_offset],
                        ['', ''],
                        ['Note:', 'Time offset calculated from DVR and Real Time']
                    ]
                else:
                    # Just show the manually entered offset
                    time_data = [
                        ['Time Offset:', form_data.time_offset],
                        ['', ''],
                        ['Note:', 'Time offset manually entered']
                    ]
            else:
                time_data = [['No time offset data available', '']]
                
            time_table = Table(time_data, colWidths=[2*inch, 4*inch])
            time_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            story.append(time_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Extraction period
            story.append(Paragraph("Extraction Period", self.styles['CustomHeader']))
            
            extraction_data = [
                ['Start:', form_data.extraction_start.toString('yyyy-MM-dd HH:mm:ss') if form_data.extraction_start else 'N/A'],
                ['End:', form_data.extraction_end.toString('yyyy-MM-dd HH:mm:ss') if form_data.extraction_end else 'N/A']
            ]
            
            extraction_table = Table(extraction_data, colWidths=[2*inch, 4*inch])
            extraction_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            story.append(extraction_table)
            story.append(Spacer(1, 0.5*inch))
            
            # Footer
            story.append(Paragraph(
                f"Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                self.styles['Normal']
            ))
            
            # Build PDF
            doc.build(story)
            return True
            
        except Exception as e:
            print(f"Error generating time offset PDF: {e}")
            return False
            
    def generate_technician_log(self, form_data: FormData, output_path: Path) -> bool:
        """
        Generate technician log PDF
        
        Args:
            form_data: Form data containing technician information
            output_path: Where to save the PDF
            
        Returns:
            True if successful
        """
        try:
            doc = SimpleDocTemplate(str(output_path), pagesize=letter)
            story = []
            
            # Title
            story.append(Paragraph("Video Evidence Upload Preparation Log", self.styles['CustomTitle']))
            story.append(Spacer(1, 0.2*inch))
            
            # Upload information
            story.append(Paragraph("Upload Details", self.styles['CustomHeader']))
            
            upload_data = [
                ['Prepared for upload on:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                ['Technician Name:', self.tech_name],
                ['Badge Number:', self.badge_number],
                ['', ''],
                ['Occurrence Number:', form_data.occurrence_number],
                ['Business:', form_data.business_name or 'N/A'],
                ['Location:', form_data.location_address]
            ]
            
            upload_table = Table(upload_data, colWidths=[2*inch, 4*inch])
            upload_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('LINEBELOW', (0, 2), (-1, 2), 1, colors.black),
                ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            story.append(upload_table)
            story.append(Spacer(1, 0.5*inch))
            
            # Certification
            story.append(Paragraph("Certification", self.styles['CustomHeader']))
            
            cert_text = (
                f"I, {self.tech_name}, certify that the video evidence "
                f"associated with occurrence number {form_data.occurrence_number} "
                f"was uploaded and processed according to departmental procedures."
            )
            
            story.append(Paragraph(cert_text, self.styles['Normal']))
            
            # Build PDF
            doc.build(story)
            return True
            
        except Exception as e:
            print(f"Error generating technician log PDF: {e}")
            return False
            
    def generate_hash_verification_csv(self, file_results: Dict[str, Dict[str, str]], 
                                     output_path: Path) -> bool:
        """
        Generate CSV file with hash verification results
        
        Args:
            file_results: Results from file copy operation
            output_path: Where to save the CSV
            
        Returns:
            True if successful
        """
        try:
            with open(output_path, 'w', newline='') as csvfile:
                fieldnames = ['Filename', 'Source Path', 'Destination Path', 
                            'Source Hash (SHA-256)', 'Destination Hash (SHA-256)', 
                            'Verification Status']
                            
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for filename, data in file_results.items():
                    writer.writerow({
                        'Filename': filename,
                        'Source Path': data.get('source_path', ''),
                        'Destination Path': data.get('dest_path', ''),
                        'Source Hash (SHA-256)': data.get('source_hash', ''),
                        'Destination Hash (SHA-256)': data.get('dest_hash', ''),
                        'Verification Status': 'PASSED' if data.get('verified', False) else 'FAILED'
                    })
                    
            return True
            
        except Exception as e:
            print(f"Error generating hash verification CSV: {e}")
            return False