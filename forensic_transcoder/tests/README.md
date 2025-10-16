# Forensic Transcoder - Test Suite

## Overview

This directory contains comprehensive automated tests for the forensic_transcoder module using **real FFmpeg execution** on actual video files.

## Test File

**`test_transcode_comprehensive.py`** - Main test suite (~1200 lines)

## What It Does

Executes **150-200 strategic test cases** covering:
- All forensic quality presets (Lossless, High, Medium, Web)
- All major codecs (H.264, H.265, VP9, AV1, NVENC)
- All container formats (MP4, MKV, MOV, AVI)
- Resolution scaling with multiple algorithms
- Frame rate adjustments (24/30/60fps)
- Audio codec variations
- Advanced options (deinterlacing, pixel formats, color spaces)
- Edge cases and boundary conditions

## Smart Sampling Strategy

Instead of exhaustive testing (10,000+ combinations), uses intelligent sampling to:
- Test all presets with baseline settings
- Test all codecs independently
- Test resolution/FPS combinations systematically
- Cover edge cases
- **Result**: 90%+ coverage with ~2% of total combinations

## Output Reports

Generates 4 report types:

1. **CSV** - Detailed data (all test parameters and results)
2. **JSON** - Summary statistics (pass/fail counts, success rate)
3. **TXT** - Failed commands log (debugging info)
4. **HTML** - Visual dashboard (executive summary)

## Running Tests

### Quick Start
```bash
cd "D:\Coding\Testing\Transcoder Testing"
RUN_TESTS.bat
```

### Manual Execution
```bash
cd "D:\Coding\Active Working Coding Projects\Folder Structure Multiple Versions\Folder_Structure_HASH_Media_Analysis"

python forensic_transcoder/tests/test_transcode_comprehensive.py
```

### Configuration
Edit these paths in the script if needed:
```python
test_video_dir = Path(r"D:\Coding\Testing\Transcoder Testing\Test Video Files")
output_dir = Path(r"D:\Coding\Testing\Transcoder Testing\Testing Destination")
report_dir = Path(r"D:\Coding\Testing\Transcoder Testing\Test Result Reports")
```

## Test Classes

### `TestCase`
Dataclass defining a single test:
- `test_id`: Unique identifier (TC0001, TC0002, ...)
- `description`: Human-readable name
- `settings`: TranscodeSettings object
- `input_file`: Path to test video

### `TestResult`
Dataclass storing test execution results:
- Test parameters (codec, format, resolution, etc.)
- Execution data (status, duration, encoding speed)
- Output validation (file exists, is playable)
- Error information (message, code, details)
- FFmpeg command that was executed

### `TranscoderTestGenerator`
Generates strategic test cases:
- `_generate_preset_tests()` - All quality presets
- `_generate_codec_tests()` - All codecs
- `_generate_hardware_tests()` - NVIDIA hardware acceleration
- `_generate_format_tests()` - Container formats
- `_generate_resolution_tests()` - Scaling tests
- `_generate_fps_tests()` - Frame rate tests
- `_generate_audio_tests()` - Audio codec tests
- `_generate_advanced_tests()` - Advanced features
- `_generate_edge_case_tests()` - Boundary conditions

### `TranscoderTestExecutor`
Executes tests on real videos:
- `execute_test()` - Run single test case
- Builds FFmpeg command
- Executes transcode service
- Validates output with FFprobe
- Returns TestResult object

### `TranscoderTestReporter`
Generates reports:
- `_write_csv_report()` - Detailed CSV
- `_write_json_summary()` - Statistics JSON
- `_write_failed_log()` - Failed tests TXT
- `_write_html_report()` - Visual HTML dashboard

## Example Output

### Console
```
[1/150] TC0001: Forensic Preset: lossless_forensic... ✓ PASS (12.3s)
[2/150] TC0002: Forensic Preset: high_forensic... ✓ PASS (8.1s)
[3/150] TC0003: Codec: H.264 (software)... ✓ PASS (7.9s)
[4/150] TC0004: HW Encoder: H.264 NVENC... ✗ FAIL (0.3s)
...

TEST SUMMARY
Total Tests:   150
Passed:        132
Failed:        18
Success Rate:  88.0%
```

### CSV Report
```csv
test_id,description,status,preset,codec,format,duration_seconds,encoding_speed,...
TC0001,Forensic Preset: lossless_forensic,PASS,lossless_forensic,libx264,mp4,12.3,0.81,...
TC0002,Forensic Preset: high_forensic,PASS,high_forensic,libx264,mp4,8.1,1.23,...
TC0003,Codec: H.264 (software),PASS,high_forensic,libx264,mp4,7.9,1.27,...
TC0004,HW Encoder: H.264 NVENC,FAIL,high_forensic,h264_nvenc,mp4,0.3,,-1,CUDA not available
```

### JSON Summary
```json
{
  "test_run": {
    "total_tests": 150,
    "passed": 132,
    "failed": 18,
    "success_rate": 88.0
  },
  "failures_by_error": {
    "Codec not available": 5,
    "Hardware acceleration not supported": 10
  }
}
```

## Time Estimates

- **Software encoding**: 5-15 seconds per test
- **Hardware encoding**: 1-3 seconds per test
- **Total suite**: 15-30 minutes

## Requirements

- FFmpeg and FFprobe installed
- Test video files (provided in Test Video Files directory)
- ~5-10GB free disk space for outputs
- Python environment with forensic_transcoder dependencies

## Validation

Each successful test is validated:
1. Output file exists
2. File size > 0 bytes
3. FFprobe can read file
4. Valid resolution and duration

## Adding New Tests

```python
# In TranscoderTestGenerator class

def _generate_my_custom_tests(self) -> List[TestCase]:
    """Test my custom feature."""
    tests = []

    settings = TranscodeSettings(
        output_format="mp4",
        video_codec="libx264",
        quality_preset=QualityPreset.HIGH_FORENSIC,
        # ... your custom settings
    )

    tests.append(TestCase(
        test_id=self._next_id(),
        description="My custom test",
        settings=settings,
        input_file=self.input_files[0]
    ))

    return tests

# Then add to generate_all_tests():
test_cases.extend(self._generate_my_custom_tests())
```

## Architecture

```
Main Test Flow:
1. TranscoderTestGenerator → generates TestCase list
2. TranscoderTestExecutor → executes each TestCase
   ├── FFmpegCommandBuilder.build_transcode_command()
   ├── TranscodeService.transcode_file()
   └── VideoAnalyzerService.analyze_video() (validation)
3. TranscoderTestReporter → generates reports from TestResult list
```

## CI/CD Integration

The JSON output is perfect for automated pipelines:

```python
import json
import sys

with open('test_summary.json') as f:
    results = json.load(f)
    success_rate = results['test_run']['success_rate']

    if success_rate < 85.0:
        print(f"FAIL: Success rate {success_rate}% below threshold")
        sys.exit(1)
    else:
        print(f"PASS: Success rate {success_rate}%")
        sys.exit(0)
```

## License

Part of the Folder Structure HASH Media Analysis application.

---

**Ready to run**: Just execute `RUN_TESTS.bat` from the Testing directory! 🚀
