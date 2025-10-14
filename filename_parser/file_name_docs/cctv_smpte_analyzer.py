#!/usr/bin/env python3
"""
CCTV SMPTE Timecode Analyzer - Meta-Algorithm
==============================================

Frame-accurate SMPTE timecode calculator for CCTV forensic analysis.
Combines filename timestamp parsing with FFprobe metadata analysis to calculate
precise sub-second frame offsets without OCR dependency.

Author: Meta-algorithm combining GPT and Perplexity approaches
Purpose: Multi-source CCTV timeline synchronization
License: MIT
"""

import subprocess
import json
import re
import datetime
from typing import List, Dict, Tuple, Optional


class CCTVSMPTEAnalyzer:
    """
    Frame-accurate SMPTE timecode calculator for CCTV forensic analysis.
    
    Calculates precise SMPTE timecodes for CCTV footage by combining filename timestamps
    with FFprobe metadata analysis. Eliminates OCR dependency through mathematical
    calculation of sub-second frame offsets.
    
    Key Features:
    - PTS-based sub-second offset calculation
    - GOP structure consistency validation with pattern visualization
    - Frame-accurate timing anomaly detection (2% threshold)
    - Statistical frame rate analysis with variance calculation
    - Comprehensive reliability scoring for quality assurance
    - Start and end timecode calculation for timeline assembly
    
    Use Case:
    Multi-source CCTV timeline synchronization requiring frame-accurate alignment
    across cameras with different recording start points within the same second.
    
    Example:
        analyzer = CCTVSMPTEAnalyzer()
        result = analyzer.analyze_video("Cam1_20251009_142300.mp4")
        
        if "error" not in result:
            print(f"Start: {result['start_timecode']}")
            print(f"Offset: {result['start_offset_frames']} frames")
            print(f"End: {result['end_timecode']}")
            print(f"Reliability: {result['reliability_score']}/100")
    """
    
    def __init__(self, ffprobe_path: str = "ffprobe"):
        """
        Initialize the CCTV SMPTE analyzer.
        
        Args:
            ffprobe_path: Path to ffprobe executable (default: "ffprobe" from PATH)
        """
        self.ffprobe_path = ffprobe_path
    
    def parse_start_time(self, filename: str) -> datetime.datetime:
        """
        Parse DVR filename for recording start timestamp.
        
        Supports multiple DVR/NVR filename formats including:
        - YYYYMMDD_HHMMSS (Dahua, Reolink, generic)
        - YYYY-MM-DD_HH-MM-SS (structured formats)
        - YYYYMMDDHHMMSS (compact format)
        - YYYY-MM-DD HH:MM:SS (natural format with various separators)
        
        Args:
            filename: Video filename containing embedded timestamp
            
        Returns:
            datetime.datetime object representing recording start time (to the second)
            
        Raises:
            ValueError: If no valid timestamp pattern found in filename
            
        Example:
            >>> analyzer.parse_start_time("Cam1_20251009_142300.mp4")
            datetime.datetime(2025, 10, 9, 14, 23, 0)
        """
        patterns = [
            (r'(\d{8})_(\d{6})', "%Y%m%d_%H%M%S"),
            (r'(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})', "%Y-%m-%d_%H-%M-%S"),
            (r'(\d{14})', "%Y%m%d%H%M%S"),
            (r'(\d{4}-\d{2}-\d{2})[ _](\d{2}[:\-]\d{2}[:\-]\d{2})', "%Y-%m-%d %H:%M:%S")
        ]
        
        for regex, datefmt in patterns:
            match = re.search(regex, filename)
            if match:
                ts_str = match.group(0)
                # Normalize separators: underscore→space, hyphen→colon
                ts_str_norm = ts_str.replace('_', ' ').replace('-', ':')
                try:
                    return datetime.datetime.strptime(ts_str_norm, datefmt)
                except ValueError:
                    continue
        
        raise ValueError(f"Could not parse timestamp from filename: {filename}")
    
    def extract_video_metadata(self, video_path: str, frame_limit: int = 100) -> Dict:
        """
        Extract video metadata using FFprobe.
        
        Retrieves both stream-level metadata (codec, frame rate, duration) and
        frame-level data (PTS, frame types) for the first N frames.
        
        Args:
            video_path: Path to video file
            frame_limit: Number of frames to analyze (default: 100)
            
        Returns:
            Dict containing:
                - 'stream_info': Stream metadata (codec, frame rate, duration)
                - 'frames': List of frame metadata (PTS, type, key frame flag)
                - 'error': Error message if extraction failed
                
        Note:
            100 frames is typically sufficient for GOP pattern analysis and
            timing calculations while maintaining performance.
        """
        try:
            # Extract stream-level metadata
            stream_cmd = [
                self.ffprobe_path, "-v", "error", "-select_streams", "v:0",
                "-show_streams", "-of", "json", video_path
            ]
            stream_result = subprocess.run(
                stream_cmd, text=True, capture_output=True, check=True
            )
            streams = json.loads(stream_result.stdout).get("streams", [])
            stream_info = streams[0] if streams else {}
            
            # Extract frame-level metadata for first N frames
            frame_cmd = [
                self.ffprobe_path, "-v", "error", "-select_streams", "v:0",
                "-show_frames", "-of", "json", 
                "-read_intervals", f"%+{frame_limit}", video_path
            ]
            frame_result = subprocess.run(
                frame_cmd, text=True, capture_output=True, check=True
            )
            frames = json.loads(frame_result.stdout).get("frames", [])
            
            return {
                "stream_info": stream_info,
                "frames": frames
            }
            
        except subprocess.CalledProcessError as e:
            return {"error": f"FFprobe execution failed: {e.stderr}"}
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse FFprobe JSON output: {e}"}
        except Exception as e:
            return {"error": f"Metadata extraction error: {e}"}
    
    def calculate_frame_rate(self, frames: List[Dict]) -> Tuple[Optional[float], bool, Optional[float]]:
        """
        Calculate frame rate from PTS intervals with variance analysis.
        
        Computes average frame rate from presentation timestamp intervals and
        detects variable frame rate conditions through variance calculation.
        
        Args:
            frames: List of frame metadata dictionaries with 'pkt_pts_time' field
            
        Returns:
            Tuple of (fps, is_variable_rate, variance):
                - fps: Calculated frames per second (None if insufficient data)
                - is_variable_rate: True if significant frame rate variance detected
                - variance: Statistical variance of frame intervals (None if insufficient data)
                
        Note:
            - Requires minimum 2 frames for calculation
            - Uses first 50 frames for statistical analysis
            - VFR threshold: variance > 0.001 * average_interval
        """
        if len(frames) < 2:
            return None, True, None
        
        # Extract PTS intervals from consecutive frames
        intervals = []
        for i in range(1, min(len(frames), 50)):
            try:
                t_prev = float(frames[i-1].get("pkt_pts_time", 0))
                t_curr = float(frames[i].get("pkt_pts_time", 0))
                delta = t_curr - t_prev
                if delta > 0:
                    intervals.append(delta)
            except (ValueError, TypeError):
                continue
        
        if not intervals:
            return None, True, None
        
        # Calculate average interval and FPS
        avg_interval = sum(intervals) / len(intervals)
        fps = 1.0 / avg_interval if avg_interval > 0 else None
        
        # Calculate variance to detect VFR
        variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
        
        # VFR detection: variance exceeds 0.1% of average interval
        is_variable = variance > (0.001 * avg_interval)
        
        return fps, is_variable, variance
    
    def analyze_gop_structure(self, frames: List[Dict]) -> Dict:
        """
        Analyze GOP (Group of Pictures) structure with pattern visualization.
        
        Examines frame types and keyframe positions to assess GOP consistency
        and create visual pattern representation.
        
        Args:
            frames: List of frame metadata dictionaries
            
        Returns:
            Dict containing:
                - 'first_frame_type': Picture type of first frame (I/P/B)
                - 'first_frame_key': Boolean indicating if first frame is keyframe
                - 'i_frame_indices': List of keyframe positions
                - 'gop_lengths': List of frame counts between consecutive keyframes
                - 'gop_consistent': Boolean indicating uniform GOP lengths
                - 'gop_pattern': Visual string representation (e.g., "IPPPPPPPPPPP")
                - 'average_gop_length': Mean GOP size in frames
                - 'total_i_frames': Total keyframes detected
                
        Note:
            Consistent GOP structure indicates professional encoding without
            re-editing or manipulation.
        """
        if not frames:
            return {
                "first_frame_type": None,
                "first_frame_key": False,
                "i_frame_indices": [],
                "gop_lengths": [],
                "gop_consistent": True,
                "gop_pattern": "",
                "average_gop_length": 0,
                "total_i_frames": 0
            }
        
        first_frame = frames[0]
        first_is_key = (first_frame.get("key_frame") == 1)
        first_type = first_frame.get("pict_type", None)
        
        # Identify I-frame (keyframe) positions
        i_frame_indices = []
        for idx, frame in enumerate(frames):
            if frame.get("pict_type") == "I" and frame.get("key_frame") == 1:
                i_frame_indices.append(idx)
        
        # Calculate GOP lengths (frame counts between keyframes)
        gop_lengths = []
        for j in range(1, len(i_frame_indices)):
            gop_lengths.append(i_frame_indices[j] - i_frame_indices[j-1])
        
        # Check GOP consistency (all lengths identical)
        gop_consistent = (len(set(gop_lengths)) <= 1) if gop_lengths else True
        
        # Create GOP pattern visualization (first 50 frames)
        gop_pattern = "".join([
            frame.get("pict_type", "?") for frame in frames[:50]
        ])
        if len(frames) > 50:
            gop_pattern += "..."
        
        # Calculate average GOP length
        avg_gop = sum(gop_lengths) / len(gop_lengths) if gop_lengths else 0
        
        return {
            "first_frame_type": first_type,
            "first_frame_key": first_is_key,
            "i_frame_indices": i_frame_indices,
            "gop_lengths": gop_lengths,
            "gop_consistent": gop_consistent,
            "gop_pattern": gop_pattern,
            "average_gop_length": round(avg_gop, 2),
            "total_i_frames": len(i_frame_indices)
        }
    
    def detect_timing_anomalies(
        self, 
        frames: List[Dict], 
        fps: float, 
        threshold: float = 0.02
    ) -> List[str]:
        """
        Detect frame timing irregularities through interval analysis.
        
        Examines PTS intervals between consecutive frames to identify dropped
        frames, timing glitches, or encoding anomalies.
        
        Args:
            frames: List of frame metadata dictionaries with PTS data
            fps: Expected frames per second
            threshold: Acceptable deviation as fraction of expected interval (default: 0.02 = 2%)
            
        Returns:
            List of anomaly descriptions with specific frame positions and measurements
            
        Example:
            ["Timing irregularity between frames 15-16: interval=0.067s (expected 0.033s)"]
            
        Note:
            2% threshold allows for normal jitter while catching dropped frames
            and significant timing issues.
        """
        anomalies = []
        
        # Extract PTS values
        pts_list = []
        for frame in frames:
            pts = frame.get("pkt_pts_time")
            if pts is not None:
                try:
                    pts_list.append(float(pts))
                except (ValueError, TypeError):
                    continue
        
        if len(pts_list) < 2:
            return anomalies
        
        # Expected frame duration
        expected_duration = 1.0 / fps
        
        # Check each interval
        for i in range(1, len(pts_list)):
            interval = pts_list[i] - pts_list[i-1]
            deviation = abs(interval - expected_duration)
            
            if deviation > (expected_duration * threshold):
                anomalies.append(
                    f"Timing irregularity between frames {i-1}-{i}: "
                    f"interval={interval:.6f}s (expected {expected_duration:.6f}s, "
                    f"deviation={deviation:.6f}s)"
                )
        
        return anomalies
    
    def compute_timecodes(
        self, 
        start_dt: datetime.datetime, 
        pts_offset: float, 
        fps: float
    ) -> Tuple[str, float, float]:
        """
        Compute SMPTE timecode from datetime and PTS offset.
        
        Calculates frame-accurate SMPTE timecode by combining base timestamp
        (to the second) with sub-second PTS offset.
        
        Args:
            start_dt: Base datetime from filename (accurate to second)
            pts_offset: Sub-second offset in seconds from first frame PTS
            fps: Frames per second for frame number calculation
            
        Returns:
            Tuple of (timecode_str, offset_seconds, offset_frames):
                - timecode_str: SMPTE formatted timecode (HH:MM:SS:FF)
                - offset_seconds: Sub-second offset as float
                - offset_frames: Number of frames into the current second
                
        Example:
            >>> compute_timecodes(datetime(2025,10,9,14,23,0), 0.333333, 30.0)
            ("14:23:00:10", 0.333333, 10.0)
            
        Note:
            Uses non-drop-frame format only (colon separator).
            Handles frame wrapping at second boundaries.
        """
        # Convert datetime to total seconds since midnight
        base_seconds = (
            start_dt.hour * 3600 + 
            start_dt.minute * 60 + 
            start_dt.second
        )
        
        # Add PTS offset for precise time
        precise_start = base_seconds + pts_offset
        
        # Extract SMPTE components
        hours = int(precise_start // 3600) % 24
        minutes = int((precise_start % 3600) // 60)
        seconds = int(precise_start % 60)
        
        # Calculate frame number within current second
        fractional = precise_start - int(precise_start)
        frame_number = int(round(fractional * fps))
        
        # Handle frame wrapping (e.g., frame 30 at 30fps wraps to next second)
        if frame_number >= int(round(fps)):
            frame_number = 0
            seconds += 1
            if seconds >= 60:
                seconds = 0
                minutes += 1
                if minutes >= 60:
                    minutes = 0
                    hours = (hours + 1) % 24
        
        # Format SMPTE timecode (non-drop-frame only)
        timecode = f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frame_number:02d}"
        
        # Calculate offset metrics
        offset_seconds = pts_offset
        offset_frames = pts_offset * fps
        
        return timecode, offset_seconds, offset_frames
    
    def calculate_reliability_score(
        self,
        gop_data: Dict,
        is_vfr: bool,
        anomalies: List[str],
        first_frame_is_key: bool
    ) -> Tuple[int, List[str], bool]:
        """
        Calculate reliability score for timecode calculation confidence.
        
        Assesses four factors to determine overall reliability:
        1. GOP Start (closed vs open)
        2. Frame Rate Consistency (constant vs variable)
        3. GOP Structure Consistency
        4. Data Sufficiency (adequate keyframes)
        
        Args:
            gop_data: GOP analysis results
            is_vfr: Variable frame rate flag
            anomalies: List of detected timing anomalies
            first_frame_is_key: Whether video starts on keyframe
            
        Returns:
            Tuple of (score, notes, needs_verification):
                - score: 0-100 reliability score (25 points per factor)
                - notes: List of explanatory notes for score
                - needs_verification: True if additional validation recommended
                
        Scoring:
            100 points: Optimal conditions, high confidence
            75-99 points: Good conditions, normal confidence
            50-74 points: Acceptable conditions, verification recommended
            <50 points: Problematic conditions, verification required
        """
        score = 0
        notes = []
        
        # Factor 1: GOP Start (25 points)
        if first_frame_is_key:
            score += 25
            notes.append("✓ Closed GOP: First frame is keyframe (I-frame)")
        else:
            notes.append("⚠ Open GOP: First frame is not a keyframe")
        
        # Factor 2: Frame Rate Consistency (25 points)
        if not is_vfr:
            score += 25
            notes.append("✓ Constant frame rate detected")
        else:
            notes.append("⚠ Variable frame rate detected")
        
        # Factor 3: GOP Structure Consistency (25 points)
        if gop_data["gop_consistent"]:
            score += 25
            notes.append("✓ Consistent GOP structure")
        else:
            notes.append("⚠ Inconsistent GOP lengths (may indicate editing)")
        
        # Factor 4: Data Sufficiency (25 points)
        keyframe_count = gop_data["total_i_frames"]
        if keyframe_count >= 2:
            score += 25
            notes.append(f"✓ Sufficient keyframes detected ({keyframe_count} I-frames)")
        else:
            notes.append(f"⚠ Limited keyframe data ({keyframe_count} I-frames)")
        
        # Add timing anomaly information
        if anomalies:
            notes.append(f"⚠ {len(anomalies)} timing irregularities detected")
            for anomaly in anomalies[:3]:  # Show first 3 anomalies
                notes.append(f"  - {anomaly}")
            if len(anomalies) > 3:
                notes.append(f"  - ... and {len(anomalies) - 3} more")
        
        # Determine if verification needed
        needs_verification = (
            score < 100 and 
            (not first_frame_is_key or is_vfr or len(anomalies) > 0)
        )
        
        return score, notes, needs_verification
    
    def analyze_video(self, video_path: str) -> Dict:
        """
        Main analysis method: Calculate frame-accurate SMPTE timecodes.
        
        Performs complete analysis workflow:
        1. Parse filename timestamp
        2. Extract video metadata with FFprobe
        3. Calculate precise frame rate with variance
        4. Analyze GOP structure and patterns
        5. Detect timing anomalies
        6. Calculate start and end SMPTE timecodes
        7. Assess reliability and quality
        
        Args:
            video_path: Path to video file (filename must contain timestamp)
            
        Returns:
            Dict containing comprehensive analysis results or error information
            
        Success Result:
            {
                "filename": "Cam1_20251009_142300.mp4",
                "video_path": "/path/to/Cam1_20251009_142300.mp4",
                "start_timestamp": "2025-10-09 14:23:00",
                "start_timecode": "14:23:00:10",
                "start_offset_seconds": 0.333333,
                "start_offset_frames": 10.0,
                "end_timecode": "14:23:30:15",
                "duration_seconds": 30.5,
                "frame_rate": 30.0,
                "frame_rate_variance": 0.00001,
                "variable_frame_rate": false,
                "first_frame_type": "I",
                "first_frame_is_keyframe": true,
                "open_gop": false,
                "gop_consistent": true,
                "gop_pattern": "IPPPPPPPPPPPIPPPPPPPPPPP...",
                "average_gop_length": 12.0,
                "first_keyframe_timecode": "14:23:00:10",
                "first_keyframe_offset_seconds": 0.333333,
                "timing_anomalies": [],
                "reliability_score": 100,
                "reliability_notes": ["✓ Closed GOP...", "✓ Constant frame rate..."],
                "needs_verification": false
            }
            
        Error Result:
            {
                "filename": "Cam1_20251009_142300.mp4",
                "video_path": "/path/to/Cam1_20251009_142300.mp4",
                "error": "Error description"
            }
        """
        filename = video_path.split("/")[-1]
        result: Dict = {
            "filename": filename,
            "video_path": video_path
        }
        
        # Step 1: Parse start time from filename
        try:
            start_dt = self.parse_start_time(filename)
            result["start_timestamp"] = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            result["error"] = f"Filename timestamp parse error: {e}"
            return result
        
        # Step 2: Extract video metadata
        metadata = self.extract_video_metadata(video_path)
        if "error" in metadata:
            result["error"] = metadata["error"]
            return result
        
        frames = metadata.get("frames", [])
        stream_info = metadata.get("stream_info", {})
        
        if not frames:
            result["error"] = "No frame data found (video may be empty or corrupted)"
            return result
        
        # Step 3: Determine frame rate with variance analysis
        calc_fps, is_vfr, variance = self.calculate_frame_rate(frames)
        fps = calc_fps
        
        # Fallback to stream metadata if calculation fails
        if not fps:
            for key in ("r_frame_rate", "avg_frame_rate"):
                val = stream_info.get(key)
                if val and "/" in val:
                    try:
                        num, den = map(int, val.split("/"))
                        if den != 0:
                            fps = num / den
                            is_vfr = False
                            variance = None
                            break
                    except (ValueError, ZeroDivisionError):
                        continue
        
        if not fps or fps <= 0:
            result["error"] = "Could not determine frame rate"
            return result
        
        result["frame_rate"] = round(fps, 6)
        result["variable_frame_rate"] = is_vfr
        if variance is not None:
            result["frame_rate_variance"] = round(variance, 8)
        
        # Step 4: Analyze GOP structure
        gop = self.analyze_gop_structure(frames)
        first_type = gop["first_frame_type"]
        first_key = gop["first_frame_key"]
        
        result["first_frame_type"] = first_type
        result["first_frame_is_keyframe"] = first_key
        result["open_gop"] = not first_key
        result["gop_consistent"] = gop["gop_consistent"]
        result["gop_pattern"] = gop["gop_pattern"]
        result["average_gop_length"] = gop["average_gop_length"]
        
        # Step 5: Detect timing anomalies
        anomalies = self.detect_timing_anomalies(frames, fps)
        result["timing_anomalies"] = anomalies
        
        # Step 6: Calculate SMPTE timecodes
        
        # First frame PTS
        first_frame_pts = float(frames[0].get("pkt_pts_time", 0.0))
        
        # Calculate start timecode (first frame in file)
        start_tc, offset_sec, offset_frames = self.compute_timecodes(
            start_dt, first_frame_pts, fps
        )
        result["start_timecode"] = start_tc
        result["start_offset_seconds"] = round(offset_sec, 6)
        result["start_offset_frames"] = round(offset_frames, 2)
        
        # Calculate first keyframe timecode (if different from first frame)
        first_keyframe_pts: Optional[float] = None
        
        if not first_key:
            # Open GOP: Find first keyframe
            for idx in gop["i_frame_indices"]:
                if idx > 0:
                    first_keyframe_pts = float(frames[idx].get("pkt_pts_time", 0.0))
                    break
        else:
            # Closed GOP: First frame is the keyframe
            first_keyframe_pts = first_frame_pts
        
        if first_keyframe_pts is not None:
            key_tc, key_offset_sec, _ = self.compute_timecodes(
                start_dt, first_keyframe_pts, fps
            )
            result["first_keyframe_timecode"] = key_tc
            result["first_keyframe_offset_seconds"] = round(key_offset_sec, 6)
        else:
            result["first_keyframe_timecode"] = None
            result["first_keyframe_offset_seconds"] = None
        
        # Calculate end timecode from duration
        try:
            duration = float(stream_info.get("duration", 0))
        except (ValueError, TypeError):
            duration = 0.0
        
        if duration > 0:
            result["duration_seconds"] = round(duration, 6)
            end_pts = first_frame_pts + duration
            end_tc, _, _ = self.compute_timecodes(start_dt, end_pts, fps)
            result["end_timecode"] = end_tc
        else:
            result["duration_seconds"] = None
            result["end_timecode"] = None
        
        # Step 7: Calculate reliability score
        score, notes, needs_verification = self.calculate_reliability_score(
            gop, is_vfr, anomalies, first_key
        )
        
        result["reliability_score"] = score
        result["reliability_notes"] = notes
        result["needs_verification"] = needs_verification
        
        return result


# Example usage and testing
if __name__ == "__main__":
    """
    Example usage demonstrating the CCTV SMPTE analyzer.
    """
    
    print("="*70)
    print("CCTV SMPTE Timecode Analyzer - Meta-Algorithm")
    print("="*70)
    print()
    
    # Example video file (replace with actual file path)
    video_file = "Cam1_20251009_142300.mp4"
    
    # Initialize analyzer
    analyzer = CCTVSMPTEAnalyzer()
    
    # Perform analysis
    print(f"Analyzing: {video_file}")
    print("-" * 70)
    
    result = analyzer.analyze_video(video_file)
    
    # Display results
    if "error" in result:
        print(f"❌ ERROR: {result['error']}")
    else:
        print(f"✓ File: {result['filename']}")
        print(f"✓ Start timestamp: {result['start_timestamp']}")
        print()
        
        print("TIMECODE INFORMATION:")
        print(f"  Start timecode:  {result['start_timecode']}")
        print(f"  Offset:          {result['start_offset_frames']:.2f} frames "
              f"({result['start_offset_seconds']:.6f} seconds)")
        
        if result.get('end_timecode'):
            print(f"  End timecode:    {result['end_timecode']}")
            print(f"  Duration:        {result['duration_seconds']:.3f} seconds")
        
        if result['open_gop'] and result.get('first_keyframe_timecode'):
            print(f"  First I-frame:   {result['first_keyframe_timecode']} "
                  f"({result['first_keyframe_offset_seconds']:.6f} sec offset)")
        print()
        
        print("TECHNICAL ANALYSIS:")
        print(f"  Frame rate:      {result['frame_rate']:.6f} FPS "
              f"({'VFR' if result['variable_frame_rate'] else 'CFR'})")
        if result.get('frame_rate_variance') is not None:
            print(f"  FPS variance:    {result['frame_rate_variance']:.8f}")
        print(f"  First frame:     {result['first_frame_type']}-frame "
              f"({'keyframe' if result['first_frame_is_keyframe'] else 'non-keyframe'})")
        print(f"  GOP structure:   {'Consistent' if result['gop_consistent'] else 'Inconsistent'} "
              f"(avg: {result['average_gop_length']:.1f} frames)")
        print(f"  GOP pattern:     {result['gop_pattern'][:60]}")
        print()
        
        print(f"RELIABILITY ASSESSMENT: {result['reliability_score']}/100")
        for note in result['reliability_notes']:
            print(f"  {note}")
        
        if result['timing_anomalies']:
            print()
            print("⚠ TIMING ANOMALIES DETECTED:")
            for anomaly in result['timing_anomalies'][:5]:
                print(f"  {anomaly}")
            if len(result['timing_anomalies']) > 5:
                print(f"  ... and {len(result['timing_anomalies']) - 5} more")
        
        if result['needs_verification']:
            print()
            print("⚠ RECOMMENDATION: Manual verification advised")
            print("  Consider reviewing footage for quality assurance")
    
    print()
    print("="*70)
    
    # JSON export example
    print()
    print("JSON OUTPUT:")
    print("-" * 70)
    print(json.dumps(result, indent=2))
