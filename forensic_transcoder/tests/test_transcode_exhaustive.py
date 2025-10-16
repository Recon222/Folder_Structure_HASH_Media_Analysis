"""
Forensic Transcoder - EXHAUSTIVE Test Suite
============================================

This module provides comprehensive cross-combination testing of all transcoder settings.
Tests EVERY meaningful combination to ensure FFmpeg command building works correctly.

Test Categories:
1. Codec × Resolution Combinations (~30 tests)
2. Preset × Format Combinations (~16 tests)
3. Codec × Audio Codec Combinations (~24 tests)
4. Hardware × Resolution Combinations (~20 tests)
5. Codec × Pixel Format Combinations (~24 tests)
6. Codec × Frame Rate Combinations (~20 tests)
7. Resolution × Scaling Algorithm Combinations (~18 tests)
8. Advanced Options Combinations (~40 tests)

Total: ~190+ tests

Execution Time: 10-30 minutes depending on system performance

Reports Generated:
- CSV: Detailed test results with FFmpeg commands
- JSON: Machine-readable results
- TXT: Failed command encyclopedia
- HTML: Visual summary with command library
- FFMPEG_COMMANDS.txt: Complete encyclopedia of all FFmpeg commands
"""

import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
import json
import subprocess
import traceback
from enum import Enum

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from forensic_transcoder.models.transcode_settings import (
    TranscodeSettings,
    QualityPreset,
    ScalingAlgorithm
)
from forensic_transcoder.services.ffmpeg_command_builder import FFmpegCommandBuilder


class TestStatus(Enum):
    """Test execution status."""
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIP = "SKIP"


@dataclass
class TestCase:
    """Represents a single test case."""
    test_id: str
    category: str
    description: str
    settings: TranscodeSettings
    input_file: Path
    expected_result: str = "PASS"


@dataclass
class TestResult:
    """Represents the result of a test execution."""
    test_case: TestCase
    status: TestStatus
    duration_seconds: float
    ffmpeg_command: str
    output_file: Optional[Path] = None
    error_message: Optional[str] = None
    output_size_mb: Optional[float] = None
    validation_passed: bool = False


