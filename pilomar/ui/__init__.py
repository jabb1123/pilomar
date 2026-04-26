#!/usr/bin/env python3
"""UI module for Pilomar terminal interface.

This module provides classes for terminal-based user interface
components including text formatting, colors, menus, and displays.

Modules:
    keyboard: Non-blocking keyboard input
    text_color: Terminal text formatting and colors
    display: Display components (sprites, windows, fields)
    menu: Interactive menu systems
"""

from .display import (
    BigLetters,
    CdSprite,
    ColorDisplay,
    Field,
    MessageWindow,
)
from .keyboard import KeyboardScanner
from .menu import (
    FileChooser,
    ListChooser,
    Menu,
    OptionMenu,
    ProcedureMenu,
)
from .text_color import TextColor

__all__ = [
    # Keyboard
    "KeyboardScanner",
    # Text formatting
    "TextColor",
    # Display components
    "CdSprite",
    "MessageWindow",
    "BigLetters",
    "Field",
    "ColorDisplay",
    # Menus
    "Menu",
    "ProcedureMenu",
    "OptionMenu",
    "ListChooser",
    "FileChooser",
]
