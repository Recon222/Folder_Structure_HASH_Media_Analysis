#!/usr/bin/env python3
"""
Hash Worker - Background hash calculation thread

Follows the unified Result-based worker pattern used in core/workers/.
Emits progress updates and final Result object via Qt signals.
"""

from pathlib import Path
from typing import List, Dict

from PySide6.QtCore import QThread, Signal

from ..unified_hash_calculator import UnifiedHashCalculator, HashResult
from core.result_types import Result
from core.logger import logger


class HashWorker(QThread):
    """
    Background worker for hash calculation

    Signals:
        result_ready: Emitted when operation completes with Result object
        progress_update: Emitted during operation with (percentage, message)
    """

    # Unified signals matching core/workers/ pattern
    result_ready = Signal(Result)
    progress_update = Signal(int, str)

    def __init__(self, paths: List[Path], algorithm: str = 'sha256',
                 enable_parallel: bool = True, max_workers_override: int = None,
                 parent=None):
        """
        Initialize hash worker

        Args:
            paths: List of file/folder paths to hash
            algorithm: Hash algorithm ('sha256', 'sha1', 'md5')
            enable_parallel: Enable parallel processing when beneficial (default: True)
            max_workers_override: Override thread count (None = auto-detect)
            parent: Parent QObject
        """
        super().__init__(parent)

        self.paths = paths
        self.algorithm = algorithm
        self.enable_parallel = enable_parallel
        self.max_workers_override = max_workers_override
        self.calculator = None
        self._is_cancelled = False

    def run(self):
        """Execute hash calculation in background thread"""
        try:
            logger.info(f"HashWorker starting: {len(self.paths)} paths with {self.algorithm}, "
                       f"parallel={self.enable_parallel}")

            # Create calculator with progress callback and parallel processing config
            self.calculator = UnifiedHashCalculator(
                algorithm=self.algorithm,
                progress_callback=self._on_progress,
                cancelled_check=self._check_cancelled,
                enable_parallel=self.enable_parallel,
                max_workers_override=self.max_workers_override
            )

            # Calculate hashes (automatically uses parallel processing when beneficial)
            result = self.calculator.hash_files(self.paths)

            # Emit result
            self.result_ready.emit(result)

            if result.success:
                files_hashed = len(result.value)
                duration = self.calculator.metrics.duration
                speed = self.calculator.metrics.average_speed_mbps
                logger.info(f"HashWorker completed: {files_hashed} files hashed in {duration:.1f}s ({speed:.1f} MB/s)")
            else:
                logger.warning(f"HashWorker completed with error: {result.error}")

        except Exception as e:
            # Unhandled exception - emit error result
            logger.error(f"HashWorker crashed: {e}", exc_info=True)
            from core.exceptions import HashCalculationError
            error = HashCalculationError(
                f"Hash worker crashed: {e}",
                user_message="An unexpected error occurred during hash calculation."
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
        logger.info("HashWorker cancellation requested")
