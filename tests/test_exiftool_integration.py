#!/usr/bin/env python3
"""
Test suite for ExifTool integration
Comprehensive tests for forensic metadata extraction and geolocation features
"""

import unittest
import tempfile
import shutil
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Test without Qt dependencies if not available
try:
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

from core.exiftool.exiftool_binary_manager import ExifToolBinaryManager
from core.exiftool.exiftool_command_builder import ExifToolForensicCommandBuilder
from core.exiftool.exiftool_wrapper import ExifToolWrapper
from core.exiftool.exiftool_normalizer import ExifToolNormalizer
from core.exiftool.exiftool_models import (
    GPSData, DeviceInfo, TemporalData, DocumentIntegrity, 
    CameraSettings, ExifToolMetadata, ExifToolSettings, 
    ExifToolAnalysisResult, GPSPrecisionLevel
)
from core.services.media_analysis_service import MediaAnalysisService
from core.result_types import Result


class TestExifToolBinaryManager(unittest.TestCase):
    """Test ExifTool binary detection and validation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = ExifToolBinaryManager()
    
    def test_initialization(self):
        """Test manager initialization"""
        self.assertIsNotNone(self.manager)
        self.assertIsInstance(self.manager.is_valid, bool)
    
    def test_get_status_info(self):
        """Test status information retrieval"""
        status = self.manager.get_status_info()
        
        self.assertIn('available', status)
        self.assertIn('version', status)
        self.assertIn('path', status)
        self.assertIn('valid', status)
    
    def test_download_instructions(self):
        """Test platform-specific download instructions"""
        instructions = self.manager.get_download_instructions()
        
        self.assertIsInstance(instructions, str)
        self.assertTrue(len(instructions) > 0)
        self.assertIn('ExifTool', instructions)
    
    def test_features_info(self):
        """Test features information"""
        features = self.manager.get_features_info()
        
        self.assertIn('gps_extraction', features)
        self.assertIn('batch_processing', features)
        self.assertIn('json_output', features)
        self.assertIn('fast_mode', features)
        self.assertIn('struct_output', features)
    
    @patch('subprocess.run')
    def test_validate_binary_success(self, mock_run):
        """Test successful binary validation"""
        # Mock successful validation
        mock_run.return_value = Mock(
            returncode=0,
            stdout='12.70',
            stderr=''
        )
        
        test_path = Path('/usr/bin/exiftool')
        result = self.manager.validate_binary(test_path)
        
        self.assertTrue(result)
        self.assertEqual(self.manager.binary_path, test_path)
        self.assertEqual(self.manager.version, '12.70')


class TestExifToolCommandBuilder(unittest.TestCase):
    """Test ExifTool command building"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.builder = ExifToolForensicCommandBuilder()
        self.binary_path = Path('/usr/bin/exiftool')
        self.test_file = Path('/test/image.jpg')
        self.settings = ExifToolSettings()
    
    def test_build_single_command(self):
        """Test single file command building"""
        cmd = self.builder.build_single_command(
            self.binary_path,
            self.test_file,
            self.settings
        )
        
        self.assertIsInstance(cmd, list)
        self.assertIn(str(self.binary_path), cmd)
        self.assertIn(str(self.test_file), cmd)
        self.assertIn('-json', cmd)
        self.assertIn('-fast2', cmd)
    
    def test_build_batch_command(self):
        """Test batch command building"""
        files = [Path(f'/test/file{i}.jpg') for i in range(100)]
        
        commands = self.builder.build_batch_command(
            self.binary_path,
            files,
            self.settings,
            max_batch=50
        )
        
        self.assertEqual(len(commands), 2)  # 100 files / 50 per batch
        self.assertEqual(len(commands[0]) - len(commands[0][:commands[0].index(str(files[0]))]), 50)
    
    def test_field_selection(self):
        """Test field selection based on settings"""
        # Disable all but GPS
        settings = ExifToolSettings(
            geospatial_enabled=True,
            temporal_enabled=False,
            device_enabled=False,
            document_integrity_enabled=False,
            camera_settings_enabled=False,
            file_properties_enabled=False
        )
        
        cmd = self.builder.build_single_command(
            self.binary_path,
            self.test_file,
            settings
        )
        
        # Should contain GPS fields
        cmd_str = ' '.join(cmd)
        self.assertIn('GPS', cmd_str)
        
        # Should not contain other fields
        self.assertNotIn('-AllDates', cmd)
        self.assertNotIn('-Make', cmd)
    
    def test_command_caching(self):
        """Test command caching for performance"""
        # Build command twice with same settings
        cmd1 = self.builder._build_base_command(self.binary_path, self.settings)
        cmd2 = self.builder._build_base_command(self.binary_path, self.settings)
        
        # Should use cache
        self.assertEqual(self.builder._cache_hits, 1)
        self.assertEqual(cmd1, cmd2)
    
    def test_performance_estimation(self):
        """Test performance improvement estimation"""
        improvement = self.builder.estimate_performance_improvement(5, 300)
        self.assertEqual(improvement, 2.5)  # 60-70% improvement for < 10 fields
        
        improvement = self.builder.estimate_performance_improvement(25, 300)
        self.assertEqual(improvement, 1.8)  # 40-50% improvement for < 30 fields


