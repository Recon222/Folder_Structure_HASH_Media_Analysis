#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Carolina Blue dark theme for the application
"""


class CarolinaBlueTheme:
    """Carolina Blue dark theme stylesheet"""
    
    COLORS = {
        'primary': '#4B9CD3',
        'secondary': '#7BAFD4',
        'background': '#2b2b2b',
        'surface': '#1e1e1e',
        'text': '#ffffff',
        'accent': '#13294B',
        'error': '#ff6b6b',
        'success': '#4B9CD3',
        'hover': '#7BAFD4',
        'pressed': '#13294B',
        'disabled_bg': '#3a3a3a',
        'disabled_text': '#666666'
    }
    
    @staticmethod
    def get_stylesheet() -> str:
        """Return the complete stylesheet"""
        return """
        QMainWindow {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        
        QGroupBox {
            font-weight: bold;
            border: 2px solid #4B9CD3;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
            background-color: #1e1e1e;
            color: #ffffff;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            color: #7BAFD4;
            background-color: #1e1e1e;
        }
        
        QPushButton {
            background-color: #4B9CD3;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            min-width: 100px;
        }
        
        QPushButton:hover {
            background-color: #7BAFD4;
        }
        
        QPushButton:pressed {
            background-color: #13294B;
        }
        
        QPushButton:disabled {
            background-color: #3a3a3a;
            color: #666666;
        }
        
        QLineEdit, QComboBox, QSpinBox, QDateTimeEdit {
            padding: 5px;
            border: 1px solid #4B9CD3;
            border-radius: 3px;
            background-color: #1e1e1e;
            color: #ffffff;
        }
        
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateTimeEdit:focus {
            border: 2px solid #7BAFD4;
            background-color: #252525;
        }
        
        QComboBox::drop-down {
            border: none;
        }
        
        QComboBox::down-arrow {
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid #7BAFD4;
            margin-right: 5px;
        }
        
        QListWidget {
            border: 1px solid #4B9CD3;
            border-radius: 3px;
            background-color: #1e1e1e;
            color: #ffffff;
            selection-background-color: #4B9CD3;
        }
        
        QListWidget::item:selected {
            background-color: #4B9CD3;
            color: #ffffff;
        }
        
        QTextEdit {
            border: 1px solid #4B9CD3;
            border-radius: 3px;
            background-color: #1e1e1e;
            color: #ffffff;
        }
        
        QLabel {
            color: #ffffff;
            background-color: transparent;
        }
        
        QProgressBar {
            border: 1px solid #4B9CD3;
            border-radius: 3px;
            text-align: center;
            background-color: #1e1e1e;
            color: #ffffff;
        }
        
        QProgressBar::chunk {
            background-color: #4B9CD3;
            border-radius: 3px;
        }
        
        QTabWidget::pane {
            border: 1px solid #4B9CD3;
            background-color: #1e1e1e;
        }
        
        QTabBar::tab {
            background-color: #2b2b2b;
            color: #ffffff;
            padding: 8px 16px;
            margin-right: 2px;
            border: 1px solid #4B9CD3;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        
        QTabBar::tab:selected {
            background-color: #4B9CD3;
            color: #ffffff;
        }
        
        QTabBar::tab:!selected {
            margin-top: 2px;
        }
        
        QStatusBar {
            background-color: #13294B;
            color: #ffffff;
            border-top: 1px solid #4B9CD3;
        }
        
        QMenuBar {
            background-color: #1e1e1e;
            color: #ffffff;
            border-bottom: 1px solid #4B9CD3;
        }
        
        QMenuBar::item {
            padding: 5px 10px;
            background-color: transparent;
        }
        
        QMenuBar::item:selected {
            background-color: #4B9CD3;
        }
        
        QMenu {
            background-color: #1e1e1e;
            color: #ffffff;
            border: 1px solid #4B9CD3;
        }
        
        QMenu::item {
            padding: 5px 20px;
        }
        
        QMenu::item:selected {
            background-color: #4B9CD3;
        }
        
        QSplitter::handle {
            background-color: #4B9CD3;
            height: 2px;
        }
        
        QScrollBar:vertical {
            background-color: #1e1e1e;
            width: 12px;
            border: none;
        }
        
        QScrollBar::handle:vertical {
            background-color: #4B9CD3;
            min-height: 20px;
            border-radius: 6px;
        }
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            border: none;
            background: none;
        }
        
        QDateTimeEdit::drop-down {
            border: none;
        }
        
        QDateTimeEdit::down-arrow {
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid #7BAFD4;
            margin-right: 5px;
        }
        
        QCheckBox {
            color: #ffffff;
        }
        
        QCheckBox::indicator {
            width: 13px;
            height: 13px;
            border: 1px solid #4B9CD3;
            background-color: #1e1e1e;
            border-radius: 2px;
        }
        
        QCheckBox::indicator:checked {
            background-color: #4B9CD3;
        }
        
        QDialogButtonBox QPushButton {
            min-width: 80px;
        }
        """