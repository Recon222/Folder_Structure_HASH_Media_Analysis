#!/usr/bin/env python3
"""
Unit tests for refactored PathService methods
Tests the new business logic extracted from MainWindow
"""
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import tempfile
import shutil

from core.services.path_service import PathService
from core.result_types import Result
from core.exceptions import FileOperationError


class TestPathServiceRefactor(unittest.TestCase):
    """Test the new PathService methods extracted from MainWindow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.service = PathService()
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
    def tearDown(self):
        """Clean up test fixtures"""
        # Remove the temporary directory
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_find_occurrence_folder_simple_structure(self):
        """Test finding occurrence folder in a simple directory structure"""
        # Create test structure: output/occurrence/business/datetime/file.txt
        output_dir = self.test_path / "output"
        occurrence_dir = output_dir / "2024-001"
        business_dir = occurrence_dir / "TestBusiness @ 123 Main St"
        datetime_dir = business_dir / "2024-01-15_1030"
        datetime_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = datetime_dir / "test.txt"
        file_path.touch()
        
        # Test finding occurrence folder from file path
        result = self.service.find_occurrence_folder(file_path, output_dir)
        
        self.assertTrue(result.success)
        self.assertEqual(result.value, occurrence_dir)
        
    def test_find_occurrence_folder_from_directory(self):
        """Test finding occurrence folder when starting from a directory"""
        # Create test structure
        output_dir = self.test_path / "output"
        occurrence_dir = output_dir / "2024-002"
        business_dir = occurrence_dir / "Business"
        business_dir.mkdir(parents=True, exist_ok=True)
        
        # Test from business directory
        result = self.service.find_occurrence_folder(business_dir, output_dir)
        
        self.assertTrue(result.success)
        self.assertEqual(result.value, occurrence_dir)
        
    def test_find_occurrence_folder_already_at_occurrence(self):
        """Test when we're already at the occurrence folder"""
        output_dir = self.test_path / "output"
        occurrence_dir = output_dir / "2024-003"
        occurrence_dir.mkdir(parents=True, exist_ok=True)
        
        result = self.service.find_occurrence_folder(occurrence_dir, output_dir)
        
        self.assertTrue(result.success)
        self.assertEqual(result.value, occurrence_dir)
        
    def test_find_occurrence_folder_error_no_occurrence(self):
        """Test error when occurrence folder cannot be found"""
        # Create a path that doesn't follow the expected structure
        output_dir = self.test_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Use output_dir as both path and root (invalid structure)
        result = self.service.find_occurrence_folder(output_dir, output_dir)
        
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, FileOperationError)
        # Check for either error message (both are valid for this case)
        self.assertTrue(
            "no occurrence folder found" in result.error.message.lower() or
            "could not find occurrence folder" in result.error.message.lower()
        )
        
    def test_navigate_to_occurrence_folder_alias(self):
        """Test that navigate_to_occurrence_folder is an alias for find_occurrence_folder"""
        output_dir = self.test_path / "output"
        occurrence_dir = output_dir / "2024-004"
        occurrence_dir.mkdir(parents=True, exist_ok=True)
        
        # Both methods should return the same result
        result1 = self.service.find_occurrence_folder(occurrence_dir, output_dir)
        result2 = self.service.navigate_to_occurrence_folder(occurrence_dir, output_dir)
        
        self.assertEqual(result1.success, result2.success)
        self.assertEqual(result1.value, result2.value)
        
    def test_determine_documents_location_occurrence_level(self):
        """Test documents placement at occurrence level"""
        # Setup structure
        output_dir = self.test_path / "output"
        occurrence_dir = output_dir / "2024-005"
        business_dir = occurrence_dir / "Business"
        datetime_dir = business_dir / "DateTime"
        datetime_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = datetime_dir / "file.txt"
        file_path.touch()
        
        # Mock template with occurrence placement
        with patch.object(self.service, '_templates', {
            self.service._current_template_id: {
                'documentsPlacement': 'occurrence'
            }
        }):
            result = self.service.determine_documents_location(file_path, output_dir)
        
        self.assertTrue(result.success)
        expected_docs_dir = occurrence_dir / "Documents"
        self.assertEqual(result.value, expected_docs_dir)
        self.assertTrue(expected_docs_dir.exists())
        
    def test_determine_documents_location_location_level(self):
        """Test documents placement at location/business level (default)"""
        # Setup structure
        output_dir = self.test_path / "output"
        occurrence_dir = output_dir / "2024-006"
        business_dir = occurrence_dir / "TestBusiness"
        datetime_dir = business_dir / "2024-01-15"
        datetime_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = datetime_dir / "file.txt"
        file_path.touch()
        
        # Mock template with location placement (default)
        with patch.object(self.service, '_templates', {
            self.service._current_template_id: {
                'documentsPlacement': 'location'
            }
        }):
            result = self.service.determine_documents_location(file_path, output_dir)
        
        self.assertTrue(result.success)
        expected_docs_dir = business_dir / "Documents"
        self.assertEqual(result.value, expected_docs_dir)
        self.assertTrue(expected_docs_dir.exists())
        
    def test_determine_documents_location_datetime_level(self):
        """Test documents placement at datetime level"""
        # Setup structure
        output_dir = self.test_path / "output"
        occurrence_dir = output_dir / "2024-007"
        business_dir = occurrence_dir / "Business"
        datetime_dir = business_dir / "DateTime"
        datetime_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = datetime_dir / "file.txt"
        file_path.touch()
        
        # Mock template with datetime placement
        with patch.object(self.service, '_templates', {
            self.service._current_template_id: {
                'documentsPlacement': 'datetime'
            }
        }):
            result = self.service.determine_documents_location(file_path, output_dir)
        
        self.assertTrue(result.success)
        expected_docs_dir = datetime_dir / "Documents"
        self.assertEqual(result.value, expected_docs_dir)
        self.assertTrue(expected_docs_dir.exists())
        
    def test_determine_documents_location_default_fallback(self):
        """Test documents placement falls back to location level when no template"""
        # Setup structure
        output_dir = self.test_path / "output"
        occurrence_dir = output_dir / "2024-008"
        business_dir = occurrence_dir / "Business"
        datetime_dir = business_dir / "DateTime"
        datetime_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = datetime_dir / "file.txt"
        file_path.touch()
        
        # Clear templates to test fallback
        with patch.object(self.service, '_templates', {}):
            result = self.service.determine_documents_location(file_path, output_dir)
        
        self.assertTrue(result.success)
        # Should default to location level
        expected_docs_dir = business_dir / "Documents"
        self.assertEqual(result.value, expected_docs_dir)
        self.assertTrue(expected_docs_dir.exists())
        
    def test_determine_documents_location_invalid_placement(self):
        """Test documents placement with invalid placement value falls back to location"""
        # Setup structure
        output_dir = self.test_path / "output"
        occurrence_dir = output_dir / "2024-009"
        business_dir = occurrence_dir / "Business"
        datetime_dir = business_dir / "DateTime"
        datetime_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = datetime_dir / "file.txt"
        file_path.touch()
        
        # Mock template with invalid placement
        with patch.object(self.service, '_templates', {
            self.service._current_template_id: {
                'documentsPlacement': 'invalid_value'
            }
        }):
            result = self.service.determine_documents_location(file_path, output_dir)
        
        self.assertTrue(result.success)
        # Should default to location level
        expected_docs_dir = business_dir / "Documents"
        self.assertEqual(result.value, expected_docs_dir)
        self.assertTrue(expected_docs_dir.exists())
        
    def test_determine_documents_location_creates_directory(self):
        """Test that determine_documents_location creates the Documents directory"""
        # Setup structure
        output_dir = self.test_path / "output"
        occurrence_dir = output_dir / "2024-010"
        business_dir = occurrence_dir / "Business"
        datetime_dir = business_dir / "DateTime"
        datetime_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = datetime_dir / "file.txt"
        file_path.touch()
        
        # Ensure Documents doesn't exist yet
        docs_dir = business_dir / "Documents"
        self.assertFalse(docs_dir.exists())
        
        result = self.service.determine_documents_location(file_path, output_dir)
        
        self.assertTrue(result.success)
        self.assertTrue(docs_dir.exists())
        
    def test_determine_documents_location_handles_find_error(self):
        """Test that determine_documents_location handles errors from find_occurrence_folder"""
        # Create invalid structure
        output_dir = self.test_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        result = self.service.determine_documents_location(output_dir, output_dir)
        
        # Should fail because find_occurrence_folder will fail
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, FileOperationError)


