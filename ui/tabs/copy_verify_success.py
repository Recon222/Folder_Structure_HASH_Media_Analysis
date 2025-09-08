#!/usr/bin/env python3
"""
Success message builder for copy & verify operations.
This module is owned by the copy & verify tab/plugin.
"""

from typing import Optional
from pathlib import Path
from core.services.success_message_data import SuccessMessageData, CopyVerifyOperationData


class CopyVerifySuccessBuilder:
    """Builds success messages for copy & verify operations"""
    
    @staticmethod
    def build_copy_verify_success_message(
        copy_data: CopyVerifyOperationData
    ) -> SuccessMessageData:
        """
        Build copy & verify operation success message.
        
        Args:
            copy_data: Copy & verify operation results
            
        Returns:
            SuccessMessageData for copy & verify success display
        """
        summary_lines = []
        
        # Main operation summary
        if copy_data.files_failed_to_copy > 0:
            total_attempted = copy_data.files_copied + copy_data.files_failed_to_copy
            summary_lines.append(f"⚠️ Copied {copy_data.files_copied}/{total_attempted} files ({copy_data.get_size_display()})")
            summary_lines.append(f"❌ {copy_data.files_failed_to_copy} files failed to copy")
        else:
            summary_lines.append(f"✅ Successfully copied {copy_data.files_copied} files ({copy_data.get_size_display()})")
        
        # Hash verification summary
        if copy_data.hash_verification_enabled:
            summary_lines.append("")  # Add spacing
            if copy_data.files_with_hash_mismatch > 0:
                summary_lines.append(f"⚠️ Hash Verification Issues:")
                summary_lines.append(f"  • {copy_data.files_with_hash_mismatch} files had hash mismatches")
                verified_count = copy_data.files_copied - copy_data.files_with_hash_mismatch
                if verified_count > 0:
                    summary_lines.append(f"  • {verified_count} files verified successfully")
            else:
                summary_lines.append(f"✅ All file hashes verified successfully")
        
        # Performance summary - show if we have any timing data at all
        if copy_data.operation_time_seconds > 0.001 and copy_data.bytes_processed > 0:
            summary_lines.append("")  # Add spacing
            summary_lines.append("📊 Performance Summary:")
            
            # Show time with appropriate precision
            if copy_data.operation_time_seconds < 1:
                summary_lines.append(f"  • Time: {copy_data.operation_time_seconds:.3f} seconds")
            else:
                summary_lines.append(f"  • Time: {copy_data.operation_time_seconds:.1f} seconds")
            
            if copy_data.average_speed_mbps > 0:
                summary_lines.append(f"  • Average speed: {copy_data.average_speed_mbps:.1f} MB/s")
            
            if copy_data.peak_speed_mbps > 0 and copy_data.peak_speed_mbps != copy_data.average_speed_mbps:
                summary_lines.append(f"  • Peak speed: {copy_data.peak_speed_mbps:.1f} MB/s")
        
        # CSV report info
        if copy_data.csv_generated and copy_data.csv_path:
            summary_lines.append("")  # Add spacing
            summary_lines.append(f"📄 CSV report saved: {copy_data.csv_path.name}")
        
        # Operation details
        if copy_data.preserve_structure:
            summary_lines.append("")  # Add spacing
            summary_lines.append("ℹ️ Folder structure preserved during copy")
        
        # Determine title and emoji based on results
        if copy_data.has_issues:
            if copy_data.files_failed_to_copy > 0:
                title = "Copy Operation Completed with Errors"
                emoji = "⚠️"
            else:
                title = "Copy Complete - Hash Verification Issues"
                emoji = "⚠️"
        else:
            title = "Copy & Verify Complete!"
            emoji = "✅"
        
        # Build performance data dictionary for compatibility
        perf_data = {}
        if copy_data.operation_time_seconds > 0:
            perf_data = {
                'files_processed': copy_data.files_copied,
                'bytes_processed': copy_data.bytes_processed,
                'total_time_seconds': copy_data.operation_time_seconds,
                'average_speed_mbps': copy_data.average_speed_mbps,
                'peak_speed_mbps': copy_data.peak_speed_mbps,
                'total_size_mb': copy_data.bytes_processed / (1024 * 1024)
            }
        
        return SuccessMessageData(
            title=title,
            summary_lines=summary_lines,
            output_location=str(copy_data.csv_path.parent) if copy_data.csv_path else None,
            celebration_emoji=emoji,
            performance_data=perf_data,
            raw_data={'copy_data': copy_data}
        )
    
    @staticmethod
    def build_csv_export_success(
        file_path: Path, 
        record_count: int
    ) -> SuccessMessageData:
        """
        Create success data for CSV export operation.
        
        Args:
            file_path: Path where CSV was saved
            record_count: Number of records exported
            
        Returns:
            SuccessMessageData for CSV export success
        """
        summary_lines = [
            f"✓ Exported {record_count} records to CSV",
            f"📁 Location: {file_path.parent}",
            f"📄 File: {file_path.name}"
        ]
        
        # Add file size if available
        try:
            if file_path.exists():
                size_bytes = file_path.stat().st_size
                if size_bytes < 1024:
                    size_str = f"{size_bytes} bytes"
                elif size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                summary_lines.append(f"💾 Size: {size_str}")
        except:
            pass  # Ignore if we can't get file size
        
        return SuccessMessageData(
            title="CSV Export Complete!",
            summary_lines=summary_lines,
            celebration_emoji="📊",
            output_location=str(file_path.parent),
            raw_data={
                'operation': 'csv_export',
                'file_path': str(file_path),
                'record_count': record_count
            }
        )