#!/usr/bin/env python3
"""
Robust Storage Detection System - Multi-method approach for reliable SSD/HDD detection

This module provides centralized storage type detection for optimal performance tuning
across all copy_hash_verify operations. It uses a layered detection strategy with
multiple fallback methods to ensure reliability across different Windows configurations.

Detection Methods (in priority order):
1. Windows Seek Penalty API (Most reliable, no admin required)
2. Performance Heuristics (Fast fallback with actual I/O testing)
3. WMI MSFT_PhysicalDisk (Backup for internal drives)
4. Conservative Fallback (Always works, assumes slowest device)

Usage:
    detector = StorageDetector()
    info = detector.analyze_path(Path("D:/evidence"))

    # Use threading recommendation
    if info.recommended_threads > 1:
        use_parallel_processing(threads=info.recommended_threads)
    else:
        use_sequential_processing()
"""

import os
import sys
import time
import platform
import ctypes
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from core.logger import logger
from core.result_types import Result
from core.exceptions import FSAError


class DriveType(Enum):
    """Drive type classification"""
    UNKNOWN = "unknown"
    HDD = "hdd"
    SSD = "ssd"
    NVME = "nvme"
    EXTERNAL_HDD = "external_hdd"
    EXTERNAL_SSD = "external_ssd"
    NETWORK = "network"


class BusType(Enum):
    """Storage bus type classification"""
    UNKNOWN = 0
    SCSI = 1
    ATAPI = 2
    ATA = 3
    IEEE1394 = 4
    SSA = 5
    FIBRE_CHANNEL = 6
    USB = 7
    RAID = 8
    ISCSI = 9
    SAS = 10
    SATA = 11
    SD = 12
    MMC = 13
    VIRTUAL = 14
    FILE_BACKED_VIRTUAL = 15
    SPACES = 16
    NVME = 17
    SCM = 18  # Storage Class Memory


@dataclass
class StorageInfo:
    """
    Complete storage characteristics for a given path

    Attributes:
        drive_type: Classification of storage device
        bus_type: Connection interface type
        is_ssd: True if SSD, False if HDD, None if unknown
        is_removable: True if external/removable drive
        recommended_threads: Optimal thread count for I/O operations
        confidence: Detection confidence (0.0-1.0)
        detection_method: Which method successfully detected storage type
        drive_letter: Windows drive letter (e.g., "C:")
        performance_class: Expected performance tier (1-5, higher is faster)
    """
    drive_type: DriveType
    bus_type: BusType
    is_ssd: Optional[bool]
    is_removable: bool
    recommended_threads: int
    confidence: float
    detection_method: str
    drive_letter: str
    performance_class: int

    def __str__(self) -> str:
        """Human-readable string representation"""
        ssd_str = "SSD" if self.is_ssd else "HDD" if self.is_ssd is False else "Unknown"
        removable_str = " (External)" if self.is_removable else ""
        return (f"{ssd_str}{removable_str} on {self.drive_letter} "
                f"[{self.bus_type.name}] → {self.recommended_threads} threads "
                f"(confidence: {self.confidence:.0%})")


