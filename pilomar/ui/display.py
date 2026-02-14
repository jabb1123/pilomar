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

__version__ = '0.1.0'

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from .text_color import TextColor


class CdSprite:
    """ This is a subclass of the colordisplay class.
        It represents 'sprites' that can be defined to move across the colordisplay buffer. 
        Originally intended to create moving markers against a set background grid. """
        
    __version__ = '0.0.1'
        
    def __init__(self,name,symbol,row=None,col=None,fg=0,bg=15,level=0):
        self.row = row
        self.column = col
        self.fg = fg
        self.bg = bg
        self.symbol = symbol
        self.name = name
        self.display = False
        self.level = level

    def colored_symbol(self):
        """ Return symbol with embedded terminal colour codes set. """
        result = result = TextColor.fgbgcolor(self.fg,self.bg,self.symbol)
        return result
        
    def label(self,color=False):
        """ Return colour coded label for the sprite. 
            Used in the key to a display.
            color=False means color is not set, plaintext is returned instead. """
        if color: result = TextColor.fgbgcolor(self.fg,self.bg,self.symbol)
        else: result = self.symbol
        result += ' = ' + self.name
        return result

# -------------------------------------------------------------------------------------------------------------------------------- 

class MessageWindow:
    """ Class to create a simple scrolling text window and to display on the terminal as needed. 
        Superceded by colordisplay class now - which contains all same functionalities. """
    
    __version__ = '0.0.1'
    
    def __init__(self,rows,columns,row=None,col=None,fg=15,bg=0,title=None):
        print (TextColor.red('TextColor.messagewindow(): Deprecated in favour of TextColor.ColorDisplay().'))
        self.display_rows = rows # How many rows deep is the display?
        self.display_columns = columns # How many columns wide is the display?
        self.display_row = row # What's the location of the 1st cell in the display on the actual terminal?
        self.display_col = col
        if row == None: # Location of the last row in the display.
            self.last_display_row = None
        else:
            self.last_display_row = row + rows - 1
        if col == None: # Location of the last column in the display.
            self.last_display_col = None
        else:
            self.last_display_col = col + columns - 1
        self.DefaultFG = fg # What's the default foreground colour?
        self.DefaultBG = bg # What's the default background colour?
        self.DefaultChar = ' '
        self.Lines = []
        self.title = title # Is there a title to the window? (Will keep 1st row static)
        if self.title != None:
            self.Lines.append(' ') # Occupy the first line of the display, because the title will overwrite it.
            if len(self.title) > self.display_columns: # Title cannot exceed window width.
                self.title = self.title[:self.display_columns]
        self.Wrap = True # Long text will wrap onto multiple lines.
        self.Log = None # Can store handle to a 'Log' method for logging messages. Needs to be defined and assigned by the calling program.
        self.RefreshRate = None # Can specify how quickly the display refreshes (in seconds).
        self.LastRefresh = None # When did the display last update?

    def SetRefreshRate(self,rate):
        """ Set selected refresh rate and reset the refresh timer. """
        self.RefreshRate = rate
        self.LastRefresh = None
        
    def RefreshDue(self):
        """ Return True if refresh is due, else False. """
        result = False
        if self.RefreshRate == None: result = True # There's no restriction so always refresh. 
        elif self.LastRefresh == None: result = True # Need to do initial drawing. 
        elif (datetime.now() - self.LastRefresh).total_seconds() >= self.RefreshRate: result = True # Refresh is due.
        return result 

    def Clear(self,immediate=False):
        """ Clear the window. """
        self.Lines = []
        if self.title != None: self.Lines.append(' ')
        if immediate: self.display()

    def display(self,screenheight=None,screenwidth=None,immediate=False):
        """ Display the window.
            If specific location has been given for the window AND the current screen size is given in screenheight/screenwidth
            this can check that the space exists in the current display size. It will only draw the window if there is enough space. """
        if immediate == False and self.RefreshDue() == False: return # Don't perform a refresh yet.
        if self.last_display_row != None and screenheight != None: # We have a specific location to use, check if that location is in the current display dimensions.
            if screenheight < self.last_display_row: # Not enough height.
                return # Don't try to display.
        if self.last_display_col != None and screenwidth != None:
            if screenwidth < self.last_display_col: # Not enough width.
                return # Don't try to display.
        for r in range(self.display_rows):
            if len(self.Lines) >= r + 1:
                line = self.Lines[r]
            else:
                line = ' '
            if r == 0 and self.title != None:
                line = self.title # 1st row is always the 'title' if specified. 
                line = TextColor.fgbgcolor(self.DefaultBG,self.DefaultFG,line.ljust(self.display_columns,' '))
            else:
                line = TextColor.fgbgcolor(self.DefaultFG,self.DefaultBG,line.ljust(self.display_columns,' '))
            if self.display_row != None and self.display_col != None:
                # The display has a specific location on the terminal window. Place it there.
                dr = self.display_row + r
                dc = self.display_col
                line = TextColor.cursor(dc,dr) + line
            print(line)
        self.LastRefresh = datetime.now()

    def Print(self,*args):
        line = ''
        for i in args:
            if len(line) > 0: line += ' '
            line += str(i)
        if not self.Wrap: # Don't wrap text, just truncate if it is wider than display.
            line = line[:self.display_columns] # Truncate the line.
        else: # Wrap long text onto multiple display lines.
            while len(line) > 0:
                self.Lines.append(line[:self.display_columns])
                if len(line) > self.display_columns:
                    line = line[self.display_columns:] # Remainder of text not yet displayed.
                else:
                    line = '' # Nothing left to display.
        while len(self.Lines) > self.display_rows:
            # temp = self.Lines.pop(0)
            self.Lines.pop(0)

# -------------------------------------------------------------------------------------------------------------------------------- 

