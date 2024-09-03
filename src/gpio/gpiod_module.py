#!/usr/bin/python

# Raspberry Pi GPIO library.
# Presents an interface to the GPIO handlers on the Raspberry Pi SBCs.
# - Different classes can be built to handle different GPIO handlers,
#   but all should present the same interface to the calling programs.

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

try:
  import gpiod  # Handling IO signals. If available.

  GPIOchip = gpiod.Chip("/dev/gpiochip0")
  print("Using GPIOD")
except ModuleNotFoundError:
  print("No GPIO driver available.")
  pass

from pilomar import MainLog

def cleanup_gpio():
  """Perform cleanup at end of session."""
  for pin in InputPinGPIO.InputPins:
    pin.line.release()
  for pin in OutputPinGPIO.OutputPins:
    pin.line.release()

class InputPinGPIO:
  """Wrapper for GPIOD input pin.
  Allows different GPIO libraries to be implemented by hiding the actual implementation behind these methods.
  Pin can be declared as None in which case it's a non-functional device.

  """

  InputPins = []  # List of all defined input pins.
  __library__ = "GPIOD"  # Which GPIO library does this support?
  __version__ = "0.0.0"  # What version of the library is this?

  def __init__(self, pinbcm, name=None, pull="up", enabled=True, invert=False):
    """Define a GPIO input pin.

    The purpose is to present a common interface to an I/O pin regardless of the underlying
    GPIO package being used. You can create alternative classes which interact with different
    packages and present the same interface to the program.

    pinbcm = the BCM pin number.
    name is an optional name for the pin.
    pull = GPIO.PUD_UP for pull up (default HIGH/ON),
         GPIO.PUD_DOWN for pull down. (default LOW/OFF)
    enabled = initial enabled(True)/disabled(False) state of the pin.
    invert = False: IsOn returns TRUE for HIGH signal.
            IsOff returns TRUE for a LOW signal.
         True:  IsOn returns TRUE for LOW signal.
            IsOff returns TRUE for a HIGH signal.

    if pinbcm is None then this is a fake input.
    it behaves as a GPIO input, but doesn't actually link to a GPIO port and always returns the PULL UP/DOWN value.
    """
    self.pin = pinbcm  # The BCM number of the pin.
    self.name = name  # A reference name of the pin.
    self.pull = pull  # Is this a PULL_UP or PULL_DOWN input.
    self.invert = invert  # IsOn/IsOff methods invert their value. is_high/is_low remain unchanged.
    if self.pin is not None:
      self.enabled = enabled
    else:
      self.enabled = False  # Dummy pins are always disabled.
    # Set the PULL UP / DOWN config for the input.
    if pull == "up":
      self.state = True  # Initial state HIGH.
    else:
      self.state = False  # Initial state LOW.
    # If it's a real pin, set it up through GPIO.

    if self.pin is not None:
      if pull == "up":
        config = {
          pinbcm: gpiod.LineSettings(
            direction=gpiod.line.Direction.INPUT,
            bias=gpiod.line.Bias.PULL_UP,
          )
        }
        self.line = GPIOchip.request_lines(config)  # Will EARTH when triggered.
      else:
        config = {
          pinbcm: gpiod.LineSettings(
            direction=gpiod.line.Direction.INPUT,
            bias=gpiod.line.Bias.PULL_DOWN,
          )
        }
        self.line = GPIOchip.request_lines(
          config
        )  # Will go HIGH when triggered.
    # Append to the global list of all input pins.
    InputPinGPIO.InputPins.append(self)  # Add to list of input pins.

  def refresh(self):
    """Get and store the current state of the pin.
    GPIO.input() returns 0 = Low, 1 = High.
    Convert to 0 = False, 1 = True
    DISABLED pins always return False (electrical LOW).
    If you want the logical state of the pin after this use IsOn() and IsOff() methods.
    If you want the physical state of the pin after this use is_high() and is_low() methods.
    """
    if self.enabled and self.line.get_value(self.pin) != 0:
      self.state = True  # High
    else:
      self.state = False  # Low

  def is_high(self):
    """Return TRUE if input is HIGH.
    This is the true electrical state of the pin.
    It does NOT respect the self.invert flag, use IsOn() for that."""
    self.refresh()  # Get current electrical state of the pin.
    return self.state  # Return True/False.

  def is_low(self):
    """Return TRUE if input is LOW.
    This is the true electrical state of the pin.
    It does NOT respect the self.invert flag, use IsOff() for that."""
    self.refresh()  # Get current electrical state of the pin.
    return not self.state  # Return True/False.

  def is_on(self):
    """Return ON/OFF state of the input, respecting the 'invert' flag.
    If you want the true electrical state of the pin use self.is_high()"""
    result = self.is_high()
    if self.invert:
      result = not result
    return result  # Return True/False.

  def is_off(self):
    """Return ON/OFF state of the input, respecting the 'invert' flag.
    If you want the true electrical state of the pin use self.is_low()"""
    result = self.is_low()
    if self.invert:
      result = not result
    return result  # Return True/False.

  def enable(self):
    """Enable the pin and set the output accordingly.
    Can only enable real GPIO pins."""
    if self.pin is not None:
      self.enabled = True  # Can only enable if it's a real pin.
    self.refresh()  # Get current electrical state of the pin.

  def disable(self):
    """Disable the pin and set the state to LOW."""
    self.enabled = False
    self.refresh()  # Get current electrical state of the pin.

  def status(self):
    """Return a string describing the current status of the pin."""
    temp = (
      "GPIOD: BCM:"
      + str(self.pin)
      + ", INPUT:"
      + " Ena:"
      + str(self.enabled).rjust(5)
      + " Inv:"
      + str(self.invert).rjust(5)
      + " IsOn:"
      + str(self.is_on()).rjust(5)
      + " IsOff:"
      + str(self.is_off()).rjust(5)
      + " is_high:"
      + str(self.is_high()).rjust(5)
      + " is_low:"
      + str(self.is_low()).rjust(5)
    )
    return temp

