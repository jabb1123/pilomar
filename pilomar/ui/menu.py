#!/usr/bin/env python3
"""Menu classes for terminal UI.

This module provides menu classes for creating interactive
terminal-based menu systems.

Classes:
    Menu: Original menu class (deprecated)
    ProcedureMenu: Menu with procedure callbacks
    OptionMenu: Option selection menu
    ListChooser: List selection menu
    FileChooser: File/directory selection menu
"""

# This software is published under the GNU General Public License v3.0.

__version__ = '0.1.0'

import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import pytz

try:
    from .text_color import TextColor
except ImportError:
    from text_color import TextColor



class Menu:
    """ Original menu class. Now replaced by proceduremenu class. """

    __version__ = '0.0.1'

    def __init__(self,dictionary,title='Menu',titlefg=None,titlebg=None,helpdir=None,helpurl=None,logger=None):
        """ Create the menu, load the dictionary.
            Initialize and validate the data.
            title = Title of menu.
            titlebg/fg colors of menu title.
            helpdir = directory where help text files exist. 
            helpurl = url to help file. """
        print ('TextColor.menu: NOTE: This is replaced by the TextColor.proceduremenu class now!')

# -------------------------------------------------------------------------------------------------------------------------------- 

class ProcedureMenu:
    """ Menu driver.
        Create a menu object.
        Give it a dictionary of menu items, including labels and functions/methods to call.
        Call the Prompt() method to execute the menu. 
        Menu quits when user selects 'x' option. 
        
        dictionary format 
                {'menuitem1key':{'label':'menu item 1 label', 'bold':True/False, 'call': ProcedureName to call, 'break': False, 'color': TextColor.yellow},
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
                'color' = The name of the textcolor color to use for the label. If missing the default is used.

                'id' is added automatically. It is the menu ID number.
                'enabled' is added automatically. It indicates that the menu option is currently visible and selectable.
                
        You can also specify global PRE and POST procedure calls by setting the procedure handle in 
        self.pre_call and self.post_call attributes.
        - self.pre_call is called for all menu options BEFORE any of the procedures defined in the dictionary.
        - self.post_call is called for all menu options AFTER all the procedures defined in the dictionary.
        
        Therefore a single menu option can execute up to 5 procedures in sequence.
        - self.pre_call gives a global 'preparation' routine to run before all menu options.
            If self.pre_call fails, the 'precall' and 'call' procedures are skipped, execution passes
            immediately to the 'postcall' and self.post_call procedures.
        - 'precall' gives an option specific preparation routine to run before the main option.
            If 'precall' fails, the 'call' procedure does not get executed, control passes immediately
            to the 'postcall' and self.post_call procedures.
        - 'call' is the main routine to run for the menu option.
            If self.pre_call or 'precall' options fail, the 'call' option is not executed, execution passes
            immediately to the cleanup 'postcall' and self.post_call procedures.
        - 'postcall' gives an option specific cleanup routine to run after the menu option even if it failed.
        - self.post_call gives a global cleanup routine to run after all menu options even if they failed.
        - 'close' when True the menu closes when the procedure completes. Otherwise the user returns to the menu.
                
        You can trigger user input via the Prompt() method.
        You can directly run a menu option without user input via the Run() method.
        """

    __version__ = '0.0.3'

    def __init__(self,dictionary,title='Menu',titlefg=None,titlebg=None,helpdir=None,helpurl=None,logger=None,labelwidth=23):
        """ Create the menu, load the dictionary.
            Initialize and validate the data.
            title = Title of menu.
            titlebg/fg colors of menu title.
            helpdir = directory where help text files exist. 
            helpurl = url to help file. """
        self.Dictionary = dictionary
        self.title = title
        self.IdWidth = 2
        self.LabelWidth = labelwidth
        self.titleFG = titlefg
        self.Columns = 2 # How many columns to draw?
        self.Log = logger # Can define a logging function to use.
        self.pre_call = None # Specify a procedure to call before ALL options.
        self.post_call = None # Specify a procedure to call AFTER ALL options.
        if titlefg == None: self.titleFG = TextColor.BLACK
        self.titleBG = titlebg
        if titlebg == None: self.titleBG = TextColor.YELLOW
        Counter = 0
        for key,value in self.Dictionary.items(): # Assign menu ID number to each entry.
            Counter += 1
            value['id'] = Counter
            value['enabled'] = True # All menu options are enabled and visible by default.
            self.LabelWidth = max(self.LabelWidth,len(value['label']))
            
            try: # Check that the procedure name to be called looks valid.
                if type(value['call']) != None: # This will fail if the procedure name is wrong.
                    pass
            except Exception as e:
                # The procedure call will not succeed if called.
                print (TextColor.red(self.title,'Cannot execute procedure',value['label']))
                print (TextColor.red(str(e)))
                traceback.print_exc()
                
            try: # Check that the pre-procedure name to be called looks valid.
                if type(value.get('precall',None)) != None: # This will fail if the procedure name is wrong.
                    pass
            except Exception as e:
                # The procedure call will not succeed if called.
                print (TextColor.red(self.title,'Cannot execute pre-procedure',value['label']))
                print (TextColor.red(str(e)))
                traceback.print_exc()
                
            try: # Check that the post-procedure name to be called looks valid.
                if type(value.get('postcall',None)) != None: # This will fail if the procedure name is wrong.
                    pass
            except Exception as e:
                # The procedure call will not succeed if called.
                print (TextColor.red(self.title,'Cannot execute post-procedure',value['label']))
                print (TextColor.red(str(e)))
                traceback.print_exc()
        self.help_dir = helpdir
        self.help_url = helpurl

    def GetHelpFile(self,menuid):
        """ Given an ID number, retrieve and display the help text if it exists. """
        filename = None
        for key,value in self.Dictionary.items(): # Find entry with matching ID.
            if value['id'] == menuid: # Found a match.
                filename = value.get('helpdoc',None) # Get the helpdoc filename.
                break # Look no further.
        if filename != None and self.help_dir != None:
            filename = self.help_dir + filename # Construct path to file.
        return filename
        
    def ShowHelpText(self,menuid):
        filename = self.GetHelpFile(menuid)
        if filename != None:
            try:
                with open(filename,'r') as f:
                    for line in f.readlines():
                        print (TextColor.cyan(line))
            except Exception as e:
                print(TextColor.red('Sorry, unable to show the help file.'))
                print(str(e))
        else:
            print (TextColor.red('Sorry, no help file is defined for menu item',menuid))
        
    def GetHelpUrl(self,menuid):
        """ Given an ID number, return URL associated with the help documentation. """
        helpurl = None
        for key,value in self.Dictionary.items(): # Find entry with matching ID.
            if value['id'] == menuid: # Found a match.
                helpurl = value.get('helpurl',None) # Get the helpdoc helpurl.
                break # Look no further.
        if helpurl != None and self.help_dir != None:
            helpurl = self.help_dir + helpurl # Construct path to file.
        return helpurl
        
    def Draw(self,menuprefix=''):
        """ Draw the menu on the terminal.
            The menu list from the dictionary will automatically gain '?' and 'x' options too. """
        # In Python 3.7 onwards, dictionaries should retain the sequence in which items are added. No sorting required.
        count = 0
        print (TextColor.clearforward()) # Blank line before menu and clear everything below that.
        print (TextColor.fgbgcolor(self.titleFG,self.titleBG,' ' + menuprefix + self.title + ' ')) # Menu title is painted in inverse colours. 
        for key,value in self.Dictionary.items(): # Go through each menu item in turn.
            if value['enabled'] == False: continue # Not visible or selectable, skip it.
            entry = TextColor.yellow(str(value['id']).rjust(self.IdWidth,' ')) + ' ' # ID number in yellow. 
            if value.get('color',None) != None: # Menu item has a specific label color.
                entry += value['color'](value['label'].ljust(self.LabelWidth,' ')[:self.LabelWidth])
            elif value.get('bold',False): # If the menu item is in bold, make it so.
                entry += TextColor.white(value['label'].ljust(self.LabelWidth,' ')[:self.LabelWidth])
            else: # Menu item is not in bold.
                entry += value['label'].ljust(self.LabelWidth,' ')[:self.LabelWidth]
            entry += ' ' # Space between columns of menu entries. 
            print (entry,end='') # Print the menu entry column, don't include 'newline' yet.
            count += 1 # Count how many entries.
            if count % self.Columns == 0: # Print 'newline' after 2nd column entry.
                print ('')
            if value.get('break',False): 
                if count % self.Columns != 0: # We're terminating the line early.
                    print ('')
                    count = 0
                print ('') # Insert a blank line break in the menu.
        if count % self.Columns != 0: # Print 'newline' if we didn't complete the 2nd column when the menu list ran out.
            print ('') # Terminate line if not already done.
        # Always include 'x' and '?' menu options automatically.
        print (TextColor.yellow('x'.rjust(self.IdWidth,' ')) + ' ' + 'Exit'.ljust(self.LabelWidth,' ')[:self.LabelWidth] + ' ',end='')
        print (TextColor.yellow('?'.rjust(self.IdWidth,' ')) + ' ' + 'Refresh'.ljust(self.LabelWidth,' ')[:self.LabelWidth])
        
    def Run(self,key):
        """ Given a menu option key, execute the procedure or sub-menu associated with it.
            if PRE and/or POST procedures are defined, execute those too. 
            These allow you to prepare and/or cleanup even if the main call fails. """
            
        ExecuteMain = True
        Success = True # Set the return code.
        
        # Global Pre procedure. # Execute BEFORE the main procedure call.
        if self.pre_call != None: # See if it's a callable function.
            try: # See if the pre-procedure will execute. 
                self.pre_call() # Call it.
            except Exception as e:
                # Procedure didn't execute. Report the error and return to the menu.
                print(TextColor.red(' *** OOPS! *** ',invert=True))
                print(TextColor.red('** Menu failed to execute ' + str(key) + " ; global pre-call " + str(self.pre_call)))
                print(TextColor.red(str(e)))
                traceback.print_exc()
                ExecuteMain = False # Do not execute the main call.
                Success = False # Set the return code.
                
        # Option Pre procedure. # Execute BEFORE the main procedure call.
        if ExecuteMain: # OK to proceed.
            Procedure = self.Dictionary[key].get('precall',None) # What pre-procedure is to be called?
            if Procedure != None: # See if it's a callable function.
                try: # See if the pre-procedure will execute. 
                    Procedure() # Call it.
                except Exception as e:
                    # Procedure didn't execute. Report the error and return to the menu.
                    print(TextColor.red(' *** OOPS! *** ',invert=True))
                    print(TextColor.red('** Menu failed to execute ' + str(key) + " ; option pre-call " + str(Procedure)))
                    print(TextColor.red(str(e)))
                    traceback.print_exc()
                    ExecuteMain = False # Do not execute the main call.
                    Success = False # Set the return code.
                
        # Main procedure.
        if ExecuteMain: # OK to proceed.
            Procedure = self.Dictionary[key]['call'] # What procedure is to be called?
            if Procedure == None: # No option to run.
                print(TextColor.yellow(str(key) + " does not have a related procedure to call."))
            elif type(Procedure) == type(self): # A submenu, so we trigger the nested submenu instead. 
                Procedure.prompt() # Execute the submenu.
            else: # See if it's a callable function.
                try: # See if the procedure will execute. 
                    Procedure() # Call it.
                except Exception as e:
                    # Procedure didn't execute. Report the error and return to the menu.
                    print(TextColor.red(' *** OOPS! *** ',invert=True))
                    print(TextColor.red('** Menu failed to execute ' + str(key) + " ; call " + str(Procedure)))
                    print(TextColor.red(str(e)))
                    traceback.print_exc()
                    Success = False # Set the return code.

        # Option Post procedure. # Execute AFTER the main procedure call.
        Procedure = self.Dictionary[key].get('postcall',None) # What post-procedure is to be called?
        if Procedure != None: # See if it's a callable function.
            try: # See if the post-procedure will execute. 
                Procedure() # Call it.
            except Exception as e:
                # Procedure didn't execute. Report the error and return to the menu.
                print(TextColor.red(' *** OOPS! *** ',invert=True))
                print(TextColor.red('** Menu failed to execute ' + str(key) + " ; option post-call " + str(Procedure)))
                print(TextColor.red(str(e)))
                traceback.print_exc()
                Success = False # Set the return code.

        # Global Post procedure. # Execute AFTER the main procedure call.
        if self.post_call != None: # See if it's a callable function.
            try: # See if the post-procedure will execute. 
                self.post_call() # Call it.
            except Exception as e:
                # Procedure didn't execute. Report the error and return to the menu.
                print(TextColor.red(' *** OOPS! *** ',invert=True))
                print(TextColor.red('** Menu failed to execute ' + str(key) + " ; global post-call " + str(self.post_call)))
                print(TextColor.red(str(e)))
                traceback.print_exc()
                Success = False # Set the return code.

        return Success # True if all succeeded, False if any failed.
        
    def ProcessHelpRequest(self,answer):
        """ Receive a text type menu id. 
            if it converts to an integer successfully, 
            show the help text associated with that menu item. """
        answer = answer.replace('?','') # Remove any question mark.
        try:
            menuid = int(answer)
        except:
            menuid = None
        if menuid != None:
            self.ShowHelpText(menuid)
        
    def prompt(self,menuprefix=''):
        """ Execute the menu. 
            This paints the menu on the terminal and deals with user selections. 
            Menu items are numbered dynamically, the user selects an item by selecting the number.
            If the user enters the number plus a '?' symbol then help text is displayed if it can be found.
            The method closes when the user selects the 'x' option. 
            
            Note, you can also trigger options from the menu without user prompting by using the menu.Run(name) method. """
        # Now paint the menu and ask the user what to do.
        self.Draw(menuprefix=menuprefix) # Paint the menu.
        closeflag = False
        while True: # Loop until explicitly told to terminate.
            if self.Log != None: self.Log('Menu waiting for user input.',terminal=False)
            answer = input(TextColor.cyan('Menu option : ')) # Prompt for input.
            if self.Log != None: self.Log('Menu received user input',answer,'.',terminal=False)
            if answer == '?': # Refresh the menu.
                self.Draw() # Refresh the menu.
                continue
            if answer == ">": # Increase columns in display.
                self.Columns += 1
                self.Draw() # Refresh the menu.
                continue
            if answer == "<": # Increase columns in display.
                self.Columns -= 1
                self.Columns = max(self.Columns,1) # must be at least 1 column.
                self.Draw() # Refresh the menu.
                continue
            if '?' in answer: # User wants help about an option.
                self.ProcessHelpRequest(answer)
                continue # Prompt again.
            # Process menu choice.
            try: # Convert text into integer if possible.
                menuid = int(answer)
            except Exception:
                # Text would not convert into integer. 
                menuid = None
            if menuid != None: # 
                found = False # Have we found and executed the menu option?
                closeflag = False # Don't close the menu.
                for key,value in self.Dictionary.items():
                    if value['enabled'] == False: continue # Not visible or selectable, skip it.
                    closeflag = self.Dictionary[key].get('close',False) # Should the menu close immediately?
                    if value['id'] == menuid:
                        self.Run(key) # Execute the option.
                        found = True # We have found and executed the option. OK to return to ask user for new input.
                        self.Draw() # Refresh the menu.
                        break # No need to check other key value pairs.
                if found: # Option was found and executed. Return to user input.
                    continue # Next user input.
            if closeflag: # The menu should shut down once the procedure has completed.
                break
            if answer.lower() == '?': # Refresh option chosen.
                self.Draw() # Refresh the menu.
                continue # Next user input.
            if answer.lower() == 'x': # User chose to quit the menu. Terminate the loop.
                break # Go UP a level, quit if at root.
            # User input was not recognised. Try again.
            print (TextColor.red("'" + str(answer) + "' Unrecognised. Try again."))