class TestPathServiceIntegration(unittest.TestCase):
    """Integration tests for PathService with real templates"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.service = PathService()
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
    def tearDown(self):
        """Clean up test fixtures"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
            
    def test_full_workflow_with_templates(self):
        """Test the full workflow of path operations with template support"""
        # Create a complex directory structure
        output_dir = self.test_path / "forensic_output"
        occurrence = "2024-CASE-001"
        business = "Evidence Corp"
        location = "123 Main Street"
        
        # Build the structure that would be created by file operations
        occurrence_dir = output_dir / occurrence
        business_dir = occurrence_dir / f"{business} @ {location}"
        datetime_dir = business_dir / "2024-01-15_1430_to_2024-01-15_1530_DVR_Time"
        datetime_dir.mkdir(parents=True, exist_ok=True)
        
        # Simulate a file that was copied
        evidence_file = datetime_dir / "evidence.mp4"
        evidence_file.touch()
        
        # Test 1: Find occurrence folder from deep in the structure
        occurrence_result = self.service.find_occurrence_folder(evidence_file, output_dir)
        self.assertTrue(occurrence_result.success)
        self.assertEqual(occurrence_result.value.name, occurrence)
        
        # Test 2: Determine documents location with different placements
        # Test occurrence level
        with patch.object(self.service, '_templates', {
            self.service._current_template_id: {'documentsPlacement': 'occurrence'}
        }):
            docs_result = self.service.determine_documents_location(evidence_file, output_dir)
            self.assertTrue(docs_result.success)
            self.assertEqual(docs_result.value.parent, occurrence_dir)
            
        # Test location level
        with patch.object(self.service, '_templates', {
            self.service._current_template_id: {'documentsPlacement': 'location'}
        }):
            docs_result = self.service.determine_documents_location(evidence_file, output_dir)
            self.assertTrue(docs_result.success)
            self.assertEqual(docs_result.value.parent, business_dir)
            
        # Test datetime level
        with patch.object(self.service, '_templates', {
            self.service._current_template_id: {'documentsPlacement': 'datetime'}
        }):
            docs_result = self.service.determine_documents_location(evidence_file, output_dir)
            self.assertTrue(docs_result.success)
            self.assertEqual(docs_result.value.parent, datetime_dir)
            
    def test_edge_cases(self):
        """Test edge cases and error conditions"""
        # Test with non-existent path
        fake_path = Path("/non/existent/path")
        fake_output = Path("/non/existent/output")
        
        result = self.service.find_occurrence_folder(fake_path, fake_output)
        self.assertFalse(result.success)
        
        # Test with path outside of output directory
        outside_path = self.test_path / "outside" / "structure"
        output_dir = self.test_path / "output"
        outside_path.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        result = self.service.find_occurrence_folder(outside_path, output_dir)
        self.assertFalse(result.success)


if __name__ == '__main__':
    unittest.main()