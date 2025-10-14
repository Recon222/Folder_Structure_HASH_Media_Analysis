"""
Baseline Performance Test for Storage Detection Refactor

This script captures baseline performance metrics before the refactor.
Run this script to establish a performance baseline, then run again after
the refactor to validate improvements.

Usage:
    python copy_hash_verify/tests/baseline_performance_test.py
"""

import sys
import time
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from copy_hash_verify.core.storage_detector import StorageDetector, DriveType


def test_storage_detection_performance():
    """Test storage detection performance across all tiers."""
    print("=" * 80)
    print("BASELINE PERFORMANCE TEST - Storage Detection")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    detector = StorageDetector()

    # Test drives - adjust these to your system
    test_drives = ["C:\\", "D:\\"]

    results = []

    for drive in test_drives:
        print(f"\n{'-' * 80}")
        print(f"Testing drive: {drive}")
        print(f"{'-' * 80}")

        # Time the detection
        start_time = time.perf_counter()
        info = detector.analyze_path(Path(drive))
        elapsed = time.perf_counter() - start_time

        result = {
            "drive": drive,
            "drive_type": info.drive_type.value,
            "detection_method": info.detection_method,
            "performance_class": info.performance_class,
            "is_removable": info.is_removable,
            "elapsed_ms": elapsed * 1000
        }
        results.append(result)

        print(f"Drive Type:          {result['drive_type']}")
        print(f"Detection Method:    {result['detection_method']}")
        print(f"Performance Class:   {result['performance_class']}")
        print(f"Is Removable:        {result['is_removable']}")
        print(f"Detection Time:      {result['elapsed_ms']:.2f} ms")

    # Summary
    print("\n" + "=" * 80)
    print("BASELINE SUMMARY")
    print("=" * 80)

    total_time = sum(r["elapsed_ms"] for r in results)
    avg_time = total_time / len(results) if results else 0

    print(f"Total drives tested: {len(results)}")
    print(f"Total detection time: {total_time:.2f} ms")
    print(f"Average per drive: {avg_time:.2f} ms")

    # Save results to file
    output_file = Path(__file__).parent / "baseline_backups" / "baseline_results.txt"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        f.write(f"Baseline Performance Test Results\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"\n{'=' * 80}\n")

        for result in results:
            f.write(f"\nDrive: {result['drive']}\n")
            f.write(f"  Type: {result['drive_type']}\n")
            f.write(f"  Method: {result['detection_method']}\n")
            f.write(f"  Performance Class: {result['performance_class']}\n")
            f.write(f"  Detection Time: {result['elapsed_ms']:.2f} ms\n")

        f.write(f"\n{'=' * 80}\n")
        f.write(f"Summary:\n")
        f.write(f"  Total drives: {len(results)}\n")
        f.write(f"  Total time: {total_time:.2f} ms\n")
        f.write(f"  Average: {avg_time:.2f} ms\n")

    print(f"\nResults saved to: {output_file}")
    print()

    return results


if __name__ == "__main__":
    try:
        test_storage_detection_performance()
        print("PASS: Baseline test completed successfully")
    except Exception as e:
        print(f"FAIL: Baseline test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
