#!/usr/bin/env python3
"""
Quick test of high-performance ZIP implementation
"""

import tempfile
import time
from pathlib import Path
from utils.zip_utils import ZipUtility, ZipSettings

def create_test_files(base_dir: Path, num_files: int = 10, file_size_kb: int = 100):
    """Create test files of various sizes"""
    files_created = []
    
    for i in range(num_files):
        test_file = base_dir / f"test_file_{i:03d}.dat"
        
        # Create file with some test content
        content = f"Test file {i} content.\n" * (file_size_kb * 10)  # Rough KB sizing
        test_file.write_text(content)
        files_created.append(test_file)
    
    return files_created

def test_zip_performance():
    """Test the new high-performance ZIP operations"""
    print("Testing High-Performance ZIP Operations")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create test directory structure
        test_source = temp_path / "test_source"
        test_source.mkdir()
        
        # Create test files with mix of small and large files
        print("Creating test files...")
        
        # Create small files (should use legacy method)
        small_files = create_test_files(test_source, num_files=20, file_size_kb=50)
        
        # Create large files (should use buffered method)
        large_files = []
        for i in range(5):
            large_file = test_source / f"large_file_{i:03d}.dat"
            content = "Large file content.\n" * 200000  # ~4MB each
            large_file.write_text(content)
            large_files.append(large_file)
        
        test_files = small_files + large_files
        total_size = sum(f.stat().st_size for f in test_files)
        print(f"Created {len(test_files)} test files ({len(small_files)} small, {len(large_files)} large)")
        print(f"Total size: {total_size / (1024*1024):.1f} MB")
        
        # Test high-performance ZIP
        print("\nTesting HIGH-PERFORMANCE ZIP:")
        zip_output_hp = temp_path / "test_high_performance.zip"
        
        def progress_callback(pct, msg):
            if pct % 25 == 0 or pct == 100:  # Only print every 25%
                print(f"  Progress: {pct:3d}% - {msg}")
        
        zip_util_hp = ZipUtility(progress_callback=progress_callback, use_high_performance=True)
        
        start_time = time.time()
        success_hp = zip_util_hp.create_archive(test_source, zip_output_hp)
        hp_duration = time.time() - start_time
        
        if success_hp:
            hp_size = zip_output_hp.stat().st_size
            hp_speed = (total_size / (1024*1024)) / hp_duration
            print(f"  SUCCESS: Created in {hp_duration:.2f}s at {hp_speed:.1f} MB/s")
            print(f"  Archive size: {hp_size / (1024*1024):.1f} MB")
            
            # Get performance metrics
            metrics = zip_util_hp.get_performance_metrics()
            if metrics:
                print(f"  Metrics: Avg {metrics.average_speed_mbps:.1f} MB/s, Peak {metrics.peak_speed_mbps:.1f} MB/s")
                print(f"  Files: {metrics.small_files_count} small, {metrics.medium_files_count} medium, {metrics.large_files_count} large")
        else:
            print("  HIGH-PERFORMANCE ZIP FAILED")
        
        # Test legacy ZIP for comparison
        print("\nTesting LEGACY ZIP (for comparison):")
        zip_output_legacy = temp_path / "test_legacy.zip"
        
        zip_util_legacy = ZipUtility(progress_callback=progress_callback, use_high_performance=False)
        
        start_time = time.time()
        success_legacy = zip_util_legacy.create_archive(test_source, zip_output_legacy)
        legacy_duration = time.time() - start_time
        
        if success_legacy:
            legacy_size = zip_output_legacy.stat().st_size
            legacy_speed = (total_size / (1024*1024)) / legacy_duration
            print(f"  SUCCESS: Created in {legacy_duration:.2f}s at {legacy_speed:.1f} MB/s")
            print(f"  Archive size: {legacy_size / (1024*1024):.1f} MB")
        else:
            print("  LEGACY ZIP FAILED")
        
        # Performance comparison
        if success_hp and success_legacy:
            speed_improvement = hp_speed / legacy_speed
            time_savings = ((legacy_duration - hp_duration) / legacy_duration) * 100
            
            print(f"\nPERFORMANCE COMPARISON:")
            print(f"  High-Performance: {hp_duration:.2f}s ({hp_speed:.1f} MB/s)")
            print(f"  Legacy:           {legacy_duration:.2f}s ({legacy_speed:.1f} MB/s)")
            print(f"  Speed Improvement: {speed_improvement:.1f}x faster")
            print(f"  Time Savings:     {time_savings:.1f}% faster")
            
            if speed_improvement > 1.5:
                print(f"  EXCELLENT: Achieved {speed_improvement:.1f}x speed improvement!")
            elif speed_improvement > 1.1:
                print(f"  GOOD: Achieved {speed_improvement:.1f}x speed improvement")
            else:
                print(f"  MINIMAL: Only {speed_improvement:.1f}x improvement (check buffer sizes)")
        
        print(f"\nTest completed successfully!")
        return success_hp and success_legacy

if __name__ == "__main__":
    try:
        test_zip_performance()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()