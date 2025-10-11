#!/usr/bin/env python3
"""
Test script to verify copy_hash_verify module imports work correctly
Run this before launching the full application
"""

import sys
from pathlib import Path

print("=" * 60)
print("Testing Copy/Hash/Verify Module Imports")
print("=" * 60)

# Test 1: Basic module import
print("\n1. Testing basic module import...")
try:
    import copy_hash_verify
    print("✓ copy_hash_verify module imported successfully")
except Exception as e:
    print(f"✗ Failed to import copy_hash_verify: {e}")
    sys.exit(1)

# Test 2: Import master tab
print("\n2. Testing master tab import...")
try:
    from copy_hash_verify import CopyHashVerifyMasterTab
    print("✓ CopyHashVerifyMasterTab imported successfully")
except Exception as e:
    print(f"✗ Failed to import CopyHashVerifyMasterTab: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Import logger console
print("\n3. Testing logger console import...")
try:
    from copy_hash_verify.ui.components.operation_log_console import OperationLogConsole
    print("✓ OperationLogConsole imported successfully")
except Exception as e:
    print(f"✗ Failed to import OperationLogConsole: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Import unified hash calculator
print("\n4. Testing unified hash calculator import...")
try:
    from copy_hash_verify.core.unified_hash_calculator import UnifiedHashCalculator
    print("✓ UnifiedHashCalculator imported successfully")
except Exception as e:
    print(f"✗ Failed to import UnifiedHashCalculator: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Import sub-tabs
print("\n5. Testing sub-tab imports...")
try:
    from copy_hash_verify.ui.tabs.calculate_hashes_tab import CalculateHashesTab
    print("✓ CalculateHashesTab imported successfully")

    from copy_hash_verify.ui.tabs.verify_hashes_tab import VerifyHashesTab
    print("✓ VerifyHashesTab imported successfully")

    from copy_hash_verify.ui.tabs.copy_verify_operation_tab import CopyVerifyOperationTab
    print("✓ CopyVerifyOperationTab imported successfully")
except Exception as e:
    print(f"✗ Failed to import sub-tabs: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Verify exception classes
print("\n6. Testing exception imports...")
try:
    from core.exceptions import HashCalculationError, HashVerificationError
    print("✓ Hash exception classes imported successfully")
except Exception as e:
    print(f"✗ Failed to import exception classes: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 7: Create instances (without Qt GUI)
print("\n7. Testing UnifiedHashCalculator instantiation...")
try:
    calculator = UnifiedHashCalculator(algorithm='sha256')
    print(f"✓ UnifiedHashCalculator created: algorithm={calculator.algorithm}")
except Exception as e:
    print(f"✗ Failed to create UnifiedHashCalculator: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ ALL IMPORT TESTS PASSED!")
print("=" * 60)
print("\nThe copy_hash_verify module is ready to use.")
print("You can now run the main application:")
print("  python main.py")
print("=" * 60)
