#!/usr/bin/env python3
"""
Comprehensive tests for the template system
"""

import pytest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime
from PySide6.QtCore import QDateTime, Qt

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import FormData
from core.template_path_builder import TemplatePathBuilder
from core.path_utils import PathSanitizer
from core.services.path_service import PathService
from core.result_types import Result


class TestTemplatePathBuilder:
    """Test the template path builder functionality"""
    
    def setup_method(self):
        """Setup test data"""
        self.sanitizer = PathSanitizer()
        
        # Test form data
        self.form_data = FormData()
        self.form_data.occurrence_number = "2024-TEST-001"
        self.form_data.business_name = "Test Business"
        self.form_data.location_address = "123 Test Street"
        self.form_data.video_start_datetime = QDateTime(2025, 8, 28, 16, 30, 0)
        self.form_data.video_end_datetime = QDateTime(2025, 8, 28, 18, 15, 0)
    
    def test_default_template_structure(self):
        """Test building path with default template"""
        template = {
            "templateName": "Default Forensic Structure",
            "structure": {
                "levels": [
                    {"pattern": "{occurrence_number}", "fallback": "NO_OCCURRENCE"},
                    {
                        "pattern": "{business_name} @ {location_address}",
                        "conditionals": {
                            "business_only": "{business_name}",
                            "location_only": "{location_address}",
                            "neither": "NO_LOCATION"
                        }
                    },
                    {
                        "pattern": "{video_start_datetime}_to_{video_end_datetime}_DVR_Time",
                        "dateFormat": "military",
                        "fallback": "{current_datetime}"
                    }
                ]
            }
        }
        
        builder = TemplatePathBuilder(template, self.sanitizer)
        path = builder.build_relative_path(self.form_data)
        
        # Check structure
        parts = path.parts
        assert len(parts) == 3
        assert parts[0] == "2024-TEST-001"
        assert parts[1] == "Test Business @ 123 Test Street"
        assert "28AUG25_1630_to_28AUG25_1815_DVR_Time" == parts[2]
    
    def test_conditional_patterns(self):
        """Test conditional patterns for business/location"""
        template = {
            "structure": {
                "levels": [
                    {"pattern": "{occurrence_number}"},
                    {
                        "pattern": "{business_name} @ {location_address}",
                        "conditionals": {
                            "business_only": "{business_name}",
                            "location_only": "{location_address}",
                            "neither": "NO_LOCATION"
                        }
                    }
                ]
            }
        }
        
        builder = TemplatePathBuilder(template, self.sanitizer)
        
        # Test business only
        form_data = FormData()
        form_data.occurrence_number = "TEST"
        form_data.business_name = "Business Only"
        form_data.location_address = ""
        
        path = builder.build_relative_path(form_data)
        assert path.parts[1] == "Business Only"
        
        # Test location only
        form_data.business_name = ""
        form_data.location_address = "Location Only"
        
        path = builder.build_relative_path(form_data)
        assert path.parts[1] == "Location Only"
        
        # Test neither
        form_data.business_name = ""
        form_data.location_address = ""
        
        path = builder.build_relative_path(form_data)
        assert path.parts[1] == "NO_LOCATION"
    
    def test_military_date_formatting(self):
        """Test military date formatting"""
        template = {
            "structure": {
                "levels": [
                    {
                        "pattern": "{video_start_datetime}",
                        "dateFormat": "military"
                    }
                ]
            }
        }
        
        builder = TemplatePathBuilder(template, self.sanitizer)
        path = builder.build_relative_path(self.form_data)
        
        # Should be 28AUG25_1630 for the test date
        assert path.parts[0] == "28AUG25_1630"
    
    def test_iso_date_formatting(self):
        """Test ISO date formatting"""
        template = {
            "structure": {
                "levels": [
                    {
                        "pattern": "{video_start_datetime}",
                        "dateFormat": "iso"
                    }
                ]
            }
        }
        
        builder = TemplatePathBuilder(template, self.sanitizer)
        path = builder.build_relative_path(self.form_data)
        
        # Should be 2025-08-28_1630 for the test date
        assert path.parts[0] == "2025-08-28_1630"
    
    def test_fallback_handling(self):
        """Test fallback patterns when data is missing"""
        template = {
            "structure": {
                "levels": [
                    {"pattern": "{missing_field}", "fallback": "FALLBACK_VALUE"},
                    {
                        "pattern": "{video_start_datetime}",
                        "dateFormat": "military",
                        "fallback": "NO_DATE"
                    }
                ]
            }
        }
        
        builder = TemplatePathBuilder(template, self.sanitizer)
        
        # Test with empty form data
        empty_form = FormData()
        path = builder.build_relative_path(empty_form)
        
        assert path.parts[0] == "FALLBACK_VALUE"
        assert path.parts[1] == "NO_DATE"


