#!/usr/bin/env python3
"""
Hash Service - Business logic for hash calculation and verification operations

Provides validation, parameter checking, and business logic for hash operations
before workers are created.
"""

from pathlib import Path
from typing import List

from .interfaces import IHashService
from core.result_types import Result
from core.exceptions import ValidationError
from core.logger import logger


class HashService(IHashService):
    """Service for hash calculation and verification operations"""

    SUPPORTED_ALGORITHMS = ['sha256', 'sha1', 'md5']
    MAX_FILES_PER_OPERATION = 10000  # Reasonable limit for UI responsiveness

    def __init__(self):
        """Initialize hash service"""
        self.name = "HashService"
        logger.info(f"{self.name} initialized")

    def validate_hash_operation(
        self,
        paths: List[Path],
        algorithm: str
    ) -> Result[bool]:
        """
        Validate hash operation parameters

        Args:
            paths: List of file/folder paths to hash
            algorithm: Hash algorithm ('sha256', 'sha1', 'md5')

        Returns:
            Result[bool] indicating validation success
        """
        # Check if paths provided
        if not paths or len(paths) == 0:
            error = ValidationError(
                "No paths provided for hash operation",
                user_message="Please select at least one file or folder to hash."
            )
            return Result.error(error)

        # Check algorithm
        algorithm_lower = algorithm.lower()
        if algorithm_lower not in self.SUPPORTED_ALGORITHMS:
            error = ValidationError(
                f"Unsupported algorithm: {algorithm}",
                user_message=f"Algorithm must be one of: {', '.join(self.SUPPORTED_ALGORITHMS).upper()}"
            )
            return Result.error(error)

        # Check if paths exist
        missing_paths = []
        for path in paths:
            if not path.exists():
                missing_paths.append(str(path))

        if missing_paths:
            error = ValidationError(
                f"Some paths do not exist: {', '.join(missing_paths[:3])}",
                user_message=f"{len(missing_paths)} path(s) do not exist. Please verify your selection."
            )
            return Result.error(error)

        # Check for excessive file count (rough estimate for folders)
        estimated_file_count = 0
        for path in paths:
            if path.is_file():
                estimated_file_count += 1
            elif path.is_dir():
                # Rough estimate: count immediate children
                try:
                    estimated_file_count += sum(1 for _ in path.rglob('*') if _.is_file())
                except Exception as e:
                    logger.warning(f"Could not estimate file count for {path}: {e}")
                    estimated_file_count += 100  # Assume some reasonable number

        if estimated_file_count > self.MAX_FILES_PER_OPERATION:
            logger.warning(
                f"Hash operation has {estimated_file_count} files, "
                f"exceeds recommended limit of {self.MAX_FILES_PER_OPERATION}"
            )
            # Don't fail, just warn

        logger.info(
            f"Hash operation validated: {len(paths)} paths, "
            f"~{estimated_file_count} files, algorithm={algorithm}"
        )

        return Result.success(True)

    def validate_verification_operation(
        self,
        source_paths: List[Path],
        target_paths: List[Path],
        algorithm: str
    ) -> Result[bool]:
        """
        Validate verification operation parameters

        Args:
            source_paths: Source file/folder paths
            target_paths: Target file/folder paths
            algorithm: Hash algorithm

        Returns:
            Result[bool] indicating validation success
        """
        # Validate source paths
        source_validation = self.validate_hash_operation(source_paths, algorithm)
        if not source_validation.success:
            return source_validation

        # Validate target paths
        target_validation = self.validate_hash_operation(target_paths, algorithm)
        if not target_validation.success:
            error = ValidationError(
                f"Target validation failed: {target_validation.error}",
                user_message="Target files validation failed. Please check your target selection."
            )
            return Result.error(error)

        logger.info(
            f"Verification operation validated: {len(source_paths)} source paths, "
            f"{len(target_paths)} target paths, algorithm={algorithm}"
        )

        return Result.success(True)
