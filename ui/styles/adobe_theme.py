#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adobe-style professional dark theme for the application.
Implements variable system, gradient builder, and cohesive design language.
"""

from typing import Dict, List, Tuple, Optional
import math


class ThemeVariables:
    """Centralized theme variable management for consistent styling"""

    def __init__(self, theme_name="dark_professional"):
        self.themes = {
            "dark_professional": {
                # Core colors - matching Adobe CEP panel aesthetic
                "primary": "#4B9CD3",           # Carolina Blue
                "primary_hover": "#5BA3D8",     # Lighter on hover
                "primary_pressed": "#3A8CC3",   # Darker when pressed

                # Backgrounds - layered depth
                "background": "#262626",        # Main window background
                "surface": "#323232",           # Panel/card background
                "surface_raised": "#3a3a3a",    # Elevated surfaces
                "surface_sunken": "#1e1e1e",    # Recessed areas (inputs, logs)

                # Text hierarchy
                "text_primary": "#e8e8e8",      # Main text
                "text_secondary": "#b4b4b4",    # Secondary/muted text
                "text_disabled": "#6b6b6b",     # Disabled state

                # Borders and dividers
                "border_subtle": "#3a3a3a",     # Subtle borders
                "border_strong": "#4a4a4a",     # Prominent borders
                "border_focus": "#4B9CD3",      # Focus indicator

                # Status colors - professional palette
                "success": "#52c41a",           # Success green
                "warning": "#faad14",           # Warning amber
                "error": "#ff4d4f",             # Error red
                "info": "#1890ff",              # Info blue

                # Component specific
                "button_gradient_start": "#3e3e3e",
                "button_gradient_end": "#323232",
                "button_hover_start": "#4a4a4a",
                "button_hover_end": "#3e3e3e",

                # Spacing and sizing
                "border_radius": "4px",
                "border_radius_large": "6px",
                "spacing_unit": "8px",
                "transition_speed": "200ms"
            }
        }

        self.current_theme = theme_name
        self.vars = self.themes[theme_name]

    def get(self, key: str, default: str = "") -> str:
        """Get a theme variable value"""
        return self.vars.get(key, default)

    def compile_stylesheet(self, template: str) -> str:
        """Replace ${variable} patterns with actual values"""
        compiled = template
        for key, value in self.vars.items():
            placeholder = f"${{{key}}}"
            compiled = compiled.replace(placeholder, value)
        return compiled


class QtGradientBuilder:
    """Generate Qt-compatible gradient strings with Adobe-quality aesthetics"""

    @staticmethod
    def linear_gradient(
        stops: List[Tuple[float, str]],
        angle: int = 180,
        spread: str = "pad"
    ) -> str:
        """
        Create a Qt linear gradient string.

        Args:
            stops: List of (position, color) tuples
            angle: Gradient angle in degrees (0=top-to-bottom, 90=left-to-right)
            spread: Spread method (pad, reflect, repeat)
        """
        # Convert angle to Qt coordinates
        rad = math.radians(angle - 90)  # Qt uses different angle reference
        x1, y1 = 0.5, 0.5  # Center start
        x2 = 0.5 + math.cos(rad) * 0.5
        y2 = 0.5 + math.sin(rad) * 0.5

        # Clamp values
        x1, y1, x2, y2 = [max(0, min(1, v)) for v in [x1, y1, x2, y2]]

        # Build gradient string
        gradient = f"qlineargradient(spread:{spread}, x1:{x1:.2f}, y1:{y1:.2f}, x2:{x2:.2f}, y2:{y2:.2f}"

        for position, color in stops:
            gradient += f", stop:{position:.2f} {color}"

        gradient += ")"
        return gradient

    @staticmethod
    def vertical_gradient(color_top: str, color_bottom: str) -> str:
        """Simple vertical gradient helper"""
        return QtGradientBuilder.linear_gradient(
            [(0, color_top), (1, color_bottom)],
            angle=180
        )

    @staticmethod
    def subtle_glossy(base_color: str, highlight_color: str) -> str:
        """Create a subtle glossy effect like Adobe panels"""
        return QtGradientBuilder.linear_gradient([
            (0, highlight_color),
            (0.48, base_color),
            (0.52, base_color),
            (1, base_color)
        ], angle=180)


class TabStyleIdentity:
    """Lightweight style identity system for tabs"""

    # Professional monochromatic approach - let actions speak through subtle differences
    BASE_BUTTON = {
        "default": "#3e3e3e",
        "hover": "#4a4a4a",
        "pressed": "#323232"
    }

    # Subtle accents for different action types
    BUTTON_ACCENTS = {
        "primary": {"border": "#4B9CD3", "glow": "rgba(75, 156, 211, 0.3)"},
        "danger": {"border": "#ff4d4f", "glow": "rgba(255, 77, 79, 0.3)"},
        "success": {"border": "#52c41a", "glow": "rgba(82, 196, 26, 0.3)"},
        "warning": {"border": "#faad14", "glow": "rgba(250, 173, 20, 0.3)"}
    }

    @staticmethod
    def get_tab_identity(tab_name: str) -> Dict:
        """Get style identity for a specific tab"""
        identities = {
            "forensic": {
                "name": "forensic",
                "primary_accent": "#4B9CD3",
                "section_headers": True,
                "uses_templates": True
            },
            "batch": {
                "name": "batch",
                "primary_accent": "#4B9CD3",  # Unified with main theme
                "queue_cards": True,
                "status_badges": True
            },
            "hashing": {
                "name": "hashing",
                "primary_accent": "#4B9CD3",
                "requires_monospace": True,
                "technical_display": True
            },
            "copy_verify": {
                "name": "copy_verify",
                "primary_accent": "#4B9CD3",
                "progress_prominent": True
            },
            "media_analysis": {
                "name": "media_analysis",
                "primary_accent": "#4B9CD3",
                "map_integration": True,
                "thumbnail_display": True
            }
        }
        return identities.get(tab_name, {})


class AdobeTheme:
    """Main theme class combining all styling elements"""

    def __init__(self):
        self.variables = ThemeVariables()
        self.gradients = QtGradientBuilder()
        self.identities = TabStyleIdentity()

    def get_stylesheet(self) -> str:
        """Generate the complete Adobe-inspired stylesheet"""

        # Build the comprehensive stylesheet
        return f"""
        /* ========================================
           Adobe-Inspired Professional Theme
           ======================================== */

        /* Main Window & Base */
        QMainWindow {{
            background-color: {self.variables.get('background')};
            color: {self.variables.get('text_primary')};
        }}

        QWidget {{
            background-color: {self.variables.get('background')};
            color: {self.variables.get('text_primary')};
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 11px;
        }}

        /* Tabs - Clean Adobe-style */
        QTabWidget::pane {{
            background-color: {self.variables.get('surface')};
            border: 1px solid {self.variables.get('border_subtle')};
            border-radius: {self.variables.get('border_radius')};
            margin-top: -1px;
        }}

        QTabBar::tab {{
            background: {self.gradients.vertical_gradient('#3a3a3a', '#323232')};
            color: {self.variables.get('text_secondary')};
            padding: 8px 16px;
            margin-right: 2px;
            border: 1px solid {self.variables.get('border_subtle')};
            border-bottom: none;
            border-top-left-radius: {self.variables.get('border_radius')};
            border-top-right-radius: {self.variables.get('border_radius')};
            font-weight: 500;
        }}

        QTabBar::tab:selected {{
            background: {self.variables.get('surface')};
            color: {self.variables.get('text_primary')};
            border-color: {self.variables.get('border_strong')};
            border-bottom: 1px solid {self.variables.get('surface')};
        }}

        QTabBar::tab:hover:!selected {{
            background: {self.gradients.vertical_gradient('#424242', '#3a3a3a')};
            color: {self.variables.get('text_primary')};
        }}

        /* Group Boxes - Section styling like CEP panels */
        QGroupBox {{
            background-color: {self.variables.get('surface')};
            border: 1px solid {self.variables.get('border_subtle')};
            border-radius: {self.variables.get('border_radius')};
            margin-top: 12px;
            padding-top: 12px;
            font-weight: 600;
            font-size: 11px;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 8px;
            color: {self.variables.get('text_primary')};
            background-color: {self.variables.get('surface')};
        }}

        /* Buttons - Professional gradient style */
        QPushButton {{
            background: {self.gradients.vertical_gradient('#3e3e3e', '#323232')};
            color: {self.variables.get('text_primary')};
            border: 1px solid {self.variables.get('border_subtle')};
            border-radius: {self.variables.get('border_radius')};
            padding: 6px 16px;
            font-weight: 500;
            min-height: 24px;
            min-width: 80px;
        }}

        QPushButton:hover {{
            background: {self.gradients.vertical_gradient('#4a4a4a', '#3e3e3e')};
            border-color: {self.variables.get('border_strong')};
        }}

        QPushButton:pressed {{
            background: {self.gradients.vertical_gradient('#323232', '#2a2a2a')};
            padding-top: 7px;
            padding-bottom: 5px;
        }}

        QPushButton:disabled {{
            background: {self.variables.get('surface')};
            color: {self.variables.get('text_disabled')};
            border-color: {self.variables.get('border_subtle')};
        }}

        /* Primary action buttons - subtle accent */
        QPushButton#primaryAction {{
            border-color: {self.variables.get('primary')};
            background: {self.gradients.vertical_gradient('#3e4e5e', '#323842')};
        }}

        QPushButton#primaryAction:hover {{
            background: {self.gradients.vertical_gradient('#4a5a6a', '#3e4e5e')};
            border-color: {self.variables.get('primary_hover')};
        }}

        /* Input fields - sunken appearance */
        QLineEdit, QComboBox, QSpinBox, QDateTimeEdit {{
            background-color: {self.variables.get('surface_sunken')};
            color: {self.variables.get('text_primary')};
            border: 1px solid {self.variables.get('border_subtle')};
            border-radius: {self.variables.get('border_radius')};
            padding: 5px 8px;
            selection-background-color: {self.variables.get('primary')};
            selection-color: white;
        }}

        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateTimeEdit:focus {{
            border-color: {self.variables.get('border_focus')};
            background-color: #1a1a1a;
        }}

        /* ComboBox styling */
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}

        QComboBox::down-arrow {{
            image: none;
            border-style: solid;
            border-width: 4px;
            border-color: transparent;
            border-top-color: {self.variables.get('text_secondary')};
            margin-right: 6px;
            margin-top: 4px;
        }}

        QComboBox:hover::down-arrow {{
            border-top-color: {self.variables.get('text_primary')};
        }}

        /* List widgets */
        QListWidget {{
            background-color: {self.variables.get('surface_sunken')};
            color: {self.variables.get('text_primary')};
            border: 1px solid {self.variables.get('border_subtle')};
            border-radius: {self.variables.get('border_radius')};
            outline: none;
        }}

        QListWidget::item {{
            padding: 4px;
            border: none;
        }}

        QListWidget::item:selected {{
            background-color: {self.variables.get('primary')};
            color: white;
        }}

        QListWidget::item:hover:!selected {{
            background-color: {self.variables.get('surface_raised')};
        }}

        /* Text Edit / Log Console */
        QTextEdit, QPlainTextEdit {{
            background-color: {self.variables.get('surface_sunken')};
            color: {self.variables.get('text_primary')};
            border: 1px solid {self.variables.get('border_subtle')};
            border-radius: {self.variables.get('border_radius')};
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 10px;
            selection-background-color: {self.variables.get('primary')};
            selection-color: white;
        }}

        /* Progress bars */
        QProgressBar {{
            background-color: {self.variables.get('surface_sunken')};
            border: 1px solid {self.variables.get('border_subtle')};
            border-radius: {self.variables.get('border_radius')};
            text-align: center;
            color: {self.variables.get('text_primary')};
            min-height: 20px;
        }}

        QProgressBar::chunk {{
            background: {self.gradients.linear_gradient(
                [(0, '#5BA3D8'), (1, '#4B9CD3')],
                angle=90
            )};
            border-radius: 3px;
        }}

        /* Scrollbars - minimal style */
        QScrollBar:vertical {{
            background-color: {self.variables.get('surface')};
            width: 12px;
            border: none;
        }}

        QScrollBar::handle:vertical {{
            background-color: {self.variables.get('surface_raised')};
            border-radius: 6px;
            min-height: 30px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {self.variables.get('border_strong')};
        }}

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical,
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: none;
            border: none;
        }}

        /* Horizontal scrollbar */
        QScrollBar:horizontal {{
            background-color: {self.variables.get('surface')};
            height: 12px;
            border: none;
        }}

        QScrollBar::handle:horizontal {{
            background-color: {self.variables.get('surface_raised')};
            border-radius: 6px;
            min-width: 30px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background-color: {self.variables.get('border_strong')};
        }}

        /* Labels */
        QLabel {{
            color: {self.variables.get('text_primary')};
            background-color: transparent;
        }}

        QLabel#sectionHeader {{
            color: {self.variables.get('text_primary')};
            font-weight: 600;
            font-size: 12px;
            padding: 4px 0;
        }}

        QLabel#mutedText {{
            color: {self.variables.get('text_secondary')};
        }}

        /* Status bar */
        QStatusBar {{
            background-color: {self.variables.get('surface')};
            color: {self.variables.get('text_secondary')};
            border-top: 1px solid {self.variables.get('border_subtle')};
            font-size: 10px;
        }}

        /* Menu bar */
        QMenuBar {{
            background-color: {self.variables.get('surface')};
            color: {self.variables.get('text_primary')};
            border-bottom: 1px solid {self.variables.get('border_subtle')};
        }}

        QMenuBar::item {{
            padding: 4px 10px;
            background-color: transparent;
        }}

        QMenuBar::item:selected {{
            background-color: {self.variables.get('surface_raised')};
        }}

        QMenu {{
            background-color: {self.variables.get('surface')};
            color: {self.variables.get('text_primary')};
            border: 1px solid {self.variables.get('border_strong')};
            padding: 4px;
        }}

        QMenu::item {{
            padding: 6px 20px;
            border-radius: 3px;
        }}

        QMenu::item:selected {{
            background-color: {self.variables.get('primary')};
            color: white;
        }}

        QMenu::separator {{
            height: 1px;
            background-color: {self.variables.get('border_subtle')};
            margin: 4px 10px;
        }}

        /* Checkboxes */
        QCheckBox {{
            color: {self.variables.get('text_primary')};
            spacing: 8px;
        }}

        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {self.variables.get('border_strong')};
            border-radius: 3px;
            background-color: {self.variables.get('surface_sunken')};
        }}

        QCheckBox::indicator:checked {{
            background-color: {self.variables.get('primary')};
            border-color: {self.variables.get('primary')};
        }}

        QCheckBox::indicator:checked:hover {{
            background-color: {self.variables.get('primary_hover')};
            border-color: {self.variables.get('primary_hover')};
        }}

        /* Radio buttons */
        QRadioButton {{
            color: {self.variables.get('text_primary')};
            spacing: 8px;
        }}

        QRadioButton::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {self.variables.get('border_strong')};
            border-radius: 8px;
            background-color: {self.variables.get('surface_sunken')};
        }}

        QRadioButton::indicator:checked {{
            background-color: {self.variables.get('primary')};
            border-color: {self.variables.get('primary')};
        }}

        /* Splitters - invisible like Adobe panels */
        QSplitter::handle {{
            background-color: transparent;
            height: 2px;
            width: 2px;
        }}

        QSplitter::handle:hover {{
            background-color: {self.variables.get('border_strong')};
        }}

        /* Tool tips */
        QToolTip {{
            background-color: {self.variables.get('surface_raised')};
            color: {self.variables.get('text_primary')};
            border: 1px solid {self.variables.get('border_strong')};
            border-radius: {self.variables.get('border_radius')};
            padding: 4px 8px;
        }}

        /* Dialog button box */
        QDialogButtonBox QPushButton {{
            min-width: 80px;
        }}

        /* Headers in tables/trees */
        QHeaderView::section {{
            background-color: {self.variables.get('surface')};
            color: {self.variables.get('text_secondary')};
            border: none;
            border-bottom: 1px solid {self.variables.get('border_subtle')};
            padding: 6px;
            font-weight: 600;
        }}
        """