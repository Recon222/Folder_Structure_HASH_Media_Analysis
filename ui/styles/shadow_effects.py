#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shadow Effects utility for Qt widgets.
Provides Adobe-quality depth and elevation to UI components.
"""

from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QColor
from typing import Optional, Tuple


class ShadowEffects:
    """Reusable shadow effects for creating depth in the UI"""

    @staticmethod
    def apply_drop_shadow(
        widget: QWidget,
        blur_radius: int = 8,
        offset: Tuple[int, int] = (0, 2),
        color: str = "#000000",
        opacity: float = 0.25
    ) -> QGraphicsDropShadowEffect:
        """
        Apply a drop shadow to any widget.

        Args:
            widget: Widget to apply shadow to
            blur_radius: Shadow blur amount (default 8)
            offset: Shadow offset as (x, y) tuple (default (0, 2))
            color: Shadow color (default black)
            opacity: Shadow opacity 0-1 (default 0.25)

        Returns:
            The shadow effect instance for further customization
        """
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(blur_radius)
        shadow.setXOffset(offset[0])
        shadow.setYOffset(offset[1])

        # Set color with opacity
        shadow_color = QColor(color)
        shadow_color.setAlphaF(opacity)
        shadow.setColor(shadow_color)

        widget.setGraphicsEffect(shadow)
        return shadow

    @staticmethod
    def elevated_card(widget: QWidget, elevation: int = 1) -> Optional[QGraphicsDropShadowEffect]:
        """
        Apply Material Design-inspired elevation to a widget.

        Args:
            widget: Widget to elevate
            elevation: Elevation level 1-5 (1=subtle, 5=floating)

        Returns:
            Shadow effect or None if invalid elevation
        """
        elevations = {
            1: (4, (0, 1), 0.15),    # Subtle shadow for cards
            2: (8, (0, 2), 0.20),     # Standard elevation
            3: (12, (0, 3), 0.25),    # Raised elements
            4: (16, (0, 4), 0.30),    # Modal/dialog shadow
            5: (20, (0, 6), 0.35)     # High elevation/floating
        }

        if elevation not in elevations:
            return None

        blur, offset, opacity = elevations[elevation]
        return ShadowEffects.apply_drop_shadow(
            widget, blur, offset, "#000000", opacity
        )

    @staticmethod
    def glow_effect(
        widget: QWidget,
        color: str = "#4B9CD3",
        blur: int = 15,
        opacity: float = 0.5
    ) -> QGraphicsDropShadowEffect:
        """
        Apply a glow effect for focus states or highlights.

        Args:
            widget: Widget to apply glow to
            color: Glow color (default Carolina Blue)
            blur: Glow blur radius (default 15)
            opacity: Glow opacity (default 0.5)

        Returns:
            The glow effect instance
        """
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(blur)
        glow.setXOffset(0)
        glow.setYOffset(0)

        glow_color = QColor(color)
        glow_color.setAlphaF(opacity)
        glow.setColor(glow_color)

        widget.setGraphicsEffect(glow)
        return glow

    @staticmethod
    def subtle_inset(widget: QWidget) -> QGraphicsDropShadowEffect:
        """
        Create an inset/sunken appearance for input fields.

        Args:
            widget: Widget to apply inset shadow to

        Returns:
            Shadow effect configured for inset appearance
        """
        # Note: Qt doesn't support true inset shadows,
        # but we can simulate with minimal top shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(3)
        shadow.setXOffset(0)
        shadow.setYOffset(-1)

        shadow_color = QColor("#000000")
        shadow_color.setAlphaF(0.1)
        shadow.setColor(shadow_color)

        widget.setGraphicsEffect(shadow)
        return shadow


class DynamicShadowWidget(QWidget):
    """
    Widget base class with dynamic shadow that responds to hover.
    Provides Adobe-like interactive depth.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.base_elevation = 1
        self.hover_elevation = 2
        self.current_shadow = None
        self.setup_shadow()

    def setup_shadow(self):
        """Initialize the base shadow"""
        self.current_shadow = ShadowEffects.elevated_card(self, self.base_elevation)

    def enterEvent(self, event):
        """Elevate on hover"""
        if self.current_shadow:
            self.current_shadow.deleteLater()
        self.current_shadow = ShadowEffects.elevated_card(self, self.hover_elevation)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Return to base elevation"""
        if self.current_shadow:
            self.current_shadow.deleteLater()
        self.current_shadow = ShadowEffects.elevated_card(self, self.base_elevation)
        super().leaveEvent(event)

    def set_elevations(self, base: int, hover: int):
        """
        Configure base and hover elevation levels.

        Args:
            base: Base elevation (1-5)
            hover: Hover elevation (1-5)
        """
        self.base_elevation = max(1, min(5, base))
        self.hover_elevation = max(1, min(5, hover))
        self.setup_shadow()


class AnimatedShadow:
    """
    Animated shadow transitions for smooth elevation changes.
    Note: Qt limitations mean we simulate animation through blur radius changes.
    """

    def __init__(self, widget: QWidget):
        self.widget = widget
        self.shadow = QGraphicsDropShadowEffect()
        self._blur_radius = 8
        self.shadow.setXOffset(0)
        self.shadow.setYOffset(2)
        self.shadow.setColor(QColor(0, 0, 0, 64))
        widget.setGraphicsEffect(self.shadow)

        # Animation setup
        self.animation = QPropertyAnimation(self, b"blur_radius")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    def get_blur_radius(self) -> int:
        return self._blur_radius

    def set_blur_radius(self, value: int):
        self._blur_radius = value
        self.shadow.setBlurRadius(value)
        # Also animate offset for more realistic elevation
        offset_ratio = value / 20  # Scale offset with blur
        self.shadow.setYOffset(2 + offset_ratio * 4)

    # Qt property for animation
    blur_radius = Property(int, get_blur_radius, set_blur_radius)

    def animate_to_elevation(self, elevation: int):
        """
        Animate shadow to match elevation level.

        Args:
            elevation: Target elevation (1-5)
        """
        blur_values = {1: 4, 2: 8, 3: 12, 4: 16, 5: 20}
        target_blur = blur_values.get(elevation, 8)

        self.animation.stop()
        self.animation.setStartValue(self._blur_radius)
        self.animation.setEndValue(target_blur)
        self.animation.start()


# Convenience functions for common shadow needs
def apply_card_shadow(widget: QWidget) -> QGraphicsDropShadowEffect:
    """Apply standard card shadow to a widget"""
    return ShadowEffects.elevated_card(widget, 2)


def apply_dialog_shadow(widget: QWidget) -> QGraphicsDropShadowEffect:
    """Apply dialog/modal shadow to a widget"""
    return ShadowEffects.elevated_card(widget, 4)


def apply_button_shadow(widget: QWidget) -> QGraphicsDropShadowEffect:
    """Apply subtle button shadow"""
    return ShadowEffects.apply_drop_shadow(
        widget,
        blur_radius=4,
        offset=(0, 1),
        opacity=0.2
    )


def apply_focus_glow(widget: QWidget, color: str = "#4B9CD3") -> QGraphicsDropShadowEffect:
    """Apply focus glow to a widget"""
    return ShadowEffects.glow_effect(widget, color, blur=12, opacity=0.4)