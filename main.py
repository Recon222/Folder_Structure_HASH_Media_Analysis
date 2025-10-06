#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Folder Structure Utility - Application Entry Point

A clean, simple approach to organized file management.
No over-engineering, just functionality.
"""

import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow


def initialize_template_system():
    """Initialize template system directories and services on startup"""
    try:
        from core.services.template_management_service import TemplateManagementService
        from core.logger import logger
        
        # Initialize template management service (creates directories)
        service = TemplateManagementService()
        logger.info("Template system initialized successfully")
        
        # Check if sample templates should be copied to user directory
        try:
            from pathlib import Path
            samples_dir = Path("templates/samples")
            if samples_dir.exists():
                sample_files = list(samples_dir.glob("*.json"))
                if sample_files:
                    logger.info(f"Found {len(sample_files)} sample templates available for import")
            else:
                logger.warning("Sample templates directory not found")
        except Exception as e:
            logger.warning(f"Error checking sample templates: {e}")
            
    except ImportError as e:
        # Template system not available - this is fine, continue without it
        from core.logger import logger
        logger.info("Template system not available (template import features disabled)")
    except Exception as e:
        # Log error but don't prevent application startup
        from core.logger import logger
        logger.warning(f"Template system initialization failed: {e}")


def main():
    """Application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("Folder Structure Utility")
    app.setOrganizationName("Simple Software")

    # Initialize template system before creating main window
    initialize_template_system()

    # Create and show main window
    window = MainWindow()
    window.show()

    # Check Windows long path support (after window is shown)
    # This runs asynchronously to not block startup
    try:
        from ui.dialogs.long_path_setup_dialog import LongPathSetupDialog
        from PySide6.QtCore import QTimer

        # Delay check by 1 second to let UI fully load
        QTimer.singleShot(1000, lambda: LongPathSetupDialog.show_if_needed(window))
    except Exception as e:
        from core.logger import logger
        logger.warning(f"Could not check long path support: {e}")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()