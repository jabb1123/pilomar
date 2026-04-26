#!/usr/bin/env python3
"""Non-blocking keyboard input handling.

This module provides a keyboard scanner class for non-blocking
keyboard input using the curses library.
"""

# This software is published under the GNU General Public License v3.0.

__version__ = "0.1.0"

import curses
import time


class KeyboardScanner:
    """Non-blocking keyboard scanner using a persistent curses session.

    Initialises curses once in ``__init__`` and keeps the screen alive for the
    lifetime of the object.  Call :meth:`close` (or use as a context manager)
    to restore the terminal when done.

    Using a persistent session avoids the overhead of ``curses.wrapper()`` on
    every :meth:`check` call, and enabling ``keypad(True)`` lets curses decode
    multi-byte escape sequences into ``curses.KEY_*`` integer constants so that
    arrow keys are recognised correctly.

    Example::

        with KeyboardScanner() as scanner:
            while True:
                key = scanner.check()
                if key == "esc":
                    break
    """

    def __init__(self):
        """Initialise curses and configure a non-blocking screen."""
        # Initialise curses once — keep the screen alive for all subsequent reads.
        self._stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        self._stdscr.keypad(True)  # decode escape sequences → KEY_* integers
        self._stdscr.nodelay(True)  # getch() returns -1 immediately if no key

        self.current_key_code: int = -1
        self.current_character: str = ""

        # Translation table keyed on *integer* key codes.
        # curses.KEY_UP etc. are ints; control characters are also ints here.
        self.translations: dict[int, str] = {
            9: "tab",
            10: "enter",
            27: "esc",
            curses.KEY_UP: "cursorup",
            curses.KEY_DOWN: "cursordown",
            curses.KEY_RIGHT: "cursorright",
            curses.KEY_LEFT: "cursorleft",
            curses.KEY_F1: "f1",
            curses.KEY_F2: "f2",
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Restore the terminal to its normal state."""
        try:
            curses.nocbreak()
            self._stdscr.keypad(False)
            curses.echo()
            curses.endwin()
        except curses.error:
            pass

    def __enter__(self) -> "KeyboardScanner":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self) -> str:
        """Check for a keypress (non-blocking).

        Returns:
            Translated name for special keys (e.g. ``'cursorup'``), the
            character string for printable keys, or ``''`` if no key was
            pressed.
        """
        self.current_key_code = self._stdscr.getch()
        if self.current_key_code == -1:
            self.current_character = ""
            return ""

        # Named keys (arrow keys, function keys, control characters)
        if self.current_key_code in self.translations:
            self.current_character = self.translations[self.current_key_code]
        else:
            try:
                self.current_character = chr(self.current_key_code)
            except (ValueError, OverflowError):
                self.current_character = ""

        return self.current_character

    def wait_for_keypress(self, timeout: float) -> str:
        """Pause for up to *timeout* seconds, returning any keypress early.

        Keyboard is polled once per second.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            Key pressed, or ``''`` if the timeout elapsed without input.
        """
        keypress = ""
        while keypress == "" and timeout > 0:
            time.sleep(1)
            timeout -= 1
            keypress = self.check()
        return keypress

    def translate(self, key: str) -> str:
        """Pass-through kept for backward compatibility.

        :meth:`check` now returns translated names directly, so this method
        is a no-op for most callers.

        Args:
            key: Key string to look up.

        Returns:
            The same string (translation happens inside :meth:`check`).
        """
        return key

    def string_check(self, translate: bool = False) -> str:  # noqa: ARG002
        """Drain all buffered keypresses into a single string.

        Args:
            translate: Accepted for backward compatibility; ignored because
                :meth:`check` already returns translated names.

        Returns:
            Concatenation of all buffered keypresses.
        """
        keypress = ""
        key = self.check()
        while key != "":
            keypress += key
            key = self.check()
        return keypress

    def flush(self) -> None:
        """Discard any pending keypresses from the buffer."""
        while self.check() != "":
            pass
