"""
Transcode service.

Executes FFmpeg transcoding operations with progress tracking and error handling.
"""

import subprocess
import re
import time
from pathlib import Path
from typing import Optional, Callable, List
from datetime import datetime

from ..models.transcode_settings import TranscodeSettings
from ..models.video_analysis import VideoAnalysis
from ..models.processing_result import ProcessingResult, ProcessingStatus, ProcessingType
from .ffmpeg_command_builder import FFmpegCommandBuilder
from .video_analyzer_service import VideoAnalyzerService


class TranscodeService:
    """
    Service for executing video transcoding operations.
    
    Handles single and batch transcoding with progress tracking, error handling,
    and performance monitoring. Uses FFmpegCommandBuilder to generate commands
    and executes them via subprocess.
    """
    
    def __init__(self):
        """Initialize the transcode service."""
        self.command_builder = FFmpegCommandBuilder()
        self.analyzer = VideoAnalyzerService()
        self._cancelled = False
    
    def transcode_file(
        self,
        input_file: Path,
        output_file: Path,
        settings: TranscodeSettings,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> ProcessingResult:
        """
        Transcode a single video file.
        
        Args:
            input_file: Path to input video file
            output_file: Path to output video file
            settings: TranscodeSettings configuration
            progress_callback: Optional callback for progress updates (percentage, message)
        
        Returns:
            ProcessingResult with outcome and statistics
        """
        result = ProcessingResult(
            processing_type=ProcessingType.TRANSCODE,
            input_file=input_file,
            output_file=output_file,
            status=ProcessingStatus.IN_PROGRESS
        )
        
        try:
            # Validate input file
            if not input_file.exists():
                result.mark_failed(f"Input file not found: {input_file}")
                return result
            
            # Get input file size
            result.input_size_bytes = input_file.stat().st_size
            
            # Analyze input video (optional but recommended)
            input_analysis = None
            try:
                if progress_callback:
                    progress_callback(5.0, f"Analyzing {input_file.name}...")
                input_analysis = self.analyzer.analyze_video(input_file)
            except Exception as e:
                result.add_warning(f"Could not analyze input: {e}")
            
            # Build FFmpeg command
            if progress_callback:
                progress_callback(10.0, "Building FFmpeg command...")
            
            cmd, cmd_string = self.command_builder.build_transcode_command(
                input_file,
                output_file,
                settings,
                input_analysis
            )
            
            result.ffmpeg_command = cmd_string
            
            # Validate command
            is_valid, error_msg = self.command_builder.validate_command(cmd)
            if not is_valid:
                result.mark_failed(f"Invalid FFmpeg command: {error_msg}")
                return result
            
            # Create output directory if needed
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Execute FFmpeg
            if progress_callback:
                progress_callback(15.0, "Starting transcode...")
            
            success = self._execute_ffmpeg(
                cmd,
                result,
                input_analysis,
                progress_callback
            )
            
            if not success:
                return result
            
            # Verify output file exists
            if not output_file.exists():
                result.mark_failed("FFmpeg completed but output file not found")
                return result
            
            # Get output file size
            result.output_size_bytes = output_file.stat().st_size
            
            # Mark as complete
            result.mark_complete(ProcessingStatus.SUCCESS)
            
            if progress_callback:
                progress_callback(100.0, f"Completed: {output_file.name}")
            
            return result
            
        except Exception as e:
            result.mark_failed(str(e))
            result.error_details = str(e)
            return result
    
    def transcode_batch(
        self,
        input_files: List[Path],
        settings: TranscodeSettings,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> List[ProcessingResult]:
        """
        Transcode multiple video files.
        
        Args:
            input_files: List of input file paths
            settings: TranscodeSettings configuration
            progress_callback: Optional callback for overall progress
        
        Returns:
            List of ProcessingResult objects
        """
        results = []
        total_files = len(input_files)
        
        for idx, input_file in enumerate(input_files):
            if self._cancelled:
                # Create cancelled result for remaining files
                result = ProcessingResult(
                    processing_type=ProcessingType.TRANSCODE,
                    input_file=input_file,
                    status=ProcessingStatus.CANCELLED
                )
                results.append(result)
                continue
            
            # Generate output filename
            output_file = self._generate_output_path(input_file, settings)
            
            # Update overall progress
            file_progress_start = (idx / total_files) * 100
            file_progress_range = (1 / total_files) * 100
            
            def file_progress_callback(file_pct: float, msg: str):
                if progress_callback:
                    overall_pct = file_progress_start + (file_pct / 100.0) * file_progress_range
                    progress_callback(overall_pct, f"[{idx+1}/{total_files}] {msg}")
            
            # Transcode file
            result = self.transcode_file(
                input_file,
                output_file,
                settings,
                file_progress_callback
            )
            
            results.append(result)
        
        return results
    
    def cancel(self):
        """Cancel ongoing batch operation."""
        self._cancelled = True
    
    def _execute_ffmpeg(
        self,
        cmd: List[str],
        result: ProcessingResult,
        input_analysis: Optional[VideoAnalysis],
        progress_callback: Optional[Callable[[float, str], None]]
    ) -> bool:
        """
        Execute FFmpeg command and track progress.
        
        Args:
            cmd: FFmpeg command array
            result: ProcessingResult to update
            input_analysis: Optional input video analysis for duration
            progress_callback: Progress callback
        
        Returns:
            True if successful, False otherwise
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
            duration = input_analysis.duration if input_analysis else None
            stderr_output = []
            
            for line in process.stderr:
                stderr_output.append(line)
                
                # Parse progress from FFmpeg output
                if progress_callback and duration:
                    progress_info = self._parse_ffmpeg_progress(line, duration)
                    if progress_info:
                        pct, speed, eta = progress_info
                        # Map 0-100% to 15-95% (reserve 0-15 for setup, 95-100 for finalization)
                        mapped_pct = 15 + (pct * 0.80)
                        msg = f"Encoding: {pct:.1f}% (speed: {speed:.2f}x)"
                        if eta:
                            msg += f" ETA: {eta}"
                        progress_callback(mapped_pct, msg)
            
            # Wait for process to complete
            process.wait()
            
            # Store FFmpeg output
            result.ffmpeg_output = ''.join(stderr_output)
            
            # Check return code
            if process.returncode != 0:
                error_msg = self._extract_ffmpeg_error(stderr_output)
                result.mark_failed(
                    f"FFmpeg failed with code {process.returncode}: {error_msg}",
                    process.returncode
                )
                return False
            
            # Extract performance metrics from output
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
    ) -> Optional[tuple[float, float, Optional[str]]]:
        """
        Parse progress information from FFmpeg output line.
        
        FFmpeg outputs progress to stderr in format:
        frame=  123 fps= 45 q=28.0 size=   1234kB time=00:01:23.45 bitrate=1234.5kbits/s speed=2.3x
        
        Args:
            line: FFmpeg stderr line
            total_duration: Total video duration in seconds
        
        Returns:
            Tuple of (percentage, speed, eta) or None if not a progress line
        """
        # Check if this is a progress line
        if 'time=' not in line or 'speed=' not in line:
            return None
        
        try:
            # Extract time
            time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})', line)
            if time_match:
                hours = int(time_match.group(1))
                minutes = int(time_match.group(2))
                seconds = float(time_match.group(3))
                current_time = hours * 3600 + minutes * 60 + seconds
                
                # Calculate percentage
                percentage = (current_time / total_duration) * 100.0 if total_duration > 0 else 0.0
                percentage = min(percentage, 100.0)
                
                # Extract speed
                speed_match = re.search(r'speed=\s*(\d+\.?\d*)x', line)
                speed = float(speed_match.group(1)) if speed_match else 1.0
                
                # Calculate ETA
                eta_str = None
                if speed > 0 and total_duration > 0:
                    remaining_time = (total_duration - current_time) / speed
                    eta_minutes = int(remaining_time // 60)
                    eta_seconds = int(remaining_time % 60)
                    eta_str = f"{eta_minutes:02d}:{eta_seconds:02d}"
                
                return percentage, speed, eta_str
        
        except (ValueError, AttributeError, ZeroDivisionError):
            pass
        
        return None
    
    def _extract_ffmpeg_error(self, stderr_lines: List[str]) -> str:
        """Extract error message from FFmpeg stderr output."""
        # Look for error indicators in last 10 lines
        for line in reversed(stderr_lines[-10:]):
            if 'error' in line.lower() or 'invalid' in line.lower():
                return line.strip()
        
        # Return last non-empty line if no error found
        for line in reversed(stderr_lines):
            if line.strip():
                return line.strip()
        
        return "Unknown error"
    
    def _extract_performance_metrics(self, stderr_lines: List[str], result: ProcessingResult):
        """Extract performance metrics from FFmpeg output."""
        # Look for final statistics in last few lines
        for line in reversed(stderr_lines[-20:]):
            # Extract encoding speed
            speed_match = re.search(r'speed=\s*(\d+\.?\d*)x', line)
            if speed_match and not result.encoding_speed:
                result.encoding_speed = float(speed_match.group(1))
            
            # Extract frames processed
            frame_match = re.search(r'frame=\s*(\d+)', line)
            if frame_match and not result.frames_processed:
                result.frames_processed = int(frame_match.group(1))
            
            # Extract average FPS
            fps_match = re.search(r'fps=\s*(\d+\.?\d*)', line)
            if fps_match and not result.average_fps:
                result.average_fps = float(fps_match.group(1))
            
            # Stop once we have all metrics
            if result.encoding_speed and result.frames_processed and result.average_fps:
                break
    
    def _generate_output_path(
        self,
        input_file: Path,
        settings: TranscodeSettings
    ) -> Path:
        """
        Generate output file path based on settings.
        
        Args:
            input_file: Input file path
            settings: TranscodeSettings with output configuration
        
        Returns:
            Output file path
        """
        # Get output directory
        if settings.output_directory:
            output_dir = settings.output_directory
        else:
            output_dir = input_file.parent
        
        # Parse filename pattern
        pattern = settings.output_filename_pattern
        
        # Replace placeholders
        original_name = input_file.stem
        ext = settings.output_format
        
        output_filename = pattern.format(
            original_name=original_name,
            ext=ext
        )
        
        output_path = output_dir / output_filename
        
        # Handle existing files
        if not settings.overwrite_existing and output_path.exists():
            # Add counter suffix
            counter = 1
            while output_path.exists():
                output_filename = pattern.format(
                    original_name=f"{original_name}_{counter}",
                    ext=ext
                )
                output_path = output_dir / output_filename
                counter += 1
        
        return output_path
