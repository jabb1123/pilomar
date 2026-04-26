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

# Sentinel values for the output parameter
_OUTPUT_NONE = "none"
_OUTPUT_TERMINAL = "terminal"


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

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _run(self, cmd: str, output: str) -> tuple[list[str], int]:
        """Run *cmd* in a shell, capture stdout+stderr, and dispatch output.

        Args:
            cmd: Shell command to execute.
            output: One of ``'none'``, ``'terminal'``, or a file path to
                append command output to.  Any value other than the two
                sentinel strings is treated as a file path.

        Returns:
            ``(lines, returncode)`` where *lines* is the list of stdout lines
            and *returncode* is the process exit code (0 = success).
        """
        if self.log is not None:
            self.log(cmd, terminal=False)

        self.last_error = None

        result = subprocess.run(
            cmd,
            shell=True,  # noqa: S602
            capture_output=True,
            text=True,
        )
        returncode = result.returncode

        if returncode != 0:
            self.last_error = result
            if self.log is not None:
                self.log(
                    f"OsCommand._run({cmd!r}) exit={returncode}",
                    terminal=False,
                )
                if result.stdout:
                    self.log(f"  stdout: {result.stdout.rstrip()}", terminal=False)
                if result.stderr:
                    self.log(f"  stderr: {result.stderr.rstrip()}", terminal=False)

        lines = result.stdout.split("\n")

        # Determine output destination
        is_file = output not in (_OUTPUT_NONE, _OUTPUT_TERMINAL)

        for line in lines:
            if is_file:
                with open(output, "a") as f:
                    f.write(line + "\n")
            if output == _OUTPUT_TERMINAL:
                print(line)
            if self.log is not None:
                self.log(f"cmd output '{line}'", terminal=False)

        self.last_output = lines
        self.return_code = returncode
        return lines, returncode

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, cmd: str, output: str = "none") -> list[str]:
        """Execute a command and return its output lines.

        Args:
            cmd: Shell command to execute.
            output: Output destination — ``'terminal'``, ``'none'`` (default),
                or a file path to append output to.

        Returns:
            List of output lines from the command.
        """
        lines, _ = self._run(cmd, output)
        return lines

    def execute_code(self, cmd: str, output: str = "none") -> int:
        """Execute a command and return its exit code.

        Args:
            cmd: Shell command to execute.
            output: Output destination — ``'terminal'``, ``'none'`` (default),
                or a file path to append output to.

        Returns:
            Exit code (0 = success, non-zero = error).
        """
        _, returncode = self._run(cmd, output)
        return returncode
