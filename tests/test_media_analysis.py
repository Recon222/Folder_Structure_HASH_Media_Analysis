#!/usr/bin/env python3
"""
Unit tests for media analysis functionality
Tests service, controller, and worker components
"""

import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import tempfile
import json

from core.media_analysis_models import (
    MediaAnalysisSettings, MediaMetadata, MediaAnalysisResult,
    MetadataFieldGroup, FileReferenceFormat
)
from core.media.ffprobe_binary_manager import FFProbeBinaryManager
from core.media.metadata_normalizer import MetadataNormalizer
from core.services.media_analysis_service import MediaAnalysisService
from controllers.media_analysis_controller import MediaAnalysisController
from core.result_types import Result
from core.exceptions import FFProbeNotFoundError, MediaExtractionError


class TestMediaAnalysisModels(unittest.TestCase):
    """Test media analysis data models"""
    
    def test_media_analysis_settings_creation(self):
        """Test MediaAnalysisSettings creation and defaults"""
        settings = MediaAnalysisSettings()
        
        # Check defaults
        self.assertTrue(settings.general_fields.enabled)
        self.assertTrue(settings.video_fields.enabled)
        self.assertTrue(settings.audio_fields.enabled)
        self.assertFalse(settings.location_fields.enabled)  # Privacy by default
        self.assertTrue(settings.device_fields.enabled)
        
        self.assertEqual(settings.file_reference_format, FileReferenceFormat.FULL_PATH)
        self.assertEqual(settings.timeout_seconds, 5.0)
        self.assertEqual(settings.max_workers, 8)
        self.assertTrue(settings.skip_non_media)
    
    def test_media_metadata_formatting(self):
        """Test MediaMetadata formatting methods"""
        metadata = MediaMetadata(
            file_path=Path("/test/video.mp4"),
            file_size=1024 * 1024 * 100,  # 100 MB
            duration=3665.5,  # 1h 1m 5.5s
            resolution=(1920, 1080)
        )
        
        # Test duration formatting
        self.assertEqual(metadata.get_duration_string(), "01:01:05")
        
        # Test resolution formatting
        self.assertEqual(metadata.get_resolution_string(), "1920x1080")
        
        # Test file size formatting
        self.assertEqual(metadata.get_file_size_string(), "100.00 MB")
        
        # Test display path formatting
        self.assertEqual(
            metadata.get_display_path(FileReferenceFormat.NAME_ONLY),
            "video.mp4"
        )
        self.assertEqual(
            metadata.get_display_path(FileReferenceFormat.PARENT_AND_NAME),
            "test/video.mp4"
        )
    
    def test_media_analysis_result_statistics(self):
        """Test MediaAnalysisResult statistics methods"""
        # Create sample metadata
        metadata_list = [
            MediaMetadata(
                file_path=Path("/test/video1.mp4"),
                file_size=1000000,
                format="mp4",
                video_codec="H.264/AVC",
                audio_codec="AAC"
            ),
            MediaMetadata(
                file_path=Path("/test/video2.mkv"),
                file_size=2000000,
                format="mkv",
                video_codec="H.265/HEVC",
                audio_codec="AAC"
            ),
            MediaMetadata(
                file_path=Path("/test/audio.mp3"),
                file_size=500000,
                format="mp3",
                audio_codec="MP3"
            )
        ]
        
        result = MediaAnalysisResult(
            total_files=5,
            successful=3,
            failed=1,
            skipped=1,
            metadata_list=metadata_list,
            processing_time=10.5,
            errors=["Error 1"]
        )
        
        # Test summary
        summary = result.get_summary()
        self.assertEqual(summary['total_files'], 5)
        self.assertEqual(summary['successful'], 3)
        self.assertEqual(summary['success_rate'], 60.0)
        
        # Test format statistics
        format_stats = result.get_format_statistics()
        self.assertEqual(format_stats['mp4'], 1)
        self.assertEqual(format_stats['mkv'], 1)
        self.assertEqual(format_stats['mp3'], 1)
        
        # Test codec statistics
        codec_stats = result.get_codec_statistics()
        self.assertEqual(codec_stats['video_codecs']['H.264/AVC'], 1)
        self.assertEqual(codec_stats['video_codecs']['H.265/HEVC'], 1)
        self.assertEqual(codec_stats['audio_codecs']['AAC'], 2)
        self.assertEqual(codec_stats['audio_codecs']['MP3'], 1)


