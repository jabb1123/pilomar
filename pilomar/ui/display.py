#!/usr/bin/env python3
"""Display classes for terminal UI components.

This module provides classes for creating terminal-based display
elements including sprites, message windows, and color displays.

Classes:
    CdSprite: Moveable sprite for color displays
    MessageWindow: Simple scrolling text window (deprecated)
    BigLetters: Large text rendering
    Field: Display field with formatting
    ColorDisplay: Full-featured terminal display buffer
"""

# This software is published under the GNU General Public License v3.0.

__version__ = "0.1.0"

import json
from datetime import datetime

from pilomar.ui.menu import ProcedureMenu

from .text_color import TextColor


class CdSprite:
    """This is a subclass of the ColorDisplay class.
    It represents 'sprites' that can be defined to move across the ColorDisplay buffer.
    Originally intended to create moving markers against a set background grid."""

    __version__ = "0.0.1"

    def __init__(self, name, symbol, row=None, col=None, fg=0, bg=15, level=0):
        self.row = row
        self.column = col
        self.fg = fg
        self.bg = bg
        self.symbol = symbol
        self.name = name
        self.display = False
        self.level = level

    def colored_symbol(self):
        """Return symbol with embedded terminal colour codes set."""
        result = result = TextColor.fgbgcolor(self.fg, self.bg, self.symbol)
        return result

    def label(self, color=False):
        """Return colour coded label for the sprite.
        Used in the key to a display.
        color=False means color is not set, plaintext is returned instead."""
        if color:
            result = TextColor.fgbgcolor(self.fg, self.bg, self.symbol)
        else:
            result = self.symbol
        result += " = " + self.name
        return result


# --------------------------------------------------------------------------------------------------------------------------------


class MessageWindow:
    """Class to create a simple scrolling text window and to display on the terminal as needed.
    Superceded by ColorDisplay class now - which contains all same functionalities."""

    __version__ = "0.0.1"

    def __init__(self, rows, columns, row=None, col=None, fg=15, bg=0, title=None):
        print(
            TextColor.red(
                "TextColor.messagewindow(): Deprecated in favour of TextColor.ColorDisplay()."
            )
        )
        # How many rows deep is the display?
        self.display_rows = rows
        # How many columns wide is the display?
        self.display_columns = columns
        # What's the location of the 1st cell in the display on the actual terminal?
        self.display_row = row
        self.display_col = col
        # Location of the last row in the display.
        if row is None:
            self.last_display_row = None
        else:
            self.last_display_row = row + rows - 1
        # Location of the last column in the display.
        if col is None:
            self.last_display_col = None
        else:
            self.last_display_col = col + columns - 1
        # What's the default foreground colour?
        self.default_fg = fg
        # What's the default background colour?
        self.default_bg = bg
        self.default_char = " "
        self.lines = []
        # Is there a title to the window? (Will keep 1st row static)
        self.title = title
        if self.title is not None:
            # Occupy the first line of the display, because the title will overwrite it.
            self.lines.append(" ")
            # Title cannot exceed window width.
            if len(self.title) > self.display_columns:
                self.title = self.title[: self.display_columns]
        # Long text will wrap onto multiple lines.
        self.wrap = True
        # Can store handle to a 'Log' method for logging messages.
        # Needs to be defined and assigned by the calling program.
        self.log = None
        # Can specify how quickly the display refreshes (in seconds).
        self.refresh_rate = None
        self.last_refresh = None  # When did the display last update?

    def set_refresh_rate(self, rate):
        """Set selected refresh rate and reset the refresh timer."""
        self.refresh_rate = rate
        self.last_refresh = None

    def refresh_due(self):
        """Return True if refresh is due, else False."""
        result = False
        if self.refresh_rate is None:
            result = True  # There's no restriction so always refresh.
        elif self.last_refresh is None:
            result = True  # Need to do initial drawing.
        elif (datetime.now() - self.last_refresh).total_seconds() >= self.refresh_rate:
            result = True  # Refresh is due.
        return result

    def clear(self, immediate=False):
        """Clear the window."""
        self.lines = []
        if self.title is not None:
            self.lines.append(" ")
        if immediate:
            self.display()

    def display(self, screenheight=None, screenwidth=None, immediate=False):
        """Display the window.
        If specific location has been given for the window AND the current screen size is given in screenheight/screenwidth
        this can check that the space exists in the current display size. It will only draw the window if there is enough space.
        """
        if not immediate and not self.refresh_due():
            # Don't perform a refresh yet.
            return
        # We have a specific location to use,
        # check if that location is in the current display dimensions.
        if self.last_display_row is not None and screenheight is not None:
            # Not enough height.
            if screenheight < self.last_display_row:
                return  # Don't try to display.
        if self.last_display_col is not None and screenwidth is not None:
            # Not enough width.
            if screenwidth < self.last_display_col:
                return  # Don't try to display.
        for r in range(self.display_rows):
            if len(self.lines) >= r + 1:
                line = self.lines[r]
            else:
                line = " "
            if r == 0 and self.title is not None:
                line = self.title  # 1st row is always the 'title' if specified.
                line = TextColor.fgbgcolor(
                    self.default_bg,
                    self.default_fg,
                    line.ljust(self.display_columns, " "),
                )
            else:
                line = TextColor.fgbgcolor(
                    self.default_fg,
                    self.default_bg,
                    line.ljust(self.display_columns, " "),
                )
            if self.display_row is not None and self.display_col is not None:
                # The display has a specific location on the terminal window. Place it there.
                dr = self.display_row + r
                dc = self.display_col
                line = TextColor.cursor(dc, dr) + line
            print(line)
        self.last_refresh = datetime.now()

    def print(self, *args):
        line = ""
        for i in args:
            if len(line) > 0:
                line += " "
            line += str(i)
        # Don't wrap text, just truncate if it is wider than display.
        if not self.wrap:
            line = line[: self.display_columns]  # Truncate the line.
        # Wrap long text onto multiple display lines.
        else:
            while len(line) > 0:
                self.lines.append(line[: self.display_columns])
                if len(line) > self.display_columns:
                    # Remainder of text not yet displayed.
                    line = line[self.display_columns :]
                else:
                    # Nothing left to display.
                    line = ""
        while len(self.lines) > self.display_rows:
            # temp = self.lines.pop(0)
            self.lines.pop(0)


# --------------------------------------------------------------------------------------------------------------------------------


class BigLetters:
    """Primitive large font sizes."""

    def __init__(self):
        self.letter_dictionary: dict[str, list[str]] = {}
        self.initialise_ld()

    def initialise_ld(self):
        """Initialise the letter dictionary with patterns for each character."""
        self.letter_dictionary = {}
        self.letter_dictionary["unknown"] = [
            "#####",
            "# # #",
            "## ##",
            "# # #",
            "#####",
        ]
        self.letter_dictionary[" "] = ["     ", "     ", "     ", "     ", "     "]
        self.letter_dictionary['"'] = [" # # ", " # # ", "     ", "     ", "     "]
        self.letter_dictionary["'"] = ["  #  ", "  #  ", "     ", "     ", "     "]
        self.letter_dictionary["0"] = ["#####", "#  ##", "# # #", "##  #", "#####"]
        self.letter_dictionary["1"] = ["   # ", "  ## ", "   # ", "   # ", " ####"]
        self.letter_dictionary["2"] = ["#####", "    #", "#####", "#    ", "#####"]
        self.letter_dictionary["3"] = ["#####", "    #", "#####", "    #", "#####"]
        self.letter_dictionary["4"] = ["#   #", "#   #", "#####", "    #", "    #"]
        self.letter_dictionary["5"] = ["#####", "#    ", "#####", "    #", "#####"]
        self.letter_dictionary["6"] = ["#####", "#    ", "#####", "#   #", "#####"]
        self.letter_dictionary["7"] = ["#####", "    #", "    #", "    #", "    #"]
        self.letter_dictionary["8"] = ["#####", "#   #", "#####", "#   #", "#####"]
        self.letter_dictionary["9"] = ["#####", "#   #", "#####", "    #", "    #"]
        self.letter_dictionary["."] = ["     ", "     ", "     ", "     ", "  #  "]
        self.letter_dictionary[","] = ["     ", "     ", "     ", "  ## ", "   # "]
        self.letter_dictionary[":"] = ["     ", "  #  ", "     ", "  #  ", "     "]
        self.letter_dictionary["!"] = ["  #  ", "  #  ", "  #  ", "     ", "  #  "]
        self.letter_dictionary["-"] = ["     ", "     ", " ### ", "     ", "     "]
        self.letter_dictionary["+"] = ["     ", "  #  ", " ### ", "  #  ", "     "]
        self.letter_dictionary["*"] = ["  #  ", "# # #", " ### ", " # # ", "#   #"]
        self.letter_dictionary["="] = ["     ", " ### ", "     ", " ### ", "     "]
        self.letter_dictionary["?"] = [" ### ", "#   #", "  ## ", "     ", "  #  "]

    def get_letter(self, letter):
        """Return letter pattern."""
        if letter in self.letter_dictionary:
            return self.letter_dictionary[letter]
        else:
            return self.letter_dictionary["unknown"]

    def generate_text(self, originaltext):
        """Given original text, generate the BigLetters version of it."""
        lines = [[] for i in range(5)]  # Create 5 empty lines.
        for character in originaltext:
            LD = self.get_letter(character)  # Returns 5 character lines.
            for i, LL in enumerate(LD):  # Parse each line in turn.
                lines[i].append(LL + " ")
        return lines


# --------------------------------------------------------------------------------------------------------------------------------


class Field:
    """A data field in a ColorDisplay window.

    Field can be regular data fields or progress bars."""

    __version__ = "0.0.2"

    def __init__(self, name, row, col, length=10, justify="l"):
        """justify = 'l' left, 'r' right."""
        # Common attributes
        self.name = name
        self.row = row
        self.column = col
        self.length = length
        self.value = None
        self.justify: str = justify  # 'left','centre','right'
        self.type: str = "Data"  # 'Data' field or 'ProgressBar'
        # Current color if it differs from the display defaults.
        self.fg_color: int | None = None
        self.bg_color: int | None = None
        # Progress bar specific attributes.
        self.pb_min: int | None = None  # Minimum value of a progress bar field.
        self.pb_max: int | None = None  # Maximum value of a progress bar field.
        self.pb_fg: int = TextColor.GREEN  # 'done' color of bar.
        self.pb_bg: int = TextColor.YELLOW  # 'todo' color of bar.
        # Colors used for ranges of values.
        # LOWLOW and HIGHHIGH values use these colors
        self.bad_fg: int | None = None
        # LOWLOW and HIGHHIGH values use these colors
        self.bad_bg: int | None = None
        # LOW and HIGH values use these colors
        self.poor_fg: int | None = None
        # LOW and HIGH values use these colors
        self.poor_bg: int | None = None
        # Special effects.
        # Seconds between changing FG/BG colors when blinking. 0 = No blink.
        self.blink_rate: int = 0
        # FG/BG pairs to alternate between when blinking.
        self.blink_colors: list[list[int]] = [
            [TextColor.WHITE, TextColor.BLACK],
            [TextColor.RED, TextColor.BLACK],
        ]

    def justified(self) -> str:
        """Return the field value as a justified string of the correct length."""
        sval = str(self.value)  # Convert to string.
        jcode = self.justify[0].lower()
        if len(sval) < self.length:  # Does the field need padding?
            if jcode == "r":
                sval = sval.strip().rjust(self.length)
            elif jcode == "c":
                sval = sval.strip().center(self.length)
            else:
                sval = sval.strip().ljust(self.length)
        return sval


# --------------------------------------------------------------------------------------------------------------------------------


class ColorDisplay:
    """Class to create a coloured character display buffer, and to display on the terminal as needed.

    Offers three basic modes of operation:
    1) Operate as addressible screen space
    2) Operate as simple scrolling text windows
    3) Operate as a form with defined data fields

    Supports sprites."""

    __version__ = "0.0.6"
    # Handles of all defined windows. Useful for scanning/updating all available windows.
    # The defining class contains some methods which can perform general updates via this list.
    defined_windows: list["ColorDisplay"] = []

    # Array of major rows/columns that ColorDisplay instances can self-align with.
    cd_layout: list[list[int]] = []
    # Each entry defines a high level 'column' of ColorDisplay locations.
    # [[fromcol,colwidth],[fromcol,colwidth],...]
    # When defining new ColorDisplay instances you can then just refer to
    # these columns rather than tailoring the coordinates of each individual window.

    @staticmethod
    def add_cd_entry(colwidth: int, startcol: int | None = None):
        """Add new entry to the ColorDisplay.CDLayout list.
        You must assign colwidth, but startcol is optional.
        If startcol is not specified, the next available one is assigned.

        CDLayout is a list of display columns that individual ColorDisplay instances can be placed in.
        This is used to simplify the creation of multi-panel displays."""
        # Starting column isn't specified, so calculate the next available one.
        if startcol is None:
            startcol = 1  # Find the next free one. 1st column if nothing exists yet.
            for cd in ColorDisplay.cd_layout:  # Check each layout already defined.
                temp = cd[0] + cd[1]
                if temp >= startcol:
                    # Start at next free column (with 1 space for border).
                    startcol = temp + 1
        # Must be at least 1 (1st column)
        startcol = max(startcol, 1)
        ColorDisplay.cd_layout.append([startcol, colwidth])
        return True

    def __init__(
        self,
        rows,
        columns=None,
        name="",
        row=None,
        col=None,
        fg=15,
        bg=0,
        first_scroll_row=0,
        title=None,
        rjtitle=None,
        titlefg=None,
        titlebg=None,
        borderfg=None,
        borderbg=None,
        cdlayout=None,
    ):
        """fg and bg parameters can be single integer value (0-255) or a list of values [(0-255),(0-255),..]
        The Print() method will cycle through the colors if lists are given.
        Other modes operate with just the first given fg and bg values, the rest of any lists are ignored.
        rows = Number of ROWS in the window.
        columns = Number of COLUMNS in the window.
        row = Display ROW number where window starts.
        col = Display COLUMN number where window starts.
        fg = Foreground. Single color code (0-255) or list of values to cycle through.
        bg = Background. Single color code (0-255) of list of values to cycle through.
        FirstScrollRow = When printing to window, this is the first row that will scroll up as new lines are printed. (allows titles to stay fixed etc)
        title = Window title.
        rjtitle = Extra text for window title that will be right justified. It overwrites basic window title.
        titlefg = Title foreground. Single color code (0-255). None will use window bg value.
        titlebg = Title background. Single color code (0-255). None will use window fg value.
        cdlayout = index of the ColorDisplay.CDLayout list. A shortcut to set col and or row values more dynamically.
        -------------------------
        After instantiation, you can also set self.ClipWindow = True to allow the window to truncate display if insufficient realestate available.
           Otherwise the entire window will be suppressed until the display is big enough to accomodate the entire window.
        """
        # A label for the display instance.
        self.display_name = name
        if columns is None and cdlayout is None:
            raise RuntimeError(
                "ColorDisplay.__init__(): You must specify columns or cdlayout parameter to define a window."
            )
        if self.display_name == "":
            # Generate a default name.
            self.display_name = f"win_{len(ColorDisplay.defined_windows)}"
        # How many rows deep is the display?
        self.display_rows = rows
        # If using predefined columns, make a note which one we're using.
        self.cd_entry = cdlayout
        # Automatically assign location on the screen.
        if (
            self.cd_entry is not None
            and self.cd_entry >= 0
            and self.cd_entry < len(ColorDisplay.cd_layout)
        ):
            # Use the CDLayout list of window columns to define the start column.
            # Pull the start character column from the CDLayout list.
            col = ColorDisplay.cd_layout[self.cd_entry][0]
            # Pull the character column width from the CDLayout list.
            columns = ColorDisplay.cd_layout[self.cd_entry][1]
            row = 1
            # Stack each new window beneath previous ones in a column.
            for cd in ColorDisplay.defined_windows:
                if cd.CDEntry == self.cd_entry and cd.last_display_row >= row:
                    # Start at next free row (with 1 row for border).
                    row = cd.last_display_row + 2
        # How many columns wide is the display?
        if columns is None:
            raise RuntimeError(
                "ColorDisplay.__init__(): You must specify columns or cdlayout parameter to define a window."
            )
        self.display_columns: int = columns
        # What's the location of the 1st cell in the display on the actual terminal?
        self.display_row: int | None = row
        self.display_col: int | None = col
        if self.display_row is not None and self.display_rows is not None:
            # Where does the display END ?
            self.last_display_row: int | None = self.display_row + self.display_rows - 1
        else:
            self.last_display_row = None
        if self.display_col is not None and self.display_columns is not None:
            self.last_display_col: int | None = self.display_col + self.display_columns
        else:
            self.last_display_col = None
        # For scrolling displays you can provide a list of alternating text colors to use.
        # This visually separates individual entries.
        if isinstance(fg, list):
            # What's the default foreground color?
            self.default_fg = fg[0]
            self.default_fgs = fg
        else:
            # What's the default foreground color?
            self.default_fg = fg
            self.default_fgs = [fg]
        # How many colors are available?
        self.fg_color_count = len(self.default_fgs)
        # Which color do we start with if multiple available?
        self.fg_color_index = 0
        # For scrolling displays you can provide a list
        # of alternating background colors to use.
        # This visually separates individual entries.
        if isinstance(bg, list):
            # What's the default background color?
            self.default_bg = bg[0]
            # List of all background colors.
            self.default_bgs = bg
        else:
            # What's the default background color?
            self.default_bg = bg
            # List of all background colors.
            self.default_bgs = [bg]
        # How many colors are available?
        self.bg_color_count = len(self.default_bgs)
        # Which color do we start with if multiple available?
        self.bg_color_index = 0
        # What color is the title row?
        self.title_fg = titlefg
        if self.title_fg is None:
            # Default to inverse.
            self.title_fg = self.default_bg
        # What color is the title row?
        self.title_bg = titlebg
        if self.title_bg is None:
            # Default to inverse.
            self.title_bg = self.default_fg
        # What color is the border?
        self.border_fg = borderfg
        if self.border_fg is None:
            # Default is same as general window.
            self.border_fg = self.default_fg
        # What color is the border.
        self.border_bg = borderbg
        if self.border_bg is None:
            # Default is same as general window.
            self.border_bg = self.default_bg
        # Create array of each cell in the window,
        # we need character, foreground color and background color.
        # Foreground colour of each character.
        self.fg_color = [
            [self.default_fg for c in range(self.display_columns)] for r in range(self.display_rows)
        ]
        # Background colour of each character.
        self.bg_color = [
            [self.default_bg for c in range(self.display_columns)] for r in range(self.display_rows)
        ]
        # Characters to display.
        self.character = [
            [" " for c in range(self.display_columns)] for r in range(self.display_rows)
        ]
        # Store the default state of the window here. This is used if the window is 'cleared'.
        # Foreground colour of each character.
        self.default_fgcolor = [
            [self.default_fg for c in range(self.display_columns)] for r in range(self.display_rows)
        ]
        # Background colour of each character.
        self.default_bgcolor = [
            [self.default_bg for c in range(self.display_columns)] for r in range(self.display_rows)
        ]
        # Characters to display.
        self.default_character = [
            [" " for c in range(self.display_columns)] for r in range(self.display_rows)
        ]
        # List of the display commands last issued to paint the display.
        # Used to check for changes.
        self.prev_line_strings: list[str | None] = [None for r in range(self.display_rows)]
        # If set to true, Display() method will only update
        # lines of the display that it thinks have changed.
        self.reduce_io = False
        # List of any active sprites in the display.
        self.sprites: list[CdSprite] = []
        # Cache of recently printed lines, used for repainting and exporting.
        self.print_history: list[str] = []
        # 0 means data starts at the first row of the window,
        # 1 means there's a title or something in row 0, etc.
        # Scrolling takes this into account.
        self.first_scroll_row = first_scroll_row
        # Can store handle to a 'Log' method for logging messages.
        # Needs to be defined and assigned by the calling program.
        self.log = None
        # Can specify how quickly the display refreshes (in seconds).
        self.refresh_rate = None
        # When did the display last update?
        self.last_refresh = None
        # List of fields if defined.
        self.fields: list[Field] = []
        # If TRUE the corners are highlighted in RED,
        # and the FIELDS are highlighted in YELLOW(for layout checking)
        self.mark_display = False
        if title is not None:
            self.window_title = " " + title.strip()
        else:
            self.window_title = None
        if rjtitle is not None:
            # A secondary title that is right justified on top of the title line.
            self.rj_title = rjtitle.strip() + " "
        else:
            self.rj_title = None
        if self.window_title is not None:
            self.set_title()
        # If TRUE, the window can be clipped to fit available terminal display.
        # This will simply truncate.
        self.clip_window = False
        # If TRUE, an additional single line border is drawn on the RIGHT and BOTTOM of the window.
        # Takes 1 extra character in each dimension.
        self.draw_border = False
        self.border_fg = self.default_fg
        self.border_bg = self.default_bg
        ColorDisplay.defined_windows.append(
            self
        )  # Add this window to the global list of all windows.

    def __del__(self):
        """Remove this window from the list of defined windows.
        *Q* This is called by the garbage collector (not guaranteed), so may not be the smartest way to do this.
        """
        for i, w in enumerate(ColorDisplay.defined_windows):
            # Found myself in the list. Remove and quit.
            if w == self:
                del ColorDisplay.defined_windows[i]
                break

    def set_title(self):
        """Turn first row of a window into a title row.
        Color appropriately and change the scroll behaviour of the window.
        1st line nolonger scrolls."""
        # Deactivate the title line.
        if self.window_title is None:
            self.first_scroll_row = 0
            for c in range(self.display_columns):
                # Regular colors if no title.
                self.fg_color[0][c] = self.default_fg
                # Regular colors if no title.
                self.bg_color[0][c] = self.default_bg
        else:  # Activate the title line.
            self.first_scroll_row = 1
            temp = (self.window_title + (" " * self.display_columns))[
                : self.display_columns
            ]  # Pad out to full window width.
            for c in range(self.display_columns):
                # Add title to window display top line.
                self.character[0][c] = temp[c]
                # Invert colors for titles.
                self.fg_color[0][c] = self.title_fg
                # Invert colors for titles.
                self.bg_color[0][c] = self.title_bg
            # There is a right justified element to the title to add.
            if self.rj_title is not None:
                sc = self.display_columns - len(self.rj_title)
                # Work backwards because we are right justifying this on top of existing title.
                for i, char in enumerate(self.rj_title):
                    c = sc + i  # Where does the character go?
                    self.character[0][c] = char

    def read_title_row(self):
        """Read the title row directly from the buffer."""
        line = ""
        for c in range(self.display_columns):
            line += self.character[0][c]
        return line

    def add_field(self, name, row, column, length=10, justify="l"):
        """Add a field to the list of fields recognised in this window.
        Duplicates are allowed."""
        self.fields.append(Field(name=name, row=row, col=column, length=length, justify=justify))
        return True

    def initialize_progress_bar(self, name, minval, maxval, fg=None, bg=None):
        """Prime a field as a progress bar."""
        found_it = False
        for f in self.fields:
            # Will initialize multiple fields with same name.
            if f.name == name:
                found_it = True
                f.pb_min = minval
                f.pb_max = maxval
                f.type = "ProgressBar"
                if fg is not None:
                    # Set the 'DONE' color
                    f.pb_fg = fg
                if bg is not None:
                    # Set the 'TODO' color
                    f.pb_bg = bg
        return found_it

    def scan_for_fields(self, startchar="[", endchar="]"):
        """Scan the current display looking for fields.
        Fields are marked by '[name    ]' strings.
        If no name, then a sequence number is assigned as a name.
        '[]' would represent a 2 character field (assigned a sequence number name automatically).
        ']' would represent a 1 character field (assigned a sequence number name automatically).
        Set the 'default' display before calling this.
        Start and End field characters are '[' and ']' by default, but you can change 'em if needed
        via the startchar and endchar parameters."""
        # 1 character only, and failsafe to the default char.
        startchar = (startchar.strip() + "[")[0]
        # 1 character only, and failsafe to the default char.
        endchar = (endchar.strip() + "]")[0]
        # Default ID for fields with no name.
        nextid = 0
        # Process each display row individually.
        for r in range(self.display_rows):
            # Fields cannot span multiple lines.
            start = None
            name = ""
            # Scan across the characters of the line.
            for c in range(self.display_columns):
                # End of field marker, and there was a start marker!
                if self.character[r][c] == endchar and start is not None:
                    nextid += 1
                    # No name yet. Assign default.
                    if name == "":
                        name = str(nextid)
                    self.add_field(name=name, row=r, column=start, length=(c - start) + 1)
                    # Clear the 'working' field name values ready for next field we find.
                    start = None
                    name = ""
                # Start of field marker.
                if self.character[r][c] == startchar:
                    start = c
                # We're in a field.
                if start is not None:
                    if self.character[r][c] not in [startchar, endchar, " "]:
                        # Add to name.
                        name += self.character[r][c]
        return True

    def get_float_value(self, input):
        """Convert an input value into a float.
        Removing special characters such as "%","C" etc."""
        allowedchars = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "."]
        # Make sure it's a string.
        sinp = str(input)
        cinp = ""  # Cleaned input.
        for s in sinp:
            if s in allowedchars:
                cinp += s
        finp = float(cinp)
        return finp

    def export_fields(self, filename, initialdictionary=None):
        """Export field values to json file.
        Data is appended to any values already existing in initialdictionary."""
        if initialdictionary is None:
            initialdictionary = {}
        tempdict = initialdictionary
        for field in self.fields:
            tempdict[self.display_name + "." + field.name] = field.value
        tempdict[self.display_name + ".PrintHistory"] = self.print_history
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(tempdict, f)
        return True

    def update_blink_status(self):
        """Check for any fields with 'BlinkRate' set.
        Adjust colors accordingly."""
        for f in self.fields:
            if f.blink_rate != 0:  # This field is in BLINK mode.
                # Choose an appropriate color scheme.
                # Current time as seconds.
                t = datetime.now().timestamp()
                # Cycle through the list of BlinkColor pairs.
                c = round(t / f.blink_rate, 0) % len(f.blink_colors)
                self.field_value(f.name, c, fg=f.blink_colors[c][0], bg=f.blink_colors[c][1])
        return True

    def set_blink_status(
        self,
        name,
        blinkrate,
        blinkcolors=None,
    ):
        """Setup blink data."""
        # Validate the color list.
        if blinkcolors is None:
            blinkcolors = [[TextColor.WHITE, TextColor.BLACK], [TextColor.BLACK, TextColor.WHITE]]
        lOK = True
        for a in blinkcolors:
            # Must be 2 colors listed in each entry.
            if len(a) != 2:
                lOK = False
                break
        if lOK:
            for f in self.fields:
                if f.name == name:
                    f.blink_rate = blinkrate
                    f.blink_colors = blinkcolors

    def field_value(self, name, value, fg: int | None = None, bg: int | None = None):
        """Update the value of a field and display it."""
        found_it = False
        pc = 0
        for f in self.fields:
            # Will update multiple fields with the same name.
            if f.name == name:
                found_it = True
                f.value = value
                if fg is not None:
                    # Tell the field what color it is.
                    f.fg_color = fg
                if bg is not None:
                    # Tell the field what color it is.
                    f.bg_color = bg
                # Make sure the value is a character string and correctly formatted.
                s_value = f.justified()
                if f.type == "ProgressBar":
                    # Limit value to progress bar limits.
                    if f.pb_max is not None and f.pb_min is not None:
                        pval = float(max(min(self.get_float_value(value), f.pb_max), f.pb_min))
                    if fg is None:
                        # Default to predefined progress bar colors.
                        fg = f.pb_fg
                    if bg is None:
                        bg = f.pb_bg
                    # Calculate % complete (offset by -1 to allow for Python 'range' function)
                    if f.pb_max is not None and f.pb_min is not None:
                        pc = round(f.length * (pval - f.pb_min) / (f.pb_max - f.pb_min)) - 1
                    for i in range(f.length):
                        # 'completed' section of progress bar.
                        if i <= pc:
                            self.fg_color[f.row][f.column + i] = fg
                            self.bg_color[f.row][f.column + i] = bg
                        # 'todo' section of progress bar (colors swapped).
                        else:
                            self.fg_color[f.row][f.column + i] = bg
                            self.bg_color[f.row][f.column + i] = fg
                        self.character[f.row][f.column + i] = s_value[i]
                # 'Data' field.
                else:
                    # Set the characters one at a time.
                    for i in range(f.length):
                        self.character[f.row][f.column + i] = s_value[i]
                        if fg is not None:
                            self.fg_color[f.row][f.column + i] = fg
                        if bg is not None:
                            self.bg_color[f.row][f.column + i] = bg
        return found_it

    def rename_field(self, oldname, newname):
        """Change the name of a data field to something more useful."""
        found_it = False
        # Check all fields.
        for f in self.fields:
            # Found original fieldname.
            if f.name == oldname:
                found_it = True
                # Assign new fieldname.
                f.name = newname
        return found_it

    def field_format(self, name, justify=None, pattern=None, bwz=None):
        """Change the format of a data field to something more useful."""
        found_it = False
        # Check all fields.
        for f in self.fields:
            # Found original fieldname.
            if f.name == name:
                found_it = True
                if justify is not None:
                    f.justify = justify
        return found_it

    def copy_field_color(self, fromname, toname):
        """Copy color of one field to another."""
        found_it = False
        # Handle to the FROM instance.
        fromfield = None
        # Handle to the TO instance.
        tofield = None
        # Find the source field.
        for f in self.fields:
            # Found the FROM instance.
            if f.name == fromname:
                fromfield = f
                break
        # Find the target field.
        for g in self.fields:
            # Found the TO instance.
            if g.name == toname:
                tofield = g
                break
        # Transfer the colors.
        if fromfield is not None and tofield is not None:
            found_it = self.field_color(toname, fg=fromfield.fg_color, bg=fromfield.bg_color)
        return found_it

    def field_color(self, name, fg=None, bg=None):
        """Update the color of a field and display it."""
        found_it = False
        if fg is None:
            fg = self.default_fg  # Set defaults if no value given.
        if bg is None:
            bg = self.default_bg
        for f in self.fields:  # Find the Field(s) by name.
            if f.type in ["ProgressBar"]:
                continue  # ProgressBars select their color differently.
            if f.name == name:  # Will update multiple fields with the same name.
                found_it = True
                if fg is not None:
                    f.fg_color = fg  # Tell the field what color it is.
                if bg is not None:
                    f.bg_color = bg  # Tell the field what color it is.
                for i in range(f.length):  # Color every character in the field.
                    self.fg_color[f.row][f.column + i] = fg
                    self.bg_color[f.row][f.column + i] = bg
                f.fg_color = fg
                f.bg_color = bg
        return found_it

    def initialize_color_range(self, name, badfg=None, badbg=None, poorfg=None, poorbg=None):
        """Set colour range for a field."""
        found_it = False  # Not found the field yet.
        for f in self.fields:  # Search the field list.
            if f.name == name:  # Will update multiple fields with the same name.
                found_it = True  # Found the field.
                f.bad_fg = badfg  # Set the color values for each range.
                f.bad_bg = badbg
                f.poor_fg = poorfg
                f.poor_bg = poorbg
        return found_it

    def range_field_color(self, name, lowlow=None, low=None, high=None, highhigh=None):
        """Update the color of a field based upon a range of values."""
        found_it = False  # Not found the field yet.
        for f in self.fields:  # Find the field in the field list.
            if f.type in ["ProgressBar"]:
                continue  # ProgressBars select their color differently.
            if f.name == name:  # Will update multiple fields with the same name.
                found_it = True  # Found the field.
                # We have a LOW LOW or HIGH HIGH value, this is BAD.
                if f.value <= lowlow or f.value >= highhigh:
                    fg = f.bad_fg
                    bg = f.bad_bg
                # We have a LOW or HIGH value, this is POOR.
                elif f.value <= low or f.value >= high:
                    fg = f.poor_fg
                    bg = f.poor_bg
                # We have a GOOD value.
                else:
                    fg = self.default_fg
                    bg = self.default_bg
                self.field_color(name, fg=fg, bg=bg)
        return found_it

    def list_fields(self) -> dict:
        """Return dictionary of fields recognised in the window."""
        dict_obj: dict[str, dict[str, int | str]] = {}
        for f in self.fields:
            dict_obj[f.name] = {
                "row": f.row,
                "col": f.column,
                "len": f.length,
                "just": f.justify,
                "type": f.type,
            }
        return dict_obj

    def set_refresh_rate(self, rate):
        """Set selected refresh rate and reset the refresh timer."""
        self.refresh_rate = rate
        self.last_refresh = None

    def set_default(self):
        """Store the current display as a default image.
        When the display is cleared, this default image is restored."""
        for c in range(self.display_columns):
            for r in range(self.display_rows):
                self.default_fgcolor[r][c] = self.fg_color[r][c]
                self.default_bgcolor[r][c] = self.bg_color[r][c]
                self.default_character[r][c] = self.character[r][c]

    def convert_lines(self):
        """Scan the current layout for '-','|','+' symbols and convert to primitive line drawing."""
        # Not yet implemented.
        return True

    def clip_row(self, row):
        if row < 0:
            row = 0
        if row >= self.display_rows:
            row = self.display_rows - 1
        return row

    def clip_col(self, col):
        if col < 0:
            col = 0
        if col >= self.display_columns:
            col = self.display_columns - 1
        return col

    def draw_box(
        self,
        fromloc,
        toloc,
        fg=None,
        bg=None,
        border=True,
        fill=True,
        overwritelist=None,
    ):
        """Use unicode line characters to draw a box on a ColorDisplay window.
        fromloc = (fromrow,fromcol)
        toloc = (torow,tocol)
        fg = Optional Foreground color.
        bg = Optional Background color.
        border = True : Draw border line.
               = False : Just color the box.
        fill = True : Color the interior cells of the box.
               False : Leave interior cell colors unchanged.
        overwritelist = [] List of characters that linedrawing is allowed to overwrite.
                        So you can 'draw' the box using these characters when you define
                        the display and ONLY these characters get overwritten, this lets
                        you have overlapping titles or gaps in the box if needed by using
                        other characters that are not in the overwritelist"""
        if overwritelist is None:
            overwritelist = ["+", "-", "|", " "]
        fromrow, fromcol = fromloc
        torow, tocol = toloc
        fromrow = self.clip_row(fromrow)
        torow = self.clip_row(torow)
        fromcol = self.clip_col(fromcol)
        tocol = self.clip_col(tocol)
        if border:  # Draw lines around box.
            for c in range(fromcol, tocol + 1):
                # Draw top
                if c == fromcol:
                    char = TextColor.SYMBOLS["corner_tl"]
                elif c == tocol:
                    char = TextColor.SYMBOLS["corner_tr"]
                else:
                    char = TextColor.SYMBOLS["horizontal"]
                cv, _, _ = self.cell_value(fromrow, c)
                if cv in overwritelist:
                    self.place_string(char, fromrow, c, fg=fg, bg=bg)
                # Draw bottom
                if c == fromcol:
                    char = TextColor.SYMBOLS["corner_bl"]
                elif c == tocol:
                    char = TextColor.SYMBOLS["corner_br"]
                else:
                    char = TextColor.SYMBOLS["horizontal"]
                cv, _, _ = self.cell_value(torow, c)
                if cv in overwritelist:
                    self.place_string(char, torow, c, fg=fg, bg=bg)
            char = TextColor.SYMBOLS["vertical"]
            if (torow - fromrow) > 1:
                for r in range(fromrow + 1, torow):
                    # Draw left
                    cv, _, _ = self.cell_value(r, fromcol)
                    if cv in overwritelist:
                        self.place_string(char, r, fromcol, fg=fg, bg=bg)
                    # Draw right
                    cv, _, _ = self.cell_value(r, tocol)
                    if cv in overwritelist:
                        self.place_string(char, r, tocol, fg=fg, bg=bg)
        if fill:  # Fill the rectangle with the color.
            for c in range(fromcol, tocol + 1):
                for r in range(fromrow, torow + 1):
                    self.color_cell(r, c, fg, bg)

    def refresh_due(self):
        """Return True if refresh is due, else False."""
        result = False
        if self.refresh_rate is None:
            result = True  # There's no restriction so always refresh.
        elif self.last_refresh is None:
            result = True  # Need to do initial drawing.
        elif (datetime.now() - self.last_refresh).total_seconds() > self.refresh_rate:
            result = True  # Refresh is due.
        return result

    def add_sprite(self, name, text, row=None, col=None, fg=15, bg=0, level=0):
        """Create a sprite.
        If name is unique, it creates an instance of cdsprite subclass and adds it to the
        list of sprites managed by this display buffer."""
        l_found = False
        for s in self.sprites:
            if s.name == name:
                l_found = True
        if not l_found:  # Safe to add.
            self.sprites.append(CdSprite(name, text, row, col, fg, bg, level))
            # Sort the sprites by level. The higher the level the more to the foreground it is.
            self.sprites = sorted(self.sprites, key=lambda sprite: sprite.level)
        else:
            print(
                "ColorDisplay: addsprite ("
                + name
                + ") rejected because a sprite by this name already exists."
            )

    def sprite_label(self, name, color=False):
        """Return sprite label (optionally colored)."""
        result = None
        for s in self.sprites:
            if s.name == name:
                result = s.label(color=color)
        return result

    def colored_sprite(self, name):
        """Return sprite character with embedded colour codes."""
        result = None
        for s in self.sprites:
            if s.name == name:
                result = s.colored_symbol()
        return result

    def move_sprite(self, name, row, col):
        for s in self.sprites:
            if s.name == name:
                s.row = row
                s.column = col

    def color_sprite(self, name, fg=None, bg=None):
        for s in self.sprites:
            if s.name == name:
                if fg is not None:
                    s.fg = fg
                if bg is not None:
                    s.bg = bg

    def hide_sprite(self, name):
        for s in self.sprites:
            if s.name == name:
                s.display = False

    def show_sprite(self, name):
        for s in self.sprites:
            if s.name == name:
                s.display = True

    def clear_sprites(self):
        self.sprites = []

    def change_sprite(self, name, symbol):
        for s in self.sprites:
            if s.name == name:
                s.symbol = symbol

    def set_border_colors(self, borderfg, borderbg):
        if borderfg is None:
            self.border_fg = self.default_fg
        else:
            self.border_fg = borderfg
        if borderbg is None:
            self.border_bg = self.default_bg
        else:
            self.border_bg = borderbg

    def clear(self, fg=None, bg=None, immediate=False):
        """Clear the display buffer, setting all characters to back to their defaults.
        Default image can be updated using the set_default() method if needed.
        It does not clear the sprites! You need to do that separately (clear_sprites() method.)
        Jan.2022 0.0.2 : fg and bg parameters nolonger used."""
        if fg is not None:
            print("TextColor.ColorDisplay.clear() fg parameter is nolonger supported.")
        if bg is not None:
            print("TextColor.ColorDisplay.clear() bg parameter is nolonger supported.")
        for r in range(self.display_rows):
            for c in range(self.display_columns):
                self.character[r][c] = self.default_character[r][c]
                self.fg_color[r][c] = self.default_fgcolor[r][c]
                self.bg_color[r][c] = self.default_bgcolor[r][c]
        # Reconstruct the title if it is set.
        self.set_title()
        if immediate:
            self.draw()  # Clear the display immediately.

    def cell_value(self, row, col):
        """Return cell contents. Character, fg and bg colors."""
        fg, bg = self.cell_color(row, col)
        char = self.character[row][col]
        return char, fg, bg

    def color_cell(self, row, col, fg, bg):
        """Change colour of a cell, but don't change the text."""
        self.fg_color[row][col] = fg
        self.bg_color[row][col] = bg

    def cell_color(self, row, col):
        """Return current color of a cell."""
        if row < 0 or row >= self.display_rows:
            fg = self.default_fg
        else:
            fg = self.fg_color[row][col]
        if col < 0 or col >= self.display_columns:
            bg = self.default_bg
        else:
            bg = self.bg_color[row][col]
        return fg, bg

    def scroll_up(self, lines=1, immediate=False):
        """Scroll the display up by a number of lines.
        Drops lines at the top,
        adds new blank lines at the bottom."""
        if lines < 1:
            lines = 1
        if lines > self.display_rows:
            lines = self.display_rows
        for _i in range(lines):
            self.character.pop(self.first_scroll_row)  # Remove entire 1st data row.
            self.fg_color.pop(self.first_scroll_row)
            self.bg_color.pop(self.first_scroll_row)
            self.character.append(
                [" " for c in range(self.display_columns)]
            )  # Add empty row at end of window.
            self.fg_color.append(
                [self.default_fgs[self.fg_color_index] for c in range(self.display_columns)]
            )
            self.bg_color.append(
                [self.default_bgs[self.bg_color_index] for c in range(self.display_columns)]
            )
        if immediate:
            self.display(immediate=immediate)

    def concat(self, *args, sep=" "):
        """Convert all the input arguments into a single string."""
        result = ""
        for arg in args:
            if result != "":
                # add single clean separator between existing values and the new one.
                result = result.strip() + sep
            result += str(arg)  # Add new value.
        result = result.strip()  # Clean up.
        return result

    def print(self, *args, fg=None, bg=None, immediate=False):
        """Simple scrolling print function.
        Appends text to bottom of window display and scrolls up as required.
        This allows the retirement of the messagewindow class.
        immediate=True: Display is immediately refreshed.
        immediate=False: Display needs to be refreshed elsewhere.
        if fg or bg colors are specified, they override the default color scheme of the display.
        """
        # Constructed line of text to display.
        text = ""
        # Concatenate all the elements into a single text line.
        for i in args:
            if len(text) > 0:
                # Default to space between each element.
                text += " "
            # All elements must be str type.
            text += str(i)
        # Retain recent lines printed.
        # Can be exported, or used to repaint the display if resized.
        self.print_history.append(text)
        # Drop unwanted lines.
        while len(self.print_history) > self.display_rows:
            self.print_history.pop(0)  # Drop the first line.
        # Display text, allowing wraparound onto multiple lines.
        while len(text) > 0:
            # Too much text to fit on one line.
            if len(text) > self.display_columns:
                # Print 1 line's worth of text.
                print_text = text[: self.display_columns]
                # Save the rest for the following line(s).
                text = text[self.display_columns :]
            else:  # Remaining text fits on a single line.
                print_text = text  # Print what's left.
                text = ""  # Nothing else to print after this.
            # No need to pass 'immediate' parameter, it's handled below.
            self.scroll_up()
            r = self.display_rows - 1
            for i, char in enumerate(print_text):
                self.character[r][i] = char
            if fg is not None:  # fg color specified.
                for i in range(self.display_columns):
                    self.fg_color[r][i] = fg
            if bg is not None:  # bg color specified.
                for i in range(self.display_columns):
                    self.bg_color[r][i] = bg
        if immediate:
            # Update the display immediately.
            self.display(immediate=immediate)
        # If multiple colors supported, then move on to next available color.
        self.fg_color_index = (self.fg_color_index + 1) % self.fg_color_count
        self.bg_color_index = (self.bg_color_index + 1) % self.bg_color_count
        return True

    def place_string(
        self,
        text,
        row: int,
        col: int,
        fg: int | None = None,
        bg: int | None = None,
    ):
        """Place a string at any given location in the display buffer.
        +ve co-ordinates are top-to-bottom, left-to-right
        -ve co-ordinates are bottom-to-top, right-to-left"""
        if row < 0:
            # Allow -ve values to work up from the bottom of the window.
            row = self.display_rows + row
        if col < 0:
            # Allow -ve values to work left from the right of the window.
            col = self.display_columns + col
        if len(text) > 0 and row >= 0 and row < self.display_rows:
            for i, char in enumerate(text):
                c = col + i  # Place in the correct column.
                if c >= 0 and c < self.display_columns:
                    self.character[row][c] = char
                    if fg is not None:
                        self.fg_color[row][c] = fg
                    if bg is not None:
                        self.bg_color[row][c] = bg

    def draw(self, screenheight=None, screenwidth=None, immediate=False):
        """Alias for Display() method. For backwards compatibility."""
        print(
            "***** ColorDisplay.Draw() method called. Depricated. Use ColorDisplay.display() method instead."
        )
        self.display(screenheight=screenheight, screenwidth=screenwidth, immediate=immediate)

    def _mark_display(self):
        """Quickly highlights window dimensions and fields.
        Helps when defining displays in new applications.
        Debug/Dev only."""
        # Mark all the fields clearly.
        for key, _value in self.list_fields().items():
            self.field_color(key, fg=TextColor.BLACK, bg=TextColor.CYAN)
        # Mark all the corners clearly.
        for c in range(self.display_columns):
            self.fg_color[0][c] = TextColor.BLACK
            self.fg_color[self.display_rows - 1][c] = TextColor.BLACK
            self.bg_color[0][c] = TextColor.RED
            self.bg_color[self.display_rows - 1][c] = TextColor.RED
        for r in range(self.display_rows):
            self.fg_color[r][0] = TextColor.BLACK
            self.fg_color[r][self.display_columns - 1] = TextColor.BLACK
            self.bg_color[r][0] = TextColor.RED
            self.bg_color[r][self.display_columns - 1] = TextColor.RED
        return True

    def transfer(self, target_buffer, display_row=None, display_col=None):
        """Transfer the current display to another buffer.
        targetbuffer is the handle to another ColorDisplay object.
        displayrow = first row in targetbuffer. If None, then this object's value is used.
        displaycol = first column in targetbuffer. If None, then this object's value is used.
        """
        max_screen_row = target_buffer.display_rows - 1
        max_screen_col = target_buffer.display_columns - 1
        if display_row is None:
            # Location in target defaults to the location of this object.
            display_row = self.display_row
        if display_col is None:
            # Location in target defaults to the location of this object.
            display_col = self.display_col
        for r in range(self.display_rows):
            # Where is this display in the new one?
            rt = r + display_row
            if rt > max_screen_row:
                break  # No space for this row.
            for c in range(self.display_columns):
                # Where is this display in the new one?
                ct = c + display_col
                if ct > max_screen_col:
                    # No space for this column.
                    break
                # Select the character for current position. Max 1 char.
                target_buffer.character[rt][ct] = self.character[r][c][0:1]
                # Current foreground color of the chosen character.
                target_buffer.fgcolor[rt][ct] = self.fg_color[r][c]
                # Current background color of the chosen character.
                target_buffer.bgcolor[rt][ct] = self.bg_color[r][c]
        return True

    def force_redraw(self):
        """Flushes old values from self.PrevLineStrings[] forcing a full refresh.
        Normally when calling the Display() method, only changes are sent to the terminal window.
        If you force_redraw() then the whole window is sent fresh."""
        self.prev_line_strings = [" " for i in self.prev_line_strings]

    @staticmethod
    def global_force_redraw():  # Common
        """Flushes old values from self.PrevLineStrings[] forcing a full refresh in all registered windows."""
        for w in ColorDisplay.defined_windows:
            try:
                w.force_redraw()
            except:
                pass  # Window nonlonger exists.

    def get_textlines(self):
        """Returns the display layout as a list of strings.
        No color or cursor codes are included, just the basic monotone display text.
        Sprites are shown in their latest position too."""
        linelist = []
        for r in range(self.display_rows):  # Go through all the rows in turn.
            line = ""
            for c in range(self.display_columns):  # Go through each column in turn.
                line += self.character[r][c][
                    0:1
                ]  # Select the character for current position. Max 1 char too!
            linelist.append(line)
        # Overlay sprites if they exist.
        for s in self.sprites:  # Check all sprites in turn.
            if (
                s.row is not None
                and s.column is not None
                and s.row >= 0
                and s.row < self.display_rows
                and s.column >= 0
                and s.column < self.display_columns
            ):  # In range.
                linelist[s.row] = (
                    linelist[s.row][: s.column] + s.symbol[0:1] + linelist[s.row][s.column + 1 :]
                )
        return linelist

    def display_textlines(self):
        """Display current contents of the window in a text box."""
        TextColor.text_box(self.get_textlines())

    @staticmethod
    def global_view_windows(titlefg=None, titlebg=None):
        """Construct a menu of all available windows
        then choose which window to display."""
        # Dynamically construct menu entries.
        dictionary = {}
        for w in ColorDisplay.defined_windows:
            itemdict = {}
            if w.window_title is not None:
                itemdict["label"] = w.window_title
            else:
                itemdict["label"] = w.display_name
            itemdict["bold"] = False
            itemdict["call"] = w.display_textlines
            itemdict["docurl"] = None
            itemdict["helpdoc"] = "help.txt"
            dictionary[w.display_name] = itemdict
        window_menu = ProcedureMenu(
            dictionary,
            "Window contents menu",
            titlefg=None,
            titlebg=None,
            labelwidth=30,
        )
        window_menu.prompt()

    def display(self, screenheight=None, screenwidth=None, immediate=False):
        """Take the display buffer and output it to the terminal.
        screenheight: Tells the number of rows available in the terminal display.
        screenwidth: Tells the number of columns available in the terminal display.
        immediate: (True) Forces immediate update of the terminal display.
                   (False) Only updates the display if the refresh timer is due."""

        if not immediate and not self.refresh_due():
            # Don't perform a refresh yet.
            return
        # Define the maximum ROW and COLUMN number that
        # can be addressed with the current window size.
        if screenheight is None:
            maxscreenrow = None
        else:
            maxscreenrow = screenheight - 1
        if screenwidth is None:
            maxscreencol = None
        else:
            maxscreencol = screenwidth - 1
        # We have a specific location to use,
        # check if that location is in the current display dimensions.
        if self.last_display_row is not None and maxscreenrow is not None:
            # Not enough height for the ENTIRE window and not allowed to clip.
            if not self.clip_window and maxscreenrow <= self.last_display_row:
                return  # Don't try to display.
            # None of the window fits on the terminal at all even if clipping allowed.
            if maxscreenrow < self.display_row:
                return  # Don't try to display.
        # We have a specific location to use,
        # check if that location is in the current display dimensions.
        if self.last_display_col is not None and maxscreencol is not None:
            # Not enough width for the ENTIRE window and not allowed to clip.
            if not self.clip_window and maxscreencol <= self.last_display_col:
                # Don't try to display.
                return
            # None of the window fits on the terminal at all even if clipping allowed.
            if maxscreencol < self.display_col:
                # Don't try to display.
                return
        horizontal_char = TextColor.SYMBOLS["horizontal"]  # '\u2500'
        vertical_char = TextColor.SYMBOLS["vertical"]  # '\u2502'
        corner_char = TextColor.SYMBOLS["corner_br"]  # '\u2518'
        self.update_blink_status()  # If any fields are supposed to blink, check their color now.
        if self.mark_display:  # We need to mark up the corners and fields.
            self._mark_display()
        for r in range(
            self.display_rows
        ):  # Go through all the rows in turn. *Q* Should respect 'ClipWindow' too.
            if (
                self.clip_window
                and self.display_row is not None
                and (r + self.display_row) > maxscreenrow
            ):
                break  # We're off the end of the available display.
            try:
                # The following code has occassionally failed with an IndexError.
                # Added some debugging in case it occurs again to aid solving.
                # Note what color we're printing at the start of the line.
                # Color control codes change when this value changes.
                runningfg = self.fg_color[r][0]
                runningbg = self.bg_color[r][0]
            except IndexError as e:
                print("ColorDisplay fault: Index out of range?", r, 0)
                print(
                    f"ColorDisplay fault: Available range fg {len(self.fg_color)} bg {len(self.bg_color)}"
                )
                print(
                    f"ColorDisplay fault: maxscreenrow {maxscreenrow} maxscreencol {maxscreencol}"
                )
                print(
                    f"ColorDisplay fault: LastDisplayRow {self.last_display_row} LastDisplayCol {self.last_display_col}"
                )
                print(
                    f"ColorDisplay fault: DisplayRow {self.display_row} DisplayCol {self.display_col}"
                )
                print(
                    f"ColorDisplay fault: DisplayRows {self.display_rows} DisplayColumns {self.display_columns}"
                )
                print(f"ColorDisplay fault: ClipWindow {self.clip_window}")
                if self.log is not None:
                    self.log(
                        f"ColorDisplay fault: Index out of range? {r}, 0",
                        level="error",
                        terminal=True,
                    )
                    self.log(
                        f"ColorDisplay fault: Available range fg {len(self.fg_color)} bg {len(self.bg_color)}",
                        level="error",
                        terminal=True,
                    )
                    self.log(
                        f"ColorDisplay fault: maxscreenrow {maxscreenrow} maxscreencol {maxscreencol}",
                        level="error",
                        terminal=True,
                    )
                    self.log(
                        f"ColorDisplay fault: LastDisplayRow {self.last_display_row} LastDisplayCol {self.last_display_col}",
                        level="error",
                        terminal=True,
                    )
                    self.log(
                        f"ColorDisplay fault: DisplayRow {self.display_row} DisplayCol {self.display_col}",
                        level="error",
                        terminal=True,
                    )
                    self.log(
                        f"ColorDisplay fault: DisplayRows {self.display_rows} DisplayColumns {self.display_columns}",
                        level="error",
                        terminal=True,
                    )
                    self.log(
                        f"ColorDisplay fault: ClipWindow {self.clip_window}",
                        level="error",
                        terminal=True,
                    )
                # Terminate through the regular exception routine.
                raise Exception("Index out of range") from e
            # Start line off with initial color scheme.
            # Leave the control code 'open' for more text to be added.
            line = TextColor.fgbgcolor(runningfg, runningbg, "", reset=False)
            # Go through each column in turn. *Q* Should respect 'ClipWindow' too.
            for c in range(self.display_columns):
                if (
                    self.clip_window
                    and self.display_col is not None
                    and (c + self.display_col) > maxscreencol
                ):
                    # We're off the end of the available display.
                    break
                # Select the character for current position. Max 1 char too!
                ch = self.character[r][c][0:1]
                # Current foreground color of the chosen character.
                f = self.fg_color[r][c]
                # Current background color of the chosen character.
                b = self.bg_color[r][c]
                # Check if any sprites override this character.
                # Check all sprites in turn.
                for s in self.sprites:
                    # Same location and visible.
                    if s.row == r and s.column == c and s.display:
                        # Only 1 character allowed for the sprite at the moment.
                        ch = s.symbol[0:1]
                        # Sprite fg and bg colors override the background.
                        f = s.fg
                        b = s.bg
                # Colour scheme has changed. Insert appropriate code.
                if runningfg != f or runningbg != b:
                    # Note new colours we're now printing with.
                    runningfg = f
                    runningbg = b
                    # Insert open-ended colour change code.
                    line += TextColor.fgbgcolor(runningfg, runningbg, "", reset=False)
                # Make sure that the character is the right length.
                if len(ch) < 1:
                    ch = " "
                # Add the character.
                line += ch
            if self.display_row is not None and self.display_col is not None:
                # The display has a specific location on the terminal window. Place it there.
                dr = self.display_row + r
                dc = self.display_col
                # Locate the line on the terminal layout.
                line = TextColor.cursor(dc, dr) + line
            line += TextColor.reset()
            if (
                self.draw_border
                and self.last_display_col is not None
                and self.last_display_col + 1 < maxscreencol
            ):
                line += TextColor.fgbgcolor(self.border_fg, self.border_bg, vertical_char)
            # The line has changed. So display the new string.
            # Otherwise save display time and leave it unchanged.
            if not self.reduce_io or self.prev_line_strings[r] != line:
                # Do not add newline character at end of the printed text.
                # Always flush the print buffer.
                print(line, end="", flush=True)
            # Store the print command so we can compare next time if anything changed.
            self.prev_line_strings[r] = line
        if (
            self.draw_border
            and self.last_display_row is not None
            and self.last_display_row + 1 < maxscreenrow
        ):
            visiblecolumns = maxscreencol - self.display_col + 1
            # We cannot fit the entire bottom border line and corner in the display,
            # just show what's possible.
            if visiblecolumns < self.display_columns + 1:
                # Truncate the line.
                line = TextColor.fgbgcolor(
                    self.border_fg, self.border_bg, (horizontal_char * visiblecolumns)
                )
            #  The whole border line and corner should fit in the display.
            else:
                # Full line including corner character.
                line = TextColor.fgbgcolor(
                    self.border_fg,
                    self.border_bg,
                    (horizontal_char * self.display_columns) + corner_char,
                )
            print(TextColor.cursor(self.display_col, self.display_row + self.display_rows) + line)
        self.last_refresh = datetime.now()

    @staticmethod
    def global_export_fields(filename, initialdictionary=None):
        """Export field values from all windows to json file.
        Data is appended to any values already existing in initialdictionary."""
        if initialdictionary is None:
            initialdictionary = {}
        tempdict = ColorDisplay.global_save_to_dictionary(initialdictionary=initialdictionary)
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(tempdict, f, default=str)
        return True

    @staticmethod
    def global_save_to_dictionary(initialdictionary=None):
        """Export field values from all windows to dictionary.
        Data is appended to any values already existing in initialdictionary."""
        if initialdictionary is None:
            initialdictionary = {}
        tempdict = initialdictionary
        for w in ColorDisplay.defined_windows:
            for field in w.fields:
                tempdict[w.display_name + "." + field.name] = field.value
            tempdict[w.display_name + ".PrintHistory"] = w.print_history
        return tempdict

    @staticmethod
    def global_field_format(name, justify=None, pattern=None, bwz=None):  # Common
        """Update the format of a field in all defined windows."""
        found_it = False
        for w in ColorDisplay.defined_windows:
            try:
                temp = w.field_format(name=name, justify=justify, pattern=pattern, bwz=bwz)
                if temp:
                    found_it = True
            except:
                pass  # Window nonlonger exists.
        return found_it

    @staticmethod
    def global_field_value(name, value, fg=None, bg=None):  # Common
        """Update the value of a field in all defined windows and display it."""
        found_it = False
        for w in ColorDisplay.defined_windows:
            try:
                temp = w.field_value(name=name, value=value, fg=fg, bg=bg)
                if temp:
                    found_it = True
            except:
                pass  # Window nonlonger exists.
        return found_it

    @staticmethod
    def global_field_color(name, fg=None, bg=None):  # Common
        """Update the color of a field in all defined windows."""
        found_it = False
        for w in ColorDisplay.defined_windows:
            try:
                temp = w.field_color(name=name, fg=fg, bg=bg)
                if temp:
                    found_it = True
            except:
                pass  # Window nolonger exists.
        return found_it

    @staticmethod
    def global_reduce_io(reduce=True):
        """Turn on/off the ReduceIO function in all defined windows.
        reduce = True turns it on.
        reduce = False turns it off.

        When True: All defined display windows will apply the ReduceIO rules.
                   When refreshing the display ONLY the changed characters are
                   updated to the terminal. This makes the refresh considerably
                   faster for displays where only a few characters change each time.
                   In most cases this is the most efficient way to refresh the displays.
        When False: All the defined display windows will completely redraw
                   all their contents each time the display is refreshed, even if
                   nothing has changed."""
        for w in ColorDisplay.defined_windows:
            try:
                w.reduce_io = reduce
            except:
                pass  # Window nolonger exists.
        return

    @staticmethod
    def global_display(screenheight=None, screenwidth=None, immediate=False):  # Common
        """Display ALL defined windows in a single call."""
        for w in ColorDisplay.defined_windows:
            try:
                w.display(
                    screenheight=screenheight,
                    screenwidth=screenwidth,
                    immediate=immediate,
                )
            except:
                pass  # Window nolonger exists.
        return

    @staticmethod
    def global_window_limits():
        """Return maximum ROW and COLUMN that any of the current windows extend into."""
        maxrow = 0
        maxcol = 0
        for w in ColorDisplay.defined_windows:
            try:
                maxrow = max(maxrow, w.last_display_row)
                maxcol = max(maxcol, w.last_display_col)
            except:
                pass  # Window nolonger exists.
        return (maxcol, maxrow)
