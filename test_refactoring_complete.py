#!/usr/bin/env python3
"""
Test script to verify Phase 3-4 refactoring completion
"""
import sys
from pathlib import Path

def test_imports():
    """Test that all refactored components import successfully"""
    print("=" * 60)
    print("Testing Imports...")
    print("=" * 60)
    
    try:
        # Test MainWindow import
        from ui.main_window import MainWindow
        print("[OK] MainWindow imports successfully")
        
        # Test service imports
        from core.services.thread_management_service import ThreadManagementService
        print("[OK] ThreadManagementService imports successfully")
        
        from core.services.performance_formatter_service import PerformanceFormatterService
        print("[OK] PerformanceFormatterService imports successfully")
        
        from core.services.path_service import PathService
        print("[OK] PathService imports successfully")
        
        # Test controller import
        from controllers.workflow_controller import WorkflowController
        print("[OK] WorkflowController imports successfully")
        
        return True
    except ImportError as e:
        print(f"[FAIL] Import failed: {e}")
        return False

def test_service_configuration():
    """Test that all services are properly configured"""
    print("\n" + "=" * 60)
    print("Testing Service Configuration...")
    print("=" * 60)
    
    try:
        from core.services.service_config import configure_services, verify_service_configuration
        
        # Configure services
        configure_services()
        
        # Verify configuration
        results = verify_service_configuration()
        
        expected_services = [
            'IPathService',
            'IFileOperationService', 
            'IReportService',
            'IArchiveService',
            'IValidationService',
            'ISuccessMessageService',
            'IThreadManagementService',
            'IPerformanceFormatterService'
        ]
        
        all_configured = True
        for service_name in expected_services:
            if service_name in results:
                status = "[OK]" if results[service_name]['configured'] else "[FAIL]"
                print(f"{status} {service_name}: {results[service_name]['configured']}")
                if not results[service_name]['configured']:
                    all_configured = False
            else:
                print(f"[FAIL] {service_name}: Not found")
                all_configured = False
        
        return all_configured
    except Exception as e:
        print(f"[FAIL] Service configuration failed: {e}")
        return False

def test_refactored_methods():
    """Test that refactored methods are accessible"""
    print("\n" + "=" * 60)
    print("Testing Refactored Methods...")
    print("=" * 60)
    
    try:
        from core.services.path_service import PathService
        from core.services.thread_management_service import ThreadManagementService
        from core.services.performance_formatter_service import PerformanceFormatterService
        from controllers.workflow_controller import WorkflowController
        
        # Test PathService methods
        path_service = PathService()
        assert hasattr(path_service, 'determine_documents_location'), "Missing determine_documents_location"
        assert hasattr(path_service, 'find_occurrence_folder'), "Missing find_occurrence_folder"
        assert hasattr(path_service, 'navigate_to_occurrence_folder'), "Missing navigate_to_occurrence_folder"
        print("[OK] PathService has all refactored methods")
        
        # Test ThreadManagementService methods
        thread_service = ThreadManagementService()
        assert hasattr(thread_service, 'discover_active_threads'), "Missing discover_active_threads"
        assert hasattr(thread_service, 'shutdown_all_threads'), "Missing shutdown_all_threads"
        print("[OK] ThreadManagementService has all refactored methods")
        
        # Test PerformanceFormatterService methods
        perf_service = PerformanceFormatterService()
        assert hasattr(perf_service, 'format_statistics'), "Missing format_statistics"
        assert hasattr(perf_service, 'extract_speed_from_message'), "Missing extract_speed_from_message"
        print("[OK] PerformanceFormatterService has all refactored methods")
        
        # Test WorkflowController cleanup method
        # Note: WorkflowController requires services to be configured
        from core.services.service_config import configure_services
        configure_services()
        workflow_controller = WorkflowController()
        assert hasattr(workflow_controller, 'cleanup_operation_resources'), "Missing cleanup_operation_resources"
        print("[OK] WorkflowController has cleanup_operation_resources method")
        
        return True
    except Exception as e:
        print(f"[FAIL] Method test failed: {e}")
        return False

def test_performance_formatter():
    """Test PerformanceFormatterService functionality"""
    print("\n" + "=" * 60)
    print("Testing Performance Formatter Functionality...")
    print("=" * 60)
    
    try:
        from core.services.performance_formatter_service import PerformanceFormatterService
        
        service = PerformanceFormatterService()
        
        # Test speed extraction
        test_message = "Copying file @ 125.5 MB/s"
        speed = service.extract_speed_from_message(test_message)
        assert speed == 125.5, f"Expected 125.5, got {speed}"
        print("[OK] Speed extraction works correctly")
        
        # Test statistics formatting
        stats = {
            'files_processed': 10,
            'total_size_mb': 500,
            'duration_seconds': 60,
            'average_speed_mbps': 8.33,
            'peak_speed_mbps': 15.0
        }
        formatted = service.format_statistics(stats)
        assert "10 files" in formatted, "Missing file count"
        assert "processed" in formatted, "Missing processed text"
        print("[OK] Statistics formatting works correctly")
        
        # Test size formatting
        size_str = service.format_size(1024 * 1024 * 100)  # 100 MB
        assert "100" in size_str and "MB" in size_str, f"Unexpected size format: {size_str}"
        print("[OK] Size formatting works correctly")
        
        return True
    except Exception as e:
        print(f"[FAIL] Performance formatter test failed: {e}")
        return False

def check_legacy_methods():
    """Check that legacy methods have been removed from MainWindow"""
    print("\n" + "=" * 60)
    print("Checking Legacy Method Removal...")
    print("=" * 60)
    
    try:
        with open('ui/main_window.py', 'r') as f:
            content = f.read()
        
        legacy_methods = [
            '_reconstruct_file_result_data',
            '_reconstruct_zip_result_data',
            '_show_legacy_completion_message',
            '_cleanup_operation_attributes'
        ]
        
        found_legacy = []
        for method in legacy_methods:
            if f"def {method}(" in content:
                found_legacy.append(method)
        
        if found_legacy:
            print(f"[FAIL] Found legacy methods that should be removed: {found_legacy}")
            return False
        else:
            print("[OK] All legacy methods have been removed")
            return True
            
    except Exception as e:
        print(f"[FAIL] Legacy method check failed: {e}")
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("PHASE 3-4 REFACTORING COMPLETION TEST")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Service Configuration", test_service_configuration()))
    results.append(("Refactored Methods", test_refactored_methods()))
    results.append(("Performance Formatter", test_performance_formatter()))
    results.append(("Legacy Method Removal", check_legacy_methods()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "PASSED" if passed else "FAILED"
        symbol = "[OK]" if passed else "[FAIL]"
        print(f"{symbol} {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("[SUCCESS] ALL TESTS PASSED - REFACTORING COMPLETE!")
    else:
        print("[ERROR] SOME TESTS FAILED - REFACTORING INCOMPLETE")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())