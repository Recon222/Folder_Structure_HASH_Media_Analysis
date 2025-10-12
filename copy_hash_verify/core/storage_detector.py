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
                f"[{self.bus_type.name}] -> {self.recommended_threads} threads "
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

        # Method 1: Windows Seek Penalty API (Most Reliable for SSD/HDD distinction)
        seek_penalty_result = None
        if self.is_windows:
            seek_penalty_result = self._detect_via_seek_penalty(drive_letter)
            # If Seek Penalty detected NVMe with high confidence, use it immediately
            if seek_penalty_result.confidence >= 0.8 and seek_penalty_result.drive_type == DriveType.NVME:
                logger.info(f"Storage detected via Seek Penalty API: {seek_penalty_result}")
                return seek_penalty_result

        # Method 2: Performance Heuristics (Detects NVMe vs SATA SSD distinction)
        perf_result = self._detect_via_performance_test(path, drive_letter)

        # Smart decision logic: Performance heuristics can detect NVMe, Seek Penalty cannot always
        if perf_result.confidence >= 0.7:
            # If performance test detects NVMe and Seek Penalty only detected generic SSD,
            # trust performance test (it measured actual NVMe speeds)
            if (perf_result.drive_type == DriveType.NVME and
                seek_penalty_result and
                seek_penalty_result.drive_type == DriveType.SSD):
                logger.info(f"Storage detected via performance heuristics (NVMe override): {perf_result}")
                return perf_result

            # If Seek Penalty failed or returned low confidence, use performance test
            if not seek_penalty_result or seek_penalty_result.confidence < 0.7:
                logger.info(f"Storage detected via performance heuristics: {perf_result}")
                return perf_result

        # If we got here, Seek Penalty succeeded but wasn't NVMe, use it
        if seek_penalty_result and seek_penalty_result.confidence >= 0.8:
            logger.info(f"Storage detected via Seek Penalty API: {seek_penalty_result}")
            return seek_penalty_result

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
            StorageInfo with high confidence (0.9) if successful
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
            from ctypes import wintypes, Structure, c_ulong, c_bool, byref, sizeof
            import ctypes

            # Windows API constants
            GENERIC_READ = 0x80000000
            GENERIC_WRITE = 0x40000000
            FILE_SHARE_READ = 0x00000001
            FILE_SHARE_WRITE = 0x00000002
            OPEN_EXISTING = 3
            FILE_ATTRIBUTE_NORMAL = 0x80

            IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400

            # Storage property IDs
            StorageDeviceSeekPenaltyProperty = 7
            StorageAdapterProperty = 1
            PropertyStandardQuery = 0

            # Structures for DeviceIoControl
            class STORAGE_PROPERTY_QUERY(Structure):
                _fields_ = [
                    ('PropertyId', c_ulong),
                    ('QueryType', c_ulong),
                    ('AdditionalParameters', c_ulong)
                ]

            class DEVICE_SEEK_PENALTY_DESCRIPTOR(Structure):
                _fields_ = [
                    ('Version', c_ulong),
                    ('Size', c_ulong),
                    ('IncursSeekPenalty', c_bool)
                ]

            class STORAGE_ADAPTER_DESCRIPTOR(Structure):
                _fields_ = [
                    ('Version', c_ulong),
                    ('Size', c_ulong),
                    ('MaximumTransferLength', c_ulong),
                    ('MaximumPhysicalPages', c_ulong),
                    ('AlignmentMask', c_ulong),
                    ('AdapterUsesPio', c_bool),
                    ('AdapterScansDown', c_bool),
                    ('CommandQueueing', c_bool),
                    ('AcceleratedTransfer', c_bool),
                    ('BusType', c_ulong),  # This is what we need!
                    # Additional fields exist but we don't need them
                ]

            # Get kernel32 functions
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            CreateFileW = kernel32.CreateFileW
            CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            CreateFileW.restype = wintypes.HANDLE

            DeviceIoControl = kernel32.DeviceIoControl
            DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID,
                                       wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                       ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
            DeviceIoControl.restype = wintypes.BOOL

            CloseHandle = kernel32.CloseHandle
            CloseHandle.argtypes = [wintypes.HANDLE]
            CloseHandle.restype = wintypes.BOOL

            # Format drive path for CreateFile (e.g., "\\.\C:")
            if drive_letter.endswith('\\'):
                drive_letter = drive_letter.rstrip('\\')
            device_path = f"\\\\.\\{drive_letter}"

            # Open handle to drive
            handle = CreateFileW(
                device_path,
                0,  # No access needed for query
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None,
                OPEN_EXISTING,
                FILE_ATTRIBUTE_NORMAL,
                None
            )

            INVALID_HANDLE_VALUE = -1
            if handle == INVALID_HANDLE_VALUE or handle == 0:
                error_code = ctypes.get_last_error()
                logger.debug(f"Failed to open device handle for {drive_letter}: error {error_code}")
                return StorageInfo(
                    drive_type=DriveType.UNKNOWN,
                    bus_type=BusType.UNKNOWN,
                    is_ssd=None,
                    is_removable=False,
                    recommended_threads=1,
                    confidence=0.0,
                    detection_method="seek_penalty_handle_failed",
                    drive_letter=drive_letter,
                    performance_class=1
                )

            try:
                # Query 1: Seek Penalty (SSD vs HDD)
                query = STORAGE_PROPERTY_QUERY()
                query.PropertyId = StorageDeviceSeekPenaltyProperty
                query.QueryType = PropertyStandardQuery
                query.AdditionalParameters = 0

                descriptor = DEVICE_SEEK_PENALTY_DESCRIPTOR()
                bytes_returned = wintypes.DWORD(0)

                result = DeviceIoControl(
                    handle,
                    IOCTL_STORAGE_QUERY_PROPERTY,
                    byref(query),
                    sizeof(query),
                    byref(descriptor),
                    sizeof(descriptor),
                    byref(bytes_returned),
                    None
                )

                if not result:
                    error_code = ctypes.get_last_error()
                    logger.debug(f"Seek Penalty query failed for {drive_letter}: error {error_code}")
                    return StorageInfo(
                        drive_type=DriveType.UNKNOWN,
                        bus_type=BusType.UNKNOWN,
                        is_ssd=None,
                        is_removable=False,
                        recommended_threads=1,
                        confidence=0.0,
                        detection_method="seek_penalty_ioctl_failed",
                        drive_letter=drive_letter,
                        performance_class=1
                    )

                incurs_seek_penalty = descriptor.IncursSeekPenalty
                is_ssd = not incurs_seek_penalty
                is_removable = self._is_removable_drive(drive_letter)

                # Query 2: Bus Type (NVMe vs SATA vs USB)
                query2 = STORAGE_PROPERTY_QUERY()
                query2.PropertyId = StorageAdapterProperty
                query2.QueryType = PropertyStandardQuery
                query2.AdditionalParameters = 0

                adapter_desc = STORAGE_ADAPTER_DESCRIPTOR()
                bytes_returned2 = wintypes.DWORD(0)

                result2 = DeviceIoControl(
                    handle,
                    IOCTL_STORAGE_QUERY_PROPERTY,
                    byref(query2),
                    sizeof(query2),
                    byref(adapter_desc),
                    sizeof(adapter_desc),
                    byref(bytes_returned2),
                    None
                )

                # Map Windows BusType values to our BusType enum
                # https://docs.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddstor/ne-ntddstor-_storage_bus_type
                api_bus_type = BusType.UNKNOWN
                if result2:
                    bus_type_value = adapter_desc.BusType
                    bus_type_map = {
                        1: BusType.SCSI,
                        2: BusType.ATAPI,
                        3: BusType.ATA,
                        4: BusType.IEEE1394,
                        5: BusType.SSA,
                        6: BusType.FIBRE_CHANNEL,
                        7: BusType.USB,
                        8: BusType.RAID,
                        9: BusType.ISCSI,
                        10: BusType.SAS,
                        11: BusType.SATA,
                        12: BusType.SD,
                        13: BusType.MMC,
                        17: BusType.NVME,
                    }
                    api_bus_type = bus_type_map.get(bus_type_value, BusType.UNKNOWN)
                    logger.debug(f"Bus Type query: {drive_letter} BusType={bus_type_value} ({api_bus_type.name})")
                else:
                    logger.debug(f"Bus Type query failed for {drive_letter}, will infer from other data")

                logger.info(f"Seek Penalty API: {drive_letter} IncursSeekPenalty={incurs_seek_penalty} "
                           f"(SSD={is_ssd}, BusType={api_bus_type.name}, removable={is_removable})")

                # Classify drive type based on SSD flag, bus type, and removable status
                if is_ssd:
                    # SSD - determine if NVMe or SATA based on bus type
                    if is_removable:
                        drive_type = DriveType.EXTERNAL_SSD
                        bus_type = BusType.USB if api_bus_type == BusType.UNKNOWN else api_bus_type
                    elif api_bus_type == BusType.NVME:
                        drive_type = DriveType.NVME
                        bus_type = BusType.NVME
                    elif api_bus_type in (BusType.SATA, BusType.ATA):
                        drive_type = DriveType.SSD
                        bus_type = api_bus_type
                    elif api_bus_type == BusType.RAID:
                        # RAID controller - could be NVMe or SATA, assume SATA for safety
                        drive_type = DriveType.SSD
                        bus_type = BusType.RAID
                    else:
                        # Unknown bus type - default to SATA SSD
                        drive_type = DriveType.SSD
                        bus_type = BusType.SATA if api_bus_type == BusType.UNKNOWN else api_bus_type
                else:
                    # HDD
                    drive_type = DriveType.EXTERNAL_HDD if is_removable else DriveType.HDD
                    bus_type = BusType.USB if is_removable else api_bus_type
                    if bus_type == BusType.UNKNOWN:
                        bus_type = BusType.SATA  # Default HDD bus type

                threads = self.THREAD_RECOMMENDATIONS[drive_type]
                perf_class = self.PERFORMANCE_CLASS[drive_type]

                return StorageInfo(
                    drive_type=drive_type,
                    bus_type=bus_type,
                    is_ssd=is_ssd,
                    is_removable=is_removable,
                    recommended_threads=threads,
                    confidence=0.9,  # High confidence - most reliable method
                    detection_method="seek_penalty_api",
                    drive_letter=drive_letter,
                    performance_class=perf_class
                )

            finally:
                CloseHandle(handle)

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
            StorageInfo with moderate confidence (0.7) if successful
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
            # Strip trailing backslash for WMI query
            if drive_letter.endswith('\\'):
                drive_letter_clean = drive_letter.rstrip('\\')
            else:
                drive_letter_clean = drive_letter

            # Connect to WMI namespaces
            cimv2_wmi = self.wmi.WMI()
            storage_wmi = self.wmi.WMI(namespace='root/Microsoft/Windows/Storage')

            # Step 1: Get disk drive for this logical disk
            # Use Win32_LogicalDisk to get the logical disk object
            logical_disks = cimv2_wmi.Win32_LogicalDisk(DeviceID=drive_letter_clean)

            if not logical_disks:
                logger.debug(f"No logical disk found for {drive_letter}")
                return StorageInfo(
                    drive_type=DriveType.UNKNOWN,
                    bus_type=BusType.UNKNOWN,
                    is_ssd=None,
                    is_removable=False,
                    recommended_threads=1,
                    confidence=0.0,
                    detection_method="wmi_no_logical_disk",
                    drive_letter=drive_letter,
                    performance_class=1
                )

            # Get partition for this logical disk
            partitions = []
            for ld in logical_disks:
                for partition in ld.associators("Win32_LogicalDiskToPartition"):
                    partitions.append(partition)

            if not partitions:
                logger.debug(f"No partition found for {drive_letter}")
                return StorageInfo(
                    drive_type=DriveType.UNKNOWN,
                    bus_type=BusType.UNKNOWN,
                    is_ssd=None,
                    is_removable=False,
                    recommended_threads=1,
                    confidence=0.0,
                    detection_method="wmi_no_partition",
                    drive_letter=drive_letter,
                    performance_class=1
                )

            # Get disk drive from partition
            disk_drives = []
            for partition in partitions:
                for disk in partition.associators("Win32_DiskDriveToDiskPartition"):
                    disk_drives.append(disk)

            if not disk_drives:
                logger.debug(f"No disk drive found for {drive_letter}")
                return StorageInfo(
                    drive_type=DriveType.UNKNOWN,
                    bus_type=BusType.UNKNOWN,
                    is_ssd=None,
                    is_removable=False,
                    recommended_threads=1,
                    confidence=0.0,
                    detection_method="wmi_no_disk_drive",
                    drive_letter=drive_letter,
                    performance_class=1
                )

            # Extract disk number from DeviceID (e.g., "\\.\PHYSICALDRIVE0")
            import re
            disk_drive = disk_drives[0]
            device_id = disk_drive.DeviceID
            disk_match = re.search(r'PHYSICALDRIVE(\d+)', device_id)
            if not disk_match:
                logger.debug(f"Could not parse disk number from: {device_id}")
                return StorageInfo(
                    drive_type=DriveType.UNKNOWN,
                    bus_type=BusType.UNKNOWN,
                    is_ssd=None,
                    is_removable=False,
                    recommended_threads=1,
                    confidence=0.0,
                    detection_method="wmi_parse_error",
                    drive_letter=drive_letter,
                    performance_class=1
                )

            disk_number = int(disk_match.group(1))
            logger.debug(f"Drive {drive_letter} is on PhysicalDrive{disk_number}")

            # Step 2: Query physical disk properties from Storage namespace
            physical_disks = storage_wmi.query(
                f"SELECT * FROM MSFT_PhysicalDisk WHERE DeviceId = '{disk_number}'"
            )

            if not physical_disks:
                logger.debug(f"No physical disk found for disk number {disk_number}")
                return StorageInfo(
                    drive_type=DriveType.UNKNOWN,
                    bus_type=BusType.UNKNOWN,
                    is_ssd=None,
                    is_removable=False,
                    recommended_threads=1,
                    confidence=0.0,
                    detection_method="wmi_no_physical_disk",
                    drive_letter=drive_letter,
                    performance_class=1
                )

            disk = physical_disks[0]

            # Parse MediaType: 3=HDD, 4=SSD, 5=SCM (Storage Class Memory)
            media_type = int(disk.MediaType) if disk.MediaType is not None else 0
            wmi_bus_type = int(disk.BusType) if disk.BusType is not None else 0

            logger.info(f"WMI: Disk #{disk_number} MediaType={media_type}, BusType={wmi_bus_type}")

            # Map media type to SSD/HDD
            if media_type == 4 or media_type == 5:  # SSD or SCM
                is_ssd = True
            elif media_type == 3:  # HDD
                is_ssd = False
            else:
                # Unknown media type
                logger.debug(f"Unknown WMI MediaType: {media_type}")
                return StorageInfo(
                    drive_type=DriveType.UNKNOWN,
                    bus_type=BusType.UNKNOWN,
                    is_ssd=None,
                    is_removable=False,
                    recommended_threads=1,
                    confidence=0.0,
                    detection_method="wmi_unknown_media_type",
                    drive_letter=drive_letter,
                    performance_class=1
                )

            # Map WMI BusType to our BusType enum
            bus_type_map = {
                1: BusType.SCSI,
                2: BusType.ATAPI,
                3: BusType.ATA,
                4: BusType.IEEE1394,
                5: BusType.SSA,
                6: BusType.FIBRE_CHANNEL,
                7: BusType.USB,
                8: BusType.RAID,
                9: BusType.ISCSI,
                10: BusType.SAS,
                11: BusType.SATA,
                12: BusType.SD,
                13: BusType.MMC,
                17: BusType.NVME,
            }
            bus_type = bus_type_map.get(wmi_bus_type, BusType.UNKNOWN)

            # Check if removable
            is_removable = self._is_removable_drive(drive_letter)

            # Classify drive type
            if is_ssd:
                if bus_type == BusType.NVME:
                    drive_type = DriveType.EXTERNAL_SSD if is_removable else DriveType.NVME
                elif is_removable:
                    drive_type = DriveType.EXTERNAL_SSD
                else:
                    drive_type = DriveType.SSD
            else:
                drive_type = DriveType.EXTERNAL_HDD if is_removable else DriveType.HDD

            threads = self.THREAD_RECOMMENDATIONS[drive_type]
            perf_class = self.PERFORMANCE_CLASS[drive_type]

            return StorageInfo(
                drive_type=drive_type,
                bus_type=bus_type,
                is_ssd=is_ssd,
                is_removable=is_removable,
                recommended_threads=threads,
                confidence=0.7,  # Moderate confidence - works well for internal drives
                detection_method="wmi",
                drive_letter=drive_letter,
                performance_class=perf_class
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
