# Copy Hash Verify SOA/DI Refactoring Plan

## Executive Summary

**Purpose:** Refactor the `copy_hash_verify` module to match the clean SOA/DI/Controller architecture demonstrated in the `media_analysis` module.

**Current State:** Anti-pattern with business logic in UI, no controller layer, incomplete service layer.

**Target State:** Clean 3-tier architecture with Controller orchestration, complete Service layer, and thin UI layer.

**Estimated Effort:** 13-18 hours of focused development across 8 phases.

**Reference Architecture:** Use `media_analysis` module as the gold standard template.

---

## Architecture Context

### Current Anti-Pattern (Copy Hash Verify)
```
UI Tab (copy_verify_tab.py)
├─ Creates workers directly
├─ Contains business logic (file discovery, copying, reports)
├─ Manually manages worker lifecycle
├─ Generates CSV reports in UI code
└─ No resource coordination

Incomplete Services
├─ CopyVerifyService (only 2 validation methods)
└─ Missing: report generation, file collection, CSV export
```

### Target Architecture (Media Analysis Pattern)
```
UI Tab (media_analysis_tab.py)
└─ Pure UI: event handling, state management

Controller (MediaAnalysisController)
├─ Orchestrates workflows
├─ Injects services via DI
├─ Manages worker lifecycle with ResourceCoordinator
└─ Returns Result objects

Services (MediaAnalysisService)
├─ All business logic: validation, analysis, reports
├─ Implements IMediaAnalysisService interface
├─ Returns Result objects
└─ No UI dependencies

Service Registration (__init__.py)
└─ Auto-registers services on module import
```

---

## Prerequisites

Before starting this refactoring, ensure you understand:

1. **Service-Oriented Architecture (SOA)**
   - Controllers orchestrate (thin layer)
   - Services contain business logic (thick layer)
   - UI only handles user interaction (thin layer)

2. **Dependency Injection (DI)**
   - Services registered in `ServiceRegistry`
   - Retrieved via `get_service(IInterface)`
   - Controllers inject services via `_get_service()`

3. **Result Objects Pattern**
   - All service methods return `Result[T]` or `Result[bool]`
   - `Result.success(value)` for success cases
   - `Result.error(error)` for failure cases
   - No exceptions thrown across service boundaries

4. **Interface-Based Contracts**
   - Abstract base classes define service contracts
   - Services implement interfaces
   - Enables testing and modularity

5. **Resource Coordination**
   - `WorkerResourceCoordinator` tracks QThread workers
   - Prevents memory leaks
   - Enables safe cleanup

---

## Phase 0: Preparation and Analysis

**Duration:** 1 hour

### Step 0.1: Read Reference Implementation

**Files to Study:**
1. `media_analysis/controllers/media_analysis_controller.py` (REFERENCE TEMPLATE)
2. `media_analysis/services/media_analysis_service.py` (REFERENCE TEMPLATE)
3. `media_analysis/services/interfaces.py` (REFERENCE TEMPLATE)
4. `media_analysis/ui/tabs/media_analysis_tab.py` (REFERENCE TEMPLATE)
5. `media_analysis/__init__.py` (REFERENCE TEMPLATE)

**What to Note:**
- How controller extends `BaseController`
- How services extend `BaseService` and implement interfaces
- How UI delegates everything to controller
- How services return `Result` objects
- How service registration works

### Step 0.2: Analyze Current Implementation

**Files to Review:**
1. `copy_hash_verify/services/copy_verify_service.py` (INCOMPLETE)
2. `copy_hash_verify/services/interfaces.py` (INCOMPLETE)
3. `ui/tabs/copy_verify_tab.py` (ANTI-PATTERN - business logic in UI)
4. `copy_hash_verify/core/workers/copy_verify_worker.py` (Worker - OK)

**Problems to Identify:**
- [ ] No controller exists
- [ ] Service layer incomplete (only validation methods)
- [ ] Business logic in UI (`_start_copy_operation`, `_export_csv`)
- [ ] No service registration pattern
- [ ] No success builder service
- [ ] Manual worker lifecycle management

### Step 0.3: Create Feature Branch

```bash
git checkout Media-File-Analysis-Modularization
git pull origin Media-File-Analysis-Modularization
git checkout -b copy-hash-verify-soa-refactor
```

### Step 0.4: Backup Critical Files

```bash
mkdir -p copy_hash_verify/refactor_backups
cp ui/tabs/copy_verify_tab.py copy_hash_verify/refactor_backups/copy_verify_tab.py.backup
cp copy_hash_verify/services/copy_verify_service.py copy_hash_verify/refactor_backups/copy_verify_service.py.backup
```

---

## Phase 1: Create Controller Layer

**Duration:** 2-3 hours

**Priority:** HIGH

**Objective:** Create `CopyHashVerifyController` that orchestrates all copy/hash/verify workflows, following the `MediaAnalysisController` pattern exactly.

### Step 1.1: Create Controller Directory

```bash
mkdir -p copy_hash_verify/controllers
```

### Step 1.2: Create Base Controller File

**File:** `copy_hash_verify/controllers/copy_hash_verify_controller.py`

**Template to Follow:** `media_analysis/controllers/media_analysis_controller.py`

**Implementation:**

