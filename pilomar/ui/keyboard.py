#!/usr/bin/env python3
"""Non-blocking keyboard input handling.

This module provides a keyboard scanner class for non-blocking
keyboard input using the curses library.
"""

# This software is published under the GNU General Public License v3.0.

__version__ = "0.1.0"

import curses
import time
from typing import Dict


class KeyboardScanner:
    """Non-blocking keyboard scanner using curses library.

    Provides non-blocking keyboard input capabilities for terminal applications.

    Example:
        scanner = KeyboardScanner()
        key = scanner.check()
        if key.lower() == 'x':
            break
    """

    def __init__(self):
        """Initialize the keyboard scanner."""
        self.current_key_code = -1
        self.current_character = ""
        self.translations: Dict[str, str] = {
            chr(9): "tab",
            chr(10): "enter",
            chr(27): "esc",
            chr(27) + chr(91) + chr(97): "cursorup",
            chr(27) + chr(91) + chr(98): "cursordown",
            chr(27) + chr(91) + chr(99): "cursorright",
            chr(27) + chr(91) + chr(100): "cursorleft",
            chr(265): "f1",
            chr(267): "f2",
        }

    def _scan(self, stdscr) -> None:
        """Non-blocking check for keypress (internal curses callback).

        Args:
            stdscr: Curses standard screen object
        """
        stdscr.nodelay(True)  # Do not wait for input
        self.current_key_code = stdscr.getch()
        self.current_character = ""
        if self.current_key_code > -1:
            self.current_character = chr(self.current_key_code)

    def wait_for_keypress(self, timeout: float) -> str:
        """Pause for specified time, scanning keyboard.

        Any input will interrupt the delay and be returned.
        Keyboard is checked every second.

        Args:
            timeout: Number of seconds to wait

        Returns:
            Key pressed, or empty string if timeout
        """
        keypress = ""
        while keypress == "" and timeout > 0:
            time.sleep(1)
            timeout -= 1
            keypress = self.check()
        return keypress

    def check(self) -> str:
        """Check for keypress (non-blocking).

        Returns:
            Character pressed, or empty string if none
        """
        curses.wrapper(self._scan)
        return self.current_character

    def translate(self, string: str) -> str:
        """Translate character codes into descriptive text.

        Args:
            string: String of character codes

        Returns:
            Translated string (e.g., code 27 becomes 'esc')
        """
        return self.translations.get(string, string)

    def string_check(self, translate: bool = False) -> str:
        """Non-blocking check for keypress with buffering.

        Concatenates entire queue of keypresses into a single value.

        Args:
            translate: If True, translate character sequences to names

        Returns:
            All buffered keypresses as a string
        """
        keypress = ""
        key = self.check()
        while key != "":
            keypress += key
            key = self.check()
        if translate:
            keypress = self.translate(keypress)
        return keypress

    def flush(self) -> None:
        """Flush any pending keypresses from the buffer."""
        while self.check() != "":
            pass
