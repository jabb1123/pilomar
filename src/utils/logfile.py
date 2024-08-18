#!/usr/bin/python

# Pilomar's logging class.

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# 09.Dec.2023 Added PackageSearchResult() function to help with analysing functionality.

from datetime import datetime, timedelta, timezone
from utils.textcolor import TextColor
import os  # OS Command execution
import traceback  # Used to record the stacktrace if recording an error.


class LogFile:  # 2 references.
  """An object to maintain a log file recording the activities and events in the program.
  This writes to a disc file and flushes the write buffers as quickly as it can.
  It can also copy ERROR messages to any nominated error window object (which must support a 'Print()' method. )
  """

  __version__ = "0.1.1"

  def __init__(self, filename: str, clockoffset=None, flush:bool=False, append:bool=True):
    """filename is the destination log file.
    clockoffset (seconds) is used by now_utc() method to create offset timestamps.
    flush : False. Log file writes are flushed to disc efficiently and more slowly by the OS.
             But there's a risk that you lose the last few messages in a catastrophic failure.
        True. Log file writes are immediately flushed to disc. Hits the SD card hard!
            But there's less risk of losing the last few messages if something bad happens.
    append: True.  Existing log file is appended to.
        False. Fresh log file is started."""
    self.filename = filename
    self.clock_offset = clockoffset  # Can establish a clock offset when replicating/simulating specific situations.
    self.prev_log_time = self.now_utc()
    self.error_window = None  # Reference to window object for displaying errors. Must offer a 'Print()' method.
    self.error_list = (
      []
    )  # Maintain list of any errors raised. These can then be summarised and reported if needed.
    # The following filters specify which types of messages are logged.
    # - If you change these lists, some messages may be ignored from file and displays.
    self.detail_filter = [
      "u",
      "f",
      "d",
    ]  # Specify the detail levels that are recorded (user choices, flow, detail).
    self.level_filter = [
      "i",
      "w",
      "e",
    ]  # Specify which message types are recorded (info, warning, error).
    self.fast_flush = False  # If TRUE all writes to the log file are immediately flushed. Hits the SD card hard!
    if os.path.exists(filename):
      if append:
        self.log("LogFile: Appending to existing", filename, terminal=False)
      else:
        os.remove(filename)  # Remove previous filename.
        self.log("LogFile: Overwriting previous", filename, terminal=False)
    else:
      self.log("LogFile: Starting new", filename, terminal=False)

  # def now_utc(self) -> datetime: # Many references.
  #    """ Get system clock as UTC (timezone aware)
  #        Microcontroller and Skyfield are operated in UTC vales.
  #        All clock-times used in this program use the UTC timestamped clock.
  #        This should be the only reference to datetime.now() method in the entire
  #        module. All other uses should refer to this now_utc() function.
  #        """
  #    return datetime.now(timezone.utc)

  def now_utc(self, real=False) -> datetime:  # Many references.
    """Get system clock as UTC (timezone aware)
    Microcontroller and Skyfield are operated in UTC vales.
    All clock-times used in this program use the UTC timestamped clock.
    This should be the only reference to datetime.now() method in the entire
    program. All other uses should refer to this now_utc() function.
    real=True means that no time offset is applied, you get the true realtime clock value.
    real=False means that any time offset is applied, making the clock run at some other point in time.
    """
    dt = datetime.now(timezone.utc)  # Offset supported.
    if real is False and self.clock_offset is not None:  # Can apply time offset.
      dt = dt + timedelta(seconds=self.clock_offset)
    return dt

  def log(self, *args, **kwargs) -> bool:
    """Record a log message.
    All unnamed arguments are converted to str type and appended to the line logged.
    Some named arguments are supported.
    terminal=True ... displays the message to the terminal too.
    level='info'/'warning'/'error' specifies level of information.
        (warning and error are repeated to the terminal automatically)
    detail='user'/'flow'/'detail' specifies the depth of logging that is recorded.
        (user means user choices)
        (flow means high level flow of the program, main logic events)
        (detail means detailed flow of the program, decisions, calculations etc)
    errorprompt=The user is required to acknowledge the error message.
    sep=Separator string inserted between each argument appended to the log message. Default is ' '.
    """
    # Establish defaults for other arguments.
    terminal = True  # Display to the user.
    errorprompt = False  # Ask user to acknowledge.
    level = "info"  # Establish log level.
    detail = "detail"  # Establish the level of detail this entry represents.
    separator = " "
    copytowindow = False
    for key, value in kwargs.items():
      if key == "level":
        level = value.lower()  # info, warning or error?
      elif key == "detail":
        detail = value.lower()  # user, flow, detail message types recorded.
      elif key == "terminal":
        terminal = value  # Display to the user or not?
      elif key == "errorprompt":
        errorprompt = value
      elif key == "window":
        copytowindow = (
          value  # Copy the message to the error window if possible.
        )
      elif key == "sep":
        separator = value  # Separator string can be overridden.
    # Now generate the log message by appending all the unnamed arguments into a single string.
    line = ""
    for x in args:  # Convert and append extra arguments.
      if not isinstance(x, str):
        x = str(x)
      line = (line + separator + x).strip()
    if errorprompt:
      terminal = (
        True  # User must see message if they are supposed to acknowledge it.
      )
    # Write the message to the log file.
    dtNow = self.now_utc()
    Elapsed = (
      dtNow - self.prev_log_time
    ).total_seconds()  # The log message includes the elapsed time since the previous message.
    ES = "{:.6f}".format(
      Elapsed
    )  # 6dp and make sure it is not in scientific notation.
    saveline = (
      str(dtNow) + "\t" + ES + "\t" + line
    )  # Add current system timestamp and elapsed time to message.
    printline = (
      str(dtNow).split(".")[0] + " " + line
    )  # Add current system timestamp to message.
    # Check if any LEVEL OR DETAIL filters are specified in the received parameters.
    if (
      level[0] in self.level_filter and detail[0] in self.detail_filter
    ):  # The filters pass the criteria for writing to disc.
      with open(self.filename, "a", encoding="utf-8") as f:
        f.write(saveline + "\n")
        if self.fast_flush:  # Update the disc immediately.
          f.flush()  # Immediately flush to disc.
          os.fsync(f)  # Flush in the OS too!
    # Handle the display and user response.
    if level[0] == "e":  # Error
      if terminal:  # We're allowed to display on the terminal.
        self.error_list.append(
          printline
        )  # Record the error for later summary or reporting.
        print(TextColor.red("** ERROR ** reported in LogFile: ") + printline)
        if errorprompt:  # User has to acknowledge the error.
          # temp = input(textcolor.cyan("Press [ENTER] to continue: "))
          input(TextColor.cyan("Press [ENTER] to continue: "))
      if self.error_window is not None:
        self.error_window.Print(
          printline, fg=TextColor.RED, bg=TextColor.BLACK
        )  # Error color.
    elif level[0] == "w":
      if terminal:  # We're allowed to display on the terminal.
        print(TextColor.yellow("WARNING: reported in LogFile: ") + printline)
        if errorprompt:  # User has to acknowledge the warning.
          # temp = input(textcolor.cyan("Press [ENTER] to continue: "))
          input(TextColor.cyan("Press [ENTER] to continue: "))
      if self.error_window is not None and copytowindow:
        self.error_window.Print(
          printline, fg=TextColor.YELLOW, bg=TextColor.BLACK
        )  # Warning color.
    elif terminal:  # Display to the terminal.
      print(printline)
      if self.error_window is not None and copytowindow:
        self.error_window.Print(
          printline
        )  # Info lines just keep default color scheme.
    self.prev_log_time = (
      self.now_utc()
    )  # Note the last time a message was logged. This is used to report the elapsed time between messages in log file.
    return True

  def report_slow_events(self, limit=4.0):  ### DEVELOPMENT ###
    """Analyses the log file and reports any events which have taken too long."""
    print("Analysing log file for slow events")
    with open(self.filename, "r", encoding="UTF-8") as f:
      prevline = ""
      for line in f:
        thisline = line.strip()
        lineitems = thisline.split("\t")
        if len(lineitems) > 2 and isinstance(lineitems[1], float):
          delay = float(lineitems[1])
          if delay >= limit:  # Delay found.
            print("Delay", delay, ":-")
            print(prevline)
            print(thisline)
        prevline = thisline
    print("Analysis complete")

  def report_exception(self, e, level="error", comment=None):
    """Record any exception class in the log file.
    This does not terminate, it just reports/logs the
    exception then allows the program to continue."""
    self.log("LogFile.report_exception(): Error", str(e), level="error")
    self.record_traceback(e)
    if hasattr(
      e, "__dict__"
    ):  # The exception object has a dictionary that can be reported.
      for key, value in e.__dict__.items():
        self.log("LogFile.report_exception():", key, ":", value, level=level)
    else:
      self.log(
        "LogFile.report_exception(): No __dict__ object to report. (",
        type(e),
        ")",
        level="error",
      )
    if comment is not None:
      self.log("LogFile.report_exception(): Comment:", str(comment), level=level)

  def raise_exception(self, e, level="error", comment=None):
    """Record any exception class in the log file.
    Then terminate via regular exception handler."""
    self.record_traceback(e)
    if hasattr(
      e, "__dict__"
    ):  # The exception object has a dictionary that can be reported.
      for key, value in e.__dict__.items():
        self.log("LogFile.raise_exception():", key, ":", value, level=level)
    else:
      self.log(
        "LogFile.raise_exception(): No __dict__ object to report. (",
        type(e),
        ")",
        level="error",
      )
    if comment is not None:
      self.log("LogFile.raise_exception(): Comment:", str(comment), level=level)
    raise Exception(
      "Program exception raised"
    ) from e  # Terminate through regular exception stack.

  def record_traceback(self, e, terminal=True):
    """Use Traceback module to report the execution stack to the log file.
    Setting terminal=False prevents the error being displayed on the screen."""
    self.log("LogFile.record_traceback(): ErrorMessage", str(e), terminal=terminal)
    a = traceback.format_exc()  # String representation of stack report.
    b = a.split("\n")
    for c in b:
      self.log("LogFile.record_traceback():", c, terminal=terminal)

  def unique_filename(self, filename):
    """Given a filename, create a unique version of it.
    This appends '.1', '.2', '.3' etc to the filename until it finds
    an unused name."""
    fileelements = filename.split(".")
    uniquefilename = (
      filename + ".err"
    )  # Something's gone wrong if this makes it through!
    available = False
    counter = 0
    while True:
      counter += 1  # Try next available filename.
      if counter > 100:
        self.log(
          "LogFile.unique_filename(",
          filename,
          "). Exhausted allowed range of names.",
          level="error",
        )
        break
      uniquefilename = (
        fileelements[0] + "_" + str(counter) + "." + fileelements[1]
      )  # bla/bla/bla/bla/filename_{count}.filetype
      if not os.path.exists(uniquefilename):  # The name is unused.
        break
    return uniquefilename

  # def PackageSearchResultXXX(self,searchterms,ignorecase=False):
  #    """ Generate a ZIP file with a selection of entries from the current log file.
  #        searchterms = the selection phrase for grep.
  #            Examples: "RPi received|RPi queueing" - Lists lines containing either phrase.
  #        Returns a ZIP filename. """
  #    path = os.path.dirname(self.filename)
  #    timestamp = str(self.now_utc())
  #    for c in ['-',':','.',' ']:
  #        timestamp = timestamp.replace(c,'')
  #    timestamp = timestamp.split('+')[0]
  #    resultfile = os.path.join(path,'result_' + timestamp + '.log')
  #    zipfile = os.path.join(path,'result_' + timestamp + '.zip')
  #    self.log("LogFile.PackageSearchResult(",searchterms,") Begin.",terminal=False)
  #    if ignorecase:
  #        # -a : Treat file as text.
  #        # -i : ignore case.
  #        cmd = 'egrep -a -i "' + searchterms + '" ' + self.filename + '>' + resultfile
  #    else:
  #        cmd = 'egrep -a "' + searchterms + '" ' + self.filename + '>' + resultfile
  #    self.log("LogFile.PackageSearchResult:",cmd,terminal=False)
  #    os.system(cmd)
  #    cmd = 'zip ' + zipfile + ' ' + resultfile
  #    self.log("LogFile.PackageSearchResult:",cmd,terminal=False)
  #    os.system(cmd)
  #    return zipfile

  def PackageSearchResult(self, searchterms, ignorecase=False):
    """Generate a ZIP file with a selection of entries from the current log file.
    searchterms = the selection phrase for grep.
      Examples: "RPi received|RPi queueing" - Lists lines containing either phrase.
    Returns a ZIP filename."""
    resultfile = self.unique_filename(self.filename)
    zipfile = resultfile.split(".")[0] + ".zip"
    self.log(
      "LogFile.PackageSearchResult(", searchterms, ") Begin.", terminal=False
    )
    if ignorecase:
      # -a : Treat file as text.
      # -i : ignore case.
      cmd = (
        'egrep -a -i "' + searchterms + '" ' + self.filename + ">" + resultfile
      )
    else:
      cmd = 'egrep -a "' + searchterms + '" ' + self.filename + ">" + resultfile
    self.log("LogFile.PackageSearchResult:", cmd, terminal=False)
    os.system(cmd)
    cmd = "zip " + zipfile + " " + resultfile
    self.log("LogFile.PackageSearchResult:", cmd, terminal=False)
    os.system(cmd)
    return zipfile


#