```python
#!/usr/bin/env python3
"""
Copy Hash Verify Controller - Orchestrates copy, hash, and verify workflows

Following the SOA/DI pattern demonstrated in MediaAnalysisController.
This controller:
- Orchestrates workflows (no business logic)
- Injects services via DI
- Manages worker lifecycle with ResourceCoordinator
- Returns Result objects for all operations
"""

from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

from controllers.base_controller import BaseController
from core.result_types import Result
from core.exceptions import ValidationError, FileOperationError
from core.logger import logger
from copy_hash_verify.services.interfaces import ICopyVerifyService, IHashService
from copy_hash_verify.core.workers.copy_verify_worker import CopyVerifyWorker


@dataclass
class CopyVerifySettings:
    """Settings for copy and verify operations"""
    algorithm: str = 'sha256'
    preserve_structure: bool = True
    generate_csv: bool = True
    calculate_hashes: bool = True


class CopyHashVerifyController(BaseController):
    """
    Controller for copy, hash, and verify operations

    Responsibilities:
    - Workflow orchestration (no business logic)
    - Service injection and delegation
    - Worker lifecycle management
    - Resource coordination

    Pattern:
    1. Validate inputs through service
    2. Create and track worker
    3. Return Result object
    """

    def __init__(self):
        """Initialize controller with service injection"""
        super().__init__("CopyHashVerifyController")

        # Lazy-loaded services (injected on first access)
        self._copy_verify_service = None
        self._hash_service = None
        self._success_builder = None

    @property
    def copy_verify_service(self) -> ICopyVerifyService:
        """Lazy-load copy verify service via DI"""
        if self._copy_verify_service is None:
            self._copy_verify_service = self._get_service(ICopyVerifyService)
        return self._copy_verify_service

    @property
    def hash_service(self) -> IHashService:
        """Lazy-load hash service via DI"""
        if self._hash_service is None:
            self._hash_service = self._get_service(IHashService)
        return self._hash_service

    @property
    def success_builder(self):
        """Lazy-load success builder service via DI"""
        if self._success_builder is None:
            from copy_hash_verify.services.interfaces import ICopyHashVerifySuccessService
            self._success_builder = self._get_service(ICopyHashVerifySuccessService)
        return self._success_builder

    def start_copy_verify_workflow(
        self,
        source_paths: List[Path],
        destination: Path,
        settings: CopyVerifySettings
    ) -> Result[CopyVerifyWorker]:
        """
        Orchestrate copy+verify workflow

        Workflow:
        1. Validate inputs through service
        2. Check destination availability
        3. Create worker
        4. Track worker with resource coordinator
        5. Return worker wrapped in Result

        Args:
            source_paths: List of source files/folders
            destination: Destination directory
            settings: Copy operation settings

        Returns:
            Result[CopyVerifyWorker]: Success with worker, or error
        """
        logger.info(f"Starting copy+verify workflow: {len(source_paths)} sources -> {destination}")

        try:
            # Step 1: Validate operation through service
            validation_result = self.copy_verify_service.validate_copy_operation(
                source_paths=source_paths,
                destination=destination,
                preserve_structure=settings.preserve_structure
            )

            if not validation_result.success:
                logger.error(f"Validation failed: {validation_result.error}")
                return Result.error(validation_result.error)

            # Step 2: Check destination space availability
            space_check = self.copy_verify_service.check_destination_availability(
                source_paths=source_paths,
                destination=destination
            )

            if not space_check.success:
                logger.error(f"Space check failed: {space_check.error}")
                return Result.error(space_check.error)

            # Step 3: Create worker
            worker = CopyVerifyWorker(
                source_paths=source_paths,
                destination=destination,
                algorithm=settings.algorithm,
                preserve_structure=settings.preserve_structure
            )

            # Step 4: Track worker with resource coordinator
            if self.resources:
                worker_id = self.resources.track_worker(
                    worker=worker,
                    name="copy_verify",
                    description=f"Copy {len(source_paths)} items to {destination.name}"
                )
                logger.debug(f"Worker tracked with ID: {worker_id}")

            logger.info("Copy+verify workflow started successfully")
            return Result.success(worker)

        except Exception as e:
            error = FileOperationError(
                f"Failed to start copy+verify workflow: {str(e)}",
                user_message="Failed to start copy operation. Please check the logs."
            )
            logger.exception("Unexpected error in start_copy_verify_workflow")
            return Result.error(error)

    def process_operation_results(
        self,
        result: Result,
        calculate_hashes: bool
    ) -> Result:
        """
        Process operation results and prepare for display

        Delegates to service for data processing.

        Args:
            result: Raw operation result from worker
            calculate_hashes: Whether hashes were calculated

        Returns:
            Result with processed operation data
        """
        logger.info("Processing operation results")

        try:
            # Delegate to service for result processing
            return self.copy_verify_service.process_operation_results(
                result=result,
                calculate_hashes=calculate_hashes
            )
        except Exception as e:
            error = FileOperationError(
                f"Failed to process results: {str(e)}",
                user_message="Failed to process operation results."
            )
            logger.exception("Error in process_operation_results")
            return Result.error(error)

    def generate_verification_report(
        self,
        results: Dict,
        output_path: Path,
        algorithm: str
    ) -> Result[Path]:
        """
        Generate CSV verification report

        Delegates to service for report generation.

        Args:
            results: Operation results dictionary
            output_path: Path to save CSV report
            algorithm: Hash algorithm used

        Returns:
            Result[Path]: Path to generated report, or error
        """
        logger.info(f"Generating verification report: {output_path}")

        try:
            # Delegate to service
            return self.copy_verify_service.generate_verification_report(
                results=results,
                output_path=output_path,
                algorithm=algorithm
            )
        except Exception as e:
            error = FileOperationError(
                f"Failed to generate report: {str(e)}",
                user_message="Failed to generate CSV report."
            )
            logger.exception("Error in generate_verification_report")
            return Result.error(error)

    def cleanup(self):
        """
        Clean up controller resources

        Releases worker tracking and cleans up service resources.
        """
        logger.debug("Cleaning up CopyHashVerifyController")

        # Release all tracked workers
        if self.resources:
            self.resources.release_all()

        # Parent cleanup
        super().cleanup()
```

### Step 1.3: Create Controller __init__.py

**File:** `copy_hash_verify/controllers/__init__.py`

```python
"""
Copy Hash Verify Controllers

Controller layer for orchestrating copy, hash, and verify workflows.
"""

from .copy_hash_verify_controller import CopyHashVerifyController, CopyVerifySettings

__all__ = [
    'CopyHashVerifyController',
    'CopyVerifySettings',
]
```

### Step 1.4: Validate Controller Implementation

**Checklist:**
- [ ] Controller extends `BaseController`
- [ ] Services injected via `@property` with `_get_service()`
- [ ] All methods return `Result` objects
- [ ] No business logic (only orchestration)
- [ ] Uses `WorkerResourceCoordinator` via `self.resources`
- [ ] Has `cleanup()` method
- [ ] Logging at appropriate levels
- [ ] Type hints on all methods

**Test Import:**
```python
from copy_hash_verify.controllers import CopyHashVerifyController
controller = CopyHashVerifyController()
print("Controller created successfully")
```

---

## Phase 2: Complete Service Layer

**Duration:** 3-4 hours

**Priority:** HIGH

**Objective:** Expand `CopyVerifyService` to contain ALL business logic, matching `MediaAnalysisService` completeness.

### Step 2.1: Update Service Interface

**File:** `copy_hash_verify/services/interfaces.py`

**Add Missing Methods:**

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Optional
from core.result_types import Result


class ICopyVerifyService(ABC):
    """
    Interface for copy and verify service operations

    All business logic for copy, hash, and verification operations.
    """

    @abstractmethod
    def validate_copy_operation(
        self,
        source_paths: List[Path],
        destination: Path,
        preserve_structure: bool
    ) -> Result[bool]:
        """
        Validate copy operation inputs

        Args:
            source_paths: List of source file/folder paths
            destination: Destination directory path
            preserve_structure: Whether to preserve folder structure

        Returns:
            Result[bool]: True if valid, error otherwise
        """
        pass

    @abstractmethod
    def check_destination_availability(
        self,
        source_paths: List[Path],
        destination: Path
    ) -> Result[bool]:
        """
        Check if destination has enough space

        Args:
            source_paths: List of source paths
            destination: Destination directory

        Returns:
            Result[bool]: True if space available, error otherwise
        """
        pass

    @abstractmethod
    def collect_source_files(
        self,
        source_paths: List[Path],
        preserve_structure: bool
    ) -> Result[List[Path]]:
        """
        Collect all files from source paths (recursive folder expansion)

        Args:
            source_paths: List of files/folders
            preserve_structure: Whether folder structure matters

        Returns:
            Result[List[Path]]: List of files to copy
        """
        pass

    @abstractmethod
    def generate_verification_report(
        self,
        results: Dict,
        output_path: Path,
        algorithm: str
    ) -> Result[Path]:
        """
        Generate CSV verification report

        Args:
            results: Operation results with hash data
            output_path: Path to save CSV
            algorithm: Hash algorithm used

        Returns:
            Result[Path]: Path to generated CSV
        """
        pass

    @abstractmethod
    def process_operation_results(
        self,
        result: Result,
        calculate_hashes: bool
    ) -> Result:
        """
        Process raw operation results for display

        Args:
            result: Raw worker result
            calculate_hashes: Whether hashes were calculated

        Returns:
            Result: Processed operation data
        """
        pass

    @abstractmethod
    def build_destination_path(
        self,
        source_path: Path,
        base_source: Path,
        destination: Path,
        preserve_structure: bool
    ) -> Path:
        """
        Build destination path for a file

        Args:
            source_path: Source file path
            base_source: Base source directory
            destination: Destination directory
            preserve_structure: Preserve folder hierarchy

        Returns:
            Path: Computed destination path
        """
        pass


