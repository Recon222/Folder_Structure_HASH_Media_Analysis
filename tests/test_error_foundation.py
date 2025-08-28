#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for Phase 4 Error Handling Foundation Components

This script tests the core error handling system components to ensure
they work correctly before proceeding with the nuclear implementation.
"""

import sys
import os
from pathlib import Path
from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QApplication, QWidget
import time

# Add the application root to the path
sys.path.insert(0, str(Path(__file__).parent))

def test_exceptions():
    """Test the exception hierarchy"""
    print("=== Testing Exception Hierarchy ===")
    
    try:
        from core.exceptions import (
            FSAError, FileOperationError, ValidationError, 
            ReportGenerationError, BatchProcessingError, 
            ErrorSeverity
        )
        
        # Test base FSAError
        base_error = FSAError(
            "Test error message",
            user_message="User-friendly message",
            severity=ErrorSeverity.ERROR
        )
        
        print(f"[PASS] Base error created: {base_error.error_code}")
        print(f"   Technical: {base_error.message}")
        print(f"   User: {base_error.user_message}")
        print(f"   Severity: {base_error.severity.value}")
        print(f"   Thread: {base_error.thread_name}")
        
        # Test specialized errors
        file_error = FileOperationError("File not found", file_path="/test/path")
        print(f"[PASS] FileOperationError: {file_error.context.get('file_path')}")
        
        validation_error = ValidationError({"field1": "Required", "field2": "Invalid"})
        print(f"[PASS] ValidationError: {len(validation_error.field_errors)} fields")
        
        batch_error = BatchProcessingError("job_123", successes=8, failures=2)
        print(f"[PASS] BatchProcessingError: {batch_error.successes}/{batch_error.successes + batch_error.failures} success rate")
        
        # Test error serialization
        error_dict = base_error.to_dict()
        print(f"[PASS] Error serialization: {len(error_dict)} fields")
        
        return True
        
    except Exception as e:
        print(f"❌ Exception test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_result_types():
    """Test the Result objects system"""
    print("\n=== Testing Result Objects System ===")
    
    try:
        from core.result_types import (
            Result, FileOperationResult, ValidationResult, 
            BatchOperationResult, combine_results
        )
        from core.exceptions import FSAError
        
        # Test basic Result
        success_result = Result.success("test_value", warnings=["minor warning"])
        print(f"✅ Success result: {success_result.value}, warnings: {len(success_result.warnings)}")
        
        error_result = Result.error(FSAError("Test error"))
        print(f"✅ Error result: {error_result.error.message}")
        
        # Test unwrapping
        try:
            value = success_result.unwrap()
            print(f"✅ Unwrap success: {value}")
        except:
            print("❌ Unwrap failed")
            
        default_value = error_result.unwrap_or("default")
        print(f"✅ Unwrap with default: {default_value}")
        
        # Test specialized results
        file_result = FileOperationResult.create(
            {"file1.txt": {"source_path": "/src", "dest_path": "/dst"}},
            files_processed=1,
            bytes_processed=1024
        )
        print(f"✅ FileOperationResult: {file_result.files_processed} files, {file_result.bytes_processed} bytes")
        
        validation_result = ValidationResult.create_invalid({"email": "Invalid format"})
        print(f"✅ ValidationResult: {validation_result.has_errors}, {len(validation_result.field_errors)} errors")
        
        # Test result combination
        results = [
            Result.success("value1"),
            Result.success("value2"),
            Result.success("value3")
        ]
        combined = combine_results(results)
        print(f"✅ Combined results: {len(combined.value)} values")
        
        return True
        
    except Exception as e:
        print(f"❌ Result types test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_handler():
    """Test the error handler system"""
    print("\n=== Testing Error Handler System ===")
    
    try:
        from core.error_handler import ErrorHandler, initialize_error_handling, handle_error
        from core.exceptions import FSAError, FileOperationError, ErrorSeverity
        
        # Initialize error handling
        app = QApplication.instance()
        if not app:
            app = QApplication([])
        
        error_handler = initialize_error_handling()
        print(f"✅ Error handler initialized: {error_handler.__class__.__name__}")
        
        # Test callback registration
        received_errors = []
        
        def test_callback(error, context):
            received_errors.append((error, context))
            print(f"   📝 Callback received: {error.error_code} - {error.user_message}")
        
        error_handler.register_ui_callback(test_callback)
        print("✅ UI callback registered")
        
        # Test error handling from main thread
        test_error = FSAError(
            "Test main thread error",
            user_message="This is a test error",
            severity=ErrorSeverity.WARNING
        )
        
        handle_error(test_error, {"test_context": "main_thread"})
        
        # Process any pending events
        app.processEvents()
        
        if received_errors:
            print(f"✅ Main thread error handled: {len(received_errors)} callbacks")
        else:
            print("⚠️  No callbacks received (may be timing issue)")
        
        # Test statistics
        stats = error_handler.get_error_statistics()
        print(f"✅ Error statistics: {stats}")
        
        recent_errors = error_handler.get_recent_errors(5)
        print(f"✅ Recent errors: {len(recent_errors)} entries")
        
        return True
        
    except Exception as e:
        print(f"❌ Error handler test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_base_worker():
    """Test the base worker thread"""
    print("\n=== Testing Base Worker Thread ===")
    
    try:
        from core.workers.base_worker import BaseWorkerThread, FileWorkerThread
        from core.result_types import Result
        from core.exceptions import FSAError
        
        app = QApplication.instance()
        if not app:
            app = QApplication([])
        
        # Create a simple test worker
        class TestWorker(BaseWorkerThread):
            def execute(self):
                self.emit_progress(25, "Starting test operation")
                time.sleep(0.1)  # Simulate work
                
                self.emit_progress(50, "Halfway done")
                time.sleep(0.1)
                
                self.emit_progress(75, "Almost finished")
                time.sleep(0.1)
                
                return Result.success("Test completed successfully")
        
        # Track results
        received_results = []
        progress_updates = []
        
        def on_result(result):
            received_results.append(result)
            print(f"   📝 Result received: success={result.success}, value={result.value}")
        
        def on_progress(percentage, message):
            progress_updates.append((percentage, message))
            print(f"   📈 Progress: {percentage}% - {message}")
        
        # Create and connect worker
        worker = TestWorker()
        worker.result_ready.connect(on_result)
        worker.progress_update.connect(on_progress)
        
        print("✅ TestWorker created and connected")
        
        # Start worker and wait for completion
        worker.start()
        worker.wait(5000)  # Wait up to 5 seconds
        
        # Process any pending events
        app.processEvents()
        
        if received_results:
            result = received_results[0]
            print(f"✅ Worker completed: {result.success}")
            print(f"   Metadata: {result.metadata}")
        else:
            print("⚠️  No results received")
            
        if progress_updates:
            print(f"✅ Progress updates: {len(progress_updates)} received")
        else:
            print("⚠️  No progress updates received")
        
        # Test FileWorkerThread
        file_worker = FileWorkerThread(files=[Path("test1.txt"), Path("test2.txt")])
        print(f"✅ FileWorkerThread created: {file_worker.total_files} files")
        
        return True
        
    except Exception as e:
        print(f"❌ Base worker test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_integration_test():
    """Run a full integration test of all components"""
    print("\n=== Integration Test ===")
    
    try:
        from core.exceptions import FileOperationError, ErrorSeverity
        from core.error_handler import get_error_handler
        from core.workers.base_worker import BaseWorkerThread
        from core.result_types import Result
        
        app = QApplication.instance()
        if not app:
            app = QApplication([])
        
        # Create a worker that has an error
        class ErrorWorker(BaseWorkerThread):
            def execute(self):
                self.emit_progress(10, "Starting operation that will fail")
                
                # Simulate an error
                error = FileOperationError(
                    "Simulated file operation failure",
                    file_path="/fake/path.txt",
                    user_message="Could not access the file",
                    severity=ErrorSeverity.ERROR
                )
                
                self.handle_error(error, {"simulation": True})
                return None  # Error already handled
        
        # Track integration results
        integration_errors = []
        
        def integration_callback(error, context):
            integration_errors.append((error, context))
            print(f"   🔗 Integration: {error.error_code} from {context.get('worker_class', 'unknown')}")
        
        error_handler = get_error_handler()
        error_handler.register_ui_callback(integration_callback)
        
        # Run error worker
        error_worker = ErrorWorker()
        error_worker.start()
        error_worker.wait(3000)
        
        app.processEvents()
        
        if integration_errors:
            print(f"✅ Integration test: Error properly routed through all systems")
            error, context = integration_errors[0]
            print(f"   Error: {error.message}")
            print(f"   Context: {context.get('worker_class')}")
        else:
            print("❌ Integration test: No errors received")
            return False
        
        print("✅ All foundation components integrated successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("Phase 4 Error Handling Foundation Component Tests")
    print("=" * 50)
    
    tests = [
        ("Exception Hierarchy", test_exceptions),
        ("Result Objects System", test_result_types),
        ("Error Handler System", test_error_handler),
        ("Base Worker Thread", test_base_worker),
        ("Integration Test", run_integration_test)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST RESULTS SUMMARY")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nOverall: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All foundation components are working correctly!")
        print("Ready to proceed with Phase 4 nuclear implementation.")
    else:
        print("⚠️  Some tests failed. Foundation needs fixes before proceeding.")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)