#!/usr/bin/env python3
"""Logging class for the Pilomar project."""

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from datetime import datetime, timedelta, timezone
import os
import traceback
from typing import Optional


class LogFile:
    """An object to maintain a log file recording activities and events.
    
    This writes to a disc file and flushes the write buffers as quickly as it can.
    It can also copy ERROR messages to any nominated error window object
    (which must support a 'Print()' method).
    """

    __version__ = '0.2.0'

    def __init__(
        self,
        filename: str,
        clock_offset: Optional[float] = None,
        flush: bool = False,
        append: bool = True
    ):
        """Initialize the log file.
        
        Args:
            filename: The destination log file path
            clock_offset: Seconds to offset timestamps (for simulation/replay)
            flush: If True, log file writes are immediately flushed to disc
            append: If True, existing log file is appended to; if False, overwrite
        """
        # Set default behaviour of log() method call
        self.default_terminal = True
        self.default_error_prompt = False
        self.default_level = 'info'
        self.default_detail = 'detail'
        self.default_separator = ' '
        self.default_copy_to_window = False
        self.default_show_time = True

        self.filename = filename
        self.clock_offset = clock_offset
        self.prev_log_time = self._now_utc()
        self.error_window = None
        self.error_list = []
        
        # Message filters
        self.detail_filter = ['u', 'f', 'd']  # user, flow, detail
        self.level_filter = ['i', 'w', 'e']  # info, warning, error
        self.fast_flush = flush

        if os.path.exists(filename):
            if append:
                self.Log("LogFile: Appending to existing", filename, terminal=False)
            else:
                os.remove(filename)
                self.Log("LogFile: Overwriting previous", filename, terminal=False)
        else:
            self.Log("LogFile: Starting new", filename, terminal=False)

    def _now_utc(self, real: bool = False) -> datetime:
        """Get system clock as UTC (timezone aware).
        
        Args:
            real: If True, no time offset is applied (true realtime clock value)
                 If False, any time offset is applied
                 
        Returns:
            Current UTC datetime
        """
        dt = datetime.now(timezone.utc)
        if real is False and self.clock_offset is not None:
            dt = dt + timedelta(seconds=self.clock_offset)
        return dt

    def show_config(self):
        """Display current configuration."""
        self.Log("LogFile.show_config(): default_terminal", self.default_terminal)
        self.Log("LogFile.show_config(): default_error_prompt", self.default_error_prompt)
        self.Log("LogFile.show_config(): default_level", self.default_level)
        self.Log("LogFile.show_config(): default_detail", self.default_detail)
        self.Log("LogFile.show_config(): default_separator", self.default_separator)
        self.Log("LogFile.show_config(): default_copy_to_window", self.default_copy_to_window)
        self.Log("LogFile.show_config(): default_show_time", self.default_show_time)
        self.Log("LogFile.show_config(): filename", self.filename)
        self.Log("LogFile.show_config(): clock_offset", self.clock_offset)
        self.Log("LogFile.show_config(): error_window", self.error_window)
        if hasattr(self.error_window, "display_name"):
            self.Log("LogFile.show_config(): error_window.display_name",
                    self.error_window.display_name)

    def Log(self, *args, **kwargs) -> bool:
        """Record a log message.
        
        All unnamed arguments are converted to str type and appended to the line logged.
        
        Args:
            *args: Message components to log
            **kwargs: Optional parameters:
                terminal (bool): Display message to terminal too
                level (str): 'info'/'warning'/'error' - message severity
                detail (str): 'user'/'flow'/'detail' - logging depth
                error_prompt (bool): User must acknowledge error
                sep (str): Separator between arguments (default ' ')
                window: Handle to error window for display
                show_time (bool): Include timestamp in terminal display
                
        Returns:
            Always returns True
        """
        # Establish defaults
        terminal = self.default_terminal
        error_prompt = self.default_error_prompt
        level = self.default_level
        detail = self.default_detail
        separator = self.default_separator
        copy_to_window = self.default_copy_to_window
        show_time = self.default_show_time

        # Process keyword arguments
        for key, value in kwargs.items():
            if key == 'level':
                level = value.lower()
            elif key == 'detail':
                detail = value.lower()
            elif key == 'terminal':
                terminal = value
            elif key == 'errorprompt' or key == 'error_prompt':
                error_prompt = value
            elif key == 'window':
                copy_to_window = value
            elif key == 'sep':
                separator = value
            elif key == 'showtime' or key == 'show_time':
                show_time = value

        # Build the log message
        line = ''
        for x in args:
            if not isinstance(x, str):
                x = str(x)
            line = (line + separator + x).strip()

        if error_prompt:
            terminal = True

        # Write message to log file
        dt_now = self._now_utc()
        elapsed = (dt_now - self.prev_log_time).total_seconds()
        elapsed_str = "{:.6f}".format(elapsed)
        save_line = str(dt_now) + "\t" + elapsed_str + "\t" + line
        
        if show_time:
            print_line = str(dt_now).split(".")[0] + " " + line
        else:
            print_line = line

        # Apply filters
        if level[0] in self.level_filter and detail[0] in self.detail_filter:
            with open(self.filename, 'a') as f:
                f.write(save_line + '\n')
                if self.fast_flush:
                    f.flush()
                    os.fsync(f)

        # Handle display and user response
        if level[0] == 'e':  # Error
            if terminal:
                self.error_list.append(print_line)
                print('** ERROR ** reported in LogFile: ' + print_line)
                if error_prompt:
                    input("Press [ENTER] to continue: ")
            if self.error_window is not None:
                # Will need textcolor module
                self.error_window.Print(print_line)
        elif level[0] == 'w':  # Warning
            if terminal:
                print('WARNING: reported in LogFile: ' + print_line)
                if error_prompt:
                    input("Press [ENTER] to continue: ")
            if self.error_window is not None and copy_to_window:
                self.error_window.Print(print_line)
        elif terminal:
            print(print_line)
            if self.error_window is not None and copy_to_window:
                self.error_window.Print(print_line)

        self.prev_log_time = self._now_utc()
        return True

    def report_exception(self, e: Exception, level: str = 'error', comment: str = None):
        """Record any exception class in the log file.
        
        This does not terminate, it just reports/logs the exception
        then allows the program to continue.
        
        Args:
            e: Exception object
            level: Log level for the exception
            comment: Optional additional comment
        """
        self.Log("LogFile.report_exception(): Error", str(e), level='error')
        self.record_traceback(e)
        if hasattr(e, '__dict__'):
            for key, value in e.__dict__.items():
                self.Log("LogFile.report_exception():", key, ":", value, level=level)
        else:
            self.Log(
                "LogFile.report_exception(): No __dict__ object to report. (",
                type(e),
                ")",
                level='error'
            )
        if comment is not None:
            self.Log("LogFile.report_exception(): Comment:", str(comment), level=level)

    def raise_exception(self, e: Exception, level: str = 'error', comment: str = None):
        """Record any exception class in the log file then terminate.
        
        Args:
            e: Exception object
            level: Log level for the exception
            comment: Optional additional comment
            
        Raises:
            Exception: Always raises to terminate program
        """
        self.record_traceback(e)
        if hasattr(e, '__dict__'):
            for key, value in e.__dict__.items():
                self.Log("LogFile.raise_exception():", key, ":", value, level=level)
        else:
            self.Log(
                "LogFile.raise_exception(): No __dict__ object to report. (",
                type(e),
                ")",
                level='error'
            )
        if comment is not None:
            self.Log("LogFile.raise_exception(): Comment:", str(comment), level=level)
        raise Exception('Program exception raised') from e

    def record_traceback(self, e: Exception, terminal: bool = True):
        """Use Traceback module to report the execution stack to the log file.
        
        Args:
            e: Exception object
            terminal: If False, prevents error being displayed on screen
        """
        self.Log("LogFile.record_traceback(): Error Message", str(e), terminal=terminal)
        a = traceback.format_exc()
        b = a.split('\n')
        for c in b:
            self.Log("LogFile.record_traceback():", c, terminal=terminal)

    def unique_filename(self, filename: str) -> str:
        """Given a filename, create a unique version of it.
        
        Appends '.1', '.2', '.3' etc until finding an unused name.
        
        Args:
            filename: Base filename
            
        Returns:
            Unique filename
        """
        file_elements = filename.split('.')
        unique_filename = filename + ".err"
        counter = 0
        
        while True:
            counter += 1
            if counter > 100:
                self.Log(
                    "LogFile.unique_filename(",
                    filename,
                    "). Exhausted allowed range of names.",
                    level='error'
                )
                break
            unique_filename = (
                file_elements[0] + "_" + str(counter) + '.' + file_elements[1]
            )
            if not os.path.exists(unique_filename):
                break
                
        return unique_filename