class TestFFProbeBinaryManager(unittest.TestCase):
    """Test FFprobe binary management"""
    
    def test_binary_manager_initialization(self):
        """Test FFProbeBinaryManager initialization"""
        manager = FFProbeBinaryManager()
        
        # Should initialize without error
        self.assertIsNotNone(manager)
        
        # Check status info
        status = manager.get_status_info()
        self.assertIn('available', status)
        self.assertIn('path', status)
        self.assertIn('version', status)
        self.assertIn('validated', status)
        self.assertIn('platform', status)
    
    @patch('subprocess.run')
    def test_binary_validation(self, mock_run):
        """Test FFprobe binary validation"""
        # Mock successful validation
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ffprobe version 4.4.0"
        mock_run.return_value = mock_result
        
        manager = FFProbeBinaryManager()
        manager.binary_path = Path("/bin/ffprobe")
        
        result = manager._validate_binary()
        
        # Should validate successfully
        self.assertTrue(result)
        self.assertTrue(manager.is_validated)
        self.assertIsNotNone(manager.version_info)


class TestMetadataNormalizer(unittest.TestCase):
    """Test metadata normalization"""
    
    def test_normalize_basic_metadata(self):
        """Test normalizing basic metadata from FFprobe output"""
        normalizer = MetadataNormalizer()
        
        # Sample FFprobe output
        raw_metadata = {
            'format': {
                'format_name': 'mov,mp4,m4a,3gp,3g2,mj2',
                'format_long_name': 'QuickTime / MOV',
                'duration': '60.5',
                'size': '10485760',
                'bit_rate': '1387168',
                'tags': {
                    'creation_time': '2024-01-15T10:30:00.000000Z',
                    'title': 'Test Video'
                }
            },
            'streams': [
                {
                    'codec_type': 'video',
                    'codec_name': 'h264',
                    'codec_long_name': 'H.264 / AVC / MPEG-4 AVC',
                    'width': 1920,
                    'height': 1080,
                    'avg_frame_rate': '30000/1001'
                },
                {
                    'codec_type': 'audio',
                    'codec_name': 'aac',
                    'codec_long_name': 'AAC (Advanced Audio Coding)',
                    'sample_rate': '48000',
                    'channels': 2,
                    'channel_layout': 'stereo'
                }
            ]
        }
        
        file_path = Path("/test/video.mp4")
        metadata = normalizer.normalize(raw_metadata, file_path)
        
        # Check normalized values
        self.assertEqual(metadata.file_path, file_path)
        self.assertEqual(metadata.format, 'QuickTime')
        self.assertEqual(metadata.duration, 60.5)
        self.assertEqual(metadata.bitrate, 1387168)
        self.assertEqual(metadata.file_size, 10485760)
        
        # Check video info
        self.assertTrue(metadata.has_video)
        self.assertEqual(metadata.video_codec, 'H.264/AVC')
        self.assertEqual(metadata.resolution, (1920, 1080))
        self.assertAlmostEqual(metadata.frame_rate, 29.97, places=2)
        
        # Check audio info
        self.assertTrue(metadata.has_audio)
        self.assertEqual(metadata.audio_codec, 'AAC')
        self.assertEqual(metadata.sample_rate, 48000)
        self.assertEqual(metadata.channels, 2)
        self.assertEqual(metadata.channel_layout, 'stereo')
        
        # Check metadata tags
        self.assertEqual(metadata.title, 'Test Video')
        self.assertIsNotNone(metadata.creation_date)
    
    def test_apply_field_filter(self):
        """Test applying field filters based on settings"""
        normalizer = MetadataNormalizer()
        
        # Create metadata with all fields
        metadata = MediaMetadata(
            file_path=Path("/test/video.mp4"),
            file_size=1000000,
            format="MP4",
            duration=60.0,
            video_codec="H.264",
            resolution=(1920, 1080),
            audio_codec="AAC",
            sample_rate=48000,
            gps_latitude=40.7128,
            gps_longitude=-74.0060,
            device_make="Apple",
            device_model="iPhone"
        )
        
        # Create settings with some fields disabled
        settings = MediaAnalysisSettings()
        settings.location_fields.enabled = False
        settings.video_fields.enabled = False
        
        # Apply filter
        filtered = normalizer.apply_field_filter(metadata, settings)
        
        # Check filtered fields
        self.assertIsNone(filtered.gps_latitude)
        self.assertIsNone(filtered.gps_longitude)
        self.assertIsNone(filtered.video_codec)
        self.assertIsNone(filtered.resolution)
        
        # Check preserved fields
        self.assertEqual(filtered.format, "MP4")
        self.assertEqual(filtered.audio_codec, "AAC")
        self.assertEqual(filtered.device_make, "Apple")


