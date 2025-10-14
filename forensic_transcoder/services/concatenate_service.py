"""
Concatenate service.

Executes FFmpeg concatenation operations to join multiple video files
with support for both mux (fast copy) and transcode (normalize) modes.
"""

import subprocess
import tempfile
import re
from pathlib import Path
from typing import Optional, Callable, List
from datetime import datetime

from ..models.concatenate_settings import ConcatenateSettings, ConcatenationMode
from ..models.video_analysis import VideoAnalysis
from ..models.processing_result import ProcessingResult, ProcessingStatus, ProcessingType
from .ffmpeg_command_builder import FFmpegCommandBuilder
from .video_analyzer_service import VideoAnalyzerService


class ConcatenateService:
    """
    Service for executing video concatenation operations.
    
    Handles joining multiple video files using either mux (fast, no re-encode)
    or transcode (normalize specs) modes. Includes progress tracking and
    error handling.
    """
    
    def __init__(self):
        """Initialize the concatenate service."""
        self.command_builder = FFmpegCommandBuilder()
        self.analyzer = VideoAnalyzerService()
        self._cancelled = False
    
    def concatenate_files(
        self,
        settings: ConcatenateSettings,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> ProcessingResult:
        """
        Concatenate multiple video files into one output file.
        
        Args:
            settings: ConcatenateSettings configuration
            progress_callback: Optional callback for progress updates (percentage, message)
        
        Returns:
            ProcessingResult with outcome and statistics
        """
        result = ProcessingResult(
            processing_type=ProcessingType.CONCATENATE,
            input_file=settings.input_files[0] if settings.input_files else Path(""),
            output_file=settings.output_file,
            status=ProcessingStatus.IN_PROGRESS
        )
        
        try:
            # Validate inputs
            if len(settings.input_files) < 2:
                result.mark_failed("At least 2 input files required for concatenation")
                return result
            
            for input_file in settings.input_files:
                if not input_file.exists():
                    result.mark_failed(f"Input file not found: {input_file}")
                    return result
            
            if not settings.output_file:
                result.mark_failed("Output file not specified")
                return result
            
            # Calculate total input size
            result.input_size_bytes = sum(f.stat().st_size for f in settings.input_files)
            
            # Analyze input videos
            if progress_callback:
                progress_callback(5.0, "Analyzing input videos...")
            
            analyses = self._analyze_inputs(settings.input_files, progress_callback)
            
            if len(analyses) != len(settings.input_files):
                result.mark_failed("Failed to analyze one or more input files")
                return result
            
            # Check compatibility and determine mode
            if progress_callback:
                progress_callback(15.0, "Checking compatibility...")
            
            compatibility_report = self._check_compatibility(analyses, settings)
            
            if compatibility_report['mode'] == ConcatenationMode.MUX:
                if progress_callback:
                    progress_callback(20.0, "Using fast mux mode (no re-encoding)...")
                success = self._concatenate_mux(settings, result, progress_callback)
            else:
                if progress_callback:
                    progress_callback(20.0, "Using transcode mode (normalizing specs)...")
                success = self._concatenate_transcode(settings, analyses, result, progress_callback)
            
            if not success:
                return result
            
            # Verify output
            if not settings.output_file.exists():
                result.mark_failed("FFmpeg completed but output file not found")
                return result
            
            # Get output file size
            result.output_size_bytes = settings.output_file.stat().st_size
            
            # Mark as complete
            result.mark_complete(ProcessingStatus.SUCCESS)
            
            if progress_callback:
                progress_callback(100.0, f"Concatenation complete: {settings.output_file.name}")
            
            return result
            
        except Exception as e:
            result.mark_failed(str(e))
            result.error_details = str(e)
            return result
    
    def cancel(self):
        """Cancel ongoing concatenation operation."""
        self._cancelled = True
    
    def _analyze_inputs(
        self,
        input_files: List[Path],
        progress_callback: Optional[Callable[[float, str], None]]
    ) -> List[VideoAnalysis]:
        """Analyze all input files."""
        analyses = []
        total = len(input_files)
        
        for idx, input_file in enumerate(input_files):
            if self._cancelled:
                break
            
            try:
                if progress_callback:
                    pct = 5.0 + (idx / total) * 10.0
                    progress_callback(pct, f"Analyzing {input_file.name}...")
                
                analysis = self.analyzer.analyze_video(input_file)
                analyses.append(analysis)
            except Exception as e:
                print(f"Failed to analyze {input_file}: {e}")
                continue
        
        return analyses
    
    def _check_compatibility(
        self,
        analyses: List[VideoAnalysis],
        settings: ConcatenateSettings
    ) -> dict:
        """
        Check if input files are compatible for concatenation.
        
        Returns:
            Dictionary with compatibility information and recommended mode
        """
        if not analyses:
            return {'mode': ConcatenationMode.TRANSCODE, 'compatible': False}
        
        # Check if user forced a mode
        if settings.concatenation_mode != ConcatenationMode.AUTO:
            return {
                'mode': settings.concatenation_mode,
                'compatible': settings.concatenation_mode == ConcatenationMode.MUX
            }
        
        # Check compatibility
        first = analyses[0]
        all_compatible = True
        
        for analysis in analyses[1:]:
            if not first.is_compatible_with(analysis, strict=not settings.allow_minor_differences):
                all_compatible = False
                break
        
        mode = ConcatenationMode.MUX if all_compatible else ConcatenationMode.TRANSCODE
        
        return {
            'mode': mode,
            'compatible': all_compatible,
            'specs': {
                'codec': first.video_codec,
                'resolution': f"{first.width}x{first.height}",
                'fps': first.fps,
                'pixel_format': first.pixel_format
            }
        }
    
    def _concatenate_mux(
        self,
        settings: ConcatenateSettings,
        result: ProcessingResult,
        progress_callback: Optional[Callable[[float, str], None]]
    ) -> bool:
        """
        Concatenate using mux mode (fast, no re-encoding).
        
        Args:
            settings: ConcatenateSettings
            result: ProcessingResult to update
            progress_callback: Progress callback
        
        Returns:
            True if successful
        """
        concat_list_file = None
        
        try:
            # Create temporary concat list file
            concat_list_file = self._create_concat_list(settings.input_files)
            
            # Build FFmpeg command for mux concatenation
            cmd = [self.command_builder.ffmpeg_path]
            cmd.extend(['-f', 'concat'])
            cmd.extend(['-safe', '0'])
            cmd.extend(['-i', str(concat_list_file)])
            cmd.extend(['-c', 'copy'])
            
            if settings.preserve_metadata:
                cmd.extend(['-map_metadata', '0'])
            
            if settings.preserve_chapters:
                cmd.extend(['-map_chapters', '0'])
            
            # Output
            cmd.extend(['-f', settings.output_format])
            cmd.append('-y')
            cmd.append(str(settings.output_file))
            
            # Format command string
            cmd_string = self.command_builder._format_command_string(cmd)
            result.ffmpeg_command = cmd_string
            
            # Create output directory
            settings.output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Execute FFmpeg
            success = self._execute_ffmpeg(cmd, result, None, progress_callback)
            
            return success
            
        finally:
            # Clean up temp file
            if concat_list_file and concat_list_file.exists():
                try:
                    concat_list_file.unlink()
                except Exception:
                    pass
    
    def _concatenate_transcode(
        self,
        settings: ConcatenateSettings,
        analyses: List[VideoAnalysis],
        result: ProcessingResult,
        progress_callback: Optional[Callable[[float, str], None]]
    ) -> bool:
        """
        Concatenate using transcode mode (normalize and join).
        
        Args:
            settings: ConcatenateSettings
            analyses: List of input video analyses
            result: ProcessingResult to update
            progress_callback: Progress callback
        
        Returns:
            True if successful
        """
        try:
            # Build FFmpeg command for transcode concatenation
            cmd, cmd_string = self.command_builder.build_concatenate_command(settings, analyses)
            
            result.ffmpeg_command = cmd_string
            
            # Create output directory
            settings.output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Get total duration for progress tracking
            total_duration = sum(a.duration for a in analyses)
            
            # Execute FFmpeg
            success = self._execute_ffmpeg(cmd, result, total_duration, progress_callback)
            
            return success
            
        except Exception as e:
            result.mark_failed(f"Failed to build transcode command: {e}")
            return False
    
    def _create_concat_list(self, input_files: List[Path]) -> Path:
        """
        Create temporary concat list file for FFmpeg.
        
        Format:
            file '/path/to/file1.mp4'
            file '/path/to/file2.mp4'
        
        Args:
            input_files: List of input file paths
        
        Returns:
            Path to temporary concat list file
        """
        # Create temporary file
        fd, temp_path = tempfile.mkstemp(suffix='.txt', prefix='concat_list_')
        temp_file = Path(temp_path)
        
        try:
            with open(fd, 'w', encoding='utf-8') as f:
                for input_file in input_files:
                    # Convert to absolute path and escape single quotes
                    abs_path = input_file.resolve()
                    escaped_path = str(abs_path).replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")
            
            return temp_file
            
        except Exception as e:
            temp_file.unlink(missing_ok=True)
            raise RuntimeError(f"Failed to create concat list: {e}")
    
    def _execute_ffmpeg(
        self,
        cmd: List[str],
        result: ProcessingResult,
        total_duration: Optional[float],
        progress_callback: Optional[Callable[[float, str], None]]
    ) -> bool:
        """
        Execute FFmpeg command and track progress.
        
        Args:
            cmd: FFmpeg command array
            result: ProcessingResult to update
            total_duration: Total duration for progress calculation (None for mux mode)
            progress_callback: Progress callback
        
        Returns:
            True if successful
        """
        try:
            # Start FFmpeg process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            # Track progress by parsing stderr
            stderr_output = []
            
            for line in process.stderr:
                stderr_output.append(line)
                
                # Parse progress
                if progress_callback and total_duration:
                    progress_info = self._parse_ffmpeg_progress(line, total_duration)
                    if progress_info:
                        pct, speed, eta = progress_info
                        # Map 0-100% to 25-95% (reserve 0-25 for analysis, 95-100 for finalization)
                        mapped_pct = 25 + (pct * 0.70)
                        msg = f"Concatenating: {pct:.1f}%"
                        if speed:
                            msg += f" (speed: {speed:.2f}x)"
                        if eta:
                            msg += f" ETA: {eta}"
                        progress_callback(mapped_pct, msg)
                elif progress_callback:
                    # For mux mode, show indeterminate progress
                    if 'time=' in line:
                        progress_callback(50.0, "Muxing streams (fast copy)...")
            
            # Wait for completion
            process.wait()
            
            # Store output
            result.ffmpeg_output = ''.join(stderr_output)
            
            # Check return code
            if process.returncode != 0:
                error_msg = self._extract_ffmpeg_error(stderr_output)
                result.mark_failed(
                    f"FFmpeg failed with code {process.returncode}: {error_msg}",
                    process.returncode
                )
                return False
            
            # Extract performance metrics
            self._extract_performance_metrics(stderr_output, result)
            
            return True
            
        except subprocess.TimeoutExpired:
            result.mark_failed("FFmpeg process timed out")
            return False
        except Exception as e:
            result.mark_failed(f"FFmpeg execution error: {e}")
            return False
    
    def _parse_ffmpeg_progress(
        self,
        line: str,
        total_duration: float
    ) -> Optional[tuple[float, Optional[float], Optional[str]]]:
        """Parse progress from FFmpeg output line."""
        if 'time=' not in line:
            return None
        
        try:
            # Extract time
            time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})', line)
            if time_match:
                hours = int(time_match.group(1))
                minutes = int(time_match.group(2))
                seconds = float(time_match.group(3))
                current_time = hours * 3600 + minutes * 60 + seconds
                
                percentage = (current_time / total_duration) * 100.0 if total_duration > 0 else 0.0
                percentage = min(percentage, 100.0)
                
                # Extract speed
                speed = None
                speed_match = re.search(r'speed=\s*(\d+\.?\d*)x', line)
                if speed_match:
                    speed = float(speed_match.group(1))
                
                # Calculate ETA
                eta_str = None
                if speed and speed > 0 and total_duration > 0:
                    remaining_time = (total_duration - current_time) / speed
                    eta_minutes = int(remaining_time // 60)
                    eta_seconds = int(remaining_time % 60)
                    eta_str = f"{eta_minutes:02d}:{eta_seconds:02d}"
                
                return percentage, speed, eta_str
        
        except (ValueError, AttributeError, ZeroDivisionError):
            pass
        
        return None
    
    def _extract_ffmpeg_error(self, stderr_lines: List[str]) -> str:
        """Extract error message from FFmpeg stderr."""
        for line in reversed(stderr_lines[-10:]):
            if 'error' in line.lower() or 'invalid' in line.lower():
                return line.strip()
        
        for line in reversed(stderr_lines):
            if line.strip():
                return line.strip()
        
        return "Unknown error"
    
    def _extract_performance_metrics(self, stderr_lines: List[str], result: ProcessingResult):
        """Extract performance metrics from FFmpeg output."""
        for line in reversed(stderr_lines[-20:]):
            if not result.encoding_speed:
                speed_match = re.search(r'speed=\s*(\d+\.?\d*)x', line)
                if speed_match:
                    result.encoding_speed = float(speed_match.group(1))
            
            if not result.frames_processed:
                frame_match = re.search(r'frame=\s*(\d+)', line)
                if frame_match:
                    result.frames_processed = int(frame_match.group(1))
            
            if not result.average_fps:
                fps_match = re.search(r'fps=\s*(\d+\.?\d*)', line)
                if fps_match:
                    result.average_fps = float(fps_match.group(1))
            
            if result.encoding_speed and result.frames_processed and result.average_fps:
                break
