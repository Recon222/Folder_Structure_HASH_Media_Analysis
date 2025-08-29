#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Non-modal error notification system for thread-safe error display

This module provides modern, non-blocking error notifications that replace
modal QMessageBox dialogs throughout the application. Integrates with the
centralized error handling system for consistent user experience.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QDialog, QTextEdit, QScrollArea, QFrame
)
from PySide6.QtCore import Signal, QTimer, Qt, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QIcon, QFont, QPixmap, QPainter, QColor, QBrush, QFontMetrics
from typing import Dict, Optional
from datetime import datetime
import uuid
import logging

# Set up logging for debugging notification behavior
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ErrorNotificationSystem')

from core.exceptions import FSAError, ErrorSeverity


class ErrorNotification(QFrame):
    """
    Individual error notification widget with severity-based styling
    
    Non-modal notification that displays error information with appropriate
    visual styling based on severity level. Supports auto-dismiss for
    non-critical errors and detailed error information on demand.
    """
    
    dismissed = Signal(str)  # notification_id
    details_requested = Signal(FSAError, dict)  # error, context
    
    def __init__(self, error: FSAError, context: dict, notification_id: str):
        """
        Initialize error notification
        
        Args:
            error: The FSAError that occurred
            context: Additional context information
            notification_id: Unique identifier for this notification
        """
        super().__init__()
        self.error = error
        self.context = context
        self.notification_id = notification_id
        
        logger.info(f"Creating notification {notification_id} with message: '{error.user_message or str(error)[:50]}...'")
        
        # Determine severity from error or context
        self.severity = self._determine_severity()
        logger.debug(f"Notification {notification_id} severity: {self.severity}")
        
        self._setup_ui()
        self._setup_auto_dismiss()
    
    def _determine_severity(self) -> ErrorSeverity:
        """Determine notification severity from error and context"""
        # Check context first
        context_severity = self.context.get('severity')
        if context_severity:
            try:
                return ErrorSeverity(context_severity)
            except ValueError:
                pass
        
        # Check error severity if available
        if hasattr(self.error, 'severity'):
            return self.error.severity
        
        # Default based on error type
        error_class = self.error.__class__.__name__
        if 'Validation' in error_class:
            return ErrorSeverity.WARNING
        elif 'Critical' in error_class or 'Fatal' in error_class:
            return ErrorSeverity.CRITICAL
        else:
            return ErrorSeverity.ERROR
    
    def _calculate_required_height(self) -> int:
        """
        Calculate the required height for the notification based on content
        
        Returns:
            int: Required height in pixels (constrained between min/max values)
        """
        # Base components height
        base_height = 24  # Top/bottom margins (8px each) + padding
        icon_height = 32  # Icon size
        button_height = 24  # Button height
        spacing = 12  # Layout spacing
        
        # Calculate text height for main message
        message_text = self.error.user_message or str(self.error)
        content_width = 300  # Available width for text (400 total - margins - icon - buttons)
        
        # Create font and metrics for calculation
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        font_metrics = QFontMetrics(font)
        
        # Calculate wrapped text height
        text_rect = font_metrics.boundingRect(
            0, 0, content_width, 0,
            Qt.TextWordWrap | Qt.AlignLeft,
            message_text
        )
        message_height = text_rect.height()
        
        # Calculate context text height if present
        context_height = 0
        if self.context.get('operation'):
            context_font = QFont()
            context_font.setPointSize(11)
            context_font.setItalic(True)
            context_metrics = QFontMetrics(context_font)
            
            context_text = f"Operation: {self.context['operation']}"
            context_rect = context_metrics.boundingRect(
                0, 0, content_width, 0,
                Qt.TextWordWrap | Qt.AlignLeft,
                context_text
            )
            context_height = context_rect.height() + 4  # +4px spacing
        
        # Calculate total required height
        content_area_height = max(message_height + context_height, button_height)
        total_height = base_height + max(icon_height, content_area_height) + spacing
        
        # Apply constraints: minimum 60px, maximum 150px
        min_height = 60
        max_height = 150
        
        return max(min_height, min(max_height, total_height))
    
    def _setup_ui(self):
        """Create the notification UI with severity-based styling"""
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setLineWidth(2)
        
        # Use dynamic height calculation instead of fixed height
        required_height = self._calculate_required_height()
        self.setFixedHeight(required_height)
        self.setMaximumWidth(400)
        
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        # Severity indicator (colored bar)
        severity_bar = QFrame()
        severity_bar.setFixedWidth(4)
        severity_bar.setStyleSheet(f"background-color: {self._get_severity_color()};")
        layout.addWidget(severity_bar)
        
        # Icon
        icon_label = QLabel()
        icon_label.setPixmap(self._get_severity_icon())
        icon_label.setFixedSize(32, 32)
        icon_label.setScaledContents(True)
        layout.addWidget(icon_label)
        
        # Message content
        content_layout = QVBoxLayout()
        
        # Error message
        message_label = QLabel(self.error.user_message or str(self.error))
        message_label.setWordWrap(True)
        message_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 13px;
                color: #ffffff;
            }
        """)
        content_layout.addWidget(message_label)
        
        # Context info (if available)
        if self.context.get('operation'):
            context_label = QLabel(f"Operation: {self.context['operation']}")
            context_label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #cccccc;
                    font-style: italic;
                }
            """)
            content_layout.addWidget(context_label)
        
        layout.addLayout(content_layout, 1)
        
        # Action buttons
        button_layout = QVBoxLayout()
        button_layout.setSpacing(4)
        
        # Details button
        details_btn = QPushButton("Details")
        details_btn.setFixedSize(60, 24)
        details_btn.clicked.connect(self._show_details)
        details_btn.setStyleSheet(self._get_button_style())
        button_layout.addWidget(details_btn)
        
        # Dismiss button
        dismiss_btn = QPushButton("✕")
        dismiss_btn.setFixedSize(24, 24)
        dismiss_btn.clicked.connect(self.dismiss)
        dismiss_btn.setStyleSheet(self._get_button_style(is_close=True))
        button_layout.addWidget(dismiss_btn)
        
        layout.addLayout(button_layout)
        
        # Apply overall styling
        self.setStyleSheet(self._get_notification_style())
    
    def _get_severity_color(self) -> str:
        """Get color based on severity level"""
        colors = {
            ErrorSeverity.INFO: '#2196F3',      # Blue
            ErrorSeverity.WARNING: '#FF9800',   # Orange  
            ErrorSeverity.ERROR: '#ff6b6b',     # Red (matches Carolina Blue theme)
            ErrorSeverity.CRITICAL: '#9C27B0'   # Purple
        }
        return colors.get(self.severity, '#ff6b6b')
    
    def _get_severity_icon(self) -> QPixmap:
        """Get icon based on severity level"""
        # Create simple colored circle icons since we may not have system icons
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw colored circle
        color = QColor(self._get_severity_color())
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 24, 24)
        
        # Draw severity symbol
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 14, QFont.Bold))
        
        symbols = {
            ErrorSeverity.INFO: 'i',
            ErrorSeverity.WARNING: '!',
            ErrorSeverity.ERROR: '×',
            ErrorSeverity.CRITICAL: '!!'
        }
        symbol = symbols.get(self.severity, '×')
        painter.drawText(pixmap.rect(), Qt.AlignCenter, symbol)
        
        painter.end()
        return pixmap
    
    def _get_notification_style(self) -> str:
        """Get overall notification styling"""
        return f"""
        ErrorNotification {{
            background-color: #2b2b2b;
            border: 1px solid {self._get_severity_color()};
            border-radius: 6px;
            margin: 2px;
        }}
        ErrorNotification:hover {{
            background-color: #3a3a3a;
        }}
        """
    
    def _get_button_style(self, is_close: bool = False) -> str:
        """Get button styling"""
        if is_close:
            return """
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 3px;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.3);
            }
            """
        else:
            return """
            QPushButton {
                background: rgba(75, 156, 211, 0.3);
                border: 1px solid #4B9CD3;
                border-radius: 3px;
                color: #ffffff;
                font-size: 10px;
                padding: 2px 4px;
            }
            QPushButton:hover {
                background: rgba(75, 156, 211, 0.5);
            }
            QPushButton:pressed {
                background: rgba(75, 156, 211, 0.7);
            }
            """
    
    def _setup_auto_dismiss(self):
        """Setup auto-dismiss timer for non-critical errors"""
        if self.severity in [ErrorSeverity.INFO, ErrorSeverity.WARNING]:
            dismiss_time = 8000 if self.severity == ErrorSeverity.WARNING else 5000
            logger.info(f"Setting up auto-dismiss for {self.notification_id} in {dismiss_time}ms")
            QTimer.singleShot(dismiss_time, self.dismiss)
        else:
            logger.debug(f"No auto-dismiss for {self.notification_id} - severity: {self.severity}")
    
    def _show_details(self):
        """Show detailed error information"""
        logger.info(f"Details button clicked for notification {self.notification_id}")
        self.details_requested.emit(self.error, self.context)
    
    def dismiss(self):
        """Dismiss this notification"""
        logger.info(f"DISMISS CALLED for notification {self.notification_id}")
        self.dismissed.emit(self.notification_id)
        
        # Remove from parent layout FIRST, then hide and delete
        logger.debug(f"Removing notification {self.notification_id} from layout")
        if self.parent() and hasattr(self.parent(), 'layout'):
            parent_layout = self.parent().layout
            if parent_layout:
                logger.debug(f"Removing {self.notification_id} from parent layout")
                parent_layout.removeWidget(self)
        
        logger.debug(f"Hiding and deleting notification {self.notification_id}")
        self.hide()
        self.deleteLater()


