"""
Windows Long Path Support Manager

Provides detection, enabling, and guidance for Windows long path support.
Handles the LongPathsEnabled registry setting gracefully without forcing users
to manually configure their systems.

Author: Claude Code
Created: 2025-10-05
"""

import sys
import platform
import winreg
from pathlib import Path
from typing import Tuple, Optional
from core.logger import logger


class WindowsLongPathManager:
    """
    Manages Windows long path support detection and configuration.

    This class provides a user-friendly way to:
    1. Detect if Windows long paths are enabled system-wide
    2. Provide instructions for enabling if needed
    3. Offer to enable it automatically (requires admin rights)
    """

    REGISTRY_PATH = r"SYSTEM\CurrentControlSet\Control\FileSystem"
    REGISTRY_KEY = "LongPathsEnabled"

    @staticmethod
    def is_windows() -> bool:
        """Check if running on Windows."""
        return platform.system() == "Windows"

    @staticmethod
    def is_long_paths_enabled() -> bool:
        """
        Check if Windows long path support is enabled system-wide.

        Returns:
            True if LongPathsEnabled=1 in registry, False otherwise
        """
        if not WindowsLongPathManager.is_windows():
            return True  # Non-Windows systems don't have this limitation

        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                WindowsLongPathManager.REGISTRY_PATH,
                0,
                winreg.KEY_READ
            )
            value, regtype = winreg.QueryValueEx(key, WindowsLongPathManager.REGISTRY_KEY)
            winreg.CloseKey(key)

            is_enabled = (value == 1)
            logger.info(f"Windows long path support: {'ENABLED' if is_enabled else 'DISABLED'}")
            return is_enabled

        except FileNotFoundError:
            # Registry key doesn't exist - long paths are disabled
            logger.warning("Windows long path registry key not found - long paths disabled")
            return False
        except PermissionError:
            # Can't read registry - assume disabled for safety
            logger.warning("Permission denied reading long path registry - assuming disabled")
            return False
        except Exception as e:
            logger.error(f"Error checking long path support: {e}", exc_info=True)
            return False

    @staticmethod
    def check_admin_rights() -> bool:
        """
        Check if the current process has administrator privileges.

        Returns:
            True if running as admin, False otherwise
        """
        if not WindowsLongPathManager.is_windows():
            return False

        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception as e:
            logger.debug(f"Could not check admin rights: {e}")
            return False

    @staticmethod
    def enable_long_paths() -> Tuple[bool, str]:
        """
        Attempt to enable Windows long path support.

        REQUIRES ADMINISTRATOR PRIVILEGES.

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not WindowsLongPathManager.is_windows():
            return False, "Not running on Windows"

        if not WindowsLongPathManager.check_admin_rights():
            return False, "Administrator privileges required"

        try:
            # Open registry key for writing
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                WindowsLongPathManager.REGISTRY_PATH,
                0,
                winreg.KEY_WRITE
            )

            # Set LongPathsEnabled to 1
            winreg.SetValueEx(key, WindowsLongPathManager.REGISTRY_KEY, 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)

            logger.info("Windows long path support ENABLED successfully")
            return True, "Long path support enabled successfully"

        except PermissionError:
            msg = "Permission denied - administrator privileges required"
            logger.error(msg)
            return False, msg
        except Exception as e:
            msg = f"Failed to enable long paths: {e}"
            logger.error(msg, exc_info=True)
            return False, msg

    @staticmethod
    def get_manual_enable_instructions() -> str:
        """
        Get step-by-step instructions for manually enabling long path support.

        Returns:
            Formatted instructions string
        """
        return """
=== How to Enable Windows Long Path Support ===

OPTION 1: Using PowerShell (Recommended)
1. Right-click Start Menu → Select "Windows PowerShell (Admin)"
2. Run this command:
   New-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
3. Restart this application (no system reboot needed)

OPTION 2: Using Group Policy Editor (Windows Pro/Enterprise)
1. Press Win+R, type: gpedit.msc
2. Navigate to: Computer Configuration → Administrative Templates → System → Filesystem
3. Double-click "Enable Win32 long paths"
4. Select "Enabled" → Click OK
5. Restart this application

OPTION 3: Using Registry Editor (Advanced)
1. Press Win+R, type: regedit
2. Navigate to: HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Control\\FileSystem
3. Create or modify DWORD value "LongPathsEnabled"
4. Set value to 1
5. Restart this application

WHY THIS IS NEEDED:
Windows has a 260-character path limit by default. Enabling long path support
removes this limitation, allowing paths up to 32,767 characters. This is essential
for forensic file processing with deep directory structures.

Note: Changes take effect immediately (no reboot required), but you must restart
this application to detect the change.
"""

    @staticmethod
    def get_status_summary() -> dict:
        """
        Get comprehensive status summary of long path support.

        Returns:
            Dictionary with status information
        """
        is_enabled = WindowsLongPathManager.is_long_paths_enabled()
        is_admin = WindowsLongPathManager.check_admin_rights()
        is_win = WindowsLongPathManager.is_windows()

        return {
            'is_windows': is_win,
            'is_enabled': is_enabled,
            'is_admin': is_admin,
            'can_auto_enable': is_admin and not is_enabled,
            'needs_manual_setup': not is_enabled and not is_admin,
            'status_message': (
                "Long paths enabled ✓" if is_enabled else
                "Long paths disabled - admin rights available" if is_admin else
                "Long paths disabled - manual setup required"
            )
        }

    @staticmethod
    def check_path_length(path: Path, threshold: int = 248) -> Tuple[bool, int]:
        """
        Check if a path exceeds Windows MAX_PATH limitations.

        Args:
            path: Path to check
            threshold: Character limit (default 248 for safety margin)

        Returns:
            Tuple of (exceeds_limit: bool, actual_length: int)
        """
        try:
            path_str = str(path.resolve())
            length = len(path_str)
            exceeds = length > threshold

            if exceeds:
                logger.warning(f"Path exceeds {threshold} chars ({length}): {path_str[:100]}...")

            return exceeds, length

        except Exception as e:
            logger.debug(f"Could not check path length for {path}: {e}")
            return False, 0


# Singleton instance
_manager = WindowsLongPathManager()


def is_long_paths_enabled() -> bool:
    """Convenience function to check if long paths are enabled."""
    return _manager.is_long_paths_enabled()


def get_status_summary() -> dict:
    """Convenience function to get status summary."""
    return _manager.get_status_summary()


def check_path_length(path: Path, threshold: int = 248) -> Tuple[bool, int]:
    """Convenience function to check path length."""
    return _manager.check_path_length(path, threshold)