class OutputPinGPIO:
  """Define a GPIO output pin.

    The purpose is to present a common interface to an I/O pin regardless of the underlying
    GPIO package being used. You can create alternative classes which interact with different
    packages and present the same interface to the program.


  Allows different GPIO libraries to be implemented by hiding the actual implementation behind these methods.
  PIN can be declared as None, in which case it's a non-functional device."""

  OutputPins = []  # List of defined pins.
  __library__ = "GPIOD"  # Which GPIO library does this support?
  __version__ = "0.0.0"  # What version of the library is this?

  @staticmethod
  def release_all():
    """Release all defined pins."""
    for pin in OutputPinGPIO.OutputPins:
      try:
        pin.line.release()
      except Exception as excep:
        MainLog.Log(
          "OutputPinGPIO.release_all(): Failed to release pin:",
          excep,
          level="error",
        )

  def __init__(self, pinbcm:int, name:str, enabled:bool=True, state:bool=False, invert:bool=False):
    """Create a new pin.
    pinbcm is the BCM number of the GPIO pin.
    name is a compulsory unique name for the pin.
    enabled = initial enabled/disabled condition of the pin.
    state = initial on(True)/off(False) condition of the pin.
    invert = Switch HIGH/LOW electrical states for the on/off status."""
    self.pin = pinbcm
    self.enabled = enabled
    self.name = name
    self.state = state
    self.invert = invert
    config = {pinbcm: gpiod.LineSettings(direction=gpiod.line.Direction.OUTPUT)}
    self.ine = GPIOchip.request_lines(config)  # Will EARTH when triggered.
    OutputPinGPIO.OutputPins.append(
      self
    )  # Add this output to the list of defined pins.
    self.refresh()

  def on(self):
    """
    Set the output pin to the ON state.
    """
    self.state = True
    self.refresh()

  def off(self):
    """
    Set the output pin to the OFF state.
    """
    self.state = False
    self.refresh()

  def refresh(self):
    """
    Reset the output pin to the current
    """
    if self.enabled and self.state:
      self.line.set_value(self.pin, gpiod.line.Value.ACTIVE)  # High
    else:
      self.line.set_value(self.pin, gpiod.line.Value.INACTIVE)  # Low

  def is_on(self):
    """Return ON/OFF state of the input, respecting the 'invert' flag.
    If you want the true electrical state of the pin use self.is_high()"""
    result = self.is_high()
    if self.invert:
      result = not result
    return result  # Return True/False.

  def is_off(self):
    """Return ON/OFF state of the input, respecting the 'invert' flag.
    If you want the true electrical state of the pin use self.is_low()"""
    result = self.is_low()
    if self.invert:
      result = not result
    return result  # Return True/False.

  def is_high(self):
    """Return TRUE if the pin is HIGH.
    The true electrical state of the pin.
    Does not respect self.invert flag.
    To respect self.invert, use IsOn()/IsOff()"""
    if self.ine.get_value(self.pin) != 0:
      result = True  # The true electrical state of the pin.
    # if GPIO.input(self.pin) != 0: result = True # The true electrical state of the pin.
    else:
      result = False
    return result

  def is_low(self):
    """Return TRUE if the pin is LOW.
    The true electrical state of the pin.
    Does not respect self.invert flag.
    To respect self.invert, use IsOn()/IsOff()"""
    if self.ine.get_value(self.pin) != 0:
      result = False  # The true electrical state of the pin.
    # if GPIO.input(self.pin) != 0: result = False # The true electrical state of the pin.
    else:
      result = True
    return result

  def enable(self):
    """
    Enable the pin.
    """
    self.enabled = True
    self.refresh()

  def disable(self):
    """
    Disable the pin.
    """
    self.enabled = False
    self.refresh()

  def status(self):
    """Return a string describing the current status of the pin."""
    temp = (
      "GPIOD: BCM:"
      + str(self.pin)
      + ", OUTPUT:"
      + " Ena:"
      + str(self.enabled).rjust(5)
      + " Inv:"
      + str(self.invert).rjust(5)
      + " IsOn:"
      + str(self.is_on()).rjust(5)
      + " IsOff:"
      + str(self.is_off()).rjust(5)
      + " is_high:"
      + str(self.is_high()).rjust(5)
      + " is_low:"
      + str(self.is_low()).rjust(5)
    )
    return temp