class ExhaustiveTestGenerator:
    """Generates exhaustive cross-combination test cases."""

    def __init__(self, input_files: List[Path]):
        """
        Initialize test generator.

        Args:
            input_files: List of input video files for testing
        """
        self.input_files = input_files
        self.test_counter = 0

    def _next_id(self) -> str:
        """Generate next test ID."""
        self.test_counter += 1
        return f"EX{self.test_counter:04d}"

    def generate_all_tests(self) -> List[TestCase]:
        """Generate complete exhaustive test suite."""
        test_cases = []

        print("\n🔬 Generating Exhaustive Test Suite...")

        # Category 1: Codec × Resolution
        codec_resolution_tests = self._generate_codec_resolution_tests()
        test_cases.extend(codec_resolution_tests)
        print(f"  ✓ Codec × Resolution: {len(codec_resolution_tests)} tests")

        # Category 2: Preset × Format
        preset_format_tests = self._generate_preset_format_tests()
        test_cases.extend(preset_format_tests)
        print(f"  ✓ Preset × Format: {len(preset_format_tests)} tests")

        # Category 3: Codec × Audio Codec
        codec_audio_tests = self._generate_codec_audio_tests()
        test_cases.extend(codec_audio_tests)
        print(f"  ✓ Codec × Audio Codec: {len(codec_audio_tests)} tests")

        # Category 4: Hardware × Resolution
        hw_resolution_tests = self._generate_hardware_resolution_tests()
        test_cases.extend(hw_resolution_tests)
        print(f"  ✓ Hardware × Resolution: {len(hw_resolution_tests)} tests")

        # Category 5: Codec × Pixel Format
        codec_pixfmt_tests = self._generate_codec_pixelformat_tests()
        test_cases.extend(codec_pixfmt_tests)
        print(f"  ✓ Codec × Pixel Format: {len(codec_pixfmt_tests)} tests")

        # Category 6: Codec × Frame Rate
        codec_fps_tests = self._generate_codec_framerate_tests()
        test_cases.extend(codec_fps_tests)
        print(f"  ✓ Codec × Frame Rate: {len(codec_fps_tests)} tests")

        # Category 7: Resolution × Scaling Algorithm
        resolution_scale_tests = self._generate_resolution_scaling_tests()
        test_cases.extend(resolution_scale_tests)
        print(f"  ✓ Resolution × Scaling: {len(resolution_scale_tests)} tests")

        # Category 8: Advanced Combinations
        advanced_tests = self._generate_advanced_combinations()
        test_cases.extend(advanced_tests)
        print(f"  ✓ Advanced Combinations: {len(advanced_tests)} tests")

        print(f"\n📊 Total Tests Generated: {len(test_cases)}")

        return test_cases

    def _generate_codec_resolution_tests(self) -> List[TestCase]:
        """Test every video codec with every common resolution."""
        tests = []

        codecs = [
            ("libx264", "mp4", "aac", "H.264"),
            ("libx265", "mp4", "aac", "H.265"),
            ("libvpx-vp9", "webm", "libopus", "VP9"),
            ("h264_nvenc", "mp4", "aac", "H.264 NVENC"),
            ("hevc_nvenc", "mp4", "aac", "H.265 NVENC"),
        ]

        resolutions = [
            (3840, 2160, "4K"),
            (1920, 1080, "1080p"),
            (1280, 720, "720p"),
            (854, 480, "480p"),
            (640, 360, "360p"),
        ]

        for codec, fmt, audio, codec_name in codecs:
            for width, height, res_name in resolutions:
                settings = TranscodeSettings(
                    output_format=fmt,
                    video_codec=codec,
                    audio_codec=audio,
                    quality_preset=QualityPreset.HIGH_FORENSIC,
                    output_width=width,
                    output_height=height,
                    use_hardware_encoder=("nvenc" in codec),
                    use_hardware_decoder=False
                )

                tests.append(TestCase(
                    test_id=self._next_id(),
                    category="Codec × Resolution",
                    description=f"{codec_name} @ {res_name}",
                    settings=settings,
                    input_file=self.input_files[0]
                ))

        return tests

    def _generate_preset_format_tests(self) -> List[TestCase]:
        """Test every quality preset with every output format."""
        tests = []

        presets = [
            QualityPreset.LOSSLESS_FORENSIC,
            QualityPreset.HIGH_FORENSIC,
            QualityPreset.MEDIUM_FORENSIC,
            QualityPreset.WEB_DELIVERY,
        ]

        formats = [
            ("mp4", "libx264", "aac"),
            ("mkv", "libx264", "aac"),
            ("mov", "libx264", "aac"),
            ("avi", "libx264", "mp3"),
        ]

        for preset in presets:
            for fmt, codec, audio in formats:
                settings = TranscodeSettings(
                    output_format=fmt,
                    video_codec=codec,
                    audio_codec=audio,
                    quality_preset=preset
                )

                tests.append(TestCase(
                    test_id=self._next_id(),
                    category="Preset × Format",
                    description=f"{preset.value} → {fmt.upper()}",
                    settings=settings,
                    input_file=self.input_files[0]
                ))

        return tests

    def _generate_codec_audio_tests(self) -> List[TestCase]:
        """Test every video codec with every audio codec."""
        tests = []

        codecs = [
            ("libx264", "mp4", "H.264"),
            ("libx265", "mp4", "H.265"),
            ("libvpx-vp9", "webm", "VP9"),
        ]

        audio_codecs = [
            ("aac", ["mp4", "mkv", "mov"]),
            ("mp3", ["mp4", "mkv", "avi"]),
            ("libopus", ["webm", "mkv"]),
            ("copy", ["mp4", "mkv", "mov", "webm", "avi"]),
        ]

        for video_codec, default_fmt, codec_name in codecs:
            for audio_codec, compatible_formats in audio_codecs:
                # Find compatible format
                fmt = default_fmt if default_fmt in compatible_formats else compatible_formats[0]

                settings = TranscodeSettings(
                    output_format=fmt,
                    video_codec=video_codec,
                    audio_codec=audio_codec,
                    quality_preset=QualityPreset.HIGH_FORENSIC
                )

                tests.append(TestCase(
                    test_id=self._next_id(),
                    category="Codec × Audio",
                    description=f"{codec_name} + {audio_codec.upper()}",
                    settings=settings,
                    input_file=self.input_files[0]
                ))

        return tests

    def _generate_hardware_resolution_tests(self) -> List[TestCase]:
        """Test hardware acceleration at every resolution."""
        tests = []

        hw_configs = [
            ("h264_nvenc", "H.264 NVENC", False, "Encoder Only"),
            ("h264_nvenc", "H.264 NVENC", True, "Encoder+Decoder"),
            ("hevc_nvenc", "H.265 NVENC", False, "Encoder Only"),
            ("hevc_nvenc", "H.265 NVENC", True, "Encoder+Decoder"),
        ]

        resolutions = [
            (1920, 1080, "1080p"),
            (1280, 720, "720p"),
            (854, 480, "480p"),
            (640, 360, "360p"),
        ]

        for codec, codec_name, use_decoder, hw_mode in hw_configs:
            for width, height, res_name in resolutions:
                settings = TranscodeSettings(
                    output_format="mp4",
                    video_codec=codec,
                    audio_codec="aac",
                    quality_preset=QualityPreset.HIGH_FORENSIC,
                    use_hardware_encoder=True,
                    use_hardware_decoder=use_decoder,
                    output_width=width,
                    output_height=height
                )

                tests.append(TestCase(
                    test_id=self._next_id(),
                    category="Hardware × Resolution",
                    description=f"{codec_name} ({hw_mode}) @ {res_name}",
                    settings=settings,
                    input_file=self.input_files[0]
                ))

        return tests

    def _generate_codec_pixelformat_tests(self) -> List[TestCase]:
        """Test every codec with different pixel formats."""
        tests = []

        codecs = [
            ("libx264", "mp4", "H.264"),
            ("libx265", "mp4", "H.265"),
            ("libvpx-vp9", "webm", "VP9"),
        ]

        pixel_formats = [
            ("yuv420p", "4:2:0 8-bit"),
            ("yuv422p", "4:2:2 8-bit"),
            ("yuv444p", "4:4:4 8-bit"),
        ]

        for codec, fmt, codec_name in codecs:
            for pix_fmt, pix_desc in pixel_formats:
                settings = TranscodeSettings(
                    output_format=fmt,
                    video_codec=codec,
                    audio_codec="aac" if fmt == "mp4" else "libopus",
                    quality_preset=QualityPreset.HIGH_FORENSIC,
                    pixel_format=pix_fmt
                )

                tests.append(TestCase(
                    test_id=self._next_id(),
                    category="Codec × Pixel Format",
                    description=f"{codec_name} + {pix_desc}",
                    settings=settings,
                    input_file=self.input_files[0]
                ))

        return tests

    def _generate_codec_framerate_tests(self) -> List[TestCase]:
        """Test every codec with different frame rates."""
        tests = []

        codecs = [
            ("libx264", "mp4", "H.264"),
            ("libx265", "mp4", "H.265"),
            ("libvpx-vp9", "webm", "VP9"),
        ]

        frame_rates = [
            (24, "24fps Cinema"),
            (30, "30fps Standard"),
            (60, "60fps Smooth"),
        ]

        for codec, fmt, codec_name in codecs:
            for fps, fps_desc in frame_rates:
                settings = TranscodeSettings(
                    output_format=fmt,
                    video_codec=codec,
                    audio_codec="aac" if fmt == "mp4" else "libopus",
                    quality_preset=QualityPreset.HIGH_FORENSIC,
                    target_fps=fps
                )

                tests.append(TestCase(
                    test_id=self._next_id(),
                    category="Codec × Frame Rate",
                    description=f"{codec_name} @ {fps_desc}",
                    settings=settings,
                    input_file=self.input_files[0]
                ))

        return tests

    def _generate_resolution_scaling_tests(self) -> List[TestCase]:
        """Test different resolutions with different scaling algorithms."""
        tests = []

        resolutions = [
            (1920, 1080, "1080p"),
            (1280, 720, "720p"),
            (640, 360, "360p"),
        ]

        algorithms = [
            (ScalingAlgorithm.LANCZOS, "Lanczos (Best)"),
            (ScalingAlgorithm.BICUBIC, "Bicubic (Balanced)"),
            (ScalingAlgorithm.BILINEAR, "Bilinear (Fast)"),
        ]

        for width, height, res_name in resolutions:
            for algo, algo_desc in algorithms:
                settings = TranscodeSettings(
                    output_format="mp4",
                    video_codec="libx264",
                    audio_codec="aac",
                    quality_preset=QualityPreset.HIGH_FORENSIC,
                    output_width=width,
                    output_height=height,
                    scaling_algorithm=algo
                )

                tests.append(TestCase(
                    test_id=self._next_id(),
                    category="Resolution × Scaling",
                    description=f"{res_name} + {algo_desc}",
                    settings=settings,
                    input_file=self.input_files[0]
                ))

        return tests

    def _generate_advanced_combinations(self) -> List[TestCase]:
        """Test advanced option combinations."""
        tests = []

        # Deinterlace with different codecs
        codecs = [("libx264", "mp4", "H.264"), ("libx265", "mp4", "H.265")]
        for codec, fmt, name in codecs:
            settings = TranscodeSettings(
                output_format=fmt,
                video_codec=codec,
                audio_codec="aac",
                quality_preset=QualityPreset.HIGH_FORENSIC,
                deinterlace=True
            )
            tests.append(TestCase(
                test_id=self._next_id(),
                category="Advanced Combinations",
                description=f"{name} + Deinterlace",
                settings=settings,
                input_file=self.input_files[0]
            ))

        # Color space with different codecs
        color_spaces = [("bt709", "BT.709"), ("bt2020nc", "BT.2020")]
        for codec, fmt, codec_name in codecs:
            for color_space, cs_name in color_spaces:
                settings = TranscodeSettings(
                    output_format=fmt,
                    video_codec=codec,
                    audio_codec="aac",
                    quality_preset=QualityPreset.HIGH_FORENSIC,
                    color_space=color_space
                )
                tests.append(TestCase(
                    test_id=self._next_id(),
                    category="Advanced Combinations",
                    description=f"{codec_name} + {cs_name}",
                    settings=settings,
                    input_file=self.input_files[0]
                ))

        # Strip metadata with different formats
        formats = ["mp4", "mkv", "mov"]
        for fmt in formats:
            settings = TranscodeSettings(
                output_format=fmt,
                video_codec="libx264",
                audio_codec="aac",
                quality_preset=QualityPreset.HIGH_FORENSIC,
                preserve_metadata=False
            )
            tests.append(TestCase(
                test_id=self._next_id(),
                category="Advanced Combinations",
                description=f"Strip Metadata ({fmt.upper()})",
                settings=settings,
                input_file=self.input_files[0]
            ))

        # CRF extremes with different codecs
        crf_values = [(0, "Lossless"), (18, "High Quality"), (28, "Balanced"), (40, "Low Quality")]
        for codec, fmt, codec_name in codecs:
            for crf, crf_desc in crf_values:
                settings = TranscodeSettings(
                    output_format=fmt,
                    video_codec=codec,
                    audio_codec="aac",
                    quality_preset=QualityPreset.HIGH_FORENSIC,
                    crf=crf
                )
                tests.append(TestCase(
                    test_id=self._next_id(),
                    category="Advanced Combinations",
                    description=f"{codec_name} CRF {crf} ({crf_desc})",
                    settings=settings,
                    input_file=self.input_files[0]
                ))

        # Audio bitrate variations with different codecs
        audio_bitrates = ["128k", "192k", "320k"]
        for bitrate in audio_bitrates:
            settings = TranscodeSettings(
                output_format="mp4",
                video_codec="libx264",
                audio_codec="aac",
                quality_preset=QualityPreset.HIGH_FORENSIC,
                audio_bitrate=bitrate
            )
            tests.append(TestCase(
                test_id=self._next_id(),
                category="Advanced Combinations",
                description=f"Audio {bitrate} AAC",
                settings=settings,
                input_file=self.input_files[0]
            ))

        # Resolution + Deinterlace + Hardware
        hw_resolutions = [(1920, 1080, "1080p"), (1280, 720, "720p")]
        for width, height, res_name in hw_resolutions:
            settings = TranscodeSettings(
                output_format="mp4",
                video_codec="h264_nvenc",
                audio_codec="aac",
                quality_preset=QualityPreset.HIGH_FORENSIC,
                use_hardware_encoder=True,
                use_hardware_decoder=True,
                output_width=width,
                output_height=height,
                deinterlace=True
            )
            tests.append(TestCase(
                test_id=self._next_id(),
                category="Advanced Combinations",
                description=f"NVENC + {res_name} + Deinterlace",
                settings=settings,
                input_file=self.input_files[0]
            ))

        return tests