class TestGPSData(unittest.TestCase):
    """Test GPS data model"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.gps = GPSData(
            latitude=40.7128,
            longitude=-74.0060,
            altitude=10.5,
            accuracy=5.0,
            speed=30.0,
            direction=45.0
        )
    
    def test_decimal_degrees(self):
        """Test decimal degree conversion"""
        lat, lon = self.gps.to_decimal_degrees()
        self.assertEqual(lat, 40.7128)
        self.assertEqual(lon, -74.0060)
    
    def test_dms_conversion(self):
        """Test DMS conversion"""
        lat_dms, lon_dms = self.gps.to_dms()
        
        self.assertIn('°', lat_dms)
        self.assertIn("'", lat_dms)
        self.assertIn('"', lat_dms)
        self.assertIn('N', lat_dms)
        self.assertIn('W', lon_dms)
    
    def test_obfuscation(self):
        """Test GPS privacy obfuscation"""
        # Test different precision levels
        exact = self.gps.obfuscate(GPSPrecisionLevel.EXACT)
        self.assertEqual(round(exact.latitude, 6), 40.7128)
        
        building = self.gps.obfuscate(GPSPrecisionLevel.BUILDING)
        self.assertEqual(round(building.latitude, 4), 40.7128)
        
        block = self.gps.obfuscate(GPSPrecisionLevel.BLOCK)
        self.assertEqual(round(block.latitude, 3), 40.713)
        
        neighborhood = self.gps.obfuscate(GPSPrecisionLevel.NEIGHBORHOOD)
        self.assertEqual(round(neighborhood.latitude, 2), 40.71)
        
        # Accuracy should be removed for privacy
        self.assertIsNone(block.accuracy)


class TestDeviceInfo(unittest.TestCase):
    """Test device information model"""
    
    def test_primary_id_priority(self):
        """Test device ID priority selection"""
        device = DeviceInfo(
            make='Apple',
            model='iPhone 13',
            serial_number='ABC123',
            camera_serial='CAM456',
            device_id='DEV789'
        )
        
        # Should prefer serial_number
        self.assertEqual(device.get_primary_id(), 'ABC123')
        
        # Test fallback
        device.serial_number = None
        self.assertEqual(device.get_primary_id(), 'CAM456')
    
    def test_display_name(self):
        """Test display name generation"""
        device = DeviceInfo(
            make='Canon',
            model='EOS R5'
        )
        
        self.assertEqual(device.get_display_name(), 'Canon EOS R5')
        
        # Test fallback
        device.make = None
        self.assertEqual(device.get_display_name(), 'EOS R5')


class TestExifToolNormalizer(unittest.TestCase):
    """Test ExifTool output normalization"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ExifToolNormalizer()
        self.test_file = Path('/test/image.jpg')
    
    def test_gps_extraction_decimal(self):
        """Test GPS extraction from decimal format"""
        raw_data = {
            'GPSLatitude': 40.7128,
            'GPSLongitude': -74.0060,
            'GPSAltitude': '100 m'
        }
        
        metadata = self.normalizer.normalize(raw_data, self.test_file)
        
        self.assertIsNotNone(metadata.gps_data)
        self.assertEqual(metadata.gps_data.latitude, 40.7128)
        self.assertEqual(metadata.gps_data.longitude, -74.0060)
        self.assertEqual(metadata.gps_data.altitude, 100.0)
    
    def test_gps_extraction_dms(self):
        """Test GPS extraction from DMS format"""
        raw_data = {
            'GPSLatitude': '40 deg 42\' 46.08" N',
            'GPSLongitude': '74 deg 0\' 21.60" W'
        }
        
        metadata = self.normalizer.normalize(raw_data, self.test_file)
        
        self.assertIsNotNone(metadata.gps_data)
        self.assertAlmostEqual(metadata.gps_data.latitude, 40.7128, places=3)
        self.assertAlmostEqual(metadata.gps_data.longitude, -74.006, places=3)
    
    def test_iso6709_parsing(self):
        """Test ISO 6709 coordinate parsing"""
        raw_data = {
            'Location': '+40.7128-074.0060/'
        }
        
        metadata = self.normalizer.normalize(raw_data, self.test_file)
        
        self.assertIsNotNone(metadata.gps_data)
        self.assertEqual(metadata.gps_data.latitude, 40.7128)
        self.assertEqual(metadata.gps_data.longitude, -74.0060)
    
    def test_device_extraction(self):
        """Test device information extraction"""
        raw_data = {
            'Make': 'Apple',
            'Model': 'iPhone 13 Pro',
            'SerialNumber': 'ABC123',
            'Software': 'iOS 15.0'
        }
        
        metadata = self.normalizer.normalize(raw_data, self.test_file)
        
        self.assertIsNotNone(metadata.device_info)
        self.assertEqual(metadata.device_info.make, 'Apple')
        self.assertEqual(metadata.device_info.model, 'iPhone 13 Pro')
        self.assertEqual(metadata.device_info.serial_number, 'ABC123')
        self.assertEqual(metadata.device_info.software, 'iOS 15.0')
    
    def test_temporal_extraction(self):
        """Test temporal data extraction"""
        raw_data = {
            'DateTimeOriginal': '2024-01-15 10:30:00',
            'CreateDate': '2024-01-15 10:30:00',
            'TimeZoneOffset': '-05:00',
            'SubSecTimeOriginal': '123'
        }
        
        metadata = self.normalizer.normalize(raw_data, self.test_file)
        
        self.assertIsNotNone(metadata.temporal_data)
        self.assertIsNotNone(metadata.temporal_data.capture_time)
        self.assertEqual(metadata.temporal_data.timezone_offset, '-05:00')
        self.assertEqual(metadata.temporal_data.subsec_time_original, '123')
    
    def test_document_integrity(self):
        """Test document integrity extraction"""
        raw_data = {
            'DocumentID': 'DOC123',
            'InstanceID': 'INST456',
            'History': ['Edit 1', 'Edit 2'],
            'OriginalFileName': 'original.jpg'
        }
        
        metadata = self.normalizer.normalize(raw_data, self.test_file)
        
        self.assertIsNotNone(metadata.document_integrity)
        self.assertEqual(metadata.document_integrity.document_id, 'DOC123')
        self.assertEqual(len(metadata.document_integrity.history), 2)
        self.assertTrue(metadata.has_edit_history)


