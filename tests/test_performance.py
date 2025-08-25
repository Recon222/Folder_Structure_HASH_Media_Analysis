#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance benchmarking tests for Phase 5 optimization
Tests buffered vs non-buffered file operations
"""

import pytest
import tempfile
import time
import os
from pathlib import Path
from typing import List, Tuple

from core.buffered_file_ops import BufferedFileOperations, PerformanceMetrics
from core.settings_manager import SettingsManager


class TestPerformance:
    """Performance benchmark tests"""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary source and destination directories"""
        with tempfile.TemporaryDirectory() as src_dir:
            with tempfile.TemporaryDirectory() as dst_dir:
                yield Path(src_dir), Path(dst_dir)
    
    @pytest.fixture
    def small_files(self, temp_dirs) -> List[Path]:
        """Create small test files (<1MB)"""
        src_dir, _ = temp_dirs
        files = []
        
        # Create 10 small files (100KB each)
        for i in range(10):
            file_path = src_dir / f"small_{i}.dat"
            file_path.write_bytes(os.urandom(100 * 1024))  # 100KB
            files.append(file_path)
        
        return files
    
    @pytest.fixture
    def medium_files(self, temp_dirs) -> List[Path]:
        """Create medium test files (1-100MB)"""
        src_dir, _ = temp_dirs
        files = []
        
        # Create 5 medium files (10MB each)
        for i in range(5):
            file_path = src_dir / f"medium_{i}.dat"
            file_path.write_bytes(os.urandom(10 * 1024 * 1024))  # 10MB
            files.append(file_path)
        
        return files
    
    @pytest.fixture
    def large_file(self, temp_dirs) -> Path:
        """Create a large test file (>100MB)"""
        src_dir, _ = temp_dirs
        file_path = src_dir / "large.dat"
        
        # Create 150MB file in chunks to avoid memory issues
        chunk_size = 10 * 1024 * 1024  # 10MB chunks
        total_size = 150 * 1024 * 1024  # 150MB total
        
        with open(file_path, 'wb') as f:
            bytes_written = 0
            while bytes_written < total_size:
                chunk = os.urandom(min(chunk_size, total_size - bytes_written))
                f.write(chunk)
                bytes_written += len(chunk)
        
        return file_path
    
    def test_buffered_small_files_performance(self, small_files, temp_dirs):
        """Test performance of buffered operations with small files"""
        _, dst_dir = temp_dirs
        
        # Test buffered operations
        buffered_ops = BufferedFileOperations()
        buffered_start = time.time()
        buffered_results = buffered_ops.copy_files(
            small_files,
            dst_dir / "buffered",
            calculate_hash=True
        )
        buffered_time = time.time() - buffered_start
        
        # Assertions
        assert len(buffered_results) >= len(small_files)
        
        # Performance metrics should be included
        assert '_performance_stats' in buffered_results
        metrics = buffered_results['_performance_stats']
        assert metrics['files_processed'] == len(small_files)
        assert metrics['mode'] == 'buffered'
        
        # Log performance results
        print(f"\nSmall Files Performance:")
        print(f"  Buffered: {buffered_time:.2f}s")
        print(f"  Speed: {metrics['average_speed_mbps']:.1f} MB/s")
        print(f"  Files processed: {metrics['files_processed']}")
    
    def test_buffered_large_file_streaming(self, large_file, temp_dirs):
        """Test streaming performance for large files"""
        _, dst_dir = temp_dirs
        
        # Test with different buffer sizes
        buffer_sizes = [8 * 1024, 256 * 1024, 1024 * 1024, 5 * 1024 * 1024]  # 8KB, 256KB, 1MB, 5MB
        results = {}
        
        for buffer_size in buffer_sizes:
            buffered_ops = BufferedFileOperations()
            
            start_time = time.time()
            result = buffered_ops.copy_file_buffered(
                large_file,
                dst_dir / f"large_{buffer_size}.dat",
                buffer_size=buffer_size,
                calculate_hash=True
            )
            duration = time.time() - start_time
            
            results[buffer_size] = {
                'duration': duration,
                'speed_mbps': result.get('speed_mbps', 0),
                'verified': result.get('verified', False)
            }
            
            # Clean up
            (dst_dir / f"large_{buffer_size}.dat").unlink()
        
        # Print results
        print(f"\nLarge File Streaming Performance (150MB file):")
        for buffer_size, metrics in results.items():
            print(f"  Buffer {buffer_size // 1024}KB: {metrics['duration']:.2f}s @ {metrics['speed_mbps']:.1f} MB/s")
        
        # Verify all copies were successful
        assert all(r['verified'] for r in results.values())
        
        # Larger buffers should generally be faster for large files
        small_buffer_time = results[8 * 1024]['duration']
        large_buffer_time = results[5 * 1024 * 1024]['duration']
        assert large_buffer_time <= small_buffer_time * 1.2  # Allow 20% variance
    
    def test_memory_efficiency(self, large_file, temp_dirs):
        """Test that buffered operations don't exhaust memory"""
        _, dst_dir = temp_dirs
        
        # Get initial memory usage
        import psutil
        process = psutil.Process()
        initial_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        # Copy large file with buffering
        buffered_ops = BufferedFileOperations()
        buffered_ops.copy_file_buffered(
            large_file,
            dst_dir / "large_copy.dat",
            buffer_size=1024 * 1024,  # 1MB buffer
            calculate_hash=True
        )
        
        # Check memory after copy
        peak_memory = process.memory_info().rss / (1024 * 1024)  # MB
        memory_increase = peak_memory - initial_memory
        
        print(f"\nMemory Usage:")
        print(f"  Initial: {initial_memory:.1f} MB")
        print(f"  Peak: {peak_memory:.1f} MB")
        print(f"  Increase: {memory_increase:.1f} MB")
        
        # Memory increase should be reasonable (not loading entire file)
        file_size_mb = large_file.stat().st_size / (1024 * 1024)
        assert memory_increase < file_size_mb * 0.2  # Should use less than 20% of file size
    
    def test_cancellation(self, medium_files, temp_dirs):
        """Test that operations can be cancelled mid-stream"""
        _, dst_dir = temp_dirs
        
        buffered_ops = BufferedFileOperations()
        
        # Start copy in a thread and cancel after short delay
        import threading
        
        def copy_task():
            buffered_ops.copy_files(
                medium_files * 10,  # Repeat files to make operation longer
                dst_dir / "cancelled",
                calculate_hash=True
            )
        
        thread = threading.Thread(target=copy_task)
        thread.start()
        
        # Cancel after 0.1 seconds
        time.sleep(0.1)
        buffered_ops.cancel()
        
        # Wait for thread to finish
        thread.join(timeout=2.0)
        
        # Operation should have been cancelled
        assert buffered_ops.cancelled
        
        # Some files may have been copied but not all
        copied_files = list((dst_dir / "cancelled").glob("*")) if (dst_dir / "cancelled").exists() else []
        assert len(copied_files) < len(medium_files) * 10
    
    def test_progress_reporting(self, medium_files, temp_dirs):
        """Test that progress is reported correctly"""
        _, dst_dir = temp_dirs
        
        progress_updates = []
        
        def progress_callback(percentage: int, message: str):
            progress_updates.append((percentage, message))
        
        buffered_ops = BufferedFileOperations(progress_callback=progress_callback)
        buffered_ops.copy_files(
            medium_files,
            dst_dir / "progress_test",
            calculate_hash=True
        )
        
        # Should have received progress updates
        assert len(progress_updates) > 0
        
        # Progress should go from 0 to 100
        percentages = [p for p, _ in progress_updates]
        assert min(percentages) >= 0
        assert max(percentages) == 100
        
        # Messages should include speed info
        speed_messages = [m for _, m in progress_updates if "MB/s" in m]
        assert len(speed_messages) > 0
    
    def test_metrics_collection(self, small_files, medium_files, temp_dirs):
        """Test performance metrics collection"""
        _, dst_dir = temp_dirs
        
        all_files = small_files + medium_files
        
        buffered_ops = BufferedFileOperations()
        results = buffered_ops.copy_files(
            all_files,
            dst_dir / "metrics_test",
            calculate_hash=True
        )
        
        # Check metrics
        metrics = buffered_ops.get_metrics()
        assert metrics.files_processed == len(all_files)
        assert metrics.small_files_count == len(small_files)
        assert metrics.medium_files_count == len(medium_files)
        assert metrics.average_speed_mbps > 0
        assert metrics.peak_speed_mbps >= metrics.average_speed_mbps
        
        # Check performance report in results
        perf_metrics = results['_performance_stats']
        assert perf_metrics['files_processed'] == len(all_files)
        assert perf_metrics['mode'] == 'buffered'


class TestIntegration:
    """Integration tests for performance features"""
    
    def test_settings_integration(self):
        """Test that settings properly control buffered operations"""
        settings = SettingsManager()
        
        # Check default is enabled
        # Buffered operations are now always enabled (no setting needed)
        
        # Test buffer size clamping
        assert 8192 <= settings.copy_buffer_size <= 10485760
        
        # Buffered operations are now always enabled (no setting toggle available)


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])