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


def main():
    """Application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("Folder Structure Utility")
    app.setOrganizationName("Simple Software")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()