#!/usr/bin/env python3
"""
Test script for new 3-tier storage detection:
Tier 0: WMI (fast, all drives)
Tier 1: Seek Penalty (backup for RAID/UNKNOWN)
Tier 2: Performance Test (final fallback)
"""

from pathlib import Path
from copy_hash_verify.core.storage_detector import StorageDetector, DriveType, BusType

def test_storage_detection_tiers():
    """Test the new 3-tier detection order"""

    print("=" * 80)
    print("Testing New 3-Tier Storage Detection")
    print("=" * 80)

    detector = StorageDetector()

    # Test drives
    test_drives = [
        ("C:\\", "NVMe RAID (should use WMI -> Seek Penalty -> Performance)"),
        ("D:\\", "NVMe RAID (should use WMI -> Seek Penalty -> Performance)"),
        ("E:\\", "External HDD (should use WMI directly)"),
    ]

    for drive_path, description in test_drives:
        print(f"\n{'-' * 80}")
        print(f"Testing: {drive_path} - {description}")
        print(f"{'-' * 80}")

        path = Path(drive_path)
        if not path.exists():
            print(f"[SKIP] Drive {drive_path} does not exist")
            continue

        try:
            info = detector.analyze_path(path)

            print(f"\n[RESULT]")
            print(f"  Drive Type: {info.drive_type.value}")
            print(f"  Bus Type: {info.bus_type.name}")
            print(f"  Is SSD: {info.is_ssd}")
            print(f"  Is Removable: {info.is_removable}")
            print(f"  Detection Method: {info.detection_method}")
            print(f"  Confidence: {info.confidence:.0%}")
            print(f"  Recommended Threads: {info.recommended_threads}")
            print(f"  Performance Class: {info.performance_class}")

            # Verify detection method priority
            if info.bus_type in (BusType.RAID, BusType.UNKNOWN, BusType.VIRTUAL):
                expected_methods = ["wmi", "seek_penalty", "performance"]
                if not any(method in info.detection_method for method in expected_methods):
                    print(f"\n[WARNING] Unexpected detection method for RAID/UNKNOWN: {info.detection_method}")

        except Exception as e:
            print(f"\n[ERROR] Detection failed: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 80)
    print("Test Complete")
    print("=" * 80)

if __name__ == "__main__":
    test_storage_detection_tiers()
