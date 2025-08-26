#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Success Message Builder - Pure business logic for building success messages.

This service class contains all the business logic for constructing success messages
from operation results, completely separated from UI concerns. It accepts Result objects
directly and produces SuccessMessageData objects for UI consumption.
"""

from typing import Dict, List, Optional, Union
from pathlib import Path

from core.result_types import (
    Result, FileOperationResult, ReportGenerationResult, ArchiveOperationResult
)
from core.services.success_message_data import (
    SuccessMessageData, QueueOperationData, HashOperationData, BatchOperationData
)


class SuccessMessageBuilder:
    """
    Pure business logic service for building success messages.
    
    This class contains no UI dependencies and focuses solely on the business logic
    of constructing appropriate success messages from operation results.
    """
    
    def build_forensic_success_message(
        self,
        file_result: FileOperationResult,
        report_results: Optional[Dict[str, ReportGenerationResult]] = None,
        zip_result: Optional[ArchiveOperationResult] = None
    ) -> SuccessMessageData:
        """
        Build comprehensive forensic operation success message.
        
        Args:
            file_result: File copying operation results
            report_results: Dictionary of report generation results
            zip_result: ZIP archive creation results
            
        Returns:
            SuccessMessageData object ready for UI display
        """
        summary_lines = []
        
        # File operation summary
        summary_lines.append(f"✓ Copied {file_result.files_processed} files")
        
        # Performance summary
        if file_result.has_performance_data():
            perf_summary = self._build_performance_summary(file_result)
            summary_lines.append(perf_summary)
        
        # Report generation summary
        if report_results:
            report_summary = self._build_report_summary(report_results)
            if report_summary:
                summary_lines.extend(report_summary)
        
        # ZIP archive summary
        if zip_result and zip_result.success:
            zip_summary = self._build_zip_summary(zip_result)
            if zip_summary:
                summary_lines.append(zip_summary)
        
        # Extract output location
        output_location = self._extract_output_location(file_result)
        
        return SuccessMessageData(
            title="Operation Complete!",
            summary_lines=summary_lines,
            output_location=output_location,
            celebration_emoji="✅",
            performance_data=self._extract_performance_dict(file_result),
            raw_data={
                'file_result': file_result,
                'report_results': report_results,
                'zip_result': zip_result
            }
        )
    
    def build_queue_save_success_message(
        self, 
        queue_data: QueueOperationData
    ) -> SuccessMessageData:
        """
        Build queue save success message.
        
        Args:
            queue_data: Queue operation data
            
        Returns:
            SuccessMessageData for queue save success
        """
        summary_lines = [
            f"✓ Saved {queue_data.job_count} jobs to queue file",
            f"📄 File size: {queue_data.get_file_size_display()}",
            f"📁 Location: {queue_data.file_path.parent}",
            f"📝 Filename: {queue_data.file_path.name}"
        ]
        
        if queue_data.duration_seconds > 0:
            summary_lines.append(f"⏱️ Save time: {queue_data.duration_seconds:.2f} seconds")
        
        return SuccessMessageData(
            title="Queue Saved Successfully!",
            summary_lines=summary_lines,
            output_location=str(queue_data.file_path),
            celebration_emoji="💾",
            raw_data={'queue_data': queue_data}
        )
    
    def build_queue_load_success_message(
        self,
        queue_data: QueueOperationData
    ) -> SuccessMessageData:
        """
        Build queue load success message.
        
        Args:
            queue_data: Queue operation data
            
        Returns:
            SuccessMessageData for queue load success
        """
        summary_lines = [
            f"✓ Loaded {queue_data.job_count} jobs from queue file",
            f"📄 File size: {queue_data.get_file_size_display()}"
        ]
        
        if queue_data.duplicate_jobs_skipped > 0:
            summary_lines.append(f"⚠️ Skipped {queue_data.duplicate_jobs_skipped} duplicate jobs")
        
        if queue_data.duration_seconds > 0:
            summary_lines.append(f"⏱️ Load time: {queue_data.duration_seconds:.2f} seconds")
        
        return SuccessMessageData(
            title="Queue Loaded Successfully!",
            summary_lines=summary_lines,
            output_location="Jobs added to current queue",
            celebration_emoji="📂",
            raw_data={'queue_data': queue_data}
        )
    
    def build_batch_success_message(
        self,
        batch_data: BatchOperationData
    ) -> SuccessMessageData:
        """
        Build batch processing success message.
        
        Args:
            batch_data: Batch operation results
            
        Returns:
            SuccessMessageData for batch completion
        """
        summary_lines = [
            f"✓ Total jobs: {batch_data.total_jobs}",
            f"✓ Successful: {batch_data.successful_jobs}"
        ]
        
        if batch_data.failed_jobs > 0:
            summary_lines.append(f"✗ Failed: {batch_data.failed_jobs}")
        
        success_rate = batch_data.get_success_rate()
        summary_lines.append(f"📊 Success Rate: {success_rate:.1f}%")
        
        if batch_data.processing_time_seconds > 0:
            summary_lines.append(f"⏱️ Total time: {batch_data.processing_time_seconds:.1f} seconds")
        
        # Choose appropriate emoji and title based on success rate
        if batch_data.is_complete_success:
            emoji = "🎉"
            title = "Batch Processing Complete!"
        elif success_rate >= 80:
            emoji = "✅"
            title = "Batch Processing Complete!"
        else:
            emoji = "⚠️"
            title = "Batch Processing Finished with Issues"
        
        return SuccessMessageData(
            title=title,
            summary_lines=summary_lines,
            celebration_emoji=emoji,
            raw_data={'batch_data': batch_data}
        )
    
    def build_hash_verification_success_message(
        self,
        hash_data: HashOperationData
    ) -> SuccessMessageData:
        """
        Build hash verification success message.
        
        Args:
            hash_data: Hash operation results
            
        Returns:
            SuccessMessageData for hash verification success
        """
        summary_lines = [
            f"✓ Verified {hash_data.files_verified} files",
            f"🔒 Algorithm: {hash_data.hash_algorithm}",
            f"⏱️ Verification time: {hash_data.verification_time_seconds:.1f} seconds"
        ]
        
        if hash_data.failed_verifications > 0:
            success_rate = hash_data.get_success_rate()
            summary_lines.append(f"⚠️ Failed verifications: {hash_data.failed_verifications}")
            summary_lines.append(f"📊 Success rate: {success_rate:.1f}%")
        
        if hash_data.csv_file_path:
            summary_lines.append(f"📄 CSV report: {hash_data.csv_file_path.name}")
        
        return SuccessMessageData(
            title="Hash Verification Complete!",
            summary_lines=summary_lines,
            output_location=str(hash_data.csv_file_path) if hash_data.csv_file_path else None,
            celebration_emoji="🔒",
            raw_data={'hash_data': hash_data}
        )
    
    # Private helper methods
    
    def _build_performance_summary(self, file_result: FileOperationResult) -> str:
        """Build performance summary from file operation result."""
        if not file_result.has_performance_data():
            return ""
        
        lines = [
            f"Files: {file_result.files_processed}",
            f"Size: {file_result.bytes_processed / (1024 * 1024):.1f} MB",
            f"Time: {file_result.duration_seconds:.1f} seconds",
            f"Average Speed: {file_result.average_speed_mbps:.1f} MB/s"
        ]
        
        # Add peak speed if available
        if hasattr(file_result, 'peak_speed_mbps') and file_result.peak_speed_mbps:
            lines.append(f"Peak Speed: {file_result.peak_speed_mbps:.1f} MB/s")
        
        # Add mode if available
        if hasattr(file_result, 'optimization_mode'):
            lines.append(f"Mode: {file_result.optimization_mode}")
        
        return "📊 Performance Summary:\n" + "\n".join(lines)
    
    def _build_report_summary(
        self, 
        report_results: Dict[str, ReportGenerationResult]
    ) -> List[str]:
        """Build report generation summary from results."""
        successful_reports = []
        
        for report_type, result in report_results.items():
            if result.success:
                # Get file size in KB
                file_size_kb = result.file_size_bytes / 1024 if result.file_size_bytes > 0 else 0
                report_name = self._get_report_display_name(report_type)
                
                if file_size_kb > 0:
                    successful_reports.append(f"  • {report_name} ({file_size_kb:.0f} KB)")
                else:
                    successful_reports.append(f"  • {report_name}")
        
        if successful_reports:
            return [f"✓ Generated {len(successful_reports)} reports"] + successful_reports
        
        return []
    
    def _build_zip_summary(self, zip_result: ArchiveOperationResult) -> str:
        """Build ZIP archive summary from results."""
        if not zip_result.success or not hasattr(zip_result, 'archives_created'):
            return ""
        
        archive_count = len(zip_result.archives_created) if zip_result.archives_created else 1
        total_size_mb = zip_result.total_compressed_size / (1024 * 1024) if zip_result.total_compressed_size else 0
        
        if total_size_mb > 0:
            return f"✓ Created {archive_count} ZIP archive(s) ({total_size_mb:.1f} MB)"
        else:
            return f"✓ Created {archive_count} ZIP archive(s)"
    
    def _extract_output_location(self, file_result: FileOperationResult) -> Optional[str]:
        """Extract output location from file operation result."""
        if hasattr(file_result, 'output_directory') and file_result.output_directory:
            return str(file_result.output_directory)
        
        # Fallback: try to extract from file paths
        if hasattr(file_result, 'value') and file_result.value:
            if isinstance(file_result.value, dict):
                for path_data in file_result.value.values():
                    if isinstance(path_data, dict) and 'dest_path' in path_data:
                        return str(Path(path_data['dest_path']).parent)
        
        return None
    
    def _extract_performance_dict(self, file_result: FileOperationResult) -> Dict[str, any]:
        """Extract performance data as dictionary for compatibility."""
        if not file_result.has_performance_data():
            return {}
        
        return {
            'files_processed': file_result.files_processed,
            'bytes_processed': file_result.bytes_processed,
            'total_time_seconds': file_result.duration_seconds,
            'average_speed_mbps': file_result.average_speed_mbps,
            'total_size_mb': file_result.bytes_processed / (1024 * 1024),
            'peak_speed_mbps': getattr(file_result, 'peak_speed_mbps', file_result.average_speed_mbps),
            'mode': getattr(file_result, 'optimization_mode', 'Balanced')
        }
    
    def _get_report_display_name(self, report_type: str) -> str:
        """Convert report type to display-friendly name."""
        display_names = {
            'time_offset': 'Time Offset Report',
            'technician_log': 'Technician Log',
            'hash_csv': 'Hash Verification CSV',
            'upload_log': 'Upload Log',
            'processing_summary': 'Processing Summary'
        }
        
        return display_names.get(report_type, report_type.replace('_', ' ').title())