class IHashService(ABC):
    """Interface for hash calculation operations"""

    @abstractmethod
    def calculate_file_hash(
        self,
        file_path: Path,
        algorithm: str = 'sha256'
    ) -> Result[str]:
        """
        Calculate hash for a single file

        Args:
            file_path: Path to file
            algorithm: Hash algorithm (sha256, sha1, md5)

        Returns:
            Result[str]: Hex digest hash string
        """
        pass

    @abstractmethod
    def verify_file_integrity(
        self,
        source_hash: str,
        dest_hash: str,
        file_path: Path
    ) -> Result[bool]:
        """
        Verify file integrity by comparing hashes

        Args:
            source_hash: Hash of source file
            dest_hash: Hash of destination file
            file_path: File path being verified

        Returns:
            Result[bool]: True if hashes match
        """
        pass


class ICopyHashVerifySuccessService(ABC):
    """Interface for building success messages"""

    @abstractmethod
    def build_copy_verify_success_message(
        self,
        operation_data
    ):
        """
        Build success message for copy+verify operation

        Args:
            operation_data: CopyVerifyOperationData with results

        Returns:
            SuccessMessageData: Formatted success message
        """
        pass
```

### Step 2.2: Implement Complete Service

**File:** `copy_hash_verify/services/copy_verify_service.py`

**Expand to Include All Business Logic:**

```python
#!/usr/bin/env python3
"""
Copy Verify Service - Business logic for copy and verify operations

All business logic for:
- Input validation
- File collection and discovery
- Space calculations
- Report generation
- Result processing
"""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from core.services.base_service import BaseService
from core.result_types import Result
from core.exceptions import ValidationError, FileOperationError
from core.logger import logger
from copy_hash_verify.services.interfaces import ICopyVerifyService
from copy_hash_verify.core.hash_reports import HashReportGenerator


class CopyVerifyService(BaseService, ICopyVerifyService):
    """
    Service for copy and verify operations

    Contains ALL business logic for copy/hash/verify workflows.
    No UI dependencies.
    """

    def __init__(self):
        super().__init__("CopyVerifyService")

    def validate_copy_operation(
        self,
        source_paths: List[Path],
        destination: Path,
        preserve_structure: bool
    ) -> Result[bool]:
        """
        Validate copy operation inputs

        Checks:
        - Source paths exist
        - Destination is valid
        - No circular copies
        - Write permissions

        Returns:
            Result[bool]: True if valid, ValidationError otherwise
        """
        logger.debug(f"Validating copy operation: {len(source_paths)} sources")

        try:
            # Check source paths exist
            if not source_paths:
                return Result.error(ValidationError(
                    "No source paths provided",
                    user_message="Please select files or folders to copy"
                ))

            for path in source_paths:
                if not path.exists():
                    return Result.error(ValidationError(
                        f"Source path does not exist: {path}",
                        user_message=f"Source file or folder not found: {path.name}"
                    ))

            # Check destination is valid
            if not destination:
                return Result.error(ValidationError(
                    "No destination provided",
                    user_message="Please select a destination folder"
                ))

            # Create destination if it doesn't exist
            if not destination.exists():
                try:
                    destination.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    return Result.error(ValidationError(
                        f"Cannot create destination: {e}",
                        user_message=f"Cannot create destination folder: {destination}"
                    ))

            # Check destination is a directory
            if not destination.is_dir():
                return Result.error(ValidationError(
                    f"Destination is not a directory: {destination}",
                    user_message="Destination must be a folder, not a file"
                ))

            # Check for circular copies (source inside destination or vice versa)
            try:
                dest_resolved = destination.resolve()
                for source in source_paths:
                    source_resolved = source.resolve()

                    # Check if source is inside destination
                    try:
                        source_resolved.relative_to(dest_resolved)
                        return Result.error(ValidationError(
                            f"Cannot copy {source} into its subdirectory {destination}",
                            user_message="Cannot copy a folder into itself"
                        ))
                    except ValueError:
                        pass  # Not relative, OK

                    # Check if destination is inside source
                    if source.is_dir():
                        try:
                            dest_resolved.relative_to(source_resolved)
                            return Result.error(ValidationError(
                                f"Cannot copy to {destination} which is inside source {source}",
                                user_message="Cannot copy to a subfolder of the source"
                            ))
                        except ValueError:
                            pass  # Not relative, OK
            except Exception as e:
                logger.warning(f"Could not check circular copy: {e}")

            # Check write permissions
            if not os.access(destination, os.W_OK):
                return Result.error(ValidationError(
                    f"No write permission for destination: {destination}",
                    user_message="You don't have permission to write to this folder"
                ))

            logger.info("Copy operation validation passed")
            return Result.success(True)

        except Exception as e:
            logger.exception("Unexpected error in validate_copy_operation")
            return Result.error(ValidationError(
                f"Validation error: {str(e)}",
                user_message="Failed to validate copy operation"
            ))

    def check_destination_availability(
        self,
        source_paths: List[Path],
        destination: Path
    ) -> Result[bool]:
        """
        Check if destination has enough space

        Calculates total source size and compares to available space.

        Returns:
            Result[bool]: True if space available, error otherwise
        """
        logger.debug("Checking destination space availability")

        try:
            # Calculate total size needed
            total_size = 0
            for path in source_paths:
                if path.is_file():
                    total_size += path.stat().st_size
                elif path.is_dir():
                    # Recursively sum folder size
                    for item in path.rglob('*'):
                        if item.is_file():
                            try:
                                total_size += item.stat().st_size
                            except (OSError, PermissionError):
                                # Skip files we can't access
                                pass

            # Get available space
            stat = shutil.disk_usage(destination)
            available_space = stat.free

            # Require 10% buffer for safety
            required_space = int(total_size * 1.1)

            logger.info(
                f"Space check: need {required_space / (1024**3):.2f} GB, "
                f"available {available_space / (1024**3):.2f} GB"
            )

            if available_space < required_space:
                return Result.error(FileOperationError(
                    f"Insufficient space: need {required_space / (1024**3):.2f} GB, "
                    f"have {available_space / (1024**3):.2f} GB",
                    user_message=(
                        f"Not enough disk space. Need {required_space / (1024**3):.2f} GB "
                        f"but only {available_space / (1024**3):.2f} GB available."
                    )
                ))

            return Result.success(True)

        except Exception as e:
            logger.exception("Error checking disk space")
            return Result.error(FileOperationError(
                f"Failed to check disk space: {str(e)}",
                user_message="Could not verify available disk space"
            ))

    def collect_source_files(
        self,
        source_paths: List[Path],
        preserve_structure: bool
    ) -> Result[List[Path]]:
        """
        Collect all files from source paths (expand folders recursively)

        Args:
            source_paths: List of files/folders
            preserve_structure: Whether structure preservation matters

        Returns:
            Result[List[Path]]: Flat list of all files to copy
        """
        logger.debug(f"Collecting files from {len(source_paths)} sources")

        try:
            all_files = []

            for path in source_paths:
                if path.is_file():
                    all_files.append(path)
                elif path.is_dir():
                    # Recursively collect files
                    for item in path.rglob('*'):
                        if item.is_file():
                            all_files.append(item)

            logger.info(f"Collected {len(all_files)} files from sources")
            return Result.success(all_files)

        except Exception as e:
            logger.exception("Error collecting source files")
            return Result.error(FileOperationError(
                f"Failed to collect files: {str(e)}",
                user_message="Could not scan source files"
            ))

    def build_destination_path(
        self,
        source_path: Path,
        base_source: Path,
        destination: Path,
        preserve_structure: bool
    ) -> Path:
        """
        Build destination path for a file

        If preserve_structure=True, maintains folder hierarchy.
        Otherwise, flattens all files to destination root.

        Args:
            source_path: File being copied
            base_source: Base source directory
            destination: Destination root
            preserve_structure: Maintain hierarchy

        Returns:
            Path: Destination path for file
        """
        if preserve_structure:
            # Maintain relative path structure
            try:
                relative = source_path.relative_to(base_source)
                return destination / relative
            except ValueError:
                # If not relative, just use filename
                return destination / source_path.name
        else:
            # Flatten - just filename
            return destination / source_path.name

    def generate_verification_report(
        self,
        results: Dict,
        output_path: Path,
        algorithm: str
    ) -> Result[Path]:
        """
        Generate CSV verification report

        Uses HashReportGenerator to create forensic-grade CSV.

        Args:
            results: Operation results with hash data
            output_path: Path to save CSV
            algorithm: Hash algorithm used

        Returns:
            Result[Path]: Path to generated CSV file
        """
        logger.info(f"Generating verification report: {output_path}")

        try:
            # Use existing HashReportGenerator
            report_gen = HashReportGenerator()

            # Generate report
            report_gen.generate_copy_verify_csv(
                results=results,
                output_path=output_path,
                algorithm=algorithm
            )

            if not output_path.exists():
                return Result.error(FileOperationError(
                    f"Report not created: {output_path}",
                    user_message="Failed to create CSV report"
                ))

            logger.info(f"Report generated successfully: {output_path}")
            return Result.success(output_path)

        except Exception as e:
            logger.exception("Error generating verification report")
            return Result.error(FileOperationError(
                f"Report generation failed: {str(e)}",
                user_message="Failed to generate CSV report"
            ))

    def process_operation_results(
        self,
        result: Result,
        calculate_hashes: bool
    ) -> Result:
        """
        Process raw operation results for display

        Extracts relevant data from worker result and packages
        it for the success message builder.

        Args:
            result: Raw Result object from worker
            calculate_hashes: Whether hashes were calculated

        Returns:
            Result: Processed CopyVerifyOperationData
        """
        logger.debug("Processing operation results")

        try:
            if not result.success:
                return result

            # Extract operation data
            raw_data = result.value

            # Build operation data structure
            # (This would match the CopyVerifyOperationData structure
            #  used by the success builder)
            from core.services.success_message_data import CopyVerifyOperationData

            operation_data = CopyVerifyOperationData(
                files_copied=raw_data.get('files_copied', 0),
                total_size=raw_data.get('total_size', 0),
                duration=raw_data.get('duration', 0),
                hash_calculated=calculate_hashes,
                verification_passed=raw_data.get('verification_passed', True),
                performance_stats=raw_data.get('performance_stats'),
                # ... other fields as needed
            )

            return Result.success(operation_data)

        except Exception as e:
            logger.exception("Error processing operation results")
            return Result.error(FileOperationError(
                f"Result processing failed: {str(e)}",
                user_message="Failed to process operation results"
            ))
