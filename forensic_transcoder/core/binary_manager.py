"""
Binary manager for FFmpeg and FFprobe executables.

This module provides singleton management for locating, validating,
and caching FFmpeg/FFprobe binary paths across the application.

INDEPENDENT MODULE: No external dependencies - self-contained for plugin architecture.
"""

import os
import platform
import subprocess
from typing import Optional, Tuple
from pathlib import Path


class FFmpegBinaryManager:
    """
    Singleton manager for FFmpeg and FFprobe binary detection.

    Handles platform-specific binary location, validation, and caching
    to avoid repeated filesystem searches.

    Fully independent - no external dependencies on main application.
    """

    _instance: Optional["FFmpegBinaryManager"] = None
    _initialized: bool = False

    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize binary manager (only once)."""
        if not FFmpegBinaryManager._initialized:
            self.ffmpeg_path: Optional[str] = None
            self.ffprobe_path: Optional[str] = None
            self.ffmpeg_version: Optional[str] = None
            self.ffprobe_version: Optional[str] = None
            self._validated: bool = False
            FFmpegBinaryManager._initialized = True

    def find_binaries(self, force_refresh: bool = False) -> Tuple[Optional[str], Optional[str]]:
        """
        Locate FFmpeg and FFprobe binaries.

        Args:
            force_refresh: If True, bypass cache and re-search for binaries

        Returns:
            Tuple of (ffmpeg_path, ffprobe_path), None if not found
        """
        if not force_refresh and self._validated:
            return self.ffmpeg_path, self.ffprobe_path

        # Search for binaries
        self.ffmpeg_path = self._find_binary("ffmpeg")
        self.ffprobe_path = self._find_binary("ffprobe")

        if self.ffmpeg_path:
            self.ffmpeg_version = self._get_version(self.ffmpeg_path)

        if self.ffprobe_path:
            self.ffprobe_version = self._get_version(self.ffprobe_path)

        self._validated = True
        return self.ffmpeg_path, self.ffprobe_path

    def get_ffmpeg_path(self) -> Optional[str]:
        """Get FFmpeg binary path (cached)."""
        if not self._validated:
            self.find_binaries()
        return self.ffmpeg_path

    def get_ffprobe_path(self) -> Optional[str]:
        """Get FFprobe binary path (cached)."""
        if not self._validated:
            self.find_binaries()
        return self.ffprobe_path

    def is_ffmpeg_available(self) -> bool:
        """Check if FFmpeg is available."""
        return self.get_ffmpeg_path() is not None

    def is_ffprobe_available(self) -> bool:
        """Check if FFprobe is available."""
        return self.get_ffprobe_path() is not None

    def _find_binary(self, binary_name: str) -> Optional[str]:
        """
        Find a binary in PATH or common locations.

        Args:
            binary_name: Name of binary ('ffmpeg' or 'ffprobe')

        Returns:
            Full path to binary or None if not found
        """
        system = platform.system()

        # Add .exe extension on Windows
        if system == "Windows":
            binary_name = f"{binary_name}.exe"

        # Try local bin/ directory first (project-bundled binaries)
        local_bin_path = self._find_in_local_bin(binary_name)
        if local_bin_path:
            return local_bin_path

        # Try PATH (most common case)
        path_result = self._find_in_path(binary_name)
        if path_result:
            return path_result

        # Try common installation locations
        common_paths = self._get_common_paths(binary_name, system)
        for path in common_paths:
            if os.path.exists(path) and self._test_binary(path):
                return path

        return None

    def _find_in_local_bin(self, binary_name: str) -> Optional[str]:
        """
        Search for binary in project's bin/ directory.

        This allows bundling FFmpeg/FFprobe with the application.
        """
        try:
            # Get project root (3 levels up from this file)
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent

            # Check bin/ directory
            bin_dir = project_root / "bin"
            binary_path = bin_dir / binary_name

            if binary_path.exists() and self._test_binary(str(binary_path)):
                return str(binary_path)
        except Exception:
            pass

        return None

    def _find_in_path(self, binary_name: str) -> Optional[str]:
        """Search for binary in system PATH."""
        system = platform.system()

        try:
            if system == "Windows":
                result = subprocess.run(
                    ["where", binary_name], capture_output=True, text=True, check=False, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    # Return first match
                    return result.stdout.strip().split("\n")[0]
            else:
                result = subprocess.run(
                    ["which", binary_name], capture_output=True, text=True, check=False, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
        except (subprocess.TimeoutExpired, Exception):
            pass

        return None

    def _get_common_paths(self, binary_name: str, system: str) -> list:
        """Get list of common installation paths for binary."""
        if system == "Windows":
            return [
                rf"C:\ffmpeg\bin\{binary_name}",
                rf"C:\Program Files\ffmpeg\bin\{binary_name}",
                rf"C:\Program Files (x86)\ffmpeg\bin\{binary_name}",
                os.path.expanduser(rf"~\ffmpeg\bin\{binary_name}"),
            ]
        elif system == "Darwin":  # macOS
            return [
                f"/usr/local/bin/{binary_name}",
                f"/opt/homebrew/bin/{binary_name}",
                f"/usr/bin/{binary_name}",
                os.path.expanduser(f"~/bin/{binary_name}"),
            ]
        else:  # Linux
            return [
                f"/usr/bin/{binary_name}",
                f"/usr/local/bin/{binary_name}",
                f"/snap/bin/{binary_name}",
                os.path.expanduser(f"~/bin/{binary_name}"),
            ]

    def _test_binary(self, path: str) -> bool:
        """Test if binary exists and is executable."""
        try:
            result = subprocess.run([path, "-version"], capture_output=True, check=False, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, Exception):
            return False

    def _get_version(self, binary_path: str) -> Optional[str]:
        """Extract version string from binary."""
        try:
            result = subprocess.run(
                [binary_path, "-version"], capture_output=True, text=True, check=False, timeout=5
            )
            if result.returncode == 0 and result.stdout:
                # Extract version from first line (e.g., "ffmpeg version 4.4.2")
                first_line = result.stdout.split("\n")[0]
                parts = first_line.split()
                if len(parts) >= 3:
                    return parts[2]
        except (subprocess.TimeoutExpired, Exception):
            pass

        return None


# Global singleton instance
binary_manager = FFmpegBinaryManager()
