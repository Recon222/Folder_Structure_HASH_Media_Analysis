#!/usr/bin/env python3
"""
Copy Verify Service - Business logic for copy and verify operations

Provides validation, destination checking, and business logic for copy operations
with integrated hash verification.
"""

import os
import shutil
from pathlib import Path
from typing import List

from .interfaces import ICopyVerifyService
from core.result_types import Result
from core.exceptions import ValidationError, FileOperationError
from core.logger import logger


class CopyVerifyService(ICopyVerifyService):
    """Service for copy and verify operations"""

    MIN_FREE_SPACE_MB = 100  # Require at least 100MB free
    SPACE_BUFFER_MULTIPLIER = 1.2  # Require 20% extra space as buffer

    def __init__(self):
        """Initialize copy verify service"""
        self.name = "CopyVerifyService"
        logger.info(f"{self.name} initialized")

    def validate_copy_operation(
        self,
        source_paths: List[Path],
        destination: Path,
        preserve_structure: bool = False
    ) -> Result[bool]:
        """
        Validate copy operation parameters

        Args:
            source_paths: Source file/folder paths
            destination: Destination directory
            preserve_structure: Whether to preserve folder structure

        Returns:
            Result[bool] indicating validation success
        """
        # Check if source paths provided
        if not source_paths or len(source_paths) == 0:
            error = ValidationError(
                "No source paths provided",
                user_message="Please select at least one file or folder to copy."
            )
            return Result.error(error)

        # Check if destination provided
        if not destination:
            error = ValidationError(
                "No destination provided",
                user_message="Please select a destination folder."
            )
            return Result.error(error)

        # Check if source paths exist
        missing_paths = []
        for path in source_paths:
            if not path.exists():
                missing_paths.append(str(path))

        if missing_paths:
            error = ValidationError(
                f"Some source paths do not exist: {', '.join(missing_paths[:3])}",
                user_message=f"{len(missing_paths)} source path(s) do not exist."
            )
            return Result.error(error)

        # Check if destination is writable (or can be created)
        if destination.exists():
            if not destination.is_dir():
                error = ValidationError(
                    f"Destination exists but is not a directory: {destination}",
                    user_message="Destination must be a directory, not a file."
                )
                return Result.error(error)

            if not os.access(destination, os.W_OK):
                error = ValidationError(
                    f"Destination is not writable: {destination}",
                    user_message="You do not have permission to write to the destination folder."
                )
                return Result.error(error)
        else:
            # Check if parent directory exists and is writable
            parent = destination.parent
            if not parent.exists():
                error = ValidationError(
                    f"Parent directory does not exist: {parent}",
                    user_message="The parent directory for the destination does not exist."
                )
                return Result.error(error)

            if not os.access(parent, os.W_OK):
                error = ValidationError(
                    f"Cannot create destination directory: {destination}",
                    user_message="You do not have permission to create the destination folder."
                )
                return Result.error(error)

        # Calculate total size needed
        total_size = 0
        file_count = 0
        for path in source_paths:
            if path.is_file():
                total_size += path.stat().st_size
                file_count += 1
            elif path.is_dir():
                for file_path in path.rglob('*'):
                    if file_path.is_file():
                        try:
                            total_size += file_path.stat().st_size
                            file_count += 1
                        except Exception as e:
                            logger.warning(f"Could not stat file {file_path}: {e}")

        logger.info(
            f"Copy operation parameters: {file_count} files, "
            f"{total_size / (1024*1024):.2f} MB, "
            f"preserve_structure={preserve_structure}"
        )

        # Check destination space
        space_check = self.check_destination_availability(
            destination,
            file_count,
            total_size
        )

        if not space_check.success:
            return space_check

        logger.info(f"Copy operation validated successfully")
        return Result.success(True)

    def check_destination_availability(
        self,
        destination: Path,
        expected_file_count: int,
        expected_size_bytes: int
    ) -> Result[bool]:
        """
        Check if destination has enough space and is writable

        Args:
            destination: Destination directory
            expected_file_count: Number of files to be copied
            expected_size_bytes: Total size of files to copy

        Returns:
            Result[bool] indicating destination is ready
        """
        try:
            # Get disk usage for destination
            if destination.exists():
                usage = shutil.disk_usage(destination)
            else:
                # Use parent directory
                usage = shutil.disk_usage(destination.parent)

            free_space_bytes = usage.free
            free_space_mb = free_space_bytes / (1024 * 1024)
            required_space_bytes = expected_size_bytes * self.SPACE_BUFFER_MULTIPLIER
            required_space_mb = required_space_bytes / (1024 * 1024)

            logger.info(
                f"Destination space check: {free_space_mb:.2f} MB free, "
                f"{required_space_mb:.2f} MB required (with buffer)"
            )

            # Check minimum free space
            if free_space_mb < self.MIN_FREE_SPACE_MB:
                error = FileOperationError(
                    f"Destination has only {free_space_mb:.2f} MB free",
                    user_message=f"Destination has insufficient free space ({free_space_mb:.0f} MB). At least {self.MIN_FREE_SPACE_MB} MB required."
                )
                return Result.error(error)

            # Check if enough space for operation
            if free_space_bytes < required_space_bytes:
                error = FileOperationError(
                    f"Insufficient space: {free_space_mb:.2f} MB free, {required_space_mb:.2f} MB needed",
                    user_message=f"Not enough space at destination. Need {required_space_mb:.0f} MB, but only {free_space_mb:.0f} MB available."
                )
                return Result.error(error)

            logger.info("Destination has sufficient space")
            return Result.success(True)

        except Exception as e:
            logger.error(f"Error checking destination space: {e}", exc_info=True)
            error = FileOperationError(
                f"Failed to check destination space: {e}",
                user_message="Could not verify destination has enough space. Operation may fail."
            )
            return Result.error(error)
