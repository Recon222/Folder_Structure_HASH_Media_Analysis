"""
FFmpeg command builder service.

Constructs FFmpeg command line arguments from TranscodeSettings and
ConcatenateSettings objects. Commands are returned as arrays suitable
for subprocess execution and as strings for display/editing.
"""

from pathlib import Path
from typing import List, Optional, Tuple
import shlex

from ..models.transcode_settings import TranscodeSettings, FPSMethod, ScalingAlgorithm
from ..models.concatenate_settings import ConcatenateSettings, ConcatenationMode, TransitionType
from ..models.video_analysis import VideoAnalysis
from ..core import (
    get_preset_for_codec,
    get_crf_for_preset,
    is_hardware_codec,
    get_available_tune_options,
)
from filename_parser.core.binary_manager import binary_manager


class FFmpegCommandBuilder:
    """
    Service for building FFmpeg command line arguments.
    
    Translates high-level TranscodeSettings and ConcatenateSettings into
    complete FFmpeg command arrays. Commands can be returned as lists for
    subprocess execution or as formatted strings for display/editing.
    """
    
    def __init__(self):
        """Initialize the command builder."""
        self.ffmpeg_path = binary_manager.get_ffmpeg_path()
        if not self.ffmpeg_path:
            raise RuntimeError("FFmpeg not found. Please ensure FFmpeg is installed.")
    
    def build_transcode_command(
        self,
        input_file: Path,
        output_file: Path,
        settings: TranscodeSettings,
        input_analysis: Optional[VideoAnalysis] = None
    ) -> Tuple[List[str], str]:
        """
        Build FFmpeg command for transcoding a single file.
        
        Args:
            input_file: Path to input video file
            output_file: Path to output video file
            settings: TranscodeSettings configuration
            input_analysis: Optional VideoAnalysis for input-aware optimizations
        
        Returns:
            Tuple of (command_array, command_string)
            - command_array: List of strings suitable for subprocess.run()
            - command_string: Formatted command string for display/editing
        """
        cmd = [self.ffmpeg_path]
        
        # === Input Options ===
        
        # Hardware decoder
        if settings.use_hardware_decoder:
            cmd.extend(self._build_hardware_decoder_args(settings.video_codec, settings.gpu_index))
        
        # Input file
        cmd.extend(['-i', str(input_file)])
        
        # === Video Encoding Options ===
        
        # Video codec
        cmd.extend(['-c:v', settings.video_codec])
        
        # Quality settings
        if settings.quality_preset.name != 'CUSTOM':
            # Use preset-based settings
            preset = get_preset_for_codec(settings.quality_preset, settings.video_codec)
            crf = get_crf_for_preset(settings.quality_preset, settings.video_codec)
            
            cmd.extend(['-crf', str(crf)])
            cmd.extend(['-preset', preset])
        else:
            # Use custom settings
            if settings.crf is not None:
                cmd.extend(['-crf', str(settings.crf)])
            if settings.preset:
                cmd.extend(['-preset', settings.preset])
        
        # Profile and level
        if settings.profile:
            cmd.extend(['-profile:v', settings.profile])
        if settings.level:
            cmd.extend(['-level:v', settings.level])
        
        # Tune option (if supported by codec)
        if settings.tune and settings.tune in get_available_tune_options(settings.video_codec):
            cmd.extend(['-tune', settings.tune])
        
        # Bitrate settings (if specified - overrides CRF)
        if settings.bitrate:
            cmd.extend(['-b:v', settings.bitrate])
            if settings.max_bitrate:
                cmd.extend(['-maxrate', settings.max_bitrate])
            if settings.buffer_size:
                cmd.extend(['-bufsize', settings.buffer_size])
        
        # === Video Filters ===
        
        video_filters = []
        
        # Deinterlace
        if settings.deinterlace:
            video_filters.append('yadif')
        
        # Resolution scaling
        if settings.output_width or settings.output_height:
            scale_filter = self._build_scale_filter(
                settings.output_width,
                settings.output_height,
                settings.maintain_aspect_ratio,
                settings.scaling_algorithm
            )
            video_filters.append(scale_filter)
        
        # Frame rate adjustment
        if settings.target_fps:
            fps_filter = self._build_fps_filter(settings.target_fps, settings.fps_method)
            video_filters.append(fps_filter)
        
        # Custom video filters
        video_filters.extend(settings.custom_video_filters)
        
        # Apply video filters
        if video_filters:
            cmd.extend(['-vf', ','.join(video_filters)])
        
        # Pixel format
        if settings.pixel_format:
            cmd.extend(['-pix_fmt', settings.pixel_format])
        
        # Color space and range
        if settings.color_space:
            cmd.extend(['-colorspace', settings.color_space])
        if settings.color_range:
            cmd.extend(['-color_range', settings.color_range])
        
        # === Audio Encoding Options ===
        
        if settings.audio_codec == 'copy':
            cmd.extend(['-c:a', 'copy'])
        else:
            cmd.extend(['-c:a', settings.audio_codec])
            
            if settings.audio_bitrate:
                cmd.extend(['-b:a', settings.audio_bitrate])
            
            if settings.audio_sample_rate:
                cmd.extend(['-ar', str(settings.audio_sample_rate)])
            
            if settings.audio_channels:
                cmd.extend(['-ac', str(settings.audio_channels)])
            
            # Custom audio filters
            if settings.custom_audio_filters:
                cmd.extend(['-af', ','.join(settings.custom_audio_filters)])
        
        # === Subtitle Handling ===
        
        if settings.copy_subtitles:
            cmd.extend(['-c:s', 'copy'])
        elif settings.burn_subtitles:
            # Burn subtitles into video (already in video filter chain if needed)
            if settings.subtitle_track is not None:
                # This would need to be added to video filters
                pass
        else:
            cmd.extend(['-sn'])  # No subtitles
        
        # === Metadata Options ===
        
        if not settings.preserve_metadata:
            cmd.append('-map_metadata')
            cmd.append('-1')  # Strip all metadata

        if settings.copy_chapters:
            cmd.append('-map_chapters')
            cmd.append('0')
        
        # === Hardware Encoder Options ===
        
        if is_hardware_codec(settings.video_codec):
            # NVENC-specific options
            if 'nvenc' in settings.video_codec:
                cmd.extend(['-rc', 'vbr'])  # Variable bitrate mode
                if settings.two_pass_encoding:
                    cmd.extend(['-multipass', 'fullres'])
            
            # GPU selection
            if settings.gpu_index > 0:
                cmd.extend(['-gpu', str(settings.gpu_index)])
        
        # === Output Options ===
        
        # Two-pass encoding (first pass)
        if settings.two_pass_encoding and not is_hardware_codec(settings.video_codec):
            # This will need special handling - two separate commands
            # For now, we'll just flag it
            pass
        
        # Output format
        cmd.extend(['-f', settings.output_format])
        
        # Overwrite output file
        cmd.append('-y')
        
        # Output file
        cmd.append(str(output_file))
        
        # Build command string
        cmd_string = self._format_command_string(cmd)
        
        return cmd, cmd_string
    
    def build_concatenate_command(
        self,
        settings: ConcatenateSettings,
        analyses: List[VideoAnalysis]
    ) -> Tuple[List[str], str]:
        """
        Build FFmpeg command for concatenating multiple files.
        
        Args:
            settings: ConcatenateSettings configuration
            analyses: List of VideoAnalysis objects for input files
        
        Returns:
            Tuple of (command_array, command_string)
        
        Raises:
            ValueError: If settings are invalid or files incompatible
        """
        if len(settings.input_files) < 2:
            raise ValueError("At least 2 input files required for concatenation")
        
        if len(settings.input_files) != len(analyses):
            raise ValueError("Number of analyses must match number of input files")
        
        # Determine concatenation mode
        mode = self._determine_concat_mode(settings, analyses)
        
        if mode == ConcatenationMode.MUX:
            return self._build_mux_concat_command(settings)
        else:
            return self._build_transcode_concat_command(settings, analyses)
    
    def _determine_concat_mode(
        self,
        settings: ConcatenateSettings,
        analyses: List[VideoAnalysis]
    ) -> ConcatenationMode:
        """Determine whether to use mux or transcode concatenation."""
        if settings.concatenation_mode != ConcatenationMode.AUTO:
            return settings.concatenation_mode
        
        # Check if all files are compatible
        if not analyses:
            return ConcatenationMode.TRANSCODE
        
        first = analyses[0]
        for analysis in analyses[1:]:
            if not first.is_compatible_with(analysis, strict=not settings.allow_minor_differences):
                return ConcatenationMode.TRANSCODE
        
        return ConcatenationMode.MUX
    
    def _build_mux_concat_command(
        self,
        settings: ConcatenateSettings
    ) -> Tuple[List[str], str]:
        """Build command for mux concatenation (no re-encoding)."""
        cmd = [self.ffmpeg_path]
        
        # Create concat demuxer input
        # Format: file 'path1.mp4'\nfile 'path2.mp4'\n...
        concat_list = []
        for input_file in settings.input_files:
            # Escape single quotes in filename
            escaped_path = str(input_file).replace("'", "'\\''")
            concat_list.append(f"file '{escaped_path}'")
        
        # We'll need to write this to a temp file in the actual execution
        # For now, just note this in the command
        cmd.extend(['-f', 'concat'])
        cmd.extend(['-safe', '0'])
        cmd.extend(['-i', '<concat_list.txt>'])  # Placeholder
        
        # Copy streams
        cmd.extend(['-c', 'copy'])
        
        # Output
        cmd.append('-y')
        cmd.append(str(settings.output_file))
        
        cmd_string = self._format_command_string(cmd)
        
        return cmd, cmd_string
    
    def _build_transcode_concat_command(
        self,
        settings: ConcatenateSettings,
        analyses: List[VideoAnalysis]
    ) -> Tuple[List[str], str]:
        """Build command for transcode concatenation (normalize and join)."""
        cmd = [self.ffmpeg_path]
        
        # Hardware decoder
        if settings.use_hardware_decoder:
            cmd.extend(self._build_hardware_decoder_args(settings.target_codec, settings.gpu_index))
        
        # Add all input files
        for input_file in settings.input_files:
            cmd.extend(['-i', str(input_file)])
        
        # Determine target specs
        target_width = settings.target_width
        target_height = settings.target_height
        target_fps = settings.target_fps
        
        if not target_width or not target_height:
            # Use maximum resolution from inputs
            max_width = max(a.width for a in analyses)
            max_height = max(a.height for a in analyses)
            target_width = target_width or max_width
            target_height = target_height or max_height
        
        if not target_fps:
            # Use most common FPS
            fps_counts = {}
            for a in analyses:
                fps_counts[a.fps] = fps_counts.get(a.fps, 0) + 1
            target_fps = max(fps_counts.items(), key=lambda x: x[1])[0]
        
        # Build filter_complex for normalization and concatenation
        filter_parts = []
        
        for i in range(len(settings.input_files)):
            # Scale and set FPS for each input
            filter_parts.append(
                f"[{i}:v]scale={target_width}:{target_height},"
                f"fps={target_fps},setsar=1[v{i}]"
            )
        
        # Concatenate normalized streams
        concat_inputs = ''.join(f"[v{i}]" for i in range(len(settings.input_files)))
        filter_parts.append(
            f"{concat_inputs}concat=n={len(settings.input_files)}:v=1:a=0[vout]"
        )
        
        filter_complex = ';'.join(filter_parts)
        cmd.extend(['-filter_complex', filter_complex])
        
        # Map output
        cmd.extend(['-map', '[vout]'])
        
        # Video encoding
        cmd.extend(['-c:v', settings.target_codec])
        cmd.extend(['-crf', str(settings.crf)])
        cmd.extend(['-preset', settings.preset])
        cmd.extend(['-pix_fmt', settings.target_pixel_format])
        
        # Audio encoding
        cmd.extend(['-c:a', settings.audio_codec])
        cmd.extend(['-b:a', settings.audio_bitrate])
        cmd.extend(['-ar', str(settings.audio_sample_rate)])
        
        # Output
        cmd.extend(['-f', settings.output_format])
        cmd.append('-y')
        cmd.append(str(settings.output_file))
        
        cmd_string = self._format_command_string(cmd)
        
        return cmd, cmd_string
    
    def _build_hardware_decoder_args(self, codec: str, gpu_index: int = 0) -> List[str]:
        """Build hardware decoder arguments."""
        args = []
        
        if 'nvenc' in codec:
            args.extend(['-hwaccel', 'cuda'])
            args.extend(['-hwaccel_output_format', 'cuda'])
            if gpu_index > 0:
                args.extend(['-hwaccel_device', str(gpu_index)])
        elif 'qsv' in codec:
            args.extend(['-hwaccel', 'qsv'])
        elif 'amf' in codec:
            args.extend(['-hwaccel', 'auto'])
        
        return args
    
    def _build_scale_filter(
        self,
        width: Optional[int],
        height: Optional[int],
        maintain_aspect: bool,
        algorithm: ScalingAlgorithm
    ) -> str:
        """Build scale filter string."""
        # Algorithm mapping
        algo_flags = {
            ScalingAlgorithm.LANCZOS: 'lanczos',
            ScalingAlgorithm.BICUBIC: 'bicubic',
            ScalingAlgorithm.BILINEAR: 'bilinear',
            ScalingAlgorithm.NEIGHBOR: 'neighbor',
            ScalingAlgorithm.SPLINE: 'spline',
        }
        
        algo = algo_flags.get(algorithm, 'lanczos')
        
        if maintain_aspect:
            # Use -1 for the dimension to maintain aspect ratio
            if width and not height:
                return f"scale={width}:-1:flags={algo}"
            elif height and not width:
                return f"scale=-1:{height}:flags={algo}"
            elif width and height:
                # Force exact dimensions but maintain aspect with padding
                return f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags={algo}"
        else:
            # Force exact dimensions
            w = width or -1
            h = height or -1
            return f"scale={w}:{h}:flags={algo}"
    
    def _build_fps_filter(self, target_fps: float, method: FPSMethod) -> str:
        """Build FPS adjustment filter."""
        if method == FPSMethod.DUPLICATE:
            # Duplicate/drop frames to match target FPS
            return f"fps={target_fps}:round=near"
        elif method == FPSMethod.PTS_ADJUST:
            # Adjust PTS to change speed
            return f"setpts=PTS*{target_fps}/TB"
        else:
            # Auto - use duplicate method by default
            return f"fps={target_fps}:round=near"
    
    def _format_command_string(self, cmd: List[str]) -> str:
        """
        Format command array as readable string with line breaks.
        
        Args:
            cmd: Command array
        
        Returns:
            Formatted multi-line command string
        """
        # Use shlex.quote to properly escape arguments
        quoted_parts = [shlex.quote(part) for part in cmd]
        
        # Build multi-line string with continuation characters
        lines = []
        current_line = quoted_parts[0]  # Start with ffmpeg path
        
        for part in quoted_parts[1:]:
            # Add line break before certain flags for readability
            if part.startswith('-') and len(current_line) > 60:
                lines.append(current_line + ' \\')
                current_line = '  ' + part  # Indent continuation
            else:
                current_line += ' ' + part
        
        # Add final line
        lines.append(current_line)
        
        return '\n'.join(lines)
    
    def validate_command(self, cmd: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Validate FFmpeg command structure.

        Args:
            cmd: Command array to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not cmd:
            return False, "Empty command"

        # Accept either ffmpeg or ffmpeg.exe
        if not (cmd[0].endswith('ffmpeg') or cmd[0].endswith('ffmpeg.exe')):
            return False, "Command must start with ffmpeg"

        # Check for at least one input
        if '-i' not in cmd:
            return False, "No input file specified (-i flag missing)"

        # Check for output file (should be last argument)
        if len(cmd) < 3:
            return False, "No output file specified"

        # Flags that intentionally take NO value
        NO_VALUE_FLAGS = {
            '-y', '-n', '-sn', '-vn', '-an', '-dn',
            '-shortest', '-re', '-nostdin', '-hide_banner',
            '-copyts'
        }

        def _is_negative_number(s: str) -> bool:
            """Check if string is a negative number (e.g., '-1', '-0', '-2')."""
            return len(s) > 1 and s[0] == '-' and s[1:].isdigit()

        # Check for orphaned flags
        i = 1
        while i < len(cmd) - 1:  # Skip last item (output file)
            tok = cmd[i]

            if tok.startswith('-'):
                if tok in NO_VALUE_FLAGS:
                    # This flag doesn't need a value
                    i += 1
                    continue

                # Flag needs a value - ensure next token is a value
                if i + 1 >= len(cmd):
                    return False, f"Orphaned flag: {tok} has no value"

                nxt = cmd[i + 1]
                # If next token starts with '-' but is a negative number (e.g., -1), that's a VALUE
                if nxt.startswith('-') and not _is_negative_number(nxt):
                    return False, f"Orphaned flag: {tok} has no value"

                # Skip both the flag and its value
                i += 2
                continue

            i += 1

        return True, None