class ExhaustiveTestExecutor:
    """Executes exhaustive test cases and collects results."""

    def __init__(self, output_dir: Path):
        """
        Initialize test executor.

        Args:
            output_dir: Directory for output files
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.command_builder = FFmpegCommandBuilder()

    def execute_tests(self, test_cases: List[TestCase]) -> List[TestResult]:
        """
        Execute all test cases.

        Args:
            test_cases: List of test cases to execute

        Returns:
            List of test results
        """
        results = []
        total = len(test_cases)

        print(f"\n🧪 Executing {total} Exhaustive Tests...")
        print("=" * 80)

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n[{i}/{total}] {test_case.test_id}: {test_case.description}...", end=" ")

            result = self._execute_single_test(test_case)
            results.append(result)

            status_icon = {
                TestStatus.PASS: "✓",
                TestStatus.FAIL: "✗",
                TestStatus.ERROR: "⚠",
                TestStatus.SKIP: "○"
            }[result.status]

            print(f"{status_icon} {result.status.value} ({result.duration_seconds:.2f}s)")

            if result.status == TestStatus.FAIL:
                print(f"    Error: {result.error_message[:100]}...")

        return results

    def _execute_single_test(self, test_case: TestCase) -> TestResult:
        """Execute a single test case."""
        start_time = datetime.now()
        ffmpeg_command_string = "NOT_BUILT"  # Default in case of early exception

        try:
            # Generate output filename with extension
            output_filename = f"{test_case.test_id}.{test_case.settings.output_format}"
            output_file = self.output_dir / output_filename

            # Build FFmpeg command (returns tuple of (cmd_array, cmd_string))
            ffmpeg_command_array, ffmpeg_command_string = self.command_builder.build_transcode_command(
                input_file=test_case.input_file,
                output_file=output_file,
                settings=test_case.settings
            )

            # Execute FFmpeg
            process = subprocess.run(
                ffmpeg_command_array,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300  # 5 minute timeout per test
            )

            duration = (datetime.now() - start_time).total_seconds()

            if process.returncode == 0:
                # Validate output file exists
                if output_file.exists():
                    output_size_mb = output_file.stat().st_size / (1024 * 1024)

                    return TestResult(
                        test_case=test_case,
                        status=TestStatus.PASS,
                        duration_seconds=duration,
                        ffmpeg_command=ffmpeg_command_string,
                        output_file=output_file,
                        output_size_mb=output_size_mb,
                        validation_passed=True
                    )
                else:
                    return TestResult(
                        test_case=test_case,
                        status=TestStatus.FAIL,
                        duration_seconds=duration,
                        ffmpeg_command=ffmpeg_command_string,
                        error_message="Output file not created",
                        validation_passed=False
                    )
            else:
                # FFmpeg failed
                stderr = process.stderr.decode('utf-8', errors='ignore')
                error_msg = self._extract_error_message(stderr, process.returncode)

                return TestResult(
                    test_case=test_case,
                    status=TestStatus.FAIL,
                    duration_seconds=duration,
                    ffmpeg_command=ffmpeg_command_string,
                    error_message=error_msg
                )

        except subprocess.TimeoutExpired:
            duration = (datetime.now() - start_time).total_seconds()
            return TestResult(
                test_case=test_case,
                status=TestStatus.FAIL,
                duration_seconds=duration,
                ffmpeg_command=ffmpeg_command_string,
                error_message="Test timeout (>5 minutes)"
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return TestResult(
                test_case=test_case,
                status=TestStatus.ERROR,
                duration_seconds=duration,
                ffmpeg_command=ffmpeg_command_string,
                error_message=f"{type(e).__name__}: {str(e)}"
            )

    def _extract_error_message(self, stderr: str, return_code: int) -> str:
        """Extract meaningful error message from FFmpeg stderr."""
        lines = stderr.strip().split('\n')

        # Look for common error patterns
        for line in reversed(lines):
            if 'error' in line.lower() or 'invalid' in line.lower() or 'failed' in line.lower():
                return line.strip()[:200]

        # Fallback to return code
        return f"FFmpeg failed with code {return_code}: {lines[-1][:100] if lines else 'Unknown error'}"


class ExhaustiveTestReporter:
    """Generates comprehensive test reports with FFmpeg command encyclopedia."""

    def __init__(self, report_dir: Path):
        """
        Initialize test reporter.

        Args:
            report_dir: Directory for report files
        """
        self.report_dir = report_dir
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate_all_reports(self, results: List[TestResult], duration_seconds: float) -> Dict[str, Path]:
        """
        Generate all report formats.

        Args:
            results: List of test results
            duration_seconds: Total test execution time

        Returns:
            Dictionary mapping report type to file path
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_files = {}

        print("\n📊 Generating Reports...")

        # 1. CSV Report
        csv_file = self._generate_csv_report(results, timestamp)
        report_files['csv'] = csv_file
        print(f"  ✓ CSV: {csv_file.name}")

        # 2. JSON Report
        json_file = self._generate_json_report(results, duration_seconds, timestamp)
        report_files['json'] = json_file
        print(f"  ✓ JSON: {json_file.name}")

        # 3. Failed Commands TXT
        txt_file = self._generate_failed_commands_txt(results, timestamp)
        report_files['txt'] = txt_file
        print(f"  ✓ Failed Commands: {txt_file.name}")

        # 4. HTML Report
        html_file = self._generate_html_report(results, duration_seconds, timestamp)
        report_files['html'] = html_file
        print(f"  ✓ HTML: {html_file.name}")

        # 5. FFmpeg Command Encyclopedia
        encyclopedia_file = self._generate_ffmpeg_encyclopedia(results, timestamp)
        report_files['encyclopedia'] = encyclopedia_file
        print(f"  ✓ FFmpeg Encyclopedia: {encyclopedia_file.name}")

        return report_files

    def _generate_csv_report(self, results: List[TestResult], timestamp: str) -> Path:
        """Generate CSV report with all test details."""
        csv_file = self.report_dir / f"exhaustive_test_results_{timestamp}.csv"

        with open(csv_file, 'w', encoding='utf-8') as f:
            # Header
            f.write("Test ID,Category,Description,Status,Duration (s),Output Size (MB),")
            f.write("Format,Codec,Audio,Preset,Resolution,FPS,Hardware,")
            f.write("Pixel Format,Deinterlace,Colorspace,Strip Metadata,CRF,Audio Bitrate,")
            f.write("Error Message,FFmpeg Command\n")

            # Data rows
            for result in results:
                tc = result.test_case
                s = tc.settings

                row = [
                    tc.test_id,
                    tc.category,
                    tc.description,
                    result.status.value,
                    f"{result.duration_seconds:.2f}",
                    f"{result.output_size_mb:.2f}" if result.output_size_mb else "N/A",
                    s.output_format,
                    s.video_codec,
                    s.audio_codec,
                    s.quality_preset.value if s.quality_preset else "None",
                    f"{s.output_width}x{s.output_height}" if s.output_width and s.output_height else "Original",
                    str(s.target_fps) if s.target_fps else "Original",
                    "Yes" if s.use_hardware_encoder else "No",
                    s.pixel_format or "Default",
                    "Yes" if s.deinterlace else "No",
                    s.color_space or "Default",
                    "No" if s.preserve_metadata else "Yes",
                    str(s.crf) if s.crf is not None else "Default",
                    s.audio_bitrate if s.audio_bitrate else "Default",
                    self._escape_csv(result.error_message or ""),
                    self._escape_csv(result.ffmpeg_command)
                ]

                f.write(",".join(row) + "\n")

        return csv_file

    def _generate_json_report(self, results: List[TestResult], duration: float, timestamp: str) -> Path:
        """Generate JSON report."""
        json_file = self.report_dir / f"exhaustive_test_results_{timestamp}.json"

        # Calculate statistics
        total = len(results)
        passed = sum(1 for r in results if r.status == TestStatus.PASS)
        failed = sum(1 for r in results if r.status == TestStatus.FAIL)
        errors = sum(1 for r in results if r.status == TestStatus.ERROR)
        skipped = sum(1 for r in results if r.status == TestStatus.SKIP)

        # Group failures by error
        failures_by_error = {}
        for result in results:
            if result.status in (TestStatus.FAIL, TestStatus.ERROR) and result.error_message:
                error_key = result.error_message[:50]
                failures_by_error[error_key] = failures_by_error.get(error_key, 0) + 1

        # Build report data
        report_data = {
            "test_run": {
                "timestamp": datetime.now().isoformat(),
                "total_tests": total,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "skipped": skipped,
                "success_rate": (passed / total * 100) if total > 0 else 0,
                "total_duration_seconds": duration,
                "average_duration_seconds": duration / total if total > 0 else 0
            },
            "results_by_status": {
                "PASS": passed,
                "FAIL": failed,
                "ERROR": errors,
                "SKIP": skipped
            },
            "results_by_category": self._group_by_category(results),
            "failures_by_error": failures_by_error,
            "validation": {
                "validated": sum(1 for r in results if r.validation_passed),
                "validation_failures": sum(1 for r in results if not r.validation_passed and r.status == TestStatus.PASS)
            },
            "detailed_results": [
                {
                    "test_id": r.test_case.test_id,
                    "category": r.test_case.category,
                    "description": r.test_case.description,
                    "status": r.status.value,
                    "duration_seconds": r.duration_seconds,
                    "output_size_mb": r.output_size_mb,
                    "error_message": r.error_message,
                    "ffmpeg_command": r.ffmpeg_command,
                    "settings": self._serialize_settings(r.test_case.settings)
                }
                for r in results
            ]
        }

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2)

        return json_file

    def _generate_failed_commands_txt(self, results: List[TestResult], timestamp: str) -> Path:
        """Generate text file with all failed FFmpeg commands."""
        txt_file = self.report_dir / f"failed_commands_{timestamp}.txt"

        failed_results = [r for r in results if r.status in (TestStatus.FAIL, TestStatus.ERROR)]

        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("FAILED FFMPEG COMMANDS - EXHAUSTIVE TEST SUITE\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Failures: {len(failed_results)}\n\n")

            if not failed_results:
                f.write("🎉 NO FAILURES! All tests passed successfully.\n")
            else:
                for i, result in enumerate(failed_results, 1):
                    f.write(f"\n{'=' * 80}\n")
                    f.write(f"FAILURE #{i}: {result.test_case.test_id}\n")
                    f.write(f"{'=' * 80}\n\n")
                    f.write(f"Category: {result.test_case.category}\n")
                    f.write(f"Description: {result.test_case.description}\n")
                    f.write(f"Status: {result.status.value}\n")
                    f.write(f"Duration: {result.duration_seconds:.2f}s\n\n")
                    f.write(f"Error Message:\n{result.error_message}\n\n")
                    f.write(f"FFmpeg Command:\n{result.ffmpeg_command}\n\n")
                    f.write(f"Settings:\n")
                    for key, value in asdict(result.test_case.settings).items():
                        f.write(f"  {key}: {value}\n")

        return txt_file

    def _generate_html_report(self, results: List[TestResult], duration: float, timestamp: str) -> Path:
        """Generate HTML report with visual summary."""
        html_file = self.report_dir / f"exhaustive_test_report_{timestamp}.html"

        total = len(results)
        passed = sum(1 for r in results if r.status == TestStatus.PASS)
        failed = sum(1 for r in results if r.status == TestStatus.FAIL)

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Exhaustive Test Report - {timestamp}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: #ecf0f1; padding: 20px; border-radius: 6px; text-align: center; }}
        .stat-value {{ font-size: 32px; font-weight: bold; color: #2c3e50; }}
        .stat-label {{ color: #7f8c8d; margin-top: 5px; }}
        .pass {{ color: #27ae60; }}
        .fail {{ color: #e74c3c; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th {{ background: #34495e; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ecf0f1; }}
        tr:hover {{ background: #f8f9fa; }}
        .status-pass {{ color: #27ae60; font-weight: bold; }}
        .status-fail {{ color: #e74c3c; font-weight: bold; }}
        .command {{ font-family: monospace; font-size: 11px; color: #555; max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 Exhaustive FFmpeg Test Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{total}</div>
                <div class="stat-label">Total Tests</div>
            </div>
            <div class="stat-card">
                <div class="stat-value pass">{passed}</div>
                <div class="stat-label">Passed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value fail">{failed}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{(passed/total*100):.1f}%</div>
                <div class="stat-label">Success Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{duration:.0f}s</div>
                <div class="stat-label">Total Duration</div>
            </div>
        </div>

        <h2>Test Results by Category</h2>
        <table>
            <tr>
                <th>Test ID</th>
                <th>Category</th>
                <th>Description</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Size</th>
            </tr>
"""

        for result in results:
            status_class = "status-pass" if result.status == TestStatus.PASS else "status-fail"
            size_str = f"{result.output_size_mb:.2f} MB" if result.output_size_mb else "N/A"

            html_content += f"""
            <tr>
                <td>{result.test_case.test_id}</td>
                <td>{result.test_case.category}</td>
                <td>{result.test_case.description}</td>
                <td class="{status_class}">{result.status.value}</td>
                <td>{result.duration_seconds:.2f}s</td>
                <td>{size_str}</td>
            </tr>
"""

        html_content += """
        </table>
    </div>
</body>
</html>
"""

        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return html_file

    def _generate_ffmpeg_encyclopedia(self, results: List[TestResult], timestamp: str) -> Path:
        """Generate complete encyclopedia of all FFmpeg commands."""
        encyclopedia_file = self.report_dir / f"FFMPEG_COMMAND_ENCYCLOPEDIA_{timestamp}.txt"

        with open(encyclopedia_file, 'w', encoding='utf-8') as f:
            f.write("=" * 100 + "\n")
            f.write("FFMPEG COMMAND ENCYCLOPEDIA - COMPLETE REFERENCE\n")
            f.write("=" * 100 + "\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Commands: {len(results)}\n")
            f.write(f"Successful Commands: {sum(1 for r in results if r.status == TestStatus.PASS)}\n")
            f.write(f"Failed Commands: {sum(1 for r in results if r.status != TestStatus.PASS)}\n\n")

            # Group by category
            by_category = {}
            for result in results:
                category = result.test_case.category
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append(result)

            # Write each category
            for category, cat_results in sorted(by_category.items()):
                f.write("\n" + "=" * 100 + "\n")
                f.write(f"CATEGORY: {category}\n")
                f.write("=" * 100 + "\n\n")

                for result in cat_results:
                    status_icon = "✓" if result.status == TestStatus.PASS else "✗"

                    f.write(f"\n{'-' * 100}\n")
                    f.write(f"{status_icon} {result.test_case.test_id}: {result.test_case.description}\n")
                    f.write(f"{'-' * 100}\n\n")

                    f.write(f"Status: {result.status.value}\n")
                    f.write(f"Duration: {result.duration_seconds:.2f}s\n")

                    if result.output_size_mb:
                        f.write(f"Output Size: {result.output_size_mb:.2f} MB\n")

                    if result.error_message:
                        f.write(f"\nError: {result.error_message}\n")

                    f.write(f"\nSettings:\n")
                    for key, value in asdict(result.test_case.settings).items():
                        if value is not None and value != "":
                            f.write(f"  {key}: {value}\n")

                    f.write(f"\nFFmpeg Command:\n")
                    f.write(f"{result.ffmpeg_command}\n")

        return encyclopedia_file

    def _serialize_settings(self, settings: TranscodeSettings) -> dict:
        """Serialize TranscodeSettings to JSON-compatible dict."""
        settings_dict = asdict(settings)

        # Convert Enum objects to their string values
        if 'quality_preset' in settings_dict and settings_dict['quality_preset'] is not None:
            settings_dict['quality_preset'] = settings_dict['quality_preset'].value if hasattr(settings_dict['quality_preset'], 'value') else str(settings_dict['quality_preset'])

        if 'scaling_algorithm' in settings_dict and settings_dict['scaling_algorithm'] is not None:
            settings_dict['scaling_algorithm'] = settings_dict['scaling_algorithm'].value if hasattr(settings_dict['scaling_algorithm'], 'value') else str(settings_dict['scaling_algorithm'])

        if 'fps_method' in settings_dict and settings_dict['fps_method'] is not None:
            settings_dict['fps_method'] = settings_dict['fps_method'].value if hasattr(settings_dict['fps_method'], 'value') else str(settings_dict['fps_method'])

        # Convert Path objects to strings
        if 'output_directory' in settings_dict and settings_dict['output_directory'] is not None:
            settings_dict['output_directory'] = str(settings_dict['output_directory'])

        return settings_dict

    def _escape_csv(self, text: str) -> str:
        """Escape text for CSV format."""
        if not text:
            return ""
        # Escape quotes and wrap in quotes if contains comma
        text = text.replace('"', '""')
        if ',' in text or '"' in text or '\n' in text:
            return f'"{text}"'
        return text

    def _group_by_category(self, results: List[TestResult]) -> Dict[str, Dict[str, int]]:
        """Group results by category and status."""
        by_category = {}

        for result in results:
            category = result.test_case.category
            if category not in by_category:
                by_category[category] = {"PASS": 0, "FAIL": 0, "ERROR": 0, "SKIP": 0}

            by_category[category][result.status.value] += 1

        return by_category


def main():
    """Main test execution function."""
    print("\n" + "=" * 80)
    print("FORENSIC TRANSCODER - EXHAUSTIVE TEST SUITE")
    print("=" * 80)

    # Configuration
    INPUT_DIR = Path(r"D:\Coding\Testing\Transcoder Testing\Test Video Files")
    OUTPUT_DIR = Path(r"D:\Coding\Testing\Transcoder Testing\Testing Destination\Exhaustive")
    REPORT_DIR = Path(r"D:\Coding\Testing\Transcoder Testing\Test Result Reports\Exhaustive")

    # Validate input files
    input_files = list(INPUT_DIR.glob("*.mp4"))
    if not input_files:
        print(f"\n❌ ERROR: No MP4 files found in {INPUT_DIR}")
        return 1

    print(f"\n📁 Input Files: {len(input_files)} videos")
    for f in input_files:
        print(f"  - {f.name}")

    print(f"\n📂 Output Directory: {OUTPUT_DIR}")
    print(f"📊 Report Directory: {REPORT_DIR}")

    # Create output directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate test cases
    generator = ExhaustiveTestGenerator(input_files)
    test_cases = generator.generate_all_tests()

    # Execute tests
    start_time = datetime.now()
    executor = ExhaustiveTestExecutor(OUTPUT_DIR)
    results = executor.execute_tests(test_cases)
    total_duration = (datetime.now() - start_time).total_seconds()

    # Generate reports
    reporter = ExhaustiveTestReporter(REPORT_DIR)
    report_files = reporter.generate_all_reports(results, total_duration)

    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    total = len(results)
    passed = sum(1 for r in results if r.status == TestStatus.PASS)
    failed = sum(1 for r in results if r.status == TestStatus.FAIL)

    print(f"\nTotal Tests: {total}")
    print(f"✓ Passed: {passed} ({passed/total*100:.1f}%)")
    print(f"✗ Failed: {failed} ({failed/total*100:.1f}%)")
    print(f"⏱ Duration: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")

    print("\n📊 Reports Generated:")
    for report_type, report_file in report_files.items():
        print(f"  - {report_type.upper()}: {report_file.name}")

    print("\n" + "=" * 80)
    print("✅ EXHAUSTIVE TEST SUITE COMPLETE")
    print("=" * 80 + "\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
