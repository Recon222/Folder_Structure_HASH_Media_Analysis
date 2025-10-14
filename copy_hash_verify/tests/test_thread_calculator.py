"""
Unit tests for ThreadCalculator utility

Tests CPU-aware thread calculation for various storage combinations.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from copy_hash_verify.core.storage_detector import StorageInfo, DriveType, BusType
from copy_hash_verify.utils.thread_calculator import ThreadCalculator


def create_storage_info(drive_type: DriveType, is_removable: bool = False) -> StorageInfo:
    """Helper to create StorageInfo for testing"""
    return StorageInfo(
        drive_type=drive_type,
        bus_type=BusType.NVME if drive_type == DriveType.NVME else BusType.SATA,
        is_ssd=drive_type not in (DriveType.HDD, DriveType.EXTERNAL_HDD, DriveType.UNKNOWN),
        is_removable=is_removable,
        confidence=1.0,
        detection_method="test",
        drive_letter="C:\\",
        performance_class=1
    )


def test_single_file():
    """Test: Single file always returns 1 thread"""
    calc = ThreadCalculator(cpu_threads=16)

    nvme_src = create_storage_info(DriveType.NVME)
    nvme_dst = create_storage_info(DriveType.NVME)

    threads = calc.calculate_optimal_threads(
        source_info=nvme_src,
        dest_info=nvme_dst,
        file_count=1
    )

    assert threads == 1, f"Expected 1 thread for single file, got {threads}"
    print("PASS: Single file returns 1 thread")


def test_hdd_destination():
    """Test: HDD destination always returns 1 thread (write bottleneck)"""
    calc = ThreadCalculator(cpu_threads=16)

    nvme_src = create_storage_info(DriveType.NVME)
    hdd_dst = create_storage_info(DriveType.HDD)

    threads = calc.calculate_optimal_threads(
        source_info=nvme_src,
        dest_info=hdd_dst,
        file_count=100
    )

    assert threads == 1, f"Expected 1 thread for HDD destination, got {threads}"
    print("PASS: HDD destination returns 1 thread")


def test_nvme_to_nvme():
    """Test: NVMe→NVMe returns 2x CPU threads, capped at 64"""
    calc = ThreadCalculator(cpu_threads=16)

    nvme_src = create_storage_info(DriveType.NVME)
    nvme_dst = create_storage_info(DriveType.NVME)

    threads = calc.calculate_optimal_threads(
        source_info=nvme_src,
        dest_info=nvme_dst,
        file_count=100
    )

    expected = min(16 * 2, 64)
    assert threads == expected, f"Expected {expected} threads for NVMe->NVMe, got {threads}"
    print(f"PASS: NVMe->NVMe returns {threads} threads (2x CPU, cap 64)")


def test_hdd_to_nvme():
    """Test: HDD→NVMe returns 8 threads (queue optimization)"""
    calc = ThreadCalculator(cpu_threads=16)

    hdd_src = create_storage_info(DriveType.HDD)
    nvme_dst = create_storage_info(DriveType.NVME)

    threads = calc.calculate_optimal_threads(
        source_info=hdd_src,
        dest_info=nvme_dst,
        file_count=100
    )

    assert threads == 8, f"Expected 8 threads for HDD->NVMe, got {threads}"
    print("PASS: HDD->NVMe returns 8 threads")


def test_ssd_to_nvme():
    """Test: SSD→NVMe returns 32 threads"""
    calc = ThreadCalculator(cpu_threads=16)

    ssd_src = create_storage_info(DriveType.SSD)
    nvme_dst = create_storage_info(DriveType.NVME)

    threads = calc.calculate_optimal_threads(
        source_info=ssd_src,
        dest_info=nvme_dst,
        file_count=100
    )

    assert threads == 32, f"Expected 32 threads for SSD->NVMe, got {threads}"
    print("PASS: SSD->NVMe returns 32 threads")


def test_ssd_to_ssd():
    """Test: SSD→SSD returns 16 threads"""
    calc = ThreadCalculator(cpu_threads=16)

    ssd_src = create_storage_info(DriveType.SSD)
    ssd_dst = create_storage_info(DriveType.SSD)

    threads = calc.calculate_optimal_threads(
        source_info=ssd_src,
        dest_info=ssd_dst,
        file_count=100
    )

    assert threads == 16, f"Expected 16 threads for SSD->SSD, got {threads}"
    print("PASS: SSD->SSD returns 16 threads")


def test_hash_only_nvme():
    """Test: Hash-only on NVMe returns 2x CPU threads"""
    calc = ThreadCalculator(cpu_threads=16)

    nvme_src = create_storage_info(DriveType.NVME)

    threads = calc.calculate_optimal_threads(
        source_info=nvme_src,
        dest_info=None,
        file_count=100,
        operation_type="hash"
    )

    expected = min(16 * 2, 64)
    assert threads == expected, f"Expected {expected} threads for hash on NVMe, got {threads}"
    print(f"PASS: Hash-only on NVMe returns {threads} threads")


def test_hash_only_hdd():
    """Test: Hash-only on HDD returns 8 threads (queue optimization)"""
    calc = ThreadCalculator(cpu_threads=16)

    hdd_src = create_storage_info(DriveType.HDD)

    threads = calc.calculate_optimal_threads(
        source_info=hdd_src,
        dest_info=None,
        file_count=100,
        operation_type="hash"
    )

    assert threads == 8, f"Expected 8 threads for hash on HDD, got {threads}"
    print("PASS: Hash-only on HDD returns 8 threads")


def test_ui_display_text():
    """Test: UI display text generation"""
    calc = ThreadCalculator(cpu_threads=16)

    nvme_src = create_storage_info(DriveType.NVME)
    nvme_dst = create_storage_info(DriveType.NVME)

    text = calc.get_ui_display_text(
        source_info=nvme_src,
        dest_info=nvme_dst,
        file_count=100,
        operation_type="copy"
    )

    assert "NVMe" in text, f"Expected NVMe in display text, got: {text}"
    assert "32" in text, f"Expected 32 in display text, got: {text}"
    print(f"PASS: UI display text: '{text}'")


def run_all_tests():
    """Run all ThreadCalculator tests"""
    print("=" * 80)
    print("ThreadCalculator Unit Tests")
    print("=" * 80)
    print()

    tests = [
        test_single_file,
        test_hdd_destination,
        test_nvme_to_nvme,
        test_hdd_to_nvme,
        test_ssd_to_nvme,
        test_ssd_to_ssd,
        test_hash_only_nvme,
        test_hash_only_hdd,
        test_ui_display_text,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__} - {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__} - {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print()
    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 80)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