```

### Step 2.3: Validate Service Implementation

**Checklist:**
- [ ] Service extends `BaseService`
- [ ] Implements `ICopyVerifyService` interface
- [ ] All interface methods implemented
- [ ] All methods return `Result` objects
- [ ] No UI dependencies (no imports from `ui/` or `PySide6.QtWidgets`)
- [ ] Comprehensive error handling with try-except
- [ ] Logging at appropriate levels
- [ ] Type hints on all methods

**Test Import:**
```python
from copy_hash_verify.services.copy_verify_service import CopyVerifyService
service = CopyVerifyService()
print("Service created successfully")
```

---

## Phase 3: Create Success Builder Service

**Duration:** 1-2 hours

**Priority:** MEDIUM

**Objective:** Create `CopyHashVerifySuccessBuilder` service that builds success messages for operations.

### Step 3.1: Create Success Builder Service

**File:** `copy_hash_verify/services/copy_hash_verify_success.py`

**Template to Follow:** `media_analysis/services/media_analysis_success_builder.py`

```python
#!/usr/bin/env python3
"""
Copy Hash Verify Success Builder - Build success messages for operations

Separates success message building logic from UI and controllers.
"""

from core.services.base_service import BaseService
from core.services.success_message_data import SuccessMessageData, CopyVerifyOperationData
from core.logger import logger
from copy_hash_verify.services.interfaces import ICopyHashVerifySuccessService


class CopyHashVerifySuccessBuilder(BaseService, ICopyHashVerifySuccessService):
    """
    Build success messages for copy/hash/verify operations

    Creates rich success message data structures with:
    - File counts and sizes
    - Performance metrics
    - Hash verification results
    - Operation duration
    """

    def __init__(self):
        super().__init__("CopyHashVerifySuccessBuilder")

    def build_copy_verify_success_message(
        self,
        operation_data: CopyVerifyOperationData
    ) -> SuccessMessageData:
        """
        Build success message for copy+verify operation

        Args:
            operation_data: Data from completed operation

        Returns:
            SuccessMessageData: Formatted success message
        """
        logger.debug("Building copy+verify success message")

        # Build title
        title = "Copy & Verify Complete"

        # Build summary
        summary_lines = [
            f"Successfully copied {operation_data.files_copied} files",
            f"Total size: {self._format_size(operation_data.total_size)}",
            f"Duration: {self._format_duration(operation_data.duration)}"
        ]

        if operation_data.hash_calculated:
            if operation_data.verification_passed:
                summary_lines.append("✓ Hash verification passed")
            else:
                summary_lines.append("✗ Hash verification failed")

        summary = "\n".join(summary_lines)

        # Build details
        details = {}

        if operation_data.performance_stats:
            perf = operation_data.performance_stats
            details['Performance'] = [
                f"Average speed: {perf.get('avg_speed_mb_s', 0):.2f} MB/s",
                f"Threads used: {perf.get('threads_used', 1)}"
            ]

        # Create success message data
        message_data = SuccessMessageData(
            title=title,
            summary=summary,
            details=details,
            operation_type="copy_verify",
            celebration_emoji="🎉"
        )

        return message_data

    def _format_size(self, size_bytes: int) -> str:
        """Format byte size for display"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    def _format_duration(self, seconds: float) -> str:
        """Format duration for display"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds / 60:.1f}m"
        else:
            return f"{seconds / 3600:.1f}h"
```

### Step 3.2: Update Service Interfaces

**File:** `copy_hash_verify/services/interfaces.py`

Add the interface definition (already included in Phase 2 Step 2.1).

### Step 3.3: Validate Success Builder

**Test:**
```python
from copy_hash_verify.services.copy_hash_verify_success import CopyHashVerifySuccessBuilder
from core.services.success_message_data import CopyVerifyOperationData

