#!/usr/bin/env python3
"""
Hash Verification Controller - Orchestrates hash verification workflows
Follows SOA/DI pattern for Verify Hashes tab
"""

from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime

from controllers.base_controller import BaseController
from core.result_types import Result
from core.exceptions import ValidationError, FileOperationError
from core.logger import logger
from core.resource_coordinators import WorkerResourceCoordinator
from copy_hash_verify.services.interfaces import IHashService
from copy_hash_verify.core.workers.verify_worker import VerifyWorker
from copy_hash_verify.core.storage_detector import StorageDetector, StorageInfo


@dataclass
class HashVerificationSettings:
    """Settings for hash verification operations"""
    algorithm: str = 'sha256'
    enable_parallel: bool = True
    max_workers_override: Optional[int] = None
    generate_csv: bool = True
    include_metadata: bool = True


class HashVerificationController(BaseController):
    """
    Controller for hash verification operations (Verify Hashes tab)

    Responsibilities:
    - Workflow orchestration (no business logic)
    - Service injection and delegation
    - Worker lifecycle management
    - Storage detection coordination (source AND target)
    - Resource coordination

    Pattern:
    1. Validate inputs through service
    2. Detect storage if needed
    3. Create and track worker
    4. Return Result object
    """

    def __init__(self):
        """Initialize controller with service injection"""
        super().__init__("HashVerificationController")

        # Current worker tracking
        self.current_worker: Optional[VerifyWorker] = None
        self._current_worker_id: Optional[str] = None

        # Lazy-loaded services (injected on first access)
        self._hash_service = None
        self._storage_detector = None

    def _create_resource_coordinator(self, component_id: str) -> WorkerResourceCoordinator:
        """Use WorkerResourceCoordinator for worker management"""
        return WorkerResourceCoordinator(component_id)

    @property
    def hash_service(self) -> IHashService:
        """Lazy-load hash service via DI"""
        if self._hash_service is None:
            self._hash_service = self._get_service(IHashService)
        return self._hash_service

    @property
    def storage_detector(self) -> StorageDetector:
        """Lazy-load storage detector (not a registered service, direct instantiation)"""
        if self._storage_detector is None:
            self._storage_detector = StorageDetector()
        return self._storage_detector

    def start_verification_workflow(
        self,
        source_paths: List[Path],
        target_paths: List[Path],
        settings: HashVerificationSettings
    ) -> Result[VerifyWorker]:
        """
        Orchestrate hash verification workflow

        Workflow:
        1. Validate inputs through service
        2. Create worker with settings
        3. Track worker with resource coordinator
        4. Return worker wrapped in Result

        Args:
            source_paths: List of source files/folders to verify
            target_paths: List of target files/folders to verify against
            settings: Verification settings

        Returns:
            Result[VerifyWorker]: Success with worker, or error
        """
        try:
            self._log_operation(
                "start_verification_workflow",
                f"Starting verification for {len(source_paths)} source items and {len(target_paths)} target items with {settings.algorithm.upper()}"
            )

            # Step 1: Validate through service
            validation_result = self.hash_service.validate_verification_operation(
                source_paths=source_paths,
                target_paths=target_paths,
                algorithm=settings.algorithm
            )

            if not validation_result.success:
                self._handle_error(validation_result.error)
                return Result.error(validation_result.error)

            logger.info("Verification operation validation passed")

            # Step 2: Create worker with settings
            # Note: VerifyWorker doesn't support parallel settings yet (unlike HashWorker)
            # TODO: Add parallel processing support to VerifyWorker in future
            worker = VerifyWorker(
                source_paths=source_paths,
                target_paths=target_paths,
                algorithm=settings.algorithm
            )

            # Store reference
            self.current_worker = worker

            # Step 3: Track worker with resource coordinator
            if self.resources:
                self._current_worker_id = self.resources.track_worker(
                    worker=worker,
                    name=f"hash_verify_{datetime.now():%H%M%S}"
                )
                logger.debug(f"Worker tracked with ID: {self._current_worker_id}")

            logger.info("Verification workflow started successfully")
            return Result.success(worker)

        except Exception as e:
            error = FileOperationError(
                f"Failed to start verification workflow: {str(e)}",
                user_message="Failed to start hash verification. Please check the logs."
            )
            logger.exception("Unexpected error in start_verification_workflow")
            self._handle_error(error)
            return Result.error(error)

    def detect_storage(self, path: Path) -> Result[StorageInfo]:
        """
        Detect storage type for given path

        Delegates to StorageDetector but wraps in Result object
        for consistent error handling.

        NOTE: Thread count calculation is done by ThreadCalculator in the UI layer
        using the returned StorageInfo + file_count + operation_type.

        Args:
            path: Path to analyze

        Returns:
            Result[StorageInfo]: Storage information or error
        """
        try:
            self._log_operation(
                "detect_storage",
                f"Detecting storage for {path}"
            )

            storage_info = self.storage_detector.analyze_path(path)

            logger.info(
                f"Storage detected: {storage_info.drive_type.value} on {storage_info.drive_letter}, "
                f"bus_type={storage_info.bus_type.name} "
                f"(confidence: {storage_info.confidence:.0%}, method: {storage_info.detection_method})"
            )

            return Result.success(storage_info)

        except Exception as e:
            error = FileOperationError(
                f"Failed to detect storage: {str(e)}",
                user_message="Storage detection failed. Will use default settings."
            )
            logger.warning(f"Storage detection error: {e}")
            self._handle_error(error)
            return Result.error(error)

    def cancel_current_operation(self):
        """Cancel the current operation if running"""
        if self.current_worker and hasattr(self.current_worker, 'isRunning') and self.current_worker.isRunning():
            self._log_operation("cancel_current_operation", "Cancelling hash verification")

            # Cancel the worker
            if hasattr(self.current_worker, 'cancel'):
                self.current_worker.cancel()

            # Wait for graceful shutdown
            if hasattr(self.current_worker, 'wait'):
                self.current_worker.wait(3000)  # Wait up to 3 seconds

            if hasattr(self.current_worker, 'isRunning') and self.current_worker.isRunning():
                logger.warning("Worker did not stop gracefully")

        # Clear references - coordinator handles cleanup
        self.current_worker = None
        self._current_worker_id = None
        logger.info("Hash verification cancelled")

    def cleanup(self):
        """
        Clean up controller resources

        Releases worker tracking and cleans up resources.
        """
        logger.debug("Cleaning up HashVerificationController")

        # Cancel any running operation
        if self.current_worker:
            self.cancel_current_operation()

        # Let resource coordinator handle cleanup
        if self.resources:
            self.resources.cleanup_all()

        # Clear references
        self.current_worker = None
        self._current_worker_id = None
        self._storage_detector = None

        # Parent cleanup
        super().cleanup()