class BigLetters:
    """ Primitive large font sizes. """
    def __init__(self):
        self.LetterDictionary = {}
        self.InitialiseLD()
        
    def InitialiseLD(self):
        self.LetterDictionary = {}
        self.LetterDictionary['unknown'] = ["#####","# # #","## ##","# # #","#####"]
        self.LetterDictionary[' '] =       ["     ","     ","     ","     ","     "]
        self.LetterDictionary['"'] =       [" # # "," # # ","     ","     ","     "]
        self.LetterDictionary["'"] =       ["  #  ","  #  ","     ","     ","     "]
        self.LetterDictionary['0'] =       ["#####","#  ##","# # #","##  #","#####"]
        self.LetterDictionary['1'] =       ["   # ","  ## ","   # ","   # "," ####"]                                      
        self.LetterDictionary['2'] =       ["#####","    #","#####","#    ","#####"]                                      
        self.LetterDictionary['3'] =       ["#####","    #","#####","    #","#####"]                                      
        self.LetterDictionary['4'] =       ["#   #","#   #","#####","    #","    #"]                                      
        self.LetterDictionary['5'] =       ["#####","#    ","#####","    #","#####"]                                      
        self.LetterDictionary['6'] =       ["#####","#    ","#####","#   #","#####"]                                      
        self.LetterDictionary['7'] =       ["#####","    #","    #","    #","    #"]                                      
        self.LetterDictionary['8'] =       ["#####","#   #","#####","#   #","#####"]                                      
        self.LetterDictionary['9'] =       ["#####","#   #","#####","    #","    #"]                                      
        self.LetterDictionary['.'] =       ["     ","     ","     ","     ","  #  "]                                      
        self.LetterDictionary[','] =       ["     ","     ","     ","  ## ","   # "]                                      
        self.LetterDictionary[':'] =       ["     ","  #  ","     ","  #  ","     "]                                      
        self.LetterDictionary['!'] =       ["  #  ","  #  ","  #  ","     ","  #  "]                                      
        self.LetterDictionary['-'] =       ["     ","     "," ### ","     ","     "]                                      
        self.LetterDictionary['+'] =       ["     ","  #  "," ### ","  #  ","     "]                                      
        self.LetterDictionary['*'] =       ["  #  ","# # #"," ### "," # # ","#   #"]                                      
        self.LetterDictionary['='] =       ["     "," ### ","     "," ### ","     "]                                      
        self.LetterDictionary['?'] =       [" ### ","#   #","  ## ","     ","  #  "]                                      

    def GetLetter(self,letter):
        """ Return letter pattern. """
        if letter in self.LetterDictionary: return self.LetterDictionary[letter]
        else: return self.LetterDictionary['unkown']
        
    def GenerateText(self,originaltext):
        """ Given original text, generate the BigLetters version of it. """
        lines = [[] for i in range(5)] # Create 5 empty lines.
        for character in originaltext:
            LD = self.GetLetter(character) # Returns 5 character lines.
            for i,LL in enumerate(LD): # Parse each line in turn.
                lines[i].append(LL + ' ')
        return lines

# -------------------------------------------------------------------------------------------------------------------------------- 

class Field:
    """ A data field in a colordisplay window.

        Field can be regular data fields or progress bars. """
    
    __version__ = '0.0.2'
    
    def __init__(self,name,row,col,length=10,justify='l'):
        """ justify = 'l' left, 'r' right. """
        # Common attributes
        self.Name = name
        self.Row = row
        self.Column = col
        self.Length = length
        self.Value = None
        self.Justify = justify # 'left','centre','right'
        self.Type = 'Data' # 'Data' field or 'ProgressBar'
        self.FGColor = None # Current color if it differs from the display defaults.
        self.BGColor = None
        # Progress bar specific attributes.
        self.PBMin = None # Minimum value of a progress bar field.
        self.PBMax = None # Maximum value of a progress bar field.
        self.PBFG = TextColor.GREEN # 'done' color of bar.
        self.PBBG = TextColor.YELLOW # 'todo' color of bar.
        # Colors used for ranges of values.
        self.BadFG = None # LOWLOW and HIGHHIGH values use these colors
        self.BadBG = None # LOWLOW and HIGHHIGH values use these colors
        self.PoorFG = None # LOW and HIGH values use these colors
        self.PoorBG = None # LOW and HIGH values use these colors
        # Special effects.
        self.BlinkRate = 0 # Seconds between changing FG/BG colors when blinking. 0 = No blink.
        self.BlinkColors = [[TextColor.WHITE,TextColor.BLACK],[TextColor.RED,TextColor.BLACK]] # FG/BG pairs to alternate between when blinking.
        
    def Justified(self):
        sval = str(self.Value) # Convert to string.
        jcode = self.Justify[0].lower()
        if len(sval) < self.Length: # Does the field need padding?
            if jcode == 'r': sval = sval.strip().rjust(self.Length)
            elif jcode == 'c': sval = sval.strip().center(self.Length)
            else: sval = sval.strip().ljust(self.Length)
        return sval

# -------------------------------------------------------------------------------------------------------------------------------- 