builder = CopyHashVerifySuccessBuilder()
op_data = CopyVerifyOperationData(files_copied=10, total_size=1024*1024*50, duration=5.5)
message = builder.build_copy_verify_success_message(op_data)
print(message.title)
print(message.summary)
```

---

## Phase 4: Refactor UI Layer

**Duration:** 2-3 hours

**Priority:** HIGH

**Objective:** Remove ALL business logic from `copy_verify_tab.py`, delegate everything to controller.

### Step 4.1: Read Current UI Implementation

**File:** `ui/tabs/copy_verify_tab.py`

**Identify Code to Remove:**
- Worker creation logic
- File discovery/collection
- CSV generation
- Result processing
- Manual worker lifecycle

**Identify Code to Keep:**
- UI widget creation
- Event handlers (but delegate to controller)
- Progress display
- State management (operation_active, etc.)

### Step 4.2: Refactor UI to Use Controller

**File:** `ui/tabs/copy_verify_tab.py`

**Changes Required:**

```python
# At top of file, add controller import
from copy_hash_verify.controllers import CopyHashVerifyController, CopyVerifySettings

class CopyVerifyTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        # CREATE CONTROLLER (new)
        self.controller = CopyHashVerifyController()

        # Get success builder through DI (new)
        from copy_hash_verify.services.interfaces import ICopyHashVerifySuccessService
        self.success_builder = get_service(ICopyHashVerifySuccessService)

        # ... rest of init ...

    def _start_copy_operation(self):
        """Start copy operation - DELEGATE TO CONTROLLER"""
        try:
            # Build settings from UI
            settings = CopyVerifySettings(
                algorithm=self.algorithm_combo.currentText().lower(),
                preserve_structure=self.preserve_structure_check.isChecked(),
                generate_csv=self.generate_csv_check.isChecked(),
                calculate_hashes=self.calculate_hashes_check.isChecked()
            )

            # Get source and destination from UI
            files, folders = self.files_panel.get_all_items()
            source_paths = files + folders
            destination = self.destination_path

            # DELEGATE TO CONTROLLER (not creating worker ourselves!)
            result = self.controller.start_copy_verify_workflow(
                source_paths=source_paths,
                destination=destination,
                settings=settings
            )

            if result.success:
                # Get worker from result
                self.current_worker = result.value

                # Connect signals
                self.current_worker.result_ready.connect(self._on_operation_complete)
                self.current_worker.progress_update.connect(self._on_progress_update)

                # Start worker
                self.current_worker.start()

                # Update UI state
                self._set_operation_active(True)
                self._log("Copy operation started...")
            else:
                # Show error
                error_msg = result.error.user_message if result.error else "Unknown error"
                self._show_error(error_msg)

        except Exception as e:
            logger.exception("Error starting copy operation")
            self._show_error(f"Failed to start operation: {str(e)}")

    def _on_operation_complete(self, result):
        """Handle operation completion - DELEGATE TO CONTROLLER"""
        self._set_operation_active(False)

        if result.success:
            # Store results
            self.last_results = result.value

            # DELEGATE result processing to controller
            process_result = self.controller.process_operation_results(
                result,
                self.calculate_hashes_check.isChecked()
            )

            if process_result.success:
                # Get operation data
                copy_data = process_result.value

                # BUILD success message through service
                message_data = self.success_builder.build_copy_verify_success_message(copy_data)

                # Log summary
                self._log(message_data.to_display_message())

                # Show success dialog
                SuccessDialog.show_success_message(message_data, self)

                # Enable CSV export
                self.export_csv_btn.setEnabled(True)
            else:
                self._log("Failed to process results")
        else:
            # Show error
            error_msg = result.error.user_message if result.error else "Operation failed"
            self._log(f"❌ {error_msg}")
            self._show_error(error_msg)

    def _export_csv(self):
        """Export CSV report - DELEGATE TO CONTROLLER"""
        if not self.last_results:
            self._show_error("No results to export")
            return

        try:
            # Ask user for file path
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save CSV Report",
                f"copy_verify_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV Files (*.csv);;All Files (*)"
            )

            if not file_path:
                return

            # DELEGATE to controller
            result = self.controller.generate_verification_report(
                results=self.last_results,
                output_path=Path(file_path),
                algorithm=self.algorithm_combo.currentText().lower()
            )

            if result.success:
                self._log(f"CSV report saved: {file_path}")
                QMessageBox.information(self, "Export Complete", f"Report saved to:\n{file_path}")
            else:
                error_msg = result.error.user_message if result.error else "Export failed"
                self._show_error(error_msg)

        except Exception as e:
            logger.exception("Error exporting CSV")
            self._show_error(f"Export failed: {str(e)}")

    def cleanup(self):
        """Clean up tab resources"""
        if self.controller:
            self.controller.cleanup()
```

### Step 4.3: Remove Old Code

**Delete from `copy_verify_tab.py`:**
- Direct worker creation: `CopyVerifyWorker(...)`
- File collection logic
- CSV generation: `HashReportGenerator()`
- Any imports of business logic services directly

**Keep Only:**
- UI widget creation
- Signal connections
- State management
- Delegating calls to controller

### Step 4.4: Validate UI Refactor

**Checklist:**
- [ ] NO direct worker creation (all through controller)
- [ ] NO business logic (validation, file collection, reports)
- [ ] Controller created in `__init__`
- [ ] Success builder injected via `get_service()`
- [ ] All operations delegate to controller
- [ ] Results processed through controller
- [ ] CSV export delegates to controller
- [ ] Cleanup calls `controller.cleanup()`

**Test Import:**
```python
from ui.tabs.copy_verify_tab import CopyVerifyTab
tab = CopyVerifyTab()
print("Tab created successfully")
```

---

## Phase 5: Service Registration

**Duration:** 30 minutes

**Priority:** MEDIUM

**Objective:** Create self-registration module so services auto-register on import.

### Step 5.1: Create __init__.py with Registration

**File:** `copy_hash_verify/__init__.py`

```python
"""
Copy Hash Verify Module

SOA/DI module for copy, hash, and verification operations.
Auto-registers services on import.
"""

from core.logger import logger


def register_services():
    """
    Register copy/hash/verify services with main application

    Services registered:
    - ICopyVerifyService -> CopyVerifyService
    - IHashService -> HashService
    - ICopyHashVerifySuccessService -> CopyHashVerifySuccessBuilder
    """
    from core.services import register_service, get_service

    # Check if already registered (idempotent)
    try:
        from .services.interfaces import ICopyVerifyService
        get_service(ICopyVerifyService)
        logger.debug("Copy/Hash/Verify services already registered")
        return
    except ValueError:
        pass  # Not registered, proceed

    try:
        # Import interfaces
        from .services.interfaces import (
            ICopyVerifyService,
            IHashService,
            ICopyHashVerifySuccessService
        )

        # Import implementations
        from .services.copy_verify_service import CopyVerifyService
        from .services.hash_service import HashService  # You may need to create this
        from .services.copy_hash_verify_success import CopyHashVerifySuccessBuilder

        # Register services
        register_service(ICopyVerifyService, CopyVerifyService())
        register_service(IHashService, HashService())
        register_service(ICopyHashVerifySuccessService, CopyHashVerifySuccessBuilder())

        logger.info("Copy/Hash/Verify services registered successfully")

    except Exception as e:
        logger.error(f"Failed to register Copy/Hash/Verify services: {e}")
        raise


# Auto-register on module import
try:
    register_services()
