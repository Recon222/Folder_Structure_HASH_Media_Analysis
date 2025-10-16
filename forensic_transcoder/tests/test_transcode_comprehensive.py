"""
Comprehensive Transcoder Test Suite - Smart Sampling Strategy

Tests the forensic_transcoder module with real video files using strategic
sampling to cover all critical parameter combinations without exhaustive testing.

Test Strategy:
- All forensic quality presets with default codec
- All major codecs with HIGH_FORENSIC preset
- Key resolution and FPS combinations
- Hardware acceleration variants (NVIDIA only)
- Edge cases and boundary conditions

Output:
- CSV report with all test results
- JSON summary statistics
- Failed commands log
- HTML report (optional)
"""

import sys
import csv
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from itertools import product

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from forensic_transcoder.models.transcode_settings import (
    TranscodeSettings,
    QualityPreset,
    FPSMethod,
    ScalingAlgorithm
)
from forensic_transcoder.models.processing_result import ProcessingResult, ProcessingStatus
from forensic_transcoder.services.transcode_service import TranscodeService
from forensic_transcoder.services.video_analyzer_service import VideoAnalyzerService
from forensic_transcoder.services.ffmpeg_command_builder import FFmpegCommandBuilder


@dataclass
class TestCase:
    """Definition of a single test case."""
    test_id: str
    description: str
    settings: TranscodeSettings
    input_file: Path


@dataclass
class TestResult:
    """Result of a single test execution."""
    test_id: str
    description: str

    # Settings
    preset: str
    codec: str
    format: str
    resolution: str
    fps: Optional[float]
    hardware_accel: bool
    crf: Optional[int]

    # Execution
    ffmpeg_command: str
    status: str  # PASS, FAIL, SKIP, ERROR
    duration_seconds: float

    # Output
    output_file: Optional[str]
    output_size_bytes: Optional[int]
    encoding_speed: Optional[float]

    # Errors
    error_message: Optional[str]
    error_code: Optional[int]

    # Validation
    output_validated: bool
    validation_error: Optional[str]


