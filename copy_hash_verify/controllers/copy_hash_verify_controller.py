#!/usr/bin/env python3
"""
Copy Hash Verify Controller - Orchestrates copy, hash, and verify workflows
Follows SOA/DI pattern demonstrated in MediaAnalysisController
"""

from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

from controllers.base_controller import BaseController
from core.result_types import Result
from core.exceptions import ValidationError, FileOperationError
from core.logger import logger
from core.resource_coordinators import WorkerResourceCoordinator
from copy_hash_verify.services.interfaces import ICopyVerifyService, IHashService
from copy_hash_verify.core.workers.copy_verify_worker import CopyVerifyWorker
from copy_hash_verify.core.workers.hash_worker import HashWorker
from copy_hash_verify.core.workers.verify_worker import VerifyWorker


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

        # Current worker tracking
        self.current_worker: Optional[object] = None
        self._current_worker_id: Optional[str] = None

        # Lazy-loaded services (injected on first access)
        self._copy_verify_service = None
        self._hash_service = None

    def _create_resource_coordinator(self, component_id: str) -> WorkerResourceCoordinator:
        """Use WorkerResourceCoordinator for worker management"""
        return WorkerResourceCoordinator(component_id)

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
        try:
            self._log_operation(
                "start_copy_verify_workflow",
                f"Starting copy of {len(source_paths)} sources to {destination.name}"
            )

            # Step 1: Validate operation through service
            validation_result = self.copy_verify_service.validate_copy_operation(
                source_paths=source_paths,
                destination=destination,
                preserve_structure=settings.preserve_structure
            )

            if not validation_result.success:
                self._handle_error(validation_result.error)
                return Result.error(validation_result.error)

            logger.info("Copy operation validation passed")

            # Step 2: Create worker
            worker = CopyVerifyWorker(
                source_paths=source_paths,
                destination=destination,
                algorithm=settings.algorithm,
                preserve_structure=settings.preserve_structure,
                calculate_hashes=settings.calculate_hashes
            )

            # Store reference
            self.current_worker = worker

            # Step 3: Track worker with resource coordinator
            if self.resources:
                self._current_worker_id = self.resources.track_worker(
                    worker=worker,
                    name=f"copy_verify_{datetime.now():%H%M%S}"
                )
                logger.debug(f"Worker tracked with ID: {self._current_worker_id}")

            logger.info("Copy+verify workflow started successfully")
            return Result.success(worker)

        except Exception as e:
            error = FileOperationError(
                f"Failed to start copy+verify workflow: {str(e)}",
                user_message="Failed to start copy operation. Please check the logs."
            )
            logger.exception("Unexpected error in start_copy_verify_workflow")
            self._handle_error(error)
            return Result.error(error)

    def start_hash_calculation_workflow(
        self,
        paths: List[Path],
        algorithm: str = 'sha256'
    ) -> Result[HashWorker]:
        """
        Orchestrate hash calculation workflow

        Workflow:
        1. Validate inputs through service
        2. Create worker
        3. Track worker
        4. Return worker

        Args:
            paths: List of files/folders to hash
            algorithm: Hash algorithm to use

        Returns:
            Result[HashWorker]: Success with worker, or error
        """
        try:
            self._log_operation(
                "start_hash_calculation_workflow",
                f"Starting hash calculation for {len(paths)} items"
            )

            # Step 1: Validate through service
            validation_result = self.hash_service.validate_hash_operation(
                paths=paths,
                algorithm=algorithm
            )

            if not validation_result.success:
                self._handle_error(validation_result.error)
                return Result.error(validation_result.error)

            logger.info("Hash operation validation passed")

            # Step 2: Create worker
            worker = HashWorker(
                paths=paths,
                algorithm=algorithm
            )

            # Store reference
            self.current_worker = worker

            # Step 3: Track worker
            if self.resources:
                self._current_worker_id = self.resources.track_worker(
                    worker=worker,
                    name=f"hash_{datetime.now():%H%M%S}"
                )

            logger.info("Hash calculation workflow started successfully")
            return Result.success(worker)

        except Exception as e:
            error = FileOperationError(
                f"Failed to start hash workflow: {str(e)}",
                user_message="Failed to start hash calculation."
            )
            logger.exception("Unexpected error in start_hash_calculation_workflow")
            self._handle_error(error)
            return Result.error(error)

    def start_verification_workflow(
        self,
        source_paths: List[Path],
        target_paths: List[Path],
        algorithm: str = 'sha256'
    ) -> Result[VerifyWorker]:
        """
        Orchestrate hash verification workflow

        Workflow:
        1. Validate inputs through service
        2. Create worker
        3. Track worker
        4. Return worker

        Args:
            source_paths: Source files/folders
            target_paths: Target files/folders
            algorithm: Hash algorithm to use

        Returns:
            Result[VerifyWorker]: Success with worker, or error
        """
        try:
            self._log_operation(
                "start_verification_workflow",
                f"Starting verification of {len(source_paths)} sources"
            )

            # Step 1: Validate through service
            validation_result = self.hash_service.validate_verification_operation(
                source_paths=source_paths,
                target_paths=target_paths,
                algorithm=algorithm
            )

            if not validation_result.success:
                self._handle_error(validation_result.error)
                return Result.error(validation_result.error)

            logger.info("Verification operation validation passed")

            # Step 2: Create worker
            worker = VerifyWorker(
                source_paths=source_paths,
                target_paths=target_paths,
                algorithm=algorithm
            )

            # Store reference
            self.current_worker = worker

            # Step 3: Track worker
            if self.resources:
                self._current_worker_id = self.resources.track_worker(
                    worker=worker,
                    name=f"verify_{datetime.now():%H%M%S}"
                )

            logger.info("Verification workflow started successfully")
            return Result.success(worker)

        except Exception as e:
            error = FileOperationError(
                f"Failed to start verification workflow: {str(e)}",
                user_message="Failed to start hash verification."
            )
            logger.exception("Unexpected error in start_verification_workflow")
            self._handle_error(error)
            return Result.error(error)

    def cancel_current_operation(self):
        """Cancel the current operation if running"""
        if self.current_worker and hasattr(self.current_worker, 'isRunning') and self.current_worker.isRunning():
            self._log_operation("cancel_current_operation", "Cancelling operation")

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
        logger.info("Operation cancelled")

    def cleanup(self):
        """
        Clean up controller resources

        Releases worker tracking and cleans up service resources.
        """
        logger.debug("Cleaning up CopyHashVerifyController")

        # Cancel any running operation
        if self.current_worker:
            self.cancel_current_operation()

        # Let resource coordinator handle cleanup
        if self.resources:
            self.resources.cleanup_all()

        # Clear references
        self.current_worker = None
        self._current_worker_id = None

        # Parent cleanup
        super().cleanup()
