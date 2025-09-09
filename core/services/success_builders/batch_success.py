#!/usr/bin/env python3
"""
Success message builder for batch processing operations.
This module is owned by the batch tab/plugin.
"""

from typing import Dict, List, Optional
from pathlib import Path
import logging

from core.services.success_message_data import (
    SuccessMessageData, 
    QueueOperationData, 
    BatchOperationData,
    EnhancedBatchOperationData
)


class BatchSuccessBuilder:
    """Builds success messages for batch processing operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
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
    
    def build_enhanced_batch_success_message(
        self,
        enhanced_batch_data: EnhancedBatchOperationData
    ) -> SuccessMessageData:
        """
        Build enhanced batch processing success message with detailed statistics.
        
        Args:
            enhanced_batch_data: Enhanced batch operation results with detailed metrics
            
        Returns:
            SuccessMessageData for enhanced batch completion display
        """
        summary_lines = []
        
        # Overall statistics with professional formatting
        summary_lines.append(f"✓ Processed {enhanced_batch_data.total_jobs} jobs total")
        summary_lines.append(f"✓ {enhanced_batch_data.successful_jobs} successful, {enhanced_batch_data.failed_jobs} failed")
        
        # File processing summary
        if enhanced_batch_data.total_files_processed > 0:
            total_gb = enhanced_batch_data.get_total_size_gb()
            if total_gb >= 1.0:
                summary_lines.append(f"✓ Processed {enhanced_batch_data.total_files_processed} files ({total_gb:.1f} GB)")
            else:
                total_mb = enhanced_batch_data.total_bytes_processed / (1024**2)
                summary_lines.append(f"✓ Processed {enhanced_batch_data.total_files_processed} files ({total_mb:.1f} MB)")
        
        # Performance metrics
        if enhanced_batch_data.processing_time_seconds > 0:
            summary_lines.append("")  # Add spacing for readability
            summary_lines.append("📊 Performance Metrics:")
            
            processing_minutes = enhanced_batch_data.get_processing_time_minutes()
            if processing_minutes >= 1.0:
                summary_lines.append(f"Time: {processing_minutes:.1f} minutes total processing")
            else:
                summary_lines.append(f"Time: {enhanced_batch_data.processing_time_seconds:.1f} seconds total processing")
            
            if enhanced_batch_data.aggregate_speed_mbps > 0:
                summary_lines.append(f"Average Speed: {enhanced_batch_data.aggregate_speed_mbps:.1f} MB/s overall")
            
            if enhanced_batch_data.peak_speed_mbps > 0 and enhanced_batch_data.peak_speed_job_name:
                summary_lines.append(f"Peak Speed: {enhanced_batch_data.peak_speed_mbps:.1f} MB/s ({enhanced_batch_data.peak_speed_job_name})")
        
        # Aggregate report summary
        if enhanced_batch_data.total_reports_generated > 0:
            summary_lines.append("")  # Spacing
            summary_lines.append(f"✓ Generated {enhanced_batch_data.total_reports_generated} reports across all jobs")
            
            for report_type, count in enhanced_batch_data.report_breakdown.items():
                display_name = self._get_report_display_name(report_type)
                summary_lines.append(f"  • {count} {display_name}{'s' if count > 1 else ''}")
            
            if enhanced_batch_data.total_report_size_bytes > 0:
                total_report_mb = enhanced_batch_data.get_total_report_size_mb()
                summary_lines.append(f"  • Total report size: {total_report_mb:.1f} MB")
        
        # ZIP summary
        if enhanced_batch_data.total_zip_archives > 0:
            total_zip_gb = enhanced_batch_data.get_total_zip_size_gb()
            if total_zip_gb >= 1.0:
                summary_lines.append(f"✓ Created {enhanced_batch_data.total_zip_archives} ZIP archives ({total_zip_gb:.1f} GB total)")
            else:
                total_zip_mb = enhanced_batch_data.total_zip_size_bytes / (1024**2)
                summary_lines.append(f"✓ Created {enhanced_batch_data.total_zip_archives} ZIP archives ({total_zip_mb:.1f} MB total)")
        
        # Success rate and failed job details
        success_rate = enhanced_batch_data.get_success_rate()
        summary_lines.append("")  # Spacing
        summary_lines.append(f"📊 Success Rate: {success_rate:.1f}%")
        
        # Show failed job names if any
        if enhanced_batch_data.failed_job_summaries:
            summary_lines.append("")  # Spacing
            for failure in enhanced_batch_data.failed_job_summaries[:3]:  # Limit to first 3
                summary_lines.append(f"⚠️ {failure}")
            if len(enhanced_batch_data.failed_job_summaries) > 3:
                remaining = len(enhanced_batch_data.failed_job_summaries) - 3
                summary_lines.append(f"⚠️ ...and {remaining} more failure{'s' if remaining > 1 else ''}")
        
        # Choose appropriate professional emoji and title
        if success_rate == 100:
            emoji = "✅"
            title = "Batch Processing Complete!"
        elif success_rate >= 90:
            emoji = "⚠️"
            title = "Batch Processing Complete with Minor Issues"
        elif success_rate >= 70:
            emoji = "⚠️"
            title = "Batch Processing Complete with Some Issues"
        else:
            emoji = "❌"
            title = "Batch Processing Complete with Significant Issues"
        
        # Output location
        output_location = None
        if enhanced_batch_data.batch_output_directories:
            if len(enhanced_batch_data.batch_output_directories) == 1:
                output_location = str(enhanced_batch_data.batch_output_directories[0])
            else:
                output_location = f"Multiple locations ({len(enhanced_batch_data.batch_output_directories)} jobs)"
        
        return SuccessMessageData(
            title=title,
            summary_lines=summary_lines,
            output_location=output_location,
            celebration_emoji=emoji,
            raw_data={'enhanced_batch_data': enhanced_batch_data}
        )
    
    def _get_report_display_name(self, report_type: str) -> str:
        """Convert report type key to display name."""
        report_names = {
            'technician_log': 'Technician Log',
            'time_offset': 'Time Offset Sheet',
            'hash_csv': 'Hash CSV Report',
            'media_analysis': 'Media Analysis Report',
            'exiftool': 'ExifTool Report'
        }
        return report_names.get(report_type, report_type.replace('_', ' ').title())