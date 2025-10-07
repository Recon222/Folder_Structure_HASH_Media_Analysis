"""
CSV Export Service for exporting timecode extraction results.

This service handles exporting processed file results to CSV format,
including file paths and extracted SMPTE timecodes.
"""

import os
import csv
from typing import List, Dict, Any, Optional
from datetime import datetime


class CSVExportService:
    """
    Service for exporting timecode extraction results to CSV files.

    This service creates CSV files containing file paths and their
    corresponding SMPTE timecodes after batch processing.
    """

    def __init__(self):
        """Initialize the CSV export service."""
        pass

    def export_results(
        self,
        results: List[Dict[str, Any]],
        output_path: Optional[str] = None,
        include_metadata: bool = True,
    ) -> tuple[bool, str]:
        """
        Export processing results to a CSV file.

        Args:
            results: List of result dictionaries containing file paths and timecodes
            output_path: Optional custom output path for CSV file
            include_metadata: Whether to include additional metadata columns

        Returns:
            Tuple of (success: bool, file_path: str) - path to created CSV file
        """
        if not results:
            return False, "No results to export"

        # Generate output path if not provided
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"timecode_export_{timestamp}.csv"

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                return False, f"Failed to create output directory: {str(e)}"

        try:
            with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
                # Define column headers based on include_metadata flag
                if include_metadata:
                    fieldnames = [
                        "source_file_path",
                        "output_file_path",
                        "smpte_timecode",
                        "frame_rate",
                        "pattern_used",
                        "time_offset_applied",
                        "status",
                        "error_message",
                    ]
                else:
                    fieldnames = ["source_file_path", "smpte_timecode"]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()

                # Write each result
                for result in results:
                    # Build row data
                    row = {
                        "source_file_path": result.get("source_file", ""),
                        "smpte_timecode": result.get("smpte_timecode", result.get("timecode", "")),
                    }

                    if include_metadata:
                        row.update(
                            {
                                "output_file_path": result.get("output_file", ""),
                                "frame_rate": result.get("frame_rate", ""),
                                "pattern_used": result.get("pattern_used", result.get("pattern", "")),
                                "time_offset_applied": result.get("time_offset_applied", False),
                                "status": result.get("status", "unknown"),
                                "error_message": result.get("error_message", result.get("error", "")),
                            }
                        )

                    writer.writerow(row)

            return True, output_path

        except Exception as e:
            return False, f"Failed to write CSV file: {str(e)}"

    def export_simple(
        self, file_timecode_pairs: List[tuple[str, str]], output_path: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Export simple file path and timecode pairs to CSV.

        Args:
            file_timecode_pairs: List of (file_path, timecode) tuples
            output_path: Optional custom output path for CSV file

        Returns:
            Tuple of (success: bool, file_path: str)
        """
        # Convert simple pairs to result dictionaries
        results = [
            {"source_file": file_path, "timecode": timecode, "status": "success"}
            for file_path, timecode in file_timecode_pairs
        ]

        return self.export_results(results, output_path, include_metadata=False)

    def append_result(self, csv_path: str, result: Dict[str, Any]) -> bool:
        """
        Append a single result to an existing CSV file.

        Args:
            csv_path: Path to existing CSV file
            result: Result dictionary to append

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if file exists to determine if we need to write header
            file_exists = os.path.exists(csv_path)

            with open(csv_path, "a", newline="", encoding="utf-8") as csvfile:
                fieldnames = [
                    "source_file_path",
                    "output_file_path",
                    "smpte_timecode",
                    "frame_rate",
                    "pattern_used",
                    "time_offset_applied",
                    "status",
                    "error_message",
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction="ignore")

                # Write header if file is new
                if not file_exists:
                    writer.writeheader()

                # Write row
                row = {
                    "source_file_path": result.get("source_file", ""),
                    "output_file_path": result.get("output_file", ""),
                    "smpte_timecode": result.get("smpte_timecode", result.get("timecode", "")),
                    "frame_rate": result.get("frame_rate", ""),
                    "pattern_used": result.get("pattern_used", result.get("pattern", "")),
                    "time_offset_applied": result.get("time_offset_applied", False),
                    "status": result.get("status", "unknown"),
                    "error_message": result.get("error_message", result.get("error", "")),
                }

                writer.writerow(row)

            return True

        except Exception:
            return False
