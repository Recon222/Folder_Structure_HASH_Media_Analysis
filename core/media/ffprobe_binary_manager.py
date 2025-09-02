#!/usr/bin/env python3
"""
FFprobe binary management for media analysis operations
Handles ffprobe.exe detection, validation, and version checking
"""

import subprocess
import platform
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
import os

from core.logger import logger
from core.result_types import Result
from core.exceptions import FSAError


class FFProbeBinaryManager:
    """Manages ffprobe binary for media metadata extraction"""
    
    def __init__(self):
        """Initialize binary manager and locate ffprobe"""
        self.binary_path: Optional[Path] = None
        self.version_info: Optional[str] = None
        self.is_validated: bool = False
        self.platform_supported: bool = True  # FFprobe works on all platforms
        
        # Locate the binary
        self._locate_binary()
        
        # Validate if found
        if self.binary_path:
            self._validate_binary()
    
    def _locate_binary(self) -> Optional[Path]:
        """Locate ffprobe binary - bundled or system"""
        try:
            # Get application root directory
            app_root = Path(__file__).parent.parent.parent
            
            # Determine platform-specific binary name
            binary_name = "ffprobe.exe" if platform.system() == "Windows" else "ffprobe"
            
            # Check bundled locations first
            potential_paths = [
                app_root / "bin" / binary_name,           # Primary bundled location
                app_root / binary_name,                   # Alternative location
                Path("bin") / binary_name,                # Relative to working directory
                Path(binary_name)                         # Working directory
            ]
            
            # Check bundled locations
            for path in potential_paths:
                if path.exists() and path.is_file():
                    logger.info(f"Found bundled ffprobe at: {path.absolute()}")
                    self.binary_path = path.resolve()
                    return self.binary_path
            
            # Fallback to system ffprobe
            system_ffprobe = shutil.which("ffprobe")
            if system_ffprobe:
                logger.info(f"Using system ffprobe at: {system_ffprobe}")
                self.binary_path = Path(system_ffprobe).resolve()
                return self.binary_path
            
            logger.warning("ffprobe not found in bundled locations or system PATH")
            logger.info("Expected bundled locations checked:")
            for path in potential_paths:
                logger.info(f"  - {path.absolute()}")
            logger.info("To use media analysis, please:")
            logger.info("  1. Download ffprobe from https://ffmpeg.org/download.html")
            logger.info(f"  2. Place {binary_name} in the 'bin' folder")
            logger.info("  3. Or install FFmpeg system-wide")
                
            return None
            
        except Exception as e:
            logger.error(f"Error locating ffprobe: {e}")
            return None
    
    def _validate_binary(self) -> bool:
        """Validate that ffprobe is functional and get version info"""
        if not self.binary_path or not self.binary_path.exists():
            logger.warning("Cannot validate ffprobe - binary not found")
            return False
        
        try:
            # Test basic functionality with -version
            logger.debug(f"Validating ffprobe at: {self.binary_path}")
            
            result = subprocess.run(
                [str(self.binary_path), "-version"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.binary_path.parent if self.binary_path.parent.exists() else None
            )
            
            # ffprobe -version returns version info on stdout
            if result.returncode == 0 and "ffprobe" in result.stdout.lower():
                # Extract version line
                version_lines = result.stdout.split('\n')
                for line in version_lines:
                    if "ffprobe version" in line.lower():
                        self.version_info = line.strip()
                        break
                else:
                    self.version_info = version_lines[0].strip() if version_lines else "Unknown version"
                
                self.is_validated = True
                logger.info(f"ffprobe validation successful: {self.version_info}")
                return True
            else:
                logger.warning(f"ffprobe validation failed - return code: {result.returncode}")
                if result.stderr:
                    logger.debug(f"stderr: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("ffprobe validation timed out")
            return False
        except Exception as e:
            logger.error(f"Error validating ffprobe: {e}")
            return False
    
    def get_binary_path(self) -> Optional[Path]:
        """Get the validated binary path"""
        if self.is_validated:
            return self.binary_path
        return None
    
    def is_available(self) -> bool:
        """Check if ffprobe is available and validated"""
        return self.is_validated and self.binary_path is not None
    
    def get_status_info(self) -> Dict[str, Any]:
        """Get status information for diagnostics"""
        return {
            "available": self.is_available(),
            "path": str(self.binary_path) if self.binary_path else None,
            "version": self.version_info,
            "validated": self.is_validated,
            "platform": platform.system()
        }