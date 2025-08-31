#!/usr/bin/env python3
"""
Debug script for error notification interaction issues

This script creates specific test cases to debug:
1. Auto-dismiss timer not working
2. X button not dismissing notifications
3. Notifications repositioning instead of disappearing
4. Details button not working after repositioning
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QTextEdit
from PySide6.QtCore import QTimer

from ui.components.error_notification_system import ErrorNotificationManager
from core.exceptions import FSAError, ErrorSeverity


class DebugWindow(QMainWindow):
    """Debug window for notification testing with logging display"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Error Notification Debug - Watch Terminal for Logs")
        self.setGeometry(100, 100, 600, 400)
        
        # Create notification manager
        self.error_manager = ErrorNotificationManager(self)
        
        # Setup UI
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Instructions
        instructions = QTextEdit()
        instructions.setPlainText("""
DEBUG INSTRUCTIONS:
1. Watch the terminal for detailed logging output
2. Test each button and observe both UI behavior and terminal logs
3. Pay attention to:
   - Auto-dismiss timers
   - Button click events
   - Manager repositioning calls
   - Animation start/finish events

ISSUES TO REPRODUCE:
- Auto-dismiss notifications not disappearing
- X button clicks triggering repositioning instead of dismissal
- Details button becoming unclickable after repositioning
        """)
        instructions.setMaximumHeight(150)
        layout.addWidget(instructions)
        
        # Test buttons
        btn1 = QPushButton("Test Auto-Dismiss INFO (5 seconds)")
        btn1.clicked.connect(self.test_auto_dismiss_info)
        layout.addWidget(btn1)
        
        btn2 = QPushButton("Test Auto-Dismiss WARNING (8 seconds)")
        btn2.clicked.connect(self.test_auto_dismiss_warning)
        layout.addWidget(btn2)
        
        btn3 = QPushButton("Test Manual Dismiss ERROR (no auto-dismiss)")
        btn3.clicked.connect(self.test_manual_dismiss)
        layout.addWidget(btn3)
        
        btn4 = QPushButton("Test Details Button CRITICAL")
        btn4.clicked.connect(self.test_details_button)
        layout.addWidget(btn4)
        
        btn5 = QPushButton("Test Multiple Notifications")
        btn5.clicked.connect(self.test_multiple)
        layout.addWidget(btn5)
        
        btn6 = QPushButton("Clear All")
        btn6.clicked.connect(self.clear_all)
        layout.addWidget(btn6)
        
        print("\n" + "="*80)
        print("DEBUG SESSION STARTED")
        print("Watch for logging output below...")
        print("="*80 + "\n")
    
    def test_auto_dismiss_info(self):
        """Test INFO severity auto-dismiss (5 seconds)"""
        print("\n>>> USER ACTION: Testing INFO auto-dismiss (should disappear in 5 seconds)")
        error = FSAError("Info test", user_message="This INFO notification should auto-dismiss in 5 seconds")
        error.severity = ErrorSeverity.INFO
        self.error_manager.show_error(error, {'operation': 'debug_info_test'})
    
    def test_auto_dismiss_warning(self):
        """Test WARNING severity auto-dismiss (8 seconds)"""
        print("\n>>> USER ACTION: Testing WARNING auto-dismiss (should disappear in 8 seconds)")
        error = FSAError("Warning test", user_message="This WARNING notification should auto-dismiss in 8 seconds")
        error.severity = ErrorSeverity.WARNING
        self.error_manager.show_error(error, {'operation': 'debug_warning_test'})
    
    def test_manual_dismiss(self):
        """Test ERROR severity manual dismiss (no auto-dismiss)"""
        print("\n>>> USER ACTION: Testing ERROR manual dismiss - click X button to test")
        error = FSAError("Error test", user_message="ERROR: Click the X button to test manual dismissal")
        error.severity = ErrorSeverity.ERROR
        self.error_manager.show_error(error, {'operation': 'debug_manual_test'})
    
    def test_details_button(self):
        """Test Details button functionality"""
        print("\n>>> USER ACTION: Testing Details button - click Details to test")
        error = FSAError("Critical test", user_message="CRITICAL: Click Details button to test dialog")
        error.severity = ErrorSeverity.CRITICAL
        self.error_manager.show_error(error, {'operation': 'debug_details_test'})
    
    def test_multiple(self):
        """Test multiple notifications interaction"""
        print("\n>>> USER ACTION: Testing multiple notifications")
        
        # Add INFO that should auto-dismiss
        error1 = FSAError("Multi test 1", user_message="INFO: Should auto-dismiss in 5 seconds")
        error1.severity = ErrorSeverity.INFO
        self.error_manager.show_error(error1, {'operation': 'multi_test_1'})
        
        # Add ERROR that requires manual dismiss
        QTimer.singleShot(1000, lambda: self._add_second_notification())
    
    def _add_second_notification(self):
        """Add second notification for multi-test"""
        error2 = FSAError("Multi test 2", user_message="ERROR: Requires manual dismiss - test X button")
        error2.severity = ErrorSeverity.ERROR
        self.error_manager.show_error(error2, {'operation': 'multi_test_2'})
    
    def clear_all(self):
        """Clear all notifications"""
        print("\n>>> USER ACTION: Clearing all notifications")
        self.error_manager.clear_all()


def main():
    app = QApplication(sys.argv)
    
    window = DebugWindow()
    window.show()
    
    print("Debug window created. Start testing notification interactions...")
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()