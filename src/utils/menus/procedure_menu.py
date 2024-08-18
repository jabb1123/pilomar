

import traceback
from utils.menus.menu import Menu
from utils.text.textcolor import TextColor


class ProcedureMenu(Menu):
  """Menu driver.
  Create a menu object.
  Give it a dictionary of menu items, including labels and functions/methods to call.
  Call the Prompt() method to execute the menu.
  Menu quits when user selects 'x' option.

  dictionary format
      {'menuitem1key':{'label':'menu item 1 label', 'bold':True/False, 'call': ProcedureName to call, 'break': False},
       'menuitem2key':{'label':'menu item 2 label', 'bold':True/False, 'call': ProcedureName to call}
      }

      'docurl' = URL for help documentation about the menu option.
      'helpdoc' = Local text file location for help documentation about the menu option.
      'break' = Insert a blank line separator in the menu after the option.
      'call' = Procedure to call if option is selected. (No parameters supported)
      'bold' = Print the menu option in bold text.
      'label' = The label to appear in the menu.
      'precall' = Optional: Procedure call to make BEFORE the 'call' procedure is called. If this fails, the 'call' and 'postcall' procedures are not called.
      'postcall' = Optional: Procedure call to make AFTER the 'call' procedure is called. This is executed even if the 'call' procedure fails.

  You can also specify global PRE and POST procedure calls by setting the procedure handle in
  self.PreCall and self.PostCall attributes.
  - self.PreCall is called for all menu options BEFORE any of the procedures defined in the dictionary.
  - self.PostCall is called for all menu options AFTER all the procedures defined in the dictionary.

  Therefore a single menu option can execute up to 5 procedures in sequence.
  - self.PreCall gives a global 'preparation' routine to run before all menu options.
    If self.PreCall fails, the 'precall' and 'call' procedures are skipped, execution passes
    immediately to the 'postcall' and self.PostCall procedures.
  - 'precall' gives an option specific preparation routine to run before the main option.
    If 'precall' fails, the 'call' procedure does not get executed, control passes immediately
    to the 'postcall' and self.PostCall procedures.
  - 'call' is the main routine to run for the menu option.
    If self.PreCall or 'precall' options fail, the 'call' option is not executed, execution passes
    immediately to the cleanup 'postcall' and self.PostCall procedures.
  - 'postcall' gives an option specific cleanup routine to run after the menu option even if it failed.
  - self.PostCall gives a global cleanup routine to run after all menu options even if they failed.

  You can trigger user input via the Prompt() method.
  You can directly run a menu option without user input via the Run() method.
  """

  __version__ = "0.0.3"

  def __init__(
    self,
    dictionary,
    title="Menu",
    titlefg=None,
    titlebg=None,
    helpdir=None,
    helpurl=None,
    logger=None,
    labelwidth=23,
  ):
    """Create the menu, load the dictionary.
    Initialize and validate the data.
    title = Title of menu.
    titlebg/fg colors of menu title.
    helpdir = directory where help text files exist.
    helpurl = url to help file."""
    super().__init__(dictionary, title, titlefg, titlebg, helpdir, helpurl, logger, labelwidth)
    self.pre_call = None  # Specify a procedure to call before ALL options.
    self.post_call = None  # Specify a procedure to call AFTER ALL options.
   
    for (key, value) in self.dictionary.items():  # Assign menu ID number to each entry.

      try:  # Check that the procedure name to be called looks valid.
        if value["call"] is not None:  # This will fail if the procedure name is wrong.
          pass
      except Exception as e:
        # The procedure call will not succeed if called.
        print(
          TextColor.red(
            self.title, "Cannot execute procedure", value["label"]
          )
        )
        print(TextColor.red(str(e)))
        traceback.print_exc()

      try:  # Check that the pre-procedure name to be called looks valid.
        if value.get("precall", None) is not None:  # This will fail if the procedure name is wrong.
          pass
      except Exception as e:
        # The procedure call will not succeed if called.
        print(
          TextColor.red(
            self.title, "Cannot execute pre-procedure", value["label"]
          )
        )
        print(TextColor.red(str(e)))
        traceback.print_exc()

      try:  # Check that the post-procedure name to be called looks valid.
        if value.get("postcall", None) is not None:  # This will fail if the procedure name is wrong.
          pass
      except Exception as e:
        # The procedure call will not succeed if called.
        print(
          TextColor.red(
            self.title, "Cannot execute post-procedure", value["label"]
          )
        )
        print(TextColor.red(str(e)))
        traceback.print_exc()
    self.help_dir = helpdir
    self.help_url = helpurl

  def run(self, key):
    """Given a menu option key, execute the procedure or sub-menu associated with it.
    if PRE and/or POST procedures are defined, execute those too.
    These allow you to prepare and/or cleanup even if the main call fails."""

    execute_main = True
    success = True  # Set the return code.

    # Global Pre procedure. # Execute BEFORE the main procedure call.
    if self.pre_call is not None:  # See if it's a callable function.
      try:  # See if the pre-procedure will execute.
        self.pre_call()  # Call it.
      except Exception as e:
        # Procedure didn't execute. Report the error and return to the menu.
        print(TextColor.red(" *** OOPS! *** ", invert=True))
        print(
          TextColor.red(
            "** Menu failed to execute "
            + str(key)
            + " ; global pre-call "
            + str(self.pre_call)
          )
        )
        print(TextColor.red(str(e)))
        traceback.print_exc()
        execute_main = False  # Do not execute the main call.
        success = False  # Set the return code.

    # Option Pre procedure. # Execute BEFORE the main procedure call.
    if execute_main:  # OK to proceed.
      procedure = self.dictionary[key].get(
        "precall", None
      )  # What pre-procedure is to be called?
      if procedure is not None:  # See if it's a callable function.
        try:  # See if the pre-procedure will execute.
          procedure()  # Call it.
        except Exception as e:
          # Procedure didn't execute. Report the error and return to the menu.
          print(TextColor.red(" *** OOPS! *** ", invert=True))
          print(
            TextColor.red(
              "** Menu failed to execute "
              + str(key)
              + " ; option pre-call "
              + str(procedure)
            )
          )
          print(TextColor.red(str(e)))
          traceback.print_exc()
          execute_main = False  # Do not execute the main call.
          success = False  # Set the return code.

    # Main procedure.
    if execute_main:  # OK to proceed.
      procedure = self.dictionary[key]["call"]  # What procedure is to be called?
      if procedure is None:  # No option to run.
        print(
          TextColor.yellow(
            str(key) + " does not have a related procedure to call."
          )
        )
      elif isinstance(procedure, type(self)):  # A submenu, so we trigger the nested submenu instead.
        procedure.prompt()  # Execute the submenu.
      else:  # See if it's a callable function.
        try:  # See if the procedure will execute.
          procedure()  # Call it.
        except Exception as e:
          # Procedure didn't execute. Report the error and return to the menu.
          print(TextColor.red(" *** OOPS! *** ", invert=True))
          print(
            TextColor.red(
              "** Menu failed to execute "
              + str(key)
              + " ; call "
              + str(procedure)
            )
          )
          print(TextColor.red(str(e)))
          traceback.print_exc()
          success = False  # Set the return code.

    # Option Post procedure. # Execute AFTER the main procedure call.
    procedure = self.dictionary[key].get(
      "postcall", None
    )  # What post-procedure is to be called?
    if procedure is not None:  # See if it's a callable function.
      try:  # See if the post-procedure will execute.
        procedure()  # Call it.
      except Exception as e:
        # Procedure didn't execute. Report the error and return to the menu.
        print(TextColor.red(" *** OOPS! *** ", invert=True))
        print(
          TextColor.red(
            "** Menu failed to execute "
            + str(key)
            + " ; option post-call "
            + str(procedure)
          )
        )
        print(TextColor.red(str(e)))
        traceback.print_exc()
        success = False  # Set the return code.

    # Global Post procedure. # Execute AFTER the main procedure call.
    if self.pre_call is not None:  # See if it's a callable function.
      try:  # See if the post-procedure will execute.
        self.post_call()  # Call it.
      except Exception as e:
        # Procedure didn't execute. Report the error and return to the menu.
        print(TextColor.red(" *** OOPS! *** ", invert=True))
        print(
          TextColor.red(
            "** Menu failed to execute "
            + str(key)
            + " ; global post-call "
            + str(self.post_call)
          )
        )
        print(TextColor.red(str(e)))
        traceback.print_exc()
        success = False  # Set the return code.

    return success  # True if all succeeded, False if any failed.

  def prompt(self, menuprefix=""):
    """Execute the menu.
    This paints the menu on the terminal and deals with user selections.
    Menu items are numbered dynamically, the user selects an item by selecting the number.
    If the user enters the number plus a '?' symbol then help text is displayed if it can be found.
    The method closes when the user selects the 'x' option.

    Note, you can also trigger options from the menu without user prompting by using the menu.Run(name) method.
    """
    # Now paint the menu and ask the user what to do.
    self.draw(menuprefix=menuprefix)  # Paint the menu.
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
            self.run(key)  # Execute the option.
            self.draw()  # Refresh the menu.
            found = True  # We have found and executed the option. OK to return to ask user for new input.
            break  # Next
        if found:  # Option was found and executed. Return to user input.
          continue  # Next user input.
      if answer.lower() == "?":  # Refresh option chosen.
        self.draw()  # Refresh the menu.
        continue  # Next user input.
      if (
        answer.lower() == "x"
      ):  # User chose to quit the menu. Terminate the loop.
        break  # Go UP a level, quit if at root.
      # User input was not recognised. Try again.
      print(TextColor.red("'" + str(answer) + "' Unrecognised. Try again."))
