#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename Parser Controller - Orchestration layer for filename parsing operations

Coordinates between UI, services, and worker threads for batch video file processing.
Follows the VehicleTrackingController pattern for optional feature modules.
"""

from pathlib import Path
from typing import List, Optional
from datetime import datetime

from controllers.base_controller import BaseController
from core.result_types import Result
from core.exceptions import ValidationError, FileOperationError
from core.resource_coordinators import WorkerResourceCoordinator

# Import models
from filename_parser.models.filename_parser_models import FilenameParserSettings
from filename_parser.models.processing_result import ProcessingStatistics

# Import services (direct instantiation - not registered yet)
from filename_parser.services.filename_parser_service import FilenameParserService
from filename_parser.services.frame_rate_service import FrameRateService
from filename_parser.services.ffmpeg_metadata_writer_service import FFmpegMetadataWriterService
from filename_parser.services.batch_processor_service import BatchProcessorService
from filename_parser.services.csv_export_service import CSVExportService

# Import worker
from filename_parser.workers.filename_parser_worker import FilenameParserWorker


class FilenameParserController(BaseController):
    """
    Controller for filename parser operations

    Orchestrates the workflow of parsing video filenames, extracting time information,
    detecting frame rates, writing SMPTE timecode metadata, and generating reports.

    Follows the pattern established by VehicleTrackingController for optional
    feature modules with worker-based background processing.
    """

    def __init__(self):
        """Initialize filename parser controller"""
        super().__init__("FilenameParserController")

        # Service dependencies (lazy created - not in registry yet)
        self._batch_service: Optional[BatchProcessorService] = None

        # Current operation state
        self.current_worker: Optional[FilenameParserWorker] = None
        self._current_worker_id: Optional[str] = None
        self.current_settings: FilenameParserSettings = FilenameParserSettings()

        self._log_operation("initialized", "Filename parser controller ready")

    def _create_resource_coordinator(self, component_id: str) -> WorkerResourceCoordinator:
        """
        Create resource coordinator for worker management

        Args:
            component_id: Unique component identifier

        Returns:
            WorkerResourceCoordinator instance for tracking workers
        """
        return WorkerResourceCoordinator(component_id)

    @property
    def batch_service(self) -> BatchProcessorService:
        """
        Lazy create batch processor service with dependency injection

        Note: Services are directly instantiated because they're not registered
        in the ServiceRegistry yet. This will be refactored in Phase 8 (integration).

        Returns:
            BatchProcessorService instance with all dependencies injected
        """
        if self._batch_service is None:
            self._log_operation("creating_service", "Creating BatchProcessorService", level="debug")

            # Create sub-services
            parser_service = FilenameParserService()
            frame_rate_service = FrameRateService()
            metadata_writer_service = FFmpegMetadataWriterService()
            csv_export_service = CSVExportService()

            # Create batch service with dependency injection
            self._batch_service = BatchProcessorService(
                parser_service=parser_service,
                frame_rate_service=frame_rate_service,
                metadata_writer_service=metadata_writer_service,
                csv_export_service=csv_export_service
            )

            self._log_operation("service_created", "BatchProcessorService ready", level="debug")

        return self._batch_service

    def start_processing_workflow(
        self,
        files: List[Path],
        settings: Optional[FilenameParserSettings] = None
    ) -> Result[FilenameParserWorker]:
        """
        Start filename parsing workflow with worker thread

        This is the main entry point for processing video files. Creates and
        returns a worker thread that the UI can connect to for progress updates
        and results.

        Args:
            files: List of video file paths to process
            settings: Optional processing settings (uses defaults if not provided)

        Returns:
            Result containing FilenameParserWorker for UI to connect signals,
            or error if workflow cannot start
        """
        try:
            self._log_operation("start_workflow", f"Starting workflow for {len(files)} files")

            # Check for existing operation
            if self.current_worker and self.current_worker.isRunning():
                error = FileOperationError(
                    "Another filename parsing operation is in progress",
                    user_message="Please wait for the current operation to complete."
                )
                self._handle_error(error, {'method': 'start_processing_workflow'})
                return Result.error(error)

            # Validate inputs
            if not files:
                error = ValidationError(
                    {'files': 'No files selected'},
                    user_message="Please select video files to process."
                )
                self._handle_error(error, {'method': 'start_processing_workflow'})
                return Result.error(error)

            # Validate files exist and are readable
            valid_files = []
            invalid_files = []

            for file_path in files:
                if not file_path.exists():
                    invalid_files.append(f"{file_path.name} (does not exist)")
                elif not file_path.is_file():
                    invalid_files.append(f"{file_path.name} (not a file)")
                else:
                    valid_files.append(file_path)

            if not valid_files:
                error = ValidationError(
                    {'files': 'No valid files found'},
                    user_message=f"No valid files to process. Issues: {', '.join(invalid_files)}"
                )
                self._handle_error(error, {'method': 'start_processing_workflow'})
                return Result.error(error)

            if invalid_files:
                self._log_operation("validation",
                                  f"Skipping {len(invalid_files)} invalid files: {', '.join(invalid_files)}",
                                  level="warning")

            # Store settings
            if settings:
                self.current_settings = settings

            # Create worker with service injection
            self.current_worker = FilenameParserWorker(
                files=valid_files,
                settings=self.current_settings,
                batch_service=self.batch_service  # Inject service
            )

            # Track worker with resource coordinator
            if self.resources:
                self._current_worker_id = self.resources.track_worker(
                    self.current_worker,
                    name=f"filename_parser_{datetime.now():%H%M%S}",
                    cancel_on_cleanup=True,
                    auto_release=True
                )
                self._log_operation("worker_tracked",
                                  f"Worker tracked with ID: {self._current_worker_id}",
                                  level="debug")

            # Start worker
            self.current_worker.start()

            self._log_operation("workflow_started",
                              f"Processing {len(valid_files)} files with worker")

            return Result.success(self.current_worker)

        except Exception as e:
            error = FileOperationError(
                f"Failed to start filename parsing workflow: {e}",
                user_message="Failed to start filename parsing operation."
            )
            self._handle_error(error, {
                'method': 'start_processing_workflow',
                'exception': str(e),
                'file_count': len(files) if files else 0
            })
            return Result.error(error)

    def cancel_processing(self) -> None:
        """
        Cancel the current filename parsing operation if running

        Implements graceful cancellation with timeout and force terminate fallback.
        Follows VehicleTrackingController pattern for robust cancellation.
        """
        if self.current_worker and self.current_worker.isRunning():
            self._log_operation("cancel", "Cancelling filename parsing operation")

            # Request cancellation
            self.current_worker.cancel()

            # Wait gracefully (5 seconds)
            if not self.current_worker.wait(5000):
                # Force terminate if graceful cancel fails
                self._log_operation("cancel_force",
                                  "Worker did not stop gracefully, terminating",
                                  level="warning")
                self.current_worker.terminate()
                self.current_worker.wait(1000)  # Wait 1 more second

            # Cleanup references (coordinator handles resource cleanup)
            self.current_worker = None
            self._current_worker_id = None

            self._log_operation("cancel_complete", "Filename parsing cancelled")
        else:
            self._log_operation("cancel_skipped", "No operation to cancel", level="debug")

    def is_processing(self) -> bool:
        """
        Check if a filename parsing operation is currently active

        Returns:
            True if worker exists and is running, False otherwise
        """
        return self.current_worker is not None and self.current_worker.isRunning()

    def validate_files(self, files: List[Path]) -> Result[List[Path]]:
        """
        Validate video files for processing

        Args:
            files: List of file paths to validate

        Returns:
            Result containing list of valid files or error
        """
        try:
            if not files:
                error = ValidationError(
                    {'files': 'No files provided'},
                    user_message="Please select files to validate."
                )
                return Result.error(error)

            valid_files = []
            errors = []

            # Supported video extensions
            video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.m4v', '.mpg', '.mpeg', '.wmv'}

            for file_path in files:
                # Check existence
                if not file_path.exists():
                    errors.append(f"{file_path.name}: File does not exist")
                    continue

                # Check is file
                if not file_path.is_file():
                    errors.append(f"{file_path.name}: Not a file")
                    continue

                # Check extension
                if file_path.suffix.lower() not in video_extensions:
                    errors.append(f"{file_path.name}: Not a supported video format")
                    continue

                # Check readability
                try:
                    # Try to open file to verify read permissions
                    with open(file_path, 'rb') as f:
                        f.read(1)  # Read one byte
                    valid_files.append(file_path)
                except PermissionError:
                    errors.append(f"{file_path.name}: Permission denied")
                except Exception as e:
                    errors.append(f"{file_path.name}: Cannot read file - {e}")

            if not valid_files:
                error = ValidationError(
                    {'files': 'No valid files found'},
                    user_message=f"No valid files to process. Errors: {'; '.join(errors[:5])}"
                )
                return Result.error(error)

            # Return success with warnings if some files were invalid
            result = Result.success(valid_files)
            if errors:
                for error_msg in errors:
                    result.add_warning(error_msg)

            return result

        except Exception as e:
            error = ValidationError(
                {'validation': f'Validation failed: {e}'},
                user_message="Failed to validate files."
            )
            self._handle_error(error, {'method': 'validate_files'})
            return Result.error(error)

    def cleanup_resources(self) -> None:
        """
        Clean up all resources and cancel operations

        Called when controller is being destroyed or tab is closed.
        Ensures all workers are stopped and resources are released.
        """
        try:
            self._log_operation("cleanup", "Starting resource cleanup")

            # Cancel any running operations
            self.cancel_processing()

            # Clear service cache
            self._batch_service = None

            # Call base class cleanup (handles resource coordinator)
            self.cleanup()

            self._log_operation("cleanup_complete", "Resource cleanup complete")

        except Exception as e:
            self._log_operation("cleanup_error", f"Cleanup error: {e}", level="error")
