"""
Timeline Integration Test

Tests the complete timeline calculation and rendering workflow.
Uses synthetic test data since we don't have actual video files in CI.
"""

import unittest
from pathlib import Path
from datetime import datetime

from filename_parser.models.timeline_models import (
    VideoMetadata,
    RenderSettings,
    Timeline,
    Gap
)
from filename_parser.services.timeline_calculator_service import TimelineCalculatorService


class TestTimelineIntegration(unittest.TestCase):
    """Integration tests for timeline calculation."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = TimelineCalculatorService()

    def test_single_video_no_gaps(self):
        """Test timeline with single video should have no gaps."""
        video = VideoMetadata(
            file_path=Path("/test/video1.mp4"),
            filename="video1.mp4",
            smpte_timecode="14:30:00:00",
            frame_rate=30.0,
            duration_seconds=120.0,
            duration_frames=3600,
            width=1920,
            height=1080,
            codec="h264",
            pixel_format="yuv420p",
            video_bitrate=5000000,
            camera_path="Location1/Camera1"
        )

        result = self.calculator.calculate_timeline([video])

        self.assertTrue(result.success)
        timeline = result.value

        self.assertEqual(len(timeline.videos), 1)
        self.assertEqual(len(timeline.gaps), 0)
        self.assertEqual(len(timeline.segments), 1)

    def test_two_videos_with_gap(self):
        """Test timeline with gap between two videos."""
        video1 = VideoMetadata(
            file_path=Path("/test/video1.mp4"),
            filename="video1.mp4",
            smpte_timecode="14:30:00:00",  # 14:30:00
            frame_rate=30.0,
            duration_seconds=60.0,
            duration_frames=1800,
            width=1920,
            height=1080,
            codec="h264",
            pixel_format="yuv420p",
            video_bitrate=5000000,
            camera_path="Location1/Camera1"
        )

        video2 = VideoMetadata(
            file_path=Path("/test/video2.mp4"),
            filename="video2.mp4",
            smpte_timecode="14:32:00:00",  # 14:32:00 - 2 minute gap
            frame_rate=30.0,
            duration_seconds=60.0,
            duration_frames=1800,
            width=1920,
            height=1080,
            codec="h264",
            pixel_format="yuv420p",
            video_bitrate=5000000,
            camera_path="Location1/Camera1"
        )

        result = self.calculator.calculate_timeline([video1, video2], min_gap_seconds=5.0)

        self.assertTrue(result.success)
        timeline = result.value

        self.assertEqual(len(timeline.videos), 2)
        self.assertEqual(len(timeline.gaps), 1)  # One gap
        self.assertEqual(len(timeline.segments), 3)  # video + gap + video

        # Verify gap
        gap = timeline.gaps[0]
        self.assertAlmostEqual(gap.duration_seconds, 60.0, delta=1.0)  # ~60 second gap

    def test_adjacent_videos_no_gap(self):
        """Test that adjacent videos don't create gaps."""
        video1 = VideoMetadata(
            file_path=Path("/test/video1.mp4"),
            filename="video1.mp4",
            smpte_timecode="14:30:00:00",
            frame_rate=30.0,
            duration_seconds=60.0,
            duration_frames=1800,
            width=1920,
            height=1080,
            codec="h264",
            pixel_format="yuv420p",
            video_bitrate=5000000,
            camera_path="Location1/Camera1"
        )

        video2 = VideoMetadata(
            file_path=Path("/test/video2.mp4"),
            filename="video2.mp4",
            smpte_timecode="14:31:00:00",  # Starts exactly when video1 ends
            frame_rate=30.0,
            duration_seconds=60.0,
            duration_frames=1800,
            width=1920,
            height=1080,
            codec="h264",
            pixel_format="yuv420p",
            video_bitrate=5000000,
            camera_path="Location1/Camera1"
        )

        result = self.calculator.calculate_timeline([video1, video2])

        self.assertTrue(result.success)
        timeline = result.value

        self.assertEqual(len(timeline.gaps), 0)  # No gaps
        self.assertEqual(len(timeline.segments), 2)  # Just two videos

    def test_different_frame_rates_time_based_calculation(self):
        """Test that different frame rates are handled with time-based calculations."""
        video1 = VideoMetadata(
            file_path=Path("/test/video1.mp4"),
            filename="video1.mp4",
            smpte_timecode="14:30:00:00",
            frame_rate=12.0,  # Different FPS
            duration_seconds=60.0,
            duration_frames=720,  # 60s * 12fps
            width=1920,
            height=1080,
            codec="h264",
            pixel_format="yuv420p",
            video_bitrate=5000000,
            camera_path="Location1/Camera1"
        )

        video2 = VideoMetadata(
            file_path=Path("/test/video2.mp4"),
            filename="video2.mp4",
            smpte_timecode="14:31:00:00",
            frame_rate=30.0,  # Different FPS
            duration_seconds=60.0,
            duration_frames=1800,  # 60s * 30fps
            width=1920,
            height=1080,
            codec="h264",
            pixel_format="yuv420p",
            video_bitrate=5000000,
            camera_path="Location1/Camera1"
        )

        result = self.calculator.calculate_timeline([video1, video2], sequence_fps=30.0)

        self.assertTrue(result.success)
        timeline = result.value

        # Both videos should be on timeline
        self.assertEqual(len(timeline.videos), 2)

        # Verify time-based positioning (no gaps despite different FPS)
        self.assertEqual(len(timeline.gaps), 0)

    def test_min_gap_threshold_filtering(self):
        """Test that small gaps below threshold are ignored."""
        video1 = VideoMetadata(
            file_path=Path("/test/video1.mp4"),
            filename="video1.mp4",
            smpte_timecode="14:30:00:00",
            frame_rate=30.0,
            duration_seconds=60.0,
            duration_frames=1800,
            width=1920,
            height=1080,
            codec="h264",
            pixel_format="yuv420p",
            video_bitrate=5000000,
            camera_path="Location1/Camera1"
        )

        video2 = VideoMetadata(
            file_path=Path("/test/video2.mp4"),
            filename="video2.mp4",
            smpte_timecode="14:31:03:00",  # 3 second gap
            frame_rate=30.0,
            duration_seconds=60.0,
            duration_frames=1800,
            width=1920,
            height=1080,
            codec="h264",
            pixel_format="yuv420p",
            video_bitrate=5000000,
            camera_path="Location1/Camera1"
        )

        # With 5 second minimum, 3 second gap should be ignored
        result = self.calculator.calculate_timeline([video1, video2], min_gap_seconds=5.0)

        self.assertTrue(result.success)
        timeline = result.value

        self.assertEqual(len(timeline.gaps), 0)  # Gap too small, ignored

        # With 2 second minimum, 3 second gap should be detected
        result2 = self.calculator.calculate_timeline([video1, video2], min_gap_seconds=2.0)

        self.assertTrue(result2.success)
        timeline2 = result2.value

        self.assertEqual(len(timeline2.gaps), 1)  # Gap detected


if __name__ == "__main__":
    unittest.main()
