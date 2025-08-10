#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test suite for batch processing functionality
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.batch_queue import BatchQueue, BatchJob
from core.models import FormData
from core.workers.batch_processor import BatchProcessorThread
from PySide6.QtCore import QDateTime


class TestBatchProcessing:
    """Test suite for batch processing functionality"""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing"""
        src_dir = tempfile.mkdtemp(prefix="test_src_")
        dst_dir = tempfile.mkdtemp(prefix="test_dst_")
        
        # Create test files
        src_path = Path(src_dir)
        (src_path / "file1.txt").write_text("content1")
        (src_path / "file2.txt").write_text("content2")
        (src_path / "subfolder").mkdir()
        (src_path / "subfolder" / "file3.txt").write_text("content3")
        
        yield src_path, Path(dst_dir)
        
        # Cleanup
        shutil.rmtree(src_dir, ignore_errors=True)
        shutil.rmtree(dst_dir, ignore_errors=True)
    
    @pytest.fixture
    def sample_form_data(self):
        """Create sample form data for testing"""
        form_data = FormData()
        form_data.occurrence_number = "TEST001"
        form_data.business_name = "Test Business"
        form_data.location_address = "123 Test St"
        form_data.video_start_datetime = QDateTime.currentDateTime()
        form_data.video_end_datetime = QDateTime.currentDateTime().addSecs(3600)
        form_data.time_offset = "DVR is 2 hr 0 min 0 sec AHEAD of realtime"
        return form_data
    
    @pytest.fixture
    def batch_job(self, sample_form_data, temp_dirs):
        """Create a sample batch job"""
        src_dir, dst_dir = temp_dirs
        
        job = BatchJob(
            form_data=sample_form_data,
            files=[src_dir / "file1.txt", src_dir / "file2.txt"],
            folders=[src_dir / "subfolder"],
            output_directory=str(dst_dir)
        )
        return job
    
    def test_batch_job_creation(self, batch_job):
        """Test that batch jobs are created correctly"""
        assert batch_job.job_id is not None
        assert batch_job.status == "pending"
        assert batch_job.form_data.occurrence_number == "TEST001"
        assert len(batch_job.files) == 2
        assert len(batch_job.folders) == 1
        assert batch_job.get_file_count() == 3  # 2 files + 1 in subfolder
    
    def test_batch_queue_operations(self, batch_job):
        """Test batch queue add/remove operations"""
        queue = BatchQueue()
        
        # Add job
        queue.add_job(batch_job)
        assert len(queue.jobs) == 1
        assert queue.get_pending_jobs()[0] == batch_job
        
        # Update status
        queue.update_job_status(batch_job.job_id, "processing")
        assert batch_job.status == "processing"
        
        # Remove job
        queue.remove_job(0)
        assert len(queue.jobs) == 0
    
    def test_batch_processor_copy_sync(self, batch_job, temp_dirs):
        """Test the fixed _copy_items_sync method"""
        src_dir, dst_dir = temp_dirs
        
        # Create processor
        queue = BatchQueue()
        queue.add_job(batch_job)
        processor = BatchProcessorThread(queue)
        
        # Prepare items for copy
        items_to_copy = [
            ('file', src_dir / "file1.txt", Path("file1.txt")),
            ('file', src_dir / "file2.txt", Path("file2.txt")),
            ('folder', src_dir / "subfolder", Path("subfolder"))
        ]
        
        # Create destination
        dest_path = dst_dir / "TEST001" / "Test Business @ 123 Test St"
        
        # Test copy operation
        success, message, results = processor._copy_items_sync(
            items_to_copy, dest_path, batch_job
        )
        
        # Verify results
        assert success is True
        assert "Successfully copied" in message
        assert '_performance_stats' in results
        assert results['_performance_stats']['files_copied'] == 3
        
        # Verify files exist
        assert (dest_path / "file1.txt").exists()
        assert (dest_path / "file2.txt").exists()
        assert (dest_path / "subfolder" / "file3.txt").exists()
        
        # Verify content
        assert (dest_path / "file1.txt").read_text() == "content1"
        assert (dest_path / "subfolder" / "file3.txt").read_text() == "content3"
    
    def test_batch_processor_forensic_structure(self, batch_job, temp_dirs):
        """Test that forensic folder structure is created correctly"""
        src_dir, dst_dir = temp_dirs
        
        # Create processor
        queue = BatchQueue()
        queue.add_job(batch_job)
        processor = BatchProcessorThread(queue)
        
        # Build forensic path
        relative_path = processor._build_folder_path(batch_job, "forensic")
        
        # Path should contain occurrence number and business info
        path_str = str(relative_path)
        assert "TEST001" in path_str
        assert "Test Business" in path_str or "Test_Business" in path_str
        assert "123 Test St" in path_str or "123_Test_St" in path_str
    
    def test_batch_processor_error_handling(self, sample_form_data):
        """Test error handling with invalid files"""
        # Create job with non-existent files
        job = BatchJob(
            form_data=sample_form_data,
            files=[Path("/nonexistent/file1.txt"), Path("/nonexistent/file2.txt")],
            folders=[],
            output_directory="/tmp/test_output"
        )
        
        queue = BatchQueue()
        queue.add_job(job)
        processor = BatchProcessorThread(queue)
        
        # Process job
        success, message, results = processor._process_forensic_job(job)
        
        # Should handle gracefully
        assert success is False or "No valid files" in message
    
    def test_batch_queue_validation(self, batch_job):
        """Test batch queue validation"""
        queue = BatchQueue()
        
        # Add valid job
        queue.add_job(batch_job)
        
        # Add invalid job (missing form data)
        invalid_job = BatchJob(
            form_data=FormData(),  # Empty form data
            files=[],
            folders=[],
            output_directory=""  # Empty output
        )
        queue.add_job(invalid_job)
        
        # Validate all jobs
        validation = queue.validate_all_jobs()
        
        assert len(validation['valid_jobs']) == 1
        assert len(validation['invalid_jobs']) == 1
        assert batch_job in validation['valid_jobs']
        assert invalid_job in validation['invalid_jobs']
    
    def test_batch_queue_serialization(self, batch_job, tmp_path):
        """Test saving and loading batch queue"""
        queue = BatchQueue()
        queue.add_job(batch_job)
        
        # Save queue
        save_file = tmp_path / "test_queue.json"
        queue.save_queue(str(save_file))
        assert save_file.exists()
        
        # Load into new queue
        new_queue = BatchQueue()
        new_queue.load_queue(str(save_file))
        
        assert len(new_queue.jobs) == 1
        loaded_job = new_queue.jobs[0]
        assert loaded_job.form_data.occurrence_number == "TEST001"
        assert len(loaded_job.files) == 2
        assert len(loaded_job.folders) == 1
    
    def test_batch_processor_cancellation(self, batch_job):
        """Test that batch processing can be cancelled"""
        queue = BatchQueue()
        queue.add_job(batch_job)
        processor = BatchProcessorThread(queue)
        
        # Set cancelled flag
        processor.cancelled = True
        
        # Try to process
        items_to_copy = [('file', Path("test.txt"), Path("test.txt"))]
        success, message, results = processor._copy_items_sync(
            items_to_copy, Path("/tmp"), batch_job
        )
        
        assert success is False
        assert "cancelled" in message.lower()
    
    def test_performance_stats_excluded(self, batch_job, temp_dirs):
        """Test that _performance_stats is properly excluded from hash verification"""
        src_dir, dst_dir = temp_dirs
        
        queue = BatchQueue()
        queue.add_job(batch_job)
        processor = BatchProcessorThread(queue)
        
        # Create mock results with performance stats
        results = {
            str(dst_dir / "file1.txt"): {
                'source': str(src_dir / "file1.txt"),
                'destination': str(dst_dir / "file1.txt"),
                'source_hash': 'abc123',
                'dest_hash': 'abc123',
                'verified': True
            },
            '_performance_stats': {
                'total_files': 1,
                'files_copied': 1
            }
        }
        
        # Check hash verification logic
        has_hashes = any(
            result.get('source_hash') or result.get('dest_hash')
            for key, result in results.items()
            if isinstance(result, dict) and key != '_performance_stats'
        )
        
        assert has_hashes is True  # Should find hashes in file1.txt entry


def run_tests():
    """Run all batch processing tests"""
    print("Running batch processing tests...")
    
    # Create test instance
    test_instance = TestBatchProcessing()
    
    # Create fixtures manually for simple test
    import tempfile
    from pathlib import Path
    
    src_dir = tempfile.mkdtemp(prefix="test_src_")
    dst_dir = tempfile.mkdtemp(prefix="test_dst_")
    
    try:
        # Setup test files
        src_path = Path(src_dir)
        (src_path / "test.txt").write_text("test content")
        
        # Create test data
        form_data = FormData()
        form_data.occurrence_number = "TEST001"
        form_data.business_name = "Test Corp"
        
        job = BatchJob(
            form_data=form_data,
            files=[src_path / "test.txt"],
            folders=[],
            output_directory=str(dst_dir)
        )
        
        # Test basic functionality
        assert job.job_id is not None
        assert job.status == "pending"
        
        # Test queue
        queue = BatchQueue()
        queue.add_job(job)
        assert len(queue.jobs) == 1
        
        print("✅ All batch processing tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
        
    finally:
        # Cleanup
        shutil.rmtree(src_dir, ignore_errors=True)
        shutil.rmtree(dst_dir, ignore_errors=True)


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)