class TranscoderTestGenerator:
    """
    Generates smart sampling test cases covering critical parameter combinations.

    Strategy:
    - Test all forensic presets with baseline settings
    - Test all major codecs independently
    - Test resolution/fps combinations
    - Test hardware acceleration
    - Test edge cases
    """

    def __init__(self, input_files: List[Path]):
        """
        Initialize test generator.

        Args:
            input_files: List of test video file paths
        """
        self.input_files = input_files
        self.test_counter = 0

    def _next_id(self) -> str:
        """Generate next test ID."""
        self.test_counter += 1
        return f"TC{self.test_counter:04d}"

    def generate_all_tests(self) -> List[TestCase]:
        """
        Generate complete test suite using smart sampling.

        Returns:
            List of TestCase objects
        """
        test_cases = []

        # Category 1: Forensic Quality Presets (baseline)
        test_cases.extend(self._generate_preset_tests())

        # Category 2: Video Codecs (software)
        test_cases.extend(self._generate_codec_tests())

        # Category 3: Hardware Acceleration (NVIDIA)
        test_cases.extend(self._generate_hardware_tests())

        # Category 4: Output Formats
        test_cases.extend(self._generate_format_tests())

        # Category 5: Resolution & Scaling
        test_cases.extend(self._generate_resolution_tests())

        # Category 6: Frame Rate Adjustments
        test_cases.extend(self._generate_fps_tests())

        # Category 7: Audio Settings
        test_cases.extend(self._generate_audio_tests())

        # Category 8: Advanced Options
        test_cases.extend(self._generate_advanced_tests())

        # Category 9: Edge Cases
        test_cases.extend(self._generate_edge_case_tests())

        return test_cases

    def _generate_preset_tests(self) -> List[TestCase]:
        """Test all forensic quality presets with default settings."""
        tests = []

        presets = [
            QualityPreset.LOSSLESS_FORENSIC,
            QualityPreset.HIGH_FORENSIC,
            QualityPreset.MEDIUM_FORENSIC,
            QualityPreset.WEB_DELIVERY,
        ]

        for preset in presets:
            settings = TranscodeSettings(
                output_format="mp4",
                video_codec="libx264",
                quality_preset=preset,
                audio_codec="aac"
            )

            tests.append(TestCase(
                test_id=self._next_id(),
                description=f"Forensic Preset: {preset.value}",
                settings=settings,
                input_file=self.input_files[0]
            ))

        return tests

    def _generate_codec_tests(self) -> List[TestCase]:
        """Test major video codecs with HIGH_FORENSIC preset."""
        tests = []

        codecs = [
            ("libx264", "H.264 (software)"),
            ("libx265", "H.265/HEVC (software)"),
            ("libvpx-vp9", "VP9 (software)"),
            # SKIP AV1 - extremely slow (5+ minutes for 14 sec video)
            # ("libaom-av1", "AV1 (software)"),
        ]

        for codec, desc in codecs:
            settings = TranscodeSettings(
                output_format="mp4" if "x26" in codec else "webm",
                video_codec=codec,
                quality_preset=QualityPreset.HIGH_FORENSIC,
                audio_codec="aac" if codec.startswith("libx26") else "libopus"
            )

            tests.append(TestCase(
                test_id=self._next_id(),
                description=f"Codec: {desc}",
                settings=settings,
                input_file=self.input_files[0]
            ))

        return tests

    def _generate_hardware_tests(self) -> List[TestCase]:
        """Test NVIDIA hardware acceleration."""
        tests = []

        hw_codecs = [
            ("h264_nvenc", "H.264 NVENC"),
            ("hevc_nvenc", "H.265 NVENC"),
        ]

        for codec, desc in hw_codecs:
            # Test with hardware encoder only
            settings = TranscodeSettings(
                output_format="mp4",
                video_codec=codec,
                quality_preset=QualityPreset.HIGH_FORENSIC,
                use_hardware_encoder=True,
                use_hardware_decoder=False,
                audio_codec="aac"
            )

            tests.append(TestCase(
                test_id=self._next_id(),
                description=f"HW Encoder: {desc}",
                settings=settings,
                input_file=self.input_files[0]
            ))

            # Test with both hardware encoder and decoder
            settings_full_hw = TranscodeSettings(
                output_format="mp4",
                video_codec=codec,
                quality_preset=QualityPreset.HIGH_FORENSIC,
                use_hardware_encoder=True,
                use_hardware_decoder=True,
                audio_codec="aac"
            )

            tests.append(TestCase(
                test_id=self._next_id(),
                description=f"HW Encoder+Decoder: {desc}",
                settings=settings_full_hw,
                input_file=self.input_files[0]
            ))

        return tests

    def _generate_format_tests(self) -> List[TestCase]:
        """Test different output container formats."""
        tests = []

        formats = [
            ("mp4", "libx264", "aac", "MP4 container"),
            ("mkv", "libx264", "aac", "Matroska container"),
            ("mov", "libx264", "aac", "QuickTime container"),
            ("avi", "libx264", "mp3", "AVI container"),
        ]

        for fmt, vcodec, acodec, desc in formats:
            settings = TranscodeSettings(
                output_format=fmt,
                video_codec=vcodec,
                quality_preset=QualityPreset.HIGH_FORENSIC,
                audio_codec=acodec
            )

            tests.append(TestCase(
                test_id=self._next_id(),
                description=f"Format: {desc}",
                settings=settings,
                input_file=self.input_files[0]
            ))

        return tests

    def _generate_resolution_tests(self) -> List[TestCase]:
        """Test resolution scaling with different algorithms."""
        tests = []

        resolutions = [
            (1920, 1080, "1080p downscale"),
            (1280, 720, "720p downscale"),
            (640, 480, "480p downscale"),
            (3840, 2160, "4K upscale"),
        ]

        algorithms = [
            ScalingAlgorithm.LANCZOS,
            ScalingAlgorithm.BICUBIC,
            ScalingAlgorithm.BILINEAR,
        ]

        # Test each resolution with default algorithm
        for width, height, desc in resolutions:
            settings = TranscodeSettings(
                output_format="mp4",
                video_codec="libx264",
                quality_preset=QualityPreset.HIGH_FORENSIC,
                output_width=width,
                output_height=height,
                scaling_algorithm=ScalingAlgorithm.LANCZOS,
                maintain_aspect_ratio=True,
                audio_codec="aac"
            )

            tests.append(TestCase(
                test_id=self._next_id(),
                description=f"Resolution: {desc}",
                settings=settings,
                input_file=self.input_files[0]
            ))

        # Test different scaling algorithms at 720p
        for algo in algorithms:
            settings = TranscodeSettings(
                output_format="mp4",
                video_codec="libx264",
                quality_preset=QualityPreset.HIGH_FORENSIC,
                output_width=1280,
                output_height=720,
                scaling_algorithm=algo,
                maintain_aspect_ratio=True,
                audio_codec="aac"
            )

            tests.append(TestCase(
                test_id=self._next_id(),
                description=f"Scaling Algorithm: {algo.value}",
                settings=settings,
                input_file=self.input_files[0]
            ))

        return tests

    def _generate_fps_tests(self) -> List[TestCase]:
        """Test frame rate adjustments."""
        tests = []

        fps_configs = [
            (24.0, FPSMethod.DUPLICATE, "24fps (duplicate frames)"),
            (30.0, FPSMethod.DUPLICATE, "30fps (duplicate frames)"),
            (60.0, FPSMethod.DUPLICATE, "60fps (duplicate frames)"),
            (30.0, FPSMethod.PTS_ADJUST, "30fps (PTS adjust)"),
        ]

        for fps, method, desc in fps_configs:
            settings = TranscodeSettings(
                output_format="mp4",
                video_codec="libx264",
                quality_preset=QualityPreset.HIGH_FORENSIC,
                target_fps=fps,
                fps_method=method,
                audio_codec="aac"
            )

            tests.append(TestCase(
                test_id=self._next_id(),
                description=f"FPS: {desc}",
                settings=settings,
                input_file=self.input_files[0]
            ))

        return tests

    def _generate_audio_tests(self) -> List[TestCase]:
        """Test different audio codec configurations."""
        tests = []

        audio_configs = [
            ("copy", None, None, "Audio: copy (no re-encode)"),
            ("aac", "128k", 44100, "Audio: AAC 128k 44.1kHz"),
            ("aac", "192k", 48000, "Audio: AAC 192k 48kHz"),
            ("aac", "320k", 48000, "Audio: AAC 320k 48kHz"),
            ("mp3", "192k", 44100, "Audio: MP3 192k 44.1kHz"),
            ("opus", "128k", 48000, "Audio: Opus 128k 48kHz"),
        ]

        for codec, bitrate, sample_rate, desc in audio_configs:
            settings = TranscodeSettings(
                output_format="mp4" if codec in ["aac", "mp3", "copy"] else "mkv",
                video_codec="libx264",
                quality_preset=QualityPreset.HIGH_FORENSIC,
                audio_codec=codec,
                audio_bitrate=bitrate,
                audio_sample_rate=sample_rate,
            )

            tests.append(TestCase(
                test_id=self._next_id(),
                description=desc,
                settings=settings,
                input_file=self.input_files[0]
            ))

        return tests

    def _generate_advanced_tests(self) -> List[TestCase]:
        """Test advanced options."""
        tests = []

        # Deinterlacing
        settings = TranscodeSettings(
            output_format="mp4",
            video_codec="libx264",
            quality_preset=QualityPreset.HIGH_FORENSIC,
            deinterlace=True,
            audio_codec="aac"
        )
        tests.append(TestCase(
            test_id=self._next_id(),
            description="Advanced: Deinterlace (yadif)",
            settings=settings,
            input_file=self.input_files[0]
        ))

        # Pixel format
        for pix_fmt in ["yuv420p", "yuv422p", "yuv444p"]:
            settings = TranscodeSettings(
                output_format="mp4",
                video_codec="libx264",
                quality_preset=QualityPreset.HIGH_FORENSIC,
                pixel_format=pix_fmt,
                audio_codec="aac"
            )
            tests.append(TestCase(
                test_id=self._next_id(),
                description=f"Advanced: Pixel Format {pix_fmt}",
                settings=settings,
                input_file=self.input_files[0]
            ))

        # Color space
        for color_space in ["bt709", "bt2020nc"]:
            settings = TranscodeSettings(
                output_format="mp4",
                video_codec="libx264",
                quality_preset=QualityPreset.HIGH_FORENSIC,
                color_space=color_space,
                audio_codec="aac"
            )
            tests.append(TestCase(
                test_id=self._next_id(),
                description=f"Advanced: Color Space {color_space}",
                settings=settings,
                input_file=self.input_files[0]
            ))

        # Metadata preservation
        settings = TranscodeSettings(
            output_format="mp4",
            video_codec="libx264",
            quality_preset=QualityPreset.HIGH_FORENSIC,
            preserve_metadata=False,
            audio_codec="aac"
        )
        tests.append(TestCase(
            test_id=self._next_id(),
            description="Advanced: Strip Metadata",
            settings=settings,
            input_file=self.input_files[0]
        ))

        return tests

    def _generate_edge_case_tests(self) -> List[TestCase]:
        """Test edge cases and boundary conditions."""
        tests = []

        # Minimum CRF (best quality)
        settings = TranscodeSettings(
            output_format="mp4",
            video_codec="libx264",
            quality_preset=QualityPreset.CUSTOM,
            crf=0,  # Lossless
            preset="veryslow",
            audio_codec="aac"
        )
        tests.append(TestCase(
            test_id=self._next_id(),
            description="Edge: CRF 0 (lossless)",
            settings=settings,
            input_file=self.input_files[0]
        ))

        # Maximum CRF (worst quality)
        settings = TranscodeSettings(
            output_format="mp4",
            video_codec="libx264",
            quality_preset=QualityPreset.CUSTOM,
            crf=51,  # Worst quality
            preset="ultrafast",
            audio_codec="aac"
        )
        tests.append(TestCase(
            test_id=self._next_id(),
            description="Edge: CRF 51 (worst quality)",
            settings=settings,
            input_file=self.input_files[0]
        ))

        # Test all input files with baseline settings
        for idx, input_file in enumerate(self.input_files[1:], start=2):
            settings = TranscodeSettings(
                output_format="mp4",
                video_codec="libx264",
                quality_preset=QualityPreset.HIGH_FORENSIC,
                audio_codec="aac"
            )
            tests.append(TestCase(
                test_id=self._next_id(),
                description=f"Edge: Different input file #{idx}",
                settings=settings,
                input_file=input_file
            ))

        return tests