class ErrorDetailsDialog(QDialog):
    """
    Detailed error information dialog
    
    Shows comprehensive technical error details including context,
    stack traces, and error metadata for debugging purposes.
    """
    
    def __init__(self, error: FSAError, context: dict, parent=None):
        """
        Initialize error details dialog
        
        Args:
            error: The FSAError to display details for
            context: Additional context information
            parent: Parent widget
        """
        super().__init__(parent)
        self.error = error
        self.context = context
        
        self.setWindowTitle("Error Details")
        self.setModal(True)
        self.resize(600, 400)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Create the details dialog UI"""
        layout = QVBoxLayout(self)
        
        # Scrollable text area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        details_text = QTextEdit()
        details_text.setReadOnly(True)
        details_text.setPlainText(self._format_error_details())
        details_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid #4B9CD3;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        
        scroll_area.setWidget(details_text)
        layout.addWidget(scroll_area)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #4B9CD3;
                border: none;
                border-radius: 4px;
                color: #ffffff;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #7BAFD4;
            }
            QPushButton:pressed {
                background: #13294B;
            }
        """)
        layout.addWidget(close_btn, 0, Qt.AlignCenter)
    
    def _format_error_details(self) -> str:
        """Format comprehensive error details for display"""
        details = []
        
        # Basic error information
        details.append("ERROR DETAILS")
        details.append("=" * 50)
        details.append(f"Error Type: {self.error.__class__.__name__}")
        details.append(f"Error Code: {getattr(self.error, 'error_code', 'N/A')}")
        details.append(f"Timestamp: {getattr(self.error, 'timestamp', datetime.now())}")
        details.append(f"Recoverable: {getattr(self.error, 'recoverable', 'Unknown')}")
        details.append("")
        
        # Messages
        details.append("MESSAGES")
        details.append("-" * 20)
        details.append(f"User Message: {getattr(self.error, 'user_message', 'N/A')}")
        details.append(f"Technical Message: {str(self.error)}")
        details.append("")
        
        # Context information
        details.append("CONTEXT")
        details.append("-" * 20)
        if self.context:
            for key, value in self.context.items():
                details.append(f"{key}: {value}")
        else:
            details.append("No context available")
        details.append("")
        
        # Thread information
        if hasattr(self.error, 'thread_id'):
            details.append("THREAD INFORMATION")
            details.append("-" * 20)
            details.append(f"Thread ID: {self.error.thread_id}")
            details.append(f"Is Main Thread: {getattr(self.error, 'is_main_thread', 'Unknown')}")
            details.append("")
        
        # Additional error attributes
        error_attrs = {}
        for attr in dir(self.error):
            if not attr.startswith('_') and not callable(getattr(self.error, attr)):
                try:
                    value = getattr(self.error, attr)
                    # Exclude redundant attributes already shown in other sections
                    if attr not in ['args', 'with_traceback', 'user_message']:
                        error_attrs[attr] = value
                except:
                    pass
        
        if error_attrs:
            details.append("ERROR ATTRIBUTES")
            details.append("-" * 20)
            for attr, value in error_attrs.items():
                details.append(f"{attr}: {value}")
        
        return "\n".join(details)


