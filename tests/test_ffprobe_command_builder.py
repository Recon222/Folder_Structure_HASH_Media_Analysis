#!/usr/bin/env python3
"""
Unit tests for FFProbeCommandBuilder
Tests optimized command generation based on user settings
"""

import pytest
from pathlib import Path
from core.media.ffprobe_command_builder import FFProbeCommandBuilder
from core.media_analysis_models import MediaAnalysisSettings, MetadataFieldGroup


class TestFFProbeCommandBuilder:
    """Test suite for FFProbe command builder"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.builder = FFProbeCommandBuilder()
        self.binary_path = Path("/usr/bin/ffprobe")
        self.file_path = Path("/test/video.mp4")
    
    def test_minimal_field_extraction(self):
        """Test that only requested fields are included in command"""
        settings = MediaAnalysisSettings()
        
        # Disable all except format and duration
        settings.general_fields.fields = {
            'format': True,
            'duration': True,
            'file_size': False,
            'bitrate': False,
            'creation_date': False
        }
        settings.video_fields.enabled = False
        settings.audio_fields.enabled = False
        settings.location_fields.enabled = False
        settings.device_fields.enabled = False
        
        cmd = self.builder.build_command(self.binary_path, self.file_path, settings)
        cmd_str = ' '.join(cmd)
        
        # Should include requested fields
        assert 'format_name' in cmd_str or 'format=' in cmd_str
        assert 'duration' in cmd_str
        
        # Should NOT include unrequested fields
        assert 'size' not in cmd_str or 'format=size' not in cmd_str
        assert 'bit_rate' not in cmd_str or 'format=bit_rate' not in cmd_str
        
        # Should have minimal command length
        assert len(cmd) < 15  # Optimized command should be short
    
    def test_all_fields_extraction(self):
        """Test extraction with all fields enabled"""
        settings = MediaAnalysisSettings()
        
        # Enable everything
        for attr in dir(settings):
            if attr.endswith('_fields'):
                field_group = getattr(settings, attr)
                if isinstance(field_group, MetadataFieldGroup):
                    field_group.enabled = True
                    for field in field_group.fields:
                        field_group.fields[field] = True
        
        cmd = self.builder.build_command(self.binary_path, self.file_path, settings)
        cmd_str = ' '.join(cmd)
        
        # Should include many fields
        assert len(cmd) > 10
        assert 'codec_name' in cmd_str
        assert 'width' in cmd_str or 'height' in cmd_str
        assert 'sample_rate' in cmd_str
    
    def test_frame_analysis_command(self):
        """Test GOP structure and frame analysis command generation"""
        settings = MediaAnalysisSettings()
        
        # Enable frame analysis
        settings.frame_analysis_fields = MetadataFieldGroup(
            enabled=True,
            fields={
                'gop_structure': True,
                'keyframe_interval': True,
                'frame_type_distribution': True
            }
        )
        
        cmd = self.builder.build_command(self.binary_path, self.file_path, settings)
        cmd_str = ' '.join(cmd)
        
        # Should include frame analysis parameters
        assert '-select_streams' in cmd
        assert 'v:0' in cmd_str
        assert 'pict_type' in cmd_str
        assert 'key_frame' in cmd_str
        assert '-read_intervals' in cmd
    
    def test_aspect_ratio_extraction(self):
        """Test SAR, PAR, DAR extraction"""
        settings = MediaAnalysisSettings()
        
        # Enable only aspect ratio fields
        settings.general_fields.enabled = False
        settings.video_fields.fields = {
            'video_codec': False,
            'resolution': False,
            'frame_rate': False,
            'aspect_ratio': True,
            'color_space': False
        }
        settings.audio_fields.enabled = False
        
        cmd = self.builder.build_command(self.binary_path, self.file_path, settings)
        cmd_str = ' '.join(cmd)
        
        # Should include aspect ratio fields
        assert 'display_aspect_ratio' in cmd_str
        assert 'sample_aspect_ratio' in cmd_str or 'sar' in cmd_str
    
    def test_advanced_video_fields(self):
        """Test advanced video properties extraction"""
        settings = MediaAnalysisSettings()
        
        # Enable advanced video fields
        settings.advanced_video_fields = MetadataFieldGroup(
            enabled=True,
            fields={
                'profile': True,
                'level': True,
                'pixel_format': True,
                'color_range': True,
                'color_transfer': True,
                'color_primaries': True
            }
        )
        
        cmd = self.builder.build_command(self.binary_path, self.file_path, settings)
        cmd_str = ' '.join(cmd)
        
        # Should include advanced fields
        assert 'profile' in cmd_str
        assert 'level' in cmd_str
        assert 'pix_fmt' in cmd_str
        assert 'color_range' in cmd_str
    
    def test_no_fields_selected(self):
        """Test behavior when no fields are selected"""
        settings = MediaAnalysisSettings()
        
        # Disable all field groups
        settings.general_fields.enabled = False
        settings.video_fields.enabled = False
        settings.audio_fields.enabled = False
        settings.location_fields.enabled = False
        settings.device_fields.enabled = False
        
        cmd = self.builder.build_command(self.binary_path, self.file_path, settings)
        
        # Should still have basic command structure
        assert str(self.binary_path) in cmd
        assert str(self.file_path) in cmd
        assert '-v' in cmd
        assert 'quiet' in cmd
        assert '-print_format' in cmd
        assert 'json' in cmd
    
    def test_location_fields_extraction(self):
        """Test GPS and location data extraction"""
        settings = MediaAnalysisSettings()
        
        # Enable location fields (usually disabled by default)
        settings.location_fields.enabled = True
        settings.location_fields.fields = {
            'gps_latitude': True,
            'gps_longitude': True,
            'location_name': True
        }
        
        cmd = self.builder.build_command(self.binary_path, self.file_path, settings)
        cmd_str = ' '.join(cmd)
        
        # Should include tags for location data
        assert 'tags' in cmd_str
        # The command should request format tags
        assert 'format=' in cmd_str
    
    def test_simple_command_builder(self):
        """Test the simple command builder for quick checks"""
        cmd = self.builder.build_simple_command(self.binary_path, self.file_path)
        cmd_str = ' '.join(cmd)
        
        # Should be minimal
        assert len(cmd) <= 8
        assert 'format_name' in cmd_str
        assert 'duration' in cmd_str
        assert 'size' in cmd_str
        assert str(self.file_path) in cmd
    
    def test_performance_estimation(self):
        """Test performance improvement estimation"""
        # Test with minimal fields
        estimate = self.builder.estimate_performance_improvement(3, 25)
        assert estimate['improvement_percent'] > 50
        assert estimate['data_reduction_percent'] > 80
        
        # Test with many fields
        estimate = self.builder.estimate_performance_improvement(20, 25)
        assert estimate['improvement_percent'] < 20
        assert estimate['data_reduction_percent'] < 20
    
    def test_optimization_info(self):
        """Test optimization statistics retrieval"""
        info = self.builder.get_optimization_info()
        
        assert 'cache_hits' in info
        assert 'cache_misses' in info
        assert 'cache_hit_rate' in info
        assert 'cached_patterns' in info
        assert info['cache_hit_rate'] >= 0
        assert info['cache_hit_rate'] <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])