"""
JSON Timeline Export Service

Exports timeline data in GPT-5-compatible format.
Allows users to review, edit, and re-import timeline data.
"""

import json
from pathlib import Path
from typing import List
from datetime import datetime

from filename_parser.models.timeline_models import VideoMetadata
from core.result_types import Result
from core.exceptions import FileOperationError
from core.logger import logger


class JSONTimelineExportService:
    """
    Export timeline data as GPT-5-compatible JSON.

    Provides JSON export/import for human-readable timeline data that matches
    the GPT-5 FFmpeg timeline builder input format.
    """

    def __init__(self):
        """Initialize JSON timeline export service."""
        self.logger = logger

    def export_timeline(
        self,
        videos: List[VideoMetadata],
        output_path: Path
    ) -> Result[None]:
        """
        Export timeline as JSON array of clips.

        Format matches GPT-5 specification:
        [
          {
            "path": "D:\\path\\to\\video.mp4",
            "start": "2025-05-21T13:00:00",
            "end": "2025-05-21T13:00:30",
            "cam_id": "A02"
          },
          ...
        ]

        Args:
            videos: List of video metadata objects
            output_path: Path where JSON file will be saved

        Returns:
            Result indicating success or error
        """
        try:
            clips = []

            for video in videos:
                clip = {
                    "path": str(video.file_path),
                    "start": video.start_time,
                    "end": video.end_time,
                    "cam_id": video.camera_path or "Unknown"
                }
                clips.append(clip)

            # Sort by start time for readability
            clips.sort(key=lambda c: c['start'] if c['start'] else '')

            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Write JSON with nice formatting
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(clips, f, indent=2)

            self.logger.info(f"Timeline JSON exported: {output_path} ({len(clips)} clips)")
            return Result.success(None)

        except Exception as e:
            self.logger.error(f"Failed to export JSON timeline: {e}", exc_info=True)
            return Result.error(
                FileOperationError(
                    f"Failed to export JSON: {e}",
                    user_message="Could not export timeline JSON. Check file permissions.",
                    context={"path": str(output_path), "error": str(e)}
                )
            )

    def import_timeline(self, json_path: Path) -> Result[List[VideoMetadata]]:
        """
        Import timeline from JSON (for advanced users).

        Reads GPT-5-compatible JSON and converts back to VideoMetadata objects.

        Args:
            json_path: Path to JSON file

        Returns:
            Result containing List[VideoMetadata] or error
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                clips = json.load(f)

            if not isinstance(clips, list):
                return Result.error(
                    FileOperationError(
                        "Invalid JSON format: expected array of clips",
                        user_message="JSON file does not contain a valid timeline array.",
                        context={"path": str(json_path)}
                    )
                )

            videos = []
            for i, clip in enumerate(clips):
                # Validate clip structure
                required_fields = ['path', 'start', 'end', 'cam_id']
                missing = [f for f in required_fields if f not in clip]
                if missing:
                    self.logger.warning(
                        f"Clip {i+1} missing fields: {missing}. Skipping."
                    )
                    continue

                # Convert clip to VideoMetadata
                file_path = Path(clip['path'])
                if not file_path.exists():
                    self.logger.warning(
                        f"Clip {i+1}: File not found: {file_path}. Skipping."
                    )
                    continue

                # Create metadata object (basic info only, user can re-parse for full metadata)
                metadata = VideoMetadata(
                    file_path=file_path,
                    filename=file_path.name,
                    smpte_timecode="00:00:00:00",  # Will be populated if re-parsed
                    start_time=clip['start'],
                    end_time=clip['end'],
                    camera_path=clip['cam_id'],
                    frame_rate=30.0,  # Default, will be updated if re-parsed
                    duration_seconds=0.0,  # Will be calculated from start/end
                )

                # Calculate duration from ISO times
                try:
                    start_dt = datetime.fromisoformat(clip['start'])
                    end_dt = datetime.fromisoformat(clip['end'])
                    metadata.duration_seconds = (end_dt - start_dt).total_seconds()
                except Exception as e:
                    self.logger.warning(f"Clip {i+1}: Could not parse times: {e}")

                videos.append(metadata)

            self.logger.info(f"Timeline JSON imported: {json_path} ({len(videos)} clips)")
            return Result.success(videos)

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON format: {e}")
            return Result.error(
                FileOperationError(
                    f"Failed to parse JSON: {e}",
                    user_message="JSON file is malformed or corrupted.",
                    context={"path": str(json_path), "error": str(e)}
                )
            )
        except Exception as e:
            self.logger.error(f"Failed to import JSON timeline: {e}", exc_info=True)
            return Result.error(
                FileOperationError(
                    f"Failed to import JSON: {e}",
                    user_message="Could not import timeline JSON. Check file format.",
                    context={"path": str(json_path), "error": str(e)}
                )
            )
