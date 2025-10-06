#!/usr/bin/env python3
"""
Integration tests for same-drive move optimization
"""

import unittest
import tempfile
import shutil
from pathlib import Path

from core.buffered_file_ops import BufferedFileOperations
from core.settings_manager import SettingsManager


class TestSameDriveMoveOptimization(unittest.TestCase):
    """Test same-drive move optimization"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.source_dir = self.test_dir / "source"
        self.dest_dir = self.test_dir / "dest"
        self.source_dir.mkdir()
        self.dest_dir.mkdir()

        # Create test files
        self.test_files = []
        for i in range(5):
            test_file = self.source_dir / f"test_{i}.txt"
            test_file.write_text(f"Test content {i}")
            self.test_files.append(test_file)

        self.ops = BufferedFileOperations()
        self.settings = SettingsManager()

    def tearDown(self):
        """Clean up test fixtures"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_same_drive_detection(self):
        """Test that same-drive detection works"""
        # Same drive
        same = self.ops._is_same_filesystem(self.source_dir, self.dest_dir)
        self.assertTrue(same, "Should detect same filesystem")

    def test_move_files_basic(self):
        """Test basic move operation"""
        items = [('file', f, f.name) for f in self.test_files]

        result = self.ops.move_files_preserving_structure(
            list(items),
            self.dest_dir,
            calculate_hash=False
        )

        self.assertTrue(result.success, "Move should succeed")
        self.assertEqual(result.files_processed, 5, "Should move 5 files")

        # Verify files moved
        for test_file in self.test_files:
            self.assertFalse(test_file.exists(), f"Source should not exist: {test_file}")
            dest_file = self.dest_dir / test_file.name
            self.assertTrue(dest_file.exists(), f"Dest should exist: {dest_file}")

    def test_move_with_hash_verification(self):
        """Test move with hash calculation"""
        items = [('file', self.test_files[0], self.test_files[0].name)]

        result = self.ops.move_files_preserving_structure(
            items,
            self.dest_dir,
            calculate_hash=True
        )

        self.assertTrue(result.success, "Move with hash should succeed")

        # Verify hash in results
        file_result = result.value[self.test_files[0].name]
        self.assertIn('dest_hash', file_result, "Should have dest_hash")
        self.assertTrue(file_result['verified'], "Should be verified")
        self.assertEqual(file_result['operation'], 'move', "Should be move operation")

    def test_settings_auto_move(self):
        """Test auto_move setting"""
        self.settings.same_drive_behavior = 'auto_move'

        items = [('file', self.test_files[0], self.test_files[0].name)]

        result = self.ops.move_files_preserving_structure(items, self.dest_dir)

        self.assertTrue(result.success)
        self.assertEqual(result.value['_performance_stats']['operation_mode'], 'move')

    def test_settings_auto_copy(self):
        """Test auto_copy setting (forces copy even on same drive)"""
        self.settings.same_drive_behavior = 'auto_copy'

        items = [('file', self.test_files[0], self.test_files[0].name)]

        result = self.ops.move_files_preserving_structure(items, self.dest_dir)

        self.assertTrue(result.success)
        # Should have copied, so source still exists
        self.assertTrue(self.test_files[0].exists(), "Source should still exist with auto_copy")

    def test_rollback_on_failure(self):
        """Test that rollback works on failure"""
        # Create a scenario that will fail
        items = [
            ('file', self.test_files[0], self.test_files[0].name),
            ('file', Path("/nonexistent/file.txt"), "file.txt")  # This will fail
        ]

        result = self.ops.move_files_preserving_structure(items, self.dest_dir)

        self.assertFalse(result.success, "Should fail on nonexistent file")

        # Verify first file was rolled back
        self.assertTrue(self.test_files[0].exists(), "First file should be rolled back")
        dest_file = self.dest_dir / self.test_files[0].name
        self.assertFalse(dest_file.exists(), "Dest file should not exist after rollback")

    def test_operation_mode_in_results(self):
        """Test that operation mode is recorded in results"""
        self.settings.same_drive_behavior = 'auto_move'
        items = [('file', self.test_files[0], self.test_files[0].name)]

        result = self.ops.move_files_preserving_structure(items, self.dest_dir)

        self.assertTrue(result.success)
        # Check individual file result
        file_result = result.value[self.test_files[0].name]
        self.assertEqual(file_result['operation'], 'move')

        # Check performance stats
        perf_stats = result.value.get('_performance_stats')
        self.assertIsNotNone(perf_stats)
        self.assertEqual(perf_stats['operation_mode'], 'move')


if __name__ == '__main__':
    unittest.main()
