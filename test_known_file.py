"""
Test PTS extraction on the known file you showed me earlier.
Expected: pts_time = 71723.297222, which should give 0.297222 (frame 9 @ 30fps)
"""
from pathlib import Path
from filename_parser.services.video_metadata_extractor import VideoMetadataExtractor

# Test file you showed me earlier
test_file = Path(r"D:\Cameras\A02\A02_20250521140357.mp4")

print("=" * 80)
print("PTS EXTRACTION TEST - KNOWN FILE")
print("=" * 80)
print(f"\nTest file: {test_file}")
print(f"File exists: {test_file.exists()}")

# Create extractor
extractor = VideoMetadataExtractor()

# Extract metadata
print("\n--- Extracting metadata ---")
probe_data = extractor.extract_metadata(test_file)

print(f"\nExtraction success: {probe_data.success}")
if probe_data.success:
    print(f"Duration: {probe_data.duration_seconds}s")
    print(f"Frame rate: {probe_data.frame_rate} fps")
    print(f"Resolution: {probe_data.width}x{probe_data.height}")
    print(f"Codec: {probe_data.codec_name}")

    print("\n" + "=" * 80)
    print("FRAME-ACCURATE TIMING")
    print("=" * 80)
    print(f"first_frame_pts: {probe_data.first_frame_pts:.6f}s")
    print(f"first_frame_type: {probe_data.first_frame_type}")
    print(f"first_frame_is_keyframe: {probe_data.first_frame_is_keyframe}")

    if probe_data.first_frame_pts > 0:
        frame_number = int(round(probe_data.first_frame_pts * probe_data.frame_rate))
        print(f"\nCalculated start frame: {frame_number}")

        print("\n--- EXPECTED vs ACTUAL ---")
        print("Expected (from your FFprobe output):")
        print("  Raw PTS: 71723.297222s")
        print("  Modulo 1.0: 0.297222s")
        print("  Frame number: 9 (at 30fps)")

        print(f"\nActual:")
        print(f"  Modulo 1.0: {probe_data.first_frame_pts:.6f}s")
        print(f"  Frame number: {frame_number}")

        expected_frame = 9
        if frame_number == expected_frame:
            print(f"\n[SUCCESS] Frame number matches! ({frame_number} == {expected_frame})")
        else:
            print(f"\n[WARNING] Frame number mismatch! (got {frame_number}, expected {expected_frame})")
    else:
        print("\n[ERROR] PTS is 0.0!")

print("\n" + "=" * 80)
