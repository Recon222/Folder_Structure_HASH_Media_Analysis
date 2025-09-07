#!/usr/bin/env python3
"""Test metrics flow from worker to success message"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import tempfile
import shutil
from pathlib import Path
from core.workers.copy_verify_worker import CopyVerifyWorker
from core.services.copy_verify_service import CopyVerifyService
from controllers.copy_verify_controller import CopyVerifyController
from core.services.service_registry import register_service
from core.services.interfaces import ICopyVerifyService

# Create test files
temp_dir = tempfile.mkdtemp()
source_dir = Path(temp_dir) / "source"
dest_dir = Path(temp_dir) / "dest"
source_dir.mkdir()

# Create a test file with some size
test_file = source_dir / "test.txt"
test_file.write_text("x" * 1024 * 1024)  # 1MB file

# Register the service
register_service(ICopyVerifyService, CopyVerifyService())

try:
    # Test 1: Worker directly
    print("=== Testing Worker Directly ===")
    worker = CopyVerifyWorker(
        source_items=[test_file],
        destination=dest_dir,
        calculate_hash=True,
        service=CopyVerifyService()
    )
    
    # Run in main thread for testing
    result = worker.execute()
    
    print(f"Worker result success: {result.success}")
    if hasattr(result, 'duration_seconds'):
        print(f"Duration: {result.duration_seconds}")
        print(f"Speed: {result.average_speed_mbps}")
    else:
        print("No duration_seconds attribute")
    
    if hasattr(result, 'value') and isinstance(result.value, dict):
        if '_performance_stats' in result.value:
            print(f"Performance stats in value: {result.value['_performance_stats']}")
    
    # Test 2: Through controller
    print("\n=== Testing Through Controller ===")
    controller = CopyVerifyController()
    
    # Process the result through controller
    message_result = controller.process_operation_results(result, True)
    
    if message_result.success:
        message_data = message_result.value
        print(f"Message title: {message_data.title}")
        print("Summary lines:")
        for line in message_data.summary_lines:
            print(f"  {line}")
    else:
        print(f"Failed to process: {message_result.error}")

finally:
    shutil.rmtree(temp_dir, ignore_errors=True)