"""
FFmpeg Timeline Builder Service

Single-pass FFmpeg command generation for CCTV timelines.
Based on GPT-5's atomic interval approach.

Creates ONE filter_complex command that:
- Normalizes all inputs (PTS-aware fps conversion)
- Generates 5-second slates for gaps
- Creates split-screen layouts for overlaps
- Concatenates everything in-memory
- Encodes once with NVENC

No intermediate files. No multi-pass transcoding. Just one beautiful command.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple, Literal, Union
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import os

from filename_parser.models.timeline_models import VideoMetadata, RenderSettings
from filename_parser.core.binary_manager import binary_manager
from core.logger import logger


# ==================== Data Models ====================

@dataclass
class Clip:
    """Single video clip with timeline position."""
    path: Path
    start: Union[float, str]  # seconds from t0 OR ISO8601 string
    end: Union[float, str]    # seconds from t0 OR ISO8601 string
    cam_id: str


@dataclass
class _NClip:
    """Normalized clip (internal - times as floats)."""
    path: Path
    start: float  # seconds from t0
    end: float
    cam_id: str


@dataclass
class _Interval:
    """Atomic time interval where camera set is constant."""
    t0: float
    t1: float
    active: List[_NClip]  # clips active in [t0, t1)


@dataclass
class _SegSlate:
    """Gap segment - 5-second slate."""
    gap_start: float
    gap_end: float
    text: str
    dur: float


@dataclass
class _SegSingle:
    """Single-camera segment."""
    clip: _NClip
    seg_start: float
    seg_end: float


@dataclass
class _SegOverlap2:
    """Two-camera overlap segment."""
    clip_a: _NClip
    clip_b: _NClip
    seg_start: float
    seg_end: float


_Segment = Union[_SegSlate, _SegSingle, _SegOverlap2]


# ==================== Main Builder Class ====================

class FFmpegTimelineBuilder:
    """
    Build single-pass FFmpeg commands for CCTV timelines.

    Implements GPT-5's atomic interval algorithm for perfect timeline construction.
    """

    def __init__(self):
        self.logger = logger

        # Windows CreateProcess argv limit
        self.WINDOWS_ARGV_LIMIT = 32768
        self.SAFE_ARGV_THRESHOLD = 29000  # 90% of limit for safety buffer

    def estimate_argv_length(
        self,
        clips: List[Clip],
        settings: RenderSettings,
        with_hwaccel: bool = False
    ) -> int:
        """
        Estimate total argv length before building command.

        Args:
            clips: List of video clips
            settings: Render settings
            with_hwaccel: Include hardware decode flags in estimate

        Returns:
            Estimated command line length in characters
        """
        # Normalize clips to get actual segments
        norm_clips = self._normalize_clip_times(clips, timeline_is_absolute=True)
        intervals = self._build_atomic_intervals(norm_clips)
        segments = self._segments_from_intervals(intervals, settings)

        # Base command overhead
        ffmpeg_path_len = len(str(binary_manager.get_ffmpeg_path() or "ffmpeg"))
        base_args = ffmpeg_path_len + 50  # -y, -filter_complex_script, etc.

        # Encoding options overhead
        encoding_args = 150  # NVENC settings

        # Per-input overhead
        inputs_count = 0
        total_path_length = 0

        for seg in segments:
            if isinstance(seg, _SegSlate):
                # Slates generate in filtergraph - no argv impact
                continue
            elif isinstance(seg, _SegSingle):
                inputs_count += 1
                total_path_length += len(str(seg.clip.path))
            elif isinstance(seg, _SegOverlap2):
                inputs_count += 2
                total_path_length += len(str(seg.clip_a.path)) + len(str(seg.clip_b.path))

        # Calculate per-input flag overhead
        if with_hwaccel:
            # -hwaccel cuda -hwaccel_output_format cuda -ss X.XXXXXX -t X.XXXXXX -i <path>
            per_input_flags = len("-hwaccel") + 1 + len("cuda") + 1  # 15
            per_input_flags += len("-hwaccel_output_format") + 1 + len("cuda") + 1  # 30
            per_input_flags += len("-ss") + 1 + 10 + 1  # 14
            per_input_flags += len("-t") + 1 + 10 + 1  # 13
            per_input_flags += len("-i") + 1  # 3
            # Total: ~75 chars per input (not including path)
            flags_overhead = inputs_count * 75
        else:
            # -ss X.XXXXXX -t X.XXXXXX -i <path>
            per_input_flags = len("-ss") + 1 + 10 + 1  # 14
            per_input_flags += len("-t") + 1 + 10 + 1  # 13
            per_input_flags += len("-i") + 1  # 3
            # Total: ~30 chars per input (not including path)
            flags_overhead = inputs_count * 30

        # Total estimate
        estimated_length = (
            base_args +
            flags_overhead +
            total_path_length +
            encoding_args +
            (inputs_count * 2)  # Spaces between args
        )

        self.logger.debug(
            f"Argv estimate: {inputs_count} inputs, {estimated_length} chars "
            f"(hwaccel={with_hwaccel})"
        )

        return estimated_length

    def build_command(
        self,
        clips: List[Clip],
        settings: RenderSettings,
        output_path: Path,
        timeline_is_absolute: bool = True
    ) -> Tuple[List[str], str]:
        """
        Build complete FFmpeg command for timeline rendering.

        Args:
            clips: List of video clips with start/end times
            settings: Render settings (resolution, fps, codec, etc.)
            output_path: Where to save the output video
            timeline_is_absolute: True if times are ISO8601, False if relative seconds

        Returns:
            Tuple of (argv list, filter_script_path)
            - argv: FFmpeg command ready for subprocess (uses -filter_complex_script)
            - filter_script_path: Path to temp file containing filtergraph (caller must clean up)
        """
        if not clips:
            raise ValueError("No clips provided for timeline")

        # Step 1: Normalize clip times to seconds from t0
        norm_clips = self._normalize_clip_times(clips, timeline_is_absolute)

        # Step 2: Build atomic intervals
        intervals = self._build_atomic_intervals(norm_clips)

        # Step 3: Create segments from intervals
        segments = self._segments_from_intervals(intervals, settings)

        # Step 4: Emit FFmpeg command (returns argv and filter script path)
        argv, filter_script_path = self._emit_ffmpeg_argv(segments, settings, output_path)

        return argv, filter_script_path

    # ==================== Time Normalization ====================

    def _normalize_clip_times(self, clips: List[Clip], absolute: bool) -> List[_NClip]:
        """
        Convert clip times to seconds from t0.

        Accepts float seconds or ISO8601 strings.
        If absolute=True, rebases all times to earliest start = 0.
        """
        parsed = []

        def to_sec(x: Union[float, str]) -> float:
            if isinstance(x, (int, float)):
                return float(x)
            try:
                return datetime.fromisoformat(x).timestamp()
            except Exception:
                raise ValueError(f"Unsupported time format: {x}")

        for c in clips:
            s = to_sec(c.start)
            e = to_sec(c.end)
            if e <= s:
                continue  # Skip invalid clips
            parsed.append((c.path, s, e, c.cam_id))

        if not parsed:
            return []

        if absolute:
            # Rebase to earliest start = 0
            t0 = min(s for _, s, _, _ in parsed)
            norm = [_NClip(p, s - t0, e - t0, cam) for p, s, e, cam in parsed]
        else:
            norm = [_NClip(p, s, e, cam) for p, s, e, cam in parsed]

        norm.sort(key=lambda c: (c.start, c.cam_id, str(c.path)))
        return norm

    # ==================== Atomic Interval Algorithm ====================

    def _build_atomic_intervals(self, clips: List[_NClip]) -> List[_Interval]:
        """
        Build atomic intervals using GPT-5's algorithm.

        Collects all time boundaries (clip starts/ends),
        then creates intervals where the active camera set is constant.
        """
        # Collect all unique time points
        bounds = set()
        for c in clips:
            bounds.add(c.start)
            bounds.add(c.end)

        edges = sorted(bounds)

        # Create intervals
        intervals = []
        for i in range(len(edges) - 1):
            a, b = edges[i], edges[i + 1]
            if b <= a:
                continue

            # Find clips active in [a, b)
            active = [c for c in clips if c.start < b and c.end > a]
            intervals.append(_Interval(a, b, active))

        self.logger.info(f"Built {len(intervals)} atomic intervals from {len(clips)} clips")
        return intervals

    # ==================== Segment Creation ====================

    def _segments_from_intervals(
        self,
        intervals: List[_Interval],
        settings: RenderSettings
    ) -> List[_Segment]:
        """
        Convert atomic intervals to renderable segments.

        Merges adjacent intervals with identical camera sets.
        Classifies as: GAP (no cameras), SINGLE (1 camera), OVERLAP (2+ cameras).
        """
        segments: List[_Segment] = []

        def key(active: List[_NClip]):
            """Create unique key for camera set."""
            ordered = sorted(active, key=lambda c: (c.cam_id, str(c.path)))
            return tuple((str(c.path), c.start, c.end) for c in ordered)

        i = 0
        while i < len(intervals):
            a = intervals[i]

            # Merge adjacent intervals with same camera set
            j = i + 1
            while j < len(intervals) and key(intervals[j].active) == key(a.active):
                j += 1

            t0, t1 = a.t0, intervals[j - 1].t1
            active = a.active

            # Classify interval
            if not active:
                # GAP - no cameras
                if settings.slate_duration_seconds > 0:
                    text = f"GAP: {self._fmt_hms(t0)} → {self._fmt_hms(t1)}  (Δ {self._fmt_dur(t1 - t0)})"
                    segments.append(_SegSlate(
                        gap_start=t0,
                        gap_end=t1,
                        text=text,
                        dur=float(settings.slate_duration_seconds)
                    ))

            elif len(active) == 1:
                # SINGLE camera
                segments.append(_SegSingle(
                    clip=active[0],
                    seg_start=t0,
                    seg_end=t1
                ))

            else:
                # OVERLAP - 2+ cameras (take first two for now)
                ordered = sorted(active, key=lambda c: (c.cam_id, str(c.path)))
                segments.append(_SegOverlap2(
                    clip_a=ordered[0],
                    clip_b=ordered[1],
                    seg_start=t0,
                    seg_end=t1
                ))

            i = j

        self.logger.info(
            f"Created {len(segments)} segments: "
            f"{sum(1 for s in segments if isinstance(s, _SegSingle))} single, "
            f"{sum(1 for s in segments if isinstance(s, _SegOverlap2))} overlap, "
            f"{sum(1 for s in segments if isinstance(s, _SegSlate))} gap"
        )

        return segments

    # ==================== FFmpeg Command Generation ====================

    def _emit_ffmpeg_argv(
        self,
        segments: List[_Segment],
        settings: RenderSettings,
        output_path: Path
    ) -> Tuple[List[str], str]:
        """
        Generate complete FFmpeg command with filter_complex_script.

        Phase 1 + Phase 2 optimizations:
        - Writes filter_complex to temp file (bypasses Windows argv limit)
        - Generates slates inside filtergraph (not as lavfi inputs)
        - Only real video files added as -i inputs

        Returns:
            Tuple of (argv, filter_script_path)
        """
        ffmpeg = binary_manager.get_ffmpeg_path()
        if not ffmpeg:
            raise RuntimeError("FFmpeg not available")

        argv = [ffmpeg, "-y"]

        # Compute pane geometry for overlaps
        if settings.split_mode == "side_by_side":
            pane_w, pane_h = settings.output_resolution[0] // 2, settings.output_resolution[1]
        else:  # stacked
            pane_w, pane_h = settings.output_resolution[0], settings.output_resolution[1] // 2

        # Build inputs and filter chains
        filter_lines = []
        next_in_idx = 0  # Track ONLY real video inputs
        seg_count = 0

        for seg in segments:
            if isinstance(seg, _SegSlate):
                # PHASE 2: Generate slate INSIDE filtergraph (not as lavfi input)
                esc_text = self._escape_drawtext(seg.text)
                fontsize = max(24, int(0.028 * settings.output_resolution[1]))
                w, h = settings.output_resolution
                fps = settings.output_fps
                dur = seg.dur

                # Create color source + drawtext in filtergraph
                filter_lines.append(
                    f"color=size={w}x{h}:rate={fps}:duration={dur} [sl{seg_count}]"
                )
                filter_lines.append(
                    f"[sl{seg_count}] drawtext=text='{esc_text}':x=(w-tw)/2:y=(h-th)/2:"
                    f"fontsize={fontsize}:fontcolor=white:box=1:boxcolor=black@0.5 [s{seg_count}]"
                )

                # No next_in_idx increment - slate is generated, not an input!
                seg_count += 1

            elif isinstance(seg, _SegSingle):
                # Single camera input - Add to argv as real -i input
                dur = seg.seg_end - seg.seg_start
                ss = max(0.0, seg.seg_start - seg.clip.start)

                # Add hardware decode flags if enabled
                if settings.use_hardware_decode:
                    argv += ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]

                # Add real video file to inputs
                argv += ["-ss", f"{ss:.6f}", "-t", f"{dur:.6f}", "-i", str(seg.clip.path)]

                # Normalize with PTS-aware fps conversion (GPT-5 best practice)
                v_in = f"[{next_in_idx}:v]"
                v_out = f"[s{seg_count}]"
                w, h = settings.output_resolution
                fps = settings.output_fps

                filter_lines.append(
                    f"{v_in} "
                    f"settb=AVTB,setpts=PTS-STARTPTS,"
                    f"fps={fps}:round=near,"
                    f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                    f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
                    f"setsar=1,format=yuv420p "
                    f"{v_out}"
                )

                next_in_idx += 1
                seg_count += 1

            else:  # _SegOverlap2
                # Two-camera overlap - Add both inputs to argv
                dur = seg.seg_end - seg.seg_start
                ss_a = max(0.0, seg.seg_start - seg.clip_a.start)
                ss_b = max(0.0, seg.seg_start - seg.clip_b.start)

                # Add hardware decode flags if enabled (for first input)
                if settings.use_hardware_decode:
                    argv += ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]

                # Add both real video files to inputs
                argv += ["-ss", f"{ss_a:.6f}", "-t", f"{dur:.6f}", "-i", str(seg.clip_a.path)]
                idx_a = next_in_idx
                next_in_idx += 1

                # Add hardware decode flags if enabled (for second input)
                if settings.use_hardware_decode:
                    argv += ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]

                argv += ["-ss", f"{ss_b:.6f}", "-t", f"{dur:.6f}", "-i", str(seg.clip_b.path)]
                idx_b = next_in_idx
                next_in_idx += 1

                # Normalize each to pane size
                va_in = f"[{idx_a}:v]"
                vb_in = f"[{idx_b}:v]"
                va_p = f"[p{seg_count}a]"
                vb_p = f"[p{seg_count}b]"
                v_out = f"[s{seg_count}]"
                fps = settings.output_fps

                # Get alignment padding
                x_pad, y_pad = self._get_alignment_padding(settings, pane_w, pane_h)

                # Normalize pane A
                filter_lines.append(
                    f"{va_in} "
                    f"settb=AVTB,setpts=PTS-STARTPTS,"
                    f"fps={fps}:round=near,"
                    f"scale={pane_w}:{pane_h}:force_original_aspect_ratio=decrease,"
                    f"pad={pane_w}:{pane_h}:{x_pad}:{y_pad}:color=black,"
                    f"setsar=1,format=yuv420p "
                    f"{va_p}"
                )

                # Normalize pane B
                filter_lines.append(
                    f"{vb_in} "
                    f"settb=AVTB,setpts=PTS-STARTPTS,"
                    f"fps={fps}:round=near,"
                    f"scale={pane_w}:{pane_h}:force_original_aspect_ratio=decrease,"
                    f"pad={pane_w}:{pane_h}:{x_pad}:{y_pad}:color=black,"
                    f"setsar=1,format=yuv420p "
                    f"{vb_p}"
                )

                # Stack panes
                if settings.split_mode == "side_by_side":
                    layout = "0_0|w0_0"  # Left | Right
                else:
                    layout = "0_0|0_h0"  # Top / Bottom

                filter_lines.append(
                    f"{va_p}{vb_p} xstack=inputs=2:layout={layout}:fill=black {v_out}"
                )

                seg_count += 1

        # Concat all segments
        concat_inputs = "".join(f"[s{i}]" for i in range(seg_count))
        filter_lines.append(
            f"{concat_inputs} concat=n={seg_count}:v=1:a=0 [vout]"
        )

        # PHASE 1: Write filter_complex to temp file instead of command line
        filter_text = "; ".join(filter_lines)

        fd, filter_script_path = tempfile.mkstemp(suffix=".fffilter", text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(filter_text)

            self.logger.info(f"Filter script written to: {filter_script_path}")
            self.logger.debug(f"Filter script length: {len(filter_text)} chars")

        except Exception as e:
            # Clean up on error
            try:
                os.unlink(filter_script_path)
            except:
                pass
            raise RuntimeError(f"Failed to write filter script: {e}")

        # Use -filter_complex_script instead of -filter_complex
        argv += ["-filter_complex_script", filter_script_path]
        argv += ["-map", "[vout]"]
        argv += ["-vsync", "0"]  # GPT-5 recommendation: avoid muxer "help"

        # Audio (drop for CCTV)
        argv += ["-an"]

        # Encoder settings (NVENC)
        argv += [
            "-c:v", settings.output_codec,
            "-preset", "p5",
            "-cq", "20",
            "-rc", "vbr_hq",
            "-b:v", "0",
            "-g", str(max(1, settings.output_fps * 2)),  # 2-second GOPs
            "-bf", "2",
            "-spatial-aq", "1",
            "-temporal-aq", "1"
        ]

        # Output file
        argv += [str(output_path)]

        return argv, filter_script_path

    # ==================== Helper Methods ====================

    def _get_alignment_padding(
        self,
        settings: RenderSettings,
        pane_w: int,
        pane_h: int
    ) -> Tuple[str, str]:
        """Get x,y padding expressions for pane alignment."""
        if settings.split_mode == "side_by_side":
            # Vertical alignment
            if settings.split_alignment == "top":
                return ("(ow-iw)/2", "0")
            elif settings.split_alignment == "bottom":
                return ("(ow-iw)/2", "oh-ih")
            else:  # center
                return ("(ow-iw)/2", "(oh-ih)/2")
        else:
            # Horizontal alignment (stacked)
            if settings.split_alignment == "left":
                return ("0", "(oh-ih)/2")
            elif settings.split_alignment == "right":
                return ("ow-iw", "(oh-ih)/2")
            else:  # center
                return ("(ow-iw)/2", "(oh-ih)/2")

    def _fmt_hms(self, t: float) -> str:
        """Format seconds as HH:MM:SS."""
        t = max(0, int(round(t)))
        h = t // 3600
        m = (t % 3600) // 60
        s = t % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _fmt_dur(self, d: float) -> str:
        """Format duration as human-readable (1h 2m 3s)."""
        d = max(0, int(round(d)))
        h = d // 3600
        m = (d % 3600) // 60
        s = d % 60
        parts = []
        if h: parts.append(f"{h}h")
        if m or (h and s): parts.append(f"{m}m")
        parts.append(f"{s}s")
        return " ".join(parts)

    def _escape_drawtext(self, s: str) -> str:
        """Escape text for FFmpeg drawtext filter."""
        return (s.replace('\\', '\\\\')
                .replace(':', '\\:')
                .replace(',', '\\,')
                .replace('=', '\\=')
                .replace("'", "\\'"))
