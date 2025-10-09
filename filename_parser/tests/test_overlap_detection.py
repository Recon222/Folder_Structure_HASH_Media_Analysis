"""
Test Overlap Detection

Tests the interval sweep algorithm for detecting multi-camera overlaps.
"""

import unittest
from pathlib import Path
from datetime import datetime

from filename_parser.models.timeline_models import (
    VideoMetadata,
    RenderSettings,
    Timeline,
    OverlapGroup,
    LayoutType
)
from filename_parser.services.timeline_calculator_service import TimelineCalculatorService


class TestOverlapDetection(unittest.TestCase):
    """Test overlap detection with multi-camera scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = TimelineCalculatorService()

    def test_two_cameras_full_overlap(self):
        """Test two cameras with complete overlap."""
        # Camera 1: 14:30:00 - 14:31:00 (60 seconds)
        cam1 = VideoMetadata(
            file_path=Path("/test/cam1.mp4"),
            filename="cam1.mp4",
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

        # Camera 2: 14:30:00 - 14:31:00 (same time, different camera)
        cam2 = VideoMetadata(
            file_path=Path("/test/cam2.mp4"),
            filename="cam2.mp4",
            smpte_timecode="14:30:00:00",  # Same start time
            frame_rate=30.0,
            duration_seconds=60.0,
            duration_frames=1800,
            width=1920,
            height=1080,
            codec="h264",
            pixel_format="yuv420p",
            video_bitrate=5000000,
            camera_path="Location1/Camera2"  # Different camera
        )

        result = self.calculator.calculate_timeline([cam1, cam2])

        self.assertTrue(result.success)
        timeline = result.value

        # Should detect overlap
        self.assertEqual(len(timeline.overlaps), 1, "Should detect 1 overlap region")

        overlap = timeline.overlaps[0]
        self.assertEqual(len(overlap.videos), 2, "Overlap should contain 2 cameras")
        self.assertEqual(overlap.layout_type, LayoutType.SIDE_BY_SIDE,
                        "2 cameras should get side-by-side layout")

        # Full overlap: 60 seconds @ 30fps = 1800 frames
        self.assertEqual(overlap.duration_frames, 1800, "Should be full 60-second overlap")

        # Should have 1 segment (the overlap)
        self.assertEqual(len(timeline.segments), 1, "Should have 1 segment (overlap only)")
        self.assertEqual(timeline.segments[0].segment_type, "overlap")

    def test_two_cameras_partial_overlap(self):
        """Test two cameras with partial overlap."""
        # Camera 1: 14:30:00 - 14:31:00 (60 seconds)
        cam1 = VideoMetadata(
            file_path=Path("/test/cam1.mp4"),
            filename="cam1.mp4",
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

        # Camera 2: 14:30:30 - 14:31:30 (starts 30 seconds later)
        cam2 = VideoMetadata(
            file_path=Path("/test/cam2.mp4"),
            filename="cam2.mp4",
            smpte_timecode="14:30:30:00",  # 30 seconds later
            frame_rate=30.0,
            duration_seconds=60.0,
            duration_frames=1800,
            width=1920,
            height=1080,
            codec="h264",
            pixel_format="yuv420p",
            video_bitrate=5000000,
            camera_path="Location1/Camera2"
        )

        result = self.calculator.calculate_timeline([cam1, cam2])

        self.assertTrue(result.success)
        timeline = result.value

        # Should detect overlap
        self.assertEqual(len(timeline.overlaps), 1, "Should detect 1 overlap region")

        overlap = timeline.overlaps[0]
        self.assertEqual(len(overlap.videos), 2, "Overlap should contain 2 cameras")

        # Partial overlap: 30 seconds @ 30fps = 900 frames
        self.assertEqual(overlap.duration_frames, 900, "Should be 30-second overlap")

        # Should have 3 segments: cam1 solo, overlap, cam2 solo
        self.assertEqual(len(timeline.segments), 3, "Should have 3 segments")

        # Verify segment types
        seg_types = [s.segment_type for s in timeline.segments]
        self.assertEqual(seg_types, ["video", "overlap", "video"])

    def test_three_cameras_overlapping(self):
        """Test three cameras with varying overlaps."""
        # Camera 1: 14:30:00 - 14:31:00
        cam1 = VideoMetadata(
            file_path=Path("/test/cam1.mp4"),
            filename="cam1.mp4",
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

        # Camera 2: 14:30:20 - 14:31:20
        cam2 = VideoMetadata(
            file_path=Path("/test/cam2.mp4"),
            filename="cam2.mp4",
            smpte_timecode="14:30:20:00",
            frame_rate=30.0,
            duration_seconds=60.0,
            duration_frames=1800,
            width=1920,
            height=1080,
            codec="h264",
            pixel_format="yuv420p",
            video_bitrate=5000000,
            camera_path="Location1/Camera2"
        )

        # Camera 3: 14:30:40 - 14:31:40
        cam3 = VideoMetadata(
            file_path=Path("/test/cam3.mp4"),
            filename="cam3.mp4",
            smpte_timecode="14:30:40:00",
            frame_rate=30.0,
            duration_seconds=60.0,
            duration_frames=1800,
            width=1920,
            height=1080,
            codec="h264",
            pixel_format="yuv420p",
            video_bitrate=5000000,
            camera_path="Location1/Camera3"
        )

        result = self.calculator.calculate_timeline([cam1, cam2, cam3])

        self.assertTrue(result.success)
        timeline = result.value

        # Should detect multiple overlap regions
        self.assertGreater(len(timeline.overlaps), 0, "Should detect overlaps")

        # Verify overlap types
        for overlap in timeline.overlaps:
            num_cams = len(overlap.videos)
            if num_cams == 2:
                self.assertEqual(overlap.layout_type, LayoutType.SIDE_BY_SIDE)
            elif num_cams == 3:
                self.assertEqual(overlap.layout_type, LayoutType.TRIPLE_SPLIT)

    def test_no_overlap_separate_cameras(self):
        """Test cameras with no overlap (sequential footage)."""
        # Camera 1: 14:30:00 - 14:31:00
        cam1 = VideoMetadata(
            file_path=Path("/test/cam1.mp4"),
            filename="cam1.mp4",
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

        # Camera 2: 14:32:00 - 14:33:00 (1 minute gap)
        cam2 = VideoMetadata(
            file_path=Path("/test/cam2.mp4"),
            filename="cam2.mp4",
            smpte_timecode="14:32:00:00",
            frame_rate=30.0,
            duration_seconds=60.0,
            duration_frames=1800,
            width=1920,
            height=1080,
            codec="h264",
            pixel_format="yuv420p",
            video_bitrate=5000000,
            camera_path="Location1/Camera2"
        )

        result = self.calculator.calculate_timeline([cam1, cam2])

        self.assertTrue(result.success)
        timeline = result.value

        # No overlap - cameras sequential
        self.assertEqual(len(timeline.overlaps), 0, "Should have no overlaps")

        # Should have gap between cameras
        self.assertEqual(len(timeline.gaps), 1, "Should have 1 gap")

        # Should have 3 segments: video, gap, video
        self.assertEqual(len(timeline.segments), 3)
        seg_types = [s.segment_type for s in timeline.segments]
        self.assertEqual(seg_types, ["video", "gap", "video"])

    def test_four_cameras_grid_layout(self):
        """Test four cameras get 2x2 grid layout."""
        cameras = []
        for i in range(4):
            cam = VideoMetadata(
                file_path=Path(f"/test/cam{i+1}.mp4"),
                filename=f"cam{i+1}.mp4",
                smpte_timecode="14:30:00:00",  # All same time
                frame_rate=30.0,
                duration_seconds=60.0,
                duration_frames=1800,
                width=1920,
                height=1080,
                codec="h264",
                pixel_format="yuv420p",
                video_bitrate=5000000,
                camera_path=f"Location1/Camera{i+1}"
            )
            cameras.append(cam)

        result = self.calculator.calculate_timeline(cameras)

        self.assertTrue(result.success)
        timeline = result.value

        # Should detect 4-camera overlap
        self.assertEqual(len(timeline.overlaps), 1)

        overlap = timeline.overlaps[0]
        self.assertEqual(len(overlap.videos), 4)
        self.assertEqual(overlap.layout_type, LayoutType.GRID_2X2,
                        "4 cameras should get 2x2 grid layout")

    def test_overlap_with_gaps(self):
        """Test complex scenario: overlaps AND gaps."""
        # Camera 1: 14:30:00 - 14:31:00
        cam1 = VideoMetadata(
            file_path=Path("/test/cam1.mp4"),
            filename="cam1.mp4",
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

        # Camera 2: 14:30:30 - 14:31:30 (overlaps with cam1)
        cam2 = VideoMetadata(
            file_path=Path("/test/cam2.mp4"),
            filename="cam2.mp4",
            smpte_timecode="14:30:30:00",
            frame_rate=30.0,
            duration_seconds=60.0,
            duration_frames=1800,
            width=1920,
            height=1080,
            codec="h264",
            pixel_format="yuv420p",
            video_bitrate=5000000,
            camera_path="Location1/Camera2"
        )

        # Camera 3: 14:33:00 - 14:34:00 (gap after cam1+cam2)
        cam3 = VideoMetadata(
            file_path=Path("/test/cam3.mp4"),
            filename="cam3.mp4",
            smpte_timecode="14:33:00:00",  # 90 second gap
            frame_rate=30.0,
            duration_seconds=60.0,
            duration_frames=1800,
            width=1920,
            height=1080,
            codec="h264",
            pixel_format="yuv420p",
            video_bitrate=5000000,
            camera_path="Location1/Camera3"
        )

        result = self.calculator.calculate_timeline([cam1, cam2, cam3], min_gap_seconds=5.0)

        self.assertTrue(result.success)
        timeline = result.value

        # Should detect overlap
        self.assertGreater(len(timeline.overlaps), 0, "Should detect overlaps")

        # Should detect gap
        self.assertEqual(len(timeline.gaps), 1, "Should detect 1 gap")

        # Gap should be ~90 seconds
        gap = timeline.gaps[0]
        self.assertAlmostEqual(gap.duration_seconds, 90.0, delta=1.0)

    def test_single_camera_no_overlap(self):
        """Test single camera produces no overlaps."""
        cam = VideoMetadata(
            file_path=Path("/test/cam1.mp4"),
            filename="cam1.mp4",
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

        result = self.calculator.calculate_timeline([cam])

        self.assertTrue(result.success)
        timeline = result.value

        # Single camera cannot overlap
        self.assertEqual(len(timeline.overlaps), 0, "Single camera should have no overlaps")
        self.assertEqual(len(timeline.segments), 1, "Should have 1 video segment")


if __name__ == "__main__":
    unittest.main()
