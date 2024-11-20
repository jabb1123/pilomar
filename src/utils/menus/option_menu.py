"""Simple menu driver."""

from utils.menus.menu import Menu
from utils.text.textcolor import TextColor


class OptionMenu(Menu):
    """Simple menu driver.
    Create a menu object.
    Give it a dictionary of menu items. Labels and the value to be returned for each item.
    Call the Prompt() method to execute the menu.
    Menu quits when user selects 'x' option.
    It returns the user's choice from the menu.
    It returns None if the user didn't select anything.

    dictionary format
        {'menuitem1key':{'label':'menu item 1 label', 'bold':True/False, 'value': 'value1' to return, 'break': False},
         'menuitem2key':{'label':'menu item 2 label', 'bold':True/False, 'value': 'value2' to return}
        }

        'docurl' = URL for help documentation about the menu option.
        'helpdoc' = Local text file location for help documentation about the menu option.
        'break' = Insert a blank line separator in the menu after the option.
        'value' = The value to return from the menu if option is selected.
        'bold' = Print the menu option in bold text.
        'label' = The label to appear in the menu.

    You can trigger user input via the Prompt() method.
    You can directly run a menu option without user input via the Run() method.
    """

    __version__ = "0.0.2"

    def __init__(
        self,
        dictionary,
        title="Menu",
        titlefg=None,
        titlebg=None,
        helpdir=None,
        helpurl=None,
        logger=None,
        labelwidth=26,
    ):
        """Create the menu, load the dictionary.
        Initialize and validate the data.
        title = Title of menu.
        titlebg/fg colors of menu title.
        helpdir = directory where help text files exist.
        helpurl = url to help file."""
        super().__init__(
            dictionary, title, titlefg, titlebg, helpdir, helpurl, logger, labelwidth
        )

    def select(self, key):
        """Given a menu option key, extract the selected value."""
        result = self.dictionary[key]["value"]  # What procedure is to be called?
        return result

    def prompt(self, menuprefix=""):
        """Execute the menu.
        This paints the menu on the terminal and deals with user selections.
        Menu items are numbered dynamically, the user selects an item by selecting the number.

        If the user enters the number plus a '?' symbol then help text is displayed if it can be found.
        The method closes when the user selects the 'x' option.
        '>' key makes the menu 1 column wider.
        '<' key makes the menu 1 column narrower.

        Return values are :
          result: Returns the option value that was chosen, or None if no option was chosen.
          found:  Returns TRUE if an option was selected, returns FALSE if nothing was chosen.

        """
        # Now paint the menu and ask the user what to do.
        self.draw(menuprefix=menuprefix)  # Paint the menu.
        result = None  # The actual choice. None if nothing chosen.
        found = False  # Set to True if a choice is successfully made, else False is returned.
        while True:  # Loop until explicitly told to terminate.
            if self.log is not None:
                self.log("Menu waiting for user input.", terminal=False)
            answer = input(TextColor.cyan("Menu option : "))  # Prompt for input.
            if self.log is not None:
                self.log("Menu received user input", answer, ".", terminal=False)
            if answer == "?":  # Refresh the menu.
                self.draw()  # Refresh the menu.
                continue
            if answer == ">":  # Increase columns in display.
                self.columns += 1
                self.draw()  # Refresh the menu.
                continue
            if answer == "<":  # Increase columns in display.
                self.columns -= 1
                self.columns = max(self.columns, 1)  # must be at least 1 column.
                self.draw()  # Refresh the menu.
                continue
            if "?" in answer:  # User wants help about an option.
                self.process_help_request(answer)
                continue  # Prompt again.
            # Process menu choice.
            try:  # Convert text into integer if possible.
                menuid = int(answer)
            # except Exception as e:
            except Exception:
                # Text would not convert into integer.
                menuid = None
            if menuid is not None:  #
                found = False  # Have we found and executed the menu option?
                for key, value in self.dictionary.items():
                    if value["id"] == menuid:
                        result = self.select(
                            key
                        )  # Choose the selected value to return.
                        found = True  # We have found and selected the option.
                        break  # Next
                if found:
                    break
            if answer.lower() == "?":  # Refresh option chosen.
                self.draw()  # Refresh the menu.
                continue  # Next user input.
            if (
                answer.lower() == "x"
            ):  # User chose to quit without selecting anything. Terminate the loop.
                found = None  # Nothing was chosen.
                break  # Go UP a level, quit if at root.
            # User input was not recognised. Try again.
            print(TextColor.red("'" + str(answer) + "' Unrecognised. Try again."))
        return result, found
