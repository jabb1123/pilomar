#!/usr/bin/python

# timer class for use in Pilomar project.

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
import threading  # To use the Event.wait() method as a non-blocking wait function.


class ProgressTimer:
  """
  Simple progress timer, provide a target count, a starting point and a current count.
  It will maintain the % complete and estimated completion time.
  
  :param name: Any name for this instance.
  :type name: str
  
  :param target: The value that's considered to be 100% complete.
  :type target: int
  
  :param start: The value that's considered to be 0% complete, defaults to 0
  :type start: int
  
  :param initial: The initial count if the process has already begun, defaults to None
  :type initial: int  
  """

  def __init__(self, name, target, start=0, initial=None):
    """Constructor method
    """
    self.name = name
    self.start = start  # Value representing 0%
    if initial is not None:
      self.current = initial  # Current value.
    else:
      self.current = start  # Current value.
    self.target = target  # Value representing 100%
    self.start_time = datetime.now(timezone.utc)

  def update_count(self, count:int):
    """Update the current count.

    :param count: The new count value.
    :type count: int
    """
    self.current = count

  def get_total_seconds(self) -> float:
    """How many seconds will the entire run take?
    
    :return: Total seconds to complete the process.
    :rtype: float
    """
    temp = self.current - self.start
    if temp != 0:  # Progress has begun.
      totalseconds = (
        (datetime.now(timezone.utc) - self.start_time).total_seconds()
        * 100
        / self.get_percent()
      )
    else:
      totalseconds = 0
    return totalseconds

  def get_eta(self)->datetime:
    """Return UTC timestamp when process will be completed.
    
    :return: UTC timestamp when process will be completed.
    :rtype: datetime
    """
    temp = self.get_total_seconds()
    if temp != 0:  # Progress has begun.
      eta = self.start_time + timedelta(seconds=temp)
    else:
      eta = self.start_time
    return eta

  def get_percent(self)->float:
    """How many % complete is the process?
    
    :return: % complete.
    :rtype: float
    """
    return 100 * (self.current - self.start) / (self.target - self.start)


class Timer:  # 14 references.
  """Clock driven timer class.
  This can be polled periodically to see if a timer is due.

  Arguments:
  :param period: Number of seconds that the timer should run for. (It will repeat!)
  :type period: int
  
  :param offset: An initial additional delay before the timer starts.
  :type offset: int
  
  :param skip: If the timer expires multiple times before being checked the extra events are ignored
  :type skip: bool
  
  Example:
    mytimer = timer(20) # Create a timer for 20 seconds.
    ...
    if mytimer.due(): # 20 seconds has elapsed.
      ...
  """

  def __init__(self, period: int, offset: int = 0, skip: bool = True):
    """Constructor method
    """
    if period < 1:
      self.period = 1
    else:
      self.period = period
    if offset == 0:
      self.next_trigger = self.now_utc() + timedelta(seconds=self.period)
    else:
      self.next_trigger = self.now_utc() + timedelta(seconds=offset)
    self.skip_events = skip  # If the timer falls behind, do we skip missed events?
    self.force_trigger = False  # When set to True, the .Due() method returns True regardless of timing.
    # Used to force an event.

  def now_utc(self) -> datetime:  # Many references.
    """Get system clock as UTC (timezone aware)
    Microcontroller and Skyfield are operated in UTC vales.
    All clock-times used in this program use the UTC timestamped clock.
    This should be the only reference to datetime.now() method in the entire
    module. All other uses should refer to this NowUTC() function.
    
    :return: UTC timestamp.
    :rtype: datetime
    """
    # Not adapted to support ClockOffset because timer clock is entirely internal.
    return datetime.now(timezone.utc)

  def set_next_trigger(self):
    """Update the trigger due time to the next occurrence.
    The next due time depends upon the skip parameter too!"""
    if self.skip_events:  # Skip any missed events.
      while self.next_trigger <= self.now_utc():
        self.next_trigger = self.next_trigger + timedelta(seconds=self.period)
    else:  # Don't skip missed events, process every one!
      self.next_trigger = self.next_trigger + timedelta(seconds=self.period)
    self.force_trigger = (
      False  # If the previous trigger was forced, reset that status now.
    )

  def elapsed(self) -> bool:
    """Return number of seconds that have elapsed since the timer was set.
    
    :return: Number of seconds that have elapsed since the timer was set.
    :rtype: float
    """
    starttime = self.next_trigger - timedelta(seconds=self.period)
    elapsed = (self.now_utc() - starttime).total_seconds()
    return elapsed

  def elapsed_pc(self) -> float:
    """Return % of time elapsed.
    
    :return: % of time elapsed.
    :rtype: float
    """
    result = round(100 * self.elapsed() / self.period, 0)
    return result

  def remaining(self) -> float:
    """Return number of seconds remaining on a timer.
    
    :return: Number of seconds remaining on a timer.
    :rtype: float
    """
    result = (self.next_trigger - self.now_utc()).total_seconds()
    if result < 0.0:
      result = 0.0  # Timer expired.
    return result

  def due(self) -> bool:
    """If timed event is due, this returns TRUE. Otherwise returns FALSE.
    It automatically sets the next due timestamp.
    
    :return: If timed event is due, this returns TRUE. Otherwise returns FALSE.
    :rtype: bool
    """
    if self.next_trigger < self.now_utc() or self.force_trigger:
      result = True
      self.set_next_trigger()
    else:
      result = False
    return result

  def wait(self) -> bool:
    """Wait for timer to expire.
    The thread cannot do anything else while waiting for this.
    
    :return: True if the timer has expired.
    :rtype: bool
    """
    # NOTE: If you're expecting the clock to change out of DST, this may last longer than you think!
    while self.due() is False:
      t = self.remaining()
      if t > 0:
        # RPi5B - Non-blocking wait function.
        event = threading.Event()
        event.wait(t)
        # time.sleep(t) # RPi4B - Blocking wait!
    return True

  # def Wait(self) -> bool:
  #    """ Wait for timer to expire.
  #        The thread cannot do anything else while waiting for this. """
  #    while self.Due() == False:
  #        t = self.Remaining()
  #        if t > 0:
  #            time.sleep(t)
  #    return True

  def restart(self) -> bool:
    """Use this to reset the timer clock.
    This will abandon the current countdown and
    restart it from the current moment.
    If multiple events are overdue for this trigger they are dropped.
    
    :return: True if the timer has been reset.
    :rtype: bool
    """
    self.next_trigger = self.now_utc() + timedelta(seconds=self.period)
    self.force_trigger = (
      False  # If the previous trigger was forced, reset that status now.
    )
    return True

  def trigger(self) -> bool:
    """Use this to trigger the timer.
    This will force the next .Due() call to return TRUE and then reset the timer.
    This is for cases where you want to override the timer.
    
    :return: True if the timer has been triggered.
    :rtype: bool
    """
    self.force_trigger = True
    return True
