#!/usr/bin/env python3
"""
Throttled Progress Reporter - Prevents UI flooding from parallel workers

Ensures maximum update rate regardless of how many worker threads are
reporting progress. Critical for parallel processing to prevent UI blocking.

Usage:
    reporter = ThrottledProgressReporter(
        callback=my_progress_callback,
        update_interval=0.1  # 10 updates/second max
    )

    # From multiple worker threads:
    reporter.report_progress(45, "Processing file 45/100")
    reporter.report_progress(46, "Processing file 46/100")
    # Only updates UI every 0.1 seconds, prevents flooding
"""

import time
import threading
from typing import Callable, Optional


class ThrottledProgressReporter:
    """
    Thread-safe progress reporter with automatic throttling

    Prevents UI flooding by limiting update frequency while ensuring
    critical milestones (0%, 100%) are always reported immediately.

    Key Features:
    - Thread-safe (multiple workers can report simultaneously)
    - Configurable update interval (default: 10 updates/sec)
    - Always reports 0% and 100% immediately
    - Prevents duplicate progress values
    - No progress updates lost (last value before throttle is reported)
    """

    def __init__(self, callback: Callable[[int, str], None],
                 update_interval: float = 0.1):
        """
        Initialize throttled progress reporter

        Args:
            callback: Function that receives (progress_pct: int, message: str)
            update_interval: Minimum time between updates in seconds (default: 0.1 = 10 updates/sec)
        """
        self.callback = callback
        self.update_interval = update_interval
        self.last_update_time = 0.0
        self.last_progress = -1
        self.last_message = ""
        self.lock = threading.Lock()
        self.pending_update: Optional[tuple] = None

    def report_progress(self, progress_pct: int, message: str):
        """
        Report progress with automatic throttling

        Thread-safe method that can be called from multiple workers.
        Updates are throttled to prevent UI flooding while ensuring
        important milestones are reported immediately.

        Args:
            progress_pct: Progress percentage (0-100)
            message: Status message describing current operation
        """
        with self.lock:
            current_time = time.time()

            # Always report 0% and 100% immediately (critical milestones)
            if progress_pct in (0, 100):
                self._do_report(progress_pct, message, current_time)
                return

            # Check if enough time has passed since last update
            time_since_last = current_time - self.last_update_time

            # Check if progress value changed (prevent duplicates)
            progress_changed = progress_pct != self.last_progress

            if time_since_last >= self.update_interval and progress_changed:
                # Enough time passed and progress changed - report immediately
                self._do_report(progress_pct, message, current_time)
            else:
                # Store pending update for later
                # This ensures we don't lose the last update before 100%
                self.pending_update = (progress_pct, message)

    def _do_report(self, progress_pct: int, message: str, current_time: float):
        """
        Internal method to actually call the callback

        Args:
            progress_pct: Progress percentage
            message: Status message
            current_time: Current timestamp
        """
        try:
            self.callback(progress_pct, message)
            self.last_update_time = current_time
            self.last_progress = progress_pct
            self.last_message = message
            self.pending_update = None
        except Exception as e:
            # Don't let callback errors break progress reporting
            import sys
            print(f"Error in progress callback: {e}", file=sys.stderr)

    def flush_pending(self):
        """
        Force report any pending update

        Useful when operation completes to ensure the last progress
        update is reported even if it was throttled.
        """
        with self.lock:
            if self.pending_update:
                progress_pct, message = self.pending_update
                self._do_report(progress_pct, message, time.time())

    def reset(self):
        """
        Reset reporter state for new operation

        Call this before starting a new progress-reporting operation
        to ensure clean state.
        """
        with self.lock:
            self.last_update_time = 0.0
            self.last_progress = -1
            self.last_message = ""
            self.pending_update = None


