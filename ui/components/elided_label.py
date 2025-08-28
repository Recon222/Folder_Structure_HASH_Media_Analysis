#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elided Label - QLabel that truncates text with ellipsis when too long
Prevents UI expansion caused by long file paths and dynamic text content
"""

from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QFontMetrics


class ElidedLabel(QLabel):
    """
    Label that elides (truncates) text with ellipsis when content is too long.
    
    Features:
    - Prevents window/widget expansion due to long text
    - Shows full text in tooltip automatically
    - Supports different elide modes (middle, left, right)
    - Configurable maximum width
    - Maintains proper size hints for layout management
    """
    
    def __init__(self, text="", max_width=400, elide_mode=Qt.ElideMiddle, parent=None):
        """
        Initialize elided label.
        
        Args:
            text: Initial text to display
            max_width: Maximum width in pixels (default 400)
            elide_mode: Where to place ellipsis (Qt.ElideMiddle, Qt.ElideRight, Qt.ElideLeft)
            parent: Parent widget
        """
        super().__init__(text, parent)
        
        self._full_text = text
        self._max_width = max_width
        self._elide_mode = elide_mode
        
        # Configure size policy to prevent expansion
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMaximumWidth(max_width)
        self.setMinimumWidth(50)  # Reasonable minimum for "..."
        
        # Set tooltip to show full text
        if text:
            self.setToolTip(text)
        
    def setText(self, text):
        """Override setText to store full text and update tooltip"""
        self._full_text = str(text) if text is not None else ""
        
        # Set tooltip to show full text
        if self._full_text:
            self.setToolTip(self._full_text)
        else:
            self.setToolTip("")
            
        # Let Qt handle the display - paintEvent will elide as needed
        super().setText(self._full_text)
        self.update()  # Trigger repaint
        
    def paintEvent(self, event):
        """Custom paint to show elided text"""
        painter = QPainter(self)
        
        try:
            # Get font metrics for current font
            metrics = QFontMetrics(self.font())
            
            # Calculate available width (leave small margin)
            available_width = self.width() - 6  # 3px margin on each side
            
            if available_width <= 0:
                return
            
            # Get elided text for current width
            elided_text = metrics.elidedText(
                self._full_text,
                self._elide_mode,
                available_width
            )
            
            # Draw the elided text with proper alignment
            text_rect = self.rect().adjusted(3, 0, -3, 0)  # Apply margin
            painter.drawText(text_rect, self.alignment(), elided_text)
            
        finally:
            painter.end()
    
    def sizeHint(self):
        """Provide size hint that respects maximum width"""
        hint = super().sizeHint()
        # Limit width to maximum, but preserve height
        hint.setWidth(min(hint.width(), self._max_width))
        return hint
    
    def minimumSizeHint(self):
        """Provide minimum size hint for ellipsis"""
        metrics = QFontMetrics(self.font())
        ellipsis_width = metrics.horizontalAdvance("...")
        min_width = max(50, ellipsis_width + 10)  # Ellipsis + small margin
        
        hint = super().minimumSizeHint()
        hint.setWidth(min_width)
        return hint
    
    def setMaxWidth(self, width):
        """Update maximum width"""
        self._max_width = width
        self.setMaximumWidth(width)
        self.update()
    
    def setElideMode(self, mode):
        """Update elide mode"""
        self._elide_mode = mode
        self.update()
    
    def getFullText(self):
        """Get the full, unelided text"""
        return self._full_text


class PathLabel(ElidedLabel):
    """
    Specialized elided label for displaying file paths.
    Uses middle elision and path-appropriate styling.
    """
    
    def __init__(self, path="", max_width=400, parent=None):
        # Use middle elision for paths - preserves filename and root
        super().__init__(str(path), max_width, Qt.ElideMiddle, parent)
        
        # Apply subtle styling for path display
        self.setStyleSheet("""
            QLabel {
                color: #555555;
                font-family: 'Consolas', 'Monaco', monospace;
                padding: 2px 4px;
                background-color: #F8F8F8;
                border: 1px solid #E0E0E0;
                border-radius: 3px;
            }
        """)