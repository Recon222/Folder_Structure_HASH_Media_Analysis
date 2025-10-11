#!/usr/bin/env python3
"""
Verify Worker - Background hash verification thread

Performs bidirectional hash verification between source and target files.
"""

from pathlib import Path
from typing import List, Dict

from PySide6.QtCore import QThread, Signal

from ..unified_hash_calculator import UnifiedHashCalculator, VerificationResult
from core.result_types import Result
from core.logger import logger


class VerifyWorker(QThread):
    """
    Background worker for hash verification

    Signals:
        result_ready: Emitted when operation completes with Result object
        progress_update: Emitted during operation with (percentage, message)
    """

    # Unified signals matching core/workers/ pattern
    result_ready = Signal(Result)
    progress_update = Signal(int, str)

    def __init__(self, source_paths: List[Path], target_paths: List[Path],
                 algorithm: str = 'sha256', parent=None):
        """
        Initialize verify worker

        Args:
            source_paths: List of source file/folder paths
            target_paths: List of target file/folder paths
            algorithm: Hash algorithm ('sha256', 'sha1', 'md5')
            parent: Parent QObject
        """
        super().__init__(parent)

        self.source_paths = source_paths
        self.target_paths = target_paths
        self.algorithm = algorithm
        self.calculator = None
        self._is_cancelled = False

    def run(self):
        """Execute hash verification in background thread"""
        try:
            logger.info(
                f"VerifyWorker starting: {len(self.source_paths)} source, "
                f"{len(self.target_paths)} target with {self.algorithm}"
            )

            # Create calculator with progress callback
            self.calculator = UnifiedHashCalculator(
                algorithm=self.algorithm,
                progress_callback=self._on_progress,
                cancelled_check=self._check_cancelled
            )

            # Verify hashes
            result = self.calculator.verify_hashes(self.source_paths, self.target_paths)

            # Emit result
            self.result_ready.emit(result)

            if result.success:
                verification_data = result.value
                matches = sum(1 for vr in verification_data.values() if vr.match)
                total = len(verification_data)
                logger.info(f"VerifyWorker completed: {matches}/{total} matches")
            else:
                logger.warning(f"VerifyWorker completed with error: {result.error}")

        except Exception as e:
            # Unhandled exception - emit error result
            logger.error(f"VerifyWorker crashed: {e}", exc_info=True)
            from core.exceptions import HashVerificationError
            error = HashVerificationError(
                f"Verify worker crashed: {e}",
                user_message="An unexpected error occurred during hash verification."
            )
            self.result_ready.emit(Result.error(error))

    def _on_progress(self, percentage: int, message: str):
        """
        Progress callback from calculator

        Args:
            percentage: Progress percentage (0-100)
            message: Status message
        """
        self.progress_update.emit(percentage, message)

    def _check_cancelled(self) -> bool:
        """
        Check if operation should be cancelled

        Returns:
            True if cancelled, False otherwise
        """
        return self._is_cancelled

    def cancel(self):
        """Cancel the current operation"""
        self._is_cancelled = True
        if self.calculator:
            self.calculator.cancel()
        logger.info("VerifyWorker cancellation requested")