except Exception as e:
    logger.error(f"Copy/Hash/Verify module registration failed: {e}")


__all__ = [
    'register_services',
]
```

### Step 5.2: Update Main Application Import

**File:** `main.py` or wherever modules are imported

Add import to trigger registration:
```python
# Import copy_hash_verify module (triggers service registration)
import copy_hash_verify
```

### Step 5.3: Validate Registration

**Test:**
```python
# This should work after registration
from core.services import get_service
from copy_hash_verify.services.interfaces import ICopyVerifyService

service = get_service(ICopyVerifyService)
print(f"Service retrieved: {service}")
```

---

## Phase 6: Create HashService (if needed)

**Duration:** 1 hour

**Priority:** MEDIUM

**Objective:** If `HashService` doesn't exist, create it to handle hash calculations.

### Step 6.1: Check if HashService Exists

Look for `copy_hash_verify/services/hash_service.py`.

If it doesn't exist, create it:

**File:** `copy_hash_verify/services/hash_service.py`

```python
#!/usr/bin/env python3
"""
Hash Service - Business logic for hash calculations

Handles:
- File hash calculation
- Hash verification
- Algorithm validation
"""

import hashlib
from pathlib import Path

from core.services.base_service import BaseService
from core.result_types import Result
from core.exceptions import HashCalculationError
from core.logger import logger
from copy_hash_verify.services.interfaces import IHashService


class HashService(BaseService, IHashService):
    """
    Service for hash calculation and verification

    Supports: SHA-256, SHA-1, MD5
    """

    SUPPORTED_ALGORITHMS = ['sha256', 'sha1', 'md5']

    def __init__(self):
        super().__init__("HashService")

    def calculate_file_hash(
        self,
        file_path: Path,
        algorithm: str = 'sha256'
    ) -> Result[str]:
        """
        Calculate hash for a single file

        Args:
            file_path: Path to file
            algorithm: Hash algorithm (sha256, sha1, md5)

        Returns:
            Result[str]: Hex digest hash string
        """
        logger.debug(f"Calculating {algorithm} hash for: {file_path}")

        try:
            # Validate algorithm
            if algorithm.lower() not in self.SUPPORTED_ALGORITHMS:
                return Result.error(HashCalculationError(
                    f"Unsupported algorithm: {algorithm}",
                    user_message=f"Hash algorithm '{algorithm}' is not supported"
                ))

            # Validate file exists
            if not file_path.exists():
                return Result.error(HashCalculationError(
                    f"File not found: {file_path}",
                    user_message=f"Cannot hash non-existent file: {file_path.name}"
                ))

            if not file_path.is_file():
                return Result.error(HashCalculationError(
                    f"Not a file: {file_path}",
                    user_message=f"Cannot hash directory: {file_path.name}"
                ))

            # Create hasher
            hasher = hashlib.new(algorithm.lower())

            # Read file in chunks
            CHUNK_SIZE = 1024 * 1024  # 1MB chunks
            with open(file_path, 'rb') as f:
                while chunk := f.read(CHUNK_SIZE):
                    hasher.update(chunk)

            # Get hex digest
            hash_value = hasher.hexdigest()

            logger.debug(f"Hash calculated: {hash_value[:16]}...")
            return Result.success(hash_value)

        except PermissionError as e:
            return Result.error(HashCalculationError(
                f"Permission denied: {file_path}",
                user_message=f"Cannot read file: {file_path.name}"
            ))
        except Exception as e:
            logger.exception(f"Error calculating hash for {file_path}")
            return Result.error(HashCalculationError(
                f"Hash calculation failed: {str(e)}",
                user_message=f"Failed to calculate hash for {file_path.name}"
            ))

    def verify_file_integrity(
        self,
        source_hash: str,
        dest_hash: str,
        file_path: Path
    ) -> Result[bool]:
        """
        Verify file integrity by comparing hashes

        Args:
            source_hash: Hash of source file
            dest_hash: Hash of destination file
            file_path: File path being verified

        Returns:
            Result[bool]: True if hashes match
        """
        logger.debug(f"Verifying integrity for: {file_path}")

        try:
            # Compare hashes (case-insensitive)
            if source_hash.lower() == dest_hash.lower():
                logger.debug(f"Integrity verified: {file_path}")
                return Result.success(True)
            else:
                logger.warning(f"Hash mismatch for {file_path}: {source_hash} != {dest_hash}")
                return Result.error(HashCalculationError(
                    f"Hash mismatch for {file_path}",
                    user_message=f"File integrity check failed: {file_path.name}"
                ))

        except Exception as e:
            logger.exception(f"Error verifying integrity for {file_path}")
            return Result.error(HashCalculationError(
                f"Verification error: {str(e)}",
                user_message=f"Could not verify: {file_path.name}"
            ))
```

---

## Phase 7: Testing and Validation

**Duration:** 3-4 hours

**Priority:** HIGH

**Objective:** Comprehensive testing of refactored architecture.

### Step 7.1: Unit Test Controller

**File:** `copy_hash_verify/tests/test_copy_hash_verify_controller.py`

```python
"""
Unit tests for CopyHashVerifyController
"""

import pytest
from pathlib import Path
from copy_hash_verify.controllers import CopyHashVerifyController, CopyVerifySettings


def test_controller_creation():
    """Test controller can be created"""
    controller = CopyHashVerifyController()
    assert controller is not None
    assert controller.name == "CopyHashVerifyController"


def test_controller_service_injection():
    """Test services are lazily injected"""
    controller = CopyHashVerifyController()

    # Services should be None initially
    assert controller._copy_verify_service is None

    # Accessing property should inject service
    service = controller.copy_verify_service
    assert service is not None
    assert controller._copy_verify_service is not None


def test_controller_cleanup():
    """Test controller cleanup releases resources"""
    controller = CopyHashVerifyController()

    # Should not raise
    controller.cleanup()


# Add more tests...
```

### Step 7.2: Unit Test Services

**File:** `copy_hash_verify/tests/test_copy_verify_service.py`

```python
"""
Unit tests for CopyVerifyService
"""

import pytest
from pathlib import Path
from copy_hash_verify.services.copy_verify_service import CopyVerifyService


def test_service_creation():
    """Test service can be created"""
    service = CopyVerifyService()
    assert service is not None


def test_validate_copy_operation_no_sources():
    """Test validation fails with no sources"""
    service = CopyVerifyService()

    result = service.validate_copy_operation(
        source_paths=[],
        destination=Path("/tmp"),
        preserve_structure=True
    )

    assert not result.success
    assert "No source paths" in str(result.error)


# Add more tests for each service method...
```

### Step 7.3: Integration Test Full Workflow

**File:** `copy_hash_verify/tests/test_integration.py`

```python
"""
Integration tests for full copy/hash/verify workflow
"""

import pytest
import tempfile
from pathlib import Path
from copy_hash_verify.controllers import CopyHashVerifyController, CopyVerifySettings


def test_full_copy_verify_workflow():
    """Test complete copy+verify workflow"""

    # Create temp source and dest
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create test files
        source_dir = tmpdir / "source"
        source_dir.mkdir()
        test_file = source_dir / "test.txt"
        test_file.write_text("Hello World")

        dest_dir = tmpdir / "dest"
        dest_dir.mkdir()

        # Create controller
        controller = CopyHashVerifyController()

        # Start workflow
        settings = CopyVerifySettings(calculate_hashes=True)
        result = controller.start_copy_verify_workflow(
            source_paths=[test_file],
            destination=dest_dir,
            settings=settings
        )

        assert result.success
        worker = result.value
        assert worker is not None

        # Cleanup
        controller.cleanup()


