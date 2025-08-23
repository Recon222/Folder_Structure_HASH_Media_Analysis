#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hash report generation - CSV exports for hash and verification results
"""

import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from core.hash_operations import HashResult, VerificationResult
from core.logger import logger


class HashReportGenerator:
    """Generates CSV reports for hash operations"""
    
    def __init__(self):
        """Initialize the report generator"""
        pass
        
    def generate_single_hash_csv(self, 
                                results: List[HashResult], 
                                output_path: Path, 
                                algorithm: str,
                                include_metadata: bool = True) -> bool:
        """Generate CSV report for single hash operation results
        
        Args:
            results: List of HashResult objects
            output_path: Path where CSV should be saved
            algorithm: Hash algorithm used
            include_metadata: Whether to include metadata header
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'File Path',
                    'Relative Path', 
                    'File Size (bytes)',
                    f'Hash ({algorithm.upper()})',
                    'Processing Time (s)',
                    'Speed (MB/s)',
                    'Status',
                    'Error Message'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write metadata header if requested
                if include_metadata:
                    metadata_writer = csv.writer(csvfile)
                    metadata_writer.writerow(['# Hash Report Metadata'])
                    metadata_writer.writerow([f'# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
                    metadata_writer.writerow([f'# Algorithm: {algorithm.upper()}'])
                    metadata_writer.writerow([f'# Total Files: {len(results)}'])
                    successful_files = len([r for r in results if r.success])
                    metadata_writer.writerow([f'# Successful: {successful_files}'])
                    metadata_writer.writerow([f'# Failed: {len(results) - successful_files}'])
                    metadata_writer.writerow([''])  # Empty line before data
                
                # Write header
                writer.writeheader()
                
                # Write data rows
                for result in results:
                    writer.writerow({
                        'File Path': str(result.file_path),
                        'Relative Path': str(result.relative_path),
                        'File Size (bytes)': result.file_size,
                        f'Hash ({algorithm.upper()})': result.hash_value if result.success else '',
                        'Processing Time (s)': f"{result.duration:.3f}",
                        'Speed (MB/s)': f"{result.speed_mbps:.2f}" if result.success else '',
                        'Status': 'SUCCESS' if result.success else 'FAILED',
                        'Error Message': result.error or ''
                    })
            
            logger.info(f"Generated single hash CSV report: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate single hash CSV: {e}")
            return False
    
    def generate_verification_csv(self, 
                                verification_results: List[VerificationResult], 
                                output_path: Path, 
                                algorithm: str,
                                include_metadata: bool = True) -> bool:
        """Generate CSV report for verification operation results
        
        Args:
            verification_results: List of VerificationResult objects
            output_path: Path where CSV should be saved
            algorithm: Hash algorithm used
            include_metadata: Whether to include metadata header
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'Source File Path',
                    'Target File Path',
                    'Source Relative Path',
                    'Target Relative Path',
                    'Source File Size (bytes)',
                    'Target File Size (bytes)',
                    f'Source Hash ({algorithm.upper()})',
                    f'Target Hash ({algorithm.upper()})',
                    'Verification Status',
                    'Match Type',
                    'Notes'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write metadata header if requested
                if include_metadata:
                    metadata_writer = csv.writer(csvfile)
                    metadata_writer.writerow(['# Hash Verification Report Metadata'])
                    metadata_writer.writerow([f'# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
                    metadata_writer.writerow([f'# Algorithm: {algorithm.upper()}'])
                    metadata_writer.writerow([f'# Total Comparisons: {len(verification_results)}'])
                    matches = len([v for v in verification_results if v.match])
                    metadata_writer.writerow([f'# Matches: {matches}'])
                    metadata_writer.writerow([f'# Mismatches: {len(verification_results) - matches}'])
                    metadata_writer.writerow([''])  # Empty line before data
                
                # Write header
                writer.writeheader()
                
                # Write data rows
                for result in verification_results:
                    # Source information
                    source_path = str(result.source_result.file_path) if result.source_result else ''
                    source_relative = str(result.source_result.relative_path) if result.source_result else ''
                    source_size = result.source_result.file_size if result.source_result else 0
                    source_hash = result.source_result.hash_value if result.source_result and result.source_result.success else ''
                    
                    # Target information
                    target_path = str(result.target_result.file_path) if result.target_result else ''
                    target_relative = str(result.target_result.relative_path) if result.target_result else ''
                    target_size = result.target_result.file_size if result.target_result else 0
                    target_hash = result.target_result.hash_value if result.target_result and result.target_result.success else ''
                    
                    writer.writerow({
                        'Source File Path': source_path,
                        'Target File Path': target_path,
                        'Source Relative Path': source_relative,
                        'Target Relative Path': target_relative,
                        'Source File Size (bytes)': source_size,
                        'Target File Size (bytes)': target_size,
                        f'Source Hash ({algorithm.upper()})': source_hash,
                        f'Target Hash ({algorithm.upper()})': target_hash,
                        'Verification Status': 'MATCH' if result.match else 'MISMATCH',
                        'Match Type': result.comparison_type,
                        'Notes': result.notes
                    })
            
            logger.info(f"Generated verification CSV report: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate verification CSV: {e}")
            return False
    
    def generate_forensic_compatible_csv(self,
                                       verification_results: List[VerificationResult],
                                       output_path: Path,
                                       algorithm: str) -> bool:
        """Generate CSV report compatible with existing forensic hash format
        
        This generates a CSV in the same format as the existing hash verification
        CSV from the forensic workflow, for compatibility.
        
        Args:
            verification_results: List of VerificationResult objects
            output_path: Path where CSV should be saved
            algorithm: Hash algorithm used
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                # Use the same fieldnames as the existing forensic CSV
                fieldnames = [
                    'Filename', 
                    'Source Path', 
                    'Destination Path',
                    f'Source Hash ({algorithm.upper()})', 
                    f'Destination Hash ({algorithm.upper()})', 
                    'Verification Status'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                # Write data rows in forensic format
                for result in verification_results:
                    # Use the filename from source result
                    filename = result.source_name if result.source_result else ''
                    source_path = str(result.source_result.file_path) if result.source_result else ''
                    target_path = str(result.target_result.file_path) if result.target_result else ''
                    source_hash = result.source_result.hash_value if result.source_result and result.source_result.success else ''
                    target_hash = result.target_result.hash_value if result.target_result and result.target_result.success else ''
                    
                    writer.writerow({
                        'Filename': filename,
                        'Source Path': source_path,
                        'Destination Path': target_path,
                        f'Source Hash ({algorithm.upper()})': source_hash,
                        f'Destination Hash ({algorithm.upper()})': target_hash,
                        'Verification Status': 'PASSED' if result.match else 'FAILED'
                    })
            
            logger.info(f"Generated forensic-compatible CSV report: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate forensic-compatible CSV: {e}")
            return False
    
    def get_default_filename(self, operation_type: str, algorithm: str) -> str:
        """Get default filename for report
        
        Args:
            operation_type: 'hash' or 'verification'
            algorithm: Hash algorithm used
            
        Returns:
            Default filename string
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if operation_type == 'hash':
            return f"hash_report_{algorithm}_{timestamp}.csv"
        elif operation_type == 'verification':
            return f"verification_report_{algorithm}_{timestamp}.csv"
        else:
            return f"hash_report_{timestamp}.csv"