class TestMediaAnalysisService(unittest.TestCase):
    """Test media analysis service"""
    
    @patch('core.services.media_analysis_service.FFProbeBinaryManager')
    @patch('core.services.media_analysis_service.FFProbeWrapper')
    def test_service_initialization(self, mock_wrapper_class, mock_manager_class):
        """Test MediaAnalysisService initialization"""
        # Mock FFprobe availability
        mock_manager = MagicMock()
        mock_manager.is_available.return_value = True
        mock_manager.get_binary_path.return_value = Path("/bin/ffprobe")
        mock_manager_class.return_value = mock_manager
        
        service = MediaAnalysisService()
        
        # Should initialize successfully
        self.assertIsNotNone(service)
        self.assertIsNotNone(service.ffprobe_manager)
        self.assertIsNotNone(service.ffprobe_wrapper)
    
    def test_validate_media_files(self):
        """Test media file validation"""
        service = MediaAnalysisService()
        
        # Create temp files for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            file1 = temp_path / "test1.mp4"
            file1.touch()
            file2 = temp_path / "test2.avi"
            file2.touch()
            
            # Create subdirectory with file
            sub_dir = temp_path / "subdir"
            sub_dir.mkdir()
            file3 = sub_dir / "test3.mkv"
            file3.touch()
            
            # Test file validation
            paths = [file1, file2, sub_dir]
            
            # Mock FFprobe availability
            service.ffprobe_wrapper = MagicMock()
            
            result = service.validate_media_files(paths)
            
            # Should succeed and return all files
            self.assertTrue(result.success)
            self.assertEqual(len(result.value), 3)
            self.assertIn(file1, result.value)
            self.assertIn(file2, result.value)
            self.assertIn(file3, result.value)
    
    def test_validate_media_files_no_ffprobe(self):
        """Test validation when FFprobe is not available"""
        service = MediaAnalysisService()
        service.ffprobe_wrapper = None
        
        result = service.validate_media_files([Path("/test.mp4")])
        
        # Should return error
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, FFProbeNotFoundError)


class TestMediaAnalysisController(unittest.TestCase):
    """Test media analysis controller"""
    
    @patch('controllers.media_analysis_controller.MediaAnalysisWorker')
    def test_start_analysis_workflow(self, mock_worker_class):
        """Test starting analysis workflow"""
        controller = MediaAnalysisController()
        
        # Mock service
        mock_service = MagicMock()
        mock_service.validate_media_files.return_value = Result.success([
            Path("/test1.mp4"),
            Path("/test2.avi")
        ])
        controller._media_service = mock_service
        
        # Mock worker
        mock_worker = MagicMock()
        mock_worker_class.return_value = mock_worker
        
        # Start workflow
        settings = MediaAnalysisSettings()
        result = controller.start_analysis_workflow(
            [Path("/test1.mp4"), Path("/test2.avi")],
            settings
        )
        
        # Should succeed and return worker
        self.assertTrue(result.success)
        self.assertEqual(result.value, mock_worker)
        self.assertEqual(controller.current_worker, mock_worker)
    
    def test_get_ffprobe_status(self):
        """Test getting FFprobe status"""
        controller = MediaAnalysisController()
        
        # Mock service
        mock_service = MagicMock()
        mock_service.get_ffprobe_status.return_value = {
            'available': True,
            'path': '/bin/ffprobe',
            'version': 'ffprobe version 4.4.0'
        }
        controller._media_service = mock_service
        
        status = controller.get_ffprobe_status()
        
        # Should return status from service
        self.assertEqual(status['available'], True)
        self.assertEqual(status['path'], '/bin/ffprobe')
        self.assertIn('version', status)


if __name__ == '__main__':
    unittest.main()