# Add more integration tests...
```

### Step 7.4: Manual Testing Checklist

Test the UI manually:

- [ ] Application launches without errors
- [ ] Copy & Verify tab loads correctly
- [ ] Storage detection display works
- [ ] Can select source files
- [ ] Can select destination folder
- [ ] Copy operation starts successfully
- [ ] Progress updates appear
- [ ] Operation completes successfully
- [ ] Success dialog appears with correct data
- [ ] CSV export works
- [ ] Error handling works (invalid paths, insufficient space, etc.)

### Step 7.5: Run All Tests

```bash
# Run unit tests
"C:\Users\kriss\anaconda3\envs\hash_media\python.exe" -m pytest copy_hash_verify/tests/ -v

# Run integration tests
"C:\Users\kriss\anaconda3\envs\hash_media\python.exe" -m pytest copy_hash_verify/tests/test_integration.py -v
```

---

## Phase 8: Documentation and Cleanup

**Duration:** 1 hour

**Priority:** LOW

**Objective:** Update documentation to reflect new architecture.

### Step 8.1: Update CLAUDE.md

**File:** `CLAUDE.md`

Add section about Copy Hash Verify architecture:

```markdown
### Copy Hash Verify Module Architecture

**NEW:** Refactored to match Media Analysis SOA/DI pattern (completed 2025-10-XX)

#### Controller Layer
- `CopyHashVerifyController` orchestrates all workflows
- Extends `BaseController` for service injection
- Manages worker lifecycle with `WorkerResourceCoordinator`

#### Service Layer
- `CopyVerifyService` - Validation, file collection, reports
- `HashService` - Hash calculation and verification
- `CopyHashVerifySuccessBuilder` - Success message construction
- All services implement interface contracts
- All methods return Result objects

#### UI Layer
- `copy_verify_tab.py` - Pure UI, delegates to controller
- No business logic in UI
- Uses dependency injection for services

#### Service Registration
- Auto-registers on module import via `__init__.py`
- Self-contained plugin architecture

#### Usage Pattern
```python
# UI creates controller
self.controller = CopyHashVerifyController()

# Delegate workflow to controller
result = self.controller.start_copy_verify_workflow(sources, dest, settings)

# Process results through service
message = self.success_builder.build_copy_verify_success_message(data)
```
```

### Step 8.2: Update Architecture Diagram

If you have an architecture diagram, update it to show:
- Controller layer between UI and Services
- Service interfaces
- Service registration module
- Dependency injection flow

### Step 8.3: Clean Up Old Code

Remove backup files and temporary refactoring artifacts:

```bash
# Remove backups if refactor is successful
rm -rf copy_hash_verify/refactor_backups/

# Remove any temporary test files
```

### Step 8.4: Create Refactor Summary

**File:** `copy_hash_verify/docs/REFACTOR_SUMMARY.md`

```markdown
# Copy Hash Verify SOA Refactor Summary

**Date:** 2025-10-XX

**Objective:** Refactor to match Media Analysis clean architecture

## Changes Made

### New Files Created
- `copy_hash_verify/controllers/copy_hash_verify_controller.py`
- `copy_hash_verify/services/copy_hash_verify_success.py`
- `copy_hash_verify/services/hash_service.py`
- `copy_hash_verify/__init__.py` (service registration)
- Multiple test files

### Files Modified
- `copy_hash_verify/services/copy_verify_service.py` (expanded)
- `copy_hash_verify/services/interfaces.py` (added methods)
- `ui/tabs/copy_verify_tab.py` (removed business logic)

### Lines of Code
- Added: ~1,200 lines (controller, services, tests)
- Removed: ~300 lines (business logic from UI)
- Net: +900 lines

## Architecture Improvements

### Before
- No controller
- Business logic in UI
- Incomplete services
- Manual worker management

### After
- Full controller layer
- Complete service layer
- Pure UI (only user interaction)
- Resource coordinator for workers
- Self-registering services

## Testing
- Unit tests: 15 tests passing
- Integration tests: 5 tests passing
- Manual UI testing: Complete

## Benefits
- Testable: Services can be unit tested
- Maintainable: Clear separation of concerns
- Consistent: Matches Media Analysis pattern
- Reusable: Services can be used by CLI or other modules
- Plugin-ready: Self-registration enables plugin architecture
```

---

## Phase 9: Final Validation and Commit

**Duration:** 30 minutes

**Priority:** HIGH

**Objective:** Final validation and git commit.

### Step 9.1: Run Full Test Suite

```bash
# Run all tests
"C:\Users\kriss\anaconda3\envs\hash_media\python.exe" -m pytest copy_hash_verify/tests/ -v --tb=short

# Check for any test failures
```

### Step 9.2: Test Application Launch

```bash
# Launch application
"C:\Users\kriss\anaconda3\envs\hash_media\python.exe" main.py

# Manually test Copy & Verify tab:
# 1. Select files
# 2. Select destination
# 3. Start copy
# 4. Wait for completion
# 5. Verify success dialog
# 6. Export CSV
```

### Step 9.3: Code Quality Check

```bash
# Check for import errors
"C:\Users\kriss\anaconda3\envs\hash_media\python.exe" -c "from copy_hash_verify.controllers import CopyHashVerifyController; print('✓ Controller imports')"
"C:\Users\kriss\anaconda3\envs\hash_media\python.exe" -c "from copy_hash_verify.services.copy_verify_service import CopyVerifyService; print('✓ Service imports')"
"C:\Users\kriss\anaconda3\envs\hash_media\python.exe" -c "from ui.tabs.copy_verify_tab import CopyVerifyTab; print('✓ UI imports')"
```

### Step 9.4: Git Commit

```bash
# Check status
git status

# Add all changes
git add copy_hash_verify/
git add ui/tabs/copy_verify_tab.py
git add CLAUDE.md

# Commit with comprehensive message
git commit -m "$(cat <<'EOF'
refactor: Implement SOA/DI architecture for Copy Hash Verify module

Refactor copy_hash_verify module to match the clean architecture
demonstrated in media_analysis module.

PHASE 1: Controller Layer
- Create CopyHashVerifyController extending BaseController
- Orchestrates all copy/hash/verify workflows
- Manages worker lifecycle with ResourceCoordinator
- Implements service injection via DI pattern

PHASE 2-3: Service Layer
- Expand CopyVerifyService with all business logic
- Add HashService for hash calculations
- Create CopyHashVerifySuccessBuilder for messages
- All services implement interface contracts
- All methods return Result objects

PHASE 4: UI Layer Refactor
- Remove ALL business logic from copy_verify_tab.py
- Delegate all operations to controller
- Pure UI: only event handling and state management
- Use dependency injection for services

PHASE 5: Service Registration
- Add __init__.py with auto-registration
- Self-contained plugin architecture
- Services register on module import

Testing:
- Unit tests for controller and services
- Integration tests for full workflow
- Manual UI testing complete

Architecture Benefits:
- Testable: Service layer can be unit tested
- Maintainable: Clear separation of concerns
- Consistent: Matches Media Analysis pattern
- Reusable: Services usable by CLI/other modules
- Plugin-ready: Self-registration pattern