class TestPathService:
    """Test the PathService with template integration"""
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        
        # Create a test template file
        self.templates_dir = self.base_path / "templates"
        self.templates_dir.mkdir(exist_ok=True)
        
        test_templates = {
            "version": "1.0.0",
            "templates": {
                "test_template": {
                    "templateName": "Test Template",
                    "structure": {
                        "levels": [
                            {"pattern": "TEST_{occurrence_number}"},
                            {"pattern": "{location_address}"}
                        ]
                    }
                }
            }
        }
        
        with open(self.templates_dir / "folder_templates.json", "w") as f:
            json.dump(test_templates, f)
        
        # Change working directory temporarily for template loading
        import os
        self.original_cwd = os.getcwd()
        os.chdir(str(self.base_path))
        
        self.path_service = PathService()
        
        # Setup test form data
        self.form_data = FormData()
        self.form_data.occurrence_number = "2024-001"
        self.form_data.location_address = "Test Location"
    
    def teardown_method(self):
        """Cleanup test environment"""
        import os
        import time
        
        os.chdir(self.original_cwd)
        
        # Close any open log files by forcing garbage collection
        import gc
        gc.collect()
        
        # Small delay to allow file handles to close
        time.sleep(0.1)
        
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            # On Windows, sometimes log files are still open
            # This is acceptable for tests
            pass
    
    def test_template_loading(self):
        """Test that templates are loaded correctly"""
        templates = self.path_service.get_available_templates()
        
        # Should have default template plus our test template
        assert len(templates) >= 2
        template_ids = [t["id"] for t in templates]
        assert "test_template" in template_ids
        assert "default_forensic" in template_ids
    
    def test_template_switching(self):
        """Test switching between templates"""
        # Default should be default_forensic
        assert self.path_service.get_current_template_id() == "default_forensic"
        
        # Switch to test template
        result = self.path_service.set_current_template("test_template")
        assert result.success
        assert self.path_service.get_current_template_id() == "test_template"
        
        # Try to switch to non-existent template
        result = self.path_service.set_current_template("nonexistent")
        assert not result.success
        assert result.error is not None
    
    def test_template_based_path_building(self):
        """Test building paths using templates"""
        # Switch to test template
        self.path_service.set_current_template("test_template")
        
        # Build path
        output_dir = self.base_path / "output"
        result = self.path_service.build_forensic_path(self.form_data, output_dir)
        
        assert result.success
        path = result.value
        
        # Should follow test template pattern: TEST_{occurrence} / {location}
        relative_parts = path.relative_to(output_dir).parts
        assert relative_parts[0] == "TEST_2024-001"
        assert relative_parts[1] == "Test Location"
    
    def test_backward_compatibility(self):
        """Test that default template produces same results as ForensicPathBuilder"""
        # Use default template
        self.path_service.set_current_template("default_forensic")
        
        # Create test data matching ForensicPathBuilder expectations
        form_data = FormData()
        form_data.occurrence_number = "2024-TEST"
        form_data.business_name = "Test Business"
        form_data.location_address = "123 Test St"
        form_data.video_start_datetime = QDateTime(2025, 7, 30, 23, 12, 0)
        form_data.video_end_datetime = QDateTime(2025, 7, 30, 23, 45, 0)
        
        output_dir = self.base_path / "output"
        result = self.path_service.build_forensic_path(form_data, output_dir)
        
        assert result.success
        path = result.value
        
        # Check structure matches expected format
        relative_parts = path.relative_to(output_dir).parts
        assert relative_parts[0] == "2024-TEST"
        assert relative_parts[1] == "Test Business @ 123 Test St"
        assert "30JUL25_2312_to_30JUL25_2345_DVR_Time" == relative_parts[2]
    
    def test_template_reload(self):
        """Test template reloading"""
        initial_count = len(self.path_service.get_available_templates())
        
        # Add another template to the file
        templates_file = self.templates_dir / "folder_templates.json"
        with open(templates_file, "r") as f:
            templates_data = json.load(f)
        
        templates_data["templates"]["new_template"] = {
            "templateName": "New Template",
            "structure": {
                "levels": [{"pattern": "NEW_{occurrence_number}"}]
            }
        }
        
        with open(templates_file, "w") as f:
            json.dump(templates_data, f)
        
        # Reload templates
        result = self.path_service.reload_templates()
        assert result.success
        
        # Should now have one more template
        new_count = len(self.path_service.get_available_templates())
        assert new_count == initial_count + 1
        
        template_ids = [t["id"] for t in self.path_service.get_available_templates()]
        assert "new_template" in template_ids


