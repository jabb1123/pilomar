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

from .keyboard import KeyboardScanner
from .text_color import TextColor
from .display import (
    CdSprite,
    MessageWindow,
    BigLetters,
    Field,
    ColorDisplay,
)
from .menu import (
    Menu,
    ProcedureMenu,
    OptionMenu,
    ListChooser,
    FileChooser,
)

__all__ = [
    # Keyboard
    'KeyboardScanner',
    # Text formatting
    'TextColor',
    # Display components
    'CdSprite',
    'MessageWindow',
    'BigLetters',
    'Field',
    'ColorDisplay',
    # Menus
    'Menu',
    'ProcedureMenu',
    'OptionMenu',
    'ListChooser',
    'FileChooser',
]

# Backward compatibility aliases
keyboardscanner = KeyboardScanner
textcolor = TextColor
cdsprite = CdSprite
messagewindow = MessageWindow
bigletters = BigLetters
field = Field
colordisplay = ColorDisplay
menu = Menu
proceduremenu = ProcedureMenu
optionmenu = OptionMenu
listchooser = ListChooser
filechooser = FileChooser