class TestExifToolAnalysisResult(unittest.TestCase):
    """Test analysis result aggregation"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create mock metadata with GPS
        self.metadata1 = ExifToolMetadata(
            file_path=Path('/test/file1.jpg'),
            gps_data=GPSData(40.7128, -74.0060),
            device_info=DeviceInfo(device_id='DEV1'),
            temporal_data=TemporalData(
                capture_time=datetime(2024, 1, 15, 10, 0, 0)
            )
        )
        
        self.metadata2 = ExifToolMetadata(
            file_path=Path('/test/file2.jpg'),
            gps_data=GPSData(40.7580, -73.9855),
            device_info=DeviceInfo(device_id='DEV1'),
            temporal_data=TemporalData(
                capture_time=datetime(2024, 1, 15, 11, 0, 0)
            )
        )
        
        self.metadata3 = ExifToolMetadata(
            file_path=Path('/test/file3.jpg'),
            device_info=DeviceInfo(device_id='DEV2')
        )
    
    def test_result_aggregation(self):
        """Test result aggregation and statistics"""
        result = ExifToolAnalysisResult(
            total_files=3,
            successful=3,
            failed=0,
            skipped=0,
            metadata_list=[self.metadata1, self.metadata2, self.metadata3],
            gps_locations=[self.metadata1, self.metadata2],
            device_map={
                'DEV1': [self.metadata1, self.metadata2],
                'DEV2': [self.metadata3]
            },
            temporal_path=[
                (self.metadata1.temporal_data.capture_time, self.metadata1),
                (self.metadata2.temporal_data.capture_time, self.metadata2)
            ],
            processing_time=1.5,
            errors=[]
        )
        
        # Test device statistics
        stats = result.get_device_statistics()
        self.assertEqual(stats['DEV1'], 2)
        self.assertEqual(stats['DEV2'], 1)
        
        # Test GPS bounds
        bounds = result.get_gps_bounds()
        self.assertIsNotNone(bounds)
        min_lat, min_lon, max_lat, max_lon = bounds
        self.assertLess(min_lat, max_lat)
        self.assertLess(min_lon, max_lon)
        
        # Test temporal range
        time_range = result.get_temporal_range()
        self.assertIsNotNone(time_range)
        start, end = time_range
        self.assertLess(start, end)


class TestMediaAnalysisServiceExifTool(unittest.TestCase):
    """Test MediaAnalysisService ExifTool integration"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.service = MediaAnalysisService()
        self.settings = ExifToolSettings()
        self.test_files = [
            Path('/test/file1.jpg'),
            Path('/test/file2.mp4')
        ]
    
    @patch.object(MediaAnalysisService, 'exiftool_wrapper')
    def test_analyze_with_exiftool(self, mock_wrapper):
        """Test ExifTool analysis through service"""
        # Mock extraction results
        mock_wrapper.extract_batch.return_value = (
            [
                {'SourceFile': '/test/file1.jpg', 'GPSLatitude': 40.7128},
                {'SourceFile': '/test/file2.mp4', 'Make': 'Apple'}
            ],
            []  # No errors
        )
        
        # Mock normalizer
        with patch.object(self.service, 'exiftool_normalizer') as mock_normalizer:
            mock_metadata = ExifToolMetadata(
                file_path=Path('/test/file1.jpg'),
                gps_data=GPSData(40.7128, -74.0060)
            )
            mock_normalizer.normalize.return_value = mock_metadata
            
            result = self.service.analyze_with_exiftool(
                self.test_files,
                self.settings
            )
            
            self.assertTrue(result.success)
            self.assertIsInstance(result.value, ExifToolAnalysisResult)
    
    def test_export_to_kml(self):
        """Test KML export functionality"""
        # Create test result with GPS data
        metadata = ExifToolMetadata(
            file_path=Path('/test/photo.jpg'),
            gps_data=GPSData(40.7128, -74.0060, altitude=10),
            device_info=DeviceInfo(device_id='iPhone', make='Apple', model='iPhone 13'),
            temporal_data=TemporalData(capture_time=datetime.now())
        )
        
        analysis_result = ExifToolAnalysisResult(
            total_files=1,
            successful=1,
            failed=0,
            skipped=0,
            metadata_list=[metadata],
            gps_locations=[metadata],
            device_map={'iPhone': [metadata]},
            temporal_path=[],
            processing_time=0.5,
            errors=[]
        )
        
        # Export to temporary file
        with tempfile.NamedTemporaryFile(suffix='.kml', delete=False) as tmp:
            output_path = Path(tmp.name)
        
        try:
            result = self.service.export_to_kml(analysis_result, output_path)
            
            self.assertTrue(result.success)
            self.assertTrue(output_path.exists())
            
            # Verify KML content
            content = output_path.read_text()
            self.assertIn('<?xml', content)
            self.assertIn('kml', content)
            self.assertIn('40.7128', content)
            self.assertIn('-74.006', content)
            self.assertIn('iPhone', content)
            
        finally:
            # Cleanup
            if output_path.exists():
                output_path.unlink()