class TestTemplateUIIntegration:
    """Test UI integration aspects"""
    
    def setup_method(self):
        """Setup Qt application for UI tests"""
        from PySide6.QtWidgets import QApplication
        import sys
        
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()
    
    def test_template_selector_creation(self):
        """Test that TemplateSelector can be created"""
        from ui.components.template_selector import TemplateSelector
        
        # Should be able to create without crashing
        selector = TemplateSelector()
        assert selector is not None
        assert hasattr(selector, 'template_combo')
        assert hasattr(selector, 'template_changed')
    
    def test_forensic_tab_integration(self):
        """Test that ForensicTab includes template selector"""
        from ui.tabs.forensic_tab import ForensicTab
        from core.models import FormData
        
        form_data = FormData()
        forensic_tab = ForensicTab(form_data)
        
        assert hasattr(forensic_tab, 'template_selector')
        assert hasattr(forensic_tab, 'template_changed')


class TestTemplateZipNaming:
    """Test template-based ZIP archive naming"""
    
    def setup_method(self):
        """Setup test data"""
        self.sanitizer = PathSanitizer()
        
        # Test form data
        self.form_data = FormData()
        self.form_data.occurrence_number = "2024-TEST-001"
        self.form_data.business_name = "Test Business"
        self.form_data.location_address = "123 Test Street"
        self.form_data.video_start_datetime = QDateTime(2025, 8, 28, 16, 30, 0)
        self.form_data.video_end_datetime = QDateTime(2025, 8, 28, 18, 15, 0)
    
    def test_default_forensic_archive_naming(self):
        """Test archive naming with default forensic template"""
        template = {
            "templateName": "Default Forensic Structure",
            "archiveNaming": {
                "pattern": "{occurrence_number} {business_name} @ {location_address} Video Recovery.zip",
                "fallbackPattern": "{occurrence_number}_Video_Recovery.zip"
            }
        }
        
        builder = TemplatePathBuilder(template, self.sanitizer)
        archive_name = builder.build_archive_name(self.form_data)
        
        expected = "2024-TEST-001 Test Business @ 123 Test Street Video Recovery.zip"
        assert archive_name == expected
    
    def test_rcmp_archive_naming(self):
        """Test archive naming with RCMP template"""
        template = {
            "templateName": "RCMP Basic Structure", 
            "archiveNaming": {
                "pattern": "FILE_{occurrence_number}_{year}_{business_name}_Evidence.zip",
                "fallbackPattern": "FILE_{occurrence_number}_Evidence.zip"
            }
        }
        
        builder = TemplatePathBuilder(template, self.sanitizer)
        archive_name = builder.build_archive_name(self.form_data)
        
        expected = f"FILE_2024-TEST-001_{datetime.now().year}_Test Business_Evidence.zip"
        assert archive_name == expected
    
    def test_agency_basic_archive_naming(self):
        """Test archive naming with generic agency template"""
        template = {
            "templateName": "Generic Agency Structure",
            "archiveNaming": {
                "pattern": "CASE_{occurrence_number}_{business_name}_Archive.zip",
                "fallbackPattern": "CASE_{occurrence_number}_Archive.zip"
            }
        }
        
        builder = TemplatePathBuilder(template, self.sanitizer)
        archive_name = builder.build_archive_name(self.form_data)
        
        expected = "CASE_2024-TEST-001_Test Business_Archive.zip"
        assert archive_name == expected
    
    def test_archive_name_fallback_with_missing_data(self):
        """Test archive naming falls back when data is missing"""
        template = {
            "archiveNaming": {
                "pattern": "{occurrence_number} {business_name} @ {location_address} Video Recovery.zip",
                "fallbackPattern": "{occurrence_number}_Recovery.zip"
            }
        }
        
        # Form data with missing fields
        form_data = FormData()
        form_data.occurrence_number = "2024-001"
        # business_name and location_address are empty
        
        builder = TemplatePathBuilder(template, self.sanitizer)
        archive_name = builder.build_archive_name(form_data)
        
        # Should clean up empty @ parts and use the pattern with missing data
        expected = "2024-001 Video Recovery.zip"
        assert archive_name == expected
    
    def test_archive_name_sanitization(self):
        """Test that archive names are properly sanitized"""
        template = {
            "archiveNaming": {
                "pattern": "{occurrence_number}_{business_name}_Archive.zip"
            }
        }
        
        # Form data with problematic characters
        form_data = FormData()
        form_data.occurrence_number = "2024/TEST<>001"
        form_data.business_name = "Test|Business*Name"
        
        builder = TemplatePathBuilder(template, self.sanitizer)
        archive_name = builder.build_archive_name(form_data)
        
        # Should sanitize problematic characters
        assert "/" not in archive_name
        assert "<" not in archive_name
        assert ">" not in archive_name
        assert "|" not in archive_name
        assert "*" not in archive_name
        assert archive_name.endswith(".zip")
    
    def test_path_service_archive_naming_integration(self):
        """Test PathService archive naming integration"""
        from tempfile import TemporaryDirectory
        import os
        import json
        
        with TemporaryDirectory() as temp_dir:
            # Create test template file
            templates_dir = Path(temp_dir) / "templates"
            templates_dir.mkdir(exist_ok=True)
            
            test_templates = {
                "version": "1.0.0",
                "templates": {
                    "test_archive_template": {
                        "templateName": "Test Archive Template",
                        "structure": {
                            "levels": [{"pattern": "{occurrence_number}"}]
                        },
                        "archiveNaming": {
                            "pattern": "TEST_{occurrence_number}_{business_name}_Archive.zip",
                            "fallbackPattern": "TEST_{occurrence_number}_Archive.zip"
                        }
                    }
                }
            }
            
            with open(templates_dir / "folder_templates.json", "w") as f:
                json.dump(test_templates, f)
            
            # Change directory and create PathService
            original_cwd = os.getcwd()
            try:
                os.chdir(str(temp_dir))
                path_service = PathService()
                
                # Switch to test template
                path_service.set_current_template("test_archive_template")
                
                # Test archive naming
                result = path_service.build_archive_name(self.form_data)
                assert result.success
                
                expected = "TEST_2024-TEST-001_Test Business_Archive.zip"
                assert result.value == expected
                
            finally:
                os.chdir(original_cwd)


def run_tests():
    """Run the tests directly if needed"""
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    run_tests()