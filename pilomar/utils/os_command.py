#!/usr/bin/env python3
"""Class to execute OS commands, return command output, exit code and/or log output."""

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import locale
import subprocess

from pilomar.core.base import AttributeMaster


class OsCommand(AttributeMaster):
    """Object to execute OS commands."""

    @staticmethod
    def delocalize(text: str) -> str:
        """Convert text from locale number format to standardized en_US format.

        The parent program must have already set the locale environment before calling this:
            import locale
            locale.setlocale(locale.LC_ALL, '')  # Get user's locale

        Args:
            text: Text to convert

        Returns:
            Converted text with standardized number format
        """
        text = text.strip()
        text = locale.delocalize(text)
        return text

    def __init__(self, logger=None):
        """Initialize OS command executor.

        Args:
            logger: Optional logger instance or Log method reference
        """
        self.set_logger(logger)
        self.last_error = None
        self.return_code = 0
        self.last_output = []

    def execute(self, cmd: str, output: str = "none") -> list[str]:
        """Execute a command and record it to the log file.

        Command and result are always recorded in the log file.
        This should be thread safe.

        Args:
            cmd: Shell command to execute
            output: Output destination:
                   'terminal' - Display to terminal
                   'none' - Suppress output (default)
                   filename - Output is written to that file

        Returns:
            List of output lines from the command
        """
        if self.log is not None:
            self.log(cmd, terminal=False)

        self.last_error = None
        returncode = 0

        try:
            result = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode(
                "utf-8"
            )
        except subprocess.CalledProcessError as e:
            self.last_error = e
            returncode = e.returncode
            if self.log is not None:
                self.log(f"OsCommand.execute({cmd}) returned {e}", terminal=False)
                self.log(
                    f"OsCommand.execute({cmd}) returned returncode {e.returncode}",
                    terminal=False,
                )
                self.log(
                    f"OsCommand.execute({cmd}) returned output {e.output}",
                    terminal=False,
                )
                self.log(f"OsCommand.execute({cmd}) returned cmd {e.cmd}", terminal=False)
                self.log(
                    f"OsCommand.execute({cmd}) returned stdout {e.stdout}",
                    terminal=False,
                )
                self.log(
                    f"OsCommand.execute({cmd}) returned stderr {e.stderr}",
                    terminal=False,
                )
            result = ""

        lines = result.split("\n")
        returnlist = []

        for line in lines:
            if "." in output:  # Assume output is a disc file
                with open(output, "a") as f:
                    f.write(line + "\n")
            if output == "terminal":
                print(line)
            if self.log is not None:
                self.log(f"cmd output '{line}'", terminal=False)
            returnlist.append(line)

        self.last_output = returnlist
        self.return_code = returncode
        return returnlist

    def execute_code(self, cmd: str, output: str = "none") -> int:
        """Execute a command and return the exit code.

        Command and result are always recorded in the log file.
        This should be thread safe.

        Args:
            cmd: Shell command to execute
            output: Output destination:
                   'terminal' - Display to terminal
                   'none' - Suppress output (default)
                   filename - Output is written to that file

        Returns:
            Return code (0 = Success, non-zero = error)
        """
        if self.log is not None:
            self.log(cmd, terminal=False)

        self.last_error = None
        returncode = 0

        try:
            result = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode(
                "utf-8"
            )
        except subprocess.CalledProcessError as e:
            self.last_error = e
            if self.log is not None:
                self.log(f"OsCommand.execute_code({cmd}) returned {e}", terminal=False)
                self.log(
                    f"OsCommand.execute_code({cmd}) returned returncode {e.returncode}",
                    terminal=False,
                )
                self.log(
                    f"OsCommand.execute_code({cmd}) returned output {e.output}",
                    terminal=False,
                )
                self.log(
                    f"OsCommand.execute_code({cmd}) returned cmd {e.cmd}",
                    terminal=False,
                )
                self.log(
                    f"OsCommand.execute_code({cmd}) returned stdout {e.stdout}",
                    terminal=False,
                )
                self.log(
                    f"OsCommand.execute_code({cmd}) returned stderr {e.stderr}",
                    terminal=False,
                )
            returncode = e.returncode
            result = ""

        returnlist = []
        lines = result.split("\n")

        for line in lines:
            if "." in output:
                with open(output, "a") as f:
                    f.write(line + "\n")
            if output == "terminal":
                print(line)
            if self.log is not None:
                self.log(f"cmd output '{line}'", terminal=False)
            returnlist.append(line)

        self.last_output = returnlist
        self.return_code = returncode
        return returncode
