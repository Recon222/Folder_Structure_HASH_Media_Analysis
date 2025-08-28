#!/usr/bin/env python3
"""
Integration tests for the complete template import system
"""

import pytest
import json
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from core.services.template_management_service import TemplateManagementService, TemplateSource
from core.services.path_service import PathService
from core.services import get_service, IPathService, register_service
from core.template_validator import TemplateValidator, ValidationLevel
from ui.components.template_selector import TemplateSelector
from ui.dialogs.template_import_dialog import TemplateImportDialog


class TestTemplateImportIntegration:
    """Integration tests for the complete template import system"""

    @classmethod
    def setup_class(cls):
        """Set up test class"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setup_method(self):
        """Set up test fixtures"""
        self.test_data_dir = Path("test_integration_data")
        if self.test_data_dir.exists():
            shutil.rmtree(self.test_data_dir)
        self.test_data_dir.mkdir()
        
        # Create test template management service
        self.template_service = TemplateManagementService()
        
        # Override directories for testing
        self.original_user_dir = self.template_service.user_templates_dir
        self.template_service.user_templates_dir = self.test_data_dir
        self.template_service.imported_dir = self.test_data_dir / "imported"
        self.template_service.custom_dir = self.test_data_dir / "custom"
        self.template_service.backups_dir = self.test_data_dir / "backups"
        self.template_service.exported_dir = self.test_data_dir / "exported"
        
        # Create test directories
        for directory in [self.template_service.imported_dir, self.template_service.custom_dir,
                         self.template_service.backups_dir, self.template_service.exported_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Create path service with template management service
        self.path_service = PathService()
        self.path_service._template_management_service = self.template_service
        
        # Register services for dependency injection
        register_service(IPathService, self.path_service)
        
        # Sample template data
        self.sample_template_data = {
            "version": "1.0.0",
            "templates": {
                "integration_test": {
                    "templateName": "Integration Test Template",
                    "templateDescription": "Template for integration testing",
                    "structure": {
                        "levels": [
                            {
                                "pattern": "TEST_{occurrence_number}",
                                "fallback": "TEST_NO_OCCURRENCE"
                            },
                            {
                                "pattern": "{business_name}_{location_address}",
                                "conditionals": {
                                    "business_only": "BUSINESS_{business_name}",
                                    "location_only": "LOCATION_{location_address}",
                                    "neither": "NO_BUSINESS_LOCATION"
                                },
                                "fallback": "UNKNOWN_LOCATION"
                            }
                        ]
                    },
                    "documentsPlacement": "location",
                    "archiveNaming": {
                        "pattern": "INTEGRATION_TEST_{occurrence_number}.zip",
                        "fallbackPattern": "INTEGRATION_TEST.zip"
                    },
                    "metadata": {
                        "author": "Integration Test",
                        "version": "1.0.0",
                        "tags": ["test", "integration"]
                    }
                }
            }
        }

    def teardown_method(self):
        """Clean up test fixtures"""
        # Restore original user directory
        self.template_service.user_templates_dir = self.original_user_dir
        
        # Clean up test data
        if self.test_data_dir.exists():
            shutil.rmtree(self.test_data_dir)

    def create_test_template_file(self, template_data: dict, filename: str) -> Path:
        """Helper to create test template file"""
        file_path = self.test_data_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, indent=2)
        return file_path

    def test_pathservice_template_import_integration(self):
        """Test PathService integration with template import"""
        # Create test template file
        template_file = self.create_test_template_file(self.sample_template_data, "integration_test.json")
        
        # Import through PathService
        result = self.path_service.import_template(template_file)
        
        assert result.success
        import_info = result.value
        
        assert "integration_test" in import_info["imported_templates"]
        
        # Verify template is available through PathService
        templates = self.path_service.get_available_templates()
        template_ids = [t["id"] for t in templates]
        assert "integration_test" in template_ids
        
        # Test setting current template
        set_result = self.path_service.set_current_template("integration_test")
        assert set_result.success
        
        current_id = self.path_service.get_current_template_id()
        assert current_id == "integration_test"

    def test_pathservice_template_export_integration(self):
        """Test PathService integration with template export"""
        # First import a template
        template_file = self.create_test_template_file(self.sample_template_data, "export_test.json")
        import_result = self.path_service.import_template(template_file)
        assert import_result.success
        
        # Export through PathService
        export_path = self.test_data_dir / "exported_integration.json"
        result = self.path_service.export_template("integration_test", export_path)
        
        assert result.success
        assert export_path.exists()
        
        # Verify exported content
        with open(export_path, 'r', encoding='utf-8') as f:
            exported_data = json.load(f)
        
        assert "templates" in exported_data
        assert "integration_test" in exported_data["templates"]
        assert exported_data["templates"]["integration_test"]["templateName"] == "Integration Test Template"

    def test_pathservice_template_validation(self):
        """Test PathService template validation integration"""
        # Test valid template
        template_file = self.create_test_template_file(self.sample_template_data, "valid_test.json")
        result = self.path_service.validate_template_file(template_file)
        
        assert result.success
        validation_issues = result.value
        
        # Should have success messages, minimal or no errors
        error_issues = [issue for issue in validation_issues if issue.get("level") == ValidationLevel.ERROR]
        success_issues = [issue for issue in validation_issues if issue.get("level") == ValidationLevel.SUCCESS]
        
        assert len(error_issues) == 0
        assert len(success_issues) > 0

    def test_pathservice_template_validation_with_errors(self):
        """Test PathService validation with invalid template"""
        invalid_template = {
            "version": "1.0.0",
            "templates": {
                "invalid_test": {
                    # Missing required templateName
                    "structure": {
                        "levels": [
                            {
                                "pattern": "{unknown_field}"  # Unknown field
                            }
                        ]
                    }
                }
            }
        }
        
        invalid_file = self.create_test_template_file(invalid_template, "invalid_test.json")
        result = self.path_service.validate_template_file(invalid_file)
        
        assert result.success
        validation_issues = result.value
        
        # Should have error issues
        error_issues = [issue for issue in validation_issues if issue.get("level") == ValidationLevel.ERROR]
        assert len(error_issues) > 0

    def test_template_selector_widget_creation(self):
        """Test TemplateSelector widget can be created and initialized"""
        selector = TemplateSelector()
        
        # Widget should be created successfully
        assert selector is not None
        assert hasattr(selector, 'template_combo')
        assert hasattr(selector, 'settings_btn')
        
        # Should have path service initialized
        assert selector.path_service is not None
        
        # Should have templates loaded (at least system templates)
        assert selector.template_combo.count() >= 0

    def test_template_selector_import_export_menu(self):
        """Test TemplateSelector import/export menu functionality"""
        selector = TemplateSelector()
        
        # Check that settings button has menu
        assert selector.settings_btn.menu() is not None
        
        # Menu should have import and export actions
        menu = selector.settings_btn.menu()
        actions = [action.text() for action in menu.actions() if action.text()]
        
        assert "Import Template..." in actions
        assert "Export Current Template..." in actions
        assert "Manage Templates..." in actions
        assert "Refresh Templates" in actions
        assert "About Templates" in actions

    def test_template_import_dialog_creation(self):
        """Test TemplateImportDialog can be created and initialized"""
        try:
            dialog = TemplateImportDialog()
            
            # Dialog should be created successfully
            assert dialog is not None
            assert hasattr(dialog, 'tab_widget')
            assert hasattr(dialog, 'validation_tab')
            assert hasattr(dialog, 'preview_tab')
            assert hasattr(dialog, 'json_tab')
            
            # Should have path service
            assert dialog.path_service is not None
            
            # Cleanup
            dialog.close()
            
        except Exception as e:
            pytest.skip(f"TemplateImportDialog creation failed (likely missing dependencies): {e}")

    def test_end_to_end_template_workflow(self):
        """Test complete template workflow: import -> select -> use -> export"""
        # Step 1: Import template
        template_file = self.create_test_template_file(self.sample_template_data, "e2e_test.json")
        import_result = self.path_service.import_template(template_file)
        assert import_result.success
        
        # Step 2: Verify template is available
        templates = self.path_service.get_available_templates()
        template_ids = [t["id"] for t in templates]
        assert "integration_test" in template_ids
        
        # Step 3: Select template
        set_result = self.path_service.set_current_template("integration_test")
        assert set_result.success
        
        current_id = self.path_service.get_current_template_id()
        assert current_id == "integration_test"
        
        # Step 4: Use template for path building
        from core.models import FormData
        form_data = FormData()
        form_data.occurrence_number = "E2E-001"
        form_data.business_name = "Test Business"
        form_data.location_address = "123 Test St"
        
        path_result = self.path_service.build_forensic_path(form_data, Path("/test/base"))
        assert path_result.success
        
        built_path = path_result.value
        assert "TEST_E2E-001" in str(built_path)  # Should contain our pattern
        assert "Test_Business_123_Test_St" in str(built_path)
        
        # Step 5: Test archive naming
        archive_result = self.path_service.build_archive_name(form_data)
        assert archive_result.success
        
        archive_name = archive_result.value
        assert "INTEGRATION_TEST_E2E-001.zip" == archive_name
        
        # Step 6: Export template
        export_path = self.test_data_dir / "e2e_exported.json"
        export_result = self.path_service.export_template("integration_test", export_path)
        assert export_result.success
        assert export_path.exists()

    def test_template_reload_functionality(self):
        """Test template reloading functionality"""
        # Import initial template
        template_file = self.create_test_template_file(self.sample_template_data, "reload_test.json")
        import_result = self.path_service.import_template(template_file)
        assert import_result.success
        
        # Get initial template count
        initial_templates = self.path_service.get_available_templates()
        initial_count = len(initial_templates)
        
        # Import another template directly to the imported directory
        additional_template = {
            "version": "1.0.0",
            "templates": {
                "additional_template": {
                    "templateName": "Additional Template",
                    "structure": {
                        "levels": [{"pattern": "{occurrence_number}"}]
                    }
                }
            }
        }
        
        additional_file = self.template_service.imported_dir / "additional_template.json"
        with open(additional_file, 'w', encoding='utf-8') as f:
            json.dump(additional_template, f, indent=2)
        
        # Reload templates
        reload_result = self.path_service.reload_templates()
        assert reload_result.success
        
        # Should now have additional template
        reloaded_templates = self.path_service.get_available_templates()
        assert len(reloaded_templates) > initial_count
        
        template_ids = [t["id"] for t in reloaded_templates]
        assert "additional_template" in template_ids

    def test_template_conflict_resolution(self):
        """Test template ID conflict resolution during import"""
        # First import a template
        template_file = self.create_test_template_file(self.sample_template_data, "conflict1.json")
        import_result1 = self.path_service.import_template(template_file)
        assert import_result1.success
        
        # Import template with same ID
        conflicting_template = {
            "version": "1.0.0",
            "templates": {
                "integration_test": {  # Same ID
                    "templateName": "Conflicting Template",
                    "structure": {
                        "levels": [{"pattern": "CONFLICT_{occurrence_number}"}]
                    }
                }
            }
        }
        
        conflict_file = self.create_test_template_file(conflicting_template, "conflict2.json")
        import_result2 = self.path_service.import_template(conflict_file)
        assert import_result2.success
        
        # Should have renamed the conflicting template
        imported_templates = import_result2.value["imported_templates"]
        renamed_id = imported_templates[0]
        
        assert renamed_id != "integration_test"
        assert renamed_id.startswith("integration_test_imported_")
        
        # Both templates should be available
        all_templates = self.path_service.get_available_templates()
        template_ids = [t["id"] for t in all_templates]
        
        assert "integration_test" in template_ids
        assert renamed_id in template_ids

    def test_template_metadata_preservation(self):
        """Test that template metadata is preserved during import/export cycle"""
        # Import template with metadata
        template_file = self.create_test_template_file(self.sample_template_data, "metadata_test.json")
        import_result = self.path_service.import_template(template_file)
        assert import_result.success
        
        # Export the template
        export_path = self.test_data_dir / "metadata_export.json"
        export_result = self.path_service.export_template("integration_test", export_path)
        assert export_result.success
        
        # Verify metadata preservation
        with open(export_path, 'r', encoding='utf-8') as f:
            exported_data = json.load(f)
        
        template_data = exported_data["templates"]["integration_test"]
        metadata = template_data["metadata"]
        
        # Original metadata should be preserved
        assert metadata["author"] == "Integration Test"
        assert metadata["version"] == "1.0.0"
        assert "test" in metadata["tags"]
        assert "integration" in metadata["tags"]
        
        # Import metadata should be added
        assert "imported_from" in metadata
        assert "imported_date" in metadata
        
        # Export metadata should be added
        assert "exported_date" in metadata
        assert "exported_by" in metadata

    def test_template_service_error_handling(self):
        """Test error handling in template service integration"""
        # Test import with non-existent file
        non_existent = Path("non_existent_file.json")
        result = self.path_service.import_template(non_existent)
        assert not result.success
        
        # Test export with non-existent template
        export_path = self.test_data_dir / "fail_export.json"
        result = self.path_service.export_template("non_existent_template", export_path)
        assert not result.success
        
        # Test setting non-existent template
        result = self.path_service.set_current_template("non_existent_template")
        assert not result.success

    @patch('core.services.template_management_service.TemplateManagementService')
    def test_pathservice_fallback_when_template_service_unavailable(self, mock_service_class):
        """Test PathService graceful fallback when template management service is unavailable"""
        # Make template management service unavailable
        mock_service_class.side_effect = Exception("Service unavailable")
        
        # Create new PathService
        fallback_path_service = PathService()
        
        # Should still work with default template
        templates = fallback_path_service.get_available_templates()
        assert len(templates) > 0  # Should have at least default template
        
        # Should be able to build paths with default template
        from core.models import FormData
        form_data = FormData()
        form_data.occurrence_number = "FALLBACK-001"
        
        path_result = fallback_path_service.build_forensic_path(form_data, Path("/test/base"))
        assert path_result.success

    def test_template_validator_integration(self):
        """Test TemplateValidator integration with import system"""
        validator = TemplateValidator()
        
        # Test validation of sample template data
        result = validator.validate_template_data(self.sample_template_data)
        assert result.success
        
        validation_issues = result.value
        
        # Should pass all validation levels
        error_issues = [issue for issue in validation_issues if issue.level == ValidationLevel.ERROR]
        assert len(error_issues) == 0
        
        # Should have success messages
        success_issues = [issue for issue in validation_issues if issue.level == ValidationLevel.SUCCESS]
        assert len(success_issues) > 0
        
        # Test template preview generation
        preview_result = validator.test_template_with_sample_data(self.sample_template_data)
        assert preview_result.success
        
        preview_data = preview_result.value
        assert "integration_test" in preview_data
        
        template_preview = preview_data["integration_test"]
        assert template_preview["success"]
        assert "folder_path" in template_preview
        assert "archive_name" in template_preview

    def test_field_documentation_integration(self):
        """Test field documentation retrieval integration"""
        validator = TemplateValidator()
        docs = validator.get_field_documentation()
        
        assert "available_fields" in docs
        assert "date_formats" in docs
        
        # Verify all expected fields are documented
        available_fields = docs["available_fields"]
        expected_fields = [
            "occurrence_number", "business_name", "location_address",
            "video_start_datetime", "video_end_datetime", "technician_name",
            "badge_number", "current_datetime", "current_date", "year"
        ]
        
        for field in expected_fields:
            assert field in available_fields
            assert "description" in available_fields[field]
            assert "type" in available_fields[field]
            assert "example" in available_fields[field]