class StorageDetector:
    """
    Robust multi-method storage detection system

    Provides reliable SSD/HDD detection across different Windows configurations
    with graceful fallback for external drives, network shares, and edge cases.
    """

    # Threading recommendations based on research
    # Source: https://pkolaczk.github.io/disk-parallelism/
    THREAD_RECOMMENDATIONS = {
        DriveType.NVME: 16,          # 4.4x speedup for sequential reads
        DriveType.SSD: 8,            # 3x speedup for internal SATA SSD
        DriveType.EXTERNAL_SSD: 4,   # USB overhead limits benefits
        DriveType.HDD: 1,            # Multi-threading HURTS sequential HDD performance
        DriveType.EXTERNAL_HDD: 1,   # External HDD - sequential only
        DriveType.NETWORK: 2,        # Limited parallelism for network stability
        DriveType.UNKNOWN: 1,        # Conservative fallback
    }

    # Performance class ratings (1=slowest, 5=fastest)
    PERFORMANCE_CLASS = {
        DriveType.NVME: 5,           # 3000-7000 MB/s
        DriveType.SSD: 4,            # 500-600 MB/s
        DriveType.EXTERNAL_SSD: 3,   # 200-400 MB/s (USB limited)
        DriveType.HDD: 2,            # 100-200 MB/s
        DriveType.EXTERNAL_HDD: 1,   # 20-60 MB/s
        DriveType.NETWORK: 1,        # Variable
        DriveType.UNKNOWN: 1,        # Assume worst case
    }

    def __init__(self):
        """Initialize storage detector with platform checks"""
        self.platform = platform.system()
        self.is_windows = self.platform == "Windows"
        self.wmi_available = False

        # Try to import WMI on Windows
        if self.is_windows:
            try:
                import wmi
                self.wmi = wmi
                self.wmi_available = True
                logger.debug("WMI available for storage detection")
            except ImportError:
                logger.debug("WMI not available (install with: pip install wmi)")

        logger.debug(f"StorageDetector initialized on {self.platform}")

    def analyze_path(self, path: Path) -> StorageInfo:
        """
        Analyze storage characteristics for a given path

        Uses layered detection with multiple fallback methods:
        1. Seek Penalty API (most reliable)
        2. Performance Heuristics (fast fallback)
        3. WMI (backup for internal drives)
        4. Conservative Fallback (always works)

        Args:
            path: Path to analyze (file or directory)

        Returns:
            StorageInfo with detected characteristics
        """
        # Normalize path
        if not path.exists():
            logger.warning(f"Path does not exist: {path}")
            return self._conservative_fallback("", "path_not_found")

        # Get drive root
        drive_letter = self._get_drive_letter(path)

        logger.debug(f"Analyzing storage for path: {path} (drive: {drive_letter})")

        # Method 1: Windows Seek Penalty API (Most Reliable)
        if self.is_windows:
            result = self._detect_via_seek_penalty(drive_letter)
            if result.confidence >= 0.8:
                logger.info(f"Storage detected via Seek Penalty API: {result}")
                return result

        # Method 2: Performance Heuristics (Fast Fallback)
        result = self._detect_via_performance_test(path, drive_letter)
        if result.confidence >= 0.7:
            logger.info(f"Storage detected via performance heuristics: {result}")
            return result

        # Method 3: WMI (Backup for internal drives only)
        if self.is_windows and self.wmi_available:
            if not self._is_removable_drive(drive_letter):
                result = self._detect_via_wmi(drive_letter)
                if result.confidence >= 0.6:
                    logger.info(f"Storage detected via WMI: {result}")
                    return result

        # Method 4: Conservative Fallback (Always Works)
        logger.warning(f"All detection methods failed for {drive_letter}, using conservative fallback")
        return self._conservative_fallback(drive_letter, "all_methods_failed")

    def _get_drive_letter(self, path: Path) -> str:
        """Extract drive letter from path (Windows) or mount point (Unix)"""
        if self.is_windows:
            # Windows: Extract drive letter (e.g., "C:")
            parts = path.resolve().parts
            if parts:
                return parts[0]  # Returns "C:\\" or similar
            return ""
        else:
            # Unix: Return mount point
            return str(path.resolve().anchor)

    def _detect_via_seek_penalty(self, drive_letter: str) -> StorageInfo:
        """
        Method 1: Windows Seek Penalty API detection

        Uses Windows DeviceIoControl with IOCTL_STORAGE_QUERY_PROPERTY
        to query StorageDeviceSeekPenaltyProperty. This is the most reliable
        method and doesn't require admin privileges.

        IncursSeekPenalty: False = SSD, True = HDD

        Returns:
            StorageInfo with high confidence (0.8-0.9) if successful
        """
        if not self.is_windows:
            return StorageInfo(
                drive_type=DriveType.UNKNOWN,
                bus_type=BusType.UNKNOWN,
                is_ssd=None,
                is_removable=False,
                recommended_threads=1,
                confidence=0.0,
                detection_method="seek_penalty_not_windows",
                drive_letter=drive_letter,
                performance_class=1
            )

        try:
            # Windows API implementation would go here
            # For now, return low confidence to trigger fallback
            # TODO: Implement ctypes-based DeviceIoControl call

            logger.debug("Seek Penalty API detection not yet implemented")
            return StorageInfo(
                drive_type=DriveType.UNKNOWN,
                bus_type=BusType.UNKNOWN,
                is_ssd=None,
                is_removable=False,
                recommended_threads=1,
                confidence=0.0,
                detection_method="seek_penalty_not_implemented",
                drive_letter=drive_letter,
                performance_class=1
            )

        except Exception as e:
            logger.debug(f"Seek Penalty API detection failed: {e}")
            return StorageInfo(
                drive_type=DriveType.UNKNOWN,
                bus_type=BusType.UNKNOWN,
                is_ssd=None,
                is_removable=False,
                recommended_threads=1,
                confidence=0.0,
                detection_method="seek_penalty_error",
                drive_letter=drive_letter,
                performance_class=1
            )

    def _detect_via_performance_test(self, path: Path, drive_letter: str) -> StorageInfo:
        """
        Method 2: Performance heuristics detection

        Performs small I/O test to measure actual performance characteristics.
        Fast and reliable fallback when API methods fail.

        Heuristics:
        - Random read speed > 100 MB/s = likely SSD
        - Random read speed < 50 MB/s = likely HDD
        - 50-100 MB/s = uncertain (older SSD or fast HDD)

        Returns:
            StorageInfo with moderate confidence (0.7) if successful
        """
        try:
            # Check if we can write test file
            test_dir = path if path.is_dir() else path.parent

            # Use temp directory if we can't write to target
            if not os.access(test_dir, os.W_OK):
                import tempfile
                test_dir = Path(tempfile.gettempdir())
                logger.debug(f"Cannot write to {path}, using temp dir for test")

            # Small I/O test (10MB read)
            test_size = 10 * 1024 * 1024  # 10MB
            test_file = test_dir / ".storage_test_temp"

            # Write test file
            start = time.time()
            with open(test_file, 'wb') as f:
                f.write(os.urandom(test_size))
                f.flush()
                os.fsync(f.fileno())
            write_duration = time.time() - start

            # Read test file
            start = time.time()
            with open(test_file, 'rb') as f:
                data = f.read()
            read_duration = time.time() - start

            # Cleanup
            test_file.unlink()

            # Calculate speeds
            write_speed_mbps = (test_size / (1024 * 1024)) / write_duration
            read_speed_mbps = (test_size / (1024 * 1024)) / read_duration

            logger.debug(f"Performance test: Write={write_speed_mbps:.1f} MB/s, Read={read_speed_mbps:.1f} MB/s")

            # IMPROVED: Check BOTH read AND write speeds to avoid misclassification
            is_removable = self._is_removable_drive(drive_letter)

            # Critical insight: HDDs have fast cached reads but SLOW writes
            # SSDs have fast reads AND fast writes
            # If write speed is slow but read is fast → likely HDD with cache

            # Check for HDD pattern: Slow write speed (< 50 MB/s) regardless of read
            if write_speed_mbps < 50:
                # Slow write = HDD (even if read is fast due to cache)
                drive_type = DriveType.EXTERNAL_HDD if is_removable else DriveType.HDD
                bus_type = BusType.USB if is_removable else BusType.SATA
                is_ssd = False
                confidence = 0.8  # High confidence - write speed is reliable indicator
                logger.info(f"HDD detected: Slow write speed ({write_speed_mbps:.1f} MB/s) indicates HDD")

            # Fast write AND fast read = SSD
            elif write_speed_mbps > 100 and read_speed_mbps > 200:
                # Very fast write + read - likely NVMe SSD
                drive_type = DriveType.EXTERNAL_SSD if is_removable else DriveType.NVME
                bus_type = BusType.USB if is_removable else BusType.NVME
                is_ssd = True
                confidence = 0.8
            elif write_speed_mbps > 50 and read_speed_mbps > 100:
                # Fast write + read - likely SATA SSD
                drive_type = DriveType.EXTERNAL_SSD if is_removable else DriveType.SSD
                bus_type = BusType.USB if is_removable else BusType.SATA
                is_ssd = True
                confidence = 0.75

            # Slow read (regardless of write) = HDD
            elif read_speed_mbps < 50:
                # Slow read - likely HDD
                drive_type = DriveType.EXTERNAL_HDD if is_removable else DriveType.HDD
                bus_type = BusType.USB if is_removable else BusType.SATA
                is_ssd = False
                confidence = 0.7

            else:
                # Uncertain - could be older SSD or unusual configuration
                # Default to HDD for safety (avoid over-parallelizing unknown devices)
                drive_type = DriveType.EXTERNAL_HDD if is_removable else DriveType.HDD
                bus_type = BusType.UNKNOWN
                is_ssd = False
                confidence = 0.4
                logger.warning(f"Uncertain storage type (W={write_speed_mbps:.1f}, R={read_speed_mbps:.1f}), "
                             f"defaulting to HDD for safety")

            threads = self.THREAD_RECOMMENDATIONS[drive_type]
            perf_class = self.PERFORMANCE_CLASS[drive_type]

            return StorageInfo(
                drive_type=drive_type,
                bus_type=bus_type,
                is_ssd=is_ssd,
                is_removable=is_removable,
                recommended_threads=threads,
                confidence=confidence,
                detection_method="performance_heuristics",
                drive_letter=drive_letter,
                performance_class=perf_class
            )

        except Exception as e:
            logger.debug(f"Performance test detection failed: {e}")
            return StorageInfo(
                drive_type=DriveType.UNKNOWN,
                bus_type=BusType.UNKNOWN,
                is_ssd=None,
                is_removable=False,
                recommended_threads=1,
                confidence=0.0,
                detection_method="performance_test_error",
                drive_letter=drive_letter,
                performance_class=1
            )

    def _detect_via_wmi(self, drive_letter: str) -> StorageInfo:
        """
        Method 3: WMI MSFT_PhysicalDisk detection

        Uses Windows Management Instrumentation to query physical disk properties.
        Backup method for internal drives only (unreliable for external drives).

        Queries:
        - MediaType: 3=HDD, 4=SSD, 5=SCM
        - BusType: Identifies connection interface

        Returns:
            StorageInfo with moderate confidence (0.6) if successful
        """
        if not self.wmi_available:
            return StorageInfo(
                drive_type=DriveType.UNKNOWN,
                bus_type=BusType.UNKNOWN,
                is_ssd=None,
                is_removable=False,
                recommended_threads=1,
                confidence=0.0,
                detection_method="wmi_not_available",
                drive_letter=drive_letter,
                performance_class=1
            )

        try:
            # Connect to WMI Storage namespace
            c = self.wmi.WMI(namespace='root/Microsoft/Windows/Storage')

            # Get logical disk to physical disk mapping
            # This is complex - for now return low confidence
            # TODO: Implement proper partition → physical disk mapping

            logger.debug("WMI detection not fully implemented yet")
            return StorageInfo(
                drive_type=DriveType.UNKNOWN,
                bus_type=BusType.UNKNOWN,
                is_ssd=None,
                is_removable=False,
                recommended_threads=1,
                confidence=0.0,
                detection_method="wmi_mapping_not_implemented",
                drive_letter=drive_letter,
                performance_class=1
            )

        except Exception as e:
            logger.debug(f"WMI detection failed: {e}")
            return StorageInfo(
                drive_type=DriveType.UNKNOWN,
                bus_type=BusType.UNKNOWN,
                is_ssd=None,
                is_removable=False,
                recommended_threads=1,
                confidence=0.0,
                detection_method="wmi_error",
                drive_letter=drive_letter,
                performance_class=1
            )

    def _is_removable_drive(self, drive_letter: str) -> bool:
        """
        Check if drive is removable/external

        Uses Windows GetDriveType API to determine if drive is:
        - DRIVE_REMOVABLE (USB, external)
        - DRIVE_REMOTE (network)
        - DRIVE_FIXED (internal)

        Returns:
            True if removable/external, False if internal
        """
        if not self.is_windows or not drive_letter:
            return False

        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            GetDriveTypeW = kernel32.GetDriveTypeW
            GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
            GetDriveTypeW.restype = wintypes.UINT

            DRIVE_UNKNOWN = 0
            DRIVE_NO_ROOT_DIR = 1
            DRIVE_REMOVABLE = 2
            DRIVE_FIXED = 3
            DRIVE_REMOTE = 4
            DRIVE_CDROM = 5
            DRIVE_RAMDISK = 6

            drive_type = GetDriveTypeW(drive_letter)

            # Removable includes USB drives and external devices
            is_removable = drive_type in (DRIVE_REMOVABLE, DRIVE_REMOTE)

            logger.debug(f"Drive {drive_letter} type: {drive_type} (removable: {is_removable})")
            return is_removable

        except Exception as e:
            logger.debug(f"Failed to check if drive is removable: {e}")
            return False

    def _conservative_fallback(self, drive_letter: str, reason: str) -> StorageInfo:
        """
        Method 4: Conservative fallback (always works)

        When all detection methods fail, assume worst-case scenario:
        - External HDD (slowest device type)
        - Sequential processing only (1 thread)
        - Performance class 1

        This ensures we never degrade performance by over-parallelizing
        a device that can't handle it.

        Returns:
            StorageInfo with low confidence but safe recommendations
        """
        logger.debug(f"Using conservative fallback for {drive_letter}: {reason}")

        return StorageInfo(
            drive_type=DriveType.EXTERNAL_HDD,
            bus_type=BusType.UNKNOWN,
            is_ssd=False,
            is_removable=True,
            recommended_threads=1,
            confidence=0.0,
            detection_method=f"conservative_fallback_{reason}",
            drive_letter=drive_letter,
            performance_class=1
        )

    def get_all_drives_info(self) -> Dict[str, StorageInfo]:
        """
        Analyze all available drives on the system

        Useful for system diagnostics and settings UI display.

        Returns:
            Dictionary mapping drive letters to StorageInfo
        """
        drives_info = {}

        if self.is_windows:
            import string
            # Check all possible drive letters
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                drive_path = Path(drive)
                if drive_path.exists():
                    try:
                        info = self.analyze_path(drive_path)
                        drives_info[drive] = info
                    except Exception as e:
                        logger.debug(f"Failed to analyze {drive}: {e}")
        else:
            # Unix: Check common mount points
            common_mounts = [Path('/'), Path('/home'), Path('/mnt'), Path('/media')]
            for mount in common_mounts:
                if mount.exists():
                    try:
                        info = self.analyze_path(mount)
                        drives_info[str(mount)] = info
                    except Exception as e:
                        logger.debug(f"Failed to analyze {mount}: {e}")

        return drives_info
