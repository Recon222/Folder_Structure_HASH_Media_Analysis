#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple performance test comparing Native 7zip vs Buffered Python
"""

import time
import tempfile
import os
from pathlib import Path

from utils.zip_utils import ZipUtility, ArchiveMethod
from core.native_7zip.controller import Native7ZipController
from core.buffered_zip_ops import BufferedZipOperations


def create_test_files(test_dir: Path, count: int = 20, size_mb: int = 1):
    """Create test files for performance comparison"""
    test_dir.mkdir(exist_ok=True)
    
    total_size = 0
    for i in range(count):
        file_path = test_dir / f"test_file_{i:03d}.dat"
        file_size = size_mb * 1024 * 1024
        with open(file_path, 'wb') as f:
            f.write(os.urandom(file_size))
        total_size += file_size
    
    return total_size


def test_native_7zip(test_dir: Path, total_size: int):
    """Test native 7zip performance"""
    print("Testing Native 7-Zip...")
    
    controller = Native7ZipController()
    if not controller.is_available():
        return None, "7za.exe not available"
    
    output_path = test_dir.parent / "test_native.7z"
    
    start_time = time.time()
    result = controller.create_archive(test_dir, output_path)
    duration = time.time() - start_time
    
    if output_path.exists():
        output_path.unlink()
    
    if result.success:
        speed_mbps = (total_size / (1024*1024)) / duration
        return speed_mbps, None
    else:
        return None, str(result.error)


def test_buffered_python(test_dir: Path, total_size: int):
    """Test buffered Python performance"""
    print("Testing Buffered Python...")
    
    buffered_ops = BufferedZipOperations()
    output_path = test_dir.parent / "test_buffered.zip"
    
    start_time = time.time()
    result = buffered_ops.create_archive_buffered(test_dir, output_path)
    duration = time.time() - start_time
    
    if output_path.exists():
        output_path.unlink()
    
    if result.success:
        speed_mbps = (total_size / (1024*1024)) / duration
        return speed_mbps, None
    else:
        return None, str(result.error)


def main():
    """Run simple performance comparison"""
    print("Simple Native 7-Zip vs Buffered Python Performance Test")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        test_data_dir = temp_path / "test_data"
        
        # Create test data
        print("Creating test data (20 files, 1MB each = 20MB total)...")
        total_size = create_test_files(test_data_dir, count=20, size_mb=1)
        print(f"Test data created: {total_size / (1024*1024):.1f} MB")
        
        # Test Native 7zip
        native_speed, native_error = test_native_7zip(test_data_dir, total_size)
        
        # Test Buffered Python
        buffered_speed, buffered_error = test_buffered_python(test_data_dir, total_size)
        
        # Results
        print("\n" + "=" * 60)
        print("RESULTS:")
        print("=" * 60)
        
        if native_speed:
            print(f"Native 7-Zip:     {native_speed:8.1f} MB/s")
        else:
            print(f"Native 7-Zip:     FAILED - {native_error}")
        
        if buffered_speed:
            print(f"Buffered Python:  {buffered_speed:8.1f} MB/s")
        else:
            print(f"Buffered Python:  FAILED - {buffered_error}")
        
        if native_speed and buffered_speed:
            improvement = native_speed / buffered_speed
            print(f"\nPerformance Improvement: {improvement:.1f}x faster with Native 7-Zip")
            
            if improvement >= 7:
                print("SUCCESS: Achieved 7x+ performance improvement!")
            elif improvement >= 2:
                print("GOOD: Significant performance improvement achieved.")
            else:
                print("NOTE: Lower than expected improvement.")
        
        print("=" * 60)


if __name__ == "__main__":
    main()