class ColorDisplay:
    """ Class to create a coloured character display buffer, and to display on the terminal as needed.
    
        Offers three basic modes of operation:
        1) Operate as addressible screen space
        2) Operate as simple scrolling text windows
        3) Operate as a form with defined data fields
        
        Supports sprites. """
    
    __version__ = '0.0.6'
    DefinedWindows = [] # Handles of all defined windows. Useful for scanning/updating all available windows.
                        # The defining class contains some methods which can perform general updates via this list.
    CDLayout = [] # Array of major rows/columns that colordisplay instances can self-align with.
                  # Each entry defines a high level 'column' of colordisplay locations. [[fromcol,colwidth],[fromcol,colwidth],...]
                  # When defining new colordisplay instances you can then just refer to these columns rather than tailoring the coordinates of each individual window.

    @staticmethod
    def AddCDEntry(colwidth,startcol=None):
        """ Add new entry to the colordisplay.CDLayout list.
            You must assign colwidth, but startcol is optional.
            If startcol is not specified, the next available one is assigned. 
            
            CDLayout is a list of display columns that individual colordisplay instances can be placed in. 
            This is used to simplify the creation of multi-panel displays. """
        if startcol == None: # Starting column isn't specified, so calculate the next available one.
            startcol = 1 # Find the next free one. 1st column if nothing exists yet.
            for cd in colordisplay.CDLayout: # Check each layout already defined.
                temp = cd[0] + cd[1]
                if temp >= startcol: startcol = temp + 1 # Start at next free column (with 1 space for border).
        startcol = max(startcol,1) # Must be at least 1 (1st column)
        colordisplay.CDLayout.append([startcol,colwidth])
        return True
    
    def __init__(self,rows,columns=None,name='',row=None,col=None,fg=15,bg=0,FirstScrollRow=0,title=None,rjtitle=None,titlefg=None,titlebg=None,borderfg=None,borderbg=None,cdlayout=None):
        """ fg and bg parameters can be single integer value (0-255) or a list of values [(0-255),(0-255),..] 
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
            cdlayout = index of the colordisplay.CDLayout list. A shortcut to set col and or row values more dynamically.
            -------------------------
            After instantiation, you can also set self.ClipWindow = True to allow the window to truncate display if insufficient realestate available.
               Otherwise the entire window will be suppressed until the display is big enough to accomodate the entire window. """
        self.DisplayName = name # A label for the display instance.
        if columns == None and cdlayout == None:
            raise Exception("colordisplay.__init__(): You must specify columns or cdlayout parameter to define a window.")
        if self.DisplayName == '':
            self.DisplayName = "win_" + str(len(colordisplay.DefinedWindows)) # Generate a default name.
        self.display_rows = rows # How many rows deep is the display?
        self.CDEntry = cdlayout # If using predefined columns, make a note which one we're using.
        if self.CDEntry != None and self.CDEntry >= 0 and self.CDEntry < len(colordisplay.CDLayout): # Automatically assign location on the screen.
            # Use the CDLayout list of window columns to define the start column.
            col = colordisplay.CDLayout[self.CDEntry][0] # Pull the start character column from the CDLayout list.
            columns = colordisplay.CDLayout[self.CDEntry][1] # Pull the character column width from the CDLayout list.
            row = 1
            for cd in colordisplay.DefinedWindows: # Stack each new window beneath previous ones in a column.
                if cd.CDEntry == self.CDEntry and cd.last_display_row >= row: row = cd.last_display_row + 2 # Start at next free row (with 1 row for border).
        self.display_columns = columns # How many columns wide is the display?
        self.display_row = row # What's the location of the 1st cell in the display on the actual terminal?
        self.display_col = col
        if self.display_row != None and self.display_rows != None:
            self.last_display_row = self.display_row + self.display_rows - 1 # Where does the display END ?  
        else:
            self.last_display_row = None
        if self.display_col != None and self.display_columns != None:
            self.last_display_col = self.display_col + self.display_columns
        else:
            self.last_display_col = None
        if type(fg) == list: # For scrolling displays you can provide a list of alternating text colors to use. This visually separates individual entries.
            self.DefaultFG = fg[0] # What's the default foreground color?
            self.DefaultFGs = fg
        else:
            self.DefaultFG = fg # What's the default foreground color?
            self.DefaultFGs = [fg]
        self.FGColorCount = len(self.DefaultFGs) # How many colors are available?
        self.FGColorIndex = 0 # Which color do we start with if multiple available?
        if type(bg) == list: # For scrolling displays you can provide a list of alternating background colors to use. This visually separates individual entries.
            self.DefaultBG = bg[0] # What's the default background color?
            self.DefaultBGs = bg # List of all background colors.
        else:
            self.DefaultBG = bg # What's the default background color?
            self.DefaultBGs = [bg] # List of all background colors.
        self.BGColorCount = len(self.DefaultBGs) # How many colors are available?
        self.BGColorIndex = 0 # Which color do we start with if multiple available?
        self.titleFG = titlefg # What color is the title row?
        if self.titleFG == None: self.titleFG = self.DefaultBG # Default to inverse.
        self.titleBG = titlebg # What color is the title row?
        if self.titleBG == None: self.titleBG = self.DefaultFG # Default to inverse.
        self.BorderFG = borderfg # What color is the border?
        if self.BorderFG == None: self.BorderFG = self.DefaultFG # Default is same as general window.
        self.BorderBG = borderbg # What color is the border.
        if self.BorderBG == None: self.BorderBG = self.DefaultBG # Default is same as general window.
        # Create array of each cell in the window, we need character, foreground color and background color.
        self.fgcolor = [[self.DefaultFG for c in range(self.display_columns)] for r in range(self.display_rows)] # Foreground colour of each character.
        self.bgcolor = [[self.DefaultBG for c in range(self.display_columns)] for r in range(self.display_rows)] # Background colour of each character.
        self.character = [[" " for c in range(self.display_columns)] for r in range(self.display_rows)] # Characters to display.
        # Store the default state of the window here. This is used if the window is 'cleared'.
        self.default_fgcolor = [[self.DefaultFG for c in range(self.display_columns)] for r in range(self.display_rows)] # Foreground colour of each character.
        self.default_bgcolor = [[self.DefaultBG for c in range(self.display_columns)] for r in range(self.display_rows)] # Background colour of each character.
        self.default_character = [[" " for c in range(self.display_columns)] for r in range(self.display_rows)] # Characters to display.
        self.PrevLineStrings = [None for r in range(self.display_rows)] # List of the display commands last issued to paint the display. Used to check for changes.
        self.ReduceIO = False # If set to true, Display() method will only update lines of the display that it thinks have changed.
        self.sprites = [] # List of any active sprites in the display.
        self.PrintHistory = [] # Cache of recently printed lines, used for repainting and exporting.
        self.FirstScrollRow = FirstScrollRow # 0 means data starts at the first row of the window, 1 means there's a title or something in row 0, etc. Scrolling takes this into account.
        self.Log = None # Can store handle to a 'Log' method for logging messages. Needs to be defined and assigned by the calling program.
        self.RefreshRate = None # Can specify how quickly the display refreshes (in seconds).
        self.LastRefresh = None # When did the display last update?
        self.Fields = [] # List of fields if defined.
        self.MarkDisplay = False # If TRUE the corners are highlighted in RED, and the FIELDS are highlighted in YELLOW(for layout checking)
        if title != None: self.WindowTitle = ' ' + title.strip()
        else: self.WindowTitle = None
        if rjtitle != None: self.RJTitle = rjtitle.strip() + ' ' # A secondary title that is right justified on top of the title line.
        else: self.RJTitle = None
        if self.WindowTitle != None: self.SetTitle()
        self.ClipWindow = False # If TRUE, the window can be clipped to fit available terminal display. This will simply truncate.
        self.DrawBorder = False # If TRUE, an additional single line border is drawn on the RIGHT and BOTTOM of the window. Takes 1 extra character in each dimension.
        self.BorderFG = self.DefaultFG
        self.BorderBG = self.DefaultBG
        colordisplay.DefinedWindows.append(self) # Add this window to the global list of all windows.

    def __del__(self):
        """ Remove this window from the list of defined windows.
            *Q* This is called by the garbage collector (not guaranteed), so may not be the smartest way to do this. """
        for i,w in enumerate(colordisplay.DefinedWindows):
            if w == self: # Found myself in the list. Remove and quit.
                del colordisplay.DefinedWindows[i]
                break

    def SetTitle(self):
        """ Turn first row of a window into a title row.
            Color appropriately and change the scroll behaviour of the window.
            1st line nolonger scrolls. """
        if self.WindowTitle == None: # Deactivate the title line.
            self.FirstScrollRow = 0
            for c in range(self.display_columns):
                self.fgcolor[0][c] = self.DefaultFG # Regular colors if no title.
                self.bgcolor[0][c] = self.DefaultBG # Regular colors if no title.
        else: # Activate the title line.
            self.FirstScrollRow = 1
            temp = (self.WindowTitle + (' ' * self.display_columns))[:self.display_columns] # Pad out to full window width.
            for c in range(self.display_columns):
                self.character[0][c] = temp[c] # Add title to window display top line.
                self.fgcolor[0][c] = self.titleFG # Invert colors for titles.
                self.bgcolor[0][c] = self.titleBG # Invert colors for titles.
            if self.RJTitle != None: # There is a right justified element to the title to add.
                sc = self.display_columns - len(self.RJTitle)
                for i in range(len(self.RJTitle)): # Work backwards because we are right justifying this on top of existing title.
                    c = sc + i # Where does the character go?
                    self.character[0][c] = self.RJTitle[i]

    def ReadTitleRow(self):
        """ Read the title row directly from the buffer. """
        line = ''
        for c in range(self.display_columns):
            line += self.character[0][c]
        return line

    def AddField(self,name,row,column,length=10,justify='l'):
        """ Add a field to the list of fields recognised in this window. 
            Duplicates are allowed. """
        self.Fields.append(Field(name=name,row=row,col=column,length=length,justify=justify))
        return True

    def InitializeProgressBar(self,name,minval,maxval,fg=None,bg=None):
        """ Prime a field as a progress bar. """
        FoundIt = False
        for f in self.Fields:
            if f.Name == name: # Will initialize multiple fields with same name.
                FoundIt = True
                f.PBMin = minval
                f.PBMax = maxval
                f.Type = 'ProgressBar'
                if fg != None: f.PBFG = fg # Set the 'DONE' color
                if bg != None: f.PBBG = bg # Set the 'TODO' color
        return FoundIt
    
    def ScanForFields(self,startchar='[',endchar=']'):
        """ Scan the current display looking for fields.
            Fields are marked by '[name    ]' strings.
            If no name, then a sequence number is assigned as a name. 
            '[]' would represent a 2 character field (assigned a sequence number name automatically). 
            ']' would represent a 1 character field (assigned a sequence number name automatically).
            Set the 'default' display before calling this. 
            Start and End field characters are '[' and ']' by default, but you can change 'em if needed
            via the startchar and endchar parameters. """
        startchar = (startchar.strip() + '[')[0] # 1 character only, and failsafe to the default char.
        endchar = (endchar.strip() + ']')[0] # 1 character only, and failsafe to the default char.
        nextid = 0 # Default ID for fields with no name.
        for r in range(self.display_rows): # Process each display row individually.
            start = None # Fields cannot span multiple lines.
            name = ''
            for c in range(self.display_columns): # Scan across the characters of the line.
                if self.character[r][c] == endchar and start != None: # End of field marker, and there was a start marker!
                    nextid += 1
                    if name == '': # No name yet. Assign default.
                        name = str(nextid)
                    self.AddField(name=name,row=r,column=start,length=(c - start) + 1)
                    start = None # Clear the 'working' field name values ready for next field we find.
                    name = ''
                if self.character[r][c] == startchar: # Start of field marker.
                    start = c
                if start != None: # We're in a field.
                    if not self.character[r][c] in [startchar,endchar,' ']:
                        name += self.character[r][c] # Add to name.
        return True

    def GetFloatValue(self,input):
        """ Convert an input value into a float.
            Removing special characters such as "%","C" etc. """
        allowedchars = ['0','1','2','3','4','5','6','7','8','9','.']
        sinp = str(input) # Make sure it's a string.
        cinp = '' # Cleaned input.
        for s in sinp:
            if s in allowedchars: cinp += s
        finp = float(cinp)
        return finp

    def ExportFields(self,filename,initialdictionary={}):
        """ Export field values to json file.
            Data is appended to any values already existing in initialdictionary. """
        tempdict = initialdictionary
        for field in self.Fields:
            tempdict[self.DisplayName + "." + field.Name] = field.Value
        tempdict[self.DisplayName + '.PrintHistory'] = self.PrintHistory
        with open(filename,'w') as f:
            json.dump(tempdict,f)
        return True

    def UpdateBlinkStatus(self):
        """ Check for any fields with 'BlinkRate' set. 
            Adjust colors accordingly. """
        for f in self.Fields:
            if f.BlinkRate != 0: # This field is in BLINK mode.
                # Choose an appropriate color scheme.
                t = datetime.now().timestamp() # Current time as seconds.
                c = round(t / f.BlinkRate,0) % len(self.BlinkColors) # Cycle through the list of BlinkColor pairs.
                self.FieldValue(f.name,fg=self.BlinkColors[c][0],bg=self.BlinkColors[c][1])
        return True

    def SetBlinkStatus(self,name,blinkrate,blinkcolors=[[TextColor.WHITE,TextColor.BLACK],[TextColor.BLACK,TextColor.WHITE]]):
        """ Setup blink data.
                    """
        # Validate the color list.
        lOK = True
        for a in blinkcolors:
            if len(a) != 2: # Must be 2 colors listed in each entry.
                lOK = False
                break
        if lOK: 
            for f in self.Fields:
                if f.Name == name:
                    f.BlinkRate = blinkrate
                    f.BlinkColors = blinkcolors
        
    def FieldValue(self,name,value,fg=None,bg=None):
        """ Update the value of a field and display it. """
        FoundIt = False
        for f in self.Fields:
            if f.Name == name: # Will update multiple fields with the same name.
                FoundIt = True
                f.Value = value
                if fg != None: f.FGColor = fg # Tell the field what color it is.
                if bg != None: f.BGColor = bg # Tell the field what color it is.
                sValue = f.Justified() # Make sure the value is a character string and correctly formatted.
                if f.Type == "ProgressBar":
                    pval = float(max(min(self.GetFloatValue(value),f.PBMax),f.PBMin)) # Limit value to progress bar limits.
                    if fg == None: fg = f.PBFG # Default to predefined progress bar colors.
                    if bg == None: bg = f.PBBG
                    pc = round(f.Length * (pval - f.PBMin) / (f.PBMax - f.PBMin)) - 1 # Calculate % complete (offset by -1 to allow for Python 'range' function)
                    for i in range(f.Length):
                        if i <= pc: # 'completed' section of progress bar.
                            self.fgcolor[f.Row][f.Column + i] = fg
                            self.bgcolor[f.Row][f.Column + i] = bg
                        else: # 'todo' section of progress bar (colors swapped).
                            self.fgcolor[f.Row][f.Column + i] = bg
                            self.bgcolor[f.Row][f.Column + i] = fg
                        self.character[f.Row][f.Column + i] = sValue[i]
                else: # 'Data' field.
                    for i in range(f.Length): # Set the characters one at a time.
                        self.character[f.Row][f.Column + i] = sValue[i]
                        if fg != None: self.fgcolor[f.Row][f.Column + i] = fg
                        if bg != None: self.bgcolor[f.Row][f.Column + i] = bg
        return FoundIt

    def RenameField(self,oldname,newname):
        """ Change the name of a data field to something more useful. """
        FoundIt = False
        for f in self.Fields: # Check all fields. 
            if f.Name == oldname: # Found original fieldname.
                FoundIt = True
                f.Name = newname # Assign new fieldname. 
        return FoundIt

    def FieldFormat(self,name, justify=None, pattern=None, bwz=None):
        """ Change the format of a data field to something more useful. """
        FoundIt = False
        for f in self.Fields: # Check all fields. 
            if f.Name == name: # Found original fieldname.
                FoundIt = True
                if justify != None: f.Justify = justify
        return FoundIt

    def CopyFieldColor(self,fromname,toname):
        """ Copy color of one field to another. """
        FoundIt = False
        fromfield = None # Handle to the FROM instance.
        tofield = None # Handle to the TO instance.
        for f in self.Fields: # Find the source field.
            if f.Name == fromname: # Found the FROM instance.
                fromfield = f
                break
        for g in self.Fields: # Find the target field.
            if g.Name == toname: # Found the TO instance.
                tofield = g
                break
        if fromfield != None and tofield != None: # Transfer the colors.
            FoundIt = self.FieldColor(toname,fg=f.FGColor,bg=f.BGColor)
        return FoundIt

    def FieldColor(self,name, fg=None, bg=None):
        """ Update the color of a field and display it. """
        FoundIt = False
        if fg == None: fg = self.DefaultFG # Set defaults if no value given.
        if bg == None: bg = self.DefaultBG
        for f in self.Fields: # Find the Field(s) by name.
            if f.Type in ['ProgressBar']: continue # ProgressBars select their color differently.
            if f.Name == name: # Will update multiple fields with the same name.
                FoundIt = True
                if fg != None: f.FGColor = fg # Tell the field what color it is.
                if bg != None: f.BGColor = bg # Tell the field what color it is.
                for i in range(f.Length): # Color every character in the field.
                    self.fgcolor[f.Row][f.Column + i] = fg
                    self.bgcolor[f.Row][f.Column + i] = bg
                f.FGColor = fg
                f.BGColor = bg
        return FoundIt

    def InitializeColorRange(self,name,badfg=None,badbg=None,poorfg=None,poorbg=None):
        """ Set colour range for a field. """
        FoundIt = False # Not found the field yet.
        for f in self.Fields: # Search the field list.
            if f.Name == name: # Will update multiple fields with the same name.
                FoundIt = True # Found the field.
                f.BadFG = badfg # Set the color values for each range.
                f.BadBG = badbg
                f.PoorFG = poorfg
                f.PoorBG = poorbg
        return FoundIt
        
    def RangeFieldColor(self,name,lowlow=None,low=None,high=None,highhigh=None):
        """ Update the color of a field based upon a range of values. """
        FoundIt = False # Not found the field yet.
        for f in self.Fields: # Find the field in the field list.
            if f.Type in ['ProgressBar']: continue # ProgressBars select their color differently.
            if f.Name == name: # Will update multiple fields with the same name.
                FoundIt = True # Found the field.
                if f.Value <= lowlow or f.Value >= highhigh: # We have a LOW LOW or HIGH HIGH value, this is BAD.
                    fg = f.BadFG
                    bg = f.BadBG
                elif f.Value <= low or f.Value >= high: # We have a LOW or HIGH value, this is POOR.
                    fg = f.PoorFG
                    bg = f.PoorBG
                else: # We have a GOOD value.
                    fg = self.DefaultFG
                    bg = self.DefaultBG
                self.FieldColor(name,fg=fg,bg=bg)
        return FoundIt

    def ListFields(self):
        """ Return dictionary of fields recognised in the window. """
        dict = {}
        for f in self.Fields:
            dict[f.Name] = {'row': f.Row, 'col': f.Column, 'len': f.Length, 'just': f.Justify, 'type': f.Type}
        return dict

    def SetRefreshRate(self,rate):
        """ Set selected refresh rate and reset the refresh timer. """
        self.RefreshRate = rate
        self.LastRefresh = None

    def SetDefault(self):
        """ Store the current display as a default image. 
            When the display is cleared, this default image is restored. """
        for c in range(self.display_columns):
            for r in range(self.display_rows):
                self.default_fgcolor[r][c] = self.fgcolor[r][c]
                self.default_bgcolor[r][c] = self.bgcolor[r][c]
                self.default_character[r][c] = self.character[r][c]

    def ConvertLines(self):
        """ Scan the current layout for '-','|','+' symbols and convert to primitive line drawing. """
        # Not yet implemented.
        return True

    def ClipRow(self,row):
        if row < 0: row = 0
        if row >= self.display_rows: row = self.display_rows - 1
        return row
        
    def ClipCol(self,col):
        if col < 0: col = 0
        if col >= self.display_columns: col = self.display_columns - 1
        return col
        
    def draw_box(self,fromloc,toloc,fg=None,bg=None,border=True,fill=True,overwritelist=['+','-','|',' ']):
        """ Use unicode line characters to draw a box on a colordisplay window. 
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
                            other characters that are not in the overwritelist """
        (fromrow, fromcol) = fromloc
        (torow, tocol) = toloc
        fromrow = self.ClipRow(fromrow)
        torow = self.ClipRow(torow)
        fromcol = self.ClipCol(fromcol)
        tocol = self.ClipCol(tocol)
        if border: # Draw lines around box.
            for c in range(fromcol,tocol + 1):
                # Draw top
                if c == fromcol: char = TextColor.SYMBOLS['corner_tl']
                elif c == tocol: char = TextColor.SYMBOLS['corner_tr']
                else: char = TextColor.SYMBOLS['horizontal']
                cv, _ , _ = self.CellValue(fromrow,c)
                if cv in overwritelist:
                    self.PlaceString(char,fromrow,c,fg=fg,bg=bg)
                # Draw bottom
                if c == fromcol: char = TextColor.SYMBOLS['corner_bl']
                elif c == tocol: char = TextColor.SYMBOLS['corner_br']
                else: char = TextColor.SYMBOLS['horizontal']
                cv , _ , _ = self.CellValue(torow,c)
                if cv in overwritelist:
                    self.PlaceString(char,torow,c,fg=fg,bg=bg)
            char = TextColor.SYMBOLS['vertical']
            if (torow - fromrow) > 1:
                for r in range(fromrow + 1,torow):
                    # Draw left
                    cv , _ , _ = self.CellValue(r,fromcol)
                    if cv in overwritelist:
                        self.PlaceString(char,r,fromcol,fg=fg,bg=bg)
                    # Draw right
                    cv , _ , _ = self.CellValue(r,tocol)
                    if cv in overwritelist:
                        self.PlaceString(char,r,tocol,fg=fg,bg=bg)
        if fill: # Fill the rectangle with the color.
            for c in range(fromcol,tocol + 1):
                for r in range(fromrow,torow + 1):
                    self.ColorCell(r,c,fg,bg)

    def RefreshDue(self):
        """ Return True if refresh is due, else False. """
        result = False
        if self.RefreshRate == None: result = True # There's no restriction so always refresh. 
        elif self.LastRefresh == None: result = True # Need to do initial drawing. 
        elif (datetime.now() - self.LastRefresh).total_seconds() > self.RefreshRate: result = True # Refresh is due.
        return result 
        
    def add_sprite(self,name,text,row=None,col=None,fg=15,bg=0,level=0):
        """ Create a sprite. 
            If name is unique, it creates an instance of cdsprite subclass and adds it to the 
            list of sprites managed by this display buffer. """
        lFound = False
        for s in self.sprites:
            if s.name == name:
                lFound = True
        if lFound == False: # Safe to add.
            self.sprites.append(CdSprite(name,text,row,col,fg,bg,level))
            # Sort the sprites by level. The higher the level the more to the foreground it is.
            self.sprites = sorted(self.sprites, key=lambda sprite: sprite.level)
        else:
            print ("colordisplay: addsprite (" + name + ") rejected because a sprite by this name already exists.")

    def SpriteLabel(self,name,color=False):
        """ Return sprite label (optionally colored). """
        result = None
        for s in self.sprites:
            if s.name == name:
                result = s.label(color=color)
        return result

    def ColoredSprite(self,name):
        """ Return sprite character with embedded colour codes. """
        result = None
        for s in self.sprites:
            if s.name == name:
                result = s.colored_symbol()
        return result

    def move_sprite(self,name,row,col):
        for s in self.sprites:
            if s.name == name:
                s.row = row
                s.column = col

    def ColorSprite(self,name,fg=None,bg=None):
        for s in self.sprites:
            if s.name == name:
                if fg != None: s.fg = fg
                if bg != None: s.bg = bg

    def hide_sprite(self,name):
        for s in self.sprites:
            if s.name == name:
                s.display = False

    def show_sprite(self,name):
        for s in self.sprites:
            if s.name == name:
                s.display = True
                
    def ClearSprites(self):
        self.sprites = []

    def ChangeSprite(self,name,symbol):
        for s in self.sprites:
            if s.name == name:
                s.symbol = symbol

    def SetBorderColors(self,borderfg,borderbg):
        if borderfg == None: self.BorderFG = self.DefaultFG
        else: self.BorderFG = borderfg
        if borderbg == None: self.BorderBG = self.DefaultBG
        else: self.BorderBG = borderbg

    def Clear(self,fg=None,bg=None,immediate=False):
        """ Clear the display buffer, setting all characters to back to their defaults.
            Default image can be updated using the SetDefault() method if needed.
            It does not clear the sprites! You need to do that separately (ClearSprites() method.)        
            Jan.2022 0.0.2 : fg and bg parameters nolonger used. """
        if fg != None: print ('TextColor.colordisplay.Clear() fg parameter is nolonger supported.')
        if bg != None: print ('TextColor.colordisplay.Clear() bg parameter is nolonger supported.')
        for r in range(self.display_rows):
            for c in range(self.display_columns):
                self.character[r][c] = self.default_character[r][c]
                self.fgcolor[r][c] = self.default_fgcolor[r][c]
                self.bgcolor[r][c] = self.default_bgcolor[r][c]
        # Reconstruct the title if it is set.
        self.SetTitle()
        if immediate: self.Draw() # Clear the display immediately.

    def CellValue(self,row,col):
        """ Return cell contents. Character, fg and bg colors. """
        fg, bg = self.CellColor(row,col)
        char = self.character[row][col]
        return char,fg,bg
        
    def ColorCell(self,row,col,fg,bg):
        """ Change colour of a cell, but don't change the text. """
        self.fgcolor[row][col] = fg
        self.bgcolor[row][col] = bg

    def CellColor(self,row,col):
        """ Return current color of a cell. """
        if row < 0 or row >= self.display_rows: fg = self.DefaultFG
        else: fg = self.fgcolor[row][col]
        if col < 0 or col >= self.display_columns: bg = self.DefaultBG
        else: bg = self.bgcolor[row][col]
        return fg, bg

    def scroll_up(self,lines=1,immediate=False):
        """ Scroll the display up by a number of lines. 
            Drops lines at the top,
            adds new blank lines at the bottom. """
        if lines < 1: lines = 1
        if lines > self.display_rows: lines = self.display_rows
        for i in range(lines):
            self.character.pop(self.FirstScrollRow) # Remove entire 1st data row.
            self.fgcolor.pop(self.FirstScrollRow)
            self.bgcolor.pop(self.FirstScrollRow)
            self.character.append([' ' for c in range(self.display_columns)]) # Add empty row at end of window.
            self.fgcolor.append([self.DefaultFGs[self.FGColorIndex] for c in range(self.display_columns)])
            self.bgcolor.append([self.DefaultBGs[self.BGColorIndex] for c in range(self.display_columns)])
        if immediate: self.display(immediate=immediate)

    def Concat(self,*args,sep=' '):
        """ Convert all the input arguments into a single string. """
        result = ''
        for arg in args:
            if result != '': result = result.strip() + sep # add single clean separator between existing values and the new one.
            result += str(arg) # Add new value.
        result = result.strip() # Clean up.
        return result

    def Print(self,*args,fg=None,bg=None,immediate=False):
        """ Simple scrolling print function. 
            Appends text to bottom of window display and scrolls up as required.
            This allows the retirement of the messagewindow class. 
            immediate=True: Display is immediately refreshed. 
            immediate=False: Display needs to be refreshed elsewhere.
            if fg or bg colors are specified, they override the default color scheme of the display. """
        text = '' # Constructed line of text to display.
        for i in args: # Concatenate all the elements into a single text line.
            if len(text) > 0: text += ' ' # Default to space between each element.
            text += str(i) # All elements must be str type.
        self.PrintHistory.append(text) # Retain recent lines printed. Can be exported, or used to repaint the display if resized.
        while len(self.PrintHistory) > self.display_rows: # Drop unwanted lines.
            self.PrintHistory.pop(0) # Drop the first line.
        while len(text) > 0: # Display text, allowing wraparound onto multiple lines.
            if len(text) > self.display_columns: # Too much text to fit on one line.
                print_text = text[:self.display_columns] # Print 1 line's worth of text.
                text = text[self.display_columns:] # Save the rest for the following line(s).
            else: # Remaining text fits on a single line.
                print_text = text # Print what's left.
                text = '' # Nothing else to print after this.
            self.scroll_up() # No need to pass 'immediate' parameter, it's handled below.
            r = self.display_rows - 1
            for i in range(len(print_text)):
                self.character[r][i] = print_text[i]
            if fg != None: # fg color specified.
                for i in range(self.display_columns):
                    self.fgcolor[r][i] = fg
            if bg != None: # bg color specified.
                for i in range(self.display_columns):
                    self.bgcolor[r][i] = bg
        if immediate: self.display(immediate=immediate) # Update the display immediately.
        self.FGColorIndex = (self.FGColorIndex + 1) % self.FGColorCount # If multiple colors supported, then move on to next available color.
        self.BGColorIndex = (self.BGColorIndex + 1) % self.BGColorCount
        return True

    def PlaceString(self,text,row=None,col=None,fg=None,bg=None):
        """ Place a string at any given location in the display buffer. 
            +ve co-ordinates are top-to-bottom, left-to-right
            -ve co-ordinates are bottom-to-top, right-to-left """
        if row < 0: row = self.display_rows + row # Allow -ve values to work up from the bottom of the window.
        if col < 0: col = self.display_columns + col # Allow -ve values to work left from the right of the window.
        if len(text) > 0 and row >= 0 and row < self.display_rows:
            for i in range(len(text)):
                c = col + i # Place in the correct column.
                if c >= 0 and c < self.display_columns:
                    self.character[row][c] = text[i]
                    if fg != None:
                        self.fgcolor[row][c] = fg
                    if bg != None:
                        self.bgcolor[row][c] = bg

    def Draw(self,screenheight=None,screenwidth=None,immediate=False):
        """ Alias for Display() method. For backwards compatibility. """
        print ("***** colordisplay.Draw() method called. Depricated. Use colordisplay.display() method instead.")
        self.display(screenheight=screenheight,screenwidth=screenwidth,immediate=immediate)

    def _MarkDisplay(self):
        """ Quickly highlights window dimensions and fields.
            Helps when defining displays in new applications.
            Debug/Dev only. """
        # Mark all the fields clearly.
        for key,value in self.ListFields.items():
            self.FieldColor(key,fg=TextColor.BLACK,bg=TextColor.CYAN)
        # Mark all the corners clearly.
        for c in range(self.display_columns):
            self.fgcolor[0][c] = TextColor.BLACK
            self.fgcolor[self.display_rows - 1][c] = TextColor.BLACK
            self.bgcolor[0][c] = TextColor.RED
            self.bgcolor[self.display_rows - 1][c] = TextColor.RED
        for r in range(self.display_rows):
            self.fgcolor[r][0] = TextColor.BLACK
            self.fgcolor[r][self.display_columns - 1] = TextColor.BLACK
            self.bgcolor[r][0] = TextColor.RED
            self.bgcolor[r][self.display_columns - 1] = TextColor.RED
        return True

    def Transfer(self,targetbuffer,displayrow=None,displaycol=None):
        """ Transfer the current display to another buffer.
            targetbuffer is the handle to another colordisplay object. 
            displayrow = first row in targetbuffer. If None, then this object's value is used. 
            displaycol = first column in targetbuffer. If None, then this object's value is used. """
        maxscreenrow = targetbuffer.display_rows - 1
        maxscreencol = targetbuffer.display_columns - 1
        if displayrow == None: displayrow = self.display_row # Location in target defaults to the location of this object.
        if displaycol == None: displaycol = self.display_col # Location in target defaults to the location of this object.
        for r in range(self.display_rows):
            rt = r + displayrow # Where is this display in the new one?
            if rt > maxscreenrow: break # No space for this row.
            for c in range(self.display_columns):
                ct = c + displaycol # Where is this display in the new one?
                if ct > maxscreencol: break # No space for this column.
                targetbuffer.character[rt][ct] = self.character[r][c][0:1] # Select the character for current position. Max 1 char.
                targetbuffer.fgcolor[rt][ct] = self.fgcolor[r][c] # Current foreground color of the chosen character.
                targetbuffer.bgcolor[rt][ct] = self.bgcolor[r][c] # Current background color of the chosen character.
        return True

    def ForceRedraw(self):
        """ Flushes old values from self.PrevLineStrings[] forcing a full refresh.
            Normally when calling the Display() method, only changes are sent to the terminal window.
            If you ForceRedraw() then the whole window is sent fresh. """
        self.PrevLineStrings = [' ' for i in self.PrevLineStrings]
    
    @staticmethod
    def GlobalForceRedraw(): # Common
        """ Flushes old values from self.PrevLineStrings[] forcing a full refresh in all registered windows. """
        for w in colordisplay.DefinedWindows:
            try:
                w.ForceRedraw()
            except:
                pass # Window nonlonger exists.

    def GetTextLines(self):
        """ Returns the display layout as a list of strings.
            No color or cursor codes are included, just the basic monotone display text.
            Sprites are shown in their latest position too. """
        linelist = []
        for r in range(self.display_rows): # Go through all the rows in turn.
            line = ''
            for c in range(self.display_columns): # Go through each column in turn. 
                line += self.character[r][c][0:1] # Select the character for current position. Max 1 char too!
            linelist.append(line)
        # Overlay sprites if they exist.
        for s in self.sprites: # Check all sprites in turn.
            if s.row != None and s.column != None and s.row >= 0 and s.row < self.display_rows and s.column >= 0 and s.column < self.display_columns: # In range.
                linelist[s.row] = linelist[s.row][:s.column] + s.symbol[0:1] + linelist[s.row][s.column + 1:]
        return linelist
    
    def DisplayTextLines(self):
        """ Display current contents of the window in a text box. """
        TextColor.TextBox(self.GetTextLines())
        
    @staticmethod
    def GlobalViewWindows(titlefg=None,titlebg=None):
        """ Construct a menu of all available windows
            then choose which window to display. """
        # Dynamically construct menu entries.
        dictionary = {}
        for w in colordisplay.DefinedWindows:
            itemdict = {}
            if w.WindowTitle != None: itemdict['label'] = w.WindowTitle
            else: itemdict['label'] = w.DisplayName
            itemdict['bold'] = False
            itemdict['call'] = w.DisplayTextLines
            itemdict['docurl'] = None
            itemdict['helpdoc'] = 'help.txt'
            dictionary[w.DisplayName] = itemdict
        WindowMenu = proceduremenu(dictionary,'Window contents menu',titlefg=None,titlebg=None,labelwidth=30)
        WindowMenu.Prompt()
        
    def display(self,screenheight=None,screenwidth=None,immediate=False):
        """ Take the display buffer and output it to the terminal. 
            screenheight: Tells the number of rows available in the terminal display. 
            screenwidth: Tells the number of columns available in the terminal display. 
            immediate: (True) Forces immediate update of the terminal display.
                       (False) Only updates the display if the refresh timer is due. """

        if immediate == False and self.RefreshDue() == False: return # Don't perform a refresh yet.
        # Define the maximum ROW and COLUMN number that can be addressed with the current window size.
        if screenheight == None: maxscreenrow = None
        else: maxscreenrow = screenheight - 1
        if screenwidth == None: maxscreencol = None
        else: maxscreencol = screenwidth - 1
        if self.last_display_row != None and maxscreenrow != None: # We have a specific location to use, check if that location is in the current display dimensions.
            if self.ClipWindow == False and maxscreenrow <= self.last_display_row: # Not enough height for the ENTIRE window and not allowed to clip.
                return # Don't try to display.
            if maxscreenrow < self.display_row: # None of the window fits on the terminal at all even if clipping allowed.
                return # Don't try to display.
        if self.last_display_col != None and maxscreencol != None: # We have a specific location to use, check if that location is in the current display dimensions.
            if self.ClipWindow == False and maxscreencol <= self.last_display_col: # Not enough width for the ENTIRE window and not allowed to clip.
                return # Don't try to display.
            if maxscreencol < self.display_col: # None of the window fits on the terminal at all even if clipping allowed.
                return # Don't try to display.
        HorizontalChar = TextColor.SYMBOLS['horizontal'] # '\u2500'
        VerticalChar = TextColor.SYMBOLS['vertical'] # '\u2502'
        CornerChar = TextColor.SYMBOLS['corner_br'] # '\u2518'
        self.UpdateBlinkStatus() # If any fields are supposed to blink, check their color now.
        if self.MarkDisplay: # We need to mark up the corners and fields.
            self._MarkDisplay()
        for r in range(self.display_rows): # Go through all the rows in turn. *Q* Should respect 'ClipWindow' too.
            if self.ClipWindow and self.display_row != None and (r + self.display_row) > maxscreenrow: break # We're off the end of the available display.
            try:
                # The following code has occassionally failed with an IndexError. Added some debugging in case it occurs again to aid solving.
                runningfg = self.fgcolor[r][0] # Note what color we're printing at the start of the line. Color control codes change when this value changes.
                runningbg = self.bgcolor[r][0]
            except IndexError as e:
                print("colordisplay fault: Index out of range?",r,0)
                print("colordisplay fault: Available range fg",len(self.fgcolor),"bg",len(self.bgcolor))
                print("colordisplay fault: maxscreenrow",maxscreenrow,"maxscreencol",maxscreencol)
                print("colordisplay fault: LastDisplayRow",self.last_display_row,"LastDisplayCol",self.last_display_row)
                print("colordisplay fault: DisplayRow",self.display_row,"DisplayCol",self.display_col)
                print("colordisplay fault: DisplayRows",self.display_rows,"DisplayColumns",self.display_columns)
                print("colordisplay fault: ClipWindow",self.ClipWindow)
                if self.Log != None:
                    self.Log("colordisplay fault: Index out of range?",r,0,level='error',terminal=True)
                    self.Log("colordisplay fault: Available range fg",len(self.fgcolor),"bg",len(self.bgcolor),level='error',terminal=True)
                    self.Log("colordisplay fault: maxscreenrow",maxscreenrow,"maxscreencol",maxscreencol,level='error',terminal=True)
                    self.Log("colordisplay fault: LastDisplayRow",self.last_display_row,"LastDisplayCol",self.last_display_row,level='error',terminal=True)
                    self.Log("colordisplay fault: DisplayRow",self.display_row,"DisplayCol",self.display_col,level='error',terminal=True)
                    self.Log("colordisplay fault: DisplayRows",self.display_rows,"DisplayColumns",self.display_columns,level='error',terminal=True)
                    self.Log("colordisplay fault: ClipWindow",self.ClipWindow,level='error',terminal=True)
                raise Exception("Index out of range") from e # Terminate through the regular exception routine.
            line = TextColor.fgbgcolor(runningfg,runningbg,"",reset=False) # Start line off with initial color scheme. Leave the control code 'open' for more text to be added.
            for c in range(self.display_columns): # Go through each column in turn. *Q* Should respect 'ClipWindow' too.
                if self.ClipWindow and self.display_col != None and (c + self.display_col) > maxscreencol: break # We're off the end of the available display.
                ch = self.character[r][c][0:1] # Select the character for current position. Max 1 char too!
                f = self.fgcolor[r][c] # Current foreground color of the chosen character.
                b = self.bgcolor[r][c] # Current background color of the chosen character.
                # Check if any sprites override this character.
                for s in self.sprites: # Check all sprites in turn.
                    if s.row == r and s.column == c and s.display: # Same location and visible.
                        ch = s.symbol[0:1] # Only 1 character allowed for the sprite at the moment.
                        f = s.fg # Sprite fg and bg colors override the background.
                        b = s.bg
                if runningfg != f or runningbg != b: # Colour scheme has changed. Insert appropriate code.
                    runningfg = f # Note new colours we're now printing with.
                    runningbg = b
                    line += TextColor.fgbgcolor(runningfg,runningbg,"",reset=False) # Insert open-ended colour change code.
                if len(ch) < 1: # Make sure that the character is the right length.
                    ch = " "
                line += ch # Add the character.
            if self.display_row != None and self.display_col != None:
                # The display has a specific location on the terminal window. Place it there.
                dr = self.display_row + r
                dc = self.display_col
                line = TextColor.cursor(dc,dr) + line # Locate the line on the terminal layout.
            line += TextColor.reset()
            if self.DrawBorder and self.last_display_col + 1 < maxscreencol: line += TextColor.fgbgcolor(self.BorderFG,self.BorderBG,VerticalChar)
            if self.ReduceIO == False or self.PrevLineStrings[r] != line: # The line has changed. So display the new string. Otherwise save display time and leave it unchanged.
                print (line,end='',flush=True) # Do not add newline character at end of the printed text. Always flush the print buffer.
            self.PrevLineStrings[r] = line # Store the print command so we can compare next time if anything changed.
        if self.DrawBorder and self.last_display_row + 1 < maxscreenrow: 
            visiblecolumns = maxscreencol - self.display_col + 1
            if visiblecolumns < self.display_columns + 1: # We cannot fit the entire bottom border line and corner in the display, just show what's possible.
                line = TextColor.fgbgcolor(self.BorderFG,self.BorderBG,(HorizontalChar * visiblecolumns)) # Truncate the line.
            else:#  The whole border line and corner should fit in the display.
                line = TextColor.fgbgcolor(self.BorderFG,self.BorderBG,(HorizontalChar * self.display_columns) + CornerChar) # Full line including corner character.
            print(TextColor.cursor(self.display_col,self.display_row + self.display_rows) + line)
        self.LastRefresh = datetime.now()

    @staticmethod
    def GlobalExportFields(filename,initialdictionary={}):
        """ Export field values from all windows to json file.
            Data is appended to any values already existing in initialdictionary. """
        tempdict = colordisplay.GlobalSaveToDictionary(initialdictionary=initialdictionary)
        with open(filename,'w') as f:
            json.dump(tempdict,f,default=str)
        return True
        
    @staticmethod
    def GlobalSaveToDictionary(initialdictionary={}):
        """ Export field values from all windows to dictionary.
            Data is appended to any values already existing in initialdictionary. """
        tempdict = initialdictionary
        for w in colordisplay.DefinedWindows:
            for field in w.Fields:
                tempdict[w.DisplayName + "." + field.Name] = field.Value
            tempdict[w.DisplayName + '.PrintHistory'] = w.PrintHistory
        return tempdict
        
    @staticmethod
    def GlobalFieldFormat(name, justify=None, pattern=None, bwz=None): # Common
        """ Update the format of a field in all defined windows. """
        FoundIt = False
        for w in colordisplay.DefinedWindows:
            try:
                temp = w.FieldFormat(name=name, justify=justify, pattern=pattern, bwz=bwz)
                if temp: FoundIt = True
            except:
                pass # Window nonlonger exists.
        return FoundIt
    
    @staticmethod
    def GlobalFieldValue(name,value,fg=None,bg=None): # Common
        """ Update the value of a field in all defined windows and display it. """
        FoundIt = False
        for w in colordisplay.DefinedWindows:
            try:
                temp = w.FieldValue(name=name,value=value,fg=fg,bg=bg)
                if temp: FoundIt = True
            except:
                pass # Window nonlonger exists.
        return FoundIt
    
    @staticmethod
    def GlobalFieldColor(name,fg=None,bg=None): # Common
        """ Update the color of a field in all defined windows. """
        FoundIt = False
        for w in colordisplay.DefinedWindows:
            try:
                temp = w.FieldColor(name=name,fg=fg,bg=bg)
                if temp: FoundIt = True
            except:
                pass # Window nolonger exists.
        return FoundIt
        

    @staticmethod
    def GlobalReduceIO(reduce=True):
        """ Turn on/off the ReduceIO function in all defined windows. 
            reduce = True turns it on.
            reduce = False turns it off. 
            
            When True: All defined display windows will apply the ReduceIO rules. 
                       When refreshing the display ONLY the changed characters are 
                       updated to the terminal. This makes the refresh considerably
                       faster for displays where only a few characters change each time. 
                       In most cases this is the most efficient way to refresh the displays.
            When False: All the defined display windows will completely redraw
                       all their contents each time the display is refreshed, even if
                       nothing has changed. """
        for w in colordisplay.DefinedWindows:
            try:
                w.ReduceIO = reduce
            except:
                pass # Window nolonger exists.
        return

    @staticmethod
    def GlobalDisplay(screenheight=None,screenwidth=None,immediate=False): # Common
        """ Display ALL defined windows in a single call. """
        for w in colordisplay.DefinedWindows:
            try:
                w.display(screenheight=screenheight,screenwidth=screenwidth,immediate=immediate)
            except:
                pass # Window nolonger exists.
        return
        
    @staticmethod
    def GlobalWindowLimits():
        """ Return maximum ROW and COLUMN that any of the current windows extend into. """
        maxrow = 0
        maxcol = 0
        for w in colordisplay.DefinedWindows:
            try:
                maxrow = max(maxrow,w.last_display_row)
                maxcol = max(maxcol,w.last_display_col)
            except:
                pass # Window nolonger exists.
        return (maxcol, maxrow)
    

# -------------------------------------------------------------------------------------------------------------------------------- 

# Backward compatibility aliases
cdsprite = CdSprite
messagewindow = MessageWindow
bigletters = BigLetters
field = Field
colordisplay = ColorDisplay