class TranscoderTestExecutor:
    """Executes test cases and collects results."""

    def __init__(self, output_dir: Path):
        """
        Initialize test executor.

        Args:
            output_dir: Directory for output files
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.service = TranscodeService()
        self.analyzer = VideoAnalyzerService()
        self.command_builder = FFmpegCommandBuilder()

    def execute_test(self, test_case: TestCase) -> TestResult:
        """
        Execute a single test case.

        Args:
            test_case: TestCase to execute

        Returns:
            TestResult with execution details
        """
        start_time = time.time()

        # Generate output filename WITH EXTENSION
        output_filename = f"{test_case.test_id}.{test_case.settings.output_format}"
        output_file = self.output_dir / output_filename

        # Build FFmpeg command for logging
        try:
            cmd_array, cmd_string = self.command_builder.build_transcode_command(
                test_case.input_file,
                output_file,
                test_case.settings
            )
        except Exception as e:
            # Command building failed
            duration = time.time() - start_time
            return self._create_error_result(
                test_case,
                cmd_string="<command build failed>",
                error_message=f"Command build error: {str(e)}",
                duration=duration
            )

        # Execute transcode
        try:
            result = self.service.transcode_file(
                input_file=test_case.input_file,
                output_file=output_file,
                settings=test_case.settings,
                progress_callback=None  # Silent execution
            )
        except Exception as e:
            # Service crashed
            duration = time.time() - start_time
            return self._create_error_result(
                test_case,
                cmd_string=cmd_string,
                error_message=f"Service error: {str(e)}",
                duration=duration
            )

        duration = time.time() - start_time

        # Validate output if successful
        output_validated = False
        validation_error = None

        if result.is_success and output_file.exists():
            output_validated, validation_error = self._validate_output(output_file)

        # Create test result
        return TestResult(
            test_id=test_case.test_id,
            description=test_case.description,
            preset=test_case.settings.quality_preset.value,
            codec=test_case.settings.video_codec,
            format=test_case.settings.output_format,
            resolution=self._format_resolution(test_case.settings),
            fps=test_case.settings.target_fps,
            hardware_accel=test_case.settings.use_hardware_encoder,
            crf=test_case.settings.crf,
            ffmpeg_command=cmd_string,
            status=self._map_status(result.status),
            duration_seconds=duration,
            output_file=str(output_file) if result.is_success else None,
            output_size_bytes=result.output_size_bytes,
            encoding_speed=result.encoding_speed,
            error_message=result.error_message,
            error_code=result.error_code,
            output_validated=output_validated,
            validation_error=validation_error
        )

    def _create_error_result(
        self,
        test_case: TestCase,
        cmd_string: str,
        error_message: str,
        duration: float
    ) -> TestResult:
        """Create TestResult for errors that occurred before execution."""
        return TestResult(
            test_id=test_case.test_id,
            description=test_case.description,
            preset=test_case.settings.quality_preset.value,
            codec=test_case.settings.video_codec,
            format=test_case.settings.output_format,
            resolution=self._format_resolution(test_case.settings),
            fps=test_case.settings.target_fps,
            hardware_accel=test_case.settings.use_hardware_encoder,
            crf=test_case.settings.crf,
            ffmpeg_command=cmd_string,
            status="ERROR",
            duration_seconds=duration,
            output_file=None,
            output_size_bytes=None,
            encoding_speed=None,
            error_message=error_message,
            error_code=None,
            output_validated=False,
            validation_error=None
        )

    def _format_resolution(self, settings: TranscodeSettings) -> str:
        """Format resolution string."""
        if settings.output_width and settings.output_height:
            return f"{settings.output_width}x{settings.output_height}"
        return "source"

    def _map_status(self, proc_status: ProcessingStatus) -> str:
        """Map ProcessingStatus to test status string."""
        mapping = {
            ProcessingStatus.SUCCESS: "PASS",
            ProcessingStatus.FAILED: "FAIL",
            ProcessingStatus.CANCELLED: "CANCELLED",
            ProcessingStatus.SKIPPED: "SKIP",
            ProcessingStatus.IN_PROGRESS: "ERROR"  # Should never happen
        }
        return mapping.get(proc_status, "UNKNOWN")

    def _validate_output(self, output_file: Path) -> Tuple[bool, Optional[str]]:
        """
        Validate output file is playable.

        Args:
            output_file: Path to output file

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check file exists and has content
            if not output_file.exists():
                return False, "File does not exist"

            if output_file.stat().st_size == 0:
                return False, "File is empty (0 bytes)"

            # Use ffprobe to validate
            analysis = self.analyzer.analyze_video(output_file)

            # Check basic properties
            if analysis.width <= 0 or analysis.height <= 0:
                return False, "Invalid resolution"

            if analysis.duration <= 0:
                return False, "Invalid duration"

            return True, None

        except Exception as e:
            return False, f"Validation error: {str(e)}"


