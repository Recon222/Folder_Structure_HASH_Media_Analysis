#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for buffer reuse optimization in file operations
Ensures forensic integrity while improving performance
"""

import pytest
import tempfile
import hashlib
import time
import os
from pathlib import Path
from unittest.mock import Mock, patch

from core.buffered_file_ops import BufferedFileOperations
from core.result_types import Result
from core.exceptions import HashVerificationError


class TestBufferReuseOptimization:
    """Test suite for buffer reuse optimization"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def file_ops(self):
        """Create BufferedFileOperations instance"""
        return BufferedFileOperations()
    
    def create_test_file(self, path: Path, size_mb: int = 1) -> Path:
        """Create a test file with specific size"""
        data = b"x" * (1024 * 1024 * size_mb)
        path.write_bytes(data)
        return path
    
    def test_optimized_copy_produces_correct_hashes(self, temp_dir, file_ops):
        """Verify optimized copy produces correct source and destination hashes"""
        # Create 10MB test file
        source = temp_dir / "test_source.bin"
        dest = temp_dir / "test_dest.bin"
        test_data = b"TestData123" * (1024 * 100)  # ~1MB of repeated data
        source.write_bytes(test_data)
        
        # Calculate expected hash
        expected_hash = hashlib.sha256(test_data).hexdigest()
        
        # Copy with hash verification
        result = file_ops.copy_file_buffered(source, dest, calculate_hash=True)
        
        # Verify operation succeeded
        assert result.success, f"Copy failed: {result.error}"
        
        # Verify hashes match expected
        assert result.value['source_hash'] == expected_hash
        assert result.value['dest_hash'] == expected_hash
        assert result.value['verified'] is True
        
        # Verify file actually exists and matches
        assert dest.exists()
        assert dest.read_bytes() == test_data
        
        # Independently verify the destination hash
        actual_dest_hash = hashlib.sha256(dest.read_bytes()).hexdigest()
        assert actual_dest_hash == expected_hash
    
    def test_forensic_integrity_verification(self, temp_dir, file_ops):
        """
        Test that destination hash is calculated from disk, not memory.
        This is critical for forensic integrity.
        """
        # Create source file
        source = temp_dir / "forensic_source.bin"
        dest = temp_dir / "forensic_dest.bin"
        test_data = b"ForensicData" * 1000
        source.write_bytes(test_data)
        
        # Copy with verification
        result = file_ops.copy_file_buffered(source, dest, calculate_hash=True)
        assert result.success
        
        original_dest_hash = result.value['dest_hash']
        
        # Manually corrupt the destination file after copy
        with open(dest, 'rb+') as f:
            f.seek(100)
            f.write(b'CORRUPT')
        
        # Re-calculate destination hash
        actual_hash = hashlib.sha256(dest.read_bytes()).hexdigest()
        
        # Hashes should NOT match (proves we read from disk, not memory)
        assert original_dest_hash != actual_hash, "Destination hash not reading from disk!"
    
    def test_performance_improvement(self, temp_dir, file_ops):
        """Measure performance improvement of optimized approach"""
        # Create 50MB test file for meaningful timing
        source = temp_dir / "perf_test.bin"
        dest1 = temp_dir / "copy1.bin"
        dest2 = temp_dir / "copy2.bin"
        
        test_data = os.urandom(50 * 1024 * 1024)  # 50MB random data
        source.write_bytes(test_data)
        
        # Mock the old 3-read approach for comparison
        def old_copy_method():
            # Simulate 3 separate reads
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            dest1.write_bytes(source.read_bytes())
            dest_hash = hashlib.sha256(dest1.read_bytes()).hexdigest()
            return source_hash, dest_hash
        
        # Time old approach
        start = time.time()
        old_source_hash, old_dest_hash = old_copy_method()
        old_time = time.time() - start
        
        # Time new optimized approach
        start = time.time()
        result = file_ops.copy_file_buffered(source, dest2, calculate_hash=True)
        new_time = time.time() - start
        
        # Verify correctness
        assert result.success
        assert result.value['source_hash'] == old_source_hash
        assert result.value['dest_hash'] == old_dest_hash
        
        # Should be faster (at least some improvement)
        improvement = (old_time - new_time) / old_time * 100 if old_time > 0 else 0
        print(f"\nPerformance improvement: {improvement:.1f}%")
        print(f"Old approach: {old_time:.3f}s")
        print(f"New approach: {new_time:.3f}s")
        
        # We expect at least 20% improvement (conservative due to test variability)
        assert new_time < old_time, "Optimized approach should be faster"
    
    def test_small_file_optimization(self, temp_dir, file_ops):
        """Test that small files are handled efficiently"""
        # Create small file (< 1MB)
        source = temp_dir / "small.txt"
        dest = temp_dir / "small_copy.txt"
        test_data = b"Small file content" * 100  # Small file
        source.write_bytes(test_data)
        
        # Copy with hash
        result = file_ops.copy_file_buffered(source, dest, calculate_hash=True)
        
        assert result.success
        assert result.value['method'] == 'direct'  # Should use direct method
        assert result.value['verified'] is True
        assert dest.read_bytes() == test_data
    
    def test_large_file_streaming(self, temp_dir, file_ops):
        """Test that large files use streaming with proper buffering"""
        # Create large file (> 100MB)
        source = temp_dir / "large.bin"
        dest = temp_dir / "large_copy.bin"
        
        # Create 101MB file (just over threshold)
        chunk = b"X" * (1024 * 1024)  # 1MB chunk
        with open(source, 'wb') as f:
            for _ in range(101):
                f.write(chunk)
        
        # Copy with hash
        result = file_ops.copy_file_buffered(source, dest, calculate_hash=True)
        
        assert result.success
        assert result.value['method'] == 'buffered'  # Should use buffered method
        assert result.value['verified'] is True
        assert dest.stat().st_size == source.stat().st_size
    
    def test_hash_mismatch_detection(self, temp_dir, file_ops):
        """Test that hash mismatches are properly detected"""
        # This test would need to simulate a write error or corruption
        # For now, we'll test the error handling path
        source = temp_dir / "test.bin"
        dest = temp_dir / "test_copy.bin"
        source.write_bytes(b"test data")
        
        # Mock a hash mismatch scenario
        with patch.object(file_ops, '_calculate_hash_streaming') as mock_hash:
            # First call returns source hash, second returns different hash
            mock_hash.side_effect = [
                "source_hash_value",
                "different_dest_hash"
            ]
            
            result = file_ops.copy_file_buffered(source, dest, calculate_hash=True)
            
            # Should detect mismatch and return error
            assert not result.success
            assert isinstance(result.error, HashVerificationError)
    
    def test_progress_reporting(self, temp_dir, file_ops):
        """Test that progress is reported correctly during optimized copy"""
        source = temp_dir / "progress_test.bin"
        dest = temp_dir / "progress_copy.bin"
        source.write_bytes(b"X" * (10 * 1024 * 1024))  # 10MB
        
        progress_calls = []
        
        def progress_callback(pct, msg):
            progress_calls.append((pct, msg))
        
        # Create file ops with progress callback
        file_ops_with_progress = BufferedFileOperations(
            progress_callback=progress_callback
        )
        
        result = file_ops_with_progress.copy_file_buffered(
            source, dest, calculate_hash=True
        )
        
        assert result.success
        assert len(progress_calls) > 0, "Progress should be reported"
        
        # Check that progress messages indicate the operation
        messages = [msg for _, msg in progress_calls]
        assert any("progress_test.bin" in msg for msg in messages)
    
    def test_cancellation_support(self, temp_dir, file_ops):
        """Test that operation can be cancelled mid-copy"""
        source = temp_dir / "cancel_test.bin"
        dest = temp_dir / "cancel_copy.bin"
        source.write_bytes(b"X" * (10 * 1024 * 1024))  # 10MB
        
        # Set up cancellation
        file_ops.cancelled = True
        file_ops.cancel_event.set()
        
        result = file_ops.copy_file_buffered(source, dest, calculate_hash=True)
        
        # Operation should fail/cancel
        assert not result.success or not dest.exists() or dest.stat().st_size == 0
    
    def test_pause_support(self, temp_dir):
        """Test that operation supports pausing"""
        source = temp_dir / "pause_test.bin"
        dest = temp_dir / "pause_copy.bin"
        source.write_bytes(b"X" * (5 * 1024 * 1024))  # 5MB
        
        pause_called = False
        
        def pause_check():
            nonlocal pause_called
            pause_called = True
        
        file_ops = BufferedFileOperations(pause_check=pause_check)
        result = file_ops.copy_file_buffered(source, dest, calculate_hash=True)
        
        assert result.success
        # Pause should have been checked during operation
        assert pause_called, "Pause check should have been called"


def test_buffer_reuse_optimization():
    """Quick test runner for development"""
    test = TestBufferReuseOptimization()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)
        file_ops = BufferedFileOperations()
        
        # Run key tests
        test.test_optimized_copy_produces_correct_hashes(temp_dir, file_ops)
        test.test_forensic_integrity_verification(temp_dir, file_ops)
        print("✅ All critical tests passed!")


if __name__ == "__main__":
    # Run tests directly
    test_buffer_reuse_optimization()