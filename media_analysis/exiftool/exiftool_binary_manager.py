#!/usr/bin/env python3
"""
ExifTool Binary Manager - Handles ExifTool detection and validation
Follows the pattern established by FFProbeBinaryManager
"""

import subprocess
import platform
from pathlib import Path
from typing import Optional, Dict, Any

from core.logger import logger


class ExifToolBinaryManager:
    """
    Manages ExifTool binary detection and validation
    Inherits patterns from FFProbeBinaryManager for consistency
    """
    
    # Platform-specific binary names
    BINARY_NAMES = {
        'Windows': ['exiftool.exe', 'exiftool.pl'],
        'Darwin': ['exiftool'],
        'Linux': ['exiftool']
    }
    
    # Common installation paths by platform
    SYSTEM_PATHS = {
        'Windows': [
            Path('C:/exiftool'),
            Path('C:/Program Files/exiftool'),
            Path('C:/Program Files (x86)/exiftool'),
        ],
        'Darwin': [
            Path('/usr/local/bin'),
            Path('/opt/homebrew/bin'),
            Path('/usr/bin'),
        ],
        'Linux': [
            Path('/usr/bin'),
            Path('/usr/local/bin'),
            Path('/snap/bin'),
        ]
    }
    
    def __init__(self):
        """Initialize the ExifTool binary manager"""
        self.binary_path: Optional[Path] = None
        self.version: Optional[str] = None
        self.is_valid: bool = False
        
        # Attempt to locate and validate binary on initialization
        self.locate_binary()
    
    def locate_binary(self) -> Optional[Path]:
        """
        Find ExifTool binary in system

        Returns:
            Path to ExifTool binary if found, None otherwise
        """
        system = platform.system()
        binary_names = self.BINARY_NAMES.get(system, ['exiftool'])

        # Check bundled locations first (prioritize media_analysis module location)
        app_dir = Path(__file__).parent.parent.parent  # Go up to application root

        bundled_locations = [
            app_dir / 'media_analysis' / 'bin',  # Media analysis module bin (NEW - PRIORITY)
            app_dir / 'bin',                      # Application root bin
        ]

        for bin_dir in bundled_locations:
            for binary_name in binary_names:
                bundled_path = bin_dir / binary_name
                if self._validate_binary(bundled_path):
                    self.binary_path = bundled_path
                    logger.info(f"Found bundled ExifTool at: {bundled_path}")

                    # For Windows standalone .exe, verify exiftool_files directory exists
                    if system == 'Windows' and binary_name == 'exiftool.exe':
                        support_dir = bin_dir / 'exiftool_files'
                        if support_dir.exists() and support_dir.is_dir():
                            logger.info(f"Verified exiftool_files directory at: {support_dir}")
                        else:
                            logger.warning(
                                f"exiftool.exe found but missing 'exiftool_files' directory at {support_dir}. "
                                "ExifTool may not function correctly."
                            )

                    return bundled_path
        
        # Check system-specific paths
        system_paths = self.SYSTEM_PATHS.get(system, [])
        for sys_path in system_paths:
            for binary_name in binary_names:
                full_path = sys_path / binary_name
                if self._validate_binary(full_path):
                    self.binary_path = full_path
                    logger.info(f"Found system ExifTool at: {full_path}")
                    return full_path
        
        # Check PATH environment variable
        for binary_name in binary_names:
            try:
                result = subprocess.run(
                    ['where' if system == 'Windows' else 'which', binary_name],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    path = Path(result.stdout.strip().split('\n')[0])
                    if self._validate_binary(path):
                        self.binary_path = path
                        logger.info(f"Found ExifTool in PATH at: {path}")
                        return path
            except (subprocess.SubprocessError, FileNotFoundError):
                continue
        
        logger.warning("ExifTool not found in system")
        return None
    
    def _validate_binary(self, path: Path) -> bool:
        """
        Validate ExifTool functionality
        
        Args:
            path: Path to potential ExifTool binary
            
        Returns:
            True if binary is valid and functional
        """
        if not path.exists():
            return False
        
        try:
            # Run exiftool -ver to get version
            result = subprocess.run(
                [str(path), '-ver'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                self.version = result.stdout.strip()
                self.is_valid = True
                
                # Verify it's actually ExifTool by checking version format
                # ExifTool versions are typically like "12.70"
                try:
                    version_num = float(self.version)
                    if version_num > 8.0:  # ExifTool versions are typically > 8.0
                        return True
                except ValueError:
                    pass
            
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            logger.debug(f"Failed to validate binary at {path}: {e}")
        
        return False
    
    def validate_binary(self, path: Path) -> bool:
        """
        Public method to validate a specific binary path
        
        Args:
            path: Path to ExifTool binary
            
        Returns:
            True if binary is valid
        """
        is_valid = self._validate_binary(path)
        if is_valid:
            self.binary_path = path
        return is_valid
    
    def is_available(self) -> bool:
        """
        Check if ExifTool is available and valid
        
        Returns:
            True if ExifTool is available
        """
        return self.is_valid and self.binary_path is not None
    
    def get_binary_path(self) -> Optional[Path]:
        """
        Get the path to the validated ExifTool binary
        
        Returns:
            Path to ExifTool binary or None
        """
        return self.binary_path
    
    def get_status_info(self) -> Dict[str, Any]:
        """
        Get detailed status information about ExifTool
        
        Returns:
            Dictionary with availability, version, and path information
        """
        return {
            'available': self.is_available(),
            'version': self.version,
            'path': str(self.binary_path) if self.binary_path else None,
            'valid': self.is_valid
        }
    
    def get_download_instructions(self) -> str:
        """
        Provide platform-specific installation instructions
        
        Returns:
            Instructions for installing ExifTool
        """
        system = platform.system()
        
        if system == 'Windows':
            return (
                "ExifTool Installation for Windows:\n"
                "1. Download from: https://exiftool.org/exiftool-12.70.zip\n"
                "2. Extract the zip file\n"
                "3. Rename 'exiftool(-k).exe' to 'exiftool.exe'\n"
                "4. Place in the 'bin' folder of this application\n"
                "   OR add to system PATH"
            )
        elif system == 'Darwin':
            return (
                "ExifTool Installation for macOS:\n"
                "Using Homebrew:\n"
                "  brew install exiftool\n\n"
                "Manual installation:\n"
                "1. Download from: https://exiftool.org/ExifTool-12.70.dmg\n"
                "2. Install the package\n"
                "3. ExifTool will be available in /usr/local/bin/"
            )
        else:  # Linux
            return (
                "ExifTool Installation for Linux:\n"
                "Ubuntu/Debian:\n"
                "  sudo apt-get install libimage-exiftool-perl\n\n"
                "Fedora/RHEL:\n"
                "  sudo dnf install perl-Image-ExifTool\n\n"
                "Arch Linux:\n"
                "  sudo pacman -S perl-image-exiftool"
            )
    
    def get_features_info(self) -> Dict[str, bool]:
        """
        Get information about available ExifTool features
        
        Returns:
            Dictionary of feature availability
        """
        if not self.is_available():
            return {
                'gps_extraction': False,
                'batch_processing': False,
                'json_output': False,
                'fast_mode': False,
                'struct_output': False
            }
        
        # All modern ExifTool versions support these features
        return {
            'gps_extraction': True,
            'batch_processing': True,
            'json_output': True,
            'fast_mode': True,
            'struct_output': float(self.version) >= 8.0 if self.version else False
        }