class TranscoderTestReporter:
    """Generates test reports in multiple formats."""

    def __init__(self, report_dir: Path):
        """
        Initialize test reporter.

        Args:
            report_dir: Directory for reports
        """
        self.report_dir = report_dir
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate_reports(self, results: List[TestResult], timestamp: str):
        """
        Generate all report formats.

        Args:
            results: List of TestResult objects
            timestamp: Timestamp string for filenames
        """
        # CSV report (detailed)
        csv_path = self.report_dir / f"test_results_{timestamp}.csv"
        self._write_csv_report(results, csv_path)
        print(f"✓ CSV report: {csv_path}")

        # JSON summary
        json_path = self.report_dir / f"test_summary_{timestamp}.json"
        self._write_json_summary(results, json_path)
        print(f"✓ JSON summary: {json_path}")

        # Failed commands log
        failed_results = [r for r in results if r.status in ["FAIL", "ERROR"]]
        if failed_results:
            log_path = self.report_dir / f"failed_commands_{timestamp}.txt"
            self._write_failed_log(failed_results, log_path)
            print(f"✓ Failed commands log: {log_path}")

        # HTML report
        html_path = self.report_dir / f"test_report_{timestamp}.html"
        self._write_html_report(results, html_path)
        print(f"✓ HTML report: {html_path}")

    def _write_csv_report(self, results: List[TestResult], path: Path):
        """Write detailed CSV report."""
        fieldnames = [
            'test_id', 'description', 'status', 'preset', 'codec', 'format',
            'resolution', 'fps', 'hardware_accel', 'crf', 'duration_seconds',
            'encoding_speed', 'output_file', 'output_size_bytes',
            'output_validated', 'error_message', 'error_code',
            'validation_error', 'ffmpeg_command'
        ]

        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                row = asdict(result)
                writer.writerow(row)

    def _write_json_summary(self, results: List[TestResult], path: Path):
        """Write JSON summary statistics."""
        total = len(results)
        passed = sum(1 for r in results if r.status == "PASS")
        failed = sum(1 for r in results if r.status == "FAIL")
        errors = sum(1 for r in results if r.status == "ERROR")
        skipped = sum(1 for r in results if r.status == "SKIP")

        total_duration = sum(r.duration_seconds for r in results)

        # Failures by category
        failures_by_error = {}
        for result in results:
            if result.status in ["FAIL", "ERROR"] and result.error_message:
                # Extract error category (first 50 chars)
                error_key = result.error_message[:50]
                failures_by_error[error_key] = failures_by_error.get(error_key, 0) + 1

        summary = {
            "test_run": {
                "timestamp": datetime.now().isoformat(),
                "total_tests": total,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "skipped": skipped,
                "success_rate": (passed / total * 100) if total > 0 else 0,
                "total_duration_seconds": round(total_duration, 2),
                "average_duration_seconds": round(total_duration / total, 2) if total > 0 else 0
            },
            "results_by_status": {
                "PASS": passed,
                "FAIL": failed,
                "ERROR": errors,
                "SKIP": skipped
            },
            "failures_by_error": failures_by_error,
            "validation": {
                "validated": sum(1 for r in results if r.output_validated),
                "validation_failures": sum(1 for r in results if r.validation_error is not None)
            }
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)

    def _write_failed_log(self, failed_results: List[TestResult], path: Path):
        """Write detailed log of failed tests."""
        with open(path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("FAILED TEST COMMANDS LOG\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")

            for result in failed_results:
                f.write(f"{'=' * 80}\n")
                f.write(f"TEST ID: {result.test_id}\n")
                f.write(f"Description: {result.description}\n")
                f.write(f"Status: {result.status}\n")
                f.write(f"\nSettings:\n")
                f.write(f"  Preset: {result.preset}\n")
                f.write(f"  Codec: {result.codec}\n")
                f.write(f"  Format: {result.format}\n")
                f.write(f"  Resolution: {result.resolution}\n")
                f.write(f"  FPS: {result.fps}\n")
                f.write(f"  Hardware Accel: {result.hardware_accel}\n")
                f.write(f"\nFFmpeg Command:\n")
                f.write(f"{result.ffmpeg_command}\n")
                f.write(f"\nError:\n")
                f.write(f"{result.error_message}\n")
                if result.error_code:
                    f.write(f"Exit Code: {result.error_code}\n")
                if result.validation_error:
                    f.write(f"Validation Error: {result.validation_error}\n")
                f.write("\n")

    def _write_html_report(self, results: List[TestResult], path: Path):
        """Write HTML report with styling."""
        passed = sum(1 for r in results if r.status == "PASS")
        failed = sum(1 for r in results if r.status == "FAIL")
        errors = sum(1 for r in results if r.status == "ERROR")
        total = len(results)
        success_rate = (passed / total * 100) if total > 0 else 0

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Forensic Transcoder Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .stat-box {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; }}
        .stat-box.success {{ background: linear-gradient(135deg, #52c41a 0%, #389e0d 100%); }}
        .stat-box.fail {{ background: linear-gradient(135deg, #ff4d4f 0%, #cf1322 100%); }}
        .stat-box h3 {{ margin: 0 0 10px 0; font-size: 14px; opacity: 0.9; }}
        .stat-box .value {{ font-size: 32px; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #3498db; color: white; position: sticky; top: 0; }}
        tr:hover {{ background: #f5f5f5; }}
        .status-badge {{ padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; }}
        .status-PASS {{ background: #52c41a; color: white; }}
        .status-FAIL {{ background: #ff4d4f; color: white; }}
        .status-ERROR {{ background: #faad14; color: white; }}
        .status-SKIP {{ background: #d9d9d9; color: #666; }}
        .command {{ font-family: monospace; font-size: 11px; color: #666; max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 Forensic Transcoder Test Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="summary">
            <div class="stat-box">
                <h3>TOTAL TESTS</h3>
                <div class="value">{total}</div>
            </div>
            <div class="stat-box success">
                <h3>PASSED</h3>
                <div class="value">{passed}</div>
            </div>
            <div class="stat-box fail">
                <h3>FAILED</h3>
                <div class="value">{failed}</div>
            </div>
            <div class="stat-box">
                <h3>SUCCESS RATE</h3>
                <div class="value">{success_rate:.1f}%</div>
            </div>
        </div>

        <h2>Test Results</h2>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Description</th>
                    <th>Status</th>
                    <th>Codec</th>
                    <th>Format</th>
                    <th>Duration</th>
                    <th>Speed</th>
                    <th>Error</th>
                </tr>
            </thead>
            <tbody>
"""

        for result in results:
            speed_str = f"{result.encoding_speed:.2f}x" if result.encoding_speed else "N/A"
            error_str = result.error_message[:50] + "..." if result.error_message and len(result.error_message) > 50 else (result.error_message or "")

            html += f"""
                <tr>
                    <td>{result.test_id}</td>
                    <td>{result.description}</td>
                    <td><span class="status-badge status-{result.status}">{result.status}</span></td>
                    <td>{result.codec}</td>
                    <td>{result.format}</td>
                    <td>{result.duration_seconds:.2f}s</td>
                    <td>{speed_str}</td>
                    <td>{error_str}</td>
                </tr>
"""

        html += """
            </tbody>
        </table>
    </div>
</body>
</html>
"""

        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)


def main():
    """Main test runner."""
    print("=" * 80)
    print("FORENSIC TRANSCODER - COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    print()

    # Configuration
    test_video_dir = Path(r"D:\Coding\Testing\Transcoder Testing\Test Video Files")
    output_dir = Path(r"D:\Coding\Testing\Transcoder Testing\Testing Destination")
    report_dir = Path(r"D:\Coding\Testing\Transcoder Testing\Test Result Reports")

    # Find test videos
    input_files = sorted(test_video_dir.glob("*.mp4"))

    if not input_files:
        print(f"ERROR: No test videos found in {test_video_dir}")
        return

    print(f"Found {len(input_files)} test video(s):")
    for f in input_files:
        print(f"  - {f.name}")
    print()

    # Generate test cases
    print("Generating test cases...")
    generator = TranscoderTestGenerator(input_files)
    test_cases = generator.generate_all_tests()
    print(f"✓ Generated {len(test_cases)} test cases\n")

    # Execute tests
    print("Executing tests...")
    print("-" * 80)

    executor = TranscoderTestExecutor(output_dir)
    results = []

    for idx, test_case in enumerate(test_cases, 1):
        print(f"[{idx}/{len(test_cases)}] {test_case.test_id}: {test_case.description}...", end=" ", flush=True)

        try:
            result = executor.execute_test(test_case)
            results.append(result)

            status_symbol = "✓" if result.status == "PASS" else "✗"
            print(f"{status_symbol} {result.status} ({result.duration_seconds:.2f}s)")

        except Exception as e:
            print(f"✗ CRASH: {str(e)}")
            # Create error result for crash
            results.append(TestResult(
                test_id=test_case.test_id,
                description=test_case.description,
                preset="N/A",
                codec="N/A",
                format="N/A",
                resolution="N/A",
                fps=None,
                hardware_accel=False,
                crf=None,
                ffmpeg_command="<test crashed>",
                status="ERROR",
                duration_seconds=0.0,
                output_file=None,
                output_size_bytes=None,
                encoding_speed=None,
                error_message=f"Test crash: {str(e)}",
                error_code=None,
                output_validated=False,
                validation_error=None
            ))

    print("-" * 80)
    print()

    # Generate reports
    print("Generating reports...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reporter = TranscoderTestReporter(report_dir)
    reporter.generate_reports(results, timestamp)
    print()

    # Summary
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    errors = sum(1 for r in results if r.status == "ERROR")
    total = len(results)
    success_rate = (passed / total * 100) if total > 0 else 0

    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests:   {total}")
    print(f"Passed:        {passed}")
    print(f"Failed:        {failed}")
    print(f"Errors:        {errors}")
    print(f"Success Rate:  {success_rate:.1f}%")
    print("=" * 80)


if __name__ == "__main__":
    main()