class TestExifToolWorker(unittest.TestCase):
    """Test ExifTool worker thread"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.service = Mock()
        self.settings = ExifToolSettings()
        self.files = [Path('/test/file.jpg')]
    
    @unittest.skipIf(not QT_AVAILABLE, "Qt not available")
    def test_worker_execution(self):
        """Test worker thread execution"""
        from core.workers.exiftool_worker import ExifToolWorker
        
        # Mock service response
        mock_result = ExifToolAnalysisResult(
            total_files=1,
            successful=1,
            failed=0,
            skipped=0,
            metadata_list=[],
            gps_locations=[],
            device_map={},
            temporal_path=[],
            processing_time=0.1,
            errors=[]
        )
        
        self.service.analyze_with_exiftool.return_value = Result.success(mock_result)
        
        # Create and run worker
        worker = ExifToolWorker(
            files=self.files,
            settings=self.settings,
            service=self.service
        )
        
        result = worker.execute()
        
        self.assertTrue(result.success)
        self.assertEqual(worker.get_results(), mock_result)
    
    def test_completion_message(self):
        """Test completion message building"""
        from core.workers.exiftool_worker import ExifToolWorker
        
        worker = ExifToolWorker(
            files=self.files,
            settings=self.settings,
            service=self.service
        )
        
        # Create test result
        result = ExifToolAnalysisResult(
            total_files=100,
            successful=95,
            failed=5,
            skipped=0,
            metadata_list=[],
            gps_locations=[Mock()] * 50,
            device_map={'DEV1': [], 'DEV2': []},
            temporal_path=[],
            processing_time=10.5,
            errors=[]
        )
        
        message = worker._build_completion_message(result)
        
        self.assertIn('100 files', message)
        self.assertIn('95 successful', message)
        self.assertIn('5 failed', message)
        self.assertIn('50 with GPS', message)
        self.assertIn('2 unique devices', message)
        self.assertIn('10.5s', message)


if __name__ == '__main__':
    unittest.main()