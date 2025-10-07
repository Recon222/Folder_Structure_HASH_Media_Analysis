"""
Timeline Render Worker - background thread for video rendering

Follows the established unified worker pattern with:
- result_ready signal (Result object)
- progress_update signal (int, str)
- Cancellation support

Renders multicam timeline video using MulticamRendererService.
"""

from typing import Optional

from PySide6.QtCore import QThread, Signal

from core.result_types import Result
from core.logger import logger

from filename_parser.models.timeline_models import Timeline, RenderSettings
from filename_parser.services.multicam_renderer_service import MulticamRendererService


class TimelineRenderWorker(QThread):
    """
    Background worker for timeline video rendering.

    Uses unified signal pattern established in FilenameParserWorker:
    - result_ready: Emits Result[Path] when complete
    - progress_update: Emits (percentage, message) during processing
    """

    # Unified signals (matching FilenameParserWorker pattern)
    result_ready = Signal(Result)       # Result[Path] with output video path
    progress_update = Signal(int, str)  # (percentage, status_message)

    def __init__(
        self,
        timeline: Timeline,
        settings: RenderSettings,
        renderer_service: MulticamRendererService,
        parent=None
    ):
        """
        Initialize timeline render worker.

        Args:
            timeline: Calculated timeline with gaps and overlaps
            settings: Render settings
            renderer_service: Renderer service instance
            parent: Parent QObject
        """
        super().__init__(parent)

        self.timeline = timeline
        self.settings = settings
        self.renderer_service = renderer_service

        self._cancelled = False

    def run(self):
        """Execute timeline rendering in background thread."""
        try:
            logger.info("Timeline render worker started")
            self.progress_update.emit(0, "Initializing timeline render...")

            # Render timeline with progress callbacks
            result = self.renderer_service.render_timeline(
                self.timeline,
                self.settings,
                progress_callback=self._on_progress
            )

            # Check for cancellation before emitting
            if self._cancelled:
                logger.info("Timeline render cancelled")
                self.progress_update.emit(0, "Render cancelled")
                # Don't emit result_ready for cancelled operations
                return

            # Emit result
            self.result_ready.emit(result)

            if result.success:
                logger.info(f"Timeline render complete: {result.value}")
            else:
                logger.error(f"Timeline render failed: {result.error.user_message}")

        except Exception as e:
            logger.error(f"Unexpected error in timeline render worker: {e}", exc_info=True)

            # Create error result
            from core.exceptions import FileOperationError
            error = FileOperationError(
                f"Timeline render crashed: {e}",
                user_message="Timeline rendering failed unexpectedly. Check logs.",
                context={"exception": str(e)}
            )
            self.result_ready.emit(Result.error(error))

    def _on_progress(self, percentage: int, message: str):
        """
        Progress callback from renderer service.

        Args:
            percentage: Completion percentage (0-100)
            message: Status message
        """
        if not self._cancelled:
            self.progress_update.emit(percentage, message)

    def cancel(self):
        """Cancel the rendering operation."""
        logger.info("Timeline render worker cancellation requested")
        self._cancelled = True

        # TODO: Implement FFmpeg process termination if needed
        # For now, just set flag - renderer will check periodically

    def is_cancelled(self) -> bool:
        """Check if rendering was cancelled."""
        return self._cancelled
