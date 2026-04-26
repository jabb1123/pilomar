#!/usr/bin/env python3
"""Timer classes for the Pilomar project."""

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import threading
from datetime import datetime, timedelta

from pilomar.core.time_utils import now_utc


class ProgressTimer:
    """Simple progress timer for tracking completion of long-running tasks.

    Provide a target count, a starting point and a current count.
    It will maintain the % complete and estimated completion time.
    """

    def __init__(self, name: str, target: int, start: int = 0, initial: int = 0):
        """Initialize progress timer.

        Args:
            name: Any name for this instance
            target: The value that's considered to be 100% complete
            start: The value that's considered to be 0% complete
            initial: The initial count if the process has already begun
        """
        self.name = name
        self.start = start
        self.current = initial if initial != start else start
        self.target = target
        self.start_time = now_utc()

    def increment(self, step: int = 1):
        """Increment current count."""
        self.current += step

    def update_count(self, count: int):
        """Update current count to new value."""
        self.current = count

    def get_total_seconds(self) -> float:
        """Calculate how many seconds the entire run will take."""
        temp = self.current - self.start
        if temp != 0:
            total_seconds = (now_utc() - self.start_time).total_seconds() * 100 / self.get_percent()
        else:
            total_seconds = 0
        return total_seconds

    def get_eta(self) -> datetime:
        """Return UTC timestamp when process will be completed."""
        temp = self.get_total_seconds()
        if temp != 0:
            eta = self.start_time + timedelta(seconds=temp)
        else:
            eta = self.start_time
        return eta

    def remaining_seconds(self) -> int:
        """Calculate how many seconds are left."""
        ts = int(round((self.get_eta() - now_utc()).total_seconds(), 0))
        return ts

    def seconds_to_hms(self, value: float) -> str:
        """Convert seconds to hh:mm:ss format string.

        Args:
            value: Number of seconds

         Returns:
            Formatted time string
        """
        if value < 0:
            sign = "-"
        else:
            sign = ""
        value = int(round(abs(value), 0))
        ss = value % 60
        value = value // 60
        mm = value % 60
        value = value // 60
        hh = value % 24
        value = value // 24
        if value > 0:
            dy = str(value) + "d "
        else:
            dy = ""
        return (
            sign
            + dy
            + str(hh).rjust(2, "0")
            + ":"
            + str(mm).rjust(2, "0")
            + ":"
            + str(ss).rjust(2, "0")
        )

    def get_percent(self) -> float:
        """Calculate how many % complete the process is."""
        return 100 * (self.current - self.start) / (self.target - self.start)

    def units_per_second(self) -> float:
        """Calculate the 'speed' of progress."""
        elapsed = (now_utc() - self.start_time).total_seconds()
        if elapsed != 0:
            return float(self.current) / elapsed
        else:
            return 0.0

    def seconds_per_unit(self) -> float:
        """Calculate the time to progress 1 unit."""
        elapsed = (now_utc() - self.start_time).total_seconds()
        if self.current != 0:
            return elapsed / float(self.current)
        else:
            return 0.0


class Timer:
    """Clock driven timer class that can be polled periodically.

    Example:
        my_timer = Timer(20)  # Create a timer for 20 seconds
        ...
        if my_timer.due():  # 20 seconds has elapsed
            ...
    """

    def __init__(self, period: int, offset: int = 0, skip: bool = True):
        """Create the timer object and set the timer parameters.

        Args:
            period: Number of seconds between events (minimum 1)
            offset: Number of seconds earlier/later than first due time
            skip: If timer is late, just trigger once then reset for next
                 future due time. If False, queued events will all trigger.
        """
        if period < 1:
            self.period: int = 1
        else:
            self.period: int = period

        if offset == 0:
            self.next_trigger: datetime = now_utc() + timedelta(seconds=self.period)
        else:
            self.next_trigger: datetime = now_utc() + timedelta(seconds=offset)

        self.skip_events: bool = skip
        self.force_trigger: bool = False

    def _set_next_trigger(self):
        """Update the trigger due time to the next occurrence."""
        if self.skip_events:
            while self.next_trigger <= now_utc():
                self.next_trigger = self.next_trigger + timedelta(seconds=self.period)
        else:
            self.next_trigger = self.next_trigger + timedelta(seconds=self.period)
        self.force_trigger = False

    def elapsed(self) -> float:
        """Return number of seconds that have elapsed since the timer was set."""
        start_time = self.next_trigger - timedelta(seconds=self.period)
        elapsed = (now_utc() - start_time).total_seconds()
        return elapsed

    def elapsed_percent(self) -> float:
        """Return % of time elapsed."""
        result = round(100 * self.elapsed() / self.period, 0)
        return result

    def remaining(self) -> float:
        """Return number of seconds remaining on a timer."""
        result = (self.next_trigger - now_utc()).total_seconds()
        if result < 0.0:
            result = 0.0
        return result

    def due(self) -> bool:
        """Check if timed event is due.

        Returns:
            True if event is due, False otherwise.
            Automatically sets the next due timestamp.
        """
        if self.next_trigger < now_utc() or self.force_trigger:
            result = True
            self._set_next_trigger()
        else:
            result = False
        return result

    def wait(self) -> bool:
        """Wait for timer to expire.

        The thread will block while waiting.

        Returns:
            True when timer expires
        """
        while not self.due():
            t = self.remaining()
            if t > 0:
                event = threading.Event()
                event.wait(t)
        return True

    def restart(self) -> bool:
        """Reset the timer clock.

        This will abandon the current countdown and restart it from the
        current moment. If multiple events are overdue for this trigger
        they are dropped.

        Returns:
            True
        """
        self.next_trigger = now_utc() + timedelta(seconds=self.period)
        self.force_trigger = False
        return True

    def trigger(self) -> bool:
        """Force the timer to trigger.

        This will force the next due() call to return True and then reset
        the timer. Use this when you want to override the timer.

        Returns:
            True
        """
        self.force_trigger = True
        return True
