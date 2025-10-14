#!/usr/bin/env python3
"""
Success Message Builder - Build formatted success messages for console display

Creates multi-line formatted messages for operation completion suitable for
HTML-formatted console display with color coding.
"""

from typing import Dict, Any, Optional
from core.logger import logger


class SuccessMessageBuilder:
    """
    Build success messages for copy/hash/verify operations

    Returns formatted strings suitable for console.success() methods
    with embedded newlines and formatting.
    """

    def __init__(self):
        """Initialize success message builder"""
        self.name = "SuccessMessageBuilder"
        logger.info(f"{self.name} initialized")

    def build_copy_verify_message(
        self,
        files_copied: int,
        total_size_bytes: int,
        duration_seconds: float,
        hashes_calculated: bool = False,
        verification_passed: Optional[bool] = None,
        performance_stats: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build success message for copy & verify operation

        Args:
            files_copied: Number of files copied
            total_size_bytes: Total size in bytes
            duration_seconds: Operation duration
            hashes_calculated: Whether hashes were calculated
            verification_passed: Whether verification passed (if applicable)
            performance_stats: Optional performance statistics

        Returns:
            Formatted multi-line success message
        """
        lines = [
            f"✓ Copy operation completed successfully!",
            f"  • Files copied: {files_copied:,}",
            f"  • Total size: {self._format_bytes(total_size_bytes)}",
            f"  • Duration: {self._format_duration(duration_seconds)}",
        ]

        if hashes_calculated:
            if verification_passed is True:
                lines.append("  • Hash verification: PASSED ✓")
            elif verification_passed is False:
                lines.append("  • Hash verification: FAILED ✗")
            else:
                lines.append("  • Hashes calculated successfully")

        if performance_stats:
            avg_speed = performance_stats.get('avg_speed_mb_s', 0)
            if avg_speed > 0:
                lines.append(f"  • Average speed: {avg_speed:.1f} MB/s")

            threads = performance_stats.get('threads_used', 0)
            if threads > 1:
                lines.append(f"  • Parallel threads: {threads}")

        return "\n".join(lines)

    def build_hash_calculation_message(
        self,
        files_hashed: int,
        algorithm: str,
        duration_seconds: float,
        total_size_bytes: Optional[int] = None
    ) -> str:
        """
        Build success message for hash calculation operation

        Args:
            files_hashed: Number of files hashed
            algorithm: Hash algorithm used
            duration_seconds: Operation duration
            total_size_bytes: Optional total size processed

        Returns:
            Formatted multi-line success message
        """
        lines = [
            f"✓ Hash calculation completed successfully!",
            f"  • Files hashed: {files_hashed:,}",
            f"  • Algorithm: {algorithm.upper()}",
            f"  • Duration: {self._format_duration(duration_seconds)}",
        ]

        if total_size_bytes:
            lines.append(f"  • Total size: {self._format_bytes(total_size_bytes)}")

        return "\n".join(lines)

    def build_verification_message(
        self,
        files_verified: int,
        files_matched: int,
        files_mismatched: int,
        algorithm: str,
        duration_seconds: float
    ) -> str:
        """
        Build success message for hash verification operation

        Args:
            files_verified: Total files verified
            files_matched: Number of files with matching hashes
            files_mismatched: Number of files with mismatched hashes
            algorithm: Hash algorithm used
            duration_seconds: Operation duration

        Returns:
            Formatted multi-line success message
        """
        verification_status = "PASSED" if files_mismatched == 0 else "FAILED"
        status_symbol = "✓" if files_mismatched == 0 else "✗"

        lines = [
            f"{status_symbol} Verification {verification_status}!",
            f"  • Files verified: {files_verified:,}",
            f"  • Matched: {files_matched:,}",
        ]

        if files_mismatched > 0:
            lines.append(f"  • Mismatched: {files_mismatched:,} ⚠")

        lines.extend([
            f"  • Algorithm: {algorithm.upper()}",
            f"  • Duration: {self._format_duration(duration_seconds)}",
        ])

        return "\n".join(lines)

    def _format_bytes(self, size_bytes: int) -> str:
        """
        Format byte size for human-readable display

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted size string (e.g., "1.5 GB")
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    def _format_duration(self, seconds: float) -> str:
        """
        Format duration for human-readable display

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string (e.g., "5.2s" or "2.5m")
        """
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds / 60:.1f}m"
        else:
            return f"{seconds / 3600:.1f}h"