# -------------------------------------------------------------------------------------------------------------------------------- 

class OptionMenu:
    """ Simple menu driver.
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
                
                'id' is added automatically. It is the menu ID number.
                'enabled' is added automatically. It indicates that the menu option is currently visible and selectable.
                
        You can trigger user input via the Prompt() method.
        You can directly run a menu option without user input via the Run() method.
        """

    __version__ = '0.0.2'

    def __init__(self,dictionary,title='Options',titlefg=None,titlebg=None,helpdir=None,helpurl=None,logger=None,columns=2):
        """ Create the menu, load the dictionary.
            Initialize and validate the data.
            title = Title of menu.
            titlebg/fg colors of menu title.
            helpdir = directory where help text files exist. 
            helpurl = url to help file. 
            logger = pilomarlog.Log() instance (optional)
            columns = Initial number of columns to display the menu in."""
        self.Dictionary = dictionary
        self.title = title
        self.IdWidth = 2
        self.LabelWidth = 26
        self.titleFG = titlefg
        self.Columns = columns # How many columns to draw?
        self.Log = logger # Can define a logging function to use.
        if titlefg == None: self.titleFG = TextColor.BLACK
        self.titleBG = titlebg
        if titlebg == None: self.titleBG = TextColor.YELLOW
        Counter = 0
        for key,value in self.Dictionary.items(): # Assign menu ID number to each entry.
            Counter += 1
            #print("Adding:",Counter,value)
            value['id'] = Counter
            value['enabled'] = True # All menu options are enabled and visible by default.
            self.LabelWidth = max(self.LabelWidth,len(value['label']))
        self.help_dir = helpdir
        self.help_url = helpurl

    def GetHelpFile(self,menuid):
        """ Given an ID number, retrieve and display the help text if it exists. """
        filename = None
        for key,value in self.Dictionary.items(): # Find entry with matching ID.
            if value['id'] == menuid: # Found a match.
                filename = value.get('helpdoc',None) # Get the helpdoc filename.
                break # Look no further.
        if filename != None and self.help_dir != None:
            filename = self.help_dir + filename # Construct path to file.
        return filename
        
    def ShowHelpText(self,menuid):
        filename = self.GetHelpFile(menuid)
        if filename != None:
            try:
                with open(filename,'r') as f:
                    for line in f.readlines():
                        print (TextColor.cyan(line))
            except Exception as e:
                print(TextColor.red('Sorry, unable to show the help file.'))
                print(str(e))
        else:
            print (TextColor.red('Sorry, no help file is defined for menu item',menuid))
        
    def GetHelpUrl(self,menuid):
        """ Given an ID number, return URL associated with the help documentation. """
        helpurl = None
        for key,value in self.Dictionary.items(): # Find entry with matching ID.
            if value['id'] == menuid: # Found a match.
                helpurl = value.get('helpurl',None) # Get the helpdoc helpurl.
                break # Look no further.
        if helpurl != None and self.help_dir != None:
            helpurl = self.help_dir + helpurl # Construct path to file.
        return helpurl
        
    def Draw(self,menuprefix=''):
        """ Draw the menu on the terminal.
            The menu list from the dictionary will automatically gain '?' and 'x' options too. """
        # In Python 3.7 onwards, dictionaries should retain the sequence in which items are added. No sorting required.
        count = 0
        print (TextColor.clearforward()) # Blank line before menu and clear everything below that.
        print (TextColor.fgbgcolor(self.titleFG,self.titleBG,' ' + menuprefix + self.title + ' ')) # Menu title is painted in inverse colours. 
        for key,value in self.Dictionary.items(): # Go through each menu item in turn.
            if value['enabled'] == False: continue # Not visible or selectable, skip it.
            entry = TextColor.yellow(str(value['id']).rjust(self.IdWidth,' ')) + ' ' # ID number in yellow. 
            if value.get('color',None) != None: # Menu item has a specific label color.
                entry += value['color'](value['label'].ljust(self.LabelWidth,' ')[:self.LabelWidth])
            elif value.get('bold',False): # If the menu item is in bold, make it so.
                entry += TextColor.white(value['label'].ljust(self.LabelWidth,' ')[:self.LabelWidth])
            else: # Menu item is not in bold.
                entry += value['label'].ljust(self.LabelWidth,' ')[:self.LabelWidth]
            entry += ' ' # Space between columns of menu entries. 
            print (entry,end='') # Print the menu entry column, don't include 'newline' yet.
            count += 1 # Count how many entries.
            if count % self.Columns == 0: # Print 'newline' after 2nd column entry.
                print ('')
            if value.get('break',False): 
                if count % self.Columns != 0: # We're terminating the line early.
                    print ('')
                    count = 0
                print ('') # Insert a blank line break in the menu.
        if count % self.Columns != 0: # Print 'newline' if we didn't complete the 2nd column when the menu list ran out.
            print ('') # Terminate line if not already done.
        # Always include 'x' and '?' menu options automatically.
        print (TextColor.yellow('x'.rjust(self.IdWidth,' ')) + ' ' + 'Exit'.ljust(self.LabelWidth,' ')[:self.LabelWidth] + ' ',end='')
        print (TextColor.yellow('?'.rjust(self.IdWidth,' ')) + ' ' + 'Refresh'.ljust(self.LabelWidth,' ')[:self.LabelWidth])
        
    def Select(self,key):
        """ Given a menu option key, extract the selected value. """
        result = self.Dictionary[key]['value'] # What procedure is to be called?
        return result

    def ProcessHelpRequest(self,answer):
        """ Receive a text type menu id. 
            if it converts to an integer successfully, 
            show the help text associated with that menu item. """
        answer = answer.replace('?','') # Remove any question mark.
        try:
            menuid = int(answer)
        except:
            menuid = None
        if menuid != None:
            self.ShowHelpText(menuid)
        
    def prompt(self,menuprefix=''):
        """ Execute the menu. 
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
        self.Draw(menuprefix=menuprefix) # Paint the menu.
        result = None # The actual choice. None if nothing chosen.
        found = False # Set to True if a choice is successfully made, else False is returned.
        while True: # Loop until explicitly told to terminate.
            if self.Log != None: self.Log('Menu waiting for user input.',terminal=False)
            answer = input(TextColor.cyan('Choose option : ')) # Prompt for input.
            if self.Log != None: self.Log('Menu received user input',answer,'.',terminal=False)
            if answer == '?': # Refresh the menu.
                self.Draw() # Refresh the menu.
                continue
            if answer == ">": # Increase columns in display.
                self.Columns += 1
                self.Draw() # Refresh the menu.
                continue
            if answer == "<": # Increase columns in display.
                self.Columns -= 1
                self.Columns = max(self.Columns,1) # must be at least 1 column.
                self.Draw() # Refresh the menu.
                continue
            if '?' in answer: # User wants help about an option.
                self.ProcessHelpRequest(answer)
                continue # Prompt again.
            # Process menu choice.
            try: # Convert text into integer if possible.
                menuid = int(answer)
            except Exception:
                # Text would not convert into integer. 
                menuid = None
            if menuid != None: # 
                found = False # Have we found and executed the menu option?
                for key,value in self.Dictionary.items():
                    if value['enabled'] == False: continue # Not visible or selectable, skip it.
                    if value['id'] == menuid:
                        result = self.Select(key) # Choose the selected value to return.
                        found = True # We have found and selected the option.
                        break # Next
                if found: break
            if answer.lower() == '?': # Refresh option chosen.
                self.Draw() # Refresh the menu.
                continue # Next user input.
            if answer.lower() == 'x': # User chose to quit without selecting anything. Terminate the loop.
                found = None # Nothing was chosen.
                break # Go UP a level, quit if at root.
            # User input was not recognised. Try again.
            print (TextColor.red("'" + str(answer) + "' Unrecognised. Try again."))
        return result, found

# -------------------------------------------------------------------------------------------------------------------------------- 

class ListChooser:
    """ Create a list of values and allow the user to select within that list.
        The search is recursive. 
        List entries are matched on anything containing the user's string. 
        If multiple entries remain, they are presented as a new list to choose from. 
        '?' to show list. 
        'x' to return to previous selection. """

    __version__ = '0.0.4'
        
    def __init__(self,inputlist,title=None,default=None,compress=True):
        self.FullList = inputlist
        self.title = title
        self.default = default
        self.Compress = compress # Long lists get compressed.
    
    def Print(self,inputlist):
        """ Supports self.Filter method. 
            Lists the choices to select from. 
            Abbreviates the list if > 10 entries, otherwise shows them all. """
        printlist = ''
        if self.Compress and len(inputlist) > 10: # Big list and we're allowed to compress it.
            for i in range(5):
                printlist += inputlist[i] + ', '
            printlist += ' ... to ... '
            for i in range(-5,0):
                printlist += ', ' + inputlist[i]
        else: # Short list or we're not allowed to compress it, so show everything.
            for i,n in enumerate(inputlist):
                if i > 0: printlist += ', '
                printlist += n
        print(printlist)
        
    def Filter(self,inputlist):
        """ Recursive!!! 
            Receive a list of text items.
            User must select one of them.
            This lists the choices and lets the user narrow down the list if it's big.
            Returns when the user has selected a single item or decided to select nothing. """
        choice = []
        while True:
            choice = []
            self.Print(inputlist)
            inputtext = input(TextColor.cyan("Choice ('x' to return) : "))
            inputtext = inputtext.lower()
            if inputtext == 'x': break # Quit.
            if len(inputtext) < 1: continue # Nothing to check, ask again.
            for i in inputlist:
                if inputtext in i.lower(): choice.append(i)
                if inputtext == i.lower(): 
                    choice = [i] # Exact match.
                    break # Look no further.
            if len(choice) < 1: 
                print(TextColor.red("'" + inputtext + "' is not in the list."))
                continue # Nothing matched, ask again.
            if len(choice) > 1 and choice != inputlist: choice = self.Filter(choice) # Refine the list further.
            if len(choice) == 1: break # Choice made, return.
        return choice

    def prompt(self):
        """ Receive a list and return the user's selection or None value. """
        result = self.Filter(self.FullList)
        if len(result) == 0: result = None # Return None value, nothing chosen. 
        elif len(result) == 1: result = result[0] # Strip the list structure off.
        # In all other cases return the selected list.
        return result
    
    # Alias for compatibility with target_chooser
    Prompt = prompt
    
