#!/usr/bin/env python3
"""
Simple test to debug notification dismissal issues
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
from PySide6.QtCore import QTimer

from ui.components.error_notification_system import ErrorNotificationManager
from core.exceptions import FSAError, ErrorSeverity


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dismiss Test - Watch Terminal")
        self.setGeometry(100, 100, 400, 300)
        
        # Create notification manager
        self.error_manager = ErrorNotificationManager(self)
        
        # Setup UI
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        btn1 = QPushButton("Test Single Auto-Dismiss INFO (5 sec)")
        btn1.clicked.connect(self.test_single_auto)
        layout.addWidget(btn1)
        
        btn2 = QPushButton("Test Single Manual ERROR (click X)")
        btn2.clicked.connect(self.test_single_manual)
        layout.addWidget(btn2)
        
        print("=== DISMISS TEST STARTED ===")
        print("Click buttons and watch notifications + terminal logs")
    
    def test_single_auto(self):
        print("\n>>> TESTING: Single auto-dismiss INFO (should disappear in 5 seconds)")
        error = FSAError("Auto test", user_message="INFO: Should auto-dismiss in 5 seconds")
        error.severity = ErrorSeverity.INFO
        self.error_manager.show_error(error, {'operation': 'single_auto_test'})
        
        # After 6 seconds, check if notification is still visible
        QTimer.singleShot(6000, lambda: self.check_notifications("auto-dismiss"))
    
    def test_single_manual(self):
        print("\n>>> TESTING: Single manual ERROR (click X to dismiss)")
        error = FSAError("Manual test", user_message="ERROR: Click X button to test manual dismiss")
        error.severity = ErrorSeverity.ERROR
        self.error_manager.show_error(error, {'operation': 'single_manual_test'})
    
    def check_notifications(self, test_type):
        count = self.error_manager.get_notification_count()
        print(f"\n>>> CHECK: {test_type} test - Active notifications: {count}")
        if count == 0:
            print("✅ SUCCESS: Notification was dismissed properly")
        else:
            print("❌ FAIL: Notification is still active")


def main():
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()