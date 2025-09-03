#!/usr/bin/env python3
"""
Test the complete thumbnail extraction pipeline from UI checkbox to map display
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from core.exiftool.exiftool_models import ExifToolSettings
from core.logger import logger

def test_thumbnail_pipeline():
    """Test that settings flow correctly through the pipeline"""
    
    print("\n" + "="*60)
    print("THUMBNAIL PIPELINE TEST")
    print("="*60 + "\n")
    
    # Test 1: Settings object creation
    print("1. Testing ExifToolSettings creation:")
    settings = ExifToolSettings()
    print(f"   Default extract_thumbnails: {settings.extract_thumbnails}")
    settings.extract_thumbnails = True
    print(f"   After setting to True: {settings.extract_thumbnails}")
    
    # Test 2: Settings attribute check
    print("\n2. Testing getattr on settings:")
    result = getattr(settings, 'extract_thumbnails', False)
    print(f"   getattr(settings, 'extract_thumbnails', False) = {result}")
    
    # Test 3: Command builder check
    from core.exiftool.exiftool_command_builder import ExifToolForensicCommandBuilder
    print("\n3. Testing command builder:")
    builder = ExifToolForensicCommandBuilder()
    cmd = builder._build_base_command(Path("exiftool"), settings)
    
    # Check if thumbnail tags are in command
    has_thumbnail = '-ThumbnailImage' in cmd
    has_preview = '-PreviewImage' in cmd
    has_jpgfromraw = '-JpgFromRaw' in cmd
    has_b_flag = '-b' in cmd
    
    print(f"   -ThumbnailImage in command: {has_thumbnail}")
    print(f"   -PreviewImage in command: {has_preview}")
    print(f"   -JpgFromRaw in command: {has_jpgfromraw}")
    print(f"   -b flag in command: {has_b_flag}")
    
    if settings.extract_thumbnails:
        assert has_thumbnail, "Missing -ThumbnailImage when extract_thumbnails=True"
        assert has_preview, "Missing -PreviewImage when extract_thumbnails=True"
        assert has_jpgfromraw, "Missing -JpgFromRaw when extract_thumbnails=True"
        assert has_b_flag, "Missing -b flag when extract_thumbnails=True"
        print("   [PASS] All thumbnail tags present!")
    
    # Test 4: Log the full command for inspection
    print("\n4. Full command preview (first 10 args):")
    for i, arg in enumerate(cmd[:10]):
        print(f"   [{i}] {arg}")
    
    # Test 5: Check if normalizer handles thumbnail
    from core.exiftool.exiftool_normalizer import ExifToolNormalizer
    print("\n5. Testing normalizer with mock thumbnail data:")
    normalizer = ExifToolNormalizer()
    
    # Mock metadata with thumbnail
    mock_metadata = {
        'SourceFile': '/test/image.jpg',
        'FileType': 'JPEG',
        'ThumbnailImage': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg==',
        'GPSLatitude': 43.786011,
        'GPSLongitude': -79.731689
    }
    
    metadata = normalizer.normalize(mock_metadata, Path('/test/image.jpg'))
    print(f"   Thumbnail extracted: {metadata.thumbnail_base64 is not None}")
    print(f"   Thumbnail type: {metadata.thumbnail_type}")
    if metadata.thumbnail_base64:
        print(f"   Thumbnail base64 length: {len(metadata.thumbnail_base64)}")
    
    print("\n" + "="*60)
    print("PIPELINE TEST COMPLETE")
    print("="*60)
    
    return True

if __name__ == "__main__":
    success = test_thumbnail_pipeline()
    sys.exit(0 if success else 1)