class MultiSourceProgressAggregator:
    """
    Aggregates progress from multiple independent sources

    Useful for parallel operations where multiple workers are processing
    different files and you need to show overall progress.

    Example:
        # 3 workers processing 100 files total
        aggregator = MultiSourceProgressAggregator(
            callback=ui_callback,
            total_items=100
        )

        # Worker 1 reports file 1 complete
        aggregator.report_item_complete(worker_id=1, message="Hashed file1.txt")

        # Worker 2 reports file 2 complete
        aggregator.report_item_complete(worker_id=2, message="Hashed file2.txt")

        # Automatically calculates overall progress (2/100 = 2%)
    """

    def __init__(self, callback: Callable[[int, str], None],
                 total_items: int,
                 update_interval: float = 0.1):
        """
        Initialize multi-source progress aggregator

        Args:
            callback: Function that receives (progress_pct: int, message: str)
            total_items: Total number of items to process
            update_interval: Minimum time between updates in seconds
        """
        self.total_items = total_items
        self.completed_items = 0
        self.lock = threading.Lock()
        self.reporter = ThrottledProgressReporter(callback, update_interval)

    def report_item_complete(self, worker_id: int, message: str):
        """
        Report completion of one item by a worker

        Args:
            worker_id: Identifier for the worker thread
            message: Status message (e.g., "Hashed file.txt")
        """
        with self.lock:
            self.completed_items += 1
            progress_pct = int((self.completed_items / self.total_items) * 100)

            # Include worker ID in message for debugging
            full_message = f"[Worker {worker_id}] {message}"

            self.reporter.report_progress(progress_pct, full_message)

    def report_progress_percentage(self, progress_pct: int, message: str):
        """
        Report progress directly as percentage (alternative to item counting)

        Args:
            progress_pct: Progress percentage (0-100)
            message: Status message
        """
        self.reporter.report_progress(progress_pct, message)

    def reset(self):
        """Reset aggregator for new operation"""
        with self.lock:
            self.completed_items = 0
            self.reporter.reset()

    def flush_pending(self):
        """Flush any pending updates"""
        self.reporter.flush_pending()


class ProgressRateCalculator:
    """
    Calculates processing rate (items/sec or MB/sec) for progress reporting

    Useful for showing "1500 files/sec" or "450 MB/s" in progress messages.

    Example:
        calc = ProgressRateCalculator()

        for file in files:
            process_file(file)
            calc.record_item(file.size)
            rate = calc.get_rate_mbps()
            reporter.report_progress(pct, f"Processing at {rate:.1f} MB/s")
    """

    def __init__(self, window_size: int = 10):
        """
        Initialize rate calculator

        Args:
            window_size: Number of recent items to consider for rate calculation
        """
        self.window_size = window_size
        self.recent_items = []  # (timestamp, bytes) tuples
        self.total_items = 0
        self.total_bytes = 0
        self.start_time = time.time()
        self.lock = threading.Lock()

    def record_item(self, item_bytes: int = 0):
        """
        Record completion of an item

        Args:
            item_bytes: Size of item in bytes (optional, for MB/s calculation)
        """
        with self.lock:
            current_time = time.time()
            self.recent_items.append((current_time, item_bytes))
            self.total_items += 1
            self.total_bytes += item_bytes

            # Keep only recent items for rate calculation
            if len(self.recent_items) > self.window_size:
                self.recent_items.pop(0)

    def get_rate_items_per_sec(self) -> float:
        """
        Calculate current processing rate in items/second

        Returns:
            Items processed per second (based on recent window)
        """
        with self.lock:
            if len(self.recent_items) < 2:
                return 0.0

            first_time, _ = self.recent_items[0]
            last_time, _ = self.recent_items[-1]
            time_span = last_time - first_time

            if time_span <= 0:
                return 0.0

            items_in_window = len(self.recent_items)
            return items_in_window / time_span

    def get_rate_mbps(self) -> float:
        """
        Calculate current processing rate in MB/second

        Returns:
            Megabytes processed per second (based on recent window)
        """
        with self.lock:
            if len(self.recent_items) < 2:
                return 0.0

            first_time, _ = self.recent_items[0]
            last_time, _ = self.recent_items[-1]
            time_span = last_time - first_time

            if time_span <= 0:
                return 0.0

            bytes_in_window = sum(b for _, b in self.recent_items)
            mb_in_window = bytes_in_window / (1024 * 1024)
            return mb_in_window / time_span

    def get_average_rate_mbps(self) -> float:
        """
        Calculate average processing rate since start

        Returns:
            Average MB/s for entire operation
        """
        with self.lock:
            elapsed = time.time() - self.start_time
            if elapsed <= 0:
                return 0.0

            mb_total = self.total_bytes / (1024 * 1024)
            return mb_total / elapsed

    def get_eta_seconds(self, remaining_items: int) -> float:
        """
        Estimate time remaining based on current rate

        Args:
            remaining_items: Number of items left to process

        Returns:
            Estimated seconds until completion (0 if rate is 0)
        """
        rate = self.get_rate_items_per_sec()
        if rate <= 0:
            return 0.0

        return remaining_items / rate

    def reset(self):
        """Reset calculator for new operation"""
        with self.lock:
            self.recent_items = []
            self.total_items = 0
            self.total_bytes = 0
            self.start_time = time.time()
