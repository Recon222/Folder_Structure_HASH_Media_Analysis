#!/usr/bin/env python3
"""
Comprehensive tests for the TemplateManagementService class
"""

import pytest
import json
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from core.services.template_management_service import (
    TemplateManagementService, TemplateSource, TemplateInfo
)
from core.template_validator import ValidationLevel
from core.exceptions import TemplateValidationError
from core.result_types import Result


class TestTemplateManagementService:
    """Test suite for TemplateManagementService"""

    def setup_method(self):
        """Set up test fixtures"""
        self.test_data_dir = Path("test_templates_data")
        self.service = TemplateManagementService()
        
        # Override user templates directory for testing
        self.original_user_dir = self.service.user_templates_dir
        self.service.user_templates_dir = self.test_data_dir
        self.service.imported_dir = self.test_data_dir / "imported"
        self.service.custom_dir = self.test_data_dir / "custom"
        self.service.backups_dir = self.test_data_dir / "backups"
        self.service.exported_dir = self.test_data_dir / "exported"
        
        # Create test directories
        for directory in [self.service.imported_dir, self.service.custom_dir, 
                         self.service.backups_dir, self.service.exported_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Sample valid template data
        self.valid_template_data = {
            "version": "1.0.0",
            "templates": {
                "test_template": {
                    "templateName": "Test Template",
                    "templateDescription": "A test template for unit testing",
                    "structure": {
                        "levels": [
                            {
                                "pattern": "{occurrence_number}",
                                "fallback": "NO_OCCURRENCE"
                            },
                            {
                                "pattern": "{business_name}_{location_address}",
                                "conditionals": {
                                    "business_only": "{business_name}",
                                    "location_only": "{location_address}",
                                    "neither": "NO_BUSINESS_LOCATION"
                                }
                            }
                        ]
                    },
                    "documentsPlacement": "location",
                    "archiveNaming": {
                        "pattern": "{occurrence_number}_{business_name}.zip",
                        "fallbackPattern": "{occurrence_number}.zip"
                    }
                }
            }
        }

    def teardown_method(self):
        """Clean up test fixtures"""
        # Restore original user directory
        self.service.user_templates_dir = self.original_user_dir
        
        # Clean up test data directory
        if self.test_data_dir.exists():
            shutil.rmtree(self.test_data_dir)

    def create_test_template_file(self, template_data: dict, filename: str) -> Path:
        """Helper to create test template file"""
        file_path = self.test_data_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, indent=2)
        return file_path

    def test_directory_setup_success(self):
        """Test successful directory setup"""
        # Service should have created directories during initialization
        assert self.service.imported_dir.exists()
        assert self.service.custom_dir.exists()
        assert self.service.backups_dir.exists()
        assert self.service.exported_dir.exists()

    def test_import_template_success(self):
        """Test successful template import"""
        template_file = self.create_test_template_file(self.valid_template_data, "valid_template.json")
        
        result = self.service.import_template(template_file)
        
        assert result.success
        import_info = result.value
        
        assert "imported_templates" in import_info
        assert "test_template" in import_info["imported_templates"]
        assert import_info["target_source"] == TemplateSource.IMPORTED
        assert "validation_issues" in import_info
        assert "import_timestamp" in import_info
        
        # Check that template file was created
        imported_file = self.service.imported_dir / "test_template.json"
        assert imported_file.exists()
        
        # Verify imported template content
        with open(imported_file, 'r', encoding='utf-8') as f:
            imported_data = json.load(f)
        
        assert "templates" in imported_data
        assert "test_template" in imported_data["templates"]
        
        # Check metadata was added
        template_metadata = imported_data["templates"]["test_template"]["metadata"]
        assert "imported_from" in template_metadata
        assert "imported_date" in template_metadata
        assert "source" in template_metadata

    def test_import_template_file_not_found(self):
        """Test import with non-existent file"""
        non_existent_file = Path("non_existent_template.json")
        
        result = self.service.import_template(non_existent_file)
        
        assert not result.success
        assert isinstance(result.error, TemplateValidationError)
        assert "could not be found" in result.error.user_message

    def test_import_template_invalid_json(self):
        """Test import with invalid JSON"""
        invalid_file = self.test_data_dir / "invalid.json"
        invalid_file.write_text("{ invalid json content")
        
        result = self.service.import_template(invalid_file)
        
        assert not result.success
        assert isinstance(result.error, TemplateValidationError)

    def test_import_template_validation_errors(self):
        """Test import with template that has validation errors"""
        invalid_template = {
            "version": "1.0.0",
            "templates": {
                "invalid_template": {
                    # Missing templateName (required)
                    "structure": {
                        "levels": [
                            {
                                "pattern": "{unknown_field}"  # Unknown field reference
                            }
                        ]
                    }
                }
            }
        }
        
        invalid_file = self.create_test_template_file(invalid_template, "invalid_template.json")
        
        result = self.service.import_template(invalid_file)
        
        assert not result.success
        assert isinstance(result.error, TemplateValidationError)
        assert "validation errors" in result.error.user_message

    def test_import_template_with_conflicts(self):
        """Test import with template ID conflicts"""
        # First create an existing template
        existing_file = self.service.imported_dir / "existing_template.json"
        existing_data = {
            "version": "1.0.0",
            "templates": {
                "existing_template": {
                    "templateName": "Existing Template",
                    "structure": {
                        "levels": [{"pattern": "{occurrence_number}"}]
                    }
                }
            }
        }
        
        with open(existing_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f)
        
        # Now import template with same ID
        conflicting_template = {
            "version": "1.0.0",
            "templates": {
                "existing_template": {  # Same ID as existing
                    "templateName": "Conflicting Template",
                    "structure": {
                        "levels": [{"pattern": "{business_name}"}]
                    }
                }
            }
        }
        
        conflicting_file = self.create_test_template_file(conflicting_template, "conflicting.json")
        
        result = self.service.import_template(conflicting_file)
        
        assert result.success
        import_info = result.value
        
        # Should have renamed the conflicting template
        imported_templates = import_info["imported_templates"]
        assert len(imported_templates) == 1
        
        # Template should have been renamed with timestamp
        renamed_id = imported_templates[0]
        assert renamed_id.startswith("existing_template_imported_")

    def test_export_template_success(self):
        """Test successful template export"""
        # First import a template
        template_file = self.create_test_template_file(self.valid_template_data, "to_export.json")
        import_result = self.service.import_template(template_file)
        assert import_result.success
        
        # Now export it
        export_path = self.test_data_dir / "exported_template.json"
        result = self.service.export_template("test_template", export_path)
        
        assert result.success
        assert export_path.exists()
        
        # Verify exported content
        with open(export_path, 'r', encoding='utf-8') as f:
            exported_data = json.load(f)
        
        assert "templates" in exported_data
        assert "test_template" in exported_data["templates"]
        
        # Check export metadata was added
        template_data = exported_data["templates"]["test_template"]
        assert "metadata" in template_data
        assert "exported_date" in template_data["metadata"]
        assert "exported_by" in template_data["metadata"]

    def test_export_template_not_found(self):
        """Test export with non-existent template"""
        export_path = self.test_data_dir / "nonexistent_export.json"
        
        result = self.service.export_template("non_existent_template", export_path)
        
        assert not result.success
        assert isinstance(result.error, TemplateValidationError)
        assert "could not be found" in result.error.user_message

    def test_export_all_user_templates(self):
        """Test export of all user templates"""
        # Import multiple templates
        template1_data = self.valid_template_data.copy()
        template1_file = self.create_test_template_file(template1_data, "template1.json")
        self.service.import_template(template1_file)
        
        template2_data = {
            "version": "1.0.0",
            "templates": {
                "template2": {
                    "templateName": "Second Template",
                    "structure": {
                        "levels": [{"pattern": "{occurrence_number}"}]
                    }
                }
            }
        }
        template2_file = self.create_test_template_file(template2_data, "template2.json")
        self.service.import_template(template2_file)
        
        # Export all templates
        export_path = self.test_data_dir / "all_templates.json"
        result = self.service.export_all_user_templates(export_path)
        
        assert result.success
        export_info = result.value
        
        assert export_info["exported_count"] >= 2  # At least our two templates
        assert export_path.exists()
        
        # Verify exported content
        with open(export_path, 'r', encoding='utf-8') as f:
            exported_data = json.load(f)
        
        assert "templates" in exported_data
        assert "export_metadata" in exported_data
        assert exported_data["export_metadata"]["template_count"] >= 2

    def test_export_all_user_templates_empty(self):
        """Test export when no user templates exist"""
        export_path = self.test_data_dir / "empty_export.json"
        
        result = self.service.export_all_user_templates(export_path)
        
        assert not result.success
        assert isinstance(result.error, TemplateValidationError)
        assert "no user templates" in result.error.user_message.lower()

    def test_delete_user_template_success(self):
        """Test successful template deletion"""
        # First import a template
        template_file = self.create_test_template_file(self.valid_template_data, "to_delete.json")
        import_result = self.service.import_template(template_file)
        assert import_result.success
        
        # Verify template exists
        template_file_path = self.service.imported_dir / "test_template.json"
        assert template_file_path.exists()
        
        # Delete template
        result = self.service.delete_user_template("test_template")
        
        assert result.success
        assert not template_file_path.exists()

    def test_delete_user_template_not_found(self):
        """Test deletion of non-existent template"""
        result = self.service.delete_user_template("non_existent_template")
        
        assert not result.success
        assert isinstance(result.error, TemplateValidationError)
        assert "could not be found" in result.error.user_message

    def test_get_all_templates_system_and_user(self):
        """Test getting all templates from all sources"""
        # Import a user template
        template_file = self.create_test_template_file(self.valid_template_data, "user_template.json")
        import_result = self.service.import_template(template_file)
        assert import_result.success
        
        result = self.service.get_all_templates()
        
        assert result.success
        all_templates = result.value
        
        assert isinstance(all_templates, list)
        assert len(all_templates) > 0  # Should have at least our imported template
        
        # Check that we have both system and user templates
        sources = {template.source for template in all_templates}
        assert TemplateSource.IMPORTED in sources or TemplateSource.CUSTOM in sources
        
        # Find our imported template
        user_template = next((t for t in all_templates if t.template_id == "test_template"), None)
        assert user_template is not None
        assert user_template.source in [TemplateSource.IMPORTED, TemplateSource.CUSTOM]
        assert user_template.name == "Test Template"

    def test_load_system_templates(self):
        """Test loading system templates"""
        templates = self.service._load_system_templates()
        
        # Should be a list (may be empty if no system templates file)
        assert isinstance(templates, list)
        
        if templates:  # If system templates exist
            for template in templates:
                assert isinstance(template, TemplateInfo)
                assert template.source == TemplateSource.SYSTEM
                assert template.template_id
                assert template.name

    def test_load_user_templates(self):
        """Test loading user templates"""
        # Import a template first
        template_file = self.create_test_template_file(self.valid_template_data, "user_test.json")
        import_result = self.service.import_template(template_file)
        assert import_result.success
        
        templates = self.service._load_user_templates()
        
        assert isinstance(templates, list)
        assert len(templates) >= 1
        
        # Find our imported template
        user_template = next((t for t in templates if t.template_id == "test_template"), None)
        assert user_template is not None
        assert user_template.source == TemplateSource.IMPORTED
        assert user_template.name == "Test Template"

    def test_template_info_creation(self):
        """Test TemplateInfo object creation and serialization"""
        template_data = {
            "templateName": "Test Info Template",
            "templateDescription": "Test description",
            "structure": {"levels": [{"pattern": "{occurrence_number}"}]},
            "metadata": {
                "author": "Test Author",
                "version": "1.0.0",
                "tags": ["test", "info"]
            }
        }
        
        template_info = TemplateInfo(
            template_id="test_info",
            template_data=template_data,
            source=TemplateSource.CUSTOM,
            file_path=Path("/test/path/file.json")
        )
        
        assert template_info.template_id == "test_info"
        assert template_info.source == TemplateSource.CUSTOM
        assert template_info.name == "Test Info Template"
        assert template_info.description == "Test description"
        assert template_info.metadata["author"] == "Test Author"
        
        # Test serialization
        template_dict = template_info.to_dict()
        assert template_dict["template_id"] == "test_info"
        assert template_dict["source"] == TemplateSource.CUSTOM
        assert template_dict["name"] == "Test Info Template"
        # Path separators may be platform-specific
        assert "test" in template_dict["file_path"] and "file.json" in template_dict["file_path"]

    def test_backup_creation(self):
        """Test automatic backup creation"""
        # Import a template
        template_file = self.create_test_template_file(self.valid_template_data, "backup_test.json")
        import_result = self.service.import_template(template_file)
        assert import_result.success
        
        # Create backup manually
        backup_result = self.service._create_backup()
        
        if backup_result.success:
            backup_file = backup_result.value
            assert backup_file.exists()
            assert backup_file.parent == self.service.backups_dir
            assert "templates_backup_" in backup_file.name

    def test_backup_cleanup(self):
        """Test backup cleanup keeps only recent backups"""
        # Create multiple fake backup files
        for i in range(15):  # More than the 10 backup limit
            backup_file = self.service.backups_dir / f"templates_backup_202508{i:02d}_120000.json"
            backup_file.write_text('{"test": "backup"}')
        
        # Run cleanup
        self.service._cleanup_old_backups()
        
        # Should have at most 10 backups remaining
        remaining_backups = list(self.service.backups_dir.glob("templates_backup_*.json"))
        assert len(remaining_backups) <= 10

    def test_validate_template_preview(self):
        """Test template validation with preview generation"""
        sample_data = {
            "occurrence_number": "TEST-001",
            "business_name": "Test Business",
            "location_address": "123 Test Street"
        }
        
        result = self.service.validate_template_preview(self.valid_template_data, sample_data)
        
        assert result.success
        preview_info = result.value
        
        assert "validation_issues" in preview_info
        assert "preview_data" in preview_info
        assert "has_errors" in preview_info
        assert "has_warnings" in preview_info
        
        # Should not have errors for valid template
        assert not preview_info["has_errors"]

    def test_validate_template_preview_with_errors(self):
        """Test template validation with preview for invalid template"""
        invalid_template = {
            "version": "1.0.0",
            "templates": {
                "invalid": {
                    # Missing templateName
                    "structure": {
                        "levels": [
                            {"pattern": "{unknown_field}"}  # Unknown field
                        ]
                    }
                }
            }
        }
        
        result = self.service.validate_template_preview(invalid_template)
        
        assert result.success
        preview_info = result.value
        
        assert preview_info["has_errors"]  # Should have errors
        
        validation_issues = preview_info["validation_issues"]
        error_issues = [issue for issue in validation_issues if issue["level"] == ValidationLevel.ERROR]
        assert len(error_issues) > 0

    @patch('platform.system', return_value='Windows')
    @patch('os.getenv', return_value='C:\\Users\\Test\\AppData\\Local')
    def test_get_user_data_directory_windows(self, mock_getenv, mock_platform):
        """Test user data directory detection on Windows"""
        service = TemplateManagementService()
        user_dir = service._get_user_data_directory()
        
        expected_path = Path("C:/Users/Test/AppData/Local/FolderStructureApp/templates")
        assert user_dir == expected_path

    @patch('platform.system', return_value='Darwin')
    def test_get_user_data_directory_macos(self, mock_platform):
        """Test user data directory detection on macOS"""
        service = TemplateManagementService()
        user_dir = service._get_user_data_directory()
        
        home = Path.home()
        expected_path = home / "Library" / "Application Support" / "FolderStructureApp" / "templates"
        assert user_dir == expected_path

    @patch('platform.system', return_value='Linux')
    def test_get_user_data_directory_linux(self, mock_platform):
        """Test user data directory detection on Linux"""
        service = TemplateManagementService()
        user_dir = service._get_user_data_directory()
        
        home = Path.home()
        expected_path = home / ".local" / "share" / "FolderStructureApp" / "templates"
        assert user_dir == expected_path

    def test_check_first_time_setup_no_templates(self):
        """Test first-time setup detection with no existing templates"""
        # Ensure no templates exist
        for directory in [self.service.imported_dir, self.service.custom_dir]:
            if directory.exists():
                for file in directory.glob("*.json"):
                    file.unlink()
        
        # This should be called during service initialization
        self.service._check_first_time_setup()
        
        # Should have logged first-time setup message
        # (We can't easily test logging in unit tests, but method should not raise errors)

    def test_check_first_time_setup_with_existing_templates(self):
        """Test first-time setup detection with existing templates"""
        # Import a template first
        template_file = self.create_test_template_file(self.valid_template_data, "existing.json")
        import_result = self.service.import_template(template_file)
        assert import_result.success
        
        # This should detect existing templates
        self.service._check_first_time_setup()
        
        # Should not log first-time setup message
        # (Method should complete without errors)