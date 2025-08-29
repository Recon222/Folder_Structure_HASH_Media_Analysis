#!/usr/bin/env python3
"""
Test script for dynamic error notification resizing

This script creates various error notifications with different message lengths
to verify that the dynamic resizing functionality works correctly.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
from PySide6.QtCore import QTimer

from ui.components.error_notification_system import ErrorNotificationManager
from core.exceptions import FSAError, ErrorSeverity


class TestWindow(QMainWindow):
    """Test window for error notification testing"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Error Notification Dynamic Resize Test")
        self.setGeometry(100, 100, 800, 600)
        
        # Create notification manager
        self.error_manager = ErrorNotificationManager(self)
        
        # Setup UI
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Test buttons for different error types
        btn1 = QPushButton("Short Error Message")
        btn1.clicked.connect(self.show_short_error)
        layout.addWidget(btn1)
        
        btn2 = QPushButton("Medium Error Message")
        btn2.clicked.connect(self.show_medium_error)
        layout.addWidget(btn2)
        
        btn3 = QPushButton("Long Error Message")
        btn3.clicked.connect(self.show_long_error)
        layout.addWidget(btn3)
        
        btn4 = QPushButton("Very Long Error Message")
        btn4.clicked.connect(self.show_very_long_error)
        layout.addWidget(btn4)
        
        btn5 = QPushButton("Hash Verification Error (Like in Image)")
        btn5.clicked.connect(self.show_hash_verification_error)
        layout.addWidget(btn5)
        
        btn6 = QPushButton("Batch Error with Details")
        btn6.clicked.connect(self.show_batch_error)
        layout.addWidget(btn6)
        
        btn7 = QPushButton("Multi-line Error")
        btn7.clicked.connect(self.show_multiline_error)
        layout.addWidget(btn7)
        
        btn8 = QPushButton("Clear All Notifications")
        btn8.clicked.connect(self.clear_all)
        layout.addWidget(btn8)
        
        # Test auto-dismiss specifically
        btn9 = QPushButton("Test Auto-Dismiss (INFO - 5 seconds)")
        btn9.clicked.connect(self.test_auto_dismiss)
        layout.addWidget(btn9)
    
    def show_short_error(self):
        """Test short error message"""
        error = FSAError("File not found", user_message="File not found")
        error.severity = ErrorSeverity.ERROR
        self.error_manager.show_error(error, {'operation': 'copy_file'})
    
    def show_medium_error(self):
        """Test medium length error message"""
        error = FSAError(
            "Permission denied accessing destination folder", 
            user_message="Permission denied accessing destination folder. Please check permissions and try again."
        )
        error.severity = ErrorSeverity.ERROR
        self.error_manager.show_error(error, {'operation': 'folder_creation'})
    
    def show_long_error(self):
        """Test long error message"""
        error = FSAError(
            "Multiple file operation failures detected",
            user_message="Cannot access files or destination. Multiple permission errors detected during batch processing. Please check file permissions, disk space, and try again."
        )
        error.severity = ErrorSeverity.CRITICAL
        self.error_manager.show_error(error, {'operation': 'batch_file_processing'})
    
    def show_very_long_error(self):
        """Test very long error message that should hit the maximum height constraint"""
        error = FSAError(
            "System error with extensive details",
            user_message="A comprehensive system error has occurred involving multiple components including file system access, network connectivity, database operations, user permissions, and resource allocation. This error requires immediate attention and may involve checking system logs, verifying network connections, ensuring adequate disk space, validating user credentials, and reviewing system resource usage patterns."
        )
        error.severity = ErrorSeverity.ERROR
        self.error_manager.show_error(error, {'operation': 'comprehensive_system_check'})
    
    def show_hash_verification_error(self):
        """Test the specific hash verification error from the image"""
        error = FSAError(
            "Hash verification failed",
            user_message="Hash Verification Failed - 227/229 verification entries processed successfully, but 1 files are missing or corrupted and require immediate attention."
        )
        error.severity = ErrorSeverity.CRITICAL
        self.error_manager.show_error(error, {'operation': 'hash_verification_batch'})
    
    def show_batch_error(self):
        """Test batch processing error with details"""
        error = FSAError(
            "Batch processing error",
            user_message="Batch job partially successful: 15 completed, 3 failed due to permission issues and disk space constraints."
        )
        error.severity = ErrorSeverity.WARNING
        self.error_manager.show_error(error, {'operation': 'batch_processing_job_456'})
    
    def show_multiline_error(self):
        """Test error with line breaks (should be handled by word wrap)"""
        error = FSAError(
            "Multi-component error",
            user_message="File operation failed.\nMultiple issues detected:\n- Permission denied\n- Insufficient disk space\n- Network timeout"
        )
        error.severity = ErrorSeverity.ERROR
        self.error_manager.show_error(error, {'operation': 'multi_step_file_operation'})
    
    def clear_all(self):
        """Clear all notifications"""
        self.error_manager.clear_all()
    
    def test_auto_dismiss(self):
        """Test auto-dismiss functionality with INFO severity"""
        error = FSAError("Auto dismiss test", user_message="This INFO notification should auto-dismiss in 5 seconds")
        error.severity = ErrorSeverity.INFO
        self.error_manager.show_error(error, {'operation': 'auto_dismiss_test'})


def main():
    app = QApplication(sys.argv)
    
    window = TestWindow()
    window.show()
    
    # Auto-generate some test notifications after a delay
    def auto_test():
        print("Auto-generating test notifications...")
        window.show_short_error()
        
        QTimer.singleShot(1000, window.show_medium_error)
        QTimer.singleShot(2000, window.show_hash_verification_error)
    
    # Start auto test after window is shown
    QTimer.singleShot(500, auto_test)
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()