Files Added:
- copy_hash_verify/controllers/copy_hash_verify_controller.py
- copy_hash_verify/services/copy_hash_verify_success.py
- copy_hash_verify/services/hash_service.py
- copy_hash_verify/__init__.py
- Multiple test files

Files Modified:
- copy_hash_verify/services/copy_verify_service.py (expanded)
- copy_hash_verify/services/interfaces.py (complete)
- ui/tabs/copy_verify_tab.py (business logic removed)

Lines Changed: ~1,200 added, ~300 removed

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### Step 9.5: Push to Remote

```bash
# Push feature branch
git push origin copy-hash-verify-soa-refactor

# Create pull request (optional)
```

---

## Appendix A: Common Issues and Solutions

### Issue: Service Not Found

**Error:**
```
ValueError: No service registered for interface ICopyVerifyService
```

**Solution:**
Ensure services are registered. Check:
1. `copy_hash_verify/__init__.py` exists with `register_services()`
2. Module is imported somewhere (triggers registration)
3. Registration didn't fail silently (check logs)

### Issue: Circular Import

**Error:**
```
ImportError: cannot import name 'CopyHashVerifyController' from partially initialized module
```

**Solution:**
Move imports inside methods (lazy import):
```python
def method(self):
    from copy_hash_verify.controllers import CopyHashVerifyController
    # use controller
```

### Issue: Worker Not Cleaning Up

**Problem:** Memory leaks, workers not stopping

**Solution:**
Ensure controller cleanup is called:
```python
def closeEvent(self, event):
    if self.controller:
        self.controller.cleanup()
    super().closeEvent(event)
```

### Issue: Result Object Errors

**Error:**
```
AttributeError: 'Result' object has no attribute 'value'
```

**Solution:**
Always check success before accessing value:
```python
result = service.method()
if result.success:
    data = result.value  # Safe
else:
    error = result.error  # Handle error
```

---

## Appendix B: Verification Checklist

Use this checklist to verify refactoring is complete:

### Controller Layer
- [ ] `CopyHashVerifyController` exists and extends `BaseController`
- [ ] Services injected via `@property` and `_get_service()`
- [ ] All methods return `Result` objects
- [ ] No business logic (only orchestration)
- [ ] Uses `WorkerResourceCoordinator`
- [ ] Has `cleanup()` method

### Service Layer
- [ ] `CopyVerifyService` implements all interface methods
- [ ] `HashService` exists (if needed)
- [ ] `CopyHashVerifySuccessBuilder` exists
- [ ] All services extend `BaseService`
- [ ] All services implement interfaces
- [ ] All methods return `Result` objects
- [ ] No UI dependencies

### UI Layer
- [ ] `copy_verify_tab.py` has NO business logic
- [ ] Controller created in `__init__`
- [ ] All operations delegate to controller
- [ ] Success builder injected via `get_service()`
- [ ] No direct worker creation
- [ ] Cleanup calls `controller.cleanup()`

### Service Registration
- [ ] `copy_hash_verify/__init__.py` exists
- [ ] Has `register_services()` function
- [ ] Auto-registers on import
- [ ] Module imported in main application

### Testing
- [ ] Unit tests for controller
- [ ] Unit tests for services
- [ ] Integration tests for full workflow
- [ ] Manual UI testing complete
- [ ] All tests passing

### Documentation
- [ ] CLAUDE.md updated
- [ ] Refactor summary created
- [ ] Code comments added
- [ ] Docstrings complete

### Git
- [ ] All changes committed
- [ ] Descriptive commit message
- [ ] Feature branch pushed
- [ ] PR created (if applicable)

---

## Appendix C: Reference Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         UI Layer                            │
│  (copy_verify_tab.py)                                       │
│                                                             │
│  - Pure UI (widgets, event handlers)                       │
│  - Delegates to controller                                 │
│  - No business logic                                       │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼ (uses)
┌─────────────────────────────────────────────────────────────┐
│                    Controller Layer                         │
│  (CopyHashVerifyController)                                 │
│                                                             │
│  - Orchestrates workflows                                  │
│  - Injects services via DI                                 │
│  - Manages worker lifecycle                                │
│  - Returns Result objects                                  │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼ (injects & delegates)
┌─────────────────────────────────────────────────────────────┐
│                     Service Layer                           │
│  (CopyVerifyService, HashService, SuccessBuilder)          │
│                                                             │
│  - ALL business logic                                      │
│  - Implements interfaces                                   │
│  - Returns Result objects                                  │
│  - No UI dependencies                                      │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼ (uses)
┌─────────────────────────────────────────────────────────────┐
│                     Worker Layer                            │
│  (CopyVerifyWorker)                                         │
│                                                             │
│  - QThread for background operations                       │
│  - Emits signals (result_ready, progress_update)          │
│  - Tracked by ResourceCoordinator                          │
└─────────────────────────────────────────────────────────────┘

SERVICE REGISTRATION FLOW:
┌──────────────────────┐
│  main.py imports     │
│  copy_hash_verify    │
└──────────────────────┘
           │
           ▼
┌──────────────────────┐
│ __init__.py runs     │
│ register_services()  │
└──────────────────────┘
           │
           ▼
┌──────────────────────┐
│ Services registered  │
│ in ServiceRegistry   │
└──────────────────────┘
           │
           ▼
┌──────────────────────┐
│ Controller injects   │
│ via get_service()    │
└──────────────────────┘
```

---

## Appendix D: Code Patterns Reference

### Pattern 1: Service Injection in Controller

```python
@property
def service_name(self) -> IServiceInterface:
    """Lazy-load service via DI"""
    if self._service_name is None:
        self._service_name = self._get_service(IServiceInterface)
    return self._service_name
```

### Pattern 2: Result Object Returns

```python
def method(self, args) -> Result[ReturnType]:
    """Method that returns Result object"""
    try:
        # Business logic
        result_data = do_something()
        return Result.success(result_data)
    except Exception as e:
        error = FSAError(
            f"Technical error: {str(e)}",
            user_message="User-friendly error message"
        )
        return Result.error(error)
```

### Pattern 3: UI Delegation to Controller

```python
def _on_button_click(self):
    """Button click handler - delegate to controller"""
    # Build request from UI state
    settings = self._build_settings_from_ui()

    # Delegate to controller
    result = self.controller.start_workflow(settings)

    # Handle result
    if result.success:
        data = result.value
        # Update UI with success
    else:
        error = result.error
        # Show error to user
```

### Pattern 4: Service Registration

```python
def register_services():
    """Register module services"""
    from core.services import register_service, get_service

    # Check if already registered (idempotent)
    try:
        get_service(IModuleService)
        return  # Already registered
    except ValueError:
        pass

    # Import and register
    from .services.module_service import ModuleService
    register_service(IModuleService, ModuleService())
    logger.info("Services registered")

# Auto-register on import
try:
    register_services()
except Exception as e:
    logger.error(f"Registration failed: {e}")
```

---

## End of Refactoring Plan

This document provides complete step-by-step instructions for refactoring the `copy_hash_verify` module to match the clean SOA/DI/Controller architecture demonstrated in the `media_analysis` module.

Follow each phase sequentially, validate at each step, and use the reference implementation as a guide throughout the process.

**Estimated Total Time:** 13-18 hours

**Priority Phases:** 1, 2, 4, 7 (HIGH priority, ~10-14 hours)

Good luck with the refactoring! 🚀
