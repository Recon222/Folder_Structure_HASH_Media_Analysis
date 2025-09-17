#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI Styles package
"""

from .carolina_blue import CarolinaBlueTheme
from .adobe_theme import AdobeTheme, ThemeVariables, QtGradientBuilder, TabStyleIdentity
from .shadow_effects import ShadowEffects, apply_card_shadow, apply_dialog_shadow

__all__ = [
    'CarolinaBlueTheme',
    'AdobeTheme',
    'ThemeVariables',
    'QtGradientBuilder',
    'TabStyleIdentity',
    'ShadowEffects',
    'apply_card_shadow',
    'apply_dialog_shadow'
]