"""
Quick test to debug PTS extraction issue.
"""
from pathlib import Path
from filename_parser.services.video_metadata_extractor import VideoMetadataExtractor

# Test file
test_file = Path(r"D:\Cameras\A02\A02_20250521140638.mp4")

print("=" * 80)
print("PTS EXTRACTION DEBUG TEST")
print("=" * 80)
print(f"\nTest file: {test_file}")
print(f"File exists: {test_file.exists()}")

# Create extractor
extractor = VideoMetadataExtractor()

# Extract metadata
print("\n--- Extracting metadata ---")
probe_data = extractor.extract_metadata(test_file)

print(f"\nExtraction success: {probe_data.success}")
if not probe_data.success:
    print(f"Error: {probe_data.error_message}")
else:
    print(f"Duration: {probe_data.duration_seconds}s")
    print(f"Frame rate: {probe_data.frame_rate} fps")
    print(f"Resolution: {probe_data.width}x{probe_data.height}")
    print(f"Codec: {probe_data.codec_name}")

    print("\n--- FRAME-ACCURATE TIMING ---")
    print(f"first_frame_pts: {probe_data.first_frame_pts:.6f}s")
    print(f"first_frame_type: {probe_data.first_frame_type}")
    print(f"first_frame_is_keyframe: {probe_data.first_frame_is_keyframe}")

    if probe_data.first_frame_pts > 0:
        frame_number = int(round(probe_data.first_frame_pts * probe_data.frame_rate))
        print(f"\nCalculated start frame: {frame_number}")
        print("[OK] PTS extraction working!")
    else:
        print("\n[ERROR] PTS is 0.0 - something is wrong!")
        print("\nDEBUG: Let's check what FFprobe returns...")

        # Run FFprobe manually to see raw output
        import subprocess
        import json
        from filename_parser.core.binary_manager import binary_manager

        ffprobe_path = binary_manager.get_ffprobe_path()
        if ffprobe_path:
            cmd = [
                ffprobe_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_frames",
                "-read_intervals", "%+#1",
                "-of", "json",
                str(test_file)
            ]

            print(f"\nRunning: {' '.join(cmd)}\n")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                frames = data.get("frames", [])

                if frames:
                    first_frame = frames[0]
                    print("First frame data:")
                    print(f"  pkt_pts_time: {first_frame.get('pkt_pts_time')}")
                    print(f"  pict_type: {first_frame.get('pict_type')}")
                    print(f"  key_frame: {first_frame.get('key_frame')}")

                    if first_frame.get('pkt_pts_time'):
                        raw_pts = float(first_frame.get('pkt_pts_time'))
                        modulo_pts = raw_pts % 1.0
                        print(f"\n  Raw PTS: {raw_pts:.6f}s")
                        print(f"  Modulo 1.0: {modulo_pts:.6f}s")
                        print(f"  Frame number: {int(round(modulo_pts * probe_data.frame_rate))}")
                else:
                    print("No frames in FFprobe output!")
            else:
                print(f"FFprobe error: {result.stderr}")

print("\n" + "=" * 80)
