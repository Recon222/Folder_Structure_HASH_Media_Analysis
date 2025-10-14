"""
Thread Calculator Utility - Centralized CPU-aware thread calculation

This module provides a single source of truth for determining optimal thread counts
based on storage characteristics and CPU core count. Eliminates code duplication
across workers and UI tabs.

Research-validated threading strategies:
- NVMe → NVMe: 2 threads per CPU core, cap at 64 (5-10x speedup)
- HDD → NVMe: 8-16 threads for OS queue optimization (1.2-1.5x speedup)
- SSD → NVMe: 32 threads (2-5x speedup)
- Any → HDD: 1 thread (HDD write bottleneck, critical)
- Single file: 1 thread (no parallelism benefit)

Usage:
    from copy_hash_verify.utils.thread_calculator import ThreadCalculator

    calculator = ThreadCalculator()
    threads = calculator.calculate_optimal_threads(
        source_info=source_storage_info,
        dest_info=dest_storage_info,
        file_count=42
    )

Research Source: https://pkolaczk.github.io/disk-parallelism/
"""

import psutil
from typing import Optional

from copy_hash_verify.core.storage_detector import StorageInfo, DriveType
from core.logger import logger


class ThreadCalculator:
    """
    Centralized thread calculation utility

    Provides CPU-aware thread count calculation based on storage characteristics
    and operation type. Single source of truth for all workers and UI tabs.
    """

    def __init__(self, cpu_threads: Optional[int] = None):
        """
        Initialize ThreadCalculator with CPU core detection

        Args:
            cpu_threads: Optional override for CPU thread count (for testing)
        """
        self.cpu_threads = cpu_threads or psutil.cpu_count(logical=True) or 16
        logger.debug(f"ThreadCalculator initialized with {self.cpu_threads} CPU threads")

    def calculate_optimal_threads(
        self,
        source_info: Optional[StorageInfo] = None,
        dest_info: Optional[StorageInfo] = None,
        file_count: int = 1,
        operation_type: str = "copy"
    ) -> int:
        """
        Calculate optimal thread count for a storage operation

        Args:
            source_info: Source storage information (None for hash-only operations)
            dest_info: Destination storage information (None for hash-only operations)
            file_count: Number of files to process
            operation_type: "copy" or "hash" operation type

        Returns:
            Optimal thread count (1 for sequential, >1 for parallel)
        """
        # Rule 1: Single file → Sequential (no parallelism benefit)
        if file_count == 1:
            logger.debug("Single file - sequential operation")
            return 1

        # Hash-only operations (no destination)
        if operation_type == "hash" and dest_info is None:
            return self._calculate_hash_threads(source_info, file_count)

        # Copy operations (source and destination)
        if operation_type == "copy":
            return self._calculate_copy_threads(source_info, dest_info, file_count)

        # Fallback: Sequential for unknown operations
        logger.warning(f"Unknown operation type: {operation_type}, using sequential")
        return 1

    def _calculate_hash_threads(
        self,
        source_info: Optional[StorageInfo],
        file_count: int
    ) -> int:
        """
        Calculate optimal threads for hash-only operations

        Args:
            source_info: Source storage information
            file_count: Number of files to hash

        Returns:
            Optimal thread count for hashing
        """
        if not source_info:
            logger.debug("No storage info - using 4 threads for hash operations")
            return min(4, self.cpu_threads)

        # Rule: HDD source → Limited parallelism (OS queue optimization)
        if source_info.drive_type in (DriveType.HDD, DriveType.EXTERNAL_HDD):
            threads = 8  # Optimal for HDD read queue optimization
            logger.debug(
                f"HDD source - using {threads} threads for hash operations "
                "(OS-level queue optimization)"
            )
            return threads

        # Rule: NVMe source → Maximum parallelism
        if source_info.drive_type == DriveType.NVME:
            threads = min(self.cpu_threads * 2, 64)
            threads = max(threads, 2)  # Minimum 2 for parallel
            logger.debug(
                f"NVMe source - using {threads} threads for hash operations "
                f"({self.cpu_threads} CPU threads × 2, cap 64)"
            )
            return threads

        # Rule: SSD source → High parallelism (2x CPU cores, no artificial cap)
        if source_info.drive_type in (DriveType.SSD, DriveType.EXTERNAL_SSD):
            threads = min(self.cpu_threads * 2, 64)  # Match NVMe cap for consistency
            threads = max(threads, 2)  # Minimum 2 for parallel
            logger.debug(
                f"SSD source - using {threads} threads for hash operations "
                f"({self.cpu_threads} CPU threads × 2, cap 64)"
            )
            return threads

        # Unknown storage → Conservative parallelism
        threads = min(4, self.cpu_threads)
        logger.debug(f"Unknown storage - using {threads} threads for hash operations")
        return threads

    def _calculate_copy_threads(
        self,
        source_info: Optional[StorageInfo],
        dest_info: Optional[StorageInfo],
        file_count: int
    ) -> int:
        """
        Calculate optimal threads for copy operations

        Research-validated threading strategy:
        - NVMe → NVMe: 2 threads per CPU core, cap at 64 (5-10x speedup)
        - HDD → NVMe: 8-16 threads for OS queue optimization (1.2-1.5x speedup)
        - SSD → NVMe: 32 threads (2-5x speedup)
        - Any → HDD: 1 thread (HDD write bottleneck)

        Args:
            source_info: Source storage information
            dest_info: Destination storage information
            file_count: Number of files to copy

        Returns:
            Optimal thread count for copying
        """
        # Require both source and dest for copy operations
        if not source_info or not dest_info:
            logger.warning("Missing storage info for copy operation - using sequential")
            return 1

        # Rule 1: HDD destination → Always sequential (write bottleneck, critical)
        if dest_info.drive_type in (DriveType.HDD, DriveType.EXTERNAL_HDD):
            logger.debug("Destination is HDD - sequential to avoid write seek penalty")
            return 1

        # Rule 2: HDD source → Fast destination (limited parallelism for queue optimization)
        if source_info.drive_type in (DriveType.HDD, DriveType.EXTERNAL_HDD):
            if dest_info.drive_type in (DriveType.SSD, DriveType.NVME, DriveType.EXTERNAL_SSD):
                # Research: 8-16 threads help OS reorder HDD reads, NVMe handles writes easily
                # Conservative 8 for large files (forensic workload), up to 16 for small files
                threads = 8
                logger.debug(
                    f"HDD source → {dest_info.drive_type.value} destination - "
                    f"using {threads} threads for OS-level queue optimization (1.2-1.5x speedup)"
                )
                return threads
            else:
                # HDD → unknown destination, stay safe
                logger.debug("HDD source with unknown destination - sequential")
                return 1

        # Rule 3: NVMe → NVMe (maximum parallelism, research shows 64 threads optimal)
        if source_info.drive_type == DriveType.NVME and dest_info.drive_type == DriveType.NVME:
            # 2 threads per CPU core, cap at 64 (research-validated)
            threads = min(self.cpu_threads * 2, 64)
            threads = max(threads, 2)  # Minimum 2 for parallel
            logger.debug(
                f"NVMe → NVMe - using {threads} threads "
                f"({self.cpu_threads} CPU threads × 2, cap 64) for maximum parallelism (5-10x speedup)"
            )
            return threads

        # Rule 4: SSD/NVMe → SSD/NVMe (high parallelism)
        if source_info.drive_type in (DriveType.SSD, DriveType.NVME, DriveType.EXTERNAL_SSD):
            if dest_info.drive_type in (DriveType.SSD, DriveType.NVME, DriveType.EXTERNAL_SSD):
                # One or both is SSD (not both NVMe) - use 32 threads
                if DriveType.NVME in (source_info.drive_type, dest_info.drive_type):
                    # At least one NVMe - use 32 threads
                    threads = 32
                else:
                    # SSD → SSD - conservative 16 threads
                    threads = 16
                threads = max(threads, 2)  # Minimum 2 for parallel
                logger.debug(
                    f"{source_info.drive_type.value} → {dest_info.drive_type.value} - "
                    f"using {threads} threads (2-5x speedup)"
                )
                return threads

        # Rule 5: Unknown/unsupported combination → Sequential (safe fallback)
        logger.debug("Unknown or unsupported storage combination - sequential for safety")
        return 1

    def get_ui_display_text(
        self,
        source_info: Optional[StorageInfo],
        dest_info: Optional[StorageInfo],
        file_count: int,
        operation_type: str = "copy"
    ) -> str:
        """
        Generate user-friendly display text for thread count decision

        Args:
            source_info: Source storage information
            dest_info: Destination storage information
            file_count: Number of files
            operation_type: "copy" or "hash"

        Returns:
            Human-readable explanation of thread count decision
        """
        threads = self.calculate_optimal_threads(
            source_info=source_info,
            dest_info=dest_info,
            file_count=file_count,
            operation_type=operation_type
        )

        if threads == 1:
            if file_count == 1:
                return f"Sequential (1 thread) - Single file"
            elif dest_info and dest_info.drive_type in (DriveType.HDD, DriveType.EXTERNAL_HDD):
                return f"Sequential (1 thread) - HDD destination"
            else:
                return f"Sequential (1 thread) - Safe fallback"
        else:
            if operation_type == "hash":
                if source_info and source_info.drive_type == DriveType.NVME:
                    return f"Parallel ({threads} threads) - NVMe optimized"
                elif source_info and source_info.drive_type in (DriveType.HDD, DriveType.EXTERNAL_HDD):
                    return f"Parallel ({threads} threads) - HDD queue optimization"
                else:
                    return f"Parallel ({threads} threads) - SSD optimized"
            else:  # copy
                if (source_info and source_info.drive_type == DriveType.NVME and
                    dest_info and dest_info.drive_type == DriveType.NVME):
                    return f"Parallel ({threads} threads) - NVMe->NVMe max performance"
                elif (source_info and source_info.drive_type in (DriveType.HDD, DriveType.EXTERNAL_HDD)):
                    return f"Parallel ({threads} threads) - HDD->Fast (queue optimization)"
                else:
                    return f"Parallel ({threads} threads) - SSD/NVMe optimized"