class ErrorNotificationManager(QWidget):
    """
    Manages multiple error notifications with positioning and lifecycle
    
    Handles display, positioning, and cleanup of error notifications.
    Maintains a maximum number of visible notifications and provides
    smooth animations for notification appearance and dismissal.
    """
    
    def __init__(self, parent=None):
        """
        Initialize notification manager
        
        Args:
            parent: Parent widget for positioning
        """
        super().__init__(parent)
        
        # Configuration
        self.max_notifications = 5
        self.notification_spacing = 4
        
        # Setup widget as top-level overlay window
        self.setFixedWidth(420)
        # Remove fixed maximum height since notifications now have variable heights
        # The height will be calculated dynamically based on notification count and their sizes
        
        # Critical z-order fixes: Use top-level window approach for guaranteed visibility
        if parent:
            # Set as top-level window but track parent for positioning
            # Remove WindowDoesNotAcceptFocus to allow button interactions
            self.setWindowFlags(
                Qt.Window | 
                Qt.WindowStaysOnTopHint | 
                Qt.FramelessWindowHint
            )
            # Make it always stay on top with transparency support
            self.setAttribute(Qt.WA_TranslucentBackground)
            # Remove ShowWithoutActivating to allow interactions
            self.parent_window = parent
        else:
            # Fallback for no parent
            self.parent_window = None
            
        # Ensure mouse events work properly
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        
        # Layout for stacking notifications
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(self.notification_spacing)
        self.layout.addStretch()  # Push notifications to top
        
        # Active notifications
        self.notifications: Dict[str, ErrorNotification] = {}
        self.notification_counter = 0
        
        # Show and position if we have a parent
        if parent:
            self.show()
            # Update initial position
            self._update_position()
    
    def _calculate_total_height(self) -> int:
        """
        Calculate total height needed for all active notifications
        
        Returns:
            int: Total height in pixels needed for the notification manager
        """
        if not self.notifications:
            return 50  # Minimum height when no notifications
        
        total_height = 20  # Top and bottom margins (10px each)
        
        # Add height of each notification plus spacing
        for notification in self.notifications.values():
            total_height += notification.height()
            total_height += self.notification_spacing
        
        # Remove the last spacing since there's no notification after the last one
        if self.notifications:
            total_height -= self.notification_spacing
        
        # Apply reasonable maximum to prevent notifications from going off-screen
        max_screen_height = 800  # Reasonable maximum for most screens
        return min(total_height, max_screen_height)
    
    def _update_manager_size(self):
        """Update the notification manager's size based on active notifications"""
        required_height = self._calculate_total_height()
        self.setFixedHeight(required_height)
        
        # Hide the manager window if no notifications, show if there are notifications
        if len(self.notifications) == 0:
            logger.debug("MANAGER: No notifications - hiding manager window")
            self.hide()
        else:
            logger.debug(f"MANAGER: {len(self.notifications)} notifications - showing manager window")
            if not self.isVisible():
                self.show()
    
    def show_error(self, error: FSAError, context: dict):
        """
        Display a new error notification
        
        Args:
            error: The FSAError that occurred  
            context: Additional context information
        """
        # Generate unique ID
        notification_id = f"error_{self.notification_counter}_{uuid.uuid4().hex[:8]}"
        self.notification_counter += 1
        
        logger.info(f"MANAGER: Showing new error notification {notification_id}")
        logger.debug(f"MANAGER: Current notifications count: {len(self.notifications)}")
        
        # Create notification
        notification = ErrorNotification(error, context, notification_id)
        notification.dismissed.connect(self._remove_notification)
        notification.details_requested.connect(self._show_error_details)
        
        # Insert at top (before stretch)
        logger.debug(f"MANAGER: Inserting notification {notification_id} into layout")
        self.layout.insertWidget(0, notification)
        self.notifications[notification_id] = notification
        
        # Enforce maximum notifications
        if len(self.notifications) > self.max_notifications:
            # Remove oldest notification
            oldest_id = min(
                self.notifications.keys(), 
                key=lambda x: int(x.split('_')[1])
            )
            self.notifications[oldest_id].dismiss()
        
        # Update manager size to accommodate new notification
        logger.debug(f"MANAGER: Updating manager size for {notification_id}")
        self._update_manager_size()
        
        # Update positioning and ensure manager stays on top
        logger.debug(f"MANAGER: Updating position for {notification_id}")
        self._update_position()
        self.raise_()
        self.activateWindow()  # Ensure top-level window is active
        
        # Show with slide-in animation
        logger.debug(f"MANAGER: Showing notification {notification_id} and starting animation")
        notification.show()
        self._animate_notification_in(notification)
    
    def _remove_notification(self, notification_id: str):
        """
        Remove notification from manager
        
        Args:
            notification_id: ID of notification to remove
        """
        logger.info(f"MANAGER: REMOVING notification {notification_id}")
        logger.debug(f"MANAGER: Notifications before removal: {list(self.notifications.keys())}")
        
        if notification_id in self.notifications:
            del self.notifications[notification_id]
            logger.info(f"MANAGER: Successfully removed {notification_id} from notifications dict")
            logger.debug(f"MANAGER: Notifications after removal: {list(self.notifications.keys())}")
            
            # Update manager size after removing notification
            logger.debug(f"MANAGER: Updating manager size after removing {notification_id}")
            self._update_manager_size()
            logger.debug(f"MANAGER: Updating position after removing {notification_id}")
            self._update_position()
        else:
            logger.warning(f"MANAGER: Attempted to remove non-existent notification {notification_id}")
            logger.debug(f"MANAGER: Available notifications: {list(self.notifications.keys())}")
    
    def _show_error_details(self, error: FSAError, context: dict):
        """
        Show detailed error information dialog
        
        Args:
            error: The FSAError to show details for
            context: Additional context information
        """
        # Use the main parent window instead of the notification manager for proper modal behavior
        parent_for_dialog = self.parent_window if self.parent_window else self
        dialog = ErrorDetailsDialog(error, context, parent_for_dialog)
        dialog.exec()
    
    def _animate_notification_in(self, notification: ErrorNotification):
        """
        Animate notification sliding in from the right
        
        Args:
            notification: Notification to animate
        """
        # Get the notification's current position in the layout
        target_geometry = notification.geometry()
        
        # Start position (off-screen right) - maintain the same height and y position
        start_geometry = QRect(
            self.width(),  # Start off-screen to the right
            target_geometry.y(),  # Keep same vertical position
            target_geometry.width(),  # Keep same width
            target_geometry.height()  # Keep calculated height
        )
        notification.setGeometry(start_geometry)
        
        # Target position (visible) - use the layout's calculated position
        # The layout should have already positioned this correctly
        
        # Animate
        animation = QPropertyAnimation(notification, b"geometry")
        animation.setDuration(250)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.setStartValue(start_geometry)
        animation.setEndValue(target_geometry)
        animation.start()
        
        # Store animation reference to prevent garbage collection
        notification._slide_animation = animation
    
    def _update_position(self):
        """Update manager position using global screen coordinates"""
        logger.debug(f"MANAGER: _update_position called")
        
        if self.parent_window:
            # Get parent window's global position and size
            parent_global_pos = self.parent_window.mapToGlobal(self.parent_window.rect().topLeft())
            parent_rect = self.parent_window.rect()
            margin = 10
            
            logger.debug(f"MANAGER: Parent window global pos: {parent_global_pos}, rect: {parent_rect}")
            
            # Try to get actual menu bar height
            menu_bar_height = 0
            if hasattr(self.parent_window, 'menuBar'):
                menu_bar = self.parent_window.menuBar()
                if menu_bar and menu_bar.isVisible():
                    menu_bar_height = menu_bar.height()
            
            # Fallback to reasonable default if we can't get menu bar height
            if menu_bar_height == 0:
                menu_bar_height = 30
            
            # Calculate global position (top-right corner of parent window)
            global_x = parent_global_pos.x() + parent_rect.width() - self.width() - margin
            global_y = parent_global_pos.y() + menu_bar_height + margin
            
            logger.debug(f"MANAGER: Calculated position: ({global_x}, {global_y})")
            logger.debug(f"MANAGER: Current position: {self.pos()}")
            
            # Move to global screen coordinates
            self.move(global_x, global_y)
            logger.debug(f"MANAGER: Moved to position: {self.pos()}")
    
    def clear_all(self):
        """Clear all active notifications"""
        notification_ids = list(self.notifications.keys())
        for notification_id in notification_ids:
            if notification_id in self.notifications:
                self.notifications[notification_id].dismiss()
    
    def get_notification_count(self) -> int:
        """Get number of active notifications"""
        return len(self.notifications)
    
    def resizeEvent(self, event):
        """Handle resize events to maintain positioning"""
        super().resizeEvent(event)
        self._update_position()