# -------------------------------------------------------------------------------------------------------------------------------- 

class FileChooser:
    """ Allow a user to browse and select a file from disc. 
    
        Define where you want to start the search. 
        User selects a file from there, or navigates the directory structure.
        
        Returns the chosen file and a 'success' flag. 
        
        Example ------------------------------------------------------
        FC = FileChooser(title='Choose an image file',default='/home/pi/pilomar/data/',types=['jpg','jpeg'])
        chosen_file, success = FC.ChooseFile()
        if success: 
            print("Chose",chosen_file)
        else:
            print("No file chosen")
            
        """
    
    def __init__(self,title,default=None,types=None):
        """ default = Default location to open browser.
                      If NONE: pwd is used.
                      If folder is not found, the parent is chosen.
            types = optional list of file types.
                    If NONE: All files are listed. """
        self.title = title
        self.defaultDir = default
        self.current_dir = default
        self.FileTypes = types

    def ToPathType(self,filepath):
        """ Make sure filepath is a Path type.
            When referring to file and folder names in the code it is easy to confuse string and Path objects.
            This makes sure that you are always using a Path object by converting string values to Path objects. """
        if type(filepath) != Path:
            filepath = Path(filepath)
        return filepath
    
    def PathExists(self,folderpath):
        """ Return TRUE if a path exists. Else False. """
        folderpath = self.ToPathType(folderpath) # Convert to Path object.
        return folderpath.exists()
        
    def NameOnly(self,folderpath):
        """ Strip full path, return only the name of the file. """        
        folderpath = self.ToPathType(folderpath) # Convert to Path object.
        return folderpath.name

    def IsFile(self,folderpath):
        """ Return TRUE if a path points to a file. Else False. """
        folderpath = self.ToPathType(folderpath) # Convert to Path object.
        return folderpath.is_file()

    def IsDir(self,folderpath):
        """ Return TRUE if a path points to a file. Else False. """
        folderpath = self.ToPathType(folderpath) # Convert to Path object.
        return folderpath.is_dir()
        
    def GetParent(self,filepath):
        """ Return PARENT of a folder. """
        filepath = self.ToPathType(filepath)        
        return filepath.parent
        
    def IsType(self,filepath, filetype, casesensitive=False):
        """ Return TRUE if the path is a file matching filetype. 
            filepath is the path to check.
            filetype can be a single value or a list that must be matched.
            casesensitive controls whether case must match. 
            File does not need to exist on disc. """
        if type(filetype) == str: filetype = [filetype] # Convert to list in all cases.
        filepath = self.ToPathType(filepath) # Convert to Path object.
        foundtype = filepath.suffix.replace('.','') # Get suffix (file type) and drop the '.' separator.
        result = False 
        if casesensitive: # Perform case sensitive match.
            if foundtype in filetype: # We found a match.
                result = True
        else: # Not case sensitive.
            filetype = [ft.lower() for ft in filetype] # Convert to lower case.
            if foundtype.lower() in filetype:
                result = True
        return result

    def VerifyFolder(self,folder=None):
        """ Given a folder name, make sure it exists, if it doesn't return the closest parent. 
            If none exist, return home directory. """
        if folder == None: 
            folder = Path.home() # returns user's home directory
        folder = self.ToPathType(folder)
        keeplooking = True # Keep searching for a valid path?
        while keeplooking:
            if self.pathExists(folder) and self.IsDir(folder): # Found valid folder.
                keeplooking = False
                break
            # This isn't valid, try parent.
            try:
                folder = folder.parent
            except:
                folder = None
                break
        if folder == None: 
            folder = Path.home() # returns user's home directory
        return folder
    
    def FileList(self,show_files=True,show_folders=True,must_exist=True):
        """ Return dictionary of files and subfolders in current folder. 
            Parameters ------------------------------------------------------
            show_files : True - will list files found.
            show_folders : True - will list folders found.
            must_exist : True - can only select existing files.
                         False - user can enter a filename that does not exist.
            Outputs ---------------------------------------------------------
            Dictionary list of files and folders identified.
            
            The list is sorted,
              1st entry is always the parent directory. 
              2nd set of entries are always the sub-directories. 
              3rd set of entries are the files. 
              directory and file groups are alphabetically sorted. """
        self.current_dir = self.VerifyFolder(self.current_dir)
        dirs = []
        files = []
        result = {}
        if show_folders: result[".."] = {'value':str(self.GetParent(self.current_dir)), 'label':'..', 'type':'dir', 'color':TextColor.cyan} # Always allow UP to parent.
        for root, dirs, files in os.walk(str(self.current_dir)):
            if show_folders:
                for entry in sorted(dirs):
                    fn = entry.split("/")[-1]
                    result[fn] = {'value':root + "/" + entry, 'label':fn, 'type':'dir', 'color':TextColor.cyan} # Folders show in CYAN.
            if show_files:
                for entry in sorted(files):
                    fn = entry.split("/")[-1]
                    ty = fn.split(".")[-1] # Get file type.
                    filepath = root + "/" + entry
                    if self.FileTypes == None or self.IsType(filepath, self.FileTypes, casesensitive=False):
                        result[fn] = {'value':filepath, 'label':fn, 'type':'file'}
            break
        if not must_exist:
            result['+'] = {'value':'+', 'label':'New file', 'type':'file', 'color':TextColor.yellow} # NEW file option is in YELLOW.
        return result

    def ChooseFile(self):
        """ Use the listchooser class to present a list of files and folders, 
            let the user select one.
            User can navigate up/down directory tree looking for appropriate files.
            Outputs ------------------------------------------------------------
            chosen_file : Full path to chosen file.
                          None if nothing selected.
            found : True if file chosen.
                    False if file was not found.
                    None if user quit without choosing anything. """
        chosen_file = None
        found = False
        title = self.title 
        if type(self.FileTypes) == list and len(self.FileTypes) > 0:
            title = (title + " " + str(self.FileTypes)).strip()
        while chosen_file == None:
            options = self.FileList() # List all the files and subfolders in the chosen directory.
            OptionMenu = OptionMenu(options,title) # Create new option menu for the current directory.
            chosen_file, found = OptionMenu.prompt() # Ask the user to select a file from the list.
            # chosen_file = full path chosen.
            # found = Was a choice made?
            if found and self.IsDir(chosen_file): # Directory
                self.current_dir = chosen_file # Switch to chosen directory
                chosen_file = None
                continue # Try again.
            if found and chosen_file == '+': # User can create new file here.
                tf = input(TextColor.cyan("Enter filename:")).trim()
                if tf == '': # Nothing entered.
                    chosen_file = None
                    continue # Try again.
                chosen_file = self.current_dir + "/" + tf
            #print("ChosenItem:",chosen_file,found)
            break # The choice is made.
        return chosen_file, found
        
# -------------------------------------------------------------------------------------------------------------------------------- 


# Backward compatibility aliases
menu = Menu
proceduremenu = ProcedureMenu
optionmenu = OptionMenu
listchooser = ListChooser
filechooser = FileChooser
