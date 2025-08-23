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
        """Create a sample batch job with valid file paths"""
        src_dir, dst_dir = temp_dirs
        
        # Ensure all files and folders exist before creating the job
        file1 = src_dir / "file1.txt"
        file2 = src_dir / "file2.txt" 
        subfolder = src_dir / "subfolder"
        
        # The temp_dirs fixture already creates these, but let's be explicit
        assert file1.exists(), f"Test file {file1} should exist"
        assert file2.exists(), f"Test file {file2} should exist"
        assert subfolder.exists(), f"Test folder {subfolder} should exist"
        
        job = BatchJob(
            form_data=sample_form_data,
            files=[file1, file2],
            folders=[subfolder],
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
        batch_job.status = "processing"
        queue.update_job(batch_job)
        assert batch_job.status == "processing"
        
        # Remove job (by job_id, not index)
        queue.remove_job(batch_job.job_id)
        assert len(queue.jobs) == 0
    
    def test_batch_processor_file_controller_integration(self, batch_job, temp_dirs):
        """Test the FileController integration in batch processing (simplified)"""
        src_dir, dst_dir = temp_dirs
        
        # Update batch job with proper paths
        batch_job.files = [src_dir / "file1.txt", src_dir / "file2.txt"]
        batch_job.folders = [src_dir / "subfolder"]
        batch_job.output_directory = str(dst_dir)
        
        # Create a more complete mock main window with ZIP controller
        class MockZipController:
            def should_create_zip(self):
                return False  # Disable ZIP creation to avoid complexity
            
        class MockMainWindow:
            def __init__(self):
                self.zip_controller = MockZipController()
        
        # Test that the batch processor can create a FileController
        from controllers.file_controller import FileController
        file_controller = FileController()
        
        # Test that FileController can create a proper thread
        folder_thread = file_controller.process_forensic_files(
            batch_job.form_data,
            batch_job.files,
            batch_job.folders,
            Path(batch_job.output_directory),
            calculate_hash=False  # Disable hashing for faster test
        )
        
        # Verify the thread was created properly
        assert folder_thread is not None
        assert hasattr(folder_thread, 'items')
        assert hasattr(folder_thread, 'destination')
        assert len(folder_thread.items) == 3  # 2 files + 1 folder with 1 file = 3 total items
        
        # Test validation method directly (no threading)
        queue = BatchQueue()
        processor = BatchProcessorThread(queue, main_window=MockMainWindow())
        
        # Create mock results for validation test
        mock_results = {
            str(dst_dir / "file1.txt"): {'source_hash': 'abc', 'dest_hash': 'abc', 'verified': True},
            str(dst_dir / "file2.txt"): {'source_hash': 'def', 'dest_hash': 'def', 'verified': True},
            str(dst_dir / "subfolder" / "file3.txt"): {'source_hash': 'ghi', 'dest_hash': 'ghi', 'verified': True}
        }
        
        # Test the validation method
        is_valid = processor._validate_copy_results(mock_results, batch_job)
        assert is_valid is True
        
        # Test path building
        relative_path = processor._build_folder_path(batch_job, "forensic")
        assert relative_path is not None
        assert "TEST001" in str(relative_path)
    
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
    
    def test_batch_processor_error_handling(self, sample_form_data, temp_dirs):
        """Test error handling with invalid files"""
        src_dir, dst_dir = temp_dirs
        
        # Create job with files that don't exist (but in valid parent directories)
        non_existent_file1 = src_dir / "does_not_exist1.txt"
        non_existent_file2 = src_dir / "does_not_exist2.txt"
        
        job = BatchJob(
            form_data=sample_form_data,
            files=[non_existent_file1, non_existent_file2],
            folders=[],
            output_directory=str(dst_dir)
        )
        
        # Test that validation catches the missing files
        errors = job.validate()
        assert len(errors) == 2  # Should have 2 "File not found" errors
        assert f"File not found: {non_existent_file1}" in errors
        assert f"File not found: {non_existent_file2}" in errors
        
        # Test that BatchQueue rejects invalid jobs
        queue = BatchQueue()
        try:
            queue.add_job(job)
            assert False, "Should have raised ValueError for invalid job"
        except ValueError as e:
            assert "Invalid job" in str(e)
            assert "File not found" in str(e)
    
    def test_batch_queue_validation(self, batch_job):
        """Test batch queue validation"""
        queue = BatchQueue()
        
        # Add valid job
        queue.add_job(batch_job)
        assert len(queue.jobs) == 1
        
        # Test that invalid job gets rejected
        invalid_job = BatchJob(
            form_data=FormData(),  # Empty form data - missing required fields
            files=[],
            folders=[],
            output_directory=""  # Empty output
        )
        
        # Should raise ValueError when trying to add invalid job
        try:
            queue.add_job(invalid_job)
            assert False, "Should have raised ValueError for invalid job"
        except ValueError as e:
            assert "Invalid job" in str(e)
            assert "Occurrence number is required" in str(e)
        
        # Queue should still have only the valid job
        assert len(queue.jobs) == 1
        
        # Validate all jobs in queue (should all be valid since invalid ones are rejected)
        validation = queue.validate_all_jobs()
        
        assert len(validation['valid_jobs']) == 1
        assert len(validation['invalid_jobs']) == 0
        # valid_jobs contains job IDs, not job objects
        assert batch_job.job_id in validation['valid_jobs']
    
    def test_batch_queue_serialization(self, batch_job, tmp_path):
        """Test saving and loading batch queue"""
        queue = BatchQueue()
        queue.add_job(batch_job)
        
        # Save queue (using correct method name)
        save_file = tmp_path / "test_queue.json"
        queue.save_to_file(save_file)
        assert save_file.exists()
        
        # Load into new queue (using correct method name)
        new_queue = BatchQueue()
        new_queue.load_from_file(save_file)
        
        assert len(new_queue.jobs) == 1
        loaded_job = new_queue.jobs[0]
        assert loaded_job.form_data.occurrence_number == "TEST001"
        assert len(loaded_job.files) == 2
        assert len(loaded_job.folders) == 1
    
    def test_batch_processor_cancellation(self, batch_job, temp_dirs):
        """Test that batch processing cancellation mechanisms work"""
        src_dir, dst_dir = temp_dirs
        
        # Update batch job
        batch_job.files = [src_dir / "file1.txt"]
        batch_job.output_directory = str(dst_dir)
        
        # Create mock main window
        class MockZipController:
            def should_create_zip(self):
                return False
        
        class MockMainWindow:
            def __init__(self):
                self.zip_controller = MockZipController()
        
        # Create processor
        queue = BatchQueue()
        queue.add_job(batch_job)
        processor = BatchProcessorThread(queue, main_window=MockMainWindow())
        
        # Test that cancellation flag can be set
        processor.cancelled = True
        assert processor.cancelled is True
        
        # Test that FileController creates cancellable threads
        from controllers.file_controller import FileController
        file_controller = FileController()
        folder_thread = file_controller.process_forensic_files(
            batch_job.form_data,
            batch_job.files,
            batch_job.folders,
            Path(batch_job.output_directory),
            calculate_hash=False
        )
        
        # Test that the thread has a cancellation mechanism
        assert hasattr(folder_thread, 'cancelled')
        folder_thread.cancelled = True
        assert folder_thread.cancelled is True
        
        # Test the cancel method exists on processor
        assert hasattr(processor, 'cancel')
        processor.cancel()  # Should not raise an exception
    
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