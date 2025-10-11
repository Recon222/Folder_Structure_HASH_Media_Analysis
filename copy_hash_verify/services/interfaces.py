#!/usr/bin/env python3
"""
Service Interfaces - Contracts for Copy/Hash/Verify business logic

These interfaces define the contracts that services must implement,
providing validation, business logic, and orchestration for hash operations.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Callable

from core.result_types import Result


class IHashService(ABC):
    """Interface for hash calculation and verification operations"""

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass


class ICopyVerifyService(ABC):
    """Interface for copy and verify operations"""

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass
