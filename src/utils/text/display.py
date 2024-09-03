

from datetime import datetime
import json
from typing import List

from utils.menus.procedure_menu import ProcedureMenu
from utils.text.textcolor import ColorDisplaySprite, Field, TextColor


class ColorDisplay:
  """Class to create a coloured character display buffer, and to display on the terminal as needed.
  Can operate as addressible screen space, or
  can operate as simple scrolling text windows.
  Supports sprites.
  Supports labelled data fields."""

  __version__ = "0.0.6"
  DefinedWindows:List = (
    []
  )  # Handles of all defined windows. Useful for scanning/updating all available windows.
  # The defining class contains some methods which can perform general updates via this list.
  CDLayout = (
    []
  )  # Array of major rows/columns that colordisplay instances can self-align with.
  # Each entry defines a high level 'column' of colordisplay locations. [[fromcol,colwidth],[fromcol,colwidth],...]
  # When defining new colordisplay instances you can then just refer to these
  # columns rather than tailoring the coordinates of each individual window.

  @staticmethod
  def add_color_display_entry(colwidth, startcol=None):
    """Add new entry to the colordisplay.CDLayout list.
    You must assign colwidth, but startcol is optional.
    If startcol is not specified, the next available one is assigned."""
    if (
      startcol is None
    ):  # Starting column isn't specified, so calculate the next available one.
      startcol = 1  # Find the next free one. 1st column if nothing exists yet.
      for cd in ColorDisplay.CDLayout:  # Check each layout already defined.
        temp = cd[0] + cd[1]
        if temp >= startcol:
          startcol = (
            temp + 1
          )  # Start at next free column (with 1 space for border).
    startcol = max(startcol, 1)  # Must be at least 1 (1st column)
    ColorDisplay.CDLayout.append([startcol, colwidth])
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
    first_scroll_row = When printing to window, this is the first row that will scroll up as new lines are printed. (allows titles to stay fixed etc)
    title = Window title.
    titlefg = Title foreground. Single color code (0-255). None will use window bg value.
    titlebg = Title background. Single color code (0-255). None will use window fg value.
    cdlayout = index of the colordisplay.CDLayout list. A shortcut to set col and or row values more dynamically.
    -------------------------
    After instantiation, you can also set self.ClipWindow = True to allow the window to truncate display if insufficient realestate available.
       Otherwise the entire window will be suppressed until the display is big enough to accomodate the entire window.
    """
    self.display_name = name  # A label for the display instance.
    if columns is None and cdlayout is None:
      raise Exception(
        "colordisplay.__init__(): You must specify columns or cdlayout parameter to define a window."
      )
    if self.display_name == "":
      self.display_name = "win_" + str(
        len(ColorDisplay.DefinedWindows)
      )  # Generate a default name.
    self.display_rows = rows  # How many rows deep is the display?
    self.color_display_entry = (
      cdlayout  # If using predefined columns, make a note which one we're using.
    )
    if (
      self.color_display_entry is not None
      and self.color_display_entry >= 0
      and self.color_display_entry < len(ColorDisplay.CDLayout)
    ):  # Automatically assign location on the screen.
      # Use the CDLayout list of window columns to define the start column.
      col = ColorDisplay.CDLayout[self.color_display_entry][
        0
      ]  # Pull the start character column from the CDLayout list.
      columns = ColorDisplay.CDLayout[self.color_display_entry][
        1
      ]  # Pull the character column width from the CDLayout list.
      row = 1
      for (
        cd
      ) in (
        ColorDisplay.DefinedWindows
      ):  # Stack each new window beneath previous ones in a column.
        if cd.CDEntry == self.color_display_entry and cd.last_display_row >= row:
          row = (
            cd.last_display_row + 2
          )  # Start at next free row (with 1 row for border).
    self.display_columns = columns  # How many columns wide is the display?
    self.display_row = row  # What's the location of the 1st cell in the display on the actual terminal?
    self.display_col = col
    if self.display_row is not None and self.display_rows is not None:
      self.last_display_row = (
        self.display_row + self.display_rows - 1
      )  # Where does the display END ?
    else:
      self.last_display_row = None
    if self.display_col is not None and self.display_columns is not None:
      # self.last_display_col = self.DisplayCol + self.DisplayColumns - 1
      self.last_display_col = self.display_col + self.display_columns
    else:
      self.last_display_col = None
    if isinstance(fg, list):
      self.default_foreground = fg[0]  # What's the default foreground color?
      self.deafult_foregrounds = fg
    else:
      self.default_foreground = fg  # What's the default foreground color?
      self.deafult_foregrounds = [fg]
    self.foregroun_color_count = len(self.deafult_foregrounds)  # How many colors are available?
    self.foreground_color_index = 0  # Which color do we start with if multiple available?
    if isinstance(bg, list):
      self.default_background = bg[0]  # What's the default background color?
      self.default_backgrounds = bg  # List of all background colors.
    else:
      self.default_background = bg  # What's the default background color?
      self.default_backgrounds = [bg]  # List of all background colors.
    self.background_color_count = len(self.default_backgrounds)  # How many colors are available?
    self.background_color_index = 0  # Which color do we start with if multiple available?
    self.title_foreground = titlefg  # What color is the title row?
    if self.title_foreground is None:
      self.title_foreground = self.default_background  # Default to inverse.
    self.title_background = titlebg  # What color is the title row?
    if self.title_background is None:
      self.title_background = self.default_foreground  # Default to inverse.
    self.border_foreground = borderfg  # What color is the border?
    if self.border_foreground is None:
      self.border_foreground = self.default_foreground  # Default is same as general window.
    self.border_background = borderbg  # What color is the border.
    if self.border_background is None:
      self.border_background = self.default_background  # Default is same as general window.
    # Create array of each cell in the window, we need character, foreground color and background color.
    self.foreground_colors = [
      [self.default_foreground for c in range(self.display_columns)]
      for r in range(self.display_rows)
    ]  # Foreground colour of each character.
    self.background_colors = [
      [self.default_background for c in range(self.display_columns)]
      for r in range(self.display_rows)
    ]  # Background colour of each character.
    self.character = [
      [" " for c in range(self.display_columns)] for r in range(self.display_rows)
    ]  # Characters to display.
    # Store the default state of the window here. This is used if the window is 'cleared'.
    self.default_fgcolor = [
      [self.default_foreground for c in range(self.display_columns)]
      for r in range(self.display_rows)
    ]  # Foreground colour of each character.
    self.default_bgcolor = [
      [self.default_background for c in range(self.display_columns)]
      for r in range(self.display_rows)
    ]  # Background colour of each character.
    self.default_character = [
      [" " for c in range(self.display_columns)] for r in range(self.display_rows)
    ]  # Characters to display.
    self.prev_line_strings = [
      None for r in range(self.display_rows)
    ]  # List of the display commands last issued to paint the display. Used to check for changes.
    self.reduce_io = False  # If set to true, Display() method will only update lines of the display that it thinks have changed.
    self.sprites:List[ColorDisplaySprite] = []  # List of any active sprites in the display.
    self.print_history = (
      []
    )  # Cache of recently printed lines, used for repainting and exporting.
    self.first_scroll_row = first_scroll_row  # 0 means data starts at the first row of the window, 1 means there's a title or something in row 0, etc. Scrolling takes this into account.
    self.log = None  # Can store handle to a 'Log' method for logging messages. Needs to be assigned by the calling program.
    self.refresh_rate = (
      None  # Can specify how quickly the display refreshes (in seconds).
    )
    self.last_refresh = None  # When did the display last update?
    # self.Metadata = {} # Dictionary of metadata for fields in the display. (Experimental)
    #                   # {'name' : 'xxx', 'row' : nn, 'col' : nn, 'fg' : nn, 'bg' : nn}
    self.fields:List[Field] = []  # List of fields if defined.
    self.mark_display = False  # If TRUE the corners are highlighted in RED, and the FIELDS are highlighted in YELLOW(for layout checking)
    if title is None:
      self.window_title = None  # Does the window have a title row?
    else:
      self.set_title(title)
    self.clip_window = False  # If TRUE, the window can be clipped to fit available terminal display. This will simply truncate.
    self.draw_border = False  # If TRUE, an additional single line border is drawn on the RIGHT and BOTTOM of the window. Takes 1 extra character in each dimension.
    self.border_foreground = self.default_foreground
    self.border_background = self.default_background
    ColorDisplay.DefinedWindows.append(
      self
    )  # Add this window to the global list of all windows.

  def __del__(self):
    """Remove this window from the list of defined windows.
    *Q* This is called by the garbage collector (not guaranteed), so may not be the smartest way to do this.
    """
    for i, w in enumerate(ColorDisplay.DefinedWindows):
      if w == self:  # Found myself in the list. Remove and quit.
        del ColorDisplay.DefinedWindows[i]
        break

  @staticmethod
  def clear_screen():
    """Use this to perform a clean wipe of the screen and force display windows to refresh."""
    ColorDisplay.global_force_redraw()  # Force all window buffers to fully redraw.
    print(TextColor.clearscreen())  # Clear screen for refresh.

  def set_title(self, title):
    """Turn first row of a window into a title row.
    Color appropriately and change the scroll behaviour of the window.
    1st line nolonger scrolls."""
    self.window_title = " " + title.strip()
    if self.window_title is not None:
      temp = self.window_title
      self.first_scroll_row = 1
    else:
      temp = ""
      self.first_scroll_row = 0
    temp = (temp + (" " * self.display_columns))[: self.display_columns]
    for c in range(self.display_columns):
      self.character[0][c] = temp[c]
      if self.window_title is not None:
        self.foreground_colors[0][c] = self.title_foreground  # Invert colors for titles.
        self.background_colors[0][c] = self.title_background  # Invert colors for titles.
      else:
        self.foreground_colors[0][c] = self.default_foreground  # Regular colors if no title.
        self.background_colors[0][c] = self.default_background  # Regular colors if no title.

  def add_field(self, name, row, column, length=10, justify="l"):
    """Add a field to the list of fields recognised in this window.
    Duplicates are allowed."""
    self.fields.append(
      Field(name=name, row=row, col=column, length=length, justify=justify)
    )
    return True

  def initialize_progress_bar(self, name, minval, maxval, fg=None, bg=None):
    """Prime a field as a progress bar."""
    result = False
    for f in self.fields:
      if f.name == name:  # Will initialize multiple fields with same name.
        result = True
        f.progress_bar_min = minval
        f.progress_bar_max = maxval
        f.type = "ProgressBar"
        if fg is not None:
          f.progress_bar_foreground = fg  # Set the 'DONE' color
        if bg is not None:
          f.progress_bar_background = bg  # Set the 'TODO' color
    return result

  def scan_for_fields(self, startchar="[", endchar="]"):
    """Scan the current display looking for fields.
    Fields are marked by '[name    ]' strings.
    If no name, then a sequence number is assigned as a name.
    '[]' would represent a 2 character field (assigned a sequence number name automatically).
    ']' would represent a 1 character field (assigned a sequence number name automatically).
    Set the 'default' display before calling this.
    Start and End field characters are '[' and ']' by default, but you can change 'em if needed
    via the startchar and endchar parameters."""
    startchar = (startchar.strip() + "[")[
      0
    ]  # 1 character only, and failsafe to the default char.
    endchar = (endchar.strip() + "]")[
      0
    ]  # 1 character only, and failsafe to the default char.
    nextid = 0  # Default ID for fields with no name.
    for r in range(self.display_rows):  # Process each display row individually.
      start = None  # Fields cannot span multiple lines.
      name = ""
      for c in range(
        self.display_columns
      ):  # Scan across the characters of the line.
        if (
          self.character[r][c] == endchar and start is not None
        ):  # End of field marker, and there was a start marker!
          nextid += 1
          if name == "":  # No name yet. Assign default.
            name = str(nextid)
          self.add_field(
            name=name, row=r, column=start, length=(c - start) + 1
          )
          start = None  # Clear the 'working' field name values ready for next field we find.
          name = ""
        if self.character[r][c] == startchar:  # Start of field marker.
          start = c
        if start is not None:  # We're in a field.
          if not self.character[r][c] in [startchar, endchar, " "]:
            name += self.character[r][c]  # Add to name.
    return True

  def get_float_value(self, input):
    """Convert an input value into a float.
    Removing special characters such as "%","C" etc."""
    allowedchars = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "."]
    sinp = str(input)  # Make sure it's a string.
    cinp = ""  # Cleaned input.
    for s in sinp:
      if s in allowedchars:
        cinp += s
    finp = float(cinp)
    return finp

  def export_fields(self, filename, initialdictionary={}):
    """Export field values to json file.
    Data is appended to any values already existing in initialdictionary."""
    tempdict = initialdictionary
    for field in self.fields:
      tempdict[self.display_name + "." + field.name] = field.value
    tempdict[self.display_name + ".print_history"] = self.print_history
    with open(filename, "w", encoding="UTF-8") as f:
      json.dump(tempdict, f)
    return True

  def update_blink_status(self):
    """Check for any fields with 'BlinkRate' set.
    Adjust colors accordingly."""
    for f in self.fields:
      if f.blink_rate != 0:  # This field is in BLINK mode.
        # Choose an appropriate color scheme.
        t = datetime.now().timestamp()  # Current time as seconds.
        c = round(t / f.blink_rate, 0) % len(
          f.blink_colors
        )  # Cycle through the list of BlinkColor pairs.
        self.field_value(
          f.name, f.value, fg=f.blink_colors[c][0], bg=f.blink_colors[c][1]
        )
    return True

  def set_blink_status(
    self,
    name,
    blinkrate,
    blinkcolors=[
      [TextColor.WHITE, TextColor.BLACK],
      [TextColor.BLACK, TextColor.WHITE],
    ],
  ):
    """Setup blink data."""
    # Validate the color list.
    lOK = True
    for a in blinkcolors:
      if len(a) != 2:  # Must be 2 colors listed in each entry.
        lOK = False
        break
    if lOK:
      for f in self.fields:
        if f.name == name:
          f.blink_rate = blinkrate
          f.blink_colors = blinkcolors

  def field_value(self, name, value, fg=None, bg=None):
    """Update the value of a field and display it."""
    result = False
    for f in self.fields:
      if f.name == name:  # Will update multiple fields with the same name.
        result = True
        f.value = value
        if fg is not None:
          f.foreground_color = fg  # Tell the field what color it is.
        if bg is not None:
          f.background_color = bg  # Tell the field what color it is.
        sValue = (
          f.justified()
        )  # Make sure the value is a character string and correctly formatted.
        if f.type == "ProgressBar":
          pval = float(
            max(min(self.get_float_value(value), f.progress_bar_max), f.progress_bar_min)
          )  # Limit value to progress bar limits.
          if fg is None:
            fg = f.progress_bar_foreground  # Default to predefined progress bar colors.
          if bg is None:
            bg = f.progress_bar_background
          pc = (
            round(f.length * (pval - f.progress_bar_min) / (f.progress_bar_max - f.progress_bar_min)) - 1
          )  # Calculate % complete (offset by -1 to allow for Python 'range' function)
          for i in range(f.length):
            if i <= pc:  # 'completed' section of progress bar.
              self.foreground_colors[f.row][f.column + i] = fg
              self.background_colors[f.row][f.column + i] = bg
            else:  # 'todo' section of progress bar (colors swapped).
              self.foreground_colors[f.row][f.column + i] = bg
              self.background_colors[f.row][f.column + i] = fg
            self.character[f.row][f.column + i] = sValue[i]
        else:  # 'Data' field.
          for i in range(f.length):  # Set the characters one at a time.
            self.character[f.row][f.column + i] = sValue[i]
            if fg is not None:
              self.foreground_colors[f.row][f.column + i] = fg
            if bg is not None:
              self.background_colors[f.row][f.column + i] = bg
    return result

  def rename_field(self, oldname, newname):
    """Change the name of a data field to something more useful."""
    result = False
    for f in self.fields:  # Check all fields.
      if f.name == oldname:  # Found original fieldname.
        result = True
        f.name = newname  # Assign new fieldname.
    return result

  def field_format(self, name, justify=None, pattern=None, bwz=None):
    """Change the format of a data field to something more useful."""
    result = False
    for f in self.fields:  # Check all fields.
      if f.name == name:  # Found original fieldname.
        result = True
        if justify is not None:
          f.justify = justify
    return result

  def copy_field_color(self, fromname, toname):
    """Copy color of one field to another."""
    result = False
    fromfield = None  # Handle to the FROM instance.
    tofield = None  # Handle to the TO instance.
    for f in self.fields:  # Find the source field.
      if f.name == fromname:  # Found the FROM instance.
        fromfield = f
        break
    for g in self.fields:  # Find the target field.
      if g.name == toname:  # Found the TO instance.
        tofield = g
        break
    if fromfield is not None and tofield is not None:  # Transfer the colors.
      result = self.field_color(toname, fg=f.foreground_color, bg=f.background_color)
    return result

  def field_color(self, name, fg=None, bg=None):
    """Update the color of a field and display it."""
    result = False
    if fg is None:
      fg = self.default_foreground  # Set defaults if no value given.
    if bg is None:
      bg = self.default_background
    for f in self.fields:  # Find the field(s) by name.
      if f.type in ["ProgressBar"]:
        continue  # ProgressBars select their color differently.
      if f.name == name:  # Will update multiple fields with the same name.
        result = True
        if fg is not None:
          f.foreground_color = fg  # Tell the field what color it is.
        if bg is not None:
          f.background_color = bg  # Tell the field what color it is.
        for i in range(f.length):  # Color every character in the field.
          self.foreground_colors[f.row][f.column + i] = fg
          self.background_colors[f.row][f.column + i] = bg
        f.foreground_color = fg
        f.background_color = bg
    return result

  def initialize_color_range(
    self, name, badfg=None, badbg=None, poorfg=None, poorbg=None
  ):
    """Set colour range for a field."""
    result = False  # Not found the field yet.
    for f in self.fields:  # Search the field list.
      if f.name == name:  # Will update multiple fields with the same name.
        result = True  # Found the field.
        f.bad_foreground = badfg  # Set the color values for each range.
        f.bad_background = badbg
        f.poor_foreground = poorfg
        f.poor_background = poorbg
    return result

  def range_field_color(self, name, lowlow=None, low=None, high=None, highhigh=None):
    """Update the color of a field based upon a range of values."""
    result = False  # Not found the field yet.
    for f in self.fields:  # Find the field in the field list.
      if f.type in ["ProgressBar"]:
        continue  # ProgressBars select their color differently.
      if f.name == name:  # Will update multiple fields with the same name.
        result = True  # Found the field.
        if (
          f.value <= lowlow or f.value >= highhigh
        ):  # We have a LOW LOW or HIGH HIGH value, this is BAD.
          fg = f.bad_foreground
          bg = f.bad_background
        elif (
          f.value <= low or f.value >= high
        ):  # We have a LOW or HIGH value, this is POOR.
          fg = f.poor_foreground
          bg = f.poor_background
        else:  # We have a GOOD value.
          fg = self.default_foreground
          bg = self.default_background
        self.field_color(name, fg=fg, bg=bg)
    return result

  def list_fields(self)->dict:
    """Return dictionary of fields recognised in the window."""
    fields_dict = {}
    for f in self.fields:
      fields_dict[f.name] = {
        "row": f.row,
        "col": f.column,
        "len": f.length,
        "just": f.justify,
        "type": f.type,
      }
    return fields_dict

  def set_refresh_rate(self, rate):
    """Set selected refresh rate and reset the refresh timer."""
    self.refresh_rate = rate
    self.last_refresh = None

  def set_default(self):
    """Store the current display as a default image.
    When the display is cleared, this default image is restored."""
    for c in range(self.display_columns):
      for r in range(self.display_rows):
        self.default_fgcolor[r][c] = self.foreground_colors[r][c]
        self.default_bgcolor[r][c] = self.background_colors[r][c]
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
    overwritelist=["+", "-", "|", " "],
  ):
    """Use unicode line characters to draw a box on a colordisplay window.
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
    (fromrow, fromcol) = fromloc
    (torow, tocol) = toloc
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
    result = False
    for s in self.sprites:
      if s.name == name:
        result = True
    if not result:  # Safe to add.
      self.sprites.append(ColorDisplaySprite(name, text, row, col, fg, bg, level))
      # Sort the sprites by level. The higher the level the more to the foreground it is.
      self.sprites = sorted(self.sprites, key=lambda sprite: sprite.level)
    else:
      print(
        "colordisplay: addsprite ("
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
    """Move a sprite to a new location."""
    for s in self.sprites:
      if s.name == name:
        s.row = row
        s.column = col

  def color_sprite(self, name, fg=None, bg=None):
    """Change the color of a sprite."""
    for s in self.sprites:
      if s.name == name:
        if fg is not None:
          s.fg = fg
        if bg is not None:
          s.bg = bg

  def hide_sprite(self, name):
    """Hide a sprite."""
    for s in self.sprites:
      if s.name == name:
        s.display = False

  def show_sprite(self, name):
    """Show a sprite."""
    for s in self.sprites:
      if s.name == name:
        s.display = True

  def clear_sprites(self):
    """Remove all sprites from the display"""
    self.sprites:List[ColorDisplaySprite] = []

  def change_sprite(self, name, symbol):
    """Change the symbol of a sprite."""
    for s in self.sprites:
      if s.name == name:
        s.symbol = symbol

  def set_border_colors(self, borderfg, borderbg):
    """Set the border colors for the window."""
    if borderfg is None:
      self.border_foreground = self.default_foreground
    else:
      self.border_foreground = borderfg
    if borderbg is None:
      self.border_background = self.default_background
    else:
      self.border_background = borderbg

  def clear(self, fg=None, bg=None, immediate=False):
    """Clear the display buffer, setting all characters to back to their defaults.
    Default image can be updated using the SetDefault() method if needed.
    It does not clear the sprites! You need to do that separately (ClearSprites() method.)
    Jan.2022 0.0.2 : fg and bg parameters nolonger used."""
    if fg is not None:
      print("textcolor.colordisplay.Clear() fg parameter is nolonger supported.")
    if bg is not None:
      print("textcolor.colordisplay.Clear() bg parameter is nolonger supported.")
    for r in range(self.display_rows):
      for c in range(self.display_columns):
        self.character[r][c] = self.default_character[r][c]
        self.foreground_colors[r][c] = self.default_fgcolor[r][c]
        self.background_colors[r][c] = self.default_bgcolor[r][c]
    if immediate:
      self.draw()  # Clear the display immediately.

  def cell_value(self, row, col):
    """Return cell contents. Character, fg and bg colors."""
    fg, bg = self.cell_color(row, col)
    char = self.character[row][col]
    return char, fg, bg

  def color_cell(self, row, col, fg, bg):
    """Change colour of a cell, but don't change the text."""
    self.foreground_colors[row][col] = fg
    self.background_colors[row][col] = bg

  def cell_color(self, row, col):
    """Return current color of a cell."""
    if row < 0 or row >= self.display_rows:
      fg = self.default_foreground
    else:
      fg = self.foreground_colors[row][col]
    if col < 0 or col >= self.display_columns:
      bg = self.default_background
    else:
      bg = self.background_colors[row][col]
    return fg, bg

  def scroll_up(self, lines=1, immediate=False):
    """Scroll the display up by a number of lines.
    Drops lines at the top,
    adds new blank lines at the bottom."""
    if lines < 1:
      lines = 1
    if lines > self.display_rows:
      lines = self.display_rows
    for i in range(lines):
      self.character.pop(self.first_scroll_row)  # Remove entire 1st data row.
      self.foreground_colors.pop(self.first_scroll_row)
      self.background_colors.pop(self.first_scroll_row)
      self.character.append(
        [" " for c in range(self.display_columns)]
      )  # Add empty row at end of window.
      self.foreground_colors.append(
        [self.deafult_foregrounds[self.foreground_color_index] for c in range(self.display_columns)]
      )
      self.background_colors.append(
        [self.default_backgrounds[self.background_color_index] for c in range(self.display_columns)]
      )
    if immediate:
      self.display(immediate=immediate)

  def print(self, *args, fg=None, bg=None, immediate=False):
    """Simple scrolling print function.
    Appends text to bottom of window display and scrolls up as required.
    This allows the retirement of the messagewindow class.
    immediate=True: Display is immediately refreshed.
    immediate=False: Display needs to be refreshed elsewhere.
    if fg or bg colors are specified, they override the default color scheme of the display.
    """
    text = ""  # Constructed line of text to display.
    for i in args:  # Concatenate all the elements into a single text line.
      if len(text) > 0:
        text += " "  # Default to space between each element.
      text += str(i)  # All elements must be str type.
    self.print_history.append(
      text
    )  # Retain recent lines printed. Can be exported, or used to repaint the display if resized.
    while len(self.print_history) > self.display_rows:  # Drop unwanted lines.
      self.print_history.pop(0)  # Drop the first line.
    while len(text) > 0:  # Display text, allowing wraparound onto multiple lines.
      if len(text) > self.display_columns:  # Too much text to fit on one line.
        print_text = text[
          : self.display_columns
        ]  # Print 1 line's worth of text.
        text = text[
          self.display_columns :
        ]  # Save the rest for the following line(s).
      else:  # Remaining text fits on a single line.
        print_text = text  # Print what's left.
        text = ""  # Nothing else to print after this.
      self.scroll_up()  # No need to pass 'immediate' parameter, it's handled below.
      r = self.display_rows - 1
      for (i, text) in enumerate(print_text):
        self.character[r][i] = text
      if fg is not None:  # fg color specified.
        for i in range(self.display_columns):
          self.foreground_colors[r][i] = fg
      if bg is not None:  # bg color specified.
        for i in range(self.display_columns):
          self.background_colors[r][i] = bg
    if immediate:
      self.display(immediate=immediate)  # Update the display immediately.
    self.foreground_color_index = (
      self.foreground_color_index + 1
    ) % self.foregroun_color_count  # If multiple colors supported, then move on to next available color.
    self.background_color_index = (self.background_color_index + 1) % self.background_color_count
    return True

  def place_string(self, text, row=None, col=None, fg=None, bg=None):
    """Place a string at any given location in the display buffer.
    +ve co-ordinates are top-to-bottom, left-to-right
    -ve co-ordinates are bottom-to-top, right-to-left"""
    if row < 0:
      row = (
        self.display_rows + row
      )  # Allow -ve values to work up from the bottom of the window.
    if col < 0:
      col = (
        self.display_columns + col
      )  # Allow -ve values to work left from the right of the window.
    if len(text) > 0 and row >= 0 and row < self.display_rows:
      for (i, t) in enumerate(text):
        c = col + i  # Place in the correct column.
        if c >= 0 and c < self.display_columns:
          self.character[row][c] = t
          if fg is not None:
            self.foreground_colors[row][c] = fg
          if bg is not None:
            self.background_colors[row][c] = bg

  def draw(self, screenheight=None, screenwidth=None, immediate=False):
    """Alias for Display() method. For backwards compatibility."""
    print(
      "***** colordisplay.Draw() method called. Depricated. Use colordisplay.Display() method instead."
    )
    self.display(
      screenheight=screenheight, screenwidth=screenwidth, immediate=immediate
    )

  def _mark_display(self):
    """Quickly highlights window dimensions and fields.
    Helps when defining displays in new applications.
    Debug/Dev only."""
    # Mark all the fields clearly.
    for key, value in self.list_fields().items():
      self.field_color(key, fg=TextColor.BLACK, bg=TextColor.CYAN)
    # Mark all the corners clearly.
    for c in range(self.display_columns):
      self.foreground_colors[0][c] = TextColor.BLACK
      self.foreground_colors[self.display_rows - 1][c] = TextColor.BLACK
      self.background_colors[0][c] = TextColor.RED
      self.background_colors[self.display_rows - 1][c] = TextColor.RED
    for r in range(self.display_rows):
      self.foreground_colors[r][0] = TextColor.BLACK
      self.foreground_colors[r][self.display_columns - 1] = TextColor.BLACK
      self.background_colors[r][0] = TextColor.RED
      self.background_colors[r][self.display_columns - 1] = TextColor.RED
    return True

  def transfer(self, targetbuffer, displayrow=None, displaycol=None):
    """Transfer the current display to another buffer.
    targetbuffer is the handle to another colordisplay object.
    displayrow = first row in targetbuffer. If None, then this object's value is used.
    displaycol = first column in targetbuffer. If None, then this object's value is used.
    """
    maxscreenrow = targetbuffer.display_rows - 1
    maxscreencol = targetbuffer.display_columns - 1
    if displayrow is None:
      displayrow = (
        self.display_row
      )  # Location in target defaults to the location of this object.
    if displaycol is None:
      displaycol = (
        self.display_col
      )  # Location in target defaults to the location of this object.
    for r in range(self.display_rows):
      rt = r + displayrow  # Where is this display in the new one?
      if rt > maxscreenrow:
        break  # No space for this row.
      for c in range(self.display_columns):
        ct = c + displaycol  # Where is this display in the new one?
        if ct > maxscreencol:
          break  # No space for this column.
        targetbuffer.character[rt][ct] = self.character[r][c][
          0:1
        ]  # Select the character for current position. Max 1 char.
        targetbuffer.foreground_colors[rt][ct] = self.foreground_colors[r][
          c
        ]  # Current foreground color of the chosen character.
        targetbuffer.background_colors[rt][ct] = self.background_colors[r][
          c
        ]  # Current background color of the chosen character.
    return True

  def force_redraw(self):
    """Flushes old values from self.PrevLineStrings[] forcing a full refresh.
    Normally when calling the Display() method, only changes are sent to the terminal window.
    If you ForceRedraw() then the whole window is sent fresh."""
    self.prev_line_strings = [" " for i in self.prev_line_strings]

  @staticmethod
  def global_force_redraw():  # Common
    """Flushes old values from self.PrevLineStrings[] forcing a full refresh in all registered windows."""
    for w in ColorDisplay.DefinedWindows:
      try:
        w.force_redraw()
      except:
        pass  # Window nonlonger exists.

  def get_text_lines(self):
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
          linelist[s.row][: s.column]
          + s.symbol[0:1]
          + linelist[s.row][s.column + 1 :]
        )
    return linelist

  def DisplayTextLines(self):
    """Display current contents of the window in a text box."""
    TextColor.text_box(self.get_text_lines())

  @staticmethod
  def GlobalViewWindows(titlefg=None, titlebg=None):
    """Construct a menu of all available windows
    then choose which window to display."""
    # Dynamically construct menu entries.
    dictionary = {}
    for w in ColorDisplay.DefinedWindows:
      itemdict = {}
      if w.window_title is not None:
        itemdict["label"] = w.window_title
      else:
        itemdict["label"] = w.display_name
      itemdict["bold"] = False
      itemdict["call"] = w.display_text_lines
      itemdict["docurl"] = None
      itemdict["helpdoc"] = "help.txt"
      dictionary[w.display_name] = itemdict
    WindowMenu = ProcedureMenu(
      dictionary,
      "Window contents menu",
      titlefg=None,
      titlebg=None,
      labelwidth=30,
    )
    WindowMenu.prompt()

  def display(self, screenheight=None, screenwidth=None, immediate=False):
    """Take the display buffer and output it to the terminal.
    screenheight: Tells the number of rows available in the terminal display.
    screenwidth: Tells the number of columns available in the terminal display.
    immediate: (True) Forces immediate update of the terminal display.
           (False) Only updates the display if the refresh timer is due."""

    if not immediate and not self.refresh_due():
      return  # Don't perform a refresh yet.
    # Define the maximum ROW and COLUMN number that can be addressed with the current window size.
    if screenheight is None:
      maxscreenrow = None
    else:
      maxscreenrow = screenheight - 1
    if screenwidth is None:
      maxscreencol = None
    else:
      maxscreencol = screenwidth - 1
    if (
      self.last_display_row is not None and maxscreenrow is not None
    ):  # We have a specific location to use, check if that location is in the current display dimensions.
      if (not self.clip_window and maxscreenrow <= self.last_display_row):  # Not enough height for the ENTIRE window and not allowed to clip.
        return  # Don't try to display.
      if (
        maxscreenrow < self.display_row
      ):  # None of the window fits on the terminal at all even if clipping allowed.
        return  # Don't try to display.
    if (
      self.last_display_col is not None and maxscreencol is not None
    ):  # We have a specific location to use, check if that location is in the current display dimensions.
      if (
        not self.clip_window and maxscreencol <= self.last_display_col
      ):  # Not enough width for the ENTIRE window and not allowed to clip.
        return  # Don't try to display.
      if (
        maxscreencol < self.display_col
      ):  # None of the window fits on the terminal at all even if clipping allowed.
        return  # Don't try to display.
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
        # The following code has occassionally failed with an IndexError. Added some debugging in case it occurs again to aid solving.
        runningfg = self.foreground_colors[r][
          0
        ]  # Note what color we're printing at the start of the line. Color control codes change when this value changes.
        runningbg = self.background_colors[r][0]
      except IndexError as e:
        print("colordisplay fault: Index out of range?", r, 0)
        print(
          "colordisplay fault: Available range fg",
          len(self.foreground_colors),
          "bg",
          len(self.background_colors),
        )
        print(
          "colordisplay fault: maxscreenrow",
          maxscreenrow,
          "maxscreencol",
          maxscreencol,
        )
        print(
          "colordisplay fault: last_display_row",
          self.last_display_row,
          "last_display_col",
          self.last_display_row,
        )
        print(
          "colordisplay fault: DisplayRow",
          self.display_row,
          "DisplayCol",
          self.display_col,
        )
        print(
          "colordisplay fault: DisplayRows",
          self.display_rows,
          "DisplayColumns",
          self.display_columns,
        )
        print("colordisplay fault: ClipWindow", self.clip_window)
        if self.log is not None:
          self.log(
            "colordisplay fault: Index out of range?",
            r,
            0,
            level="error",
            terminal=True,
          )
          self.log(
            "colordisplay fault: Available range fg",
            len(self.foreground_colors),
            "bg",
            len(self.background_colors),
            level="error",
            terminal=True,
          )
          self.log(
            "colordisplay fault: maxscreenrow",
            maxscreenrow,
            "maxscreencol",
            maxscreencol,
            level="error",
            terminal=True,
          )
          self.log(
            "colordisplay fault: last_display_row",
            self.last_display_row,
            "last_display_col",
            self.last_display_row,
            level="error",
            terminal=True,
          )
          self.log(
            "colordisplay fault: DisplayRow",
            self.display_row,
            "DisplayCol",
            self.display_col,
            level="error",
            terminal=True,
          )
          self.log(
            "colordisplay fault: DisplayRows",
            self.display_rows,
            "DisplayColumns",
            self.display_columns,
            level="error",
            terminal=True,
          )
          self.log(
            "colordisplay fault: ClipWindow",
            self.clip_window,
            level="error",
            terminal=True,
          )
        raise Exception(
          "Index out of range"
        ) from e  # Terminate through the regular exception routine.
      line = TextColor.fgbgcolor(
        runningfg, runningbg, "", reset=False
      )  # Start line off with initial color scheme. Leave the control code 'open' for more text to be added.
      for c in range(
        self.display_columns
      ):  # Go through each column in turn. *Q* Should respect 'ClipWindow' too.
        if (
          self.clip_window
          and self.display_col is not None
          and (c + self.display_col) > maxscreencol
        ):
          break  # We're off the end of the available display.
        ch = self.character[r][c][
          0:1
        ]  # Select the character for current position. Max 1 char too!
        f = self.foreground_colors[r][
          c
        ]  # Current foreground color of the chosen character.
        b = self.background_colors[r][
          c
        ]  # Current background color of the chosen character.
        # Check if any sprites override this character.
        for s in self.sprites:  # Check all sprites in turn.
          if (
            s.row == r and s.column == c and s.display
          ):  # Same location and visible.
            ch = s.symbol[
              0:1
            ]  # Only 1 character allowed for the sprite at the moment.
            f = s.fg  # Sprite fg and bg colors override the background.
            b = s.bg
        if (
          runningfg != f or runningbg != b
        ):  # Colour scheme has changed. Insert appropriate code.
          runningfg = f  # Note new colours we're now printing with.
          runningbg = b
          line += TextColor.fgbgcolor(
            runningfg, runningbg, "", reset=False
          )  # Insert open-ended colour change code.
        if len(ch) < 1:  # Make sure that the character is the right length.
          ch = " "
        line += ch  # Add the character.
      if self.display_row is not None and self.display_col is not None:
        # The display has a specific location on the terminal window. Place it there.
        dr = self.display_row + r
        dc = self.display_col
        line = (
          TextColor.cursor(dc, dr) + line
        )  # Locate the line on the terminal layout.
      line += TextColor.reset()
      if self.draw_border and self.last_display_col + 1 < maxscreencol:
        line += TextColor.fgbgcolor(self.border_foreground, self.border_background, vertical_char)
      if (not self.reduce_io or self.prev_line_strings[r] != line):  # The line has changed. So display the new string. Otherwise save display time and leave it unchanged.
        print(
          line, end="", flush=True
        )  # Do not add newline character at end of the printed text. Always flush the print buffer.
      self.prev_line_strings[r] = (
        line  # Store the print command so we can compare next time if anything changed.
      )
    if self.draw_border and self.last_display_row + 1 < maxscreenrow:
      visiblecolumns = maxscreencol - self.display_col + 1
      if (
        visiblecolumns < self.display_columns + 1
      ):  # We cannot fit the entire bottom border line and corner in the display, just show what's possible.
        line = TextColor.fgbgcolor(
          self.border_foreground, self.border_background, (horizontal_char * visiblecolumns)
        )  # Truncate the line.
      else:  #  The whole border line and corner should fit in the display.
        line = TextColor.fgbgcolor(
          self.border_foreground,
          self.border_background,
          (horizontal_char * self.display_columns) + corner_char,
        )  # Full line including corner character.
      print(
        TextColor.cursor(self.display_col, self.display_row + self.display_rows)
        + line
      )
    self.last_refresh = datetime.now()

  @staticmethod
  def global_export_fields(filename, initialdictionary={}):
    """Export field values from all windows to json file.
    Data is appended to any values already existing in initialdictionary."""
    tempdict = ColorDisplay.global_save_to_dictionary(
      initialdictionary=initialdictionary
    )
    with open(filename, "w", encoding="utf-8") as f:
      json.dump(tempdict, f, default=str)
    return True

  @staticmethod
  def global_save_to_dictionary(initialdictionary={}):
    """Export field values from all windows to dictionary.
    Data is appended to any values already existing in initialdictionary."""
    tempdict = initialdictionary
    for w in ColorDisplay.DefinedWindows:
      for field in w.fields:
        tempdict[w.display_name + "." + field.name] = field.value
      tempdict[w.display_name + ".print_history"] = w.print_history
    return tempdict

  @staticmethod
  def global_field_format(name, justify=None, pattern=None, bwz=None):  # Common
    """Update the format of a field in all defined windows."""
    result = False
    for w in ColorDisplay.DefinedWindows:
      try:
        temp = w.field_format(
          name=name, justify=justify, pattern=pattern, bwz=bwz
        )
        if temp:
          result = True
      except:
        pass  # Window nonlonger exists.
    return result

  @staticmethod
  def global_field_value(name, value, fg=None, bg=None):  # Common
    """Update the value of a field in all defined windows and display it."""
    result = False
    for w in ColorDisplay.DefinedWindows:
      try:
        temp = w.field_value(name=name, value=value, fg=fg, bg=bg)
        if temp:
          result = True
      except:
        pass  # Window nonlonger exists.
    return result

  @staticmethod
  def global_field_color(name, fg=None, bg=None):  # Common
    """Update the color of a field in all defined windows."""
    result = False
    for w in ColorDisplay.DefinedWindows:
      try:
        temp = w.field_color(name=name, fg=fg, bg=bg)
        if temp:
          result = True
      except:
        pass  # Window nolonger exists.
    return result

  @staticmethod
  def global_reduce_io(reduce=True):
    """Turn on/off the ReduceIO function in all defined windows.
    True turns it on.
    False turns it off."""
    for w in ColorDisplay.DefinedWindows:
      try:
        w.reduce_io = reduce
      except:
        pass  # Window nolonger exists.
    return

  @staticmethod
  def global_display(screenheight=None, screenwidth=None, immediate=False):  # Common
    """Display ALL defined windows in a single call."""
    for w in ColorDisplay.DefinedWindows:
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
    for w in ColorDisplay.DefinedWindows:
      try:
        maxrow = max(maxrow, w.last_display_row)
        maxcol = max(maxcol, w.last_display_col)
      except:
        pass  # Window nolonger exists.
    return (maxcol, maxrow)

