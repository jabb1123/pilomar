#!/usr/bin/env python3
"""Terminal text formatting with colors and positioning.

This module provides the TextColor class with static methods for
terminal text formatting, colors, cursor positioning, and special
characters.

Works best with PuTTY remote terminal connections. Behavior may
differ in local terminal windows.

Example:
    from pilomar.ui.text_color import TextColor
    
    TextColor.clearscreen()
    print(TextColor.red('Hello'))
    print(TextColor.fgbgcolor(TextColor.YELLOW, TextColor.BLUE, 'Colored text'))
"""

# This software is published under the GNU General Public License v3.0.

__version__ = '0.1.0'

import locale
import subprocess
from typing import Any, List, Optional, Tuple, Union


class TextColor:
    """ Class with lots of static methods to help with writing to terminals with position and formatting. 
        This is primarily designed to work under puTTY remote terminal connections.
        Behaviour is different under a command line window opened from the desktop.
        
        You don't need to create an instance, it's OK to use TextColor.method() calls directly in your
        code.
                from textcolor import textcolor
                TextColor.clearscreen() 
                print(TextColor.red('Hello'))
                
        It includes various constants such as names of colors.
        It also makes some unicode symbols available via a dictionary so you can refer to them by name.

        Usage :-

            from textcolor import textcolor
            print(TextColor.yellow("Hello") 
                     Would print "Hello" in yellow text on default background. 
                     
            """

    __version__ = '0.0.6'
    TermType = None
    Mode = 'putty' # 'putty' = full colour remote terminal, 'simple' = No colour, 'local' = Direct connection colour.
    # Some standard color names (XTERM names & a couple of common aliases).
    BLACK = 0
    MAROON = 1
    GREEN = 2
    OLIVE = 3
    NAVY = 4
    PURPLE = 5
    TEAL = 6
    SILVER = 7
    GRAY = GREY = 8
    RED = 9
    LIME = 10
    YELLOW = 11
    BLUE = 12
    FUCHSIA = MAGENTA = 13
    AQUA = CYAN = 14
    WHITE = 15
    GREY0 = 16
    NAVYBLUE = 17
    DARKBLUE = 18
    BLUE3 = 19
    BLUE3A = 20
    BLUE1 = 21
    DARKGREEN = 22
    DEEPSKYBLUE4 = 23
    DEEPSKYBLUE4A = 24
    DEEPSKYBLUE4B = 25
    DODGERBLUE3 = 26
    DODGERBLUE2 = 27
    GREEN4 = 28
    SPRINGGREEN4 = 29
    TURQUOISE4 = 30
    DEEPSKYBLUE3 = 31
    DEEPSKYBLUE3A = 32
    DODGERBLUE1 = 33
    GREEN3 = 34
    SPRINGGREEN3 = 35
    DARKCYAN = 36
    LIGHTSEAGREEN = 37
    DEEPSKYBLUE2 = 38
    DEEPSKYBLUE1 = 39
    GREEN3A = 40
    SPRINGGREEN3A = 41
    SPRINGGREEN2 = 42
    CYAN3 = 43
    DARKTURQUOISE = 44
    TURQUOISE2 = 45
    GREEN1 = 46
    SPRINGGREEN2 = 47
    SPRINGGREEN1 = 48
    MEDIUMSPRINGGREEN = 49
    CYAN2 = 50
    CYAN1 = 51
    DARKRED = 52
    DEEPPINK4 = 53
    PURPLE4 = 54
    PURPLE4A = 55
    PURPLE3 = 56
    BLUEVIOLET = 57
    ORANGE4 = ORANGE = 58
    GREY37 = 59
    MEDIUMPURPLE4 = 60
    SLATEBLUE3 = 61
    SLATEBLUE3A = 62
    ROYALBLUE1 = 63
    CHARTREUSE4 = 64
    DARKSEAGREEN4 = 65
    PALETURQUOISE4 = 66
    STEELBLUE = 67
    STEELBLUE3 = 68
    CORNFLOWERBLUE = 69
    CHARTREUSE3 = 70
    DARKSEAGREEN4A = 71
    CADETBLUE = 72
    CADETBLUEA = 73
    SKYBLUE3 = 74
    STEELBLUE1 = 75
    CHARTREUSE3A = 76
    PALEGREEN3 = 77
    SEAGREEN3 = 78
    AQUAMARINE3 = 79
    MEDIUMTURQUOISE = 80
    STEELBLUE1 = 81
    CHARTREUSE2 = 82
    SEAGREEN2 = 83
    SEAGREEN1 = 84
    SEAGREEN1A = 85
    AQUAMARINE1 = 86
    DARKSLATEGRAY2 = 87
    DARKRED = 88
    DEEPPINK4 = 89
    DARKMAGENTA = 90
    DARKMAGENTAA = 91
    DARKVIOLET = 92
    PURPLE = 93
    ORANGE4 = 94
    LIGHTPINK4 = 95
    PLUM4 = 96
    MEDIUMPURPLE3 = 97
    MEDIUMPURPLE3A = 98
    SLATEBLUE1 = 99
    YELLOW4 = 100
    WHEAT4 = 101
    GREY53 = 102
    LIGHTSLATEGREY = 103
    MEDIUMPURPLE = 104
    LIGHTSLATEBLUE = 105
    YELLOW4 = 106
    DARKOLIVEGREEN3 = 107
    DARKSEAGREEN = 108
    LIGHTSKYBLUE3 = 109
    LIGHTSKYBLUE3A = 110
    SKYBLUE2 = 111
    CHARTREUSE2 = 112
    DARKOLIVEGREEN3A = 113
    PALEGREEN3 = 114
    DARKSEAGREEN3 = 115
    DARKSLATEGRAY3 = 116
    SKYBLUE1 = 117
    CHARTREUSE1 = 118
    LIGHTGREEN = 119
    LIGHTGREENA = 120
    PALEGREEN1 = 121
    AQUAMARINE1 = 122
    DARKSLATEGRAY1 = 123
    RED3 = 124
    DEEPPINK4 = 125
    MEDIUMVIOLETRED = 126
    MAGENTA3 = 127
    DARKVIOLET = 128
    PURPLE = 129
    DARKORANGE3 = 130
    INDIANRED = 131
    HOTPINK3 = 132
    MEDIUMORCHID3 = 133
    MEDIUMORCHID = 134
    MEDIUMPURPLE2 = 135
    DARKGOLDENROD = 136
    LIGHTSALMON3 = 137
    ROSYBROWN = 138
    GREY63 = 139
    MEDIUMPURPLE2 = 140
    MEDIUMPURPLE1 = 141
    GOLD3 = 142
    DARKKHAKI = 143
    NAVAJOWHITE3 = 144
    GREY69 = 145
    LIGHTSTEELBLUE3 = 146
    LIGHTSTEELBLUE = 147
    YELLOW3 = 148
    DARKOLIVEGREEN3 = 149
    DARKSEAGREEN3A = 150
    DARKSEAGREEN2 = 151
    LIGHTCYAN3 = 152
    LIGHTSKYBLUE1 = 153
    GREENYELLOW = 154
    DARKOLIVEGREEN2 = 155
    PALEGREEN1 = 156
    DARKSEAGREEN2A = 157
    DARKSEAGREEN1 = 158
    PALETURQUOISE1 = 159
    RED3A = 160
    DEEPPINK3 = 161
    DEEPPINK3A = 162
    MAGENTA3 = 163
    MAGENTA3A = 164
    MAGENTA2 = 165
    DARKORANGE3 = 166
    INDIANRED = 167
    HOTPINK3 = 168
    HOTPINK2 = 169
    ORCHID = 170
    MEDIUMORCHID1 = 171
    ORANGE3 = 172
    LIGHTSALMON3 = 173
    LIGHTPINK3 = 174
    PINK3 = 175
    PLUM3 = 176
    VIOLET = 177
    GOLD3 = 178
    LIGHTGOLDENROD3 = 179
    TAN = 180
    MISTYROSE3 = 181
    THISTLE3 = 182
    PLUM2 = 183
    YELLOW3 = 184
    KHAKI3 = 185
    LIGHTGOLDENROD2 = 186
    LIGHTYELLOW3 = 187
    GREY84 = 188
    LIGHTSTEELBLUE1 = 189
    YELLOW2 = 190
    DARKOLIVEGREEN1 = 191
    DARKOLIVEGREEN1A = 192
    DARKSEAGREEN1A = 193
    HONEYDEW2 = 194
    LIGHTCYAN1 = 195
    RED1 = 196
    DEEPPINK2 = 197
    DEEPPINK1 = 198
    DEEPPINK1A = 199
    MAGENTA2 = 200
    MAGENTA1 = 201
    ORANGERED1 = 202
    INDIANRED1 = 203
    INDIANRED1A = 204
    HOTPINK = 205
    HOTPINKA = 206
    MEDIUMORCHID1 = 207
    DARKORANGE = 208
    SALMON1 = 209
    LIGHTCORAL = 210
    PALEVIOLETRED1 = 211
    ORCHID2 = 212
    ORCHID1 = 213
    ORANGE1 = 214
    SANDYBROWN = 215
    LIGHTSALMON1 = 216
    LIGHTPINK1 = 217
    PINK1 = 218
    PLUM1 = 219
    GOLD1 = 220
    LIGHTGOLDENROD2 = 221
    LIGHTGOLDENROD2A = 222
    NAVAJOWHITE1 = 223
    MISTYROSE1 = 224
    THISTLE1 = 225
    YELLOW1 = 226
    LIGHTGOLDENROD1 = 227
    KHAKI1 = 228
    WHEAT1 = 229
    CORNSILK1 = 230
    GREY100 = 231
    GREY3 = 232
    GREY7 = 233
    GREY11 = 234
    GREY15 = 235
    GREY19 = 236
    GREY23 = 237
    GREY27 = 238
    GREY30 = 239
    GREY35 = 240
    GREY39 = 241
    GREY42 = 242
    GREY46 = 243
    GREY50 = 244
    GREY54 = 245
    GREY58 = 246
    GREY62 = 247
    GREY66 = 248
    GREY70 = 249
    GREY74 = 250
    GREY78 = 251
    GREY82 = 252
    GREY85 = 253
    GREY89 = 254
    GREY93 = 255
    
    # UTF-8 symbols for special items.
    SYMBOLS = {'left' : '\u2190', 'right' : '\u2192', 'up' : '\u2191', 'down' : '\u2193', 
               'degree' : '\u00B0', 'delta' : '\u0394', 
               'horizontal' : '\u2500', 'vertical' : '\u2502', 'corner_tl' : '\u250c', 'corner_tr' : '\u2510', 'corner_bl' : '\u2514', 'corner_br' : '\u2518', 'crossover' : '\u253c',
               'left_junction' : '\u2524', 'right_junction' : '\u251c', 'top_junction' : '\u2534', 'bottom_junction' : '\u252c',
               'sun' : '\u2609', 'moon' : '\u263D', 'mercury' : '\u263F', 'venus' : '\u2640', 'earth' : '\u2641', 'mars' : '\u2642', 'jupiter' : '\u2643', 'saturn' : '\u2644', 'uranus' : '\u2645', 'neptune' : '\u2646', 'pluto' : '\u2647', 'comet' : '\u2604', 'star' : '\u2736'
              }
    # Alternative 8bit character symbols for special items. (If environment doesn't support UTF-8)
    SYMBOLS8 = {'left' : '<', 'right' : '>', 'up' : '^', 'down' : 'v', 
               'degree' : 'd', 'delta' : '~', 
               'horizontal' : '-', 'vertical' : '|', 'corner_tl' : '+', 'corner_tr' : '+', 'corner_bl' : '+', 'corner_br' : '+', 'crossover' : '+',
               'left_junction' : '+', 'right_junction' : '+', 'top_junction' : '+', 'bottom_junction' : '+',
               'sun' : 'S', 'moon' : 'l', 'mercury' : 'm', 'venus' : 'v', 'earth' : 'e', 'mars' : 'M', 'jupiter' : 'J', 'saturn' : 's', 'uranus' : 'u', 'neptune' : 'n', 'pluto' : 'p', 'comet' : '@', 'star' : '*'
              }

    @staticmethod
    def set_current_locale():
        """ Load the locale into the textcolor library.
            Python may assume it's in UTF-8 unless we load the current environment's settings. """
        locale.setlocale(locale.LC_ALL, '')
        
    @staticmethod
    def get_locale():
        """ Retrieve the current locale setting for the session.
            Output -------------------------------------------------------------------
            Returns the detected locale (Language, Characterset) tuple. """
        Lang, CharSet = locale.getlocale()
        return (Lang, CharSet)

    @staticmethod
    def check_locale(switch=False):
        """ If the character set is not UTF-8 then special characters won't print. 
            In that case, convert the SYMBOLS list to safer ISO8859-1 characters.
            Call this at the start of a session before using other textcolor methods.
            Parameters ---------------------------------------------------------------
            switch: False. No changes are made.
            switch: True. The SYMBOLS list is switched to a simpler version that will work with more character sets.
            Output -------------------------------------------------------------------
            Returns the detected locale (Language, Characterset) tuple. """
        Lang, CharSet = TextColor.get_locale()
        if not CharSet in ["UTF-8"] and switch: # Special characters won't work, but we can switch to an alternative list.
            print("TextColor.CheckLocale: Downgrading special characters for character set",CharSet)
            TextColor.SYMBOLS = TextColor.SYMBOLS8
        return (Lang, CharSet)

    @staticmethod
    def text_box(linelist,row=None,col=None,fg=None,bg=None,textfg=None,textbg=None,borderfg=None,borderbg=None,minwidth=None,justify=None):
        """ Receive a single string or list of strings.
            Embedded newline characters will also split the text into separate lines within the bounding box.
            Make all lines the same length, surrounded with a box using line drawing characters.
            Print the resulting text box. 
            - row/col specify the location of the top-left corner of the box.
            Colors are applied if specified. 
            - fg/bg applies to text and border. 
            - textfg/textbg applies to text only. 
            - borderfg/borderbg applies to border only.
            - minwidth = minimum character width.
            - justify = 'l'(left),'c'(center),'r'(right) 
            
            If the O/S character set is not UTF-8 the line drawing can fail. 
            So if the print() statements fail, this routine will just print the lines individually instead. """
        if type(linelist) != list: linelist = [linelist] # Convert single values to list for simpler processing.
        if justify != None: justify = justify[0].lower() # standardise code.
        # Convert embedded newline characters into separate list elements.
        templinelist = []
        for line in linelist: # Read all the input lines.
            for newline in line.split('\n'): # Break on newline character.
                templinelist.append(newline)
        linelist = templinelist
        if textfg == None: textfg = fg # Use same color scheme for text and border.
        if textbg == None: textbg = bg # Use same color scheme for text and border.
        if borderfg == None: borderfg = fg # Use same color scheme for text and border.
        if borderbg == None: borderbg = bg # Use same color scheme for text and border.
        maxlen = 0
        for line in linelist: maxlen = max(maxlen,len(line)) # What's the longest line?
        if minwidth != None: maxlen = max(maxlen,minwidth) # Respect minwidth.
        #lines = [line.ljust(maxlen) for line in linelist] # Make all lines the same length.
        printlines = [] # List of color constructed lines to print.
        # 1: Construct top of box.
        if borderfg != None and borderbg != None: # Border color is specified.
            temp = TextColor.fgbgcolor(borderfg,borderbg,TextColor.SYMBOLS['corner_tl'] + (TextColor.SYMBOLS['horizontal'] * maxlen) + TextColor.SYMBOLS['corner_tr'])
            printlines.append(temp)
        else: # No colors specified.
            temp = TextColor.SYMBOLS['corner_tl'] + (TextColor.SYMBOLS['horizontal'] * maxlen) + TextColor.SYMBOLS['corner_tr']
            printlines.append(temp)
        # 2: Construct text lines and box edges.
        for line in linelist:
            temp = ''
            # Vertical edge on left. Color if needed.
            if borderfg != None and borderbg != None: # Border color is specified.
                temp += TextColor.fgbgcolor(borderfg,borderbg,TextColor.SYMBOLS['vertical'])
            else: temp += TextColor.SYMBOLS['vertical']
            # Text inside box. Color if needed.
            # - Justify.
            if justify == 'l': line = line.strip().ljust(maxlen) # left justify (default).
            elif justify == 'c': line = line.strip().center(maxlen) # center justify.
            elif justify == 'r': line = line.strip().rjust(maxlen) # right justify.
            else: line = (line + " " * maxlen)[:maxlen] # Just pad whatever we were given.
            # - Add color.
            if textfg != None and textbg != None: # Text color is specified.
                temp += TextColor.fgbgcolor(textfg,textbg,line)
            else: temp += line
            # Vertical edge on right. Color if needed.
            if borderfg != None and borderbg != None: # Border color is specified.
                temp += TextColor.fgbgcolor(borderfg,borderbg,TextColor.SYMBOLS['vertical'])
            else: temp += TextColor.SYMBOLS['vertical']
            printlines.append(temp)
        # 3: Construct bottom of box.
        if borderfg != None and borderbg != None: # Border color is specified.
            temp = TextColor.fgbgcolor(borderfg,borderbg,TextColor.SYMBOLS['corner_bl'] + (TextColor.SYMBOLS['horizontal'] * maxlen) + TextColor.SYMBOLS['corner_br'])
            printlines.append(temp)
        else: # No colors specified.
            temp = TextColor.SYMBOLS['corner_bl'] + (TextColor.SYMBOLS['horizontal'] * maxlen) + TextColor.SYMBOLS['corner_br']
            printlines.append(temp)
        try: # Try to print with full graphics, but if character set does not allow it, print basic text instead.
            for i,line in enumerate(printlines): # Now display the whole box.
                if row != None and col != None: line = TextColor.cursor(col=col,row=row + i) + line # Add screen location (row and column).
                elif col != None: line = TextColor.cursorright(cols=col) + line # Add screen location (column only).
                TextColor.safeprint(line)
                #TextColor.safeprint(line) # This would reduce to latin1 even if the characters are utf-8
        except Exception as e: # Print simple text if the display won't allow UTF-8 characters.
            print(TextColor.red("TextColor.text_box():",str(e)))
            for line in linelist:
                print(line)

    @staticmethod
    def list_symbols():
        for key,value in TextColor.SYMBOLS.items():
            print (key, value)
        
    @staticmethod
    def safetype(raw):
        if type(raw) != type(str): raw = str(raw)
        return raw     

    @staticmethod
    def booltocolor(value,fgtrue=None,fgfalse=None):
        """ Given a boolean (or text) value, return it as colored text. 
            True values are colored fgtrue color. 
            False valuse are colored fgfalse color. 
            None values are not colored. """
        if fgtrue == None: fgtrue = TextColor.GREEN
        if fgfalse == None: fgfalse = TextColor.RED
        temp = str(value)
        temp = temp.replace("True",TextColor.fgbgcolor(fgtrue,TextColor.BLACK,"True"))
        temp = temp.replace("False",TextColor.fgbgcolor(fgfalse,TextColor.BLACK,"False"))
        return temp

    @staticmethod
    def listtotext(arglist,sep=' '):
        """ Given a list of arguments, append all of them into a single string.
            This behaves like the 'print' command for stringing together a list of items
            into a single string. All arguments are converted to 'str' type before adding
            to the output string. 
            sep parameter says what separator is inserted between each element. (default ' ') """
        result = ''
        for a in arglist:
            if a != '':
                if result != '': result += sep
                result += str(a)
        return result

    @staticmethod
    def neatprint(*args,**kwargs):
        """ Own 'print' function. 
            Formats neatly in early Python versions. """
        sep = ' '
        end = '\n'
        for key,value in kwargs.items():
            if key == 'sep': sep = value
            elif key == 'end': end = value
        line = ''
        for a in args:
            a = TextColor.safetype(a)
            if len(line) > 0: line += sep
            line += a
        print(line,end=end)

    @staticmethod
    def safeprint(*args,**kwargs):
        """ Own 'print' function. 
            Formats neatly in early Python versions, and reduces utf8 to latin1. """
        sep = ' '
        end = '\n'
        for key,value in kwargs.items():
            if key == 'sep': sep = value
            elif key == 'end': end = value
        line = ''
        for a in args:
            a = TextColor.safetype(a)
            if len(line) > 0: line += sep
            line += a
        _, CharSet = locale.getlocale()
        if not CharSet in ["UTF-8"]: # We cannot use utf-8 full set, reduce to simpler iso-8859-1 character set.
            line = line.encode('iso-8859-1', errors='replace').decode()
        print(line,end=end)

    @staticmethod
    def getterminalsize(): # Common
        """ Return tuple of the current screen dimensions. 
              (cols,rows) """
        print('TextColor.getterminalsize() is deprecated in favour of TextColor.terminalsize()')
        cols = 80
        rows = 24
        cols = int(TextColor.oscommand('tput cols')[0])
        rows = int(TextColor.oscommand('tput lines')[0])
        return (cols,rows)

    @staticmethod
    def hr_number(value,base=1000,decimals=1):
        """ Given a number return a human readable text version.
            Eg, turning 1,000,000 into 1.0M 
            
            inputs :-
                value = The number to be converted.
                base = 1000. Runs in thousands.
                     = 1024. Runs in IT measurements.
                decimals = The number of decimal places to return.

            HRNumber(56312703,1000) returns :-
                result = '56.3M'
                prefix = 'mega'
                symbol = 'M' 
                
                """
        valdic = {'yocto':{'power':-8,'symbol':'y','name':'septillionth'},
                  'zepto':{'power':-7,'symbol':'z','name':'sextillionth'},
                  'atto' :{'power':-6,'symbol':'a','name':'quintillionth'},
                  'femto':{'power':-5,'symbol':'f','name':'quadrillionth'},
                  'pico': {'power':-4,'symbol':'p','name':'trillionth'},
                  'nano': {'power':-3,'symbol':'n','name':'billionth'},
                  'micro':{'power':-2,'symbol':'u','name':'millionth'},
                  'milli':{'power':-1,'symbol':'m','name':'thousandth'},
                  '':     {'power':0, 'symbol':'','name':''},
                  'kilo': {'power':1, 'symbol':'k','name':'thousand'},
                  'mega': {'power':2, 'symbol':'M','name':'million'},
                  'giga': {'power':3, 'symbol':'G','name':'billion'},
                  'tera': {'power':4, 'symbol':'T','name':'trillion'},
                  'peta': {'power':5, 'symbol':'P','name':'quadrillion'},
                  'exa':  {'power':6, 'symbol':'E','name':'quintillion'},
                  'zetta':{'power':7, 'symbol':'Z','name':'sextillion'},
                  'yotta':{'power':8, 'symbol':'Y','name':'septillion'}}
                  # Not used here...
                  #'centi':{'power':-2, 'symbol':'c','name':'hundredth'},
                  #'deci': {'power':-1, 'symbol':'d','name':'tenth'},
                  #'deca': {'power':1,  'symbol':'da','name':'ten'},
                  #'hecto':{'power':2,  'symbol':'h','name':'hundred'},
        # Default return values.
        result = str(value) # Default has no conversion.
        prefix = ''
        symbol = ''
        # Find better return conversion if possible.
        for key,subdict in valdic.items():
            scale = base ** subdict['power']
            ranged = round(value / scale,decimals)
            if 1.0 <= ranged < 1000: # This is a good fit.
                result = str(ranged) + subdict['symbol']
                prefix = key
                symbol = subdict['symbol']
                break
        return result, prefix, symbol

    @staticmethod
    def stripcodes(line):
        """ Remove embedded terminal display codes from a line of text.
            Removes any text starting with "\033[" up to the first letter. (A-Z,a-z) """
        result = ''
        CodeStart = "\033["
        InCode = False
        if line is None or line == '': result = line
        else: # Need to process the characters.
            for i in range(len(line)):
                if line[i:].startswith(CodeStart): InCode = True # We've started a code sequence.
                if not InCode: # We have printable characters.
                    result += line[i]
                if InCode: # We're in a code sequence. Check for it ending.
                    if "a" <= line[i].lower() <= "z": # Code terminator.
                        InCode = False
        return result
        
    @staticmethod
    def oscommand(cmd): # Common
        """ Execute a command,result is returned as clean list of lines. """
        try:
            result = subprocess.check_output(cmd,shell=True,stderr=subprocess.DEVNULL).decode('utf-8')
        except subprocess.CalledProcessError as e:
            print("TextColor.oscommand(" + cmd + ") returned " + str(e))
            print("TextColor.oscommand(" + cmd + ") returned returncode " + str(e.returncode))
            print("TextColor.oscommand(" + cmd + ") returned output " + str(e.output))
            print("TextColor.oscommand(" + cmd + ") returned cmd " + str(e.cmd))
            print("TextColor.oscommand(" + cmd + ") returned stdout " + str(e.stdout))
            print("TextColor.oscommand(" + cmd + ") returned stderr " + str(e.stderr))
            result = "" # We lose result output, even if some was generated before the error was reached.
        lines = result.split('\n')
        returnlist = []
        for line in lines:
            returnlist.append(line) # Construct clean returnlist of the output.
        return returnlist

    @staticmethod
    def get_term_type(): # Common
        """ Return the termtype and also set the global variable TermType. """
        TextColor.TermType = TextColor.oscommand('echo $TERM')[0]
        return TextColor.TermType

    @staticmethod
    def terminalsize(): # Common
        """ Return tuple of the current screen dimensions (in characters) = (cols,rows) """
        cols = 80
        rows = 24
        cols = int(TextColor.oscommand('tput cols')[0])
        rows = int(TextColor.oscommand('tput lines')[0])
        return (cols,rows)

    @staticmethod
    def hidecursor(): # Common
        """ Make the cursor invisible. """
        TextColor.oscommand('tput civis')

    @staticmethod
    def showcursor(): # Common
        """ Make the cursor visible. """
        TextColor.oscommand('tput cnorm')

    @staticmethod
    def cursorhome():
        return TextColor.cursor(0,0)

    @staticmethod
    def cursor(col=0,row=0):
        return "\033[" + str(row) + ";" + str(col) + "H"

    @staticmethod
    def cursorup(rows=1):
        return "\033[" + str(rows) + "A"

    @staticmethod
    def cursordown(rows=1):
        return "\033[" + str(rows) + "B"

    @staticmethod
    def cursorleft(cols=1):
        return "\033[" + str(cols) + "D"

    @staticmethod
    def cursorright(cols=1):
        return "\033[" + str(cols) + "C"

    @staticmethod
    def nextline(rows=1):
        return "\033[" + str(rows) + "E"

    @staticmethod
    def prevline(rows=1):
        return "\033[" + str(rows) + "F"

    @staticmethod
    def clearlineforward():
        return "\033[0K"

    @staticmethod
    def clearlinebackward():
        return "\033[1K"

    @staticmethod
    def clearline():
        return "\033[2K"

    @staticmethod
    def clearforward():
        return "\033[0J"

    @staticmethod
    def clearbackward():
        return "\033[1J"

    @staticmethod
    def clearall():
        return "\033[2J"

    @staticmethod
    def clearscreen():
        return TextColor.cursorhome() + TextColor.clearall()

    @staticmethod
    def reset(text=""):
        return "\033[0m" + text

    @staticmethod
    def color(value=7,text=''):
        """ 256 colour mode supported. """
        if TextColor.Mode == 'simple':
            return text
        else:
            return "\033[38;5;" + str(value) + "m" + text + TextColor.reset()

    @staticmethod
    def truecolor(r,g,b,text=''):
        """ Truecolor colour mode supported. """
        if TextColor.Mode == 'simple':
            return text
        else:
            return "\033[38;2;" + str(r)+ ";" + str(g) + ";" + str(b) + "mtext\033[0m" + text + TextColor.reset()

    @staticmethod
    def bgcolor(value=0,text=''):
        """ 256 colour mode supported."""
        if TextColor.Mode == 'simple':
            return text
        else:
            return "\033[48;5;" + str(value) + "m" + text + TextColor.reset()

    @staticmethod
    def rgbassign(r):
        """ change r(or g or b) value from 0.0-1.0 range into 0-5 range
            This assigns the 0-5 range more evenly depending upon the input 0.0-1.0 value. """
        #if r <= 0.167: re = 0
        #elif r <= 0.333: re = 1
        #elif r <= 0.500: re = 2
        #elif r <= 0.668: re = 3
        #elif r <= 0.833: re = 4
        #else: re = 5
        re = min(int(r // (1/6)),5)
        return re

    @staticmethod
    def rgbdecimal(r,g,b):
        """ Take rgb values (scale 0.00-1.00) and calculate nearest 215 color scheme value.
            method parameter allows for alternative calculations.        """
        # 0.0 = Level 0
        # 1.0 = Level 5
        #re = round(r * 5)
        #ge = round(g * 5)
        #be = round(b * 5)
        re = TextColor.rgbassign(r)
        ge = TextColor.rgbassign(g)
        be = TextColor.rgbassign(b)
        v = int(re * 6 * 6) + int(ge * 6) + int(be) + 16
        return v
        
    @staticmethod
    def rgbditherdecimal(r,g,b):
        """ Take rgb values (scale 0.00-1.00) and calculate 2 nearest 215 color scheme values. 
            This is to support using 'dithering' to match colors better.
            Returns 2 colors.            """
        # How close is the closest single available color?
        ri = round(r * 5) / 5 # What are the rounded r,g,b levels for input values.
        gi = round(g * 5) / 5
        bi = round(b * 5) / 5
        # What's the difference?
        rd = r - ri
        gd = g - gi
        bd = b - bi
        # Calculate colors each side of the nearest color.
        r1 = max(r - rd,0.0)
        g1 = max(g - gd,0.0)
        b1 = max(b - bd,0.0)
        r2 = min(r + rd,1.0)
        g2 = min(g + gd,1.0)
        b2 = min(b + bd,1.0)
        # Establish the TWO colors either side of the NEAREST color. When mixed is this closer to the original.
        #v1 = int(round(r1 * 5) * 6 * 6) + int(round(g1 * 5) * 6) + int(round(b1 * 5)) + 16
        #v2 = int(round(r2 * 5) * 6 * 6) + int(round(g2 * 5) * 6) + int(round(b2 * 5)) + 16
        v1 = TextColor.rgbdecimal(r1,g1,b1)
        v2 = TextColor.rgbdecimal(r2,g2,b2)
        return v1, v2
        
    @staticmethod
    def rgbpure(r,g,b):
        """ Take RGB values (scale 0-5) and calculate nearest 256 color scheme value. """
        v = (r * 6 * 6) + (g * 6) + b + 16
        v = v % 256 # Clip for safety.
        return v

    @staticmethod
    def fgbgcolor(fg=7,bg=0,*args,sep=' ',reset=True):
        """ 256 colour mode supported. 
            fg = foreground color (0-255)
            bg = background color (0-255)
            args = unlimited comma separated list of items to print.
            sep = ' ' separator placed between each argument when printed.
            if reset=True, the color is stopped at the end of the text. 
            if reset=False, the color setting remains active after the text. """
        text = TextColor.listtotext(args,sep=sep)
        if TextColor.Mode == 'simple':
            return text
        else:
            if reset: 
                return "\033[38;5;" + str(fg) + "m" + "\033[48;5;" + str(bg) + "m" + text + TextColor.reset() # Stop using this color after the text.
            else:
                return "\033[38;5;" + str(fg) + "m" + "\033[48;5;" + str(bg) + "m" + text # Leave the color active.

    @staticmethod
    def listcolors():
        """ List all colours available. """
        # First list on BLACK background.
        for i in range(0, 16):
            line = ""
            for j in range(0, 16):
                code = i * 16 + j
                line += TextColor.fgbgcolor(code, 0, str(code).rjust(4))
            print (line)
        # Second show BLACK characters on coloured background.
        for i in range(0, 16):
            line = ""
            for j in range(0, 16):
                code = i * 16 + j
                line += TextColor.fgbgcolor(0,code, str(code).rjust(4))
            print (line)
        print (TextColor.reset())
        print (TextColor.black('Black'))
        print (TextColor.red('Red'))
        print (TextColor.green('Green'))
        print (TextColor.blue('Blue'))
        print (TextColor.yellow('Yellow'))
        print (TextColor.aqua('Aqua'))
        print (TextColor.white('White'))
        print (TextColor.magenta('Magenta'))
        print ("termtype",TextColor.get_term_type())

    @staticmethod
    def opposite(colnum,color=False):
        """ Return an opposing color to the proposed one. 
            color = True: Return the 'negative' color. 
            coloer = False: Return BLACK or WHITE. """
        # *Q* Not finished yet.
        if colnum == TextColor.BLACK: oppcol = TextColor.WHITE
        else: oppcol = TextColor.BLACK
        return oppcol

    @staticmethod
    def black(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args,sep=sep)
        if invert:
            return TextColor.fgbgcolor(TextColor.WHITE,TextColor.BLACK,text)
        else:
            return TextColor.fgbgcolor(TextColor.BLACK,TextColor.WHITE,text)

    @staticmethod
    def red(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args,sep=sep)
        if invert:
            return TextColor.fgbgcolor(TextColor.BLACK,TextColor.RED,text)
        else:
            return TextColor.fgbgcolor(TextColor.RED,TextColor.BLACK,text)

    @staticmethod
    def green(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args,sep=sep)
        if invert:
            return TextColor.fgbgcolor(TextColor.BLACK,TextColor.GREEN,text)
        else:
            return TextColor.fgbgcolor(TextColor.GREEN,TextColor.BLACK,text)

    #@staticmethod
    #def yellowxxx(text="",invert=False):
    #    print('yellowxxx is a depricated version of yellow()')
    #    if invert:
    #        return TextColor.fgbgcolor(TextColor.BLACK,TextColor.YELLOW,text)
    #    else:
    #        return TextColor.fgbgcolor(TextColor.YELLOW,TextColor.BLACK,text)

    @staticmethod
    def yellow(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args,sep=sep)
        if invert:
            return TextColor.fgbgcolor(TextColor.BLACK,TextColor.YELLOW,text)
        else:
            return TextColor.fgbgcolor(TextColor.YELLOW,TextColor.BLACK,text)

    @staticmethod
    def yellow4(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args,sep=sep)
        if invert:
            return TextColor.fgbgcolor(TextColor.BLACK,TextColor.YELLOW4,text)
        else:
            return TextColor.fgbgcolor(TextColor.YELLOW4,TextColor.BLACK,text)

    @staticmethod
    def orange(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args,sep=sep)
        if invert:
            return TextColor.fgbgcolor(TextColor.BLACK,TextColor.ORANGE1,text)
        else:
            return TextColor.fgbgcolor(TextColor.ORANGE1,TextColor.BLACK,text)

    @staticmethod
    def blue(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args,sep=sep)
        if invert:
            return TextColor.fgbgcolor(TextColor.BLACK,TextColor.BLUE,text)
        else:
            return TextColor.fgbgcolor(TextColor.BLUE,TextColor.BLACK,text)

    @staticmethod
    def magenta(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args,sep=sep)
        if invert:
            return TextColor.fgbgcolor(TextColor.BLACK,TextColor.MAGENTA,text)
        else:
            return TextColor.fgbgcolor(TextColor.MAGENTA,TextColor.BLACK,text)

    @staticmethod
    def cyan(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args,sep=sep)
        if invert:
            return TextColor.fgbgcolor(TextColor.BLACK,TextColor.CYAN,text)
        else:
            return TextColor.fgbgcolor(TextColor.CYAN,TextColor.BLACK,text)

    @staticmethod
    def aqua(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args,sep=sep)
        if invert:
            return TextColor.fgbgcolor(TextColor.BLACK,TextColor.AQUA,text)
        else:
            return TextColor.fgbgcolor(TextColor.AQUA,TextColor.BLACK,text)

    @staticmethod
    def navy(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args,sep=sep)
        if invert:
            return TextColor.fgbgcolor(TextColor.BLACK,TextColor.NAVY,text)
        else:
            return TextColor.fgbgcolor(TextColor.NAVY,TextColor.BLACK,text)

    @staticmethod
    def teal(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args,sep=sep)
        if invert:
            return TextColor.fgbgcolor(TextColor.BLACK,TextColor.TEAL,text)
        else:
            return TextColor.fgbgcolor(TextColor.TEAL,TextColor.BLACK,text)

    @staticmethod
    def white(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args,sep=sep)
        if invert:
            return TextColor.fgbgcolor(TextColor.BLACK,TextColor.WHITE,text)
        else:
            return TextColor.fgbgcolor(TextColor.WHITE,TextColor.BLACK,text)

    @staticmethod
    def bold(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args,sep=sep)
        return "\033[1m" + text + TextColor.reset()

    @staticmethod
    def underline(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args,sep=sep)
        return "\033[4m" + text + TextColor.reset()

    @staticmethod
    def blink(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args,sep=sep)
        return "\033[5m" + text + TextColor.reset()

    @staticmethod
    def framed(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args,sep=sep)
        return "\033[51m" + text + TextColor.reset()

    @staticmethod
    def reversed(*args,sep=' ',invert=False):
        text = TextColor.listtotext(args)
        return "\033[7m" + text + TextColor.reset()

# ------------------------------------------------------------------------------------------------


# Backward compatibility alias
textcolor = TextColor
