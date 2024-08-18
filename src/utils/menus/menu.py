"""Base class for all menus."""

from utils.text.textcolor import TextColor


class Menu:
  """Simple menu driver.
  
  This is the base class for all menus.
  """
  __version__ = "0.0.1"

  def __init__(self,dictionary,title="Menu",titlefg=None,titlebg=None,helpdir=None,helpurl=None,logger=None,labelwidth=23,):
    """Create the menu, load the dictionary.
    Initialize and validate the data.
    title = Title of menu.
    titlebg/fg colors of menu title.
    helpdir = directory where help text files exist.
    helpurl = url to help file."""
    self.dictionary:dict = dictionary
    self.title = title
    self.id_width = 2
    self.label_width = labelwidth
    self.title_foreground = titlefg
    self.columns = 2  # How many columns to draw?
    self.log = logger  # Can define a logging function to use.
    if titlefg is None:
      self.title_foreground = TextColor.BLACK
    self.title_background = titlebg
    if titlebg is None:
      self.title_background = TextColor.YELLOW
    counter = 0
    for (key, value) in self.dictionary.items():  # Assign menu ID number to each entry.
      counter += 1
      value["id"] = counter
      self.label_width = max(self.label_width, len(value["label"]))
    self.help_dir = helpdir
    self.help_url = helpurl

  def get_help_file(self, menuid):
    """Given an ID number, retrieve and display the help text if it exists."""
    filename = None
    for key, value in self.dictionary.items():  # Find entry with matching ID.
      if value["id"] == menuid:  # Found a match.
        filename = value.get("helpdoc", None)  # Get the helpdoc filename.
        break  # Look no further.
    if filename is not None and self.help_dir is not None:
      filename = self.help_dir + filename  # Construct path to file.
    return filename

  def show_help_text(self, menuid):
    """Given an ID number, display the help text associated with that menu item."""
    filename = self.get_help_file(menuid)
    if filename is not None:
      try:
        with open(filename, "r") as f:
          for line in f.readlines():
            print(TextColor.cyan(line))
      except Exception as e:
        print(TextColor.red("Sorry, unable to show the help file."))
        print(str(e))
    else:
      print(TextColor.red("Sorry, no help file is defined for menu item", menuid))

  def get_help_url(self, menuid):
    """Given an ID number, return URL associated with the help documentation."""
    helpurl = None
    for key, value in self.dictionary.items():  # Find entry with matching ID.
      if value["id"] == menuid:  # Found a match.
        helpurl = value.get("helpurl", None)  # Get the helpdoc helpurl.
        break  # Look no further.
    if helpurl is not None and self.help_dir is not None:
      helpurl = self.help_dir + helpurl  # Construct path to file.
    return helpurl

  def draw(self, menuprefix=""):
    """Draw the menu on the terminal.
    The menu list from the dictionary will automatically gain '?' and 'x' options too.
    """
    # In Python 3.7 onwards, dictionaries should retain the sequence in which items are added. No sorting required.
    count = 0
    print(
      TextColor.clearforward()
    )  # Blank line before menu and clear everything below that.
    print(
      TextColor.fgbgcolor(
        self.title_foreground, self.title_background, " " + menuprefix + self.title + " "
      )
    )  # Menu title is painted in inverse colours.
    for key, value in self.dictionary.items():  # Go through each menu item in turn.
      entry = (
        TextColor.yellow(str(value["id"]).rjust(self.id_width, " ")) + " "
      )  # ID number in yellow.
      if (
        "bold" in value and value["bold"]
      ):  # If the menu item is in bold, make it so.
        entry += TextColor.white(
          value["label"].ljust(self.label_width, " ")[: self.label_width]
        )
      else:  # Menu item is not in bold.
        entry += value["label"].ljust(self.label_width, " ")[: self.label_width]
      entry += " "  # Space between columns of menu entries.
      print(
        entry, end=""
      )  # Print the menu entry column, don't include 'newline' yet.
      count += 1  # Count how many entries.
      if count % self.columns == 0:  # Print 'newline' after 2nd column entry.
        print("")
      if "break" in value and value["break"]:
        if count % self.columns != 0:  # We're terminating the line early.
          print("")
          count = 0
        print("")  # Insert a blank line break in the menu.
    if (
      count % self.columns != 0
    ):  # Print 'newline' if we didn't complete the 2nd column when the menu list ran out.
      print("")  # Terminate line if not already done.
    # Always include 'x' and '?' menu options automatically.
    print(
      TextColor.yellow("x".rjust(self.id_width, " "))
      + " "
      + "Exit".ljust(self.label_width, " ")[: self.label_width]
      + " ",
      end="",
    )
    print(
      TextColor.yellow("?".rjust(self.id_width, " "))
      + " "
      + "Refresh".ljust(self.label_width, " ")[: self.label_width]
    )

  def process_help_request(self, answer):
    """Receive a text type menu id.
    if it converts to an integer successfully,
    show the help text associated with that menu item."""
    answer = answer.replace("?", "")  # Remove any question mark.
    try:
      menuid = int(answer)
    except:
      menuid = None
    if menuid is not None:
      self.show_help_text(menuid)
