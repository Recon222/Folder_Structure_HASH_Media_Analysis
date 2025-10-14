"""
Format mapping module for video container conversions.

This module handles the conversion of proprietary video formats to standard
containers for better compatibility and metadata support, particularly for
forensic video analysis workflows.
"""

import os
from typing import Tuple, Dict, Optional


class FormatMapper:
    """
    Handles video format conversions for better compatibility.

    This class provides mappings from proprietary or problematic video
    containers to standard formats that have better metadata support
    and wider compatibility.
    """

    # Format conversion mapping dictionary
    # Maps proprietary/problematic formats to standard containers
    FORMAT_CONVERSIONS: Dict[str, str] = {
        # Dahua camera formats
        ".dav": ".mp4",  # Dahua proprietary format
        ".dh": ".mp4",  # Older Dahua format
        # Raw H.264/H.265 streams
        ".264": ".mp4",  # Raw H.264 stream
        ".h264": ".mp4",  # Raw H.264 stream
        ".265": ".mp4",  # Raw H.265/HEVC stream
        ".h265": ".mp4",  # Raw H.265/HEVC stream
        ".hevc": ".mp4",  # Raw HEVC stream
        # Other security camera formats
        ".av": ".mp4",  # Some Asian DVR systems
        ".asf": ".mp4",  # Advanced Systems Format (limited metadata support)
        ".dvr": ".mp4",  # Generic DVR format
        ".eye": ".mp4",  # i-Catcher Console format
        ".vvf": ".mp4",  # Video Verification format
        # Formats with poor metadata support
        ".3gp": ".mp4",  # Limited metadata capabilities
        ".3g2": ".mp4",  # Limited metadata capabilities
        # Note: Standard formats like .mp4, .mov, .mkv, .mxf are not included
        # as they already have good metadata support
    }

    @classmethod
    def get_output_format(cls, input_path: str) -> Tuple[str, bool]:
        """
        Determine the output format for a given input file.

        Args:
            input_path: Path to the input file

        Returns:
            Tuple of (output_extension, was_converted)
            - output_extension: The extension to use for output (including dot)
            - was_converted: True if format conversion is recommended
        """
        # Get the file extension
        _, ext = os.path.splitext(input_path)
        ext_lower = ext.lower()

        # Check if conversion is needed
        if ext_lower in cls.FORMAT_CONVERSIONS:
            return cls.FORMAT_CONVERSIONS[ext_lower], True

        # No conversion needed - use original extension
        return ext, False

    @classmethod
    def is_proprietary_format(cls, file_path: str) -> bool:
        """
        Check if a file uses a proprietary format that needs conversion.

        Args:
            file_path: Path to the file to check

        Returns:
            True if the format is proprietary and should be converted
        """
        _, ext = os.path.splitext(file_path)
        return ext.lower() in cls.FORMAT_CONVERSIONS

    @classmethod
    def get_format_info(cls, file_path: str) -> Dict[str, any]:
        """
        Get detailed information about format conversion for a file.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary containing:
            - original_format: Original file extension
            - output_format: Recommended output format
            - needs_conversion: Boolean indicating if conversion is needed
            - reason: Human-readable reason for conversion
        """
        _, ext = os.path.splitext(file_path)
        ext_lower = ext.lower()

        info = {
            "original_format": ext,
            "output_format": ext,
            "needs_conversion": False,
            "reason": "Standard format with good metadata support",
        }

        if ext_lower in cls.FORMAT_CONVERSIONS:
            info["output_format"] = cls.FORMAT_CONVERSIONS[ext_lower]
            info["needs_conversion"] = True

            # Provide specific reasons for common formats
            if ext_lower in [".dav", ".dh"]:
                info["reason"] = "Dahua proprietary format - converting for better compatibility"
            elif ext_lower in [".264", ".h264", ".265", ".h265", ".hevc"]:
                info["reason"] = "Raw video stream - needs container for metadata"
            elif ext_lower in [".asf", ".3gp", ".3g2"]:
                info["reason"] = "Limited metadata support - converting to MP4"
            else:
                info["reason"] = "Proprietary format - converting for better compatibility"

        return info

    @classmethod
    def get_supported_conversions(cls) -> Dict[str, str]:
        """
        Get a copy of all supported format conversions.

        Returns:
            Dictionary mapping source formats to target formats
        """
        return cls.FORMAT_CONVERSIONS.copy()
