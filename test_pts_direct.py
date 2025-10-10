"""
Test FFprobe directly to see what's wrong with -read_intervals
"""
import subprocess
import json

test_file = r"D:\Cameras\A02\A02_20250521140638.mp4"
ffprobe = r"C:\ffmpeg\bin\ffprobe.exe"

print("=" * 80)
print("TEST 1: With -read_intervals (current approach)")
print("=" * 80)

cmd1 = [
    ffprobe,
    "-v", "error",
    "-select_streams", "v:0",
    "-show_frames",
    "-read_intervals", "%+#1",
    "-of", "json",
    test_file
]

print(f"Command: {' '.join(cmd1)}\n")
result1 = subprocess.run(cmd1, capture_output=True, text=True)
data1 = json.loads(result1.stdout)
frame1 = data1.get("frames", [{}])[0]

print("First frame fields:")
for key, value in frame1.items():
    print(f"  {key}: {value}")

print("\n" + "=" * 80)
print("TEST 2: Without -read_intervals (get all frames)")
print("=" * 80)

cmd2 = [
    ffprobe,
    "-v", "error",
    "-select_streams", "v:0",
    "-show_frames",
    "-count_frames",
    "-of", "json",
    test_file
]

print(f"Command: {' '.join(cmd2)}\n")
print("Getting first few frames...\n")
result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=5)
data2 = json.loads(result2.stdout)
frames2 = data2.get("frames", [])

if frames2:
    print(f"Total frames retrieved: {len(frames2)}")
    print("\nFirst frame fields:")
    for key, value in frames2[0].items():
        print(f"  {key}: {value}")
else:
    print("No frames found!")

print("\n" + "=" * 80)
