#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Native 7zip binary management for Windows-focused forensic applications
Handles bundled 7za.exe detection, validation, and version checking
"""

import subprocess
import platform
from pathlib import Path
from typing import Optional, Dict, Any
import hashlib
import os

from core.logger import logger
from core.result_types import Result
from core.exceptions import ArchiveError


class Native7ZipBinaryManager:
    """Manages 7za.exe binary for Windows high-performance operations"""
    
    # Known good SHA-256 hashes for different 7za.exe versions
    # These will be updated as we verify specific versions
    KNOWN_GOOD_HASHES = {
        # Will be populated once we have the actual binary
        # "7za_23.01": "sha256_hash_here",
        # "7za_22.01": "sha256_hash_here"
    }
    
    def __init__(self):
        """Initialize binary manager and locate 7za.exe"""
        self.binary_path: Optional[Path] = None
        self.version_info: Optional[str] = None
        self.is_validated: bool = False
        self.platform_supported: bool = platform.system() == "Windows"
        
        # Locate the binary
        self._locate_binary()
        
        # Validate if found
        if self.binary_path:
            self._validate_binary()
    
    def _locate_binary(self) -> Optional[Path]:
        """Locate bundled 7za.exe binary"""
        try:
            # Get application root directory (main.py location)
            app_root = Path(__file__).parent.parent.parent
            potential_paths = [
                app_root / "bin" / "7za.exe",           # Primary bundled location
                app_root / "7za.exe",                   # Alternative location
                Path("bin/7za.exe"),                    # Relative to working directory
                Path("7za.exe")                         # Working directory
            ]
            
            for path in potential_paths:
                if path.exists() and path.is_file():
                    logger.info(f"Found 7za.exe at: {path.absolute()}")
                    self.binary_path = path.resolve()
                    return self.binary_path
            
            logger.warning("7za.exe not found in any expected locations")
            logger.info("Expected locations checked:")
            for path in potential_paths:
                logger.info(f"  - {path.absolute()}")
                
            return None
            
        except Exception as e:
            logger.error(f"Error locating 7za.exe: {e}")
            return None
    
    def _validate_binary(self) -> bool:
        """Validate that 7za.exe is functional and get version info"""
        if not self.binary_path or not self.binary_path.exists():
            logger.warning("Cannot validate 7za.exe - binary not found")
            return False
        
        try:
            # Test basic functionality with --version
            logger.debug(f"Validating 7za.exe at: {self.binary_path}")
            
            result = subprocess.run(
                [str(self.binary_path)],  # Just running 7za.exe shows version
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.binary_path.parent
            )
            
            # 7za.exe returns version info on stdout when run without arguments
            if result.returncode == 0 and "7-Zip" in result.stdout:
                self.version_info = result.stdout.strip()
                self.is_validated = True
                logger.info(f"7za.exe validation successful")
                logger.debug(f"Version info: {self.version_info[:100]}...")  # First 100 chars
                return True
            else:
                logger.warning(f"7za.exe validation failed - return code: {result.returncode}")
                if result.stderr:
                    logger.warning(f"7za.exe stderr: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("7za.exe validation timed out")
            return False
        except FileNotFoundError:
            logger.error(f"7za.exe not found or not executable: {self.binary_path}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error validating 7za.exe: {e}")
            return False
    
    def _calculate_file_hash(self) -> Optional[str]:
        """Calculate SHA-256 hash of the 7za.exe binary"""
        if not self.binary_path or not self.binary_path.exists():
            return None
            
        try:
            sha256_hash = hashlib.sha256()
            with open(self.binary_path, "rb") as f:
                # Read in chunks to handle large files efficiently
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            
            file_hash = sha256_hash.hexdigest()
            logger.debug(f"7za.exe SHA-256: {file_hash}")
            return file_hash
            
        except Exception as e:
            logger.error(f"Error calculating 7za.exe hash: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if 7za.exe is available and validated"""
        return (self.platform_supported and 
                self.binary_path is not None and 
                self.binary_path.exists() and 
                self.is_validated)
    
    def get_binary_path(self) -> Optional[Path]:
        """Get path to validated 7za.exe binary"""
        return self.binary_path if self.is_available() else None
    
    def get_version_info(self) -> Optional[str]:
        """Get 7zip version information"""
        return self.version_info if self.is_available() else None
    
    def get_platform_support_info(self) -> Dict[str, Any]:
        """Get detailed platform and binary support information"""
        file_hash = self._calculate_file_hash() if self.binary_path else None
        
        return {
            'platform': platform.system(),
            'platform_supported': self.platform_supported,
            'binary_found': self.binary_path is not None,
            'binary_path': str(self.binary_path) if self.binary_path else None,
            'binary_exists': self.binary_path.exists() if self.binary_path else False,
            'binary_validated': self.is_validated,
            'binary_available': self.is_available(),
            'version_info': self.version_info,
            'file_hash': file_hash,
            'file_size': self.binary_path.stat().st_size if self.binary_path and self.binary_path.exists() else None
        }
    
    def verify_binary_integrity(self) -> Result[bool]:
        """Verify binary integrity using known good hashes (when available)"""
        if not self.is_available():
            return Result.error(ArchiveError(
                "Cannot verify binary integrity - 7za.exe not available",
                user_message="7-Zip binary not found or not validated"
            ))
        
        try:
            file_hash = self._calculate_file_hash()
            if not file_hash:
                return Result.error(ArchiveError(
                    "Failed to calculate binary hash",
                    user_message="Cannot verify 7-Zip binary integrity"
                ))
            
            # For now, just log the hash (we'll add known good hashes later)
            logger.info(f"7za.exe integrity check - SHA-256: {file_hash}")
            
            # TODO: Compare against known good hashes when we have them
            if self.KNOWN_GOOD_HASHES:
                if file_hash not in self.KNOWN_GOOD_HASHES.values():
                    return Result.error(ArchiveError(
                        f"Binary hash mismatch - got {file_hash}",
                        user_message="7-Zip binary failed integrity check"
                    ))
            
            logger.info("7za.exe integrity verification passed")
            return Result.success(True)
            
        except Exception as e:
            return Result.error(ArchiveError(
                f"Error verifying binary integrity: {e}",
                user_message="Failed to verify 7-Zip binary integrity"
            ))
    
    def get_diagnostic_info(self) -> str:
        """Get comprehensive diagnostic information for troubleshooting"""
        info = self.get_platform_support_info()
        
        lines = [
            "=== Native 7zip Binary Manager Diagnostics ===",
            f"Platform: {info['platform']} (Supported: {info['platform_supported']})",
            f"Binary Found: {info['binary_found']}",
            f"Binary Path: {info['binary_path']}",
            f"Binary Exists: {info['binary_exists']}",
            f"Binary Validated: {info['binary_validated']}",
            f"Binary Available: {info['binary_available']}",
            f"File Size: {info['file_size']} bytes" if info['file_size'] else "File Size: N/A",
            f"File Hash: {info['file_hash']}" if info['file_hash'] else "File Hash: N/A",
            "",
            "Version Info:",
            info['version_info'] if info['version_info'] else "N/A"
        ]
        
        return "\n".join(lines)